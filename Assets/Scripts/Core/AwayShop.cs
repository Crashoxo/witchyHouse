using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 你不在店裡的時候，店還是要做生意。
    ///
    /// 原本顧客只由 <see cref="CustomerManager"/> 產生，而它是**進 shop 場景才生出來的** ——
    /// 所以玩家一去採集、逛街、煉藥，店就等於關門，架上的東西一件也賣不掉。這一支補上那段空窗：
    /// 用**跟在場時完全一樣的規則**（招牌等級 × 名聲 × 節日的來客間隔、08:00–20:00 的營業時間、
    /// 架上有貨才成交）在背景成交，只是沒有走進來的那位村民、沒有對話泡。
    ///
    /// ⚠️ 刻意**不做離線收益**（關掉遊戲的那段時間不算）—— 這個遊戲的時間本來就只在遊玩時前進
    ///    （<see cref="TimeDriver"/> 每幀推 <see cref="TimeSystem"/>），關了遊戲時間就停，
    ///    所以「關著也在賣」會跟時鐘、花的成長、日夜全部對不起來。
    ///
    /// ⚠️ 成交走 <see cref="CustomerManager.CompleteSale"/>，跟在場時是同一段程式 ——
    ///    收錢、記今日營收、加名聲、記任務進度都一致，不會出現「離店賣掉的不算任務」這種落差。
    ///
    /// 賣掉的東西會累計起來，回到店裡時用一則 Toast 告訴玩家（<see cref="ReportOnReturn"/>）；
    /// 帳本身早就進了 <see cref="DailyLog"/>，所以睡覺時的每日結算也看得到。
    /// </summary>
    public class AwayShop : MonoBehaviour
    {
        public static AwayShop Instance { get; private set; }

        /// <summary>店裡那張場景的名字（在這張場景就交給真的顧客跑，這裡不動作）。</summary>
        const string ShopScene = "shop";

        /// <summary>
        /// 沒人顧店時的成交效率。1 ＝ 跟你站在店裡完全一樣。
        /// 想讓「親自顧店」比較划算就調低（例如 0.7 ＝ 慢三成）。
        /// </summary>
        const float AwayRate = 1f;

        float timer;
        int soldCount;      // 這次離店期間賣掉幾件
        int soldGold;       // 這次離店期間賺了多少

        public static AwayShop Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("AwayShop");
            DontDestroyOnLoad(go);      // 換場景不能被銷毀，不然一過圖就從頭數
            return go.AddComponent<AwayShop>();
        }

        void Awake() { Instance = this; }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Update()
        {
            // 人在店裡 → 由 CustomerManager 生真的顧客，這裡讓開（不然會雙倍賣）
            if (UnityEngine.SceneManagement.SceneManager.GetActiveScene().name == ShopScene) return;
            // 開著視窗時整個遊戲是停的（時間也不走），成交也要跟著停
            if (UIState.ModalOpen) return;
            if (!DailyLog.IsShopOpen()) { timer = 0f; return; }
            if (ShopStock.Types == 0) { timer = 0f; return; }

            // 來客間隔：跟 CustomerManager 同一條式子
            bool festival = TimeSystem.FestivalToday() != null;
            float interval = Upgrades.CustomerInterval() * Reputation.IntervalScale()
                             * (festival ? 0.6f : 1f);
            if (AwayRate > 0f) interval /= AwayRate;

            timer += Time.deltaTime;
            if (timer < interval) return;
            timer -= interval;          // 用減的不要歸零，掉幀時才不會少算客人

            Sell();
        }

        /// <summary>來一位看不見的客人：隨機挑一件架上的東西買走。</summary>
        void Sell()
        {
            var list = ShopStock.Listings();
            if (list.Count == 0) return;

            string want = list[Random.Range(0, list.Count)].name;
            int price = CustomerManager.CompleteSale(want);
            if (price <= 0) return;     // 剛好賣完了 —— 跟在場時一樣，這位客人空手而歸

            soldCount++;
            soldGold += price;
        }

        /// <summary>
        /// 回到店裡時報告這段期間賣了什麼。由 PlayerController 進 shop 場景時呼叫。
        /// 沒賣掉東西就什麼都不做（不要每次進店都跳一則「賣出 0 件」）。
        /// </summary>
        public static void ReportOnReturn()
        {
            var a = Instance;
            if (a == null || a.soldCount <= 0) return;
            UI.Toast.Show($"你不在的時候賣出 {a.soldCount} 件，賺了 {a.soldGold} 金");
            a.soldCount = 0;
            a.soldGold = 0;
        }
    }
}
