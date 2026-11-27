using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>
    /// 佈置模式底下那條托盤：列出「買了但還沒擺出來」的家具、貨架與裝飾，
    /// 點一下就放進房間。
    ///
    /// ⚠️ 沒有這個托盤的話，在花店買的東西會卡在「擁有」清單裡永遠拿不出來 ——
    ///    佈置模式只能搬動已經擺出來的東西。這是進入房間的唯一入口。
    ///
    /// 托盤刻意**不擋滑鼠以外的操作**：它是 UI Toolkit 的一層，但不設 UIState.ModalOpen，
    /// 因為佈置模式本身還要能用滑鼠拖房間裡的家具。
    ///
    /// ── 提示列（使用者回饋「解釋的文字太多了」之後改成圖示）──────────
    ///   以前是一整行 rich text 句子；現在是一排「圖示組」（[鍵帽][動作圖]），
    ///   依狀態（<see cref="HintMode"/>）只顯示相關的那幾組，其他隱藏。
    ///   圖示組**只建一次**，換狀態只切 display／class（不重建元素，UI Toolkit 才不會一直重排）。
    ///
    /// ── 像素外觀（<see cref="UiSkin.On"/>）──────────────────────────
    ///   底座＝下排背包列同一塊深木（hud-bar 九宮格）；提示列是亮的羊皮紙膠囊＋左邊金條；
    ///   托盤格＝紫布金框（同背包格），格子裡只有圖＋右下角的數量徽章，**名稱改成滑鼠移上去時的浮動說明**（在格子上方）。
    ///   外觀關著時照舊（HudExtraStyle 的 .tray-*，格子裡圖＋名稱）。
    /// </summary>
    public class ShopRoomTray : MonoBehaviour
    {
        public static ShopRoomTray Instance { get; private set; }

        public static ShopRoomTray Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("ShopRoomTrayUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<ShopRoomTray>();
        }

        /// <summary>提示列的狀態：沒選東西／選中家具／拖家具中／選中或拖曳商品。</summary>
        public enum HintMode { Idle, Furniture, DragFurniture, Good }

        /// <summary>
        /// 托盤現在給哪個房間用（2026-11-28 家裡也能擺）：
        ///   Shop ── 店裡佈置（ShopRoomEditor）：全部「還沒擺」的家具、貨架、陳列桌、裝飾。
        ///   Home ── 家裡佈置（HomeArrange）：只列能擺家裡的（Furnishings.CanPlaceAtHome：燈、家具、裝飾、地毯；陳列類不列）。
        /// 數量一律是「擁有 − 店裡擺的 − 家裡擺的」（RoomLayout.Unplaced／DecorCatalog.UnplacedCount，家裡那份經 HomeLayout 的掛鉤扣掉）。
        /// </summary>
        public enum Room { Shop, Home }

        /// <summary>目前是哪個房間的托盤（Show 時設）。</summary>
        public Room Mode { get; private set; } = Room.Shop;

        /// <summary>提示列圖示高度（畫面 px；24 格的圖，鍵帽約 30px 高）。</summary>
        const float HintIconH = 30f;

        /// <summary>
        /// 托盤格的列：固定一排、超過就翻頁（2026-11-27，見 <see cref="Pager"/>；以前是換行、最多兩排 148，再多就溢出托盤）。
        /// 一格佔 66 ＋ margin 3×2 ＝ 72（像素外觀；舊外觀 78＋6 ＝ 84）。格子區固定 78 高：多出的 6 是數量徽章
        /// （.sk .tray-item .sk-badge 壓在格子右下角外 6 px），格子區 overflow 隱藏，不留這 6 會被切掉。
        /// 一頁幾格照格子區實際寬度算（扣掉右邊徽章的 6；托盤寬 92%、最多 880，跟畫面比例有關；寬度變了才重算）。
        /// </summary>
        const float CellH = 78f;
        const float CellW = 72f, CellWOld = 84f;

        UIDocument doc;
        VisualElement root, itemsBox, hintRow;   // itemsBox ＝ pager.Body
        Pager pager;
        bool built;
        bool skin;        // 這次用的是不是像素外觀（Build 時決定）
        /// <summary>像素外觀：托盤格的浮動說明（名稱）；掛在托盤上，清單重建時要收起來。</summary>
        VisualElement trayBox;
        Label tip;
        /// <summary>提示列的各組（名稱 → 元素）。名稱見 BuildHints。</summary>
        readonly Dictionary<string, VisualElement> groups = new();
        VisualElement anchorIcon, whyIcon;
        string anchorName, whyName;
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）

        /// <summary>點了托盤裡的東西要做什麼（由 ShopRoomEditor 指派）。</summary>
        public Action<string, bool> onPick;   // (id, isDecor)

        /// <summary>
        /// 在托盤格上**按下**滑鼠（還沒放開）—— 家裡佈置用來「從托盤拖出來」（HomeArrange 指派；店裡是 null）。
        /// 放開時如果還在同一格上，按鈕照樣會送 onPick（家裡那邊把 onPick 設成 null，不會做兩次）。
        /// </summary>
        public Action<string, bool> onPress;  // (id, isDecor)

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 15;
            if (doc.panelSettings == null)
                Debug.LogError("[ShopRoomTray] 找不到 Resources/ui/UIPanelSettings");
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        public void Show(Room room = Room.Shop)
        {
            if (!built) Build();
            if (!built) return;
            Mode = room;
            if (room == Room.Shop) onPress = null;     // 托盤跨場景常駐：家裡留下的「按下」回呼不能帶進店裡
            anim.Show();                // 淡入（邏輯上這一行就算開著，見 UIAnim）
            pager.Reset();               // 每次進佈置模式都從第 1 頁看
            Refresh();
        }

        /// <summary>
        /// 這個螢幕座標（Input.mousePosition）落在托盤上嗎（家裡佈置：拖到托盤上放開＝收回；點在托盤上不算點地板）。
        /// 托盤沒開回 false。
        /// </summary>
        public bool PointerOverTray(Vector2 screenPos)
        {
            if (!built || anim == null || !anim.IsOpen || trayBox == null || trayBox.panel == null) return false;
            // 面板座標的 y 是往下的，Input.mousePosition 是往上的 → 先翻過來（同 CornerHud.BlocksWorldClick）
            var p = RuntimePanelUtils.ScreenToPanel(trayBox.panel, new Vector2(screenPos.x, Screen.height - screenPos.y));
            return trayBox.worldBound.Contains(p);
        }

        public void Hide()
        {
            anim?.Hide();                // 淡出只是視覺殘影，邏輯上這一行就算關了
        }

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[ShopRoomTray] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            UiSkin.Apply(root);           // 8-bit 外觀（總開關 UiSkin.Enabled）
            skin = UiSkin.On;
            root.pickingMode = PickingMode.Ignore;   // 只有托盤本身吃滑鼠，其他地方要能拖家具
            CjkFont.Apply(root);
            Sfx.BindClicks(root);         // 托盤按鈕的 click 音（放得下時會被 place 蓋過）

            var layer = new VisualElement();
            layer.AddToClassList("tray-layer");
            layer.pickingMode = PickingMode.Ignore;
            root.Add(layer);

            var tray = new VisualElement();
            tray.AddToClassList("tray");
            layer.Add(tray);

            var head = new VisualElement();
            head.AddToClassList("tray-head");
            tray.Add(head);

            // 標題改成木槌圖示（原本是「佈置模式」四個字）
            head.Add(UiIcons.Element("act_edit", 34f, "tray-title-icon"));

            hintRow = new VisualElement();
            hintRow.AddToClassList("tray-hints");
            hintRow.pickingMode = PickingMode.Ignore;
            head.Add(hintRow);
            BuildHints();

            // [格子區（一排，固定 72 高）][◀ n/m ▶]
            var itemsRow = new VisualElement();
            itemsRow.style.flexDirection = FlexDirection.Row;
            itemsRow.style.alignItems = Align.Center;
            tray.Add(itemsRow);

            pager = new Pager(10, CellH, Refresh);
            itemsBox = pager.Body;
            itemsBox.AddToClassList("tray-items");
            itemsBox.style.flexDirection = FlexDirection.Row;   // ⚠️ SkinBase 的 .pg-body 是直排，這裡要橫排
            itemsBox.style.flexWrap = Wrap.NoWrap;
            itemsBox.style.flexGrow = 1;
            itemsBox.style.flexShrink = 1;
            itemsBox.style.flexBasis = 0;
            itemsBox.RegisterCallback<GeometryChangedEvent>(OnItemsGeometry);
            itemsRow.Add(itemsBox);

            pager.Bar.AddToClassList("pg-bar--dark");          // 深木底：頁碼用米白字
            pager.Bar.style.marginLeft = 9;
            itemsRow.Add(pager.Bar);

            trayBox = tray;
            if (skin) tip = UiSkin.MakeTip(tray);     // 托盤格的名稱（滑過才出現）

            root.style.display = DisplayStyle.None;
            anim = UIAnim.SlideUp(root, tray);                // 從下方滑上來
            built = true;
        }

        /// <summary>
        /// 建一次全部的圖示組。順序就是畫面上由左到右的順序：
        ///   操作（拖曳／從托盤拿／F 轉向／T 基準角／右鍵收回）｜圖例（綠／紅／藍格、陳列位圈）｜R 完成、Esc 取消
        /// </summary>
        void BuildHints()
        {
            Group("drag", "mouse_drag", "act_move");
            Group("place", "mouse_left", "act_unstash");
            Group("flip", "key_f", "act_rotate");
            anchorIcon = Group("anchor", "key_t", "anchor_0")[1];
            anchorName = "anchor_0";
            Group("stash", "mouse_right", "act_stash");
            Sep("sep1");
            var why = Group("why", "st_no", "blk_overlap");
            whyIcon = why[1];
            whyName = "blk_overlap";
            groups["why"].AddToClassList("hint-group--bad");
            Group("lg_green", "tile_green", "st_ok");
            Group("lg_red", "tile_red", "st_no");
            Group("lg_blue", "tile_blue", "act_walk");
            Group("rg_green", "ring_green", "st_ok");
            Group("rg_orange", "ring_orange", "act_swap");
            Group("rg_out", "act_return");
            Sep("sep2");
            Group("done", "key_r", "act_done");
            Group("cancel", "key_esc", "act_cancel");
            Group("esc_done", "key_esc", "act_done");      // 家裡：每一步都當下存了，Esc 也是「完成」（同後花園）
        }

        List<VisualElement> Group(string key, params string[] icons)
        {
            var g = new VisualElement();
            g.AddToClassList("hint-group");
            g.pickingMode = PickingMode.Ignore;
            var list = new List<VisualElement>();
            foreach (var n in icons)
            {
                var el = UiIcons.Element(n, HintIconH, "hint-icon");
                g.Add(el);
                list.Add(el);
            }
            hintRow.Add(g);
            groups[key] = g;
            return list;
        }

        void Sep(string key)
        {
            var s = new VisualElement();
            s.AddToClassList("hint-sep");
            s.pickingMode = PickingMode.Ignore;
            hintRow.Add(s);
            groups[key] = s;
        }

        /// <summary>
        /// 依狀態切換提示列（只在狀態變的時候由 ShopRoomEditor 叫，不要每幀叫）。
        /// </summary>
        /// <param name="anchor">選中家具目前的基準角（0 前、1 左、2 右）—— T 那組的圖跟著換</param>
        /// <param name="canStash">選中的能不能收回托盤（販售桌不行 → 右鍵那組隱藏）</param>
        /// <param name="why">拖家具時放不下的原因圖示名（null＝放得下）</param>
        public void SetHint(HintMode mode, int anchor = 0, bool canStash = true, string why = null)
        {
            if (!built) return;

            bool idle = mode == HintMode.Idle, furn = mode == HintMode.Furniture,
                 drag = mode == HintMode.DragFurniture, good = mode == HintMode.Good;
            Show("drag", true);
            Show("place", idle);
            Show("flip", furn);
            Show("anchor", furn);
            Show("stash", idle || (furn && canStash));
            Show("sep1", true);
            Show("why", drag && why != null);
            Show("lg_green", !good);
            Show("lg_red", !good);
            Show("lg_blue", !good);
            Show("rg_green", good);
            Show("rg_orange", good);
            Show("rg_out", good);
            Show("sep2", true);
            Show("done", true);
            Show("cancel", true);
            Show("esc_done", false);

            // 拖家具時：圖例是重點（亮起），其他照常
            groups["lg_green"].EnableInClassList("hint-group--hot", drag && why == null);
            groups["lg_red"].EnableInClassList("hint-group--hot", drag && why != null);
            groups["lg_blue"].EnableInClassList("hint-group--hot", drag);

            string an = "anchor_" + Mathf.Clamp(anchor, 0, 2);
            if (an != anchorName) { anchorName = an; UiIcons.Set(anchorIcon, an, HintIconH); }
            if (why != null && why != whyName) { whyName = why; UiIcons.Set(whyIcon, why, HintIconH); }
        }

        /// <summary>
        /// 家裡佈置的提示列（HomeArrange 在狀態變的時候叫）：
        ///   沒拿東西　[拖曳][移動] [左鍵][從托盤拿] [右鍵][收回]（＋選中一件時 [F][翻面]）｜[綠格✓][紅格×]｜[R][完成] [Esc][完成]
        ///   拿著東西　[F][翻面]｜[綠格✓][紅格×]（放不下時 [×][原因] 亮起）｜[R][完成] [Esc][完成]
        /// </summary>
        /// <param name="holding">手上拿著（拖曳中／從托盤拿出來還沒放下）</param>
        /// <param name="selected">選中一件（F 會翻它）</param>
        /// <param name="why">放不下的原因圖示名（null＝放得下或沒拿東西）</param>
        /// <param name="whySprite">原因用任意圖（例如貓）時給這個，蓋過 why</param>
        public void SetHomeHint(bool holding, bool selected, string why = null, Sprite whySprite = null)
        {
            if (!built) return;
            bool bad = holding && (why != null || whySprite != null);
            Show("drag", !holding);
            Show("place", !holding);
            Show("flip", holding || selected);
            Show("anchor", false);
            Show("stash", !holding);
            Show("sep1", true);
            Show("why", bad);
            Show("lg_green", true);
            Show("lg_red", true);
            Show("lg_blue", false);
            Show("rg_green", false);
            Show("rg_orange", false);
            Show("rg_out", false);
            Show("sep2", true);
            Show("done", true);
            Show("cancel", false);
            Show("esc_done", true);

            groups["lg_green"].EnableInClassList("hint-group--hot", holding && !bad);
            groups["lg_red"].EnableInClassList("hint-group--hot", bad);
            groups["lg_blue"].EnableInClassList("hint-group--hot", false);

            if (whySprite != null)
            {
                string key = "sprite:" + whySprite.name;
                if (key != whyName)
                {
                    whyName = key;
                    whyIcon.style.height = HintIconH;
                    whyIcon.style.width = HintIconH * UiIcons.Aspect(whySprite);
                    whyIcon.style.backgroundImage = new StyleBackground(whySprite);
                }
            }
            else if (why != null && why != whyName) { whyName = why; UiIcons.Set(whyIcon, why, HintIconH); }
        }

        void Show(string key, bool on)
        {
            if (!groups.TryGetValue(key, out var g)) return;
            var want = on ? DisplayStyle.Flex : DisplayStyle.None;
            if (g.style.display != want) g.style.display = want;
        }

        /// <summary>格子區的寬度定了（或變了）→ 重算一頁幾格。</summary>
        void OnItemsGeometry(GeometryChangedEvent e)
        {
            float w = e.newRect.width;
            if (w <= 0f) return;
            int cols = Mathf.Max(1, Mathf.FloorToInt((w - 6f) / (skin ? CellW : CellWOld)));
            if (cols == pager.PerPage) return;
            pager.SetPerPage(cols);
            Refresh();
        }

        public void Refresh()
        {
            if (!built) return;

            UiSkin.HideTip(tip);                       // 被 Clear 掉的格子不會再送 PointerLeave
            var list = new List<(string id, string name, int left, Sprite sp, bool decor)>();

            bool home = Mode == Room.Home;      // 家裡：只列能擺家裡的（陳列類只能擺店裡）

            // 家具與貨架（吃格盤）
            foreach (var f in Furniture.All)
            {
                if (home && !Furnishings.CanPlaceAtHome(f.Id)) continue;
                int left = RoomLayout.Unplaced(f.Id);
                if (left <= 0) continue;
                list.Add((f.Id, f.Name, left, GameArt.FurnitureArt(f.Id), false));
            }

            // 裝飾（自由座標）
            foreach (var d in Decor.Catalog)
            {
                if (home && !Furnishings.CanPlaceAtHome(d.Id)) continue;
                int left = DecorCatalog.UnplacedCount(d.Id);
                if (left <= 0) continue;
                list.Add((d.Id, d.Name, left, GameArt.Decoration(d.Id), true));
            }

            // 拿出一件放進房間 → 托盤少一格：頁碼只夾回範圍內，不跳回第 1 頁
            pager.Render(list.Count, i =>
            {
                var it = list[i];
                var cell = Item(it.id, it.name, it.left, it.sp, it.decor);
                cell.style.flexShrink = 0;
                return cell;
            }, "空的 · 去花店買", "tray-empty");
        }

        VisualElement Item(string id, string name, int count, Sprite sp, bool isDecor)
        {
            var b = new Button(() => onPick?.Invoke(id, isDecor)) { focusable = false };   // 不拿焦點：Space 不會「再點一次」
            b.AddToClassList("tray-item");
            // 按下就送（家裡佈置：從托盤直接拖出來）。TrickleDown：按鈕自己的 Clickable 會吃掉 PointerDown，要在它之前拿到
            b.RegisterCallback<PointerDownEvent>(e => { if (e.button == 0) onPress?.Invoke(id, isDecor); }, TrickleDown.TrickleDown);

            var icon = new VisualElement();
            icon.AddToClassList("tray-icon");
            icon.pickingMode = PickingMode.Ignore;
            if (sp != null) icon.style.backgroundImage = new StyleBackground(sp);
            b.Add(icon);

            if (skin)
            {
                // 像素外觀：格子裡只有圖＋數量徽章；名稱放到滑過時的浮動說明（托盤貼著畫面下緣 → 顯示在格子上方）
                if (count > 1) b.Add(UiSkin.Badge("×" + count));
                UiSkin.Tip(b, tip, trayBox, name, above: true);
                return b;
            }

            var l = new Label(count > 1 ? $"{name} ×{count}" : name);
            l.AddToClassList("tray-name");
            b.Add(l);

            return b;
        }
    }
}
