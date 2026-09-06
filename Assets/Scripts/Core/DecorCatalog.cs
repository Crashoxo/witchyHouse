using System;
using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>擺在店裡的一件裝飾（房間內的世界座標，不是格座標）。</summary>
    [Serializable]
    public class PlacedDecor
    {
        public string id;
        public float x, y;
        public bool flip;

        public PlacedDecor() { }
        public PlacedDecor(string id, float x, float y, bool flip = false)
        { this.id = id; this.x = x; this.y = y; this.flip = flip; }
    }

    /// <summary>
    /// 裝飾品的資料層：
    ///   - 目錄 Decor.Catalog：花店賣的 19 種裝飾（id / 中文名 / 售價）。
    ///   - owned：每種買了幾個。
    ///   - placed：目前擺在自己店裡的實例（id + 房間內座標 x,y）。
    /// 「托盤裡可擺的數量」＝ owned − 已擺出的同 id 數量。純裝飾，不影響數值。
    ///
    /// ⚠️ 裝飾品用的是**自由座標 (x, y)**，不是家具那套格座標 (gx, gy)——
    ///    裝飾可以擺在桌上、架上任何位置，不吃格盤。別把兩者搞混。
    /// </summary>
    public static class DecorCatalog
    {
        const string OwnKey = "witch.decor.owned";
        const string PlacedKey = "witch.decor.placed";

        /// <summary>
        /// 沒有指定 Scale 的裝飾用這個縮放。
        /// 最早那十六款是從大張圖切下來的，不縮會比房間還大（對應原版 DecorRoom.decorScale）。
        /// </summary>
        public const float DefaultScale = 0.4f;

        [Serializable] class OwnedShape { public List<string> keys = new(); public List<int> counts = new(); }
        [Serializable] class PlacedShape { public List<PlacedDecor> items = new(); }

        static OwnedShape owned;
        static PlacedShape placed;

        static OwnedShape Owned
        {
            get
            {
                if (owned == null)
                {
                    try { owned = JsonUtility.FromJson<OwnedShape>(SaveManager.GetString(OwnKey)); }
                    catch { owned = null; }
                    owned ??= new OwnedShape();
                }
                return owned;
            }
        }

        static PlacedShape Placed
        {
            get
            {
                if (placed == null)
                {
                    try { placed = JsonUtility.FromJson<PlacedShape>(SaveManager.GetString(PlacedKey)); }
                    catch { placed = null; }
                    placed ??= new PlacedShape();
                    // 壞檔防禦：只留認得的 id
                    placed.items.RemoveAll(p => p == null || Decor.ById(p.id) == null);
                }
                return placed;
            }
        }

        static void SaveOwned() => SaveManager.SetString(OwnKey, JsonUtility.ToJson(Owned));
        static void SavePlaced() => SaveManager.SetString(PlacedKey, JsonUtility.ToJson(Placed));

        public static DecorDef Def(string id) => Decor.ById(id);

        public static int OwnedCount(string id)
        {
            int i = Owned.keys.IndexOf(id);
            return i < 0 ? 0 : Owned.counts[i];
        }

        public static int PlacedCountOf(string id)
        {
            int n = 0;
            foreach (var p in Placed.items) if (p.id == id) n++;
            return n;
        }

        /// <summary>托盤裡（買了但還沒擺出去）可用的數量。</summary>
        public static int UnplacedCount(string id) => Mathf.Max(0, OwnedCount(id) - PlacedCountOf(id));

        /// <summary>從花店買一個：金幣夠才成交。</summary>
        public static bool Buy(string id)
        {
            var d = Decor.ById(id);
            if (d == null || Wallet.Gold < d.Price) return false;
            Wallet.Add(-d.Price);
            DailyLog.RecordSpend(d.Price);
            int i = Owned.keys.IndexOf(id);
            if (i < 0) { Owned.keys.Add(id); Owned.counts.Add(1); }
            else Owned.counts[i]++;
            SaveOwned();
            return true;
        }

        /// <summary>目前擺出來的清單（複本，外部別直接改）。</summary>
        public static List<PlacedDecor> PlacedList()
        {
            var outList = new List<PlacedDecor>(Placed.items.Count);
            foreach (var p in Placed.items) outList.Add(new PlacedDecor(p.id, p.x, p.y, p.flip));
            return outList;
        }

        /// <summary>整批覆寫已擺清單並存檔（佈置模式結束時用）。</summary>
        public static void SetPlaced(List<PlacedDecor> list)
        {
            Placed.items = new List<PlacedDecor>();
            foreach (var p in list) Placed.items.Add(new PlacedDecor(p.id, p.x, p.y, p.flip));
            SavePlaced();
        }

        /// <summary>擺一個到房間（需托盤還有存貨）；回傳新實例的 index，失敗回 -1。</summary>
        public static int Place(string id, float x, float y)
        {
            if (UnplacedCount(id) <= 0) return -1;
            Placed.items.Add(new PlacedDecor(id, x, y));
            SavePlaced();
            return Placed.items.Count - 1;
        }

        /// <summary>移動已擺出的實例。</summary>
        public static void Move(int index, float x, float y)
        {
            if (index < 0 || index >= Placed.items.Count) return;
            Placed.items[index].x = x;
            Placed.items[index].y = y;
            SavePlaced();
        }

        /// <summary>收回一個已擺出的實例（回到托盤，不退錢）。</summary>
        public static void RemoveAt(int index)
        {
            if (index < 0 || index >= Placed.items.Count) return;
            Placed.items.RemoveAt(index);
            SavePlaced();
        }
    }
}
