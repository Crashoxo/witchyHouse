import { SaveManager } from './SaveManager';
import { TimeSystem } from './TimeSystem';
import { Reputation } from './Reputation';

/**
 * 每日循環（Phase 3）——「今天」的經營記帳簿。
 *
 * 遊戲裡的一天（06:00 起床 → 睡覺或 02:00 昏倒）會把當天的營收、賣出、採集、
 * 煉製、支出統計起來；跨到隔天時 `rollover()` 把今天封存成 `last`（供結算畫面
 * DaySummaryPanel 顯示），並依當日營收再發一筆名聲，然後歸零開始新的一天。
 *
 * 掛勾方式：本模組 import 時就向 `TimeSystem.onNewDay` 註冊 rollover，所以只要
 * 有人 import DailyLog（CustomerManager / GatherTree / BrewCauldron / 結算畫面）
 * 每日結算就會自動運作，不需要任何場景改動。
 *
 * 資料存 module 變數（換場景保留）＋ SaveManager 存檔（關遊戲再開接著算）。
 */
const KEY = 'witch.daily';

/** 店裡的營業時間（顧客只在這段時間上門）。 */
export const SHOP_OPEN_HOUR = 8;
export const SHOP_CLOSE_HOUR = 20;

/** 一天的統計。 */
export interface DayStats {
    revenue: number;    // 顧客買走商品的收入
    sales: number;      // 賣出件數
    trade: number;      // 材料拿去雜貨鋪收購的收入
    spent: number;      // 支出（升級、買裝飾）
    gathered: number;   // 採集到的材料數
    brewed: number;     // 煉製出的藥水數
    rep: number;        // 今天賺到的名聲點數
    items: Record<string, { q: number; g: number }>;   // 賣出明細：品名 → {件數, 金額}
}

/** 已結算的一天（比 DayStats 多「第幾天」與「是不是昏倒收場」）。 */
export interface DayRecord extends DayStats {
    day: number;
    collapsed: boolean;
}

function blank(): DayStats {
    return { revenue: 0, sales: 0, trade: 0, spent: 0, gathered: 0, brewed: 0, rep: 0, items: {} };
}

/** 把存檔讀回來的東西補齊/清乾淨（欄位是後來加的、或存檔壞掉都不會炸）。 */
function sanitize(o: any): DayStats | null {
    if (!o || typeof o !== 'object') return null;
    const s = blank();
    const num = (v: any) => (Number.isFinite(v) && v >= 0 ? Math.floor(v) : 0);
    s.revenue = num(o.revenue); s.sales = num(o.sales); s.trade = num(o.trade);
    s.spent = num(o.spent); s.gathered = num(o.gathered); s.brewed = num(o.brewed);
    s.rep = num(o.rep);
    if (o.items && typeof o.items === 'object') {
        const keys = Object.keys(o.items);
        for (let i = 0; i < keys.length; i++) {
            const it = o.items[keys[i]];
            if (it && Number.isFinite(it.q)) s.items[keys[i]] = { q: num(it.q), g: num(it.g) };
        }
    }
    return s;
}

let today: DayStats = blank();
let last: DayRecord | null = null;

{
    try {
        const raw = SaveManager.getString(KEY);
        if (raw) {
            const o = JSON.parse(raw);
            const t = sanitize(o?.t);
            if (t) today = t;
            const l = sanitize(o?.l);
            if (l && o.l && Number.isFinite(o.l.day)) {
                last = l as DayRecord;
                last.day = Math.max(1, Math.floor(o.l.day));
                last.collapsed = !!o.l.collapsed;
            }
        }
    } catch (e) { /* 壞檔 → 從空的一天重來 */ }
}

function save() {
    SaveManager.setString(KEY, JSON.stringify({ t: today, l: last }));
}

/** 跨日：封存今天 → 發當日名聲 → 歸零。由 TimeSystem.onNewDay 呼叫。 */
function rollover(cause: 'sleep' | 'collapse') {
    today.rep += Reputation.addDaily(today.revenue);
    // rollToNextDay 已經 +1 天了，所以「剛結束的那天」是 totalDay - 1
    const rec: DayRecord = {
        day: Math.max(1, TimeSystem.totalDay - 1),
        collapsed: cause === 'collapse',
        revenue: today.revenue, sales: today.sales, trade: today.trade,
        spent: today.spent, gathered: today.gathered, brewed: today.brewed,
        rep: today.rep, items: today.items,
    };
    last = rec;
    today = blank();
    save();
}

TimeSystem.onNewDay(rollover);

export const DailyLog = {
    /** 今天到目前為止的統計（唯讀用）。 */
    get today(): DayStats { return today; },
    /** 最近一次結算完的一天（還沒過完第一天時是 null）。 */
    get last(): DayRecord | null { return last; },

    /** 現在店裡是營業時間嗎（顧客只在這段時間上門）。 */
    isShopOpen(): boolean {
        const h = TimeSystem.todHours;
        return h >= SHOP_OPEN_HOUR && h < SHOP_CLOSE_HOUR;
    },

    /** 營業時間文字，例：「08:00 – 20:00」。 */
    hoursText(): string {
        const p = (h: number) => `${h < 10 ? '0' : ''}${h}:00`;
        return `${p(SHOP_OPEN_HOUR)} – ${p(SHOP_CLOSE_HOUR)}`;
    },

    /** 顧客買走一件商品（金額已進 Wallet；這裡只記帳＋加名聲）。 */
    recordSale(name: string, gold: number): void {
        today.revenue += gold;
        today.sales += 1;
        const e = today.items[name];
        if (e) { e.q += 1; e.g += gold; }
        else today.items[name] = { q: 1, g: gold };
        today.rep += Reputation.recordSale(gold);
        save();
    },

    /** 材料賣給雜貨鋪的收購收入（不算店裡的生意，不加名聲）。 */
    recordTrade(gold: number): void { today.trade += gold; save(); },

    /** 採集到材料。 */
    recordGather(qty: number): void { today.gathered += Math.max(0, qty); save(); },

    /** 煉製出藥水。 */
    recordBrew(qty: number): void { today.brewed += Math.max(0, qty); save(); },

    /** 花掉金幣（升級、買裝飾）。 */
    recordSpend(gold: number): void { today.spent += Math.max(0, gold); save(); },
};
