using UnityEngine;

namespace WitchShop.Data
{
    /// <summary>一種可以種的花。</summary>
    public class FlowerDef
    {
        /// <summary>GameArt 的走圖名（Resources/garden/&lt;Art&gt;.png，6 階成長 ＋ 6 階枯萎）。</summary>
        public string Art;
        /// <summary>種子的道具名（背包裡拿的東西）。</summary>
        public string Seed;
        /// <summary>收成後拿到的花的道具名。</summary>
        public string Flower;
        /// <summary>收成幾朵。</summary>
        public int Yield;
        /// <summary>
        /// 花店賣這包種子的價錢。
        /// 抓法：一包種子要比「收成後拿去雜貨鋪賣」便宜一點（種了才划算），
        /// 但星鈴花刻意訂在雜貨鋪收購價上下 —— 稀有花要自己開店賣給顧客才有賺頭。
        /// </summary>
        public int SeedPrice;
        /// <summary>圖鑑說明。</summary>
        public string Desc;
    }

    /// <summary>
    /// 後花園「內容」資料：種哪些花、花圃擺在哪、長大與枯萎要多久。
    /// （狀態＝哪一格種了什麼、澆了沒，在 Garden.cs 的執行期元件，走 SaveManager 存檔。）
    ///
    /// ⚠️ 座標沿用 Cocos 的「像素」數值 —— Unity 這邊 Sprite 的 Pixels Per Unit 一律設 1，
    ///    所以 1 世界單位 ＝ 1 像素，原專案所有手調過的座標都能原封不動用。
    ///    （見 Assets/Scripts/Core/PortNotes.md）
    /// </summary>
    public static class GardenData
    {
        public static readonly FlowerDef[] Flowers =
        {
            new() { Art = "lavender", Seed = "薰衣草種子", Flower = "薰衣草", Yield = 2, SeedPrice = 25,
                    Desc = "一串串的紫色小花，香味安神，藥水鋪常來收。" },
            new() { Art = "foxglove", Seed = "毛地黃種子", Flower = "毛地黃", Yield = 2, SeedPrice = 35,
                    Desc = "粉紫色的鐘形花，開得又高又艷，但別亂入藥。" },
            new() { Art = "starbell", Seed = "星鈴花種子", Flower = "星鈴花", Yield = 1, SeedPrice = 60,
                    Desc = "夜裡會泛著微光的藍白鈴花，稀少而值錢。" },
        };

        public static FlowerDef FlowerBySeed(string seed)
        {
            foreach (var f in Flowers) if (f.Seed == seed) return f;
            return null;
        }

        // ── 成長與枯萎的時間，單位是「遊戲時間的分鐘」 ─────────────────────────
        //
        // ⚠️ 這裡的「分鐘」是**遊戲時鐘上的分鐘**，不是現實分鐘。換算：正常速度下
        // 10 遊戲分鐘 ≈ 7.3 現實秒 → 1 遊戲小時（60 分）≈ 44 現實秒，一個遊戲日
        // （06:00~26:00 ＝ 1200 分）≈ 14.6 現實分。
        //
        // 一株花的節奏是：
        //   種下（乾土，只有一個芽，**不澆水不會長**）
        //   → 澆水（土變深色，開始長）→ 澆下去算起 1 遊戲小時完全開花，按 E 就能摘
        //   → 一次澆的水撐 1.5 遊戲小時（夠長到開花）；水剩 1/4 時花圃冒「缺水」提醒
        //   → 沒補水就土乾＋開始枯萎，但枯得很慢（整整一個遊戲日才死透）**所以撐得過一夜**，
        //     睡醒再去補澆還來得及；拖過一整天才會枯死只能清掉。
        //
        // ⚠️ 一次澆的水（Dry）一定要**比長大所需（Grow）久**，不然種下澆一次水、乖乖等的
        //    玩家會在開花前先看到花枯掉 —— 等於永遠摘不到。
        //
        // ⚠️ 睡覺會一次跳過好幾個遊戲小時（最多從 06:00 跳到 20:00 ＝ 840 分），所以枯萎的
        //    總長度 WiltMinutes 設成**一整個遊戲日（1200）**，花才撐得過一夜 —— 睡醒時大約枯到
        //    第 3 階，還在「澆水救得回來」的範圍內，已經開花的也還摘得到。

