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

        /// <summary>
        /// 一頁幾列（2026-11-27 改成固定高度＋翻頁，見 <see cref="Pager"/>；以前是捲動，而且上架頁最多只列 14 種）。
        /// 面板高（像素外觀）＝ padding 30 ＋ 標題列 5 ＋ 分頁 48 ＋ 欄位標頭格 24 ＋ 清單 6 × 60 ＝ 360
        ///   ＋ 分隔線 18 ＋ 底列 30 ＋ padding 24 ＝ 539（max-height 88%＝563 以內）。兩個分頁一樣高：
        ///   升級頁沒有欄位標頭，但標頭格照樣佔 24（空著），切分頁時面板不會伸縮。
        /// </summary>
        const int RowsPerPage = 6;
        /// <summary>列距：`.sk .row` 高 57 ＋ margin-bottom 3。</summary>
        const int RowPitch = 60;
        /// <summary>欄位標頭格的高（`.sk .head-row` 24）。</summary>
        const int HeadH = 24;

        UIDocument doc;
        VisualElement root, panel, tabsBox;
        VisualElement headBox, rowsBox;    // 欄位標頭格（固定高）／這一頁的列（＝ pager.Body）
        Pager pager;
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
            UiSkin.Apply(root);           // 8-bit 外觀（總開關在 UiSkin.Enabled）
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

            header.Add(UiSkin.GoldBox(out goldLabel));      // [金幣][數字]（舊外觀：「123 金」）

            var close = new Button(Close) { text = "×" };
            close.AddToClassList("close");
            header.Add(close);

            tabsBox = new VisualElement();
            tabsBox.AddToClassList("tabs");
            panel.Add(tabsBox);
            AddTab("上架定價", Tab.Stock);
            AddTab("升級", Tab.Upgrade);

            // 欄位標頭格：固定高，沒有標頭的分頁就空著（面板高度不跟著分頁變）
            headBox = new VisualElement();
            headBox.AddToClassList("pg-head");
            headBox.style.height = HeadH;
            headBox.style.flexShrink = 0;
            panel.Add(headBox);

            // 清單：固定 6 列高、超過就翻頁（不捲動）
            pager = new Pager(RowsPerPage, RowsPerPage * RowPitch, Refresh);
            rowsBox = pager.Body;
            rowsBox.AddToClassList("rows");
            panel.Add(rowsBox);

            hintLabel = UiSkin.Footer(panel, "關閉", "Esc");   // [Esc] 關閉 ……… 右邊放短資訊
            pager.Bar.AddToClassList("pg-bar--center");          // 翻頁鈕擺在底列正中間
            hintLabel.parent.Add(pager.Bar);

            anim = UIAnim.Pop(root, panel, dim);              // 淡入＋輕微放大，暗幕只淡入
            built = true;
        }

        void AddTab(string label, Tab t)
        {
            var b = new Button(() => { tab = t; pager.Reset(); Sfx.Play("ui-tab"); Refresh(); }) { text = label };
            b.AddToClassList("tab");
            b.userData = t;
            tabsBox.Add(b);
        }

        // ──────────── 內容 ────────────

        void Refresh()
        {
            if (!built) return;

            goldLabel.text = UiSkin.MoneyText(Wallet.Gold);
            foreach (var b in tabsBox.Children()) b.EnableInClassList("active", (Tab)b.userData == tab);

            headBox.Clear();
            if (tab == Tab.Stock) BuildStock(); else BuildUpgrades();
            UiSkin.Stripe(rowsBox);
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
            }
            return outList;
        }

        void BuildStock()
        {
            hintLabel.text = $"貨架 {ShopStock.Types}/{Upgrades.ShelfCap()} 種";

            var head = new VisualElement();
            head.AddToClassList("head-row");
            var iconGap = new VisualElement();                 // 對齊列上的道具圖
            iconGap.AddToClassList("stock-icon");
            head.Add(iconGap);
            head.Add(HeadLabel("品項", "col-name"));
            head.Add(HeadLabel("可用", "col-bag"));
            head.Add(HeadLabel("架上", "col-shelf"));
            head.Add(HeadLabel("售價", "col-price"));
            headBox.Add(head);

            // 上架／撤下／調價之後東西會變：只把頁碼夾回範圍內，不跳回第 1 頁
            var items = StockItems();
            pager.Render(items.Count, i => StockRow(items[i]),
                "背包裡沒有可上架的東西 —— 去森林採集或到藥水室調配吧");
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

            var icon = new VisualElement();
            icon.AddToClassList("stock-icon");
            var sp = GameArt.Item(name);
            if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
            row.Add(icon);

            var nameCol = Col(name, "col-name", true);
            nameCol.AddToClassList("stock-name");
            row.Add(nameCol);
            row.Add(Col(avail.ToString(), "col-bag", avail > 0));
            row.Add(Col(shelf.ToString(), "col-shelf", shelf > 0));

            var minus = new Button(() => { ShopStock.SetPrice(name, price - 1); Refresh(); }) { text = "－" };
            minus.AddToClassList("btn"); minus.AddToClassList("btn-step"); minus.AddToClassList("sk-minus");
            minus.SetEnabled(shelf > 0);
            row.Add(minus);

            var priceBox = UiSkin.Money(price);
            priceBox.AddToClassList("col-price");
            row.Add(priceBox);

            var plus = new Button(() => { ShopStock.SetPrice(name, price + 1); Refresh(); }) { text = "＋" };
            plus.AddToClassList("btn"); plus.AddToClassList("btn-step"); plus.AddToClassList("sk-plus");
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
            hintLabel.text = "升級立即生效";

            var tracks = new List<Track>(Upgrades.Tracks());
            pager.Render(tracks.Count, i => UpgradeRow(tracks[i]));
        }

        VisualElement UpgradeRow(Track t)
        {
            var d = Upgrades.Def(t);
            var row = new VisualElement();
            row.AddToClassList("row");

            // 名稱＋等級徽章（以前是「招牌 Lv.2」一整串字）
            var nameBox = new VisualElement();
            nameBox.AddToClassList("up-name-box");
            var nameLabel = new Label(d.Name);
            nameLabel.AddToClassList("up-name");
            nameBox.Add(nameLabel);
            var lv = UiSkin.Badge($"Lv.{Upgrades.Level(t)}");
            lv.AddToClassList("up-lv");
            nameBox.Add(lv);
            row.Add(nameBox);

            var desc = new Label(d.Desc);
            desc.AddToClassList("up-desc");
            row.Add(desc);

            bool max = Upgrades.IsMax(t);
            row.Add(EffectBox(t, max));

            // 費用：金幣＋數字；滿級改成「✓ 滿級」小圖（舊外觀：「已滿級」文字）
            int cost = Upgrades.Cost(t);
            if (max && UiSkin.On)
            {
                var done = new VisualElement();
                done.AddToClassList("up-max");
                done.Add(UiSkin.Ico("check"));
                var dl = new Label("滿級");
                dl.AddToClassList("up-max-text");
                done.Add(dl);
                row.Add(done);
            }
            else if (max)
            {
                var costLabel = new Label("已滿級");
                costLabel.AddToClassList("up-cost");
                row.Add(costLabel);
            }
            else
            {
                var costBox = UiSkin.Money(cost);
                costBox.AddToClassList("up-cost");
                row.Add(costBox);
            }

            var buy = new Button(() =>
            {
                if (Upgrades.Buy(t)) { Sfx.Play("upgrade"); Refresh(); }
                else Sfx.Play("deny");                  // 錢不夠或已滿級（按鈕通常已經灰掉，保險）
            }) { text = "升級" };
            buy.AddToClassList("btn"); buy.AddToClassList("btn-buy");
            buy.SetEnabled(!max && Wallet.Gold >= cost);
            row.Add(buy);

            return row;
        }

        /// <summary>
        /// 效果欄：「現在 → 下一級」。外觀開著時中間的「→」換成綠色小箭頭圖；滿級只寫現在的值。
        /// </summary>
        static VisualElement EffectBox(Track t, bool max)
        {
            if (max || !UiSkin.On)
            {
                var effect = new Label(max
                    ? Upgrades.EffectNow(t)
                    : $"{Upgrades.EffectNow(t)} → {Upgrades.EffectNext(t)}");
                effect.AddToClassList("up-effect");
                return effect;
            }
            var box = new VisualElement();
            box.AddToClassList("up-effect-box");
            var now = new Label(Upgrades.EffectNow(t));
            now.AddToClassList("up-effect");
            now.AddToClassList("up-effect-now");
            box.Add(now);
            box.Add(UiSkin.Ico("arrow"));
            var next = new Label(Upgrades.EffectNext(t));
            next.AddToClassList("up-effect");
            next.AddToClassList("up-effect-next");
            box.Add(next);
            return box;
        }
    }
}
