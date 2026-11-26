using System.Collections;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 第一次進店時跳一次的「佈置圖解卡」—— 幾格連環圖，純圖示＋鍵帽，不寫句子：
    ///
    ///   ① [左鍵][關店招牌] → ② [R][木槌] → ③ [拖曳][貨架] → ④ [拖曳][商品] → ⑤ [R][完成] [左鍵][開店招牌]
    ///
    /// ①⑤ 的「左鍵＋招牌」＝點上方工具列的開關店鈕（UI/CornerHud；以前是走到門口招牌按 E，已經拿掉）。
    ///
    /// 為什麼：以前是一則 5 秒的長句 Toast（「小提示：按 R 進入佈置模式 —— …」），
    /// 玩家回饋「解釋的文字太多了」，又加了「關店才能佈置」—— 流程變長，用圖講比較清楚。
    ///
    /// 點一下或按任意鍵關閉。開著時設 UIState.ModalOpen（角色不走、R 不會順便進佈置模式）；
    /// ⚠️ 關掉時 ModalOpen **延一幀**才放開：同一幀裡 ShopRoomEditor.Update 可能排在後面，
    ///    當場放開的話「按 R 關卡片」會直接進佈置模式（開店中還會多跳一個「不能佈置」）。
    /// ⚠️ 只有自己設的 ModalOpen 才自己放開 —— 開卡片時別的面板已經開著的話就不動它。
    /// </summary>
    public class ShopEditIntroCard : MonoBehaviour
    {
        static ShopEditIntroCard instance;

        /// <summary>跳出圖解卡（已經開著就不重開）。</summary>
        public static void Show()
        {
            if (instance != null) return;
            var go = new GameObject("ShopEditIntroCardUI");
            instance = go.AddComponent<ShopEditIntroCard>();
        }

        const float IconH = 40f;

        UIDocument doc;
        bool ownsModal;
        bool closing;
        float openedAt;

        void Awake()
        {
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 45;            // 面板之上、Toast（50）之下
            if (doc.panelSettings == null)
            {
                Debug.LogError("[ShopEditIntroCard] 找不到 Resources/ui/UIPanelSettings");
                Destroy(gameObject);
                return;
            }
            Build();
            if (!UIState.ModalOpen) { UIState.ModalOpen = true; ownsModal = true; }
            openedAt = Time.unscaledTime;
            Sfx.Play("ui-open");
        }

        void OnDestroy()
        {
            if (instance == this) instance = null;
            if (ownsModal) UIState.ModalOpen = false;     // 場景切走等意外收掉時也要放開
        }

        void Build()
        {
            var root = doc.rootVisualElement;
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            CjkFont.Apply(root);

            var layer = new VisualElement();
            layer.AddToClassList("intro-layer");
            root.Add(layer);

            var card = new VisualElement();
            card.AddToClassList("intro-card");
            card.AddToClassList("uia-pop");
            layer.Add(card);

            var shelf = GameArt.FurnitureArt("shelf_plank");
            var good = GameArt.Item("清涼藥水");

            Step(card, 1, Icon("mouse_left"), Icon("shop_closed"));      // 點工具列的招牌 → 關店
            Arrow(card);
            Step(card, 2, Icon("key_r"), Icon("act_edit"));
            Arrow(card);
            Step(card, 3, Icon("mouse_drag"), shelf != null ? UiIcons.Element(shelf, IconH, "intro-icon") : Icon("act_move"));
            Arrow(card);
            Step(card, 4, Icon("mouse_drag"), good != null ? UiIcons.Element(good, IconH, "intro-icon") : Icon("ring_green"));
            Arrow(card);
            Step(card, 5, Icon("key_r"), Icon("act_done"), Icon("mouse_left"), Icon("shop_open"));

            UIAnim.UseStyles(card);
            // 下一個 tick 才掛 open class，pop 進場才播得出來（見 UIAnim 類別註解）
            root.schedule.Execute(() => root.AddToClassList("uia--open")).StartingIn(30);
        }

        static VisualElement Icon(string name) => UiIcons.Element(name, IconH, "intro-icon");

        /// <summary>一格：上面一個小編號，下面一排圖示（四個以上就排兩列）。</summary>
        static void Step(VisualElement card, int n, params VisualElement[] icons)
        {
            var step = new VisualElement();
            step.AddToClassList("intro-step");
            var num = new Label(n.ToString());
            num.AddToClassList("intro-num");
            step.Add(num);
            VisualElement row = null;
            for (int i = 0; i < icons.Length; i++)
            {
                if (i % 2 == 0)
                {
                    row = new VisualElement();
                    row.AddToClassList("intro-row");
                    step.Add(row);
                }
                row.Add(icons[i]);
            }
            card.Add(step);
        }

        static void Arrow(VisualElement card) => card.Add(UiIcons.Element("arrow", 28f, "intro-arrow"));

        void Update()
        {
            if (closing) return;
            // 剛跳出來的那一下不算（避免玩家正在按的鍵直接把它關掉）
            if (Time.unscaledTime - openedAt < 0.4f) return;
            if (Input.anyKeyDown) StartCoroutine(Close());
        }

        IEnumerator Close()
        {
            closing = true;
            Sfx.Play("ui-close");
            doc.rootVisualElement.style.display = DisplayStyle.None;
            yield return null;                          // 延一幀才放開 ModalOpen（理由見類別註解）
            if (ownsModal) { UIState.ModalOpen = false; ownsModal = false; }
            Destroy(gameObject);
        }
    }
}
