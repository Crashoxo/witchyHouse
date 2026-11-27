using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 藥水室（女巫的房間）：日夜背景、鍋爐、床、倉庫木箱、衣櫃、回店裡的門。
    /// 由 PlayerController 進 brew 場景時呼叫 Ensure()。
    ///
    /// 兩個版本，用 <see cref="UseSvgRoom"/> 切：
    ///   true  ── SVG 重畫的房間（tools/gen_brew_room.py）：房間殼＋一件件獨立的家具，照 Data.BrewRoomLayout 擺；
    ///            家具照前後關係遮住女巫、有碰撞（Obstacles 的凸多邊形）、女巫只能走在地板多邊形裡；
    ///            夜晚換房間殼、家具乘夜色、蠟燭／壁爐／鍋爐火／水晶球亮起光暈。
    ///   false ── 舊房間：整張背景圖（rooms/brew-room-day/night）＋舊鍋爐，互動點照原場景座標，沒有碰撞。
    ///
    /// ⚠️ 互動點彼此要拉開：一顆 E 只能觸發一件事（兩個感應圈重疊時 Unity 不保證誰先跑）。
    ///    SVG 房間的距離與「同時在兩個範圍內的可走位置」由 tools/gen_brew_room.py 離線檢查（目前全部為無）；
    ///    舊房間是木箱 (-360,-125)、鍋爐 (59,-135)、出口 (0,-330) 互相都超過 410px。
    /// </summary>
    public class BrewRoom : MonoBehaviour
    {
        /// <summary>
        /// 開關：true ＝ SVG 重畫的房間；false ＝ 退回舊的整張背景圖與原座標（舊圖與舊鍋爐都還在，沒刪）。
        /// 改這裡就好，GameArt / PlayerController 都看它。
        /// </summary>
        public static readonly bool UseSvgRoom = true;

        /// <summary>
        /// 開關（UseSvgRoom 開著才有用）：true ＝ 細畫像素版（Resources/rooms/brew8/，tools/gen_brew_room8.py）；
        /// false ＝ SVG 版（rooms/brew/）。兩組圖同檔名、同尺寸、同樞紐，配置表／碰撞／互動點完全共用；
        /// 細畫版缺哪張就逐張退回 rooms/brew/（例如貓 cat-0..2 沒有重畫）。GameArt.BrewTex 看它。
        /// </summary>
        public static readonly bool UsePixelRoom = true;

        public static BrewRoom Instance { get; private set; }

        public static BrewRoom Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("BrewRoom").AddComponent<BrewRoom>();
        }

        // ── 舊房間：原場景量到的位置 ──
        static readonly Vector2 CauldronPos = new(59f, -135f);
        static readonly Vector2 BedPos = new(319f, 179f);
        static readonly Vector2 ExitPos = new(0f, -330f);
        /// <summary>背景左邊畫好的那口木箱＝倉庫。</summary>
        static readonly Vector2 ChestPos = new(-360f, -125f);
        /// <summary>同一面牆再往上那座雕花木櫃＝衣櫃。離木箱 320px，兩個 E 不會打架。</summary>
        static readonly Vector2 WardrobePos = new(-505f, 160f);

        /// <summary>
        /// 舊鍋爐圖的縮放。
        /// ⚠️ 原圖是 224×343，但 Cocos 場景裡的 UITransform 是 123×189 ——
        ///    也就是它**一直是被縮到 0.55 顯示的**。照原尺寸擺會大將近一倍。
        ///    （SVG 房間的鍋爐是照新尺寸畫的，1:1 不縮放。）
        /// </summary>
        const float CauldronScale = 123f / 224f;   // ≈ 0.549

        // 光暈最暗與最亮之間的閃爍幅度（燭火、爐火）
        const float FlickerAmount = 0.12f;

        SpriteRenderer bg;
        bool wasNight;

        // SVG 房間：夜晚要乘色的家具、光暈
        readonly List<SpriteRenderer> tinted = new();
        readonly List<(SpriteRenderer Sr, float Alpha, bool Flicker, float Seed)> glows = new();
        BrewCauldron cauldron;

        void Awake() { Instance = this; GameArt.Preload(); }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start()
        {
            GameArt.OnReady(Build);
        }

        void Build()
        {
            // 背景（日夜兩張）：舊房間是整張圖，SVG 房間是牆＋地板的房間殼
            var go = new GameObject("RoomArt");
            go.transform.SetParent(transform);
            go.transform.position = Vector3.zero;
            bg = go.AddComponent<SpriteRenderer>();
            bg.sortingOrder = -10000;

            if (UseSvgRoom) BuildSvgRoom();
            else BuildLegacyRoom();

            wasNight = !TimeSystem.IsNight;      // 逼 Update 第一幀就套一次
            ApplyDayNight();
        }

        // ──────────── 舊房間 ────────────

        void BuildLegacyRoom()
        {
            // 鍋爐
            // ⚠️ Cocos 那邊鍋爐的錨點是 (0.5, 0)＝腳底，Unity 的 Sprite 樞紐在正中心，
            //    所以要把圖往上推半個身高，物件的 position 才是「站在地上的那一點」。
            //    同時要套 CauldronScale，不然會大將近一倍（見上面的說明）。
            var c = new GameObject("Cauldron");
            c.transform.SetParent(transform);
            c.transform.position = new Vector3(CauldronPos.x, CauldronPos.y, 0f);
            c.AddComponent<BrewCauldron>();      // 預設 artScale 就是 CauldronScale

            AddBed(BedPos, 140f);
            AddWardrobe(WardrobePos, 130f);      // 木箱 150、衣櫃 130，相距 320px 才不會搶同一顆 E
            AddChest(ChestPos, 150f);
            AddExit(ExitPos, 200f, 70f);
        }

        // ──────────── SVG 房間 ────────────

        void BuildSvgRoom()
        {
            var art = new GameObject("Pieces").transform;
            art.SetParent(transform, false);

            foreach (var p in BrewRoomLayout.Pieces)
            {
                // 原本只會眨眼的裝飾貓：活貓（RoomCat）開著、而且載得到貓的圖時不擺，改由 RoomCat 自己走來走去
                if (p.Name == "cat" && RoomCat.Enabled && RoomCat.ArtReady) continue;
                var frames = GameArt.BrewFrames(p);
                if (p.Name == "cauldron")
                {
                    // 鍋爐：沿用 BrewCauldron 的互動與熬煮動畫，只換圖（幀數跟舊圖一樣是 6 幀）
                    var c = new GameObject("Cauldron");
                    c.transform.SetParent(transform);
                    c.transform.position = new Vector3(p.X, p.Y, 0f);
                    cauldron = c.AddComponent<BrewCauldron>();
                    cauldron.interactRange = BrewRoomLayout.CauldronRange;
                    cauldron.UseRoomArt(frames, p.Order);
                    RegisterShape(p);
                    continue;
                }

                var go = new GameObject(p.Name);
                go.transform.SetParent(art, false);
                go.transform.position = new Vector3(p.X, p.Y, 0f);   // 樞紐在落腳點（GameArt 照表設的）
                var sr = go.AddComponent<SpriteRenderer>();
                sr.sprite = frames.Length > 0 ? frames[0] : null;
                sr.sortingOrder = p.Order;
                if (frames.Length > 1 && p.Fps > 0f)
                {
                    var anim = go.AddComponent<FrameAnim>();
                    anim.frames = frames;
                    anim.fps = p.Fps;
                    anim.sequence = p.Seq;
                    anim.phase = Mathf.Abs(p.X * 0.013f) % 1f;
                }
                if (p.Tint) tinted.Add(sr);
                RegisterShape(p);
            }

            // 夜晚的光暈（蠟燭、壁爐、鍋爐的火、水晶球）：畫在所有家具與女巫之上
            var glowSprite = GameArt.BrewGlow;
            if (glowSprite != null)
            {
                var gRoot = new GameObject("Glows").transform;
                gRoot.SetParent(transform, false);
                int k = 0;
                foreach (var g in BrewRoomLayout.Glows)
                {
                    var go = new GameObject("glow");
                    go.transform.SetParent(gRoot, false);
                    go.transform.position = new Vector3(g.X, g.Y, 0f);
                    float sc = g.Radius * 2f / BrewRoomLayout.GlowSize;
                    go.transform.localScale = new Vector3(sc, sc, 1f);
                    var sr = go.AddComponent<SpriteRenderer>();
                    sr.sprite = glowSprite;
                    sr.sortingOrder = 8000;
                    float a = BrewRoomLayout.GlowAlpha * g.Strength;
                    var col = BrewRoomLayout.GlowColor;
                    col.a = a;
                    sr.color = col;
                    glows.Add((sr, a, g.Flicker, k++ * 1.7f));
                }
            }

            AddBed(BrewRoomLayout.BedAt, BrewRoomLayout.BedRange);
            AddWardrobe(BrewRoomLayout.WardrobeAt, BrewRoomLayout.WardrobeRange);
            AddChest(BrewRoomLayout.ChestAt, BrewRoomLayout.ChestRange);
            AddExit(BrewRoomLayout.ExitAt, BrewRoomLayout.ExitRange, BrewRoomLayout.ExitAuto);

            // 自己擺的家具／燈／裝飾（HomeLayout）＋R 佈置：要排在房間家具登記之後（驗存檔要量碰撞）、貓之前（貓一出生就繞著它們走）
            if (HomeArrange.Enabled)
            {
                HomeFurnishings.Build(transform);
                HomeArrange.Ensure(transform);
            }

            // 活貓：要排在家具登記（RegisterShape）與互動點之後 —— 牠找路看 Obstacles，摸牠的優先順序看那些互動點
            if (RoomCat.Enabled) RoomCat.Spawn(transform);
        }

        /// <summary>家具的落地範圍交給 Obstacles（凸多邊形或等距圓＝橢圓）。</summary>
        static void RegisterShape(in BrewPiece p)
        {
            if (p.Shape == BrewShape.Poly) Obstacles.AddPoly(p.Name, p.Poly);
            else if (p.Shape == BrewShape.Ellipse)
                Obstacles.AddEllipse(p.Name, new Vector2(p.Cx, p.Cy), new Vector2(p.Hx, p.Hy));
        }

        /// <summary>
        /// 女巫在藥水室的排序（PlayerController.LateUpdate 每幀問）。
        ///
        /// 等距的長家具（床、煉金台）沒辦法用單一個 y 排對：站在床尾前面時她的腳 y 可能比床的前角還高。
        /// 所以改成：只看畫面上跟她重疊的家具，用地板 uv 判斷前後 ——
        ///   她在家具「看得到的那兩面」（+u 面、+v 面）外側 ＝ 她在前面；在背面那兩面外側 ＝ 她在後面。
        /// 家具彼此的靜態排序是離線排好的（gen_brew_room.py 的拓樸排序，間隔 20），她插在「該在她後面的最大值」之上。
        /// 跟 tools/gen_brew_room.py 的 player_order() 是同一個算法（預覽圖就是用它疊的）。
        /// </summary>
        /// <param name="foot">落腳點（世界座標）</param>
        /// <param name="w">她的圖在世界上的寬（含透明邊）</param>
        /// <param name="h">她的圖在世界上的高</param>
        public static int PlayerOrder(Vector2 foot, float w, float h)
        {
            var uv = BrewRoomLayout.ToUV(foot.x, foot.y);
            // 只用看得到的身體那一塊（女巫的格子左右各有透明邊）
            float x0 = foot.x - w * 0.35f, x1 = foot.x + w * 0.35f, y0 = foot.y, y1 = foot.y + h * 0.9f;
            int lo = int.MinValue, hi = int.MaxValue;
            foreach (var p in BrewRoomLayout.Pieces)
            {
                if (p.Kind != BrewKind.Stand) continue;
                if (x1 <= p.RectXMin || p.RectXMax <= x0 || y1 <= p.RectYMin || p.RectYMax <= y0) continue;
                bool front;
                if (uv.x >= p.U1 || uv.y >= p.V1) front = true;
                else if (uv.x <= p.U0 || uv.y <= p.V0) front = false;
                else front = uv.x + uv.y > (p.U0 + p.U1 + p.V0 + p.V1) * 0.5f;   // 踩進範圍裡（不該發生）：看對角線
                if (front) lo = Mathf.Max(lo, p.Order);
                else hi = Mathf.Min(hi, p.Order);
            }
            // 家裡自己擺的東西（HomeFurnishings；order 都是 4 的倍數，女巫拿 lo+1／hi−1 不會跟它們同號）
            foreach (var q in HomeFurnishings.SortBoxes)
            {
                if (x1 <= q.Rect.xMin || q.Rect.xMax <= x0 || y1 <= q.Rect.yMin || q.Rect.yMax <= y0) continue;
                bool front;
                if (uv.x >= q.U1 || uv.y >= q.V1) front = true;
                else if (uv.x <= q.U0 || uv.y <= q.V0) front = false;
                else front = uv.x + uv.y > (q.U0 + q.U1 + q.V0 + q.V1) * 0.5f;   // 裝飾不擋路，可能站在它的範圍裡
                if (front) lo = Mathf.Max(lo, q.Order);
                else hi = Mathf.Min(hi, q.Order);
            }
            if (lo == int.MinValue && hi == int.MaxValue) return Mathf.RoundToInt(-foot.y);
            if (lo == int.MinValue) return hi - 1;
            return lo + 1;
        }

        // ──────────── 互動點（兩個版本共用）────────────

        void AddBed(Vector2 at, float range)
        {
            var bed = new GameObject("Bed");
            bed.transform.SetParent(transform);
            bed.transform.position = new Vector3(at.x, at.y, 0f);
            var b = bed.AddComponent<Bed>();
            b.hintAnchor = PieceHintAnchor("bed", 100f);   // 四柱床的頂篷很高：提示放在枕頭上方，不要飄到頂篷上去
            b.hintText = "按 E 睡覺";
            b.interactRange = range;
        }

        void AddWardrobe(Vector2 at, float range)
        {
            var wardrobe = new GameObject("Wardrobe");
            wardrobe.transform.SetParent(transform);
            wardrobe.transform.position = new Vector3(at.x, at.y, 0f);
            var w = wardrobe.AddComponent<Wardrobe>();
            w.hintAnchor = PieceHintAnchor("wardrobe");
            w.hintText = "按 E 換衣服";
            w.interactRange = range;
        }

        void AddChest(Vector2 at, float range)
        {
            var chest = new GameObject("StorageChest");
            chest.transform.SetParent(transform);
            chest.transform.position = new Vector3(at.x, at.y, 0f);
            var c = chest.AddComponent<StorageCabinet>();
            c.hintAnchor = PieceHintAnchor("chest");
            c.hintText = "按 E 開倉庫";
            c.interactRange = range;
        }

        /// <summary>
        /// 互動提示放在那件家具的圖的上緣（床、衣櫃、木箱的互動點本身是隱形的，不給的話提示固定在互動點往上 70）。
        /// maxRise：最多比落腳點高多少（四柱床的圖頂是頂篷，太高）。舊房間（UseSvgRoom＝false）沒有配置表 → null（退回 +70）。
        /// </summary>
        static System.Func<Vector3> PieceHintAnchor(string piece, float maxRise = float.MaxValue)
        {
            if (!UseSvgRoom) return null;
            foreach (var p in BrewRoomLayout.Pieces)
                if (p.Name == piece)
                {
                    var at = new Vector3(p.X, Mathf.Min(p.RectYMax, p.Y + maxRise) + 4f, 0f);
                    return () => at;
                }
            return null;
        }

        void AddExit(Vector2 at, float range, float auto)
        {
            var exit = new GameObject("ExitDoor");
            exit.transform.SetParent(transform);
            exit.transform.position = new Vector3(at.x, at.y, 0f);
            var d = exit.AddComponent<SceneDoor>();
            d.targetScene = "shop";
            d.hintText = "回店裡";
            d.interactRange = range;
            d.autoRange = auto;
        }

        // ──────────── 日夜 ────────────

        void Update()
        {
            if (bg == null) return;
            if (TimeSystem.IsNight != wasNight) ApplyDayNight();
            if (wasNight && glows.Count > 0)
            {
                float t = Time.time;
                foreach (var g in glows)
                {
                    if (!g.Flicker || g.Sr == null) continue;
                    // 兩個不同頻率的正弦疊起來，看起來像燭火在晃（不配置記憶體）
                    float f = 1f - FlickerAmount * (0.5f + 0.3f * Mathf.Sin(t * 7.3f + g.Seed) + 0.2f * Mathf.Sin(t * 12.9f + g.Seed * 2.1f));
                    var c = g.Sr.color;
                    c.a = g.Alpha * f;
                    g.Sr.color = c;
                }
            }
        }

        void ApplyDayNight()
        {
            wasNight = TimeSystem.IsNight;
            var sp = GameArt.BrewRoom(wasNight);
            if (sp != null) bg.sprite = sp;
            if (!UseSvgRoom) return;

            var tint = wasNight ? BrewRoomLayout.NightTint : Color.white;
            foreach (var sr in tinted) if (sr != null) sr.color = tint;
            if (cauldron != null) cauldron.SetTint(tint);
            foreach (var g in glows) if (g.Sr != null) g.Sr.gameObject.SetActive(wasNight);
        }
    }
}
