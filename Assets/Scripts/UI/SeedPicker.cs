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

        /// <summary>
        /// 一頁幾列（2026-11-27 改成固定高度＋翻頁，見 <see cref="Pager"/>）。
        /// 面板高（像素外觀）＝ padding 30 ＋ 標題列 5 ＋ 清單 5 × 60 ＝ 300 ＋ 分隔線 18 ＋ 底列 30 ＋ padding 24 ＝ 407。
        /// </summary>
        const int RowsPerPage = 5;
        /// <summary>列距：`.sk .row` 高 57 ＋ margin-bottom 3。</summary>
        const int RowPitch = 60;

        UIDocument doc;
        VisualElement root;
        VisualElement rowsBox;       // ＝ pager.Body
        Pager pager;
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
            if (!anim.IsOpen) return;
            if (Input.GetKeyDown(KeyCode.Escape)) Cancel();
            else pager.HandleKeys();     // ←／→、A／D 翻頁
        }

        /// <summary>開啟；玩家挑好之後呼叫 pick(種子名)。取消的話不呼叫。</summary>
        public void Open(Action<string> pick)
        {
            onPick = pick;
            if (!built) Build();
            if (!built) return;
            anim.Show();                 // 淡入（邏輯上這一行就算開著，見 UIAnim）
            UIState.ModalOpen = true;
            pager.Reset();               // 每次打開都從第 1 頁看
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
            UiSkin.Apply(root);           // 8-bit 外觀（總開關在 UiSkin.Enabled）
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

            // 清單：固定 5 列高、超過就翻頁（不捲動）
            pager = new Pager(RowsPerPage, RowsPerPage * RowPitch, Refresh);
            rowsBox = pager.Body;
            rowsBox.AddToClassList("rows");
            panel.Add(rowsBox);

            var info = UiSkin.Footer(panel, "取消", "Esc");
            pager.Bar.AddToClassList("pg-bar--center");      // 翻頁鈕擺在底列正中間
            info.parent.Add(pager.Bar);

            anim = UIAnim.Pop(root, panel, dim);              // 淡入＋輕微放大，暗幕只淡入
            built = true;
        }

        void Refresh()
        {
            var seeds = SeedsInBag();
            pager.Render(seeds.Count, i => SeedRow(seeds[i]),
                "背包裡沒有種子 —— 森林採集時偶爾會撿到，花店也買得到");
            UiSkin.Stripe(rowsBox);
        }

        VisualElement SeedRow(string s)
        {
            var f = GardenData.FlowerBySeed(s);

            var row = new VisualElement();
            row.AddToClassList("row");

            var icon = new VisualElement();
            icon.AddToClassList("stock-icon");
            var sp = GameArt.Item(s);
            if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
            row.Add(icon);

            // 名稱＋持有數徽章（舊外觀：名稱與「×3」各自一個字串，看起來跟以前差不多）
            var name = new Label(s);
            name.AddToClassList("col-name");
            name.AddToClassList("seed-name");
            row.Add(name);
            row.Add(UiSkin.Badge($"×{Inventory.CountOf(s)}"));

            // 收成：[花的小圖]×3（舊外觀：「收成 3 朵」）
            VisualElement yieldCell;
            if (f != null && UiSkin.On)
            {
                yieldCell = UiSkin.IconCount(GameArt.Item(f.Flower), $"×{f.Yield}");
                yieldCell.AddToClassList("seed-yield");
            }
            else
            {
                yieldCell = new Label(f != null ? $"收成 {f.Yield} 朵" : "");
                yieldCell.AddToClassList("up-effect");
            }
            row.Add(yieldCell);

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

            return row;
        }
    }
}
