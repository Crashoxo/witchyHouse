using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 戶外（城鎮 town／糖果鎮 candy）NPC 的尋路：村民、街上晃的小動物用它繞過房子、河、招牌柱、樹……
    ///
    /// 為什麼需要：TownFolk／CandyTown 原本是在路點之間**直線**走 —— 路點都在路上，但兩個路點之間的直線
    /// 常常切過房子或河（使用者回報「路人走路不要穿牆」）。玩家的 <see cref="Obstacles"/> 是「即時推牆滑動」，
    /// 拿來替 NPC 找路既不保證走得到也貴；這裡在它上面另建一張粗格圖跑 A*。
    ///
    /// ── 做法 ──────────────────────────────────────────────
    ///   ● 障礙**就是玩家的那一份**（Obstacles：掃 SpriteRenderer 查 ArtFootprints ＋ 執行期登記的河、招牌柱腳），
    ///     只是腳底圓的半徑換成 <see cref="Radius"/>（村民比女巫寬一點，而且寧可離牆遠一點）。
    ///   ● 可走範圍（Obstacles.WalkRect，地圖邊緣已內縮）切成 <see cref="CellSize"/>＝32px 的格子；
    ///     格子中心 InWalk 且 IsFree(中心, Radius) 才算可站。城鎮 3200×2048 → 約 98×62 ≈ 6000 格。
    ///   ● 相鄰兩格要「連得通」才算一條邊：直向（東、北）多驗兩格中間那一點；斜向不能切角（兩個直向鄰格都要可站），
    ///     再驗對角線上 1/4、1/2、3/4 三點。⚠️ 只驗格子中心的話，兩個可站的中心之間仍可能夾著一根細柱子
    ///     （招牌柱腳半寬只有十幾 px）—— 取樣間距 ≤ <see cref="SampleStep"/>（16px）時，線段上每一點離障礙都至少
    ///     Radius − SampleStep/2 ＝ 4px，才敢說「不穿過」。
    ///   ● 建圖時順便標連通區塊（components）：兩點不在同一塊（被河隔開又沒橋）就不用跑 A*，直接回「走不到」，
    ///     呼叫端換一個目的地。
    ///   ● A*：八向、octile 估價；求出格子路徑後做「拉直」—— 從目前的點往後找最遠一個能直線走到的點
    ///     （直線用同一個取樣規則驗），人才不會一格一格走鋸齒。
    ///   ● 偏好走在路上（城鎮）：離 TownRoads.Walk 路點 PreferRadius 內的格子算路面，草地的步數代價 × OffRoadCost；
    ///     拉直也不准把兩端都在路上的一段拉成斜切草地（<see cref="StaysCheap"/>）。只是代價，草地照樣走得過。
    ///
    /// ── 什麼時候重建 ──────────────────────────────────────
    ///   Obstacles 每重建一次障礙清單 Version 就 +1（換場景、糖果鎮建築擺完 MarkDirty、店裡改家具……）。
    ///   這裡記著建圖時的 Version，**不一樣才重建**（<see cref="Refresh"/>）。走到一半障礙變了的人，
    ///   呼叫端比對 <see cref="GridVersion"/> 自己重算路。
    ///
    /// ── 效能 ──────────────────────────────────────────────
    ///   建圖：約 6000 格 × 5 次 IsFree，只在 Version 變的時候一次。
    ///   尋路：只在**挑新目的地的那一刻**算一次（呼叫端還會錯開，一幀最多算一條）；
    ///   A* 的陣列、二元堆積、格子路徑緩衝全部重用，用「戳記」代替清空 —— 尋路本身不配置記憶體
    ///   （結果寫進呼叫端傳進來、自己重用的 List）。
    ///
    /// 離線版：tools/check_npc_paths.py（同一份格距、半徑、取樣、八向不切角；常數直接從這個檔讀）。
    /// 後花園沒開 Obstacles（<see cref="Ready"/> 為 false）→ TownFolk 改走「折線路點」模式，不用這支。
    /// </summary>
    public static class TownNav
    {
        /// <summary>格子邊長（px）。</summary>
        public const float CellSize = 32f;
        /// <summary>NPC 腳底圓的半徑（px）。女巫是 11；村民的腳畫得比較開、也寧可離牆遠一點。</summary>
        public const float Radius = 12f;
        /// <summary>
        /// 線段取樣間距（px）。⚠️ 一定要 ≤ 2×Radius 才保證不穿過：線段上任一點離最近的取樣點不超過 SampleStep/2，
        /// 取樣點都離障礙 ≥ Radius → 線上每一點都離障礙 ≥ Radius − SampleStep/2（現在是 4px）。
        /// </summary>
        public const float SampleStep = 16f;
        /// <summary>拉直時一次最多往後看幾個路點（限制最壞情況的取樣次數）。</summary>
        const int MaxPull = 40;
        /// <summary>找「最近的可站格」最多往外找幾圈。</summary>
        const int SnapRings = 10;
        /// <summary>
        /// 「偏好走在路上」：離任一個路點（<see cref="Prefer"/> 給的點）不到 PreferRadius 的格子算路面，
        /// 其他格子（草地）每走一步的代價 × OffRoadCost。
        /// ⚠️ 城鎮沒有「路面格子」的資料（路面烤在 town-ground.png 裡），只有 TownRoads.Walk 的路點 ——
        ///    那些路點本來就是從路的內部抽出來、間距 ≤ 約 190px，所以「離路點夠近」大致就是路面。
        ///    只是代價、不是障礙：草地照樣走得過去，只是有路可走時會繞一點走路上。
        /// </summary>
        public const float PreferRadius = 112f;
        public const float OffRoadCost = 2f;

        // 連線位元：這一格往 東 / 北 / 東北 / 西北 連不連得通（反方向由鄰格的位元查）
        const byte LinkE = 1, LinkN = 2, LinkNE = 4, LinkNW = 8;

        static int builtVersion = int.MinValue;
        static bool ready;
        static int nx, ny;
        static Vector2 origin;                 // 格子 (0,0) 的中心
        static bool[] free = new bool[0];
        static byte[] link = new byte[0];
        static int[] comp = new int[0];        // 連通區塊編號（-1＝不可站）
        static float[] mult = new float[0];    // 這一格每走一步的代價倍率（路面 1、草地 OffRoadCost）
        static Vector2[] preferPts;            // 偏好的路點（null＝不分路面草地）
        static string preferScene;             // 那份路點是哪個場景給的（換場景後不沿用）

        // A* 的工作陣列（重用；用 stamp 判斷「這一輪有沒有碰過」，不用每次清空）
        static float[] gScore = new float[0];
        static int[] parent = new int[0];
        static int[] seen = new int[0];        // == stamp：這一輪開過；
        static bool[] closed = new bool[0];
        static int stamp;
        static int[] heap = new int[0];
        static float[] heapKey = new float[0];
        static int heapCount;
        static readonly List<int> cellPath = new(256);
        static readonly List<Vector2> pts = new(256);
        static readonly Stack<int> fillStack = new(256);

        /// <summary>
        /// 除錯顯示用：目前在走的 NPC 路徑（ObstacleDebugView 在 F3 開著時畫出來）。
        /// 呼叫端建立 Walker 時 Register、銷毀時 Unregister；登記的是呼叫端自己重用的 List（不另外複製）。
        /// </summary>
        public static readonly List<List<Vector2>> DebugPaths = new();
        public static void Register(List<Vector2> path) { if (!DebugPaths.Contains(path)) DebugPaths.Add(path); }
        public static void Unregister(List<Vector2> path) => DebugPaths.Remove(path);

        /// <summary>這個場景有沒有可用的格圖（有開碰撞的戶外場景才有；後花園沒有）。會順便檢查要不要重建。</summary>
        public static bool Ready { get { Refresh(); return ready; } }

        /// <summary>目前格圖對應的 Obstacles.Version（呼叫端拿來判斷手上的路是不是舊的）。</summary>
        public static int GridVersion { get { Refresh(); return builtVersion; } }

        /// <summary>
        /// 設定「路面」：離這些點 PreferRadius 內的格子走起來比較便宜（見 <see cref="PreferRadius"/>）。
        /// 城鎮的 TownFolk 給 TownRoads.Walk；null＝不分（糖果鎮的路點太稀，整張都是鋪面）。
        /// 綁在目前場景上 —— 換場景之後舊的那份自動作廢，不會套到別張地圖。
        /// </summary>
        public static void Prefer(Vector2[] points)
        {
            string scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
            if (points == preferPts && scene == preferScene) return;
            preferPts = points;
            preferScene = scene;
            builtVersion = int.MinValue;          // 下次查詢時重建
        }

        static Vector2[] avoidC;
        static float[] avoidR;
        static string avoidScene;
        static bool avoidOn;                   // 建圖當下：額外圓形障礙是不是這個場景的

        /// <summary>
        /// 只擋 NPC、不擋玩家的圓形範圍（中心、半徑；腳底圓心離中心至少 半徑＋Radius）。
        /// 糖果鎮用：中央的薄荷糖噴泉是畫在地面圖裡的（玩家可以踩上去，Obstacles 沒有它），
        /// 但小動物從噴泉正中間直直穿過去看起來就是「穿牆」；站著的三位 NPC 也一樣（他們沒有落地範圍）。
        /// 綁在目前場景上，換場景自動作廢；null＝沒有。
        /// </summary>
        public static void Avoid(Vector2[] centers, float[] radii)
        {
            avoidC = centers;
            avoidR = radii;
            avoidScene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
            builtVersion = int.MinValue;          // 下次查詢時重建
        }

        /// <summary>障礙清單變了就重建格圖（沒變什麼都不做，便宜到可以每幀呼叫）。</summary>
        public static void Refresh()
        {
            Obstacles.EnsureBuilt();
            if (builtVersion == Obstacles.Version) return;
            Build();
        }

        // ──────────── 建圖 ────────────

        static void Build()
        {
            builtVersion = Obstacles.Version;
            ready = Obstacles.Enabled && Obstacles.WalkPolygon == null;   // 房間（地板多邊形）不用這套
            if (!ready) return;

            var w = Obstacles.WalkRect;
            nx = Mathf.Max(1, Mathf.FloorToInt(w.width / CellSize));
            ny = Mathf.Max(1, Mathf.FloorToInt(w.height / CellSize));
            origin = new Vector2(w.xMin + CellSize * 0.5f, w.yMin + CellSize * 0.5f);
            int n = nx * ny;
            if (free.Length != n)
            {
                free = new bool[n]; link = new byte[n]; comp = new int[n]; mult = new float[n];
                gScore = new float[n]; parent = new int[n]; seen = new int[n]; closed = new bool[n];
                heap = new int[n * 8 + 8]; heapKey = new float[n * 8 + 8];   // 允許重複入堆（不做 decrease-key）
                stamp = 0;
            }

            string scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
            var prefer = preferScene == scene ? preferPts : null;
            avoidOn = avoidScene == scene && avoidC != null && avoidR != null;
            float pr2 = PreferRadius * PreferRadius;
            for (int j = 0; j < ny; j++)
                for (int i = 0; i < nx; i++)
                {
                    var c = Center(i, j);
                    int k = j * nx + i;
                    free[k] = Standable(c);
                    float m = 1f;
                    if (prefer != null && prefer.Length > 0)
                    {
                        m = OffRoadCost;
                        foreach (var q in prefer)
                            if ((q - c).sqrMagnitude <= pr2) { m = 1f; break; }
                    }
                    mult[k] = m;
                }

            for (int j = 0; j < ny; j++)
                for (int i = 0; i < nx; i++)
                {
                    int k = j * nx + i;
                    byte b = 0;
                    if (free[k])
                    {
                        var c = Center(i, j);
                        float h = CellSize * 0.5f;
                        if (i + 1 < nx && free[k + 1] && Standable(c + new Vector2(h, 0f))) b |= LinkE;
                        if (j + 1 < ny && free[k + nx] && Standable(c + new Vector2(0f, h))) b |= LinkN;
                        // 斜向：不切角（兩個直向鄰格都要可站）＋ 對角線上三點
                        if (i + 1 < nx && j + 1 < ny && free[k + nx + 1] && free[k + 1] && free[k + nx]
                            && DiagClear(c, new Vector2(CellSize, CellSize))) b |= LinkNE;
                        if (i - 1 >= 0 && j + 1 < ny && free[k + nx - 1] && free[k - 1] && free[k + nx]
                            && DiagClear(c, new Vector2(-CellSize, CellSize))) b |= LinkNW;
                    }
                    link[k] = b;
                }

            // 連通區塊
            for (int k = 0; k < n; k++) comp[k] = -1;
            int label = 0;
            for (int k = 0; k < n; k++)
            {
                if (!free[k] || comp[k] >= 0) continue;
                comp[k] = label;
                fillStack.Clear();
                fillStack.Push(k);
                while (fillStack.Count > 0)
                {
                    int cur = fillStack.Pop();
                    for (int d = 0; d < 8; d++)
                    {
                        int nb = Neighbor(cur, d, out _);
                        if (nb < 0 || comp[nb] >= 0) continue;
                        comp[nb] = label;
                        fillStack.Push(nb);
                    }
                }
                label++;
            }
        }

        static bool DiagClear(Vector2 c, Vector2 d) =>
            Standable(c + d * 0.25f) && Standable(c + d * 0.5f) && Standable(c + d * 0.75f);

        /// <summary>這一點 NPC 站不站得住：在可走範圍內、腳底圓不碰到任何障礙。</summary>
        public static bool Standable(Vector2 p)
        {
            if (!Obstacles.InWalk(p) || !Obstacles.IsFree(p, Radius)) return false;
            if (avoidOn)
                for (int i = 0; i < avoidC.Length && i < avoidR.Length; i++)
                {
                    float r = avoidR[i] + Radius;
                    if ((p - avoidC[i]).sqrMagnitude < r * r) return false;
                }
            return true;
        }

        static Vector2 Center(int i, int j) => new(origin.x + i * CellSize, origin.y + j * CellSize);
        static Vector2 Center(int k) => Center(k % nx, k / nx);

        /// <summary>
        /// 第 d 個方向的鄰格（連得通才回傳，否則 -1）。d：0東 1西 2北 3南 4東北 5西南 6西北 7東南。
        /// 反方向的連線存在鄰格的位元裡（例如「往西」＝左邊那格的「往東」）。
        /// </summary>
        static int Neighbor(int k, int d, out float cost)
        {
            int i = k % nx, j = k / nx;
            cost = CellSize;
            switch (d)
            {
                case 0: return (link[k] & LinkE) != 0 ? k + 1 : -1;
                case 1: return i > 0 && (link[k - 1] & LinkE) != 0 ? k - 1 : -1;
                case 2: return (link[k] & LinkN) != 0 ? k + nx : -1;
                case 3: return j > 0 && (link[k - nx] & LinkN) != 0 ? k - nx : -1;
            }
            cost = CellSize * 1.41421356f;
            switch (d)
            {
                case 4: return (link[k] & LinkNE) != 0 ? k + nx + 1 : -1;
                case 5: return i > 0 && j > 0 && (link[k - nx - 1] & LinkNE) != 0 ? k - nx - 1 : -1;
                case 6: return (link[k] & LinkNW) != 0 ? k + nx - 1 : -1;
                default: return i + 1 < nx && j > 0 && (link[k - nx + 1] & LinkNW) != 0 ? k - nx + 1 : -1;
            }
        }

        // ──────────── 查詢 ────────────

        /// <summary>p 所在的格子（夾在格圖內）。</summary>
        static int CellOf(Vector2 p)
        {
            int i = Mathf.Clamp(Mathf.RoundToInt((p.x - origin.x) / CellSize), 0, nx - 1);
            int j = Mathf.Clamp(Mathf.RoundToInt((p.y - origin.y) / CellSize), 0, ny - 1);
            return j * nx + i;
        }

        /// <summary>離 p 最近的可站格（一圈一圈往外找，最多 SnapRings 圈）；找不到回 -1。</summary>
        static int NearestFreeCell(Vector2 p)
        {
            int k0 = CellOf(p);
            if (free[k0]) return k0;
            int i0 = k0 % nx, j0 = k0 / nx;
            for (int r = 1; r <= SnapRings; r++)
            {
                int best = -1;
                float bd = float.MaxValue;
                for (int j = j0 - r; j <= j0 + r; j++)
                    for (int i = i0 - r; i <= i0 + r; i++)
                    {
                        if (Mathf.Max(Mathf.Abs(i - i0), Mathf.Abs(j - j0)) != r) continue;
                        if (i < 0 || j < 0 || i >= nx || j >= ny) continue;
                        int k = j * nx + i;
                        if (!free[k]) continue;
                        float d = (Center(i, j) - p).sqrMagnitude;
                        if (d < bd) { bd = d; best = k; }
                    }
                if (best >= 0) return best;
            }
            return -1;
        }

        /// <summary>
        /// 把一點吸附到站得住的地方：本身站得住就原樣回傳，否則換成最近的可站格中心。
        /// 路點落在建築範圍裡（城鎮有 4 個）就靠這支。找不到（理論上不會）回傳原點。
        /// </summary>
        public static Vector2 Snap(Vector2 p)
        {
            Refresh();
            if (!ready) return p;
            if (Standable(p) && comp[CellOf(p)] >= 0 && SegmentClear(Center(CellOf(p)), p)) return p;
            int k = NearestFreeCell(p);
            return k >= 0 ? Center(k) : p;
        }

        /// <summary>p 屬於哪個連通區塊（-1＝附近沒有站得住的格子）。兩點同一塊才走得到。</summary>
        public static int ComponentAt(Vector2 p)
        {
            Refresh();
            if (!ready) return -1;
            int k = NearestFreeCell(p);
            return k >= 0 ? comp[k] : -1;
        }

        /// <summary>
        /// 這一點能不能當「停下來站著」的位置：站得住、所在格可站、而且從格子中心直線走得過來
        /// （Find 的最後一段就是「終點格中心 → 這一點」）。
        /// </summary>
        public static bool GoodStop(Vector2 p)
        {
            Refresh();
            if (!ready) return true;
            if (!Standable(p)) return false;
            int k = CellOf(p);
            return free[k] && SegmentClear(Center(k), p);
        }

        /// <summary>a→b 的直線上每隔 SampleStep 取一點都站得住（兩端點不驗，呼叫端保證）。</summary>
        public static bool SegmentClear(Vector2 a, Vector2 b)
        {
            float len = Vector2.Distance(a, b);
            int n = Mathf.CeilToInt(len / SampleStep);
            for (int s = 1; s < n; s++)
                if (!Standable(Vector2.Lerp(a, b, s / (float)n))) return false;
            return true;
        }

        /// <summary>
        /// 從 from 走到 to 的路點（世界座標，不含起點、最後一點是終點），寫進呼叫端重用的 path。
        /// 回傳 false ＝ 走不到（不同連通區塊、或附近沒有站得住的格子）—— 呼叫端應該換一個目的地，
        /// **不要**退回直線（那就是穿牆）。
        /// to 建議先用 <see cref="GoodStop"/> 驗過；沒過的話這裡會把終點換成終點格的中心。
        /// </summary>
        public static bool Find(Vector2 from, Vector2 to, List<Vector2> path)
        {
            path.Clear();
            Refresh();
            if (!ready) return false;

            int s = NearestFreeCell(from), g = NearestFreeCell(to);
            if (s < 0 || g < 0 || comp[s] != comp[g]) return false;
            if (!AStar(s, g)) return false;

            // 路點：起點（真實位置）＋ 每一格中心 ＋ 終點
            pts.Clear();
            pts.Add(from);
            foreach (var k in cellPath) pts.Add(Center(k));
            var end = to;
            if (!Standable(end) || !SegmentClear(Center(g), end)) end = Center(g);
            if ((end - pts[pts.Count - 1]).sqrMagnitude > 0.01f) pts.Add(end);

            // 拉直：從目前的點往後找最遠一個能直線走到的點（第一個走不到就停，最多看 MaxPull 個）。
            // 相鄰兩點（格子中心之間）的連線建圖時就驗過，所以「至少前進一點」一定安全。
            // ⚠️ 起點 → 起點格中心那一段不驗：人本來就站在那裡（可能剛好貼著牆），讓他走得出來。
            int at = 0;
            while (at < pts.Count - 1)
            {
                int next = at + 1;
                int last = Mathf.Min(pts.Count - 1, at + MaxPull);
                for (int j = at + 2; j <= last; j++)
                {
                    if (!SegmentClear(pts[at], pts[j]) || !StaysCheap(pts[at], pts[j])) break;
                    next = j;
                }
                path.Add(pts[next]);
                at = next;
            }
            return true;
        }

        /// <summary>
        /// 拉直不能把「沿著路走」拉成「斜切過草地」：直線上每個取樣點所在格的倍率，不能比兩端點所在格的倍率還貴。
        /// （兩端都在路上 → 整條要在路上；有一端在草地 → 本來就在草地上，隨便拉。）
        /// </summary>
        static bool StaysCheap(Vector2 a, Vector2 b)
        {
            float cap = Mathf.Max(mult[CellOf(a)], mult[CellOf(b)]);
            float len = Vector2.Distance(a, b);
            int n = Mathf.CeilToInt(len / SampleStep);
            for (int s = 1; s < n; s++)
                if (mult[CellOf(Vector2.Lerp(a, b, s / (float)n))] > cap) return false;
            return true;
        }

        static bool AStar(int s, int g)
        {
            cellPath.Clear();
            if (s == g) { cellPath.Add(s); return true; }
            stamp++;
            if (stamp == int.MaxValue) { System.Array.Clear(seen, 0, seen.Length); stamp = 1; }
            heapCount = 0;
            var goal = Center(g);

            seen[s] = stamp; closed[s] = false; gScore[s] = 0f; parent[s] = -1;
            Push(s, H(s, goal));
            bool found = false;
            while (heapCount > 0)
            {
                int cur = Pop();
                if (closed[cur]) continue;
                closed[cur] = true;
                if (cur == g) { found = true; break; }
                for (int d = 0; d < 8; d++)
                {
                    int nb = Neighbor(cur, d, out float cost);
                    if (nb < 0) continue;
                    // 代價 ＝ 距離 × 兩格倍率的平均（草地貴一點）；倍率最小是 1，octile 估價仍不會高估
                    float ng = gScore[cur] + cost * 0.5f * (mult[cur] + mult[nb]);
                    if (seen[nb] == stamp && (closed[nb] || ng >= gScore[nb])) continue;
                    if (seen[nb] != stamp) { seen[nb] = stamp; closed[nb] = false; }
                    gScore[nb] = ng;
                    parent[nb] = cur;
                    if (heapCount < heap.Length) Push(nb, ng + H(nb, goal));
                }
            }
            if (!found) return false;
            for (int k = g; k >= 0; k = parent[k]) cellPath.Add(k);
            cellPath.Reverse();
            return true;
        }

        /// <summary>octile 估價（八向、斜走 √2）—— 不會高估，A* 求得到最短路。</summary>
        static float H(int k, Vector2 goal)
        {
            var c = Center(k);
            float dx = Mathf.Abs(c.x - goal.x), dy = Mathf.Abs(c.y - goal.y);
            return Mathf.Max(dx, dy) + 0.41421356f * Mathf.Min(dx, dy);
        }

        // ── 二元最小堆（key＝f 值）──
        static void Push(int k, float key)
        {
            int i = heapCount++;
            heap[i] = k; heapKey[i] = key;
            while (i > 0)
            {
                int p = (i - 1) >> 1;
                if (heapKey[p] <= heapKey[i]) break;
                (heap[p], heap[i]) = (heap[i], heap[p]);
                (heapKey[p], heapKey[i]) = (heapKey[i], heapKey[p]);
                i = p;
            }
        }

        static int Pop()
        {
            int top = heap[0];
            heapCount--;
            heap[0] = heap[heapCount]; heapKey[0] = heapKey[heapCount];
            int i = 0;
            while (true)
            {
                int l = i * 2 + 1, r = l + 1, m = i;
                if (l < heapCount && heapKey[l] < heapKey[m]) m = l;
                if (r < heapCount && heapKey[r] < heapKey[m]) m = r;
                if (m == i) break;
                (heap[m], heap[i]) = (heap[i], heap[m]);
                (heapKey[m], heapKey[i]) = (heapKey[i], heapKey[m]);
                i = m;
            }
            return top;
        }
    }
}
