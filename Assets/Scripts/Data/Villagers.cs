namespace WitchShop.Data
{
    public class VillagerDef
    {
        /// <summary>名字（＝TalkNpc.NpcName＝友誼度的 key）。</summary>
        public string Name;
        /// <summary>GameArt portraits 的頭像名（留空＝面板畫一個代用圓框）。</summary>
        public string Portrait;
        /// <summary>住處／店名。</summary>
        public string Place;
        /// <summary>一句話介紹。</summary>
        public string Desc;
    }

    /// <summary>
    /// 村民「內容」資料：玩家資訊面板（Tab）的村民頁要顯示誰、頭像用哪張、住在哪。
    ///
    /// ⚠️ Name 必須跟場景裡 TalkNpc 的 NpcName 完全一致 —— 友誼度是用名字當 key 記的
    ///    （同 Quests 的 Giver 對應方式），這樣新增村民只要「掛上 TalkNpc + 在這裡加一筆」。
    /// </summary>
    public static class Villagers
    {
        public static readonly VillagerDef[] All =
        {
            new() { Name = "地精老闆", Portrait = "gnome", Place = "藥水鋪",
                    Desc = "鎮上開店最久的地精，嘴上唸個不停，其實很照顧新來的。" },
            new() { Name = "精靈書商", Portrait = "elf",   Place = "卷軸鋪",
                    Desc = "賣卷軸與古書的精靈，對能背下配方的人特別有好感。" },
            new() { Name = "魔法貓",   Portrait = "fox",   Place = "法術鋪",
                    Desc = "看店的黑貓。沒人知道真正的店主是誰，牠也不打算說。" },
        };

        /// <summary>每一顆心需要的友誼點數，以及最多幾顆心。</summary>
        public const int PointsPerHeart = 50;
        public const int MaxHearts = 5;
        /// <summary>每天第一次跟同一位村民交談可得的友誼點數。</summary>
        public const int TalkPoints = 8;
    }

    /// <summary>
    /// 對話「內容」資料。TalkNpc 沒指定台詞時，用這組預設閒聊。
    /// （之後 AI-NPC 對話或更多樹狀分支台詞也可以集中放這裡。）
    /// </summary>
    public static class Dialogue
    {
        public static readonly string[] DefaultNpcLines =
        {
            "嗨，旅行者！歡迎來到魔法小鎮。",
            "往東邊的森林去採些材料，回你的店裡上架，客人自然會上門喔。",
            "有空再來找我聊聊吧！",
        };
    }
}
