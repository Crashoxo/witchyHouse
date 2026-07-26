import { SaveManager } from './SaveManager';

/**
 * 店鋪名聲：賣東西給顧客會累積名聲點數，達到門檻升一級（共 5 級，各有稱號）。
 *
 * 名聲影響「來客」——跟「招牌」升級是兩條互補的軌：
 *   招牌（花金幣買）  → 基礎的來客間隔與同時人數（Upgrades）
 *   名聲（做生意賺來）→ 在招牌的基礎上再加成（間隔 ×scale、同時人數 +extra）
 * CustomerManager 生成顧客時把兩者相乘/相加，所以「好好經營」本身就會讓店更熱鬧。
 *
 * 點數存 module 變數（換場景保留）＋ SaveManager 存檔。
 * 加點的入口統一走 DailyLog（賣出當下 recordSale、當日結算 addDaily），
 * 這樣「今天賺到多少名聲」才能寫進當日結算畫面。
 */
const KEY = 'witch.reputation';

interface Rank {
    need: number;      // 升到這一級所需的累積點數
    title: string;     // 稱號
    extra: number;     // 同時來客 +N
    scale: number;     // 來客間隔倍率（<1＝來得更快）
}

const RANKS: Rank[] = [
    { need: 0,   title: '無名小店', extra: 0, scale: 1.00 },
    { need: 40,  title: '略有耳聞', extra: 0, scale: 0.92 },
    { need: 120, title: '小有名氣', extra: 1, scale: 0.85 },
    { need: 300, title: '遠近馳名', extra: 1, scale: 0.78 },
    { need: 700, title: '傳說名店', extra: 2, scale: 0.70 },
];

function load(): number {
    const v = SaveManager.getString(KEY);
    const n = v ? parseInt(v, 10) : 0;
    return Number.isFinite(n) && n > 0 ? n : 0;
}

let points = load();

function save() { SaveManager.setString(KEY, String(points)); }

/** 目前等級的索引（0 起）。 */
function rankIdx(): number {
    let i = 0;
    for (let k = 0; k < RANKS.length; k++) if (points >= RANKS[k].need) i = k;
    return i;
}

export const Reputation = {
    get points(): number { return points; },
    /** 等級 1..5。 */
    get level(): number { return rankIdx() + 1; },
    get title(): string { return RANKS[rankIdx()].title; },
    get isMax(): boolean { return rankIdx() >= RANKS.length - 1; },

    /** 升下一級所需的累積點數；已滿級回 null。 */
    get nextNeed(): number | null {
        const i = rankIdx();
        return i >= RANKS.length - 1 ? null : RANKS[i + 1].need;
    },

    /** 往下一級的進度 0..1（已滿級回 1）。 */
    get progress(): number {
        const i = rankIdx();
        if (i >= RANKS.length - 1) return 1;
        const a = RANKS[i].need, b = RANKS[i + 1].need;
        return Math.min(1, Math.max(0, (points - a) / (b - a)));
    },

    /** 直接加點（回傳實際加了多少，方便呼叫端記帳）。 */
    add(n: number): number {
        if (!(n > 0)) return 0;
        points += Math.floor(n);
        save();
        return Math.floor(n);
    },

    /** 賣出一件商品：固定 1 點，賣得越貴額外加點。 */
    recordSale(gold: number): number {
        return this.add(1 + Math.floor(gold / 40));
    },

    /** 當日結算：依整天營收再給一筆。 */
    addDaily(revenue: number): number {
        return this.add(Math.floor(revenue / 100));
    },

    // ---- 給 CustomerManager 讀的來客加成 ----

    /** 同時來客人數加成（疊在招牌升級之上）。 */
    extraCustomers(): number { return RANKS[rankIdx()].extra; },
    /** 來客間隔倍率（疊在招牌升級之上，<1＝來得更快）。 */
    intervalScale(): number { return RANKS[rankIdx()].scale; },
};
