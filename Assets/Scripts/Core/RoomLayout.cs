using System;
using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 擺出來的一件家具。
    ///
    /// flip＝左右鏡像。家具圖是等距的，鏡像＝把 scale.x 取負，位置完全不用改。
    /// ⚠️ 光源會從左上翻到右上 —— 實際擺出來看不太出來，比再生一組八朝向划算。
    /// </summary>
    /// <summary>
    /// 家具圖對齊佔地的哪一個角。
    ///
    /// 等距房間的 gx 往右下、gy 往左下，所以房間有兩面後牆：gx=0 那排（左後牆）
    /// 與 gy=0 那排（右後牆）。貨架的圖是「背板朝畫面左上、開口朝右下」畫的 ——
    /// 預設給左後牆用；要靠右後牆就得翻面，而翻面之後基準點要換一個角才貼得住牆。
    /// </summary>
    public enum FurnitureAnchor
    {
        Front = 0,   // 佔地的前角（最靠畫面下方那一角）—— 桌椅類的預設
        Left = 1,    // 佔地的左角 —— 靠左後牆的貨架
        Right = 2,   // 佔地的右角 —— 靠右後牆的貨架（通常搭配翻面）
    }

    [Serializable]
    public class PlacedFurniture
    {
        public string id;
        public int gx, gy;
        public bool flip;
        /// <summary>對齊哪個角（見 FurnitureAnchor）。舊存檔沒這欄＝0＝Front。</summary>
        public int anchor;

        /// <summary>
        /// 轉向後的實際佔地。
        ///
        /// ⚠️ 等距房間裡「轉向」不只是把圖鏡像 —— **佔地的寬深也要對調**。
        ///    一個 1×3 的貨架靠左後牆是「1 寬 3 深」，轉去靠右後牆就變成「3 寬 1 深」。
        ///    只鏡像圖不換佔地的話，地上的格子提示會跟實際擋住的範圍對不起來。
        /// </summary>
        public (int W, int H) Size
        {
            get
            {
                var d = Furniture.ById(id);
                if (d == null) return (1, 1);
                return flip ? (d.H, d.W) : (d.W, d.H);
            }
        }

        public PlacedFurniture() { }
        public PlacedFurniture(string id, int gx, int gy, bool flip = false, int anchor = 0)
        { this.id = id; this.gx = gx; this.gy = gy; this.flip = flip; this.anchor = anchor; }

        public FurnitureAnchor Anchor => (FurnitureAnchor)Mathf.Clamp(anchor, 0, 2);
    }

    /// <summary>
    /// 家具放不下的原因 —— 佈置模式要把「為什麼不行」講給玩家聽，
    /// 光是「移不動」玩家只會以為卡住了。順序＝檢查順序（見 RoomLayout.Check）。
    /// </summary>
    public enum PlaceBlock
    {
        Ok = 0,
        OffFloor,      // 佔地超出地板
        Overlap,       // 跟別件家具重疊
        Door,          // 壓到門口的保留格
        Aisle,         // 壓到別的貨架前方的走道
        NoAisle,       // 自己前方的走道被擋住、或走道不在地板上
        ThroughWall,   // 格子沒問題，但圖會穿出牆外
    }

    /// <summary>
    /// 店裡的家具擺在哪幾格（存檔 key: witch.room）。
    ///
    /// 分成「擁有幾件」與「擺出來的清單」兩份 —— 買了可以先收著不擺，
    /// 佈置模式的托盤就是列 Unplaced() 的那些。
    /// </summary>
    public static class RoomLayout
    {
        const string Key = "witch.room";

        /// <summary>販售桌檯面離地多高（跟原專案 gen_shop_room.py 裡 sale_table 的 height 一致）。</summary>
        const float SaleTopH = 20f;
        /// <summary>顧客站在桌前角再往畫面下方多遠（不要跟桌子疊在一起）。</summary>
        const float SaleStandGap = 26f;

        [Serializable]
        class SaveShape
        {
            public List<string> ownedKeys = new();
            public List<int> ownedCounts = new();
            public List<PlacedFurniture> placed = new();
        }

        static SaveShape data;

        static SaveShape Data
        {
            get { data ??= Load(); return data; }
        }

        /// <summary>新開的店：送一張販售桌並擺在預設位置。</summary>
        static SaveShape Blank()
        {
            var s = new SaveShape();
            s.ownedKeys.Add("sale_table");
            s.ownedCounts.Add(1);
            s.placed.Add(new PlacedFurniture("sale_table",
                ShopRoom.DefaultSaleCell.gx, ShopRoom.DefaultSaleCell.gy));
            return s;
        }

        static SaveShape Load()
        {
            try
            {
                var raw = SaveManager.GetString(Key);
                if (!string.IsNullOrEmpty(raw))
                {
                    var o = JsonUtility.FromJson<SaveShape>(raw);
                    if (o != null)
                    {
                        var clean = new SaveShape();
                        // 只收得認得的家具（房間改過、家具被移除的舊存檔不會壞）
                        for (int i = 0; i < o.ownedKeys.Count && i < o.ownedCounts.Count; i++)
                            if (Furniture.ById(o.ownedKeys[i]) != null)
                            {
                                clean.ownedKeys.Add(o.ownedKeys[i]);
                                clean.ownedCounts.Add(o.ownedCounts[i]);
                            }
                        foreach (var p in o.placed)
                        {
                            var d = p == null ? null : Furniture.ById(p.id);
                            if (d == null) continue;
                            if (!ShopRoom.Fits(p.gx, p.gy, d.W, d.H)) continue;   // 房間改過大小的舊存檔
                            clean.placed.Add(new PlacedFurniture(d.Id, p.gx, p.gy, p.flip, p.anchor));
                        }
                        EnsureSaleTable(clean);
                        return clean;
                    }
                }
            }
            catch { /* 壞檔就當新的 */ }
            return Blank();
        }

        /// <summary>舊檔沒有販售桌就補一張，不然店開不了。</summary>
        static void EnsureSaleTable(SaveShape s)
        {
            foreach (var p in s.placed)
            {
                var d = Furniture.ById(p.id);
                if (d != null && d.Sale) return;
            }
            SetOwned(s, "sale_table", Mathf.Max(1, GetOwned(s, "sale_table")));
            s.placed.Add(new PlacedFurniture("sale_table",
                ShopRoom.DefaultSaleCell.gx, ShopRoom.DefaultSaleCell.gy));
        }

        static int GetOwned(SaveShape s, string id)
        {
            int i = s.ownedKeys.IndexOf(id);
            return i < 0 ? 0 : s.ownedCounts[i];
        }

        static void SetOwned(SaveShape s, string id, int n)
        {
            int i = s.ownedKeys.IndexOf(id);
            if (i < 0) { s.ownedKeys.Add(id); s.ownedCounts.Add(n); }
            else s.ownedCounts[i] = n;
        }

        static void Save() => SaveManager.SetString(Key, JsonUtility.ToJson(Data));

        /// <summary>某件家具佔的所有格子。</summary>
        static IEnumerable<Cell> CellsOf(PlacedFurniture p)
        {
            var (w, h) = p.Size;      // 轉向後的佔地
            if (w <= 0) yield break;
            for (int c = 0; c < w; c++)
                for (int r = 0; r < h; r++)
                    yield return new Cell(p.gx + c, p.gy + r);
        }

        /// <summary>格子當 HashSet 的 key（重疊檢查用）。</summary>
        static string CellKey(Cell c) => $"{c.gx},{c.gy}";

        // ──────────── 對外 API ────────────

        public static FurnitureDef Def(string id) => Furniture.ById(id);

        public static int OwnedCount(string id) => GetOwned(Data, id);

        public static List<PlacedFurniture> PlacedList() => new(Data.placed);

        public static int PlacedCountOf(string id)
        {
            int n = 0;
            foreach (var p in Data.placed) if (p.id == id) n++;
            return n;
        }

        /// <summary>買了但還沒擺出來的數量（＝托盤裡可以拿出來擺的）。</summary>
        public static int Unplaced(string id) => Mathf.Max(0, OwnedCount(id) - PlacedCountOf(id));

        /// <summary>花金幣買一件（錢不夠回 false）。</summary>
        public static bool Buy(string id)
        {
            var d = Furniture.ById(id);
            if (d == null || d.Price <= 0 || Wallet.Gold < d.Price) return false;
            Wallet.Add(-d.Price);
            DailyLog.RecordSpend(d.Price);
            SetOwned(Data, id, OwnedCount(id) + 1);
            Save();
            return true;
        }

        /// <summary>
        /// 這件家具放得進 (gx,gy) 嗎：整塊要在地板上，而且不能跟別件重疊。
        /// </summary>
        /// <param name="skip">搬動中的那一件（檢查時要忽略它自己原本佔的格子）</param>
        public static bool CanPlace(string id, int gx, int gy, PlacedFurniture skip = null,
                                    bool flipped = false)
        {
            var d = Furniture.ById(id);
            if (d == null) return false;
            int w = flipped ? d.H : d.W, h = flipped ? d.W : d.H;
            if (!ShopRoom.Fits(gx, gy, w, h)) return false;

            var taken = new HashSet<string>();
            foreach (var p in Data.placed)
            {
                if (skip != null && ReferenceEquals(p, skip)) continue;
                foreach (var c in CellsOf(p)) taken.Add(CellKey(c));
            }
            for (int c = 0; c < w; c++)
                for (int r = 0; r < h; r++)
                    if (taken.Contains($"{gx + c},{gy + r}")) return false;
            return true;
        }

        /// <summary>
        /// 貨架前方必須淨空的那排格子 —— 玩家要走得過去拿東西。
        ///
        /// 等距房間的 gx 往右下、gy 往左下，而貨架的圖是「背板朝左上、開口朝右下」：
        ///   沒轉向（靠左後牆，1×N）→ 開口朝 +gx，前方是 gx+w 那一列
        ///   轉向後（靠右後牆，N×1）→ 開口朝 +gy，前方是 gy+h 那一排
        /// 非貨架（桌椅）不留走道，回空的。
        /// </summary>
        public static List<Cell> FrontClearance(PlacedFurniture p)
        {
            var outList = new List<Cell>();
            var d = Furniture.ById(p.id);
            if (d == null || !d.Shelf) return outList;

            var (w, h) = p.Size;
            if (!p.flip)
                for (int r = 0; r < h; r++) outList.Add(new Cell(p.gx + w, p.gy + r));
            else
                for (int c = 0; c < w; c++) outList.Add(new Cell(p.gx + c, p.gy + h));
            return outList;
        }

        /// <summary>
        /// 這件家具擺在 (gx,gy) 時，會不會擋到別的貨架的走道、或自己的走道被擋住。
        /// </summary>
        /// <param name="flipped">要檢查的轉向狀態</param>
        public static bool ClearanceOk(string id, int gx, int gy, PlacedFurniture skip, bool flipped)
        {
            var me = new PlacedFurniture(id, gx, gy, flipped);
            var d = Furniture.ById(id);
            if (d == null) return false;
            var (w, h) = me.Size;

            // 我自己佔的格子
            var mine = new HashSet<string>();
            for (int c = 0; c < w; c++)
                for (int r = 0; r < h; r++) mine.Add($"{gx + c},{gy + r}");

            foreach (var other in Data.placed)
            {
                if (skip != null && ReferenceEquals(other, skip)) continue;

                // ① 我不能壓在別人的走道上
                foreach (var c in FrontClearance(other))
                    if (mine.Contains($"{c.gx},{c.gy}")) return false;

                // ② 別人不能壓在我的走道上
                var (ow, oh) = other.Size;
                foreach (var c in FrontClearance(me))
                    if (c.gx >= other.gx && c.gx < other.gx + ow
                        && c.gy >= other.gy && c.gy < other.gy + oh) return false;
            }

            // ③ 我的走道要在地板上（貨架不能背對著地板邊緣，那樣前面沒地方站）
            foreach (var c in FrontClearance(me))
                if (!ShopRoom.InGrid(c.gx, c.gy)) return false;

            return true;
        }

        /// <summary>
        /// 這件家具擺在 (gx,gy) 行不行 —— 不行的話**回傳是哪一條規則擋的**。
        ///
        /// 佈置模式（拖曳、翻面、換基準點、從托盤放進來）全部走這一支，
        /// 四個入口才不會各檢查各的、規則對不起來。<see cref="CanPlace"/> 與
        /// <see cref="ClearanceOk"/> 是它的其中兩條規則，留著給只問單一條件的地方用。
        /// </summary>
        /// <param name="skip">搬動中的那一件（要忽略它自己原本佔的格子）</param>
        /// <param name="flipped">要檢查的轉向狀態</param>
        /// <param name="anchor">要檢查的基準角（圖會落在哪 → 會不會穿牆）</param>
        /// <param name="conflicts">不是 null 的話，填入「擋住我的那幾格」給提示用</param>
        public static PlaceBlock Check(string id, int gx, int gy, PlacedFurniture skip,
                                       bool flipped, FurnitureAnchor anchor,
                                       List<Cell> conflicts = null)
        {
            conflicts?.Clear();

            var d = Furniture.ById(id);
            if (d == null) return PlaceBlock.OffFloor;

            var me = new PlacedFurniture(id, gx, gy, flipped);
            var (w, h) = me.Size;
            if (!ShopRoom.Fits(gx, gy, w, h)) return PlaceBlock.OffFloor;

            var mine = new HashSet<string>();
            for (int c = 0; c < w; c++)
                for (int r = 0; r < h; r++) mine.Add($"{gx + c},{gy + r}");

            // ① 不能跟別件重疊
            bool hit = false;
            foreach (var p in Data.placed)
            {
                if (skip != null && ReferenceEquals(p, skip)) continue;
                foreach (var c in CellsOf(p))
                    if (mine.Contains(CellKey(c))) { hit = true; conflicts?.Add(c); }
            }
            if (hit) return PlaceBlock.Overlap;

            // ② 門口那幾格要留著（格線上畫紅色的那些）
            foreach (var c in ShopRoom.ReservedCells())
                if (mine.Contains(CellKey(c))) { hit = true; conflicts?.Add(c); }
            if (hit) return PlaceBlock.Door;

            // ③ 我不能壓在別的貨架前方的走道上
            foreach (var other in Data.placed)
            {
                if (skip != null && ReferenceEquals(other, skip)) continue;
                foreach (var c in FrontClearance(other))
                    if (mine.Contains(CellKey(c))) { hit = true; conflicts?.Add(c); }
            }
            if (hit) return PlaceBlock.Aisle;

            // ④ 我自己的走道：不能被別人佔著，而且要在地板上
            foreach (var c in FrontClearance(me))
            {
                if (!ShopRoom.InGrid(c.gx, c.gy)) { hit = true; continue; }   // 沒格子可標
                foreach (var other in Data.placed)
                {
                    if (skip != null && ReferenceEquals(other, skip)) continue;
                    var (ow, oh) = other.Size;
                    if (c.gx >= other.gx && c.gx < other.gx + ow
                        && c.gy >= other.gy && c.gy < other.gy + oh)
                    { hit = true; conflicts?.Add(c); break; }
                }
            }
            if (hit) return PlaceBlock.NoAisle;

            // ⑤ 格子都沒問題了，最後看圖會不會穿出牆外
            if (!ArtFits(id, AnchorPos(gx, gy, w, h, anchor), flipped)) return PlaceBlock.ThroughWall;

            return PlaceBlock.Ok;
        }

        /// <summary>
        /// 這件家具的圖擺在 anchor 會不會穿牆（沒有圖就不擋）。兩條規則：
        ///   ① **腳要踩在地板上** —— 圖的底緣兩端都要在地板菱形內
        ///   ② 整張可見範圍不能凸出房間輪廓 —— 往上長到牆上是可以的
        ///
        /// ⚠️ ① 才是擋掉「貨架埋進牆裡」的那條。基準點設成左上/右上會把圖搬到佔地的另一個角，
        ///    配錯翻面狀態時整個架子會平移到牆面上 —— 但它四個角都還在「地板＋牆」的輪廓內，
        ///    所以只驗 ② 是擋不掉的（玩家實際踩到的 bug：不翻面卻用右上基準點）。
        ///
        /// ⚠️ 用的是 <see cref="FurnitureBounds"/>（圖真正畫到東西的範圍），不是整張 PNG ——
        ///    家具圖有很大一塊透明邊而且**不置中**（shelf_box 圖寬 176，實際只畫在 62..172），
        ///    拿整張矩形去比會左邊誤擋、右邊漏擋。換美術要重跑 tools/gen_furniture_bounds.py。
        /// </summary>
        public static bool ArtFits(string id, Vector2 anchor, bool flipped)
        {
            var sp = GameArt.FurnitureArt(id);
            if (sp == null) return true;

            float w = sp.rect.width, h = sp.rect.height;
            float x0 = 0f, y0 = 0f, x1 = w, y1 = h;
            if (FurnitureBounds.TryGet(id, out var box) && Mathf.Approximately(box.ImgW, w))
            { x0 = box.X0; y0 = box.Y0; x1 = box.X1; y1 = box.Y1; }

            if (flipped) { float l = w - x1, r = w - x0; x0 = l; x1 = r; }   // 翻面＝左右鏡像

            float left = anchor.x - w / 2f + x0;
            float right = anchor.x - w / 2f + x1;
            float bottom = anchor.y + y0;
            float top = anchor.y + y1;

            return ShopRoom.RectOnFloor(left, right, bottom)
                && ShopRoom.RectInsideRoom(left, right, bottom, top);
        }

        /// <summary>放不下的原因，講成玩家看得懂的一句話。</summary>
        public static string BlockText(PlaceBlock b) => b switch
        {
            PlaceBlock.Overlap => "跟這裡的東西疊到了",
            PlaceBlock.Door => "這裡是門口，要留著讓人進出",
            PlaceBlock.Aisle => "這裡是貨架前的走道（藍色格），要留給客人走",
            PlaceBlock.NoAisle => "貨架前面要留一格走道，這個方向擠不下",
            PlaceBlock.ThroughWall => "這樣會卡進牆裡 —— 架子的腳要踩在地板上",
            PlaceBlock.OffFloor => "超出地板了",
            _ => "",
        };

        /// <summary>
        /// 把存檔裡「已經卡在牆裡」的家具挪回來，回傳挪了幾件。
        ///
        /// 為什麼需要：能不能放是**放的時候**檢查的，所以規則改嚴之前存下來的擺設不會自己變好——
        /// 玩家看到的還是那個埋在牆裡的貨架。進店時掃一次，能就地救的就地救：
        ///   ① 同一格換基準角（最常見的錯就是基準角配錯翻面狀態，換回前角就對了）
        ///   ② 同一格再試翻面
        ///   ③ 都不行才找離原位最近的合法格
        /// 三步都不行就原樣留著 —— 寧可醜，也不要把玩家買的東西弄不見。
        ///
        /// ⚠️ 要等美術載好才有意義（穿牆的判斷要量圖），所以由 ShopRoomView 在 GameArt 就緒後呼叫。
        /// </summary>
        public static int RepairPlacements()
        {
            int fixedCount = 0;

            foreach (var p in Data.placed)
            {
                if (Check(p.id, p.gx, p.gy, p, p.flip, p.Anchor) == PlaceBlock.Ok) continue;

                if (TryFixInPlace(p) || TryFixNearby(p)) fixedCount++;
            }

            if (fixedCount > 0) Save();
            return fixedCount;
        }

        /// <summary>同一格裡換基準角／翻面就能救回來嗎。</summary>
        static bool TryFixInPlace(PlacedFurniture p)
        {
            foreach (bool flip in new[] { p.flip, !p.flip })
                for (int a = 0; a < 3; a++)
                    if (Check(p.id, p.gx, p.gy, p, flip, (FurnitureAnchor)a) == PlaceBlock.Ok)
                    { p.flip = flip; p.anchor = a; return true; }
            return false;
        }

        /// <summary>找離原位最近的合法格（由近而遠，同距離時掃過所有翻面/基準角組合）。</summary>
        static bool TryFixNearby(PlacedFurniture p)
        {
            int ox = p.gx, oy = p.gy;
            for (int rad = 1; rad < Mathf.Max(ShopRoom.GridW, ShopRoom.GridH); rad++)
                for (int gx = ox - rad; gx <= ox + rad; gx++)
                    for (int gy = oy - rad; gy <= oy + rad; gy++)
                    {
                        // 只看這一圈新增的格子，內圈上一輪試過了
                        if (Mathf.Max(Mathf.Abs(gx - ox), Mathf.Abs(gy - oy)) != rad) continue;
                        if (!ShopRoom.InGrid(gx, gy)) continue;

                        foreach (bool flip in new[] { p.flip, !p.flip })
                            for (int a = 0; a < 3; a++)
                                if (Check(p.id, gx, gy, p, flip, (FurnitureAnchor)a) == PlaceBlock.Ok)
                                { p.gx = gx; p.gy = gy; p.flip = flip; p.anchor = a; return true; }
                    }
            return false;
        }

        /// <summary>整批覆寫（佈置模式按「完成」時用）。</summary>
        public static void SetPlaced(List<PlacedFurniture> list)
        {
            Data.placed = new List<PlacedFurniture>();
            foreach (var p in list) Data.placed.Add(new PlacedFurniture(p.id, p.gx, p.gy, p.flip, p.anchor));
            Save();
        }

        /// <summary>
        /// 一件擺出來的家具，圖該落在哪個世界座標 —— 依它的基準角決定。
        /// 渲染（ShopRoomView）與拖曳預覽（ShopRoomEditor）都走這支，兩邊才不會算不一樣。
        /// </summary>
        public static Vector2 AnchorPos(PlacedFurniture p)
        {
            var (w, h) = p.Size;
            if (w <= 0) return ShopRoom.TileFront(p.gx, p.gy);
            return AnchorPos(p.gx, p.gy, w, h, p.Anchor);
        }

        /// <summary>同上，但直接給格子與佔地（拖曳預覽時資料還沒寫回去）。</summary>
        public static Vector2 AnchorPos(int gx, int gy, int w, int h, FurnitureAnchor a) => a switch
        {
            // gx 往右下、gy 往左下 → 佔地的四個角分別是：
            //   前角 (gx+w-1, gy+h-1)  最靠畫面下方
            //   左角 (gx,     gy+h-1)  靠左後牆
            //   右角 (gx+w-1, gy)      靠右後牆
            FurnitureAnchor.Left => ShopRoom.TileFront(gx, gy + h - 1),
            FurnitureAnchor.Right => ShopRoom.TileFront(gx + w - 1, gy),
            _ => ShopRoom.TileFront(gx + w - 1, gy + h - 1),
        };

        /// <summary>目前的販售桌（沒有回 null）。</summary>
        public static PlacedFurniture SaleTable()
        {
            foreach (var p in Data.placed)
            {
                var d = Furniture.ById(p.id);
                if (d != null && d.Sale) return p;
            }
            return null;
        }

        /// <summary>販售桌檯面中心（商品陳列位置）；沒有販售桌回 null。</summary>
        public static Vector2? SaleTop()
        {
            var t = SaleTable();
            if (t == null) return null;
            var (w, h) = t.Size;
            var c = ShopRoom.FootprintCenter(t.gx, t.gy, w, h);
            return new Vector2(c.x, c.y + SaleTopH);
        }

        /// <summary>顧客站在販售桌前挑東西的位置；沒有販售桌回 null。</summary>
        public static Vector2? SaleFront()
        {
            var t = SaleTable();
            if (t == null) return null;
            var (w2, h2) = t.Size;
            var f = ShopRoom.FrontCorner(t.gx, t.gy, w2, h2);
            return new Vector2(f.x, f.y - SaleStandGap);
        }
    }
}
