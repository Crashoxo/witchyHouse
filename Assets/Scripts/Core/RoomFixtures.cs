using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 「走近按 E」的簡單互動點基底：床、倉庫木箱、衣櫃都是同一個模式 ——
    /// 進範圍就冒提示，按 E 做一件事。
    ///
    /// ⚠️ 各互動點的感應半徑要彼此拉開。原專案的註解特別提過：藥水室的木箱、鍋爐、
    ///    出口的感應圈若重疊，一顆 E 會同時觸發兩件事（例如想開倉庫卻被門送去別的場景）。
    ///    木箱擺 (-360,-125)、鍋爐 (59,-135)、出口 (0,-330)，彼此都超過 410px。
    /// </summary>
    public abstract class InteractPoint : MonoBehaviour
    {
        public float interactRange = 150f;
        public string hintText = "按 E";

        protected Transform player;
        GameObject hint;

        protected virtual void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;
            BuildHint();
        }

        void Update()
        {
            bool near = player != null
                        && Vector2.Distance(player.position, transform.position) <= interactRange;
            bool usable = near && !UIState.ModalOpen;
            if (hint != null) hint.SetActive(usable);
            if (usable && Input.GetKeyDown(KeyCode.E)) Activate();
        }

        protected abstract void Activate();

        void BuildHint()
        {
            hint = new GameObject("hint");
            hint.transform.SetParent(transform, false);
            hint.transform.localPosition = new Vector3(0f, 70f, 0f);

            var tm = hint.AddComponent<TextMesh>();
            tm.text = hintText;
            tm.fontSize = 36;
            tm.characterSize = 4.5f;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.color = new Color32(255, 244, 214, 255);

            var font = UI.CjkFont.Get();
            if (font != null)
            {
                tm.font = font;
                hint.GetComponent<MeshRenderer>().material = font.material;
            }
            hint.GetComponent<MeshRenderer>().sortingOrder = 9400;
            hint.SetActive(false);
        }
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
        protected override void Activate() => UI.BagPanel.Ensure().OpenStorage();
    }

    /// <summary>
    /// 衣櫃：藥水室左邊那座雕花木櫃。按 E 開衣櫃面板換造型。
    /// 物件本身沒有圖（櫃子是背景畫好的），只是個隱形觸發 —— 同倉庫木箱、床的作法。
    /// </summary>
    public class Wardrobe : InteractPoint
    {
        protected override void Activate() => UI.WardrobePanel.Ensure().Open();
    }

    /// <summary>
    /// 床：按 E 睡覺。白天睡 → 跳到當晚 20:00；晚上睡 → 跳到隔天 06:00。
    /// </summary>
    public class Bed : InteractPoint
    {
        protected override void Activate()
        {
            // 過場自己會推進時間（畫面全黑之後才動，玩家看不到跳動）
            UI.SleepOverlay.Ensure().Play();
        }

    }
}
