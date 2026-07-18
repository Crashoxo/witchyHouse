import { sys } from 'cc';
import { Wallet } from './Wallet';

/**
 * 店鋪升級：花金幣升級各項軌道，等級存 localStorage（key `witch.upgrades`）。
 * 各系統從這裡「讀值」——升級就自動生效：
 *   Inventory.slotCount ← bagSlots()
 *   CustomerManager 生成 ← customerInterval() / customerMax()
 *   ShopStock 展示上限 ← shelfCap()
 */
export type Track = 'signboard' | 'bag' | 'shelf';

/** 每項升級的定義：名稱、各級費用（長度＝最高等級）、每級效果文字。 */
interface Def {
    name: string;
    desc: string;
    costs: number[];
    effect: (lv: number) => string;
}

// 各級數值（index = 等級，0 = 未升級）
function intervalAt(lv: number): number { return [6, 5, 4, 3, 2.5][Math.min(lv, 4)]; }
function maxAt(lv: number): number { return [2, 3, 3, 4, 5][Math.min(lv, 4)]; }
function bagAt(lv: number): number { return 8 + lv * 2; }        // 8,10,12,14
function shelfAt(lv: number): number { return 3 + lv * 2; }      // 3,5,7

const DEFS: Record<Track, Def> = {
    signboard: {
        name: '招牌', desc: '顧客來得更快、同時更多人',
        costs: [100, 250, 500, 1000],
        effect: lv => `每 ${intervalAt(lv)} 秒 · 同時 ${maxAt(lv)} 人`,
    },
    bag: {
        name: '背包', desc: '採集能攜帶更多材料',
        costs: [80, 200, 450],
        effect: lv => `${bagAt(lv)} 格`,
    },
    shelf: {
        name: '貨架', desc: '桌上能展示更多種商品',
        costs: [120, 300],
        effect: lv => `${shelfAt(lv)} 種`,
    },
};

const KEY = 'witch.upgrades';

function load(): Record<Track, number> {
    const base: Record<Track, number> = { signboard: 0, bag: 0, shelf: 0 };
    try {
        const v = sys.localStorage.getItem(KEY);
        if (v) {
            const o = JSON.parse(v);
            for (const t of Object.keys(base) as Track[]) {
                if (typeof o[t] === 'number' && o[t] >= 0) base[t] = Math.min(o[t], DEFS[t].costs.length);
            }
        }
    } catch { /* 壞檔就用預設 */ }
    return base;
}

const levels = load();

function save() { sys.localStorage.setItem(KEY, JSON.stringify(levels)); }

export const Upgrades = {
    tracks(): Track[] { return ['signboard', 'bag', 'shelf']; },
    def(t: Track): Def { return DEFS[t]; },

    level(t: Track): number { return levels[t]; },
    maxLevel(t: Track): number { return DEFS[t].costs.length; },
    isMax(t: Track): boolean { return levels[t] >= DEFS[t].costs.length; },

    /** 升下一級的費用；已滿級回 null。 */
    cost(t: Track): number | null {
        return this.isMax(t) ? null : DEFS[t].costs[levels[t]];
    },

    /** 目前等級的效果文字。 */
    effectNow(t: Track): string { return DEFS[t].effect(levels[t]); },
    /** 下一級的效果文字（已滿級回空）。 */
    effectNext(t: Track): string { return this.isMax(t) ? '' : DEFS[t].effect(levels[t] + 1); },

    /** 買下一級：金幣夠且未滿級才成功。 */
    buy(t: Track): boolean {
        const c = this.cost(t);
        if (c === null || Wallet.gold < c) return false;
        Wallet.add(-c);
        levels[t] += 1;
        save();
        return true;
    },

    // ---- 給各系統讀的衍生值 ----
    bagSlots(): number { return bagAt(levels.bag); },
    shelfCap(): number { return shelfAt(levels.shelf); },
    customerInterval(): number { return intervalAt(levels.signboard); },
    customerMax(): number { return maxAt(levels.signboard); },
};
