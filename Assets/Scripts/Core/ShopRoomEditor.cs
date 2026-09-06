using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 店內佈置模式：按 R 進入，用滑鼠把家具與裝飾拖到想要的位置，再按 R（或 Esc）完成。
    ///
    /// 對應 Cocos 的 DecorRoom.ts 的另一半（enterEdit / makeDraggable / drawGrid / buildTray）。
    ///
    /// 兩種東西的規則不一樣：
    ///   **家具** 吃等距格盤 —— 放開時吸附到最近的格；能不能放由 RoomLayout.Check
    ///            一次判完（超出地板／重疊／門口／貨架前的走道／圖穿出牆外），
    ///            擋住的格子會標紅色、原因寫在托盤那行提示上。
    ///   **裝飾** 是自由座標 —— 可以擺在桌上、架上任何位置，只夾在菱形地板內。
    ///
    /// ⚠️ 拖曳中會即時改物件位置，但**存檔要等按下完成才寫**（RoomLayout.SetPlaced /
    ///    DecorCatalog.SetPlaced）—— 中途反悔按 Esc 就整批還原。
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

        // 拖曳中的東西
        GameObject dragGo;
        PlacedFurniture dragFurn;      // 拖家具時有值
        int dragDecorIndex = -1;       // 拖裝飾時 >= 0
        Vector3 dragOffset;
        Cell dragOrigCell;
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
        readonly List<GameObject> conflictMarks = new();

        // 進入編輯時的快照，按 Esc 還原用
        List<PlacedFurniture> snapFurn;
        List<PlacedDecor> snapDecor;

        readonly List<GameObject> gridCells = new();
        /// <summary>佔地預覽：拖曳/選取中那件家具會佔到的格子，綠＝放得下、紅＝放不下。</summary>
        readonly List<GameObject> footprint = new();

        /// <summary>目前選中的家具（拖過或點過的），F 翻面 / T 換基準角都作用在它身上。</summary>
        PlacedFurniture selected;

        void Awake() { Instance = this; cam = Camera.main; }
        void OnDestroy() { if (Instance == this) Instance = null; }

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

            // 選中一件家具之後：F 翻面、T 換基準角（靠牆的貨架要用）
            if (selected != null)
            {
                if (Input.GetKeyDown(KeyCode.F)) { Flip(); return; }
                if (Input.GetKeyDown(KeyCode.T)) { CycleAnchor(); return; }
            }

            if (Input.GetMouseButtonDown(1)) { PickUp(); return; }   // 右鍵收回托盤
            if (Input.GetMouseButtonDown(0)) BeginDrag();
            else if (Input.GetMouseButton(0) && dragGo != null) Drag();
            else if (Input.GetMouseButtonUp(0) && dragGo != null) EndDrag();
        }

        // ──────────── 進出 ────────────

        void Enter()
        {
            Editing = true;

            // 快照：按 Esc 要能整批還原
            snapFurn = RoomLayout.PlacedList();
            snapDecor = DecorCatalog.PlacedList();

            selected = null;
            BuildGrid();

            var tray = UI.ShopRoomTray.Ensure();
            tray.onPick = PlaceFromTray;
            tray.Show();
            UpdateHint();
        }

        void Finish()
        {
            Editing = false;
            selected = null;
            ClearGrid();
            ClearFootprint();
            ShowConflicts(null);
            UI.ShopRoomTray.Instance?.Hide();
            // 拖曳過程已經即時寫進 RoomLayout / DecorCatalog 的資料，這裡只要收工
            UI.Toast.Show("佈置完成");
            view.Rebuild();
        }

        void Cancel()
        {
            Editing = false;
            selected = null;
            ClearGrid();
            ClearFootprint();
            ShowConflicts(null);
            UI.ShopRoomTray.Instance?.Hide();
            RoomLayout.SetPlaced(snapFurn);
            DecorCatalog.SetPlaced(snapDecor);
            UI.Toast.Show("已取消，恢復原本的擺設");
            view.Rebuild();
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
            var m = MouseWorld();

            // 先找裝飾（它們通常疊在家具上面），再找家具
            foreach (var (go, index) in view.Decors)
            {
                if (go == null || !HitTest(go, m)) continue;
                dragGo = go; dragDecorIndex = index; dragFurn = null;
                dragOrigPos = go.transform.position;
                dragOffset = go.transform.position - m;
                return;
            }
            foreach (var (go, data) in view.Furnitures)
            {
                if (go == null || !HitTest(go, m)) continue;
                dragGo = go; dragFurn = data; dragDecorIndex = -1;
                selected = data;                       // 選中 → F/T 作用在它身上
                dragOrigCell = new Cell(data.gx, data.gy);
                lastValidCell = dragOrigCell;
                lastValidAnchor = data.anchor;
                dragBlock = PlaceBlock.Ok;
                ShowConflicts(null);
                dragOffset = go.transform.position - m;
                ShowFootprint(data, true);
                UpdateHint();
                return;
            }

            // 點空地＝取消選取
            selected = null;
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

                // 提示格永遠畫在圖真正落腳的那一格；顏色反映「玩家想去的地方行不行」
                Tint(dragGo, ok ? new Color(0.75f, 1f, 0.78f) : new Color(1f, 0.86f, 0.7f));
                ShowFootprintAt(use.gx, use.gy, w, h, true);

                // 擋住我的那幾格標紅色 —— 「是疊到什麼」要看得見，
                // 不然玩家只覺得莫名其妙拖不過去（原因同時寫在托盤那行提示上）
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
                // 在放不下的地方放開手：東西停在最後一個合法格，這裡把原因講出來
                if (dragBlock != PlaceBlock.Ok)
                    UI.Toast.Show("放不下 —— " + RoomLayout.BlockText(dragBlock));

                // Drag 只會停在合法格，正常不會進到這裡；保險起見還是驗一次
                var b = CheckCell(dragFurn, new Cell(dragFurn.gx, dragFurn.gy));
                if (b != PlaceBlock.Ok)
                {
                    dragFurn.gx = dragOrigCell.gx;
                    dragFurn.gy = dragOrigCell.gy;
                    UI.Toast.Show("放回原位 —— " + RoomLayout.BlockText(b));
                }
                var list = RoomLayout.PlacedList();
                foreach (var p in list)
                    if (p.id == dragFurn.id && p.gx == dragOrigCell.gx && p.gy == dragOrigCell.gy)
                    {
                        p.gx = dragFurn.gx; p.gy = dragFurn.gy;
                        p.anchor = dragFurn.anchor;      // 靠牆吸附時會順手改基準角
                        break;
                    }
                RoomLayout.SetPlaced(list);
            }
            else if (dragDecorIndex >= 0)
            {
                DecorCatalog.Move(dragDecorIndex, dragGo.transform.position.x, dragGo.transform.position.y);
            }

            dragGo = null; dragFurn = null; dragDecorIndex = -1;
            dragBlock = PlaceBlock.Ok;
            ShowConflicts(null);
            view.Rebuild();
            if (Editing) { BuildGrid(); ReselectAfterRebuild(); UpdateHint(); }   // Rebuild 會換掉物件
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
            if (turn != PlaceBlock.Ok)
            {
                UI.Toast.Show("這個位置轉不過去 —— " + RoomLayout.BlockText(turn));
                return;
            }

            var list = RoomLayout.PlacedList();
            foreach (var p in list)
                if (p.id == selected.id && p.gx == selected.gx && p.gy == selected.gy)
                { p.flip = want; selected.flip = want; break; }
            RoomLayout.SetPlaced(list);

            var (w, h) = selected.Size;
            UI.Toast.Show($"已轉向 —— 佔地 {w}×{h}");
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
            if (next == selected.anchor)
            {
                UI.Toast.Show("這個位置換不了基準點 —— " + RoomLayout.BlockText(why));
                return;
            }

            var list = RoomLayout.PlacedList();
            foreach (var p in list)
                if (p.id == selected.id && p.gx == selected.gx && p.gy == selected.gy)
                { p.anchor = next; selected.anchor = next; break; }
            RoomLayout.SetPlaced(list);
            UI.Toast.Show("基準點：" + AnchorName(next));
            AfterEdit();
        }

        static string AnchorName(int a) => a switch
        {
            1 => "左上（靠左後牆）",
            2 => "右上（靠右後牆）",
            _ => "前角（不靠牆）",
        };

        /// <summary>改完之後重畫並保持選取。</summary>
        void AfterEdit()
        {
            view.Rebuild();
            BuildGrid();
            ReselectAfterRebuild();
            UpdateHint();
        }

        /// <summary>Rebuild 會生出全新的物件，選取要靠格座標重新對上。</summary>
        void ReselectAfterRebuild()
        {
            if (selected == null) return;
            foreach (var (go, data) in view.Furnitures)
                if (data.id == selected.id && data.gx == selected.gx && data.gy == selected.gy)
                { selected = data; ShowFootprint(data, true); return; }
            selected = null;
            ClearFootprint();
        }

        // ──────────── 佔地預覽與提示 ────────────

        void ShowFootprint(PlacedFurniture p, bool ok)
        {
            var (w, h) = p.Size;      // 轉向後的佔地 —— 提示格子要跟著轉
            if (w <= 0) { ClearFootprint(); return; }
            ShowFootprintAt(p.gx, p.gy, w, h, ok);
        }

        /// <summary>把「這件家具會佔到哪幾格」畫出來 —— 綠＝放得下、紅＝放不下。</summary>
        /// <summary>
        /// 把「這件家具會佔到哪幾格」畫出來。
        ///
        /// ⚠️ 這些格子是**重複使用**的，不是每幀砍掉重生 —— Unity 的 Destroy() 要等到
        ///    該幀結束才真的刪掉，拖曳時每幀清空再重畫會讓舊格子與新格子同時出現一幀，
        ///    看起來就像提示格壞掉。這裡改成調整既有的，不夠才補、多的關掉。
        /// </summary>
        void ShowFootprintAt(int gx, int gy, int w, int h, bool ok)
        {
            var color = ok ? new Color(0.5f, 1f, 0.6f, 0.42f) : new Color(1f, 0.45f, 0.45f, 0.42f);
            int used = 0;

            for (int c = 0; c < w; c++)
                for (int r = 0; r < h; r++)
                {
                    if (!ShopRoom.InGrid(gx + c, gy + r)) continue;
                    var pos = ShopRoom.TileCenter(gx + c, gy + r);

                    if (used >= footprint.Count) footprint.Add(MakeCellSprite());
                    var go = footprint[used++];
                    go.SetActive(true);
                    go.transform.position = new Vector3(pos.x, pos.y, 0f);
                    go.GetComponent<SpriteRenderer>().color = color;
                }

            for (int i = used; i < footprint.Count; i++)
                if (footprint[i] != null) footprint[i].SetActive(false);
        }

        GameObject MakeCellSprite()
        {
            var go = new GameObject("footprint");
            go.transform.SetParent(transform);
            go.transform.localScale = new Vector3(1f, 0.5f, 1f);   // 菱形磚 64x32
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = DiamondSprite();
            sr.sortingOrder = -9400;      // 格線之上、家具之下
            return go;
        }

        void ClearFootprint()
        {
            foreach (var g in footprint) if (g != null) g.SetActive(false);
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
                {
                    if (!ShopRoom.InGrid(c.gx, c.gy)) continue;
                    if (used >= conflictMarks.Count)
                    {
                        var made = MakeCellSprite();
                        made.name = "conflict";
                        made.GetComponent<SpriteRenderer>().sortingOrder = 4000;
                        conflictMarks.Add(made);
                    }
                    var go = conflictMarks[used++];
                    go.SetActive(true);
                    var pos = ShopRoom.TileCenter(c.gx, c.gy);
                    go.transform.position = new Vector3(pos.x, pos.y, 0f);
                    go.GetComponent<SpriteRenderer>().color = new Color(1f, 0.32f, 0.3f, 0.5f);
                }

            for (int i = used; i < conflictMarks.Count; i++)
                if (conflictMarks[i] != null) conflictMarks[i].SetActive(false);
        }

        /// <summary>托盤上那行提示要跟著選取狀態變 —— 沒選東西時不該叫人按 F/T。</summary>
        void UpdateHint()
        {
            var tray = UI.ShopRoomTray.Instance;
            if (tray == null) return;

            // 拖曳中撞到規則 —— 提示這行就是「為什麼拖不過去」的主要出口
            if (dragFurn != null && dragBlock != PlaceBlock.Ok)
            {
                tray.SetHint($"× 放不下：{RoomLayout.BlockText(dragBlock)} · 紅色格＝擋住的地方 · " +
                             "鬆手會停在最後一個放得下的位置");
                return;
            }

            if (selected == null)
            {
                tray.SetHint("點托盤裡的東西放進房間 · 左鍵拖曳搬位置 · 右鍵收回托盤 · " +
                             "藍色格＝貨架前的走道，要留給客人走 · R 完成 / Esc 取消");
                return;
            }
            var d = Furniture.ById(selected.id);
            string name = d != null ? d.Name : selected.id;
            var (w, h) = selected.Size;
            tray.SetHint($"選中「{name}」佔地 {w}×{h} · F 轉向 · " +
                         $"T 換基準點（{AnchorName(selected.anchor)}）· 貨架拖近後牆會自動貼齊 · " +
                         "右鍵收回 · R 完成");
        }

        // ──────────── 托盤 ↔ 房間 ────────────

        /// <summary>從托盤點一個東西放進房間。</summary>
        void PlaceFromTray(string id, bool isDecor)
        {
            if (!Editing) return;

            if (isDecor)
            {
                // 裝飾是自由座標 —— 放在房間正中央，玩家自己再拖到想要的位置
                var c = ShopRoom.TileCenter(ShopRoom.GridW / 2, ShopRoom.GridH / 2);
                if (DecorCatalog.Place(id, c.x, c.y) < 0) { UI.Toast.Show("托盤裡沒有這個了"); return; }
                UI.Toast.Show($"擺好了 —— 拖曳可以調位置");
            }
            else
            {
                var d = Furniture.ById(id);
                if (d == null) return;
                var cell = FirstFreeCell(id, d.W, d.H);
                if (cell == null) { UI.Toast.Show("房間裡沒有空位了 —— 先把別的東西收回托盤"); return; }

                var list = RoomLayout.PlacedList();
                list.Add(new PlacedFurniture(id, cell.Value.gx, cell.Value.gy));
                RoomLayout.SetPlaced(list);
                UI.Toast.Show($"擺好了 —— 拖曳可以搬位置");
            }

            view.Rebuild();
            BuildGrid();
            UI.ShopRoomTray.Instance?.Refresh();
        }

        /// <summary>右鍵點房間裡的東西 → 收回托盤（不退錢，之後還能再擺）。</summary>
        void PickUp()
        {
            var m = MouseWorld();

            // 先試裝飾（通常疊在家具上面）
            foreach (var (go, index) in view.Decors)
            {
                if (go == null || !HitTest(go, m)) continue;
                DecorCatalog.RemoveAt(index);
                Done("收回托盤了");
                return;
            }

            foreach (var (go, data) in view.Furnitures)
            {
                if (go == null || !HitTest(go, m)) continue;

                // ⚠️ 販售桌不能收 —— 沒有它就沒辦法賣東西，收掉會讓店整個停擺
                var d = Furniture.ById(data.id);
                if (d != null && d.Sale) { UI.Toast.Show("販售桌不能收起來，只能搬位置"); return; }

                var list = RoomLayout.PlacedList();
                for (int i = 0; i < list.Count; i++)
                    if (list[i].id == data.id && list[i].gx == data.gx && list[i].gy == data.gy)
                    { list.RemoveAt(i); break; }
                RoomLayout.SetPlaced(list);
                Done("收回托盤了");
                return;
            }

            void Done(string msg)
            {
                UI.Toast.Show(msg);
                view.Rebuild();
                BuildGrid();
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

        /// <summary>把整片地板的格子畫出來，玩家才看得出東西會吸附到哪。</summary>
        /// <summary>
        /// 把整片地板的格子畫出來，玩家才看得出東西會吸附到哪。
        ///
        /// ⚠️ **只建一次**，之後只更新顏色。原本每次放開/翻面都 ClearGrid() 再重建 140 個，
        ///    但 Unity 的 Destroy() 延到該幀結束才真的刪 —— 舊的 140 個與新的 140 個會疊在
        ///    同一幀，看起來就是格線錯亂。同 ShowFootprintAt 踩過的坑。
        /// </summary>
        void BuildGrid()
        {
            if (gridCells.Count > 0) { UpdateGridColors(); return; }

            var reserved = new HashSet<string>();
            foreach (var c in ShopRoom.ReservedCells()) reserved.Add($"{c.gx},{c.gy}");

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
                    sr.sprite = DiamondSprite();
                    // 門口那幾格不給擺東西，畫成紅的
                    sr.color = reserved.Contains($"{gx},{gy}")
                        ? new Color(1f, 0.5f, 0.5f, 0.18f)
                        : new Color(1f, 1f, 1f, 0.13f);
                    sr.sortingOrder = -9500;      // 地板之上、家具之下
                    gridCells.Add(go);
                }

            UpdateGridColors();
        }

        /// <summary>更新格線顏色：門口紅、貨架走道藍、其餘白。</summary>
        void UpdateGridColors()
        {
            var reserved = new HashSet<string>();
            foreach (var c in ShopRoom.ReservedCells()) reserved.Add($"{c.gx},{c.gy}");

            // 所有貨架前方的走道 —— 標出來玩家才知道那裡是刻意空著的
            var aisle = new HashSet<string>();
            foreach (var (_, data) in view.Furnitures)
                foreach (var c in RoomLayout.FrontClearance(data)) aisle.Add($"{c.gx},{c.gy}");

            int i = 0;
            for (int gx = 0; gx < ShopRoom.GridW; gx++)
                for (int gy = 0; gy < ShopRoom.GridH; gy++)
                {
                    if (i >= gridCells.Count) return;
                    var go = gridCells[i++];
                    if (go == null) continue;
                    string key = $"{gx},{gy}";
                    go.GetComponent<SpriteRenderer>().color =
                        reserved.Contains(key) ? new Color(1f, 0.5f, 0.5f, 0.18f)
                      : aisle.Contains(key)    ? new Color(0.6f, 0.8f, 1f, 0.22f)
                      : new Color(1f, 1f, 1f, 0.13f);
                }
        }

        void ClearGrid()
        {
            foreach (var g in gridCells) if (g != null) Destroy(g);
            gridCells.Clear();
        }

        static Sprite diamond;

        /// <summary>等距菱形的格線貼圖（程式生成：菱形內側淡色、邊緣亮一點）。</summary>
        static Sprite DiamondSprite()
        {
            if (diamond != null) return diamond;
            const int N = 64;
            var tex = new Texture2D(N, N, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            float c = (N - 1) / 2f;
            for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    // 曼哈頓距離 <= 半徑 ＝ 菱形內
                    float d = (Mathf.Abs(x - c) + Mathf.Abs(y - c)) / c;
                    float a = d > 1f ? 0f : (d > 0.86f ? 1f : 0.28f);   // 邊緣一圈畫亮一點
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
                }
            tex.Apply();
            diamond = Sprite.Create(tex, new Rect(0, 0, N, N), new Vector2(0.5f, 0.5f), 1f);
            return diamond;
        }
    }
}
