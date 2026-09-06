namespace WitchShop.Data
{
    /// <summary>
    /// 開遊戲時那張「更新公告板」要寫什麼（<see cref="UI.UpdatePanel"/> 用）。
    ///
    /// 資料跟版面分開放，是這個專案的通例（同 Quests / Villagers / Furniture）——
    /// 改公告只要動這個檔，`UpdatePanel` 一行都不用碰。
    ///
    /// 寫法：一行一條，開頭的「·」是刻意留在文字裡的（版面不另外做項目符號，
    /// 這樣要寫不帶符號的說明句也可以）。行數多的時候字級會自己縮，但超過八、九條
    /// 就會開始難讀 —— 與其塞滿，不如只留玩家真的看得出差別的那幾條。
    /// </summary>
    public static class UpdateNotes
    {
        /// <summary>顯示在公告最上方的日期。</summary>
        public const string Date = "2026 / 09 / 06";

        /// <summary>這次更新的內容，一行一條。</summary>
        public static readonly string[] Lines =
        {
            "· 整個遊戲換成 Unity 重做了一遍",
            "· 睡醒之後多了「今日結算」帳單",
            "· 店內佈置：擋路或穿牆的格子會標紅，並說明原因",
            "· 靠牆的貨架可以換基準點，貼得住牆了",
            "· 角色腳下都有了影子",
            "· 修好女巫比地面低半身的問題",
        };
    }
}
