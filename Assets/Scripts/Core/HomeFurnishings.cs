using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 家裡（藥水室）擺出來的家具／燈／裝飾／地毯的**畫面**：照 <see cref="HomeLayout"/> 生物件、登記碰撞、排序、夜色。
    /// 由 BrewRoom.BuildSvgRoom 在房間原本的家具登記完、貓生出來之前呼叫 <see cref="Build"/>（開關 <see cref="HomeArrange.Enabled"/>）。
    ///
    ///   · 物件：FurnishingVisual.Create(id, 落腳點, flip, 這裡, FurnitureLight.Mode.NightOnly) —— 店裡同一支工廠；
    ///     燈在家裡是「天黑才亮」，光暈比店裡大一圈、多一塊地上的暖光（FurnitureLight 的 NightOnly 模式）。
    ///   · 夜色：工廠不上色 —— 這裡在天黑時把 "art" 乘 BrewRoomLayout.NightTint（同房間原本的家具）；
    ///     會發光的（燈、星光花櫃）只壓一點（LampNightLift）（同房間的蠟燭不乘夜色的道理：光源本身不該暗掉）。
    ///   · 碰撞：會擋路的（吃格子的家具）登記到 Obstacles，類別 <see cref="Category"/>；每次重畫先清掉再整批登記
    ///     （Obstacles.Version 會變 → 貓的格子自己重建）。
    ///   · 排序：HomePlacement.AssignOrders 插進房間原本那條序列；<see cref="SortBoxes"/> 給 BrewRoom.PlayerOrder（女巫、貓）一起比。
    ///   · 擺下去的地方剛好有人：女巫／貓站的位置被新的碰撞蓋到 → 挪到最近、走得到的空位（不會卡在家具裡）。
    ///   · 進房間時驗存檔：逐件照規則（HomePlacement.Check，含可達性）驗，不合法的退回托盤（房間或規則改過的舊存檔不會壞、不會擋路）。
    /// </summary>
    public class HomeFurnishings : MonoBehaviour
    {
        public const string Category = "home_furnishing";

        public static HomeFurnishings Instance { get; private set; }

        /// <summary>給 BrewRoom.PlayerOrder 的排序盒子（站著的東西；地毯不列）。</summary>
        public struct SortEntry
        {
            public float U0, U1, V0, V1;
            public Rect Rect;
            public int Order;
        }

        public static readonly List<SortEntry> SortBoxes = new();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { SortBoxes.Clear(); Instance = null; }

        /// <summary>
        /// 會發光的東西（燈、星光花櫃）夜裡只壓暗一點：夜色往白色拉回這麼多（0＝跟一般家具一樣暗、1＝完全不暗）。
        /// 房間原本的蠟燭、燭台完全不乘夜色；燈還有燈柱、燈罩，全亮會像貼上去的 → 留一點夜色。tools/check_home_place.py 讀這個值。
        /// </summary>
        public const float LampNightLift = 0.75f;

        static Color LampNightTint => Color.Lerp(BrewRoomLayout.NightTint, Color.white, LampNightLift);

        readonly List<GameObject> gos = new();
        readonly List<HomeShape> shapes = new();
        int[] orders = new int[0];
        bool wasNight;
        Transform player;

        /// <summary>第 i 件的物件（跟 HomeLayout 的第 i 件同一個順序）。</summary>
        public GameObject GoAt(int i) => i >= 0 && i < gos.Count ? gos[i] : null;
        public HomeShape ShapeAt(int i) => shapes[i];
        public int Count => gos.Count;
        public IReadOnlyList<HomeShape> Shapes => shapes;

        public static HomeFurnishings Build(Transform parent)
        {
            if (Instance != null) return Instance;
            var go = new GameObject("HomeFurnishings");
            go.transform.SetParent(parent, false);
            var h = go.AddComponent<HomeFurnishings>();
            Instance = h;
            h.ValidateSaved();
            h.Rebuild();
            return h;
        }

        void Awake() { Instance = this; }

        void OnDestroy()
        {
            if (Instance == this) { Instance = null; SortBoxes.Clear(); }
        }

        /// <summary>存檔裡的位置逐件驗（照存檔順序累加），不合法的退回托盤。</summary>
        void ValidateSaved()
        {
            int n = HomeLayout.Count;
            if (n == 0) return;
            var keep = new bool[n];
            var ok = new List<HomeShape>();
            for (int i = 0; i < n; i++)
            {
                var p = HomeLayout.At(i);
                if (p == null || GameArt.FurnishingArt(p.id) == null) continue;    // 沒有圖：不擺（退回托盤）
                var s = HomePlacement.Shape(p.id, p.Pos, p.flip);
                if (HomePlacement.Check(s, ok) != HomeBlock.Ok) continue;
                keep[i] = true;
                ok.Add(s);
            }
            int dropped = HomeLayout.KeepOnly(keep);
            if (dropped > 0)
                Debug.Log($"[HomeFurnishings] 家裡有 {dropped} 件東西的位置已經不能擺（房間或規則改過），退回托盤");
        }

        /// <summary>
        /// 照 HomeLayout 全部重畫：物件、排序、碰撞、夜色，然後檢查女巫和貓有沒有被蓋到。
        /// ⚠️ Destroy 是延遲的 —— 舊物件先 SetActive(false)，同一幀新舊才不會疊在一起。
        /// </summary>
        public void Rebuild()
        {
            foreach (var g in gos) if (g != null) { g.SetActive(false); Destroy(g); }
            gos.Clear();
            shapes.Clear();

            int n = HomeLayout.Count;
            for (int i = 0; i < n; i++)
            {
                var p = HomeLayout.At(i);
                shapes.Add(HomePlacement.Shape(p.id, p.Pos, p.flip));
            }
            orders = new int[n];
            HomePlacement.AssignOrders(shapes, orders);

            SortBoxes.Clear();
            Obstacles.ClearRegistered(Category);
            for (int i = 0; i < n; i++)
            {
                var p = HomeLayout.At(i);
                var go = FurnishingVisual.Create(p.id, p.Pos, p.flip, transform, FurnitureLight.Mode.NightOnly);
                if (go == null) go = new GameObject($"missing-{p.id}");    // 沒圖也佔一個位子，索引才對得上
                go.transform.SetParent(transform, true);
                gos.Add(go);
                var art = FurnishingVisual.ArtOf(go);
                if (art != null) art.sortingOrder = orders[i];

                var s = shapes[i];
                if (!s.Flat)
                    SortBoxes.Add(new SortEntry { U0 = s.U0, U1 = s.U1, V0 = s.V0, V1 = s.V1, Rect = s.Art, Order = orders[i] });
                if (s.Blocks && s.Solid != null) Obstacles.AddPoly($"home-{p.id}", s.Solid, Category);
            }

            wasNight = TimeSystem.IsNight;
            ApplyTint();
            Unstick();
        }

        /// <summary>會擋路的碰撞多邊形（可達性、挪人用）。skip＝不算哪一件（拖曳中那件）。</summary>
        public List<Vector2[]> Solids(int skip = -1)
        {
            var list = new List<Vector2[]>();
            for (int i = 0; i < shapes.Count; i++)
                if (i != skip && shapes[i].Blocks && shapes[i].Solid != null) list.Add(shapes[i].Solid);
            return list;
        }

        /// <summary>除了 skip 之外的其他件（規則檢查的 others）。</summary>
        public List<HomeShape> Others(int skip)
        {
            var list = new List<HomeShape>(shapes.Count);
            for (int i = 0; i < shapes.Count; i++) if (i != skip) list.Add(shapes[i]);
            return list;
        }

        /// <summary>女巫或貓被新擺的東西蓋到了 → 挪到最近、走得到的空位。</summary>
        void Unstick()
        {
            if (player == null)
            {
                var p = GameObject.Find("Player");
                player = p != null ? p.transform : null;
            }
            var solids = Solids();
            if (player != null && solids.Count > 0)
            {
                Vector2 at = player.position;
                if (!Obstacles.IsFree(at))
                {
                    var to = HomePlacement.NearestReachable(at, HomePlacement.PlayerR, solids);
                    player.position = new Vector3(to.x, to.y, player.position.z);
                }
            }
            var cat = RoomCat.Live;
            if (cat != null)
            {
                Vector2 c = cat.transform.position;
                bool stuck = !(Obstacles.InWalk(c) && Obstacles.IsFree(c, RoomCat.Radius));
                cat.OnRoomChanged(stuck && (c - RoomCat.CatBed).sqrMagnitude > 4f
                    ? HomePlacement.NearestReachable(c, HomePlacement.CatR, solids)
                    : (Vector2?)null);
            }
        }

        void Update()
        {
            if (TimeSystem.IsNight != wasNight)
            {
                wasNight = TimeSystem.IsNight;
                ApplyTint();
            }
        }

        /// <summary>第 i 件平常該乘的顏色（白天白色、夜晚夜色；會發光的只壓一點）。</summary>
        public Color BaseTint(int i)
        {
            if (!TimeSystem.IsNight || i < 0 || i >= shapes.Count) return Color.white;
            return Furnishings.LightOf(shapes[i].Id).HasValue ? LampNightTint : BrewRoomLayout.NightTint;
        }

        /// <summary>夜色重套一遍（拖曳結束、日夜切換時）。</summary>
        public void ApplyTint()
        {
            for (int i = 0; i < gos.Count; i++)
            {
                var art = FurnishingVisual.ArtOf(gos[i]);
                if (art != null) art.color = BaseTint(i);
            }
        }

        /// <summary>第 i 件原本的 order（拖曳放回去時還原）。</summary>
        public int OrderAt(int i) => i >= 0 && i < orders.Length ? orders[i] : 0;
    }
}
