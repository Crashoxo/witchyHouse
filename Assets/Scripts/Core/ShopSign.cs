using System;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 店門口的「開店／關店」招牌 —— 玩家自己決定今天要不要做生意。
    ///
    /// 為什麼要這個（使用者實機回饋）：「關店才可以擺放貨架，所以要有關店跟開店」。
    /// 佈置模式（ShopRoomEditor）只在關店時進得去，開店時顧客照常進門買東西。
    ///
    /// 兩個概念要分清楚：
    ///   ● <see cref="IsOpen"/>＝**玩家掛的牌子**（存檔）。跟時間無關。
    ///   ● <see cref="DailyLog.IsShopOpen"/>＝**營業時間** 08:00–20:00（別處在用，語意不動）。
    ///   ● <see cref="Serving"/>＝兩者都成立＝「現在真的在做生意」。
    ///     CustomerManager（進新客）與 AwayShop（不在店裡時的背景成交）都看這個。
    ///
    /// 存檔 key：<c>witch.shop.sign</c>，內容 "1"／"0"。**沒有這個 key＝開店**
    /// （舊存檔升上來行為不變：以前沒有招牌，店就是一直開著的）。
    ///
    /// 每天早上**不會自動開店**：維持玩家上次的設定。關著的時候門口招牌會一直輕輕晃
    /// （ShopSignPost），提醒玩家「店還沒開」。
    ///
    /// ⚠️ 靜態狀態：關掉 Domain Reload 進 Play 時，上一輪的快取與事件訂閱會留著 ——
    ///    <see cref="ResetStatics"/> 在 SubsystemRegistration 清乾淨（照 Sfx.Changed 的做法）。
    /// ⚠️ 開新遊戲（SaveManager.Wipe）會刪掉這個 key，但記憶體裡的快取不會自己知道 ——
    ///    所以讀值時**每次都從 SaveManager 讀**（它本身就是記憶體裡的 Dictionary，很便宜），
    ///    不另外快取，免得 Wipe 之後還是舊值。
    /// </summary>
    public static class ShopSign
    {
        /// <summary>存檔 key（已列進 SaveManager.SaveKeys）。</summary>
        public const string SaveKey = "witch.shop.sign";

        /// <summary>開店／關店的風鈴聲（Resources/audio/，tools/gen_sfx.py 合成）。</summary>
        public const string ChimeOpen = "chime-open";
        public const string ChimeClose = "chime-close";

        /// <summary>玩家設定的開店／關店（存檔）；**不含營業時間**。沒存過＝開店。</summary>
        public static bool IsOpen
        {
            get
            {
                var raw = SaveManager.GetString(SaveKey);
                return raw != "0";      // null（沒存過）、"1"、或讀不懂的值一律當開店 —— 寧可多做生意也不要莫名關店
            }
        }

        /// <summary>
        /// 現在真的在做生意＝招牌開著 **且** 在營業時間內。
        /// 顧客進門、背景成交都看這個；不要直接改 DailyLog.IsShopOpen 的語意。
        /// </summary>
        public static bool Serving => IsOpen && DailyLog.IsShopOpen();

        /// <summary>狀態變了就發（HUD、門口招牌訂閱）。值沒變不發。</summary>
        public static event Action Changed;

        /// <summary>設定＋存檔＋發事件＋播風鈴聲；值沒變就什麼都不做。</summary>
        public static void SetOpen(bool open)
        {
            if (open == IsOpen) return;
            SaveManager.SetString(SaveKey, open ? "1" : "0");
            Sfx.Play(open ? ChimeOpen : ChimeClose);
            try { Changed?.Invoke(); }
            catch (Exception e) { Debug.LogWarning($"[ShopSign] Changed 的訂閱者出錯：{e.Message}"); }
        }

        /// <summary>開↔關 切換（上方工具列的開關店鈕／熱鍵 P，見 UI/CornerHud）。</summary>
        public static void Toggle() => SetOpen(!IsOpen);

        /// <summary>關掉 Domain Reload 進 Play 時，上一輪的訂閱者會留著 —— 這裡清掉。</summary>
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() => Changed = null;
    }
}
