using System;
using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 8-bit 後花園（<see cref="GardenRoom.UsePixelGarden"/>）的花圃擺位：第 i 塊花圃在哪一格。
    /// 存檔 key：witch.garden.layout（花圃種了什麼仍在 witch.garden，index 0..11 不變 —— 這裡只管位置）。
    ///
    /// 規則：
    ///   · 一塊花圃＝一格（GardenRoomData 的等距格，64×32）。
    ///   · 不能擺的格：格盤外、門那格與門前那格、裝飾（樹、雨水桶）那格、別的花圃已經佔的格。
    ///   · 預設排法＝舊的 4×3 排法搬到 (PlotBlockGx, PlotBlockGy) 起的一塊（照 PlotOrder 開墾：6 塊＝3×2、9＝3×3、12＝4×3）。
    ///   · 讀檔時壞掉／缺的／超出範圍／跟別塊重疊的位置一律退回預設格；預設格被佔了就找最近的空格。
    ///     新開墾的花圃也一樣（預設格，被佔就最近的空格）。解析結果跟存檔不同時順手寫回去，位置才不會下次又變。
    ///   · 只看「已開墾」的花圃（還沒開墾的不佔格）；開墾數變了會自動重新解析。
    /// </summary>
    public static class GardenLayout
    {
        const string Key = "witch.garden.layout";

        /// <summary>這一格為什麼不能放（Ok＝可以）。</summary>
        public enum Block { Ok, OffGrid, Door, Decor, Occupied }

        [Serializable] class Entry { public int i; public int gx; public int gy; }
        [Serializable] class Shape { public List<Entry> plots = new(); }

        /// <summary>已開墾的花圃 index → 格。null ＝ 還沒解析。</summary>
        static Dictionary<int, Cell> cells;
        static int resolvedFor = -1;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { cells = null; resolvedFor = -1; }

        /// <summary>第 i 塊的預設格（同舊的 4×3 排法：col = i%4 往右下、row = i/4 往左下）。</summary>
        public static Cell DefaultCell(int i) =>
            new(GardenRoomData.PlotBlockGx + i % GardenData.PlotCols, GardenRoomData.PlotBlockGy + i / GardenData.PlotCols);

        /// <summary>這一格本身能不能擺花圃（不看別的花圃）：格盤內、不是門口兩格、不是裝飾。</summary>
        public static Block CellRule(int gx, int gy)
        {
            if (!GardenRoomData.InGrid(gx, gy)) return Block.OffGrid;
            if ((gx == GardenRoomData.DoorGx && gy == GardenRoomData.DoorGy)
                || (gx == GardenRoomData.DoorFrontGx && gy == GardenRoomData.DoorFrontGy)) return Block.Door;
            foreach (var d in GardenRoomData.Decor)
                if (d.Gx == gx && d.Gy == gy) return Block.Decor;
            return Block.Ok;
        }

        /// <summary>第 i 塊花圃現在在哪一格（還沒開墾的回預設格）。</summary>
        public static Cell CellOf(int i)
        {
            Ensure();
            return cells.TryGetValue(i, out var c) ? c : DefaultCell(i);
        }

        /// <summary>第 i 塊花圃的世界座標（格中心＝土壤磚頂面菱形的中心）。</summary>
        public static Vector2 PosOf(int i)
        {
            var c = CellOf(i);
            return GardenRoomData.CellCenter(c.gx, c.gy);
        }

        /// <summary>這一格上是哪一塊花圃（-1＝沒有）。</summary>
        public static int PlotAt(int gx, int gy)
        {
            Ensure();
            foreach (var kv in cells)
                if (kv.Value.gx == gx && kv.Value.gy == gy) return kv.Key;
            return -1;
        }

        /// <summary>第 i 塊能不能搬到 (gx,gy)。搬回自己原本那格算 Ok。</summary>
        public static Block Check(int i, int gx, int gy)
        {
            var r = CellRule(gx, gy);
            if (r != Block.Ok) return r;
            int other = PlotAt(gx, gy);
            return other >= 0 && other != i ? Block.Occupied : Block.Ok;
        }

        /// <summary>把第 i 塊搬到 (gx,gy) 並存檔；放不下回 false（什麼都不改）。</summary>
        public static bool Move(int i, int gx, int gy)
        {
            Ensure();
            if (!cells.ContainsKey(i) || Check(i, gx, gy) != Block.Ok) return false;
            var c = cells[i];
            if (c.gx == gx && c.gy == gy) return true;
            cells[i] = new Cell(gx, gy);
            Save();
            return true;
        }

        /// <summary>
        /// 跟第 i 塊十字相鄰（上下左右四格）的已開墾花圃（不含自己）。
        /// 澆水壺升級一階（Garden.WaterTargets 的 spread 1）用：看的是**實際擺的格子**，不是舊的固定 4×3 編號。
        /// </summary>
        public static List<int> Neighbours(int i, List<int> open)
        {
            var outList = new List<int>();
            var c = CellOf(i);
            foreach (var k in open)
            {
                if (k == i) continue;
                var d = CellOf(k);
                if (Mathf.Abs(d.gx - c.gx) + Mathf.Abs(d.gy - c.gy) == 1) outList.Add(k);
            }
            return outList;
        }

        // ──────────── 讀檔／解析 ────────────

        static void Ensure()
        {
            int n = Garden.UnlockedCount();
            if (cells != null && resolvedFor == n) return;
            Resolve(n);
        }

        static long K(Cell c) => ((long)c.gx << 32) ^ (uint)c.gy;

        static void Resolve(int n)
        {
            var saved = Load();
            var result = new Dictionary<int, Cell>();
            var taken = new HashSet<long>();
            var open = Garden.UnlockedPlots();

            // ① 存檔裡合法的先佔（照開墾順序：先開的那塊優先；重疊的後者退回預設）
            foreach (var i in open)
                if (saved.TryGetValue(i, out var c) && CellRule(c.gx, c.gy) == Block.Ok && taken.Add(K(c)))
                    result[i] = c;

            // ② 其餘（沒存、存壞、被佔）：預設格；被佔就找最近的空格
            bool changed = false;
            foreach (var i in open)
            {
                if (result.ContainsKey(i)) continue;
                var want = DefaultCell(i);
                var c = CellRule(want.gx, want.gy) == Block.Ok && !taken.Contains(K(want)) ? want : Nearest(want, taken);
                if (c.gx < 0) continue;            // 整片都滿了（12 塊不可能發生）
                result[i] = c;
                taken.Add(K(c));
                changed = true;
            }
            // 存檔裡有、但這次沒用到（壞的、重疊的、還沒開墾的）也算「不一樣」→ 寫回乾淨的版本
            if (saved.Count != result.Count) changed = true;

            cells = result;
            resolvedFor = n;
            if (changed) Save();
        }

        /// <summary>離 from 最近（曼哈頓距離；同距離時照掃描順序）的可擺空格；沒有回 (-1,-1)。</summary>
        static Cell Nearest(Cell from, HashSet<long> taken)
        {
            var best = new Cell(-1, -1);
            int bestD = int.MaxValue;
            for (int gy = 0; gy < GardenRoomData.Rows; gy++)
                for (int gx = 0; gx < GardenRoomData.Cols; gx++)
                {
                    var c = new Cell(gx, gy);
                    if (CellRule(gx, gy) != Block.Ok || taken.Contains(K(c))) continue;
                    int d = Mathf.Abs(gx - from.gx) + Mathf.Abs(gy - from.gy);
                    if (d < bestD) { bestD = d; best = c; }
                }
            return best;
        }

        static Dictionary<int, Cell> Load()
        {
            var outDict = new Dictionary<int, Cell>();
            try
            {
                var raw = SaveManager.GetString(Key);
                if (!string.IsNullOrEmpty(raw))
                {
                    var o = JsonUtility.FromJson<Shape>(raw);
                    if (o?.plots != null)
                        foreach (var e in o.plots)
                            if (e != null && e.i >= 0 && e.i < GardenData.PlotCount && !outDict.ContainsKey(e.i))
                                outDict[e.i] = new Cell(e.gx, e.gy);
                }
            }
            catch { /* 壞檔就全部用預設 */ }
            return outDict;
        }

        static void Save()
        {
            var s = new Shape();
            var keys = new List<int>(cells.Keys);
            keys.Sort();
            foreach (var i in keys) s.plots.Add(new Entry { i = i, gx = cells[i].gx, gy = cells[i].gy });
            SaveManager.SetString(Key, JsonUtility.ToJson(s));
        }
    }
}
