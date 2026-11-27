using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 把店裡的東西畫出來：地板底圖 ＋ RoomLayout 裡擺出來的家具 ＋ 擺出來的裝飾。
    ///
    /// 由 PlayerController 進 shop 場景時呼叫 Ensure() —— 不用改場景檔。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// 對應 Cocos 的 DecorRoom.ts（636 行）的**渲染那一半**：
    ///   applyRoomArt / spawnAll / createEntry / syncAll
    ///
    /// 另一半是「佈置模式」（拖曳家具、格線提示、托盤），拆到 ShopRoomEditor.cs ——
    /// 渲染和編輯是兩件事，原版擠在同一個 636 行的檔裡不好找。
    ///
    /// ⚠️ 家具圖的錨點約定是「圖的正下方中央＝佔地前角」，所以跟 VillagerAnim 一樣，
    ///    SpriteRenderer 掛在子物件上往上推半個身高，父物件的 position 才是落地點。
    /// </summary>
    public class ShopRoomView : MonoBehaviour
    {
        public static ShopRoomView Instance { get; private set; }

        public static ShopRoomView Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("ShopRoom");
            return go.AddComponent<ShopRoomView>();
        }

        readonly List<GameObject> spawned = new();

        /// <summary>擺出來的家具：物件 ↔ 存檔裡那一筆。佈置模式要靠它才知道拖的是誰。</summary>
        public readonly List<(GameObject Go, PlacedFurniture Data)> Furnitures = new();
        /// <summary>擺出來的裝飾：物件 ↔ 在 DecorCatalog.PlacedList() 裡的索引。</summary>
        public readonly List<(GameObject Go, int Index)> Decors = new();

        /// <summary>
        /// 女巫排序要用的家具資料（每次 Rebuild 重算）：佔地格、排序值、圖真正畫到東西的範圍。
        /// </summary>
        struct SortPiece
        {
            public int Gx, Gy, W, H;
            public int Order;
            public Rect Art;
        }
        readonly List<SortPiece> sortPieces = new();

        /// <summary>登記到 Obstacles 的類別名（Rebuild 時只清這一類，見 Obstacles.ClearRegistered）。</summary>
        const string ObstacleCategory = "shop_furniture";

        void Awake()
        {
            Instance = this;
            GameArt.Preload();
        }

        /// <summary>
        /// ⚠️ 第一次 Rebuild 一定要在 Start（不能在 Awake）：Rebuild 會把家具登記進 Obstacles，
        ///    而 PlayerController.Awake 在**叫完 ShopRoomView.Ensure() 之後**才呼叫 Obstacles.Begin，
        ///    Begin 會清空所有登記 —— 在 Awake 裡登記會被清掉，店裡就變成家具全都穿得過去。
        ///    （GameArt.OnReady 是同步的、會立刻執行，所以以前放在 Awake 裡就等於在 Awake 裡 Rebuild。）
        /// </summary>
        void Start()
        {
            GameArt.OnReady(() =>
            {
                // 舊存檔裡可能有「已經卡在牆裡」的家具（擺放規則是放的時候才檢查的，
                // 規則改嚴之前存下來的不會自己變好）。要等美術載好才量得出圖的範圍。
                int moved = RoomLayout.RepairPlacements();
                if (moved > 0)
                    UI.Toast.Show($"有 {moved} 件家具卡在牆裡，已經幫你挪回地板上");
                Rebuild();
            });
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        // 庫存變了（上架／下架／顧客買走）只重擺商品，不整間重建（家具、碰撞都沒變）
        void OnEnable() => ShopStock.Changed += OnStockChanged;
        void OnDisable() => ShopStock.Changed -= OnStockChanged;

        void OnStockChanged()
        {
            if (Furnitures.Count == 0) return;     // 還沒 Rebuild 過（美術還沒好）—— Rebuild 時會擺
            SpawnGoods();
        }

        /// <summary>
        /// 整間店重畫一次（買了新家具、佈置完成後叫這個）。
        /// 家具的碰撞也在這裡整批重登記 —— 佈置模式每次放下／翻面／收回都會叫 Rebuild，
        /// 拖曳中途不會叫（只改物件位置），所以不會每幀重建障礙清單。
        /// </summary>
        public void Rebuild()
        {
            // 先關掉再 Destroy（Destroy 延到這一幀結束，不關的話新舊家具會疊一幀）
            foreach (var go in spawned) if (go != null) { go.SetActive(false); Destroy(go); }
            spawned.Clear();
            Furnitures.Clear();
            Decors.Clear();
            FlatDecors.Clear();
            sortPieces.Clear();

            ApplyRoomArt();
            SpawnFurniture();
            SpawnDecor();
            SpawnGoods();
            RegisterObstacles();
        }

        /// <summary>
        /// 每件擺出來的家具登記一個碰撞多邊形：佔地 w×h 格的等距平行四邊形，每邊往內縮
        /// <see cref="ShopRoom.FurnitureInset"/> 格（為什麼要縮、縮多少見那個常數的說明）。
        ///
        /// 裝飾（DecorCatalog）**不擋**：地毯要踩得上去、小盆栽／擺飾通常放在桌上架上，
        /// 而且裝飾是自由座標、沒有佔地格，硬擋只會讓玩家在莫名其妙的地方卡住。
        ///
        /// ⚠️ 佈置完女巫可能正站在新擺的家具裡：Obstacles 的防卡死（往外走、穿入深度變小一律放行）
        ///    對多邊形一樣成立（Pen ＝ R − 有號距離，越往外越小），她走得出來，不用另外把她推開。
        /// </summary>
        void RegisterObstacles()
        {
            Obstacles.ClearRegistered(ObstacleCategory);
            foreach (var (_, p) in Furnitures)
            {
                var (w, h) = p.Size;
                if (w <= 0 || h <= 0) continue;
                Obstacles.AddPoly(p.id, ShopRoom.FootprintPoly(p.gx, p.gy, w, h), ObstacleCategory);
            }
        }

        /// <summary>
        /// 女巫在店裡的排序（PlayerController.LateUpdate 每幀問）。仿 BrewRoom.PlayerOrder。
        ///
        /// 等距的長家具（1×3 的貨架、2×1 的販售桌）沒辦法用單一個 y 排對：站在貨架側面時她的腳 y
        /// 可能比貨架的錨點還低（看起來該在前面）、其實卻在它後面。所以改用格座標判斷：
        ///   她腳底的連續格座標 (fx, fy)，對佔 [gx, gx+w)×[gy, gy+h) 的家具，
        ///   fx ≥ gx+w-0.5 或 fy ≥ gy+h-0.5（在它看得到的 +gx 面或 +gy 面外側）＝ 她在前面；否則在後面。
        ///   （碰撞範圍內縮之後，她的腳可以踩進佔地格左右兩個尖角一點點（銳角那兩個，約 1～2px 深）；
        ///     踩進格子裡時門檻放寬 FurnitureInset —— 那裡就是貼著看得到的那一面，算前面才不會走到尖角時
        ///     被家具突然蓋掉半個身體。前後兩個鈍角被腳底圓整個蓋住，踩不進去。）
        /// 只看畫面上跟她的身體重疊的家具。家具自己的排序（-錨點 y）不動 —— 佈置模式、顧客都依賴它。
        ///
        /// 取值：該在她後面的最大 order ＋2（lo+2）；只有該在她前面的就取最小 order −1（hi-1）；
        /// 都沒有疊到就用 -腳底 y（跟顧客、裝飾同一套）。
        /// ⚠️ 是 +2 不是 +1：架上的商品（SpawnGoods）用「家具 order ＋1」—— 她站在貨架前面時若也是 +1，
        ///    會跟商品同一個 sortingOrder，誰蓋誰不一定（商品會閃到她身上）。+2 保證她蓋在商品上面；
        ///    她在家具後面時取 hi-1，商品（hi+1）自然蓋在她身上，這邊不用改。
        ///    家具的 order 是 -錨點 y，錨點都落在半格（16px）的整數倍上，相鄰兩件至少差 16，+2 不會越過下一件。
        /// ⚠️ 兩邊同時有、而且 lo+2 ≥ hi（家具彼此的 -y 排序跟她的相對位置矛盾，例如她在一件
        ///    錨點很低的長貨架後面、同時在一件錨點較高的家具前面）時，沒有一個值能同時滿足 ——
        ///    **優先保證她正貼著的那件**：取腳底到佔地格距離最近的那件，它要求她在前就取 lo+1、要求在後就取 hi-1。
        ///    離得遠的那件會短暫錯一下，但那件跟她的圖只疊到邊緣，不容易看出來。
        /// </summary>
        /// <param name="foot">落腳點（世界座標）</param>
        /// <param name="w">她的圖在世界上的寬（含透明邊）</param>
        /// <param name="h">她的圖在世界上的高</param>
        public static int PlayerOrder(Vector2 foot, float w, float h)
        {
            int fallback = Mathf.RoundToInt(-foot.y);
            var me = Instance;
            if (me == null || me.sortPieces.Count == 0) return fallback;

            var g = ShopRoom.ToGrid(foot.x, foot.y);
            const float tol = ShopRoom.FurnitureInset;
            // 只用看得到的身體那一塊（女巫的格子左右各有透明邊）—— 跟 BrewRoom.PlayerOrder 同一組比例
            float x0 = foot.x - w * 0.35f, x1 = foot.x + w * 0.35f, y0 = foot.y, y1 = foot.y + h * 0.9f;

            int lo = int.MinValue, hi = int.MaxValue;
            float nearest = float.MaxValue;
            bool nearestFront = false;
            foreach (var p in me.sortPieces)
            {
                var a = p.Art;
                if (x1 <= a.xMin || a.xMax <= x0 || y1 <= a.yMin || a.yMax <= y0) continue;

                float ex = p.Gx + p.W - 0.5f, ey = p.Gy + p.H - 0.5f;   // +gx 面、+gy 面
                bool front = g.x >= ex || g.y >= ey;
                // 腳踩進佔地格裡（只會發生在左右兩個尖角）：離看得到的那一面 tol 以內就算前面。
                // ⚠️ 放寬只能用在「踩進格子裡」這個情況 —— 在格子外的背面（-gx/-gy 側）也放寬的話，
                //    站在貨架右後方靠近右尖角時會被誤判成在前面，直接畫到架子上。
                if (!front && g.x > p.Gx - 0.5f && g.y > p.Gy - 0.5f)
                    front = g.x >= ex - tol || g.y >= ey - tol;
                if (front) lo = Mathf.Max(lo, p.Order);
                else hi = Mathf.Min(hi, p.Order);

                // 腳底到佔地格（格座標矩形）的距離平方 —— 衝突時用來挑「她正貼著的那件」
                float dx = Mathf.Max(0f, Mathf.Max(p.Gx - 0.5f - g.x, g.x - ex));
                float dy = Mathf.Max(0f, Mathf.Max(p.Gy - 0.5f - g.y, g.y - ey));
                float d = dx * dx + dy * dy;
                if (d < nearest) { nearest = d; nearestFront = front; }
            }

            if (lo == int.MinValue && hi == int.MaxValue) return fallback;
            if (lo == int.MinValue) return hi - 1;
            if (hi == int.MaxValue || lo + 2 < hi) return lo + 2;
            return nearestFront ? lo + 2 : hi - 1;   // 矛盾：保住最近的那件
        }

        /// <summary>地板底圖。整張畫好的 960×640，不是一塊塊磚拼的。</summary>
        void ApplyRoomArt()
        {
            var sp = GameArt.ShopRoom;
            if (sp == null) { Debug.LogWarning("[ShopRoomView] 沒有店內底圖 rooms/shop-room"); return; }
            var go = new GameObject("RoomArt");
            go.transform.SetParent(transform);
            go.transform.position = Vector3.zero;
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = -10000;
            spawned.Add(go);
        }

        void SpawnFurniture()
        {
            foreach (var p in RoomLayout.PlacedList())
            {
                var d = Furniture.ById(p.id);
                if (d == null) continue;
                var sp = GameArt.FurnitureArt(d.Id);
                if (sp == null) { Debug.LogWarning($"[ShopRoomView] 沒有家具圖 furniture8/{d.Id}"); continue; }

                // 落地點依基準角＋轉向後的佔地算（見 PlacedFurniture.Size / FurnitureAnchor）
                var front = RoomLayout.AnchorPos(p);
                // 圖＋燈的光暈都由共用工廠生（家裡之後也走同一支）
                var go = FurnishingVisual.Create(d.Id, front, p.flip, null, FurnitureLight.Mode.Shop);
                if (go == null) continue;
                spawned.Add(go);
                Furnitures.Add((go, p));

                // 女巫排序用：order 要跟 MakeGrounded 設的一模一樣（-錨點 y）
                var (w, h) = p.Size;
                if (!RoomLayout.ArtRect(d.Id, front, p.flip, out var art))
                    art = new Rect(front.x - sp.rect.width / 2f, front.y, sp.rect.width, sp.rect.height);
                sortPieces.Add(new SortPiece
                {
                    Gx = p.gx, Gy = p.gy, W = w, H = h,
                    Order = Mathf.RoundToInt(-front.y), Art = art,
                });
            }
        }

        /// <summary>擺出來的裝飾品。</summary>
        void SpawnDecor()
        {
            var list = DecorCatalog.PlacedList();
            for (int i = 0; i < list.Count; i++)
            {
                var placed = list[i];
                var d = Decor.ById(placed.id);
                if (d == null) continue;
                // ⚠️ 裝飾用的是自由座標 (x, y)，不吃家具那套格盤 —— 它們可以擺在桌上、架上。
                //    縮放（細畫版 1、舊圖 DecorDef.Scale）、地毯的排序（壓在最底）都在 FurnishingVisual 裡。
                var dgo = FurnishingVisual.Create(d.Id, new Vector2(placed.x, placed.y), placed.flip, null,
                                                  FurnitureLight.Mode.Shop);
                if (dgo == null) continue;
                spawned.Add(dgo);
                Decors.Add((dgo, i));
                if (d.Flat) FlatDecors.Add(dgo);
            }
        }

        /// <summary>
        /// 平貼地板的裝飾（地毯）。佈置模式點選時排在最後（家具、一般裝飾優先）——
        /// 地毯很大、又壓在家具底下，先試它的話點家具永遠只會抓到地毯。
        /// </summary>
        public readonly HashSet<GameObject> FlatDecors = new();

        // ──────────── 架上的商品 ────────────

        /// <summary>擺在家具上的商品物件（家具的子物件；Rebuild 時跟著家具一起被刪）。</summary>
        readonly List<GameObject> goods = new();

        /// <summary>
        /// 一個陳列位（每次 SpawnGoods 重建）。佈置模式拖商品時靠它畫「可以放的位子」、找最近的落點。
        /// Index ＝ 在那件家具的 SlotSequence 裡的第幾個（畫面順序）＝ ShopDisplay 存的 slot。
        /// </summary>
        public sealed class DisplaySpot
        {
            public PlacedFurniture Furn;
            public GameObject FurnGo;
            public int Index, Row;
            public DisplaySlot Slot;
            /// <summary>擺在這格的商品名（null ＝空位）。</summary>
            public string Occupant;
            /// <summary>位子的底部中心（層板／桌面頂面）世界座標 —— 跟 MakeGood 同一套換算。</summary>
            public Vector2 World => SlotWorld(Furn, Slot);
            /// <summary>位子的中心（標記與「離滑鼠多近」用這個，比底部更像玩家眼中的那一格）。</summary>
            public Vector2 Center => World + new Vector2(0f, Slot.MaxH * 0.5f);
        }

        /// <summary>一種商品這次擺在哪（每次 SpawnGoods 重建）。</summary>
        public sealed class GoodPlacement
        {
            public string Name;
            public PlacedFurniture Furn;
            /// <summary>從第幾個位子開始、佔幾個（畫面順序）。</summary>
            public int Start, Count;
            /// <summary>是不是照玩家指定擺的（false ＝ 自動分配）。</summary>
            public bool Pinned;
            /// <summary>畫出來的商品物件（沒有道具圖的話是空的）。</summary>
            public readonly List<GameObject> Gos = new();
        }

        /// <summary>所有家具上的陳列位（先販售桌、再貨架，同一件家具的位子連在一起、照畫面順序）。</summary>
        public readonly List<DisplaySpot> Spots = new();
        /// <summary>這次擺出來的商品。</summary>
        public readonly List<GoodPlacement> Goods = new();

        /// <summary>一種商品依數量佔幾個相鄰的陳列位：1 件→1、2～4 件→2、5 件以上→3（位子不夠就少擺）。</summary>
        const int GoodsMany = 5, GoodsSome = 2;
        static int SlotsFor(int count) => count >= GoodsMany ? 3 : count >= GoodsSome ? 2 : 1;

        /// <summary>只重擺商品（佈置模式拖完商品、改了指定位置之後叫）—— 家具、碰撞都不動。</summary>
        public void RefreshGoods()
        {
            if (Furnitures.Count == 0) return;
            SpawnGoods();
        }

        /// <summary>
        /// 把上架清單（ShopStock.Listings）擺到家具的陳列位上。兩輪：
        ///   ① **玩家指定過位置的**（ShopDisplay）：那件家具（uid）還擺著、起始位子存在而且還空著才算；
        ///      從起始位子往右連續拿空位，**不跨層**（玩家是把它放在「這一層」上），拿到 SlotsFor 個或碰到
        ///      別人／層尾就停（＝放不下就少擺）。指定失效就掉到第②輪，但指定本身不刪（家具擺回來就恢復）。
        ///   ② 其餘的照原本的自動規則：**先販售桌、再依擺出來的順序的貨架**，從頭找空位連續擺
        ///      （這一輪可以跨層，跟以前一樣），一種商品不拆到兩件家具上；這件家具剩的位子不夠就少擺幾個，
        ///      下一種商品換下一件家具（位子全滿就不擺了 —— 只是「看起來」，賣不賣得掉跟擺不擺出來無關）。
        ///   沒有任何指定時，②的結果跟改版前一模一樣。
        ///
        /// 陳列位是 tools/gen_shop_art.py 跟家具圖一起算出來的（Data/ShopDisplaySlots.cs）：
        /// 相對於家具錨點的偏移＋最大寬高。商品圖等比縮到塞得下，底部中心對在位子上。
        ///
        /// ⚠️ 做成**家具根物件的子物件**：佈置模式拖曳時只移動根物件，商品自然跟著走。
        ///    不掛在 "art" 底下 —— art 翻面時 scale.x 是負的，商品圖會跟著被鏡像（字、瓶標反過來）；
        ///    所以翻面只把位子的 X 取負，商品本身不翻。
        ///    ⚠️ 也因為這樣，商品要排在 "art" **之後**（AddChild 的順序）：ShopRoomEditor 的
        ///    HitTest／Tint 用 GetComponentInChildren&lt;SpriteRenderer&gt;() 找家具的圖，會拿到第一個子物件。
        /// ⚠️ sortingOrder ＝家具的 order ＋1：蓋在自己的家具上、又不會越過下一件家具（相鄰家具至少差 16）。
        ///    女巫站在家具前面時是 order ＋2（見 PlayerOrder），所以商品不會畫到她身上。
        /// ⚠️ 舊的商品先 SetActive(false) 再 Destroy：Destroy 要等這一幀結束才真的刪，不先關掉的話
        ///    舊位置與新位置的商品會同時出現一幀（佈置模式拖完放下時看得到閃一下）。
        /// </summary>
        void SpawnGoods()
        {
            foreach (var g in goods) if (g != null) { g.SetActive(false); Destroy(g); }
            goods.Clear();
            goodsOn.Clear();
            Goods.Clear();
            Spots.Clear();
            if (Furnitures.Count == 0) return;

            // ── 所有陳列位：先販售桌、再其他（貨架），各自保持擺出來的順序 ──
            var order = new List<(GameObject Go, PlacedFurniture Data)>();
            foreach (var f in Furnitures) { var d = Furniture.ById(f.Data.id); if (d != null && d.Sale) order.Add(f); }
            foreach (var f in Furnitures) { var d = Furniture.ById(f.Data.id); if (d != null && !d.Sale) order.Add(f); }

            var spans = new List<(GameObject Go, PlacedFurniture P, int SortOrder, int First, int Count)>();
            foreach (var (go, p) in order)
            {
                if (go == null) continue;
                var art = go.transform.Find("art");
                var artSr = art != null ? art.GetComponent<SpriteRenderer>() : null;
                if (artSr == null || artSr.sprite == null) continue;

                var slots = ShopDisplaySlots.Get(p.id, artSr.sprite.rect.width, artSr.sprite.rect.height);
                if (slots.Length == 0) continue;
                var seq = SlotSequence(slots, p.flip);

                spans.Add((go, p, artSr.sortingOrder + 1, Spots.Count, seq.Count));
                for (int i = 0; i < seq.Count; i++)
                    Spots.Add(new DisplaySpot { Furn = p, FurnGo = go, Index = i, Row = seq[i].Row, Slot = seq[i] });
            }

            var list = ShopStock.Listings();
            var listed = new HashSet<string>();
            foreach (var l in list) listed.Add(l.name);
            ShopDisplay.Prune(listed);           // 已下架的指定順手清掉（正常在 ShopStock.RemoveOne 當下就清了）
            if (list.Count == 0 || spans.Count == 0) return;

            // ── ① 玩家指定的：照 ShopDisplay 的優先順序（最近動過的先擺，兩個搶同一格時玩家手上那個贏）──
            var byName = new Dictionary<string, Listing>();
            foreach (var l in list) byName[l.name] = l;
            var pinnedDone = new HashSet<string>();
            foreach (var e in ShopDisplay.Snapshot())
            {
                if (!byName.TryGetValue(e.name, out var l)) continue;
                int uid = e.uid, slot = e.slot;
                int si = spans.FindIndex(x => x.P.uid == uid);
                if (si < 0 || slot >= spans[si].Count) continue;                  // 家具收起來了／位子不存在 → 第②輪
                var sp0 = spans[si];
                var first = Spots[sp0.First + slot];
                if (first.Occupant != null) continue;                             // 被更優先的指定佔走了 → 第②輪

                int need = SlotsFor(l.count), take = 0;
                for (int j = slot; j < sp0.Count && take < need; j++)
                {
                    var s = Spots[sp0.First + j];
                    if (s.Row != first.Row || s.Occupant != null) break;           // 不跨層、不壓別人
                    take++;
                }
                Place(l, sp0.Go, sp0.P, sp0.SortOrder, sp0.First, slot, take, true);
                pinnedDone.Add(l.name);
            }
            var rest = new List<Listing>();
            foreach (var l in list) if (!pinnedDone.Contains(l.name)) rest.Add(l);    // 保持上架順序

            // ── ② 其餘自動補空位（沒有指定時跟改版前同一個結果）──
            int li = 0;
            foreach (var sp0 in spans)
            {
                if (li >= rest.Count) break;
                int k = 0;
                while (li < rest.Count)
                {
                    while (k < sp0.Count && Spots[sp0.First + k].Occupant != null) k++;
                    if (k >= sp0.Count) break;                                     // 這件滿了 → 下一件
                    var l = rest[li++];
                    int need = SlotsFor(l.count), take = 0;
                    while (take < need && k + take < sp0.Count && Spots[sp0.First + k + take].Occupant == null) take++;
                    Place(l, sp0.Go, sp0.P, sp0.SortOrder, sp0.First, k, take, false);
                    k += take;
                }
            }
        }

        /// <summary>把一種商品擺到某件家具的 [start, start+take) 位子上，並登記到 Spots／Goods／goodsOn。</summary>
        void Place(Listing l, GameObject furnGo, PlacedFurniture p, int sortOrder, int first, int start, int take, bool pinned)
        {
            if (take <= 0) return;
            var gp = new GoodPlacement { Name = l.name, Furn = p, Start = start, Count = take, Pinned = pinned };
            var sp = GameArt.Item(l.name);
            for (int j = 0; j < take; j++)
            {
                var spot = Spots[first + start + j];
                spot.Occupant = l.name;
                if (sp == null) continue;
                var go = MakeGood(furnGo.transform, sp, spot.Slot, p.flip, sortOrder, l.name);
                goods.Add(go);
                gp.Gos.Add(go);
            }
            Goods.Add(gp);
            // ⚠️ 沒有道具圖（畫面上看不到）就不登記給顧客 —— 不然顧客會走去對著空架子看
            if (gp.Gos.Count > 0) goodsOn[l.name] = (p, SlotWorld(p, Spots[first + start].Slot));
        }

        /// <summary>
        /// 陳列位的擺放順序：由上而下、每層由左而右。表裡是「沒翻面」時的左右；
        /// 翻面後畫面左右顛倒，所以每一層倒過來排，一種商品的幾個位子才會在畫面上連在一起由左往右長。
        /// </summary>
        static List<DisplaySlot> SlotSequence(DisplaySlot[] slots, bool flip)
        {
            var seq = new List<DisplaySlot>(slots.Length);
            int i = 0;
            while (i < slots.Length)
            {
                int j = i;
                while (j < slots.Length && slots[j].Row == slots[i].Row) j++;
                if (flip) for (int k = j - 1; k >= i; k--) seq.Add(slots[k]);
                else for (int k = i; k < j; k++) seq.Add(slots[k]);
                i = j;
            }
            return seq;
        }

        /// <summary>
        /// 生一個商品：等比縮到塞得進位子（MaxW×MaxH），底部中心對在位子上。
        /// 用 sprite.bounds 算（含 PPU 與樞紐），道具圖的尺寸、樞紐怎麼設都對得上。
        /// </summary>
        static GameObject MakeGood(Transform parent, Sprite sp, DisplaySlot slot, bool flip, int order, string name)
        {
            var go = new GameObject($"good-{name}");
            go.transform.SetParent(parent, false);

            var b = sp.bounds;
            float k = Mathf.Min(slot.MaxW / Mathf.Max(0.01f, b.size.x), slot.MaxH / Mathf.Max(0.01f, b.size.y));
            float x = flip ? -slot.X : slot.X;
            go.transform.localScale = new Vector3(k, k, 1f);
            // 圖的底部中心 → 位子（位子本身就是層板／桌面的頂面，產生器算好的）
            go.transform.localPosition = new Vector3(x - b.center.x * k, slot.Y - b.min.y * k, 0f);

            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = order;
            return go;
        }

        /// <summary>每種擺出來的商品在哪件家具上、第一個位子的世界座標（SpawnGoods 每次重填）。</summary>
        readonly Dictionary<string, (PlacedFurniture Furn, Vector2 Pos)> goodsOn = new();

        /// <summary>陳列位的世界座標：家具錨點＋位子偏移（翻面時 X 取負）。跟 MakeGood 同一套換算。</summary>
        public static Vector2 SlotWorld(PlacedFurniture p, DisplaySlot slot)
        {
            var a = RoomLayout.AnchorPos(p);
            return new Vector2(a.x + (p.flip ? -slot.X : slot.X), a.y + slot.Y);
        }

        /// <summary>
        /// 顧客要看某樣上架商品時該站在哪（世界座標）。該商品擺在販售桌上 → 桌前（RoomLayout.SaleFront）；
        /// 擺在貨架上 → 那座貨架前方走道（RoomLayout.FrontClearance 的格子）裡離商品最近那格的中心；
        /// 沒擺出來或店還沒建好 → null。
        ///
        /// ⚠️ 查的是「這一刻畫面上擺的結果」（SpawnGoods 填的 goodsOn），不是存檔 —— 位子滿了沒擺出來的商品
        ///    就回 null，顧客不會走去一個空架子前面看。
        /// </summary>
        public static Vector2? BrowseSpotFor(string itemName)
        {
            var me = Instance;
            if (me == null || string.IsNullOrEmpty(itemName)) return null;
            if (!me.goodsOn.TryGetValue(itemName, out var at) || at.Furn == null) return null;

            var d = Furniture.ById(at.Furn.id);
            if (d == null) return null;
            if (d.Sale) return RoomLayout.SaleFront();

            var lane = RoomLayout.FrontClearance(at.Furn);
            if (lane.Count == 0)
            {
                // 陳列桌（不靠牆、沒有固定走道）：站在桌邊一圈空格裡離那樣商品最近的一格；
                // 優先畫面下方那兩邊（+gx／+gy，看得到桌面的那側），一圈都被堵住才退回前角往下一點。
                var (w, h) = at.Furn.Size;
                var blocked = ShopPath.BlockedCells();
                Vector2? pick = null;
                float pickD = float.MaxValue;
                for (int gx = at.Furn.gx - 1; gx <= at.Furn.gx + w; gx++)
                    for (int gy = at.Furn.gy - 1; gy <= at.Furn.gy + h; gy++)
                    {
                        bool inside = gx >= at.Furn.gx && gx < at.Furn.gx + w && gy >= at.Furn.gy && gy < at.Furn.gy + h;
                        bool corner = (gx < at.Furn.gx || gx >= at.Furn.gx + w) && (gy < at.Furn.gy || gy >= at.Furn.gy + h);
                        if (inside || corner || !ShopRoom.InGrid(gx, gy) || blocked[gx, gy]) continue;
                        var wc = ShopRoom.TileCenter(gx, gy);
                        bool back = gx < at.Furn.gx || gy < at.Furn.gy;      // 桌子後面（-gx／-gy 側）
                        float dd = (wc - at.Pos).sqrMagnitude + (back ? 4000f : 0f);
                        if (dd < pickD) { pickD = dd; pick = wc; }
                    }
                if (pick.HasValue) return pick.Value;
                var f = ShopRoom.FrontCorner(at.Furn.gx, at.Furn.gy, w, h);
                return new Vector2(f.x, f.y - 26f);
            }
            Vector2 best = default;
            float bestD = float.MaxValue;
            foreach (var c in lane)
            {
                var wc = ShopRoom.TileCenter(c.gx, c.gy);
                float dd = (wc - at.Pos).sqrMagnitude;
                if (dd < bestD) { bestD = dd; best = wc; }
            }
            return best;
        }

        // 佈置模式（拖曳家具、格線提示、托盤）在 ShopRoomEditor.cs。
    }
}
