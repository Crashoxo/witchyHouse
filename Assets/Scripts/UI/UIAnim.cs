using System.Runtime.CompilerServices;
using UnityEngine;
using UnityEngine.UIElements;

namespace WitchShop.UI
{
    /// <summary>
    /// 面板開關動效與 HUD 小回饋的共用工具。樣式在 `Resources/ui/AnimStyle.uss`
    /// （由這裡自己掛到面板的根上，呼叫端不用另外 Add 樣式表）。
    ///
    /// 用法（面板）：Build 時建一個，之後用它取代 `root.style.display = Flex/None`：
    /// <code>
    ///     anim = UIAnim.Pop(root, panel, dim);      // 置中面板：淡入＋輕微放大，暗幕只淡入
    ///     anim = UIAnim.SlideRight(root, scroll);   // 靠右的捲軸：從右邊滑進來
    ///     anim = UIAnim.SlideUp(root, box);         // 畫面下方的對話框／托盤：從下面滑上來
    ///     anim.Show();   anim.Hide();   anim.IsOpen
    /// </code>
    /// 用法（HUD）：<c>UIAnim.Bump(元素)</c> 彈一下；可再帶一個短暫套上的 class（例如變色）。
    ///
    /// ── 為什麼要這樣包 ──────────────────────────────────────────
    /// ⚠️ 1. **「開著沒」改看 <see cref="IsOpen"/>，不要再看 `root.style.display`。**
    ///    關閉動畫要等淡出跑完才能把 display 設成 None，這段期間 display 還是 Flex；
    ///    拿它判斷的話 Esc、OnDestroy 解除 ModalOpen、SleepOverlay 等帳單⋯⋯全都會誤判成「還開著」。
    ///    <see cref="IsOpen"/> 在 Show()/Hide() 的**那一刻**就翻過去，動畫只是視覺殘影。
    ///
    /// ⚠️ 2. **進場要延兩個排程 tick 才加上 open class。** UI Toolkit 的 transition 是
    ///    「已解析的樣式變了」才會跑；元素剛從 display:none 變 flex 的同一輪還沒有
    ///    「前一個樣式」可以比，那一輪就加 class 會直接跳到終點、不播動畫。
    ///    排程（`schedule.Execute`）在每輪面板更新的最前面跑、樣式解析在後面，而且
    ///    排程回呼裡再排的東西一定落到**下一輪** —— 所以巢狀兩層保證「關閉狀態」先被
    ///    解析過一次，第二層加 class 時才有東西可以 transition。（UpdatePanel 用的
    ///    `StartingIn(16)` 是同一個意思，但依賴幀率與那一幀有多長，這裡用巢狀比較穩。）
    ///    沒用 `experimental.animation`：它是 experimental API，USS transition 可以在 .uss 裡調。
    ///
    /// ⚠️ 3. **快速連按（開→關→開）**：延後的動作（加 open class、收 display）都記在
    ///    <c>pending</c>，Show/Hide 一進來就先 Pause 掉；回呼裡再比對 <c>serial</c>，
    ///    上一次留下的排程就算漏網也不會作用 —— 不會出現「重開之後被前一次的延後隱藏關掉」。
    ///
    /// ⚠️ 4. **排程回呼只碰 VisualElement，不碰 MonoBehaviour。** 面板可能在換場景時被
    ///    Destroy（而且是延遲的）；UIDocument 一停用，根就離開面板，排程本來就不會再跑，
    ///    就算跑了也只是改一個沒人看得到的元素的樣式，不會摸到已銷毀的元件。
    ///
    /// 5. 關閉中的面板**不收點擊**：根上掛了 trickle-down 的攔截，非開啟狀態一律
    ///    StopPropagation（按鈕收不到 PointerDown 就不會觸發 click）。不用 SetEnabled(false)
    ///    —— 那會套上 `:disabled` 樣式（按鈕變半透明），淡出時看得到一閃。
    ///
    /// 6. 時間全走 UI Toolkit 的 transition 與 schedule（毫秒、真實時間），
    ///    不受 `Time.timeScale` 影響；沒有執行緒，WebGL 沒問題。
    /// </summary>
    public sealed class UIAnim
    {
        const string SheetPath = "ui/AnimStyle";
        /// <summary>整個面板的「開著」狀態掛在根上，子元素用後代選擇器吃。</summary>
        const string OpenClass = "uia--open";

