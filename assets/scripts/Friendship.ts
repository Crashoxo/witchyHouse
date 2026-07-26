import { SaveManager } from './SaveManager';
import { TimeSystem } from './TimeSystem';
import { VILLAGERS, VillagerDef, POINTS_PER_HEART, MAX_HEARTS, TALK_POINTS } from './data/villagers';

/**
 * 村民友誼度（module ＋ SaveManager，仿 Wallet/Reputation）。
 *
 * 目前累積方式：**每天第一次跟同一位村民交談 +TALK_POINTS**（同一天再聊不重複給，
 * 所以會想每天繞去打招呼——這正是每日循環要的節奏）。每 POINTS_PER_HEART 點一顆心，
 * 最多 MAX_HEARTS 顆。
 *
 * 誰是村民寫在 data/villagers.ts，`name` 必須跟場景裡 TalkNpc 的 npcName 一致。
 * 掛勾點只有一個：TalkNpc.onKeyDown 交談時呼叫 `Friendship.talk(npcName)`。
 */
const KEY = 'witch.friendship';

interface Entry {
    p: number;    // 友誼點數
    d: number;    // 最後一次因交談加點的「第幾天」（TimeSystem.totalDay）
}

function load(): Record<string, Entry> {
    const out: Record<string, Entry> = {};
    try {
        const raw = SaveManager.getString(KEY);
        if (raw) {
            const o = JSON.parse(raw);
            if (o && typeof o === 'object') {
                const keys = Object.keys(o);
                for (let i = 0; i < keys.length; i++) {
                    const e = o[keys[i]];
                    if (e && Number.isFinite(e.p)) {
                        out[keys[i]] = { p: Math.max(0, Math.floor(e.p)), d: Number.isFinite(e.d) ? e.d : 0 };
                    }
                }
            }
        }
    } catch (e) { /* 壞檔 → 從零開始 */ }
    return out;
}

const book = load();

function save() { SaveManager.setString(KEY, JSON.stringify(book)); }

function entry(name: string): Entry {
    let e = book[name];
    if (!e) { e = { p: 0, d: 0 }; book[name] = e; }
    return e;
}

export const Friendship = {
    /** 村民清單（面板用，順序同 data/villagers.ts）。 */
    villagers(): VillagerDef[] { return VILLAGERS; },

    /** 某位村民的友誼點數。 */
    points(name: string): number { return book[name]?.p ?? 0; },

    /** 幾顆心（0..MAX_HEARTS）。 */
    hearts(name: string): number {
        return Math.min(MAX_HEARTS, Math.floor(this.points(name) / POINTS_PER_HEART));
    },
    get maxHearts(): number { return MAX_HEARTS; },

    /** 目前這顆心的進度 0..1（已滿心回 1）。 */
    heartProgress(name: string): number {
        if (this.hearts(name) >= MAX_HEARTS) return 1;
        return (this.points(name) % POINTS_PER_HEART) / POINTS_PER_HEART;
    },

    /** 今天已經跟這位聊過（加過點）了嗎。 */
    talkedToday(name: string): boolean {
        return (book[name]?.d ?? 0) === TimeSystem.totalDay;
    },

    /**
     * 交談：每天第一次才加點。回傳實際加了幾點（0＝今天已經聊過了）。
     * 沒列在 VILLAGERS 裡的 NPC 也能記，之後補進名單就會顯示。
     */
    talk(name: string): number {
        if (!name) return 0;
        const e = entry(name);
        const today = TimeSystem.totalDay;
        if (e.d === today) return 0;
        e.d = today;
        e.p = Math.min(e.p + TALK_POINTS, POINTS_PER_HEART * MAX_HEARTS);
        save();
        return TALK_POINTS;
    },

    /** 直接加點（之後做送禮／任務獎勵可以用）。 */
    add(name: string, n: number): void {
        if (!name || !(n > 0)) return;
        const e = entry(name);
        e.p = Math.min(e.p + Math.floor(n), POINTS_PER_HEART * MAX_HEARTS);
        save();
    },
};
