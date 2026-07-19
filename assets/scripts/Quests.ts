import { sys } from 'cc';
import { Wallet } from './Wallet';
import { Inventory } from './Inventory';

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

export type ObjKind = 'gather' | 'sell' | 'brew' | 'have' | 'gold';

export interface QuestObjective {
    kind: ObjKind;
    item?: string;      // gather/sell/brew/have 的物品名；留空＝任意（gather/sell/brew）。gold 不用
    count: number;
    consume?: boolean;  // have 專用：回報時把物品扣掉（送貨任務）
}

export interface QuestDef {
    id: string;
    giver: string;          // 發任務的 NPC 名（＝TalkNpc.npcName，用來對應）
    title: string;
    objective: QuestObjective;
    rewardGold: number;
    rewardItem?: string;    // 額外物品獎勵（可省）
    rewardQty?: number;
    offerLines: string[];   // 提供任務時 NPC 說的話
    activeLines: string[];  // 進行中（還沒完成）
    readyLines: string[];   // 完成、可回報時
    doneLines: string[];    // 領獎後
    requires?: string;      // 前置任務 id（要先 claimed 才會解鎖）
}

export type QuestStatus = 'locked' | 'available' | 'active' | 'ready' | 'claimed';

/** 地精老闆的任務鏈（依 requires 串成前後接續）。 */
const QUEST_DEFS: QuestDef[] = [
    {
        id: 'gather_wood', giver: '地精老闆', title: '收集木材',
        objective: { kind: 'gather', item: '木材', count: 5 },
        rewardGold: 30,
        offerLines: ['唉，我的藥架又搖搖晃晃了…',
                     '你能幫我到東邊森林採 5 個木材回來嗎？'],
        activeLines: ['木材採到 5 個了嗎？往東邊森林走，靠近樹按 E 就能採。'],
        readyLines: ['喔！木材都齊了，太感謝你了！'],
        doneLines: ['這 30 金幣是謝禮，拿去吧。'],
    },
    {
        id: 'sell_three', giver: '地精老闆', title: '第一批生意',
        objective: { kind: 'sell', count: 3 },
        rewardGold: 40, requires: 'gather_wood',
        offerLines: ['開店最重要的，就是把東西賣出去。',
                     '去把商品上架，賣出 3 件給上門的客人，讓我看看你的本事。'],
        activeLines: ['賣出 3 件商品了嗎？把材料或藥水擺上桌，客人自然會來。'],
        readyLines: ['生意做得有模有樣嘛！'],
        doneLines: ['這是給新手老闆的鼓勵，收下這 40 金。'],
    },
    {
        id: 'brew_two', giver: '地精老闆', title: '初嘗煉金',
        objective: { kind: 'brew', count: 2 },
        rewardGold: 60, requires: 'sell_three',
        offerLines: ['光賣原料利潤太薄了。',
                     '到店裡右上角的藥水室，調配 2 瓶藥水吧——附加價值高多了。'],
        activeLines: ['調好 2 瓶藥水了嗎？店面右上角進藥水室，走到鍋爐按 E。'],
        readyLines: ['我聞到藥香了！你有天份。'],
        doneLines: ['這瓶配方費 60 金給你，繼續加油。'],
    },
    {
        id: 'deliver_berry', giver: '地精老闆', title: '地精的點心',
        objective: { kind: 'have', item: '漿果', count: 5, consume: true },
        rewardGold: 50, rewardItem: '金蘋果', rewardQty: 1, requires: 'brew_two',
        offerLines: ['說來有點不好意思…我肚子餓了。',
                     '幫我帶 5 個漿果來，我請你吃一顆金蘋果！'],
        activeLines: ['漿果帶來了嗎？背包裡要有 5 個，我才收得下。'],
        readyLines: ['哇，新鮮的漿果！謝謝你～'],
        doneLines: ['說好的金蘋果給你，還有 50 金當跑腿費！'],
    },
    {
        id: 'gold_300', giver: '地精老闆', title: '小有積蓄',
        objective: { kind: 'gold', count: 300 },
        rewardGold: 100, rewardItem: '金蘋果', rewardQty: 2, requires: 'deliver_berry',
        offerLines: ['當老闆的目標是什麼？當然是賺錢！',
                     '等你存到 300 金幣，再來找我，有好東西給你。'],
        activeLines: ['存到 300 金幣了嗎？多調點藥水賣，錢很快就進來了。'],
        readyLines: ['300 金！你已經是像樣的老闆了。'],
        doneLines: ['這是給成功商人的賀禮：100 金，還有兩顆金蘋果！'],
    },
];

// ---- 存檔 ----

const STATE_KEY = 'witch.quests.state';       // { accepted:[], claimed:[] }
const COUNTER_KEY = 'witch.quests.counters';  // { "gather:木材": 5, "sell:*": 3, ... }

interface SaveState { accepted: string[]; claimed: string[]; }

function loadState(): SaveState {
    try {
        const v = sys.localStorage.getItem(STATE_KEY);
        const o = v ? JSON.parse(v) : null;
        const a = o && Array.isArray(o.accepted) ? o.accepted.filter((x: unknown) => typeof x === 'string') : [];
        const c = o && Array.isArray(o.claimed) ? o.claimed.filter((x: unknown) => typeof x === 'string') : [];
        return { accepted: a, claimed: c };
    } catch { return { accepted: [], claimed: [] }; }
}

function loadCounters(): Record<string, number> {
    try {
        const v = sys.localStorage.getItem(COUNTER_KEY);
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

function saveState() { sys.localStorage.setItem(STATE_KEY, JSON.stringify(state)); }
function saveCounters() { sys.localStorage.setItem(COUNTER_KEY, JSON.stringify(counters)); }

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
