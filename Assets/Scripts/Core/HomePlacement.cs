using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>家裡放不下的原因（順序＝檢查順序）。</summary>
    public enum HomeBlock
    {
        Ok = 0,
        OffFloor,   // 佔地超出地板（可走範圍）
        Overlap,    // 跟房間原本的家具、或自己擺的別件疊到
        Door,       // 門口（門→出生點那一條）、貓迎接的位置
        UseSpot,    // 床／鍋爐／木箱／衣櫃前面站著按 E 的位置
        CatBed,     // 壓到貓窩
        CutOff,     // 擺下去之後，從門口走不到某個互動點／門，或貓回不了窩
    }

    /// <summary>一件擺在家裡的東西算好的幾何（佔地、碰撞、排序用的 uv 盒子、圖的範圍）。</summary>
    public struct HomeShape
    {
        public string Id;
        public Vector2 Pos;
        public bool Flip;
        public bool Grid, Flat, Blocks;
        /// <summary>完整佔地（凸多邊形，世界座標）：疊到別的東西／禁區的判斷用。地毯＝整張橢圓。</summary>
        public Vector2[] Foot;
        /// <summary>
        /// 擋路的碰撞（吃格子的家具＝佔地每邊內縮 <see cref="HomePlacement.Inset"/> 格，同店裡；其他 null）。
        /// 也是「要在地板上」量的那一塊 —— 圖可以比它多出一點點貼到牆邊。
        /// </summary>
        public Vector2[] Solid;
        /// <summary>地板 uv 的盒子（女巫／貓的前後排序，同 BrewPiece.U0..V1）。</summary>
        public float U0, U1, V0, V1;
        /// <summary>圖真正畫到東西的範圍（世界座標）。</summary>
        public Rect Art;

        public float Depth => (U0 + U1 + V0 + V1) * 0.5f;
    }

    /// <summary>
    /// 家裡（藥水室 brew）自由擺放的規則 —— 純計算，不碰場景（HomeArrange 拖曳時、HomeFurnishings 進房間驗存檔都問這裡）。
    /// 離線版：tools/check_home_place.py（**讀這支檔案的常數**，兩邊不要各寫一份數字）。
    ///
    /// ── 位置 ──
    ///   自由座標，但軟吸附到地板 uv 的 <see cref="Snap"/> 格（看不到格線，只是讓東西排得整齊）。
    ///   吃格子的家具：落腳點＝佔地前角（同店裡的 RoomLayout.AnchorPos），佔地 W×H 格（64×32 的等距格，翻面寬深對調）——
    ///   藥水室的 uv 軸跟店裡的格子軸同方向（u＝畫面右下、v＝畫面左下），一格＝32 uv。
    ///   裝飾：落腳點＝圖的正下方中央，佔地＝Furnishings.DecorFootprint 的小橢圓；地毯：整張橢圓。
    ///
    /// ── 能不能放（<see cref="Check"/>）──
    ///   ① 碰撞那塊（家具內縮後的佔地／裝飾與地毯的橢圓）整個在可走範圍 BrewRoomLayout.Walk 裡
    ///   地毯到這裡只再看 ⑥ 貓窩（可以壓在家具底下、人跟貓都走在上面）
    ///   ② 完整佔地不能疊到房間原本的家具（BrewRoomLayout 的 Poly／Ellipse）或自己擺的別件（地毯除外）
    ///   ③ 不能壓到門口：門→出生點那一條（半徑 <see cref="DoorClear"/>）、貓的門口迎接點（<see cref="GreetClear"/>）
    ///   ④ 不能壓到床／衣櫃／木箱／鍋爐前面站著按 E 的那一塊（<see cref="UseSpots"/>，半徑 <see cref="UseClear"/>）
    ///   ⑤ 不能壓到貓窩（RoomCat.CatBed 的橢圓 <see cref="CatBedHalf"/>）
    ///   ⑥ 會擋路的（吃格子的家具）擺下去之後：從出生點（女巫半徑 11、8px 格、四向）還要走得到每個互動點的範圍內、
    ///      門的自動觸發範圍內；貓（半徑 8）還要能從貓窩走到門口迎接點。不行＝CutOff。
    ///   裝飾不擋路（同店裡），所以不跑 ⑥。
    ///
    /// ── 排序（<see cref="AssignOrders"/>）──
    ///   房間原本的家具是離線拓樸排好的固定 order（約 -3000..-2620、間隔 20），女巫插在中間（BrewRoom.PlayerOrder）。
    ///   擺出來的東西要插進同一條序列：跟它「附近」（圖的範圍各往外長 <see cref="NearX"/>×<see cref="NearY"/>，女巫夾在中間也算得到）的
    ///   每件家具（固定的＋已經排好的）用 uv 盒子判前後 → 夾出 (lo, hi)，取依深度估的基準值夾進去，對齊 4 的倍數。
    ///   女巫拿到的是 lo+1／hi−1（不是 4 的倍數），所以永遠不會跟擺出來的東西同 order。
    /// </summary>
    public static class HomePlacement
    {
        // ── 規則常數（tools/check_home_place.py 用正規式讀這幾行，格式別改）──
        /// <summary>軟吸附：地板 uv 每幾格（px）一個點。</summary>
        public const float Snap = 8f;
        /// <summary>吃格子的家具碰撞內縮（格），同 ShopRoom.FurnitureInset。</summary>
        public const float Inset = 0.2f;
        /// <summary>門→出生點那一條要淨空的半徑。</summary>
        public const float DoorClear = 30f;
        /// <summary>貓的門口迎接點要淨空的半徑。</summary>
        public const float GreetClear = 14f;
        /// <summary>互動點前面站人的那一塊的半徑。</summary>
        public const float UseClear = 22f;
        /// <summary>貓窩不能壓到的橢圓半徑（貓窩畫面上約 44×22）。</summary>
        public static readonly Vector2 CatBedHalf = new(24f, 13f);
        /// <summary>可達性格子（px）。</summary>
        public const float Step = 8f;
        /// <summary>女巫腳底半徑（同 ArtFootprints.PlayerRadius）。</summary>
        public const float PlayerR = ArtFootprints.PlayerRadius;
        /// <summary>貓的腳底半徑（同 RoomCat.Radius）。</summary>
        public const float CatR = RoomCat.Radius;
        /// <summary>排序：兩件東西的圖往外長多少還算「附近」（女巫的身體寬約 34、高約 84，夾在兩件中間時兩件都要比過）。</summary>
        public const float NearX = 40f, NearY = 90f;
        /// <summary>排序基準：order ≈ BaseA + BaseK × 深度（深度＝uv 盒子中心的 u+v；跟房間原本家具的 order 大致對齊）。</summary>
        public const float BaseA = -3032f, BaseK = 0.5f;

        /// <summary>
        /// 床、衣櫃、木箱、鍋爐前面站著按 E 的位置（空房間時從出生點走得到、離互動點最近的那一格；check_home_place.py 驗過在範圍內、站得住）。
        /// </summary>
        public static readonly Vector2[] UseSpots =
        {
            new(212f, -82f),    // 床（BedAt 184,-43.5）
            new(-108f, 102f),   // 衣櫃（WardrobeAt）
            new(-372f, -58f),   // 木箱（ChestAt）
            new(-20f, -154f),   // 鍋爐（CauldronAt，鍋子正前方）
        };

        // ──────────── 幾何 ────────────

        /// <summary>吸附到地板 uv 的 <see cref="Snap"/> 格。</summary>
        public static Vector2 SnapPos(Vector2 world)
        {
            var uv = BrewRoomLayout.ToUV(world.x, world.y);
            float u = Mathf.Round(uv.x / Snap) * Snap, v = Mathf.Round(uv.y / Snap) * Snap;
            return FromUV(u, v);
        }

        public static Vector2 FromUV(float u, float v) =>
            new(BrewRoomLayout.IsoX + u - v, BrewRoomLayout.IsoY - (u + v) * 0.5f);

        /// <summary>算一件東西擺在 pos 的幾何（沒有圖也算得出來，圖的範圍用估的）。</summary>
        public static HomeShape Shape(string id, Vector2 pos, bool flip)
        {
            var s = new HomeShape { Id = id, Pos = pos, Flip = flip };
            s.Grid = Furnishings.IsGrid(id);
            s.Flat = Furnishings.Flat(id);
            s.Blocks = Furnishings.Blocking(id);
            var sp = GameArt.FurnishingArt(id);
            float scale = s.Grid ? 1f : GameArt.DecorScale(id);
            float iw = sp != null ? sp.rect.width : 48f, ih = sp != null ? sp.rect.height : 64f;

            if (s.Grid)
            {
                var d = Furniture.ById(id);
                int w = flip ? d.H : d.W, h = flip ? d.W : d.H;
                s.Foot = Furnishings.FootprintWorld(pos, w, h, 0f);
                s.Solid = Furnishings.FootprintWorld(pos, w, h, Inset);
                var uv = BrewRoomLayout.ToUV(pos.x, pos.y);
                s.U1 = uv.x; s.U0 = uv.x - Furnishings.CellH * w;   // 一格＝32 uv
                s.V1 = uv.y; s.V0 = uv.y - Furnishings.CellH * h;
                // 圖的實心範圍（同 RoomLayout.ArtRect）
                float x0 = 0f, y0 = 0f, x1 = iw, y1 = ih;
                if (sp != null && FurnitureBounds.TryGet(id, iw, ih, out var box)) { x0 = box.X0; y0 = box.Y0; x1 = box.X1; y1 = box.Y1; }
                if (flip) { float l = iw - x1, r = iw - x0; x0 = l; x1 = r; }
                s.Art = new Rect(pos.x - iw * 0.5f + x0, pos.y + y0, x1 - x0, y1 - y0);
            }
            else
            {
                var (c, rx, ry) = Furnishings.DecorFootprint(id, pos, iw * scale);
                s.Foot = Ellipse(c, rx, ry, 16);
                s.Solid = null;
                var uv = BrewRoomLayout.ToUV(c.x, c.y);
                float r = rx / 1.41421356f;                           // 等距的圓：世界半寬 ＝ uv 半徑 × √2
                s.U0 = uv.x - r; s.U1 = uv.x + r; s.V0 = uv.y - r; s.V1 = uv.y + r;
                s.Art = new Rect(pos.x - iw * scale * 0.5f, pos.y, iw * scale, ih * scale);
            }
            return s;
        }

        /// <summary>軸對齊橢圓 → 凸多邊形（逆時針）。</summary>
        public static Vector2[] Ellipse(Vector2 c, float rx, float ry, int n)
        {
            var pts = new Vector2[n];
            for (int i = 0; i < n; i++)
            {
                float a = i * Mathf.PI * 2f / n;
                pts[i] = c + new Vector2(Mathf.Cos(a) * rx, Mathf.Sin(a) * ry);
            }
            return pts;
        }

        // ──────────── 房間原本的東西（只算一次）────────────

        struct Fixed
        {
            public string Name;
            public Vector2[] Poly;        // 凸多邊形（逆時針）；橢圓也轉一份給 SAT 用
            public bool Ellipse;
            public Vector2 C, H;          // 橢圓
        }

        struct SortBox
        {
            public float U0, U1, V0, V1;
            public Rect Rect;
            public int Order;
        }

        static Fixed[] fixedShapes;
        static SortBox[] fixedSort;
        static Vector2[] walkCcw;
        static Vector2[] catBedPoly;
        static Vector2 catBedAt;

        static void EnsureFixed()
        {
            if (fixedShapes != null && catBedAt == RoomCat.CatBed) return;
            var list = new List<Fixed>();
            var sort = new List<SortBox>();
            foreach (var p in BrewRoomLayout.Pieces)
            {
                if (p.Shape == BrewShape.Poly)
                    list.Add(new Fixed { Name = p.Name, Poly = Ccw(p.Poly) });
                else if (p.Shape == BrewShape.Ellipse)
                {
                    var c = new Vector2(p.Cx, p.Cy);
                    var h = new Vector2(p.Hx, p.Hy);
                    list.Add(new Fixed { Name = p.Name, Poly = Ellipse(c, h.x, h.y, 16), Ellipse = true, C = c, H = h });
                }
                if (p.Kind == BrewKind.Stand && p.Name != "cat")
                    sort.Add(new SortBox
                    {
                        U0 = p.U0, U1 = p.U1, V0 = p.V0, V1 = p.V1, Order = p.Order,
                        Rect = Rect.MinMaxRect(p.RectXMin, p.RectYMin, p.RectXMax, p.RectYMax),
                    });
            }
            fixedShapes = list.ToArray();
            fixedSort = sort.ToArray();
            walkCcw = Ccw(BrewRoomLayout.Walk);
            catBedAt = RoomCat.CatBed;
            catBedPoly = Ellipse(catBedAt, CatBedHalf.x, CatBedHalf.y, 16);
            baseFreePlayer = null;
            baseFreeCat = null;
        }

        // ──────────── 判斷 ────────────

        /// <summary>
        /// me 擺得下嗎（others＝家裡其他已經擺好的，不含 me 自己）。
        /// reach ＝ 要不要跑 ⑥ 可達性（拖曳中每換一格都跑，約 7000 格的 flood，夠快）。
        /// </summary>
        public static HomeBlock Check(in HomeShape me, IReadOnlyList<HomeShape> others, bool reach = true)
        {
            EnsureFixed();
            // ① 在地板上
            var inner = me.Solid ?? me.Foot;
            foreach (var q in inner)
                if (PolyDist(walkCcw, q) > 0f) return HomeBlock.OffFloor;

            if (me.Flat)
                return Overlaps(me.Foot, catBedPoly) ? HomeBlock.CatBed : HomeBlock.Ok;

            // ② 疊到別的東西
            foreach (var f in fixedShapes)
                if (Overlaps(me.Foot, f.Poly)) return HomeBlock.Overlap;
            if (others != null)
                foreach (var o in others)
                    if (!o.Flat && Overlaps(me.Foot, o.Foot)) return HomeBlock.Overlap;

            // ③ 門口
            if (PolyNearSegment(me.Foot, BrewRoomLayout.ExitAt, BrewRoomLayout.Spawn, DoorClear)) return HomeBlock.Door;
            if (PolyNearSegment(me.Foot, RoomCat.DoorGreet, RoomCat.DoorGreet, GreetClear)) return HomeBlock.Door;

            // ④ 互動點前面
            foreach (var u in UseSpots)
                if (PolyNearSegment(me.Foot, u, u, UseClear)) return HomeBlock.UseSpot;

            // ⑤ 貓窩
            if (Overlaps(me.Foot, catBedPoly)) return HomeBlock.CatBed;

            // ⑥ 擋路
            if (reach && me.Blocks)
            {
                var solids = new List<Vector2[]>();
                if (others != null) foreach (var o in others) if (o.Blocks && o.Solid != null) solids.Add(o.Solid);
                solids.Add(me.Solid);
                if (!ReachOk(solids)) return HomeBlock.CutOff;
            }
            return HomeBlock.Ok;
        }

        // ──────────── 可達性 ────────────

        static bool[] baseFreePlayer, baseFreeCat;
        static int gw, gh;
        static Vector2 gOrigin;

        static void EnsureBaseGrid()
        {
            EnsureFixed();
            if (baseFreePlayer != null) return;
            float x0 = float.MaxValue, y0 = float.MaxValue, x1 = float.MinValue, y1 = float.MinValue;
            foreach (var q in walkCcw) { x0 = Mathf.Min(x0, q.x); x1 = Mathf.Max(x1, q.x); y0 = Mathf.Min(y0, q.y); y1 = Mathf.Max(y1, q.y); }
            gOrigin = new Vector2(x0, y0);
            gw = Mathf.FloorToInt((x1 - x0) / Step) + 1;
            gh = Mathf.FloorToInt((y1 - y0) / Step) + 1;
            baseFreePlayer = new bool[gw * gh];
            baseFreeCat = new bool[gw * gh];
            for (int j = 0; j < gh; j++)
                for (int i = 0; i < gw; i++)
                {
                    var p = Cell(i, j);
                    if (PolyDist(walkCcw, p) > 0f) continue;
                    baseFreePlayer[j * gw + i] = FixedPen(p, PlayerR) <= 0f;
                    baseFreeCat[j * gw + i] = FixedPen(p, CatR) <= 0f;
                }
        }

        static Vector2 Cell(int i, int j) => gOrigin + new Vector2(i * Step, j * Step);

        /// <summary>房間原本家具的穿入深度（同 Obstacles.Pen：多邊形往外長 r、橢圓半徑各加 r）。</summary>
        static float FixedPen(Vector2 p, float r)
        {
            float worst = float.MinValue;
            foreach (var f in fixedShapes)
            {
                float v;
                if (f.Ellipse)
                {
                    float rx = f.H.x + r, ry = f.H.y + r;
                    float ex = (p.x - f.C.x) / rx, ey = (p.y - f.C.y) / ry;
                    v = (1f - Mathf.Sqrt(ex * ex + ey * ey)) * Mathf.Min(rx, ry);
                }
                else v = r - PolyDist(f.Poly, p);
                if (v > worst) worst = v;
            }
            return worst;
        }

        /// <summary>加上這些碰撞多邊形之後的可站格（半徑 r）。</summary>
        static bool[] FreeGrid(List<Vector2[]> solids, float r, bool[] baseFree)
        {
            var free = (bool[])baseFree.Clone();
            foreach (var s in solids)
            {
                if (s == null) continue;
                var poly = Ccw(s);
                float x0 = float.MaxValue, y0 = float.MaxValue, x1 = float.MinValue, y1 = float.MinValue;
                foreach (var q in poly) { x0 = Mathf.Min(x0, q.x); x1 = Mathf.Max(x1, q.x); y0 = Mathf.Min(y0, q.y); y1 = Mathf.Max(y1, q.y); }
                int i0 = Mathf.Max(0, Mathf.FloorToInt((x0 - r - gOrigin.x) / Step)), i1 = Mathf.Min(gw - 1, Mathf.CeilToInt((x1 + r - gOrigin.x) / Step));
                int j0 = Mathf.Max(0, Mathf.FloorToInt((y0 - r - gOrigin.y) / Step)), j1 = Mathf.Min(gh - 1, Mathf.CeilToInt((y1 + r - gOrigin.y) / Step));
                for (int j = j0; j <= j1; j++)
                    for (int i = i0; i <= i1; i++)
                    {
                        int k = j * gw + i;
                        if (free[k] && r - PolyDist(poly, Cell(i, j)) > 0f) free[k] = false;
                    }
            }
            return free;
        }

        /// <summary>從 start 最近的可站格四向 flood（同 Obstacles.SelfCheck）。</summary>
        static bool[] Flood(bool[] free, Vector2 start)
        {
            var reach = new bool[free.Length];
            int s = NearestIndex(free, start, 8);
            if (s < 0) return reach;
            var stack = new Stack<int>();
            stack.Push(s);
            reach[s] = true;
            while (stack.Count > 0)
            {
                int k = stack.Pop();
                int i = k % gw, j = k / gw;
                Visit(i + 1, j); Visit(i - 1, j); Visit(i, j + 1); Visit(i, j - 1);
                void Visit(int a, int b)
                {
                    if (a < 0 || b < 0 || a >= gw || b >= gh) return;
                    int q = b * gw + a;
                    if (!free[q] || reach[q]) return;
                    reach[q] = true;
                    stack.Push(q);
                }
            }
            return reach;
        }

        static int NearestIndex(bool[] mask, Vector2 p, int maxR)
        {
            int ci = Mathf.RoundToInt((p.x - gOrigin.x) / Step), cj = Mathf.RoundToInt((p.y - gOrigin.y) / Step);
            int best = -1;
            float bd = float.MaxValue;
            for (int rr = 0; rr <= maxR && best < 0; rr++)
                for (int j = cj - rr; j <= cj + rr; j++)
                    for (int i = ci - rr; i <= ci + rr; i++)
                    {
                        if (i < 0 || j < 0 || i >= gw || j >= gh || !mask[j * gw + i]) continue;
                        float d = (Cell(i, j) - p).sqrMagnitude;
                        if (d < bd) { bd = d; best = j * gw + i; }
                    }
            return best;
        }

        static bool AnyWithin(bool[] reach, Vector2 at, float range)
        {
            int i0 = Mathf.Max(0, Mathf.FloorToInt((at.x - range - gOrigin.x) / Step)), i1 = Mathf.Min(gw - 1, Mathf.CeilToInt((at.x + range - gOrigin.x) / Step));
            int j0 = Mathf.Max(0, Mathf.FloorToInt((at.y - range - gOrigin.y) / Step)), j1 = Mathf.Min(gh - 1, Mathf.CeilToInt((at.y + range - gOrigin.y) / Step));
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                    if (reach[j * gw + i] && (Cell(i, j) - at).sqrMagnitude <= range * range) return true;
            return false;
        }

        /// <summary>
        /// 這些碰撞多邊形（家裡擺的、會擋路的全部）擋下去之後，女巫從出生點還走得到每個互動點與門、貓還回得了窩嗎。
        /// </summary>
        public static bool ReachOk(List<Vector2[]> solids)
        {
            EnsureBaseGrid();
            var reach = Flood(FreeGrid(solids, PlayerR, baseFreePlayer), BrewRoomLayout.Spawn);
            if (!AnyWithin(reach, BrewRoomLayout.BedAt, BrewRoomLayout.BedRange)) return false;
            if (!AnyWithin(reach, BrewRoomLayout.WardrobeAt, BrewRoomLayout.WardrobeRange)) return false;
            if (!AnyWithin(reach, BrewRoomLayout.ChestAt, BrewRoomLayout.ChestRange)) return false;
            if (!AnyWithin(reach, BrewRoomLayout.CauldronAt, BrewRoomLayout.CauldronRange)) return false;
            if (!AnyWithin(reach, BrewRoomLayout.ExitAt, BrewRoomLayout.ExitAuto)) return false;

            var catFree = FreeGrid(solids, CatR, baseFreeCat);
            var catReach = Flood(catFree, RoomCat.CatBed);
            int g = NearestIndex(catFree, RoomCat.DoorGreet, 6);
            return g >= 0 && catReach[g];
        }

        /// <summary>
        /// 離 p 最近、從出生點走得到的可站點（半徑 r；solids＝家裡會擋路的碰撞）。找不到回 p。
        /// 東西擺到女巫／貓腳下時把人挪出來用。
        /// </summary>
        public static Vector2 NearestReachable(Vector2 p, float r, List<Vector2[]> solids)
        {
            EnsureBaseGrid();
            bool cat = r < PlayerR - 0.01f;
            var free = FreeGrid(solids, cat ? CatR : PlayerR, cat ? baseFreeCat : baseFreePlayer);
            var reach = cat ? Flood(free, RoomCat.CatBed) : Flood(free, BrewRoomLayout.Spawn);
            int k = NearestIndex(reach, p, Mathf.Max(gw, gh));
            return k < 0 ? p : Cell(k % gw, k / gw);
        }

        // ──────────── 排序 ────────────

        /// <summary>
        /// 幫每件站著的東西排 order（地毯另外排在 FurnishingVisual.FlatOrder 上）。orders[i] 對 items[i]。
        /// 演算法見類別說明。結果都是 4 的倍數。
        /// </summary>
        public static void AssignOrders(IReadOnlyList<HomeShape> items, int[] orders)
        {
            EnsureFixed();
            int n = items.Count;
            var idx = new List<int>(n);
            int flat = 0;
            for (int i = 0; i < n; i++)
            {
                if (items[i].Flat) { orders[i] = FurnishingVisual.FlatOrder + flat++; continue; }
                idx.Add(i);
            }
            // 從後面排到前面（深度小＝後面），同深度照原順序
            idx.Sort((a, b) =>
            {
                int c = items[a].Depth.CompareTo(items[b].Depth);
                return c != 0 ? c : a.CompareTo(b);
            });
            var done = new List<int>(n);
            foreach (int i in idx)
            {
                var me = items[i];
                float lo = float.NegativeInfinity, hi = float.PositiveInfinity;
                foreach (var f in fixedSort)
                {
                    if (!Near(me.Art, f.Rect)) continue;
                    if (Front(me.U0, me.U1, me.V0, me.V1, f.U0, f.U1, f.V0, f.V1)) lo = Mathf.Max(lo, f.Order);
                    else hi = Mathf.Min(hi, f.Order);
                }
                foreach (int j in done)
                {
                    var o = items[j];
                    if (!Near(me.Art, o.Art)) continue;
                    if (Front(me.U0, me.U1, me.V0, me.V1, o.U0, o.U1, o.V0, o.V1)) lo = Mathf.Max(lo, orders[j]);
                    else hi = Mathf.Min(hi, orders[j]);
                }
                orders[i] = Pick(BaseA + BaseK * me.Depth, lo, hi);
                done.Add(i);
            }
        }

        static int Pick(float baseOrder, float lo, float hi)
        {
            float want = baseOrder;
            bool hasLo = !float.IsNegativeInfinity(lo), hasHi = !float.IsPositiveInfinity(hi);
            if (hasLo && hasHi && hi - lo < 8f) want = (lo + hi) * 0.5f;   // 夾得太緊（或矛盾）：取中間
            else
            {
                if (hasLo) want = Mathf.Max(want, lo + 4f);
                if (hasHi) want = Mathf.Min(want, hi - 4f);
            }
            int c = Mathf.RoundToInt(want / 4f) * 4;
            if (hasLo && c <= lo) c += 4;
            if (hasHi && c >= hi && (!hasLo || c - 4 > lo)) c -= 4;
            return c;
        }

        static bool Near(Rect a, Rect b) =>
            a.xMin - NearX < b.xMax && b.xMin < a.xMax + NearX && a.yMin - NearY < b.yMax && b.yMin < a.yMax + NearY;

        /// <summary>
        /// a 的 uv 盒子在 b 前面嗎：某一軸完全分開就看那一軸（兩軸方向相反＝左右並排，看中心深度）；
        /// 盒子重疊（不該發生）也看中心深度。同 BrewRoom.PlayerOrder 的判法。
        /// </summary>
        public static bool Front(float au0, float au1, float av0, float av1, float bu0, float bu1, float bv0, float bv1)
        {
            int su = au0 >= bu1 ? 1 : bu0 >= au1 ? -1 : 0;
            int sv = av0 >= bv1 ? 1 : bv0 >= av1 ? -1 : 0;
            if (su != 0 && sv != 0 && su != sv) su = sv = 0;
            if (su != 0) return su > 0;
            if (sv != 0) return sv > 0;
            return au0 + au1 + av0 + av1 > bu0 + bu1 + bv0 + bv1;
        }

        // ──────────── 多邊形小工具 ────────────

        public static Vector2[] Ccw(Vector2[] pts)
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

        /// <summary>點到凸多邊形（逆時針）的有號距離：外面正、裡面負（同 Obstacles.PolyDist）。</summary>
        public static float PolyDist(Vector2[] poly, Vector2 p)
        {
            bool inside = true;
            float best = float.MaxValue;
            for (int i = 0, n = poly.Length; i < n; i++)
            {
                var a = poly[i];
                var b = poly[(i + 1) % n];
                var d = b - a;
                float l2 = d.sqrMagnitude;
                if (l2 < 1e-8f) continue;
                float t = Mathf.Clamp01(Vector2.Dot(p - a, d) / l2);
                float dist = (p - (a + d * t)).sqrMagnitude;
                if (dist < best) best = dist;
                if (d.x * (p.y - a.y) - d.y * (p.x - a.x) < 0f) inside = false;
            }
            best = Mathf.Sqrt(best);
            return inside ? -best : best;
        }

        /// <summary>兩個凸多邊形有沒有重疊（分離軸；只碰到邊不算）。</summary>
        public static bool Overlaps(Vector2[] a, Vector2[] b)
        {
            return !Separated(a, b) && !Separated(b, a);

            static bool Separated(Vector2[] p, Vector2[] q)
            {
                for (int i = 0; i < p.Length; i++)
                {
                    var e = p[(i + 1) % p.Length] - p[i];
                    var nrm = new Vector2(-e.y, e.x);
                    if (nrm.sqrMagnitude < 1e-10f) continue;
                    float pmin = float.MaxValue, pmax = float.MinValue, qmin = float.MaxValue, qmax = float.MinValue;
                    foreach (var v in p) { float d = Vector2.Dot(v, nrm); pmin = Mathf.Min(pmin, d); pmax = Mathf.Max(pmax, d); }
                    foreach (var v in q) { float d = Vector2.Dot(v, nrm); qmin = Mathf.Min(qmin, d); qmax = Mathf.Max(qmax, d); }
                    if (pmax <= qmin + 1e-3f || qmax <= pmin + 1e-3f) return true;
                }
                return false;
            }
        }

        /// <summary>凸多邊形離線段 a–b 不到 r（含線段穿過多邊形）。a＝b 時就是圓。</summary>
        public static bool PolyNearSegment(Vector2[] poly, Vector2 a, Vector2 b, float r)
        {
            var ccw = Ccw(poly);
            if (PolyDist(ccw, a) <= r || PolyDist(ccw, b) <= r) return true;
            for (int i = 0; i < poly.Length; i++)
            {
                var p = poly[i];
                var q = poly[(i + 1) % poly.Length];
                if (SegSegDist(a, b, p, q) <= r) return true;
            }
            return false;
        }

        static float SegPointDist(Vector2 a, Vector2 b, Vector2 p)
        {
            var d = b - a;
            float l2 = d.sqrMagnitude;
            float t = l2 < 1e-8f ? 0f : Mathf.Clamp01(Vector2.Dot(p - a, d) / l2);
            return Vector2.Distance(p, a + d * t);
        }

        static float SegSegDist(Vector2 a, Vector2 b, Vector2 c, Vector2 d)
        {
            if (SegmentsCross(a, b, c, d)) return 0f;
            return Mathf.Min(Mathf.Min(SegPointDist(a, b, c), SegPointDist(a, b, d)),
                             Mathf.Min(SegPointDist(c, d, a), SegPointDist(c, d, b)));
        }

        static bool SegmentsCross(Vector2 a, Vector2 b, Vector2 c, Vector2 d)
        {
            float Cross(Vector2 o, Vector2 p, Vector2 q) => (p.x - o.x) * (q.y - o.y) - (p.y - o.y) * (q.x - o.x);
            float d1 = Cross(c, d, a), d2 = Cross(c, d, b), d3 = Cross(a, b, c), d4 = Cross(a, b, d);
            return ((d1 > 0f && d2 < 0f) || (d1 < 0f && d2 > 0f)) && ((d3 > 0f && d4 < 0f) || (d3 < 0f && d4 > 0f));
        }

        /// <summary>原因 → 提示圖示（tools/gen_ui_icons.py 的那幾張；貓窩用貓的圖，見 HomeArrange）。</summary>
        public static string BlockIcon(HomeBlock b) => b switch
        {
            HomeBlock.OffFloor => "blk_offfloor",
            HomeBlock.Overlap => "blk_overlap",
            HomeBlock.Door => "blk_door",
            HomeBlock.UseSpot => "key_e",
            HomeBlock.CutOff => "blk_aisle",
            HomeBlock.CatBed => "blk_overlap",
            _ => "st_no",
        };
    }
}
