using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 最小的循環幀動畫：照 fps 換 SpriteRenderer 的圖。藥水室的貓（甩尾巴、抖耳朵）、壁爐的火用它。
    ///
    /// sequence 不是 null 時照它的順序播（例如貓大部分時間停在第 0 幀：{0,0,0,1,1,0,0,2,0}）。
    /// 起始相位 phase 讓好幾個同樣的動畫不要同步跳。
    /// 鍋爐**不**用這個 —— 它只在熬煮時播，由 BrewCauldron 自己控制。
    /// </summary>
    [RequireComponent(typeof(SpriteRenderer))]
    public class FrameAnim : MonoBehaviour
    {
        public Sprite[] frames = System.Array.Empty<Sprite>();
        public float fps = 4f;
        public int[] sequence;
        public float phase;

        SpriteRenderer sr;
        int shown = -1;

        void Awake() { sr = GetComponent<SpriteRenderer>(); }

        void Update()
        {
            if (frames.Length == 0 || fps <= 0f) return;
            int n = sequence != null && sequence.Length > 0 ? sequence.Length : frames.Length;
            int step = Mathf.FloorToInt(Time.time * fps + phase) % n;
            int i = sequence != null && sequence.Length > 0 ? sequence[step] : step;
            i = Mathf.Clamp(i, 0, frames.Length - 1);
            if (i == shown) return;
            shown = i;
            if (frames[i] != null) sr.sprite = frames[i];
        }
    }
}