        /// <summary>
        /// 關閉後幾毫秒才真的 display:none。要比 AnimStyle.uss 的關閉 transition（0.10s）長一點，
        /// 不然最後幾幀會被切掉。
        /// </summary>
        const long HideDelayMs = 140;

        /// <summary>Bump：放大那段的長度（毫秒）。⚠️ 跟 AnimStyle.uss 的 `.uia-bump--up` 同步。</summary>
        const long BumpUpMs = 70;
        /// <summary>Bump 帶的額外 class（例如金幣變色）停留多久才拿掉。</summary>
        const long FlashHoldMs = 260;

        static StyleSheet sheet;

        readonly VisualElement root;
        IVisualElementScheduledItem pending;
        int serial;
        /// <summary>open class 現在有沒有掛在根上（跟 IsOpen 不同步：進場會晚兩個 tick 才掛）。</summary>
        bool classOn;
        /// <summary>關閉的那一刻 class 掛著沒（同一幀又重開時，掛著才能直接掛回去不重播）。</summary>
        bool wasOnAtClose;
        int openedFrame = -1, closedFrame = -1;

        /// <summary>邏輯上的開關狀態 —— Show()/Hide() 當下就變，不等動畫。</summary>
        public bool IsOpen { get; private set; }

        /// <summary>這一幀剛打開。用同一顆鍵開關的面板，Update 裡要跳過這一幀（見 QuestPanel）。</summary>
        public bool OpenedThisFrame => openedFrame == Time.frameCount;

        /// <summary>這一幀剛關掉。用同一顆鍵開關的面板，Open 裡要擋掉這一幀的重開。</summary>
        public bool ClosedThisFrame => closedFrame == Time.frameCount;

        // ── 建立 ────────────────────────────────────────────────

        /// <summary>置中的面板：body 淡入＋從 0.94 放大到 1；backdrop（暗幕）只淡入淡出。</summary>
        public static UIAnim Pop(VisualElement root, VisualElement body, VisualElement backdrop = null) =>
            new UIAnim(root, body, "uia-pop", backdrop);

        /// <summary>靠右的面板（任務簿捲軸）：從右邊滑進來＋淡入。</summary>
        public static UIAnim SlideRight(VisualElement root, VisualElement body) =>
            new UIAnim(root, body, "uia-right", null);

        /// <summary>貼著畫面下緣的東西（對話框、佈置托盤）：從下面滑上來＋淡入。</summary>
        public static UIAnim SlideUp(VisualElement root, VisualElement body) =>
            new UIAnim(root, body, "uia-up", null);

        UIAnim(VisualElement root, VisualElement body, string bodyClass, VisualElement backdrop)
        {
            this.root = root;
            UseStyles(root);
            body?.AddToClassList(bodyClass);
            backdrop?.AddToClassList("uia-fade");

            // 關閉中（淡出那 0.1 秒）不收點擊 —— 見類別註解第 5 點
            // （PointerUp 不攔：關之前就按住的按鈕要收得到放開，才不會卡在「按著」的捕捉狀態）
            root.RegisterCallback<PointerDownEvent>(BlockWhenClosed, TrickleDown.TrickleDown);
            root.RegisterCallback<ClickEvent>(BlockWhenClosed, TrickleDown.TrickleDown);
        }

        void BlockWhenClosed(EventBase e)
        {
            if (!IsOpen) e.StopPropagation();
        }

        /// <summary>把共用的動效樣式表掛到這個元素所在的最上層（重複呼叫沒關係）。</summary>
        public static void UseStyles(VisualElement any)
        {
            if (any == null) return;
            var top = any;
            while (top.hierarchy.parent != null) top = top.hierarchy.parent;
            if (sheet == null) sheet = Resources.Load<StyleSheet>(SheetPath);
            if (sheet == null)
            {
                Debug.LogWarning("[UIAnim] 找不到 Resources/" + SheetPath + "，面板會照常開關但沒有動畫");
                return;
            }
            if (!top.styleSheets.Contains(sheet)) top.styleSheets.Add(sheet);
        }

        // ── 開關 ────────────────────────────────────────────────

