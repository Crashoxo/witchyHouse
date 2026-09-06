using System;
using System.Collections;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UIElements;

namespace WitchShop.UI
{
    /// <summary>
    /// 場景切換淡入淡出：黑幕淡出 → 載入場景 → 黑幕淡入。
    /// 換場景就呼叫 <c>SceneFade.Go("town")</c> 取代 SceneManager.LoadScene。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版每次都在「目前 Canvas」底下生一層黑幕，換場景後再在新場景生一層 ——
    /// 因為節點會隨場景銷毀。Unity 這邊用 DontDestroyOnLoad 的常駐 UIDocument，
    /// **同一層黑幕跨場景活著**，所以不會有「舊場景的黑幕沒了、新場景的還沒生出來」
    /// 那一幀的閃爍。
    /// </summary>
    public class SceneFade : MonoBehaviour
    {
        static SceneFade instance;

        static SceneFade Ensure()
        {
            if (instance != null) return instance;
            var go = new GameObject("SceneFadeUI");
            DontDestroyOnLoad(go);
            instance = go.AddComponent<SceneFade>();
            return instance;
        }

        /// <summary>正在換場（擋住重複觸發）。</summary>
        public static bool Busy { get; private set; }

        /// <summary>淡出 → 載入場景 → 淡入。dur＝單邊時間（秒）。</summary>
        public static void Go(string sceneName, float dur = 0.3f, Action onArrive = null)
        {
            if (Busy || string.IsNullOrEmpty(sceneName)) return;

            if (!Application.CanStreamedLevelBeLoaded(sceneName))
            {
                Debug.LogWarning($"[SceneFade] 場景「{sceneName}」不在 Build Settings 裡，不換場。" +
                                 "跑一次選單 Witch Shop → 重新登記所有場景。");
                return;
            }

            Ensure().StartCoroutine(Ensure().Run(sceneName, dur, onArrive));
        }

        UIDocument doc;
        VisualElement veil;

        void Awake()
        {
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 100;         // 黑幕要蓋在所有東西之上
            if (doc.panelSettings == null)
            {
                Debug.LogError("[SceneFade] 找不到 Resources/ui/UIPanelSettings");
                return;
            }

            var root = doc.rootVisualElement;
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));

            veil = new VisualElement();
            veil.AddToClassList("fade");
            veil.style.opacity = 0f;
            veil.pickingMode = PickingMode.Ignore;     // 平常不擋操作
            root.Add(veil);
        }

        void OnDestroy() { if (instance == this) instance = null; }

        IEnumerator Run(string sceneName, float dur, Action onArrive)
        {
            Busy = true;
            if (veil != null) veil.pickingMode = PickingMode.Position;   // 換場期間擋操作

            yield return Fade(0f, 1f, dur);

            var op = SceneManager.LoadSceneAsync(sceneName);
            while (op != null && !op.isDone) yield return null;

            // 等一幀讓新場景的 Awake/Start 跑完，畫面才不會在還沒擺好時就亮出來
            yield return null;

            yield return Fade(1f, 0f, dur);

            if (veil != null) veil.pickingMode = PickingMode.Ignore;
            Busy = false;
            onArrive?.Invoke();
        }

        IEnumerator Fade(float from, float to, float dur)
        {
            if (veil == null) yield break;
            float t = 0f;
            dur = Mathf.Max(0.01f, dur);
            while (t < dur)
            {
                t += Time.unscaledDeltaTime;      // 換場時 Time.timeScale 可能被別的東西動過
                veil.style.opacity = Mathf.Lerp(from, to, Mathf.Clamp01(t / dur));
                yield return null;
            }
            veil.style.opacity = to;
        }
    }
}
