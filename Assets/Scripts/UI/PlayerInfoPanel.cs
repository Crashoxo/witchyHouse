using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>
    /// 玩家資訊面板（按 Tab 或 I 開），四個分頁：
    ///   任務 —— 所有任務的狀態（可回報/進行中/可接/已完成）
    ///   物品 —— 每樣東西的說明（圖鑑），已經拿過的才列
    ///   村民 —— 認識的人、住哪、友誼度幾顆心
    ///   日曆 —— 這個月的日期格，標出今天與節日
    ///
    /// ⚠️ 跟按 Q 的任務簿不一樣：那個是**右側的捲軸**，只列進行中的任務，
    ///    是玩的時候隨時瞄一眼用的；這裡是完整清單，含已完成的。
    ///
    /// ⚠️ Tab 鍵在瀏覽器（WebGL）裡常被拿去切換焦點，所以 I 也能開，兩個鍵等價 ——
    ///    原專案就是為了這個才留兩顆鍵的。
    /// </summary>
    public class PlayerInfoPanel : MonoBehaviour
    {
        public static PlayerInfoPanel Instance { get; private set; }

        public static PlayerInfoPanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("PlayerInfoUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<PlayerInfoPanel>();
        }

        enum Tab { Quests, Items, Villagers, Calendar }

        /// <summary>
        /// 清單區固定高（2026-11-27 改成固定高度＋翻頁，見 <see cref="Pager"/>）：6 × 60 ＝ 360。
        /// 任務／物品一頁 6 列（`.sk .row` 57 ＋ 3）；村民列比較高（`.sk .vil-row` 63 ＋ 3 ＝ 66）一頁 5 列；
        /// 日曆不是清單，整張（標題 ≈30 ＋ 4 × 60 ＋ 下一個節日 ≈30～50）放在同一塊裡，不翻頁。
        /// 面板高（像素外觀）＝ padding 30 ＋ 標題列 5 ＋ 分頁 48 ＋ 360 ＋ 分隔線 18 ＋ 底列 30 ＋ padding 24 ＝ 515。
        /// </summary>
        const int ListH = 360;
        const int RowsPerPage = 6;
        const int VillagersPerPage = 5;

        UIDocument doc;
        VisualElement root, tabsBox;
        VisualElement rowsBox;       // ＝ pager.Body
        Pager pager;
        Label titleLabel, hintLabel;
        Tab tab = Tab.Quests;
        bool built;
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 12;
            if (doc.panelSettings == null)
                Debug.LogError("[PlayerInfoPanel] 找不到 Resources/ui/UIPanelSettings");
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
            // ⚠️ Tab/I 開關同一顆鍵，「開」在 PlayerController.Update —— 誰先跑不一定，
            //    開的那一幀不吃鍵，不然可能開了立刻關（同 QuestPanel）
            if (anim.OpenedThisFrame) return;
            if (Input.GetKeyDown(KeyCode.Escape) || Input.GetKeyDown(KeyCode.Tab)
                || Input.GetKeyDown(KeyCode.I)) Close();
            else pager.HandleKeys();     // ←／→、A／D 翻頁
        }

        public void Open()
        {
            if (!built) Build();
            if (!built) return;
            if (anim.ClosedThisFrame) return;     // 這一幀才用 Tab/I 關掉的，別被同一下又打開（同 QuestPanel）
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

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[PlayerInfoPanel] 沒有 rootVisualElement"); return; }
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

            titleLabel = new Label("女巫的手札");
            titleLabel.AddToClassList("title");
            header.Add(titleLabel);

            var spacer = new VisualElement();
            spacer.AddToClassList("spacer");
            header.Add(spacer);

            var close = new Button(Close) { text = "×" };
            close.AddToClassList("close");
            header.Add(close);

            tabsBox = new VisualElement();
            tabsBox.AddToClassList("tabs");
            panel.Add(tabsBox);
            foreach (var (label, t) in new[]
                     {
                         ("任務", Tab.Quests), ("物品", Tab.Items),
                         ("村民", Tab.Villagers), ("日曆", Tab.Calendar),
                     })
            {
                var tt = t;
                var b = new Button(() => { tab = tt; pager.Reset(); Sfx.Play("ui-tab"); Refresh(); }) { text = label };
                b.AddToClassList("tab");
                b.userData = tt;
                tabsBox.Add(b);
            }

            // 清單：固定高、超過就翻頁（不捲動）
            pager = new Pager(RowsPerPage, ListH, Refresh);
            rowsBox = pager.Body;
            rowsBox.AddToClassList("rows");
            panel.Add(rowsBox);

            hintLabel = UiSkin.Footer(panel, "關閉", "Tab", "Esc");   // [Tab][Esc] 關閉 ……… 右邊放短資訊
            pager.Bar.AddToClassList("pg-bar--center");                // 翻頁鈕擺在底列正中間
            hintLabel.parent.Add(pager.Bar);

            root.style.display = DisplayStyle.None;
            anim = UIAnim.Pop(root, panel, dim);              // 淡入＋輕微放大，暗幕只淡入
            built = true;
        }

        void Refresh()
        {
            foreach (var b in tabsBox.Children()) b.EnableInClassList("active", (Tab)b.userData == tab);
            pager.SetPerPage(tab == Tab.Villagers ? VillagersPerPage : RowsPerPage);

            switch (tab)
            {
                case Tab.Quests: BuildQuests(); break;
                case Tab.Items: BuildItems(); break;
                case Tab.Villagers: BuildVillagers(); break;
                case Tab.Calendar: BuildCalendar(); break;
            }
            UiSkin.Stripe(rowsBox);
        }

        // ──────────── 任務 ────────────

        void BuildQuests()
        {
            hintLabel.text = "找發任務的人回報 · Q 看捲軸";

            // 排序：可回報 → 進行中 → 可接 → 已完成。鎖住的不列（玩家還不知道它存在）
            var order = new[] { QuestStatus.Ready, QuestStatus.Active,
                                QuestStatus.Available, QuestStatus.Claimed };
            var list = new System.Collections.Generic.List<(QuestDef def, QuestStatus st)>();

            foreach (var want in order)
                foreach (var d in QuestLog.Defs())
                {
                    if (QuestLog.StatusOf(d.Id) != want) continue;
                    list.Add((d, want));
                }

            pager.Render(list.Count, i => QuestRow(list[i].def, list[i].st),
                "還沒有任務 —— 去城鎮找頭頂有「？」的人聊聊吧");
        }

        VisualElement QuestRow(QuestDef d, QuestStatus st)
        {
            var row = new VisualElement();
            row.AddToClassList("row");
            row.AddToClassList("quest-row");

            // ⚠️ 顏色一律走 class（SkinBase.uss 是舊配色、Skin8.uss 是彩色小膠囊）——
            //    以前寫成 inline style.color，換成淺色羊皮紙底之後蓋不掉、字就看不見了。
            var (tag, cls) = st switch
            {
                QuestStatus.Ready     => ("可回報", "quest-tag--ready"),
                QuestStatus.Active    => ("進行中", "quest-tag--active"),
                QuestStatus.Available => ("可接",   "quest-tag--avail"),
                _                     => ("已完成", "quest-tag--done"),
            };

            var tagLabel = new Label(tag);
            tagLabel.AddToClassList("quest-tag");
            tagLabel.AddToClassList(cls);
            row.Add(tagLabel);

            var title = new Label(d.Title);
            title.AddToClassList("col-name");
            title.AddToClassList("quest-title");
            if (st == QuestStatus.Claimed) title.AddToClassList("quest-title--done");
            row.Add(title);

            var obj = new Label(QuestLog.ObjectiveText(d));
            obj.AddToClassList("up-desc");
            row.Add(obj);

            var prog = new Label(st == QuestStatus.Claimed ? "—" : QuestLog.ProgressText(d.Id));
            prog.AddToClassList("up-effect");
            prog.AddToClassList("quest-prog");
            row.Add(prog);

            var reward = new Label(QuestLog.RewardText(d));
            reward.AddToClassList("col-price");
            reward.AddToClassList("quest-reward");
            row.Add(reward);

            var giver = new Label(st == QuestStatus.Claimed ? "" : $"找 {d.Giver}");
            giver.AddToClassList("quest-giver");
            row.Add(giver);

            return row;
        }

        // ──────────── 物品圖鑑 ────────────

        void BuildItems()
        {
            hintLabel.text = "拿過的才會列出來";

            var names = new System.Collections.Generic.List<string>();
            foreach (var name in AllItemNames())
            {
                // 沒拿過的不劇透 —— 圖鑑要靠玩才會慢慢長出來
                if (Storage.AvailableOf(name) <= 0 && ShopStock.CountOf(name) <= 0) continue;
                names.Add(name);
            }
            pager.Render(names.Count, i => ItemRow(names[i]), "還沒有任何東西 —— 去森林採集看看吧");
        }

        static VisualElement ItemRow(string name)
        {
            var row = new VisualElement();
            row.AddToClassList("row");
            row.AddToClassList("info-row");

            var icon = new VisualElement();
            icon.AddToClassList("stock-icon");
            var sp = GameArt.Item(name);
            if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
            row.Add(icon);

            var n = new Label(name);
            n.AddToClassList("col-name");
            n.AddToClassList("info-name");
            row.Add(n);

            // 數量：小徽章（舊外觀就是一個「×3」）
            var haveBox = new VisualElement();
            haveBox.AddToClassList("info-have");
            haveBox.Add(UiSkin.Badge($"×{Storage.AvailableOf(name)}"));
            row.Add(haveBox);

            var desc = new Label(Items.DescOf(name));
            desc.AddToClassList("up-desc");
            row.Add(desc);

            return row;
        }

        /// <summary>圖鑑的排列順序：材料 → 花與種子 → 藥水 → 糖果鎮的貨。</summary>
        static System.Collections.Generic.List<string> AllItemNames()
        {
            var all = new System.Collections.Generic.List<string>(Items.Materials);
            foreach (var f in GardenData.Flowers) { all.Add(f.Seed); all.Add(f.Flower); }
            foreach (var kv in Items.PotionItems) all.Add(kv.Key);
            foreach (var kv in Items.CandyItems) all.Add(kv.Key);
            return all;
        }

        // ──────────── 村民 ────────────

        void BuildVillagers()
        {
            hintLabel.text = $"每天第一次聊天 +{Villagers.TalkPoints} 友誼";

            var all = Villagers.All;
            pager.Render(all.Length, i => VillagerRow(all[i]));
        }

        static VisualElement VillagerRow(VillagerDef v)
        {
            var row = new VisualElement();
            row.AddToClassList("row");
            row.AddToClassList("vil-row");

            var icon = new VisualElement();
            icon.AddToClassList("vil-portrait");
            var sp = string.IsNullOrEmpty(v.Portrait) ? null : GameArt.Portrait(v.Portrait);
            if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
            row.Add(icon);

            var n = new Label(v.Name);
            n.AddToClassList("col-name");
            n.AddToClassList("vil-name");
            row.Add(n);

            var place = new Label(v.Place);
            place.AddToClassList("up-effect");
            place.AddToClassList("vil-place");
            row.Add(place);

            var desc = new Label(v.Desc);
            desc.AddToClassList("up-desc");
            row.Add(desc);

            // 友誼度：實心/空心愛心（外觀開著是小圖，關著退回 ♥♡ 文字）
            row.Add(UiSkin.Hearts(Friendship.Hearts(v.Name), Villagers.MaxHearts));

            return row;
        }

        // ──────────── 日曆 ────────────

        void BuildCalendar()
        {
            var f = TimeSystem.FestivalToday();
            hintLabel.text = f != null
                ? $"今天是「{f.Name}」"
                : "節日客人特別多";

            // 日曆不是清單：整張包成一塊交給翻頁器（永遠 1 頁 → 翻頁鈕藏起來）
            pager.Render(1, _ => CalendarSheet());
        }

        static VisualElement CalendarSheet()
        {
            var sheet = new VisualElement();
            var head = new Label(
                $"{TimeSystem.DateTextFull()}　·　{TimeSystem.SeasonDef.Desc}");
            head.AddToClassList("up-desc");
            head.AddToClassList("cal-head");
            sheet.Add(head);

            // 一個月 28 天，排成 4 列 × 7 格
            int today = TimeSystem.Day, month = TimeSystem.Month;
            for (int r = 0; r < 4; r++)
            {
                var line = new VisualElement();
                line.AddToClassList("cal-line");

                for (int c = 0; c < 7; c++)
                {
                    int day = r * 7 + c + 1;
                    var fest = Seasons.FestivalOn(month, day);

                    // 格子外觀全部走 class（SkinBase：舊的描邊格；Skin8：凹槽／節日卡／今天金框）——
                    // 以前是一整段 inline 顏色，換了淺色底之後蓋不掉。
                    bool isToday = day == today;
                    var cell = new VisualElement();
                    cell.AddToClassList("cal-cell");
                    if (fest != null) cell.AddToClassList("cal-cell--fest");
                    if (isToday) cell.AddToClassList("cal-cell--today");

                    var dl = new Label(day.ToString());
                    dl.AddToClassList("cal-day");
                    cell.Add(dl);

                    if (fest != null)
                    {
                        var fl = new Label(fest.Name);
                        fl.AddToClassList("cal-fest");
                        cell.Add(fl);
                    }

                    line.Add(cell);
                }
                sheet.Add(line);
            }

            // 下一個節日
            var next = TimeSystem.NextFestivalFrom(month, today);
            if (next != null)
            {
                var nl = new Label($"下一個節日：{next.Name}（{next.Month} 月 {next.Day} 日）—— {next.Desc}");
                nl.AddToClassList("up-desc");
                nl.AddToClassList("cal-next");
                sheet.Add(nl);
            }
            return sheet;
        }
    }
}
