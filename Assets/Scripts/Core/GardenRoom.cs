using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 後花園：背景、花圃、回店裡的門，還有沿著柵欄外那條石板路經過的村民。
    /// 由 PlayerController 進 garden 場景時呼叫 Ensure()。
    ///
    /// 兩個版本，用 <see cref="UsePixelGarden"/> 切：
    ///   true  ── 8-bit 重畫的圍牆花園（tools/gen_garden_art.py → rooms/garden8*、Data/GardenRoomData）：
    ///            四面圍牆走不出去（PlayerController 用 GardenRoomData.Walk 當地板多邊形、開碰撞與 y 排序），
    ///            前面兩道矮牆是另一張前景圖（女巫走到牆後面會被遮住腳）、樹與雨水桶照腳底排序並登記成障礙；
    ///            花圃一塊一格、位置玩家自己擺（按 R 進 GardenArrange 拖曳；位置存 witch.garden.layout，見 GardenLayout）；
    ///            圍牆外一圈奶油色小路，路人（GardenFolk）在上面隨機散步、偶爾走出畫面再回來。
    ///   false ── 舊的整張圖（rooms/garden）、固定的 4×3 花圃（GardenData.PlotPos）、夾矩形、柵欄外的路人。
    ///
    /// 操作只有**一顆 E 鍵** —— 看花圃現在是什麼狀態決定做什麼：
    ///   枯死了 → 清掉　空地 → 挑種子種下　開花了 → 收成　其他 → 澆水
    /// </summary>
    public class GardenRoom : MonoBehaviour
    {
        /// <summary>
        /// 開關：true ＝ 8-bit 圍牆花園＋可自由擺的花圃；false ＝ 退回舊圖與舊行為（舊圖沒刪）。
        /// 改這裡就好，PlayerController／Garden.WaterTargets／GardenData.GardenToShop 都看它。
        /// </summary>
        public static readonly bool UsePixelGarden = true;

        public static GardenRoom Instance { get; private set; }

        public static GardenRoom Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("GardenRoom").AddComponent<GardenRoom>();
        }

        /// <summary>玩家離花圃多近才操作得到。</summary>
        const float Reach = 90f;

        readonly List<GardenPlot> plots = new();
        /// <summary>場上的花圃（只有已開墾的）。GardenArrange 拖曳時用。</summary>
        public IReadOnlyList<GardenPlot> Plots => plots;
        Transform player;

        void Awake() { Instance = this; GameArt.Preload(); }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;

            if (UsePixelGarden) BuildPixelGarden();
            else ApplyBackground();
            BuildPlots();
            BuildDoor();
            if (UsePixelGarden)
            {
                // 按 R 搬花圃；圍牆外的小路上有路人隨機散步（GardenFolk，路網來自 GardenRoomData）
                GardenArrange.Ensure();
                GardenFolk.Ensure();
            }
            else
            {
                // 柵欄外經過的村民（路窄，兩個就夠熱鬧）。舊花園沒開 Obstacles，用 polyline 模式：
                // 只沿 FenceWalk 相鄰兩點走，不會兩點直線切進柵欄裡（見 GardenData.FenceWalk）。
                TownFolk.Ensure(GardenData.FenceWalk, 2, polyline: true);
            }
        }

        /// <summary>
        /// 8-bit 圍牆花園：底圖、前景牆、圍牆內的裝飾（照腳底排序、登記成障礙）。
        /// ⚠️ 障礙要在 Obstacles.Begin（PlayerController.Awake）之後登記 —— 這裡是 Start，沒問題。
        /// 缺圖時退回舊底圖（碰撞照新的走，至少不會走出去）。
        /// </summary>
        void BuildPixelGarden()
        {
            var bg = LoadArt(GardenRoomData.Background);
            if (bg == null)
            {
                Debug.LogWarning($"[GardenRoom] 沒有 8-bit 底圖 {GardenRoomData.Background}（跑 tools/gen_garden_art.py），先用舊圖");
                ApplyBackground();
            }
            else AddArt("GardenArt", bg, Vector2.zero, GardenRoomData.BgOrder);

            // 鏡頭的範圍改成新底圖的大小（場景檔的 Ground 是舊圖，比新圖小 —— 不改的話新圖的邊緣永遠拍不到）。
            // 這裡是 Start：CameraFollow.Awake 已經照 Ground 量過一次，這一行蓋掉它。
            var follow = Camera.main != null ? Camera.main.GetComponent<CameraFollow>() : null;
            if (follow != null)
                follow.ClampTo(new Rect(-GardenRoomData.ImgW / 2f, -GardenRoomData.ImgH / 2f, GardenRoomData.ImgW, GardenRoomData.ImgH));

            // 底圖之上的三張圖層（後景：後牆＋小屋、前牆、小路外側的樹叢），排序見 GardenRoomData 與 GardenFolk。
            // 底圖本身已經是完整畫面 —— 圖層缺了只會讓路人／女巫的前後關係錯，不會破洞。
            foreach (var l in GardenRoomData.Layers)
            {
                var sp = LoadArt(l.Sprite);
                if (sp != null) AddArt("layer-" + l.Sprite, sp, new Vector2(l.X, l.Y), l.Order);
                else Debug.LogWarning($"[GardenRoom] 沒有圖層 {l.Sprite}（跑 tools/gen_garden_art.py）");
            }

            foreach (var d in GardenRoomData.Decor)
            {
                var sp = LoadArt(d.Sprite);
                if (sp != null) AddArt("decor-" + d.Name, sp, new Vector2(d.X, d.Y), d.Order);
                Obstacles.AddEllipse(d.Name, new Vector2(d.Cx, d.Cy), new Vector2(d.Hx, d.Hy), "garden_decor");
            }
        }

        static Sprite LoadArt(string path)
        {
            var t = Resources.Load<Texture2D>(path);
            return t != null ? SheetSlicer.Whole(t) : null;     // 樞紐在中心、PPU 1
        }

        void AddArt(string name, Sprite sp, Vector2 at, int order)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform);
            go.transform.position = new Vector3(at.x, at.y, 0f);
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = order;
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
                // 8-bit 花園：位置是玩家擺的格（GardenLayout）；舊花園：固定的 4×3 排法
                plot.Init(i, UsePixelGarden ? GardenLayout.PosOf(i) : GardenData.PlotPos(i));
                plots.Add(plot);

                // 提示與按 E 交給共用的互動系統（2026-11-28）：每塊花圃自己一個，最近的那塊冒提示、吃 E（同以前的「最近那塊」）。
                // 搬花圃中（GardenArrange）、開著面板時 Interact 整個暫停。
                var it = Interactable.Attach(go, Reach, () => Act(plot), () => PlotLook(plot));
                it.anchor = plot.HintAnchor;
                plot.interactable = it;
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
            if (UsePixelGarden)
            {
                // 提示／E 的範圍收成跟自動觸發一樣大（同店裡的門）：花圃可以擺到門邊，
                // 兩個感應圈重疊的話「按 E 澆水」會順便把人送回店裡。
                d.autoRange = GardenRoomData.DoorRange;
                d.interactRange = GardenRoomData.DoorRange;
            }
        }

        // ──────────── 提示：一塊花圃四種狀態各一張圖 ────────────

        /// <summary>
        /// [E][圖]：枯死 → 鐮刀；空地 → 種子（背包沒種子 → 鍵帽變暗，按了照舊「沒有種子」）；
        /// 盛開 → 那朵花自己的道具圖；其他 → 澆花器。
        /// </summary>
        HintLook PlotLook(GardenPlot plot)
        {
            var v = Garden.View(plot.index);
            if (v.Dead) return HintLook.E(HintIcons.Ui("act_clear"), "按 E 清掉枯枝");
            if (v.Empty)
            {
                var seeds = UI.SeedPicker.SeedsInBag();
                var icon = HintIcons.Item(seeds.Count > 0 ? seeds[0] : GardenData.Flowers[0].Seed);
                return HintLook.E(icon, "按 E 種下種子", dim: seeds.Count == 0);
            }
            if (v.Ripe) return HintLook.E(HintIcons.Item(FlowerOfArt(v.Art)) ?? HintIcons.Ui("act_done"), "按 E 收成");
            return HintLook.E(HintIcons.Ui("act_water"), "按 E 澆水");
        }

        static string FlowerOfArt(string art)
        {
            foreach (var f in GardenData.Flowers) if (f.Art == art) return f.Flower;
            return null;
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
                if (Garden.Clear(plot.index)) { Sfx.Play("gather"); plot.PopIcon(HintIcons.Ui("act_clear"), null, null, "清掉了枯枝"); }
            }
            else if (v.Empty)
            {
                // 有哪幾種種子讓玩家自己挑（面板是 modal，挑完才回來種）
                if (UI.SeedPicker.SeedsInBag().Count == 0) { Sfx.Play("deny"); plot.PopIcon(HintIcons.Item(GardenData.Flowers[0].Seed), null, HintIcons.Ui("st_no"), "沒有種子…"); return; }
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
                    Sfx.Play("harvest");
                    plot.PopIcon(HintIcons.Item(got.Value.Name), $"×{got.Value.Count}", null, $"＋{got.Value.Name} ×{got.Value.Count}");
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
                Sfx.Play("water");
                plot.PopIcon(HintIcons.Items8("water-drop"), n > 1 ? $"×{n}" : null, null, n > 1 ? $"澆了 {n} 塊" : "澆好水了");

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
                Sfx.Play("deny");
                plot.PopIcon(HintIcons.Items8("water-drop"), null, HintIcons.Ui("st_no"), "救不回來了…");
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
            Sfx.Play("plant");
            plot.PopIcon(HintIcons.Item(seed), null, null, $"種下 {seed}");
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

        /// <summary>第 index 塊花圃的物件（還沒開墾的回 null）。</summary>
        public GardenPlot FindPlot(int index) => PlotAt(index);

        GardenPlot PlotAt(int index)
        {
            foreach (var p in plots) if (p.index == index) return p;
            return null;
        }
    }
}
