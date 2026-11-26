using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>
    /// 任務簿（按 Q 開）—— **靠畫面右側的羊皮紙捲軸**，不是置中的視窗。
    ///
    /// 只列「已接的任務」（進行中＋可回報）；還沒接的、已完成的都不列 ——
    /// 那些去找 NPC 談就好，捲軸是給玩家隨時瞄一眼「我現在該做什麼」。
    ///
    /// 這裡**只看不做**：接任務和回報都要回去找發任務的人（見 TalkNpc），
    /// 所以每一條會標「去找誰」。
    ///
    /// ⚠️ 字要用**深墨色**（rgb(88,52,32) 那組）—— 底是米色羊皮紙，
    ///    用平常那套淺色字會完全看不見。同樣的坑在時鐘的月/日數字踩過一次。
    ///
    /// ── 像素外觀（<see cref="UiSkin.On"/>）──────────────────────────
    /// 底換成 skin8 的羊皮紙卷軸（scroll-paper 九宮格：上下兩根木軸），標題是紫布緞帶、關閉是 skin 的紅鈕。
    /// 每條任務是一張清單列卡片，能用圖的不用句子：
    ///   [勾選框][任務名]　／　[動詞][目標道具圖][進度條][2/5]　／　[→ 發任務的人]……[金幣 30][獎勵道具 ×1]
    /// 可回報＝金框卡＋打勾＋金色進度條。底下 [Q][Esc] 關閉 …… 頁數。
    /// 外觀關著時照舊（quest-scroll.png 底圖＋整句文字）。
    /// </summary>
    public class QuestPanel : MonoBehaviour
    {
        public static QuestPanel Instance { get; private set; }

        public static QuestPanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("QuestUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<QuestPanel>();
        }

        /// <summary>一頁列幾條（超過就翻頁）。</summary>
        const int PerPage = 5;

        UIDocument doc;
        VisualElement root, scroll, listBox;
        Label footLabel;
        int page;
        bool built;
        bool skin;        // 這次用的是不是像素外觀（Build 時決定）
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 12;
            if (doc.panelSettings == null)
                Debug.LogError("[QuestPanel] 找不到 Resources/ui/UIPanelSettings");
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
            // Q 或 Esc 都能關 —— 開的那顆鍵也能關，是最直覺的。
            // ⚠️ 「開」在 PlayerController.Update、「關」在這裡，Unity 不保證兩邊誰先跑：
            //    PlayerController 先跑的話，開的那一幀這裡又讀到同一下 Q → 開了立刻關。
            if (anim.OpenedThisFrame) return;
            if (Input.GetKeyDown(KeyCode.Escape) || Input.GetKeyDown(KeyCode.Q)) Close();
        }

        public bool IsOpen => built && anim != null && anim.IsOpen;   // ⚠️ 不看 display：關閉動畫期間它還是 Flex

        public void Open()
        {
            if (!built) Build();
            if (!built) return;
            // ⚠️ 反方向的同一個問題：這裡先跑、按 Q 關掉並解除 ModalOpen，同一幀
            //    PlayerController 又讀到那一下 Q 來開 → 關了立刻重開。關掉的那一幀不重開。
            if (anim.ClosedThisFrame) return;
            page = 0;
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

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[QuestPanel] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            UiSkin.Apply(root);           // 8-bit 外觀（總開關 UiSkin.Enabled）
            skin = UiSkin.On;
            CjkFont.Apply(root);
            Sfx.BindClicks(root);         // 所有按鈕的 click 音

            var layer = new VisualElement();
            layer.AddToClassList("quest-layer");
            root.Add(layer);

            scroll = new VisualElement();
            scroll.AddToClassList("quest-scroll");
            // 底板：像素外觀＝Skin8 的 scroll-paper（這裡不寫 inline —— inline 的優先權比 uss 高，會把它蓋掉）；
            // 舊外觀：有捲軸美術就用它，沒有的話退回一張米色羊皮紙
            var frame = GameArt.QuestScroll;
            if (skin) { }
            else if (frame != null) scroll.style.backgroundImage = new StyleBackground(frame);
            else
            {
                scroll.style.backgroundColor = new Color(226 / 255f, 210 / 255f, 170 / 255f, 0.98f);
                scroll.style.borderTopWidth = scroll.style.borderBottomWidth =
                    scroll.style.borderLeftWidth = scroll.style.borderRightWidth = 4;
                var brown = new Color(120 / 255f, 90 / 255f, 60 / 255f);
                scroll.style.borderTopColor = scroll.style.borderBottomColor =
                    scroll.style.borderLeftColor = scroll.style.borderRightColor = brown;
            }
            layer.Add(scroll);

            var title = new Label("任務簿");
            title.AddToClassList("quest-title");
            scroll.Add(title);

            if (!skin)                    // 像素外觀：標題是緞帶，不需要底下那條線
            {
                var rule = new VisualElement();
                rule.AddToClassList("quest-rule");
                scroll.Add(rule);
            }

            listBox = new VisualElement();
            listBox.AddToClassList("quest-list");
            scroll.Add(listBox);

            if (skin)
                footLabel = UiSkin.Footer(scroll, "關閉", "Q", "Esc");   // [Q][Esc] 關閉 …… 頁數
            else
            {
                footLabel = new Label();
                footLabel.AddToClassList("quest-foot");
                scroll.Add(footLabel);
            }

            var close = new Button(Close) { text = "×", focusable = false };
            close.AddToClassList("quest-close");
            scroll.Add(close);

            root.style.display = DisplayStyle.None;
            anim = UIAnim.SlideRight(root, scroll);           // 靠右的捲軸：從右邊滑進來（縮放不適合貼邊的東西）
            built = true;
        }

        void Refresh()
        {
            listBox.Clear();
            var ids = QuestLog.AcceptedIds();

            if (ids.Count == 0)
            {
                var msg = new Label("目前沒有\n進行中的任務。\n\n去城鎮找頭頂\n有「！」的\nNPC 聊聊吧！");
                msg.AddToClassList("quest-empty");
                listBox.Add(msg);
                footLabel.text = skin ? "" : "Q / Esc 關閉";
                return;
            }

            int pages = Mathf.Max(1, Mathf.CeilToInt(ids.Count / (float)PerPage));
            page = Mathf.Clamp(page, 0, pages - 1);

            for (int i = page * PerPage; i < ids.Count && i < (page + 1) * PerPage; i++)
                listBox.Add(skin ? SkinEntry(ids[i]) : Entry(ids[i]));

            if (skin)
                footLabel.text = pages > 1 ? $"‹ {page + 1}/{pages} ›" : "";   // 關閉的鍵帽已經在左邊
            else
                footLabel.text = pages > 1
                    ? $"‹ {page + 1} / {pages} ›　（← → 翻頁）　Q / Esc 關閉"
                    : "Q / Esc 關閉";

            // 多頁時用左右鍵翻
            if (pages > 1)
            {
                if (Input.GetKeyDown(KeyCode.LeftArrow) && page > 0) { page--; Refresh(); }
                if (Input.GetKeyDown(KeyCode.RightArrow) && page < pages - 1) { page++; Refresh(); }
            }
        }

        /// <summary>一條任務：名稱／目標＋進度／狀態＋獎勵＋去找誰。</summary>
        VisualElement Entry(string id)
        {
            var d = QuestLog.Def(id);
            var box = new VisualElement();
            box.AddToClassList("quest-entry");
            if (d == null) return box;

            bool ready = QuestLog.StatusOf(id) == QuestStatus.Ready;

            var title = new Label((ready ? "✓ " : "· ") + d.Title);
            title.AddToClassList("quest-entry-title");
            if (ready) title.AddToClassList("quest-ready");
            box.Add(title);

            var obj = new Label($"{QuestLog.ObjectiveText(d)}　{QuestLog.ProgressText(id)}");
            obj.AddToClassList("quest-entry-obj");
            box.Add(obj);

            var sub = new Label(ready
                ? $"可回報 → 找 {d.Giver}　賞 {QuestLog.RewardText(d)}"
                : $"找 {d.Giver}　賞 {QuestLog.RewardText(d)}");
            sub.AddToClassList("quest-entry-sub");
            if (ready) sub.AddToClassList("quest-ready");
            box.Add(sub);

            return box;
        }

        /// <summary>
        /// 像素外觀的一條任務（清單列卡片，三行）：
        ///   [勾選框][任務名]
        ///   [動詞][目標道具圖][進度條][2/5]
        ///   [→ 發任務的人] …… [金幣 30][獎勵道具 ×1]
        /// 可回報：卡片換金框（sk-q-ready）、勾選框打勾、進度條變金色。
        /// </summary>
        VisualElement SkinEntry(string id)
        {
            var d = QuestLog.Def(id);
            var box = new VisualElement();
            box.AddToClassList("quest-entry");
            if (d == null) return box;

            bool ready = QuestLog.StatusOf(id) == QuestStatus.Ready;
            box.EnableInClassList("sk-q-ready", ready);

            // ① [勾選框][任務名]
            var l1 = Line(box, "sk-q-line--1");
            var check = new VisualElement();
            check.AddToClassList("sk-q-box");
            l1.Add(check);
            var title = new Label(d.Title);
            title.AddToClassList("sk-q-title");
            l1.Add(title);

            // ② [動詞][目標圖][進度條][2/5]
            var o = d.Objective;
            var l2 = Line(box, "sk-q-line--2");
            var verb = new Label(VerbOf(o.Kind));
            verb.AddToClassList("sk-q-verb");
            l2.Add(verb);
            l2.Add(TargetIcon(o));
            var bar = new VisualElement();
            bar.AddToClassList("sk-q-bar");
            var fill = new VisualElement();
            fill.AddToClassList("sk-q-fill");
            float frac = o.Count > 0 ? Mathf.Clamp01(QuestLog.Progress(id) / (float)o.Count) : 1f;
            fill.style.width = Length.Percent(frac * 100f);
            bar.Add(fill);
            l2.Add(bar);
            var num = new Label(QuestLog.ProgressText(id));
            num.AddToClassList("sk-q-num");
            l2.Add(num);

            // ③ [→ 誰] …… [獎勵]
            var l3 = Line(box, "sk-q-line--3");
            l3.Add(UiSkin.Ico("arrow"));
            var giver = new Label(d.Giver);
            giver.AddToClassList("sk-q-giver");
            l3.Add(giver);
            var reward = new VisualElement();
            reward.AddToClassList("sk-q-reward");
            if (d.RewardGold > 0) reward.Add(UiSkin.Money(d.RewardGold, "sk-q-rewardnum"));
            if (!string.IsNullOrEmpty(d.RewardItem) && d.RewardQty > 0)
                reward.Add(UiSkin.IconCount(GameArt.Item(d.RewardItem), "×" + d.RewardQty));
            l3.Add(reward);

            return box;
        }

        static VisualElement Line(VisualElement box, string cls)
        {
            var l = new VisualElement();
            l.AddToClassList("sk-q-line");
            l.AddToClassList(cls);
            box.Add(l);
            return l;
        }

        /// <summary>目標動詞（同 QuestLog.ObjectiveText 的那組，只是不帶道具名與數量 —— 那兩個改用圖與進度表達）。</summary>
        static string VerbOf(ObjKind k)
        {
            switch (k)
            {
                case ObjKind.Gather: return "採集";
                case ObjKind.Sell: return "賣出";
                case ObjKind.Brew: return "調配";
                case ObjKind.Have: return "備齊";
                default: return "存到";
            }
        }

        /// <summary>目標的圖：指定道具＝道具圖；存錢＝金幣；沒指定道具時依種類給一個通用圖（賣＝籃子、調配＝藥瓶、其他＝葉子）。</summary>
        static VisualElement TargetIcon(QuestObjective o)
        {
            if (o.Kind == ObjKind.Gold) return UiSkin.Coin();
            var sp = string.IsNullOrEmpty(o.Item) ? null : GameArt.Item(o.Item);
            if (sp != null)
            {
                var ic = new VisualElement();
                ic.AddToClassList("sk-q-icon");
                ic.style.backgroundImage = new StyleBackground(sp);
                return ic;
            }
            return UiSkin.Ico(o.Kind == ObjKind.Sell ? "basket" : o.Kind == ObjKind.Brew ? "flask" : "leaf");
        }
    }
}
