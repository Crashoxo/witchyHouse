import { Wallet } from './Wallet';
import { Inventory } from './Inventory';
import { SaveManager } from './SaveManager';
import { ObjKind, QuestObjective, QuestDef, QUEST_DEFS } from './data/quests';

/**
 * 任務系統的資料層（純 module，仿 Wallet / Upgrades 中央化）。
 *
 * 任務定義寫死在 QUEST_DEFS，進度／狀態放在 module 變數並用 `sys.localStorage`
 * 存檔（換場景 director.loadScene 保留、關遊戲再開也在）。UI（QuestLog）與對話
 * （TalkNpc）都只讀這裡的資料，不自己存狀態。
 *
 * 任務狀態機：
 *   locked    —— 前置任務還沒完成（requires）
 *   available —— 可接（前置 OK、還沒接）
 *   active    —— 已接、目標還沒達成
 *   ready     —— 已接、目標達成、可回報領獎
 *   claimed   —— 已回報領獎（結束）
 *
 * 目標種類：
 *   gather / sell / brew —— 累積計數（採集/賣出/調配「總數」，只增不減，靠事件點
 *                            呼叫 record() 累加）。item 留空＝任意種類。
 *   have   —— 目前背包持有 N 個（consume=true 時回報會扣掉＝送貨任務）。
 *   gold   —— 錢包金幣達到 N。
 */

// ObjKind / QuestObjective / QuestDef 型別已搬到 data/quests.ts（見頂部 import）。
export type QuestStatus = 'locked' | 'available' | 'active' | 'ready' | 'claimed';

// QUEST_DEFS（任務內容）已搬到 data/quests.ts，見頂部 import。

// ---- 存檔 ----

const STATE_KEY = 'witch.quests.state';       // { accepted:[], claimed:[] }
const COUNTER_KEY = 'witch.quests.counters';  // { "gather:木材": 5, "sell:*": 3, ... }

interface SaveState { accepted: string[]; claimed: string[]; }

function loadState(): SaveState {
    try {
        const v = SaveManager.getString(STATE_KEY);
        const o = v ? JSON.parse(v) : null;
        const a = o && Array.isArray(o.accepted) ? o.accepted.filter((x: unknown) => typeof x === 'string') : [];
        const c = o && Array.isArray(o.claimed) ? o.claimed.filter((x: unknown) => typeof x === 'string') : [];
        return { accepted: a, claimed: c };
    } catch { return { accepted: [], claimed: [] }; }
}

function loadCounters(): Record<string, number> {
    try {
        const v = SaveManager.getString(COUNTER_KEY);
        const o = v ? JSON.parse(v) : null;
        const out: Record<string, number> = {};
        if (o && typeof o === 'object') {
            for (const k of Object.keys(o)) {
                const n = o[k];
                if (typeof n === 'number' && Number.isFinite(n)) out[k] = n;
            }
        }
        return out;
    } catch { return {}; }
}

const state = loadState();
const counters = loadCounters();

function saveState() { SaveManager.setString(STATE_KEY, JSON.stringify(state)); }
function saveCounters() { SaveManager.setString(COUNTER_KEY, JSON.stringify(counters)); }

// ---- 內部工具 ----

function counterKey(kind: ObjKind, item?: string): string {
    return `${kind}:${item ? item : '*'}`;
}

/** 目前這個目標的進度值（未夾上限）。 */
function progressOf(o: QuestObjective): number {
    switch (o.kind) {
        case 'gold': return Wallet.gold;
        case 'have': return Inventory.ensure()?.countOf(o.item ?? '') ?? 0;
        default:     return counters[counterKey(o.kind, o.item)] ?? 0;   // gather/sell/brew
    }
}

function def(id: string): QuestDef | undefined {
    return QUEST_DEFS.find(q => q.id === id);
}

// ---- 對外 API ----

