using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 後花園「搬花圃」模式（<see cref="GardenArrange"/>）底下那一條圖示提示 —— 只有圖、沒有句子
    /// （玩家說過「解釋的文字太多了」，見 ShopRoomTray 檔頭）：
    ///
    ///   [土壤磚] ┃ [滑鼠拖曳][移動] ┃ [綠格][勾] [紅格][叉] ([叉][原因]) ┃ [R][完成] [Esc][完成]
    ///
    /// 樣式整個借店裡佈置托盤的（.tray／.tray-head／.tray-hints／.hint-group，像素外觀在 Skin8.uss），
    /// 只是沒有下面那排托盤格，寬度改成跟著內容。
    /// 不吃滑鼠（PickingMode.Ignore）、不設 UIState.ModalOpen —— 這個模式本身要用滑鼠拖花圃。
    /// </summary>
    public class GardenArrangeHud : MonoBehaviour
    {
        public static GardenArrangeHud Instance { get; private set; }

        /// <summary>跟著場景走（後花園才有），不 DontDestroyOnLoad。</summary>
        public static GardenArrangeHud Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("GardenArrangeHudUI").AddComponent<GardenArrangeHud>();
        }

        const float IconH = 30f;

        UIDocument doc;
        VisualElement root, hintRow;
        bool built;
        UIAnim anim;
        readonly Dictionary<string, VisualElement> groups = new();
        VisualElement whyIcon;
        string whyName;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 15;
            if (doc.panelSettings == null)
                Debug.LogError("[GardenArrangeHud] 找不到 Resources/ui/UIPanelSettings");
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        public void Show()
        {
            if (!built) Build();
            if (!built) return;
            anim.Show();
            SetState(false, null);
        }

        public void Hide() => anim?.Hide();

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[GardenArrangeHud] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            UiSkin.Apply(root);
            root.pickingMode = PickingMode.Ignore;
            CjkFont.Apply(root);

            var layer = new VisualElement { pickingMode = PickingMode.Ignore };
            layer.AddToClassList("tray-layer");
            root.Add(layer);

            var tray = new VisualElement { pickingMode = PickingMode.Ignore };
            tray.AddToClassList("tray");
            tray.style.width = StyleKeyword.Auto;            // 店裡的托盤是 92% 寬；這裡只有一排圖示
            tray.style.maxWidth = StyleKeyword.None;
            layer.Add(tray);

            var head = new VisualElement { pickingMode = PickingMode.Ignore };
            head.AddToClassList("tray-head");
            head.style.marginBottom = 0;
            tray.Add(head);

            // 標題＝一塊土壤磚（「這是擺花圃的模式」）；沒圖時是同尺寸的空格，版面不會亂
            head.Add(UiIcons.Element(GameArt.Soil(false), 34f, "tray-title-icon"));

            hintRow = new VisualElement { pickingMode = PickingMode.Ignore };
            hintRow.AddToClassList("tray-hints");
            head.Add(hintRow);

            Group("drag", "mouse_drag", "act_move");
            Sep();
            Group("ok", "tile_green", "st_ok");
            Group("bad", "tile_red", "st_no");
            var why = Group("why", "st_no", "blk_overlap");
            whyIcon = why[1];
            whyName = "blk_overlap";
            groups["why"].AddToClassList("hint-group--bad");
            Sep();
            Group("done", "key_r", "act_done");
            Group("esc", "key_esc", "act_done");

            root.style.display = DisplayStyle.None;
            anim = UIAnim.SlideUp(root, tray);
            built = true;
        }

        List<VisualElement> Group(string key, params string[] icons)
        {
            var g = new VisualElement { pickingMode = PickingMode.Ignore };
            g.AddToClassList("hint-group");
            var list = new List<VisualElement>();
            foreach (var n in icons)
            {
                var el = UiIcons.Element(n, IconH, "hint-icon");
                g.Add(el);
                list.Add(el);
            }
            hintRow.Add(g);
            groups[key] = g;
            return list;
        }

        void Sep()
        {
            var s = new VisualElement { pickingMode = PickingMode.Ignore };
            s.AddToClassList("hint-sep");
            hintRow.Add(s);
        }

        /// <summary>
        /// 依狀態切換（只在狀態變的時候叫，不要每幀叫）。
        /// </summary>
        /// <param name="dragging">正在拖一塊花圃</param>
        /// <param name="why">放不下的原因圖示名（null＝放得下／沒在拖）</param>
        public void SetState(bool dragging, string why)
        {
            if (!built) return;
            Show("why", why != null);
            groups["ok"].EnableInClassList("hint-group--hot", dragging && why == null);
            groups["bad"].EnableInClassList("hint-group--hot", why != null);
            if (why != null && why != whyName) { whyName = why; UiIcons.Set(whyIcon, why, IconH); }
        }

        void Show(string key, bool on)
        {
            if (!groups.TryGetValue(key, out var g)) return;
            var want = on ? DisplayStyle.Flex : DisplayStyle.None;
            if (g.style.display != want) g.style.display = want;
        }
    }
}
