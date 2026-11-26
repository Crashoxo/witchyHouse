using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Data
{
    /// <summary>格盤上的一格。</summary>
    public struct Cell
    {
        public int gx, gy;
        public Cell(int gx, int gy) { this.gx = gx; this.gy = gy; }
        public override string ToString() => $"{gx},{gy}";
    }

    /// <summary>
    /// 店內等距房間：格子座標系。
    ///
    /// 地板是 GridW × GridH 的等距菱形磚，**一塊磚＝一個家具放置格**。格子座標 (gx, gy)
    /// 的 gx 往畫面右下、gy 往畫面左下：
    ///
    ///     tile(gx,gy) 中心 = ( OriginX + (gx-gy)*TileW/2 , OriginY - (gx+gy)*TileH/2 )
    ///
    /// ⚠️ 這套數學跟原專案 tools/gen_shop_room.py（畫底圖與家具圖的產生器）是同一套，
    ///    改任何一個常數都要兩邊一起改，否則家具會跟磚縫對不齊。
    ///
    /// 家具圖的錨點約定：**圖的正下方中央＝佔地的「前角」**。所以物件用腳底錨點、
    /// 位置擺在 FrontCorner() 算出來的座標即可，position.y 剛好是佔地最前緣 → YSort 自然就對。
    ///
    /// ⚠️ 這是整個專案唯一有自訂座標系的地方，也是**抽座標救不了、只能真的把幾何搬過來**
    ///    的一塊 —— 商店場景在 Cocos 那邊只有 9 個節點，其他全是執行期算出來的。
    /// </summary>
    public static class ShopRoom
    {
        // ⚠️ 磚的尺寸是配合美術來源訂的：等距磚原生輸出 32x32（菱形 32x16），
        //    x2 NEAREST 放大＝遊戲內一格 64x32。改這裡等於要重出所有地板/家具素材。
        public const float TileW = 64f;      // 一格的寬（等距 2:1）
        public const float TileH = 32f;      // 一格的高
        public const int GridW = 14;         // 橫向格數（gx: 0..GridW-1）
        public const int GridH = 10;         // 縱向格數（gy: 0..GridH-1）
        public const float OriginX = -64f;   // tile(0,0) 中心的世界座標
        public const float OriginY = 108f;
        public const float RoomW = 960f;     // 底圖尺寸
        public const float RoomH = 640f;

        /// <summary>格子中心的世界座標。</summary>
        public static Vector2 TileCenter(int gx, int gy) => GridToWorld(gx, gy);

        /// <summary>格子的「下角」＝落地點（家具/裝飾的錨點對在這裡）。</summary>
        public static Vector2 TileFront(int gx, int gy) =>
            new(OriginX + (gx - gy) * TileW / 2f, OriginY - (gx + gy) * TileH / 2f - TileH / 2f);

        /// <summary>佔地 fw×fh 的家具擺在 (gx,gy)（左上角那格）時，前角的世界座標。</summary>
        public static Vector2 FrontCorner(int gx, int gy, int fw, int fh) =>
            TileFront(gx + fw - 1, gy + fh - 1);

        /// <summary>佔地的中心（商品要畫在檯面正中央時用）。</summary>
        public static Vector2 FootprintCenter(int gx, int gy, int fw, int fh)
        {
            var a = TileCenter(gx, gy);
            var b = TileCenter(gx + fw - 1, gy + fh - 1);
            return (a + b) * 0.5f;
        }

        /// <summary>世界座標 → 連續格座標（會是小數，也可能落在格子外）。</summary>
        public static Vector2 ToGrid(float x, float y)
        {
            float a = (x - OriginX) / (TileW / 2f);
            float b = (OriginY - y) / (TileH / 2f);
            return new Vector2((a + b) / 2f, (b - a) / 2f);
        }

        /// <summary>世界座標 → 最近的那一格。</summary>
        public static Cell WorldToTile(float x, float y)
        {
            var g = ToGrid(x, y);
            return new Cell(Mathf.RoundToInt(g.x), Mathf.RoundToInt(g.y));
        }

        /// <summary>這一格在不在地板上。</summary>
        public static bool InGrid(int gx, int gy) =>
            gx >= 0 && gx < GridW && gy >= 0 && gy < GridH;

        /// <summary>佔地 fw×fh 擺在 (gx,gy) 時整塊都在地板上嗎。</summary>
        public static bool Fits(int gx, int gy, int fw, int fh) =>
            InGrid(gx, gy) && InGrid(gx + fw - 1, gy + fh - 1);

        /// <summary>把 (gx,gy) 夾到「整件家具都放得下」的範圍內。</summary>
        public static Cell ClampCell(int gx, int gy, int fw, int fh) =>
            new(Mathf.Clamp(gx, 0, GridW - fw), Mathf.Clamp(gy, 0, GridH - fh));

        /// <summary>連續格座標 → 世界座標（<see cref="ToGrid"/> 的反函數；格子中心是整數、磚緣是 ±0.5）。</summary>
        public static Vector2 GridToWorld(float gx, float gy) =>
            new(OriginX + (gx - gy) * TileW / 2f, OriginY - (gx + gy) * TileH / 2f);

        /// <summary>
        /// 女巫的落腳點離最外圈磚緣至少留幾格（避免整個人站到磚外）。
        /// <see cref="ClampToFloor"/> 與 <see cref="WalkFloor"/> 共用這個值，兩邊的邊界才會一模一樣。
        /// </summary>
        public const float FloorMargin = 0.18f;

        /// <summary>
        /// 把落腳點夾在地板菱形內。
        ///
        /// ⚠️ 等距房間**不能**用 PlayerController 原本的矩形夾邊 —— 塞得進這個菱形的
        ///    最大矩形只有地板的一小塊（地板本身 768×384），玩家會被關在正中間。
        ///    所以改成換算成格座標後夾住 col/row，再換算回來。
        ///    margin 是離最外圈磚緣留幾格（避免整個人站到磚外）。
        /// 女巫本人現在改走 Obstacles（地板多邊形＝<see cref="WalkFloor"/>），這支留給佈置模式拖裝飾用。
        /// </summary>
        public static Vector2 ClampToFloor(float x, float y, float margin = FloorMargin)
        {
            var g = ToGrid(x, y);
            float lo = -0.5f + margin;
            float c = Mathf.Clamp(g.x, lo, GridW - 0.5f - margin);
            float r = Mathf.Clamp(g.y, lo, GridH - 0.5f - margin);
            return GridToWorld(c, r);
        }

        /// <summary>
        /// 女巫在店裡的可走範圍：地板菱形往內縮 margin 格之後的四個頂點（世界座標，順時針：上、右、下、左）。
        /// 給 Obstacles.Begin 的 walkPolygon 用。
        ///
        /// 跟 <see cref="ClampToFloor"/> 是**同一塊區域**：格座標 gx、gy 各自夾在
        /// [-0.5+margin, GridW/GridH-0.5-margin]，在世界上就是一個平行四邊形（等距下是菱形）。
        /// ⚠️ 兩者只差在「點在外面時夾到哪」：ClampToFloor 是在格座標裡各軸分別夾，
        ///    Obstacles.ClampWalk 是取多邊形邊上最近的點 —— 範圍一樣，推牆時的滑動方向略有不同，玩家感覺不出來。
        /// </summary>
        public static Vector2[] WalkFloor(float margin = FloorMargin)
        {
            float lo = -0.5f + margin;
            float hx = GridW - 0.5f - margin, hy = GridH - 0.5f - margin;
            return new[]
            {
                GridToWorld(lo, lo),   // 上角（兩面牆交會處）
                GridToWorld(hx, lo),   // 右角
                GridToWorld(hx, hy),   // 下角
                GridToWorld(lo, hy),   // 左角
            };
        }

        /// <summary>
        /// 家具的碰撞範圍每一邊往內縮幾格（只影響碰撞，不影響擺放規則與畫面）。
        ///
        /// 為什麼要縮：一格的等距菱形只有 64×32，**兩條平行磚緣之間的垂直距離只有 ≈28.6px**
        /// （(32,-16) 投影到磚緣法線上）。女巫腳底是半徑 11 的圓，兩側各吃掉 11 → 一格走道只剩 ≈6.6px，
        /// 斜著走、或滑鼠點地自動走時幾乎一定會卡住。貨架前規定只留一格走道，這條一定要走得過。
        ///
        /// 縮 0.2 格之後：一格走道（兩側都是家具）淨寬 28.6 ×（1 + 2×0.2）≈ 40.1px，
        /// 扣掉 22px 的身寬還剩 ≈18px 的餘裕；家具靠地板邊緣時那一格的淨寬更大（地板邊只縮 FloorMargin）。
        /// 離線驗證：tools/check_shop_walk.py（改這個值要一起改那邊）。
        ///
        /// ⚠️ 代價：兩件家具**斜對角相鄰**（只在一個角點相碰）時，中間那個角縫只有 64×0.2 ≈12.8px，
        ///    女巫過不去 —— 這跟畫面一致（兩件家具在那裡是頂著的），而且旁邊兩格是正常的四向連通，繞得過去。
        ///    要讓角縫也能鑽，得縮到 0.35 格以上，家具看起來就會「站在東西裡面」了，不划算。
        /// ⚠️ 女巫的圖會跟家具的圖疊到一點（約 0.2 格）—— 那是排序（ShopRoomView.PlayerOrder）要處理的，不是碰撞。
        /// </summary>
        public const float FurnitureInset = 0.2f;

        /// <summary>
        /// 佔地 w×h 格、擺在 (gx,gy) 的家具的碰撞多邊形（世界座標四個頂點，順時針：上、右、下、左）。
        /// 格座標從 (gx-0.5+inset, gy-0.5+inset) 到 (gx+w-0.5-inset, gy+h-0.5-inset)，換算成世界座標是等距平行四邊形。
        /// </summary>
        public static Vector2[] FootprintPoly(int gx, int gy, int w, int h, float inset = FurnitureInset)
        {
            float x0 = gx - 0.5f + inset, x1 = gx + w - 0.5f - inset;
            float y0 = gy - 0.5f + inset, y1 = gy + h - 0.5f - inset;
            return new[]
            {
                GridToWorld(x0, y0),   // 上角（後角）
                GridToWorld(x1, y0),   // 右角
                GridToWorld(x1, y1),   // 下角（前角）
                GridToWorld(x0, y1),   // 左角
            };
        }

        /// <summary>
        /// 後牆的高度（世界單位）。
        /// 底圖產生器 gen_shop_room.py 的 WALL_H2 是 96，但那張圖是半解析度 480×320
        /// 畫完再 x2 放大的 —— 所以世界單位要 ×2。改那邊要跟著改這裡。
        /// </summary>
        public const float WallH = 192f;

        static Vector2[] silhouette;

        /// <summary>
        /// 房間的可視輪廓：地板菱形 ＋ 兩面後牆，順時針六個頂點（凸多邊形）。
        ///
        /// 跟底圖產生器 gen_shop_room.py 的 build_room() 是同一組點
        /// （top_v / right_v / left_v，往上長 WALL_H2）。
        /// </summary>
        public static Vector2[] Silhouette()
        {
            if (silhouette != null) return silhouette;

            var top = new Vector2(OriginX, OriginY + TileH / 2f);                  // 兩面牆交會的上頂點
            var right = TileCenter(GridW - 1, 0) + new Vector2(TileW / 2f, 0f);    // 右後牆的外端
            var left = TileCenter(0, GridH - 1) - new Vector2(TileW / 2f, 0f);     // 左後牆的外端
            var bottom = TileCenter(GridW - 1, GridH - 1) - new Vector2(0f, TileH / 2f);
            var up = new Vector2(0f, WallH);

            silhouette = new[] { left + up, top + up, right + up, right, bottom, left };
            return silhouette;
        }

        static Vector2[] floorPoly;

        /// <summary>地板菱形的四個頂點（順時針）—— 牆不算在內。</summary>
        public static Vector2[] Floor()
        {
            if (floorPoly != null) return floorPoly;
            floorPoly = new[]
            {
                new Vector2(OriginX, OriginY + TileH / 2f),                    // 上角（兩面牆交會處）
                TileCenter(GridW - 1, 0) + new Vector2(TileW / 2f, 0f),        // 右角
                TileCenter(GridW - 1, GridH - 1) - new Vector2(0f, TileH / 2f),// 下角
                TileCenter(0, GridH - 1) - new Vector2(TileW / 2f, 0f),        // 左角
            };
            return floorPoly;
        }

        /// <summary>點在凸多邊形內嗎（頂點順時針；margin＝離每條邊至少留幾 px）。</summary>
        static bool InsidePoly(Vector2[] poly, Vector2 p, float margin)
        {
            for (int i = 0; i < poly.Length; i++)
            {
                var a = poly[i];
                var b = poly[(i + 1) % poly.Length];
                var d = b - a;
                float len = d.magnitude;
                if (len < 0.001f) continue;
                // 順時針 → 內側在每條邊的右手邊（外積為負），距離＝外積 / 邊長
                float cross = (d.x * (p.y - a.y) - d.y * (p.x - a.x)) / len;
                if (-cross < margin) return false;
            }
            return true;
        }

        /// <summary>這個點在房間輪廓內嗎（地板 ＋ 兩面牆）。</summary>
        public static bool PointInsideRoom(Vector2 p, float margin = 0f) => InsidePoly(Silhouette(), p, margin);

        /// <summary>這個點踩在地板上嗎（牆不算）。</summary>
        public static bool PointOnFloor(Vector2 p, float margin = 0f) => InsidePoly(Floor(), p, margin);

        /// <summary>
        /// 一張圖的可見範圍會不會凸出房間外。
        ///
        /// ⚠️ 這是「貨架不能穿牆」判準的**上半**：往上長到牆上是可以的（東西站在地板上、
        ///    身體遮住後面的牆本來就對），只是不能凸出房間輪廓。
        ///    **下半**是 RectOnFloor —— 腳一定要踩在地板上，那條才是擋掉「架子埋進牆裡」的。
        ///
        /// ⚠️ 傳進來的要是**圖真正畫到東西的範圍**（見 Data.FurnitureBounds），
        ///    不是整張 PNG 的矩形 —— 家具圖有很大一塊透明邊而且不置中，拿整張比會兩邊都判錯。
        /// </summary>
        public static bool RectInsideRoom(float left, float right, float bottom, float top,
                                          float margin = 4f) =>
            PointInsideRoom(new Vector2(left, bottom), margin)
            && PointInsideRoom(new Vector2(right, bottom), margin)
            && PointInsideRoom(new Vector2(left, top), margin)
            && PointInsideRoom(new Vector2(right, top), margin);

        /// <summary>
        /// 落地的那條邊（圖的底緣）兩端都踩在地板上嗎。
        ///
        /// ⚠️ 這條才是擋掉「貨架埋進牆裡」的關鍵。基準點設成左上/右上時，圖會被搬到佔地的
        ///    另一個角 —— 配錯翻面狀態的話，整個架子會平移到牆面上，但它的四個角其實都還在
        ///    「地板 ＋ 牆」的輪廓裡，所以只驗輪廓是擋不掉的（實際踩到的 bug）。
        /// </summary>
        public static bool RectOnFloor(float left, float right, float bottom, float margin = 0f) =>
            PointOnFloor(new Vector2(left, bottom), margin)
            && PointOnFloor(new Vector2(right, bottom), margin);

        // ──────────── 門與出生點 ────────────

        /// <summary>
        /// 玩家從城鎮進店時的抵達點。
        /// ⚠️ 要離 DoorTown 夠遠：門是「走上去就過圖」的，出生點若太近，
        ///    一進店往前走兩步就會被彈回城鎮。這裡相距 148px。
        /// </summary>
        public static readonly Cell PlayerSpawn = new(6, 5);

        public static readonly Cell DoorTown = new(11, 9);    // 前方（畫面下）走出去回城鎮
        public static readonly Cell DoorBrew = new(13, 0);    // 右角落 → 藥水室
        public static readonly Cell DoorGarden = new(0, 9);   // 左角落 → 後花園

        /// <summary>開店時就送的第一張販售桌擺在哪一格（沒有它就沒辦法賣東西）。</summary>
        public static readonly Cell DefaultSaleCell = new(5, 2);

        /// <summary>
        /// 門口那幾格不給擺東西（擺上去會把出口堵住、光圈也會被蓋掉）。
        /// 一格只有 64×32，光一格擋不住整個門，所以連同上下左右四格一起保留。
        /// </summary>
        public static List<Cell> ReservedCells()
        {
            var outList = new List<Cell>();
            var doors = new[] { DoorTown, DoorBrew, DoorGarden };
            var offsets = new[] { (0, 0), (1, 0), (-1, 0), (0, 1), (0, -1) };
            foreach (var d in doors)
                foreach (var (dx, dy) in offsets)
                {
                    int gx = d.gx + dx, gy = d.gy + dy;
                    if (InGrid(gx, gy)) outList.Add(new Cell(gx, gy));
                }
            return outList;
        }
    }
}
