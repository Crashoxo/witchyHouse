using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 後花園：背景、花圃、回店裡的門，還有沿著柵欄外那條石板路經過的村民。
    /// 由 PlayerController 進 garden 場景時呼叫 Ensure()。
    ///
    /// 操作只有**一顆 E 鍵** —— 看花圃現在是什麼狀態決定做什麼：
    ///   枯死了 → 清掉　空地 → 挑種子種下　開花了 → 收成　其他 → 澆水
    /// </summary>
    public class GardenRoom : MonoBehaviour
    {
        public static GardenRoom Instance { get; private set; }

        public static GardenRoom Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("GardenRoom").AddComponent<GardenRoom>();
        }

        /// <summary>玩家離花圃多近才操作得到。</summary>
        const float Reach = 90f;

        readonly List<GardenPlot> plots = new();
        Transform player;
        GardenPlot active;
        GameObject hint;

        void Awake() { Instance = this; GameArt.Preload(); }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;

            ApplyBackground();
            BuildPlots();
            BuildDoor();
            BuildHint();
            TownFolk.Ensure(GardenData.FenceWalk, 2);   // 柵欄外經過的村民（路窄，兩個就夠熱鬧）
        }

        void ApplyBackground()
        {
            var sp = GameArt.GardenRoom;
            if (sp == null) { Debug.LogWarning("[GardenRoom] 沒有後花園底圖 rooms/garden"); return; }
            var go = new GameObject("GardenArt");
            go.transform.SetParent(transform);
            go.transform.position = Vector3.zero;
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = -10000;
        }

        /// <summary>只做「已開墾」的那幾塊；其餘還是荒地（要在店裡升級花圃）。</summary>
        void BuildPlots()
        {
            foreach (var i in Garden.UnlockedPlots())
            {
                var go = new GameObject($"Plot{i}");
                go.transform.SetParent(transform);
                var plot = go.AddComponent<GardenPlot>();
                plot.Init(i, GardenData.PlotPos(i));
                plots.Add(plot);
            }
        }

        void BuildDoor()
        {
            var go = new GameObject("ShopDoor");
            go.transform.SetParent(transform);
            go.transform.position = new Vector3(GardenData.GardenToShop.x, GardenData.GardenToShop.y, 0f);
            var d = go.AddComponent<SceneDoor>();
            d.targetScene = "shop";
            d.hintText = "回店裡";
        }

        void Update()
        {
            if (player == null || UIState.ModalOpen)
            {
                if (hint != null) hint.SetActive(false);
                return;
            }

            // 找最近的那塊花圃（在伸手範圍內）
            active = null;
            float best = Reach;
            foreach (var p in plots)
            {
                float d = Vector2.Distance(player.position, p.transform.position);
                if (d < best) { best = d; active = p; }
            }

            UpdateHint();

            if (active != null && Input.GetKeyDown(KeyCode.E)) Act(active);
        }

        // ──────────── 一顆 E 鍵做四件事 ────────────

        void Act(GardenPlot plot)
        {
            var v = Garden.View(plot.index);
            var anim = player != null ? player.GetComponent<CharacterAnimator>() : null;
            float faceX = player != null ? plot.transform.position.x - player.position.x : 0f;
            int dir = DirTo(plot);

            if (v.Dead)
            {
                if (Garden.Clear(plot.index)) plot.Popup("清掉了枯枝");
            }
            else if (v.Empty)
            {
                // 有哪幾種種子讓玩家自己挑（面板是 modal，挑完才回來種）
                if (UI.SeedPicker.SeedsInBag().Count == 0) { plot.Popup("沒有種子…"); return; }
                UI.SeedPicker.Ensure().Open(seed => PlantSeed(plot, seed));
                return;                      // 面板關掉後才會真的種
            }
            else if (v.Ripe)
            {
                var got = Garden.Harvest(plot.index);
                if (got != null)
                {
                    Inventory.Add(got.Value.Name, got.Value.Count);
                    DailyLog.RecordGather(got.Value.Count);
                    QuestLog.Record(ObjKind.Gather, got.Value.Name, got.Value.Count);
                    anim?.PlayOneShot(GameArt.PickFrames(dir), 0.9f, faceX, true, dir);
                    plot.Popup($"＋{got.Value.Name} ×{got.Value.Count}");
                }
            }
            else
            {
                Water(plot, anim, faceX, dir);
            }
            plot.Refresh();
        }

        /// <summary>
        /// 澆水。澆水壺升級後一次澆得到旁邊幾塊（Garden.WaterTargets 算範圍）。
        /// 空地也會被澆濕（土變深色），但只有「有種東西」的才算進訊息裡。
        /// </summary>
        void Water(GardenPlot plot, CharacterAnimator anim, float faceX, int dir)
        {
            int n = 0;
            var watered = new List<int>();
            foreach (var i in Garden.WaterTargets(plot.index))
            {
                bool planted = !Garden.View(i).Empty;
                if (Garden.Water(i)) { watered.Add(i); if (planted) n++; }
            }

            if (n > 0)
            {
                // 澆水借施法那組八方向的圖 → 直接挑「朝花圃」的那個方向，人會轉過去澆
                anim?.PlayOneShot(GameArt.WaterFrames(dir), 0.9f, faceX, false, dir);
                plot.Popup(n > 1 ? $"澆了 {n} 塊" : "澆好水了");

                // 灑水特效：水從她手上澆花器的壺口出來，澆到的每一塊都來一份
                var spout = SpoutPos(plot);
                foreach (var i in watered)
                {
                    var p = PlotAt(i);
                    if (p == null) continue;
                    p.PlayWater(spout.x - p.transform.position.x, spout.y - p.transform.position.y);
                }
            }
            else
            {
                plot.Popup("救不回來了…");
            }

            foreach (var p in plots) p.Refresh();   // 波及到的花圃也要跟著換濕土
        }

        /// <summary>挑好種子之後真的種下去（面板已經關掉了）。</summary>
        void PlantSeed(GardenPlot plot, string seed)
        {
            if (!Garden.View(plot.index).Empty) return;        // 挑的時候狀態變了就算了
            if (!Inventory.Remove(seed, 1)) return;
            if (!Garden.Plant(plot.index, seed))
            {
                Inventory.Add(seed, 1);                        // 種不下去要把種子還回去
                return;
            }
            var anim = player != null ? player.GetComponent<CharacterAnimator>() : null;
            float faceX = player != null ? plot.transform.position.x - player.position.x : 0f;
            anim?.PlayOneShot(GameArt.PickFrames(DirTo(plot)), 0.7f, faceX, true, DirTo(plot));
            plot.Popup($"種下 {seed}");
            plot.Refresh();
        }

        // ──────────── 小工具 ────────────

        int DirTo(GardenPlot plot)
        {
            if (player == null) return WitchDir.South;
            return CharacterAnimator.DirOf(plot.transform.position.x - player.position.x,
                                           plot.transform.position.y - player.position.y);
        }

        /// <summary>女巫手上澆花器壺口的大概位置（灑水特效從這裡出發）。</summary>
        Vector2 SpoutPos(GardenPlot toward)
        {
            if (player == null) return Vector2.zero;
            var p = (Vector2)player.position;
            if (toward == null) return p + new Vector2(0f, 40f);
            var d = ((Vector2)toward.transform.position - p).normalized;
            return p + d * 26f + new Vector2(0f, 40f);
        }

        GardenPlot PlotAt(int index)
        {
            foreach (var p in plots) if (p.index == index) return p;
            return null;
        }

        // ──────────── 提示 ────────────

        void BuildHint()
        {
            hint = new GameObject("plot-hint");
            var tm = hint.AddComponent<TextMesh>();
            tm.fontSize = 36;
            tm.characterSize = 4.5f;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.color = new Color32(255, 244, 214, 255);
            var font = UI.CjkFont.Get();
            if (font != null)
            {
                tm.font = font;
                hint.GetComponent<MeshRenderer>().material = font.material;
            }
            hint.GetComponent<MeshRenderer>().sortingOrder = 9400;
            hint.SetActive(false);
        }

        void UpdateHint()
        {
            if (hint == null) return;
            if (active == null) { hint.SetActive(false); return; }

            var v = Garden.View(active.index);
            string msg = v.Dead ? "按 E 清掉枯枝"
                       : v.Empty ? "按 E 種下種子"
                       : v.Ripe ? "按 E 收成"
                       : "按 E 澆水";

            hint.GetComponent<TextMesh>().text = msg;
            hint.transform.position = active.transform.position + new Vector3(0f, 64f, 0f);
            hint.SetActive(true);
        }
    }
}
