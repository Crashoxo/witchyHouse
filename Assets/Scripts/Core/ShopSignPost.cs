using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 城鎮裡、自家小屋（cottage-home）門口外面的立式招牌＋風鈴 —— **純顯示**：跟著 <see cref="ShopSign"/>
    /// 翻面、搖風鈴、關店時輕輕晃提醒。路過的村民與回家的玩家都看得到店有沒有開。
    ///
    /// 由 <see cref="Doorways"/>.InstallTown 生出來（跟小屋的門同一個時機，不改場景檔），
    /// 落地點＝小屋位置＋Doorways.CottageSign。
    ///
    /// ── 為什麼不在店裡 ──────────────────────────────────────────
    /// 以前站在店裡通往城鎮那道門旁邊（ShopRoom 的 (7,9) 格，還得列成保留格、不給擺家具）。
    /// 使用者回饋「開關店那個旗子不要放在店裡面」→ 搬到城鎮的店門口：招牌本來就該掛在店外面給客人看，
    /// 店裡那一格也還給佈置。
    ///
    /// ── 為什麼不能按 ────────────────────────────────────────────
    /// 以前是「走近按 E 切換開店／關店」；使用者實機回饋「開關店要做在工具列上啦XD（上方）」→
    /// 入口改成上方工具列的按鈕（UI/CornerHud，也有熱鍵 P），在任何場景都能切。
    /// 招牌只負責顯示，**沒有互動、沒有按鍵提示**（兩個入口只會讓人搞混）。
    ///
    /// ── 美術 ───────────────────────────────────────────────────
    /// Resources/shopsign/ 底下的圖由 tools/gen_shop_sign.py 程式點陣畫（道具圖示那套畫風），
    /// 全部同一張畫布（<see cref="CanvasW"/>×<see cref="CanvasH"/>），疊起來就是完整招牌：
    ///   post（柱子＋橫桿，不動）、board-open／board-closed（木牌兩面）、chime（風鈴）。
    /// 每一層用 SheetSlicer.Whole 自己指定 pivot 建 Sprite：柱子的 pivot＝落地點、木牌與風鈴的 pivot＝掛點，
    /// 所以轉動／翻面直接轉 transform 就好，不用再套一層空物件。
    /// 原尺寸擺（1 圖片像素＝1 世界像素、顆粒 2px）：招牌高 94，跟女巫（×1.6 後約一個身高）差不多，
    /// 站在小屋旁邊比例剛好、OPEN／CLOSED 看得清楚；城鎮地面也是 2px 顆粒，對得上。
    /// ⚠️ 下面幾個像素座標（Foot／BoardPivot／ChimePivot）是產生器印出來的，改圖要一起改。
    ///
    /// ── 位置 ───────────────────────────────────────────────────
    /// 小屋正面右邊、門前石階的右側草地上（柱子在屋子正面轉角的前方，木牌掛在右側牆前面）。
    /// 刻意**避開門口光圈**（PortalGlow 的 76×30 橢圓，圓心在門的觸發點）與石階，
    /// 也不壓到門邊的花與右邊的樹樁；不在村民路點上（小屋前面是草地，路在外圍）。
    /// tools/gen_shop_sign.py --preview 會照同一組座標疊在城鎮實景上給人看。
    ///
    /// ── 排序 ───────────────────────────────────────────────────
    /// 戶外那一套：order ＝ -落地點 y（柱子），木牌與風鈴 +1；女巫也是 -腳底 y。
    /// 女巫站在招牌前面（腳底比較低）→ 蓋住招牌；繞到它後面（靠牆那側）→ 被招牌蓋住。
    /// 小屋是 KeepOrder（照圖片中心 y 390 排，order −390），招牌的 −246 比它大 → 永遠畫在房子前面。
    ///
    /// ── 碰撞 ───────────────────────────────────────────────────
    /// 柱子很細，只登記一個很小的橢圓（<see cref="BlockHalf"/>，在柱腳）—— 戶外其他東西都會擋，
    /// 唯獨招牌能穿過去會很怪；又小到不會卡住往門口走的路。
    /// 在 Start 登記：PlayerController.Awake 的 Obstacles.Begin 會清空登記，Start 一定在它之後。
    /// tools/check_walkable.py 讀同一組數字（Doorways.CottageSign、BlockHalf）把它算進城鎮的檢查。
    ///
    /// ── 夜晚 ───────────────────────────────────────────────────
    /// 跟房子一樣被 DayNightTint 的夜色蓋暗（不另外發光）：路燈有光，招牌暗暗的反而像真的。
    ///
    /// ── 動畫（不配置記憶體，只轉 transform）──────────────────────────
    ///   ● 切換（工具列按鈕、熱鍵、或任何地方呼叫 ShopSign.SetOpen）：木牌以掛點為軸翻面
    ///     （scale.x 走 |cos|，過半時換圖）＋最後彈一下；風鈴大幅搖一陣慢慢停。
    ///   ● 關店時：木牌與風鈴**一直輕輕晃**，提醒玩家「店還沒開」；走進城鎮、或新的一天開始時店還關著，
    ///     先大大晃一下（醒目，但不用任何文字）。
    ///   ● 開店時：只有風鈴被風吹得微微動。
    ///   時間用 Time.unscaledTime（開著面板 timeScale 改了也照樣動，跟 Sfx 的習慣一致）。
    /// </summary>
    public class ShopSignPost : MonoBehaviour
    {
        public static ShopSignPost Instance { get; private set; }

        /// <summary>柱腳的碰撞橢圓（兩個半徑，圓心＝落地點）。tools/check_walkable.py 讀這一行。</summary>
        public static readonly Vector2 BlockHalf = new(8f, 4f);

        // ── 圖的幾何（像素，左上原點、y 往下；tools/gen_shop_sign.py 印出來的）──
        const float CanvasW = 100f, CanvasH = 94f;
        static readonly Vector2 Foot = new(11f, 90f);
        static readonly Vector2 BoardPivot = new(47f, 20f);
        static readonly Vector2 ChimePivot = new(85f, 20f);

        const string Folder = "shopsign/";

        // ── 動畫參數 ──
        const float FlipTime = 0.32f;          // 翻面全程（秒）
        const float SwingDecay = 2.2f;         // 晃動的衰減（1/秒）
        const float SwingFreq = 2.0f;          // 晃動頻率（Hz）
        const float IdleClosedDeg = 3.2f;      // 關店時木牌持續輕晃的幅度（度）
        const float IdlePeriod = 2.6f;         // 持續輕晃的週期（秒）

        SpriteRenderer postSr, boardSr, chimeSr;
        Transform board, chime;
        Sprite openSp, closedSp;

        bool shownOpen;                        // 木牌現在畫的是哪一面
        float flipStart = -99f;                // 翻面動畫開始的時間（unscaledTime）
        float swingStart = -99f, swingAmp;     // 一次性大晃（切換、提醒）的起點與幅度
        int lastDay = -1;

        /// <summary>
        /// 城鎮呼叫一次（重複呼叫安全）。foot＝落地點（世界座標）；會對齊到偶數像素。
        /// </summary>
        public static ShopSignPost Ensure(Vector2 foot)
        {
            if (Instance != null) return Instance;
            // 落地點對齊到偶數像素：城鎮地面是「1 美術像素＝2 世界像素」，招牌的顆粒也是 2px，
            // 對齊了顆粒才不會看起來半格錯位
            var go = new GameObject("ShopSign");
            go.transform.position = new Vector3(Mathf.Round(foot.x / 2f) * 2f, Mathf.Round(foot.y / 2f) * 2f, 0f);
            return go.AddComponent<ShopSignPost>();
        }

        void Awake() { Instance = this; }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        void OnEnable() => ShopSign.Changed += OnSignChanged;
        void OnDisable() => ShopSign.Changed -= OnSignChanged;

        void Start()
        {
            if (!Build())
            {
                // 沒圖（還沒跑 tools/gen_shop_sign.py）：整個物件停掉
                Debug.LogWarning("[ShopSignPost] 找不到 Resources/shopsign/ 的圖 —— 跑一次 python tools/gen_shop_sign.py");
                enabled = false;
                return;
            }

            shownOpen = ShopSign.IsOpen;
            boardSr.sprite = shownOpen ? openSp : closedSp;
            lastDay = TimeSystem.TotalDay;

            // 柱腳的小碰撞（見檔頭「碰撞」）：Start 一定在 PlayerController.Awake 的 Obstacles.Begin 之後
            Obstacles.AddEllipse("shop-sign", transform.position, BlockHalf, "prop");

            // 一走進城鎮若是關著的：先大大晃一下（遲一點，等淡入結束玩家看得到）
            if (!shownOpen) Nudge(0.5f);
        }

        // ──────────── 建物件 ────────────

        static Sprite Load(string name, Vector2 pivotPx)
        {
            var t = Resources.Load<Texture2D>(Folder + name);
            if (t == null) return null;
            // pivot 是正規化座標、y 往上；產生器給的是像素、y 往下
            var pivot = new Vector2(pivotPx.x / t.width, 1f - pivotPx.y / t.height);
            return SheetSlicer.Whole(t, pivot);
        }

        bool Build()
        {
            var post = Load("post", Foot);
            openSp = Load("board-open", BoardPivot);
            closedSp = Load("board-closed", BoardPivot);
            var chimeSp = Load("chime", ChimePivot);
            if (post == null || openSp == null || closedSp == null || chimeSp == null) return false;

            int order = Mathf.RoundToInt(-transform.position.y);  // 戶外那一套（-落地點 y，女巫也是）

            postSr = Layer("post", post, Vector2.zero, order);
            boardSr = Layer("board", openSp, BoardPivot - Foot, order + 1);
            chimeSr = Layer("chime", chimeSp, ChimePivot - Foot, order + 1);
            board = boardSr.transform;
            chime = chimeSr.transform;
            return true;
        }

        /// <summary>
        /// 一層圖。offsetPx 是「這層的 pivot 相對落地點」的像素位移（y 往下），換成世界的 y 往上。
        /// </summary>
        SpriteRenderer Layer(string name, Sprite sp, Vector2 offsetPx, int order)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            go.transform.localPosition = new Vector3(offsetPx.x, -offsetPx.y, 0f);
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = order;
            return sr;
        }

        // ──────────── 每幀 ────────────

        void Update()
        {
            // 新的一天開始時店還關著 → 大晃一下提醒（在城鎮裡過了午夜）
            int day = TimeSystem.TotalDay;
            if (day != lastDay)
            {
                lastDay = day;
                if (!ShopSign.IsOpen) Nudge(0f);
            }

            Animate(Time.unscaledTime);
        }

        /// <summary>狀態變了（工具列按鈕、熱鍵、或別處呼叫 ShopSign.SetOpen）：翻面＋風鈴大晃。</summary>
        void OnSignChanged()
        {
            if (boardSr == null) return;
            flipStart = Time.unscaledTime;
            swingStart = flipStart;
            swingAmp = 16f;
        }

        /// <summary>一次性的提醒大晃（不翻面、不出聲）。delay 秒後開始。</summary>
        void Nudge(float delay)
        {
            swingStart = Time.unscaledTime + delay;
            swingAmp = 10f;
        }

        void Animate(float now)
        {
            if (board == null) return;
            bool open = ShopSign.IsOpen;

            // ① 翻面：scale.x ＝ |cos(πt)|，過半（側面朝玩家、看不到的那一瞬）才換圖
            float ft = (now - flipStart) / FlipTime;
            float sx = 1f, sy = 1f;
            if (ft >= 0f && ft < 1f)
            {
                sx = Mathf.Max(0.08f, Mathf.Abs(Mathf.Cos(ft * Mathf.PI)));
                if (ft >= 0.5f && shownOpen != open) { shownOpen = open; boardSr.sprite = open ? openSp : closedSp; }
                if (ft >= 0.5f) sy = 1f + 0.12f * Mathf.Sin((ft - 0.5f) * 2f * Mathf.PI);   // 翻回來時彈一下
            }
            else if (shownOpen != open)
            {
                // 沒有在翻面卻對不上（例如翻面途中又被切回去、動畫被略過）—— 直接換掉
                shownOpen = open;
                boardSr.sprite = open ? openSp : closedSp;
            }
            board.localScale = new Vector3(sx, sy, 1f);

            // ② 晃動：一次性大晃（指數衰減的正弦）＋ 關店時的持續輕晃
            float st = now - swingStart;
            float burst = st >= 0f && st < 3f
                ? swingAmp * Mathf.Exp(-st * SwingDecay) * Mathf.Sin(st * SwingFreq * 2f * Mathf.PI)
                : 0f;
            float idle = open ? 0f : IdleClosedDeg * Mathf.Sin(now * 2f * Mathf.PI / IdlePeriod);
            board.localRotation = Quaternion.Euler(0f, 0f, burst * 0.55f + idle);

            // 風鈴比木牌輕：晃得更大、相位慢一拍；開店時也有一點點微風
            float breeze = (open ? 1.5f : IdleClosedDeg * 1.4f) * Mathf.Sin(now * 2f * Mathf.PI / IdlePeriod - 0.9f);
            chime.localRotation = Quaternion.Euler(0f, 0f, burst * 1.2f + breeze);
        }
    }
}
