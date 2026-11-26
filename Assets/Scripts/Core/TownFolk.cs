using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 城鎮街上走動的村民（後花園柵欄外經過的那幾位也是這支）。
    ///
    /// 跟店裡的顧客是同一批人（Resources/villagers ＋ VillagerAnim），在鎮上晃來晃去：
    /// 挑一個目的地 → 沿路走過去 → 停一下 → 再挑下一個。目的地來自 TownRoads.Walk（原專案從烤好的
    /// 城鎮小地圖抽出來的「路的內部」格子）。
    ///
    /// ── 不穿牆（使用者回報「路人走路不要穿牆」）─────────────────────
    /// 舊版在兩個路點之間**直線**走 —— 路點都在路上，但直線常常切過房子、河。現在分兩種模式：
    ///   ● 城鎮（有開 Obstacles）：交給 <see cref="TownNav"/>（32px 格子 A*，障礙跟玩家同一份，含河與招牌柱腳）
    ///     求出一串路點沿著走。路只在**挑新目的地的那一刻**算一次，而且一幀最多替一個人算（錯開，避免尖峰）；
    ///     兩點不連通（被河隔開又沒橋）就換一個目的地。障礙清單變了（Obstacles.Version）→ 走到一半的人重算路。
    ///     路點本身落在建築裡的（城鎮有 4 個）先吸附到最近的可站格（TownNav.Snap）。
    ///   ● 後花園（沒開 Obstacles）：<c>polyline</c> 模式 —— 路點是一條**有順序**的折線（柵欄外的石板路），
    ///     只沿著相鄰路點走（從第 i 點走到第 j 點會依序經過中間每一點），不會兩點直線切進花園。
    ///     每個人有一條固定的小偏移（Lane）讓兩個人不會疊在同一條線上，偏移量小於路寬的一半。
    ///
    /// 停下來的位置彼此至少隔 <see cref="MinSpacing"/>（不會兩個人完全疊在一起）；村民彼此、村民與女巫之間
    /// 走路時不互相避讓（維持原樣）。
    ///
    /// 由 PlayerController 在 town 場景呼叫 Ensure()；GardenRoom 用 polyline 模式呼叫 —— 不用改場景。
    /// </summary>
    public class TownFolk : MonoBehaviour
    {
        public static TownFolk Instance { get; private set; }

        /// <summary>白天街上幾個人；入夜後只剩 NightCount 個（其他人回家了）。</summary>
        public const int DayCount = 6;
        public const int NightCount = 2;

        /// <summary>
        /// 停點在路點附近的隨機偏移（全寬，x / y）—— 免得所有人都站在同一點、走同一條線。
        /// 偏移後的點要過 TownNav.GoodStop（站得住）才用；tools/check_npc_paths.py 會讀這個值。
        /// </summary>
        static readonly Vector2 StopJitter = new(90f, 60f);
        /// <summary>兩個人的停點至少隔多遠（px）。</summary>
        const float MinSpacing = 28f;
        /// <summary>polyline 模式（後花園）每個人固定的橫向偏移上限（px，±）。石板路寬約 100px，留在路中間那一段。</summary>
        const float LaneMax = 12f;

        /// <summary>
        /// 生一個 TownFolk 出來（重複呼叫安全）。
        /// </summary>
        /// <param name="route">走哪些路點</param>
        /// <param name="crowd">同時最多幾個人</param>
        /// <param name="polyline">true＝路點是有順序的折線，只沿相鄰路點走（沒有 Obstacles 的場景用，例如後花園）</param>
        public static TownFolk Ensure(Vector2[] route, int crowd = DayCount, bool polyline = false)
        {
            if (Instance != null) return Instance;
            var go = new GameObject("TownFolk");
            var f = go.AddComponent<TownFolk>();
            f.waypoints = route;
            f.crowd = crowd;
            f.polyline = polyline;
            if (!polyline) TownNav.Prefer(route);   // 城鎮：離路點近的格子算路面，尋路時偏好走路上
            return f;
        }

        class Walker
        {
            public GameObject Node;
            public VillagerAnim Anim;
            public string Who;
            public float Speed;
            public float Pause;      // 還要站多久（秒）
            /// <summary>要走的路點（不含目前位置）；重用，不每次 new。</summary>
            public readonly List<Vector2> Path = new(32);
            public int PathIdx;
            /// <summary>目前的目的地＝要停下來的那一點（別人挑停點時要避開）。</summary>
            public Vector2 Goal;
            /// <summary>等著算路（停頓結束後、輪到他時才算 —— 一幀只算一個人）。</summary>
            public bool NeedPath;
            /// <summary>重算路時沿用原本的目的地（障礙變了，不是走到了）。</summary>
            public bool KeepGoal;
            /// <summary>這條路是對哪一版格圖算的（版本變了就重算）。</summary>
            public int PathVer;
            /// <summary>polyline 模式：目前在第幾個路點、固定的橫向偏移。</summary>
            public int RouteIdx;
            public float Lane;
        }

        Vector2[] waypoints = System.Array.Empty<Vector2>();
        Vector2[] snapped = System.Array.Empty<Vector2>();   // 吸附到站得住的位置之後的路點（城鎮模式）
        int snappedVer = int.MinValue;
        readonly List<Walker> folk = new();
        int crowd = DayCount;
        bool polyline;
        float retry;
        int planCursor;          // 輪流：上次從誰開始找「要算路的人」

        void Awake() { Instance = this; GameArt.Preload(); }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            foreach (var w in folk) TownNav.Unregister(w.Path);
        }

        void Update()
        {
            if (UIState.ModalOpen) return;      // 開著選單/對話時整個鎮上靜止
            if (waypoints.Length < 2) return;

            bool nav = !polyline && TownNav.Ready;
            if (!polyline && !nav) return;      // 城鎮卻沒有格圖（理論上不會）：寧可站著也不要直線穿牆
            int ver = nav ? TownNav.GridVersion : 0;
            if (nav) EnsureSnapped(ver);

            // 白天熱鬧、晚上剩零星幾個（其他人回家了）
            int want = TimeSystem.IsNight ? Mathf.Min(NightCount, crowd) : crowd;

            if (folk.Count < want && GameArt.Ready)
            {
                retry += Time.deltaTime;
                if (retry > 0.8f) { retry = 0f; Spawn(nav); }
            }
            else if (folk.Count > want)
            {
                var bye = folk[folk.Count - 1];
                folk.RemoveAt(folk.Count - 1);
                TownNav.Unregister(bye.Path);
                if (bye.Node != null) Destroy(bye.Node);
            }

            // 障礙變了（例：糖果鎮的建築剛擺好、場景裡多了會擋路的東西）→ 走到一半的人沿用目的地重算路
            if (nav)
                foreach (var w in folk)
                    if (!w.NeedPath && w.PathIdx < w.Path.Count && w.PathVer != ver)
                    { w.NeedPath = true; w.KeepGoal = true; }

            // 一幀最多替一個人算路（多個人同時走到也不會擠在同一幀）
            int n = folk.Count;
            for (int k = 0; k < n; k++)
            {
                var w = folk[(planCursor + k) % n];
                if (!w.NeedPath || w.Pause > 0f || w.Node == null) continue;
                Plan(w, nav, ver);
                planCursor = (planCursor + k + 1) % n;
                break;
            }

            foreach (var w in folk) Step(w, Time.deltaTime);
        }

        /// <summary>城鎮模式：把路點吸附到站得住的位置（格圖重建才重算）。</summary>
        void EnsureSnapped(int ver)
        {
            if (snappedVer == ver && snapped.Length == waypoints.Length) return;
            snappedVer = ver;
            if (snapped.Length != waypoints.Length) snapped = new Vector2[waypoints.Length];
            for (int i = 0; i < waypoints.Length; i++) snapped[i] = TownNav.Snap(waypoints[i]);
        }

        /// <summary>p 附近（MinSpacing 內）有沒有別人的停點。</summary>
        bool Crowded(Vector2 p, Walker self)
        {
            foreach (var o in folk)
                if (o != self && (o.Goal - p).sqrMagnitude < MinSpacing * MinSpacing) return true;
            return false;
        }

        /// <summary>
        /// 城鎮模式挑一個停點：隨機路點（已吸附）＋偏移，要站得住、不跟別人的停點疊在一起；
        /// 試幾次都不行就用吸附後的路點本身。
        /// </summary>
        Vector2 PickStop(Walker self)
        {
            for (int t = 0; t < 6; t++)
            {
                var b = snapped[Random.Range(0, snapped.Length)];
                var p = new Vector2(b.x + (Random.value - 0.5f) * StopJitter.x,
                                    b.y + (Random.value - 0.5f) * StopJitter.y);
                if (TownNav.GoodStop(p) && !Crowded(p, self)) return p;
            }
            for (int t = 0; t < 6; t++)
            {
                var b = snapped[Random.Range(0, snapped.Length)];
                if (!Crowded(b, self)) return b;
            }
            return snapped[Random.Range(0, snapped.Length)];
        }

        void Spawn(bool nav)
        {
            var names = GameArt.VillagerNames();
            if (names.Length == 0) return;

            // 盡量不要跟街上現有的人重複
            var taken = new HashSet<string>();
            foreach (var w0 in folk) taken.Add(w0.Who);
            var pool = new List<string>();
            foreach (var n in names) if (!taken.Contains(n)) pool.Add(n);
            if (pool.Count == 0) pool.AddRange(names);
            string who = pool[Random.Range(0, pool.Count)];

            var w = new Walker
            {
                Who = who,
                Speed = 50f + Random.value * 30f,
                Pause = Random.value * 2f,
                NeedPath = true,
            };

            // 出生點：城鎮＝站得住的停點；後花園＝折線上的某一點（加自己的橫向偏移）
            Vector2 start;
            if (nav) start = PickStop(w);
            else
            {
                w.Lane = Random.Range(-LaneMax, LaneMax);
                w.RouteIdx = Random.Range(0, waypoints.Length);
                start = LanePoint(w.RouteIdx, w.Lane);
            }
            w.Goal = start;

            var go = new GameObject("Folk-" + who);
            go.transform.SetParent(transform);
            go.transform.position = new Vector3(start.x, start.y, 0f);
            var anim = go.AddComponent<VillagerAnim>();
            anim.Init(who);
            w.Node = go; w.Anim = anim;

            folk.Add(w);
            TownNav.Register(w.Path);
        }

        /// <summary>polyline 模式：第 i 個路點往下（y）挪 lane —— 石板路是斜的帶狀，上下挪一點還在路面上。</summary>
        Vector2 LanePoint(int i, float lane) => new(waypoints[i].x, waypoints[i].y + lane);

        /// <summary>替一個人算下一段路（一幀最多叫一次）。</summary>
        void Plan(Walker w, bool nav, int ver)
        {
            var p = (Vector2)w.Node.transform.position;
            w.Path.Clear();
            w.PathIdx = 0;

            if (!nav)
            {
                // 後花園：沿折線走到另一個路點（依序經過中間每一點，不會兩點直線切進柵欄裡）
                int to = w.RouteIdx;
                for (int t = 0; t < 4; t++)
                {
                    to = Random.Range(0, waypoints.Length);
                    if (to != w.RouteIdx && !Crowded(LanePoint(to, w.Lane), w)) break;
                }
                if (to == w.RouteIdx) to = (w.RouteIdx + 1) % waypoints.Length;
                int step = to > w.RouteIdx ? 1 : -1;
                for (int i = w.RouteIdx + step; ; i += step)
                {
                    w.Path.Add(LanePoint(i, w.Lane));
                    if (i == to) break;
                }
                w.RouteIdx = to;
                w.Goal = w.Path[w.Path.Count - 1];
                w.NeedPath = false;
                return;
            }

            // 障礙變了要重算：先試原本的目的地
            if (w.KeepGoal)
            {
                w.KeepGoal = false;
                if (TownNav.Find(p, w.Goal, w.Path)) { w.PathVer = ver; w.NeedPath = false; return; }
            }

            // 挑新目的地；走不到（不同連通區塊）就換一個
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
            // 這一輪都找不到：原地站一下再試（不要退回直線）
            w.Path.Clear();
            w.Goal = p;
            w.Pause = 1f + Random.value;
        }

        /// <summary>推進一位村民：停頓中或等著算路就站著，否則沿路點走，走完就停一下、排隊算下一段。</summary>
        void Step(Walker w, float dt)
        {
            if (w.Node == null) return;
            if (w.Pause > 0f || w.NeedPath)
            {
                if (w.Pause > 0f) w.Pause -= dt;
                w.Anim.SetMove(0f, 0f);
                return;
            }

            float budget = w.Speed * dt;
            while (w.PathIdx < w.Path.Count)
            {
                var target = w.Path[w.PathIdx];
                var p = w.Node.transform.position;
                float dx = target.x - p.x, dy = target.y - p.y;
                float dist = Mathf.Sqrt(dx * dx + dy * dy);
                if (dist <= budget)
                {
                    // 這一段走完，剩下的步長接著走下一段（轉角不會頓一下）
                    w.Node.transform.position = new Vector3(target.x, target.y, 0f);
                    budget -= dist;
                    w.PathIdx++;
                    continue;
                }
                w.Node.transform.position = new Vector3(p.x + dx / dist * budget, p.y + dy / dist * budget, 0f);
                w.Anim.SetMove(dx / dist, dy / dist);
                return;
            }

            // 到了：停一下，停完再排隊算下一段
            w.Anim.SetMove(0f, 0f);
            w.Pause = 1.5f + Random.value * 2.5f;
            w.NeedPath = true;
        }
    }
}