export const Quests = {
    /** 全部任務定義。 */
    defs(): QuestDef[] { return QUEST_DEFS; },
    def,

    /** 某任務目前狀態。 */
    statusOf(id: string): QuestStatus {
        const d = def(id);
        if (!d) return 'locked';
        if (state.claimed.indexOf(id) >= 0) return 'claimed';
        if (state.accepted.indexOf(id) >= 0) return Quests.isComplete(id) ? 'ready' : 'active';
        if (d.requires && state.claimed.indexOf(d.requires) < 0) return 'locked';
        return 'available';
    },

    /** 目標是否已達成（供 accepted 的任務判斷 ready）。 */
    isComplete(id: string): boolean {
        const d = def(id);
        if (!d) return false;
        return progressOf(d.objective) >= d.objective.count;
    },

    /** 進度值（夾在 0..count）。 */
    progress(id: string): number {
        const d = def(id);
        if (!d) return 0;
        return Math.max(0, Math.min(progressOf(d.objective), d.objective.count));
    },

    /** 接下任務（available → active）。 */
    accept(id: string): boolean {
        if (Quests.statusOf(id) !== 'available') return false;
        state.accepted.push(id);
        saveState();
        return true;
    },

    /** 回報領獎（ready → claimed）。發金幣＋物品，送貨任務扣掉材料。 */
    claim(id: string): boolean {
        if (Quests.statusOf(id) !== 'ready') return false;
        const d = def(id)!;
        // 送貨任務：先扣掉要交的材料
        if (d.objective.kind === 'have' && d.objective.consume) {
            const inv = Inventory.ensure();
            if (!inv || !inv.remove(d.objective.item ?? '', d.objective.count)) return false;
        }
        if (d.rewardGold > 0) Wallet.add(d.rewardGold);
        if (d.rewardItem && (d.rewardQty ?? 0) > 0) Inventory.ensure()?.add(d.rewardItem, d.rewardQty);
        const i = state.accepted.indexOf(id);
        if (i >= 0) state.accepted.splice(i, 1);
        state.claimed.push(id);
        saveState();
        return true;
    },

    /**
     * 累積某類事件（採集/賣出/調配）。由 GatherTree / CustomerManager / BrewCauldron
     * 在對應時機呼叫，同時累加「該物品」與「任意（*）」兩個計數，讓指定物品與
     * 不指定物品的任務都能推進。
     */
    record(kind: 'gather' | 'sell' | 'brew', item: string, amount = 1): void {
        const anyKey = counterKey(kind);            // kind:*
        const itemKey = counterKey(kind, item);     // kind:item
        counters[anyKey] = (counters[anyKey] ?? 0) + amount;
        counters[itemKey] = (counters[itemKey] ?? 0) + amount;
        saveCounters();
    },

    /**
     * 某 NPC（依 giver 名）現在該處理的任務：優先「可回報」，其次「進行中」，
     * 再其次「可接」；都沒有回 null（此 NPC 沒任務可談→走一般對話）。
     */
    currentFor(giver: string): string | null {
        const mine = QUEST_DEFS.filter(q => q.giver === giver);
        const pick = (s: QuestStatus) => mine.find(q => Quests.statusOf(q.id) === s)?.id ?? null;
        return pick('ready') || pick('active') || pick('available');
    },

    /** 已接（進行中＋可回報）的任務 id，給任務簿列出。 */
    acceptedIds(): string[] { return state.accepted.slice(); },

    // ---- 顯示用文字 ----

    /** 目標描述，例：「採集 木材 ×5」。 */
    objectiveText(d: QuestDef): string {
        const o = d.objective;
        const verb = o.kind === 'gather' ? '採集'
                   : o.kind === 'sell' ? '賣出'
                   : o.kind === 'brew' ? '調配'
                   : o.kind === 'have' ? '備齊'
                   : '存到';
        if (o.kind === 'gold') return `${verb} ${o.count} 金幣`;
        const what = o.item ? o.item : (o.kind === 'sell' ? '商品' : o.kind === 'brew' ? '藥水' : '物品');
        return `${verb} ${what} ×${o.count}`;
    },

    /** 獎勵描述，例：「30 金」「50 金 + 金蘋果×1」。 */
    rewardText(d: QuestDef): string {
        const parts: string[] = [];
        if (d.rewardGold > 0) parts.push(`${d.rewardGold} 金`);
        if (d.rewardItem && (d.rewardQty ?? 0) > 0) parts.push(`${d.rewardItem}×${d.rewardQty}`);
        return parts.length ? parts.join(' + ') : '（無）';
    },

    /** 進度文字，例：「3/5」。 */
    progressText(id: string): string {
        const d = def(id);
        if (!d) return '';
        return `${Quests.progress(id)}/${d.objective.count}`;
    },
};
