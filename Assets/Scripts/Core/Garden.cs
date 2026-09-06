using System;
using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>一格花圃的存檔狀態。</summary>
    [Serializable]
    public class Plot
    {
        public string seed = "";   // 種下的種子名（""＝空地）
        public float planted;      // 種下時的遊戲總分鐘
        public float watered;      // 最後一次澆水的遊戲總分鐘（0＝種下後還沒澆過）
    }

    /// <summary>一格花圃現在的樣子（給畫面用）。</summary>
    public struct PlotView
    {
        public bool Empty;
        public string Art;      // 花的走圖名
        public int Stage;       // 第幾格圖
        public bool Wilting;    // true＝畫枯萎那一列
        public bool Dead;       // 枯死了，只能清掉
        public bool Ripe;       // 完全開花，可以收成
        public bool Wet;        // 土是濕的（畫深色土）
    }

    /// <summary>
    /// 後花園的種植狀態（純資料）。
    ///
    /// 每一格花圃記三件事：種了什麼、什麼時候種的、最後一次澆水是什麼時候。
    /// 時間全部用 **TimeSystem 的總分鐘數**（遊戲時間），所以：
    ///   - 睡一覺跳過的時間也算進成長，醒來花就長大了；
    ///   - 關掉遊戲再回來不會平白長大（現實時間不計）。
    /// 成長是純看時間；**澆水管的是不枯萎**（太久沒澆 → 開始枯 → 再拖下去就死了）。
    /// </summary>
    public static class Garden
    {
        const string Key = "witch.garden";

        const float MinutesPerDay = 1200f;
        const float DayStart = 6 * 60f;

        [Serializable] class Shape { public List<Plot> plots = new(); }

        static List<Plot> plots;

        /// <summary>
        /// 目前的遊戲總分鐘（跨日累加）。
        /// ⚠️ 不能用 Hour：它把 25:00 顯示成 1:00，深夜會倒退。一天是 06:00 醒到 26:00 昏倒
        ///    ＝ 1200 分鐘，所以直接拿 TodHours 換算，這樣才是單調遞增的。
        /// </summary>
        static float Now() =>
            (TimeSystem.TotalDay - 1) * MinutesPerDay + (TimeSystem.TodHours * 60f - DayStart);

        static List<Plot> Plots
        {
            get
            {
                if (plots != null) return plots;
                plots = new List<Plot>();
                for (int i = 0; i < GardenData.PlotCount; i++) plots.Add(new Plot());
                try
                {
                    var o = JsonUtility.FromJson<Shape>(SaveManager.GetString(Key));
                    if (o?.plots != null)
                        for (int i = 0; i < GardenData.PlotCount && i < o.plots.Count; i++)
                        {
                            var p = o.plots[i];
                            if (p == null) continue;
                            // 防壞檔：認不得的種子當空地
                            string seed = p.seed ?? "";
                            if (seed != "" && GardenData.FlowerBySeed(seed) == null) continue;
                            plots[i] = new Plot { seed = seed, planted = p.planted, watered = p.watered };
                        }
                }
                catch { /* 壞檔就用空的 */ }
                return plots;
            }
        }

        static void Save() => SaveManager.SetString(Key, JsonUtility.ToJson(new Shape { plots = Plots }));

        /// <summary>
        /// 這格「上一次有水」是什麼時候 —— 沒澆過就算種下的那一刻。
        /// ⚠️ 這跟「土看起來濕不濕」是兩回事：種下去土是**乾的**（要自己澆才會變深色），
        ///    但枯萎的倒數還是從種下開始算，不然沒澆過的 watered=0 會被當成幾百天沒澆、種下就枯。
        /// </summary>
        static float LastWet(Plot p) => Mathf.Max(p.watered, p.planted);

        /// <summary>這格的狀態（給畫面用）。</summary>
        public static PlotView View(int i)
        {
            var p = i >= 0 && i < Plots.Count ? Plots[i] : null;
            var blank = new PlotView { Empty = true, Art = "" };
            if (p == null || string.IsNullOrEmpty(p.seed))
            {
                // 空地澆了水也會是深色的（先澆再種也行）
                blank.Wet = p != null && p.watered > 0f && Now() - p.watered < GardenData.WetMinutes;
                return blank;
            }
            var f = GardenData.FlowerBySeed(p.seed);
            if (f == null) return blank;

            bool wet = p.watered > 0f && Now() - p.watered < GardenData.WetMinutes;
            float dry = Now() - LastWet(p);

            // ⚠️ 還沒澆過水就不會長 —— 乾土裡的種子不發芽（澆下去那一刻才開始計時，見 Water()）
            float grown = p.watered == 0f ? 0f
                : Mathf.Min(1f, (Now() - p.planted) / GardenData.GrowMinutes);

            if (dry >= GardenData.DryMinutes)
            {
                float t = (dry - GardenData.DryMinutes) / GardenData.WiltMinutes;
                int stage = Mathf.Min(GardenData.WiltStages - 1, Mathf.FloorToInt(t * GardenData.WiltStages));
                // 水乾的那一刻長到哪就凍在哪。**已經開花的還是摘得到**（只要還沒枯過頭）——
                // 花開了卻晚幾分鐘回來就整株報銷，太苛了。
                float frozen = p.watered == 0f ? 0f
                    : Mathf.Min(1f, (LastWet(p) + GardenData.DryMinutes - p.planted) / GardenData.GrowMinutes);
                return new PlotView
                {
                    Empty = false, Art = f.Art, Stage = stage, Wilting = true,
                    Dead = stage >= GardenData.WiltStages - 1,
                    Ripe = frozen >= 1f && stage <= GardenData.WiltRescuable,
                    Wet = wet,
                };
            }

            // 前面幾階平均分配在成長時間裡，**最後一階（完全開花）剛好落在時間到的那一刻** ——
            // 這樣「種下一小時後開花可以摘」才是字面上的一小時，而不是 80% 就先開了。
            int s = grown >= 1f ? GardenData.GrowStages - 1
                                : Mathf.FloorToInt(grown * (GardenData.GrowStages - 1));
            return new PlotView
            {
                Empty = false, Art = f.Art, Stage = s, Wilting = false, Dead = false,
                Ripe = s >= GardenData.GrowStages - 1, Wet = wet,
            };
        }

        /// <summary>
        /// 種下一顆種子；回傳是否成功（格子要是空的、種子要認得）。
        /// **不會順手澆水** —— 剛種下的土是乾的，玩家自己澆過才變成濕土。
        /// </summary>
        public static bool Plant(int i, string seed)
        {
            if (i < 0 || i >= Plots.Count) return false;
            var p = Plots[i];
            if (!string.IsNullOrEmpty(p.seed) || GardenData.FlowerBySeed(seed) == null) return false;
            p.seed = seed;
            p.planted = Now();
            p.watered = 0f;
            Save();
            return true;
        }

        /// <summary>澆水。枯萎還沒太嚴重的話會救回來（枯萎進度歸零、成長從現在續算）。</summary>
        public static bool Water(int i)
        {
            if (i < 0 || i >= Plots.Count) return false;
            var p = Plots[i];
            var v = View(i);
            if (v.Dead) return false;

            if (!string.IsNullOrEmpty(p.seed) && p.watered == 0f)
            {
                // 第一次澆水＝成長開始計時（種下到現在乾等的那段不算）
                p.planted = Now();
            }
            else if (v.Wilting)
            {
                if (v.Stage > GardenData.WiltRescuable) return false;   // 枯太久了，救不回來
                // 救回來：把「已經長到哪」保留下來，重新開始算成長時間
                float grown = Mathf.Min(1f,
                    (LastWet(p) + GardenData.DryMinutes - p.planted) / GardenData.GrowMinutes);
                p.planted = Now() - grown * GardenData.GrowMinutes;
            }
            p.watered = Now();
            Save();
            return true;
        }

        /// <summary>收成：完全開花才收得到，回傳花名與數量；收不到回 null。</summary>
        public static (string Name, int Count)? Harvest(int i)
        {
            if (i < 0 || i >= Plots.Count) return null;
            var p = Plots[i];
            if (string.IsNullOrEmpty(p.seed)) return null;
            if (!View(i).Ripe) return null;
            var f = GardenData.FlowerBySeed(p.seed);
            p.seed = "";
            Save();
            return f == null ? null : (f.Flower, f.Yield);
        }

        /// <summary>清掉枯死的花，讓格子可以重種。</summary>
        public static bool Clear(int i)
        {
            if (i < 0 || i >= Plots.Count) return false;
            var p = Plots[i];
            if (string.IsNullOrEmpty(p.seed) || !View(i).Dead) return false;
            p.seed = "";
            Save();
            return true;
        }

        /// <summary>花圃快沒水了（花圃上會冒「缺水」提醒）。</summary>
        public static bool NeedsWater(int i)
        {
            if (i < 0 || i >= Plots.Count) return false;
            var p = Plots[i];
            return !string.IsNullOrEmpty(p.seed)
                   && Now() - LastWet(p) >= GardenData.DryMinutes * 0.75f;
        }

        /// <summary>
        /// 現在開墾了幾塊花圃（其餘的還是荒地，要在店裡升級「花圃」才開得出來）。
        /// </summary>
        public static int UnlockedCount() => Mathf.Min(GardenData.PlotCount, Upgrades.GardenPlots());

        /// <summary>已開墾的花圃 index（照 PlotOrder 的開墾順序）。</summary>
        public static List<int> UnlockedPlots()
        {
            var outList = new List<int>();
            int n = UnlockedCount();
            for (int k = 0; k < n && k < GardenData.PlotOrder.Length; k++) outList.Add(GardenData.PlotOrder[k]);
            return outList;
        }

        /// <summary>
        /// 澆一塊花圃時，跟著一起澆到的格子（澆水壺升級後一次澆得更多）。
        /// 0＝只有自己；1＝十字相鄰；2＝整片花園。回傳的 index 都是已開墾的。
        /// </summary>
        public static List<int> WaterTargets(int i)
        {
            var open = UnlockedPlots();
            int spread = Upgrades.WaterSpread();
            if (spread >= 2) return open;
            var outList = new List<int> { i };
            if (spread <= 0) return outList;

            int col = i % GardenData.PlotCols, row = i / GardenData.PlotCols;
            void Push(int c, int r)
            {
                if (c < 0 || c >= GardenData.PlotCols || r < 0 || r >= GardenData.PlotRows) return;
                int k = r * GardenData.PlotCols + c;
                if (open.Contains(k)) outList.Add(k);       // 還沒開墾的鄰居不算
            }
            Push(col - 1, row); Push(col + 1, row); Push(col, row - 1); Push(col, row + 1);
            return outList;
        }

        /// <summary>在花店買一包種子：扣金幣、進背包。金幣不夠或認不得的種子回 false。</summary>
        public static bool BuySeed(string seed)
        {
            var f = GardenData.FlowerBySeed(seed);
            if (f == null || Wallet.Gold < f.SeedPrice) return false;
            if (!Inventory.Add(seed, 1)) return false;      // 背包滿了就不扣錢
            Wallet.Add(-f.SeedPrice);
            DailyLog.RecordSpend(f.SeedPrice);
            return true;
        }
    }
}
