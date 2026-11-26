using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 店裡顧客的「便宜尋路」：在 14×10 的格盤上做 BFS，避開家具佔的格子。
    ///
    /// 為什麼需要：顧客沒有碰撞，原本是從門口直線走到販售桌 —— 貨架一多，就會看到人穿過貨架。
    /// 女巫用的是 Obstacles 的多邊形碰撞（推牆滑動），那套是給「玩家即時操控」用的，
    /// 拿來替 NPC 找路既貴又不保證走得到；而店本來就是格子，格子 BFS 便宜又直觀。
    ///
    /// 用法：只在**設定目的地的那一刻**算一次（<see cref="Find"/>），回傳一串世界座標路點，
    /// 顧客沿路點走。⚠️ 不要每幀尋路 —— 也不需要：佈置模式改了家具之後，
    /// 下一次設定目的地自然就會用新的格子。走到一半／站著時家具被搬動：CustomerManager 比對
    /// <see cref="LayoutSignature"/>，變了就重新找路（站位被佔就換站位，走不到就離開）。
    ///
    /// 規則：
    ///   ● 八向走，但**斜走不能切角**（兩個直向鄰格都要空著）—— 兩件家具斜對角相碰時中間那條縫
    ///     跟女巫一樣過不去，畫面上也確實是頂著的（見 ShopRoom.FurnitureInset 的說明）。
    ///   ● 起點格就算被家具佔了也照樣出發（顧客站著的時候家具被搬到他腳下）。
    ///   ● 終點格被佔 → 改去離它最近的空格。
    ///   ● **找不到路**（例如家具把門口整個圍起來）→ 回傳 null，呼叫端改站別的位置或提早離開。
    ///     ⚠️ 舊版退回直線 —— 那就是「穿過家具」，使用者回報「路人走路不要穿牆」之後拿掉了。
    ///   ● 求出格子路徑後做一次「拉直」（string pulling）：能直線走到的路點就跳過，
    ///     不然人會沿著格子中心一格一格走鋸齒。
    ///   ● 「站得住」不只看點落在哪一格（<see cref="Standable"/>）：點在格子裡偏向一個被家具佔的鄰格、
    ///     或偏向地板外，超過 <see cref="EdgeClear"/>／<see cref="FloorEdgeClear"/> 就不行 ——
    ///     不然站位的亂數偏移、拉直後的斜線會貼著（看起來是踩進）貨架或牆腳。拉直的直線也用同一個判準取樣。
    /// </summary>
    public static class ShopPath
    {
        static readonly (int dx, int dy)[] Dirs =
        {
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1),
        };

        /// <summary>
        /// 家具佔的格子（每次呼叫都重建 —— 14×10 只有 140 格，比維護快取簡單也不會過期）。
        /// 要連續問很多點能不能站時，先拿一份再傳給 <see cref="Walkable(Vector2, bool[,])"/>。
        /// </summary>
        public static bool[,] BlockedCells() => Blocked();

        static bool[,] Blocked()
        {
            var b = new bool[ShopRoom.GridW, ShopRoom.GridH];
            foreach (var p in RoomLayout.PlacedList())
            {
                var (w, h) = p.Size;
                for (int c = 0; c < w; c++)
                    for (int r = 0; r < h; r++)
                    {
                        int gx = p.gx + c, gy = p.gy + r;
                        if (ShopRoom.InGrid(gx, gy)) b[gx, gy] = true;
                    }
            }
            return b;
        }

        /// <summary>這個點能不能站人（在地板格子上、而且那格沒有家具）。</summary>
        public static bool Walkable(Vector2 p) => Walkable(p, Blocked());

        public static bool Walkable(Vector2 p, bool[,] blocked)
        {
            var c = ShopRoom.WorldToTile(p.x, p.y);
            return ShopRoom.InGrid(c.gx, c.gy) && !blocked[c.gx, c.gy];
        }

        /// <summary>
        /// 點在格子裡往「被家具佔的鄰格」偏移最多多少格（格座標；格子中心 0、磚緣 0.5）。
        /// 0.25 ＝ 離家具那格的磚緣至少 0.25 格 —— 人的腳不會壓到貨架腳。
        /// </summary>
        public const float EdgeClear = 0.25f;
        /// <summary>往地板外偏移最多多少格 ＝ 0.5 − ShopRoom.FloorMargin（跟女巫的可走範圍同一條邊）。</summary>
        public const float FloorEdgeClear = 0.5f - ShopRoom.FloorMargin;

        /// <summary>
        /// 顧客站不站得住 p（比 <see cref="Walkable(Vector2, bool[,])"/> 嚴格）：
        /// 那格在地板上、沒有家具，而且點在格子裡往被佔的鄰格（含斜角）偏不超過 EdgeClear、往地板外偏不超過 FloorEdgeClear。
        /// 站位（CustomerManager.FreeSpotNear）與拉直的直線取樣都用它。
        /// </summary>
        public static bool Standable(Vector2 p, bool[,] blocked)
        {
            var g = ShopRoom.ToGrid(p.x, p.y);
            int cx = Mathf.RoundToInt(g.x), cy = Mathf.RoundToInt(g.y);
            if (!ShopRoom.InGrid(cx, cy) || blocked[cx, cy]) return false;
            float fx = g.x - cx, fy = g.y - cy;
            int sx = fx >= 0f ? 1 : -1, sy = fy >= 0f ? 1 : -1;
            if (!SideOk(cx + sx, cy, Mathf.Abs(fx), blocked)) return false;
            if (!SideOk(cx, cy + sy, Mathf.Abs(fy), blocked)) return false;
            // 斜角：兩個方向都偏得夠多時，斜對角那格也不能有家具
            if (Mathf.Abs(fx) > EdgeClear && Mathf.Abs(fy) > EdgeClear)
            {
                int dx = cx + sx, dy = cy + sy;
                if (ShopRoom.InGrid(dx, dy) && blocked[dx, dy]) return false;
            }
            return true;
        }

        /// <summary>往鄰格 (nx,ny) 偏了 off 格：鄰格在地板外看 FloorEdgeClear、有家具看 EdgeClear。</summary>
        static bool SideOk(int nx, int ny, float off, bool[,] blocked)
        {
            if (!ShopRoom.InGrid(nx, ny)) return off <= FloorEdgeClear;
            return !blocked[nx, ny] || off <= EdgeClear;
        }

        /// <summary>離 p 最近的空格中心（p 那格空著就是那格）；整個地板都滿了回傳 null。</summary>
        public static Vector2? NearestFreeCenter(Vector2 p, bool[,] blocked)
        {
            var c = ShopRoom.WorldToTile(p.x, p.y);
            c = new Cell(Mathf.Clamp(c.gx, 0, ShopRoom.GridW - 1), Mathf.Clamp(c.gy, 0, ShopRoom.GridH - 1));
            if (!blocked[c.gx, c.gy]) return ShopRoom.TileCenter(c.gx, c.gy);
            if (NearestFree(c, blocked, out var f)) return ShopRoom.TileCenter(f.gx, f.gy);
            return null;
        }

        /// <summary>
        /// 家具擺設的指紋（位置與轉向後的佔地）—— CustomerManager 每隔一小段時間比一次，
        /// 變了就讓走到一半／站著的顧客重新找路。（RoomLayout 沒有版本號；家具頂多幾十件，算一次很便宜。）
        /// </summary>
        public static int LayoutSignature()
        {
            unchecked
            {
                int h = 17;
                foreach (var p in RoomLayout.PlacedList())
                {
                    var (w, d) = p.Size;
                    h = h * 31 + p.gx;
                    h = h * 31 + p.gy;
                    h = h * 31 + w;
                    h = h * 31 + d;
                }
                return h;
            }
        }

        /// <summary>
        /// 從 from 走到 to 的路點（世界座標，不含起點，最後一點是終點）。
        /// **找不到路時回傳 null**（不要退回直線 —— 那就是穿過家具）；呼叫端改站別處或離開。
        /// </summary>
        public static List<Vector2> Find(Vector2 from, Vector2 to)
        {
            var blocked = Blocked();

            var s = ShopRoom.WorldToTile(from.x, from.y);
            var g = ShopRoom.WorldToTile(to.x, to.y);
            // 起點在地板格外（理論上不會：顧客從門口那格進來）→ 夾回最近的格子當起點，讓他走回來
            s = new Cell(Mathf.Clamp(s.gx, 0, ShopRoom.GridW - 1), Mathf.Clamp(s.gy, 0, ShopRoom.GridH - 1));
            if (!ShopRoom.InGrid(g.gx, g.gy)) return null;          // 目的地在地板外：不去

            // 終點在家具裡 → 換成最近的空格中心；空格但貼家具／地板邊太近 → 換成那格中心
            Vector2 end = to;
            if (blocked[g.gx, g.gy])
            {
                if (!NearestFree(g, blocked, out g)) return null;
                end = ShopRoom.TileCenter(g.gx, g.gy);
            }
            else if (!Standable(end, blocked)) end = ShopRoom.TileCenter(g.gx, g.gy);
            if (s.gx == g.gx && s.gy == g.gy) return new List<Vector2> { end };

            // ── BFS ──
            int W = ShopRoom.GridW, H = ShopRoom.GridH;
            var prev = new int[W * H];
            for (int i = 0; i < prev.Length; i++) prev[i] = -2;     // -2＝還沒到過
            var q = new Queue<int>();
            int sIdx = s.gx + s.gy * W, gIdx = g.gx + g.gy * W;
            prev[sIdx] = -1;
            q.Enqueue(sIdx);
            bool found = false;
            while (q.Count > 0)
            {
                int cur = q.Dequeue();
                if (cur == gIdx) { found = true; break; }
                int cx = cur % W, cy = cur / W;
                foreach (var (dx, dy) in Dirs)
                {
                    int nx = cx + dx, ny = cy + dy;
                    if (!ShopRoom.InGrid(nx, ny) || blocked[nx, ny]) continue;
                    // 斜走不切角：兩個直向鄰格都要空著
                    if (dx != 0 && dy != 0 && (blocked[cx + dx, cy] || blocked[cx, cy + dy])) continue;
                    int ni = nx + ny * W;
                    if (prev[ni] != -2) continue;
                    prev[ni] = cur;
                    q.Enqueue(ni);
                }
            }
            if (!found) return null;          // 被圍起來了：呼叫端改站別處或離開（不走直線穿家具）

            // ── 還原格子路徑（終點 → 起點，再反轉）──
            var cells = new List<int>();
            for (int i = gIdx; i >= 0; i = prev[i]) cells.Add(i);
            cells.Reverse();

            // 路點：起點（真實位置）＋ 中間各格中心 ＋ 終點（真實位置）
            var pts = new List<Vector2> { from };
            for (int k = 1; k < cells.Count - 1; k++)
                pts.Add(ShopRoom.TileCenter(cells[k] % W, cells[k] / W));
            pts.Add(end);

            // ── 拉直：從目前的點往後找「最遠一個能直線到的點」──
            var outList = new List<Vector2>();
            int at = 0;
            while (at < pts.Count - 1)
            {
                int next = at + 1;
                for (int j = pts.Count - 1; j > at + 1; j--)
                    if (LineClear(pts[at], pts[j], blocked, s)) { next = j; break; }
                outList.Add(pts[next]);
                at = next;
            }
            return outList;
        }

        /// <summary>
        /// a→b 的直線有沒有穿過家具、貼到家具、或走出地板（每 6px 取樣一次，判準＝<see cref="Standable"/>）。
        /// 起點格例外（顧客可能正站在剛被搬來的家具上、或貼著家具站著，要讓他走得出來）。
        /// </summary>
        static bool LineClear(Vector2 a, Vector2 b, bool[,] blocked, Cell start)
        {
            float len = Vector2.Distance(a, b);
            int n = Mathf.Max(1, Mathf.CeilToInt(len / 6f));
            for (int i = 1; i <= n; i++)
            {
                var p = Vector2.Lerp(a, b, i / (float)n);
                var c = ShopRoom.WorldToTile(p.x, p.y);
                if (!ShopRoom.InGrid(c.gx, c.gy)) return false;
                if (c.gx == start.gx && c.gy == start.gy) continue;
                if (!Standable(p, blocked)) return false;
            }
            return true;
        }

        /// <summary>離 c 最近的空格（一圈一圈往外找）。</summary>
        static bool NearestFree(Cell c, bool[,] blocked, out Cell found)
        {
            for (int rad = 1; rad < Mathf.Max(ShopRoom.GridW, ShopRoom.GridH); rad++)
            {
                float best = float.MaxValue;
                found = c;
                for (int gx = c.gx - rad; gx <= c.gx + rad; gx++)
                    for (int gy = c.gy - rad; gy <= c.gy + rad; gy++)
                    {
                        if (Mathf.Max(Mathf.Abs(gx - c.gx), Mathf.Abs(gy - c.gy)) != rad) continue;
                        if (!ShopRoom.InGrid(gx, gy) || blocked[gx, gy]) continue;
                        float d = (gx - c.gx) * (gx - c.gx) + (gy - c.gy) * (gy - c.gy);
                        if (d < best) { best = d; found = new Cell(gx, gy); }
                    }
                if (best < float.MaxValue) return true;
            }
            found = c;
            return false;
        }
    }
}
