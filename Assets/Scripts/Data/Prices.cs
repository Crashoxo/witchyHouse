using System.Collections.Generic;

namespace WitchShop.Data
{
    /// <summary>商店收購一項材料的定義：名稱 + 單價。</summary>
    public readonly struct BuyEntry
    {
        public readonly string Name;
        public readonly int Price;
        public BuyEntry(string name, int price) { Name = name; Price = price; }
    }

    /// <summary>
    /// 價格「內容」資料：
    ///   - DefaultBuy：雜貨鋪「收購」玩家材料的預設單價（換金幣）。
    ///   - BasePrice：在「自己的店」賣給顧客的建議售價（比收購價高）。藥水價＝配方 SellPrice。
    /// </summary>
    public static class Prices
    {
        /// <summary>沒在 Inspector 指定時，雜貨鋪預設收購的材料與單價。</summary>
        public static readonly BuyEntry[] DefaultBuy =
        {
            new("木材", 5), new("樹枝", 3), new("漿果", 8), new("落葉", 2),
            new("藥草", 12), new("黑莓", 10), new("金蘋果", 50),
            new("薰衣草", 22), new("毛地黃", 26), new("星鈴花", 60),
            // 糖果鎮的商品（雜貨鋪也收，但收得比你自己賣給顧客低）
            new("焦糖蘋果棒", 28), new("鱷魚軟糖袋", 40), new("永恆彩球糖", 60),
            new("糖李礦坑地圖", 95), new("妖精粉小袋", 130), new("時晶法杖", 260),
        };

        /// <summary>各材料/藥水的建議售價（賣給顧客，比雜貨鋪收購價高一些）。藥水價＝配方 SellPrice。</summary>
        public static readonly Dictionary<string, int> BasePrice = new()
        {
            ["木材"] = 8, ["樹枝"] = 5, ["漿果"] = 12, ["落葉"] = 3,
            ["藥草"] = 18, ["黑莓"] = 15, ["金蘋果"] = 80, ["藍莓"] = 14,
            // 後花園種出來的花
            ["薰衣草"] = 34, ["毛地黃"] = 40, ["星鈴花"] = 95,
            // 藥水成品（＝ Recipes 的 SellPrice）
            ["清涼藥水"] = 35, ["戀愛藥水"] = 40, ["暗影藥水"] = 42, ["烈焰藥水"] = 45,
            ["溫暖熱可可"] = 30, ["蜂蜜藥劑"] = 55, ["黃金藥劑"] = 70,
            ["夜影掃帚"] = 120, ["星光掃帚"] = 140, ["羽翼掃帚"] = 160,
            // 花做的藥水（後花園）
            ["安眠藥水"] = 110, ["花香水"] = 125, ["星光藥劑"] = 175,
            // 糖果鎮進的貨：買進價 45/60/90/150/200/400，賣給自己的顧客有價差可賺
            ["焦糖蘋果棒"] = 70, ["鱷魚軟糖袋"] = 95, ["永恆彩球糖"] = 140,
            ["糖李礦坑地圖"] = 230, ["妖精粉小袋"] = 300, ["時晶法杖"] = 600,
        };
    }
}
