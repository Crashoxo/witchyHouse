using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 「往上飄、淡出、自己消失」的小特效元件。採集的星星與材料圖示都用它。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版是兩條 tween 疊在一起：
    ///     tween(n).by(dur, { position: ... }).start();
    ///     tween(op).delay(dur*0.35).to(dur*0.65, { opacity: 0 }).call(() => n.destroy()).start();
    ///
    /// Unity 沒有內建 tween。與其為了這個引一整套 DOTween，不如讓特效物件**自己動**——
    /// 生出來就掛這個元件，它自己位移、自己淡出、時間到自己 Destroy。
    /// 沒有中央的 tween 管理器要維護，物件被銷毀時也不會留下懸空的動畫。
    /// </summary>
    public class FloatAway : MonoBehaviour
    {
        Vector3 from, delta;
        float dur, fadeStart, fadeDur, t;
        SpriteRenderer[] sprites;
        TextMesh[] texts;
        Color[] spriteColors;
        Color[] textColors;

        /// <summary>
        /// 開始飄。
        /// </summary>
        /// <param name="move">整段位移</param>
        /// <param name="duration">位移總時間</param>
        /// <param name="fadeDelayRatio">淡出從總時間的幾成開始（0.35 ＝ 前 35% 不淡）</param>
        public void Begin(Vector3 move, float duration, float fadeDelayRatio = 0.45f)
        {
            from = transform.position;
            delta = move;
            dur = Mathf.Max(0.01f, duration);
            fadeStart = dur * fadeDelayRatio;
            fadeDur = Mathf.Max(0.01f, dur - fadeStart);

            sprites = GetComponentsInChildren<SpriteRenderer>();
            texts = GetComponentsInChildren<TextMesh>();
            spriteColors = new Color[sprites.Length];
            for (int i = 0; i < sprites.Length; i++) spriteColors[i] = sprites[i].color;
            textColors = new Color[texts.Length];
            for (int i = 0; i < texts.Length; i++) textColors[i] = texts[i].color;
        }

        void Update()
        {
            t += Time.deltaTime;
            float k = Mathf.Clamp01(t / dur);
            // 緩出：一開始快、後面慢，比等速自然
            float ease = 1f - (1f - k) * (1f - k);
            transform.position = from + delta * ease;

            float a = t <= fadeStart ? 1f : 1f - Mathf.Clamp01((t - fadeStart) / fadeDur);
            for (int i = 0; i < sprites.Length; i++)
            {
                var c = spriteColors[i]; c.a *= a; sprites[i].color = c;
            }
            for (int i = 0; i < texts.Length; i++)
            {
                var c = textColors[i]; c.a *= a; texts[i].color = c;
            }

            if (t >= dur) Destroy(gameObject);
        }
    }
}
