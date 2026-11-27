using System;
using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>擺在家裡（藥水室）的一件家具／燈／裝飾／地毯。</summary>
    [Serializable]
    public class PlacedHome
    {
        public string id;
        /// <summary>落腳點（世界座標）：吃格子的家具＝佔地前角；裝飾／地毯＝圖的正下方中央。</summary>
        public float x, y;
        public bool flip;

        public PlacedHome() { }
        public PlacedHome(string id, float x, float y, bool flip = false)
        { this.id = id; this.x = x; this.y = y; this.flip = flip; }

        public Vector2 Pos => new(x, y);
        public PlacedHome Clone() => new(id, x, y, flip);
    }

    /// <summary>
    /// 家裡擺了哪些東西（存檔 key: witch.home.layout，已列進 SaveManager.SaveKeys）——
    /// **純資料、靜態**（同 RoomLayout），不是場景物件：人在店裡、城鎮時，店裡的托盤／花店的「未擺」一樣要扣掉家裡擺的。
    ///
    /// ── 一件只能在一個地方 ──
    ///   擁有數只有一份（家具在 RoomLayout 的 witch.room、裝飾在 DecorCatalog 的 witch.decor.owned）。
    ///   「還沒擺」＝擁有 − 店裡擺出的 − 家裡擺出的：家裡這一份由這裡算，掛在
    ///   <see cref="RoomLayout.PlacedElsewhere"/>／<see cref="DecorCatalog.PlacedElsewhere"/> 兩個掛鉤上（遊戲一啟動就掛，跟哪個場景無關）。
    ///   所以店裡托盤、家裡托盤、花店都問同一支 Unplaced，數字一定對得起來。
    ///
    /// ── 存檔格式 ──
    ///   {"items":[{"id":"lamp_moon","x":-212.0,"y":-40.0,"flip":false}, …]}
    ///   讀檔很寬鬆：不認得的 id、不能擺家裡的（陳列類）、數字壞掉的、超過「擁有 − 店裡擺出的」那幾件 → 丟掉（＝回到托盤），
    ///   有丟就順手寫回。位置合不合法（房間改過、規則變嚴）要量房間，等進了藥水室由 HomeFurnishings 驗，不合的一樣退回托盤。
    ///
    /// ── 開關 ──
    ///   <see cref="HomeArrange.Enabled"/> 關掉時：掛鉤回 0（家裡擺的全部當成「還沒擺」，店裡托盤拿得到）、家裡不畫、R 沒作用；存檔不動。
    /// </summary>
    public static class HomeLayout
    {
        public const string Key = "witch.home.layout";

        [Serializable]
        class SaveShape { public List<PlacedHome> items = new(); }

        static SaveShape data;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { data = null; }

        /// <summary>遊戲一啟動就把兩個掛鉤掛上（人不在家裡時店裡也要扣掉家裡擺的）。</summary>
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void InstallHooks()
        {
            RoomLayout.PlacedElsewhere = CountForHooks;
            DecorCatalog.PlacedElsewhere = CountForHooks;
        }

        static int CountForHooks(string id) => HomeArrange.Enabled ? CountOf(id) : 0;

        static SaveShape Data
        {
            get { data ??= Load(); return data; }
        }

        static SaveShape Load()
        {
            var clean = new SaveShape();
            bool changed = false;
            try
            {
                var raw = SaveManager.GetString(Key);
                if (!string.IsNullOrEmpty(raw))
                {
                    var o = JsonUtility.FromJson<SaveShape>(raw);
                    if (o?.items != null)
                    {
                        var used = new Dictionary<string, int>();
                        foreach (var p in o.items)
                        {
                            if (!Acceptable(p, used)) { changed = true; continue; }
                            clean.items.Add(p.Clone());
                        }
                    }
                }
            }
            catch { changed = true; /* 壞檔就當空的 */ }
            // ⚠️ 不能呼叫 Save()：它讀的是 Data，而 Data 正在初始化（會無窮遞迴）
            if (changed) SaveManager.SetString(Key, JsonUtility.ToJson(clean));
            return clean;
        }

        /// <summary>這一筆收不收：認得、能擺家裡、數字正常、而且還有「沒擺在店裡」的那一件可以用。</summary>
        static bool Acceptable(PlacedHome p, Dictionary<string, int> used)
        {
            if (p == null || string.IsNullOrEmpty(p.id) || !Furnishings.CanPlaceAtHome(p.id)) return false;
            if (!Finite(p.x) || !Finite(p.y) || Mathf.Abs(p.x) > 4000f || Mathf.Abs(p.y) > 4000f) return false;
            used.TryGetValue(p.id, out int n);
            if (n >= OwnedMinusShop(p.id)) return false;      // 擁有的都在店裡了（或根本沒買）
            used[p.id] = n + 1;
            return true;
        }

        static bool Finite(float v) => !float.IsNaN(v) && !float.IsInfinity(v);

        /// <summary>擁有 − 店裡擺出的（不經過掛鉤，免得遞迴）。</summary>
        static int OwnedMinusShop(string id) => Furnishings.IsGrid(id)
            ? RoomLayout.OwnedCount(id) - RoomLayout.PlacedCountOf(id)
            : DecorCatalog.OwnedCount(id) - DecorCatalog.PlacedCountOf(id);

        static void Save() => SaveManager.SetString(Key, JsonUtility.ToJson(Data));

        // ──────────── 對外 API ────────────

        /// <summary>家裡擺了幾件這個 id（掛鉤用的就是它）。</summary>
        public static int CountOf(string id)
        {
            int n = 0;
            foreach (var p in Data.items) if (p.id == id) n++;
            return n;
        }

        /// <summary>還沒擺（店裡、家裡都沒擺）的數量 ＝ 家裡托盤能拿出來的。</summary>
        public static int Unplaced(string id) => Furnishings.IsGrid(id)
            ? RoomLayout.Unplaced(id)
            : DecorCatalog.UnplacedCount(id);

        public static int Count => Data.items.Count;

        /// <summary>第 i 件（直接是存檔裡那一份，別改；要改請用 <see cref="Move"/>）。</summary>
        public static PlacedHome At(int i) => i >= 0 && i < Data.items.Count ? Data.items[i] : null;

        /// <summary>全部的深複本。</summary>
        public static List<PlacedHome> Snapshot()
        {
            var outList = new List<PlacedHome>(Data.items.Count);
            foreach (var p in Data.items) outList.Add(p.Clone());
            return outList;
        }

        /// <summary>從托盤擺一件出來（沒有存貨回 false）。</summary>
        public static bool Add(string id, Vector2 pos, bool flip)
        {
            if (!Furnishings.CanPlaceAtHome(id) || Unplaced(id) <= 0) return false;
            Data.items.Add(new PlacedHome(id, pos.x, pos.y, flip));
            Save();
            return true;
        }

        /// <summary>搬動／翻面第 i 件。</summary>
        public static void Move(int i, Vector2 pos, bool flip)
        {
            var p = At(i);
            if (p == null) return;
            p.x = pos.x; p.y = pos.y; p.flip = flip;
            Save();
        }

        /// <summary>收回托盤（不退錢）。</summary>
        public static void RemoveAt(int i)
        {
            if (i < 0 || i >= Data.items.Count) return;
            Data.items.RemoveAt(i);
            Save();
        }

        /// <summary>只留 keep[i] 為 true 的那幾件（進房間時驗位置，不合法的退回托盤）。回傳丟了幾件。</summary>
        public static int KeepOnly(bool[] keep)
        {
            int dropped = 0;
            for (int i = Data.items.Count - 1; i >= 0; i--)
                if (i >= keep.Length || !keep[i]) { Data.items.RemoveAt(i); dropped++; }
            if (dropped > 0) Save();
            return dropped;
        }
    }
}
