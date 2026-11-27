using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 8-bit 後花園的「搬花圃」模式：按 R 進出（跟店裡佈置同一顆鍵），用滑鼠把花圃拖到別的空格。
    /// 只在 <see cref="GardenRoom.UsePixelGarden"/> 時由 GardenRoom 叫起來。
    ///
    ///   · 進場：草地壓暗、整片格線亮出來（門口兩格、樹和雨水桶那格是紅的＝不能放）；
    ///     下面一條圖示提示（UI/GardenArrangeHud），上方工具列的 R 提示收起來。
    ///   · 按住花圃拖：花圃（土＋花＋缺水提醒）整塊跟著滑鼠，腳下那一格出現預覽菱形：綠＝可以、紅＝不行
    ///     （被別塊佔了／門口／裝飾／格盤外）。放開：可以 → 搬過去並**當下存檔**（witch.garden.layout）、place 音；
    ///     不行 → 回原位、deny 音、左右抖一下，提示列亮出原因圖。放回原格不出聲。
    ///   · R 或 Esc 離開（每次放下都已經存了，沒有「取消還原」）。
    ///   · 佈置中女巫不走、E 不作用（PlayerController／GardenRoom 看 <see cref="Editing"/>）；開著面板時不吃輸入。
    /// 種了花的花圃一起搬：花長到哪、澆過水沒都記在 Garden（照 index），位置是另一份資料（GardenLayout）。
    /// </summary>
    public class GardenArrange : MonoBehaviour
    {
        public static GardenArrange Instance { get; private set; }

        public static GardenArrange Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("GardenArrange").AddComponent<GardenArrange>();
        }

        public bool Editing { get; private set; }

        Camera cam;

        // 拖曳中
        GardenPlot drag;
        Cell dragFrom;
        Vector3 grabOffset;
        Cell hover;
        GardenLayout.Block hoverBlock = GardenLayout.Block.Ok;

        readonly List<SpriteRenderer> gridCells = new();
        SpriteRenderer ghost, dimmer;

        // 放不下：抖一下＋提示列短暫亮原因
        GardenPlot shakePlot;
        Vector3 shakeBase;
        float shakeT0, flashUntil;

        // ── 顏色（同店裡佈置模式）──
        static readonly Color GridCol = new(1f, 1f, 1f, 0.34f);
        static readonly Color BlockedCol = new(1f, 0.3f, 0.28f, 0.7f);
        static readonly Color GhostOk = new(0.25f, 1f, 0.4f, 0.8f);
        static readonly Color GhostBad = new(1f, 0.18f, 0.18f, 0.85f);
        static readonly Color TintOk = new(0.8f, 1f, 0.82f, 1f);
        static readonly Color TintBad = new(1f, 0.62f, 0.6f, 1f);

        // ── 排序 ──
        const int OrderDim = -9600;       // 底圖（-10000）之上、格線之下：只壓暗草地，花圃不暗
        const int OrderGrid = -9500;
        const int OrderGhost = 4000;      // 花圃與前景牆（3000）之上；拖著的花圃（5000）之下

        const float ShakeSecs = 0.35f;
        const float FlashSecs = 1.4f;

        void Awake() { Instance = this; cam = Camera.main; }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Update()
        {
            if (GardenRoom.Instance == null) return;

            // R 切換。⚠️ 開著別的面板（選種子…）時不吃
            if (!UIState.ModalOpen && Input.GetKeyDown(KeyCode.R))
            {
                if (Editing) Exit(); else Enter();
                return;
            }
            if (!Editing) return;

            if (UIState.ModalOpen)
            {
                if (drag != null) Drop(forceBack: true);
                return;
            }
            if (Input.GetKeyDown(KeyCode.Escape)) { Exit(); return; }

            if (Input.GetMouseButtonDown(0)) BeginDrag();
            else if (drag != null && Input.GetMouseButton(0)) DragMove();
            else if (drag != null && Input.GetMouseButtonUp(0)) Drop(forceBack: false);
        }

        void LateUpdate()
        {
            if (!Editing) return;
            float t = Time.unscaledTime;
            UpdateShake(t);
            if (flashUntil > 0f && t > flashUntil) { flashUntil = 0f; UI.GardenArrangeHud.Instance?.SetState(drag != null, null); }
            if (ghost != null && ghost.gameObject.activeSelf)
            {
                var c = hoverBlock == GardenLayout.Block.Ok ? GhostOk : GhostBad;
                c.a *= 0.7f + 0.3f * (0.5f + 0.5f * Mathf.Sin(t * 5f));
                ghost.color = c;
            }
        }

        // ──────────── 進出 ────────────

        void Enter()
        {
            Editing = true;
            Sfx.Play("ui-open");
            BuildGrid();
            ShowDimmer(true);
            UI.GardenArrangeHud.Ensure().Show();
        }

        void Exit()
        {
            if (drag != null) Drop(forceBack: false);     // 拖到一半按 R：照放開處理（放得下就存）
            StopShake();
            Editing = false;
            flashUntil = 0f;
            ShowGrid(false);
            ShowDimmer(false);
            ShowGhost(false);
            UI.GardenArrangeHud.Instance?.Hide();
            Sfx.Play("ui-close");
        }

        // ──────────── 拖曳 ────────────

        Vector3 MouseWorld()
        {
            if (cam == null) cam = Camera.main;
            var w = cam != null ? cam.ScreenToWorldPoint(Input.mousePosition) : Vector3.zero;
            w.z = 0f;
            return w;
        }

        void BeginDrag()
        {
            if (UI.CornerHud.BlocksWorldClick(Input.mousePosition)) return;   // 點在上方工具列
            StopShake();
            var m = MouseWorld();
            var plot = PlotUnder(m);
            if (plot == null) return;

            drag = plot;
            dragFrom = GardenLayout.CellOf(plot.index);
            grabOffset = plot.transform.position - m;
            hover = dragFrom;
            hoverBlock = GardenLayout.Block.Ok;
            plot.SetLifted(true, TintOk);
            ShowGhostAt(hover);
            Sfx.Play("pickup");
            UI.GardenArrangeHud.Instance?.SetState(true, null);
        }

        /// <summary>
        /// 滑鼠底下是哪一塊花圃：先看滑鼠所在的格子（土壤磚就是那一格）；
        /// 沒有的話再看長高的花的圖（點到花上半部時，格子會算到後面那一格）—— 疊在一起拿最前面的。
        /// </summary>
        GardenPlot PlotUnder(Vector3 m)
        {
            var room = GardenRoom.Instance;
            var c = GardenRoomData.WorldToCell(m.x, m.y);
            int at = GardenLayout.PlotAt(c.gx, c.gy);
            if (at >= 0)
            {
                var p = room.FindPlot(at);
                if (p != null) return p;
            }
            GardenPlot best = null;
            float bestY = float.MaxValue;
            foreach (var p in room.Plots)
            {
                if (p == null) continue;
                foreach (var sr in p.GetComponentsInChildren<SpriteRenderer>())
                {
                    if (sr.sprite == null || !sr.gameObject.activeInHierarchy) continue;
                    var b = sr.bounds;
                    if (!b.Contains(new Vector3(m.x, m.y, b.center.z))) continue;
                    if (p.transform.position.y < bestY) { bestY = p.transform.position.y; best = p; }
                }
            }
            return best;
        }

        void DragMove()
        {
            var want = MouseWorld() + grabOffset;
            drag.transform.position = new Vector3(want.x, want.y, 0f);     // 整塊跟著滑鼠（含缺水提醒）

            var c = GardenRoomData.WorldToCell(want.x, want.y);
            if (c.gx == hover.gx && c.gy == hover.gy) return;            // 換格才重算
            hover = c;
            var b = GardenLayout.Check(drag.index, c.gx, c.gy);
            bool changed = b != hoverBlock;
            hoverBlock = b;
            if (GardenRoomData.InGrid(c.gx, c.gy)) ShowGhostAt(c); else ShowGhost(false);
            drag.SetLifted(true, b == GardenLayout.Block.Ok ? TintOk : TintBad);
            if (changed) UI.GardenArrangeHud.Instance?.SetState(true, b == GardenLayout.Block.Ok ? null : BlockIcon(b));
        }

        /// <param name="forceBack">true ＝ 不管腳下哪格，直接放回原位（開了面板之類被打斷）</param>
        void Drop(bool forceBack)
        {
            var p = drag;
            drag = null;
            ShowGhost(false);
            if (p == null) return;

            bool same = hover.gx == dragFrom.gx && hover.gy == dragFrom.gy;
            bool ok = !forceBack && !same && hoverBlock == GardenLayout.Block.Ok
                      && GardenLayout.Move(p.index, hover.gx, hover.gy);
            var to = ok ? hover : dragFrom;
            p.MoveTo(GardenRoomData.CellCenter(to.gx, to.gy));
            p.SetLifted(false);

            if (ok)
            {
                Sfx.Play("place");
                UI.GardenArrangeHud.Instance?.SetState(false, null);
            }
            else if (!forceBack && !same)
            {
                // 放不下：回原位、deny、抖一下，提示列短暫亮出原因（不跳句子）
                Sfx.Play("deny");
                StartShake(p);
                flashUntil = Time.unscaledTime + FlashSecs;
                UI.GardenArrangeHud.Instance?.SetState(false, BlockIcon(hoverBlock));
            }
            else UI.GardenArrangeHud.Instance?.SetState(false, null);
            hoverBlock = GardenLayout.Block.Ok;
        }

        /// <summary>放不下的原因 → 提示圖示（tools/gen_ui_icons.py 畫的那幾張）。</summary>
        static string BlockIcon(GardenLayout.Block b) => b switch
        {
            GardenLayout.Block.OffGrid => "blk_offfloor",
            GardenLayout.Block.Door => "blk_door",
            GardenLayout.Block.Decor => "blk_overlap",
            GardenLayout.Block.Occupied => "blk_overlap",
            _ => "st_no",
        };

        void StartShake(GardenPlot p)
        {
            StopShake();
            shakePlot = p;
            shakeBase = p.transform.position;
            shakeT0 = Time.unscaledTime;
        }

        void UpdateShake(float now)
        {
            if (shakePlot == null) return;
            float t = now - shakeT0;
            if (t >= ShakeSecs || drag == shakePlot) { StopShake(); return; }
            float k = 1f - t / ShakeSecs;
            shakePlot.transform.position = shakeBase + new Vector3(Mathf.Sin(t * 70f) * 3f * k, 0f, 0f);
        }

        void StopShake()
        {
            if (shakePlot != null && drag != shakePlot) shakePlot.transform.position = shakeBase;
            shakePlot = null;
        }

        // ──────────── 格線、預覽、壓暗 ────────────

        /// <summary>整片格子（只建一次，之後只開關＋更新顏色 —— Destroy 是延遲的，重建會新舊疊在同一幀）。</summary>
        void BuildGrid()
        {
            if (gridCells.Count == 0)
            {
                for (int gy = 0; gy < GardenRoomData.Rows; gy++)
                    for (int gx = 0; gx < GardenRoomData.Cols; gx++)
                    {
                        var p = GardenRoomData.CellCenter(gx, gy);
                        var go = new GameObject($"cell{gx}-{gy}");
                        go.transform.SetParent(transform);
                        go.transform.position = new Vector3(p.x, p.y, 0f);
                        go.transform.localScale = TileScale;    // 64×64 的菱形貼圖縮放成一格（GardenRoomData.TileW×TileH）
                        var sr = go.AddComponent<SpriteRenderer>();
                        sr.sortingOrder = OrderGrid;
                        gridCells.Add(sr);
                    }
            }
            int i = 0;
            for (int gy = 0; gy < GardenRoomData.Rows; gy++)
                for (int gx = 0; gx < GardenRoomData.Cols; gx++)
                {
                    var sr = gridCells[i++];
                    bool blocked = GardenLayout.CellRule(gx, gy) != GardenLayout.Block.Ok;
                    sr.sprite = blocked ? FillSprite() : GridSprite();
                    sr.color = blocked ? BlockedCol : GridCol;
                }
            ShowGrid(true);
        }

        void ShowGrid(bool on)
        {
            foreach (var sr in gridCells) if (sr != null) sr.gameObject.SetActive(on);
        }

        void ShowGhostAt(Cell c)
        {
            if (ghost == null)
            {
                var go = new GameObject("arrange-ghost");
                go.transform.SetParent(transform);
                go.transform.localScale = TileScale;
                ghost = go.AddComponent<SpriteRenderer>();
                ghost.sprite = FillSprite();
                ghost.sortingOrder = OrderGhost;
            }
            var p = GardenRoomData.CellCenter(c.gx, c.gy);
            ghost.transform.position = new Vector3(p.x, p.y, 0f);
            ghost.gameObject.SetActive(true);
        }

        void ShowGhost(bool on)
        {
            if (ghost != null) ghost.gameObject.SetActive(on);
        }

        void ShowDimmer(bool on)
        {
            if (dimmer == null)
            {
                if (!on) return;
                var go = new GameObject("arrange-dim");
                go.transform.SetParent(transform);
                dimmer = go.AddComponent<SpriteRenderer>();
                dimmer.sprite = PixelSprite();
                dimmer.sortingOrder = OrderDim;
                dimmer.color = new Color(0.04f, 0.02f, 0.08f, 0.32f);
                go.transform.position = Vector3.zero;
                go.transform.localScale = new Vector3(GardenRoomData.ImgW + 200f, GardenRoomData.ImgH + 200f, 1f);   // 底圖掛在原點
            }
            dimmer.gameObject.SetActive(on);
        }

        // ──────────── 程式生成的貼圖（像素風：Point，不糊）────────────

        static Sprite gridSprite, fillSprite, pixelSprite;

        /// <summary>菱形貼圖是 64×64 的方形 → 縮放成一格的大小（格子大小只看 GardenRoomData，這裡不寫死）。</summary>
        static Vector3 TileScale => new(GardenRoomData.TileW / 64f, GardenRoomData.TileH / 64f, 1f);

        /// <summary>等距菱形：曼哈頓距離 ≤ 半徑＝菱形內；邊緣 edgeFrom 以外那圈畫 1、內側畫 inner。64×64，用時 y 壓一半。</summary>
        static Sprite MakeDiamond(float edgeFrom, float inner)
        {
            const int N = 64;
            var tex = new Texture2D(N, N, TextureFormat.RGBA32, false) { filterMode = FilterMode.Point };
            float c = (N - 1) / 2f;
            for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    float d = (Mathf.Abs(x - c) + Mathf.Abs(y - c)) / c;
                    float a = d > 1f ? 0f : (d > edgeFrom ? 1f : inner);
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
                }
            tex.Apply();
            return Sprite.Create(tex, new Rect(0, 0, N, N), new Vector2(0.5f, 0.5f), 1f);
        }

        static Sprite GridSprite() => gridSprite != null ? gridSprite : gridSprite = MakeDiamond(0.88f, 0.16f);
        static Sprite FillSprite() => fillSprite != null ? fillSprite : fillSprite = MakeDiamond(0.8f, 0.55f);

        static Sprite PixelSprite()
        {
            if (pixelSprite != null) return pixelSprite;
            var tex = new Texture2D(1, 1, TextureFormat.RGBA32, false) { filterMode = FilterMode.Point };
            tex.SetPixel(0, 0, Color.white);
            tex.Apply();
            pixelSprite = Sprite.Create(tex, new Rect(0, 0, 1, 1), new Vector2(0.5f, 0.5f), 1f);
            return pixelSprite;
        }
    }
}
