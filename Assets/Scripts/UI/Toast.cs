using System.Collections;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 畫面上方冒一行字、飄一下就淡掉的小提示（例如「材料已收進倉庫」）。
    ///
    /// 用法：任何地方 <c>Toast.Show("…")</c> 就好，不用先準備什麼。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版是純 module（不是 Component），因為它「只是生一個節點跑 tween」。
    /// Unity 這邊需要一個 UIDocument 才畫得出 UI Toolkit 的東西，也需要 MonoBehaviour
    /// 才能跑協程做淡入淡出 —— 所以做成一個自動生成的常駐單例，但**對外仍然只有
    /// 一個 static Show()**，呼叫端跟原版一樣簡單。
    /// </summary>
    public class Toast : MonoBehaviour
    {
        static Toast instance;

        static Toast Ensure()
        {
            if (instance != null) return instance;
            var go = new GameObject("ToastUI");
            DontDestroyOnLoad(go);
            instance = go.AddComponent<Toast>();
            return instance;
        }

        /// <summary>冒一行提示。</summary>
        public static void Show(string text, float seconds = 1.8f)
        {
            if (string.IsNullOrEmpty(text)) return;
            Ensure().Spawn(text, seconds);
        }

        UIDocument doc;
        VisualElement layer;

        void Awake()
        {
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 50;          // 疊在所有面板之上
            if (doc.panelSettings == null)
            {
                Debug.LogError("[Toast] 找不到 Resources/ui/UIPanelSettings");
                return;
            }

            var root = doc.rootVisualElement;
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            root.pickingMode = PickingMode.Ignore;      // 提示不擋滑鼠
            CjkFont.Apply(root);

            layer = new VisualElement();
            layer.AddToClassList("toast-layer");
            layer.pickingMode = PickingMode.Ignore;
            root.Add(layer);
        }

        void OnDestroy() { if (instance == this) instance = null; }

        void Spawn(string text, float seconds)
        {
            if (layer == null) { Debug.Log($"[Toast] {text}"); return; }   // UI 沒起來就退回 Console

            var el = new Label(text);
            el.AddToClassList("toast");
            el.pickingMode = PickingMode.Ignore;
            el.style.opacity = 0f;
            layer.Add(el);

            StartCoroutine(Play(el, seconds));
        }

        /// <summary>淡入 0.18 秒 → 停一下 → 淡出 0.32 秒，同時整條往上飄 18px（同原版節奏）。</summary>
        IEnumerator Play(VisualElement el, float seconds)
        {
            const float fadeIn = 0.18f, fadeOut = 0.32f;
            float hold = Mathf.Max(0.2f, seconds - fadeIn - fadeOut);
            float total = fadeIn + hold + fadeOut;
            float t = 0f;

            while (t < total)
            {
                t += Time.unscaledDeltaTime;      // 開著選單時也要能看到提示
                float a = t < fadeIn ? t / fadeIn
                        : t < fadeIn + hold ? 1f
                        : 1f - (t - fadeIn - hold) / fadeOut;
                el.style.opacity = Mathf.Clamp01(a);
                el.style.top = 76f - 18f * Mathf.Clamp01(t / total);
                yield return null;
            }
            el.RemoveFromHierarchy();
        }
    }
}
