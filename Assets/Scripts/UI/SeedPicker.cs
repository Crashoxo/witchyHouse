using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>
    /// 種子選單：站在空花圃前按 E 時跳出來，讓玩家挑背包裡的哪一種種子種下去。
    ///
    /// 是 modal —— 挑完（或取消）才把控制權還給 GardenRoom，由它真的種下去。
    /// 樣式沿用 ShopManageStyle（同一套暗木＋米黃描邊的視覺）。
    /// </summary>
    public class SeedPicker : MonoBehaviour
    {
        public static SeedPicker Instance { get; private set; }

        public static SeedPicker Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("SeedPickerUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<SeedPicker>();
        }

        /// <summary>背包裡有哪些種子（照 GardenData.Flowers 的順序）。</summary>
        public static List<string> SeedsInBag()
        {
            var outList = new List<string>();
            foreach (var f in GardenData.Flowers)
                if (Inventory.CountOf(f.Seed) > 0) outList.Add(f.Seed);
            return outList;
        }

        UIDocument doc;
        VisualElement root;
        ScrollView rowsBox;
        Action<string> onPick;
        bool built;
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 14;
            if (doc.panelSettings == null)
                Debug.LogError("[SeedPicker] 找不到 Resources/ui/UIPanelSettings");
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (anim != null && anim.IsOpen) UIState.ModalOpen = false;
        }

        void Update()
        {
            if (!built || root == null) return;
            if (anim.IsOpen && Input.GetKeyDown(KeyCode.Escape)) Cancel();
        }

        /// <summary>開啟；玩家挑好之後呼叫 pick(種子名)。取消的話不呼叫。</summary>
        public void Open(Action<string> pick)
        {
            onPick = pick;
            if (!built) Build();
            if (!built) return;
            anim.Show();                 // 淡入（邏輯上這一行就算開著，見 UIAnim）
            UIState.ModalOpen = true;
            Sfx.Play("ui-open");                                    // 音效：面板打開
            Refresh();
        }

        void Cancel()
        {
            onPick = null;
            Close();
        }

        void Close()
        {
            anim?.Hide();                // 淡出只是視覺殘影，邏輯上這一行就算關了
            UIState.ModalOpen = false;
            Sfx.Play("ui-close");                                   // 音效：面板關閉
        }

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[SeedPicker] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/ShopManageStyle"));
            CjkFont.Apply(root);
            Sfx.BindClicks(root);         // 所有按鈕的 click 音

            var dim = new VisualElement();
            dim.AddToClassList("dim");
            root.Add(dim);

            var panel = new VisualElement();
            panel.AddToClassList("panel");
            panel.style.width = 460;
            dim.Add(panel);

            var header = new VisualElement();
            header.AddToClassList("header");
            panel.Add(header);

            var title = new Label("要種什麼？");
            title.AddToClassList("title");
            header.Add(title);

            var spacer = new VisualElement();
            spacer.AddToClassList("spacer");
            header.Add(spacer);

            var close = new Button(Cancel) { text = "×" };
            close.AddToClassList("close");
            header.Add(close);

            rowsBox = new ScrollView();
            rowsBox.AddToClassList("rows");
            rowsBox.style.minHeight = 140;
            panel.Add(rowsBox);

            var hint = new Label("Esc 取消");
            hint.AddToClassList("hint");
            panel.Add(hint);

            anim = UIAnim.Pop(root, panel, dim);              // 淡入＋輕微放大，暗幕只淡入
            built = true;
        }

        void Refresh()
        {
            rowsBox.Clear();
            var seeds = SeedsInBag();
            if (seeds.Count == 0)
            {
                var msg = new Label("背包裡沒有種子 —— 森林採集時偶爾會撿到，花店也買得到");
                msg.AddToClassList("empty-msg");
                rowsBox.Add(msg);
                return;
            }

            foreach (var seed in seeds)
            {
                string s = seed;                       // 迴圈變數要抓進閉包
                var f = GardenData.FlowerBySeed(s);

                var row = new VisualElement();
                row.AddToClassList("row");

                var icon = new VisualElement();
                icon.style.width = 32; icon.style.height = 32; icon.style.marginRight = 10;
                var sp = GameArt.Item(s);
                if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
                row.Add(icon);

                var name = new Label($"{s} ×{Inventory.CountOf(s)}");
                name.AddToClassList("col-name");
                name.style.width = 150;
                row.Add(name);

                var yieldLabel = new Label(f != null ? $"收成 {f.Yield} 朵" : "");
                yieldLabel.AddToClassList("up-effect");
                row.Add(yieldLabel);

                var pick = new Button(() =>
                {
                    var cb = onPick;
                    onPick = null;
                    Close();
                    cb?.Invoke(s);          // ⚠️ 先關面板再回呼，不然種下去的動畫會被 modal 擋住
                }) { text = "種下" };
                pick.AddToClassList("btn");
                pick.AddToClassList("btn-list");
                row.Add(pick);

                rowsBox.Add(row);
            }
        }
    }
}
