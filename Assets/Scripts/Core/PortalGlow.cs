using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 傳送點的地上光圈。兩種：
    ///   ① 門（SceneDoor）—— 房子門口、店裡通往別間房的門，光圈小一點
    ///   ② 邊界傳送點 —— 走出地圖那一側的定點，光圈大一些（那是一道門不是門檻），
    ///      而且會標「前往 ○○」
    ///
    /// 沒有這層光的話玩家看不出「邊界哪裡能走」——整條邊看起來都一樣，
    /// 只有一個定點會傳送，找不到就會以為卡住了。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版用 Graphics 疊了十幾層半透明橢圓做出光暈漸層，每幀重畫。
    /// Unity 沒有等價的即時繪圖，所以光暈是**程式生成的一張徑向漸層貼圖**（生一次快取），
    /// 之後只要縮放與調整 alpha —— 每幀不用重畫任何幾何。
    /// </summary>
    public class PortalGlow : MonoBehaviour
    {
        public static PortalGlow Instance { get; private set; }

        public static PortalGlow Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("PortalGlow").AddComponent<PortalGlow>();
        }

        // ⚠️ 這幾個值比原版放大了：原版是 58/23 與 78/30，實機上在森林那種
        //    大地圖裡太不明顯（玩家找不到出口）。連同下面的 Alpha 一起調亮。
        const float DoorRx = 76f, DoorRy = 30f;    // 門口光圈（壓扁＝貼在地上，俯視角）
        const float EdgeRx = 108f, EdgeRy = 42f;   // 邊界傳送點的光圈大一些
        /// <summary>光圈最亮時的不透明度（原版 0.55 太淡）。</summary>
        const float PeakAlpha = 0.85f;
        /// <summary>光暈往地圖內縮多少 —— 刻意小於半徑，光圈會被畫面邊緣切掉一角，
        /// 那樣才像「邊界上的一道門」，而不是浮在地上的一團光。</summary>
        const float DefaultInset = 26f;

        static readonly Color32 Glow = new(150, 220, 255, 255);

        class Portal
        {
            public SpriteRenderer Sr;
            public SpriteRenderer Beam;   // 往上的光柱（遠處也看得到這裡是入口）
            public GameObject Label;      // 只有邊界傳送點有「前往 ○○」
            public Transform Follow;      // 門會跟著它的物件走（門可能被搬動）
            public Vector2 Offset;
        }

        readonly List<Portal> portals = new();
        Transform player;
        float time;

        void Awake() { Instance = this; }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;

            BuildDoorGlows();
            BuildEdgeGlows();
        }

        /// <summary>掃出場景裡所有掛了 SceneDoor 的物件，各給一個門口光暈。</summary>
        void BuildDoorGlows()
        {
            foreach (var d in FindObjectsByType<SceneDoor>(FindObjectsSortMode.None))
                portals.Add(MakeGlow(new Vector2(d.doorX, d.doorY), DoorRx, DoorRy,
                                     d.transform, null));
        }

        /// <summary>依 Portals 表在地圖邊界上擺光圈，並標出去哪裡。</summary>
        void BuildEdgeGlows()
        {
            string scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
            var ground = GameObject.Find("Ground");
            if (ground == null || !ground.TryGetComponent<SpriteRenderer>(out var gsr)) return;
            var b = gsr.bounds;

            // 上緣：玩家的可走範圍往內縮了一個身高（Data.ArtFootprints.EdgeTop，女巫的頭才不會畫到地面外），
            // 光圈若還在 26px 處，腳根本踩不到圈心。往下移到腳走得到的地方（略高於可走範圍的上緣）。
            // 左右（內縮 22）與下緣（內縮 6）都比 26 小，維持原樣。
            float topInset = Mathf.Max(DefaultInset, Data.ArtFootprints.EdgeTop - 10f);

            foreach (var g in Portals.Of(scene))
            {
                // 左右側的邊 → At 是 y 座標；上下側 → At 是 x 座標
                Vector2 pos = g.Side switch
                {
                    "left"  => new Vector2(b.min.x + DefaultInset, g.At),
                    "right" => new Vector2(b.max.x - DefaultInset, g.At),
                    "top"   => new Vector2(g.At, b.max.y - topInset),
                    _       => new Vector2(g.At, b.min.y + DefaultInset),
                };
                portals.Add(MakeGlow(pos, EdgeRx, EdgeRy, null, $"前往 {SceneLabel(g.To)}"));
            }
        }

        static string SceneLabel(string scene) => scene switch
        {
            "main" => "森林", "town" => "城鎮", "shop" => "店裡",
            "brew" => "藥水室", "garden" => "後花園", "candy" => "糖果鎮",
            _ => scene,
        };

        Portal MakeGlow(Vector2 pos, float rx, float ry, Transform follow, string label)
        {
            var go = new GameObject("glow");
            go.transform.SetParent(transform);
            var basePos = follow != null ? (Vector2)follow.position + pos : pos;
            go.transform.position = new Vector3(basePos.x, basePos.y, 0f);

            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = GlowSprite();
            sr.color = Glow;
            // 壓扁成橢圓＝貼在地上。sprite 是 128px 的方形，所以縮放＝半徑/64
            go.transform.localScale = new Vector3(rx / 64f * 2f, ry / 64f * 2f, 1f);
            sr.sortingOrder = -9000;      // 在地面之上、所有物件之下（光是「畫在地上」的）

            // 往上的光柱：原版有、我一開始漏掉了。註解寫得很清楚 ——
            // 「房間另一頭／街上遠處也看得到這裡是入口」。地上的橢圓從遠處看太扁。
            var beamGo = new GameObject("beam");
            beamGo.transform.SetParent(go.transform, false);
            var beam = beamGo.AddComponent<SpriteRenderer>();
            beam.sprite = BeamSprite();
            beam.color = Glow;
            beam.sortingOrder = -8999;                       // 剛好在地上光圈之上
            // go 已經被縮放過，所以這裡用相對值把光柱撐成「下寬上窄」的一道
            beamGo.transform.localScale = new Vector3(0.55f, 2.6f, 1f);
            beamGo.transform.localPosition = new Vector3(0f, 0.5f, 0f);   // 從地面往上長

            GameObject lab = null;
            if (!string.IsNullOrEmpty(label))
            {
                lab = new GameObject("label");
                lab.transform.SetParent(go.transform, false);
                lab.transform.localPosition = new Vector3(0f, 0.9f, 0f);   // 已被縮放過，用相對值
                lab.transform.localScale = new Vector3(1f / go.transform.localScale.x,
                                                       1f / go.transform.localScale.y, 1f);
                var tm = lab.AddComponent<TextMesh>();
                tm.text = label;
                tm.fontSize = 36;
                tm.characterSize = 4.5f;
                tm.anchor = TextAnchor.MiddleCenter;
                tm.color = new Color32(214, 244, 255, 255);
                var font = UI.CjkFont.Get();
                if (font != null)
                {
                    tm.font = font;
                    lab.GetComponent<MeshRenderer>().material = font.material;
                }
                lab.GetComponent<MeshRenderer>().sortingOrder = 9400;
                lab.SetActive(false);
            }

            return new Portal { Sr = sr, Beam = beam, Label = lab, Follow = follow, Offset = pos };
        }

        void Update()
        {
            time += Time.deltaTime;
            // 呼吸：0.62 ~ 1.0（同原版節奏）
            float pulse = 0.62f + 0.38f * Mathf.Sin(time * 2.1f);

            foreach (var p in portals)
            {
                if (p.Sr == null) continue;

                if (p.Follow != null)
                    p.Sr.transform.position = new Vector3(p.Follow.position.x + p.Offset.x,
                                                          p.Follow.position.y + p.Offset.y, 0f);

                var c = p.Sr.color;
                c.a = pulse * PeakAlpha;
                p.Sr.color = c;

                if (p.Beam != null)
                {
                    var bc = p.Beam.color;
                    bc.a = pulse * PeakAlpha * 0.45f;    // 光柱比地上的圈淡一些，才不會糊成一團
                    p.Beam.color = bc;
                }

                // 「前往 ○○」只在玩家靠近時顯示，遠看只有一團光
                if (p.Label != null && player != null)
                {
                    float d = Vector2.Distance(player.position, p.Sr.transform.position);
                    p.Label.SetActive(d < 220f && !UIState.ModalOpen);
                }
            }
        }

        static Sprite beamSprite;

        /// <summary>
        /// 光柱貼圖：下寬上窄、越往上越淡。
        /// 原版是疊 8 層梯形矩形畫出來的，這裡直接烤成一張圖，每幀不用重畫。
        /// </summary>
        static Sprite BeamSprite()
        {
            if (beamSprite != null) return beamSprite;

            const int W = 64, H = 128;
            var tex = new Texture2D(W, H, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            for (int y = 0; y < H; y++)
            {
                float t = (float)y / (H - 1);              // 0 = 底部，1 = 頂端
                float halfW = (W / 2f) * (1f - t * 0.55f); // 下寬上窄
                float fade = (1f - t) * (1f - t);          // 往上淡出
                for (int x = 0; x < W; x++)
                {
                    float dx = Mathf.Abs(x - (W - 1) / 2f);
                    float edge = Mathf.Clamp01(1f - dx / Mathf.Max(1f, halfW));
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, edge * edge * fade * 0.9f));
                }
            }
            tex.Apply();
            // 樞紐在底部中央 → 從地面往上長
            beamSprite = Sprite.Create(tex, new Rect(0, 0, W, H), new Vector2(0.5f, 0f), 1f);
            return beamSprite;
        }

        static Sprite glowSprite;

        /// <summary>徑向漸層的圓形光暈（程式生成一次，之後共用）。</summary>
        static Sprite GlowSprite()
        {
            if (glowSprite != null) return glowSprite;

            const int N = 128;
            var tex = new Texture2D(N, N, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            float c = (N - 1) / 2f;
            for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    float d = Vector2.Distance(new Vector2(x, y), new Vector2(c, c)) / c;
                    // 外圈柔和淡出 + 中心再亮一點的核心（對應原版疊兩組橢圓的效果）
                    float halo = Mathf.Clamp01(1f - d);
                    float core = Mathf.Clamp01(1f - d / 0.42f);
                    float a = halo * halo * 0.55f + core * core * 0.45f;
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, Mathf.Clamp01(a)));
                }
            tex.Apply();
            glowSprite = Sprite.Create(tex, new Rect(0, 0, N, N), new Vector2(0.5f, 0.5f), 1f);
            return glowSprite;
        }
    }
}
