using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 畫面左上角常駐的金幣與店鋪名聲。
    ///
    /// 名聲會影響來客速度與人數，所以放在玩家隨時看得到的地方 ——
    /// 「好好經營 → 店更熱鬧」這條回饋要看得見才有意義。
    ///
    /// 由 PlayerController 每個場景喚起（跟下排背包 HUD、時鐘同一批），
    /// 走到哪都看得到，不用逐場景擺 UI。
    ///
    /// ⚠️ 叫 CornerHud 而不是 Hud —— UnityEngine 沒有同名的東西，但專案裡已經有
    ///    InventoryHud / ClockHud，統一用 XxxHud 的命名比較好認。
    /// </summary>
    public class CornerHud : MonoBehaviour
    {
        public static CornerHud Instance { get; private set; }

        public static CornerHud Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("CornerHud");
            DontDestroyOnLoad(go);
            return go.AddComponent<CornerHud>();
        }

        UIDocument doc;
        Label goldLabel, repLabel;
        VisualElement barFill;
        int lastGold = int.MinValue, lastPoints = int.MinValue;
        bool built;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 5;          // 同時鐘：在面板之下、遊戲畫面之上
            if (doc.panelSettings == null)
            {
                Debug.LogError("[CornerHud] 找不到 Resources/ui/UIPanelSettings");
                return;
            }
            Build();
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        void Build()
        {
            var root = doc.rootVisualElement;
            if (root == null) return;
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            root.pickingMode = PickingMode.Ignore;
            CjkFont.Apply(root);

            var box = new VisualElement();
            box.AddToClassList("hud-corner");
            box.pickingMode = PickingMode.Ignore;
            root.Add(box);

            goldLabel = new Label();
            goldLabel.AddToClassList("hud-gold");
            box.Add(goldLabel);

            repLabel = new Label();
            repLabel.AddToClassList("hud-rep");
            box.Add(repLabel);

            var bar = new VisualElement();
            bar.AddToClassList("hud-bar");
            box.Add(bar);

            barFill = new VisualElement();
            barFill.AddToClassList("hud-bar-fill");
            bar.Add(barFill);

            built = true;
            Refresh();
        }

        void Update()
        {
            if (!built) return;
            // 數字沒變就不動 UI（每幀重設文字會讓 UI Toolkit 一直重排）
            if (Wallet.Gold != lastGold || Reputation.Points != lastPoints) Refresh();
        }

        void Refresh()
        {
            lastGold = Wallet.Gold;
            lastPoints = Reputation.Points;

            goldLabel.text = $"{lastGold} 金";
            repLabel.text = Reputation.IsMax
                ? $"名聲 Lv.{Reputation.Level} {Reputation.Title}（滿）"
                : $"名聲 Lv.{Reputation.Level} {Reputation.Title}　{lastPoints}/{Reputation.NextNeed}";

            barFill.style.width = Length.Percent(Reputation.Progress * 100f);
        }
    }
}
