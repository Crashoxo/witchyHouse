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

        UIDocument doc;
        VisualElement root, tabsBox;
        ScrollView rowsBox;
        Label titleLabel, hintLabel;
        Tab tab = Tab.Quests;
        bool built;

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
            if (root != null && root.style.display == DisplayStyle.Flex) UIState.ModalOpen = false;
        }

        void Update()
        {
            if (!built || root == null) return;
            if (root.style.display != DisplayStyle.Flex) return;
            if (Input.GetKeyDown(KeyCode.Escape) || Input.GetKeyDown(KeyCode.Tab)
                || Input.GetKeyDown(KeyCode.I)) Close();
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
            if (root == null) { Debug.LogError("[PlayerInfoPanel] 沒有 rootVisualElement"); return; }
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
                var b = new Button(() => { tab = tt; Refresh(); }) { text = label };
                b.AddToClassList("tab");
                b.userData = tt;
                tabsBox.Add(b);
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

        void Refresh()
        {
            foreach (var b in tabsBox.Children()) b.EnableInClassList("active", (Tab)b.userData == tab);
            rowsBox.Clear();

            switch (tab)
            {
                case Tab.Quests: BuildQuests(); break;
                case Tab.Items: BuildItems(); break;
                case Tab.Villagers: BuildVillagers(); break;
                case Tab.Calendar: BuildCalendar(); break;
            }
        }

        // ──────────── 任務 ────────────

        void BuildQuests()
        {
            hintLabel.text = "Tab / Esc 關閉 · 接任務與回報都要找發任務的人談（按 Q 可看右側捲軸）";

            // 排序：可回報 → 進行中 → 可接 → 已完成。鎖住的不列（玩家還不知道它存在）
            var order = new[] { QuestStatus.Ready, QuestStatus.Active,
                                QuestStatus.Available, QuestStatus.Claimed };
            bool any = false;

            foreach (var want in order)
                foreach (var d in QuestLog.Defs())
                {
                    if (QuestLog.StatusOf(d.Id) != want) continue;
                    any = true;
                    rowsBox.Add(QuestRow(d, want));
                }

            if (!any)
            {
                var msg = new Label("還沒有任務 —— 去城鎮找頭頂有「？」的人聊聊吧");
                msg.AddToClassList("empty-msg");
                rowsBox.Add(msg);
            }
        }

        VisualElement QuestRow(QuestDef d, QuestStatus st)
        {
            var row = new VisualElement();
            row.AddToClassList("row");
            row.style.height = 56;

            var (tag, color) = st switch
            {
                QuestStatus.Ready     => ("可回報", new Color(1f, 0.87f, 0.45f)),
                QuestStatus.Active    => ("進行中", new Color(0.78f, 0.90f, 0.78f)),
                QuestStatus.Available => ("可接",   new Color(0.72f, 0.86f, 0.95f)),
                _                     => ("已完成", new Color(0.52f, 0.50f, 0.48f)),
            };

            var tagLabel = new Label(tag);
            tagLabel.style.width = 58;
            tagLabel.style.fontSize = 15;
            tagLabel.style.color = color;
            tagLabel.style.unityTextAlign = TextAnchor.MiddleCenter;
            row.Add(tagLabel);

            var title = new Label(d.Title);
            title.AddToClassList("col-name");
            title.style.width = 105;
            if (st == QuestStatus.Claimed) title.style.color = new Color(0.52f, 0.50f, 0.48f);
            row.Add(title);

            var obj = new Label(QuestLog.ObjectiveText(d));
            obj.AddToClassList("up-desc");
            row.Add(obj);

            var prog = new Label(st == QuestStatus.Claimed ? "—" : QuestLog.ProgressText(d.Id));
            prog.AddToClassList("up-effect");
            prog.style.width = 66;
            row.Add(prog);

            var reward = new Label(QuestLog.RewardText(d));
            reward.AddToClassList("col-price");
            reward.style.width = 118;
            row.Add(reward);

            var giver = new Label(st == QuestStatus.Claimed ? "" : $"找 {d.Giver}");
            giver.style.width = 96;
            giver.style.fontSize = 15;
            giver.style.color = new Color(0.72f, 0.69f, 0.65f);
            giver.style.unityTextAlign = TextAnchor.MiddleCenter;
            row.Add(giver);

            return row;
        }

        // ──────────── 物品圖鑑 ────────────

        void BuildItems()
        {
            hintLabel.text = "Tab / Esc 關閉 · 手上或倉庫裡有的東西才會列出來";

            int shown = 0;
            foreach (var name in AllItemNames())
            {
                // 沒拿過的不劇透 —— 圖鑑要靠玩才會慢慢長出來
                if (Storage.AvailableOf(name) <= 0 && ShopStock.CountOf(name) <= 0) continue;
                shown++;

                var row = new VisualElement();
                row.AddToClassList("row");
                row.style.height = 52;

                var icon = new VisualElement();
                icon.style.width = 34; icon.style.height = 34; icon.style.marginRight = 8;
                var sp = GameArt.Item(name);
                if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
                row.Add(icon);

                var n = new Label(name);
                n.AddToClassList("col-name");
                n.style.width = 110;
                row.Add(n);

                var have = new Label($"×{Storage.AvailableOf(name)}");
                have.AddToClassList("col-bag");
                row.Add(have);

                var desc = new Label(Items.DescOf(name));
                desc.AddToClassList("up-desc");
                row.Add(desc);

                rowsBox.Add(row);
            }

            if (shown == 0)
            {
                var msg = new Label("還沒有任何東西 —— 去森林採集看看吧");
                msg.AddToClassList("empty-msg");
                rowsBox.Add(msg);
            }
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
            hintLabel.text = $"Tab / Esc 關閉 · 每天第一次跟同一個人聊天 +{Villagers.TalkPoints} 友誼";

            foreach (var v in Villagers.All)
            {
                var row = new VisualElement();
                row.AddToClassList("row");
                row.style.height = 62;

                var icon = new VisualElement();
                icon.style.width = 44; icon.style.height = 44; icon.style.marginRight = 10;
                var sp = string.IsNullOrEmpty(v.Portrait) ? null : GameArt.Portrait(v.Portrait);
                if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
                row.Add(icon);

                var n = new Label(v.Name);
                n.AddToClassList("col-name");
                n.style.width = 100;
                row.Add(n);

                var place = new Label(v.Place);
                place.AddToClassList("up-effect");
                place.style.width = 90;
                row.Add(place);

                var desc = new Label(v.Desc);
                desc.AddToClassList("up-desc");
                row.Add(desc);

                // 友誼度用實心/空心愛心表示
                int hearts = Friendship.Hearts(v.Name);
                var h = new Label(new string('♥', hearts) + new string('♡', Villagers.MaxHearts - hearts));
                h.AddToClassList("col-price");
                h.style.width = 100;
                h.style.color = new Color(1f, 0.55f, 0.62f);
                row.Add(h);

                rowsBox.Add(row);
            }
        }

        // ──────────── 日曆 ────────────

        void BuildCalendar()
        {
            var f = TimeSystem.FestivalToday();
            hintLabel.text = f != null
                ? $"Tab / Esc 關閉 · 今天是「{f.Name}」—— {f.Desc}"
                : "Tab / Esc 關閉 · 節日當天客人特別多";

            var head = new Label(
                $"{TimeSystem.DateTextFull()}　·　{TimeSystem.SeasonDef.Desc}");
            head.AddToClassList("up-desc");
            head.style.fontSize = 18;
            head.style.marginBottom = 8;
            rowsBox.Add(head);

            // 一個月 28 天，排成 4 列 × 7 格
            int today = TimeSystem.Day, month = TimeSystem.Month;
            for (int r = 0; r < 4; r++)
            {
                var line = new VisualElement();
                line.style.flexDirection = FlexDirection.Row;
                line.style.marginBottom = 6;

                for (int c = 0; c < 7; c++)
                {
                    int day = r * 7 + c + 1;
                    var fest = Seasons.FestivalOn(month, day);

                    var cell = new VisualElement();
                    cell.style.width = 88;
                    cell.style.height = 54;
                    cell.style.marginRight = 6;
                    cell.style.paddingLeft = 6;
                    cell.style.justifyContent = Justify.Center;
                    cell.style.borderTopWidth = cell.style.borderBottomWidth =
                        cell.style.borderLeftWidth = cell.style.borderRightWidth = 2;

                    bool isToday = day == today;
                    var border = isToday ? new Color(1f, 0.88f, 0.5f)
                               : fest != null ? new Color(0.62f, 0.86f, 0.68f)
                               : new Color(1f, 1f, 1f, 0.12f);
                    cell.style.borderTopColor = cell.style.borderBottomColor =
                        cell.style.borderLeftColor = cell.style.borderRightColor = border;
                    if (isToday) cell.style.backgroundColor = new Color(1f, 0.88f, 0.5f, 0.12f);

                    var dl = new Label(day.ToString());
                    dl.style.fontSize = 17;
                    dl.style.color = isToday ? new Color(1f, 0.9f, 0.6f) : new Color(0.83f, 0.80f, 0.76f);
                    cell.Add(dl);

                    if (fest != null)
                    {
                        var fl = new Label(fest.Name);
                        fl.style.fontSize = 12;
                        fl.style.color = new Color(0.68f, 0.92f, 0.74f);
                        fl.style.whiteSpace = WhiteSpace.Normal;
                        cell.Add(fl);
                    }

                    line.Add(cell);
                }
                rowsBox.Add(line);
            }

            // 下一個節日
            var next = TimeSystem.NextFestivalFrom(month, today);
            if (next != null)
            {
                var nl = new Label($"下一個節日：{next.Name}（{next.Month} 月 {next.Day} 日）—— {next.Desc}");
                nl.AddToClassList("up-desc");
                nl.style.marginTop = 10;
                rowsBox.Add(nl);
            }
        }
    }
}
