using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>分頁：全部／材料／花與種子／藥水。</summary>
    public enum BagTab { All, Mat, Flower, Potion }

    /// <summary>面板模式：純看背包（B 鍵）／在櫥櫃前跟倉庫搬東西（E）。</summary>
    public enum BagMode { Bag, Storage }

    /// <summary>
    /// 背包／倉庫面板。
    ///
    /// 兩種開法共用同一張列表，因為欄位幾乎一樣，分成兩支 UI 只會重複一遍：
    ///   Open()        ── 任何場景按 B：只看背包裡有什麼、還剩幾種。
    ///   OpenStorage() ── 店裡走到左邊櫥櫃按 E：多出倉庫那一欄與存入/取回按鈕。
    ///
    /// ⚠️ 背包的上限是「幾**種**東西」（同名無限疊加），所以列表是一種一列、右邊寫數量，
    ///    而不是一格一個。倉庫模式也會列出「只有倉庫裡有」的品項，才拿得回來。
    ///
    /// ── 移植註記：改用 UI Toolkit ──────────────────────────────
    /// Cocos 版是 421 行純程式碼堆節點：每顆按鈕都要 new Node() + addComponent(UITransform)
    /// + setPosition(手算的 x, y)，四個分頁鈕的位置寫成 -246 + i * 164，顏色是散落各處的
    /// new Color(118, 92, 58, 255)。加一個欄位＝重算一整排 offset。
    ///
    /// 這裡拆成三塊：
    ///   Resources/ui/BagPanel.uxml       結構（像 HTML）
    ///   Resources/ui/BagPanelStyle.uss   外觀（像 CSS，顏色/尺寸集中在這）
    ///   本檔                              只剩「資料 → UI」的繫結
    ///
    /// ⚠️ 路徑是小寫 ui/ —— 那個資料夾是從 Cocos 專案搬過來的（GameArt 一直用
    ///    ui/clock/face 這種路徑）。Windows 檔名不分大小寫，寫成 UI/ 會靜默地
    ///    掉進同一個資料夾，但 AssetDatabase 的路徑是**嚴格區分大小寫**的，
    ///    Editor 端就會建到錯的地方。兩邊一律用小寫。
    ///
    /// 位置全部交給 flexbox，沒有任何一個手算座標。
    /// </summary>
    public class BagPanel : MonoBehaviour
    {
        public static BagPanel Instance { get; private set; }

        /// <summary>取得面板；沒有的話自動生一個（跨場景保留）。</summary>
        public static BagPanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("BagUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<BagPanel>();
        }

        // ── 分類 ────────────────────────────────────────────────

        static string[] potions;
        static string[] gardenItems;

        static string[] Potions
        {
            get
            {
                if (potions == null)
                {
                    var l = new List<string>(Items.PotionItems.Keys);
                    potions = l.ToArray();
                }
                return potions;
            }
        }

        static string[] GardenItems
        {
            get
            {
                if (gardenItems == null)
                {
                    var l = new List<string>();
                    foreach (var f in GardenData.Flowers) { l.Add(f.Seed); l.Add(f.Flower); }
                    gardenItems = l.ToArray();
                }
                return gardenItems;
            }
        }

        static BagTab TabOf(string name)
        {
            if (System.Array.IndexOf(Items.Materials, name) >= 0) return BagTab.Mat;
            if (System.Array.IndexOf(GardenItems, name) >= 0) return BagTab.Flower;
            if (System.Array.IndexOf(Potions, name) >= 0) return BagTab.Potion;
            return BagTab.All;      // 認不得的東西只在「全部」看得到
        }

        static readonly (BagTab Tab, string Label)[] TabDefs =
        {
            (BagTab.All, "全部"), (BagTab.Mat, "材料"),
            (BagTab.Flower, "花與種子"), (BagTab.Potion, "藥水"),
        };

        // ── 狀態與 UI 參照 ───────────────────────────────────────

        UIDocument doc;
        VisualElement root;
        Label titleLabel, capLabel, hintLabel;
        VisualElement tabsBox;
        ScrollView rowsBox;
        Button stashAllBtn;

        BagTab tab = BagTab.All;
        BagMode mode = BagMode.Bag;
        bool built;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.visualTreeAsset = Resources.Load<VisualTreeAsset>("ui/BagPanel");
            doc.sortingOrder = 10;      // 疊在下排 HUD（sortingOrder 0）之上
            if (doc.panelSettings == null)
                Debug.LogError("[BagPanel] 找不到 Resources/ui/UIPanelSettings —— " +
                               "跑一次選單 Witch Shop → 建立 UI 設定檔");
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (root != null && root.style.display == DisplayStyle.Flex) UIState.ModalOpen = false;
        }

        void Update()
        {
            if (!built || root == null) return;
            // ⚠️ 只吃 Esc 關閉，不吃 B/E —— 開啟的那一下按鍵同一幀還會再被讀到。
            if (root.style.display == DisplayStyle.Flex && Input.GetKeyDown(KeyCode.Escape))
                Close();
        }

        /// <summary>B 鍵：看背包。</summary>
        public void Open() => Show(BagMode.Bag);

        /// <summary>櫥櫃前按 E：跟倉庫搬東西。</summary>
        public void OpenStorage() => Show(BagMode.Storage);

        void Show(BagMode m)
        {
            mode = m;
            if (!built) Build();
            if (!built) return;          // 建不起來就別往下走（Build 會印出原因）
            root.style.display = DisplayStyle.Flex;
            UIState.ModalOpen = true;
            GameArt.OnReady(Refresh);
        }

        public void Close()
        {
            if (root != null) root.style.display = DisplayStyle.None;
            UIState.ModalOpen = false;
        }

        // ── 建構（只跑一次）────────────────────────────────────

        /// <summary>
        /// 建構整棵 UI 樹（只成功一次）。
        ///
        /// ⚠️ built 一定要**最後**才設 true。之前寫成一開頭就設，結果 rootVisualElement
        ///    回 null（PanelSettings 沒載到時會這樣）時 Build 中途丟例外，卻留下
        ///    built=true / root=null 的半殘狀態 —— Update() 就每一幀狂丟
        ///    NullReferenceException。初始化失敗時旗標必須保持 false，下次才會重試。
        /// </summary>
        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null)
            {
                Debug.LogError("[BagPanel] UIDocument 沒有 rootVisualElement —— " +
                               "多半是 PanelSettings 或 UXML 沒載到，先跑選單 " +
                               "Witch Shop → 建立 UI 設定檔");
                return;
            }

            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/BagPanelStyle"));
            CjkFont.Apply(root);          // ⚠️ 見 CjkFont：預設字型沒有中文字

            titleLabel = root.Q<Label>("title");
            capLabel = root.Q<Label>("cap");
            hintLabel = root.Q<Label>("hint");
            tabsBox = root.Q<VisualElement>("tabs");
            rowsBox = root.Q<ScrollView>("rows");
            stashAllBtn = root.Q<Button>("stashAll");

            var closeBtn = root.Q<Button>("close");

            // ⚠️ 這個檢查一定要排在任何 .clicked += 之前 —— UXML 沒載到時這些全是 null，
            //    先接事件就會在這裡炸掉，反而看不到真正的原因。
            if (titleLabel == null || tabsBox == null || rowsBox == null
                || stashAllBtn == null || closeBtn == null)
            {
                Debug.LogError("[BagPanel] UXML 的元件找不到（title / tabs / rows / 按鈕）—— " +
                               "確認 Resources/ui/BagPanel.uxml 存在且有被匯入");
                root = null;
                return;
            }

            closeBtn.clicked += Close;
            stashAllBtn.clicked += StashAllInTab;

            // 分頁鈕：數量由 TabDefs 決定，位置交給 flexbox（.tab 有 flex-grow: 1）
            foreach (var d in TabDefs)
            {
                var t = d.Tab;
                var b = new Button(() => { tab = t; Refresh(); }) { text = d.Label };
                b.AddToClassList("tab");
                b.userData = t;
                tabsBox.Add(b);
            }

            built = true;      // ⚠️ 全部成功了才標記，見上面註解
        }

        // ── 內容 ────────────────────────────────────────────────

        /// <summary>要列的品項：背包有的 ＋（倉庫模式）倉庫有的，材料→花→藥水的順序。</summary>
        List<string> ItemsToShow()
        {
            var seen = new HashSet<string>();
            var all = new List<string>();
            foreach (var s in Inventory.List()) if (seen.Add(s.name)) all.Add(s.name);
            if (mode == BagMode.Storage)
                foreach (var s in Storage.List()) if (seen.Add(s.name)) all.Add(s.name);

            var order = new List<string>(Items.Materials);
            order.AddRange(GardenItems);
            order.AddRange(Potions);
            all.Sort((a, b) =>
            {
                int ia = order.IndexOf(a), ib = order.IndexOf(b);
                return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib);
            });

            if (tab == BagTab.All) return all;
            return all.FindAll(n => TabOf(n) == tab);
        }

        void Refresh()
        {
            if (!built) return;
            int bagTypes = Inventory.Types;

            titleLabel.text = mode == BagMode.Storage ? "倉庫" : "背包";

            capLabel.text = mode == BagMode.Storage
                ? $"背包 {bagTypes}/{Upgrades.BagSlots()} 種　倉庫 {Storage.Types()}/{Storage.Capacity()} 種"
                : $"{bagTypes}/{Upgrades.BagSlots()} 種";

            hintLabel.text = mode == BagMode.Storage
                ? "Esc 關閉 · 存入／取回整疊搬，[1] 只搬一個"
                : "Esc 關閉 · 背包裝不下時，把東西放進店裡左邊的櫥櫃";

            stashAllBtn.style.display = mode == BagMode.Storage ? DisplayStyle.Flex : DisplayStyle.None;

            foreach (var b in tabsBox.Children())
                b.EnableInClassList("active", (BagTab)b.userData == tab);

            rowsBox.Clear();
            var items = ItemsToShow();
            if (items.Count == 0)
            {
                var msg = new Label(tab == BagTab.All ? "空空如也 —— 去森林採點東西吧" : "這一類目前沒有東西");
                msg.AddToClassList("empty-msg");
                rowsBox.Add(msg);
                return;
            }
            foreach (var name in items) rowsBox.Add(MakeRow(name));
        }

        VisualElement MakeRow(string name)
        {
            int bag = Inventory.CountOf(name);
            int kept = Storage.Count(name);

            var row = new VisualElement();
            row.AddToClassList("row");

            var icon = new VisualElement();
            icon.AddToClassList("row-icon");
            var sp = GameArt.Item(name);
            if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
            row.Add(icon);

            var nameLabel = new Label(name);
            nameLabel.AddToClassList("row-name");
            row.Add(nameLabel);

            if (mode == BagMode.Bag)
            {
                var count = new Label(bag > 0 ? $"×{bag}" : "—");
                count.AddToClassList("row-count");
                if (bag <= 0) count.AddToClassList("empty");
                row.Add(count);
                return row;
            }

            // 倉庫模式：背包數 ─ 存入／取回 ─ 倉庫數
            var bagSide = new Label($"背包 {bag}");
            bagSide.AddToClassList("row-side");
            bagSide.AddToClassList(bag > 0 ? "bag" : "empty");
            row.Add(bagSide);

            bool canKeep = bag > 0 && Storage.CanAdd(name);
            row.Add(RowButton("存入", "btn-keep btn-wide", canKeep, () => MoveToStorage(name, bag)));
            row.Add(RowButton("[1]", "btn-keep btn-one", canKeep, () => MoveToStorage(name, 1)));

            bool canTake = kept > 0;
            row.Add(RowButton("取回", "btn-take btn-wide", canTake, () => MoveToBag(name, kept)));
            row.Add(RowButton("[1]", "btn-take btn-one", canTake, () => MoveToBag(name, 1)));

            var keptSide = new Label($"倉庫 {kept}");
            keptSide.AddToClassList("row-side");
            keptSide.AddToClassList(kept > 0 ? "kept" : "empty");
            row.Add(keptSide);

            return row;
        }

        static Button RowButton(string text, string classes, bool enabled, System.Action onClick)
        {
            var b = new Button(onClick) { text = text };
            b.AddToClassList("btn");
            foreach (var c in classes.Split(' ')) b.AddToClassList(c);
            b.SetEnabled(enabled);
            return b;
        }

        // ── 搬運 ────────────────────────────────────────────────

        /// <summary>背包 → 倉庫（倉庫放得下才扣背包）。</summary>
        void MoveToStorage(string name, int qty)
        {
            if (qty <= 0 || !Storage.CanAdd(name)) return;
            if (!Inventory.Remove(name, qty)) return;
            Storage.Add(name, qty);
            Refresh();
        }

        /// <summary>倉庫 → 背包（背包種類滿了就搬不動，東西留在倉庫）。</summary>
        void MoveToBag(string name, int qty)
        {
            if (qty <= 0 || Storage.Count(name) < qty) return;
            if (!Inventory.Add(name, qty)) return;      // Add 回 false ＝ 背包種類滿了
            Storage.Remove(name, qty);
            Refresh();
        }

        /// <summary>
        /// 把「目前分頁裡、背包有的」東西一次全部存進倉庫。
        /// 吃分頁是刻意的：在「全部」頁就是整個背包倒進去，切到「材料」頁就只倒材料，
        /// 不必為了「只想存材料」再多做一顆按鈕。
        /// </summary>
        void StashAllInTab()
        {
            int moved = 0;
            foreach (var name in ItemsToShow())
            {
                int qty = Inventory.CountOf(name);
                if (qty <= 0 || !Storage.CanAdd(name)) continue;   // 倉庫種類滿了就跳過
                if (!Inventory.Remove(name, qty)) continue;
                Storage.Add(name, qty);
                moved++;
            }
            Toast.Show(moved > 0 ? $"已存入 {moved} 種" : "沒有可以存入的東西");
            Refresh();
        }
    }
}
