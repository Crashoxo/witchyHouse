using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 店內佈置模式：按 R 進入，用滑鼠把家具、裝飾、**架上的商品**拖到想要的位置，再按 R 完成（Esc 取消）。
    ///
    /// 對應 Cocos 的 DecorRoom.ts 的另一半（enterEdit / makeDraggable / drawGrid / buildTray）。
    ///
    /// 三種東西的規則不一樣：
    ///   **家具** 吃等距格盤 —— 放開時吸附到最近的格；能不能放由 RoomLayout.Check
    ///            一次判完（超出地板／重疊／門口／貨架前的走道／圖穿出牆外），
    ///            擋住的格子會標紅色、原因寫在家具頭上的小標籤與托盤那行提示上。
    ///   **裝飾** 是自由座標 —— 可以擺在桌上、架上任何位置，只夾在菱形地板內。
    ///   **商品** 吃家具的陳列位（ShopRoomView.Spots）—— 拖起來時所有位子都標出來（綠＝空位、橘＝會交換），
    ///            放開落到最近的位子；位置記在 ShopDisplay（商品名 → 家具 uid＋第幾個位子）。
    ///
    /// ⚠️ 拖曳中會即時改物件位置，放下時就寫存檔（RoomLayout.SetPlaced / DecorCatalog.Move / ShopDisplay.Set）——
    ///    所以進場時要拍三份**深複本**快照，按 Esc 才整批還原得回去。
    ///
    /// ── 提示（玩家回饋「擺放貨架的提示不夠明顯」之後加強的）──────────
    ///   · 進佈置模式時地板壓暗（家具不暗），格線用有亮邊的菱形，門口紅格、走道藍格用實心＋粗邊
    ///   · 佔地預覽綠／紅加粗、緩慢脈動（unscaledTime，沒有每幀配置）；放不下時「想去的那一格」畫紅色殘影
    ///   · 拖貨架時連它自己需要的走道一起用藍框預覽
    ///   · 世界空間小標籤跟著被選的東西走：可以放／放不下的原因、F／T／右鍵這些按鍵
    ///
    /// ── 說明改成圖示（玩家回饋「解釋擺放東西不用要字，用圖文的方式，解釋的文字太多了」）──
    ///   · 托盤提示列＝一排圖示組（ShopRoomTray.SetHint(HintMode…)），依狀態只顯示相關的那幾組
    ///   · 頭上的標籤＝圖示泡泡（SpriteRenderer，不用 TextMesh）：綠勾／紅叉＋原因圖／F・T・右鍵
    ///   · 放下失敗、轉不過去 → 不跳句子 Toast，改成 deny 音＋東西抖一下閃紅＋泡泡短暫顯示原因
    ///   · 第一次進店 → 圖解卡（UI/ShopEditIntroCard），不是長句 Toast
    ///   圖都是 tools/gen_ui_icons.py 畫的（UI/UiIcons 依名稱取）。
    ///
    /// ── 關店才能佈置（玩家回饋「關店才可以擺放貨架」）──
    ///   ShopSign.IsOpen 時按 R 進不去：deny＋圖示 Toast「開店招牌 → 滑鼠左鍵 → 關店招牌 → R」
    ///   ＋上方工具列的開關店鈕抖一下（CornerHud.NudgeShop）、旁邊的 R 提示彈一下。
    ///   只擋「進入」：店裡還有沒走完的顧客不擋。佈置中店被打開（理論上不會）→ 照「完成」收工。
    /// </summary>
    public class ShopRoomEditor : MonoBehaviour
    {
        public static ShopRoomEditor Instance { get; private set; }

        public static ShopRoomEditor Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("ShopRoomEditor").AddComponent<ShopRoomEditor>();
        }

        public bool Editing { get; private set; }

        Camera cam;
        ShopRoomView view;

        // 拖曳中的東西（家具／裝飾）
        GameObject dragGo;
        PlacedFurniture dragFurn;      // 拖家具時有值
        int dragDecorIndex = -1;       // 拖裝飾時 >= 0
        Vector3 dragOffset;
        Cell dragOrigCell;
        int dragOrigAnchor;
        Vector2 dragOrigPos;
        /// <summary>拖曳中最後一個「放得下」的格子 —— 放不下時圖就停在這，不會穿進牆裡。</summary>
        Cell lastValidCell;
        /// <summary>那一格當時用的基準角 —— SnapToWall 會在拖曳中改基準角，
        /// 停在舊格子卻套新基準角的話，圖會跳到另一個角上（一樣會穿牆）。</summary>
        int lastValidAnchor;
        /// <summary>拖曳中「玩家想去的那一格」為什麼放不下（Ok＝放得下）。</summary>
        PlaceBlock dragBlock = PlaceBlock.Ok;
        /// <summary>擋住我的那幾格 —— 標成紅色，玩家才知道是疊到什麼。</summary>
        readonly List<Cell> conflictCells = new();

        // 拖曳中的商品
        ShopRoomView.GoodPlacement dragGood;
        readonly List<Vector3> dragGoodOrig = new();
        Vector3 dragGoodGrab;
        /// <summary>放開的話會落在哪個陳列位（null ＝ 離每個位子都太遠 → 回原位）。</summary>
        ShopRoomView.DisplaySpot goodTarget;
        /// <summary>放開時離陳列位中心多近才算落在那格（世界 px）。位子之間大約隔 23～30px。</summary>
        const float GoodPickRange = 34f;

        /// <summary>選中的商品（名字；Rebuild 會換掉所有物件，所以記名字不記物件）。</summary>
        string selectedGood;
        GameObject selectedGoodGo;

        // 進入編輯時的快照，按 Esc 還原用（⚠️ 一定要深複本，見 RoomLayout.PlacedSnapshot）
        List<PlacedFurniture> snapFurn;
        List<PlacedDecor> snapDecor;
        List<ShopDisplay.Entry> snapDisplay;

        readonly List<SpriteRenderer> gridCells = new();
        /// <summary>佔地預覽：拖曳/選取中那件家具實際會佔到的格子（綠＝放得下）。</summary>
        readonly List<SpriteRenderer> footprint = new();
        /// <summary>放不下時「玩家想去的那一格」的紅色殘影。</summary>
        readonly List<SpriteRenderer> ghost = new();
        /// <summary>擋住我的那幾格（紅，畫在家具之上）。</summary>
        readonly List<SpriteRenderer> conflictMarks = new();
        /// <summary>選中／拖曳中的貨架自己需要的走道（藍框）。</summary>
        readonly List<SpriteRenderer> aisleMarks = new();
        /// <summary>拖商品時每個陳列位的小圈。</summary>
        readonly List<SpriteRenderer> spotMarks = new();
        SpriteRenderer dimmer;
        WorldTag worldTag;
        Color footColor = FootOk;

        /// <summary>目前選中的家具（拖過或點過的），F 翻面 / T 換基準角都作用在它身上。</summary>
        PlacedFurniture selected;
        GameObject selectedGo;

        // ── 顏色（集中在這裡調）──
        static readonly Color FootOk = new(0.25f, 1f, 0.4f, 0.85f);
        static readonly Color FootBad = new(1f, 0.18f, 0.18f, 0.9f);
        static readonly Color ConflictCol = new(1f, 0.15f, 0.12f, 0.8f);
        static readonly Color AisleCol = new(0.35f, 0.72f, 1f, 1f);
        static readonly Color GridCol = new(1f, 1f, 1f, 0.38f);
        static readonly Color DoorCol = new(1f, 0.3f, 0.28f, 0.75f);
        static readonly Color AisleGridCol = new(0.35f, 0.7f, 1f, 0.7f);
        static readonly Color SpotFree = new(0.35f, 1f, 0.5f, 0.95f);
        static readonly Color SpotSwap = new(1f, 0.68f, 0.2f, 0.95f);
        static readonly Color SpotOwn = new(1f, 1f, 1f, 0.55f);
        static readonly Color TagOk = new(0.13f, 0.55f, 0.24f, 0.95f);
        static readonly Color TagBad = new(0.78f, 0.13f, 0.12f, 0.96f);
        static readonly Color TagSwap = new(0.8f, 0.45f, 0.08f, 0.96f);
        static readonly Color TagIdle = new(0.14f, 0.11f, 0.2f, 0.92f);

        // ── 排序（集中寫，免得互相蓋錯）──
        const int OrderDim = -9600;       // 底圖（-10000）之上、格線之下：只壓暗地板，家具不暗
        const int OrderGrid = -9500;
        const int OrderFoot = -9400;      // 格線之上、家具之下
        const int OrderGhost = -9390;
        const int OrderAisle = -9380;
        const int OrderConflict = 4000;   // 家具之上（家具 order 是 -pos.y，最大約 260）
        const int OrderSpot = 4500;       // 商品（家具＋1）之上
        const int OrderDragGood = 5000;   // 拖著走的商品蓋過一切（標籤除外）
        const int OrderTag = 9100;

        const string TipKey = "witch.tips.shopedit";

        void Awake() { Instance = this; cam = Camera.main; }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void OnEnable() => ShopSign.Changed += OnSignChanged;
        void OnDisable() => ShopSign.Changed -= OnSignChanged;

        /// <summary>
        /// 佈置中店被打開了（正常不會：佈置中走不到門口招牌）—— 防禦性處理：照「完成」收工，改過的都留著。
        /// </summary>
        void OnSignChanged()
        {
            if (Editing && ShopSign.IsOpen && view != null) Finish();
        }

        /// <summary>
        /// 第一次進店跳一次圖解卡 —— 玩家回饋「不知道可以佈置」。之後靠 CornerHud 上常駐的 [招牌][R][木槌]。
        /// 延遲一下才跳：剛進店時還有「家具卡牆已挪回」「不在時賣掉了…」那幾則 Toast，疊在一起會被淹掉。
        /// </summary>
        IEnumerator Start()
        {
            if (SaveManager.GetString(TipKey) == "1") yield break;
            yield return new WaitForSecondsRealtime(1.5f);
            SaveManager.SetString(TipKey, "1");
            UI.ShopEditIntroCard.Show();
        }

        bool Dragging => dragGo != null || dragGood != null;

        void Update()
        {
            view = ShopRoomView.Instance;
            if (view == null) return;

            // R 切換佈置模式。⚠️ 開著別的面板時不吃，不然在上架面板裡打字會誤觸
            if (!UIState.ModalOpen && Input.GetKeyDown(KeyCode.R))
            {
                if (Editing) Finish(); else Enter();
                return;
            }

            if (!Editing) return;

            if (Input.GetKeyDown(KeyCode.Escape)) { Cancel(); return; }

            // 選中一件家具之後：F 翻面、T 換基準角（靠牆的貨架要用）。
            // ⚠️ 拖曳中不吃：翻面會 SetPlaced＋Rebuild，手上拖著的物件會被換掉。
            if (selected != null && !Dragging)
            {
                if (Input.GetKeyDown(KeyCode.F)) { Flip(); return; }
                if (Input.GetKeyDown(KeyCode.T)) { CycleAnchor(); return; }
            }

            if (Input.GetMouseButtonDown(1) && !Dragging) { PickUp(); return; }   // 右鍵收回托盤
            if (Input.GetMouseButtonDown(0)) BeginDrag();
            else if (Input.GetMouseButton(0) && dragGo != null) Drag();
            else if (Input.GetMouseButton(0) && dragGood != null) DragGood();
            else if (Input.GetMouseButtonUp(0) && dragGo != null) EndDrag();
            else if (Input.GetMouseButtonUp(0) && dragGood != null) EndGoodDrag();
        }

        /// <summary>
        /// 每幀只做「便宜的」事：脈動（改既有 SpriteRenderer 的 color）、標籤跟著東西走。
        /// ⚠️ 不配置記憶體、不 new 物件、不重設字串 —— 字串只在狀態變的時候由 UpdateHint 設。
        /// </summary>
        void LateUpdate()
        {
            if (!Editing || view == null) return;

            float t = Time.unscaledTime;
            UpdateShake(t);
            if (flashUntil > 0f && t > flashUntil) { flashUntil = 0f; UpdateHint(); }   // 泡泡的「放不下」閃示結束
            float pulse = 0.7f + 0.3f * (0.5f + 0.5f * Mathf.Sin(t * 5f));
            Pulse(footprint, footColor, pulse);
            Pulse(ghost, FootBad, pulse);
            Pulse(conflictMarks, ConflictCol, pulse);

            // 拖商品時，會落下的那一格放大閃一下
            if (dragGood != null && goodTarget != null)
            {
                int i = view.Spots.IndexOf(goodTarget);
                if (i >= 0 && i < spotMarks.Count && spotMarks[i] != null)
                {
                    float s = SpotScale * (1.35f + 0.2f * Mathf.Sin(t * 8f));
                    spotMarks[i].transform.localScale = new Vector3(s, s, 1f);
                }
            }

            UpdateTagPosition();
        }

        static void Pulse(List<SpriteRenderer> pool, Color baseCol, float k)
        {
            var c = new Color(baseCol.r, baseCol.g, baseCol.b, baseCol.a * k);
            for (int i = 0; i < pool.Count; i++)
            {
                var sr = pool[i];
                if (sr != null && sr.gameObject.activeSelf) sr.color = c;
            }
        }

        // ──────────── 進出 ────────────

        /// <summary>上一次「開店中不能佈置」的提示時間 —— 連按 R 不要疊一串 Toast。</summary>
        float lastLockedHint = -10f;

        void Enter()
        {
            // 關店才能佈置（玩家回饋）。只擋「進入」—— 店裡還有沒走完的顧客不管。
            if (ShopSign.IsOpen)
            {
                Sfx.Play("deny");
                UI.CornerHud.Instance?.NudgeEdit();
                UI.CornerHud.Instance?.NudgeShop();      // 工具列的開關店鈕抖一下：「點這裡」
                if (Time.unscaledTime - lastLockedHint > 1.5f)
                {
                    lastLockedHint = Time.unscaledTime;
                    // 開店招牌 → 滑鼠左鍵 → 關店招牌 → R：「先點上方工具列的招牌關店，再按 R」
                    UI.Toast.ShowIcons(new[] { "shop_open", "arrow", "mouse_left", "shop_closed", "arrow", "key_r" }, null, 2.6f);
                }
                return;
            }

            Editing = true;
            Sfx.Play("ui-open");

            // 快照：按 Esc 要能整批還原。⚠️ 家具一定要深複本 —— PlacedList() 是淺複本，
            // 拖曳會直接改裡面的物件，快照會跟著被改掉（以前第一次拖的那件 Esc 還原不回去）。
            snapFurn = RoomLayout.PlacedSnapshot();
            snapDecor = DecorCatalog.PlacedList();
            snapDisplay = ShopDisplay.Snapshot();

            ResetDragState();
            selected = null; selectedGo = null;
            selectedGood = null; selectedGoodGo = null;
            BuildGrid();
            ShowDimmer(true);

            var tray = UI.ShopRoomTray.Ensure();
            tray.onPick = PlaceFromTray;
            tray.Show();
            UpdateHint();
        }

        void Finish()
        {
            // 拖到一半按 R：先照「放開」處理完（驗格子、寫存檔），不然拖曳中改過的資料沒存到
            if (dragGo != null) EndDrag();
            if (dragGood != null) EndGoodDrag();

            Editing = false;
            LeaveCommon();
            // 拖曳過程已經即時寫進 RoomLayout / DecorCatalog / ShopDisplay 的資料，這裡只要收工
            // （不跳「佈置完成」的字：托盤收起來＋收工音就看得出來）
            Sfx.Play("ui-close");
            view.Rebuild();
        }

        void Cancel()
        {
            Editing = false;
            ResetDragState();
            LeaveCommon();
            RoomLayout.SetPlaced(snapFurn);
            DecorCatalog.SetPlaced(snapDecor);
            ShopDisplay.Restore(snapDisplay);
            Sfx.Play("ui-close");
            UI.Toast.ShowIcons(new[] { "key_esc", "act_return" }, "還原");
            view.Rebuild();
        }

        /// <summary>離開佈置模式時共用的收尾：提示全部收起來。</summary>
        void LeaveCommon()
        {
            selected = null; selectedGo = null;
            selectedGood = null; selectedGoodGo = null;
            StopShake();
            flashUntil = 0f;
            ClearGrid();
            ClearFootprint();
            ShowConflicts(null);
            ShowSpotMarks(false);
            ShowDimmer(false);
            worldTag?.Hide();
            UI.ShopRoomTray.Instance?.Hide();
        }

        /// <summary>
        /// 手上拖著的東西全部放掉（不寫存檔）。⚠️ Esc 取消時一定要清：不清的話 dragGo 會指著被 Rebuild 砍掉的物件，
        /// 下次進佈置模式一按住滑鼠就去拖一個已經不存在的東西。
        /// </summary>
        void ResetDragState()
        {
            dragGo = null; dragFurn = null; dragDecorIndex = -1;
            dragBlock = PlaceBlock.Ok;
            dragGood = null; goodTarget = null;
            dragGoodOrig.Clear();
        }

        // ──────────── 拖曳 ────────────

        Vector3 MouseWorld()
        {
            var w = cam.ScreenToWorldPoint(Input.mousePosition);
            w.z = 0f;
            return w;
        }

        void BeginDrag()
        {
            StopShake();                 // 抖到一半又抓起來：先把位置還原，不然拖曳的起點會偏
            flashUntil = 0f;
            var m = MouseWorld();

            // ① 先找商品 —— 商品畫在家具上面、又小，點到它就是要搬它（不然永遠只會抓到後面的貨架）。
            //    疊在一起時拿畫在最上面（sortingOrder 最大）的那個。
            ShopRoomView.GoodPlacement hitGood = null;
            int hitOrder = int.MinValue;
            foreach (var gp in view.Goods)
                foreach (var g in gp.Gos)
                {
                    if (g == null || !g.activeInHierarchy) continue;
                    var sr = g.GetComponent<SpriteRenderer>();
                    if (sr == null || sr.sortingOrder <= hitOrder) continue;
                    var b = sr.bounds;
                    b.Expand(new Vector3(6f, 6f, 0f));       // 商品圖只有 20px 上下，放寬一點比較好點
                    if (!b.Contains(new Vector3(m.x, m.y, b.center.z))) continue;
                    hitGood = gp; hitOrder = sr.sortingOrder;
                }
            if (hitGood != null) { BeginGoodDrag(hitGood, m); return; }

            // ② 再找裝飾（它們通常疊在家具上面），最後找家具
            foreach (var (go, index) in view.Decors)
            {
                if (go == null || !HitTest(go, m)) continue;
                dragGo = go; dragDecorIndex = index; dragFurn = null;
                selected = null; selectedGo = null; selectedGood = null; selectedGoodGo = null;
                ClearFootprint();
                dragOrigPos = go.transform.position;
                dragOffset = go.transform.position - m;
                UpdateHint();
                return;
            }
            foreach (var (go, data) in view.Furnitures)
            {
                if (go == null || !HitTest(go, m)) continue;
                dragGo = go; dragFurn = data; dragDecorIndex = -1;
                selected = data; selectedGo = go;      // 選中 → F/T 作用在它身上
                selectedGood = null; selectedGoodGo = null;
                dragOrigCell = new Cell(data.gx, data.gy);
                dragOrigAnchor = data.anchor;
                lastValidCell = dragOrigCell;
                lastValidAnchor = data.anchor;
                dragBlock = PlaceBlock.Ok;
                ShowConflicts(null);
                dragOffset = go.transform.position - m;
                // 拖曳中它原本的走道不算擋路（Check 會 skip 它自己）—— 格線上的藍格先拿掉，改用跟著它走的藍框
                UpdateGridColors(data);
                ShowFootprint(data, true);
                UpdateHint();
                return;
            }

            // 點空地＝取消選取
            selected = null; selectedGo = null;
            selectedGood = null; selectedGoodGo = null;
            ClearFootprint();
            UpdateHint();
        }

        /// <summary>
        /// 貨架靠近後牆就吸上去，並順手把基準角設成對的那一邊。
        ///
        /// 等距房間的兩面後牆是 gx=0（左後牆）與 gy=0（右後牆）。靠牆的貨架要**貼齊**
        /// 才好看 —— 差一格就會露出一條縫，用滑鼠很難每次都拖準，所以在 1 格內自動吸。
        /// </summary>
        Cell SnapToWall(Cell cell, int w, int h)
        {
            const int Near = 1;      // 離牆幾格以內就吸上去
            bool nearLeft = cell.gx <= Near;
            bool nearRight = cell.gy <= Near;

            // 兩邊都靠近（角落）→ 選比較近的那面
            if (nearLeft && nearRight)
            {
                if (cell.gx <= cell.gy) nearRight = false; else nearLeft = false;
            }

            if (nearLeft)
            {
                cell.gx = 0;
                SetWallAnchor(cell, FurnitureAnchor.Left);
            }
            else if (nearRight)
            {
                cell.gy = 0;
                SetWallAnchor(cell, FurnitureAnchor.Right);
            }
            return cell;
        }

        /// <summary>
        /// 靠牆時挑一個「圖不會卡進牆裡」的基準角：先試這面牆偏好的那個，不行就退回前角。
        ///
        /// ⚠️ 偏好的基準角只有在**翻面狀態配對正確**時才成立（左後牆配不翻面、右後牆配翻面）。
        ///    配錯的話那個角會把整張圖平移到牆面上（玩家實際踩到的 bug：沒翻面卻吸到右後牆），
        ///    所以一定要驗過再套 —— 不能像以前那樣無條件設。
        /// </summary>
        void SetWallAnchor(Cell cell, FurnitureAnchor prefer)
        {
            if (RoomLayout.Check(dragFurn.id, cell.gx, cell.gy, dragFurn, dragFurn.flip, prefer)
                == PlaceBlock.Ok)
            { SetAnchor((int)prefer); return; }
            SetAnchor((int)FurnitureAnchor.Front);
        }

        /// <summary>
        /// 這一格放不放得下 —— 重疊、門口、走道、穿牆全部由 RoomLayout.Check 一次判完，
        /// 回傳的是**哪一條規則擋的**，才有辦法把原因講給玩家聽。
        /// </summary>
        PlaceBlock CheckCell(PlacedFurniture p, Cell cell) =>
            RoomLayout.Check(p.id, cell.gx, cell.gy, p, p.flip, p.Anchor, conflictCells);

        /// <summary>拖曳中直接改基準角（不重畫，Drag 每幀都會用到新值）。</summary>
        void SetAnchor(int a)
        {
            if (dragFurn == null || dragFurn.anchor == a) return;
            dragFurn.anchor = a;
            if (selected == dragFurn) UpdateHint();
        }

        /// <summary>滑鼠有沒有點在這個物件的圖上（用 SpriteRenderer 的 bounds 判斷）。</summary>
        static bool HitTest(GameObject go, Vector3 world)
        {
            var sr = go.GetComponentInChildren<SpriteRenderer>();
            return sr != null && sr.bounds.Contains(new Vector3(world.x, world.y, sr.bounds.center.z));
        }

        void Drag()
        {
            var want = MouseWorld() + dragOffset;

            if (dragFurn != null)
            {
                var d = Furniture.ById(dragFurn.id);
                if (d == null) return;
                var (w, h) = dragFurn.Size;          // 轉向後的佔地

                var cell = ShopRoom.WorldToTile(want.x, want.y);
                cell = ShopRoom.ClampCell(cell.gx - (w - 1), cell.gy - (h - 1), w, h);
                if (d.Shelf) cell = SnapToWall(cell, w, h);   // 貨架靠近後牆就吸上去

                // 格子放得下 **而且** 圖不會凸出房間外（貨架比牆高，會穿牆）
                var block = CheckCell(dragFurn, cell);
                bool ok = block == PlaceBlock.Ok;

                // ⚠️ 放不下就**不移動** —— 停在最後一個合法格，像撞到牆一樣。
                //    之前是照樣把圖移過去、只把提示格變紅，結果變成「圖在牆外、格子在別處」，
                //    看起來就是提示格壞掉。圖與提示格一定要指向同一格。
                //    基準角也要一起回到當時的值 —— SnapToWall 每幀都可能改它。
                if (ok) { lastValidCell = cell; lastValidAnchor = dragFurn.anchor; }
                else dragFurn.anchor = lastValidAnchor;
                var use = ok ? cell : lastValidCell;

                var front = RoomLayout.AnchorPos(use.gx, use.gy, w, h, dragFurn.Anchor);
                dragGo.transform.position = new Vector3(front.x, front.y, 0f);
                dragFurn.gx = use.gx; dragFurn.gy = use.gy;

                // 圖本身也染色：綠＝這裡可以、紅＝想去的地方不行（之前的淡橘太接近原色，看不出來）
                Tint(dragGo, ok ? new Color(0.72f, 1f, 0.74f) : new Color(1f, 0.6f, 0.58f));
                // 綠格永遠畫在圖真正落腳的那一格；放不下時另外在「想去的那一格」畫紅色殘影，
                // 玩家才看得出「我想放那裡、但那裡不行」（以前放不下時只剩綠格，紅色從來沒出現過）
                ShowFootprintAt(use.gx, use.gy, w, h, true);
                if (ok) ShowGhost(0, 0, 0, 0);
                else ShowGhost(cell.gx, cell.gy, w, h);
                ShowAisle(dragFurn);

                // 擋住我的那幾格標紅色 —— 「是疊到什麼」要看得見，
                // 不然玩家只覺得莫名其妙拖不過去（原因同時寫在頭上的標籤與托盤那行提示上）
                ShowConflicts(ok ? null : conflictCells);
                if (block != dragBlock) { dragBlock = block; UpdateHint(); }   // 只在變了才重設字串
            }
            else
            {
                // 裝飾：自由座標，只夾在菱形地板內
                var c = ShopRoom.ClampToFloor(want.x, want.y);
                dragGo.transform.position = new Vector3(c.x, c.y, 0f);
                Tint(dragGo, new Color(0.85f, 0.95f, 1f));
            }
        }

        void EndDrag()
        {
            if (dragGo != null) Tint(dragGo, Color.white);

            if (dragFurn != null)
            {
                // 在放不下的地方放開手：東西停在最後一個合法格。原因不寫字 ——
                // 放開後讓它抖一下閃紅、頭上的泡泡短暫顯示 [紅叉][原因圖]（見下面的 Deny）
                bool denied = dragBlock != PlaceBlock.Ok;
                var deniedWhy = dragBlock;

                // Drag 只會停在合法格，正常不會進到這裡；保險起見還是驗一次
                var b = CheckCell(dragFurn, new Cell(dragFurn.gx, dragFurn.gy));
                if (b != PlaceBlock.Ok)
                {
                    dragFurn.gx = dragOrigCell.gx;
                    dragFurn.gy = dragOrigCell.gy;
                    dragFurn.anchor = dragOrigAnchor;     // 基準角也要回去（SnapToWall 可能改過）
                    denied = true;
                    deniedWhy = b;
                }
                // 被規則擋 → deny（由 Deny 播）；真的換了位置 → 放下的「叩」。只是點一下沒搬動就不出聲。
                bool moved = dragFurn.gx != dragOrigCell.gx || dragFurn.gy != dragOrigCell.gy;
                if (!denied && moved) Sfx.Play("place");

                // ⚠️ 用 uid 找回存檔裡的那一筆 —— 以前用「id＋原本的格子」找，但 dragFurn 跟存檔是同一個物件、
                //    格子早就被拖曳改掉了，那個條件根本對不到（只是剛好因為同一個物件而沒出事）。
                var list = RoomLayout.PlacedList();
                foreach (var p in list)
                    if (p.uid == dragFurn.uid)
                    {
                        p.gx = dragFurn.gx; p.gy = dragFurn.gy;
                        p.anchor = dragFurn.anchor;      // 靠牆吸附時會順手改基準角
                        break;
                    }
                RoomLayout.SetPlaced(list);
                if (denied) pendingDeny = deniedWhy;
            }
            else if (dragDecorIndex >= 0)
            {
                DecorCatalog.Move(dragDecorIndex, dragGo.transform.position.x, dragGo.transform.position.y);
                if (((Vector2)dragGo.transform.position - (Vector2)dragOrigPos).sqrMagnitude > 1f) Sfx.Play("place");
            }

            ResetDragState();
            ShowConflicts(null);
            ShowGhost(0, 0, 0, 0);
            view.Rebuild();
            if (Editing) { BuildGrid(); ReselectAfterRebuild(); UpdateHint(); }   // Rebuild 會換掉物件
            // 放不下：Rebuild 之後才對新物件抖（舊的已經被換掉了）
            if (pendingDeny != PlaceBlock.Ok)
            {
                Deny(selectedGo, pendingDeny);
                pendingDeny = PlaceBlock.Ok;
            }
        }

        PlaceBlock pendingDeny = PlaceBlock.Ok;

        // ──────────── 拖商品 ────────────

        void BeginGoodDrag(ShopRoomView.GoodPlacement gp, Vector3 m)
        {
            dragGood = gp;
            selectedGood = gp.Name;
            selectedGoodGo = gp.Gos.Count > 0 ? gp.Gos[0] : null;
            selected = null; selectedGo = null;     // 選商品時 F/T 不作用在家具上
            ClearFootprint();
            ShowConflicts(null);

            dragGoodGrab = m;
            dragGoodOrig.Clear();
            foreach (var g in gp.Gos)
            {
                dragGoodOrig.Add(g != null ? g.transform.position : Vector3.zero);
                var sr = g != null ? g.GetComponent<SpriteRenderer>() : null;
                if (sr != null) sr.sortingOrder = OrderDragGood;    // 拖著走時蓋過家具（放下會整批重擺，不用改回）
            }
            goodTarget = null;
            ShowSpotMarks(true);
            Sfx.Play("pickup");
            UpdateHint();
        }

        void DragGood()
        {
            var m = MouseWorld();
            var delta = m - dragGoodGrab;
            for (int i = 0; i < dragGood.Gos.Count && i < dragGoodOrig.Count; i++)
            {
                var g = dragGood.Gos[i];
                if (g != null) g.transform.position = dragGoodOrig[i] + delta;
            }

            // 找離滑鼠最近的陳列位（太遠就不算，放開會回原位）
            ShopRoomView.DisplaySpot best = null;
            float bestD = GoodPickRange * GoodPickRange;
            foreach (var s in view.Spots)
            {
                float d = ((Vector2)m - s.Center).sqrMagnitude;
                if (d < bestD) { bestD = d; best = s; }
            }
            if (best != goodTarget)
            {
                // 換目標：上一個的放大還原
                int prev = goodTarget != null ? view.Spots.IndexOf(goodTarget) : -1;
                if (prev >= 0 && prev < spotMarks.Count && spotMarks[prev] != null)
                    spotMarks[prev].transform.localScale = new Vector3(SpotScale, SpotScale, 1f);
                goodTarget = best;
                UpdateHint();
            }
        }

        /// <summary>
        /// 放開商品：落在空位（或自己原本的位子之一）→ 指定到那格；落在別的商品上 → 兩種交換；
        /// 離每個位子都太遠 → 什麼都不改（重擺之後就回原位）。
        ///
        /// ⚠️ 交換時兩筆指定都要寫，而且**被拖的那個要最後寫**：ShopDisplay.Set 會把它排到最前面，
        ///    SpawnGoods 的第①輪照這個順序擺 —— 兩個位子在同一層又互相重疊時，玩家手上那個優先拿到位子。
        /// </summary>
        void EndGoodDrag()
        {
            var a = dragGood;
            var t = goodTarget;
            bool changed = false;

            if (a != null && t != null && a.Furn != null && a.Furn.uid > 0 && t.Furn != null && t.Furn.uid > 0)
            {
                bool own = t.Occupant == null || t.Occupant == a.Name;
                if (own)
                {
                    bool same = t.Furn.uid == a.Furn.uid && t.Index == a.Start;
                    if (!same) { ShopDisplay.Set(a.Name, t.Furn.uid, t.Index); changed = true; }
                }
                else
                {
                    var b = view.Goods.Find(x => x.Name == t.Occupant);
                    if (b != null && b.Furn != null && b.Furn.uid > 0)
                    {
                        ShopDisplay.Set(b.Name, a.Furn.uid, a.Start);
                        ShopDisplay.Set(a.Name, b.Furn.uid, b.Start);
                        changed = true;      // 畫面上兩樣直接對調＋place 音，不另外跳字
                    }
                }
            }

            ResetDragState();
            ShowSpotMarks(false);
            view.RefreshGoods();                 // 不管有沒有改都要重擺：手上那幾個被拖離原位了
            selectedGoodGo = FindGoodGo(selectedGood);
            if (changed) Sfx.Play("place");
            UpdateHint();
        }

        GameObject FindGoodGo(string name)
        {
            if (string.IsNullOrEmpty(name) || view == null) return null;
            foreach (var gp in view.Goods)
                if (gp.Name == name && gp.Gos.Count > 0) return gp.Gos[0];
            return null;
        }

        // ──────────── 翻面 / 基準角 ────────────

        /// <summary>左右鏡像。等距的家具圖鏡像＝把 scale.x 取負，格子位置不用改。</summary>
        void Flip()
        {
            bool want = !selected.flip;

            // ⚠️ 轉向會把佔地的寬深對調 —— 轉完可能就放不下了（例如 1×3 的架子
            //    貼在右邊界，轉成 3×1 就超出去），連走道的方向也會跟著轉。先檢查再套用。
            var turn = RoomLayout.Check(selected.id, selected.gx, selected.gy,
                                        selected, want, selected.Anchor);
            if (turn != PlaceBlock.Ok) { Deny(selectedGo, turn); return; }

            var list = RoomLayout.PlacedList();
            foreach (var p in list)
                if (p.uid == selected.uid)
                { p.flip = want; selected.flip = want; break; }
            RoomLayout.SetPlaced(list);

            Sfx.Play("place");          // 轉過去了畫面就看得到，不跳字
            AfterEdit();
        }

        /// <summary>
        /// 換基準角：前角 → 左上 → 右上 → 前角。
        /// 靠左後牆的貨架用「左上」、靠右後牆的用「右上」（通常搭配翻面），
        /// 桌椅那種不靠牆的維持「前角」就好。
        /// </summary>
        void CycleAnchor()
        {
            // ⚠️ 換基準角＝**把圖搬到佔地的另一個角**，靠牆的貨架很容易一換就穿出牆外。
            //    先驗過再套用，不行的就跳過去試下一個，免得玩家卡在同一個換不了的角。
            int next = selected.anchor;
            var why = PlaceBlock.Ok;
            for (int i = 1; i <= 3; i++)
            {
                int cand = (selected.anchor + i) % 3;
                why = RoomLayout.Check(selected.id, selected.gx, selected.gy,
                                       selected, selected.flip, (FurnitureAnchor)cand);
                if (why == PlaceBlock.Ok) { next = cand; break; }
            }
            if (next == selected.anchor) { Deny(selectedGo, why); return; }

            var list = RoomLayout.PlacedList();
            foreach (var p in list)
                if (p.uid == selected.uid)
                { p.anchor = next; selected.anchor = next; break; }
            RoomLayout.SetPlaced(list);
            Sfx.Play("place");          // 托盤上 T 那組的圖會換成新的基準角，不跳字
            AfterEdit();
        }

        /// <summary>改完之後重畫並保持選取。</summary>
        void AfterEdit()
        {
            view.Rebuild();
            BuildGrid();
            ReselectAfterRebuild();
            UpdateHint();
        }

        /// <summary>
        /// Rebuild 會生出全新的物件（SetPlaced 也會換掉全部 PlacedFurniture），選取要靠 **uid** 重新對上。
        /// 以前用「id＋格座標」對，同款家具剛好擺過同一格時會選錯；uid 是唯一的。
        /// </summary>
        void ReselectAfterRebuild()
        {
            selectedGoodGo = FindGoodGo(selectedGood);
            if (selectedGood != null && selectedGoodGo == null) selectedGood = null;   // 那樣商品已經沒擺出來了

            if (selected == null) { selectedGo = null; ClearFootprint(); return; }
            foreach (var (go, data) in view.Furnitures)
                if (data.uid == selected.uid)
                { selected = data; selectedGo = go; ShowFootprint(data, true); return; }
            selected = null; selectedGo = null;
            ClearFootprint();
        }

        // ──────────── 佔地預覽與提示 ────────────

        void ShowFootprint(PlacedFurniture p, bool ok)
        {
            var (w, h) = p.Size;      // 轉向後的佔地 —— 提示格子要跟著轉
            if (w <= 0) { ClearFootprint(); return; }
            ShowFootprintAt(p.gx, p.gy, w, h, ok);
            ShowAisle(p);
        }

        /// <summary>
        /// 把「這件家具會佔到哪幾格」畫出來（實心＋粗邊，LateUpdate 讓它緩慢脈動）。
        ///
        /// ⚠️ 這些格子是**重複使用**的，不是每幀砍掉重生 —— Unity 的 Destroy() 要等到
        ///    該幀結束才真的刪掉，拖曳時每幀清空再重畫會讓舊格子與新格子同時出現一幀，
        ///    看起來就像提示格壞掉。這裡改成調整既有的，不夠才補、多的關掉。
        /// </summary>
        void ShowFootprintAt(int gx, int gy, int w, int h, bool ok)
        {
            footColor = ok ? FootOk : FootBad;
            int used = 0;
            for (int c = 0; c < w; c++)
                for (int r = 0; r < h; r++)
                    PoolCell(footprint, ref used, gx + c, gy + r, FillSprite(), OrderFoot, footColor, "footprint");
            PoolTrim(footprint, used);
        }

        /// <summary>放不下時「想去的那一格」的紅色殘影（w=0 ＝ 收起來）。</summary>
        void ShowGhost(int gx, int gy, int w, int h)
        {
            int used = 0;
            for (int c = 0; c < w; c++)
                for (int r = 0; r < h; r++)
                    PoolCell(ghost, ref used, gx + c, gy + r, FillSprite(), OrderGhost, FootBad, "ghost");
            PoolTrim(ghost, used);
        }

        /// <summary>
        /// 這件家具（貨架）自己需要的走道：藍框。玩家回饋看不懂藍格是什麼 —— 拖貨架時看到藍框跟著它走、
        /// 再對照提示裡的圖例「藍＝貨架前要留的走道」，就知道為什麼前面那排不能擺東西。非貨架傳進來會畫 0 格。
        /// </summary>
        void ShowAisle(PlacedFurniture p)
        {
            int used = 0;
            if (p != null)
                foreach (var c in RoomLayout.FrontClearance(p))
                    PoolCell(aisleMarks, ref used, c.gx, c.gy, OutlineSprite(), OrderAisle, AisleCol, "aisle");
            PoolTrim(aisleMarks, used);
        }

        /// <summary>從池子拿一格（不夠才補），擺到 (gx,gy)。出了格盤的跳過。</summary>
        void PoolCell(List<SpriteRenderer> pool, ref int used, int gx, int gy, Sprite sp, int order, Color col, string name)
        {
            if (!ShopRoom.InGrid(gx, gy)) return;
            if (used >= pool.Count) pool.Add(MakeCellSprite(name, sp, order));
            var sr = pool[used++];
            sr.gameObject.SetActive(true);
            var pos = ShopRoom.TileCenter(gx, gy);
            sr.transform.position = new Vector3(pos.x, pos.y, 0f);
            sr.sprite = sp;
            sr.color = col;
        }

        static void PoolTrim(List<SpriteRenderer> pool, int used)
        {
            for (int i = used; i < pool.Count; i++)
                if (pool[i] != null) pool[i].gameObject.SetActive(false);
        }

        SpriteRenderer MakeCellSprite(string name, Sprite sp, int order)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform);
            go.transform.localScale = new Vector3(1f, 0.5f, 1f);   // 菱形磚 64x32
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = order;
            return sr;
        }

        void ClearFootprint()
        {
            PoolTrim(footprint, 0);
            PoolTrim(ghost, 0);
            PoolTrim(aisleMarks, 0);
        }

        /// <summary>
        /// 把「擋住我的那幾格」標成紅色（傳 null ＝ 收起來）。
        ///
        /// ⚠️ sortingOrder 要壓在家具**之上** —— 重疊時要標的就是被壓到的那件家具佔的格子，
        ///    畫在它底下等於看不見。家具用的是 -pos.y（最大約 260），所以這裡用 4000。
        /// ⚠️ 跟佔地預覽一樣**重複使用**物件，不要每幀砍掉重生（Destroy() 是延遲的，
        ///    新舊會疊在同一幀）。
        /// </summary>
        void ShowConflicts(List<Cell> cells)
        {
            int used = 0;
            if (cells != null)
                foreach (var c in cells)
                    PoolCell(conflictMarks, ref used, c.gx, c.gy, FillSprite(), OrderConflict, ConflictCol, "conflict");
            PoolTrim(conflictMarks, used);
        }

        /// <summary>拖商品時圈出所有陳列位：綠＝空位、橘＝那裡有別的商品（放下會交換）、白＝它自己現在的位子。</summary>
        const float SpotScale = 0.5f;     // 圈圈貼圖 32px → 世界 16px

        void ShowSpotMarks(bool on)
        {
            int used = 0;
            if (on && view != null && dragGood != null)
                foreach (var s in view.Spots)
                {
                    if (used >= spotMarks.Count)
                    {
                        var go = new GameObject("spot");
                        go.transform.SetParent(transform);
                        var made = go.AddComponent<SpriteRenderer>();
                        made.sprite = RingSprite();
                        made.sortingOrder = OrderSpot;
                        spotMarks.Add(made);
                    }
                    var sr = spotMarks[used++];
                    sr.gameObject.SetActive(true);
                    var c = s.Center;
                    sr.transform.position = new Vector3(c.x, c.y, 0f);
                    sr.transform.localScale = new Vector3(SpotScale, SpotScale, 1f);
                    sr.color = s.Occupant == null ? SpotFree : s.Occupant == dragGood.Name ? SpotOwn : SpotSwap;
                }
            // ⚠️ 索引要跟 view.Spots 一一對應（LateUpdate 用 IndexOf 找要放大的那一個）—— 所以上面不能跳過任何一格
            PoolTrim(spotMarks, used);
        }

        /// <summary>
        /// 托盤提示列與頭上的圖示泡泡要跟著狀態變 —— 沒選東西時不該叫人按 F/T。
        /// 只在狀態變的時候叫（開始／結束拖曳、規則結果變了、目標陳列位變了、閃示結束），不要每幀叫。
        ///
        /// 全部是圖示，不寫句子（玩家回饋「解釋的文字太多了」）：
        ///   拖家具　　放得下＝[綠勾]、放不下＝[紅叉][原因圖]
        ///   選中家具　[F][轉向] [T][基準角] [右鍵][收回]（販售桌沒有收回）
        ///   拖商品　　圈外＝[回原位]、空位＝[綠勾]、有別的商品＝[交換][對方的圖]
        ///   選中商品　[拖曳]
        /// </summary>
        void UpdateHint()
        {
            var tray = UI.ShopRoomTray.Instance;
            EnsureTag();
            tagBuf.Clear();

            // ── 拖商品 ──
            if (dragGood != null)
            {
                Color bg;
                if (goodTarget == null) { TagAdd("act_return"); bg = TagIdle; }
                else if (goodTarget.Occupant == null || goodTarget.Occupant == dragGood.Name) { TagAdd("st_ok"); bg = TagOk; }
                else
                {
                    TagAdd("act_swap");
                    var other = GameArt.Item(goodTarget.Occupant);
                    if (other != null) tagBuf.Add(other);
                    bg = TagSwap;
                }
                worldTag.Set(tagBuf, bg);
                tray?.SetHint(UI.ShopRoomTray.HintMode.Good);
                return;
            }

            // ── 拖家具 ──
            if (dragFurn != null)
            {
                bool ok = dragBlock == PlaceBlock.Ok;
                // 拖曳中 F/T 不吃（見 Update），所以這時候的泡泡只講「行不行、為什麼」
                if (ok) TagAdd("st_ok"); else { TagAdd("st_no"); TagAdd(BlockIcon(dragBlock)); }
                worldTag.Set(tagBuf, ok ? TagOk : TagBad);
                tray?.SetHint(UI.ShopRoomTray.HintMode.DragFurniture, why: ok ? null : BlockIcon(dragBlock));
                return;
            }

            // ── 剛被擋下來（放開在不行的地方、轉不過去、販售桌不能收）：泡泡短暫顯示原因 ──
            if (flashUntil > 0f && flashIcons != null && (selectedGo != null || selected != null))
            {
                foreach (var n in flashIcons) TagAdd(n);
                worldTag.Set(tagBuf, TagBad);
                HintForSelection(tray);
                return;
            }

            // ── 選中商品（剛放下）──
            if (selectedGood != null)
            {
                TagAdd("mouse_drag");
                worldTag.Set(tagBuf, TagIdle);
                tray?.SetHint(UI.ShopRoomTray.HintMode.Good);
                return;
            }

            // ── 選中家具 ──
            if (selected != null)
            {
                bool sale = IsSale(selected);
                TagAdd("key_f"); TagAdd("act_rotate"); tagBuf.Add(null);
                TagAdd("key_t"); TagAdd("anchor_" + Mathf.Clamp(selected.anchor, 0, 2));
                if (!sale) { tagBuf.Add(null); TagAdd("mouse_right"); TagAdd("act_stash"); }
                worldTag.Set(tagBuf, TagIdle);
                HintForSelection(tray);
                return;
            }

            // ── 什麼都沒選 ──
            worldTag.Hide();
            tray?.SetHint(UI.ShopRoomTray.HintMode.Idle);
        }

        void HintForSelection(UI.ShopRoomTray tray)
        {
            if (tray == null) return;
            if (selected != null)
                tray.SetHint(UI.ShopRoomTray.HintMode.Furniture, selected.anchor, !IsSale(selected));
            else
                tray.SetHint(UI.ShopRoomTray.HintMode.Idle);
        }

        static bool IsSale(PlacedFurniture p)
        {
            var d = Furniture.ById(p.id);
            return d != null && d.Sale;
        }

        /// <summary>PlaceBlock → 原因的象形圖名稱（tools/gen_ui_icons.py 的 blk_*）。</summary>
        static string BlockIcon(PlaceBlock b) => b switch
        {
            PlaceBlock.OffFloor => "blk_offfloor",
            PlaceBlock.Overlap => "blk_overlap",
            PlaceBlock.Door => "blk_door",
            PlaceBlock.Aisle => "blk_aisle",
            PlaceBlock.NoAisle => "blk_noaisle",
            PlaceBlock.ThroughWall => "blk_wall",
            _ => "st_no",
        };

        // 泡泡內容的暫存（null ＝ 組與組之間的小空隙）；只在狀態變時填，不是每幀
        readonly List<Sprite> tagBuf = new();
        void TagAdd(string icon) => tagBuf.Add(UI.UiIcons.Get(icon));

        // ──────────── 被擋下來的回饋：抖一下＋閃紅＋泡泡短暫顯示原因 ────────────

        const float FlashSecs = 1.4f;
        const float ShakeSecs = 0.35f;
        static readonly string[] FlashLock = { "mouse_right", "lock" };
        float flashUntil;
        string[] flashIcons;
        GameObject shakeGo;
        Vector3 shakeBase;
        float shakeT0;

        /// <summary>
        /// 放不下／轉不過去：deny 音、那件東西左右抖一下並閃紅、頭上的泡泡顯示 [紅叉][原因圖] 一下子。
        /// 取代以前的「放不下 —— ……」「這個位置轉不過去 —— ……」那些句子 Toast。
        /// </summary>
        void Deny(GameObject go, PlaceBlock why)
        {
            Sfx.Play("deny");
            StartShake(go);
            flashIcons = new[] { "st_no", BlockIcon(why) };
            flashUntil = Time.unscaledTime + FlashSecs;
            UpdateHint();
        }

        void StartShake(GameObject go)
        {
            StopShake();
            if (go == null) return;
            shakeGo = go;
            shakeBase = go.transform.position;
            shakeT0 = Time.unscaledTime;
        }

        /// <summary>
        /// LateUpdate 叫：位置左右晃（越來越小）、圖染紅後褪回白。
        /// ⚠️ 晃的是物件本身的位置，結束（或被打斷）時一定要放回 shakeBase —— 見 StopShake。
        /// </summary>
        void UpdateShake(float now)
        {
            if (shakeGo == null) return;
            if (!shakeGo.activeInHierarchy) { shakeGo = null; return; }    // 被 Rebuild 換掉了：新物件本來就在原位
            float t = now - shakeT0;
            if (t >= ShakeSecs) { StopShake(); return; }
            float k = 1f - t / ShakeSecs;
            shakeGo.transform.position = shakeBase + new Vector3(Mathf.Sin(t * 70f) * 3f * k, 0f, 0f);
            Tint(shakeGo, Color.Lerp(Color.white, new Color(1f, 0.45f, 0.42f), k));
        }

        void StopShake()
        {
            if (shakeGo != null)
            {
                shakeGo.transform.position = shakeBase;
                Tint(shakeGo, Color.white);
            }
            shakeGo = null;
        }

        // ──────────── 世界標籤（圖示泡泡）────────────

        void EnsureTag()
        {
            if (worldTag == null) worldTag = new WorldTag(transform);
        }

        /// <summary>標籤跟著「現在在操作的那個東西」走：拖著的家具／商品、選中的家具／商品。</summary>
        void UpdateTagPosition()
        {
            if (worldTag == null || !worldTag.Visible) return;

            // Rebuild／庫存變動會換掉物件（舊的先被關掉、這一幀結束才刪）→ 失聯就照名字／uid 再找一次
            if (dragGood == null && selectedGood != null && (selectedGoodGo == null || !selectedGoodGo.activeInHierarchy))
                selectedGoodGo = FindGoodGo(selectedGood);
            if (selected != null && (selectedGo == null || !selectedGo.activeInHierarchy))
            {
                selectedGo = null;
                foreach (var (go, data) in view.Furnitures)
                    if (data.uid == selected.uid) { selectedGo = go; break; }
            }

            Vector2 at;
            if (dragGood != null)
            {
                var g = dragGood.Gos.Count > 0 ? dragGood.Gos[0] : null;
                if (g == null) { worldTag.Hide(); return; }
                var b = g.GetComponent<SpriteRenderer>().bounds;
                at = new Vector2(b.center.x, b.max.y + 8f);
            }
            else if (selectedGood != null)
            {
                if (selectedGoodGo == null) { worldTag.Hide(); return; }
                var b = selectedGoodGo.GetComponent<SpriteRenderer>().bounds;
                at = new Vector2(b.center.x, b.max.y + 8f);
            }
            else
            {
                var p = dragFurn ?? selected;
                var go = dragFurn != null ? dragGo : selectedGo;
                if (p == null || go == null) { worldTag.Hide(); return; }
                // 抖動中用原位算，泡泡不要跟著晃
                Vector2 front = go == shakeGo ? (Vector2)shakeBase : (Vector2)go.transform.position;
                at = RoomLayout.ArtRect(p.id, front, p.flip, out var r)
                    ? new Vector2(r.center.x, r.yMax + 6f)
                    : front + new Vector2(0f, 120f);
            }

            // 別跑出畫面上緣（靠後牆的高貨架頭頂就快到畫面頂了）
            if (cam != null && cam.orthographic)
            {
                float top = cam.transform.position.y + cam.orthographicSize - 6f;
                at.y = Mathf.Min(at.y, top - worldTag.Height);
            }
            worldTag.Move(at);
        }

        /// <summary>
        /// 世界空間的圖示泡泡（色底＋白邊＋一排 8-bit 圖示），畫在所有東西之上。
        ///
        /// 以前是 TextMesh 寫句子（「✓ 可以放這裡」「F 轉向 · T 換基準點 · 右鍵 收回」…），
        /// 玩家說字太多 → 改成一排圖示（SpriteRenderer，池化重複使用）。
        /// ⚠️ 圖示一律縮到 IconH 高（24 格的圖 → 1 格＝1 世界 px，NEAREST 不會糊）；商品圖也縮到同高。
        /// ⚠️ 只在內容真的變了才重排（Set 會比對上一次的圖與底色）。
        /// </summary>
        sealed class WorldTag
        {
            const float IconH = 24f;       // 世界 px（相機 1 單位≈1 px）
            const float Gap = 2f;          // 同一組圖示之間
            const float GroupGap = 7f;     // 組與組之間（Set 傳 null）
            const float Pad = 4f;

            readonly GameObject root;
            readonly SpriteRenderer bg, edge;
            readonly List<SpriteRenderer> icons = new();
            readonly List<Sprite> cur = new();
            Color curBg;

            public bool Visible => root != null && root.activeSelf;
            public float Height { get; private set; }

            public WorldTag(Transform parent)
            {
                root = new GameObject("edit-tag");
                root.transform.SetParent(parent);
                edge = NewQuad("edge", OrderTag);
                bg = NewQuad("bg", OrderTag + 1);
                root.SetActive(false);
            }

            SpriteRenderer NewQuad(string name, int order)
            {
                var go = new GameObject(name);
                go.transform.SetParent(root.transform, false);
                var sr = go.AddComponent<SpriteRenderer>();
                sr.sprite = PixelSprite();
                sr.sortingOrder = order;
                return sr;
            }

            bool Same(List<Sprite> list, Color bgCol)
            {
                if (bgCol != curBg || list.Count != cur.Count) return false;
                for (int i = 0; i < list.Count; i++) if (list[i] != cur[i]) return false;
                return true;
            }

            /// <summary>設內容：一排圖示（null ＝ 組間空隙；缺圖的 Sprite 也是 null，當空隙處理不會壞）。</summary>
            public void Set(List<Sprite> list, Color bgCol)
            {
                if (root == null) return;
                root.SetActive(true);
                if (Same(list, bgCol)) return;
                cur.Clear(); cur.AddRange(list);
                curBg = bgCol;

                // 先量總寬
                float w = 0f;
                int n = 0;
                bool prevIcon = false;
                foreach (var sp in list)
                {
                    if (sp == null) { if (prevIcon) w += GroupGap; prevIcon = false; continue; }
                    if (prevIcon) w += Gap;
                    w += IconH * UI.UiIcons.Aspect(sp);
                    prevIcon = true;
                    n++;
                }
                if (n == 0) { Hide(); return; }

                float h = IconH + Pad * 2f;
                float bw = w + Pad * 2f;
                Height = h;

                // 再擺：從左到右，圖示中心在泡泡中線
                int used = 0;
                float x = -w * 0.5f;
                prevIcon = false;
                foreach (var sp in list)
                {
                    if (sp == null) { if (prevIcon) x += GroupGap; prevIcon = false; continue; }
                    if (prevIcon) x += Gap;
                    float iw = IconH * UI.UiIcons.Aspect(sp);
                    if (used >= icons.Count) icons.Add(NewIcon());
                    var sr = icons[used++];
                    sr.gameObject.SetActive(true);
                    sr.sprite = sp;
                    float s = IconH / Mathf.Max(1f, sp.rect.height);
                    sr.transform.localScale = new Vector3(s, s, 1f);
                    // Sprite 的 pivot 不一定在中心（商品圖是 SheetSlicer.Whole 的預設），用 bounds 換算
                    var c = sp.bounds.center * s;
                    sr.transform.localPosition = new Vector3(x + iw * 0.5f - c.x, h * 0.5f - c.y, 0f);
                    x += iw;
                    prevIcon = true;
                }
                for (int i = used; i < icons.Count; i++) icons[i].gameObject.SetActive(false);

                bg.color = bgCol;
                bg.transform.localScale = new Vector3(bw, h, 1f);
                bg.transform.localPosition = new Vector3(0f, h * 0.5f, 0f);
                edge.color = new Color(1f, 1f, 1f, 0.85f);
                edge.transform.localScale = new Vector3(bw + 3f, h + 3f, 1f);
                edge.transform.localPosition = new Vector3(0f, h * 0.5f, 0f);
            }

            SpriteRenderer NewIcon()
            {
                var go = new GameObject("icon");
                go.transform.SetParent(root.transform, false);
                var sr = go.AddComponent<SpriteRenderer>();
                sr.sortingOrder = OrderTag + 2;
                return sr;
            }

            /// <summary>標籤的底邊中央放在 pos。</summary>
            public void Move(Vector2 pos)
            {
                if (root != null) root.transform.position = new Vector3(pos.x, pos.y, 0f);
            }

            public void Hide()
            {
                if (root != null) root.SetActive(false);
                cur.Clear();
            }
        }

        // ──────────── 托盤 ↔ 房間 ────────────

        /// <summary>從托盤點一個東西放進房間。</summary>
        void PlaceFromTray(string id, bool isDecor)
        {
            if (!Editing || Dragging) return;

            if (isDecor)
            {
                // 裝飾是自由座標 —— 放在房間正中央，玩家自己再拖到想要的位置
                var c = ShopRoom.TileCenter(ShopRoom.GridW / 2, ShopRoom.GridH / 2);
                if (DecorCatalog.Place(id, c.x, c.y) < 0) { Sfx.Play("deny"); return; }
                Sfx.Play("place");          // 東西出現在房間中央＋place 音，不跳字
            }
            else
            {
                var d = Furniture.ById(id);
                if (d == null) return;
                var cell = FirstFreeCell(id, d.W, d.H);
                if (cell == null)
                {
                    // 房間滿了：[紅叉][重疊] → [右鍵][收回]（先收掉別的騰出位子）
                    Sfx.Play("deny");
                    UI.Toast.ShowIcons(new[] { "st_no", "blk_overlap", "arrow", "mouse_right", "act_stash" }, null, 2.4f);
                    return;
                }

                var list = RoomLayout.PlacedList();
                list.Add(new PlacedFurniture(id, cell.Value.gx, cell.Value.gy));   // uid 0 → SetPlaced 發新號
                RoomLayout.SetPlaced(list);
                Sfx.Play("place");
            }

            view.Rebuild();
            BuildGrid();
            ReselectAfterRebuild();
            UpdateHint();
            UI.ShopRoomTray.Instance?.Refresh();
        }

        /// <summary>
        /// 右鍵點房間裡的東西 → 收回托盤（不退錢，之後還能再擺）。
        /// 架上商品的指定位置**不刪**：同一件家具擺回來（uid 不變）就恢復；這段時間那些商品先自動分配到別處。
        /// </summary>
        void PickUp()
        {
            var m = MouseWorld();

            // 先試裝飾（通常疊在家具上面）
            foreach (var (go, index) in view.Decors)
            {
                if (go == null || !HitTest(go, m)) continue;
                DecorCatalog.RemoveAt(index);
                Done();
                return;
            }

            foreach (var (go, data) in view.Furnitures)
            {
                if (go == null || !HitTest(go, m)) continue;

                // ⚠️ 販售桌不能收 —— 沒有它就沒辦法賣東西，收掉會讓店整個停擺
                var d = Furniture.ById(data.id);
                if (d != null && d.Sale)
                {
                    // 販售桌：選中它、抖一下，泡泡顯示 [右鍵][鎖頭]
                    selected = data; selectedGo = go;
                    selectedGood = null; selectedGoodGo = null;
                    ShowFootprint(data, true);
                    Sfx.Play("deny");
                    StartShake(go);
                    flashIcons = FlashLock;
                    flashUntil = Time.unscaledTime + FlashSecs;
                    UpdateHint();
                    return;
                }

                var list = RoomLayout.PlacedList();
                for (int i = 0; i < list.Count; i++)
                    if (list[i].uid == data.uid) { list.RemoveAt(i); break; }
                RoomLayout.SetPlaced(list);
                Done();
                return;
            }

            void Done()
            {
                Sfx.Play("pickup");          // 東西消失、托盤多一格＋pickup 音，不跳字
                view.Rebuild();
                BuildGrid();
                ReselectAfterRebuild();
                UpdateHint();
                UI.ShopRoomTray.Instance?.Refresh();
            }
        }

        /// <summary>
        /// 找第一個放得下的格子（跳過門口那幾格）。
        /// 由上而下、由左而右掃，所以新擺的東西會出現在房間後方，不會壓在玩家臉上。
        /// </summary>
        static Cell? FirstFreeCell(string id, int w, int h)
        {
            for (int gy = 0; gy + h <= ShopRoom.GridH; gy++)
                for (int gx = 0; gx + w <= ShopRoom.GridW; gx++)
                    if (RoomLayout.Check(id, gx, gy, null, false, FurnitureAnchor.Front) == PlaceBlock.Ok)
                        return new Cell(gx, gy);
            return null;
        }

        static void Tint(GameObject go, Color c)
        {
            var sr = go.GetComponentInChildren<SpriteRenderer>();
            if (sr != null) sr.color = c;
        }

        // ──────────── 格線 ────────────

        /// <summary>
        /// 把整片地板的格子畫出來，玩家才看得出東西會吸附到哪。
        ///
        /// ⚠️ **只建一次**，之後只更新顏色。原本每次放開/翻面都 ClearGrid() 再重建 140 個，
        ///    但 Unity 的 Destroy() 延到該幀結束才真的刪 —— 舊的 140 個與新的 140 個會疊在
        ///    同一幀，看起來就是格線錯亂。同 ShowFootprintAt 踩過的坑。
        /// </summary>
        void BuildGrid()
        {
            if (gridCells.Count > 0) { UpdateGridColors(null); return; }

            for (int gx = 0; gx < ShopRoom.GridW; gx++)
                for (int gy = 0; gy < ShopRoom.GridH; gy++)
                {
                    var p = ShopRoom.TileCenter(gx, gy);
                    var go = new GameObject($"cell{gx}-{gy}");
                    go.transform.SetParent(transform);
                    go.transform.position = new Vector3(p.x, p.y, 0f);
                    // 菱形磚是 64×32，貼圖是 64×64 的方形 → y 壓一半
                    go.transform.localScale = new Vector3(1f, 0.5f, 1f);

                    var sr = go.AddComponent<SpriteRenderer>();
                    sr.sprite = GridSprite();
                    sr.color = GridCol;
                    sr.sortingOrder = OrderGrid;      // 地板之上、家具之下
                    gridCells.Add(sr);
                }

            UpdateGridColors(null);
        }

        /// <summary>
        /// 更新格線顏色：門口紅、貨架走道藍（實心＋粗邊）、其餘只有亮邊的淡格。
        ///
        /// 改版前 alpha 只有 0.13～0.22（再乘上貼圖內側的 0.28 → 實際不到 0.06），玩家說幾乎看不到。
        /// 現在一般格：內側約 0.08、邊 0.38；門口：內側約 0.45、邊 0.75；走道：內側約 0.42、邊 0.7。
        /// </summary>
        /// <param name="skipAisle">拖曳中的那件 —— 它原本的走道先不畫（它會跟著拖曳畫藍框）</param>
        void UpdateGridColors(PlacedFurniture skipAisle)
        {
            var reserved = new HashSet<string>();
            foreach (var c in ShopRoom.ReservedCells()) reserved.Add($"{c.gx},{c.gy}");

            // 所有貨架前方的走道 —— 標出來玩家才知道那裡是刻意空著的
            var aisle = new HashSet<string>();
            foreach (var (_, data) in view.Furnitures)
            {
                if (skipAisle != null && data.uid == skipAisle.uid) continue;
                foreach (var c in RoomLayout.FrontClearance(data)) aisle.Add($"{c.gx},{c.gy}");
            }

            int i = 0;
            for (int gx = 0; gx < ShopRoom.GridW; gx++)
                for (int gy = 0; gy < ShopRoom.GridH; gy++)
                {
                    if (i >= gridCells.Count) return;
                    var sr = gridCells[i++];
                    if (sr == null) continue;
                    string key = $"{gx},{gy}";
                    bool door = reserved.Contains(key), lane = !door && aisle.Contains(key);
                    sr.sprite = door || lane ? FillSprite() : GridSprite();
                    sr.color = door ? DoorCol : lane ? AisleGridCol : GridCol;
                }
        }

        void ClearGrid()
        {
            foreach (var g in gridCells) if (g != null) Destroy(g.gameObject);
            gridCells.Clear();
        }

        /// <summary>
        /// 佈置模式時把**地板**壓暗一點（只蓋在底圖之上、格線之下，家具與商品不受影響），
        /// 格線與佔地預覽才跳得出來。一個物件重複開關，不每次重生。
        /// </summary>
        void ShowDimmer(bool on)
        {
            if (dimmer == null)
            {
                if (!on) return;
                var go = new GameObject("edit-dim");
                go.transform.SetParent(transform);
                dimmer = go.AddComponent<SpriteRenderer>();
                dimmer.sprite = PixelSprite();
                dimmer.sortingOrder = OrderDim;
                dimmer.color = new Color(0.04f, 0.02f, 0.08f, 0.38f);
                // 底圖 960×640 掛在 (0,0)；蓋大一點不怕邊緣漏
                go.transform.position = Vector3.zero;
                go.transform.localScale = new Vector3(ShopRoom.RoomW + 200f, ShopRoom.RoomH + 200f, 1f);
            }
            dimmer.gameObject.SetActive(on);
        }

        // ──────────── 程式生成的貼圖 ────────────

        static Sprite gridSprite, fillSprite, outlineSprite, ringSprite, pixelSprite;

        /// <summary>
        /// 等距菱形貼圖：曼哈頓距離 ≤ 半徑＝菱形內；邊緣 edge 以外那圈畫 1、內側畫 inner。
        /// 64×64 的方形，用的時候 y 壓一半變 64×32。
        /// </summary>
        static Sprite MakeDiamond(float edgeFrom, float inner)
        {
            const int N = 64;
            var tex = new Texture2D(N, N, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            float c = (N - 1) / 2f;
            for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    float d = (Mathf.Abs(x - c) + Mathf.Abs(y - c)) / c;
                    float a = d > 1f ? 0f : (d > edgeFrom ? 1f : inner);
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
                }
            tex.Apply();
            return Sprite.Create(tex, new Rect(0, 0, N, N), new Vector2(0.5f, 0.5f), 1f);
        }

        /// <summary>一般格線：內側很淡、邊緣一圈亮（格線邊框）。</summary>
        static Sprite GridSprite() => gridSprite != null ? gridSprite : gridSprite = MakeDiamond(0.88f, 0.22f);
        /// <summary>實心格（佔地、門口、走道、擋住）：內側六成、粗邊。</summary>
        static Sprite FillSprite() => fillSprite != null ? fillSprite : fillSprite = MakeDiamond(0.8f, 0.6f);
        /// <summary>只有粗框（自己的走道預覽）。</summary>
        static Sprite OutlineSprite() => outlineSprite != null ? outlineSprite : outlineSprite = MakeDiamond(0.78f, 0.12f);

        /// <summary>陳列位的小圈（32px：外圈實心、中間透明，商品看得到）。</summary>
        static Sprite RingSprite()
        {
            if (ringSprite != null) return ringSprite;
            const int N = 32;
            var tex = new Texture2D(N, N, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            float c = (N - 1) / 2f;
            for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    float d = Mathf.Sqrt((x - c) * (x - c) + (y - c) * (y - c)) / c;
                    float a = d > 1f ? 0f : d > 0.68f ? 1f : 0.18f;
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
                }
            tex.Apply();
            ringSprite = Sprite.Create(tex, new Rect(0, 0, N, N), new Vector2(0.5f, 0.5f), 1f);
            return ringSprite;
        }

        /// <summary>1×1 白點（標籤底板、壓暗用，靠 scale 拉成需要的大小）。</summary>
        static Sprite PixelSprite()
        {
            if (pixelSprite != null) return pixelSprite;
            var tex = new Texture2D(1, 1, TextureFormat.RGBA32, false) { filterMode = FilterMode.Point };
            tex.SetPixel(0, 0, Color.white);
            tex.Apply();
            pixelSprite = Sprite.Create(tex, new Rect(0, 0, 1, 1), new Vector2(0.5f, 0.5f), 1f);
            return pixelSprite;
        }
    }
}
