using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 城鎮街上走動的村民。
    ///
    /// 跟店裡的顧客是同一批人（Resources/villagers ＋ VillagerAnim），在鎮上晃來晃去：
    /// 走到一個路點 → 停一下 → 再挑下一個。路點來自 TownRoads.Walk（原專案從烤好的
    /// 城鎮小地圖抽出來的「路的內部」格子），所以他們一定走在真的有路的地方。
    ///
    /// 由 PlayerController 在 town 場景呼叫 Ensure() —— 不用改場景。
    /// </summary>
    public class TownFolk : MonoBehaviour
    {
        public static TownFolk Instance { get; private set; }

        /// <summary>白天街上幾個人；入夜後只剩 NightCount 個（其他人回家了）。</summary>
        public const int DayCount = 6;
        public const int NightCount = 2;

        /// <summary>
        /// 生一個 TownFolk 出來（重複呼叫安全）。
        /// </summary>
        /// <param name="route">走哪些路點</param>
        /// <param name="crowd">同時最多幾個人</param>
        public static TownFolk Ensure(Vector2[] route, int crowd = DayCount)
        {
            if (Instance != null) return Instance;
            var go = new GameObject("TownFolk");
            var f = go.AddComponent<TownFolk>();
            f.waypoints = route;
            f.crowd = crowd;
            return f;
        }

        class Walker
        {
            public GameObject Node;
            public VillagerAnim Anim;
            public string Who;
            public Vector2 Target;
            public float Speed;
            public float Pause;      // 還要站多久（秒）
        }

        Vector2[] waypoints = System.Array.Empty<Vector2>();
        readonly List<Walker> folk = new();
        int crowd = DayCount;
        float retry;

        void Awake() { Instance = this; GameArt.Preload(); }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Update()
        {
            if (UIState.ModalOpen) return;      // 開著選單/對話時整個鎮上靜止
            if (waypoints.Length < 2) return;

            // 白天熱鬧、晚上剩零星幾個（其他人回家了）
            int want = TimeSystem.IsNight ? Mathf.Min(NightCount, crowd) : crowd;

            if (folk.Count < want && GameArt.Ready)
            {
                retry += Time.deltaTime;
                if (retry > 0.8f) { retry = 0f; Spawn(); }
            }
            else if (folk.Count > want)
            {
                var bye = folk[folk.Count - 1];
                folk.RemoveAt(folk.Count - 1);
                if (bye.Node != null) Destroy(bye.Node);
            }

            foreach (var w in folk) Step(w, Time.deltaTime);
        }

        Vector2 PickWaypoint()
        {
            var p = waypoints[Random.Range(0, waypoints.Length)];
            // 加點偏移，免得所有人都走同一條線
            return new Vector2(p.x + (Random.value - 0.5f) * 90f,
                               p.y + (Random.value - 0.5f) * 60f);
        }

        void Spawn()
        {
            var names = GameArt.VillagerNames();
            if (names.Length == 0) return;

            // 盡量不要跟街上現有的人重複
            var taken = new HashSet<string>();
            foreach (var w in folk) taken.Add(w.Who);
            var pool = new List<string>();
            foreach (var n in names) if (!taken.Contains(n)) pool.Add(n);
            if (pool.Count == 0) pool.AddRange(names);
            string who = pool[Random.Range(0, pool.Count)];

            var go = new GameObject("Folk-" + who);
            go.transform.SetParent(transform);
            var start = PickWaypoint();
            go.transform.position = new Vector3(start.x, start.y, 0f);
            var anim = go.AddComponent<VillagerAnim>();
            anim.Init(who);

            folk.Add(new Walker
            {
                Node = go, Anim = anim, Who = who,
                Target = PickWaypoint(),
                Speed = 50f + Random.value * 30f,
                Pause = Random.value * 2f,
            });
        }

        /// <summary>推進一位村民：停頓中就站著，否則往目標走，到了就再挑一個。</summary>
        void Step(Walker w, float dt)
        {
            if (w.Node == null) return;
            if (w.Pause > 0f)
            {
                w.Pause -= dt;
                w.Anim.SetMove(0f, 0f);
                return;
            }
            var p = w.Node.transform.position;
            float dx = w.Target.x - p.x, dy = w.Target.y - p.y;
            float dist = Mathf.Sqrt(dx * dx + dy * dy);
            float stepLen = w.Speed * dt;
            if (dist <= stepLen)
            {
                w.Node.transform.position = new Vector3(w.Target.x, w.Target.y, 0f);
                w.Anim.SetMove(0f, 0f);
                w.Target = PickWaypoint();
                w.Pause = 1.5f + Random.value * 2.5f;
                return;
            }
            w.Node.transform.position = new Vector3(p.x + dx / dist * stepLen,
                                                    p.y + dy / dist * stepLen, 0f);
            w.Anim.SetMove(dx / dist, dy / dist);
        }
    }
}
