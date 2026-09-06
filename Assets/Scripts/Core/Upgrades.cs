using System;
using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>可升級的軌道。</summary>
    public enum Track { Signboard, Bag, Shelf, Plot, Can }

    /// <summary>每項升級的定義：名稱、各級費用（長度＝最高等級）、每級效果文字。</summary>
    public class UpgradeDef
    {
        public string Name;
        public string Desc;
        public int[] Costs;
        public Func<int, string> Effect;
    }

    /// <summary>
    /// 店鋪升級：花金幣升級各項軌道，等級存檔（key witch.upgrades）。
    /// 各系統從這裡「讀值」—— 升級就自動生效：
    ///   Inventory 的種類上限 ← BagSlots()
    ///   CustomerManager 生成 ← CustomerInterval() / CustomerMax()
    ///   ShopStock 展示上限   ← ShelfCap()
    /// </summary>
    public static class Upgrades
    {
        // ── 各級數值（index = 等級，0 = 未升級）──────────────────────
        static float IntervalAt(int lv) => new[] { 6f, 5f, 4f, 3f, 2.5f }[Mathf.Min(lv, 4)];
        static int MaxAt(int lv) => new[] { 2, 3, 3, 4, 5 }[Mathf.Min(lv, 4)];

        // 12,15,18,21 —— 上限算的是「能放幾**種**東西」，而遊戲裡的道具有二十幾種，
        // 所以起手就給 12 種；真的帶不完的東西丟店裡的倉庫（Storage）。
        static int BagAt(int lv) => 12 + lv * 3;
        static int ShelfAt(int lv) => 3 + lv * 2;                 // 3,5,7
        // 6,9,12 —— 一次開三塊，剛好每一級都是完整的菱形區塊（見 GardenData.PlotOrder）
        static int PlotAt(int lv) => 6 + lv * 3;
        static readonly string[] CanText = { "一次一塊", "十字四周", "整片花園" };
        static string CanAt(int lv) => CanText[Mathf.Min(lv, 2)];

        static readonly Dictionary<Track, UpgradeDef> Defs = new()
        {
            [Track.Signboard] = new UpgradeDef
            {
                Name = "招牌", Desc = "顧客來得更快、同時更多人",
                Costs = new[] { 100, 250, 500, 1000 },
                Effect = lv => $"每 {IntervalAt(lv)} 秒 · 同時 {MaxAt(lv)} 人",
            },
            [Track.Bag] = new UpgradeDef
            {
                Name = "背包", Desc = "採集能攜帶更多材料",
                Costs = new[] { 80, 200, 450 },
                Effect = lv => $"{BagAt(lv)} 格",
            },
            [Track.Shelf] = new UpgradeDef
            {
                Name = "貨架", Desc = "桌上能展示更多種商品",
                Costs = new[] { 120, 300 },
                Effect = lv => $"{ShelfAt(lv)} 種",
            },
            [Track.Plot] = new UpgradeDef
            {
                Name = "花圃", Desc = "把後花園的荒地開墾成花圃",
                Costs = new[] { 200, 500 },
                Effect = lv => $"{PlotAt(lv)} 塊",
            },
            [Track.Can] = new UpgradeDef
            {
                Name = "澆水壺", Desc = "一次澆得到更多塊花圃",
                Costs = new[] { 180, 500 },
                Effect = lv => CanAt(lv),
            },
        };

        const string Key = "witch.upgrades";

        static Dictionary<Track, int> levels;

        /// <summary>存檔用的形狀（JsonUtility 不吃 Dictionary，用固定欄位最單純）。</summary>
        [Serializable]
        class Save { public int signboard, bag, shelf, plot, can; }

        static Dictionary<Track, int> Levels
        {
            get
            {
                if (levels != null) return levels;
                levels = new Dictionary<Track, int>
                {
                    [Track.Signboard] = 0, [Track.Bag] = 0, [Track.Shelf] = 0,
                    [Track.Plot] = 0, [Track.Can] = 0,
                };
                try
                {
                    var raw = SaveManager.GetString(Key);
                    if (!string.IsNullOrEmpty(raw))
                    {
                        var o = JsonUtility.FromJson<Save>(raw);
                        if (o != null)
                        {
                            levels[Track.Signboard] = Clamp(o.signboard, Track.Signboard);
                            levels[Track.Bag]       = Clamp(o.bag,       Track.Bag);
                            levels[Track.Shelf]     = Clamp(o.shelf,     Track.Shelf);
                            levels[Track.Plot]      = Clamp(o.plot,      Track.Plot);
                            levels[Track.Can]       = Clamp(o.can,       Track.Can);
                        }
                    }
                }
                catch { /* 壞檔就用預設 */ }
                return levels;
            }
        }

        static int Clamp(int v, Track t) => Mathf.Clamp(v, 0, Defs[t].Costs.Length);

        static void SaveLevels()
        {
            SaveManager.SetString(Key, JsonUtility.ToJson(new Save
            {
                signboard = Levels[Track.Signboard],
                bag       = Levels[Track.Bag],
                shelf     = Levels[Track.Shelf],
                plot      = Levels[Track.Plot],
                can       = Levels[Track.Can],
            }));
        }

        // ──────────── 對外 API ────────────

        public static Track[] Tracks() => new[] { Track.Signboard, Track.Bag, Track.Shelf, Track.Plot, Track.Can };
        public static UpgradeDef Def(Track t) => Defs[t];

        public static int Level(Track t) => Levels[t];
        public static int MaxLevel(Track t) => Defs[t].Costs.Length;
        public static bool IsMax(Track t) => Levels[t] >= Defs[t].Costs.Length;

        /// <summary>升下一級的費用；已滿級回 -1。</summary>
        public static int Cost(Track t) => IsMax(t) ? -1 : Defs[t].Costs[Levels[t]];

        /// <summary>目前等級的效果文字。</summary>
        public static string EffectNow(Track t) => Defs[t].Effect(Levels[t]);
        /// <summary>下一級的效果文字（已滿級回空）。</summary>
        public static string EffectNext(Track t) => IsMax(t) ? "" : Defs[t].Effect(Levels[t] + 1);

        /// <summary>買下一級：金幣夠且未滿級才成功。</summary>
        public static bool Buy(Track t)
        {
            int c = Cost(t);
            if (c < 0 || Wallet.Gold < c) return false;
            Wallet.Add(-c);
            DailyLog.RecordSpend(c);      // 記進今日支出
            Levels[t] += 1;
            SaveLevels();
            return true;
        }

        // ── 給各系統讀的衍生值 ──────────────────────────────────
        public static int BagSlots() => BagAt(Levels[Track.Bag]);
        public static int ShelfCap() => ShelfAt(Levels[Track.Shelf]);
        public static float CustomerInterval() => IntervalAt(Levels[Track.Signboard]);
        public static int CustomerMax() => MaxAt(Levels[Track.Signboard]);
        /// <summary>後花園開墾了幾塊花圃（Garden.UnlockedCount 讀這個）。</summary>
        public static int GardenPlots() => PlotAt(Levels[Track.Plot]);
        /// <summary>澆水波及範圍：0＝只有腳下那塊、1＝十字相鄰、2＝整片花園。</summary>
        public static int WaterSpread() => Levels[Track.Can];
    }
}
