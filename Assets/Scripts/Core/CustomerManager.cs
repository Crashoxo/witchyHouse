using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 顧客系統：定時生一位村民走進店裡，看中一件上架商品就買下
    /// （ShopStock.SellOne → Wallet.Add），冒對話泡，然後離開。
    ///
    /// 顧客跟城鎮街上走動的是同一批人（VillagerAnim ＋ Resources/villagers）。
    /// 由 PlayerController 進 shop 場景時呼叫 Ensure()。
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

        /// <summary>顧客的行為狀態。</summary>
        enum St { Enter, Browse, Leave }

        class Customer
        {
            public GameObject Node;
            public VillagerAnim Anim;
            public St State;
            public float Timer;
            public string Want;        // 想買的東西
            public Vector2 Target;
            public Sprite[] EmoteFrames;
            public SpriteRenderer EmoteSr;
            public float EmoteTimer;
        }

        readonly List<Customer> customers = new();
        float spawnTimer;

        void Awake() { Instance = this; GameArt.Preload(); }
        void OnDestroy() { if (Instance == this) Instance = null; }

        /// <summary>進出口＝通往城鎮那道門所在的格子（門搬家顧客就跟著改走那裡）。</summary>
        static Vector2 EntrancePos() =>
            ShopRoom.TileCenter(ShopRoom.DoorTown.gx, ShopRoom.DoorTown.gy);

        /// <summary>
        /// 挑貨位置＝販售桌前面。桌子是玩家自己擺的，所以每次生成都重新問一次
        /// RoomLayout —— 搬了桌子，顧客動線就跟著變。
        /// </summary>
        static Vector2 BrowseSpot()
        {
            var f = RoomLayout.SaleFront();
            if (f == null) return EntrancePos();
            return new Vector2(f.Value.x + (Random.value - 0.5f) * 70f,
                               f.Value.y + (Random.value - 0.5f) * 24f);
        }

        void Update()
        {
            if (UIState.ModalOpen) return;

            // 生成（來客速度/人數＝「招牌」升級決定）
            spawnTimer += Time.deltaTime;
            // 來客速度/人數 ＝ 招牌升級 × 名聲加成 × 節日加成
            bool festival = TimeSystem.FestivalToday() != null;
            float interval = Upgrades.CustomerInterval() * Reputation.IntervalScale()
                             * (festival ? 0.6f : 1f);
            if (spawnTimer >= interval)
            {
                spawnTimer = 0f;
                int room = Upgrades.CustomerMax() + Reputation.ExtraCustomers() + (festival ? 1 : 0);
                // ⚠️ 只在營業時間上門（08:00-20:00）—— 沒有這個限制的話，
                //    半夜三點也會有人來買藥水。
                if (DailyLog.IsShopOpen() && GameArt.Ready
                    && ShopStock.Types > 0 && customers.Count < room) Spawn();
            }

            // 推進每位顧客
            for (int i = customers.Count - 1; i >= 0; i--)
            {
                if (Step(customers[i], Time.deltaTime))
                {
                    if (customers[i].Node != null) Destroy(customers[i].Node);
                    customers.RemoveAt(i);
                }
            }
        }

        void Spawn()
        {
            var names = GameArt.VillagerNames();
            if (names.Length == 0) return;
            string who = names[Random.Range(0, names.Length)];

            var list = ShopStock.Listings();
            if (list.Count == 0) return;
            string want = list[Random.Range(0, list.Count)].name;

            var go = new GameObject("Customer-" + who);
            go.transform.SetParent(transform);
            var e = EntrancePos();
            go.transform.position = new Vector3(e.x, e.y, 0f);
            var anim = go.AddComponent<VillagerAnim>();
            anim.Init(who, displayScale);

            customers.Add(new Customer
            {
                Node = go, Anim = anim, State = St.Enter, Timer = 0f,
                Want = want, Target = BrowseSpot(),
            });
        }

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

        /// <summary>推進一位顧客；回傳 true＝該離場銷毀。</summary>
        bool Step(Customer c, float dt)
        {
            if (c.Node == null) return true;
            AnimateEmote(c, dt);

            switch (c.State)
            {
                case St.Enter:
                    if (MoveTo(c, c.Target, dt))
                    {
                        c.State = St.Browse; c.Timer = 0f;
                        c.Anim.FaceTo(0f, 1f);     // 停在桌前，面向桌上的商品（背對玩家）
                        SpeechBubble.Show(c.Node.transform, c.Anim.DisplayHeight,
                                          GameArt.Item(c.Want), $"想要 {c.Want}",
                                          new Color32(30, 24, 40, 230));
                    }
                    return false;

                case St.Browse:
                    c.Timer += dt;
                    if (c.Timer >= 1.2f)
                    {
                        // 嘗試購買：想要的還在架上就成交
                        int price = CompleteSale(c.Want);
                        if (price > 0)
                        {
                            ShowEmote(c, price);
                        }
                        else
                        {
                            SpeechBubble.Show(c.Node.transform, c.Anim.DisplayHeight,
                                              null, "沒貨…下次吧",
                                              new Color32(150, 120, 120, 235));
                        }
                        c.State = St.Leave; c.Timer = 0f;
                    }
                    return false;

                case St.Leave:
                    c.Timer += dt;
                    if (c.Timer < 1.0f) return false;      // 成交後停一下再走
                    return MoveTo(c, EntrancePos(), dt);   // 走到出口就銷毀
            }
            return false;
        }

        /// <summary>朝 target 移動；到達回 true。走路動畫與面向交給 VillagerAnim。</summary>
        bool MoveTo(Customer c, Vector2 target, float dt)
        {
            var p = c.Node.transform.position;
            float dx = target.x - p.x, dy = target.y - p.y;
            float dist = Mathf.Sqrt(dx * dx + dy * dy);
            float step = walkSpeed * dt;
            if (dist <= step)
            {
                c.Node.transform.position = new Vector3(target.x, target.y, 0f);
                c.Anim.SetMove(0f, 0f);
                return true;
            }
            c.Node.transform.position = new Vector3(p.x + dx / dist * step, p.y + dy / dist * step, 0f);
            c.Anim.SetMove(dx / dist, dy / dist);
            return false;
        }

        // ──────────── 成交後的表情動畫 ────────────

        static readonly string[] EmoteNames = { "emo18", "emo3", "emo2", "emo32", "emo51" };

        void ShowEmote(Customer c, int price)
        {
            SpeechBubble.Show(c.Node.transform, c.Anim.DisplayHeight,
                              null, $"+{price}", new Color32(60, 90, 60, 235));

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
