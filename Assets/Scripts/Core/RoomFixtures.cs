using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 「走近按 E」的簡單互動點基底：床、倉庫木箱、衣櫃、城鎮的商店都是同一個模式 ——
    /// 進範圍就冒提示，按 E 做一件事。
    ///
    /// 2026-11-28 起提示與按 E 都交給共用的互動系統（<see cref="Interactable"/>／<see cref="Interact"/>）：
    /// 頭上是 [E 鍵帽][動作圖]（<see cref="HintIcon"/>），範圍重疊時只有最近的那個會冒提示、吃 E。
    /// <see cref="hintText"/> 只在 InteractHint.Enabled＝false（退回舊的文字提示）時用。
    /// </summary>
    public abstract class InteractPoint : MonoBehaviour
    {
        public float interactRange = 150f;
        public string hintText = "按 E";
        /// <summary>動作圖（icons8 的名字；空字串＝用子類別的預設 <see cref="DefaultIcon"/>）。</summary>
        public string hintIcon = "";
        /// <summary>動作圖直接給一張圖（優先於 hintIcon；例如花店用花的道具圖）。</summary>
        public Sprite hintSprite;
        /// <summary>提示底邊放哪（世界座標；null ＝ 互動點往上 70，跟以前的文字一樣高 —— 這些點本身是隱形的）。</summary>
        public System.Func<Vector3> hintAnchor;

        protected Transform player;
        protected Interactable interactable;

        protected virtual string DefaultIcon => "act_done";

        protected virtual void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;
            interactable = Interactable.Attach(gameObject, interactRange, Activate, Look);
            interactable.anchor = hintAnchor;
        }

        protected virtual HintLook Look()
        {
            var icon = hintSprite != null ? hintSprite : HintIcons.Ui(string.IsNullOrEmpty(hintIcon) ? DefaultIcon : hintIcon);
            return HintLook.E(icon, hintText);
        }

        protected abstract void Activate();
    }

    /// <summary>
    /// 通用互動點：按 E 執行指定的動作。城鎮那幾間商店（雜貨鋪、花店）都用它 ——
    /// 建築本身是背景圖，只是在門口補一個隱形觸發。
    /// </summary>
    public class ActionPoint : InteractPoint
    {
        /// <summary>按 E 時要做什麼（生成後直接指派）。</summary>
        public System.Action onActivate;

        protected override void Activate() => onActivate?.Invoke();
    }

    /// <summary>房間左邊背景畫好的那口木箱 ＝ 倉庫。按 E 開背包的倉庫模式。</summary>
    public class StorageCabinet : InteractPoint
    {
        protected override string DefaultIcon => "act_chest";
        protected override void Activate() => UI.BagPanel.Ensure().OpenStorage();
    }

    /// <summary>
    /// 衣櫃：藥水室左邊那座雕花木櫃。按 E 開衣櫃面板換造型。
    /// 物件本身沒有圖（櫃子是背景畫好的），只是個隱形觸發 —— 同倉庫木箱、床的作法。
    /// </summary>
    public class Wardrobe : InteractPoint
    {
        protected override string DefaultIcon => "act_wardrobe";
        protected override void Activate() => UI.WardrobePanel.Ensure().Open();
    }

    /// <summary>
    /// 床：按 E 睡覺。白天睡 → 跳到當晚 20:00；晚上睡 → 跳到隔天 06:00。
    /// </summary>
    public class Bed : InteractPoint
    {
        protected override string DefaultIcon => "act_sleep";
        protected override void Activate()
        {
            // 過場自己會推進時間（畫面全黑之後才動，玩家看不到跳動）
            UI.SleepOverlay.Ensure().Play();
        }

    }
}
