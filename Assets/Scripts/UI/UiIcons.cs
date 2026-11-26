using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 依名稱取 UI 圖示（tools/gen_ui_icons.py 畫的 8-bit 圖，放在 Resources/ui/icons8/）。
    ///
    /// 為什麼有這支：使用者回饋「解釋擺放東西不用要字，用圖文的方式」—— 佈置模式的提示列、
    /// 物件頭上的標籤、Toast 都改成「鍵帽＋象形圖」，這裡集中載圖與做 UI Toolkit 的圖示元素。
    ///
    /// 名稱就是檔名（key_r、mouse_drag、blk_door…），清單與用途見 gen_ui_icons.py 的 ICONS。
    ///
    /// ⚠️ 缺圖時**不丟例外**：Get 回 null（只警告一次），Element 照樣回一個同尺寸的空元素，
    ///    版面不會亂、遊戲不會停。
    /// ⚠️ Sprite.Create 出來的物件離開 Play 時會被 Unity 收掉（變成 fake null），快取裡的要重新驗；
    ///    關掉 Domain Reload 時靜態快取會留著 → 一律用 <c>s != null</c>（Unity 的比較）判斷要不要重載。
    /// </summary>
    public static class UiIcons
    {
        const string Folder = "ui/icons8/";

        /// <summary>邏輯格高度（24 格）—— 圖都是 24 格高，寬度依圖（Esc 是 34 格寬）。</summary>
        public const float LogicalH = 24f;

        static readonly Dictionary<string, Sprite> cache = new();
        static readonly HashSet<string> missing = new();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { cache.Clear(); missing.Clear(); }

        /// <summary>取圖；沒有這張回 null（只在第一次警告）。</summary>
        public static Sprite Get(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            if (cache.TryGetValue(name, out var s) && s != null) return s;
            if (missing.Contains(name)) return null;

            var t = Resources.Load<Texture2D>(Folder + name);
            if (t == null)
            {
                missing.Add(name);
                Debug.LogWarning($"[UiIcons] 找不到 Resources/{Folder}{name}（跑 tools/gen_ui_icons.py）");
                return null;
            }
            s = SheetSlicer.Whole(t);
            cache[name] = s;
            return s;
        }

        /// <summary>寬高比（缺圖當 1）。</summary>
        public static float Aspect(Sprite s) => s != null && s.rect.height > 0f ? s.rect.width / s.rect.height : 1f;

        /// <summary>
        /// 一個顯示圖示的 VisualElement（不吃滑鼠）。<paramref name="height"/> 是畫面 px，寬度照圖的比例。
        /// </summary>
        public static VisualElement Element(string name, float height, string cls = null)
        {
            var el = new VisualElement { pickingMode = PickingMode.Ignore };
            el.AddToClassList("ui-icon");
            if (cls != null) el.AddToClassList(cls);
            Set(el, name, height);
            return el;
        }

        /// <summary>換掉既有元素的圖（例如基準角換了，提示列那顆圖跟著換）。</summary>
        public static void Set(VisualElement el, string name, float height)
        {
            var sp = Get(name);
            el.style.height = height;
            el.style.width = height * Aspect(sp);
            el.style.backgroundImage = sp != null ? new StyleBackground(sp) : new StyleBackground(StyleKeyword.None);
        }

        /// <summary>用任意 Sprite（例如商品圖、家具圖）做一個同樣排版的元素。</summary>
        public static VisualElement Element(Sprite sp, float height, string cls = null)
        {
            var el = new VisualElement { pickingMode = PickingMode.Ignore };
            el.AddToClassList("ui-icon");
            if (cls != null) el.AddToClassList(cls);
            el.style.height = height;
            el.style.width = height * Aspect(sp);
            if (sp != null) el.style.backgroundImage = new StyleBackground(sp);
            return el;
        }
    }
}
