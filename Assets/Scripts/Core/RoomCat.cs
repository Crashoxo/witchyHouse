using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 藥水室的貓（魔女的使魔）：會在房間裡走來走去、坐著、理毛、睡覺，走近按 E 可以摸牠。
    /// 由 <see cref="BrewRoom"/> 在 SVG 房間蓋好之後呼叫 <see cref="Spawn"/>（只有藥水室有）。
    ///
    /// ── 美術 ──（tools/gen_cat_art.py → Resources/cat8/cat.png，規格見產生器開頭）
    ///   一張 6 欄 × 10 列、每格 40×36 原生像素，跟女巫一樣 ×<see cref="GameArt.WitchScale"/> 顯示（像素一樣大）；
    ///   腳底在格子底邊往上 3px（<see cref="FootPad"/>），所以切格的樞紐放在那條線上，物件的 position ＝ 落腳點。
    ///   側面只畫朝左，往右用 flipX。夜晚**不乘**房間的夜色（跟女巫一樣），黑貓靠藍紫色的背光在暗處讀得出來。
    ///
    /// ── 狀態 ──
    ///   Sit（坐著甩尾巴、眨眼；女巫在附近站著不動時抬頭看她）、Groom（理毛）、Walk（照格子路徑走）、
    ///   Sleep（在貓窩捲成一團，冒 z）、Petted（被摸）、Wake（被摸醒：睡眼惺忪→打哈欠）、Stretch（伸懶腰）、
    ///   Hop（女巫衝刺從旁邊擦過去時嚇一跳）、Greet（好感夠高時，女巫一進門就坐在門口迎接）。
    ///   決定下一件事（<see cref="Decide"/>）：晚上回貓窩睡；白天隨機 —— 走去女巫旁邊坐（好感越高越常）、去貓窩午睡、理毛、坐著、隨便走走。
    ///
    /// ── 走路 ──
    ///   不套女巫的推牆碰撞：在可走範圍上鋪 8px 的格子（格子中心在地板多邊形內、半徑 <see cref="Radius"/> 的圓不碰到任何家具 ＝ 可站，
    ///   用的是 Obstacles.InWalk／IsFree(p, r)），BFS 八向不切角找路、拉直，沿路點直線走（每段都驗過）。
    ///   目的地只從「從現在位置 BFS 走得到的格子」裡挑；走太久（超過預估時間 ×1.6＋2 秒）就放棄、坐下、重新決定 —— 不會卡住。
    ///   貓不擋女巫（沒有登記成障礙）。
    ///
    /// ── 互動的優先順序 ──
    ///   2026-11-28 起交給共用的互動系統（<see cref="Interactable"/>／<see cref="Interact"/>）：貓是一個 range＝<see cref="PetRange"/> 的
    ///   Interactable，跟床、倉庫、衣櫃、鍋爐、門一起比，最近的那個冒提示、吃 E。頭上提示是 [E][愛心]（共用的 InteractHint）。
    ///   家裡佈置中（HomeArrange）、開著面板時 Interact.Suspended 整個暫停（以前是 RoomCat.TakesE 在佈置中回 true 的權宜做法，已拿掉）。
    /// ── 存檔 ──（key "witch.cat"，已列進 SaveManager.SaveKeys）
    ///   JSON {"a":好感, "d":最後摸的那天（TimeSystem.TotalDay）, "n":那天摸了幾次}。每天前 <see cref="DailyPets"/> 次摸＋1，
    ///   上限 <see cref="MaxAffection"/>。缺檔、壞檔＝0。好感只影響貓的行為（更常跟著、更常呼嚕、在門口迎接），不給東西、不碰金幣。
    /// </summary>
    public class RoomCat : MonoBehaviour
    {
        /// <summary>開關：false ＝ 不生活貓，房間照舊擺原本那隻只會眨眼的裝飾貓（BrewRoom 看這個）。</summary>
        public static bool Enabled = true;

        /// <summary>
        /// ★ 貓窩的位置（世界座標＝貓睡覺時的落腳點）。兩種：
        ///   <see cref="DrawnBedAt"/> ── 細畫版房間（BrewRoom.UsePixelRoom、rooms/brew8/rug-hearth 載得到）在壁爐地毯上畫好的粉紅貓窩中心；
        ///   <see cref="OwnBedAt"/>   ── 其他情況（舊 SVG 房間）：同一塊地毯左半邊，RoomCat 自己擺一個紫色坐墊。
        /// 搬貓窩：改那兩個值（細畫版的貓窩是 tools/gen_brew_room8.py 畫在 rug-hearth 上的，兩邊要一起改）。
        /// 離線檢查：python tools/check_cat_room.py（兩個位置都驗：站不站得住、從這裡走得到多少地板）。
        /// </summary>
        public static Vector2 CatBed => DrawnBed ? DrawnBedAt : OwnBedAt;

        public static readonly Vector2 DrawnBedAt = new(305f, -138f);
        public static readonly Vector2 OwnBedAt = new(300f, -138f);

        /// <summary>
        /// 房間美術有沒有畫好貓窩：判斷跟 GameArt.BrewTex 一樣（開關開著、而且細畫版的 rug-hearth 真的載得到 ——
        /// 缺那張圖時 BrewTex 會退回舊地毯，舊地毯上沒有貓窩）。每次 Spawn 重算一次。
        /// </summary>
        public static bool DrawnBed
        {
            get
            {
                if (!drawnBedKnown)
                {
                    drawnBedKnown = true;
                    drawnBed = BrewRoom.UsePixelRoom && Resources.Load<Texture2D>("rooms/brew8/rug-hearth") != null;
                }
                return drawnBed;
            }
        }
        static bool drawnBed, drawnBedKnown;

        /// <summary>好感夠高時，女巫進門那一刻貓坐在這裡迎接（出生點 Spawn 的左上方、在摸得到的距離內）。</summary>
        public static readonly Vector2 DoorGreet = new(44f, -192f);

        /// <summary>貓的腳底圓半徑（找路時離家具多遠）。</summary>
        public const float Radius = 8f;
        /// <summary>女巫的腳離貓的腳多近才能摸（像素）。</summary>
        public const float PetRange = 60f;
        /// <summary>同一次摸之後多久才算「再摸一次」（之內連按 E 只冒小愛心）。</summary>
        public const float PetCooldown = 1.4f;
        public const int MaxAffection = 50;
        /// <summary>每天前幾次摸會加好感。</summary>
        public const int DailyPets = 3;
        /// <summary>好感到這裡起，女巫進門時會在門口迎接。</summary>
        public const int GreetAffection = 5;

        // ── 動畫表（tools/gen_cat_art.py）──
        const string SheetPath = "cat8/cat";
        const int CellW = 40, CellH = 36, Cols = 6, Rows = 10;
        const float FootPad = 3f;
        const int RowWalkDown = 0, RowWalkSide = 1, RowWalkUp = 2, RowSit = 3, RowGroom = 4, RowSleep = 5,
                  RowHappy = 6, RowAct = 7, RowFx = 8, RowProps = 9;
        const int FxHeart = 0, FxHeartSmall = 1, FxZ = 2, FxZBig = 3, FxNote = 4, FxQuestion = 5;
        /// <summary>坐墊在格子裡的落地中心（產生器的 CUSHION_FOOT = (20,29) 的像素中心 → 從左 20.5、從下 36−29.5）。</summary>
        static readonly Vector2 CushionPivot = new(20.5f / CellW, 6.5f / CellH);
        /// <summary>睡在自己擺的坐墊上時，貓往上抬幾個原生 px（坐在墊子凹下去那一塊上）。</summary>
        const float CushionLift = 2f;
        /// <summary>
        /// 睡在房間美術畫的貓窩裡時抬幾個原生 px。貓窩是平貼在地毯上的、裡面奶油色的墊子比 DrawnBedAt 高一點，
        /// 腳底點直接對在中心時貓會偏上（頭跑出窩外）—— 往下 2 剛好窩在墊子正中、上下都露出粉紅的邊（gen_cat_art.py 預覽 bedfit）。
        /// </summary>
        const float DrawnBedLift = -2f;

        static float Scale => GameArt.WitchScale;

        const float WalkSpeed = 52f, TrotSpeed = 92f;
        const float GridStep = 8f;

        enum St { Sit, Groom, Walk, Sleep, Petted, Wake, Stretch, Hop, Greet }
        enum Goal { Wander, ToWitch, ToBed }

        public static RoomCat Live { get; private set; }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { Live = null; save = null; drawnBedKnown = false; }

        /// <summary>在藥水室生一隻貓（BrewRoom.BuildSvgRoom 的最後呼叫）。缺美術時不生、回 null（房間照常）。</summary>
        public static RoomCat Spawn(Transform parent)
        {
            drawnBedKnown = false;                 // 換了房間美術（熱重載）也重新判斷
            if (!LoadSheet())
            {
                Debug.LogWarning("[RoomCat] 找不到 Resources/cat8/cat（跑 python tools/gen_cat_art.py），這次不放貓");
                return null;
            }
            var go = new GameObject("RoomCat");
            go.transform.SetParent(parent, false);
            return go.AddComponent<RoomCat>();
        }

        // ──────────── 美術 ────────────

        static Texture2D sheetTex;
        static Sprite[,] cells;

        static bool LoadSheet()
        {
            var t = Resources.Load<Texture2D>(SheetPath);
            if (t == null) return false;
            // ⚠️ Sprite.Create 的東西離開 Play 會變 fake null，靜態快取要用 Unity 的比較重新驗
            if (t == sheetTex && cells != null && cells[0, 0] != null) return true;
            sheetTex = t;
            cells = new Sprite[Rows, Cols];
            var foot = new Vector2(0.5f, FootPad / CellH);
            var mid = new Vector2(0.5f, 0.5f);
            for (int r = 0; r < Rows; r++)
                for (int c = 0; c < Cols; c++)
                {
                    var pivot = r == RowFx ? mid : r == RowProps ? CushionPivot : foot;
                    cells[r, c] = SheetSlicer.Cell(t, c, r, Cols, Rows, pivot);
                }
            return true;
        }

        static Sprite Cell(int row, int col) => cells[row, col];

        /// <summary>貓的圖載得到嗎（缺圖時 BrewRoom 照舊擺裝飾貓）。</summary>
        public static bool ArtReady => LoadSheet();

        // 各動作的幀序（欄號；同一列）。坐著那串很長：大多是坐好，偶爾甩尾巴、眨眼、抖耳朵。
        static readonly int[] SitSeq = { 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 2, 2, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 4, 0, 0, 0, 1, 1, 0, 0, 2, 2, 0, 0, 0, 3, 0, 0 };
        static readonly int[] WalkSeq = { 0, 1, 2, 3 };
        static readonly int[] GroomSeq = { 0, 1, 0, 1, 2, 3, 2, 3 };
        static readonly int[] SleepSeq = { 0, 1, 2, 2, 1, 0, 0, 0, 1, 2, 2, 1, 0, 0, 3, 0 };
        static readonly int[] HappySeq = { 0, 1, 2, 1, 2, 3 };
        // 列 7（ACT）：0/1 伸懶腰、2 跳起來、3 落地、4 睡眼惺忪、5 打哈欠
        static readonly (int r, int c)[] WakeSeq =
        {
            (RowAct, 4), (RowAct, 4), (RowAct, 4), (RowAct, 5), (RowAct, 5), (RowAct, 5), (RowAct, 4), (RowAct, 4), (RowSit, 3), (RowSit, 0),
        };
        static readonly (int r, int c)[] StretchSeq = { (RowAct, 0), (RowAct, 1), (RowAct, 1), (RowAct, 1), (RowAct, 1), (RowAct, 0), (RowSit, 0) };
        static readonly (int r, int c)[] HopSeq = { (RowAct, 2), (RowAct, 2), (RowAct, 3), (RowAct, 3), (RowSit, 0) };

        // ──────────── 物件 ────────────

        SpriteRenderer sr;
        Transform art;
        Interactable interactable;
        SpriteRenderer cushionSr;
        bool ownCushion;
        Transform player;
        SpriteRenderer playerSr;
        CharacterAnimator playerAnim;

        // 互動點（優先順序用；場景蓋好後才找得到，第一次問的時候才收集）

        // 狀態
        St state;
        float stateTime;         // 這個狀態還剩幾秒（Sit／Groom／Sleep／Petted／Greet 用）
        Goal goal;
        readonly List<Vector2> path = new();
        int pathIdx;
        float speed;
        float walkBudget;
        bool flip;               // true ＝ 圖往右（翻面）
        bool onBed;
        float awakeUntil;        // 被摸醒之後至少醒到這個時間（晚上才不會馬上又睡回去）
        float lastPetAt = -99f;
        float nextZ;
        float hopReadyAt;
        float greetMeowAt = -1f;
        int pendingHearts;
        float nextHeartAt;
        float playerStill;       // 女巫站著不動多久了
        Vector3 playerPrev;

        // 時間跳躍偵測（睡覺過場：畫面全黑時時間會一下子跳到晚上或隔天早上）
        int lastDay;
        float lastTod;

        // 動畫
        int[] seq;
        (int r, int c)[] seqRC;
        int seqRow;
        float fps;
        bool loop;
        float animT;
        bool animDone;
        int lookOverride = -1;   // 坐著抬頭看女巫時用（欄號）

        void Awake()
        {
            Live = this;
            var a = new GameObject("art");
            art = a.transform;
            art.SetParent(transform, false);
            art.localScale = new Vector3(Scale, Scale, 1f);
            sr = a.AddComponent<SpriteRenderer>();
        }

        void OnDestroy()
        {
            if (Live == this) Live = null;
        }

        void Start()
        {
            LoadSheet();
            var p = GameObject.Find("Player");
            if (p != null)
            {
                player = p.transform;
                playerSr = p.GetComponent<SpriteRenderer>();
                playerAnim = p.GetComponent<CharacterAnimator>();
                playerPrev = player.position;
            }
            lastDay = TimeSystem.TotalDay;
            lastTod = TimeSystem.TodHours;

            BuildCushion();
            // 摸：交給共用的互動系統（提示 [E][愛心]；被摸的那一下收起來，連按 E 照樣只冒小愛心）
            interactable = Interactable.Attach(gameObject, PetRange, Pet, () => HintLook.E(HintIcons.Ui("act_pet"), null));
            interactable.anchor = () => transform.position + new Vector3(0f, state == St.Sleep ? 22f : 40f, 0f);
            interactable.hideHint = () => state == St.Petted;
            ShadowLayer.Follow(transform, 26f, 0f);

            // 出場：好感夠高、女巫剛從門口進來 → 坐在門口迎接；晚上 → 在貓窩睡；白天 → 隨機
            bool fromDoor = player != null && Vector2.Distance(player.position, BrewRoomLayout.Spawn) < 60f;
            if (fromDoor && Affection >= GreetAffection && Random.value < 0.85f)
            {
                Place(DoorGreet);
                EnterGreet();
            }
            else if (TimeSystem.IsNight || Random.value < 0.25f)
            {
                Place(CatBed);
                EnterSleep(TimeSystem.IsNight ? 30f : Random.Range(8f, 20f));
            }
            else
            {
                var spot = RandomReachable(transform.position, 0f, CatBed);
                Place(spot ?? CatBed);
                EnterSit(Random.Range(2f, 5f));
            }
        }

        void Place(Vector2 p)
        {
            transform.position = new Vector3(p.x, p.y, 0f);
            onBed = (p - CatBed).sqrMagnitude < 4f;
        }

        // ──────────── 每幀 ────────────

        void Update()
        {
            if (cells == null || cells[0, 0] == null) return;
            float dt = Time.deltaTime;
            // 開著面板、家裡佈置中、換場景（Interact.Suspended）：不走，動畫照播；E 由 Interact 處理
            bool modal = Interact.Suspended;

            DetectTimeJump();
            TrackPlayer(dt);
            Animate(dt);

            if (!modal)
            {
                Think(dt);
                Fx();
            }

            UpdateCushionTint();
        }

        void LateUpdate()
        {
            if (sr == null || sr.sprite == null) return;
            var p = transform.position;
            // 排序：跟女巫同一套（看跟貓的圖重疊的家具在前面還是後面）
            var b = sr.bounds.size;
            sr.sortingOrder = BrewRoom.PlayerOrder(p, b.x, b.y);
            // 跟女巫算出同一個 order 時（兩個都在同一件家具前面），用 z 分前後：腳比她高（在她後面）就往後推
            float z = 0f;
            if (player != null) z = p.y > player.position.y ? 0.5f : -0.5f;
            if (!Mathf.Approximately(p.z, z)) transform.position = new Vector3(p.x, p.y, z);
            // 睡在自己擺的坐墊上要抬高一點；房間美術畫的貓窩用 DrawnBedLift
            float lift = (state == St.Sleep || state == St.Wake) && onBed ? (ownCushion ? CushionLift : DrawnBedLift) * Scale : 0f;
            art.localPosition = new Vector3(0f, lift, 0f);
        }

        void TrackPlayer(float dt)
        {
            if (player == null) return;
            var pp = player.position;
            float moved = Vector2.Distance(pp, playerPrev);
            playerStill = moved < 0.01f ? playerStill + dt : 0f;
            // 女巫衝刺（Shift）從旁邊擦過 → 嚇一跳
            if (dt > 0f && moved / dt > 280f && Time.time >= hopReadyAt && !UIState.ModalOpen
                && (state == St.Sit || state == St.Groom)
                && Vector2.Distance(pp, transform.position) < 48f)
            {
                hopReadyAt = Time.time + 25f;
                EnterOneShot(St.Hop, HopSeq, 8f);
                Sfx.Play("cat-chirp", 0.7f);
            }
            playerPrev = pp;
        }

        void DetectTimeJump()
        {
            int day = TimeSystem.TotalDay;
            float tod = TimeSystem.TodHours;
            bool jumped = day != lastDay || Mathf.Abs(tod - lastTod) > 1f;
            lastDay = day;
            lastTod = tod;
            if (!jumped) return;
            // 睡覺過場（畫面全黑）時間跳了：貓也在貓窩睡著，醒來的那一幕牠在窩裡
            path.Clear();
            Place(CatBed);
            awakeUntil = 0f;
            EnterSleep(TimeSystem.IsNight ? 30f : Random.Range(4f, 9f));
        }

        // ──────────── 決定下一件事 ────────────

        void Think(float dt)
        {
            switch (state)
            {
                case St.Walk:
                    FollowPath(dt);
                    return;
                case St.Sit:
                case St.Greet:
                    UpdateLook();
                    if (state == St.Greet && greetMeowAt > 0f && Time.time >= greetMeowAt)
                    {
                        greetMeowAt = -1f;
                        Sfx.Play("meow", 0.8f);
                        SpawnFx(FxHeart, HeadPos() + new Vector3(0f, 6f, 0f));
                    }
                    break;
                case St.Sleep:
                    stateTime -= dt;
                    if (stateTime > 0f) return;
                    if (TimeSystem.IsNight && Time.time >= awakeUntil) { stateTime = 10f; return; }   // 晚上一直睡
                    EnterOneShot(St.Wake, WakeSeq, 4f);
                    return;
                case St.Petted:
                    stateTime -= dt;
                    if (stateTime <= 0f) EnterSit(Random.Range(2.5f, 4f));   // 摸完坐著、抬頭看她（UpdateLook）
                    return;
                case St.Wake:
                case St.Stretch:
                case St.Hop:
                    if (animDone)
                    {
                        if (state == St.Wake && Random.value < 0.6f) { EnterOneShot(St.Stretch, StretchSeq, 4f); return; }
                        EnterSit(Random.Range(1.5f, 3f));
                    }
                    return;
            }
            stateTime -= dt;
            if (stateTime <= 0f) Decide();
        }

        void Decide()
        {
            lookOverride = -1;
            var here = (Vector2)transform.position;
            float a = Affection;
            bool night = TimeSystem.IsNight && Time.time >= awakeUntil;

            if (night)
            {
                if (onBed) { EnterSleep(30f); return; }
                if (GoTo(CatBed, Goal.ToBed, WalkSpeed)) return;
                EnterSit(3f);
                return;
            }

            float follow = Mathf.Lerp(0.12f, 0.45f, a / 20f);
            float r = Random.value;
            if (player != null && Vector2.Distance(player.position, here) > 80f && r < follow)
            {
                if (GoToWitch()) return;
            }
            r = Random.value;
            if (r < 0.10f && !onBed && GoTo(CatBed, Goal.ToBed, WalkSpeed)) return;
            if (r < 0.28f) { EnterGroom(); return; }
            if (r < 0.50f) { EnterSit(Random.Range(3f, 7f)); return; }
            if (r < 0.56f) { EnterOneShot(St.Stretch, StretchSeq, 4f); return; }
            var t = RandomReachable(here, 70f, here);
            if (t.HasValue && GoTo(t.Value, Goal.Wander, WalkSpeed)) return;
            EnterSit(2f);
        }

        bool GoToWitch()
        {
            if (player == null) return false;
            Vector2 w = player.position;
            Vector2 here = transform.position;
            // 坐到她旁邊（靠貓過來的那一側），在摸得到的距離內
            float side = here.x < w.x ? -1f : 1f;
            Vector2[] tries = { w + new Vector2(34f * side, -6f), w + new Vector2(-34f * side, -6f), w + new Vector2(0f, -30f), w + new Vector2(24f * side, 18f) };
            foreach (var t in tries)
                if (GoTo(t, Goal.ToWitch, TrotSpeed)) return true;
            return false;
        }

        void OnArrive()
        {
            switch (goal)
            {
                case Goal.ToBed:
                    onBed = true;
                    EnterSleep(TimeSystem.IsNight ? 30f : Random.Range(15f, 35f));
                    break;
                case Goal.ToWitch:
                    FaceToward(player != null ? (Vector2)player.position : (Vector2)transform.position);
                    EnterSit(Random.Range(5f, 9f));
                    if (Random.value < 0.3f + Affection / 60f) Sfx.Play("cat-chirp", 0.6f);
                    break;
                default:
                    if (Random.value < 0.35f) EnterGroom();
                    else EnterSit(Random.Range(2.5f, 6f));
                    break;
            }
        }

        // ──────────── 進入各狀態 ────────────

        void EnterSit(float secs)
        {
            state = St.Sit;
            stateTime = secs;
            PlayLoop(RowSit, SitSeq, 5f);
            ShadowLayer.Follow(transform, 26f, 0f);
        }

        void EnterGreet()
        {
            state = St.Greet;
            stateTime = 3.5f;
            greetMeowAt = Time.time + 0.5f;
            if (player != null) FaceToward(player.position);
            PlayLoop(RowSit, SitSeq, 5f);
        }

        void EnterGroom()
        {
            state = St.Groom;
            stateTime = Random.Range(3f, 5.5f);
            PlayLoop(RowGroom, GroomSeq, 5f);
        }

        void EnterSleep(float secs)
        {
            state = St.Sleep;
            stateTime = secs;
            nextZ = Time.time + 1.2f;
            PlayLoop(RowSleep, SleepSeq, 2.5f);
            ShadowLayer.Follow(transform, 34f, 0f);
        }

        void EnterOneShot(St s, (int r, int c)[] frames, float f)
        {
            state = s;
            path.Clear();
            PlayOnce(frames, f);
            ShadowLayer.Follow(transform, 26f, 0f);
        }

        // ──────────── 摸 ────────────

        void Pet()
        {
            FaceWitchToCat();
            if (player != null) FaceToward(player.position);

            bool spam = Time.time - lastPetAt < PetCooldown;
            if (spam)
            {
                SpawnFx(FxHeartSmall, HeadPos() + new Vector3(Random.Range(-6f, 6f), 2f, 0f), 0.8f);
                return;
            }
            lastPetAt = Time.time;
            AddAffection();
            path.Clear();

            if (state == St.Sleep || state == St.Wake)
            {
                // 摸醒：慢慢睜眼、打個哈欠，冒個問號跟小愛心（溫柔，不是被嚇醒）
                awakeUntil = Time.time + Random.Range(12f, 18f);
                EnterOneShot(St.Wake, WakeSeq, 4f);
                SpawnFx(FxQuestion, HeadPos() + new Vector3(6f, 4f, 0f), 1.1f);
                pendingHearts = 1;
                nextHeartAt = Time.time + 0.9f;
                Sfx.Play("cat-chirp", 0.6f);
                return;
            }

            state = St.Petted;
            stateTime = 1.8f;
            PlayLoop(RowHappy, HappySeq, 6f);
            SpawnFx(FxHeart, HeadPos() + new Vector3(-4f, 4f, 0f));
            pendingHearts = 2;
            nextHeartAt = Time.time + 0.35f;
            float purr = 0.45f + Affection / 40f;
            if (Random.value < purr)
            {
                Sfx.Play("purr", 0.8f);
                if (Affection >= GreetAffection && Random.value < 0.5f)
                    SpawnFx(FxNote, HeadPos() + new Vector3(10f, 0f, 0f), 1.4f);
            }
            else Sfx.Play("meow", 0.75f);
        }

        /// <summary>女巫轉向貓（插播一格她那個方向的站姿；播完的待機也維持這個方向）。</summary>
        void FaceWitchToCat()
        {
            if (playerAnim == null || player == null) return;
            var d = transform.position - player.position;
            int dir = CharacterAnimator.DirOf(d.x, d.y);
            var idle = GameArt.WitchIdle(dir);
            if (idle != null) playerAnim.PlayOneShot(new[] { idle }, 0.6f, 0f, false, dir);
        }

        // ──────────── 好感（存檔 witch.cat）────────────

        const string SaveKey = "witch.cat";

        [System.Serializable]
        class CatSave { public int a; public int d = -1; public int n; }

        static CatSave save;

        static CatSave Save
        {
            get
            {
                if (save != null) return save;
                save = new CatSave();
                try
                {
                    var raw = SaveManager.GetString(SaveKey);
                    if (!string.IsNullOrEmpty(raw)) JsonUtility.FromJsonOverwrite(raw, save);
                }
                catch (System.Exception e)
                {
                    Debug.LogWarning($"[RoomCat] 存檔讀不懂，好感從 0 開始：{e.Message}");
                    save = new CatSave();
                }
                save.a = Mathf.Clamp(save.a, 0, MaxAffection);
                save.n = Mathf.Clamp(save.n, 0, DailyPets);
                return save;
            }
        }

        /// <summary>目前的好感（0..MaxAffection）。</summary>
        public static int Affection => Save.a;

        static void AddAffection()
        {
            var s = Save;
            int day = TimeSystem.TotalDay;
            if (s.d != day) { s.d = day; s.n = 0; }
            if (s.n >= DailyPets) return;
            s.n++;
            s.a = Mathf.Min(MaxAffection, s.a + 1);
            SaveManager.SetString(SaveKey, JsonUtility.ToJson(s));
        }

        // ──────────── 走路與找路 ────────────

        bool GoTo(Vector2 target, Goal g, float spd)
        {
            if (!FindPath(transform.position, target, g == Goal.ToBed, path)) return false;
            goal = g;
            speed = spd;
            pathIdx = 0;
            float len = 0f;
            Vector2 prev = transform.position;
            foreach (var q in path) { len += Vector2.Distance(prev, q); prev = q; }
            if (len < 2f) { path.Clear(); OnArrive(); return true; }
            walkBudget = len / spd * 1.6f + 2f;
            state = St.Walk;
            onBed = false;
            lookOverride = -1;
            ShadowLayer.Follow(transform, 26f, 0f);
            return true;
        }

        void FollowPath(float dt)
        {
            walkBudget -= dt;
            if (pathIdx >= path.Count) { path.Clear(); OnArrive(); return; }
            if (walkBudget <= 0f)
            {
                // 走太久（理論上不會，保險）：放棄、坐下、等一下重新決定
                path.Clear();
                EnterSit(1.5f);
                return;
            }
            Vector2 p = transform.position;
            Vector2 t = path[pathIdx];
            Vector2 d = t - p;
            float dist = d.magnitude;
            float step = speed * dt;
            Vector2 np = dist <= step ? t : p + d / dist * step;
            if (dist <= step) pathIdx++;
            transform.position = new Vector3(np.x, np.y, transform.position.z);

            if (dist > 0.01f)
            {
                var v = d / dist;
                int row = Mathf.Abs(v.x) > Mathf.Abs(v.y) * 1.1f ? RowWalkSide : v.y > 0f ? RowWalkUp : RowWalkDown;
                if (row == RowWalkSide) flip = v.x > 0f;
                float f = speed > WalkSpeed + 1f ? 12f : 8f;
                if (seqRow != row || seqRC != null || !loop || !Mathf.Approximately(fps, f)) PlayLoop(row, WalkSeq, f, keepTime: seqRow != row ? false : true);
            }
            if (pathIdx >= path.Count) { path.Clear(); OnArrive(); }
        }

        // 格子：可走範圍的外接矩形，8px 一格；格子中心在地板多邊形內、半徑 Radius 不碰家具 ＝ 可站
        bool[] free;
        int gw, gh;
        Vector2 gOrigin;
        int gridVersion = -1;

        void EnsureGrid()
        {
            Obstacles.EnsureBuilt();
            if (free != null && gridVersion == Obstacles.Version) return;
            var r = Obstacles.WalkRect;
            gOrigin = new Vector2(r.xMin, r.yMin);
            gw = Mathf.Max(1, Mathf.FloorToInt(r.width / GridStep) + 1);
            gh = Mathf.Max(1, Mathf.FloorToInt(r.height / GridStep) + 1);
            free = new bool[gw * gh];
            for (int j = 0; j < gh; j++)
                for (int i = 0; i < gw; i++)
                {
                    var p = CellPos(i, j);
                    free[j * gw + i] = Obstacles.InWalk(p) && Obstacles.IsFree(p, Radius);
                }
            gridVersion = Obstacles.Version;
        }

        Vector2 CellPos(int i, int j) => gOrigin + new Vector2(i * GridStep, j * GridStep);

        (int i, int j) CellOf(Vector2 p) =>
            (Mathf.Clamp(Mathf.RoundToInt((p.x - gOrigin.x) / GridStep), 0, gw - 1),
             Mathf.Clamp(Mathf.RoundToInt((p.y - gOrigin.y) / GridStep), 0, gh - 1));

        bool Free(int i, int j) => i >= 0 && j >= 0 && i < gw && j < gh && free[j * gw + i];

        /// <summary>離 p 最近的可站格（最多找 maxR 格遠；找不到回 -1）。</summary>
        int NearestFree(Vector2 p, int maxR = 6)
        {
            var (ci, cj) = CellOf(p);
            int best = -1;
            float bd = float.MaxValue;
            for (int rr = 0; rr <= maxR && best < 0; rr++)
                for (int j = cj - rr; j <= cj + rr; j++)
                    for (int i = ci - rr; i <= ci + rr; i++)
                    {
                        if (!Free(i, j)) continue;
                        float d = (CellPos(i, j) - p).sqrMagnitude;
                        if (d < bd) { bd = d; best = j * gw + i; }
                    }
            return best;
        }

        static readonly (int dx, int dy)[] Dirs = { (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1) };
        int[] prevCell;
        readonly Queue<int> queue = new();

        /// <summary>從 start 那格 BFS（八向不切角），prevCell 記來源；回傳走得到的格子數。</summary>
        int Bfs(int start, int stopAt = -1)
        {
            if (prevCell == null || prevCell.Length != free.Length) prevCell = new int[free.Length];
            for (int k = 0; k < prevCell.Length; k++) prevCell[k] = -2;
            queue.Clear();
            queue.Enqueue(start);
            prevCell[start] = -1;
            int n = 0;
            while (queue.Count > 0)
            {
                int k = queue.Dequeue();
                n++;
                if (k == stopAt) break;
                int i = k % gw, j = k / gw;
                foreach (var (dx, dy) in Dirs)
                {
                    int a = i + dx, b = j + dy;
                    if (!Free(a, b)) continue;
                    if (dx != 0 && dy != 0 && (!Free(i + dx, j) || !Free(i, j + dy))) continue;   // 不切角
                    int q = b * gw + a;
                    if (prevCell[q] != -2) continue;
                    prevCell[q] = k;
                    queue.Enqueue(q);
                }
            }
            return n;
        }

        /// <summary>
        /// 找一條從 from 到 to 的路（拉直過的世界座標路點，不含起點）。走不到回 false。
        /// exactEnd：終點就算不是可站格也走到正中（貓窩：房間美術的貓窩若登記了碰撞，最後一小段直接踩上去）。
        /// </summary>
        bool FindPath(Vector2 from, Vector2 to, bool exactEnd, List<Vector2> outPath)
        {
            outPath.Clear();
            EnsureGrid();
            int s = NearestFree(from);
            int g = NearestFree(to);
            if (s < 0 || g < 0) return false;
            Bfs(s, g);
            if (prevCell[g] == -2) return false;

            var cellsPath = new List<Vector2>();
            for (int k = g; k >= 0; k = prevCell[k]) cellsPath.Add(CellPos(k % gw, k / gw));
            cellsPath.Reverse();
            Vector2 end = CellPos(g % gw, g / gw);
            bool endFree = Obstacles.InWalk(to) && Obstacles.IsFree(to, Radius);
            if (endFree || (exactEnd && Vector2.Distance(end, to) <= 32f)) end = to;
            cellsPath[cellsPath.Count - 1] = end;

            // 拉直：從目前的點能直線走到的最遠路點就跳過去
            Vector2 cur = from;
            int idx = 0;
            while (idx < cellsPath.Count)
            {
                int far = idx;
                for (int k = cellsPath.Count - 1; k > idx; k--)
                    if (LineFree(cur, cellsPath[k], k == cellsPath.Count - 1 && end == to && !endFree)) { far = k; break; }
                outPath.Add(cellsPath[far]);
                cur = cellsPath[far];
                idx = far + 1;
            }
            return true;
        }

        /// <summary>a→b 這段直線上每 4px 取一點，都要在可站格裡（最後一段走進貓窩時放寬最後 32px）。</summary>
        bool LineFree(Vector2 a, Vector2 b, bool relaxEnd)
        {
            float len = Vector2.Distance(a, b);
            int n = Mathf.Max(1, Mathf.CeilToInt(len / 4f));
            for (int k = 1; k <= n; k++)
            {
                var p = Vector2.Lerp(a, b, (float)k / n);
                if (relaxEnd && Vector2.Distance(p, b) <= 32f) continue;
                var (i, j) = CellOf(p);
                // 取樣點附近四格都要是可站的（格子中心之間的線才不會擦過家具角）
                int i0 = Mathf.FloorToInt((p.x - gOrigin.x) / GridStep), j0 = Mathf.FloorToInt((p.y - gOrigin.y) / GridStep);
                if (!Free(i0, j0) || !Free(i0 + 1, j0) || !Free(i0, j0 + 1) || !Free(i0 + 1, j0 + 1))
                {
                    if (!Free(i, j)) return false;
                    if (!(Obstacles.InWalk(p) && Obstacles.IsFree(p, Radius))) return false;
                }
            }
            return true;
        }

        /// <summary>從 from 走得到、離 avoid 至少 minDist 的隨機可站點（找不到回 null）。</summary>
        Vector2? RandomReachable(Vector2 from, float minDist, Vector2 avoid)
        {
            EnsureGrid();
            int s = NearestFree(from, 10);
            if (s < 0) return null;
            Bfs(s);
            var cand = new List<int>();
            for (int k = 0; k < prevCell.Length; k++)
                if (prevCell[k] != -2 && (CellPos(k % gw, k / gw) - avoid).sqrMagnitude >= minDist * minDist) cand.Add(k);
            if (cand.Count == 0) return null;
            int pick = cand[Random.Range(0, cand.Count)];
            return CellPos(pick % gw, pick / gw);
        }

        // ──────────── 看女巫 ────────────

        void UpdateLook()
        {
            if (player == null) return;
            float d = Vector2.Distance(player.position, transform.position);
            bool look = d < 160f && (playerStill > 0.6f || state == St.Greet);
            if (look)
            {
                FaceToward(player.position);
                lookOverride = 5;
            }
            else lookOverride = -1;
        }

        void FaceToward(Vector2 p)
        {
            // 坐姿的「抬頭看」那格瞳孔偏左 → 看右邊時翻面
            flip = p.x > transform.position.x;
        }

        Vector3 HeadPos()
        {
            float up = state == St.Sleep ? 14f : 30f;
            float side = state == St.Sleep ? (flip ? 9f : -9f) : 0f;
            return transform.position + new Vector3(side, up, 0f);
        }

        // ──────────── 動畫播放 ────────────

        void PlayLoop(int row, int[] frames, float f, bool keepTime = false)
        {
            seqRow = row;
            seq = frames;
            seqRC = null;
            fps = f;
            loop = true;
            animDone = false;
            if (!keepTime) animT = 0f;
            ShowFrame();
        }

        void PlayOnce((int r, int c)[] frames, float f)
        {
            seqRC = frames;
            seq = null;
            seqRow = -1;
            fps = f;
            loop = false;
            animDone = false;
            animT = 0f;
            ShowFrame();
        }

        void Animate(float dt)
        {
            animT += dt;
            ShowFrame();
        }

        void ShowFrame()
        {
            int n = seqRC != null ? seqRC.Length : seq != null ? seq.Length : 0;
            if (n == 0) return;
            int i = Mathf.FloorToInt(animT * fps);
            if (loop) i %= n;
            else if (i >= n) { i = n - 1; animDone = true; }
            Sprite s;
            if (seqRC != null) s = Cell(seqRC[i].r, seqRC[i].c);
            else if (seqRow == RowSit && lookOverride >= 0 && seq[i] != 3) s = Cell(RowSit, lookOverride);   // 看著她時照樣會眨眼
            else s = Cell(seqRow, seq[i]);
            sr.sprite = s;
            // 走路以外的動作（坐、睡、被摸…）都是正面或朝左畫的，翻不翻看 flip；朝上／朝下走不翻
            bool vertical = seqRC == null && (seqRow == RowWalkDown || seqRow == RowWalkUp);
            sr.flipX = !vertical && flip;
        }

        // ──────────── 特效 ────────────

        void Fx()
        {
            if (state == St.Sleep && Time.time >= nextZ)
            {
                nextZ = Time.time + 1.7f;
                bool big = Random.value < 0.4f;
                var at = HeadPos() + new Vector3(flip ? 6f : -6f, 8f, 0f);
                SpawnFx(big ? FxZBig : FxZ, at, 2.2f, new Vector3(flip ? 10f : -10f, 26f, 0f));
            }
            if (pendingHearts > 0 && Time.time >= nextHeartAt)
            {
                pendingHearts--;
                nextHeartAt = Time.time + 0.35f;
                SpawnFx(pendingHearts % 2 == 0 ? FxHeartSmall : FxHeart, HeadPos() + new Vector3(Random.Range(-8f, 8f), 4f, 0f));
            }
        }

        void SpawnFx(int col, Vector3 at, float dur = 1.2f, Vector3? move = null)
        {
            var go = new GameObject("cat-fx");
            go.transform.position = new Vector3(at.x, at.y, 0f);
            go.transform.localScale = new Vector3(Scale, Scale, 1f);
            var s = go.AddComponent<SpriteRenderer>();
            s.sprite = Cell(RowFx, col);
            s.sortingOrder = 9300;
            go.AddComponent<FloatAway>().Begin(move ?? new Vector3(Random.Range(-4f, 4f), 30f, 0f), dur, 0.5f);
        }

        // ──────────── 家裡佈置（HomeArrange／HomeFurnishings 叫）────────────

        /// <summary>
        /// 家裡的擺設變了（進佈置模式、擺下家具、進房間驗存檔）：丟掉走到一半的路、坐下；
        /// moveTo 有值 ＝ 新擺的家具壓到貓了，挪到那個（最近、走得到的）空位。找路的格子看 Obstacles.Version 自己重建。
        /// </summary>
        public void OnRoomChanged(Vector2? moveTo)
        {
            if (moveTo.HasValue) Place(moveTo.Value);
            if (state == St.Walk || moveTo.HasValue)
            {
                path.Clear();
                EnterSit(Random.Range(2f, 4f));
            }
        }

        /// <summary>貓的小圖（坐姿那一格；家裡佈置的提示列「這裡是貓窩」用）。缺美術回 null。</summary>
        public static Sprite IconSprite => LoadSheet() ? Cell(RowSit, 0) : null;

        // ──────────── 貓窩 ────────────

        void BuildCushion()
        {
            // 房間美術自己畫了貓窩（細畫版地毯上的、或家具名含 cushion／cat-bed）就不另外擺
            if (DrawnBed) return;
            foreach (var p in BrewRoomLayout.Pieces)
            {
                var n = p.Name ?? "";
                if (n.Contains("cushion") || n.Contains("cat-bed") || n.Contains("catbed") || n.Contains("pet-bed")) return;
            }
            var go = new GameObject("CatCushion");
            go.transform.SetParent(transform.parent, false);
            go.transform.position = new Vector3(CatBed.x, CatBed.y, 0f);
            go.transform.localScale = new Vector3(Scale, Scale, 1f);
            cushionSr = go.AddComponent<SpriteRenderer>();
            cushionSr.sprite = Cell(RowProps, 0);
            // 平貼地面的東西：壓在地毯（-9500）之上、影子（-8500）之下 —— 貓睡在上面、影子落在墊子上
            cushionSr.sortingOrder = -9000;
            ownCushion = true;
            UpdateCushionTint(true);
        }

        bool cushionNight;

        void UpdateCushionTint(bool force = false)
        {
            if (cushionSr == null) return;
            bool night = TimeSystem.IsNight;
            if (!force && night == cushionNight) return;
            cushionNight = night;
            cushionSr.color = night ? BrewRoomLayout.NightTint : Color.white;
        }
    }
}
