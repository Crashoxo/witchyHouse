using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 城鎮路燈的夜間發光。
    ///
    /// 天色色板（DayNightTint）是整片蓋在世界之上把場景壓暗，所以「發光」必須畫在
    /// 色板**之上**才不會被夜色吃掉 —— 這是這支存在的唯一理由，不然直接在燈的圖上
    /// 疊個光暈就好了。
    ///
    /// 濃度依時間：傍晚漸亮 → 整夜全亮 → 清晨熄滅 → 白天全暗。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版要在 Canvas 底下插一層 GlowLayer、用 siblingIndex 卡在「色板之上、HUD 之下」，
    /// 而且因為路燈會隨鏡頭捲動，每幀都得把光暈的世界座標換算回那層的本地座標。
    ///
    /// Unity 這邊光暈直接生成在**路燈自己底下**當子物件 —— 位置永遠跟著燈走，不用每幀對位。
    /// 「畫在色板之上」則靠 sortingOrder（色板 20000，光暈 20100），也不用管 HUD ——
    /// UI Toolkit 的 HUD 本來就畫在所有世界物件之上。
    /// </summary>
    public class LampGlow : MonoBehaviour
    {
        public static LampGlow Instance { get; private set; }

        public static LampGlow Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("LampGlow").AddComponent<LampGlow>();
        }

        /// <summary>
        /// 各種路燈的光暈設定：Match＝物件名（用 Contains 比對）、
        /// OffY＝燈頭相對物件原點的高度、Radius＝光暈半徑。
        /// </summary>
        static readonly (string Match, float OffX, float OffY, float Radius)[] Lamps =
        {
            ("lamp-post",  0f, 118f, 40f),
            ("lamp-small", 0f, 74f,  30f),
            ("fence-lamp", 0f, 58f,  34f),
        };

        static readonly Color32 GlowColor = new(255, 208, 120, 255);
        /// <summary>深夜最亮時的濃度。</summary>
        const float MaxOpacity = 0.5f;

        readonly List<SpriteRenderer> glows = new();
        float lastFactor = -1f;

        void Awake() { Instance = this; }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start()
        {
            // 掃全場景找路燈。名字來自 TownLayout 的圖檔名（lamp-post / lamp-small / fence-lamp）
            foreach (var sr in FindObjectsByType<SpriteRenderer>(FindObjectsSortMode.None))
            {
                var go = sr.gameObject;
                foreach (var cfg in Lamps)
                {
                    if (!go.name.Contains(cfg.Match)) continue;

                    var gn = new GameObject("glow");
                    gn.transform.SetParent(go.transform, false);
                    gn.transform.localPosition = new Vector3(cfg.OffX, cfg.OffY, 0f);
                    // 光暈貼圖是 128px 方形 → 縮放＝半徑/64
                    float k = cfg.Radius / 64f * 2f;
                    gn.transform.localScale = new Vector3(k, k, 1f);

                    var gsr = gn.AddComponent<SpriteRenderer>();
                    gsr.sprite = GlowSprite();
                    gsr.color = new Color32(GlowColor.r, GlowColor.g, GlowColor.b, 0);
                    // ⚠️ 一定要大於 DayNightTint 的 20000，不然光暈會被夜色蓋掉
                    gsr.sortingOrder = 20100;
                    glows.Add(gsr);
                    break;
                }
            }

            if (glows.Count == 0) Debug.Log("[LampGlow] 這個場景沒有路燈");
        }

        void Update()
        {
            float factor = LampOn(TimeSystem.TodHours);
            if (Mathf.Abs(factor - lastFactor) <= 0.004f) return;   // 沒明顯變化就不動
            lastFactor = factor;

            byte a = (byte)Mathf.RoundToInt(255f * MaxOpacity * factor);
            foreach (var g in glows)
                if (g != null) g.color = new Color32(GlowColor.r, GlowColor.g, GlowColor.b, a);
        }

        /// <summary>依當日時數算路燈亮度（0..1）：傍晚漸亮、整夜全亮、清晨熄滅、白天全暗。</summary>
        static float LampOn(float h)
        {
            if (h >= 19.5f) return 1f;                  // 19:30–02:00 全亮
            if (h >= 17.5f) return (h - 17.5f) / 2f;    // 17:30–19:30 漸亮
            if (h <= 7.0f) return (7.0f - h) * 0.6f;    // 06:00–07:00 清晨殘留漸滅
            return 0f;                                  // 白天全暗
        }

        static Sprite glowSprite;

        /// <summary>柔和的放射狀光暈（程式生成一次，之後共用）。</summary>
        static Sprite GlowSprite()
        {
            if (glowSprite != null) return glowSprite;
            const int N = 128;
            var tex = new Texture2D(N, N, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            float c = (N - 1) / 2f;
            for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    float d = Vector2.Distance(new Vector2(x, y), new Vector2(c, c)) / c;
                    float a = Mathf.Clamp01(1f - d);
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, a * a * 0.9f));
                }
            tex.Apply();
            glowSprite = Sprite.Create(tex, new Rect(0, 0, N, N), new Vector2(0.5f, 0.5f), 1f);
            return glowSprite;
        }
    }
}
