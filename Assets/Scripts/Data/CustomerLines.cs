using System.Collections.Generic;

namespace WitchShop.Data
{
    /// <summary>
    /// 店裡顧客的台詞「內容」資料（<see cref="Core.CustomerManager"/> 用）。
    ///
    /// 資料跟邏輯分開放，是這個專案的通例（同 Quests / Villagers / UpdateNotes）——
    /// 想加一句、改語氣，只要動這個檔，CustomerManager 一行都不用碰。
    ///
    /// 佔位字：
    ///   {item} ＝ 這位顧客正在看／想買的那樣商品（例：「藥草」）
    ///   {fest} ＝ 今天的節日名（只用在 <see cref="Festival"/> 那組，沒有節日時那組根本不會被抽到）
    ///
    /// 怎麼被抽：
    ///   ● 招呼（Greet）會混進「時段」「季節」「節日」那幾組加料一起抽 —— 早上進門跟傍晚進門講的不一樣。
    ///   ● 同一位顧客不會連續講同一句；同時在場、泡泡還沒消失的人講過的那句也會先避開
    ///     （真的抽不到別的才放寬，所以池子再小都不會卡住）。
    ///   ● <see cref="Personal"/> 是個別村民的專屬台詞，進門招呼時有一定機率（30%）改抽它。
    ///
    /// ⚠️ 字型是子集化過的（tools/subset_font.py 會掃整個 Assets 的原始碼收字），
    ///    這裡寫的字會自動被收進去；但**不要用 emoji 或冷門符號**（完整字型裡也沒有的字，
    ///    子集化再怎麼跑都只會是豆腐）。「～ … ！ ？ ♪」完整字型裡都有，可以用。
    /// ⚠️ 泡泡會依長度自動加寬、太長換成兩行（SpeechBubble），但兩行就是上限 ——
    ///    一句盡量控制在 16 個字以內，最長別超過 22 個字。
    /// </summary>
    public static class CustomerLines
    {
        /// <summary>進門的招呼。</summary>
        public static readonly string[] Greet =
        {
            "打擾了～",
            "哇，好香的味道！",
            "今天有什麼新貨嗎？",
            "魔女小姐，午安～",
            "聽說這裡的東西很靈驗",
            "來逛逛～",
            "門口的鈴鐺好可愛",
            "我又來了！",
            "朋友推薦我來的",
        };

        /// <summary>早上（11 點前）進門時加料。</summary>
        public static readonly string[] Morning =
        {
            "早安～開門了嗎？",
            "一大早就來報到！",
            "趁上班前來一趟",
            "早上的店裡好亮呢",
        };

        /// <summary>傍晚（17 點後）進門時加料。</summary>
        public static readonly string[] Evening =
        {
            "還好趕上了！",
            "下班順路來看看～",
            "天快黑了，買完就回家",
            "晚上的店裡好有氣氛",
        };

        /// <summary>季節加料，索引同 <see cref="Seasons.All"/>（0 春 1 夏 2 秋 3 冬）。</summary>
        public static readonly string[][] Season =
        {
            new[] { "外面的花都開了呢", "春天就是想買點新東西", "今天風好舒服～" },
            new[] { "外面好熱…讓我涼一下", "夏天果然要喝點清涼的", "曬得頭都暈了" },
            new[] { "落葉沙沙的好好聽", "秋天的空氣好清爽", "收成季，錢包也飽飽的" },
            new[] { "好冷好冷，讓我進來", "店裡好暖和～", "下雪前先來囤點貨" },
        };

        /// <summary>節日當天加料（{fest}＝節日名）。</summary>
        public static readonly string[] Festival =
        {
            "{fest}快樂！",
            "今天是{fest}耶～",
            "{fest}當然要來逛！",
            "趁{fest}買點好東西",
            "{fest}的人潮好多喔",
        };

        /// <summary>
        /// 走到商品前說想要什麼（會配上那樣商品的圖示）。
        /// ⚠️ 第一句維持舊版的「想要 X」—— 玩家已經習慣看這句認東西了。
        /// </summary>
        public static readonly string[] Want =
        {
            "想要 {item}",
            "我要這個 {item}",
            "{item} 請給我一個",
            "就是它了，{item}！",
            "找了好久的 {item}",
            "{item} 看起來好棒",
            "幫我包一個 {item}",
            "今天就買 {item} 吧",
        };

