using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 藥水室（女巫的房間）：日夜背景、鍋爐、床、倉庫木箱、回店裡的門。
    /// 由 PlayerController 進 brew 場景時呼叫 Ensure()。
    ///
    /// ⚠️ 各互動點的座標抄自原場景，彼此距離是刻意拉開的 —— 木箱 (-360,-125)、
    ///    鍋爐 (59,-135)、出口 (0,-330) 互相都超過 410px，一顆 E 才不會同時觸發兩件事。
    /// </summary>
    public class BrewRoom : MonoBehaviour
    {
        public static BrewRoom Instance { get; private set; }

        public static BrewRoom Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("BrewRoom").AddComponent<BrewRoom>();
        }

        // 原場景量到的位置
        static readonly Vector2 CauldronPos = new(59f, -135f);
        static readonly Vector2 BedPos = new(319f, 179f);
        static readonly Vector2 ExitPos = new(0f, -330f);
        /// <summary>背景左邊畫好的那口木箱＝倉庫。</summary>
        static readonly Vector2 ChestPos = new(-360f, -125f);
        /// <summary>同一面牆再往上那座雕花木櫃＝衣櫃。離木箱 320px，兩個 E 不會打架。</summary>
        static readonly Vector2 WardrobePos = new(-505f, 160f);

        /// <summary>
        /// 鍋爐圖的縮放。
        /// ⚠️ 原圖是 224×343，但 Cocos 場景裡的 UITransform 是 123×189 ——
        ///    也就是它**一直是被縮到 0.55 顯示的**。照原尺寸擺會大將近一倍。
        /// </summary>
        const float CauldronScale = 123f / 224f;   // ≈ 0.549

        SpriteRenderer bg;
        bool wasNight;

        void Awake() { Instance = this; GameArt.Preload(); }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start()
        {
            GameArt.OnReady(Build);
        }

        void Build()
        {
            // 背景（日夜兩張）
            var go = new GameObject("RoomArt");
            go.transform.SetParent(transform);
            go.transform.position = Vector3.zero;
            bg = go.AddComponent<SpriteRenderer>();
            bg.sortingOrder = -10000;
            wasNight = !TimeSystem.IsNight;      // 逼 Update 第一幀就套一次
            ApplyBackground();

            // 鍋爐
            // ⚠️ Cocos 那邊鍋爐的錨點是 (0.5, 0)＝腳底，Unity 的 Sprite 樞紐在正中心，
            //    所以要把圖往上推半個身高，物件的 position 才是「站在地上的那一點」。
            //    同時要套 CauldronScale，不然會大將近一倍（見上面的說明）。
            var cauldron = new GameObject("Cauldron");
            cauldron.transform.SetParent(transform);
            cauldron.transform.position = new Vector3(CauldronPos.x, CauldronPos.y, 0f);
            cauldron.AddComponent<BrewCauldron>();

            // 床
            var bed = new GameObject("Bed");
            bed.transform.SetParent(transform);
            bed.transform.position = new Vector3(BedPos.x, BedPos.y, 0f);
            var b = bed.AddComponent<Bed>();
            b.hintText = "按 E 睡覺";
            b.interactRange = 140f;

            // 衣櫃（同一面牆再往上）
            var wardrobe = new GameObject("Wardrobe");
            wardrobe.transform.SetParent(transform);
            wardrobe.transform.position = new Vector3(WardrobePos.x, WardrobePos.y, 0f);
            var w = wardrobe.AddComponent<Wardrobe>();
            w.hintText = "按 E 換衣服";
            w.interactRange = 130f;      // 木箱 150、衣櫃 130，相距 320px 才不會搶同一顆 E

            // 倉庫木箱
            var chest = new GameObject("StorageChest");
            chest.transform.SetParent(transform);
            chest.transform.position = new Vector3(ChestPos.x, ChestPos.y, 0f);
            var c = chest.AddComponent<StorageCabinet>();
            c.hintText = "按 E 開倉庫";
            c.interactRange = 150f;

            // 回店裡的門
            var exit = new GameObject("ExitDoor");
            exit.transform.SetParent(transform);
            exit.transform.position = new Vector3(ExitPos.x, ExitPos.y, 0f);
            var d = exit.AddComponent<SceneDoor>();
            d.targetScene = "shop";
            d.hintText = "回店裡";

        }

        void Update()
        {
            if (bg == null) return;
            if (TimeSystem.IsNight != wasNight) ApplyBackground();
        }

        void ApplyBackground()
        {
            wasNight = TimeSystem.IsNight;
            var sp = GameArt.BrewRoom(wasNight);
            if (sp != null) bg.sprite = sp;
        }
    }
}
