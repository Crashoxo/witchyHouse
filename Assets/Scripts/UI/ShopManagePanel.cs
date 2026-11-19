using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>
    /// 店內「經營商店」管理面板，兩個分頁：
    ///   上架定價 —— 一列一種東西，從背包/倉庫上架、撤下、調售價（受貨架上限）
    ///   升級     —— 花金幣升級招牌/背包/貨架/花圃/澆水壺
    ///
    /// 走到販售桌前按 E 開啟（見 SaleCounter）。
    ///
    /// ⚠️ 「可用數量」是**背包＋倉庫**（Storage.AvailableOf），不是只看背包 ——
    ///    材料一進城鎮就會自動歸位到倉庫，只看背包的話整排會空掉。
    /// </summary>
    public class ShopManagePanel : MonoBehaviour
    {
        public static ShopManagePanel Instance { get; private set; }

        public static ShopManagePanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("ShopManageUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<ShopManagePanel>();
        }

        enum Tab { Stock, Upgrade }

        /// <summary>上架頁最多顯示幾列。</summary>
        const int MaxStockRows = 14;

        UIDocument doc;
        VisualElement root, panel, tabsBox;
        ScrollView rowsBox;
        Label titleLabel, goldLabel, hintLabel;
        Tab tab = Tab.Stock;
        bool built;
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 12;
            if (doc.panelSettings == null)
                Debug.LogError("[ShopManagePanel] 找不到 Resources/ui/UIPanelSettings —— " +
                               "跑一次選單 Witch Shop → 建立 UI 設定檔");
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (anim != null && anim.IsOpen) UIState.ModalOpen = false;
        }

        void Update()
        {
            if (!built || root == null) return;
            if (anim.IsOpen && Input.GetKeyDown(KeyCode.Escape)) Close();
        }

        public void Open()
        {
            if (!built) Build();
            if (!built) return;
            anim.Show();                 // 淡入（邏輯上這一行就算開著，見 UIAnim）
            UIState.ModalOpen = true;
            Sfx.Play("ui-open");                                    // 音效：面板打開
            GameArt.OnReady(Refresh);
        }

        public void Close()
        {
            anim?.Hide();                // 淡出只是視覺殘影，邏輯上這一行就算關了
            UIState.ModalOpen = false;
            Sfx.Play("ui-close");                                   // 音效：面板關閉
        }

        public bool IsOpen => built && anim != null && anim.IsOpen;   // ⚠️ 不看 display：關閉動畫期間它還是 Flex

        // ──────────── 建構 ────────────

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null)
            {
                Debug.LogError("[ShopManagePanel] UIDocument 沒有 rootVisualElement");
                return;
            }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/ShopManageStyle"));
            CjkFont.Apply(root);
            Sfx.BindClicks(root);         // 所有按鈕的 click 音

            // 這個面板結構單純（沒有 UXML），直接在程式裡搭骨架 ——
            // 外觀仍然全部走 USS，沒有寫死的顏色或座標。
            var dim = new VisualElement();
            dim.AddToClassList("dim");
            root.Add(dim);

            panel = new VisualElement();
            panel.AddToClassList("panel");
            dim.Add(panel);

            var header = new VisualElement();
            header.AddToClassList("header");
            panel.Add(header);

            titleLabel = new Label("經營商店");
            titleLabel.AddToClassList("title");
            header.Add(titleLabel);

            var spacer = new VisualElement();
            spacer.AddToClassList("spacer");
            header.Add(spacer);

            goldLabel = new Label();
            goldLabel.AddToClassList("gold");
            header.Add(goldLabel);

            var close = new Button(Close) { text = "×" };
            close.AddToClassList("close");
            header.Add(close);

            tabsBox = new VisualElement();
            tabsBox.AddToClassList("tabs");
            panel.Add(tabsBox);
            AddTab("上架定價", Tab.Stock);
            AddTab("升級", Tab.Upgrade);

            rowsBox = new ScrollView();
            rowsBox.AddToClassList("rows");
            panel.Add(rowsBox);

            hintLabel = new Label();
            hintLabel.AddToClassList("hint");
            panel.Add(hintLabel);

            anim = UIAnim.Pop(root, panel, dim);              // 淡入＋輕微放大，暗幕只淡入
            built = true;
        }

        void AddTab(string label, Tab t)
        {
            var b = new Button(() => { tab = t; Sfx.Play("ui-tab"); Refresh(); }) { text = label };
            b.AddToClassList("tab");
            b.userData = t;
            tabsBox.Add(b);
        }

        // ──────────── 內容 ────────────

        void Refresh()
        {
            if (!built) return;

            goldLabel.text = $"{Wallet.Gold} 金";
            foreach (var b in tabsBox.Children()) b.EnableInClassList("active", (Tab)b.userData == tab);

            rowsBox.Clear();
            if (tab == Tab.Stock) BuildStock(); else BuildUpgrades();
        }

        /// <summary>目前可管理的品項：材料在前、藥水在後，只列「手上有的或已上架的」。</summary>
        List<string> StockItems()
        {
            var outList = new List<string>();
            var all = new List<string>(Items.Materials);
            foreach (var kv in Items.PotionItems) all.Add(kv.Key);
            foreach (var f in GardenData.Flowers) all.Add(f.Flower);
            foreach (var kv in Items.CandyItems) all.Add(kv.Key);

            foreach (var n in all)
            {
                // 「可用」＝背包＋倉庫。材料進城鎮會自動歸位到倉庫，只看背包會整排空掉。
                if (Storage.AvailableOf(n) > 0 || ShopStock.CountOf(n) > 0) outList.Add(n);
                if (outList.Count >= MaxStockRows) break;
            }
            return outList;
        }

        void BuildStock()
        {
            hintLabel.text = $"Esc 關閉 · 貨架上限 {ShopStock.Types}/{Upgrades.ShelfCap()} 種 · " +
                             "上架後顧客才會上門";

            var head = new VisualElement();
            head.AddToClassList("head-row");
            head.Add(HeadLabel("品項", "col-name"));
            head.Add(HeadLabel("可用", "col-bag"));
            head.Add(HeadLabel("架上", "col-shelf"));
            head.Add(HeadLabel("售價", "col-price"));
            rowsBox.Add(head);

            var items = StockItems();
            if (items.Count == 0)
            {
                var msg = new Label("背包裡沒有可上架的東西 —— 去森林採集或到藥水室調配吧");
                msg.AddToClassList("empty-msg");
                rowsBox.Add(msg);
                return;
            }
            foreach (var name in items) rowsBox.Add(StockRow(name));
        }

        static Label HeadLabel(string text, string cls)
        {
            var l = new Label(text);
            l.AddToClassList("head-label");
            l.AddToClassList(cls);
            return l;
        }

        VisualElement StockRow(string name)
        {
            int avail = Storage.AvailableOf(name);
            int shelf = ShopStock.CountOf(name);
            int price = shelf > 0 ? ShopStock.PriceOf(name) : ShopStock.SuggestedPrice(name);

            var row = new VisualElement();
            row.AddToClassList("row");

            row.Add(Col(name, "col-name", true));
            row.Add(Col(avail.ToString(), "col-bag", avail > 0));
            row.Add(Col(shelf.ToString(), "col-shelf", shelf > 0));

            var minus = new Button(() => { ShopStock.SetPrice(name, price - 1); Refresh(); }) { text = "－" };
            minus.AddToClassList("btn"); minus.AddToClassList("btn-step");
            minus.SetEnabled(shelf > 0);
            row.Add(minus);

            row.Add(Col($"{price}金", "col-price", true));

            var plus = new Button(() => { ShopStock.SetPrice(name, price + 1); Refresh(); }) { text = "＋" };
            plus.AddToClassList("btn"); plus.AddToClassList("btn-step");
            plus.SetEnabled(shelf > 0);
            row.Add(plus);

            bool canList = avail > 0 && ShopStock.CanAdd(name);
            var list = new Button(() =>
            {
                if (canList && Storage.TakeAny(name, 1)) { ShopStock.Add(name); Refresh(); }
            }) { text = "上架" };
            list.AddToClassList("btn"); list.AddToClassList("btn-list");
            list.SetEnabled(canList);
            row.Add(list);

            var pull = new Button(() =>
            {
                if (!ShopStock.RemoveOne(name)) return;
                // 背包種類滿了就退回倉庫，別讓撤下來的東西憑空不見
                if (!Inventory.Add(name, 1)) Storage.Add(name, 1);
                Refresh();
            }) { text = "撤下" };
            pull.AddToClassList("btn"); pull.AddToClassList("btn-pull");
            pull.SetEnabled(shelf > 0);
            row.Add(pull);

            return row;
        }

        static Label Col(string text, string cls, bool bright)
        {
            var l = new Label(text);
            l.AddToClassList(cls);
            if (!bright) l.AddToClassList("dimmed");
            return l;
        }

        // ──────────── 升級分頁 ────────────

        void BuildUpgrades()
        {
            hintLabel.text = "Esc 關閉 · 升級立即生效";

            foreach (var t in Upgrades.Tracks())
            {
                var d = Upgrades.Def(t);
                var row = new VisualElement();
                row.AddToClassList("row");

                var nameLabel = new Label($"{d.Name} Lv.{Upgrades.Level(t)}");
                nameLabel.AddToClassList("up-name");
                row.Add(nameLabel);

                var desc = new Label(d.Desc);
                desc.AddToClassList("up-desc");
                row.Add(desc);

                bool max = Upgrades.IsMax(t);
                var effect = new Label(max
                    ? Upgrades.EffectNow(t)
                    : $"{Upgrades.EffectNow(t)} → {Upgrades.EffectNext(t)}");
                effect.AddToClassList("up-effect");
                row.Add(effect);

                int cost = Upgrades.Cost(t);
                var costLabel = new Label(max ? "已滿級" : $"{cost} 金");
                costLabel.AddToClassList("up-cost");
                row.Add(costLabel);

                var buy = new Button(() =>
                {
                    if (Upgrades.Buy(t)) { Sfx.Play("upgrade"); Refresh(); }
                    else Sfx.Play("deny");                  // 錢不夠或已滿級（按鈕通常已經灰掉，保險）
                }) { text = "升級" };
                buy.AddToClassList("btn"); buy.AddToClassList("btn-buy");
                buy.SetEnabled(!max && Wallet.Gold >= cost);
                row.Add(buy);

                rowsBox.Add(row);
            }
        }
    }
}