        /// <summary>成交後的道謝／評語（排在 +金額 泡泡之後）。</summary>
        public static readonly string[] Thanks =
        {
            "謝謝魔女小姐～",
            "太好了，買到了！",
            "下次還會再來的",
            "包裝好用心～",
            "回家馬上試試看",
            "這家店果然沒讓我失望",
            "價格好實在！",
            "今天運氣真好♪",
        };

        /// <summary>想要的東西剛好賣完（{item}＝他想要的那樣）。</summary>
        public static readonly string[] SoldOut =
        {
            "沒貨…下次吧",
            "{item} 賣完了嗎…",
            "唉，晚了一步",
            "下次要早點來…",
            "{item} 好搶手喔",
            "白跑一趟了…",
            "有進貨要跟我說喔",
        };

        /// <summary>只逛不買的人在商品前的評論（會配上那樣商品的圖示）。</summary>
        public static readonly string[] Browse =
        {
            "這個好可愛～",
            "{item}…看起來不錯",
            "嗯…再考慮一下",
            "原來有賣 {item} 啊",
            "擺得好整齊",
            "{item} 是做什麼用的？",
            "好想全部帶回家",
            "顏色好漂亮",
            "這個送人應該不錯",
        };

        /// <summary>只逛不買、要走的時候說的。</summary>
        public static readonly string[] BrowseLeave =
        {
            "下次發薪水再來",
            "今天先看看就好",
            "我回去想一想～",
            "錢包說不行…",
            "先記下來，改天買",
            "下次帶朋友來",
            "逛得好開心",
        };

        /// <summary>
        /// 結伴進門的一搭一唱：[0] 第一位進門時說、[1] 第二位跟在後面接話。
        /// 第三位（如果有）說 <see cref="GroupTail"/>。
        /// </summary>
        public static readonly string[][] Duo =
        {
            new[] { "就是這家！", "哇，跟你說的一樣可愛" },
            new[] { "你上次買的就是這裡？", "對呀，超好用的" },
            new[] { "說好只看不買喔", "嗯…盡量" },
            new[] { "快點快點～", "等一下啦！" },
            new[] { "這次換我請客", "真的？那我要挑貴的" },
            new[] { "聽說有新貨", "那一定要搶先看" },
            new[] { "先說好，不准亂花錢", "你自己才是吧～" },
            new[] { "魔女小姐人很好喔", "我有點緊張…" },
        };

        /// <summary>結伴的第三位（跟在最後面）。</summary>
        public static readonly string[] GroupTail =
        {
            "等等我～",
            "你們走好快！",
            "我也要看！",
            "別丟下我嘛",
            "我來了我來了",
            "幫我也留一個",
        };

        /// <summary>
        /// 個別村民的專屬台詞（key ＝ GameArt.VillagerNames() 的名字＝Resources/villagers 的檔名）。
        /// 進門招呼時有機率改抽這裡，讓常客有點個性。沒列到的村民就只講通用台詞。
        /// ⚠️ 只用在招呼（不用在商品前的評論）—— 寫的時候當成「一進門說的第一句」來寫。
        /// </summary>
        public static readonly Dictionary<string, string[]> Personal = new()
        {
            ["frog"]        = new[] { "呱！有新貨嗎？", "雨天最適合逛街了，呱", "這裡濕度剛剛好，呱～" },
            ["fox"]         = new[] { "嘿嘿，我只是路過", "這個價錢…可以算便宜點嗎？", "尾巴都興奮起來了" },
            ["rabbit"]      = new[] { "蹦蹦～我來了！", "有胡蘿蔔味的嗎？", "耳朵豎起來了！" },
            ["hedgehog"]    = new[] { "小心別被我刺到喔", "我慢慢看，不急", "縮成一團好想睡…" },
            ["deer"]        = new[] { "森林那邊也在聊這家店", "角卡到門框了…", "這裡跟森林一樣安靜" },
            ["fairy"]       = new[] { "亮晶晶的我都喜歡！", "我翅膀上的粉可以換嗎？", "飛累了，休息一下♪" },
            ["traveler"]    = new[] { "旅途中難得的好店", "幫我推薦點路上用的", "下一站也要介紹別人來" },
            ["mage"]        = new[] { "同行來觀摩一下", "這配方…有兩下子", "研究用，先買再說" },
            ["witch"]       = new[] { "同為魔女，來交流一下", "你的掃帚停哪裡？", "我也想開一間店～" },
            ["broomwitch"]  = new[] { "掃帚先停門口喔", "飛過來只花了一下下", "今天風向剛好" },
            ["rabbitwitch"] = new[] { "兔耳帽是我的招牌！", "魔法跟胡蘿蔔都要帶", "蹦～施個小魔法" },
        };
    }
}
