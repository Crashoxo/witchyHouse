using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>撞到地圖哪一側（給「切換下一張地圖」用）。</summary>
    public enum EdgeSide { Left, Right, Top, Bottom }

    /// <summary>
    /// 俯視角魔女角色控制：
    ///   WASD / 方向鍵 = 八方向移動
    ///   按住 Shift    = 衝刺（速度 ×runMultiplier，動畫自動換成跑步）
    ///   滑鼠點地面    = 自動走過去（按方向鍵會立刻接手）
    ///   J 或 空白鍵   = 往目前面向施放魔法彈
    ///
    /// 移動會被夾在地圖範圍內（走不出邊界）。邊界預設自動從場景裡名叫 "Ground" 的物件
    /// 讀 SpriteRenderer 的尺寸算出來；找不到就用底下的 worldHalfWidth / worldHalfHeight。
    /// 戶外地圖（森林／城鎮／糖果鎮）另外有碰撞（樹幹、房子、灌木……見 <see cref="Obstacles"/>）
    /// 與邊緣內縮（女巫的圖不會畫到地面外）。
    /// 藥水室（SVG 房間，<see cref="BrewRoom.UseSvgRoom"/>）、店裡（等距菱形地板）與 8-bit 後花園
    /// （圍牆花園，<see cref="GardenRoom.UsePixelGarden"/>）也有碰撞，
    /// 但可走範圍是地板多邊形、沒有邊緣內縮 —— 三個房間走同一條程式路徑，差別只在多邊形與障礙是誰登記的。
    ///
    /// ── 移植註記 ────────────────────────────────────────────────
    /// 1. **輸入**：Cocos 版用 input.on(KEY_DOWN/KEY_UP) 自己維護一個 keys Set。
    ///    Unity 的 Input.GetKey 本來就是輪詢式的，那個 Set 直接不需要了。
    ///    （專案用舊版 Input Manager —— manifest 已拿掉 com.unity.inputsystem，
    ///      免得新舊兩套輸入打架。）
    ///
    /// 2. **點擊移動**：Cocos 版把 TOUCH_END 掛在 Ground 節點上（避免 UI 面板的點擊穿透），
    ///    還得在 onDestroy 小心 isValid 才不會炸。Unity 這邊改成 Camera 反投影 + UIState 判斷，
    ///    沒有節點生命週期的問題，那段 onDestroy 的坑一起消失。
    ///
    /// 3. **子系統的喚起**：Cocos 版 onLoad 會一併叫起 Clock / Outfits / DayNightTint …，
    ///    這裡照搬到 <see cref="Awake"/>。只有 UpdatePanel（更新公告板）還沒移植過來。
    ///    ShadowLayer（腳下影子）不在這裡叫 —— 它由第一個 <c>ShadowLayer.Follow()</c>
    ///    自己生出來，主角、顧客、村民、小動物各自登記。
    /// </summary>
    [RequireComponent(typeof(CharacterAnimator))]
    public class PlayerController : MonoBehaviour
    {
        [Header("移動")]
        [Tooltip("移動速度（像素/秒）")]
        public float moveSpeed = 200f;
        [Tooltip("按住 Shift 衝刺時的速度倍率（動畫會自己換成跑步那組）")]
        public float runMultiplier = 1.7f;

        [Header("地圖邊界")]
        [Tooltip("是否把角色夾在地圖範圍內（擋住邊界）")]
        public bool clampToBounds = true;
        [Tooltip("找不到 Ground 時用的地圖半寬（像素）")]
        public float worldHalfWidth = 1408f;
        [Tooltip("找不到 Ground 時用的地圖半高（像素）")]
        public float worldHalfHeight = 896f;
        // 戶外地圖的邊緣內縮（上一個身高、左右半個身寬、下一點點）不再是節點上的欄位：
        // 數值在 Data.ArtFootprints（tools/gen_footprints.py 產生），離線可達性檢查也讀同一份。

        [Header("換場")]
        [Tooltip("走到指定邊界要切換到的場景名稱（空字串＝先不切）。例：'town'")]
        public string nextMapScene = "town";
        [Tooltip("哪一側邊界會觸發切換")]
        public EdgeSide nextMapEdge = EdgeSide.Right;

        Vector2 dir;                  // 目前移動方向
        Vector2 facing = Vector2.right;  // 最後面向（施法方向）

        // 地圖邊界
        float minX, maxX, minY, maxY;
        bool switching;               // 已在切換地圖，避免重複觸發

        // 三件事分開開關（藥水室、店裡要前兩件、不要第三件）：
        //   ySort     女巫照腳底排序（戶外：腳底 y；藥水室：BrewRoom.PlayerOrder；店裡：ShopRoomView.PlayerOrder ——
        //             兩個房間都是看跟她重疊的家具在她前面還是後面）
        //   collide   套 Obstacles 碰撞（戶外：樹幹、房子…；藥水室／店裡：家具的落地範圍＋地板多邊形）
        //   edgeInset 地圖邊緣內縮（只有戶外 —— 那是為了女巫的圖不畫到地面外；房間的地板多邊形自己已經縮好了）
        // 8-bit 後花園（GardenRoom.UsePixelGarden）要前兩件（排序照腳底 y）；舊後花園三件都不要，維持原本的夾邊方式。
        bool outdoor, ySort, collide, edgeInset;
        bool brewRoom;                // 藥水室的 SVG 房間（排序與出生點看 BrewRoom／BrewRoomLayout）
        bool shopRoom;                // 店裡（等距房間；排序看 ShopRoomView、地板是 ShopRoom.WalkFloor 的菱形）
        bool gardenRoom;              // 8-bit 後花園（四面圍牆；地板是 GardenRoomData.Walk 的菱形，障礙是樹與雨水桶）
        // 地板多邊形（藥水室、店裡）；null ＝ 用矩形。
        // ⚠️ 等距房間不能用矩形夾邊：塞得進菱形的最大矩形只剩正中間一小塊。有它的場景一律交給 Obstacles.ClampWalk。
        Vector2[] walkPoly;
        SpriteRenderer sr;

        // 點地自動走被擋住時不能原地一直推：連續 StallTime 秒幾乎沒有往目的地前進就放棄
        const float StallTime = 0.35f;
        float stallTimer;

        Transform ground;             // 點擊移動的接收面（也用來量邊界）
        Vector3? moveTarget;          // 點擊指定的目的地（null＝沒有）
        CharacterAnimator anim;
        Camera cam;

        // 腳步聲：量實際位移，每走 StepStride 像素響一步（跑步時一樣的步幅、更快走完 → 自然變密）
        const float StepStride = 64f;
        Vector3 lastPos;
        float stepAccum;

        void Awake()
        {
            anim = GetComponent<CharacterAnimator>();
            sr = GetComponent<SpriteRenderer>();
            cam = Camera.main;
            string scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
            outdoor = scene == "main" || scene == "town" || scene == "candy";
            brewRoom = scene == "brew" && BrewRoom.UseSvgRoom;
            shopRoom = scene == "shop";
            gardenRoom = scene == "garden" && GardenRoom.UsePixelGarden;
            ySort = outdoor || brewRoom || shopRoom || gardenRoom;
            collide = outdoor || brewRoom || shopRoom || gardenRoom;
            edgeInset = outdoor;
            if (brewRoom)
            {
                walkPoly = Data.BrewRoomLayout.Walk;
                // 出生點跟著配置表（場景檔裡的 (0,-250) 是舊房間的；新房間的門在別處）。
                // SceneDoor 的 armed 機制另外擋「一進來就被門彈回去」。
                var sp = Data.BrewRoomLayout.Spawn;
                transform.position = new Vector3(sp.x, sp.y, transform.position.z);
            }
            else if (shopRoom)
            {
                // 店裡：地板菱形內縮 FloorMargin（跟以前的 ShopRoom.ClampToFloor 同一塊範圍）。
                // 出生點照場景檔（ShopSceneBuilder 用 ShopRoom.PlayerSpawn 換算的），不用另外搬。
                walkPoly = Data.ShopRoom.WalkFloor();
            }
            else if (gardenRoom)
            {
                // 8-bit 後花園：草地菱形內縮（腳底圓不壓到圍牆），走不出去。
                // 出生點跟著配置表（門前的踏腳石上）—— 場景檔裡的 (250,55) 是舊花園的門口，新花園那裡是小屋的牆。
                walkPoly = Data.GardenRoomData.Walk;
                var sp = Data.GardenRoomData.Spawn;
                transform.position = new Vector3(sp.x, sp.y, transform.position.z);
            }
            ComputeBounds();
            GameArt.Preload();
            // 每個場景都有 Player → 在這裡叫出下排背包 HUD，讓它永遠顯示
            // （對應 Cocos 版 onLoad 裡的 Inventory.ensure()）
            UI.InventoryHud.Ensure();
            TimeDriver.Ensure();       // 遊戲時間（花的成長、日夜、節日都靠它）
            UI.ClockHud.Ensure();      // 右上角時鐘（只負責顯示，時間由 TimeDriver 推）
            UI.CornerHud.Ensure();     // 左上角金幣與名聲
            UI.SleepOverlay.Arm();     // 撐到 02:00 昏倒時也演睡覺過場並送回房間
            Outfits.Apply();           // 換裝：把存檔裡那套的圖套到女巫身上（每個場景都要）
            UI.UpdatePanel.ShowOnce();  // 更新公告板（一次執行只跳一次，換場景不重跳）
            AwayShop.Ensure();          // 你不在店裡時，店還是照常做生意

            // 各場景專屬的東西，同樣在這裡喚起 —— 不用改場景檔（對應原版的做法）
            if (scene == "shop")
            {
                ShopRoomView.Ensure();       // 地板底圖 + 擺出來的家具與裝飾
                ShopRoomEditor.Ensure();     // 按 R 進入佈置模式（拖曳家具）
                CustomerManager.Ensure();    // 顧客上門買東西
                SaleCounter.Ensure();        // 販售桌前按 E 開上架面板
                AwayShop.ReportOnReturn();   // 回店：報告剛剛不在時賣掉了什麼
            }
            if (scene == "garden") GardenRoom.Ensure();      // 背景、花圃、回店的門（舊花園另有柵欄外的村民；新花園另有 R 搬花圃）
            if (scene == "candy") CandyTown.Ensure();        // 建築、裝飾、NPC、街上的小動物
            if (scene == "brew") BrewRoom.Ensure();          // 日夜背景、鍋爐、床、倉庫、回店的門
            if (scene == "town")
            {
                TownFolk.Ensure(Data.TownRoads.Walk);   // 街上走動的村民
                // 採集完一走進城鎮，材料與花自動歸位到房間的倉庫（藥水與種子留在身上）
                int n = Storage.StashFromBag();
                if (n > 0) UI.Toast.Show($"材料已收進倉庫（{n} 種）");
            }
            // 戶外天色色板：只在戶外裝（室內 brew/shop 各自有自己的背景，不套）
            if (scene == "main" || scene == "town" || scene == "candy") DayNightTint.Ensure();
            // ⚠️ 一定要排在 DayNightTint 之後：路燈的光要畫在天色色板**之上**才不會被夜色吃掉
            if (scene == "town") LampGlow.Ensure();

            // ⚠️ 一定要排在 PortalGlow 之前：Doorways 會去找場景裡既有的物件
            //    （例如城鎮的 cottage-home）並掛上 SceneDoor，光圈才掃得到那些門。
            Doorways.Install(scene);
            PortalGlow.Ensure();       // 門與邊界傳送點的地上光圈

            // 碰撞：戶外地圖、藥水室、店裡才擋。這裡只記下場景與可走範圍，障礙清單在第一次移動時才建 ——
            // 糖果鎮的建築是 CandyTown 在 Start 裡才擺出來的（擺完會再叫 Obstacles.MarkDirty）；
            // 藥水室的家具由 BrewRoom 在 Start 裡登記（Obstacles.AddPoly／AddEllipse）；8-bit 後花園的樹與雨水桶由 GardenRoom 在 Start 裡登記；
            // 店裡的家具由 ShopRoomView.Rebuild() 登記（第一次在它的 Start，之後每次佈置完重登記）。
            // ⚠️ Begin 會清空所有登記，所以上面那些「在 Start 裡登記」不能提早到 Awake。
            Obstacles.Begin(scene, new Rect(minX, minY, maxX - minX, maxY - minY), transform.position, collide, walkPoly);
            if (scene == "town") TownWater.Register();   // 河不能直接走過去、要走橋（一定要在 Begin 之後：Begin 會清空登記）
            if (collide) ObstacleDebugView.Ensure();   // F3 顯示落地範圍

            lastPos = transform.position;
        }

        /// <summary>
        /// 腳步聲。跟 CharacterAnimator 同一套想法：**量這一幀實際移動了多少**，
        /// 不管是鍵盤、點地面自動走、還是衝刺都一樣算；站著（或推著牆走不動）就不響。
        /// 放 LateUpdate 是為了量到這一幀所有移動之後的位置。
        /// </summary>
        void LateUpdate()
        {
            var p = transform.position;

            // 戶外：女巫照腳底 y 排序（YSort），才會走到樹冠／屋頂後面被遮住、走到前面蓋住它們。
            // 物件那邊由 Obstacles 建清單時一併改成看腳底（原本是圖片中心）。
            // 藥水室：等距的長家具用單一 y 排不對，改問 BrewRoom.PlayerOrder（看跟她重疊的家具在她前面還是後面）。
            // 店裡：同一個想法，改問 ShopRoomView.PlayerOrder（用格座標判斷前後）。
            // ⚠️ 原本女巫的 sortingOrder 一直是場景產生器給的 0，跟所有物件的前後關係是固定的。
            if (ySort && sr != null)
            {
                if (brewRoom || shopRoom)
                {
                    var b = sr.bounds.size;
                    sr.sortingOrder = brewRoom ? BrewRoom.PlayerOrder(p, b.x, b.y)
                                               : ShopRoomView.PlayerOrder(p, b.x, b.y);
                }
                else sr.sortingOrder = Mathf.RoundToInt(-p.y);
            }

            float d = Vector2.Distance(p, lastPos);
            lastPos = p;

            if (d < 0.01f) { stepAccum = StepStride * 0.6f; return; }   // 停下來：下次起步走一小段就響第一步
            if (d > 40f) return;                                        // 一幀跳太遠＝被瞬移（出生點、夾回地板），不是走路

            stepAccum += d;
            if (stepAccum < StepStride) return;
            stepAccum -= StepStride;
            bool running = d / Mathf.Max(Time.deltaTime, 1e-4f) > moveSpeed * 1.3f;
            Sfx.Play("step", running ? 0.9f : 0.7f);
        }

        void Update()
        {
            if (UIState.ModalOpen) { moveTarget = null; return; }   // 開著視窗時角色不動
            // 佈置模式中滑鼠是用來拖家具的，不能同時當「點地面走過去」
            if (ShopRoomEditor.Instance != null && ShopRoomEditor.Instance.Editing)
            { moveTarget = null; return; }
            // 後花園搬花圃中也一樣（滑鼠在拖花圃）
            if (GardenArrange.Instance != null && GardenArrange.Instance.Editing)
            { moveTarget = null; return; }
            // 家裡（藥水室）擺家具中也一樣
            if (HomeArrange.Busy) { moveTarget = null; return; }

            HandleHotkeys();

            float x = (Key(KeyCode.D) || Key(KeyCode.RightArrow) ? 1f : 0f)
                    - (Key(KeyCode.A) || Key(KeyCode.LeftArrow) ? 1f : 0f);
            float y = (Key(KeyCode.W) || Key(KeyCode.UpArrow) ? 1f : 0f)
                    - (Key(KeyCode.S) || Key(KeyCode.DownArrow) ? 1f : 0f);

            // 按住 Shift 衝刺。動畫不用通知 —— CharacterAnimator 是量「這一幀跑多遠」
            // 自己決定要播走路還是跑步的。
            float speed = moveSpeed *
                (Key(KeyCode.LeftShift) || Key(KeyCode.RightShift) ? runMultiplier : 1f);

            float dt = Time.deltaTime;
            bool auto = false;                  // 這一幀是不是點地自動走
            float distBefore = 0f;

            if (x != 0f || y != 0f)
            {
                moveTarget = null;              // 鍵盤一動就接手，取消點擊移動
                stallTimer = 0f;
            }
            else if (moveTarget.HasValue)
            {
                var p0 = transform.position;
                float tx = moveTarget.Value.x - p0.x, ty = moveTarget.Value.y - p0.y;
                float dist = Mathf.Sqrt(tx * tx + ty * ty);
                if (dist <= Mathf.Max(speed * dt, 2f))   // 到了：貼齊目的地就收工
                {
                    // 貼齊也要過碰撞（目的地點在樹幹上時不能一步跳進去）
                    var snap = Obstacles.Resolve(p0, moveTarget.Value);
                    transform.position = new Vector3(snap.x, snap.y, p0.z);
                    moveTarget = null;
                    stallTimer = 0f;
                    return;
                }
                x = tx / dist; y = ty / dist;
                auto = true;
                distBefore = dist;
            }

            dir = new Vector2(x, y);
            if (dir.sqrMagnitude > 0f)
            {
                dir.Normalize();
                facing = dir;                   // 記住最後移動方向當作面向
                var p = transform.position;
                float nx = p.x + dir.x * speed * dt;
                float ny = p.y + dir.y * speed * dt;

                // 想走出哪一側（夾邊之前記下來，換場景要用）
                bool outL = nx < minX, outR = nx > maxX, outB = ny < minY, outT = ny > maxY;
                if (clampToBounds)
                {
                    nx = Mathf.Clamp(nx, minX, maxX);
                    ny = Mathf.Clamp(ny, minY, maxY);
                }

                // 碰撞：樹幹、房子、房間的家具…（戶外、藥水室、店裡；後花園 Resolve 直接回傳原值）。
                // 有地板多邊形的房間（藥水室、店裡的菱形）另外在這裡被夾進多邊形（Obstacles.ClampWalk）。
                // 店裡以前是另一條路（只有 ShopRoom.ClampToFloor、沒有碰撞），現在跟藥水室走同一條。
                var r = Obstacles.Resolve(p, new Vector2(nx, ny));
                nx = r.x; ny = r.y;

                // 撞邊換場景：照舊是「推到邊界」觸發，只是邊界換成內縮後的那條。
                // 要真的站在邊上（沒被障礙擋在半路）才算。
                // ⚠️ 有地板多邊形的房間不觸發：那個矩形只是多邊形的外接框、不是牆，
                //    房間的出口一律是地板上的門（SceneDoor；店裡見 ShopRoom.Door*）。
                if (clampToBounds && walkPoly == null)
                {
                    const float on = 0.5f;
                    if (outL && nx <= minX + on) OnReachEdge(EdgeSide.Left, ny);
                    else if (outR && nx >= maxX - on) OnReachEdge(EdgeSide.Right, ny);
                    if (outB && ny <= minY + on) OnReachEdge(EdgeSide.Bottom, nx);
                    else if (outT && ny >= maxY - on) OnReachEdge(EdgeSide.Top, nx);
                }

                // 點地自動走被擋住：連續一小段時間幾乎沒有更接近目的地，就放棄（不做尋路）。
                // 鍵盤移動不受影響 —— 推著牆走不動是玩家自己的選擇。
                if (auto && moveTarget.HasValue)
                {
                    float distAfter = Vector2.Distance(new Vector2(nx, ny), moveTarget.Value);
                    if (distBefore - distAfter < speed * dt * 0.15f) stallTimer += dt;
                    else stallTimer = 0f;
                    if (stallTimer >= StallTime) { moveTarget = null; stallTimer = 0f; }
                }

                transform.position = new Vector3(nx, ny, p.z);
            }
        }

        static bool Key(KeyCode k) => Input.GetKey(k);

        void HandleHotkeys()
        {
            // 點地面 → 記下目的地，Update 每幀走過去。
            // ⚠️ 這裡不看 UI：HUD 幾乎全是 PickingMode.Ignore，上方工具列（開關店鈕、設定鈕）要自己排除，
            //    不然按下去那一下人就往左上角走了（見 CornerHud.BlocksWorldClick）。
            if (Input.GetMouseButtonDown(0) && cam != null && !UI.CornerHud.BlocksWorldClick(Input.mousePosition))
            {
                var w = cam.ScreenToWorldPoint(Input.mousePosition);
                stallTimer = 0f;
                if (walkPoly != null)
                {
                    // 藥水室、店裡、8-bit 後花園：目的地夾進地板多邊形（點到牆上就走到牆腳）。
                    // 點在家具上不另外處理：走到撞住就沿邊滑，滑不動 StallTime 秒後自己放棄（不做尋路）。
                    var c = Obstacles.ClampWalk(new Vector2(w.x, w.y));
                    moveTarget = new Vector3(c.x, c.y, 0f);
                }
                else
                {
                    // 目的地夾在邊界內縮一點 —— 自動走到底不該把人帶去別張地圖，
                    // 換場景仍然只由玩家自己按方向鍵推到邊界觸發。
                    const float m = 4f;
                    moveTarget = new Vector3(Mathf.Clamp(w.x, minX + m, maxX - m),
                                             Mathf.Clamp(w.y, minY + m, maxY - m), 0f);
                }
            }

            if (Input.GetKeyDown(KeyCode.J) || Input.GetKeyDown(KeyCode.Space)) Cast();

            if (Input.GetKeyDown(KeyCode.B))                                 // B 開背包
            {
                Debug.Log("[PlayerController] 收到 B 鍵，準備開背包");      // 移植期診斷用
                UI.BagPanel.Ensure().Open();
            }

            if (Input.GetKeyDown(KeyCode.Q)) UI.QuestPanel.Ensure().Open();   // Q 開任務簿

            // Tab 開玩家資訊（物品/村民/日曆）。⚠️ 瀏覽器常把 Tab 拿去切換焦點，
            // 所以 I 也能開 —— 兩顆鍵等價（原專案就是為了這個留兩顆的）。
            if (Input.GetKeyDown(KeyCode.Tab) || Input.GetKeyDown(KeyCode.I))
                UI.PlayerInfoPanel.Ensure().Open();

            // O 開設定（音樂／音效音量、靜音）。關在 SettingsPanel 自己的 Update（同一顆鍵，見 QuestPanel）
            if (Input.GetKeyDown(KeyCode.O)) UI.SettingsPanel.Ensure().Open();
        }

        /// <summary>
        /// 從場景裡的 "Ground" 物件算出可走範圍；沒有就用 worldHalfWidth/Height。
        /// 有 "WalkArea" 就以它為準：後花園的草地是個菱形，可以走的範圍比整張背景小很多，
        /// 不然人會走到柵欄外的石板路和房子上面去。
        /// 有地板多邊形（藥水室、店裡）時，矩形改成多邊形的外接矩形（真正的夾邊由 Obstacles.ClampWalk 做）。
        /// </summary>
        void ComputeBounds()
        {
            ground = FindUpwards("Ground");     // 點擊移動的接收面（多邊形那條路也要有）
            if (walkPoly != null && walkPoly.Length > 0)
            {
                minX = maxX = walkPoly[0].x;
                minY = maxY = walkPoly[0].y;
                foreach (var q in walkPoly)
                {
                    minX = Mathf.Min(minX, q.x); maxX = Mathf.Max(maxX, q.x);
                    minY = Mathf.Min(minY, q.y); maxY = Mathf.Max(maxY, q.y);
                }
                return;
            }

            float halfW = worldHalfWidth, halfH = worldHalfHeight, cx = 0f, cy = 0f;

            // Ground 不一定是玩家的兄弟（原專案 Player 在 Props 下、Ground 在 World 下），
            // 所以從父層往上一路找。找不到就退回全場景搜尋。
            ground = FindUpwards("Ground");
            var area = FindUpwards("WalkArea");
            var bounds = area != null ? area : ground;

            if (bounds != null && bounds.TryGetComponent<SpriteRenderer>(out var sr))
            {
                var size = sr.bounds.size;
                halfW = size.x / 2f;
                halfH = size.y / 2f;
                cx = bounds.position.x;
                cy = bounds.position.y;
            }

            minX = cx - halfW;
            maxX = cx + halfW;
            minY = cy - halfH;
            maxY = cy + halfH;

            // 戶外地圖：往內縮，女巫的圖才不會畫到地面外（「穿邊邊」）。她的樞紐在腳底、圖高約 66、
            // 寬約 49 → 上緣縮一個身高、左右各縮半個身寬、下緣只縮一點點。
            // ⚠️ 邊界換場景（OnReachEdge）是在「推到這條新邊界」時觸發的；PortalGlow 的上緣光圈
            //    也跟著往下移到腳走得到的地方（見 PortalGlow.BuildEdgeGlows）。
            if (edgeInset)
            {
                minX += Data.ArtFootprints.EdgeSide;
                maxX -= Data.ArtFootprints.EdgeSide;
                minY += Data.ArtFootprints.EdgeBottom;
                maxY -= Data.ArtFootprints.EdgeTop;
            }
        }

        /// <summary>從自己的父層一路往上找同名的子物件；找不到再退回全場景找。</summary>
        Transform FindUpwards(string name)
        {
            for (var n = transform.parent; n != null; n = n.parent)
            {
                var hit = n.Find(name);
                if (hit != null) return hit;
            }
            var go = GameObject.Find(name);
            return go != null ? go.transform : null;
        }

        /// <summary>
        /// 撞到地圖邊界時呼叫（持續推邊會每幀觸發）。
        /// </summary>
        /// <param name="side">撞到哪一側</param>
        /// <param name="along">撞上去時人在那條邊上的位置（左右側＝y、上下側＝x）</param>
        void OnReachEdge(EdgeSide side, float along)
        {
            if (switching) return;

            // 一張地圖可以有好幾個出口（森林往東到城鎮、往北到糖果鎮）。撞到的那一側
            // 有出口、而且**撞在那個點上**才過得去 —— 整條邊只有那一段能走，其他地方就是牆。
            string sideName = side switch
            {
                EdgeSide.Left => "left", EdgeSide.Right => "right",
                EdgeSide.Top => "top", _ => "bottom",
            };
            string scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
            var gates = Data.Portals.Of(scene);
            foreach (var g in gates)
            {
                if (g.Side != sideName || Mathf.Abs(along - g.At) > g.Span) continue;

                // ⚠️ Unity 的 LoadScene 要求場景**登記在 Build Settings** 裡，沒有的話會直接丟錯。
                //    移植途中有些場景還沒蓋（例如糖果鎮），走到那個門時要安靜地當作牆，
                //    而不是把遊戲炸掉。
                if (!Application.CanStreamedLevelBeLoaded(g.To))
                {
                    Debug.Log($"[PlayerController] 場景「{g.To}」還沒搬過來，這個出口先當牆");
                    return;
                }

                switching = true;
                UI.SceneFade.Go(g.To);          // 淡出 → 切場景 → 淡入
                return;
            }

            // 沒登記在表裡的場景才退回節點上的設定（舊行為）
            if (gates.Count > 0 || string.IsNullOrEmpty(nextMapScene) || side != nextMapEdge) return;
            switching = true;
            UI.SceneFade.Go(nextMapScene);
        }

        void Cast()
        {
            // ⚠️ 動作要先演，而且不受有沒有 spell prefab 影響 —— 按了鍵人卻完全沒反應
            // 是最難查的那種「壞掉了嗎？」。長度跟澆水一樣 0.9 秒，六幀才看得清楚。
            int d = CharacterAnimator.DirOf(facing.x, facing.y);
            var frames = GameArt.CastFrames(d);
            if (frames.Length > 0) anim.PlayOneShot(frames, 0.9f, 0f, true, d);

            Sfx.Play("cast");
            SpellProjectile.Spawn(transform.position, facing);
        }
    }
}
