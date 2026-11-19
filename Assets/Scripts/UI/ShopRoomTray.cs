using System;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>
    /// 佈置模式底下那條托盤：列出「買了但還沒擺出來」的家具、貨架與裝飾，
    /// 點一下就放進房間。
    ///
    /// ⚠️ 沒有這個托盤的話，在花店買的東西會卡在「擁有」清單裡永遠拿不出來 ——
    ///    佈置模式只能搬動已經擺出來的東西。這是進入房間的唯一入口。
    ///
    /// 托盤刻意**不擋滑鼠以外的操作**：它是 UI Toolkit 的一層，但不設 UIState.ModalOpen，
    /// 因為佈置模式本身還要能用滑鼠拖房間裡的家具。
    /// </summary>
    public class ShopRoomTray : MonoBehaviour
    {
        public static ShopRoomTray Instance { get; private set; }

        public static ShopRoomTray Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("ShopRoomTrayUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<ShopRoomTray>();
        }

        UIDocument doc;
        VisualElement root, itemsBox;
        Label hintLabel;
        bool built;
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）

        /// <summary>點了托盤裡的東西要做什麼（由 ShopRoomEditor 指派）。</summary>
        public Action<string, bool> onPick;   // (id, isDecor)

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 15;
            if (doc.panelSettings == null)
                Debug.LogError("[ShopRoomTray] 找不到 Resources/ui/UIPanelSettings");
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        public void Show()
        {
            if (!built) Build();
            if (!built) return;
            anim.Show();                 // 淡入（邏輯上這一行就算開著，見 UIAnim）
            Refresh();
        }

        public void Hide()
        {
            anim?.Hide();                // 淡出只是視覺殘影，邏輯上這一行就算關了
        }

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[ShopRoomTray] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            root.pickingMode = PickingMode.Ignore;   // 只有托盤本身吃滑鼠，其他地方要能拖家具
            CjkFont.Apply(root);
            Sfx.BindClicks(root);         // 托盤按鈕的 click 音（放得下時會被 place 蓋過）

            var layer = new VisualElement();
            layer.AddToClassList("tray-layer");
            layer.pickingMode = PickingMode.Ignore;
            root.Add(layer);

            var tray = new VisualElement();
            tray.AddToClassList("tray");
            layer.Add(tray);

            var head = new VisualElement();
            head.AddToClassList("tray-head");
            tray.Add(head);

            var title = new Label("佈置模式");
            title.AddToClassList("tray-title");
            head.Add(title);

            hintLabel = new Label();
            hintLabel.AddToClassList("tray-hint");
            head.Add(hintLabel);

            itemsBox = new VisualElement();
            itemsBox.AddToClassList("tray-items");
            tray.Add(itemsBox);

            root.style.display = DisplayStyle.None;
            anim = UIAnim.SlideUp(root, tray);                // 從下方滑上來
            built = true;
        }

        /// <summary>提示文字由 ShopRoomEditor 依「有沒有選中東西」即時換。</summary>
        public void SetHint(string text)
        {
            if (built && hintLabel != null) hintLabel.text = text;
        }

        public void Refresh()
        {
            if (!built) return;

            itemsBox.Clear();
            int n = 0;

            // 家具與貨架（吃格盤）
            foreach (var f in Furniture.All)
            {
                int left = RoomLayout.Unplaced(f.Id);
                if (left <= 0) continue;
                n++;
                itemsBox.Add(Item(f.Id, f.Name, left, GameArt.FurnitureArt(f.Id), false));
            }

            // 裝飾（自由座標）
            foreach (var d in Decor.Catalog)
            {
                int left = DecorCatalog.UnplacedCount(d.Id);
                if (left <= 0) continue;
                n++;
                itemsBox.Add(Item(d.Id, d.Name, left, GameArt.Decoration(d.Id), true));
            }

            if (n == 0)
            {
                var msg = new Label("托盤是空的 —— 去城鎮的花店買家具、貨架或裝飾，買了才擺得出來");
                msg.AddToClassList("tray-empty");
                itemsBox.Add(msg);
            }
        }

        VisualElement Item(string id, string name, int count, Sprite sp, bool isDecor)
        {
            var b = new Button(() => onPick?.Invoke(id, isDecor));
            b.AddToClassList("tray-item");

            var icon = new VisualElement();
            icon.AddToClassList("tray-icon");
            if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
            b.Add(icon);

            var l = new Label(count > 1 ? $"{name} ×{count}" : name);
            l.AddToClassList("tray-name");
            b.Add(l);

            return b;
        }
    }
}
