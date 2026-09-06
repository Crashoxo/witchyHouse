using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>
    /// 城鎮商店面板的共用骨架 —— 標題列、金幣、清單、提示、關閉。
    /// 雜貨鋪（賣材料換錢）與花店（買種子和裝飾）都從這裡長出來，
    /// 差別只在 Refresh() 填什麼列。
    /// </summary>
    public abstract class TownShopPanel : MonoBehaviour
    {
        protected UIDocument doc;
        protected VisualElement root;
        protected ScrollView rowsBox;
        protected Label titleLabel, goldLabel, hintLabel;
        protected VisualElement tabsBox;
        bool built;

        protected abstract string Title { get; }
        protected abstract string Hint { get; }
        protected abstract void Refresh();

        /// <summary>要不要分頁列（花店有「種子／裝飾」兩頁，雜貨鋪沒有）。</summary>
        protected virtual bool UseTabs => false;

        protected void Init(int sortingOrder)
        {
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = sortingOrder;
            if (doc.panelSettings == null)
                Debug.LogError($"[{GetType().Name}] 找不到 Resources/ui/UIPanelSettings");
        }

        protected void Update()
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
            GameArt.OnReady(RefreshAll);
        }

        public void Close()
        {
            if (root != null) root.style.display = DisplayStyle.None;
            UIState.ModalOpen = false;
        }

        protected void RefreshAll()
        {
            if (!built) return;
            goldLabel.text = $"{Wallet.Gold} 金";
            hintLabel.text = Hint;
            Refresh();
        }

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError($"[{GetType().Name}] 沒有 rootVisualElement"); return; }
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

            titleLabel = new Label(Title);
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

            if (UseTabs)
            {
                tabsBox = new VisualElement();
                tabsBox.AddToClassList("tabs");
                panel.Add(tabsBox);
            }

            rowsBox = new ScrollView();
            rowsBox.AddToClassList("rows");
            panel.Add(rowsBox);

            hintLabel = new Label();
            hintLabel.AddToClassList("hint");
            panel.Add(hintLabel);

            root.style.display = DisplayStyle.None;
            built = true;
        }

        // ── 給子類用的小工具 ────────────────────────────────────

        protected static VisualElement Icon(Sprite sp, float size = 34f)
        {
            var el = new VisualElement();
            el.style.width = size; el.style.height = size; el.style.marginRight = 8;
            if (sp != null) el.style.backgroundImage = new StyleBackground(sp);
            return el;
        }

        protected static Label Col(string text, string cls, float width = 0f)
        {
            var l = new Label(text);
            l.AddToClassList(cls);
            if (width > 0f) l.style.width = width;
            return l;
        }

        protected static Button Act(string text, string extraClass, bool enabled, System.Action onClick)
        {
            var b = new Button(onClick) { text = text };
            b.AddToClassList("btn");
            if (!string.IsNullOrEmpty(extraClass)) b.AddToClassList(extraClass);
            b.SetEnabled(enabled);
            return b;
        }
    }

    /// <summary>
    /// 雜貨鋪 · 收購：把背包／倉庫裡的材料賣掉換金幣。
    ///
    /// ⚠️ 收購價（Prices.DefaultBuy）**比你自己店裡賣給顧客的價錢低**（Prices.BasePrice）——
    ///    這是刻意的：想賺得多就得自己開店做生意，雜貨鋪只是「懶得經營時的保底出路」。
    /// </summary>
    public class GeneralStorePanel : TownShopPanel
    {
        public static GeneralStorePanel Instance { get; private set; }

        public static GeneralStorePanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("GeneralStoreUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<GeneralStorePanel>();
        }

        void Awake() { Instance = this; Init(12); }
        void OnDestroy() { if (Instance == this) Instance = null; }

        protected override string Title => "雜貨鋪 · 收購";
        protected override string Hint => "Esc 關閉 · 收購價比你自己店裡賣得低，想賺多還是要自己做生意";

        protected override void Refresh()
        {
            rowsBox.Clear();

            var head = new VisualElement();
            head.AddToClassList("head-row");
            head.Add(Col("品項", "head-label col-name"));
            head.Add(Col("持有", "head-label col-bag"));
            head.Add(Col("單價", "head-label col-price"));
            rowsBox.Add(head);

            bool any = false;
            foreach (var e in Prices.DefaultBuy)
            {
                int have = Storage.AvailableOf(e.Name);
                if (have <= 0) continue;
                any = true;
                string name = e.Name;
                int price = e.Price;

                var row = new VisualElement();
                row.AddToClassList("row");
                row.Add(Icon(GameArt.Item(name)));
                row.Add(Col(name, "col-name", 120f));
                row.Add(Col(have.ToString(), "col-bag"));
                row.Add(Col($"{price} 金", "col-price"));

                row.Add(Act("賣 1", "btn-list", true, () => Sell(name, price, 1)));
                row.Add(Act($"賣全部（{have * price} 金）", "btn-buy", true,
                            () => Sell(name, price, have)));
                rowsBox.Add(row);
            }

            if (!any)
            {
                var msg = new Label("背包和倉庫裡沒有雜貨鋪收的東西 —— 去森林採點材料吧");
                msg.AddToClassList("empty-msg");
                rowsBox.Add(msg);
            }
        }

        void Sell(string name, int price, int qty)
        {
            if (qty <= 0) return;
            if (!Storage.TakeAny(name, qty)) return;      // 先扣背包、不夠再扣倉庫
            int gold = price * qty;
            Wallet.Add(gold);
            DailyLog.RecordTrade(gold);                   // 收購收入不算店裡的生意，不加名聲
            Toast.Show($"賣出 {name} ×{qty}　＋{gold} 金");
            RefreshAll();
        }
    }

    /// <summary>
    /// 花店：買花的種子與店內裝飾。
    ///   種子 → 進背包，拿去後花園種
    ///   裝飾 → 進「擁有」清單，要在店裡的佈置模式才擺得出來
    /// </summary>
    public class FlowerShopPanel : TownShopPanel
    {
        public static FlowerShopPanel Instance { get; private set; }

        public static FlowerShopPanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("FlowerShopUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<FlowerShopPanel>();
        }

        /// <summary>
        /// ⚠️ 貨架單獨一頁 —— 原版資料的註解就寫著「貨架：花店裡另開一個分頁賣，
        ///    不跟桌椅擠在同一頁」。十六款貨架擠進家具頁會整個洗版。
        /// </summary>
        enum Tab { Seeds, Decor, Furniture, Shelf }
        Tab tab = Tab.Seeds;

        void Awake() { Instance = this; Init(12); }
        void OnDestroy() { if (Instance == this) Instance = null; }

        protected override bool UseTabs => true;
        protected override string Title => "花店";
        protected override string Hint => tab switch
        {
            Tab.Seeds => "Esc 關閉 · 種子種在後花園，開花後可以自己賣或拿去調藥水",
            Tab.Decor => "Esc 關閉 · 買來的裝飾要回自己店裡才擺得出來",
            Tab.Shelf => "Esc 關閉 · 貨架佔 1×2 格，靠左後牆那排最好看",
            _         => "Esc 關閉 · 販售桌是上架商品用的，顧客會走到桌前來買",
        };

        protected override void Refresh()
        {
            BuildTabs();
            rowsBox.Clear();
            switch (tab)
            {
                case Tab.Seeds: BuildSeeds(); break;
                case Tab.Decor: BuildDecor(); break;
                case Tab.Furniture: BuildFurniture(false); break;
                case Tab.Shelf: BuildFurniture(true); break;
            }
        }

        void BuildTabs()
        {
            if (tabsBox.childCount == 0)
            {
                foreach (var (label, t) in new[]
                {
                    ("種子", Tab.Seeds), ("裝飾", Tab.Decor),
                    ("家具", Tab.Furniture), ("貨架", Tab.Shelf),
                })
                {
                    var tt = t;
                    var b = new Button(() => { tab = tt; RefreshAll(); }) { text = label };
                    b.AddToClassList("tab");
                    b.userData = tt;
                    tabsBox.Add(b);
                }
            }
            foreach (var b in tabsBox.Children()) b.EnableInClassList("active", (Tab)b.userData == tab);
        }

        void BuildSeeds()
        {
            foreach (var f in GardenData.Flowers)
            {
                var def = f;
                var row = new VisualElement();
                row.AddToClassList("row");
                row.style.height = 52;

                row.Add(Icon(GameArt.Item(def.Seed)));
                row.Add(Col(def.Seed, "col-name", 120f));
                row.Add(Col(def.Desc, "up-desc"));
                row.Add(Col($"收成 {def.Yield} 朵", "up-effect"));
                row.Add(Col($"{def.SeedPrice} 金", "col-price"));

                bool canBuy = Wallet.Gold >= def.SeedPrice;
                row.Add(Act("買 1", "btn-buy", canBuy, () =>
                {
                    if (!Garden.BuySeed(def.Seed)) { Toast.Show("買不了 —— 金幣不夠或背包滿了"); return; }
                    Toast.Show($"買了 {def.Seed}　－{def.SeedPrice} 金");
                    RefreshAll();
                }));
                rowsBox.Add(row);
            }
        }

        /// <summary>家具與貨架（同一份目錄，用 Shelf 旗標分頁）。</summary>
        void BuildFurniture(bool shelves)
        {
            var head = new VisualElement();
            head.AddToClassList("head-row");
            head.Add(Col("家具", "head-label col-name"));
            head.Add(Col("佔地", "head-label up-effect"));
            head.Add(Col("售價", "head-label col-price"));
            rowsBox.Add(head);

            foreach (var f in Furniture.All)
            {
                if (f.Shelf != shelves) continue;
                // 售價 0 ＝開店就送的（販售桌），買不到
                if (f.Price <= 0) continue;
                var def = f;
                int owned = RoomLayout.OwnedCount(def.Id);
                int unplaced = RoomLayout.Unplaced(def.Id);

                var row = new VisualElement();
                row.AddToClassList("row");
                row.style.height = 56;

                row.Add(Icon(GameArt.FurnitureArt(def.Id), 40f));
                row.Add(Col(def.Name, "col-name", 120f));
                row.Add(Col(def.Desc, "up-desc"));
                row.Add(Col($"{def.W}×{def.H} 格", "up-effect"));
                row.Add(Col($"{def.Price} 金", "col-price"));
                row.Add(Col(owned > 0 ? $"已有 {owned}（未擺 {unplaced}）" : "", "up-effect"));

                bool canBuy = Wallet.Gold >= def.Price;
                row.Add(Act("買 1", "btn-buy", canBuy, () =>
                {
                    if (!RoomLayout.Buy(def.Id)) { Toast.Show("金幣不夠"); return; }
                    Toast.Show($"買了 {def.Name}　－{def.Price} 金");
                    RefreshAll();
                }));
                rowsBox.Add(row);
            }
        }

        void BuildDecor()
        {
            foreach (var d in Decor.Catalog)
            {
                var def = d;
                int owned = DecorCatalog.OwnedCount(def.Id);

                var row = new VisualElement();
                row.AddToClassList("row");
                row.style.height = 52;

                row.Add(Icon(GameArt.Decoration(def.Id)));
                row.Add(Col(def.Name, "col-name", 130f));
                row.Add(Col(owned > 0 ? $"已有 {owned}" : "", "up-effect"));
                row.Add(Col($"{def.Price} 金", "col-price"));

                bool canBuy = Wallet.Gold >= def.Price;
                row.Add(Act("買 1", "btn-buy", canBuy, () =>
                {
                    if (!DecorCatalog.Buy(def.Id)) { Toast.Show("金幣不夠"); return; }
                    Toast.Show($"買了 {def.Name}　－{def.Price} 金");
                    RefreshAll();
                }));
                rowsBox.Add(row);
            }
        }
    }

    /// <summary>
    /// 糖果鎮的商店（軟糖鱷馴養師）：買森林那邊買不到的貨。
    ///
    /// ⚠️ 這裡買進的價錢（Candy.Goods）**低於**你自己店裡賣給顧客的建議售價
    ///    （Prices.BasePrice）—— 差價就是跑這一趟的利潤，這是糖果鎮存在的理由。
    /// </summary>
    public class GoodsShopPanel : TownShopPanel
    {
        public static GoodsShopPanel Instance { get; private set; }

        public static GoodsShopPanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("GoodsShopUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<GoodsShopPanel>();
        }

        string shopTitle = "商行";

        void Awake() { Instance = this; Init(12); }
        void OnDestroy() { if (Instance == this) Instance = null; }

        protected override string Title => shopTitle;
        protected override string Hint => "Esc 關閉 · 買回去擺自己店裡賣，賺的是價差";

        public void Open(string title)
        {
            shopTitle = string.IsNullOrEmpty(title) ? "商行" : title;
            if (titleLabel != null) titleLabel.text = shopTitle;
            Open();
        }

        protected override void Refresh()
        {
            if (titleLabel != null) titleLabel.text = shopTitle;
            rowsBox.Clear();

            var head = new VisualElement();
            head.AddToClassList("head-row");
            head.Add(Col("商品", "head-label col-name"));
            head.Add(Col("進價", "head-label col-price"));
            head.Add(Col("你店裡建議售價", "head-label up-effect"));
            rowsBox.Add(head);

            foreach (var (name, price) in Candy.Goods)
            {
                string n = name;
                int cost = price;
                int resale = Prices.BasePrice.TryGetValue(n, out var r) ? r : 0;

                var row = new VisualElement();
                row.AddToClassList("row");
                row.Add(Icon(GameArt.Item(n)));
                row.Add(Col(n, "col-name", 130f));
                row.Add(Col($"{cost} 金", "col-price"));
                row.Add(Col(resale > 0 ? $"{resale} 金（賺 {resale - cost}）" : "", "up-effect"));

                bool canBuy = Wallet.Gold >= cost;
                row.Add(Act("買 1", "btn-buy", canBuy, () => Buy(n, cost)));
                rowsBox.Add(row);
            }
        }

        void Buy(string name, int cost)
        {
            if (Wallet.Gold < cost) { Toast.Show("金幣不夠"); return; }
            if (!Inventory.Add(name, 1)) { Toast.Show("背包滿了 —— 先整理一下"); return; }
            Wallet.Add(-cost);
            DailyLog.RecordSpend(cost);
            Toast.Show($"買了 {name}　－{cost} 金");
            RefreshAll();
        }
    }
}
