using System;
using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>背包／倉庫裡的一疊東西。</summary>
    [Serializable]
    public class Stack
    {
        public string name;
        public int count;

        public Stack() { }
        public Stack(string name, int count) { this.name = name; this.count = count; }
        public Stack Clone() => new(name, count);
    }

    /// <summary>
    /// Stack 清單的存檔序列化。
    ///
    /// ⚠️ Unity 的 JsonUtility **不能把 List&lt;T&gt; 直接當根物件**序列化，一定要包一層。
    ///    Cocos 版是 JSON.stringify(stock) 直接吐出陣列 —— 存檔格式因此不同，
    ///    但兩邊本來就是各自獨立的存檔，不需要互通。
    /// </summary>
    static class StackListJson
    {
        [Serializable] class Wrap { public List<Stack> items = new(); }

        public static string ToJson(List<Stack> list) => JsonUtility.ToJson(new Wrap { items = list });

        /// <summary>只收合法的堆疊，避免壞存檔炸掉（沿用 Cocos 版的過濾條件）。</summary>
        public static List<Stack> FromJson(string raw)
        {
            if (string.IsNullOrEmpty(raw)) return new List<Stack>();
            try
            {
                var w = JsonUtility.FromJson<Wrap>(raw);
                var outList = new List<Stack>();
                if (w?.items != null)
                    foreach (var s in w.items)
                        if (s != null && !string.IsNullOrEmpty(s.name) && s.count > 0) outList.Add(s);
                return outList;
            }
            catch { return new List<Stack>(); }      // 壞檔就當空的
        }
    }

    /// <summary>
    /// 背包「資料」。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版的 Inventory.ts 把兩件事放在同一個檔：
    ///   (a) module 層的 `stock` 陣列＝資料，換場景不會被清掉
    ///   (b) 一個 Component＝畫面下排那排格子的 UI
    /// 這裡只搬 (a)。C# 的 static 欄位跨場景本來就存在，效果跟 module 變數一樣。
    /// UI 那半留給之後的 InventoryHud —— 原本就是概念上分開的兩件事，
    /// 分檔之後 add/remove 的邏輯也不必再跟節點生命週期綁在一起。
    ///
    /// 背包的上限是「幾**種**東西」（同名無限疊加），不是幾個格子裝幾個。
    /// </summary>
    public static class Inventory
    {
        const string StockKey = "witch.stock";

        static List<Stack> stock;

        static List<Stack> Stock
        {
            get
            {
                stock ??= StackListJson.FromJson(SaveManager.GetString(StockKey));
                return stock;
            }
        }

        static void Save() => SaveManager.SetString(StockKey, StackListJson.ToJson(Stock));

        static Stack Find(string name)
        {
            foreach (var s in Stock) if (s.name == name) return s;
            return null;
        }

        /// <summary>目前內容（複本，改它不會動到真資料）。</summary>
        public static List<Stack> List()
        {
            var outList = new List<Stack>(Stock.Count);
            foreach (var s in Stock) outList.Add(s.Clone());
            return outList;
        }

        /// <summary>背包裡放了幾種東西。</summary>
        public static int Types => Stock.Count;

        /// <summary>某樣東西在背包裡有幾個。</summary>
        public static int CountOf(string name) => Find(name)?.count ?? 0;

        /// <summary>加入物品：先找同名的堆疊疊加，沒有就新增一堆；種類滿了回傳 false。</summary>
        public static bool Add(string name, int qty = 1)
        {
            if (qty <= 0) return false;
            var s = Find(name);
            if (s != null)
            {
                s.count += qty;
            }
            else
            {
                if (Stock.Count >= Upgrades.BagSlots())
                {
                    Debug.LogWarning($"[Inventory] 背包滿了，{name} 放不下");
                    return false;
                }
                Stock.Add(new Stack(name, qty));
            }
            Save();
            return true;
        }

        /// <summary>取出物品；數量不足回 false。</summary>
        public static bool Remove(string name, int qty = 1)
        {
            if (qty <= 0) return false;
            for (int i = 0; i < Stock.Count; i++)
            {
                if (Stock[i].name != name) continue;
                if (Stock[i].count < qty) return false;
                Stock[i].count -= qty;
                if (Stock[i].count == 0) Stock.RemoveAt(i);
                Save();
                return true;
            }
            return false;
        }
    }
}
