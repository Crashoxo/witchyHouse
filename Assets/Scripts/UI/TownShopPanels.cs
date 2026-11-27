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
        /// <summary>
        /// 一頁幾列（2026-11-27 改成固定高度＋翻頁，見 <see cref="Pager"/>）。
        /// 面板高（像素外觀）＝ padding 30 ＋ 標題列 5 ＋（花店才有的分頁 48）＋ 欄位標頭格 24 ＋ 清單 6 × 60 ＝ 360
        ///   ＋ 分隔線 18 ＋ 底列 30 ＋ padding 24 ＝ 491（雜貨鋪、商行）／539（花店）。
        ///   沒有欄位標頭的分頁（種子、裝飾）標頭格照樣佔 24（空著），切分頁時面板不會伸縮。
        /// </summary>
        const int RowsPerPage = 6;
        /// <summary>列距：`.sk .row` 高 57 ＋ margin-bottom 3。</summary>
        const int RowPitch = 60;
        /// <summary>欄位標頭格的高（`.sk .head-row` 24）。</summary>
        const int HeadH = 24;

        protected UIDocument doc;
        protected VisualElement root;
        /// <summary>這一頁的列（＝ pager.Body）；欄位標頭放 <see cref="headBox"/>。</summary>
        protected VisualElement rowsBox, headBox;
        protected Pager pager;
        protected Label titleLabel, goldLabel, hintLabel;
        protected VisualElement tabsBox;
        bool built;
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）

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
            if (!anim.IsOpen) return;
            if (Input.GetKeyDown(KeyCode.Escape)) Close();
            else pager.HandleKeys();     // ←／→、A／D 翻頁
        }

        public void Open()
        {
            if (!built) Build();
            if (!built) return;
            anim.Show();                 // 淡入（邏輯上這一行就算開著，見 UIAnim）
            UIState.ModalOpen = true;
            pager.Reset();               // 每次打開都從第 1 頁看
            Sfx.Play("ui-open");                                    // 音效：面板打開
            GameArt.OnReady(RefreshAll);
        }

        public void Close()
        {
            anim?.Hide();                // 淡出只是視覺殘影，邏輯上這一行就算關了
            UIState.ModalOpen = false;
            Sfx.Play("ui-close");                                   // 音效：面板關閉
        }

        protected void RefreshAll()
        {
            if (!built) return;
            goldLabel.text = UiSkin.MoneyText(Wallet.Gold);
            hintLabel.text = Hint;
            headBox.Clear();
            Refresh();
            UiSkin.Stripe(rowsBox);
        }

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError($"[{GetType().Name}] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/ShopManageStyle"));
            UiSkin.Apply(root);           // 8-bit 外觀（總開關在 UiSkin.Enabled）
            CjkFont.Apply(root);
            Sfx.BindClicks(root);         // 所有按鈕的 click 音

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

            header.Add(UiSkin.GoldBox(out goldLabel));      // [金幣][數字]（舊外觀：「123 金」）

            var close = new Button(Close) { text = "×" };
            close.AddToClassList("close");
            header.Add(close);

            if (UseTabs)
            {
                tabsBox = new VisualElement();
                tabsBox.AddToClassList("tabs");
                panel.Add(tabsBox);
            }

            // 欄位標頭格：固定高，沒有標頭的分頁就空著
            headBox = new VisualElement();
            headBox.AddToClassList("pg-head");
            headBox.style.height = HeadH;
            headBox.style.flexShrink = 0;
            panel.Add(headBox);

            // 清單：固定 6 列高、超過就翻頁（不捲動）
            pager = new Pager(RowsPerPage, RowsPerPage * RowPitch, RefreshAll);
            rowsBox = pager.Body;
            rowsBox.AddToClassList("rows");
            panel.Add(rowsBox);

            hintLabel = UiSkin.Footer(panel, "關閉", "Esc");   // [Esc] 關閉 ……… 右邊放一句短提醒
            pager.Bar.AddToClassList("pg-bar--center");          // 翻頁鈕擺在底列正中間
            hintLabel.parent.Add(pager.Bar);

            root.style.display = DisplayStyle.None;
            anim = UIAnim.Pop(root, panel, dim);              // 淡入＋輕微放大，暗幕只淡入
            built = true;
        }

        // ── 給子類用的小工具 ────────────────────────────────────

        /// <summary>
        /// 列最前面的圖示。尺寸走 class（舊外觀 34／40、像素外觀 48）——
        /// ⚠️ 以前是 inline 的 style.width，inline 優先權最高，uss 改不動。
        /// </summary>
        protected static VisualElement Icon(Sprite sp, bool big = false)
        {
            var el = new VisualElement();
            el.AddToClassList("ts-icon");
            if (big) el.AddToClassList("ts-icon--big");
            if (sp != null) el.style.backgroundImage = new StyleBackground(sp);
            return el;
        }

        /// <summary>價格欄：金幣圖示＋數字（舊外觀：「12 金」），套 col-price 的欄寬。</summary>
        protected static VisualElement Price(int amount)
        {
            var m = UiSkin.Money(amount);
            m.AddToClassList("col-price");
            return m;
        }

        /// <summary>欄位標頭最前面的空白，寬度＝列圖示（標頭字才對得齊下面的欄）。</summary>
        protected static VisualElement HeadGap()
        {
            var el = new VisualElement();
            el.AddToClassList("ts-icon");
            el.AddToClassList("ts-headgap");
            return el;
        }

        /// <summary>
        /// 一欄文字。<paramref name="cls"/> 可以是空白分隔的好幾個 class（"head-label col-price"）。
        /// ⚠️ AddToClassList 不會幫你拆空白：以前整串直接丟進去，標頭字拿到的是一個叫「head-label col-price」的怪 class，
        ///    head-label 與欄寬一個都沒套到 → 標頭跟下面的欄對不齊（2026-11-27 查花店跑版時一起找到）。
        /// </summary>
        protected static Label Col(string text, string cls, float width = 0f)
        {
            var l = new Label(text);
            foreach (var c in cls.Split(' '))
                if (c.Length > 0) l.AddToClassList(c);
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

        /// <summary>
        /// 把整張清單交給翻頁器：<paramref name="rows"/> 是每一列的「做法」（只有目前這頁的會真的建出來）。
        /// 買賣之後東西變多變少只會把頁碼夾回範圍內，不跳回第 1 頁。
        /// </summary>
        protected void ShowRows(List<System.Func<VisualElement>> rows, string emptyText = null)
        {
            pager.Render(rows.Count, i => rows[i](), emptyText);
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
        protected override string Hint => "自己開店賣得更貴";

        protected override void Refresh()
        {
            var head = new VisualElement();
            head.AddToClassList("head-row");
            head.Add(HeadGap());
            head.Add(Col("品項", "head-label col-name", 120f));
            head.Add(Col("持有", "head-label col-bag"));
            head.Add(Col("單價", "head-label col-price"));
            headBox.Add(head);

            var rows = new List<System.Func<VisualElement>>();
            foreach (var e in Prices.DefaultBuy)
            {
                int have = Storage.AvailableOf(e.Name);
                if (have <= 0) continue;
                string name = e.Name;
                int price = e.Price;
                rows.Add(() => SellRow(name, price, have));
            }
            ShowRows(rows, "背包和倉庫裡沒有雜貨鋪收的東西 —— 去森林採點材料吧");
        }

        VisualElement SellRow(string name, int price, int have)
        {
            var row = new VisualElement();
            row.AddToClassList("row");
            row.Add(Icon(GameArt.Item(name)));
            row.Add(Col(name, "col-name", 120f));
            var haveBox = new VisualElement();                      // 持有：小徽章
            haveBox.AddToClassList("col-bag");
            haveBox.AddToClassList("ts-cell");
            haveBox.Add(UiSkin.Badge($"×{have}"));
            row.Add(haveBox);
            row.Add(Price(price));

            row.Add(Act("賣 1", "btn-list", true, () => Sell(name, price, 1)));
            // 「全賣 [金]84」：按鈕裡直接看得到一共換多少（舊外觀：「賣全部（84 金）」）
            var sellAll = Act("", "btn-buy", true, () => Sell(name, price, have));
            UiSkin.MoneyButtonContent(sellAll, "全賣", have * price, $"賣全部（{have * price} 金）");
            row.Add(sellAll);
            return row;
        }

        void Sell(string name, int price, int qty)
        {
            if (qty <= 0) return;
            if (!Storage.TakeAny(name, qty)) { Sfx.Play("deny"); return; }   // 先扣背包、不夠再扣倉庫
            int gold = price * qty;
            Wallet.Add(gold);
            Sfx.Play("coin");
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
            Tab.Seeds => "種在後花園",
            Tab.Decor => "回店裡佈置",
            Tab.Shelf => "靠左後牆最好看",
            _         => "回店裡佈置",
        };

        protected override void Refresh()
        {
            BuildTabs();
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
                    var b = new Button(() => { tab = tt; pager.Reset(); Sfx.Play("ui-tab"); RefreshAll(); }) { text = label };
                    b.AddToClassList("tab");
                    b.userData = tt;
                    tabsBox.Add(b);
                }
            }
            foreach (var b in tabsBox.Children()) b.EnableInClassList("active", (Tab)b.userData == tab);
        }

        void BuildSeeds()
        {
            var rows = new List<System.Func<VisualElement>>();
            foreach (var f in GardenData.Flowers)
            {
                var def = f;
                rows.Add(() => SeedRow(def));
            }
            ShowRows(rows);
        }

        VisualElement SeedRow(FlowerDef def)
        {
            var row = new VisualElement();
            row.AddToClassList("row");
            row.AddToClassList("ts-row");

            row.Add(Icon(GameArt.Item(def.Seed)));
            row.Add(Col(def.Seed, "col-name", 120f));
            row.Add(Col(def.Desc, "up-desc"));
            // 收成：[花的小圖]×3（舊外觀沒有圖示時就是「收成 3 朵」）
            row.Add(YieldCell(def.Flower, def.Yield));
            row.Add(Price(def.SeedPrice));

            bool canBuy = Wallet.Gold >= def.SeedPrice;
            row.Add(Act("買 1", "btn-buy", canBuy, () =>
            {
                if (!Garden.BuySeed(def.Seed)) { Sfx.Play("deny"); Toast.Show("買不了 —— 金幣不夠或背包滿了"); return; }
                Sfx.Play("buy");
                Toast.Show($"買了 {def.Seed}　－{def.SeedPrice} 金");
                RefreshAll();
            }));
            return row;
        }

        /// <summary>家具與貨架（同一份目錄，用 Displays 分頁：貨架＋陳列桌一頁、燈與其他家具一頁）。</summary>
        void BuildFurniture(bool shelves)
        {
            var head = new VisualElement();
            head.AddToClassList("head-row");
            head.Add(HeadGap());
            head.Add(Col("家具", "head-label col-name", 120f));
            head.Add(Col("", "head-label up-desc"));               // 說明欄沒有標頭字，但要佔位，後面的欄才對得齊
            head.Add(Col("佔地", "head-label up-effect ts-size"));
            head.Add(Col("售價", "head-label col-price"));
            headBox.Add(head);

            var rows = new List<System.Func<VisualElement>>();
            foreach (var f in Furniture.All)
            {
                // 貨架頁＝會陳列商品的（貨架＋陳列桌）；家具頁＝其他（燈、沙發、書櫃…）
                if (f.Displays != shelves) continue;
                // 售價 0 ＝開店就送的（販售桌），買不到
                if (f.Price <= 0) continue;
                // 沒有圖的不賣（例如 GameArt.UsePixelFurniture 關掉時，新款家具沒有舊圖）
                if (GameArt.FurnitureArt(f.Id) == null) continue;
                var def = f;
                rows.Add(() => FurnitureRow(def));
            }
            ShowRows(rows, "這一類目前沒有東西");   // 家具頁現在只有販售桌（送的、不賣）→ 空的
        }

        VisualElement FurnitureRow(FurnitureDef def)
        {
            int owned = RoomLayout.OwnedCount(def.Id);
            int unplaced = RoomLayout.Unplaced(def.Id);

            var row = new VisualElement();
            row.AddToClassList("row");
            row.AddToClassList("ts-row--big");

            row.Add(Icon(GameArt.FurnitureArt(def.Id), true));
            row.Add(Col(def.Name, "col-name", 120f));
            row.Add(Col(def.Desc, "up-desc"));
            row.Add(Col($"{def.W}×{def.H} 格", "up-effect ts-size"));   // 66 寬（以前借 up-effect 的 150，把說明欄擠扁）
            row.Add(Price(def.Price));
            row.Add(OwnedCell(owned, unplaced, true));

            bool canBuy = Wallet.Gold >= def.Price;
            row.Add(Act("買 1", "btn-buy", canBuy, () =>
            {
                if (!RoomLayout.Buy(def.Id)) { Sfx.Play("deny"); Toast.Show("金幣不夠"); return; }
                Sfx.Play("buy");
                Toast.Show($"買了 {def.Name}　－{def.Price} 金");
                RefreshAll();
            }));
            return row;
        }

        /// <summary>收成欄：花的小圖＋「×3」；外觀關著維持原本的「收成 3 朵」。</summary>
        static VisualElement YieldCell(string flower, int yield)
        {
            if (!UiSkin.On) return Col($"收成 {yield} 朵", "up-effect");
            var cell = UiSkin.IconCount(GameArt.Item(flower), $"×{yield}");
            cell.AddToClassList("ts-yield");
            return cell;
        }

        /// <summary>
        /// 已擁有欄：外觀開著是「有 N」小徽章（還沒擺出來的再加一個「未擺 M」）；關著維持原本那句字。
        /// </summary>
        static VisualElement OwnedCell(int owned, int unplaced, bool showUnplaced)
        {
            if (!UiSkin.On)
                return Col(owned <= 0 ? "" : showUnplaced ? $"已有 {owned}（未擺 {unplaced}）" : $"已有 {owned}", "up-effect");
            var cell = new VisualElement();
            cell.AddToClassList("ts-owned");
            if (owned > 0)
            {
                cell.Add(UiSkin.Badge($"有 {owned}"));
                if (unplaced > 0)
                {
                    var u = new Label($"未擺 {unplaced}");
                    u.AddToClassList("ts-unplaced");
                    cell.Add(u);
                }
            }
            return cell;
        }

        void BuildDecor()
        {
            var rows = new List<System.Func<VisualElement>>();
            foreach (var d in Decor.Catalog)
            {
                if (GameArt.Decoration(d.Id) == null) continue;     // 沒有圖的不賣（地毯只有細畫版）
                var def = d;
                rows.Add(() => DecorRow(def));
            }
            ShowRows(rows);
        }

        VisualElement DecorRow(DecorDef def)
        {
            int owned = DecorCatalog.OwnedCount(def.Id);

            var row = new VisualElement();
            row.AddToClassList("row");
            row.AddToClassList("ts-row");

            row.Add(Icon(GameArt.Decoration(def.Id)));
            row.Add(Col(def.Name, "col-name", 130f));
            row.Add(OwnedCell(owned, 0, false));
            row.Add(Price(def.Price));

            bool canBuy = Wallet.Gold >= def.Price;
            row.Add(Act("買 1", "btn-buy", canBuy, () =>
            {
                if (!DecorCatalog.Buy(def.Id)) { Sfx.Play("deny"); Toast.Show("金幣不夠"); return; }
                Sfx.Play("buy");
                Toast.Show($"買了 {def.Name}　－{def.Price} 金");
                RefreshAll();
            }));
            return row;
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
        protected override string Hint => "買回店裡賣，賺價差";

        public void Open(string title)
        {
            shopTitle = string.IsNullOrEmpty(title) ? "商行" : title;
            if (titleLabel != null) titleLabel.text = shopTitle;
            Open();
        }

        protected override void Refresh()
        {
            if (titleLabel != null) titleLabel.text = shopTitle;

            var head = new VisualElement();
            head.AddToClassList("head-row");
            head.Add(HeadGap());
            head.Add(Col("商品", "head-label col-name", 130f));
            head.Add(Col("進價", "head-label col-price"));
            head.Add(Col("店裡售價", "head-label up-effect"));
            headBox.Add(head);

            var rows = new List<System.Func<VisualElement>>();
            foreach (var (name, price) in Candy.Goods)
            {
                string n = name;
                int cost = price;
                rows.Add(() => GoodsRow(n, cost));
            }
            ShowRows(rows);
        }

        VisualElement GoodsRow(string n, int cost)
        {
            int resale = Prices.BasePrice.TryGetValue(n, out var r) ? r : 0;

            var row = new VisualElement();
            row.AddToClassList("row");
            row.Add(Icon(GameArt.Item(n)));
            row.Add(Col(n, "col-name", 130f));
            row.Add(Price(cost));
            row.Add(ResaleCell(resale, cost));

            bool canBuy = Wallet.Gold >= cost;
            row.Add(Act("買 1", "btn-buy", canBuy, () => Buy(n, cost)));
            return row;
        }

        /// <summary>店裡售價欄：[金幣]120 ＋綠字「+30」（舊外觀：「120 金（賺 30）」）。</summary>
        static VisualElement ResaleCell(int resale, int cost)
        {
            if (resale <= 0) return Col("", "up-effect");
            if (!UiSkin.On) return Col($"{resale} 金（賺 {resale - cost}）", "up-effect");
            var cell = new VisualElement();
            cell.AddToClassList("ts-resale");
            cell.Add(UiSkin.Money(resale));
            var p = new Label($"+{resale - cost}");
            p.AddToClassList("ts-profit");
            cell.Add(p);
            return cell;
        }

        void Buy(string name, int cost)
        {
            if (Wallet.Gold < cost) { Sfx.Play("deny"); Toast.Show("金幣不夠"); return; }
            if (!Inventory.Add(name, 1)) { Sfx.Play("deny"); Toast.Show("背包滿了 —— 先整理一下"); return; }
            Wallet.Add(-cost);
            DailyLog.RecordSpend(cost);
            Sfx.Play("buy");
            Toast.Show($"買了 {name}　－{cost} 金");
            RefreshAll();
        }
    }
}
