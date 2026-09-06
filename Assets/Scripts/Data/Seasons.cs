using System.Collections.Generic;

namespace WitchShop.Data
{
    public class SeasonDef
    {
        /// <summary>單字季名（時鐘盤面那個小框放得下的長度）。</summary>
        public string Name;
        /// <summary>完整季名（面板標題用）。</summary>
        public string Label;
        /// <summary>一句話的季節描述（日曆頁顯示）。</summary>
        public string Desc;
        /// <summary>天亮時刻偏移（小時，正＝亮得晚）。</summary>
        public float DawnShift;
        /// <summary>天黑時刻偏移（小時，負＝黑得早）。</summary>
        public float DuskShift;
        /// <summary>當季盛產的材料（採集會多給、稀有掉落機率提高）。</summary>
        public string[] BonusItems;
    }

    /// <summary>節日：某個月的第幾天。當天客人特別多，日曆上會標出來。</summary>
    public class Festival
    {
        public int Month;   // 1..12
        public int Day;     // 1..28
        public string Name;
        public string Desc;
    }

    /// <summary>
    /// 年曆與季節「內容」資料：一個月 28 天、一年 12 個月（336 天），每 3 個月一季。
    ///   一～三月＝春　四～六月＝夏　七～九月＝秋　十～十二月＝冬
    ///
    /// 季節目前影響三件事，都是從這張表讀出來的：
    ///   1. 天色 —— DawnShift / DuskShift 把 DayNightTint 的曲線整段前後挪（冬天早黑晚亮）。
    ///   2. 採集 —— BonusItems 是當季盛產的材料，採到會多給、稀有掉落機率也高一點。
    ///   3. 節日 —— Festivals 標在日曆上，當天客人特別多。
    /// 要調整季節感就改這裡，程式不用動。
    /// </summary>
    public static class Seasons
    {
        /// <summary>四季，索引 0..3。</summary>
        public static readonly SeasonDef[] All =
        {
            new() { Name = "春", Label = "春天", Desc = "萬物冒芽，花草長得特別快。",
                    DawnShift = 0f,     DuskShift = 0f,     BonusItems = new[] { "藥草", "漿果" } },
            new() { Name = "夏", Label = "夏天", Desc = "日照最長的季節，莓果又甜又多。",
                    DawnShift = -0.5f,  DuskShift = 1.0f,   BonusItems = new[] { "漿果", "黑莓", "藍莓" } },
            new() { Name = "秋", Label = "秋天", Desc = "果實成熟、落葉滿地，收成的季節。",
                    DawnShift = 0.4f,   DuskShift = -0.7f,  BonusItems = new[] { "落葉", "金蘋果" } },
            new() { Name = "冬", Label = "冬天", Desc = "天黑得早，只有耐寒的枯枝與木材。",
                    DawnShift = 1.0f,   DuskShift = -1.5f,  BonusItems = new[] { "木材", "樹枝" } },
        };

        /// <summary>一個月 28 天、一年 12 個月，每 3 個月一季。</summary>
        public const int DaysPerMonth   = 28;
        public const int MonthsPerYear  = 12;
        public const int MonthsPerSeason = 3;

        public static readonly Festival[] Festivals =
        {
            new() { Month = 1,  Day = 7,  Name = "播種祭",     Desc = "村民互相分送種子，森林的藥草冒得特別旺。" },
            new() { Month = 3,  Day = 21, Name = "花之祭典",   Desc = "街上鋪滿花瓣，逛街的人潮一整天不斷。" },
            new() { Month = 5,  Day = 14, Name = "仲夏螢火節", Desc = "入夜後溪邊全是螢火蟲，鎮上熱鬧到很晚。" },
            new() { Month = 6,  Day = 18, Name = "盛夏市集",   Desc = "廣場擺滿攤子，連隔壁村的人都來逛。" },
            new() { Month = 8,  Day = 10, Name = "月光茶會",   Desc = "大家帶著自釀的飲品聚在廣場，藥水特別好賣。" },
            new() { Month = 9,  Day = 28, Name = "豐收祭",     Desc = "一年裡最盛大的市集，店門口大排長龍。" },
            new() { Month = 11, Day = 5,  Name = "初雪祭",     Desc = "第一場雪落下的日子，鎮上會煮熱飲請大家。" },
            new() { Month = 12, Day = 24, Name = "星光節",     Desc = "冬夜點起星燈，村民習慣在這天互送小禮物。" },
        };

        /// <summary>某月屬於哪一季（0..3）。月份是 1..12。</summary>
        public static int SeasonOfMonth(int month) => ((month - 1) / MonthsPerSeason) % All.Length;

        public static Festival FestivalOn(int month, int day)
        {
            foreach (var f in Festivals) if (f.Month == month && f.Day == day) return f;
            return null;
        }
    }
}
