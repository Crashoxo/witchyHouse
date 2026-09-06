using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>
    /// 更新公告板：開遊戲時從畫面上方滑下來停在正中央，列出這次更新了什麼。
    /// 底圖是 `Resources/ui/update-frame`（木框＋UPDATE 招牌＋**畫好的 OK 鈕**），
    /// 所以 OK 只要在畫上去的按鈕位置疊一個透明的可點區即可。
    ///
    /// **一次執行只跳一次**（靜態 <c>shown</c>）—— 換場景不會再跳出來煩人。
    /// 公告內容在 <see cref="UpdateNotes"/>，這裡只負責版面。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// 1. Cocos 版為了底圖有一整套非同步流程：先畫素框＋「載入中…」，再單獨 load
    ///    這一張（不能等 GameArt.onReady，那要等上百張圖），還要在回呼裡確認元件
    ///    還活著。Unity 這邊 <c>Resources.Load</c> 是同步的（見 PORTING.md 第三節），
    ///    <c>GameArt.Preload()</c> 回來時圖就在了 —— 那整套流程直接消失。
    ///    只留一條退路：真的載不到就套 `.update-panel--bare`（素框），不開天窗。
    ///
    /// 2. 版面從「照底圖比例硬算每個子節點的座標」改成 **USS 的百分比絕對定位** ——
    ///    內裡與 OK 鈕的位置本來就是量出來的比例（<c>INNER</c> / <c>OK_BTN</c>），
    ///    UI Toolkit 直接吃 `left: 9.9%` 這種寫法，那些換算全部不用寫。
    ///    只剩字級要跟著面板高度縮，那個在 <see cref="OnGeometry"/> 裡設。
    ///
    /// 3. 滑入/滑出從 <c>tween</c> 改成 USS transition（`translate` ＋ `ease-out-back`），
    ///    關閉時換成 `.update-panel--closing` 改成 `ease-in-back`。
    ///
    /// ⚠️ sortingOrder = 60：要蓋在所有面板（≤20）與 Toast（50）之上，
    ///    但低於睡覺黑幕（90）與換場黑幕（100）—— 開場的淡入還是該蓋過公告板。
    /// </summary>
    public class UpdatePanel : MonoBehaviour
    {
        public static UpdatePanel Instance { get; private set; }

        /// <summary>這次執行跳過了沒（換場景不重跳）。</summary>
        static bool shown;

        /// <summary>開遊戲時叫一次；第二次以後直接回來。</summary>
        public static void ShowOnce()
        {
            if (shown || Instance != null) return;
            shown = true;
            if (UpdateNotes.Lines == null || UpdateNotes.Lines.Length == 0) return;
            var go = new GameObject("UpdateUI");
            DontDestroyOnLoad(go);
            go.AddComponent<UpdatePanel>();
        }

        /// <summary>底圖的長寬比（update-frame.png 是 1031×647）。</summary>
        const float ArtAspect = 1031f / 647f;
        /// <summary>面板最寬幾 px（再寬字會顯得太小）。</summary>
        const float MaxWidth = 760f;
        /// <summary>面板佔畫面寬的比例。</summary>
        const float WidthRatio = 0.88f;
        /// <summary>滑入動畫跑完之前先擋著按鍵，免得剛開遊戲的手殘一下就關掉。</summary>
        const float InputGuard = 0.5f;
        /// <summary>底圖上「米色內裡」的上下緣（佔底圖高的比例，量出來的）。
        /// ⚠️ 跟 HudExtraStyle.uss 的 `.update-inner` 是同一組數字，改要一起改。</summary>
        const float InnerTopEdge = 0.284f, InnerBottomEdge = 0.839f;

        UIDocument doc;
        VisualElement root, panel, inner;
        Label dateLabel, bodyLabel;
        float openedAt;
        bool closing;
        bool ownedModal;   // ModalOpen 是不是我開的（別把別人的關掉）

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 60;
            if (doc.panelSettings == null)
            {
                Debug.LogError("[UpdatePanel] 找不到 Resources/ui/UIPanelSettings");
                return;
            }
            GameArt.Preload();
            Build();
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (ownedModal) UIState.ModalOpen = false;
        }

        // ── 版面 ────────────────────────────────────────────────

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[UpdatePanel] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            CjkFont.Apply(root);

            ownedModal = !UIState.ModalOpen;
            if (ownedModal) UIState.ModalOpen = true;
            openedAt = Time.unscaledTime;

            // 半透明背板：擋住世界的點擊（PlayerController 是看 UIState.ModalOpen）
            var layer = new VisualElement();
            layer.AddToClassList("update-layer");
            root.Add(layer);

            panel = new VisualElement();
            panel.AddToClassList("update-panel");
            var art = GameArt.UpdateFrame;
            if (art != null) panel.style.backgroundImage = new StyleBackground(art);
            else panel.AddToClassList("update-panel--bare");   // 沒圖也要有個框，別開天窗
            layer.Add(panel);

            inner = new VisualElement();
            inner.AddToClassList("update-inner");
            panel.Add(inner);

            dateLabel = new Label(UpdateNotes.Date);
            dateLabel.AddToClassList("update-date");
            inner.Add(dateLabel);

            bodyLabel = new Label(string.Join("\n", UpdateNotes.Lines));
            bodyLabel.AddToClassList("update-body");
            inner.Add(bodyLabel);

            // OK：底圖已經畫好按鈕，這裡只疊一個透明可點區
            var ok = new VisualElement();
            ok.AddToClassList("update-ok");
            ok.RegisterCallback<PointerDownEvent>(_ => panel.AddToClassList("update-panel--press"));
            ok.RegisterCallback<PointerUpEvent>(_ =>
            {
                panel.RemoveFromClassList("update-panel--press");
                Close();
            });
            ok.RegisterCallback<PointerLeaveEvent>(_ => panel.RemoveFromClassList("update-panel--press"));
            panel.Add(ok);

            // 面板大小要跟著畫面走（底圖等比），字級再跟著面板高度縮
            layer.RegisterCallback<GeometryChangedEvent>(OnGeometry);

            // 從上方滑進來：先推到畫面外，下一幀再回到 0 讓 transition 跑起來
            panel.style.translate = new StyleTranslate(new Translate(0, Length.Percent(-160f)));
            panel.schedule.Execute(() =>
                panel.style.translate = new StyleTranslate(new Translate(0, Length.Percent(0f))))
                 .StartingIn(16);
        }

        /// <summary>畫面大小變了就重算面板尺寸與字級（底圖等比，字跟著面板高度）。</summary>
        void OnGeometry(GeometryChangedEvent e)
        {
            float avail = e.newRect.width;
            if (avail <= 0f) return;

            float w = Mathf.Min(avail * WidthRatio, MaxWidth);
            float h = w / ArtAspect;
            panel.style.width = w;
            panel.style.height = h;

            dateLabel.style.fontSize = Mathf.Round(h * 0.062f);

            // 行高依行數自動收斂，條目多的時候才不會壓到底下的裝飾線與 OK 鈕。
            // ⚠️ 內裡高度用**比例**算，不要讀 inner.resolvedStyle —— 這一輪 layout 還沒跑完，
            //    讀到的是上一次的值（第一次是 0），字級會忽大忽小。
            float bodyH = h * (InnerBottomEdge - InnerTopEdge) - h * 0.11f;
            float lineH = Mathf.Min(h * 0.088f, bodyH / Mathf.Max(1, UpdateNotes.Lines.Length));
            bodyLabel.style.fontSize = Mathf.Round(Mathf.Min(h * 0.052f, lineH * 0.62f));
            bodyLabel.style.height = StyleKeyword.Auto;
            bodyLabel.style.marginTop = Mathf.Round(h * 0.02f);
        }

        // ── 關閉 ────────────────────────────────────────────────

        void Update()
        {
            if (closing || root == null) return;
            if (Time.unscaledTime - openedAt < InputGuard) return;
            if (Input.GetKeyDown(KeyCode.Escape) || Input.GetKeyDown(KeyCode.Return)
                || Input.GetKeyDown(KeyCode.KeypadEnter) || Input.GetKeyDown(KeyCode.Space)
                || Input.GetKeyDown(KeyCode.E))
                Close();
        }

        /// <summary>往上滑回去，動畫跑完才銷毀。</summary>
        public void Close()
        {
            if (closing) return;
            closing = true;
            if (ownedModal) UIState.ModalOpen = false;
            ownedModal = false;

            panel.RemoveFromClassList("update-panel--press");
            panel.AddToClassList("update-panel--closing");
            panel.style.translate = new StyleTranslate(new Translate(0, Length.Percent(-160f)));
            root.AddToClassList("update-root--closing");   // 背板一起淡掉

            // ⚠️ 不能直接 Destroy —— 要等滑出去的 transition 跑完，
            //    而且 UIDocument 被銷毀時面板會整個瞬間消失。
            panel.schedule.Execute(() => { if (this != null) Destroy(gameObject); })
                 .StartingIn(400);
        }
    }
}
