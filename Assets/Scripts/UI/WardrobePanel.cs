using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 衣櫃面板：列出所有造型，點一下就換上。走到藥水室左邊那座雕花木櫃前按 E 開啟。
    ///
    /// 造型立繪在 Resources/portraits/outfit8-*.png（載入在 GameArt 的 brew 組裡，
    /// 因為只有這個房間的衣櫃會用到）。
    /// </summary>
    public class WardrobePanel : MonoBehaviour
    {
        public static WardrobePanel Instance { get; private set; }

        public static WardrobePanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("WardrobeUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<WardrobePanel>();
        }

        UIDocument doc;
        VisualElement root;
        ScrollView rowsBox;
        bool built;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 12;
            if (doc.panelSettings == null)
                Debug.LogError("[WardrobePanel] 找不到 Resources/ui/UIPanelSettings");
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (root != null && root.style.display == DisplayStyle.Flex) UIState.ModalOpen = false;
        }

        void Update()
        {
            if (!built || root == null) return;
            if (root.style.display == DisplayStyle.Flex && Input.GetKeyDown(KeyCode.Escape)) Close();
        }

        public void Open()
        {
            if (!built) Build();
            if (!built) return;
            root.style.display = DisplayStyle.Flex;
            UIState.ModalOpen = true;
            GameArt.OnReady(Refresh);
        }

        public void Close()
        {
            if (root != null) root.style.display = DisplayStyle.None;
            UIState.ModalOpen = false;
        }

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[WardrobePanel] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/ShopManageStyle"));
            CjkFont.Apply(root);

            var dim = new VisualElement();
            dim.AddToClassList("dim");
            root.Add(dim);

            var panel = new VisualElement();
            panel.AddToClassList("panel");
            panel.style.width = 560;
            dim.Add(panel);

            var header = new VisualElement();
            header.AddToClassList("header");
            panel.Add(header);

            var title = new Label("衣櫃");
            title.AddToClassList("title");
            header.Add(title);

            var spacer = new VisualElement();
            spacer.AddToClassList("spacer");
            header.Add(spacer);

            var close = new Button(Close) { text = "×" };
            close.AddToClassList("close");
            header.Add(close);

            rowsBox = new ScrollView();
            rowsBox.AddToClassList("rows");
            rowsBox.style.minHeight = 200;
            panel.Add(rowsBox);

            var hint = new Label("Esc 關閉 · 換上之後所有動作的圖都會跟著換");
            hint.AddToClassList("hint");
            panel.Add(hint);

            built = true;
        }

        void Refresh()
        {
            rowsBox.Clear();
            string cur = Outfits.CurrentId();

            foreach (var o in Outfits.All())
            {
                var def = o;                       // 迴圈變數要抓進閉包
                var row = new VisualElement();
                row.AddToClassList("row");
                row.style.height = 64;

                // 立繪（沒有的話留白）
                var icon = new VisualElement();
                icon.style.width = 44; icon.style.height = 52; icon.style.marginRight = 10;
                var sp = string.IsNullOrEmpty(def.Portrait) ? null : GameArt.Portrait(def.Portrait);
                if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
                row.Add(icon);

                var name = new Label(def.Name);
                name.AddToClassList("col-name");
                name.style.width = 110;
                row.Add(name);

                var desc = new Label(def.Desc);
                desc.AddToClassList("up-desc");
                row.Add(desc);

                bool wearing = def.Id == cur;
                var pick = new Button(() => { Outfits.Set(def.Id); Refresh(); })
                { text = wearing ? "穿著中" : "換上" };
                pick.AddToClassList("btn");
                pick.AddToClassList(wearing ? "btn-buy" : "btn-list");
                pick.SetEnabled(!wearing);
                row.Add(pick);

                rowsBox.Add(row);
            }
        }
    }
}
