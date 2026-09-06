using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 店鋪名聲：賣東西給顧客會累積名聲點數，達到門檻升一級（共 5 級，各有稱號）。
    ///
    /// 名聲影響「來客」—— 跟「招牌」升級是兩條互補的軌：
    ///   招牌（花金幣買）  → 基礎的來客間隔與同時人數（Upgrades）
    ///   名聲（做生意賺來）→ 在招牌的基礎上再加成（間隔 ×Scale、同時人數 +Extra）
    /// CustomerManager 生成顧客時把兩者相乘/相加，所以「好好經營」本身就會讓店更熱鬧。
    ///
    /// 加點的入口統一走 DailyLog（賣出當下 RecordSale、當日結算 AddDaily），
    /// 這樣「今天賺到多少名聲」才能寫進當日結算畫面。
    /// </summary>
    public static class Reputation
    {
        const string Key = "witch.reputation";

        class Rank
        {
            public int Need;        // 升到這一級所需的累積點數
            public string Title;    // 稱號
            public int Extra;       // 同時來客 +N
            public float Scale;     // 來客間隔倍率（<1＝來得更快）
        }

        static readonly Rank[] Ranks =
        {
            new() { Need = 0,   Title = "無名小店", Extra = 0, Scale = 1.00f },
            new() { Need = 40,  Title = "略有耳聞", Extra = 0, Scale = 0.92f },
            new() { Need = 120, Title = "小有名氣", Extra = 1, Scale = 0.85f },
            new() { Need = 300, Title = "遠近馳名", Extra = 1, Scale = 0.78f },
            new() { Need = 700, Title = "傳說名店", Extra = 2, Scale = 0.70f },
        };

        static int? points;

        public static int Points
        {
            get
            {
                if (points == null)
                {
                    var v = SaveManager.GetString(Key);
                    points = int.TryParse(v, out var n) && n > 0 ? n : 0;
                }
                return points.Value;
            }
        }

        static void Save() => SaveManager.SetString(Key, Points.ToString());

        /// <summary>目前等級的索引（0 起）。</summary>
        static int RankIdx()
        {
            int i = 0;
            for (int k = 0; k < Ranks.Length; k++) if (Points >= Ranks[k].Need) i = k;
            return i;
        }

        /// <summary>等級 1..5。</summary>
        public static int Level => RankIdx() + 1;
        public static string Title => Ranks[RankIdx()].Title;
        public static bool IsMax => RankIdx() >= Ranks.Length - 1;

        /// <summary>升下一級所需的累積點數；已滿級回 -1。</summary>
        public static int NextNeed
        {
            get { int i = RankIdx(); return i >= Ranks.Length - 1 ? -1 : Ranks[i + 1].Need; }
        }

        /// <summary>往下一級的進度 0..1（已滿級回 1）。</summary>
        public static float Progress
        {
            get
            {
                int i = RankIdx();
                if (i >= Ranks.Length - 1) return 1f;
                float a = Ranks[i].Need, b = Ranks[i + 1].Need;
                return Mathf.Clamp01((Points - a) / (b - a));
            }
        }

        /// <summary>直接加點（回傳實際加了多少，方便呼叫端記帳）。</summary>
        public static int Add(int n)
        {
            if (n <= 0) return 0;
            points = Points + n;
            Save();
            return n;
        }

        /// <summary>賣出一件商品：固定 1 點，賣得越貴額外加點。</summary>
        public static int RecordSale(int gold) => Add(1 + gold / 40);

        /// <summary>當日結算：依整天營收再給一筆。</summary>
        public static int AddDaily(int revenue) => Add(revenue / 100);

        // ── 給 CustomerManager 讀的來客加成 ──────────────────────

        /// <summary>同時來客人數加成（疊在招牌升級之上）。</summary>
        public static int ExtraCustomers() => Ranks[RankIdx()].Extra;
        /// <summary>來客間隔倍率（疊在招牌升級之上，&lt;1＝來得更快）。</summary>
        public static float IntervalScale() => Ranks[RankIdx()].Scale;
    }
}
