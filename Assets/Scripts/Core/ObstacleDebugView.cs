using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 碰撞的除錯顯示：按 F3 切換，把所有落地範圍（紅）、玩家腳底的碰撞圓（青）、
    /// 可走範圍（黃，地圖邊緣內縮後；藥水室是地板多邊形）、村民／小動物目前的路徑（綠，TownNav）畫在世界上，
    /// 排序在最上層。預設關閉。
    /// 給使用者截圖回報「哪裡卡住／哪裡穿過去」用。
    ///
    /// 用 LineRenderer（每個障礙一條、重複使用）—— 每幀只更新玩家那一圈的座標，不配置記憶體。
    /// 由 PlayerController 在有碰撞的場景（戶外、藥水室、店裡）喚起。
    /// </summary>
    public class ObstacleDebugView : MonoBehaviour
    {
        public static ObstacleDebugView Instance { get; private set; }

        public static ObstacleDebugView Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("ObstacleDebugView").AddComponent<ObstacleDebugView>();
        }

        const int Order = 30000;        // 天色色板 20000、路燈光暈 20100 之上
        const int CircleSegs = 24;
        const float Width = 2f;

        static readonly Color ShapeColor = new(1f, 0.2f, 0.2f, 0.95f);
        static readonly Color PlayerColor = new(0.2f, 1f, 1f, 1f);
        static readonly Color WalkColor = new(1f, 0.85f, 0.2f, 0.9f);
        static readonly Color PathColor = new(0.3f, 1f, 0.3f, 0.95f);
        readonly List<LineRenderer> pathLines = new();

        bool on;
        int builtVersion = -1;
        readonly List<LineRenderer> lines = new();
        LineRenderer playerRing, walkRect;
        readonly Vector3[] ring = new Vector3[CircleSegs];
        Transform player;
        Material mat;

        void Awake() { Instance = this; }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.F3))
            {
                on = !on;
                Debug.Log($"[Obstacles] 除錯顯示 {(on ? "開" : "關")}（F3）");
                if (!on) SetVisible(false);
            }
            if (!on) return;

            Obstacles.EnsureBuilt();
            if (builtVersion != Obstacles.Version) Rebuild();

            if (player != null && playerRing != null)
            {
                Vector3 c = player.position;
                for (int i = 0; i < CircleSegs; i++)
                {
                    float a = i * Mathf.PI * 2f / CircleSegs;
                    ring[i] = new Vector3(c.x + Mathf.Cos(a) * Data.ArtFootprints.PlayerRadius,
                                          c.y + Mathf.Sin(a) * Data.ArtFootprints.PlayerRadius, 0f);
                }
                playerRing.SetPositions(ring);
            }

            DrawNpcPaths();
        }

        /// <summary>
        /// 村民／小動物目前的路徑（TownNav.DebugPaths，綠線）。每幀照路點數更新，LineRenderer 重用、不配置記憶體。
        /// 給使用者截圖回報「哪個路人又穿牆了」用：線穿過紅框就是 TownNav 的 bug，線沒穿但人穿了就是走路那段的 bug。
        /// </summary>
        void DrawNpcPaths()
        {
            var paths = TownNav.DebugPaths;
            while (pathLines.Count < paths.Count)
            {
                var lr = MakeLine("npc-path", PathColor);
                lr.loop = false;
                pathLines.Add(lr);
            }
            for (int i = 0; i < pathLines.Count; i++)
            {
                var lr = pathLines[i];
                var path = i < paths.Count ? paths[i] : null;
                if (path == null || path.Count < 2) { lr.gameObject.SetActive(false); continue; }
                lr.gameObject.SetActive(true);
                lr.positionCount = path.Count;
                for (int k = 0; k < path.Count; k++) lr.SetPosition(k, new Vector3(path[k].x, path[k].y, 0f));
            }
        }

        void Rebuild()
        {
            builtVersion = Obstacles.Version;
            int n = Obstacles.Count;
            while (lines.Count < n) lines.Add(MakeLine("shape", ShapeColor));
            for (int i = 0; i < lines.Count; i++)
            {
                var lr = lines[i];
                if (i >= n) { lr.gameObject.SetActive(false); continue; }
                lr.gameObject.SetActive(true);
                Obstacles.GetShape(i, out var c, out var h, out var ellipse);
                var poly = Obstacles.ShapePoly(i);
                if (poly != null)
                {
                    lr.positionCount = poly.Length;
                    for (int k = 0; k < poly.Length; k++) lr.SetPosition(k, new Vector3(poly[k].x, poly[k].y, 0f));
                }
                else if (ellipse)
                {
                    lr.positionCount = CircleSegs;
                    for (int k = 0; k < CircleSegs; k++)
                    {
                        float a = k * Mathf.PI * 2f / CircleSegs;
                        lr.SetPosition(k, new Vector3(c.x + Mathf.Cos(a) * h.x, c.y + Mathf.Sin(a) * h.y, 0f));
                    }
                }
                else
                {
                    lr.positionCount = 4;
                    lr.SetPosition(0, new Vector3(c.x - h.x, c.y - h.y, 0f));
                    lr.SetPosition(1, new Vector3(c.x + h.x, c.y - h.y, 0f));
                    lr.SetPosition(2, new Vector3(c.x + h.x, c.y + h.y, 0f));
                    lr.SetPosition(3, new Vector3(c.x - h.x, c.y + h.y, 0f));
                }
            }

            if (playerRing == null)
            {
                playerRing = MakeLine("player", PlayerColor);
                playerRing.positionCount = CircleSegs;
            }
            if (walkRect == null) walkRect = MakeLine("walk", WalkColor);
            var wp = Obstacles.WalkPolygon;
            if (wp != null)
            {
                walkRect.positionCount = wp.Length;
                for (int k = 0; k < wp.Length; k++) walkRect.SetPosition(k, new Vector3(wp[k].x, wp[k].y, 0f));
            }
            else
            {
                var w = Obstacles.WalkRect;
                walkRect.positionCount = 4;
                walkRect.SetPosition(0, new Vector3(w.xMin, w.yMin, 0f));
                walkRect.SetPosition(1, new Vector3(w.xMax, w.yMin, 0f));
                walkRect.SetPosition(2, new Vector3(w.xMax, w.yMax, 0f));
                walkRect.SetPosition(3, new Vector3(w.xMin, w.yMax, 0f));
            }
            SetVisible(true);
        }

        void SetVisible(bool v)
        {
            int n = v ? Obstacles.Count : 0;
            for (int i = 0; i < lines.Count; i++) lines[i].gameObject.SetActive(i < n);
            if (playerRing != null) playerRing.gameObject.SetActive(v);
            if (walkRect != null) walkRect.gameObject.SetActive(v);
            if (!v) foreach (var lr in pathLines) lr.gameObject.SetActive(false);
        }

        LineRenderer MakeLine(string name, Color col)
        {
            if (mat == null) mat = new Material(Shader.Find("Sprites/Default"));
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var lr = go.AddComponent<LineRenderer>();
            lr.useWorldSpace = true;
            lr.loop = true;
            lr.widthMultiplier = Width;
            lr.numCapVertices = 0;
            lr.sharedMaterial = mat;
            lr.startColor = lr.endColor = col;
            lr.sortingOrder = Order;
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;
            return lr;
        }
    }
}
