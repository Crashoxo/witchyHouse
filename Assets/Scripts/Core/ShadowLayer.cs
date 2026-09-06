using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 角色腳下的影子（女巫主角、店裡的顧客、街上的村民、糖果鎮的小動物都用這個）。
    ///
    /// 沒有影子的話，俯視角下角色看起來是「貼」在地上而不是「站」在地上 —— 尤其在
    /// 店裡的木地板與糖果鎮那種高彩度背景上特別明顯。
    ///
    /// 用法：<c>ShadowLayer.Follow(角色的 transform, 角色在畫面上的寬度, 腳底相對 position 的偏移)</c>。
    /// 同一個 transform 重複呼叫＝更新尺寸（美術載好、換面向、換衣服後再叫一次就好）。
    /// 目標被銷毀（顧客離場、換場景）會自動清掉，呼叫端不用收尾。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版用一個 Graphics 每幀重畫全部橢圓，而且**不能**掛成角色的子節點 ——
    /// Cocos 先畫父節點再畫子節點，影子會蓋在角色身上，所以原版在 World 底下另插一層
    /// `Shadows` 並排在 `Props` 之前。
    ///
    /// Unity 的繪製順序看 <c>sortingOrder</c>、跟階層無關，所以那套排序技巧整個不需要：
    /// 影子固定 <see cref="Order"/>，一定畫在地面（-10000）之上、所有角色與道具
    /// （YSort 的 -y，量級只有幾千）之下。夜晚也不用另外處理 —— DayNightTint 的色板
    /// 在 20000，會一起壓暗。
    ///
    /// 幾何也不再每幀重畫：橢圓是**程式生成的一張柔邊圓形貼圖**（生一次共用），
    /// 每個角色一顆 SpriteRenderer，每幀只更新位置（同 PortalGlow 的作法）。
    ///
    /// ⚠️ 影子刻意**不掛成角色的子物件**（Unity 明明可以）：角色的 transform 帶著
    ///    縮放（女巫 <c>WitchScale</c>）而且面向靠 <c>localScale.x</c> 正負翻面，
    ///    掛進去要一路把那些縮放除回來，換衣服/換面向時還得同步。獨立一層便宜得多。
    /// </summary>
    public class ShadowLayer : MonoBehaviour
    {
        public static ShadowLayer Instance { get; private set; }

        /// <summary>地面（-10000）之上、所有角色與道具（YSort 的 -y）之下。
        /// 比傳送點光圈（-9000/-8999）高一點 —— 站在傳送點上時影子要看得見。</summary>
        const int Order = -8500;

        /// <summary>柔和的深色，不用純黑免得太重（同原版）。</summary>
        static readonly Color32 Ink = new(24, 22, 30, 110);

        const float RxRatio = 0.36f;    // 橢圓半寬 ÷ 角色寬
        const float RyRatio = 0.125f;   // 橢圓半高 ÷ 角色寬（壓扁＝俯視角的地面）

        class Caster
        {
            public Transform Target;      // 跟著誰
            public Transform Shadow;      // 影子本體
            public SpriteRenderer Sr;
            public float FootY;           // 腳底相對 Target.position.y 的偏移
            public float Ry;
        }

        readonly List<Caster> casters = new();

        void Awake() { Instance = this; }
        void OnDestroy() { if (Instance == this) Instance = null; }

        /// <summary>取得（或建立）影子層。</summary>
        public static ShadowLayer Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("Shadows").AddComponent<ShadowLayer>();
        }

        /// <summary>
        /// 讓某個角色腳下出現影子。
        /// </summary>
        /// <param name="target">角色的 transform</param>
        /// <param name="width">角色在畫面上的寬度（世界單位＝像素，PPU=1）</param>
        /// <param name="footY">腳底相對 <c>target.position.y</c> 的偏移。
        ///   村民、糖果鎮小動物的 position 本來就是落腳點 → 0（預設）；
        ///   女巫的 Sprite 樞紐在正中心 → 傳 −半個身高。</param>
        public static void Follow(Transform target, float width, float footY = 0f)
        {
            if (target == null || width <= 0f) return;
            Ensure().Add(target, width, footY);
        }

        void Add(Transform target, float width, float footY)
        {
            float rx = Mathf.Max(4f, width * RxRatio);
            float ry = Mathf.Max(2f, width * RyRatio);

            foreach (var c in casters)
            {
                if (c.Target != target) continue;
                Resize(c, rx, ry, footY);
                return;
            }

            var go = new GameObject("shadow");
            go.transform.SetParent(transform);
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = DiscSprite();
            sr.color = Ink;
            sr.sortingOrder = Order;

            var caster = new Caster { Target = target, Shadow = go.transform, Sr = sr };
            Resize(caster, rx, ry, footY);
            Place(caster);
            casters.Add(caster);
        }

        static void Resize(Caster c, float rx, float ry, float footY)
        {
            c.Ry = ry;
            c.FootY = footY;
            // 貼圖是 TexN 見方、PPU=1 → 縮放＝直徑 ÷ TexN
            c.Shadow.localScale = new Vector3(rx * 2f / TexN, ry * 2f / TexN, 1f);
        }

        static void Place(Caster c)
        {
            var p = c.Target.position;
            // 橢圓中心比落腳點高一點點 —— 讓影子的上緣壓在鞋底下方，而不是整個掛在腳前面
            c.Shadow.position = new Vector3(p.x, p.y + c.FootY + c.Ry * 0.6f, 0f);
        }

        /// <summary>用 LateUpdate：角色是在 Update 裡移動的，這裡才讀得到這一幀的位置（不會慢一幀）。</summary>
        void LateUpdate()
        {
            for (int i = casters.Count - 1; i >= 0; i--)
            {
                var c = casters[i];
                // 目標沒了（顧客離場、換場景）→ 連影子一起收掉
                if (c.Target == null)
                {
                    if (c.Shadow != null) Destroy(c.Shadow.gameObject);
                    casters.RemoveAt(i);
                    continue;
                }
                // 角色被暫時關掉（例如過場）時影子也跟著藏起來
                bool on = c.Target.gameObject.activeInHierarchy;
                if (c.Sr.enabled != on) c.Sr.enabled = on;
                if (on) Place(c);
            }
        }

        // ──────────── 貼圖 ────────────

        const int TexN = 64;
        static Sprite discSprite;

        /// <summary>
        /// 柔邊的圓（縮放成扁橢圓來用）。中心實心、外圈淡出 ——
        /// 原版是 Graphics 畫的硬邊橢圓，放大後邊緣會有鋸齒，這裡順手做柔一點。
        /// </summary>
        static Sprite DiscSprite()
        {
            if (discSprite != null) return discSprite;

            var tex = new Texture2D(TexN, TexN, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp,
            };
            const float Solid = 0.62f;                  // 這個半徑內是滿的，之後才淡出
            float mid = (TexN - 1) / 2f;
            var px = new Color[TexN * TexN];
            for (int y = 0; y < TexN; y++)
            {
                for (int x = 0; x < TexN; x++)
                {
                    float dx = (x - mid) / mid, dy = (y - mid) / mid;
                    float d = Mathf.Sqrt(dx * dx + dy * dy);
                    float a = d <= Solid ? 1f
                            : Mathf.Clamp01(1f - (d - Solid) / (1f - Solid));
                    px[y * TexN + x] = new Color(1f, 1f, 1f, a * a);
                }
            }
            tex.SetPixels(px);
            tex.Apply();

            discSprite = Sprite.Create(tex, new Rect(0, 0, TexN, TexN),
                                       new Vector2(0.5f, 0.5f), 1f, 0, SpriteMeshType.FullRect);
            return discSprite;
        }
    }
}
