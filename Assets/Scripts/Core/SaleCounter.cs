using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 販售桌的櫃台：走到桌前按 E 開「經營商店」面板。
    ///
    /// 位置每幀跟著 RoomLayout.SaleFront() 走 —— 玩家把販售桌搬到別的格子，
    /// 感應點就自動跟過去，不用重建場景。
    ///
    /// ⚠️ 感應半徑刻意壓在 90：店裡的門（SceneDoor）也吃 E，兩個感應圈重疊的話
    ///    「按 E 上架」會同時把人送去別的場景（原專案在花園那道門踩過這個坑）。
    ///    通往城鎮的門在 (11,9)，販售桌預設在 (5,2)，正常擺法不會打架；
    ///    但玩家可以把桌子搬到門邊，所以還是把半徑收小。
    /// </summary>
    public class SaleCounter : MonoBehaviour
    {
        public static SaleCounter Instance { get; private set; }

        public static SaleCounter Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("SaleCounter").AddComponent<SaleCounter>();
        }

        const float InteractRange = 90f;

        Transform player;
        GameObject hint;

        void Awake() { Instance = this; }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;
            BuildHint();
        }

        void Update()
        {
            if (player == null) return;

            var spot = RoomLayout.SaleFront();
            if (spot == null) { if (hint != null) hint.SetActive(false); return; }

            transform.position = new Vector3(spot.Value.x, spot.Value.y, 0f);

            bool near = Vector2.Distance(player.position, spot.Value) <= InteractRange;
            if (hint != null) hint.SetActive(near && !UIState.ModalOpen);

            if (near && !UIState.ModalOpen && Input.GetKeyDown(KeyCode.E))
                UI.ShopManagePanel.Ensure().Open();
        }

        void BuildHint()
        {
            hint = new GameObject("hint");
            hint.transform.SetParent(transform, false);
            hint.transform.localPosition = new Vector3(0f, 54f, 0f);

            var tm = hint.AddComponent<TextMesh>();
            tm.text = "按 E 經營商店";
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
}
