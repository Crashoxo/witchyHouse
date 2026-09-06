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
        [Tooltip("離邊界再往內縮多少（像素），避免角色圖貼齊切邊")]
        public float edgeMargin = 0f;

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

        // 等距房間（店裡）：地板是菱形，不能用矩形夾邊，改用 ShopRoom 的格座標夾。
        bool isoRoom;

        Transform ground;             // 點擊移動的接收面（也用來量邊界）
        Vector3? moveTarget;          // 點擊指定的目的地（null＝沒有）
        CharacterAnimator anim;
        Camera cam;

        void Awake()
        {
            anim = GetComponent<CharacterAnimator>();
            cam = Camera.main;
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

            // 各場景專屬的東西，同樣在這裡喚起 —— 不用改場景檔（對應原版的做法）
            string scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
            isoRoom = scene == "shop";
            if (scene == "shop")
            {
                ShopRoomView.Ensure();       // 地板底圖 + 擺出來的家具與裝飾
                ShopRoomEditor.Ensure();     // 按 R 進入佈置模式（拖曳家具）
                CustomerManager.Ensure();    // 顧客上門買東西
                SaleCounter.Ensure();        // 販售桌前按 E 開上架面板
            }
            if (scene == "garden") GardenRoom.Ensure();      // 背景、花圃、回店的門、柵欄外的村民
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


        }

        void Update()
        {
            if (UIState.ModalOpen) { moveTarget = null; return; }   // 開著視窗時角色不動
            // 佈置模式中滑鼠是用來拖家具的，不能同時當「點地面走過去」
            if (ShopRoomEditor.Instance != null && ShopRoomEditor.Instance.Editing)
            { moveTarget = null; return; }

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

            if (x != 0f || y != 0f)
            {
                moveTarget = null;              // 鍵盤一動就接手，取消點擊移動
            }
            else if (moveTarget.HasValue)
            {
                var p0 = transform.position;
                float tx = moveTarget.Value.x - p0.x, ty = moveTarget.Value.y - p0.y;
                float dist = Mathf.Sqrt(tx * tx + ty * ty);
                if (dist <= Mathf.Max(speed * dt, 2f))   // 到了：貼齊目的地就收工
                {
                    transform.position = new Vector3(moveTarget.Value.x, moveTarget.Value.y, p0.z);
                    moveTarget = null;
                    return;
                }
                x = tx / dist; y = ty / dist;
            }

            dir = new Vector2(x, y);
            if (dir.sqrMagnitude > 0f)
            {
                dir.Normalize();
                facing = dir;                   // 記住最後移動方向當作面向
                var p = transform.position;
                float nx = p.x + dir.x * speed * dt;
                float ny = p.y + dir.y * speed * dt;

                if (isoRoom)
                {
                    // 等距房間：夾在菱形地板內。出口不是邊界而是地板上的門（見 ShopRoom.Door*）。
                    var c = Data.ShopRoom.ClampToFloor(nx, ny);
                    nx = c.x; ny = c.y;
                }
                else if (clampToBounds)
                {
                    if (nx < minX) { nx = minX; OnReachEdge(EdgeSide.Left, ny); }
                    else if (nx > maxX) { nx = maxX; OnReachEdge(EdgeSide.Right, ny); }
                    if (ny < minY) { ny = minY; OnReachEdge(EdgeSide.Bottom, nx); }
                    else if (ny > maxY) { ny = maxY; OnReachEdge(EdgeSide.Top, nx); }
                }
                transform.position = new Vector3(nx, ny, p.z);
            }
        }

        static bool Key(KeyCode k) => Input.GetKey(k);

        void HandleHotkeys()
        {
            // 點地面 → 記下目的地，Update 每幀走過去。
            if (Input.GetMouseButtonDown(0) && cam != null)
            {
                var w = cam.ScreenToWorldPoint(Input.mousePosition);
                if (isoRoom)
                {
                    var c = Data.ShopRoom.ClampToFloor(w.x, w.y);
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
        }

        /// <summary>
        /// 從場景裡的 "Ground" 物件算出可走範圍；沒有就用 worldHalfWidth/Height。
        /// 有 "WalkArea" 就以它為準：後花園的草地是個菱形，可以走的範圍比整張背景小很多，
        /// 不然人會走到柵欄外的石板路和房子上面去。
        /// </summary>
        void ComputeBounds()
        {
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

            minX = cx - halfW + edgeMargin;
            maxX = cx + halfW - edgeMargin;
            minY = cy - halfH + edgeMargin;
            maxY = cy + halfH - edgeMargin;
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

            SpellProjectile.Spawn(transform.position, facing);
        }
    }
}
