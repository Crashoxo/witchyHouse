using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 家具燈的光暈（店裡、家裡共用）：掛在家具根物件底下的一張柔和放射狀光暈，輕微閃爍。
    ///
    /// ⚠️ 名字不叫 LampGlow —— 那支是城鎮路燈（掃場景找路燈、單例），這支是「每盞燈自己一個」的小元件。
    ///
    /// 兩種模式：
    ///   <see cref="Mode.Shop"/>      店裡沒有夜色色板：白天也有一點暖光（Strength × <see cref="ShopDay"/>），
    ///                                傍晚漸亮、晚上全亮。
    ///   <see cref="Mode.NightOnly"/> 家裡（藥水室）：白天看不到、天黑才亮（跟 BrewRoom 的蠟燭光暈一樣，
    ///                                家具本身在夜裡乘 NightTint，光暈畫在最上面不乘）。
    /// 排序預設 8000（同 BrewRoom 的光暈：蓋在所有家具與人物之上，在 DayNightTint 20000 之下）。
    /// </summary>
    public class FurnitureLight : MonoBehaviour
    {
        public enum Mode { Shop, NightOnly }

        /// <summary>店裡白天的亮度比例（傍晚以後 1）。</summary>
        public const float ShopDay = 0.45f;
        public const int DefaultOrder = 8000;

        // ── 家裡（NightOnly）加強（2026-11-28 第二階段）──
        //   藥水室晚上本身就有壁爐、蠟燭一圈圈的暖光（shell-night＋BrewRoom 的光暈），店裡那個大小的光暈擺進去幾乎看不出來是燈。
        //   所以家裡的燈：光暈半徑 ×HomeRadiusK、亮度 ×HomeStrengthK（上限 HomeMaxAlpha），
        //   再多一塊**地上的暖光**（壓扁的橢圓，排在地毯之上、影子之下）——「燈照亮了腳邊的地板」最能讀成光源。
        //   數值是照 tools/check_home_place.py 的夜晚合成圖調的。
        public const float HomeRadiusK = 1.7f;
        public const float HomeStrengthK = 1.6f;
        public const float HomeMaxAlpha = 0.92f;
        /// <summary>地上暖光的半寬 ＝ 光暈半徑 × 這個（高度再減半，等距的圓）。</summary>
        public const float PoolRadiusK = 2.4f;
        /// <summary>地上暖光最亮處的 alpha ＝ Strength × 這個。</summary>
        public const float PoolAlphaK = 0.95f;
        /// <summary>地上暖光的排序：自己擺的地毯（-9000）之上、人物影子（-8500）之下。</summary>
        public const int PoolOrder = -8900;

        SpriteRenderer sr;
        LightSpec spec;
        Mode mode;
        float seed;
        bool pool;          // 這個是「地上的暖光」（家裡的燈才有）

        /// <summary>
        /// 在 host 底下加一個光暈。localOffset＝相對 host 原點（落腳點）的位置（已經照翻面鏡像好）。
        /// ⚠️ host 的第一個 SpriteRenderer 子物件必須是家具的圖（佈置模式的 HitTest／Tint 拿第一個）——
        ///    所以要在 "art" 之後才加。
        /// </summary>
        public static FurnitureLight Attach(GameObject host, Vector2 localOffset, LightSpec spec, Mode mode,
                                            int sortingOrder = DefaultOrder)
        {
            var go = new GameObject("light");
            go.transform.SetParent(host.transform, false);
            go.transform.localPosition = new Vector3(localOffset.x, localOffset.y, 0f);
            float radius = mode == Mode.NightOnly ? spec.Radius * HomeRadiusK : spec.Radius;
            float k = radius * 2f / GlowSize;
            go.transform.localScale = new Vector3(k, k, 1f);
            var l = go.AddComponent<FurnitureLight>();
            l.sr = go.AddComponent<SpriteRenderer>();
            l.sr.sprite = GlowSprite();
            l.sr.sortingOrder = sortingOrder;
            l.spec = spec;
            l.mode = mode;
            l.seed = Mathf.Abs(localOffset.x * 0.37f + host.transform.position.x * 0.013f + host.transform.position.y * 0.029f) % 6.28f;
            l.Apply();

            // 家裡：腳邊地板一塊暖光（一件家具只放一塊 —— 三叉燭台有三個光點）
            if (mode == Mode.NightOnly && host.transform.Find("pool") == null)
            {
                var pg = new GameObject("pool");
                pg.transform.SetParent(host.transform, false);
                pg.transform.localPosition = new Vector3(0f, 2f, 0f);
                float pr = spec.Radius * PoolRadiusK;
                pg.transform.localScale = new Vector3(pr * 2f / GlowSize, pr / GlowSize, 1f);
                var p = pg.AddComponent<FurnitureLight>();
                p.sr = pg.AddComponent<SpriteRenderer>();
                p.sr.sprite = GlowSprite();
                p.sr.sortingOrder = PoolOrder;
                p.spec = spec;
                p.mode = mode;
                p.pool = true;
                p.seed = l.seed;
                p.Apply();
            }
            return l;
        }

        void Update() => Apply();

        void Apply()
        {
            if (sr == null) return;
            float h = TimeSystem.TodHours;
            float on = mode == Mode.Shop ? Mathf.Lerp(ShopDay, 1f, Evening(h)) : (TimeSystem.IsNight ? 1f : 0f);
            if (on <= 0.001f) { if (sr.enabled) sr.enabled = false; return; }
            if (!sr.enabled) sr.enabled = true;
            float t = Time.time;
            // 兩個不同頻率的正弦疊起來（同 BrewRoom 的燭火），不配置記憶體
            float f = 1f - spec.Flicker * (0.5f + 0.3f * Mathf.Sin(t * 7.3f + seed) + 0.2f * Mathf.Sin(t * 12.9f + seed * 2.1f));
            var c = (Color)spec.Color;
            float a = spec.Strength;
            if (mode == Mode.NightOnly) a = pool ? spec.Strength * PoolAlphaK : Mathf.Min(HomeMaxAlpha, spec.Strength * HomeStrengthK);
            c.a = a * on * f;
            sr.color = c;
        }

        /// <summary>傍晚漸亮（17:30→19:30）、整夜全亮、清晨 6～7 點漸暗；白天 0。同 LampGlow.LampOn。</summary>
        static float Evening(float h)
        {
            if (h >= 19.5f) return 1f;
            if (h >= 17.5f) return (h - 17.5f) / 2f;
            if (h <= 6f) return 1f;
            if (h <= 7f) return 7f - h;
            return 0f;
        }

        const int GlowSize = 128;
        static Sprite glowSprite;

        /// <summary>柔和放射狀光暈（白色＋alpha，顏色由 SpriteRenderer.color 給；同 gen_brew_room8.glow_image 的衰減）。</summary>
        public static Sprite GlowSprite()
        {
            if (glowSprite != null) return glowSprite;
            var tex = new Texture2D(GlowSize, GlowSize, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            float c = (GlowSize - 1) / 2f;
            var px = new Color32[GlowSize * GlowSize];
            for (int y = 0; y < GlowSize; y++)
                for (int x = 0; x < GlowSize; x++)
                {
                    float d = Mathf.Clamp01(Vector2.Distance(new Vector2(x, y), new Vector2(c, c)) / (GlowSize / 2f));
                    float a = (1f - d) * (1f - d) * (1f - d * 0.15f);
                    px[y * GlowSize + x] = new Color32(255, 255, 255, (byte)Mathf.RoundToInt(255f * Mathf.Clamp01(a)));
                }
            tex.SetPixels32(px);
            tex.Apply();
            glowSprite = Sprite.Create(tex, new Rect(0, 0, GlowSize, GlowSize), new Vector2(0.5f, 0.5f), 1f);
            return glowSprite;
        }
    }
}
