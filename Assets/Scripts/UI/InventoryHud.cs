using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 畫面下排常駐的背包格子。
    ///
    /// Cocos 版是 Inventory.ts 裡的 Component 那一半（build / layoutSlots / buildCell /
    /// renderAll）。這裡只負責「把 Inventory 的資料畫出來」，資料本身在 Core.Inventory。
    ///
    /// ⚠️ 背包上限是「幾**種**東西」，所以格數＝Upgrades.BagSlots()，
    ///    一格放一種，右下角寫數量。升級背包後格數會變，Refresh() 會自動重排。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// 原版 layoutSlots() 有一段手算的換行邏輯：一排最多 12 格，超過往上換行，
    /// 而且「最後一排不滿時要各自置中」，所以要算 rowW、算每一格的 x/y。
    /// 這裡在 HudStyle.uss 用 flex-wrap + justify-content: center，
    /// 換行與置中都是排版引擎自己做的，那段算式整個不見。
    /// </summary>
    public class InventoryHud : MonoBehaviour
    {
        public static InventoryHud Instance { get; private set; }

        /// <summary>取得下排 HUD；沒有的話自動生一個（跨場景保留）。</summary>
        public static InventoryHud Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("InventoryHud");
            DontDestroyOnLoad(go);
            return go.AddComponent<InventoryHud>();
        }

        UIDocument doc;
        VisualElement hud;
        /// <summary>
        /// 格子實際放在這一層：像素外觀時它是一條木頭底座（Skin8 的 .hud-bar），舊外觀時沒有樣式、只負責換行置中。
        /// ⚠️ 不能直接把底座圖掛在 .hud 上：.hud 是整條螢幕寬（left 0／right 0），底座會變成橫跨全螢幕的木條；
        ///    多包一層、讓它照內容縮寬，再由 .hud 的 justify-content: center 置中。
        /// </summary>
        VisualElement bar;
        int builtCap = -1;      // 目前排出來的格數（偵測背包升級後重建）

        /// <summary>
        /// true ＝ 魔女腰包版面：[左端][口袋]×N[右端] 一個接一個排（每格 51×60、兩端 18×78，全是固定尺寸的圖，
        /// 布條的金虛線剛好接起來）。12／15／18 格總寬 648／801／954，960 寬的畫面也放得下、不換行。
        /// false ＝ 舊外觀（UiSkin 關著）：照舊用 .hud-bar＋.slot。
        /// </summary>
        bool belt;

        /// <summary>剛拿到東西的那格（奶油白襯裡＋右上角一顆星）亮多久。</summary>
        const long NewGlowMs = 1200;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            if (doc.panelSettings == null)
            {
                Debug.LogError("[InventoryHud] 找不到 Resources/ui/UIPanelSettings —— " +
                               "跑一次選單 Witch Shop → 建立 UI 設定檔");
                return;
            }
            // HUD 疊在遊戲之上、但要在背包面板之下
            doc.sortingOrder = 0;

            var root = doc.rootVisualElement;
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudStyle"));
            UiSkin.Apply(root);           // 8-bit 外觀：深紫布＋金框的格子（總開關在 UiSkin.Enabled）
            root.pickingMode = PickingMode.Ignore;      // HUD 不吃滑鼠，點地面才點得到
            CjkFont.Apply(root);

            hud = new VisualElement();
            hud.AddToClassList("hud");
            hud.pickingMode = PickingMode.Ignore;
            root.Add(hud);

            // 像素外觀開著 → 魔女腰包（.hud-belt 與 belt-* 的圖，見 Skin8.uss）；關著 → 舊的 .hud-bar＋.slot。
            // ⚠️ 腰包不共用 .hud-bar／.slot：那兩組 class 與圖還有上方工具列、Toast、托盤、背包面板在用。
            belt = UiSkin.On;
            bar = new VisualElement();
            bar.AddToClassList(belt ? "hud-belt" : "hud-bar");
            bar.pickingMode = PickingMode.Ignore;
            hud.Add(bar);

            GameArt.OnReady(Refresh);
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        /// <summary>每幀輕量檢查：內容或容量變了才重畫。</summary>
        void Update()
        {
            if (hud == null) return;
            if (Upgrades.BagSlots() != builtCap) { Refresh(); return; }
            if (DirtyCheck()) Refresh();
        }

        string lastSignature = "";

        /// <summary>把背包內容壓成一個字串，跟上次比對 —— 變了才重畫。</summary>
        bool DirtyCheck()
        {
            var sb = new System.Text.StringBuilder();
            foreach (var s in Inventory.List()) sb.Append(s.name).Append(':').Append(s.count).Append('|');
            var sig = sb.ToString();
            if (sig == lastSignature) return false;
            lastSignature = sig;
            return true;
        }

        /// <summary>
        /// 上一次畫出來時每樣東西有幾個 —— 用來找「哪一格變多了」好讓它彈一下。
        /// null＝還沒畫過：第一次（開場、讀檔後）只記下來不彈。
        /// 這個 HUD 跨場景常駐，換場景不會重建，所以換場也不會誤彈。
        /// </summary>
        System.Collections.Generic.Dictionary<string, int> lastCounts;

        public void Refresh()
        {
            if (hud == null) return;
            bar.Clear();

            int cap = Upgrades.BagSlots();
            builtCap = cap;
            var items = Inventory.List();
            var prev = lastCounts;
            lastCounts = new System.Collections.Generic.Dictionary<string, int>();
            foreach (var st in items) lastCounts[st.name] = st.count;

            if (belt) { RefreshBelt(cap, items, prev); return; }

            for (int i = 0; i < cap; i++)
            {
                var slot = new VisualElement();
                slot.AddToClassList("slot");
                slot.EnableInClassList("slot--empty", i >= items.Count);   // 空格：換一張暗一點的底

                if (i < items.Count)
                {
                    var st = items[i];
                    var sp = GameArt.Item(st.name);
                    if (sp != null)
                    {
                        var icon = new VisualElement();
                        icon.AddToClassList("slot-icon");
                        icon.style.backgroundImage = new StyleBackground(sp);
                        slot.Add(icon);
                    }
                    else
                    {
                        // 沒有圖示時退回文字（原版同樣的做法）
                        var nameLabel = new Label(st.name);
                        nameLabel.AddToClassList("slot-name");
                        slot.Add(nameLabel);
                    }

                    if (st.count > 1)
                    {
                        var count = new Label(st.count.ToString());
                        count.AddToClassList("slot-count");
                        slot.Add(count);
                    }
                }

                bar.Add(slot);

                // 數量變多（含新撿到的一種）→ 那一格彈一下。變少（賣掉、收進倉庫）不彈。
                if (prev != null && i < items.Count)
                {
                    prev.TryGetValue(items[i].name, out int before);
                    if (items[i].count > before) UIAnim.Bump(slot);
                }
            }
        }

        /// <summary>魔女腰包版面（像素外觀）：兩端的扣子＋一格一個縫出來的口袋。行為跟舊版一樣，只是換 class。</summary>
        void RefreshBelt(int cap, System.Collections.Generic.List<Stack> items,
                         System.Collections.Generic.Dictionary<string, int> prev)
        {
            bar.Add(BeltPart("belt-end", "belt-end--l"));

            for (int i = 0; i < cap; i++)
            {
                bool full = i < items.Count;
                var slot = BeltPart("belt-slot", full ? null : "belt-slot--empty");

                if (full)
                {
                    var st = items[i];
                    var sp = GameArt.Item(st.name);
                    if (sp != null)
                    {
                        var icon = BeltPart("belt-icon");
                        icon.style.backgroundImage = new StyleBackground(sp);
                        slot.Add(icon);
                    }
                    else
                    {
                        var nameLabel = new Label(st.name);
                        nameLabel.AddToClassList("belt-name");
                        nameLabel.pickingMode = PickingMode.Ignore;
                        slot.Add(nameLabel);
                    }

                    if (st.count > 1)
                    {
                        var count = new Label(st.count.ToString());
                        count.AddToClassList("belt-count");
                        count.pickingMode = PickingMode.Ignore;
                        slot.Add(count);
                    }
                }

                bar.Add(slot);

                // 數量變多（含新撿到的一種）→ 那一格彈一下，並亮一下（奶油白襯裡＋星星）。變少不彈。
                if (prev != null && full)
                {
                    prev.TryGetValue(items[i].name, out int before);
                    if (items[i].count > before)
                    {
                        slot.AddToClassList("belt-slot--new");
                        var spark = BeltPart("belt-spark");
                        slot.Add(spark);
                        slot.schedule.Execute(() =>
                        {
                            slot.RemoveFromClassList("belt-slot--new");
                            spark.RemoveFromHierarchy();
                        }).StartingIn(NewGlowMs);
                        UIAnim.Bump(slot);
                    }
                }
            }

            bar.Add(BeltPart("belt-end", "belt-end--r"));
        }

        static VisualElement BeltPart(string cls, string extra = null)
        {
            var el = new VisualElement();
            el.AddToClassList(cls);
            if (extra != null) el.AddToClassList(extra);
            el.pickingMode = PickingMode.Ignore;
            return el;
        }
    }
}
