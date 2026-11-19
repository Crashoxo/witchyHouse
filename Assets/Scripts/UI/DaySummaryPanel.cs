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
            CjkFont.Apply(root);

            var layer = new VisualElement();
            layer.AddToClassList("day-layer");
            root.Add(layer);

            card = new VisualElement();
            card.AddToClassList("day-card");
            layer.Add(card);

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

            root.style.display = DisplayStyle.None;
            anim = UIAnim.Pop(root, card);                    // 黑幕是 SleepOverlay 的，這裡只動帳單本身
            built = true;
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
