using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 設定面板（按 O 開，或點左上角 HUD 底下的「設定 (O)」）：音樂音量、音效音量、靜音。
    ///
    /// 這裡**只是介面**：數值全部存在 <see cref="Sfx"/>（<see cref="Sfx.MusicVolume"/> /
    /// <see cref="Sfx.Volume"/> / <see cref="Sfx.Muted"/>，存檔 key `witch.audio`、寫檔有防抖），
    /// 背景音樂由 <see cref="Bgm"/> 訂閱 <see cref="Sfx.Changed"/> 自己跟上。
    /// 這個面板也訂閱同一個事件 —— 按 M 靜音時，開著的面板會跟著重畫。
    ///
    /// ⚠️ 音量條**不用 UI Toolkit 內建的 Slider**：執行期沒有預設主題樣式表，
    ///    Slider 的拖曳鈕和軌道會整個看不到。改成 10 個小方塊自己畫（滿格／空格兩種顏色），
    ///    旁邊 −／＋ 每下 ±10%，也可以直接點方塊跳到那一格。
    ///
    /// ⚠️ O 鍵「開」在 PlayerController、「關」在這裡的 Update —— 跟 QuestPanel 一樣
    ///    擋掉同一幀開了又關／關了又開（<c>anim.OpenedThisFrame</c> / <c>anim.ClosedThisFrame</c>）。
    /// </summary>
    public class SettingsPanel : MonoBehaviour
    {
        public static SettingsPanel Instance { get; private set; }

        public static SettingsPanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("SettingsUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<SettingsPanel>();
        }

        /// <summary>音量條幾格（一格 10%）。</summary>
        const int Cells = 10;

        UIDocument doc;
        VisualElement root;
        bool built;
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）

        // 兩列音量條：方塊與百分比文字
        VisualElement[] musicCells, sfxCells;
        Label musicPct, sfxPct;
        Button muteBtn;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 12;
            if (doc.panelSettings == null)
                Debug.LogError("[SettingsPanel] 找不到 Resources/ui/UIPanelSettings");
        }

        void OnDestroy()
        {
            Sfx.Changed -= OnSettingsChanged;
            if (Instance == this) Instance = null;
            if (anim != null && anim.IsOpen) UIState.ModalOpen = false;
        }

        void Update()
        {
            if (!built || root == null) return;
            if (!anim.IsOpen) return;
            // O 或 Esc 都能關。⚠️ 開的那一幀不關（PlayerController 可能比這裡先跑，見 QuestPanel）
            if (anim.OpenedThisFrame) return;
            if (Input.GetKeyDown(KeyCode.Escape) || Input.GetKeyDown(KeyCode.O)) Close();
        }

        public bool IsOpen => built && anim != null && anim.IsOpen;   // ⚠️ 不看 display：關閉動畫期間它還是 Flex

        public void Open()
        {
            if (!built) Build();
            if (!built) return;
            // ⚠️ 反方向：這裡先跑、按 O 關掉並解除 ModalOpen，同一幀 PlayerController 又讀到 O → 關了立刻重開
            if (anim.ClosedThisFrame || anim.IsOpen) return;
            anim.Show();                 // 淡入（邏輯上這一行就算開著，見 UIAnim）
            UIState.ModalOpen = true;
            Sfx.Play("ui-open");                                    // 音效：面板打開
            Refresh();
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
            if (root == null) { Debug.LogError("[SettingsPanel] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/ShopManageStyle"));
            UiSkin.Apply(root);           // 8-bit 外觀（總開關在 UiSkin.Enabled）
            CjkFont.Apply(root);
            Sfx.BindClicks(root);         // 所有按鈕的 click 音

            var dim = new VisualElement();
            dim.AddToClassList("dim");
            root.Add(dim);

            var panel = new VisualElement();
            panel.AddToClassList("panel");
            panel.style.width = 520;
            dim.Add(panel);

            var header = new VisualElement();
            header.AddToClassList("header");
            panel.Add(header);

            var title = new Label("設定");
            title.AddToClassList("title");
            header.Add(title);

            var spacer = new VisualElement();
            spacer.AddToClassList("spacer");
            header.Add(spacer);

            var close = new Button(Close) { text = "×" };
            close.AddToClassList("close");
            header.Add(close);

            // 音樂：調完不用另外播聲音 —— 背景音樂本身就在響
            panel.Add(VolumeRow("音樂", out musicCells, out musicPct,
                () => Sfx.MusicVolume, v => Sfx.MusicVolume = v, null));
            // 音效：調完播一聲 pickup，讓玩家聽到新的音量
            panel.Add(VolumeRow("音效", out sfxCells, out sfxPct,
                () => Sfx.Volume, v => Sfx.Volume = v, "pickup"));

            // 靜音（跟 M 鍵是同一個開關）
            var muteRow = new VisualElement();
            muteRow.AddToClassList("row");
            muteRow.AddToClassList("set-row");
            var muteLabel = new Label("靜音");
            muteLabel.AddToClassList("set-label");
            muteRow.Add(muteLabel);
            muteBtn = new Button(Sfx.ToggleMute);
            muteBtn.AddToClassList("btn");
            muteBtn.AddToClassList("set-mute");
            muteRow.Add(muteBtn);
            panel.Add(muteRow);

            // 底部：[O][Esc] 關閉 ……… [M] 靜音（鍵帽取代「O / Esc 關閉 · M 快速靜音」那句）
            var info = UiSkin.Footer(panel, "關閉", "O", "Esc");
            info.text = "靜音";
            info.parent.Insert(info.parent.IndexOf(info), UiSkin.KeyCap("M"));

            anim = UIAnim.Pop(root, panel, dim);              // 淡入＋輕微放大，暗幕只淡入
            Sfx.Changed += OnSettingsChanged;
            built = true;
        }

        /// <summary>
        /// 一列音量：標籤、−、10 格音量條、＋、百分比。
        /// <paramref name="cue"/>：調整後要播的音效（null＝不播；按鈕本身的 click 音由 BindClicks 負責）。
        /// </summary>
        VisualElement VolumeRow(string label, out VisualElement[] cells, out Label pct,
                                System.Func<float> get, System.Action<float> set, string cue)
        {
            var row = new VisualElement();
            row.AddToClassList("row");
            row.AddToClassList("set-row");

            var name = new Label(label);
            name.AddToClassList("set-label");
            row.Add(name);

            void Apply(float v)
            {
                set(Mathf.Clamp01(Mathf.Round(v * Cells) / Cells));   // 對齊到格子上（舊存檔可能是 0.83 這種值）
                if (cue != null) Sfx.Play(cue);
            }

            var minus = new Button(() => Apply(get() - 1f / Cells)) { text = "−" };
            minus.AddToClassList("btn");
            minus.AddToClassList("btn-step");
            minus.AddToClassList("sk-minus");
            row.Add(minus);

            var bar = new VisualElement();
            bar.AddToClassList("set-bar");
            cells = new VisualElement[Cells];
            for (int i = 0; i < Cells; i++)
            {
                int level = i + 1;                                     // 迴圈變數要抓進閉包
                var c = new VisualElement();
                c.AddToClassList("set-cell");
                // 點方塊直接跳到那一格（已經是那一格再點一次＝少一格，才調得到 0）
                c.RegisterCallback<ClickEvent>(_ =>
                {
                    int now = Mathf.RoundToInt(get() * Cells);
                    Apply((now == level ? level - 1 : level) / (float)Cells);
                    if (cue == null) Sfx.Play("ui-click");
                });
                bar.Add(c);
                cells[i] = c;
            }
            row.Add(bar);

            var plus = new Button(() => Apply(get() + 1f / Cells)) { text = "+" };
            plus.AddToClassList("btn");
            plus.AddToClassList("btn-step");
            plus.AddToClassList("sk-plus");
            row.Add(plus);

            pct = new Label();
            pct.AddToClassList("set-pct");
            row.Add(pct);
            return row;
        }

        void OnSettingsChanged()
        {
            if (built && anim != null && anim.IsOpen) Refresh();
        }

        void Refresh()
        {
            Paint(musicCells, musicPct, Sfx.MusicVolume);
            Paint(sfxCells, sfxPct, Sfx.Volume);
            bool muted = Sfx.Muted;
            muteBtn.text = muted ? "已靜音" : "有聲音";
            muteBtn.EnableInClassList("set-mute--on", muted);
        }

        static void Paint(VisualElement[] cells, Label pct, float v)
        {
            int on = Mathf.RoundToInt(v * Cells);
            for (int i = 0; i < cells.Length; i++) cells[i].EnableInClassList("set-cell--on", i < on);
            pct.text = $"{Mathf.RoundToInt(v * 100f)}%";
        }
    }
}
