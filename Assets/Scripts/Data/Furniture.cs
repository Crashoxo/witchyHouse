using System.Collections.Generic;
using System.Linq;
using UnityEngine;

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
        /// <summary>種類（販售桌／貨架／陳列桌／家具／燈）。</summary>
        public FurnKind Kind = FurnKind.Furniture;
        /// <summary>靠牆的東西（書櫃、老爺鐘）：拖到牆邊會自動吸上去（貨架本來就會）。</summary>
        public bool Wall;
        /// <summary>燈的光暈（null＝不發光）。位置在 FurnitureArt8（跟著圖量的）。</summary>
        public LightSpec? Light;

        /// <summary>會陳列商品（販售桌、貨架、陳列桌）—— 這些只能擺在店裡。</summary>
        public bool Displays => Sale || Shelf || Kind == FurnKind.Table;
        /// <summary>拖到牆邊會吸上去。</summary>
        public bool WallSnap => Shelf || Wall;
        public PlaceRoom Where => Displays ? PlaceRoom.ShopOnly : PlaceRoom.ShopOrHome;
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

        /// <summary>
        /// 陳列桌（2026-11-28）：桌面上擺商品，不用靠牆、前面不留走道，顧客站到桌邊任一個空格看。
        /// 最後兩欄是佔地 W×H（沒翻面時：W 沿 gx、H 沿 gy）。位子數在 FurnitureArt8（跟著圖量的）。
        /// ⚠️ tools/gen_furniture8.py 與 tools/check_shop_walk.py 用正規式讀這張表，格式別改。
        /// </summary>
        static readonly (string id, string name, int price, string desc, int w, int h)[] TableStyles =
        {
            ("table_barrel",   "木桶小桌", 130, "舊酒桶改的小桌，鐵箍擦得亮亮的。", 1, 1),
            ("table_round",    "蕾絲圓桌", 150, "鋪著蕾絲桌巾的小圓桌，擺兩樣剛好。", 1, 1),
            ("table_pedestal", "絲絨展台", 180, "紅絲絨墊在石柱上，只放一樣、放得特別大。", 1, 1),
            ("table_crate",    "木箱堆",   170, "三個木箱疊成高低台，市集攤位的味道。", 2, 1),
            ("table_long",     "格紋長桌", 200, "藍白格紋桌巾的長桌，一排擺三樣。", 2, 1),
            ("table_tier",     "階梯展台", 300, "前低後高的兩層木台，擺六樣也不互相擋。", 2, 1),
            ("table_cart",     "條紋攤車", 360, "粉白條紋遮陽棚的小推車，像在趕集。", 2, 1),
        };

        /// <summary>
        /// 不陳列商品的家具與燈（2026-11-28）：店裡、家裡都能擺。kind：Lamp／Furniture；wall＝靠牆吸附。
        /// ⚠️ tools/gen_furniture8.py 與 tools/check_shop_walk.py 用正規式讀這張表，格式別改。
        /// </summary>
        static readonly (string id, string name, int price, string desc, int w, int h, FurnKind kind, bool wall)[] PieceStyles =
        {
            ("lamp_pumpkin",    "南瓜燈",   120, "刻了笑臉的南瓜，頭上疊一顆小的。", 1, 1, FurnKind.Lamp, false),
            ("lamp_mushroom",   "蘑菇燈",   180, "紅點點的大蘑菇，傘底下會發光。", 1, 1, FurnKind.Lamp, false),
            ("lamp_candelabra", "三叉燭台", 200, "三根蠟燭的鐵燭台，燭火輕輕晃。", 1, 1, FurnKind.Lamp, false),
            ("lamp_lantern",    "提燈立燈", 220, "鐵柱吊著一盞玻璃提燈，晚上暖暖的。", 1, 1, FurnKind.Lamp, false),
            ("lamp_crystal",    "水晶燈",   240, "一叢紫水晶，自己會微微發亮。", 1, 1, FurnKind.Lamp, false),
            ("lamp_moon",       "星月燈",   260, "睡著的彎月掛在黃銅臂上，垂著小星星。", 1, 1, FurnKind.Lamp, false),
            ("side_table",      "圓邊几",    90, "小圓桌上一組藍邊茶壺茶杯。", 1, 1, FurnKind.Furniture, false),
            ("plant_monstera",  "龜背芋",   160, "大片裂葉的龜背芋，種在白陶盆裡。", 1, 1, FurnKind.Furniture, false),
            ("armchair",        "絨布椅",   200, "青綠絨布圓背椅，掛著一條針織毯。", 1, 1, FurnKind.Furniture, false),
            ("cat_tree",        "貓跳台",   240, "麻繩柱加兩層軟墊，貓咪最愛。", 1, 1, FurnKind.Furniture, false),
            ("bookshelf",       "小書櫃",   260, "塞滿書和小罐子的書櫃，靠牆擺。", 1, 2, FurnKind.Furniture, true),
            ("sofa_small",      "雙人沙發", 320, "薰衣草紫的絨布小沙發，兩顆抱枕。", 2, 1, FurnKind.Furniture, false),
            ("clock_tall",      "老爺鐘",   340, "高高的落地鐘，頂上一彎小月亮。", 1, 1, FurnKind.Furniture, true),
        };

        /// <summary>燈的光暈（半徑、顏色、最亮 alpha、閃爍幅度）。位置由產生器量在 FurnitureArt8。</summary>
        static readonly Dictionary<string, LightSpec> Lights = new()
        {
            ["lamp_pumpkin"] = new LightSpec(34f, new Color32(255, 170, 80, 255), 0.55f, 0.18f),
            ["lamp_mushroom"] = new LightSpec(40f, new Color32(255, 214, 140, 255), 0.5f, 0.05f),
            ["lamp_candelabra"] = new LightSpec(46f, new Color32(255, 196, 120, 255), 0.6f, 0.2f),
            ["lamp_lantern"] = new LightSpec(46f, new Color32(255, 200, 120, 255), 0.6f, 0.14f),
            ["lamp_crystal"] = new LightSpec(40f, new Color32(206, 170, 255, 255), 0.5f, 0.04f),
            ["lamp_moon"] = new LightSpec(44f, new Color32(255, 232, 150, 255), 0.55f, 0.03f),
        };

        public static readonly FurnitureDef[] All =
            new[]
            {
                new FurnitureDef { Id = "sale_table", Name = "販售桌", W = 2, H = 1, Price = 0, Sale = true, Kind = FurnKind.Sale,
                                   Desc = "上架的商品會擺在這張桌上，顧客走到桌前挑東西。" },
            }
            .Concat(ShelfStyles.Select(s => new FurnitureDef
            {
                Id = s.id, Name = s.name, Price = s.price, Desc = s.desc,
                W = 1, H = s.depth, Shelf = true, Kind = FurnKind.Shelf,
            }))
            .Concat(TableStyles.Select(t => new FurnitureDef
            {
                Id = t.id, Name = t.name, Price = t.price, Desc = t.desc, W = t.w, H = t.h, Kind = FurnKind.Table,
            }))
            .Concat(PieceStyles.Select(t => new FurnitureDef
            {
                Id = t.id, Name = t.name, Price = t.price, Desc = t.desc, W = t.w, H = t.h, Kind = t.kind, Wall = t.wall,
                Light = Lights.TryGetValue(t.id, out var l) ? l : (LightSpec?)null,
            }))
            .ToArray();

        public static FurnitureDef ById(string id)
        {
            foreach (var f in All) if (f.Id == id) return f;
            return null;
        }
    }
}
