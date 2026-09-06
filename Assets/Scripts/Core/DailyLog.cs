using System;
using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>賣出明細的一筆：某品項今天賣了幾件、共多少錢。</summary>
    [Serializable]
    public class SaleEntry
    {
        public string name;
        public int q;    // 件數
        public int g;    // 金額
    }

    /// <summary>一天的統計。</summary>
    [Serializable]
    public class DayStats
    {
        public int revenue;    // 顧客買走商品的收入
        public int sales;      // 賣出件數
        public int trade;      // 材料拿去雜貨鋪收購的收入
        public int spent;      // 支出（升級、買裝飾）
        public int gathered;   // 採集到的材料數
        public int brewed;     // 煉製出的藥水數
        public int rep;        // 今天賺到的名聲點數
        public List<SaleEntry> items = new();

        public SaleEntry Find(string n)
        {
            foreach (var e in items) if (e.name == n) return e;
            return null;
        }
    }

    /// <summary>已結算的一天（比 DayStats 多「第幾天」與「是不是昏倒收場」）。</summary>
    [Serializable]
    public class DayRecord : DayStats
    {
        public int day;
        public bool collapsed;
    }

    /// <summary>
    /// 每日循環 ——「今天」的經營記帳簿。
    ///
    /// 遊戲裡的一天（06:00 起床 → 睡覺或 02:00 昏倒）會把當天的營收、賣出、採集、
    /// 煉製、支出統計起來；跨到隔天時 Rollover() 把今天封存成 Last（供結算畫面顯示），
    /// 並依當日營收再發一筆名聲，然後歸零開始新的一天。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版是「import 這個模組時就順便向 TimeSystem.onNewDay 註冊 rollover」——
    /// 靠 ES module 的載入副作用。C# 的 static 類別是**惰性初始化**的（沒人碰就不會跑），
    /// 照抄的話會變成「都沒人賣東西的那幾天不會結算」。
    /// 所以改用 [RuntimeInitializeOnLoadMethod]：遊戲一啟動就註冊，不管有沒有人用到它。
    /// </summary>
    public static class DailyLog
    {
        const string Key = "witch.daily";

        /// <summary>店裡的營業時間（顧客只在這段時間上門）。</summary>
        public const int ShopOpenHour = 8;
        public const int ShopCloseHour = 20;

        [Serializable] class Shape { public DayStats t; public DayRecord l; }

        static DayStats today;
        static DayRecord last;
        static bool loaded;

        /// <summary>遊戲一啟動就掛上跨日結算（取代原版的 module import 副作用）。</summary>
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Hook()
        {
            EnsureLoaded();
            TimeSystem.OnNewDay(Rollover);
        }

        static void EnsureLoaded()
        {
            if (loaded) return;
            loaded = true;
            today = new DayStats();
            try
            {
                var o = JsonUtility.FromJson<Shape>(SaveManager.GetString(Key));
                if (o?.t != null) today = o.t;
                if (o?.l != null && o.l.day > 0) last = o.l;
            }
            catch { /* 壞檔 → 從空的一天重來 */ }
            today.items ??= new List<SaleEntry>();
        }

        static void Save() =>
            SaveManager.SetString(Key, JsonUtility.ToJson(new Shape { t = today, l = last }));

        /// <summary>跨日：封存今天 → 發當日名聲 → 歸零。由 TimeSystem.OnNewDay 呼叫。</summary>
        static void Rollover(DayEndCause cause)
        {
            EnsureLoaded();
            today.rep += Reputation.AddDaily(today.revenue);

            // RollToNextDay 已經 +1 天了，所以「剛結束的那天」是 TotalDay - 1
            last = new DayRecord
            {
                day = Mathf.Max(1, TimeSystem.TotalDay - 1),
                collapsed = cause == DayEndCause.Collapse,
                revenue = today.revenue, sales = today.sales, trade = today.trade,
                spent = today.spent, gathered = today.gathered, brewed = today.brewed,
                rep = today.rep, items = today.items,
            };
            today = new DayStats();
            Save();
        }

        /// <summary>今天到目前為止的統計。</summary>
        public static DayStats Today { get { EnsureLoaded(); return today; } }
        /// <summary>最近一次結算完的一天（還沒過完第一天時是 null）。</summary>
        public static DayRecord Last { get { EnsureLoaded(); return last; } }

        /// <summary>現在店裡是營業時間嗎（顧客只在這段時間上門）。</summary>
        public static bool IsShopOpen()
        {
            float h = TimeSystem.TodHours;
            return h >= ShopOpenHour && h < ShopCloseHour;
        }

        /// <summary>營業時間文字，例：「08:00 – 20:00」。</summary>
        public static string HoursText() => $"{ShopOpenHour:00}:00 – {ShopCloseHour:00}:00";

        /// <summary>顧客買走一件商品（金額已進 Wallet；這裡只記帳＋加名聲）。</summary>
        public static void RecordSale(string name, int gold)
        {
            EnsureLoaded();
            today.revenue += gold;
            today.sales += 1;
            var e = today.Find(name);
            if (e != null) { e.q += 1; e.g += gold; }
            else today.items.Add(new SaleEntry { name = name, q = 1, g = gold });
            today.rep += Reputation.RecordSale(gold);
            Save();
        }

        /// <summary>材料賣給雜貨鋪的收購收入（不算店裡的生意，不加名聲）。</summary>
        public static void RecordTrade(int gold) { EnsureLoaded(); today.trade += Mathf.Max(0, gold); Save(); }

        /// <summary>採集到材料。</summary>
        public static void RecordGather(int qty) { EnsureLoaded(); today.gathered += Mathf.Max(0, qty); Save(); }

        /// <summary>煉製出藥水。</summary>
        public static void RecordBrew(int qty) { EnsureLoaded(); today.brewed += Mathf.Max(0, qty); Save(); }

        /// <summary>花掉金幣（升級、買裝飾）。</summary>
        public static void RecordSpend(int gold) { EnsureLoaded(); today.spent += Mathf.Max(0, gold); Save(); }
    }
}
