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

        /// <summary>按 E 的感應半徑。public 是給 Obstacles 的可達性自我檢查用（tools/check_shop_walk.py 也照這個值）。</summary>
        public const float InteractRange = 90f;

        Transform player;

        void Awake() { Instance = this; }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;

            // 提示與按 E 交給共用的互動系統（2026-11-28）：頭上 [E][金幣]（以前是「按 E 經營商店」）。
            // 佈置模式中（ShopRoomEditor）Interact 整個暫停，不會冒提示。
            var it = Interactable.Attach(gameObject, InteractRange, () => UI.ShopManagePanel.Ensure().Open(),
                () => HintLook.E(HintIcons.Ui("act_sell"), "按 E 經營商店"));
            it.available = () => RoomLayout.SaleFront() != null;
            it.anchor = () => transform.position + new Vector3(0f, 40f, 0f);
        }

        void Update()
        {
            // 櫃台每幀跟著販售桌搬家（佈置模式會搬桌子）；按 E 由 Interact 處理
            var spot = RoomLayout.SaleFront();
            if (spot != null) transform.position = new Vector3(spot.Value.x, spot.Value.y, 0f);
        }
    }
}
