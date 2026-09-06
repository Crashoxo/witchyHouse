using System;
using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>貨架上的一筆上架品。</summary>
    [Serializable]
    public class Listing
    {
        public string name;
        public int price;
        public int count;

        public Listing() { }
        public Listing(string name, int price, int count)
        { this.name = name; this.price = price; this.count = count; }
    }

    /// <summary>
    /// 玩家商店的「貨架」資料：把材料上架、定價，等顧客上門買。
    /// 純資料模組，不含 UI（面板在 ShopManagePanel）。
    ///
    /// ⚠️ 上架的**種類數**受「貨架」升級限制（Upgrades.ShelfCap），同名可以無限疊加。
    /// </summary>
    public static class ShopStock
    {
        const string Key = "witch.shop.listings";

        [Serializable] class Shape { public List<Listing> items = new(); }

        static List<Listing> listings;

        static List<Listing> All
        {
            get
            {
                if (listings == null)
                {
                    listings = new List<Listing>();
                    try
                    {
                        var o = JsonUtility.FromJson<Shape>(SaveManager.GetString(Key));
                        if (o?.items != null)
                            foreach (var l in o.items)
                                if (l != null && !string.IsNullOrEmpty(l.name) && l.count > 0)
                                    listings.Add(l);
                    }
                    catch { /* 壞檔就當空架子 */ }
                }
                return listings;
            }
        }

        static void Save() => SaveManager.SetString(Key, JsonUtility.ToJson(new Shape { items = All }));

        static Listing Find(string name)
        {
            foreach (var l in All) if (l.name == name) return l;
            return null;
        }

        /// <summary>目前貨架上的所有上架品（複本；改動請用下面的方法）。</summary>
        public static List<Listing> Listings()
        {
            var outList = new List<Listing>(All.Count);
            foreach (var l in All) outList.Add(new Listing(l.name, l.price, l.count));
            return outList;
        }

        /// <summary>貨架上有幾種東西。</summary>
        public static int Types => All.Count;

        /// <summary>某材料的建議售價。</summary>
        public static int SuggestedPrice(string name) =>
            Prices.BasePrice.TryGetValue(name, out var p) ? p : 10;

        /// <summary>能不能再上架這個？（同名可疊加；新種類受貨架上限限制）</summary>
        public static bool CanAdd(string name) =>
            Find(name) != null || All.Count < Upgrades.ShelfCap();

        /// <summary>上架一個：同名疊加、否則新增（新增時用建議售價）。超過貨架上限回 false。</summary>
        public static bool Add(string name)
        {
            var l = Find(name);
            if (l != null)
            {
                l.count += 1;
            }
            else
            {
                if (All.Count >= Upgrades.ShelfCap()) return false;
                All.Add(new Listing(name, SuggestedPrice(name), 1));
            }
            Save();
            return true;
        }

        /// <summary>撤下一個：數量歸零就移除。回傳是否成功。</summary>
        public static bool RemoveOne(string name)
        {
            for (int i = 0; i < All.Count; i++)
            {
                if (All[i].name != name) continue;
                All[i].count -= 1;
                if (All[i].count <= 0) All.RemoveAt(i);
                Save();
                return true;
            }
            return false;
        }

        /// <summary>某上架品目前有幾個。</summary>
        public static int CountOf(string name) => Find(name)?.count ?? 0;

        /// <summary>某上架品的售價（沒上架回 0）。</summary>
        public static int PriceOf(string name) => Find(name)?.price ?? 0;

        /// <summary>調整某上架品的售價（最低 1）。</summary>
        public static void SetPrice(string name, float price)
        {
            var l = Find(name);
            if (l == null) return;
            l.price = Mathf.Max(1, Mathf.RoundToInt(price));
            Save();
        }

        /// <summary>賣掉一個（顧客成交用）：回傳售價，賣不掉回 0。</summary>
        public static int SellOne(string name)
        {
            var l = Find(name);
            if (l == null || l.count <= 0) return 0;
            int price = l.price;
            RemoveOne(name);
            return price;
        }
    }
}
