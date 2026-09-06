using System.Collections.Generic;

namespace WitchShop.Data
{
    /// <summary>一張藥水配方。</summary>
    public class Recipe
    {
        /// <summary>成品中文名。</summary>
        public string Name;
        /// <summary>材料名 → 需要數量。</summary>
        public Dictionary<string, int> Inputs;
        /// <summary>賣給顧客的建議售價（也塞進 Prices.BasePrice）。</summary>
        public int SellPrice;
        /// <summary>熬煮動畫長度（秒）。</summary>
        public float BrewSeconds;
    }

    /// <summary>
    /// 藥水配方「內容」資料。成品名同時是背包/貨架用的物品名，圖示由 GameArt.Item() 提供
    /// （藥水圖已用中文名載進 items map）。材料都是採集得到的（見 Items.Materials）。
    /// 製作邏輯（扣料/產出）在 PotionRecipes.cs。
    /// </summary>
    public static class Recipes
    {
        public static readonly Recipe[] All =
        {
            new() { Name = "清涼藥水",   SellPrice = 35,  BrewSeconds = 2.2f, Inputs = new() { ["藍莓"] = 2, ["藥草"] = 1 } },
            new() { Name = "戀愛藥水",   SellPrice = 40,  BrewSeconds = 2.2f, Inputs = new() { ["漿果"] = 2, ["黑莓"] = 1 } },
            new() { Name = "暗影藥水",   SellPrice = 42,  BrewSeconds = 2.4f, Inputs = new() { ["落葉"] = 3, ["黑莓"] = 1 } },
            new() { Name = "烈焰藥水",   SellPrice = 45,  BrewSeconds = 2.4f, Inputs = new() { ["藥草"] = 2, ["樹枝"] = 2 } },
            new() { Name = "溫暖熱可可", SellPrice = 30,  BrewSeconds = 2.0f, Inputs = new() { ["金蘋果"] = 1, ["漿果"] = 2 } },
            new() { Name = "蜂蜜藥劑",   SellPrice = 55,  BrewSeconds = 2.6f, Inputs = new() { ["金蘋果"] = 2, ["藥草"] = 1 } },
            new() { Name = "黃金藥劑",   SellPrice = 70,  BrewSeconds = 2.8f, Inputs = new() { ["金蘋果"] = 2, ["藍莓"] = 2 } },
            new() { Name = "夜影掃帚",   SellPrice = 120, BrewSeconds = 3.0f, Inputs = new() { ["木材"] = 3, ["樹枝"] = 2, ["黑莓"] = 1 } },
            new() { Name = "星光掃帚",   SellPrice = 140, BrewSeconds = 3.0f, Inputs = new() { ["木材"] = 3, ["樹枝"] = 2, ["藍莓"] = 2 } },
            new() { Name = "羽翼掃帚",   SellPrice = 160, BrewSeconds = 3.2f, Inputs = new() { ["木材"] = 3, ["樹枝"] = 3, ["金蘋果"] = 1 } },
            // 後花園的花做的三支 —— 花本身就值錢，所以成品價訂得比「材料直接賣」再高一截
            new() { Name = "安眠藥水",   SellPrice = 110, BrewSeconds = 2.6f, Inputs = new() { ["薰衣草"] = 2, ["藥草"] = 1 } },
            new() { Name = "花香水",     SellPrice = 125, BrewSeconds = 2.6f, Inputs = new() { ["毛地黃"] = 2, ["漿果"] = 1 } },
            new() { Name = "星光藥劑",   SellPrice = 175, BrewSeconds = 3.0f, Inputs = new() { ["星鈴花"] = 1, ["藍莓"] = 2 } },
        };

        public static Recipe ByName(string name)
        {
            foreach (var r in All) if (r.Name == name) return r;
            return null;
        }
    }
}
