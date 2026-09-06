using System.Collections;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 睡覺過場：淡入全螢幕深色幕 → 中央顯示睡覺中的女巫立繪（含她自己的小床，
    /// 所以不會跟房間的床衝突）→ 時間前進 → 顯示新的日期時間 → 每日結算帳單 → 淡出。
    ///
    /// 兩個入口：
    ///   Play()         —— 走到床邊按 E 主動睡覺（**由這裡推進時間**）。
    ///   PlayCollapse() —— 撐到 02:00 昏倒。此時 TimeSystem 已經自己跳過日了，
    ///                     所以**不再推進時間**，只演過場；而且醒來一定要在房間，
    ///                     人不在 brew 場景時趁畫面全黑直接載入房間再淡入。
    ///
    /// 昏倒的觸發靠 Arm() 註冊 TimeSystem.OnNewDay。
    /// </summary>
    public class SleepOverlay : MonoBehaviour
    {
        public static SleepOverlay Instance { get; private set; }

        public static SleepOverlay Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("SleepOverlayUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<SleepOverlay>();
        }

        static bool armed;

        /// <summary>
        /// 掛上「撐到 02:00 昏倒也要演過場」。整個遊戲只註冊一次。
        /// 由 PlayerController 每個場景呼叫（重複呼叫安全）。
        /// </summary>
        public static void Arm()
        {
            if (armed) return;
            armed = true;
            TimeSystem.OnNewDay(cause =>
            {
                // ⚠️ 只有「昏倒」要在這裡演 —— 自己去睡的那條路是 Play() 先演過場再推時間，
                //    在這裡再演一次會變成兩層黑幕疊在一起。
                if (cause == DayEndCause.Collapse) Ensure().PlayCollapse();
            });
        }

        UIDocument doc;
        VisualElement root, veil, witch;
        Label topLabel, bottomLabel;
        bool built;
        bool playing;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 90;      // 蓋在所有面板之上、換場黑幕（100）之下
            if (doc.panelSettings == null)
                Debug.LogError("[SleepOverlay] 找不到 Resources/ui/UIPanelSettings");
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        /// <summary>主動睡覺：演過場，中途推進時間。</summary>
        public void Play()
        {
            if (playing) return;
            StartCoroutine(Run(true));
        }

        /// <summary>昏倒：時間已經被 TimeSystem 跳過了，這裡只演過場並把人送回房間。</summary>
        public void PlayCollapse()
        {
            if (playing) return;
            StartCoroutine(Run(false));
        }

        IEnumerator Run(bool advanceTime)
        {
            if (!built) Build();
            if (!built) yield break;

            playing = true;
            UIState.ModalOpen = true;                 // 過場中角色不動、時間凍結

            topLabel.text = advanceTime ? "呼……睡一下吧" : "撐不住了…";
            bottomLabel.text = "";
            root.style.display = DisplayStyle.Flex;

            yield return Fade(0f, 1f, 0.45f);

            // 畫面全黑之後才動時間與場景 —— 玩家看不到中間的跳動
            if (advanceTime) TimeSystem.Sleep();

            // 昏倒醒來一定要在房間
            if (!advanceTime && SceneManager.GetActiveScene().name != "brew"
                && Application.CanStreamedLevelBeLoaded("brew"))
            {
                var op = SceneManager.LoadSceneAsync("brew");
                while (op != null && !op.isDone) yield return null;
                yield return null;                    // 等一幀讓新場景擺好
                UIState.ModalOpen = true;             // 新場景會重置，這裡補回來
            }

            topLabel.text = advanceTime ? "睡了一覺" : "醒來時已經是……";
            bottomLabel.text = $"{TimeSystem.DateTextFull()}　{TimeSystem.ClockText()}";

            yield return new WaitForSecondsRealtime(1.1f);

            // 帳單接在這裡 —— 時間已經推進、畫面還全黑，玩家按鍵關掉才繼續淡出。
            // 放在淡出之後就會蓋在遊戲畫面上，那不是要的效果。
            if (DaySummaryPanel.HasData)
            {
                ShowStage(false);                 // 兩層置中的東西會疊在一起，先把立繪收掉
                var sum = DaySummaryPanel.Ensure();
                sum.Open();
                while (sum.IsOpen) yield return null;
                ShowStage(true);
                UIState.ModalOpen = true;         // 保險：淡出這段仍然不讓角色動
            }

            yield return Fade(1f, 0f, 0.5f);

            root.style.display = DisplayStyle.None;
            UIState.ModalOpen = false;
            playing = false;
        }

        /// <summary>帳單開著時把睡覺過場的立繪與文字收起來（不然兩層置中的東西會疊在一起）。</summary>
        void ShowStage(bool show)
        {
            var v = show ? DisplayStyle.Flex : DisplayStyle.None;
            if (topLabel != null) topLabel.style.display = v;
            if (witch != null) witch.style.display = v;
            if (bottomLabel != null) bottomLabel.style.display = v;
        }

        IEnumerator Fade(float from, float to, float dur)
        {
            float t = 0f;
            dur = Mathf.Max(0.01f, dur);
            while (t < dur)
            {
                t += Time.unscaledDeltaTime;
                veil.style.opacity = Mathf.Lerp(from, to, Mathf.Clamp01(t / dur));
                yield return null;
            }
            veil.style.opacity = to;
        }

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[SleepOverlay] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            CjkFont.Apply(root);

            veil = new VisualElement();
            veil.AddToClassList("sleep-veil");
            veil.style.opacity = 0f;
            root.Add(veil);

            topLabel = new Label();
            topLabel.AddToClassList("sleep-top");
            veil.Add(topLabel);

            witch = new VisualElement();
            witch.AddToClassList("sleep-witch");
            var sp = GameArt.WitchSleep;
            if (sp != null)
            {
                witch.style.backgroundImage = new StyleBackground(sp);
                // 依原圖比例撐開，最高 220px
                float k = 220f / Mathf.Max(1f, sp.rect.height);
                witch.style.width = sp.rect.width * k;
                witch.style.height = 220f;
            }
            veil.Add(witch);

            bottomLabel = new Label();
            bottomLabel.AddToClassList("sleep-bottom");
            veil.Add(bottomLabel);

            root.style.display = DisplayStyle.None;
            built = true;
        }
    }
}
