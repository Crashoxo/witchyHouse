using System;
using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 上架商品「玩家指定的陳列位置」（存檔 key: witch.shop.display）：商品名 → 哪一件家具（uid）、從第幾個位子開始。
    ///
    /// 為什麼另開一個 key、不加在 Listing 上：Listing 是「賣什麼、賣多少錢、剩幾個」的經營資料，
    /// 顧客系統、離店成交、上架面板都在讀寫它；擺在哪只是店面的樣子。分開存，改陳列不會動到經營資料，
    /// 舊存檔也不用遷移（沒有這個 key ＝全部自動分配，跟以前一樣）。
    ///
    /// 位子編號（slot）＝ShopRoomView.SlotSequence 排出來的**畫面順序**（由上而下、每層由左而右，
    /// 翻面的家具每層倒過來排）—— 所以家具翻面之後，商品還是在畫面上同一層、同一側的位置。
    ///
    /// 規則（ShopRoomView.SpawnGoods 照這個擺）：
    ///   · 有指定、而且那件家具還擺著、位子有效又沒被先佔 → 擺在那裡
    ///   · 否則退回自動分配 —— 但**指定不刪**：家具收回托盤再擺回來（uid 不變）就恢復原位
    ///   · 商品下架（Listing 消失，包括賣完）→ 指定清掉（ShopStock.RemoveOne 呼叫 <see cref="Clear"/>）
    ///
    /// ⚠️ 一放下就存檔（跟家具一樣）；佈置模式按 Esc 時由 ShopRoomEditor 用 <see cref="Snapshot"/>／
    ///    <see cref="Restore"/> 整批還原成進場前的樣子。
    /// </summary>
    public static class ShopDisplay
    {
        const string Key = "witch.shop.display";

        [Serializable]
        public class Entry
        {
            public string name;
            /// <summary>家具的 PlacedFurniture.uid。</summary>
            public int uid;
            /// <summary>從那件家具的第幾個位子（畫面順序）開始擺。</summary>
            public int slot;

            public Entry() { }
            public Entry(string name, int uid, int slot) { this.name = name; this.uid = uid; this.slot = slot; }
        }

        [Serializable] class Shape { public List<Entry> items = new(); }

        static List<Entry> entries;

        static List<Entry> All
        {
            get
            {
                if (entries == null)
                {
                    entries = new List<Entry>();
                    try
                    {
                        var raw = SaveManager.GetString(Key);
                        if (!string.IsNullOrEmpty(raw))
                        {
                            var o = JsonUtility.FromJson<Shape>(raw);
                            if (o?.items != null)
                                foreach (var e in o.items)
                                    if (e != null && !string.IsNullOrEmpty(e.name) && e.uid > 0 && e.slot >= 0
                                        && Find(e.name) == null)          // 同名只留第一筆
                                        entries.Add(new Entry(e.name, e.uid, e.slot));
                        }
                    }
                    catch { /* 壞檔就當全部自動分配 */ }
                }
                return entries;
            }
        }

        static void Save() => SaveManager.SetString(Key, JsonUtility.ToJson(new Shape { items = All }));

        /// <summary>⚠️ 只在 entries 已經載好時呼叫（All 的載入迴圈裡用來去重）。</summary>
        static Entry Find(string name)
        {
            if (entries == null) return null;
            foreach (var e in entries) if (e.name == name) return e;
            return null;
        }

        /// <summary>這個商品有沒有玩家指定的位置。</summary>
        public static bool TryGet(string name, out int uid, out int slot)
        {
            _ = All;
            var e = Find(name);
            uid = e?.uid ?? 0;
            slot = e?.slot ?? 0;
            return e != null;
        }

        /// <summary>
        /// 指定（或改）一個商品的位置並存檔。**改過的排到最前面** —— 清單順序＝擺放優先順序
        /// （ShopRoomView.SpawnGoods 第①輪照這個順序擺）：兩個指定搶同一格時，玩家最後動的那個贏。
        /// </summary>
        public static void Set(string name, int uid, int slot)
        {
            if (string.IsNullOrEmpty(name) || uid <= 0 || slot < 0) return;
            _ = All;
            var e = Find(name);
            if (e != null && e.uid == uid && e.slot == slot) return;   // 沒變就不寫檔（也不改優先順序）
            if (e != null) All.Remove(e);
            All.Insert(0, new Entry(name, uid, slot));
            Save();
        }

        /// <summary>清掉一個商品的指定（下架／賣完時）。</summary>
        public static void Clear(string name)
        {
            _ = All;
            for (int i = 0; i < All.Count; i++)
                if (All[i].name == name) { All.RemoveAt(i); Save(); return; }
        }

        /// <summary>
        /// 清掉「已經不在上架清單裡」的指定（ShopRoomView 每次擺商品時順手掃一次）。
        /// 正常情況 ShopStock.RemoveOne 當下就清了；這裡補的是 Esc 還原快照把已下架商品的指定帶回來之類的邊角。
        /// </summary>
        public static void Prune(HashSet<string> listed)
        {
            bool changed = false;
            for (int i = All.Count - 1; i >= 0; i--)
                if (!listed.Contains(All[i].name)) { All.RemoveAt(i); changed = true; }
            if (changed) Save();
        }

        /// <summary>目前所有指定的深複本，照優先順序（最近改的在前）。佈置模式進場時的快照、SpawnGoods 第①輪都用它。</summary>
        public static List<Entry> Snapshot()
        {
            var outList = new List<Entry>(All.Count);
            foreach (var e in All) outList.Add(new Entry(e.name, e.uid, e.slot));
            return outList;
        }

        /// <summary>整批覆寫成某份快照並存檔（佈置模式按 Esc）。</summary>
        public static void Restore(List<Entry> snap)
        {
            entries = new List<Entry>();
            if (snap != null)
                foreach (var e in snap)
                    if (e != null && Find(e.name) == null) entries.Add(new Entry(e.name, e.uid, e.slot));
            Save();
        }
    }
}