        /// <summary>打開：IsOpen 立刻為真，視覺上淡入（見類別註解第 2 點）。</summary>
        public void Show()
        {
            if (root == null) return;
            bool reopenSameFrame = ClosedThisFrame && wasOnAtClose;
            IsOpen = true;
            openedFrame = Time.frameCount;
            Cancel();
            root.style.display = DisplayStyle.Flex;

            // 同一幀「關了又開」（例如對話選項：先關掉這段、馬上開下一段）——
            // 畫面上根本還沒開始淡出，直接把 class 掛回去，不要閃一下重播進場。
            if (reopenSameFrame) { root.AddToClassList(OpenClass); classOn = true; }
            if (classOn) return;

            int my = serial;
            pending = root.schedule.Execute(() =>
            {
                if (my != serial) return;
                // 第二層：落在下一輪面板更新，這時「關閉狀態」已經解析過一次了
                pending = root.schedule.Execute(() =>
                {
                    if (my != serial || !IsOpen) return;
                    root.AddToClassList(OpenClass);
                    classOn = true;
                });
            });
        }

        /// <summary>
        /// 關閉：IsOpen 立刻為假（呼叫端同一行就解除 ModalOpen），視覺上淡出，
        /// 跑完才 display:none。沒開著時呼叫不會怎樣。
        /// </summary>
        public void Hide()
        {
            if (root == null || !IsOpen) return;
            IsOpen = false;
            closedFrame = Time.frameCount;
            Cancel();
            wasOnAtClose = classOn;
            root.RemoveFromClassList(OpenClass);
            classOn = false;

            int my = serial;
            pending = root.schedule.Execute(() =>
            {
                if (my != serial || IsOpen) return;
                root.style.display = DisplayStyle.None;
            }).StartingIn(HideDelayMs);
        }

        /// <summary>作廢所有還沒跑的延後動作（見類別註解第 3 點）。</summary>
        void Cancel()
        {
            serial++;
            pending?.Pause();
            pending = null;
        }

        // ── HUD 小回饋 ──────────────────────────────────────────

        /// <summary>每個元素各自的 Bump 排程，連續彈時要能取消上一次（元素被丟掉時自動回收）。</summary>
        static readonly ConditionalWeakTable<VisualElement, BumpState> bumps = new();

        sealed class BumpState
        {
            public IVisualElementScheduledItem item;
            public IVisualElementScheduledItem flashOff;
            public string flash;
        }

        /// <summary>
        /// 彈一下：1 → 1.18 → 1，約 0.2 秒。剛建立的元素也可以（同樣延兩個 tick 才開始，理由見類別註解第 2 點）。
        /// <paramref name="flashClass"/>：同時短暫套上的 class（例如金幣增加時變綠），停一下再拿掉。
        /// ⚠️ 元素上別的 class 不要再設 transition-property —— 同一個屬性只會有一條規則勝出，
        ///    會把這裡的 scale 動畫蓋掉（要變色就把顏色寫在 flashClass 裡，`.uia-bump` 已經會 transition color）。
        /// </summary>
        public static void Bump(VisualElement el, string flashClass = null)
        {
            if (el == null) return;
            UseStyles(el);
            el.AddToClassList("uia-bump");

            var st = bumps.GetOrCreateValue(el);
            st.item?.Pause();
            st.flashOff?.Pause();
            if (st.flash != null && st.flash != flashClass) el.RemoveFromClassList(st.flash);
            st.flash = flashClass;

            st.item = el.schedule.Execute(() =>
            {
                st.item = el.schedule.Execute(() =>
                {
                    el.AddToClassList("uia-bump--up");
                    if (flashClass != null) el.AddToClassList(flashClass);
                    // 放大到頂就收回來（回程用 .uia-bump 的時間與緩動）
                    st.item = el.schedule.Execute(() => el.RemoveFromClassList("uia-bump--up"))
                                .StartingIn(BumpUpMs);
                    if (flashClass != null)
                        st.flashOff = el.schedule.Execute(() =>
                        {
                            el.RemoveFromClassList(flashClass);
                            if (st.flash == flashClass) st.flash = null;
                        }).StartingIn(FlashHoldMs);
                });
            });
        }
    }
}
