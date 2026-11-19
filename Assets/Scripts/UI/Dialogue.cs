using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>對話框裡的一句話。可以附選項（附了就要選完才往下走）。</summary>
    public class DialogueLine
    {
        public string Text;
        public List<(string Label, Action OnPick)> Choices;

        public DialogueLine(string text) { Text = text; }
        public DialogueLine(string text, List<(string, Action)> choices) { Text = text; Choices = choices; }

        /// <summary>方便把純字串陣列轉成一串台詞。</summary>
        public static List<DialogueLine> Of(IEnumerable<string> texts)
        {
            var outList = new List<DialogueLine>();
            foreach (var t in texts) outList.Add(new DialogueLine(t));
            return outList;
        }
    }

    /// <summary>
    /// 畫面下方的對話框：頭像 ＋ 名字 ＋ 一句一句的台詞，最後可以附選項。
    ///
    /// 一般閒聊就是幾句話按過去；任務對話會在最後一句附「接受／再想想」這種選項
    /// （見 TalkNpc）。開著的時候是 modal —— 角色不動、時間暫停。
    ///
    /// 操作：**E 或空白鍵**往下一句（跟「跟東西互動」同一顆鍵，不用另外學），
    /// Esc 直接關掉。
    /// </summary>
    public class Dialogue : MonoBehaviour
    {
        public static Dialogue Instance { get; private set; }

        public static Dialogue Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("DialogueUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<Dialogue>();
        }

        UIDocument doc;
        VisualElement root, box, portraitEl, choicesBox;
        Label nameLabel, textLabel, nextLabel;

        List<DialogueLine> lines;
        int index;
        bool built;
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）
        /// <summary>開啟的那一幀不要吃按鍵 —— 開對話用的也是 E，同一幀會直接跳掉第一句。</summary>
        int openedFrame = -1;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 20;
            if (doc.panelSettings == null)
                Debug.LogError("[Dialogue] 找不到 Resources/ui/UIPanelSettings");
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (anim != null && anim.IsOpen) UIState.ModalOpen = false;
        }

        public bool IsOpen => built && anim != null && anim.IsOpen;   // ⚠️ 不看 display：關閉動畫期間它還是 Flex

        /// <summary>
        /// 這一幀才關掉。⚠️ 最後一句按 E 關掉時 ModalOpen 當下就解除了，同一幀 TalkNpc
        /// 若排在後面跑，會讀到同一下 E 又開一次對話 —— TalkNpc 要看這個擋掉。
        /// </summary>
        public bool ClosedThisFrame => anim != null && anim.ClosedThisFrame;

        /// <summary>開始一段對話。</summary>
        public void Open(string speaker, List<DialogueLine> script, string portrait = null)
        {
            if (script == null || script.Count == 0) return;
            if (!built) Build();
            if (!built) return;

            lines = script;
            index = 0;
            openedFrame = Time.frameCount;

            nameLabel.text = speaker ?? "";
            var sp = string.IsNullOrEmpty(portrait) ? null : GameArt.Portrait(portrait);
            portraitEl.style.display = sp != null ? DisplayStyle.Flex : DisplayStyle.None;
            if (sp != null) portraitEl.style.backgroundImage = new StyleBackground(sp);

            anim.Show();                 // 淡入（邏輯上這一行就算開著，見 UIAnim）
            UIState.ModalOpen = true;
            ShowLine();
        }

        /// <summary>純字串版（一般閒聊）。</summary>
        public void Open(string speaker, IEnumerable<string> texts, string portrait = null) =>
            Open(speaker, DialogueLine.Of(texts), portrait);

        public void Close()
        {
            anim?.Hide();                // 淡出只是視覺殘影，邏輯上這一行就算關了
            UIState.ModalOpen = false;
            lines = null;
        }

        void Update()
        {
            if (!IsOpen) return;
            if (Time.frameCount == openedFrame) return;      // 開啟那一幀不吃鍵

            if (Input.GetKeyDown(KeyCode.Escape)) { Close(); return; }

            // 有選項的那一句要用點的，不能按過去
            var cur = lines[index];
            if (cur.Choices != null && cur.Choices.Count > 0) return;

            if (Input.GetKeyDown(KeyCode.E) || Input.GetKeyDown(KeyCode.Space)) Next();
        }

        void Next()
        {
            index++;
            if (lines == null || index >= lines.Count) { Close(); return; }
            ShowLine();
        }

        void ShowLine()
        {
            var l = lines[index];
            textLabel.text = l.Text;
            Sfx.Play("talk");             // 音效：開對話、換下一句都走這裡

            choicesBox.Clear();
            bool hasChoices = l.Choices != null && l.Choices.Count > 0;
            choicesBox.style.display = hasChoices ? DisplayStyle.Flex : DisplayStyle.None;
            nextLabel.style.display = hasChoices ? DisplayStyle.None : DisplayStyle.Flex;

            if (!hasChoices)
            {
                nextLabel.text = index < lines.Count - 1 ? "E / 空白鍵 繼續" : "E / 空白鍵 結束";
                return;
            }

            foreach (var (label, onPick) in l.Choices)
            {
                var cb = onPick;
                var b = new Button(() =>
                {
                    // ⚠️ 先關掉再執行 —— 選項的動作常常是「再開一段新對話」，
                    //    不先關的話新對話會被這一段的關閉蓋掉。
                    Close();
                    cb?.Invoke();
                }) { text = label };
                b.AddToClassList("dlg-choice");
                choicesBox.Add(b);
            }
        }

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[Dialogue] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            CjkFont.Apply(root);
            Sfx.BindClicks(root);         // 選項按鈕的 click 音（選完接著開新對話時會被 talk 蓋過）

            var layer = new VisualElement();
            layer.AddToClassList("dlg-layer");
            root.Add(layer);

            box = new VisualElement();
            box.AddToClassList("dlg-box");
            layer.Add(box);

            portraitEl = new VisualElement();
            portraitEl.AddToClassList("dlg-portrait");
            box.Add(portraitEl);

            var body = new VisualElement();
            body.AddToClassList("dlg-body");
            box.Add(body);

            nameLabel = new Label();
            nameLabel.AddToClassList("dlg-name");
            body.Add(nameLabel);

            textLabel = new Label();
            textLabel.AddToClassList("dlg-text");
            body.Add(textLabel);

            choicesBox = new VisualElement();
            choicesBox.AddToClassList("dlg-choices");
            body.Add(choicesBox);

            nextLabel = new Label();
            nextLabel.AddToClassList("dlg-next");
            body.Add(nextLabel);

            root.style.display = DisplayStyle.None;
            anim = UIAnim.SlideUp(root, box);                 // 從下方滑上來；換句不動它（只有 Open/Close 會）
            built = true;
        }
    }
}
