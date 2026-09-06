using System.Collections.Generic;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 玩家錢包（金幣）。金額存在 static 欄位（換場景保留），並透過 SaveManager 存檔 ——
    /// 關掉遊戲再開，金幣還在。賣東西時 Add()，Hud 常駐顯示讀 Gold。
    /// </summary>
    public static class Wallet
    {
        const string Key = "witch.gold";

        static int? gold;

        public static int Gold
        {
            get
            {
                if (gold == null)
                {
                    var v = SaveManager.GetString(Key);
                    gold = int.TryParse(v, out var n) ? n : 0;
                }
                return gold.Value;
            }
        }

        static void Save() => SaveManager.SetString(Key, Gold.ToString());

        public static void Add(int amount) { gold = Gold + amount; Save(); }
        public static void Set(int amount) { gold = amount; Save(); }
    }

    /// <summary>
    /// 店裡的倉庫（純資料，仿 Inventory）。
    ///
    /// 為什麼要有它：背包的上限是「能放幾**種**東西」（同名無限疊加），而遊戲裡的道具種類
    /// 已經有二十幾種 —— 材料、種子、花、藥水。背包再怎麼升級也塞不下全部，所以採集回來的
    /// 東西要有地方放。倉庫容量大得多，走到店裡左邊的櫥櫃按 E 就能存取。
    ///
    /// ⚠️ 上架與煉藥的材料仍然是從**背包**拿的（要用什麼就先從倉庫取回來），這樣「這趟出門
    ///    要帶什麼」才有取捨。日後想讓貨架/鍋爐直接吃倉庫，改那幾支的取料來源即可。
    /// </summary>
    public static class Storage
    {
        const string Key = "witch.storage";

        /// <summary>倉庫能放幾種東西（同名一樣無限疊加）。</summary>
        const int CapacityConst = 40;

        static List<Stack> chest;

        static List<Stack> Chest
        {
            get
            {
                chest ??= StackListJson.FromJson(SaveManager.GetString(Key));
                return chest;
            }
        }

        static void Save() => SaveManager.SetString(Key, StackListJson.ToJson(Chest));

        static Stack Find(string name)
        {
            foreach (var s in Chest) if (s.name == name) return s;
            return null;
        }

        /// <summary>
        /// 進城鎮時會自動歸位的東西＝採集材料與後花園的花。
        /// 種子留在背包（要拿去種），藥水也留著（要拿去上架賣給顧客）。
        /// </summary>
        static readonly HashSet<string> AutoStash = BuildAutoStash();

        static HashSet<string> BuildAutoStash()
        {
            var set = new HashSet<string>(Items.Materials);
            foreach (var f in GardenData.Flowers) set.Add(f.Flower);
            return set;
        }

        /// <summary>種類上限。</summary>
        public static int Capacity() => CapacityConst;

        /// <summary>現在放了幾種。</summary>
        public static int Types() => Chest.Count;

        /// <summary>目前內容（複本，改它不會動到真資料）。</summary>
        public static List<Stack> List()
        {
            var outList = new List<Stack>(Chest.Count);
            foreach (var s in Chest) outList.Add(s.Clone());
            return outList;
        }

        /// <summary>某樣東西在倉庫裡有幾個。</summary>
        public static int Count(string name) => Find(name)?.count ?? 0;

        /// <summary>放得下嗎（已經有同名的就一定放得下）。</summary>
        public static bool CanAdd(string name) => Find(name) != null || Chest.Count < CapacityConst;

        /// <summary>存進倉庫；種類滿了回 false。</summary>
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
                if (Chest.Count >= CapacityConst) return false;
                Chest.Add(new Stack(name, qty));
            }
            Save();
            return true;
        }

        /// <summary>從倉庫取出；數量不足回 false。</summary>
        public static bool Remove(string name, int qty = 1)
        {
            if (qty <= 0) return false;
            for (int i = 0; i < Chest.Count; i++)
            {
                if (Chest[i].name != name) continue;
                if (Chest[i].count < qty) return false;
                Chest[i].count -= qty;
                if (Chest[i].count == 0) Chest.RemoveAt(i);
                Save();
                return true;
            }
            return false;
        }

        /// <summary>
        /// 「手上能動用的量」＝背包 ＋ 倉庫。
        ///
        /// ⚠️ 材料一進城鎮就會自動歸位到倉庫（StashFromBag），所以**凡是要消耗材料的地方
        ///    （雜貨鋪收購、煉藥、上架）都要用這一組，不能只看背包**，否則材料才剛收好就變成
        ///    「什麼都不能做」。背包上限限制的是「採集當下能扛多少種回來」，那個限制仍然在。
        /// </summary>
        public static int AvailableOf(string name) => Inventory.CountOf(name) + Count(name);

        /// <summary>消耗 qty 個：先扣背包、不夠的再從倉庫補。任何一邊失敗就整筆退回。</summary>
        public static bool TakeAny(string name, int qty = 1)
        {
            if (qty <= 0) return false;
            int bag = Inventory.CountOf(name);
            if (bag + Count(name) < qty) return false;
            int fromBag = Mathf_Min(bag, qty);
            if (fromBag > 0 && !Inventory.Remove(name, fromBag)) return false;
            int rest = qty - fromBag;
            if (rest > 0 && !Remove(name, rest))
            {
                if (fromBag > 0) Inventory.Add(name, fromBag);   // 退回去，不要吃掉玩家的東西
                return false;
            }
            return true;
        }

        static int Mathf_Min(int a, int b) => a < b ? a : b;

        /// <summary>這樣東西進城鎮時會不會被自動收進倉庫。</summary>
        public static bool IsMaterial(string name) => AutoStash.Contains(name);

        /// <summary>
        /// 把背包裡的**材料與花**整批收進倉庫，回傳收了幾種。
        /// 一走進城鎮就會自動跑一次 —— 採集回來不必自己整理。
        /// **藥水不收**（要拿去上架賣）、**種子不收**（要留著種），倉庫種類滿了就留在背包。
        /// </summary>
        public static int StashFromBag()
        {
            int moved = 0;
            foreach (var s in Inventory.List())          // List() 是複本，邊搬邊改也安全
            {
                if (!IsMaterial(s.name)) continue;
                if (!CanAdd(s.name)) continue;           // 倉庫種類滿了 → 留在背包
                if (!Inventory.Remove(s.name, s.count)) continue;
                Add(s.name, s.count);
                moved++;
            }
            return moved;
        }
    }
}
