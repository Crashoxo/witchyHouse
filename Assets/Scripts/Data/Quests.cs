namespace WitchShop.Data
{
    /// <summary>
    /// 任務目標的種類。
    ///   Gather / Sell / Brew —— 累積計數（採集/賣出/調配「總數」，只增不減）。Item 留空＝任意種類。
    ///   Have  —— 目前背包持有 N 個（Consume=true 時回報會扣掉＝送貨任務）。
    ///   Gold  —— 錢包金幣達到 N。
    /// </summary>
    public enum ObjKind { Gather, Sell, Brew, Have, Gold }

    public class QuestObjective
    {
        public ObjKind Kind;
        public string Item = "";   // 留空＝任意（Gather/Sell/Brew）。Gold 不用
        public int Count;
        public bool Consume;        // Have 專用：回報時把物品扣掉（送貨任務）
    }

    public class QuestDef
    {
        public string Id;
        public string Giver;        // 發任務的 NPC 名（＝TalkNpc.NpcName，用來對應）
        public string Title;
        public QuestObjective Objective;
        public int RewardGold;
        public string RewardItem = "";
        public int RewardQty;
        public string[] OfferLines;   // 提供任務時 NPC 說的話
        public string[] ActiveLines;  // 進行中（還沒完成）
        public string[] ReadyLines;   // 完成、可回報時
        public string[] DoneLines;    // 領獎後
        public string Requires = ""; // 前置任務 id（要先領獎才會解鎖）
    }

    /// <summary>
    /// 任務「內容」資料。狀態機、進度、存檔在 Core/Quests.cs。
    ///
    /// ⚠️ 這個檔是**從 Cocos 的 data/quests.ts 自動轉出來的** —— 台詞很多，手打容易漏字。
    ///    原專案改了任務內容的話重跑轉換器即可（見 PortNotes.md）。
    /// </summary>
    public static class Quests
    {
        /// <summary>9 個任務，依 Requires 串成任務鏈。</summary>
        public static readonly QuestDef[] All =
        {
            new()
            {
                Id = "gather_wood", Giver = "地精老闆", Title = "收集木材",
                Objective = new() { Kind = ObjKind.Gather, Item = "木材", Count = 5 },
                RewardGold = 30,
                OfferLines  = new[] { "唉，我的藥架又搖搖晃晃了…", "你能幫我到東邊森林採 5 個木材回來嗎？" },
                ActiveLines = new[] { "木材採到 5 個了嗎？往東邊森林走，靠近樹按 E 就能採。" },
                ReadyLines  = new[] { "喔！木材都齊了，太感謝你了！" },
                DoneLines   = new[] { "這 30 金幣是謝禮，拿去吧。" },
            },
            new()
            {
                Id = "sell_three", Giver = "地精老闆", Title = "第一批生意",
                Objective = new() { Kind = ObjKind.Sell, Item = "", Count = 3 },
                RewardGold = 40, Requires = "gather_wood",
                OfferLines  = new[] { "開店最重要的，就是把東西賣出去。", "去把商品上架，賣出 3 件給上門的客人，讓我看看你的本事。" },
                ActiveLines = new[] { "賣出 3 件商品了嗎？把材料或藥水擺上桌，客人自然會來。" },
                ReadyLines  = new[] { "生意做得有模有樣嘛！" },
                DoneLines   = new[] { "這是給新手老闆的鼓勵，收下這 40 金。" },
            },
            new()
            {
                Id = "brew_two", Giver = "地精老闆", Title = "初嘗煉金",
                Objective = new() { Kind = ObjKind.Brew, Item = "", Count = 2 },
                RewardGold = 60, Requires = "sell_three",
                OfferLines  = new[] { "光賣原料利潤太薄了。", "到店裡右上角的藥水室，調配 2 瓶藥水吧——附加價值高多了。" },
                ActiveLines = new[] { "調好 2 瓶藥水了嗎？店面右上角進藥水室，走到鍋爐按 E。" },
                ReadyLines  = new[] { "我聞到藥香了！你有天份。" },
                DoneLines   = new[] { "這瓶配方費 60 金給你，繼續加油。" },
            },
            new()
            {
                Id = "deliver_berry", Giver = "地精老闆", Title = "地精的點心",
                Objective = new() { Kind = ObjKind.Have, Item = "漿果", Count = 5, Consume = true },
                RewardGold = 50, RewardItem = "金蘋果", RewardQty = 1, Requires = "brew_two",
                OfferLines  = new[] { "說來有點不好意思…我肚子餓了。", "幫我帶 5 個漿果來，我請你吃一顆金蘋果！" },
                ActiveLines = new[] { "漿果帶來了嗎？背包裡要有 5 個，我才收得下。" },
                ReadyLines  = new[] { "哇，新鮮的漿果！謝謝你～" },
                DoneLines   = new[] { "說好的金蘋果給你，還有 50 金當跑腿費！" },
            },
            new()
            {
                Id = "gold_300", Giver = "地精老闆", Title = "小有積蓄",
                Objective = new() { Kind = ObjKind.Gold, Item = "", Count = 300 },
                RewardGold = 100, RewardItem = "金蘋果", RewardQty = 2, Requires = "deliver_berry",
                OfferLines  = new[] { "當老闆的目標是什麼？當然是賺錢！", "等你存到 300 金幣，再來找我，有好東西給你。" },
                ActiveLines = new[] { "存到 300 金幣了嗎？多調點藥水賣，錢很快就進來了。" },
                ReadyLines  = new[] { "300 金！你已經是像樣的老闆了。" },
                DoneLines   = new[] { "這是給成功商人的賀禮：100 金，還有兩顆金蘋果！" },
            },
            new()
            {
                Id = "eb_herbs", Giver = "精靈書商", Title = "古籍的配方",
                Objective = new() { Kind = ObjKind.Gather, Item = "藥草", Count = 4 },
                RewardGold = 35,
                OfferLines  = new[] { "這本舊書寫著一帖失傳的配方…", "幫我採 4 株藥草來，我想試著重現它。" },
                ActiveLines = new[] { "藥草採到 4 株了嗎？森林的花圃裡就有。" },
                ReadyLines  = new[] { "正是這種藥草！書上畫的沒錯。" },
                DoneLines   = new[] { "謝謝你，這 35 金是酬勞。" },
            },
            new()
            {
                Id = "eb_rich", Giver = "精靈書商", Title = "藏書的價值",
                Objective = new() { Kind = ObjKind.Gold, Item = "", Count = 500 },
                RewardGold = 0, RewardItem = "金蘋果", RewardQty = 2, Requires = "eb_herbs",
                OfferLines  = new[] { "知識是無價的，但書可不便宜。", "等你存到 500 金幣，我把珍藏的好東西分你一些。" },
                ActiveLines = new[] { "存到 500 金幣了嗎？藥水利潤最高囉。" },
                ReadyLines  = new[] { "哇，你真的辦到了！" },
                DoneLines   = new[] { "說好的珍藏——兩顆金蘋果，收下吧。" },
            },
            new()
            {
                Id = "cat_berries", Giver = "魔法貓", Title = "喵的點心",
                Objective = new() { Kind = ObjKind.Gather, Item = "黑莓", Count = 3 },
                RewardGold = 30,
                OfferLines  = new[] { "喵～我最愛黑莓了。", "去採 3 顆黑莓給我，我告訴你一個祕密，喵。" },
                ActiveLines = new[] { "黑莓採到 3 顆了嗎？荊棘叢裡有喔，喵。" },
                ReadyLines  = new[] { "喵嗚～就是這個味道！" },
                DoneLines   = new[] { "祕密是…東邊森林的樹會結金蘋果喔。這 30 金給你，喵。" },
            },
            new()
            {
                Id = "cat_leaves", Giver = "魔法貓", Title = "鋪窩大工程",
                Objective = new() { Kind = ObjKind.Gather, Item = "落葉", Count = 6 },
                RewardGold = 40, Requires = "cat_berries",
                OfferLines  = new[] { "本喵想鋪一個又軟又香的窩，喵。", "幫我收集 6 片落葉吧！" },
                ActiveLines = new[] { "落葉撿到 6 片了嗎？樹下的落葉堆最多，喵。" },
                ReadyLines  = new[] { "蓬鬆鬆的，本喵很滿意，喵～" },
                DoneLines   = new[] { "賞你 40 金，去買點好吃的吧，喵。" },
            },
        };

        public static QuestDef ById(string id)
        {
            foreach (var q in All) if (q.Id == id) return q;
            return null;
        }
    }
}
