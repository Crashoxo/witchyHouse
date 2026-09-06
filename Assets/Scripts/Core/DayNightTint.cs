using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 戶外天色色板（森林／城鎮／糖果鎮用）。
    ///
    /// 房間（藥水室）是「一張完整背景圖」，所以 BrewRoom 直接換白天/夜晚兩張；但森林
    /// 和城鎮是一堆物件（樹、路面、噴泉、路燈…）拼的，逐一出圖不切實際。這裡改用一層
    /// 蓋滿畫面的半透明色板，顏色與濃度依 TimeSystem 連續變化，就得到
    /// **白天 → 黃昏 → 夜晚 → 拂曉** 的平滑天色，中間色都是免費的、隨時可調。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版是在 Canvas 底下、World 正上方插一個 Graphics 節點（靠 siblingIndex
    /// 卡在「世界之上、HUD 之下」）。Unity 這邊改成**掛在攝影機底下的一張 Sprite**：
    ///   - 跟著攝影機走，永遠蓋滿畫面，不用管視窗尺寸
    ///   - UI Toolkit 的 HUD 本來就畫在所有世界物件之上，所以「在 HUD 之下」是免費的，
    ///     不需要再去喬 siblingIndex
    /// 色板不吃輸入（Sprite 沒有 Collider），玩家照常走動、點地面移動。
    /// </summary>
    public class DayNightTint : MonoBehaviour
    {
        public static DayNightTint Instance { get; private set; }

        public static DayNightTint Ensure()
        {
            if (Instance != null) return Instance;
            var cam = Camera.main;
            if (cam == null) { Debug.LogWarning("[DayNightTint] 找不到主攝影機"); return null; }
            var go = new GameObject("DayNightTint");
            go.transform.SetParent(cam.transform, false);
            return go.AddComponent<DayNightTint>();
        }

        /// <summary>
        /// 天色關鍵幀：[當日時數 6..26, R, G, B, alpha]。相鄰幀之間線性內插。
        /// alpha=0 的那幾幀顏色不影響畫面（全透明），純粹當「白天」錨點。
        /// **要調天色改這裡就好。**
        /// </summary>
        static readonly float[][] Keys =
        {
            new[] {  6.0f,  30f,  45f, 100f, 0.42f },   // 06:00 拂曉：冷藍微光（剛醒）
            new[] {  8.0f, 255f, 240f, 200f, 0.00f },   // 08:00 天亮：全透明
            new[] { 16.5f, 255f, 240f, 200f, 0.00f },   // 16:30 白天：全透明
            new[] { 18.0f, 240f, 120f,  40f, 0.22f },   // 18:00 黃昏：暖橘（時鐘此時換月亮）
            new[] { 19.5f, 110f,  70f, 120f, 0.38f },   // 19:30 暮色：偏紫
            new[] { 21.0f,  25f,  35f,  90f, 0.50f },   // 21:00 入夜：深藍
            new[] { 26.0f,  18f,  26f,  72f, 0.55f },   // 02:00 深夜（昏倒前最暗）
        };

        SpriteRenderer sr;
        Camera cam;

        void Awake()
        {
            Instance = this;
            cam = GetComponentInParent<Camera>();
            sr = gameObject.AddComponent<SpriteRenderer>();
            sr.sprite = WhitePixel();
            sr.drawMode = SpriteDrawMode.Sliced;
            // 蓋在所有世界物件之上（YSort 用的是 -y，最多到幾千，兩萬綽綽有餘），
            // 但仍在 UI Toolkit 的 HUD 之下。
            sr.sortingOrder = 20000;
            transform.localPosition = new Vector3(0f, 0f, 1f);   // 在攝影機前方一點
            Resize();
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        void Resize()
        {
            if (cam == null) return;
            // 放大 1.4 倍，避免視窗長寬比變動時露出邊
            float h = cam.orthographicSize * 2f * 1.4f;
            sr.size = new Vector2(h * cam.aspect, h);
        }

        void LateUpdate()
        {
            Resize();

            var s = TimeSystem.SeasonDef;
            var c = Sample(TimeSystem.TodHours, s.DawnShift, s.DuskShift);
            sr.color = c;
            // 全透明時直接關掉 renderer，省一次 overdraw
            sr.enabled = c.a > 0.002f;
        }

        /// <summary>
        /// 關鍵幀的時刻依季節挪動：dawn 挪「天亮」那一幀（冬天亮得晚）、dusk 挪傍晚到入夜
        /// 那幾幀（冬天黑得早、夏天黑得晚）。第一幀（06:00 拂曉）與最後一幀（02:00 最暗）
        /// 不動，挪動幅度也刻意小於幀距，所以時間序永遠遞增、插值不會壞掉。
        /// </summary>
        static float KeyTime(int i, float dawn, float dusk)
        {
            float t = Keys[i][0];
            if (i == 1) return t + dawn;                 // 08:00 天亮
            if (i >= 3 && i <= 5) return t + dusk;       // 18:00 / 19:30 / 21:00
            return t;
        }

        /// <summary>在 Keys 上依當日時數線性內插出顏色（時刻先套季節偏移）。</summary>
        static Color Sample(float h, float dawn, float dusk)
        {
            Color Of(float[] k) => new(k[1] / 255f, k[2] / 255f, k[3] / 255f, k[4]);

            if (h <= Keys[0][0]) return Of(Keys[0]);
            var last = Keys[Keys.Length - 1];
            if (h >= last[0]) return Of(last);

            for (int i = 0; i < Keys.Length - 1; i++)
            {
                float at = KeyTime(i, dawn, dusk), bt = KeyTime(i + 1, dawn, dusk);
                if (h < at || h > bt) continue;
                float t = (h - at) / Mathf.Max(0.001f, bt - at);
                return Color.Lerp(Of(Keys[i]), Of(Keys[i + 1]), t);
            }
            return Of(last);
        }

        static Sprite white;

        /// <summary>純白 1px 圖（用 Sliced 撐開當色板）。</summary>
        static Sprite WhitePixel()
        {
            if (white != null) return white;
            var tex = new Texture2D(4, 4, TextureFormat.RGBA32, false);
            for (int y = 0; y < 4; y++)
                for (int x = 0; x < 4; x++) tex.SetPixel(x, y, Color.white);
            tex.Apply();
            white = Sprite.Create(tex, new Rect(0, 0, 4, 4), new Vector2(0.5f, 0.5f), 1f,
                                  0, SpriteMeshType.FullRect, new Vector4(1, 1, 1, 1));
            return white;
        }
    }
}
