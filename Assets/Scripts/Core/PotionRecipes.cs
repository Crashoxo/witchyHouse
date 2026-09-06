using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 藥水配方的「製作邏輯」。配方內容在 Data.Recipes，這裡只管扣料與產出。
    /// </summary>
    public static class PotionRecipes
    {
        /// <summary>一次最多熬幾份（面板的「最大」也吃這個上限）。</summary>
        public const int MaxBatch = 10;

        public static Recipe Get(string name) => Recipes.ByName(name);

        /// <summary>
        /// 材料是否足夠做 qty 份。
        /// ⚠️ 算的是**背包＋倉庫**：材料一進城鎮就自動歸位到倉庫，只看背包的話回到鍋爐前
        ///    會變成什麼都做不了（倉庫就在同一個房間的木箱裡）。
        /// </summary>
        public static bool CanCraft(Recipe r, int qty = 1)
        {
            if (r == null || qty <= 0) return false;
            foreach (var kv in r.Inputs)
                if (Storage.AvailableOf(kv.Key) < kv.Value * qty) return false;
            return true;
        }

        /// <summary>現在的材料最多能做幾份（上限 MaxBatch）。</summary>
        public static int MaxCraftable(Recipe r)
        {
            if (r == null) return 0;
            int n = MaxBatch;
            foreach (var kv in r.Inputs)
                n = Mathf.Min(n, Storage.AvailableOf(kv.Key) / kv.Value);
            return Mathf.Max(0, n);
        }

        /// <summary>只扣材料（開始熬煮時呼叫）。材料不足回 false、不扣。先扣背包再扣倉庫。</summary>
        public static bool Consume(Recipe r, int qty = 1)
        {
            if (!CanCraft(r, qty)) return false;
            foreach (var kv in r.Inputs) Storage.TakeAny(kv.Key, kv.Value * qty);
            return true;
        }

        /// <summary>只把成品加進背包（熬煮動畫結束時呼叫）；背包種類滿了就先放進倉庫，別弄丟。</summary>
        public static void Produce(Recipe r, int qty = 1)
        {
            if (r == null || qty <= 0) return;
            if (!Inventory.Add(r.Name, qty)) Storage.Add(r.Name, qty);
        }

        /// <summary>一次做完：扣料＋產出（Consume 成功才 Produce）。</summary>
        public static bool Craft(Recipe r, int qty = 1)
        {
            if (!Consume(r, qty)) return false;
            Produce(r, qty);
            return true;
        }
    }
}
