using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 8-bit 後花園（<see cref="GardenRoom.UsePixelGarden"/>）圍牆外小路上散步的路人。
    ///
    /// 路網是產生器（tools/gen_garden_art.py）畫小路時一起算的：GardenRoomData.FolkNodes／FolkEdges ——
    /// 繞花園一圈（含小屋後面）＋幾條走出畫面的岔路（FolkExits）。每個人：
    ///   · 在節點上**隨機**挑下一段（不立刻走回頭，死路才回頭）；
    ///   · 三成機率停下來站一會兒；走到畫面外的岔路盡頭就待 4～10 秒再走回來（像去別處逛一圈）；
    ///   · 有一個固定的小偏移（Lane，±10px），幾個人不會疊在同一條線上。
    /// 白天 GardenRoomData.FolkCount 位、晚上兩位；開著面板時全部停住（同 TownFolk）。
    ///
    /// 排序（前後要對）：
    ///   · 站在後牆、小屋「後面」的（GardenRoomData.BehindBack：腳底沿視線往玩家那邊碰到後景層物件）
    ///     → FolkBackOrder 附近（-8190..-8010）：在影子層（-8500）之上、後景層（-8000）之下 → 被牆與小屋擋住；
    ///   · 其他 → FolkFrontOrder − y：在前牆（3000）之上、最前景樹叢（6000）之下。
    /// 女巫走不出圍牆、路人也進不來（路網整個在牆外，tools/check_garden_walk.py 有驗）—— 兩邊不會碰到。
    ///
    /// 為什麼不用 TownFolk：它的折線模式只會沿一條路來回，城鎮模式要 TownNav／Obstacles 的格圖（後花園外面沒有）。
    /// 這支是獨立的小元件，城鎮與糖果鎮的路人行為完全不受影響。
    /// </summary>
    public class GardenFolk : MonoBehaviour
    {
        public static GardenFolk Instance { get; private set; }

        public static GardenFolk Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("GardenFolk").AddComponent<GardenFolk>();
        }

        const int NightCount = 2;
        const float LaneMax = 10f;
        /// <summary>後面的人彼此也要排前後：FolkBackOrder ± 這麼多（還在影子層 -8500 與後景層 -8000 之間）。</summary>
        const int BackSpread = 90;

        class Walker
        {
            public GameObject Node;
            public VillagerAnim Anim;
            public string Who;
            public float Speed;
            public float Pause;
            public int Prev = -1, At, To;
            public Vector2 Lane;
        }

        readonly List<Walker> folk = new();
        List<int>[] adj;
        readonly HashSet<int> exits = new();
        float retry;

        void Awake()
        {
            Instance = this;
            GameArt.Preload();
            int n = GardenRoomData.FolkNodes.Length;
            adj = new List<int>[n];
            for (int i = 0; i < n; i++) adj[i] = new List<int>();
            var e = GardenRoomData.FolkEdges;
            for (int i = 0; i + 1 < e.Length; i += 2)
            {
                if (e[i] < 0 || e[i] >= n || e[i + 1] < 0 || e[i + 1] >= n) continue;
                adj[e[i]].Add(e[i + 1]);
                adj[e[i + 1]].Add(e[i]);
            }
            foreach (var x in GardenRoomData.FolkExits) exits.Add(x);
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        void Update()
        {
            if (UIState.ModalOpen) return;
            if (adj == null || adj.Length < 2) return;

            int want = TimeSystem.IsNight ? Mathf.Min(NightCount, GardenRoomData.FolkCount) : GardenRoomData.FolkCount;
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

            float dt = Time.deltaTime;
            foreach (var w in folk) Step(w, dt);
        }

        Vector2 Pos(Walker w, int node) => GardenRoomData.FolkNodes[node] + w.Lane;

        void Spawn()
        {
            var names = GameArt.VillagerNames();
            if (names.Length == 0) return;
            var taken = new HashSet<string>();
            foreach (var w0 in folk) taken.Add(w0.Who);
            var pool = new List<string>();
            foreach (var nm in names) if (!taken.Contains(nm)) pool.Add(nm);
            if (pool.Count == 0) pool.AddRange(names);

            // 出生在路上的某個節點（不是畫面外的岔路盡頭）
            int start = 0;
            for (int t = 0; t < 12; t++)
            {
                start = Random.Range(0, adj.Length);
                if (!exits.Contains(start) && adj[start].Count > 0) break;
            }

            var w = new Walker
            {
                Who = pool[Random.Range(0, pool.Count)],
                Speed = 40f + Random.value * 25f,
                Pause = Random.value * 2f,
                At = start,
                To = start,
                Lane = Random.insideUnitCircle * LaneMax,
            };
            var p = Pos(w, start);
            var go = new GameObject("Folk-" + w.Who);
            go.transform.SetParent(transform);
            go.transform.position = new Vector3(p.x, p.y, 0f);
            var anim = go.AddComponent<VillagerAnim>();
            anim.Init(w.Who);
            var tr = go.transform;
            anim.orderOverride = () => OrderAt(tr.position);
            w.Node = go;
            w.Anim = anim;
            folk.Add(w);
        }

        /// <summary>這一點的路人該排在哪（見檔頭）。</summary>
        public static int OrderAt(Vector3 p)
        {
            if (GardenRoomData.BehindBack(p))
                return GardenRoomData.FolkBackOrder + Mathf.Clamp(Mathf.RoundToInt(-p.y / 8f), -BackSpread, BackSpread);
            return GardenRoomData.FolkFrontOrder + Mathf.RoundToInt(-p.y);
        }

        /// <summary>到了一個節點：隨機挑下一個相鄰節點（不立刻走回頭，除非是死路）。</summary>
        int PickNext(Walker w)
        {
            var nb = adj[w.At];
            if (nb.Count == 0) return w.At;
            if (nb.Count == 1) return nb[0];
            for (int t = 0; t < 8; t++)
            {
                int c = nb[Random.Range(0, nb.Count)];
                if (c != w.Prev) return c;
            }
            return nb[0];
        }

        void Step(Walker w, float dt)
        {
            if (w.Node == null) return;
            if (w.Pause > 0f)
            {
                w.Pause -= dt;
                w.Anim.SetMove(0f, 0f);
                return;
            }
            if (w.To == w.At)
            {
                w.To = PickNext(w);
                if (w.To == w.At) { w.Pause = 1f; return; }
            }

            var target = Pos(w, w.To);
            var p = (Vector2)w.Node.transform.position;
            var d = target - p;
            float dist = d.magnitude;
            float stepLen = w.Speed * dt;
            if (dist <= stepLen)
            {
                w.Node.transform.position = new Vector3(target.x, target.y, 0f);
                w.Prev = w.At;
                w.At = w.To;
                // 走到畫面外的岔路盡頭：在外面待一會兒再回來；其他節點偶爾停下來看看風景
                if (exits.Contains(w.At)) w.Pause = 4f + Random.value * 6f;
                else if (Random.value < 0.3f) w.Pause = 1f + Random.value * 2.5f;
                w.Anim.SetMove(0f, 0f);
                return;
            }
            var dir = d / dist;
            w.Node.transform.position = new Vector3(p.x + dir.x * stepLen, p.y + dir.y * stepLen, 0f);
            w.Anim.SetMove(dir.x, dir.y);
        }
    }
}
