using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 每日結算 —— 睡醒（或昏倒醒來）之後、畫面還全黑的時候蓋上來的那張帳單。
    ///
    /// 資料全部來自 <see cref="DailyLog.Last"/>（跨日時 Rollover() 封存的那一天），
    /// 這裡**只顯示、不計算**，唯一算出來的是「淨收入 ＝ 營收 ＋ 收購 － 支出」。
    ///
    /// 由 <see cref="SleepOverlay"/> 在時間推進之後、黑幕淡出之前叫起來，
    /// 玩家按鍵關掉才繼續淡出 —— 所以不會被自動流程蓋掉，帳單一定看得到。
    ///
    /// ⚠️ sortingOrder = 95：要蓋在睡覺黑幕（90）**之上**、換場黑幕（100）之下。
    ///    低於 90 會被黑幕吃掉，症狀是「什麼都沒發生但卡住不動」。
    ///
    /// ⚠️ 開場先擋 0.45 秒的按鍵 —— 「按 E 去睡」的那一下會穿透過來，
    ///    不擋的話帳單會在出現的同一瞬間被關掉。
    ///
    /// ── 像素外觀（<see cref="UiSkin.On"/>）──────────────────────────
    /// 跟其他面板同一套木框＋羊皮紙＋紫布緞帶標題。數字改成「圖示＋數字＋兩個字的小標」的小卡，三欄排：
    ///   營收[金幣] 賣出[籃子] 收購[麻袋] 支出[金幣，紅字] 採集[葉子] 煉製[藥瓶] 名聲[星星]（0 的那幾格不出）。
    /// 賣出明細是一列列小卡 [道具圖][名稱][×n 徽章][金幣 金額]；淨收入是金框卡；底下 [Enter][Space] 繼續。
    /// 外觀關著時照舊（HudExtraStyle 的 .day-*，一行一行的「項目 —— 數字」）。
    /// </summary>
    public class DaySummaryPanel : MonoBehaviour
    {
        public static DaySummaryPanel Instance { get; private set; }

        public static DaySummaryPanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("DaySummaryUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<DaySummaryPanel>();
        }

        /// <summary>有沒有結算資料可以顯示（第一天還沒過完時是沒有的）。</summary>
        public static bool HasData => DailyLog.Last != null;

        const float InputGuard = 0.45f;

        UIDocument doc;
        VisualElement root, card, statBox, listBox;
        Label titleLabel, dateLabel, noteLabel, netLabel, goldLabel;
        ScrollView listScroll;
        float openedAt;
        bool ownedModal;
        bool built;
        bool skin;        // 這次用的是不是像素外觀（Build 時決定）
        /// <summary>像素外觀：淨收入的金幣＋數字那一格、持有金幣的數字（每次 Refresh 重填）。</summary>
        VisualElement netMoneyBox;
        Label walletLabel;
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 95;
            if (doc.panelSettings == null)
                Debug.LogError("[DaySummaryPanel] 找不到 Resources/ui/UIPanelSettings");
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (IsOpen && ownedModal) UIState.ModalOpen = false;
        }

        public bool IsOpen => built && anim != null && anim.IsOpen;   // ⚠️ 不看 display：關閉動畫期間它還是 Flex

        void Update()
        {
            if (!IsOpen) return;
            if (Time.unscaledTime - openedAt < InputGuard) return;
            if (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter)
                || Input.GetKeyDown(KeyCode.Space) || Input.GetKeyDown(KeyCode.E)
                || Input.GetKeyDown(KeyCode.Escape) || Input.GetMouseButtonDown(0))
                Close();
        }

        public void Open()
        {
            if (!HasData) return;
            if (!built) Build();
            if (!built) return;

            // 睡覺過場本來就佔著 Modal，別重複開關（不然關帳單時會提早解鎖操作）
            ownedModal = !UIState.ModalOpen;
            if (ownedModal) UIState.ModalOpen = true;

            openedAt = Time.unscaledTime;
            anim.Show();                 // 淡入（邏輯上這一行就算開著，見 UIAnim）
            Sfx.Play("ui-open");                                    // 音效：面板打開
            GameArt.OnReady(Refresh);      // 同步載入，OnReady 只是保證圖示已經在了
        }

        public void Close()
        {
            anim?.Hide();                // 淡出只是視覺殘影，邏輯上這一行就算關了
            if (ownedModal) UIState.ModalOpen = false;
            ownedModal = false;
            Sfx.Play("ui-close");                                   // 音效：面板關閉
        }

        // ── 版面 ────────────────────────────────────────────────

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[DaySummaryPanel] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            UiSkin.Apply(root);           // 8-bit 外觀（總開關 UiSkin.Enabled）
            skin = UiSkin.On;
            CjkFont.Apply(root);

            var layer = new VisualElement();
            layer.AddToClassList("day-layer");
            root.Add(layer);

            card = new VisualElement();
            card.AddToClassList("day-card");
            layer.Add(card);

            if (skin) BuildSkin();
            else BuildPlain();

            root.style.display = DisplayStyle.None;
            anim = UIAnim.Pop(root, card);                    // 黑幕是 SleepOverlay 的，這裡只動帳單本身
            built = true;
        }

        /// <summary>
        /// 像素外觀：[緞帶「今日結算」] / 日期 / （昏倒的提醒）/ 數字小卡 / 分隔線 / 明細 / 淨收入金框卡 / 持有 / [Enter][Space] 繼續。
        /// </summary>
        void BuildSkin()
        {
            var header = new VisualElement();
            header.AddToClassList("header");
            card.Add(header);
            titleLabel = new Label("今日結算");
            titleLabel.AddToClassList("title");
            header.Add(titleLabel);

            dateLabel = new Label();
            dateLabel.AddToClassList("day-date");
            card.Add(dateLabel);

            noteLabel = new Label();
            noteLabel.AddToClassList("day-note");
            card.Add(noteLabel);

            statBox = new VisualElement();
            statBox.AddToClassList("sk-day-stats");
            card.Add(statBox);

            var div = new VisualElement();
            div.AddToClassList("sk-divider");
            card.Add(div);

            listScroll = new ScrollView(ScrollViewMode.Vertical);
            listScroll.AddToClassList("day-list");
            card.Add(listScroll);
            listBox = listScroll.contentContainer;

            // 淨收入：[淨收入] …… [金幣 +248]
            var net = new VisualElement();
            net.AddToClassList("sk-day-net");
            card.Add(net);
            netLabel = new Label("淨收入");
            netLabel.AddToClassList("sk-day-net-label");
            net.Add(netLabel);
            netMoneyBox = new VisualElement();
            netMoneyBox.AddToClassList("sk-money");
            netMoneyBox.Add(UiSkin.Coin());
            goldLabel = new Label();                          // 淨收入的數字（像素外觀時 goldLabel 拿來放它）
            goldLabel.AddToClassList("sk-day-netnum");
            netMoneyBox.Add(goldLabel);
            net.Add(netMoneyBox);

            // 持有：…… [持有][金幣 1280]
            var wallet = new VisualElement();
            wallet.AddToClassList("sk-day-wallet");
            card.Add(wallet);
            var wl = new Label("持有");
            wl.AddToClassList("sk-day-wallet-label");
            wallet.Add(wl);
            var wm = UiSkin.Money(0, "sk-day-walletnum");
            walletLabel = wm.Q<Label>();
            wallet.Add(wm);

            UiSkin.Footer(card, "繼續", "Enter", "Space");
        }

        /// <summary>舊外觀：一行一行的「項目 —— 數字」（HudExtraStyle 的 .day-*）。</summary>
        void BuildPlain()
        {
            titleLabel = new Label("今日結算");
            titleLabel.AddToClassList("day-title");
            card.Add(titleLabel);

            dateLabel = new Label();
            dateLabel.AddToClassList("day-date");
            card.Add(dateLabel);

            noteLabel = new Label();
            noteLabel.AddToClassList("day-note");
            card.Add(noteLabel);

            card.Add(Rule());

            statBox = new VisualElement();
            card.Add(statBox);

            card.Add(Rule());

            var sub = new Label("賣出明細");
            sub.AddToClassList("day-sub");
            card.Add(sub);

            listScroll = new ScrollView(ScrollViewMode.Vertical);
            listScroll.AddToClassList("day-list");
            card.Add(listScroll);
            listBox = listScroll.contentContainer;

            card.Add(Rule());

            netLabel = new Label();
            netLabel.AddToClassList("day-net");
            card.Add(netLabel);

            goldLabel = new Label();
            goldLabel.AddToClassList("day-gold");
            card.Add(goldLabel);

            var foot = new Label("按 Enter／空白鍵繼續");
            foot.AddToClassList("day-foot");
            card.Add(foot);
        }

        static VisualElement Rule()
        {
            var v = new VisualElement();
            v.AddToClassList("day-rule");
            return v;
        }

        // ── 內容 ────────────────────────────────────────────────

        void Refresh()
        {
            var d = DailyLog.Last;
            if (d == null) return;

            dateLabel.text = $"第 {d.day} 天　{TimeSystem.DateTextOf(d.day)}";

            noteLabel.text = d.collapsed ? "撐到 02:00 才倒下 —— 下次早點睡吧。" : "";
            noteLabel.style.display = d.collapsed ? DisplayStyle.Flex : DisplayStyle.None;

            if (skin) { RefreshSkin(d); return; }

            statBox.Clear();
            statBox.Add(Row("店內營收", $"+{d.revenue} G", d.revenue > 0 ? "day-plus" : null));
            statBox.Add(Row("賣出件數", $"{d.sales} 件", null));
            if (d.trade > 0)    statBox.Add(Row("材料收購", $"+{d.trade} G", "day-plus"));
            if (d.spent > 0)    statBox.Add(Row("支出", $"-{d.spent} G", "day-minus"));
            if (d.gathered > 0) statBox.Add(Row("採集", $"{d.gathered} 個", null));
            if (d.brewed > 0)   statBox.Add(Row("煉製", $"{d.brewed} 瓶", null));
            if (d.rep > 0)
                statBox.Add(Row("名聲", $"+{d.rep}　Lv.{Reputation.Level} {Reputation.Title}", "day-plus"));

            listBox.Clear();
            if (d.items == null || d.items.Count == 0)
            {
                var empty = new Label("今天沒有客人買走東西。");
                empty.AddToClassList("day-empty");
                listBox.Add(empty);
            }
            else
            {
                foreach (var e in d.items) listBox.Add(SaleRow(e));
            }

            int net = d.revenue + d.trade - d.spent;
            netLabel.text = $"淨收入　{(net < 0 ? "-" : "+")}{Mathf.Abs(net)} G";
            netLabel.EnableInClassList("day-plus", net > 0);
            netLabel.EnableInClassList("day-minus", net < 0);

            goldLabel.text = $"目前金幣　{Wallet.Gold} G";
        }

        /// <summary>像素外觀的內容：數字小卡、明細小卡、淨收入、持有。</summary>
        void RefreshSkin(DayRecord d)
        {
            statBox.Clear();
            int n = 0;
            void Tile(VisualElement icon, string num, string cap, string numClass)
            {
                var t = new VisualElement();
                t.AddToClassList("sk-day-tile");
                if (++n % 3 == 0) t.AddToClassList("sk-day-tile--end");   // 每列第 3 格不留右邊距（USS 沒有 :nth-child）
                var ib = new VisualElement();
                ib.AddToClassList("sk-day-ico");
                ib.Add(icon);
                t.Add(ib);
                var tx = new VisualElement();
                tx.AddToClassList("sk-day-tile-text");
                var nl = new Label(num);
                nl.AddToClassList("sk-day-num");
                if (numClass != null) nl.AddToClassList(numClass);
                tx.Add(nl);
                var cl = new Label(cap);
                cl.AddToClassList("sk-day-cap");
                tx.Add(cl);
                t.Add(tx);
                statBox.Add(t);
            }
            Tile(UiSkin.Coin(), $"+{d.revenue}", "營收", d.revenue > 0 ? "day-plus" : null);
            Tile(UiSkin.Ico("basket"), d.sales.ToString(), "賣出", null);
            if (d.trade > 0)    Tile(UiSkin.Ico("sack"), $"+{d.trade}", "收購", "day-plus");
            if (d.spent > 0)    Tile(UiSkin.Coin(), $"-{d.spent}", "支出", "day-minus");
            if (d.gathered > 0) Tile(UiSkin.Ico("leaf"), d.gathered.ToString(), "採集", null);
            if (d.brewed > 0)   Tile(UiSkin.Ico("flask"), d.brewed.ToString(), "煉製", null);
            if (d.rep > 0)      Tile(UiSkin.Ico("star"), $"+{d.rep}", $"名聲 Lv.{Reputation.Level}", "day-plus");

            listBox.Clear();
            if (d.items == null || d.items.Count == 0)
            {
                var empty = new Label("今天沒有客人買走東西。");
                empty.AddToClassList("day-empty");
                listBox.Add(empty);
            }
            else
            {
                int i = 0;
                foreach (var e in d.items)
                {
                    var row = SkinSaleRow(e);
                    row.EnableInClassList("sk-alt", (i++ & 1) == 1);   // 交錯列
                    listBox.Add(row);
                }
            }

            int net = d.revenue + d.trade - d.spent;
            goldLabel.text = $"{(net < 0 ? "-" : "+")}{Mathf.Abs(net)}";
            goldLabel.EnableInClassList("day-plus", net > 0);
            goldLabel.EnableInClassList("day-minus", net < 0);
            walletLabel.text = UiSkin.MoneyText(Wallet.Gold);
        }

        /// <summary>像素外觀的明細一列：[道具圖][名稱][×n 徽章][金幣 金額]。</summary>
        static VisualElement SkinSaleRow(SaleEntry e)
        {
            var row = new VisualElement();
            row.AddToClassList("day-item");

            var icon = new VisualElement();
            icon.AddToClassList("day-icon");
            var sp = GameArt.Item(e.name);
            if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
            row.Add(icon);

            var name = new Label(e.name);
            name.AddToClassList("day-item-name");
            name.style.flexGrow = 1;
            row.Add(name);

            var qty = new VisualElement();
            qty.AddToClassList("sk-day-qty");
            qty.Add(UiSkin.Badge("×" + e.q));
            row.Add(qty);

            var gold = new VisualElement();
            gold.AddToClassList("sk-day-gold");
            gold.Add(UiSkin.Money(e.g, "sk-day-goldnum"));
            row.Add(gold);

            return row;
        }

        /// <summary>一列「項目 —— 數字」。</summary>
        static VisualElement Row(string key, string val, string valClass)
        {
            var row = new VisualElement();
            row.AddToClassList("day-row");

            var k = new Label(key);
            k.AddToClassList("day-key");
            row.Add(k);

            var v = new Label(val);
            v.AddToClassList("day-val");
            if (!string.IsNullOrEmpty(valClass)) v.AddToClassList(valClass);
            row.Add(v);

            return row;
        }

        /// <summary>賣出明細的一列：圖示＋品名＋件數＋金額。</summary>
        static VisualElement SaleRow(SaleEntry e)
        {
            var row = new VisualElement();
            row.AddToClassList("day-item");

            var icon = new VisualElement();
            icon.AddToClassList("day-icon");
            var sp = GameArt.Item(e.name);
            if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
            row.Add(icon);

            var name = new Label(e.name);
            name.AddToClassList("day-item-name");
            row.Add(name);

            var qty = new Label($"× {e.q}");
            qty.AddToClassList("day-item-qty");
            row.Add(qty);

            var gold = new Label($"{e.g} G");
            gold.AddToClassList("day-item-gold");
            row.Add(gold);

            return row;
        }
    }
}
