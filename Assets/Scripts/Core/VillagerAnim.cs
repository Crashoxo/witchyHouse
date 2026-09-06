using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 村民走路動畫：把 Resources/villagers/*.png（4 幀 × 3 面向）接到一個物件上。
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

        /// <summary>顯示高度（像素）—— 對話泡要擺在頭頂時用。</summary>
        public float DisplayHeight => height;

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

        void Update()
        {
            if (frames.Length == 0) return;
            if (!moving) { ShowFrame(0); timer = 0f; return; }
            timer += Time.deltaTime;
            ShowFrame(Mathf.FloorToInt(timer * Fps) % frames.Length);
        }

        void LateUpdate()
        {
            // YSort：站得低的畫在前面（同 ForestSceneBuilder 的作法）
            if (sr != null) sr.sortingOrder = Mathf.RoundToInt(-transform.position.y);
        }

        void ApplyDir(int d, bool force = false)
        {
            if (d == dir && !force && frames.Length > 0) return;
            dir = d;
            var f = GameArt.VillagerFrames(villager, d);
            if (f.Length == 0) return;
            frames = f;
            idx = -1;                                    // 換面向 → 強制重畫一次

            var r = f[0].rect;
            height = r.height * scale;
            art.localScale = new Vector3(scale, scale, 1f);
            art.localPosition = new Vector3(0f, height * 0.5f, 0f);   // 腳底錨點：圖往上推半身

            // 腳下的影子（尺寸確定後才叫得準）。這裡的 position 本來就是落腳點 → 不用再補偏移
            ShadowLayer.Follow(transform, r.width * scale);

            ShowFrame(moving ? Mathf.FloorToInt(timer * Fps) % f.Length : 0);
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
