using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 全域 UI 狀態旗標（跨腳本共用）。
    ///
    /// ModalOpen＝目前有沒有開著擋操作的視窗（商店、對話…）。開著時
    /// PlayerController 不移動 / 不施法、GatherTree 不採集，避免操作穿透到世界。
    /// 用一個純 static 類別而不是掛在某個元件上，是為了讓各腳本都能引用又不互相牽連。
    /// </summary>
    public static class UIState
    {
        public static bool ModalOpen;
    }

    /// <summary>
    /// 女巫的走路動畫。
    ///
    /// 判斷方式是「這一幀節點有沒有移動」，所以完全不用改 PlayerController ——
    /// 任何會移動節點的東西掛上去就會動。
    ///
    /// ── 八方向 ──
    /// GameArt.WitchReady() 為真時走 chibi 圖集：每個方向都有自己的站姿與 8 幀走路，
    /// **不再翻面**（八個方向都畫好了，翻面反而會把帽子與手上的杖照鏡子），
    /// 節點縮放也由這裡統一設成 WitchScale，所以場景一個都不用改。
    ///
    /// ── 跑步 ──
    /// 要不要播跑步是**看這一幀移動得多快**算出來的（超過 RunSpeed 就換跑步圖），
    /// 不用 PlayerController 通知 —— 跟上面「靠位移判斷」同一套想法，之後不管是衝刺、
    /// 加速道具還是被推著跑，動畫都會自己對。
    ///
    /// 另外提供 PlayOneShot() 讓別的腳本插播一段動作動畫（採集、施法、澆水）。
    /// 播放期間走路/待機不搶畫面；玩家一移動就自動取消。
    ///
    /// ── 移植註記 ──
    /// Cocos 版有一段 applyWitchScale()，要把 Sprite 的 sizeMode 從 RAW 改成 CUSTOM，
    /// 否則切出來的一格會被拉伸成整張圖集那麼大。Unity 的 SpriteRenderer 直接照
    /// Sprite 自己的 rect 畫，**沒有這個問題**，所以那段只剩下設 localScale。
    /// </summary>
    [RequireComponent(typeof(SpriteRenderer))]
    public class CharacterAnimator : MonoBehaviour
    {
        /// <summary>
        /// 移動速度超過這個值（像素/秒）就播跑步。
        /// PlayerController 走路 200、按住 Shift 衝刺 ×1.7 ＝ 340，取中間值當門檻，
        /// 點擊自動尋路（用的是走路速度）就不會誤判成在跑。
        /// </summary>
        const float RunSpeed = 260f;

        [Tooltip("待機圖（舊圖 fallback：正面）。圖集載得到時用不到。")]
        public Sprite idle;
        [Tooltip("走路循環（舊圖 fallback：側面朝左）。")]
        public Sprite[] walk = new Sprite[0];
        [Tooltip("舊圖 fallback 的播放速度（每秒幾格）。")]
        public int walkFps = 10;

        SpriteRenderer sr;
        Vector3 prev;
        float timer;
        int frame;
        int dir;              // 目前面向（見 WitchDir）
        bool scaled;          // 已依圖集調過節點縮放

        // 插播動畫（採集等）
        Sprite[] shot = new Sprite[0];
        float shotTimer = -1f;   // <0 ＝ 沒在插播
        float shotDur;

        void Awake()
        {
            sr = GetComponent<SpriteRenderer>();
            prev = transform.position;
            GameArt.Preload();
        }

        /// <summary>目前面向（0 南、2 東、4 北、6 西；每 45° 一格）。</summary>
        public int FacingDir => dir;

        /// <summary>現在是不是正在插播動作動畫。</summary>
        public bool Busy => shotTimer >= 0f;

        /// <summary>
        /// 插播一段一次性動作動畫（等分幀、播完回到走路/待機）。
        /// </summary>
        /// <param name="frames">動畫幀（空陣列＝不播）</param>
        /// <param name="dur">總長度（秒）</param>
        /// <param name="faceX">面向：&gt;0 朝右、&lt;0 朝左、0 維持原朝向。**只有舊圖會用到**
        ///   （舊圖的動作幀只有正面，翻面只會讓她背對玩家）</param>
        /// <param name="front">正面圖＝一律不翻面。同樣只有舊圖會用到</param>
        /// <param name="faceDir">這段動作朝哪個方向（見 WitchDir，負數＝不改）。圖集的動作幀是
        ///   分方向的，傳進來的話連「播完之後的待機」也會維持那個朝向，人才不會演完就轉回去。</param>
        public void PlayOneShot(Sprite[] frames, float dur = 0.9f, float faceX = 0f,
                                bool front = false, int faceDir = -1)
        {
            if (sr == null || frames == null || frames.Length == 0) return;
            if (faceDir >= 0) dir = ((faceDir % GameArt.WitchDirs) + GameArt.WitchDirs) % GameArt.WitchDirs;
            shot = frames;
            shotDur = Mathf.Max(0.1f, dur);
            shotTimer = 0f;
            if (!GameArt.WitchReady())
            {
                var s = transform.localScale;
                if (front)
                {
                    if (s.x < 0) transform.localScale = new Vector3(-s.x, s.y, s.z);
                }
                else if (!Mathf.Approximately(faceX, 0f))
                {   // 側面圖畫的是朝左，朝右要翻面
                    float want = faceX > 0 ? -Mathf.Abs(s.x) : Mathf.Abs(s.x);
                    if (!Mathf.Approximately(want, s.x)) transform.localScale = new Vector3(want, s.y, s.z);
                }
            }
            sr.sprite = shot[0];
        }

        /// <summary>
        /// 位移向量 → 方向索引。0 是南（往下），每 45° 逆時針加一。
        /// 圖集的欄序是 south, south-east, east, …，剛好就是這個順序。
        /// （公開的：施法與澆水要用「朝目標的方向」去挑那一組動作幀。）
        /// </summary>
        public static int DirOf(float dx, float dy)
        {
            float deg = Mathf.Atan2(dy, dx) * Mathf.Rad2Deg;      // 東＝0、北＝90
            int i = Mathf.RoundToInt((deg + 90f) / 45f) % GameArt.WitchDirs;
            return (i + GameArt.WitchDirs) % GameArt.WitchDirs;
        }

        /// <summary>圖集就緒後把節點調成該有的大小（只做一次）。</summary>
        void ApplyWitchScale()
        {
            if (scaled) return;
            var f = GameArt.WitchIdle(0);
            if (f == null || sr == null) return;
            scaled = true;
            // PPU = 1，所以 Sprite 本身就是原始像素大小，只要縮放節點即可。
            transform.localScale = new Vector3(GameArt.WitchScale, GameArt.WitchScale, 1f);
        }

        // ──────────── 腳下影子 ────────────

        /// <summary>女巫圖集裡，鞋底到那一格底緣還剩幾個像素的透明邊（量 base.png 得到 3）。</summary>
        const float FootPad = 3f;

        float shadowW = -1f;   // 上次登記的影子寬度（尺寸沒變就不用再叫 ShadowLayer）

        /// <summary>
        /// 把影子的大小與落腳點交給 <see cref="ShadowLayer"/>。
        ///
        /// 女巫的圖是用 <see cref="SheetSlicer.Foot"/> 切的（樞紐在格子底邊），所以
        /// <c>position</c> 已經是落腳點；只差鞋底到格子底邊那幾個像素的透明邊。
        /// </summary>
        void UpdateShadow()
        {
            var sp = sr.sprite;
            if (sp == null) return;

            // 面向是靠 localScale.x 翻正負的，取絕對值才是實際大小
            float sx = Mathf.Abs(transform.localScale.x);
            float w = sp.rect.width * sx;
            if (Mathf.Approximately(w, shadowW)) return;   // 每幀換圖但格寬一樣 → 通常直接回來
            shadowW = w;

            ShadowLayer.Follow(transform, w, FootPad * Mathf.Abs(transform.localScale.y));
        }

        /// <summary>用 LateUpdate：PlayerController 是在 Update 裡移動角色的，這裡才讀得到這一幀的位移。</summary>
        void LateUpdate()
        {
            if (sr == null) return;
            float dt = Time.deltaTime;

            var p = transform.position;
            float dx = p.x - prev.x;
            float dy = p.y - prev.y;
            bool moving = dx != 0f || dy != 0f;
            prev = p;

            bool eight = GameArt.WitchReady();
            if (eight) ApplyWitchScale();
            UpdateShadow();
            if (moving) dir = DirOf(dx, dy);

            // 插播中：走路/待機讓位，玩家一動就取消（不然採集動作會卡住畫面）
            if (shotTimer >= 0f)
            {
                if (moving)
                {
                    shotTimer = -1f;
                }
                else
                {
                    shotTimer += dt;
                    if (shotTimer >= shotDur)
                    {
                        shotTimer = -1f;
                    }
                    else
                    {
                        int i = Mathf.Min(shot.Length - 1,
                                          Mathf.FloorToInt(shotTimer / shotDur * shot.Length));
                        sr.sprite = shot[i];
                        return;
                    }
                }
            }

            // 跑得夠快就換跑步那組（沒有的話 WitchRun 回空陣列，照樣走路）
            bool running = eight && moving && dt > 0f
                && Mathf.Sqrt(dx * dx + dy * dy) / dt > RunSpeed
                && GameArt.WitchRun(dir).Length > 0;

            var walkFrames = eight ? (running ? GameArt.WitchRun(dir) : GameArt.WitchWalk(dir)) : walk;
            var idleFrame = eight ? GameArt.WitchIdle(dir) : idle;
            var scale = transform.localScale;

            if (!moving || walkFrames.Length == 0)
            {
                timer = 0f;
                frame = 0;
                if (idleFrame != null) sr.sprite = idleFrame;
                // 舊圖的待機是正面圖，翻面沒有意義
                if (!eight && scale.x < 0)
                    transform.localScale = new Vector3(-scale.x, scale.y, scale.z);
                return;
            }

            if (!eight && dx != 0f)
            {   // 舊圖：側面朝左，往右走翻面（純上下走時維持原朝向）
                float want = dx > 0 ? -Mathf.Abs(scale.x) : Mathf.Abs(scale.x);
                if (!Mathf.Approximately(want, scale.x))
                    transform.localScale = new Vector3(want, scale.y, scale.z);
            }

            // 圖集一輪 8 幀（舊圖 5 幀），照 10fps 播會顯得拖 → 八方向固定 13fps，
            // 跑步再快一點（16fps），腳步才跟得上速度
            timer += dt;
            float step = 1f / (eight ? (running ? 16f : 13f) : Mathf.Max(1f, walkFps));
            while (timer >= step)
            {
                timer -= step;
                frame = (frame + 1) % walkFrames.Length;
            }
            sr.sprite = walkFrames[frame % walkFrames.Length];
        }
    }
}
