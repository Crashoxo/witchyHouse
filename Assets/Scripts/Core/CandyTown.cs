using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 糖果鎮：森林北邊那張地圖。地面、建築、裝飾、三位 NPC、街上晃來晃去的
    /// 軟糖鱷與薑餅人，全部依 Data.Candy 生出來。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版的 CandyTown.ts 幾乎什麼都不做（只把商品清單交給場景裡的商店節點），
    /// 因為地圖與房子**都是 candy.scene 裡的真節點** —— 使用者要能在 Cocos 編輯器裡
    /// 自己拖。這邊沒有那個場景檔，但 Data.Candy 裡的座標是完整的（那份資料本來就是
    /// 早期用來生成的），所以改成全部由這支生出來，結果一樣。
    ///
    /// 進出是「走到地圖邊界」：森林北側 → 糖果鎮、糖果鎮南側 → 森林，
    /// 兩邊都登記在 Data.Portals，PortalGlow 會在那個點畫光圈。
    /// </summary>
    public class CandyTown : MonoBehaviour
    {
        public static CandyTown Instance { get; private set; }

        public static CandyTown Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("CandyTown").AddComponent<CandyTown>();
        }

        /// <summary>⚠️ NPC 與建築的圖在 art/candy/（不是 candy/）—— 那批在 Cocos 是場景節點用的。</summary>
        const string ArtDir = "art/candy/";

        /// <summary>同時最多幾隻街上晃的小動物。</summary>
        const int CritterCount = 6;

        /// <summary>
        /// 停點在路點附近的隨機偏移（全寬，x / y）。偏移後的點要過 TownNav.GoodStop（站得住）才用。
        /// tools/check_npc_paths.py 會讀這個值。
        /// </summary>
        static readonly Vector2 StopJitter = new(120f, 80f);
        /// <summary>兩隻的停點至少隔多遠（px）。</summary>
        const float MinSpacing = 28f;

        /// <summary>
        /// 街上晃的一隻小動物。走法跟城鎮村民（TownFolk）同一套：挑停點 → TownNav 求路（繞過糖果屋、樹、灌木）→
        /// 沿路點走 → 停一下。路只在挑新目的地時算一次，一幀最多替一隻算。
        /// </summary>
        class Walker
        {
            public GameObject Node;
            public float Speed;
            public float Pause;
            public SpriteRenderer Sr;
            public readonly List<Vector2> Path = new(32);   // 重用
            public int PathIdx;
            public Vector2 Goal;
            public bool NeedPath, KeepGoal;
            public int PathVer;
        }

        readonly List<Walker> critters = new();
        int planCursor;

        void Awake() { Instance = this; GameArt.Preload(); }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            foreach (var w in critters) TownNav.Unregister(w.Path);
        }

        void Start()
        {
            GameArt.OnReady(Build);
        }

        void Build()
        {
            SpawnProps();
            SpawnNpcs();
            // 建築與裝飾是這時才擺出來的 → 玩家碰撞的障礙清單要重掃（建得比這裡早的話會漏掉）。
            // ⚠️ 要在 SpawnCritters 之前：小動物的出生點要問 TownNav（站不站得住），它的格圖建在這份障礙上。
            Obstacles.MarkDirty();
            TownNav.Prefer(null);          // 糖果鎮整張都是鋪面、路點又稀，不分路面草地
            RegisterNpcAvoid();
            SpawnCritters();
        }

        /// <summary>
        /// 中央薄荷糖噴泉的位置與半徑（地面圖 art/ground/candy 量的：粉白圓盤 x、y 都是 −98..98）。
        /// 噴泉是畫在地面裡的，玩家可以踩上去（Obstacles 沒有它）；小動物要繞開，不然看起來是從噴泉中間穿過去。
        /// tools/check_npc_paths.py 會讀這兩個值。
        /// </summary>
        static readonly Vector2 Fountain = new(0f, 0f);
        const float FountainR = 98f;
        /// <summary>站著的 NPC 腳底要讓開多大一圈（NPC 沒有落地範圍，玩家也能穿過去；小動物繞一下比較像樣）。</summary>
        const float NpcAvoidR = 16f;

        /// <summary>只擋小動物、不擋玩家的圓：噴泉 ＋ 三位 NPC 的腳底（見 TownNav.Avoid）。</summary>
        static void RegisterNpcAvoid()
        {
            var c = new Vector2[Candy.Npcs.Length + 1];
            var r = new float[c.Length];
            c[0] = Fountain; r[0] = FountainR;
            for (int i = 0; i < Candy.Npcs.Length; i++)
            {
                c[i + 1] = new Vector2(Candy.Npcs[i].X, Candy.Npcs[i].Y);
                r[i + 1] = NpcAvoidR;
            }
            TownNav.Avoid(c, r);
        }

        // ──────────── 建築與裝飾 ────────────

        void SpawnProps()
        {
            var buildings = new GameObject("Buildings");
            buildings.transform.SetParent(transform);
            foreach (var b in Candy.Buildings)
                Place(b.Art, b.X, b.Y, b.Scale, buildings.transform);

            var props = new GameObject("Props");
            props.transform.SetParent(transform);
            foreach (var p in Candy.Props)
                Place(p.Art, p.X, p.Y, p.Scale, props.transform);
        }

        /// <summary>
        /// 擺一張圖，錨點在腳底（跟村民、家具同一套）—— position 就是「站在地上那一點」，
        /// YSort 才排得對。
        /// </summary>
        GameObject Place(string art, float x, float y, float scale, Transform parent)
        {
            var sp = Resources.Load<Sprite>(ArtDir + art);
            if (sp == null) { Debug.LogWarning($"[CandyTown] 找不到 {ArtDir}{art}"); return null; }

            var go = new GameObject(art);
            go.transform.SetParent(parent);
            go.transform.position = new Vector3(x, y, 0f);

            var artGo = new GameObject("art");
            artGo.transform.SetParent(go.transform, false);
            artGo.transform.localScale = new Vector3(scale, scale, 1f);
            artGo.transform.localPosition = new Vector3(0f, sp.rect.height * 0.5f * scale, 0f);

            var sr = artGo.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = Mathf.RoundToInt(-y);
            return go;
        }

        // ──────────── NPC ────────────

        void SpawnNpcs()
        {
            var box = new GameObject("Npcs");
            box.transform.SetParent(transform);

            foreach (var n in Candy.Npcs)
            {
                var go = Place(n.Art, n.X, n.Y, n.Scale, box.transform);
                if (go == null) continue;
                go.name = n.Id;

                var talk = go.AddComponent<TalkNpc>();
                talk.npcName = n.Name;
                talk.lines = n.Lines;
                talk.portrait = "";              // 糖果鎮的角色沒有頭像立繪
                talk.interactRange = 200f;
                // 有店名的就兼賣東西：聊完會問「要看看貨嗎」（見 TalkNpc.shopTitle 的說明，
                // 刻意不做成第二個按 E 的觸發點，那樣兩個感應圈會搶同一顆 E）
                talk.shopTitle = n.ShopTitle ?? "";
            }
        }

        // ──────────── 街上晃來晃去的小動物 ────────────

        void SpawnCritters()
        {
            var box = new GameObject("Critters");
            box.transform.SetParent(transform);

            for (int i = 0; i < CritterCount && i < Candy.Critters.Length; i++)
            {
                var c = Candy.Critters[i];
                var sp = GameArt.CandyArt(c.Art);
                if (sp == null) continue;

                var self = new Walker
                {
                    Speed = 34f + Random.value * 26f,
                    Pause = Random.value * 3f,
                    NeedPath = true,
                };
                var start = PickStop(self);        // 出生點也要站得住（不能生在糖果屋裡）
                self.Goal = start;
                var go = new GameObject("critter-" + c.Art);
                go.transform.SetParent(box.transform);
                go.transform.position = new Vector3(start.x, start.y, 0f);

                var artGo = new GameObject("art");
                artGo.transform.SetParent(go.transform, false);
                artGo.transform.localScale = new Vector3(c.Scale, c.Scale, 1f);
                artGo.transform.localPosition = new Vector3(0f, sp.rect.height * 0.5f * c.Scale, 0f);
                var sr = artGo.AddComponent<SpriteRenderer>();
                sr.sprite = sp;

                // 腳下的影子（go 的 position 就是落腳點）
                ShadowLayer.Follow(go.transform, sp.rect.width * c.Scale);

                self.Node = go; self.Sr = sr;
                critters.Add(self);
                TownNav.Register(self.Path);
            }
        }

        /// <summary>p 附近（MinSpacing 內）有沒有別隻的停點。</summary>
        bool Crowded(Vector2 p, Walker self)
        {
            foreach (var o in critters)
                if (o != self && (o.Goal - p).sqrMagnitude < MinSpacing * MinSpacing) return true;
            return false;
        }

        /// <summary>
        /// 挑一個停點：隨機路點（吸附到站得住的位置）＋偏移，要站得住、不跟別隻的停點疊在一起；
        /// 試幾次都不行就用吸附後的路點本身。
        /// </summary>
        Vector2 PickStop(Walker self)
        {
            for (int t = 0; t < 6; t++)
            {
                var b = TownNav.Snap(Candy.Walk[Random.Range(0, Candy.Walk.Length)]);
                var p = new Vector2(b.x + (Random.value - 0.5f) * StopJitter.x,
                                    b.y + (Random.value - 0.5f) * StopJitter.y);
                if (TownNav.GoodStop(p) && !Crowded(p, self)) return p;
            }
            return TownNav.Snap(Candy.Walk[Random.Range(0, Candy.Walk.Length)]);
        }

        /// <summary>替一隻算下一段路（一幀最多叫一次）。走不到就換目的地，都不行就原地再站一下 —— 不退回直線。</summary>
        void Plan(Walker w, int ver)
        {
            var p = (Vector2)w.Node.transform.position;
            w.PathIdx = 0;
            if (w.KeepGoal)
            {
                w.KeepGoal = false;
                if (TownNav.Find(p, w.Goal, w.Path)) { w.PathVer = ver; w.NeedPath = false; return; }
            }
            for (int t = 0; t < 4; t++)
            {
                var goal = PickStop(w);
                if (TownNav.Find(p, goal, w.Path))
                {
                    w.Goal = w.Path.Count > 0 ? w.Path[w.Path.Count - 1] : goal;
                    w.PathVer = ver;
                    w.NeedPath = false;
                    return;
                }
            }
            w.Path.Clear();
            w.Goal = p;
            w.Pause = 1f + Random.value;
        }

        void Update()
        {
            if (UIState.ModalOpen) return;
            float dt = Time.deltaTime;
            if (critters.Count == 0 || !TownNav.Ready) return;   // 沒有格圖就站著（不要直線穿牆）
            int ver = TownNav.GridVersion;

            // 障礙變了 → 走到一半的沿用目的地重算路
            foreach (var w in critters)
                if (!w.NeedPath && w.PathIdx < w.Path.Count && w.PathVer != ver)
                { w.NeedPath = true; w.KeepGoal = true; }

            // 一幀最多替一隻算路
            int n = critters.Count;
            for (int k = 0; k < n; k++)
            {
                var w = critters[(planCursor + k) % n];
                if (!w.NeedPath || w.Pause > 0f || w.Node == null) continue;
                Plan(w, ver);
                planCursor = (planCursor + k + 1) % n;
                break;
            }

            foreach (var w in critters)
            {
                if (w.Node == null) continue;

                // YSort：站得低的畫在前面
                w.Sr.sortingOrder = Mathf.RoundToInt(-w.Node.transform.position.y);

                if (w.Pause > 0f) { w.Pause -= dt; continue; }
                if (w.NeedPath) continue;            // 等輪到牠算路

                float budget = w.Speed * dt;
                float lastDx = 0f;
                while (w.PathIdx < w.Path.Count)
                {
                    var target = w.Path[w.PathIdx];
                    var p = w.Node.transform.position;
                    float dx = target.x - p.x, dy = target.y - p.y;
                    float dist = Mathf.Sqrt(dx * dx + dy * dy);
                    if (dist <= budget)
                    {
                        w.Node.transform.position = new Vector3(target.x, target.y, 0f);
                        budget -= dist;
                        w.PathIdx++;
                        continue;
                    }
                    w.Node.transform.position =
                        new Vector3(p.x + dx / dist * budget, p.y + dy / dist * budget, 0f);
                    lastDx = dx;
                    break;
                }

                if (w.PathIdx >= w.Path.Count)
                {
                    // 到了：停一下，停完再排隊算下一段
                    w.Pause = 1.5f + Random.value * 3f;
                    w.NeedPath = true;
                    continue;
                }

                // 往右走就翻面（這批圖畫的都是朝左）
                if (lastDx != 0f)
                {
                    var s = w.Node.transform.localScale;
                    float want = lastDx > 0 ? -Mathf.Abs(s.x) : Mathf.Abs(s.x);
                    if (!Mathf.Approximately(want, s.x))
                        w.Node.transform.localScale = new Vector3(want, s.y, s.z);
                }
            }
        }
    }
}
