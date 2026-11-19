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
        public const string Date = "2026 / 11 / 19";

        /// <summary>這次更新的內容，一行一條。</summary>
        public static readonly string[] Lines =
        {
            "· 遊戲有聲音了：腳步、採集、施法、收錢…（按 M 靜音）",
            "· 森林、城鎮、糖果鎮的地面重新畫過",
            "· 樹和房子腳下有了樹蔭，草地上多了小花",
            "· 打開背包、任務簿等面板時會有動態",
            "· 撿到東西、金幣變動時，畫面會跳一下提示",
            "· 修好任務簿偶爾按了沒反應的問題",
        };
    }
}
