using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 村民走路動畫：把 Resources/villagers8/*.png（8-bit 新圖）或 villagers/*.png（舊圖）
    /// （都是 4 幀 × 3 面向）接到一個物件上。用哪張由 GameArt.UsePixelVillagers 決定。
    /// 店裡的顧客和城鎮街上走動的村民共用這支。
    ///
    /// 用法：生一個空物件 → AddComponent&lt;VillagerAnim&gt;().Init("frog") → 每幀餵
    /// SetMove(dx, dy)（不動就餵 0,0），面向與播放交給它。
    ///
    /// 面向：走路表只有下／側／上三列，側面一律朝左 → 往右走時把 scale.x 取負
    /// （同女巫 CharacterAnimator 的作法）。
    ///
    /// ── 移植註記：腳底錨點 ──────────────────────────────────────
    /// Cocos 版把 UITransform 的錨點設成 (0.5, 0)＝腳底，這樣物件的 position 就是
    /// 「站在地上的那一點」，YSort 才排得對。Unity 的 Sprite 樞紐在正中心（見 SheetSlicer），
    /// 所以這裡讓 SpriteRenderer 掛在一個**子物件**上、往上偏移半個身高 ——
    /// 父物件的 position 依然代表腳底，呼叫端與排序邏輯都跟原版一致。
    /// </summary>
    public class VillagerAnim : MonoBehaviour
    {
        /// <summary>每秒播幾幀（走路循環）。</summary>
        public const float Fps = 8f;

        /// <summary>
        /// 原圖縮到畫面上的比例。**改女巫尺寸（<see cref="GameArt.WitchScale"/>）時要一起動。**
        ///
        /// 怎麼定的：量兩邊圖上**真的畫到東西**的高度（不是格子高，透明邊很大）——
        /// 女巫一格 49×66、可見 58px，×1.6 ＝ 畫面上 93px；
        /// 十一張村民圖平均可見 98px，所以 ×1.0 ＝ 畫面上 **98px**，比女巫高約 5%
        /// （大人比小女巫高一點點，剛好）。
        ///
        /// 試過 0.85（83px、比女巫矮一成）——太小了，看起來不像大人。1.0 是實機挑過的。
        ///
        /// ⚠️ 最早是 1.28（＝舊值 0.8 跟著女巫一起 ×1.6 推出來的），那樣村民 125px、
        ///    比女巫高 34%，站在一起大人像巨人。等比放大只有在兩邊原圖比例一樣時才成立，
        ///    這裡不是（女巫的格子 66px、村民的格子 100px），所以要量出來定。
        ///
        /// 這個常數同時是**店裡顧客**的預設值（`CustomerManager.displayScale`）——
        /// 兩邊是同一批人，本來就該一樣大。只想動其中一邊就改那個欄位。
        ///
        /// ⚠️ 上面量的是**舊圖**。8-bit 新圖（Resources/villagers8，見 GameArt.UsePixelVillagers）
        ///    格子與比例都不同，實際縮放＝這個值 × <see cref="GameArt.VillagerArtScale"/>
        ///    （新圖是原生 1px 像素、×WitchScale＝1.6，像素跟女巫一樣大），所以這裡維持 1.0 不動、舊圖的比例也不會被弄壞。
        /// </summary>
        public const float Scale = 1.0f;

        string villager = "";
        float scale = Scale;
        Transform art;                 // 掛 SpriteRenderer 的子物件（往上偏移半個身高）
        SpriteRenderer sr;
        Sprite[] frames = System.Array.Empty<Sprite>();
        int dir = VillagerDir.Down;
        bool faceRight;
        bool moving;
        float timer;
        int idx = -1;
        float height = 70f;

        float width = 50f;

        /// <summary>顯示高度（像素）—— 對話泡要擺在頭頂時用。</summary>
        public float DisplayHeight => height;
        /// <summary>顯示寬度（像素，含格子的透明邊）—— 店裡的排序（ShopRoomView.PlayerOrder）要用。</summary>
        public float DisplayWidth => width;

        /// <summary>
        /// 排序覆寫：有設的話 LateUpdate 用它的回傳值當 sortingOrder，不再用 -y。
        ///
        /// 為什麼要有：店裡的長貨架是等距斜放的，單純比腳底 y 會在貨架兩端排錯
        /// （人明明站在架子前面卻被架子蓋掉）。女巫在店裡是問 ShopRoomView.PlayerOrder，
        /// 顧客走同一套就設這個（見 CustomerManager.Spawn）。
        /// ⚠️ 只有店裡的顧客設 —— 城鎮的村民（TownFolk）保持 null，行為完全不變。
        /// </summary>
        public System.Func<int> orderOverride;

        /// <summary>指定要演哪位村民。name 取自 GameArt.VillagerNames()。</summary>
        public void Init(string name, float s = Scale)
        {
            villager = name;
            scale = s;

            var go = new GameObject("art");
            art = go.transform;
            art.SetParent(transform, false);
            sr = go.AddComponent<SpriteRenderer>();

            ApplyDir(VillagerDir.Down, true);
            if (frames.Length == 0) GameArt.OnReady(() => { if (this != null) ApplyDir(dir, true); });
        }

        /// <summary>
        /// 餵目前的移動方向（不必正規化；0,0 ＝站著）。
        /// 橫向為主就走側面（往右走翻面），否則依上下決定背面/正面。
        /// </summary>
        public void SetMove(float dx, float dy)
        {
            moving = Mathf.Abs(dx) > 0.001f || Mathf.Abs(dy) > 0.001f;
            if (!moving) return;
            if (Mathf.Abs(dx) >= Mathf.Abs(dy))
            {
                ApplyDir(VillagerDir.Side);
                SetFacing(dx > 0f);
            }
            else
            {
                ApplyDir(dy > 0f ? VillagerDir.Up : VillagerDir.Down);
            }
        }

        /// <summary>站定時要面向哪邊（不播動畫，只換圖）。</summary>
        public void FaceTo(float dx, float dy) { SetMove(dx, dy); moving = false; }

        /// <summary>一直在飄的村民（騎掃帚的魔女）站著時的播放速度：走路表本身就是上下浮＋鬃毛擺，慢一點播。</summary>
        public const float HoverIdleFps = 4f;

        /// <summary>
        /// 走路動畫的播放倍數（1 ＝ <see cref="Fps"/>）。走得比較慢的人（店裡的顧客）調低，腳步才跟得上位移、不會滑步。
        /// 只影響走路，不影響騎掃帚魔女站著飄的速度。
        /// </summary>
        public float FpsScale = 1f;

        void Update()
        {
            if (frames.Length == 0) return;
            if (!moving)
            {
                // 騎掃帚的魔女站著也在飄（GameArt.VillagerHovers）：照樣播，只是慢一點；其他人停在第 0 幀
                if (GameArt.VillagerHovers(villager))
                {
                    timer += Time.deltaTime;
                    ShowFrame(Mathf.FloorToInt(timer * HoverIdleFps) % frames.Length);
                    return;
                }
                ShowFrame(0); timer = 0f; return;
            }
            timer += Time.deltaTime;
            ShowFrame(Mathf.FloorToInt(timer * Fps * FpsScale) % frames.Length);
        }

        void LateUpdate()
        {
            // YSort：站得低的畫在前面（同 ForestSceneBuilder 的作法）；店裡的顧客改問覆寫掛勾
            if (sr != null)
                sr.sortingOrder = orderOverride != null ? orderOverride()
                                                        : Mathf.RoundToInt(-transform.position.y);
        }

        void ApplyDir(int d, bool force = false)
        {
            if (d == dir && !force && frames.Length > 0) return;
            dir = d;
            var f = GameArt.VillagerFrames(villager, d);
            if (f.Length == 0) return;
            frames = f;
            idx = -1;                                    // 換面向 → 強制重畫一次

            // 實際縮放＝呼叫端給的 scale × 這張圖自己的倍數（8-bit 新圖 GameArt.PixelVillagerScale、舊圖 1）。
            // 分開乘是因為 CustomerManager.displayScale 是序列化欄位、場景裡存著舊值 —— 新舊圖的比例差
            // 由 GameArt 依「實際載到哪張圖」決定，切開關或缺圖退回時兩邊都不會變形。
            float k = scale * GameArt.VillagerArtScale(villager);
            var r = f[0].rect;
            height = r.height * k;
            width = r.width * k;
            art.localScale = new Vector3(k, k, 1f);
            // 腳底錨點：圖往上推半個格子高 → 格子底邊＝position。
            // 新圖的鞋底在格子底邊往上 3px（×k，同女巫），跟女巫一樣**不把圖往下拉**（女巫的鞋底也在 position
            // 上方 FootPad×1.6），兩邊站在同一個 y 時腳才對齊；那段落差交給影子的 footY 對準鞋底。
            art.localPosition = new Vector3(0f, height * 0.5f, 0f);

            // 腳下的影子（尺寸確定後才叫得準）：新圖格子兩側透明邊較寬 → 寬度打折，中心對準鞋底
            ShadowLayer.Follow(transform, width * GameArt.VillagerShadowRatio(villager),
                               GameArt.VillagerFootPad(villager) * k);

            ShowFrame(moving ? Mathf.FloorToInt(timer * Fps * FpsScale) % f.Length
                      : GameArt.VillagerHovers(villager) ? Mathf.FloorToInt(timer * HoverIdleFps) % f.Length : 0);
        }

        void SetFacing(bool right)
        {
            if (right == faceRight) return;
            faceRight = right;
            var s = transform.localScale;
            transform.localScale = new Vector3(right ? -Mathf.Abs(s.x) : Mathf.Abs(s.x), s.y, s.z);
        }

        void ShowFrame(int i)
        {
            if (i == idx || sr == null || frames.Length == 0) return;
            idx = i;
            sr.sprite = frames[i];
        }
    }
}
