using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 顧客系統：村民三三兩兩走進店裡，逛到商品前說幾句話，一部分人買下（ShopStock.SellOne → Wallet.Add），
    /// 一部分人只逛不買，然後離開。
    ///
    /// 顧客跟城鎮街上走動的是同一批人（VillagerAnim ＋ Resources/villagers）。
    /// 由 PlayerController 進 shop 場景時呼叫 Ensure()。
    ///
    /// ── 來客節奏（11/26 改版）──────────────────────────────────────
    /// 舊版：每 I 秒準時進來一位（I ＝ 招牌間隔 × 名聲倍率 × 節日 0.6），每位都買一件。
    ///       實機玩起來像輸送帶 —— 一個走、下一個才進來，店裡永遠只有一個人。
    /// 新版：
    ///   ● 下一組的等待時間 ＝ I × f，f ＝ GapMin + GapSpan × u^GapPow（u 均勻 0..1）
    ///     ＝ 0.35～1.75、平均 0.91。指數 1.5 讓短間隔比較多（兩三位接連進來）、
    ///     又留一條長尾（空一陣子）—— 實測 32% 的間隔 &lt; 0.6I、17% &gt; 1.4I。
    ///   ● 每一組有 GroupChance（25%）是結伴的 2～3 人（3 人佔其中 35%），
    ///     彼此錯開 0.6～1.8 秒進門（第三位 0.6～2.5 秒），不會疊在門口同一點同時冒出來。
    ///   ● 每位顧客以 BuyChance 的機率是「要買的」，其餘只逛不買（看 1～2 樣、評論幾句就走）。
    ///
    /// ── 經濟：為什麼成交量沒變 ──────────────────────────────────
    ///   舊版期望成交率 ＝ 1 / I（件/秒）—— 舊版的同時上限從來碰不到（一位顧客停留約 5 秒、間隔最短 1.05 秒、
    ///   上限 8），所以就是準時每 I 秒一件。
    ///   新版期望成交率 ＝ (1 / (I × E[f])) × E[每組人數] × BuyChance
    ///                 ＝ (1 / (I × 0.91)) × 1.3375 × BuyChance
    ///   要跟舊版一樣 → BuyChance ＝ E[f] / E[每組人數] ＝ 0.91 / 1.3375 ≈ 0.68。
    ///   也就是：進門的人變成舊版的 1.47 倍，其中約 68% 會買 → 成交件數不變。
    ///   BuyChance 是從上面幾個常數**算出來的**，改任何一個參數成交率都會自動維持。
    ///   離線模擬：tools/sim_customers.py（含同時上限、結伴被上限截掉、停留時間的影響）。
    ///   模擬結果（新/舊 成交件數，每設定 400 遊戲小時）：
    ///     招牌0 名聲1 96%　招牌0+節日 100%　招牌2 名聲3 100%　招牌4 名聲5 98%　招牌4 名聲5 節日（最快）89%
    ///   最快那檔掉 11% 是店裡 12% 的時間是滿的（14 人）—— 在 ±20% 內，而且那是一年只有幾天的節日。
    ///
    ///   ⚠️ 同時上限 ＝ ceil(舊上限 × 1.5) ＋ 2（最低階 5 人）。人變多、每位停留也變長（會講話、會逛兩樣），
    ///      上限不跟著放寬的話，高等級時店裡一直是滿的，新的一組進不來 → 成交率會掉。
    ///   ⚠️ 滿了的時候「下一組」不會被丟掉，而是在門外等到有人離開才進來（舊版是直接跳過）——
    ///      這樣上限只會讓客人晚一點進來，不會讓期望成交率偷偷變少。
    ///   ⚠️ AwayShop（玩家不在店裡時的背景成交）用它自己的速率 0.7 / I，沒有動；新版在店裡平均仍是 1 / I，
    ///      兩者的比例（離店 = 在店的七成）跟以前一樣。
    ///
    /// ── 走位 ───────────────────────────────────────────────────
    ///   目的地＝他想要的那樣商品擺的地方（ShopRoomView.BrowseSpotFor：販售桌 → 桌前、貨架 → 架前走道），
    ///   沒擺出來就退回販售桌前。多人時用 FreeSpotNear 錯開站位；走路沿 ShopPath 的格子 BFS 路點，繞過家具。
    ///   ⚠️ 不穿家具（使用者回報「路人走路不要穿牆」）：找不到路時**不退回直線** —— 跳過那樣商品或提早離開；
    ///      站位（含亂數偏移）一律過 ShopPath.Standable（不在家具格、不貼家具、不出地板菱形）；
    ///      佈置模式搬了家具 → 每 0.25 秒比一次擺設指紋，變了就 Relayout（重算路／換站位／離開）。
    ///      地板菱形以外只有「門口那一格」會去：進出口＝DoorTown 那格的中心，本身就在地板上。
    ///   排序：店裡的長貨架用 -y 排會錯，所以顧客跟女巫一樣問 ShopRoomView.PlayerOrder（VillagerAnim.orderOverride）。
    ///   兩個角色拿到同一個 order 時（例如都站在同一座貨架前面），靠節點的 z 決定前後：
    ///   z ＝ (腳底 y − 女巫腳底 y) × 0.001 —— 內建管線的正交攝影機在同 order 時比 z（離攝影機近的畫在上面），
    ///   而女巫的 z 是 0，所以「比她低（在她前面）」的顧客 z 為負、畫在她上面；顧客彼此之間也是腳底低的在前。
    /// </summary>
    public class CustomerManager : MonoBehaviour
    {
        public static CustomerManager Instance { get; private set; }

        public static CustomerManager Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("CustomerManager").AddComponent<CustomerManager>();
        }

        [Tooltip("顧客走路速度（像素/秒）")] public float walkSpeed = 120f;
        [Tooltip("顧客立繪縮放")] public float displayScale = VillagerAnim.Scale;

        // ──────────── 來客節奏參數（見檔頭的經濟說明）────────────

        /// <summary>間隔係數 f 的下限與範圍：f ∈ [0.35, 1.75]。</summary>
        const float GapMin = 0.35f, GapSpan = 1.4f;
        /// <summary>u^GapPow：&gt;1 讓短間隔比較常見（接連進來），長尾留給「空一陣子」。</summary>
        const float GapPow = 1.5f;
        /// <summary>E[f] ＝ GapMin + GapSpan / (GapPow + 1) ＝ 0.91。</summary>
        const float MeanGap = GapMin + GapSpan / (GapPow + 1f);
        /// <summary>一組是結伴（2～3 人）的機率，以及結伴裡 3 人的比例。</summary>
        const float GroupChance = 0.25f, Group3Share = 0.35f;
        /// <summary>E[每組人數] ＝ 1 + GroupChance × (1 + Group3Share) ＝ 1.3375。</summary>
        const float MeanVisitors = 1f + GroupChance * (1f + Group3Share);
        /// <summary>每位顧客「要買」的機率 ＝ E[f] / E[每組人數] ≈ 0.68 —— 讓期望成交率維持舊版的 1 / I。</summary>
        const float BuyChance = MeanGap / MeanVisitors;

        // 停留節奏（秒）
        const float WantTime = 1.6f;      // 說「想要 X」到成交
        const float PaidTime = 1.4f;      // +金額泡泡（表情動畫同時播）到說謝謝
        const float ThankWalk = 0.6f;     // 說謝謝後多久轉身走（邊走邊講完）
        const float SoldOutWait = 1.3f;   // 沒貨抱怨後多久走
        const float LookMin = 2.4f, LookMax = 3.2f;   // 只逛不買的人在每樣商品前站多久

        /// <summary>兩位顧客的站位至少隔多遠（px）。</summary>
        const float SpotGap = 26f;
        /// <summary>專屬台詞（CustomerLines.Personal）被抽到的機率。</summary>
        const float PersonalChance = 0.3f;

        /// <summary>顧客的行為狀態。</summary>
        enum St { Walk, Stand, Leave }

        /// <summary>站完之後要做什麼。</summary>
        enum Act { Buy, Thank, NextVisit, Leave }

        class Customer
        {
            public GameObject Node;
            public VillagerAnim Anim;
            public string Who;
            public St State;
            public float Timer;           // Stand：還要站多久
            public Act After;
            public bool Buyer;
            public string Want;           // 想買的東西（Buyer 才有意義）
            public List<string> Visits = new();   // 要逛的商品（Buyer ＝ [Want]）
            public int VisitIdx;
            public Vector2 Spot;          // 目前要去／正站著的位置（別人挑站位時要避開）
            public bool HasSpot;
            public Vector2 SpotBase;      // 站位是在哪一點附近挑的（家具被搬動、站位被佔時從這裡重挑）
            /// <summary>
            /// 站到一半被家具擠開、正走去新站位：走到了就回到 Stand（沿用原本的 Timer／After），
            /// 不重新開口說話、也不重算停留時間 —— 顧客經濟的節奏不受影響。
            /// </summary>
            public bool Resume;
            public List<Vector2> Path = new();
            public int PathIdx;
            public string LastLine;       // 上一句（原始模板）—— 同一位不要連講同一句
            public string CurLine;        // 頭上這句（原始模板）—— 同時在場的人避開
            public float CurUntil;        // 這句什麼時候消失（Time.time）
            public Sprite[] EmoteFrames;
            public SpriteRenderer EmoteSr;
            public float EmoteTimer;
        }

        /// <summary>還沒進門的結伴成員（已經算進同時人數，免得進門時超過上限）。</summary>
        class Pending
        {
            public float Delay;
            public int Size, Index, Duo;
        }

        readonly List<Customer> customers = new();
        readonly List<Pending> pending = new();
        float arrivalTimer = -1f;         // &lt;0 ＝ 還沒排第一組
        PlayerController witch;
        float witchSearch;
        // 家具擺設的指紋（ShopPath.LayoutSignature）：每 0.25 秒比一次，變了就 Relayout
        int layoutSig;
        bool layoutKnown;
        float layoutCheckAt;

        void Awake() { Instance = this; GameArt.Preload(); }
        void OnDestroy() { if (Instance == this) Instance = null; }

        /// <summary>進出口＝通往城鎮那道門所在的格子（門搬家顧客就跟著改走那裡）。</summary>
        static Vector2 EntrancePos() =>
            ShopRoom.TileCenter(ShopRoom.DoorTown.gx, ShopRoom.DoorTown.gy);

        /// <summary>來客間隔基準 I（秒）＝ 招牌升級 × 名聲加成 × 節日加成。跟 AwayShop 同一條式子。</summary>
        static float BaseInterval(bool festival) =>
            Upgrades.CustomerInterval() * Reputation.IntervalScale() * (festival ? 0.6f : 1f);

        /// <summary>
        /// 同時在店裡的上限 ＝ ceil(舊上限 × 1.5) ＋ 2。舊上限 ＝ 招牌 ＋ 名聲 ＋ 節日（2..8）→ 新的 5..14。
        /// 為什麼要放寬見檔頭。試過 ＋1（4..13）：最低階 10% 的時間是滿的，成交率只剩舊版的 91%；
        /// 最高階節日 86%。＋2 之後是 96%／89%，其餘設定 98～100%（tools/sim_customers.py）。
        /// </summary>
        static int RoomCap(bool festival)
        {
            int old = Upgrades.CustomerMax() + Reputation.ExtraCustomers() + (festival ? 1 : 0);
            return Upgrades.CrowdCap(old);
        }

        static float GapFactor() => GapMin + GapSpan * Mathf.Pow(Random.value, GapPow);

        void Update()
        {
            if (UIState.ModalOpen) return;
            float dt = Time.deltaTime;

            bool festival = TimeSystem.FestivalToday() != null;
            float interval = BaseInterval(festival);
            // ⚠️ 只在營業時間上門（08:00-20:00）—— 沒有這個限制的話，半夜三點也會有人來買藥水。
            //    門口招牌翻成 CLOSED（ShopSign）也一樣：不進新客、門外等的結伴成員取消，跟打烊同一條路。
            //    沒上架任何東西時不來客（跟舊版一樣）。已經在店裡的人不受影響，照常逛完走人。
            // ⚠️ 用 ShopSign.Serving（招牌 && 營業時間），不要去改 DailyLog.IsShopOpen 的語意 —— 別處在用。
            bool canServe = ShopSign.Serving && GameArt.Ready && ShopStock.Types > 0;

            if (!canServe)
            {
                pending.Clear();                       // 還在門外的結伴成員就不進來了
                if (arrivalTimer < 0f) arrivalTimer = interval * GapFactor();
            }
            else
            {
                if (arrivalTimer < 0f) arrivalTimer = interval * GapFactor();   // 剛進店：照常排第一組

                // 門外的結伴成員：時間到就進門
                for (int i = pending.Count - 1; i >= 0; i--)
                {
                    var p = pending[i];
                    p.Delay -= dt;
                    if (p.Delay > 0f) continue;
                    pending.RemoveAt(i);
                    Spawn(p.Size, p.Index, p.Duo);
                }

                // 下一組：時間到、而且店裡還有空位才進來；滿了就停在 0 等（不丟掉，見檔頭）
                if (arrivalTimer > 0f) arrivalTimer -= dt;
                int room = RoomCap(festival);
                int used = customers.Count + pending.Count;
                if (arrivalTimer <= 0f && used < room)
                {
                    int size = 1;
                    if (Random.value < GroupChance) size = Random.value < Group3Share ? 3 : 2;
                    size = Mathf.Min(size, room - used);
                    int duo = Random.Range(0, CustomerLines.Duo.Length);

                    Spawn(size, 0, duo);
                    float delay = 0f;
                    for (int k = 1; k < size; k++)
                    {
                        delay += k == 1 ? Random.Range(0.6f, 1.8f) : Random.Range(0.6f, 2.5f);
                        pending.Add(new Pending { Delay = delay, Size = size, Index = k, Duo = duo });
                    }
                    arrivalTimer = interval * GapFactor();
                }
            }

            // 家具被搬動了（佈置模式）→ 走到一半、站著的人重新找路（見 Relayout）
            if (Time.time >= layoutCheckAt)
            {
                layoutCheckAt = Time.time + 0.25f;
                int sig = ShopPath.LayoutSignature();
                if (!layoutKnown || sig != layoutSig)
                {
                    bool first = !layoutKnown;
                    layoutKnown = true;
                    layoutSig = sig;
                    if (!first) foreach (var c in customers) Relayout(c);
                }
            }

            // 推進每位顧客
            for (int i = customers.Count - 1; i >= 0; i--)
            {
                if (Step(customers[i], dt))
                {
                    // ⚠️ 泡泡與表情都是 Node 的子物件 —— 一起銷毀，不用另外清
                    if (customers[i].Node != null) Destroy(customers[i].Node);
                    customers.RemoveAt(i);
                }
            }
        }

        void LateUpdate()
        {
            // 同 order 時的前後：用 z 微調（見檔頭「排序」）。女巫找不到就當她在 y = 0。
            if (witch == null && Time.time >= witchSearch)
            {
                witch = FindAnyObjectByType<PlayerController>();
                witchSearch = Time.time + 1f;          // 找不到也別每幀找
            }
            float wy = witch != null ? witch.transform.position.y : 0f;
            foreach (var c in customers)
            {
                if (c.Node == null) continue;
                var p = c.Node.transform.position;
                c.Node.transform.position = new Vector3(p.x, p.y, (p.y - wy) * 0.001f);
            }
        }

        // ──────────── 生成 ────────────

        /// <param name="size">這一組幾個人</param>
        /// <param name="index">這位是組裡第幾個進門的（0 起）</param>
        /// <param name="duo">結伴時一搭一唱用哪一組台詞（CustomerLines.Duo 的索引）</param>
        void Spawn(int size, int index, int duo)
        {
            var names = GameArt.VillagerNames();
            if (names.Length == 0) return;
            var list = ShopStock.Listings();
            if (list.Count == 0) return;

            // 挑人：盡量不要跟店裡已經在的人撞臉（同一個村民不會分身出現兩次）
            var free = new List<string>(names);
            foreach (var c0 in customers) free.Remove(c0.Who);
            string who = free.Count > 0 ? free[Random.Range(0, free.Count)]
                                        : names[Random.Range(0, names.Length)];

            var c = new Customer { Who = who, Buyer = Random.value < BuyChance };
            if (c.Buyer)
            {
                c.Want = list[Random.Range(0, list.Count)].name;
                c.Visits.Add(c.Want);
            }
            else
            {
                // 只逛不買：看 1～2 樣不同的商品
                int n = list.Count >= 2 && Random.value < 0.5f ? 2 : 1;
                var pool = new List<string>();
                foreach (var l in list) pool.Add(l.name);
                for (int k = 0; k < n && pool.Count > 0; k++)
                {
                    int j = Random.Range(0, pool.Count);
                    c.Visits.Add(pool[j]);
                    pool.RemoveAt(j);
                }
            }

            var go = new GameObject("Customer-" + who);
            go.transform.SetParent(transform);
            var e = EntrancePos();
            go.transform.position = new Vector3(e.x, e.y, 0f);
            var anim = go.AddComponent<VillagerAnim>();
            anim.Init(who, displayScale);
            // 店裡的排序跟女巫同一套（長貨架用 -y 排會錯）；城鎮的村民不設，行為不變
            var tr = go.transform;
            anim.orderOverride = () => ShopRoomView.PlayerOrder(tr.position, anim.DisplayWidth, anim.DisplayHeight);
            c.Node = go; c.Anim = anim;
            customers.Add(c);

            // 進門的招呼。結伴：第一位起頭、第二位接話、第三位喊「等等我」
            string greet;
            if (size >= 2 && index == 0) greet = PickFrom(c, new[] { CustomerLines.Duo[duo][0] });
            else if (size >= 2 && index == 1) greet = PickFrom(c, new[] { CustomerLines.Duo[duo][1] });
            else if (size >= 3 && index >= 2) greet = PickFrom(c, CustomerLines.GroupTail);
            else greet = PickFrom(c, GreetPool(c));
            Say(c, null, Fill(greet), BgTalk, 2.2f);

            GoToVisit(c);
        }

        // ──────────── 成交（AwayShop 也用，行為不要改）────────────

        /// <summary>
        /// 成交：扣架上的貨、收錢、記今日營收（順便加名聲）、記任務進度。
        /// 回傳成交價，**0 ＝架上已經沒貨**（顧客空手而歸）。
        ///
        /// 抽成 static 是為了讓 <see cref="AwayShop"/>（你不在店裡時的背景成交）
        /// 走同一段程式 —— 不然很容易出現「離店賣掉的不算任務進度」這種對不起來的落差。
        /// </summary>
        public static int CompleteSale(string want)
        {
            int price = ShopStock.SellOne(want);
            if (price <= 0) return 0;
            Wallet.Add(price);
            DailyLog.RecordSale(want, price);   // 記進今日營收，順便加名聲
            QuestLog.Record(ObjKind.Sell, want, 1);
            return price;
        }

        // ──────────── 行為 ────────────

        /// <summary>推進一位顧客；回傳 true＝該離場銷毀。</summary>
        bool Step(Customer c, float dt)
        {
            if (c.Node == null) return true;
            AnimateEmote(c, dt);

            switch (c.State)
            {
                case St.Walk:
                    if (FollowPath(c, dt))
                    {
                        if (c.Resume) { c.Resume = false; c.State = St.Stand; FaceGoods(c); }   // 被擠開後站回去
                        else Arrive(c);
                    }
                    return false;

                case St.Stand:
                    c.Timer -= dt;
                    if (c.Timer <= 0f) DoAfter(c);
                    return false;

                case St.Leave:
                    return FollowPath(c, dt);          // 走到出口就銷毀
            }
            return false;
        }

        /// <summary>出發去 Visits[VisitIdx] 那樣商品的位置。</summary>
        void GoToVisit(Customer c)
        {
            string item = c.Visits[c.VisitIdx];
            Vector2 baseSpot = ShopRoomView.BrowseSpotFor(item)
                               ?? RoomLayout.SaleFront()
                               ?? EntrancePos();
            c.SpotBase = baseSpot;
            c.Spot = FreeSpotNear(baseSpot, c);
            c.HasSpot = true;
            c.Resume = false;
            if (!SetPath(c, c.Spot))
            {
                // 走不到那樣商品前（家具把那一區圍起來了）：寧可跳過它／提早離開，也不要直線穿過家具
                c.HasSpot = false;
                c.VisitIdx++;
                if (c.VisitIdx < c.Visits.Count) GoToVisit(c);
                else Leave(c);
                return;
            }
            c.State = St.Walk;
        }

        /// <summary>
        /// 家具被搬動之後重新安排這位顧客（只在擺設指紋變了的那一刻呼叫）：
        ///   ● 走向站位中：站位還站得住就重算路；被家具佔了就在原本的商品附近重挑站位；走不到就離開；
        ///   ● 站著：腳下還站得住就不動；被家具壓到／貼太近 → 走去附近的新站位，到了接著站完剩下的時間（Resume）；
        ///   ● 離開中：重算往門口的路；門口被圍死（走不到）→ 路是空的，下一幀就直接消失 —— 不穿過家具。
        /// </summary>
        void Relayout(Customer c)
        {
            if (c.Node == null) return;
            var blocked = ShopPath.BlockedCells();
            var pos = (Vector2)c.Node.transform.position;
            switch (c.State)
            {
                case St.Leave:
                    SetPath(c, EntrancePos());
                    return;

                case St.Walk:
                    if (!ShopPath.Standable(c.Spot, blocked)) c.Spot = FreeSpotNear(c.SpotBase, c);
                    if (!SetPath(c, c.Spot)) Leave(c);
                    return;

                case St.Stand:
                    if (ShopPath.Standable(pos, blocked)) return;
                    c.Spot = FreeSpotNear(c.SpotBase, c);
                    if (!SetPath(c, c.Spot)) { Leave(c); return; }
                    c.Resume = true;
                    c.State = St.Walk;
                    return;
            }
        }

        /// <summary>走到商品前：面向商品、開口說話。</summary>
        void Arrive(Customer c)
        {
            FaceGoods(c);
            string item = c.Visits[c.VisitIdx];
            if (c.Buyer)
            {
                Say(c, GameArt.Item(item), Fill(PickFrom(c, CustomerLines.Want), item), BgWant, WantTime + 0.6f);
                Stand(c, WantTime, Act.Buy);
            }
            else
            {
                string[] pool = CustomerLines.Browse;
                float look = Random.Range(LookMin, LookMax);
                Say(c, GameArt.Item(item), Fill(PickFrom(c, pool), item), BgBrowse, look);
                Stand(c, look, Act.NextVisit);
            }
        }

        /// <summary>
        /// 站定後面向商品：看腳下那格旁邊哪一格有家具，就轉向它（先看直向四格、再看斜角）。
        /// 貨架前的走道 → 側身對著貨架；販售桌前（桌子在斜後方）→ 背對玩家面向桌子。
        /// 旁邊都沒家具（退回直線、站歪了）就照舊版面向上方。
        /// </summary>
        static void FaceGoods(Customer c)
        {
            var p = c.Node.transform.position;
            var me = ShopRoom.WorldToTile(p.x, p.y);
            var blocked = ShopPath.BlockedCells();
            var dirs = new[] { (-1, 0), (0, -1), (1, 0), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1) };
            foreach (var (dx, dy) in dirs)
            {
                int gx = me.gx + dx, gy = me.gy + dy;
                if (!ShopRoom.InGrid(gx, gy) || !blocked[gx, gy]) continue;
                var w = ShopRoom.TileCenter(gx, gy);
                c.Anim.FaceTo(w.x - p.x, w.y - p.y);
                return;
            }
            c.Anim.FaceTo(0f, 1f);
        }

        void Stand(Customer c, float t, Act after)
        {
            c.State = St.Stand; c.Timer = t; c.After = after;
            c.Anim.SetMove(0f, 0f);
        }

        void DoAfter(Customer c)
        {
            switch (c.After)
            {
                case Act.Buy:
                {
                    // 嘗試購買：想要的還在架上就成交
                    int price = CompleteSale(c.Want);
                    if (price > 0)
                    {
                        // 收錢的音效掛在這裡、不掛在 CompleteSale 裡 —— AwayShop 離店成交也走
                        // CompleteSale，玩家不在店裡時不該每一筆都叮一聲（回店那則彙總才響）。
                        Sfx.Play("coin");
                        ShowEmote(c, price);                     // +金額泡泡 ＋ 表情動畫
                        Stand(c, PaidTime, Act.Thank);           // 等它播完才說謝謝，兩顆泡泡不互蓋
                    }
                    else
                    {
                        Say(c, null, Fill(PickFrom(c, CustomerLines.SoldOut), c.Want), BgSad, 2.6f);
                        Stand(c, SoldOutWait, Act.Leave);
                    }
                    break;
                }
                case Act.Thank:
                    Say(c, null, Fill(PickFrom(c, CustomerLines.Thanks)), BgHappy, 2.4f);
                    Stand(c, ThankWalk, Act.Leave);              // 邊走邊把話講完
                    break;

                case Act.NextVisit:
                    c.VisitIdx++;
                    if (c.VisitIdx < c.Visits.Count) { GoToVisit(c); break; }
                    // 逛完了：一半的人留句話再走
                    if (Random.value < 0.55f)
                    {
                        Say(c, null, Fill(PickFrom(c, CustomerLines.BrowseLeave)), BgTalk, 2.4f);
                        Stand(c, 0.8f, Act.Leave);
                    }
                    else Leave(c);
                    break;

                case Act.Leave:
                    Leave(c);
                    break;
            }
        }

        void Leave(Customer c)
        {
            c.HasSpot = false;                 // 讓出站位
            SetPath(c, EntrancePos());
            c.State = St.Leave;
        }

        // ──────────── 走路 ────────────

        /// <summary>
        /// 設定目的地：算一次格子路徑（ShopPath.Find），之後沿路點走。
        /// ⚠️ 只在這裡算 —— 不要每幀尋路。
        /// 回傳 false ＝ 走不到（家具把路堵死）：路清成空的（FollowPath 會立刻當作「到了」），
        /// 呼叫端自己決定改站別處或離開 —— **不退回直線**（舊版那樣會穿過家具）。
        /// 走得到時，站位 Spot 更新成路的終點（終點貼家具時 ShopPath 會換成那格中心，別人錯開站位要看真的位置）。
        /// </summary>
        static bool SetPath(Customer c, Vector2 target)
        {
            var p = c.Node.transform.position;
            var path = ShopPath.Find(new Vector2(p.x, p.y), target);
            c.PathIdx = 0;
            if (path == null || path.Count == 0)
            {
                c.Path.Clear();
                return false;
            }
            c.Path = path;
            if (c.HasSpot && c.State != St.Leave) c.Spot = path[path.Count - 1];
            return true;
        }

        /// <summary>沿路點走；走到最後一點回 true。</summary>
        bool FollowPath(Customer c, float dt)
        {
            if (c.Path == null || c.PathIdx >= c.Path.Count) { c.Anim.SetMove(0f, 0f); return true; }
            float budget = walkSpeed * dt;
            while (c.PathIdx < c.Path.Count)
            {
                var target = c.Path[c.PathIdx];
                var p = c.Node.transform.position;
                float dx = target.x - p.x, dy = target.y - p.y;
                float dist = Mathf.Sqrt(dx * dx + dy * dy);
                if (dist <= budget)
                {
                    // 這一段走完，剩下的步長接著走下一段（轉角不會頓一下）
                    c.Node.transform.position = new Vector3(target.x, target.y, p.z);
                    budget -= dist;
                    c.PathIdx++;
                    continue;
                }
                c.Node.transform.position = new Vector3(p.x + dx / dist * budget, p.y + dy / dist * budget, p.z);
                c.Anim.SetMove(dx / dist, dy / dist);
                return false;
            }
            c.Anim.SetMove(0f, 0f);
            return true;
        }

        /// <summary>
        /// 在 baseSpot 附近挑一個站位：要站得住（ShopPath.Standable：不在家具上、不貼家具、在地板菱形內），
        /// 而且跟其他顧客的站位隔開 SpotGap。
        /// 候選點沿等距的兩條格線方向往外排（貨架前的走道就是沿格線斜的），都擠滿了就挑「離別人最遠」的那個。
        /// ⚠️ 加了亂數偏移之後要**再驗一次**（舊版先驗後加，偏移會把點推到家具格或地板外）；
        ///    一個站得住的候選都沒有時，退回 baseSpot 附近最近的空格中心（舊版直接回 baseSpot，可能在家具裡）。
        /// </summary>
        Vector2 FreeSpotNear(Vector2 baseSpot, Customer self)
        {
            // 格座標的一步在世界上：+gx ＝ (32,-16)、+gy ＝ (-32,-16)
            var ax = new Vector2(ShopRoom.TileW / 2f, -ShopRoom.TileH / 2f);
            var ay = new Vector2(-ShopRoom.TileW / 2f, -ShopRoom.TileH / 2f);
            float[] along = { 0f, 0.45f, -0.45f, 0.9f, -0.9f, 1.35f, -1.35f };   // 沿走道（主方向）
            float[] across = { 0f, 0.35f, -0.35f };                             // 往走道兩側一點點
            var blocked = ShopPath.BlockedCells();       // 一次算好，候選點都用這份

            Vector2 best = baseSpot;
            float bestScore = -1f;
            foreach (float a in along)
                foreach (float b in across)
                    // 不知道走道是沿哪條格線（貨架靠左牆或右牆），兩個方向都試
                    foreach (var p in new[] { baseSpot + ax * a + ay * b, baseSpot + ay * a + ax * b })
                    {
                        if (!ShopPath.Standable(p, blocked)) continue;
                        float near = float.MaxValue;
                        foreach (var o in customers)
                            if (o != self && o.HasSpot) near = Mathf.Min(near, Vector2.Distance(o.Spot, p));
                        // 夠空就用它，加一點點亂數，同一個位置的人不會每次都站在完全同一點（偏移後還要站得住）
                        if (near >= SpotGap)
                        {
                            var q = p + new Vector2(Random.Range(-4f, 4f), Random.Range(-2f, 2f));
                            return ShopPath.Standable(q, blocked) ? q : p;
                        }
                        if (near > bestScore) { bestScore = near; best = p; }
                    }
            // 全部候選都擠：挑離別人最遠的那個。一個站得住的都沒有（bestScore 仍 -1）→ 最近的空格中心
            if (bestScore < 0f) return ShopPath.NearestFreeCenter(baseSpot, blocked) ?? baseSpot;
            return best;
        }

        // ──────────── 說話 ────────────

        static readonly Color32 BgTalk = new(60, 48, 76, 230);     // 一般閒聊：紫灰
        static readonly Color32 BgWant = new(30, 24, 40, 230);     // 想要 X：沿用舊版的深色
        static readonly Color32 BgBrowse = new(52, 64, 88, 230);   // 只逛不買的評論：藍灰
        static readonly Color32 BgHappy = new(60, 90, 60, 235);    // 道謝：跟 +金額同色系
        static readonly Color32 BgSad = new(150, 120, 120, 235);   // 沒貨：沿用舊版

        void Say(Customer c, Sprite icon, string text, Color32 bg, float life)
        {
            if (c.Node == null) return;
            SpeechBubble.Show(c.Node.transform, c.Anim.DisplayHeight, icon, text, bg, life);
            c.CurUntil = Time.time + life;
        }

        /// <summary>招呼的候選：通用 ＋ 時段 ＋ 季節 ＋ 節日（有的話），再有機率換成專屬台詞。</summary>
        List<string> GreetPool(Customer c)
        {
            var pool = new List<string>(CustomerLines.Greet);
            float h = TimeSystem.TodHours;
            if (h < 11f) pool.AddRange(CustomerLines.Morning);
            else if (h >= 17f) pool.AddRange(CustomerLines.Evening);
            int s = TimeSystem.Season;
            if (s >= 0 && s < CustomerLines.Season.Length) pool.AddRange(CustomerLines.Season[s]);
            if (TimeSystem.FestivalToday() != null)
            {
                // 節日當天加料多一點（加兩次＝權重加倍），不然被一大堆通用招呼稀釋掉
                pool.AddRange(CustomerLines.Festival);
                pool.AddRange(CustomerLines.Festival);
            }
            if (Random.value < PersonalChance && CustomerLines.Personal.TryGetValue(c.Who, out var mine))
                return new List<string>(mine);
            return pool;
        }

        /// <summary>
        /// 從候選裡挑一句（回傳原始模板，記成這位的 LastLine/CurLine）：
        /// 避開自己上一句、以及同時在場的人頭上正掛著的那句；都避不開就放寬。
        /// </summary>
        string PickFrom(Customer c, IList<string> pool)
        {
            if (pool == null || pool.Count == 0) return "";
            var busy = new HashSet<string>();
            foreach (var o in customers)
                if (o != c && o.CurLine != null && Time.time < o.CurUntil) busy.Add(o.CurLine);

            var ok = new List<string>();
            foreach (var l in pool) if (l != c.LastLine && !busy.Contains(l)) ok.Add(l);
            if (ok.Count == 0) foreach (var l in pool) if (l != c.LastLine) ok.Add(l);
            if (ok.Count == 0) ok.AddRange(pool);

            string pick = ok[Random.Range(0, ok.Count)];
            c.LastLine = pick;
            c.CurLine = pick;
            return pick;
        }

        /// <summary>代入佔位字：{item}＝商品名、{fest}＝今天的節日名。</summary>
        static string Fill(string line, string item = null)
        {
            if (string.IsNullOrEmpty(line)) return "";
            if (item != null) line = line.Replace("{item}", item);
            if (line.Contains("{fest}"))
            {
                var f = TimeSystem.FestivalToday();
                line = line.Replace("{fest}", f != null ? f.Name : "節日");
            }
            return line;
        }

        // ──────────── 成交後的表情動畫 ────────────

        static readonly string[] EmoteNames = { "emo18", "emo3", "emo2", "emo32", "emo51" };

        void ShowEmote(Customer c, int price)
        {
            // +金額只掛 PaidTime 秒：時間一到就換成道謝（Act.Thank），兩顆不會同時在頭上互蓋
            SpeechBubble.Show(c.Node.transform, c.Anim.DisplayHeight,
                              null, $"+{price}", BgHappy, PaidTime);
            c.CurLine = null;

            // 先清掉上一個還沒播完的表情（理論上一位顧客只買一次，保險起見）
            if (c.EmoteSr != null) Destroy(c.EmoteSr.gameObject);
            c.EmoteFrames = null; c.EmoteSr = null;

            var frames = GameArt.Emote(EmoteNames[Random.Range(0, EmoteNames.Length)]);
            if (frames.Length == 0) return;

            var go = new GameObject("emote");
            go.transform.SetParent(c.Node.transform, false);
            go.transform.localPosition = new Vector3(28f, c.Anim.DisplayHeight + 62f, 0f);
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = frames[0];
            sr.sortingOrder = 9600;

            c.EmoteFrames = frames;
            c.EmoteSr = sr;
            c.EmoteTimer = 0f;
        }

        static void AnimateEmote(Customer c, float dt)
        {
            if (c.EmoteFrames == null || c.EmoteSr == null) return;
            c.EmoteTimer += dt;
            int i = Mathf.FloorToInt(c.EmoteTimer * 24f);      // 表情動畫 24fps
            if (i >= c.EmoteFrames.Length)
            {
                if (c.EmoteSr != null) Destroy(c.EmoteSr.gameObject);
                c.EmoteFrames = null; c.EmoteSr = null;
                return;
            }
            c.EmoteSr.sprite = c.EmoteFrames[i];
        }
    }
}
