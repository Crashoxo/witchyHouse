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
    ///
    /// 外觀：像素外觀開著時是一塊深木底座（hud-bar 九宮格）＋米白字，關著時是舊的深色半透明框（HudExtraStyle 的 .toast）。
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

        /// <summary>
        /// 一排圖示（＋最多兩三個字）的提示 —— 佈置模式用（使用者回饋「解釋的文字太多了」）。
        /// <paramref name="icons"/> 是 <see cref="UiIcons"/> 的名稱；缺圖的那顆會留空位，不會壞。
        /// </summary>
        public static void ShowIcons(string[] icons, string text = null, float seconds = 1.8f)
        {
            if ((icons == null || icons.Length == 0) && string.IsNullOrEmpty(text)) return;
            Ensure().SpawnIcons(icons, text, seconds);
        }

        /// <summary>圖示 Toast 裡每顆圖的高度（畫面 px）。</summary>
        const float IconH = 34f;

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
            // 8-bit 外觀（總開關 UiSkin.Enabled）：深木底座＋米白字，跟下排背包列同一塊木頭（Skin8.uss 的 .sk .toast）
            UiSkin.Apply(root);
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

        void SpawnIcons(string[] icons, string text, float seconds)
        {
            if (layer == null) { Debug.Log($"[Toast] {string.Join(" ", icons ?? new string[0])} {text}"); return; }

            var el = new VisualElement();
            el.AddToClassList("toast");
            el.AddToClassList("toast--icons");
            el.pickingMode = PickingMode.Ignore;
            el.style.opacity = 0f;
            if (icons != null)
                foreach (var n in icons) el.Add(UiIcons.Element(n, IconH, "toast-icon"));
            if (!string.IsNullOrEmpty(text))
            {
                var l = new Label(text);
                l.AddToClassList("toast-icon-text");
                l.pickingMode = PickingMode.Ignore;
                el.Add(l);
            }
            layer.Add(el);
            StartCoroutine(Play(el, seconds));
        }

        /// <summary>進場時從下面多少 px 滑上來。</summary>
        const float RiseIn = 12f;
        /// <summary>停留時慢慢往上飄、淡出時再往上飄的距離（合計 18px，同原版）。</summary>
        const float DriftHold = 4f, DriftOut = 14f;

        /// <summary>
        /// 淡入 0.18 秒（同時從下方滑上來，ease-out）→ 停一下（慢慢往上飄一點）→
        /// 淡出 0.32 秒（ease-in，邊淡邊往上飄）。時間節奏同原版，只是把線性換成緩動。
        ///
        /// 位移改用 <c>translate</c>，不再每幀改 <c>top</c> —— translate 不會觸發重新排版，
        /// 改 top 每幀都要重跑整層 layout。
        /// </summary>
        IEnumerator Play(VisualElement el, float seconds)
        {
            const float fadeIn = 0.18f, fadeOut = 0.32f;
            float hold = Mathf.Max(0.2f, seconds - fadeIn - fadeOut);
            float total = fadeIn + hold + fadeOut;
            float t = 0f;

            while (t < total)
            {
                t += Time.unscaledDeltaTime;      // 開著選單時也要能看到提示
                float a, y;
                if (t < fadeIn)
                {
                    float p = EaseOut(t / fadeIn);
                    a = p;
                    y = RiseIn * (1f - p);
                }
                else if (t < fadeIn + hold)
                {
                    a = 1f;
                    y = -DriftHold * ((t - fadeIn) / hold);
                }
                else
                {
                    float q = Mathf.Clamp01((t - fadeIn - hold) / fadeOut);
                    q *= q;                         // ease-in：一開始慢、越後面越快
                    a = 1f - q;
                    y = -DriftHold - DriftOut * q;
                }
                el.style.opacity = Mathf.Clamp01(a);
                el.style.translate = new StyleTranslate(new Translate(0, y));
                yield return null;
            }
            el.RemoveFromHierarchy();
        }

        /// <summary>三次方 ease-out：一開始快、收尾慢。</summary>
        static float EaseOut(float x)
        {
            x = 1f - Mathf.Clamp01(x);
            return 1f - x * x * x;
        }
    }
}
