using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 戶外地圖（森林 main／城鎮 town／糖果鎮 candy）的**玩家碰撞**：樹幹、房子、灌木、圍籬……
    /// 走到它們的「落地範圍」就停下來，可以沿著邊滑過去，也能繞到樹冠後面被樹遮住。
    ///
    /// 純資料、不靠 Unity 物理（專案沒有任何 Collider/Rigidbody）：
    ///   - 一個場景一份障礙清單（世界座標），場景載入後第一次查詢時才建 ——
    ///     糖果鎮的建築是 CandyTown 在 Start 裡才生出來的，太早建會漏掉；它生完會呼叫 <see cref="MarkDirty"/>；
    ///   - 清單是**掃場景裡實際的 SpriteRenderer** 建的：用 sprite 名稱查 <see cref="ArtFootprints"/>
    ///     （離線量 PNG 產生的表），位置／縮放／翻面都取物件真正的值。查不到的圖一律不擋；
    ///   - 形狀有三種：軸對齊橢圓（樹幹、灌木）、軸對齊矩形（建築、圍籬）、凸多邊形（藥水室的家具 ——
    ///     等距視角下落地範圍是平行四邊形）。玩家是腳底一個半徑 <see cref="ArtFootprints.PlayerRadius"/> 的圓，
    ///     碰撞時把形狀往外長一個半徑、玩家當成一個點；
    ///   - 128px 的空間切格，查詢只看玩家所在那一格的障礙，每幀不配置記憶體。
    ///
    /// 只擋**玩家**（推牆滑動）。城鎮村民、糖果鎮小動物不套這裡的即時碰撞，而是由 <see cref="TownNav"/>
    /// 用同一份障礙（<see cref="IsFree(Vector2, float)"/>，半徑換成 NPC 的）建格圖求路；店裡顧客走 ShopPath 的格子 BFS。魔法彈不管。
    ///
    /// 藥水室（brew，SVG 重畫的那一版）與店裡（shop，等距房間）也走這裡，但做法不同：
    ///   - 可走範圍是**地板多邊形**（<see cref="Begin"/> 的 walkPolygon），不是矩形 —— 女巫走不上牆；
    ///     店裡是 ShopRoom.WalkFloor()（跟舊的 ShopRoom.ClampToFloor 同一塊菱形）；
    ///   - 障礙不掃 SpriteRenderer，由房間直接登記（<see cref="AddPoly"/>／<see cref="AddEllipse"/>）：
    ///     藥水室由 BrewRoom 照 Data.BrewRoomLayout 登記一次；店裡由 ShopRoomView.Rebuild() 每次重畫後
    ///     先 <see cref="ClearRegistered"/> 再整批重登記（佈置模式會改家具）。
    ///
    /// ⚠️ 防卡死：玩家若已經站在某個障礙裡（出生點、出門的位置、範圍量得太大），
    ///    任何「讓穿入深度變小或離開」的移動都放行 —— 永遠走得出來。
    ///
    /// 調範圍：改 tools/gen_footprints.py 的 CATS → 重跑 → 用 tools/check_walkable.py 看預覽。
    /// 遊戲裡按 F3 會畫出所有落地範圍與玩家的碰撞圓（<see cref="ObstacleDebugView"/>）。
    /// </summary>
    public static class Obstacles
    {
        enum Kind { Box, Ellipse, Poly }

        struct Shape
        {
            public float Cx, Cy, Hx, Hy;    // 形狀本身（世界座標；橢圓＝半徑、矩形＝半寬半高、多邊形＝外接矩形）
            public Kind Kind;
            public Vector2[] Poly;          // 凸多邊形的頂點（逆時針、世界座標）；其他形狀為 null
            public string Name, Category;
        }

        const float R = ArtFootprints.PlayerRadius;
        const float Eps = 0.01f;

        static Shape[] shapes = new Shape[0];
        static int count;

        // 空間切格：cellStart[c]..cellStart[c+1] 是格子 c 裡的障礙在 cellItems 的範圍
        static int[] cellStart = new int[1];
        static int[] cellItems = new int[0];
        static int gw, gh;

        static bool enabled, dirty;
        static string sceneName = "";
        static Rect walk;
        static Vector2[] walkPoly;          // 地板多邊形（null ＝ 用矩形 walk）；逆時針
        static Vector2 spawn;
        /// <summary>執行期直接登記的障礙（藥水室的家具）。Begin 時清空。</summary>
        static readonly List<Shape> registered = new();

        /// <summary>這個場景有沒有套碰撞（戶外地圖、藥水室、店裡）。</summary>
        public static bool Enabled => enabled;
        /// <summary>每重建一次 +1（除錯顯示用來判斷要不要重畫）。</summary>
        public static int Version { get; private set; }
        public static int Count { get { EnsureBuilt(); return count; } }
        /// <summary>玩家可走範圍（地圖邊緣已內縮）。有地板多邊形時是它的外接矩形。</summary>
        public static Rect WalkRect => walk;
        /// <summary>地板多邊形（藥水室）；null ＝ 可走範圍就是 <see cref="WalkRect"/>。</summary>
        public static Vector2[] WalkPolygon => walkPoly;

        /// <summary>
        /// 場景載入時由 PlayerController.Awake 呼叫：記下場景、可走範圍與出生位置，
        /// 標記成「要重建」（真的建是第一次查詢時）。on=false 的場景（後花園）完全不擋。
        /// ⚠️ 會清空執行期登記的障礙 —— 房間要登記家具，一定要在這之後（Start 或更晚），不能在 Awake 裡。
        /// walkPolygon 不是 null 時，可走範圍改成那個凸多邊形（walkRect 要傳它的外接矩形，切格與自我檢查用）。
        /// </summary>
        public static void Begin(string scene, Rect walkRect, Vector2 spawnPos, bool on, Vector2[] walkPolygon = null)
        {
            sceneName = scene;
            walk = walkRect;
            walkPoly = walkPolygon != null ? Ccw(walkPolygon) : null;
            spawn = spawnPos;
            enabled = on;
            dirty = on;
            count = 0;
            registered.Clear();
            Version++;
        }

        /// <summary>
        /// 登記一個凸多邊形障礙（世界座標，順逆時針都可以）。藥水室的家具用這個 ——
        /// 等距視角的落地範圍是平行四邊形，用矩形框會在斜邊多擋一大塊。
        /// 登記完會在下一次查詢時重建（不用另外呼叫 MarkDirty）。
        /// </summary>
        public static void AddPoly(string name, Vector2[] pts, string category = "furniture")
        {
            if (pts == null || pts.Length < 3) return;
            var poly = Ccw(pts);
            float x0 = float.MaxValue, y0 = float.MaxValue, x1 = float.MinValue, y1 = float.MinValue;
            foreach (var q in poly)
            {
                x0 = Mathf.Min(x0, q.x); x1 = Mathf.Max(x1, q.x);
                y0 = Mathf.Min(y0, q.y); y1 = Mathf.Max(y1, q.y);
            }
            registered.Add(new Shape
            {
                Cx = (x0 + x1) * 0.5f, Cy = (y0 + y1) * 0.5f, Hx = (x1 - x0) * 0.5f, Hy = (y1 - y0) * 0.5f,
                Kind = Kind.Poly, Poly = poly, Name = name, Category = category,
            });
            MarkDirty();
        }

        /// <summary>
        /// 清掉執行期登記的障礙（category＝null 全清；給了就只清那一類）。下一次查詢時重建。
        ///
        /// 店裡的家具會在佈置模式被搬動／收回／新增，ShopRoomView.Rebuild() 每次重畫都先清掉
        /// "shop_furniture" 再整批重登記 —— 只清自己那一類，別的系統登記的東西（例如城鎮的河）不受影響。
        /// ⚠️ 換場景時 <see cref="Begin"/> 本來就會全清，這支只給「同一個場景裡清單變了」用。
        /// </summary>
        public static void ClearRegistered(string category = null)
        {
            if (category == null) registered.Clear();
            else registered.RemoveAll(s => s.Category == category);
            MarkDirty();
        }

        /// <summary>登記一個軸對齊橢圓障礙（世界座標；half＝兩個半徑）。</summary>
        public static void AddEllipse(string name, Vector2 center, Vector2 half, string category = "furniture")
        {
            registered.Add(new Shape
            {
                Cx = center.x, Cy = center.y, Hx = half.x, Hy = half.y,
                Kind = Kind.Ellipse, Name = name, Category = category,
            });
            MarkDirty();
        }

        /// <summary>把多邊形整理成逆時針（複製一份，不改呼叫端的陣列）。</summary>
        static Vector2[] Ccw(Vector2[] pts)
        {
            float area = 0f;
            for (int i = 0; i < pts.Length; i++)
            {
                var a = pts[i];
                var b = pts[(i + 1) % pts.Length];
                area += a.x * b.y - b.x * a.y;
            }
            var outp = (Vector2[])pts.Clone();
            if (area < 0f) System.Array.Reverse(outp);
            return outp;
        }

        /// <summary>場景裡多了／少了會擋路的東西（例：CandyTown 剛把建築生出來）→ 下次查詢時重建。</summary>
        public static void MarkDirty()
        {
            if (enabled) dirty = true;
        }

        public static void EnsureBuilt()
        {
            if (enabled && dirty) Build();
        }

        // ──────────── 查詢 ────────────

        /// <summary>
        /// 玩家腳底從 from 想走到 to，回傳實際走得到的位置：
        ///   整步可走就走 → 不行就沿著擋住的那個障礙的切線滑 → 再試只走 X、只走 Y → 都不行就不動。
        /// to 會先夾在可走範圍內（呼叫端通常已經夾過）。
        /// </summary>
        public static Vector2 Resolve(Vector2 from, Vector2 to)
        {
            if (!enabled) return to;
            EnsureBuilt();
            to = ClampWalk(to);
            if (count == 0) return to;

            int hit = FirstBlocker(from, to);
            if (hit < 0) return to;

            // ① 沿切線滑：拿掉往障礙裡面的那個分量（撞樹幹時斜著推會繞過去）
            Vector2 move = to - from;
            Vector2 n = Normal(hit, to);
            float into = Vector2.Dot(move, n);
            if (into < 0f)
            {
                var slide = ClampWalk(from + (move - n * into));
                if ((slide - from).sqrMagnitude > 1e-6f && FirstBlocker(from, slide) < 0) return slide;
            }

            // ② 分軸：只走 X、只走 Y（貼著牆斜走時沿牆滑）
            var onlyX = ClampWalk(new Vector2(to.x, from.y));
            if (onlyX.x != from.x && FirstBlocker(from, onlyX) < 0) return onlyX;
            var onlyY = ClampWalk(new Vector2(from.x, to.y));
            if (onlyY.y != from.y && FirstBlocker(from, onlyY) < 0) return onlyY;

            // ③ 防卡死：本來就卡在障礙裡（可能同時插在兩個裡面）時，只要總穿入深度變小就放行
            float p0 = TotalPen(from);
            if (p0 > 0f)
            {
                if (TotalPen(to) < p0 - Eps) return to;
                if (TotalPen(onlyX) < p0 - Eps) return onlyX;
                if (TotalPen(onlyY) < p0 - Eps) return onlyY;
            }
            return from;
        }

        /// <summary>這一點能不能站（腳底圓不碰到任何落地範圍）。</summary>
        public static bool IsFree(Vector2 p)
        {
            if (!enabled) return true;
            EnsureBuilt();
            return TotalPen(p) <= 0f;
        }

        /// <summary>
        /// NPC 尋路用的唯讀查詢：半徑 radius 的腳底圓站在 p 會不會碰到任何障礙（**不看**可走範圍，要的話另外問 <see cref="InWalk"/>）。
        /// 沒開碰撞的場景（後花園）一律回 true。跟玩家用的 <see cref="IsFree(Vector2)"/> 同一個穿入算法，只差半徑。
        ///
        /// ⚠️ 切格表裡每個障礙只登記到「外接框再長一個玩家半徑 R」涵蓋的格子 —— 半徑比 R 大時，
        ///    離 p 不到 radius、卻沒登記在 p 那一格的障礙會漏掉，所以要把 p 周圍 (radius − R) 內的格子都看一遍。
        ///    同一個障礙可能出現在好幾格裡（重複看沒關係，這裡只問「有沒有碰到」，不加總）。
        /// TownNav（城鎮／糖果鎮的村民與小動物）用它建可走格圖；不影響玩家的碰撞。
        /// </summary>
        public static bool IsFree(Vector2 p, float radius)
        {
            if (!enabled) return true;
            EnsureBuilt();
            if (count == 0) return true;
            float extra = Mathf.Max(0f, radius - R);
            float cs = ArtFootprints.CellSize;
            int x0 = Mathf.Clamp((int)((p.x - extra - walk.xMin) / cs), 0, gw - 1);
            int x1 = Mathf.Clamp((int)((p.x + extra - walk.xMin) / cs), 0, gw - 1);
            int y0 = Mathf.Clamp((int)((p.y - extra - walk.yMin) / cs), 0, gh - 1);
            int y1 = Mathf.Clamp((int)((p.y + extra - walk.yMin) / cs), 0, gh - 1);
            for (int y = y0; y <= y1; y++)
                for (int x = x0; x <= x1; x++)
                {
                    int c = y * gw + x;
                    for (int k = cellStart[c], end = cellStart[c + 1]; k < end; k++)
                        if (Pen(cellItems[k], p, radius) > 0f) return false;
                }
            return true;
        }

        /// <summary>除錯顯示用：第 i 個障礙的形狀（多邊形回傳外接矩形，頂點另外用 <see cref="ShapePoly"/> 拿）。</summary>
        public static void GetShape(int i, out Vector2 center, out Vector2 half, out bool ellipse)
        {
            var s = shapes[i];
            center = new Vector2(s.Cx, s.Cy);
            half = new Vector2(s.Hx, s.Hy);
            ellipse = s.Kind == Kind.Ellipse;
        }

        /// <summary>除錯顯示用：第 i 個障礙若是凸多邊形，回傳它的頂點；其他形狀回傳 null。</summary>
        public static Vector2[] ShapePoly(int i) => shapes[i].Poly;

        /// <summary>
        /// 把一點夾進可走範圍：有地板多邊形就夾進多邊形（在外面時取邊上最近的點 —— 斜著推牆會沿牆滑），
        /// 否則夾在矩形裡。點地走路的目的地也用它。
        /// </summary>
        public static Vector2 ClampWalk(Vector2 p)
        {
            if (walkPoly == null)
                return new(Mathf.Clamp(p.x, walk.xMin, walk.xMax), Mathf.Clamp(p.y, walk.yMin, walk.yMax));
            if (PolyDist(walkPoly, p, out var closest) <= 0f) return p;
            return closest;
        }

        /// <summary>這一點在不在可走範圍裡（地板多邊形或矩形）。</summary>
        public static bool InWalk(Vector2 p) =>
            walkPoly != null ? PolyDist(walkPoly, p, out _) <= 0f : walk.Contains(p);

        /// <summary>
        /// 點到凸多邊形（逆時針）的有號距離：外面為正、裡面為負。closest ＝ 邊上最近的點。
        /// 跟 tools/gen_brew_room.py 的 poly_signed_dist() 同一個算法。
        /// </summary>
        static float PolyDist(Vector2[] poly, Vector2 p, out Vector2 closest)
        {
            bool inside = true;
            float best = float.MaxValue;
            closest = p;
            for (int i = 0, n = poly.Length; i < n; i++)
            {
                var a = poly[i];
                var b = poly[(i + 1) % n];
                var d = b - a;
                float l2 = d.sqrMagnitude;
                if (l2 < 1e-8f) continue;
                float t = Mathf.Clamp01(Vector2.Dot(p - a, d) / l2);
                var q = a + d * t;
                float dist = (p - q).sqrMagnitude;
                if (dist < best) { best = dist; closest = q; }
                if (d.x * (p.y - a.y) - d.y * (p.x - a.x) < 0f) inside = false;   // 逆時針：內側在左手邊
            }
            best = Mathf.Sqrt(best);
            return inside ? -best : best;
        }

        /// <summary>
        /// 從 from 走到 to 會被哪個障礙擋（-1＝不會）。
        /// 判準：to 插進某個障礙、而且**比 from 插得更深** —— 本來就在裡面的話，往外走一律放行（防卡死）。
        /// </summary>
        static int FirstBlocker(Vector2 from, Vector2 to)
        {
            int c = CellOf(to);
            for (int k = cellStart[c], end = cellStart[c + 1]; k < end; k++)
            {
                int i = cellItems[k];
                float pt = Pen(i, to);
                if (pt <= 0f) continue;
                if (pt > Pen(i, from) + Eps) return i;
            }
            return -1;
        }

        static float TotalPen(Vector2 p)
        {
            int c = CellOf(p);
            float sum = 0f;
            for (int k = cellStart[c], end = cellStart[c + 1]; k < end; k++)
            {
                float v = Pen(cellItems[k], p);
                if (v > 0f) sum += v;
            }
            return sum;
        }

        /// <summary>
        /// 腳底圓心在 p 時插進第 i 個障礙多深（&lt;=0 ＝沒碰到）。
        /// 橢圓：半徑各加 R 之後的正規化距離換算回像素（近似，夠用）；
        /// 矩形：到矩形的距離（＝圓角矩形的有號距離）。跟 tools/gen_footprints.py 的 penetration() 同一個算法。
        /// </summary>
        static float Pen(int i, Vector2 p) => Pen(i, p, R);

        static float Pen(int i, Vector2 p, float r)
        {
            var s = shapes[i];
            if (s.Kind == Kind.Poly) return r - PolyDist(s.Poly, p, out _);   // 凸多邊形往外長 r（圓角）
            float dx = p.x - s.Cx, dy = p.y - s.Cy;
            if (s.Kind == Kind.Ellipse)
            {
                float rx = s.Hx + r, ry = s.Hy + r;
                float ex = dx / rx, ey = dy / ry;
                float d = Mathf.Sqrt(ex * ex + ey * ey);
                return (1f - d) * Mathf.Min(rx, ry);
            }
            float qx = Mathf.Abs(dx) - s.Hx, qy = Mathf.Abs(dy) - s.Hy;
            float ox = Mathf.Max(qx, 0f), oy = Mathf.Max(qy, 0f);
            float outside = Mathf.Sqrt(ox * ox + oy * oy) + Mathf.Min(Mathf.Max(qx, qy), 0f);
            return r - outside;
        }

        /// <summary>第 i 個障礙在 p 那裡往外的法線（滑動用）。</summary>
        static Vector2 Normal(int i, Vector2 p)
        {
            var s = shapes[i];
            float dx = p.x - s.Cx, dy = p.y - s.Cy;
            Vector2 n;
            if (s.Kind == Kind.Poly)
            {
                float sd = PolyDist(s.Poly, p, out var q);
                if (sd > 1e-4f) n = p - q;                     // 外面：從最近的邊點指向自己
                else
                {
                    // 裡面（防卡死那條路會處理）：往最近那條邊走就是出去的方向
                    var d = q - p;
                    n = d.sqrMagnitude > 1e-10f ? d : new Vector2(dx, dy);
                }
            }
            else if (s.Kind == Kind.Ellipse)
            {
                float rx = s.Hx + R, ry = s.Hy + R;
                n = new Vector2(dx / (rx * rx), dy / (ry * ry));
            }
            else
            {
                float qx = Mathf.Abs(dx) - s.Hx, qy = Mathf.Abs(dy) - s.Hy;
                if (qx > 0f && qy > 0f) n = new Vector2(Mathf.Sign(dx) * qx, Mathf.Sign(dy) * qy);
                else if (qx > qy) n = new Vector2(Mathf.Sign(dx), 0f);
                else n = new Vector2(0f, Mathf.Sign(dy));
            }
            return n.sqrMagnitude > 1e-12f ? n.normalized : Vector2.up;
        }

        static int CellOf(Vector2 p)
        {
            int cx = Mathf.Clamp((int)((p.x - walk.xMin) / ArtFootprints.CellSize), 0, gw - 1);
            int cy = Mathf.Clamp((int)((p.y - walk.yMin) / ArtFootprints.CellSize), 0, gh - 1);
            return cy * gw + cx;
        }

        // ──────────── 建立 ────────────

        static void Build()
        {
            dirty = false;
            Version++;

            var list = new List<Shape>(128);
            int matched = 0;
            foreach (var sr in Object.FindObjectsByType<SpriteRenderer>(FindObjectsSortMode.None))
            {
                var sp = sr.sprite;
                if (sp == null || !ArtFootprints.TryGet(sp.name, out var fp)) continue;
                if (sr.GetComponentInParent<PlayerController>() != null) continue;
                matched++;

                var t = sr.transform;
                Vector3 c = t.TransformPoint(sp.bounds.center);       // 圖片中心（不管樞紐在中心還是腳底）
                Vector3 ls = t.lossyScale;
                float sx = Mathf.Abs(ls.x), sy = Mathf.Abs(ls.y);
                bool flip = sr.flipX ^ (ls.x < 0f);

                // 排序改成看「腳底」：森林／城鎮的場景物件原本用圖片中心的 -y 排，女巫站在樹幹後面
                // 卻在樹冠中心以下時會畫到樹前面。平貼地面的東西（橋）壓到最底，人走上去一律在上面。
                // 城鎮建築（KeepOrder）不動：門口的花台／灌木是貼著正面擺的，改成腳底會被房子蓋掉；
                // 建築的範圍深到圖片中心，女巫不是在中心以下就是以上，照中心排一樣對。
                if (fp.Flat) sr.sortingOrder = ArtFootprints.FlatOrder;
                else if (!fp.KeepOrder) sr.sortingOrder = Mathf.RoundToInt(-(c.y + fp.BottomY * sy));

                if (!fp.Blocks) continue;
                list.Add(new Shape
                {
                    Cx = c.x + (flip ? -fp.Cx : fp.Cx) * sx,
                    Cy = c.y + fp.Cy * sy,
                    Hx = fp.Hx * sx,
                    Hy = fp.Hy * sy,
                    Kind = fp.Shape == FootShape.Ellipse ? Kind.Ellipse : Kind.Box,
                    Name = sp.name,
                    Category = fp.Category,
                });
            }
            list.AddRange(registered);

            CarveDoors(list);

            shapes = list.ToArray();
            count = shapes.Length;
            BuildGrid();

#if UNITY_EDITOR
            SelfCheck(matched);
#endif
        }

        /// <summary>
        /// 門口挖開：門（SceneDoor）的觸發點落在建築範圍裡、或就在建築正後方（自動觸發距離內）時，
        /// 把那棟建築的範圍拆成左右兩塊，中間留 2×DoorGapHalf 的通道 —— 不然玩家被牆擋住，
        /// 永遠走不到「走上去就進門」的距離內。觸發點在範圍**底緣以下**（正面、玩家本來就走得到）
        /// 時不挖。判準跟 tools/gen_footprints.py 的 carve_doors() 一樣。
        /// </summary>
        static void CarveDoors(List<Shape> list)
        {
            foreach (var d in Object.FindObjectsByType<SceneDoor>(FindObjectsSortMode.None))
            {
                float dx = d.transform.position.x + d.doorX;
                float dy = d.transform.position.y + d.doorY;
                for (int i = list.Count - 1; i >= 0; i--)
                {
                    var s = list[i];
                    if (s.Kind != Kind.Box || (s.Category != "building" && s.Category != "building_iso")) continue;
                    if (Mathf.Abs(dx - s.Cx) >= s.Hx || Mathf.Abs(dy - s.Cy) > s.Hy + d.autoRange) continue;
                    if (dy < s.Cy - s.Hy) continue;   // 在正面（底緣以下）：從前面就走得到，不用挖

                    list.RemoveAt(i);
                    float l0 = s.Cx - s.Hx, l1 = dx - ArtFootprints.DoorGapHalf;
                    float r0 = dx + ArtFootprints.DoorGapHalf, r1 = s.Cx + s.Hx;
                    if (l1 - l0 > 2f) list.Add(Piece(s, l0, l1));
                    if (r1 - r0 > 2f) list.Add(Piece(s, r0, r1));
                }
            }

            static Shape Piece(Shape s, float a, float b)
            {
                s.Cx = (a + b) * 0.5f;
                s.Hx = (b - a) * 0.5f;
                s.Name += "（門邊）";
                return s;
            }
        }

        static void BuildGrid()
        {
            float cs = ArtFootprints.CellSize;
            gw = Mathf.Max(1, Mathf.CeilToInt(walk.width / cs));
            gh = Mathf.Max(1, Mathf.CeilToInt(walk.height / cs));
            int cells = gw * gh;
            var counts = new int[cells + 1];

            for (int pass = 0; pass < 2; pass++)
            {
                if (pass == 1)
                {
                    // 前綴和 → 每格的起點；counts 重用成「這格已經填了幾個」
                    cellStart = new int[cells + 1];
                    for (int c = 0; c < cells; c++) cellStart[c + 1] = cellStart[c] + counts[c];
                    cellItems = new int[cellStart[cells]];
                    System.Array.Clear(counts, 0, counts.Length);
                }
                for (int i = 0; i < count; i++)
                {
                    var s = shapes[i];
                    int x0 = Mathf.Clamp((int)((s.Cx - s.Hx - R - walk.xMin) / cs), 0, gw - 1);
                    int x1 = Mathf.Clamp((int)((s.Cx + s.Hx + R - walk.xMin) / cs), 0, gw - 1);
                    int y0 = Mathf.Clamp((int)((s.Cy - s.Hy - R - walk.yMin) / cs), 0, gh - 1);
                    int y1 = Mathf.Clamp((int)((s.Cy + s.Hy + R - walk.yMin) / cs), 0, gh - 1);
                    for (int y = y0; y <= y1; y++)
                        for (int x = x0; x <= x1; x++)
                        {
                            int c = y * gw + x;
                            if (pass == 1) cellItems[cellStart[c] + counts[c]] = i;
                            counts[c]++;
                        }
                }
            }
        }

#if UNITY_EDITOR
        // ──────────── 可達性自我檢查（只在編輯器裡跑）────────────

        const float FloodOutdoor = 16f;
        /// <summary>
        /// 房間（有地板多邊形）用細一點的格子。
        /// ⚠️ 店裡一格寬的走道是斜的（等距 2:1），淨寬只有 ≈18px；16px 的格子四向連通時，
        ///    相鄰兩欄的取樣點常常對不到同一列，會**誤報**走不過去。8px 就夠細了（房間小，格數不多）。
        /// </summary>
        const float FloodRoom = 8f;

        /// <summary>
        /// 障礙建好後跑一次：從出生點用粗格（戶外 16px、房間 8px）flood fill，逐一檢查每個互動點在它的互動距離內
        /// 有沒有走得到的格子。目標是「走不到的互動點」清單為空。
        /// 離線版：tools/check_walkable.py（戶外）、tools/gen_brew_room.py（藥水室）、tools/check_shop_walk.py（店裡）。
        /// </summary>
        static void SelfCheck(int matched)
        {
            float Flood = walkPoly != null ? FloodRoom : FloodOutdoor;
            int nx = Mathf.FloorToInt(walk.width / Flood) + 1;
            int ny = Mathf.FloorToInt(walk.height / Flood) + 1;
            var free = new bool[nx * ny];
            var reach = new bool[nx * ny];
            int start = -1;
            float best = float.MaxValue;
            for (int j = 0; j < ny; j++)
                for (int i = 0; i < nx; i++)
                {
                    var p = Cell(i, j);
                    int k = j * nx + i;
                    free[k] = InWalk(p) && TotalPen(p) <= 0f;
                    float d = (p - spawn).sqrMagnitude;
                    if (free[k] && d < best) { best = d; start = k; }
                }

            int reachable = 0;
            if (start >= 0)
            {
                var stack = new Stack<int>();
                stack.Push(start);
                reach[start] = true;
                while (stack.Count > 0)
                {
                    int k = stack.Pop();
                    reachable++;
                    int i = k % nx, j = k / nx;
                    Visit(i + 1, j); Visit(i - 1, j); Visit(i, j + 1); Visit(i, j - 1);

                    void Visit(int a, int b)
                    {
                        if (a < 0 || b < 0 || a >= nx || b >= ny) return;
                        int q = b * nx + a;
                        if (!free[q] || reach[q]) return;
                        reach[q] = true;
                        stack.Push(q);
                    }
                }
            }

            bool Reach(Vector2 at, float range)
            {
                int i0 = Mathf.Max(0, Mathf.FloorToInt((at.x - range - walk.xMin) / Flood));
                int i1 = Mathf.Min(nx - 1, Mathf.CeilToInt((at.x + range - walk.xMin) / Flood));
                int j0 = Mathf.Max(0, Mathf.FloorToInt((at.y - range - walk.yMin) / Flood));
                int j1 = Mathf.Min(ny - 1, Mathf.CeilToInt((at.y + range - walk.yMin) / Flood));
                for (int j = j0; j <= j1; j++)
                    for (int i = i0; i <= i1; i++)
                        if (reach[j * nx + i] && (Cell(i, j) - at).sqrMagnitude <= range * range) return true;
                return false;
            }

            var bad = new List<string>();
            int points = 0;
            foreach (var g in Object.FindObjectsByType<GatherTree>(FindObjectsSortMode.None))
            {
                points++;
                if (!Reach(g.transform.position, g.gatherRange))
                    bad.Add($"採集 {g.name} {Fmt(g.transform.position)} 範圍 {g.gatherRange:0}");
            }
            foreach (var d in Object.FindObjectsByType<SceneDoor>(FindObjectsSortMode.None))
            {
                points++;
                var at = (Vector2)d.transform.position + new Vector2(d.doorX, d.doorY);
                if (!Reach(at, d.interactRange))
                    bad.Add($"門 {d.name}→{d.targetScene} {Fmt(at)} 按 E 範圍 {d.interactRange:0}");
                else if (d.autoEnter && !Reach(at, d.autoRange))
                    bad.Add($"門 {d.name}→{d.targetScene} {Fmt(at)} 只能按 E，走不到自動觸發的 {d.autoRange:0} 內");
            }
            foreach (var t in Object.FindObjectsByType<TalkNpc>(FindObjectsSortMode.None))
            {
                points++;
                if (!Reach(t.transform.position, t.interactRange))
                    bad.Add($"NPC {t.npcName}（{t.name}）{Fmt(t.transform.position)} 範圍 {t.interactRange:0}");
            }
            foreach (var a in Object.FindObjectsByType<InteractPoint>(FindObjectsSortMode.None))
            {
                points++;
                if (!Reach(a.transform.position, a.interactRange))
                    bad.Add($"互動點 {a.name} {Fmt(a.transform.position)} 範圍 {a.interactRange:0}");
            }
            foreach (var c in Object.FindObjectsByType<BrewCauldron>(FindObjectsSortMode.None))
            {
                points++;
                if (!Reach(c.transform.position, c.interactRange))
                    bad.Add($"鍋爐 {c.name} {Fmt(c.transform.position)} 範圍 {c.interactRange:0}");
            }
            // 店裡的販售桌櫃台不是 InteractPoint（它每幀跟著桌子搬家），另外檢查。
            // 位置直接問 RoomLayout —— SaleCounter 的 transform 要等它自己的 Update 才會搬過去。
            if (SaleCounter.Instance != null && RoomLayout.SaleFront() is Vector2 sale)
            {
                points++;
                if (!Reach(sale, SaleCounter.InteractRange))
                    bad.Add($"販售桌前 {Fmt(sale)} 按 E 範圍 {SaleCounter.InteractRange:0}");
            }
            var gates = Portals.Of(sceneName);
            foreach (var g in gates)
            {
                points++;
                bool ok = false;
                for (int j = 0; j < ny && !ok; j++)
                    for (int i = 0; i < nx && !ok; i++)
                    {
                        if (!reach[j * nx + i]) continue;
                        var p = Cell(i, j);
                        ok = g.Side switch
                        {
                            "right" => p.x >= walk.xMax - Flood && Mathf.Abs(p.y - g.At) <= g.Span,
                            "left" => p.x <= walk.xMin + Flood && Mathf.Abs(p.y - g.At) <= g.Span,
                            "top" => p.y >= walk.yMax - Flood && Mathf.Abs(p.x - g.At) <= g.Span,
                            _ => p.y <= walk.yMin + Flood && Mathf.Abs(p.x - g.At) <= g.Span,
                        };
                    }
                if (!ok) bad.Add($"邊界出口 {g.Side}→{g.To}（At {g.At:0} ±{g.Span:0}）");
            }

            var roadBad = new List<string>();
            if (sceneName == "town")
                foreach (var w in TownRoads.Walk)
                    for (int i = 0; i < count; i++)
                        if (Pen(i, w, 0f) > 0f)      // 路點本身（不含玩家半徑）落在範圍裡
                        {
                            roadBad.Add($"{Fmt(w)} 在 {shapes[i].Name} 裡");
                            break;
                        }

            var cats = new SortedDictionary<string, int>();
            foreach (var s in shapes) cats[s.Category] = cats.TryGetValue(s.Category, out var n) ? n + 1 : 1;
            var catText = new List<string>();
            foreach (var kv in cats) catText.Add($"{kv.Key} {kv.Value}");

            bool spawnInside = TotalPen(spawn) > 0f || !InWalk(spawn);
            var msg = $"[Obstacles] {sceneName}：障礙 {count} 個（{string.Join("、", catText)}；對到表的圖 {matched} 張）；" +
                      $"可走面積 {100f * reachable / free.Length:0.0}%；出生點 {Fmt(spawn)}" + (spawnInside ? "（⚠️ 在障礙裡，靠防卡死走出來）" : "") +
                      $"\n可走範圍 x {walk.xMin:0}..{walk.xMax:0}、y {walk.yMin:0}..{walk.yMax:0}" +
                      (walkPoly != null ? $"（地板多邊形 {walkPoly.Length} 邊）" : "") + $"；檢查了 {points} 個互動點" +
                      "\n走不到的互動點：" + (bad.Count == 0 ? "無" : "\n  - " + string.Join("\n  - ", bad)) +
                      (sceneName == "town"
                          ? "\n落在障礙裡的村民路點（TownNav 會吸附到最近的可站格，不會走進去）：" +
                            (roadBad.Count == 0 ? "無" : "\n  - " + string.Join("\n  - ", roadBad))
                          : "");
            if (bad.Count > 0 || spawnInside) Debug.LogWarning(msg);
            else Debug.Log(msg);

            Vector2 Cell(int i, int j) => new(walk.xMin + i * Flood, walk.yMin + j * Flood);
            static string Fmt(Vector2 v) => $"({v.x:0}, {v.y:0})";
        }
#endif
    }
}
