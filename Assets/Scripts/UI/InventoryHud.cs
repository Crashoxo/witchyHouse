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
        int builtCap = -1;      // 目前排出來的格數（偵測背包升級後重建）

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
            root.pickingMode = PickingMode.Ignore;      // HUD 不吃滑鼠，點地面才點得到
            CjkFont.Apply(root);

            hud = new VisualElement();
            hud.AddToClassList("hud");
            hud.pickingMode = PickingMode.Ignore;
            root.Add(hud);

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
            hud.Clear();

            int cap = Upgrades.BagSlots();
            builtCap = cap;
            var items = Inventory.List();
            var prev = lastCounts;
            lastCounts = new System.Collections.Generic.Dictionary<string, int>();
            foreach (var st in items) lastCounts[st.name] = st.count;

            for (int i = 0; i < cap; i++)
            {
                var slot = new VisualElement();
                slot.AddToClassList("slot");

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

                hud.Add(slot);

                // 數量變多（含新撿到的一種）→ 那一格彈一下。變少（賣掉、收進倉庫）不彈。
                if (prev != null && i < items.Count)
                {
                    prev.TryGetValue(items[i].name, out int before);
                    if (items[i].count > before) UIAnim.Bump(slot);
                }
            }
        }
    }
}
