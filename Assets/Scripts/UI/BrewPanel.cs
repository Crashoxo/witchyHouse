using System.Text;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>
    /// 調配藥水面板：列出所有配方 —— 成品圖示、名稱、需要的材料、售價、熬煮時間，
    /// 材料夠的才按得下去。走到鍋爐前按 E 開啟。
    ///
    /// ⚠️ 材料算的是**背包＋倉庫**（PotionRecipes 走 Storage.AvailableOf）——
    ///    倉庫就在同一個房間的木箱裡，只看背包的話回到鍋爐前會什麼都做不了。
    /// </summary>
    public class BrewPanel : MonoBehaviour
    {
        public static BrewPanel Instance { get; private set; }

        public static BrewPanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("BrewUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<BrewPanel>();
        }

        UIDocument doc;
        VisualElement root;
        ScrollView rowsBox;
        Label hintLabel;
        BrewCauldron cauldron;
        bool built;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 12;
            if (doc.panelSettings == null)
                Debug.LogError("[BrewPanel] 找不到 Resources/ui/UIPanelSettings");
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

        public void Open(BrewCauldron c)
        {
            cauldron = c;
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
            if (root == null) { Debug.LogError("[BrewPanel] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/ShopManageStyle"));
            CjkFont.Apply(root);

            var dim = new VisualElement();
            dim.AddToClassList("dim");
            root.Add(dim);

            var panel = new VisualElement();
            panel.AddToClassList("panel");
            dim.Add(panel);

            var header = new VisualElement();
            header.AddToClassList("header");
            panel.Add(header);

            var title = new Label("調配藥水");
            title.AddToClassList("title");
            header.Add(title);

            var spacer = new VisualElement();
            spacer.AddToClassList("spacer");
            header.Add(spacer);

            var close = new Button(Close) { text = "✕" };
            close.AddToClassList("close");
            header.Add(close);

            rowsBox = new ScrollView();
            rowsBox.AddToClassList("rows");
            panel.Add(rowsBox);

            hintLabel = new Label("Esc 關閉 · 材料算背包＋房間裡的倉庫");
            hintLabel.AddToClassList("hint");
            panel.Add(hintLabel);

            built = true;
        }

        void Refresh()
        {
            if (!built) return;
            rowsBox.Clear();

            foreach (var r in Recipes.All)
            {
                var row = new VisualElement();
                row.AddToClassList("row");
                row.style.height = 52;

                var icon = new VisualElement();
                icon.style.width = 34; icon.style.height = 34; icon.style.marginRight = 8;
                var sp = GameArt.Item(r.Name);
                if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
                row.Add(icon);

                var name = new Label(r.Name);
                name.AddToClassList("col-name");
                name.style.width = 110;
                row.Add(name);

                var inputs = new Label(InputsText(r));
                inputs.AddToClassList("up-desc");
                row.Add(inputs);

                var price = new Label($"{r.SellPrice} 金");
                price.AddToClassList("col-price");
                row.Add(price);

                int max = PotionRecipes.MaxCraftable(r);

                var one = new Button(() => Brew(r, 1)) { text = "熬 1" };
                one.AddToClassList("btn"); one.AddToClassList("btn-list");
                one.SetEnabled(max >= 1);
                row.Add(one);

                var all = new Button(() => Brew(r, max)) { text = max > 0 ? $"熬 {max}" : "熬最大" };
                all.AddToClassList("btn"); all.AddToClassList("btn-buy");
                all.SetEnabled(max >= 1);
                row.Add(all);

                rowsBox.Add(row);
            }
        }

        /// <summary>「藍莓×2　藥草×1」這種材料清單，數量不足的標成紅字。</summary>
        static string InputsText(Recipe r)
        {
            var sb = new StringBuilder();
            foreach (var kv in r.Inputs)
            {
                if (sb.Length > 0) sb.Append("　");
                int have = Storage.AvailableOf(kv.Key);
                sb.Append($"{kv.Key}×{kv.Value}");
                if (have < kv.Value) sb.Append($"（有 {have}）");
            }
            return sb.ToString();
        }

        void Brew(Recipe r, int qty)
        {
            if (cauldron == null || qty <= 0) return;
            cauldron.StartBrew(r, qty);
            Close();          // 關掉面板才看得到鍋爐在冒泡
        }
    }
}
