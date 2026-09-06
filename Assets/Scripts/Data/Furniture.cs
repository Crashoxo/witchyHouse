using System.Collections.Generic;
using System.Linq;

namespace WitchShop.Data
{
    /// <summary>店內一件家具。等距格佔 W×H 格。</summary>
    public class FurnitureDef
    {
        public string Id;
        public string Name;
        public int Price;
        public string Desc;
        public int W = 1;
        public int H = 1;
        /// <summary>是不是「販售桌」（上架的商品擺在上面，顧客走到桌前挑東西）。</summary>
        public bool Sale;
        /// <summary>是不是貨架。</summary>
        public bool Shelf;
    }

    /// <summary>
    /// 店內家具「內容」資料。
    ///
    /// 貨架只列每款不一樣的欄位，W/H/Shelf 由 <see cref="Shelves"/> 統一補上 ——
    /// 沿用原專案 shopRoom.ts 的做法（16 款貨架的差別只有名字/價錢/說明）。
    ///
    /// 等距格盤的數學（格子↔世界座標、ReservedCells()、Door* / PlayerSpawn）
    /// 在 Data/ShopRoom.cs。
    /// </summary>
    public static class Furniture
    {
        /// <summary>
        /// 貨架款式。最後一欄是**佔地深度**（格）。
        ///
        /// ⚠️ 除了「四層高架」是 2 格，其餘十五款都是 3 格 —— 它們的圖寬都在 164px 以上，
        ///    而一格的等距菱形只有約 96px 寬，擺 2 格會凸出去跟隔壁的架子疊在一起。
        ///    只有四層高架窄（124px），2 格剛好。換美術的話記得跟著調。
        /// </summary>
        static readonly (string id, string name, int price, string desc, int depth)[] ShelfStyles =
        {
            ("shelf_narrow",  "三層細架",   200, "細長的三層開放架，牆邊塞哪裡都不佔位。", 3),
            ("shelf_tall",    "四層高架",   240, "瘦高的四層架，往上長比較省地。", 2),
            ("shelf_cross",   "交叉撐架",   260, "背後打了交叉木撐，粗獷耐看。", 3),
            ("shelf_plank",   "厚板木架",   280, "厚實的原木層板，帶點灰調的舊木色。", 3),
            ("shelf_box",     "素面方架",   300, "方方正正的木箱式貨架，什麼都好搭。", 3),
            ("shelf_slat",    "木條背板架", 320, "背板是一根根木條，透光又通風。", 3),
            ("shelf_back",    "封背貨架",   320, "整面實心背板，擺小東西不會掉到牆縫裡。", 3),
            ("shelf_round",   "圓角貨架",   340, "四角磨圓的箱型架，線條柔和。", 3),
            ("shelf_deep",    "深底貨架",   340, "最下層特別深，重的東西往下擺。", 3),
            ("shelf_curve",   "曲線頂長架", 360, "頂板做成波浪曲線，像老家具行的樣品架。", 3),
            ("shelf_two",     "雙層抽屜架", 380, "兩層層板加一個下抽屜，收納最實用。", 3),
            ("shelf_scallop", "波浪簷貨架", 400, "頂上一排扇貝花邊，很有店面的味道。", 3),
            ("shelf_peak",    "尖頂小屋架", 420, "尖屋頂造型，擺在角落像一間小房子。", 3),
            ("shelf_arch",    "拱頂貨架",   440, "半圓拱頂，最像藥草鋪會有的那種櫃子。", 3),
            ("shelf_cabinet", "附櫃貨架",   460, "下方多一個對開小櫃，藏東西剛好。", 3),
            ("shelf_drawer",  "抽屜貨架",   500, "底下六個小抽屜，最貴也最有份量。", 3),
        };

        public static readonly FurnitureDef[] All =
            new[]
            {
                new FurnitureDef { Id = "sale_table", Name = "販售桌", W = 2, H = 1, Price = 0, Sale = true,
                                   Desc = "上架的商品會擺在這張桌上，顧客走到桌前挑東西。" },
            }
            .Concat(ShelfStyles.Select(s => new FurnitureDef
            {
                Id = s.id, Name = s.name, Price = s.price, Desc = s.desc,
                W = 1, H = s.depth, Shelf = true,
            }))
            .ToArray();

        public static FurnitureDef ById(string id)
        {
            foreach (var f in All) if (f.Id == id) return f;
            return null;
        }
    }
}
