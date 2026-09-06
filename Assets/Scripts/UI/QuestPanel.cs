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
            if (root != null && root.style.display == DisplayStyle.Flex) UIState.ModalOpen = false;
        }

        void Update()
        {
            if (!built || root == null) return;
            if (root.style.display != DisplayStyle.Flex) return;
            // Q 或 Esc 都能關 —— 開的那顆鍵也能關，是最直覺的
            if (Input.GetKeyDown(KeyCode.Escape) || Input.GetKeyDown(KeyCode.Q)) Close();
        }

        public bool IsOpen => built && root != null && root.style.display == DisplayStyle.Flex;

        public void Open()
        {
            if (!built) Build();
            if (!built) return;
            page = 0;
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
            if (root == null) { Debug.LogError("[QuestPanel] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            CjkFont.Apply(root);

            var layer = new VisualElement();
            layer.AddToClassList("quest-layer");
            root.Add(layer);

            scroll = new VisualElement();
            scroll.AddToClassList("quest-scroll");
            // 底板：有捲軸美術就用它，沒有的話退回一張米色羊皮紙
            var frame = GameArt.QuestScroll;
            if (frame != null) scroll.style.backgroundImage = new StyleBackground(frame);
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

            var rule = new VisualElement();
            rule.AddToClassList("quest-rule");
            scroll.Add(rule);

            listBox = new VisualElement();
            listBox.AddToClassList("quest-list");
            scroll.Add(listBox);

            footLabel = new Label();
            footLabel.AddToClassList("quest-foot");
            scroll.Add(footLabel);

            var close = new Button(Close) { text = "×" };
            close.AddToClassList("quest-close");
            scroll.Add(close);

            root.style.display = DisplayStyle.None;
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
                footLabel.text = "Q / Esc 關閉";
                return;
            }

            int pages = Mathf.Max(1, Mathf.CeilToInt(ids.Count / (float)PerPage));
            page = Mathf.Clamp(page, 0, pages - 1);

            for (int i = page * PerPage; i < ids.Count && i < (page + 1) * PerPage; i++)
                listBox.Add(Entry(ids[i]));

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
    }
}