        /// <summary>第一次澆水 → 完全開花（1 遊戲小時 ≈ 44 現實秒）。</summary>
        public const int GrowMinutes = 60;
        /// <summary>澆水 → 水乾了開始枯萎（1.5 遊戲小時，比長大久一點）。</summary>
        public const int DryMinutes = 90;
        /// <summary>土看起來濕的時間＝水還在的時間（兩者一致才好懂）。</summary>
        public const int WetMinutes = 90;
        /// <summary>開始枯萎 → 完全枯死（一整個遊戲日，撐得過一夜）。</summary>
        public const int WiltMinutes = 1200;

        /// <summary>
        /// 成長／枯萎各有幾階。
        ///
        /// ⚠️ 走圖是 6 欄，但**成長只用到前 5 欄**：第 4 欄（index 4）才是完全開花，
        ///    第 5 欄（index 5）畫的是「開完乾掉的褐色枯穗」（毛地黃與星鈴花特別明顯）。
        ///    早期把 6 欄全當成長階段 → 花開好時還不算成熟、要等它變成乾穗才收得到（等於收不到）。
        ///    背包圖示本來就是取 index 4，這裡跟它對齊。枯萎那一列則是完整用滿 6 欄。
        /// </summary>
        public const int GrowStages = 5;
        public const int WiltStages = 6;
        /// <summary>枯萎超過這一階就救不回來了。</summary>
        public const int WiltRescuable = 3;

        /// <summary>土壤磚原圖 153x100 → 約 84x55。</summary>
        public const float PlotScale = 0.55f;
        /// <summary>花畫在磚上的縮放（原圖一株盛開約 68px，跟主角一樣高，縮一點才像庭園花草）。</summary>
        public const float FlowerScale = 0.78f;

        // 花圃的位置（garden 場景的世界座標，錨點在磚的中心）。
        // 底圖的草地是等距菱形，所以花圃也照等距排：往右下一格 (+HalfW, -HalfH)、
        // 往左下一格 (-HalfW, -HalfH)。
        private const float HalfW = 43f, HalfH = 27f;
        private const float OriginX = 0f, OriginY = 50f;

        public const int PlotCols = 4;
        public const int PlotRows = 3;
        public const int PlotCount = PlotCols * PlotRows;

        /// <summary>第 i 格花圃的位置（i ＝ row * PlotCols + col）。</summary>
        public static Vector2 PlotPos(int i)
        {
            int col = i % PlotCols, row = i / PlotCols;
            return new Vector2(OriginX + (col - row) * HalfW,
                               OriginY - (col + row) * HalfH);
        }

        /// <summary>
        /// 花圃的開墾順序（在店裡升級「花圃」會一次多開幾塊）。
        /// 刻意不是 0,1,2,3… —— 那樣會先開滿第一排，剩下的變成缺一角的形狀。
        /// 照這個順序開出來的是完整的小菱形：6 塊＝3×2、9 塊＝3×3、12 塊＝整片 4×3。
        /// </summary>
        public static readonly int[] PlotOrder = { 0, 1, 2, 4, 5, 6, 8, 9, 10, 3, 7, 11 };

        /// <summary>
        /// 柵欄「外面」那條石板路上的路點 —— 村民沿著這條路經過花園，不會走進來。
        /// 座標從底圖（rooms/garden.png，1376×768、中心在原點）量出來的：左上角那條斜斜的石板大道，
        /// 上緣是樹籬、下緣是柵欄，這幾點落在路面中線上。
        ///
        /// ⚠️ 這是一條**有順序的折線**（由左下往右上）：TownFolk 以 polyline 模式只沿相鄰兩點走。
        ///    舊版是五個散點、村民在任兩點之間直線走 —— (-680,60) 那點就壓在左邊柵欄的轉角上，
        ///    (-660,250)、(-520,300) 落在樹籬上，連線會斜穿柵欄。改點之後要照順序排，不能打亂。
        /// </summary>
        public static readonly Vector2[] FenceWalk =
        {
            new(-676f, 144f), new(-538f, 203f), new(-388f, 266f),
            new(-238f, 309f), new(-128f, 334f),
        };

        /// <summary>從店裡進花園的門（裝在 shop 場景）。</summary>
        public static readonly Vector2 ShopToGarden = new(600f, -150f);
        /// <summary>從花園回店裡的門（裝在 garden 場景）。</summary>
        public static readonly Vector2 GardenToShop = new(250f, 130f);
    }
}
