using System;
using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>任務狀態。</summary>
    public enum QuestStatus
    {
        Locked,      // 前置任務還沒領獎
        Available,   // 可以接
        Active,      // 進行中
        Ready,       // 目標達成、可回報
        Claimed,     // 已回報領獎（結束）
    }

    /// <summary>
    /// 任務系統的狀態機、進度與存檔。任務內容在 Data.Quests。
    ///
    /// 進度分兩種來源：
    ///   Gather / Sell / Brew ── 累積計數，由 GatherTree / CustomerManager / BrewCauldron
    ///                            在對應時機呼叫 Record()。只增不減。
    ///   Have / Gold          ── 即時查背包或錢包（Have 的送貨任務回報時才扣）。
    ///
    /// ⚠️ 類別叫 QuestLog 而不是 Quests —— Data 命名空間裡已經有一個 Quests（資料表）。
    ///    同名的話 Core 裡的檔案會優先抓到自己那個，而且錯誤訊息完全看不出是撞名
    ///    （之前 Outfits 就是這樣咬過一次）。同 Decor / DecorCatalog 的命名原則。
    /// </summary>
    public static class QuestLog
    {
        const string StateKey = "witch.quests.state";
        const string CounterKey = "witch.quests.counters";

        [Serializable] class SaveState { public List<string> accepted = new(); public List<string> claimed = new(); }
        [Serializable] class Counters { public List<string> keys = new(); public List<int> values = new(); }

        static SaveState state;
        static Counters counters;

        static SaveState State
        {
            get
            {
                if (state == null)
                {
                    try { state = JsonUtility.FromJson<SaveState>(SaveManager.GetString(StateKey)); }
                    catch { state = null; }
                    state ??= new SaveState();
                    state.accepted ??= new List<string>();
                    state.claimed ??= new List<string>();
                }
                return state;
            }
        }

        static Counters Counts
        {
            get
            {
                if (counters == null)
                {
                    try { counters = JsonUtility.FromJson<Counters>(SaveManager.GetString(CounterKey)); }
                    catch { counters = null; }
                    counters ??= new Counters();
                }
                return counters;
            }
        }

        static void SaveState_() => SaveManager.SetString(StateKey, JsonUtility.ToJson(State));
        static void SaveCounters() => SaveManager.SetString(CounterKey, JsonUtility.ToJson(Counts));

        static string CounterKeyOf(ObjKind kind, string item) =>
            $"{kind}:{(string.IsNullOrEmpty(item) ? "*" : item)}";

        static int GetCount(string key)
        {
            int i = Counts.keys.IndexOf(key);
            return i < 0 ? 0 : Counts.values[i];
        }

        static void AddCount(string key, int amount)
        {
            int i = Counts.keys.IndexOf(key);
            if (i < 0) { Counts.keys.Add(key); Counts.values.Add(amount); }
            else Counts.values[i] += amount;
        }

        /// <summary>目前這個目標的進度值（未夾上限）。</summary>
        static int ProgressOf(QuestObjective o) => o.Kind switch
        {
            ObjKind.Gold => Wallet.Gold,
            ObjKind.Have => Inventory.CountOf(o.Item ?? ""),
            _ => GetCount(CounterKeyOf(o.Kind, o.Item)),      // Gather / Sell / Brew
        };

        // ──────────── 對外 API ────────────

        public static QuestDef[] Defs() => Data.Quests.All;
        public static QuestDef Def(string id) => Data.Quests.ById(id);

        /// <summary>某任務目前狀態。</summary>
        public static QuestStatus StatusOf(string id)
        {
            var d = Def(id);
            if (d == null) return QuestStatus.Locked;
            if (State.claimed.Contains(id)) return QuestStatus.Claimed;
            if (State.accepted.Contains(id))
                return IsComplete(id) ? QuestStatus.Ready : QuestStatus.Active;
            if (!string.IsNullOrEmpty(d.Requires) && !State.claimed.Contains(d.Requires))
                return QuestStatus.Locked;
            return QuestStatus.Available;
        }

        /// <summary>目標是否已達成。</summary>
        public static bool IsComplete(string id)
        {
            var d = Def(id);
            return d != null && ProgressOf(d.Objective) >= d.Objective.Count;
        }

        /// <summary>進度值（夾在 0..Count）。</summary>
        public static int Progress(string id)
        {
            var d = Def(id);
            return d == null ? 0 : Mathf.Clamp(ProgressOf(d.Objective), 0, d.Objective.Count);
        }

        /// <summary>接下任務（Available → Active）。</summary>
        public static bool Accept(string id)
        {
            if (StatusOf(id) != QuestStatus.Available) return false;
            State.accepted.Add(id);
            SaveState_();
            return true;
        }

        /// <summary>回報領獎（Ready → Claimed）。發金幣＋物品，送貨任務扣掉材料。</summary>
        public static bool Claim(string id)
        {
            if (StatusOf(id) != QuestStatus.Ready) return false;
            var d = Def(id);

            // 送貨任務：先扣掉要交的材料
            if (d.Objective.Kind == ObjKind.Have && d.Objective.Consume)
                if (!Inventory.Remove(d.Objective.Item ?? "", d.Objective.Count)) return false;

            if (d.RewardGold > 0) Wallet.Add(d.RewardGold);
            if (!string.IsNullOrEmpty(d.RewardItem) && d.RewardQty > 0)
                Inventory.Add(d.RewardItem, d.RewardQty);

            State.accepted.Remove(id);
            State.claimed.Add(id);
            SaveState_();
            return true;
        }

        /// <summary>
        /// 累積某類事件（採集/賣出/調配）。同時累加「該物品」與「任意（*）」兩個計數，
        /// 讓指定物品與不指定物品的任務都能推進。
        /// </summary>
        public static void Record(ObjKind kind, string item, int amount = 1)
        {
            if (amount <= 0) return;
            AddCount(CounterKeyOf(kind, null), amount);    // kind:*
            AddCount(CounterKeyOf(kind, item), amount);    // kind:item
            SaveCounters();
        }

        /// <summary>
        /// 某 NPC（依 Giver 名）現在該處理的任務：優先「可回報」，其次「進行中」，
        /// 再其次「可接」；都沒有回 null（此 NPC 沒任務可談 → 走一般對話）。
        /// </summary>
        public static string CurrentFor(string giver)
        {
            string Pick(QuestStatus s)
            {
                foreach (var q in Data.Quests.All)
                    if (q.Giver == giver && StatusOf(q.Id) == s) return q.Id;
                return null;
            }
            return Pick(QuestStatus.Ready) ?? Pick(QuestStatus.Active) ?? Pick(QuestStatus.Available);
        }

        /// <summary>已接（進行中＋可回報）的任務 id，給任務簿列出。</summary>
        public static List<string> AcceptedIds() => new(State.accepted);

        // ──────────── 顯示用文字 ────────────

        /// <summary>目標描述，例：「採集 木材 ×5」。</summary>
        public static string ObjectiveText(QuestDef d)
        {
            var o = d.Objective;
            string verb = o.Kind switch
            {
                ObjKind.Gather => "採集", ObjKind.Sell => "賣出", ObjKind.Brew => "調配",
                ObjKind.Have => "備齊", _ => "存到",
            };
            if (o.Kind == ObjKind.Gold) return $"{verb} {o.Count} 金幣";
            string what = !string.IsNullOrEmpty(o.Item) ? o.Item
                        : o.Kind == ObjKind.Sell ? "商品"
                        : o.Kind == ObjKind.Brew ? "藥水" : "物品";
            return $"{verb} {what} ×{o.Count}";
        }

        /// <summary>獎勵描述，例：「30 金」「50 金 + 金蘋果×1」。</summary>
        public static string RewardText(QuestDef d)
        {
            var parts = new List<string>();
            if (d.RewardGold > 0) parts.Add($"{d.RewardGold} 金");
            if (!string.IsNullOrEmpty(d.RewardItem) && d.RewardQty > 0)
                parts.Add($"{d.RewardItem}×{d.RewardQty}");
            return parts.Count > 0 ? string.Join(" + ", parts) : "（無）";
        }

        /// <summary>進度文字，例：「3/5」。</summary>
        public static string ProgressText(string id)
        {
            var d = Def(id);
            return d == null ? "" : $"{Progress(id)}/{d.Objective.Count}";
        }
    }
}
