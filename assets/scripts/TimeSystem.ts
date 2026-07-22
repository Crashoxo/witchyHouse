import { sys } from 'cc';

/**
 * 遊戲時間系統。時間在遊玩時「實時流動」——由常駐的 Clock HUD 每幀呼叫 tick(dt)
 * 推進。以「總遊戲分鐘」float 存在 module 變數（換場景 director.loadScene 保留），
 * 並用 sys.localStorage 存檔（關遊戲再開時間接著走）。月/日/時/分都由總分鐘推算，
 * 對應盤面：羅馬數字 I..XII＝12 小時、外圈 1..31＝當月日期。
 */
const KEY = 'witch.time';

/**
 * 星露谷（Stardew Valley）式換算：每 7 真實秒過 10 遊戲分鐘。
 * → 每遊戲分鐘 = 0.7 真實秒；1 遊戲小時 = 42 秒；完整 24h ≈ 16.8 真實分
 *   （星露谷可玩時段 6:00→凌晨2:00 共 20h ≈ 14 真實分，之後睡覺跳到隔天）。
 * 想調快慢就改這個數值。星露谷時間以 10 分鐘為單位跳動，這裡內部連續累積讓
 * 指針平滑轉，文字讀數 clockText() 則向下取整到 10 分（呈現同星露谷）。
 */
const REAL_SEC_PER_GAME_MIN = 0.7;
const STEP_MIN = 10;                      // 星露谷式 10 分鐘顯示單位
const MIN_PER_DAY = 24 * 60;              // 1440
const DAYS_PER_MONTH = 31;               // 對應盤面外圈 1..31
const MONTHS_PER_YEAR = 12;              // 對應羅馬數字 I..XII
/** 開新檔的起始時刻：第 1 年 1 月 1 日 06:00（星露谷每天早上 6 點起床）。 */
const START_MINUTES = 6 * 60;
/** 夜晚：19:00 起到隔天 06:00。決定盤面頂端顯示太陽還是月亮。 */
const NIGHT_START = 19;
const DAWN = 6;
/** 存檔節流：每過這麼多真實秒才寫一次 localStorage（避免每幀寫檔）。 */
const SAVE_EVERY_REAL = 4;

function load(): number {
    const v = sys.localStorage.getItem(KEY);
    const n = v ? parseFloat(v) : NaN;
    return Number.isFinite(n) && n >= 0 ? n : START_MINUTES;
}

let totalMin = load();       // 累積的總遊戲分鐘
let sinceSave = 0;           // 距上次存檔的真實秒

function save() {
    sys.localStorage.setItem(KEY, String(Math.floor(totalMin)));
}

/** 一天內的分鐘數（0..1439）。 */
function intoDay(): number {
    const m = totalMin % MIN_PER_DAY;
    return m < 0 ? m + MIN_PER_DAY : m;
}
/** 從紀元起算的第幾天（0 起）。 */
function dayIndex(): number {
    return Math.floor(totalMin / MIN_PER_DAY);
}

export const TimeSystem = {
    /** 每幀推進時間（dt＝真實秒）。由 Clock HUD 驅動，全遊戲單一來源。 */
    tick(dt: number): void {
        if (!(dt > 0)) return;
        if (dt > 0.25) dt = 0.25;                       // 掉幀/剛換場景時鉗住，避免時間爆衝
        totalMin += dt / REAL_SEC_PER_GAME_MIN;         // 真實秒 → 遊戲分鐘（星露谷式）
        sinceSave += dt;
        if (sinceSave >= SAVE_EVERY_REAL) { sinceSave = 0; save(); }
    },

    get hour(): number { return Math.floor(intoDay() / 60); },
    get minute(): number { return Math.floor(intoDay() % 60); },
    get day(): number { return (dayIndex() % DAYS_PER_MONTH) + 1; },
    get month(): number { return (Math.floor(dayIndex() / DAYS_PER_MONTH) % MONTHS_PER_YEAR) + 1; },
    get year(): number { return Math.floor(dayIndex() / (DAYS_PER_MONTH * MONTHS_PER_YEAR)) + 1; },

    /** 夜晚？（決定盤面日/月圖示，之後也可拿來開關店/顧客）。 */
    get isNight(): boolean { const h = this.hour; return h < DAWN || h >= NIGHT_START; },

    /** 時針角度比例（0..1，含分鐘的平滑量，12 小時制）。 */
    get hourFraction(): number { return ((intoDay() / 60) % 12) / 12; },
    /** 分針角度比例（0..1）。 */
    get minuteFraction(): number { return (intoDay() % 60) / 60; },

    /** "HH:MM" 字串，分鐘向下取整到 10（呈現同星露谷：6:00, 6:10, 6:20…）。 */
    clockText(): string {
        const h = this.hour;
        const m = Math.floor(this.minute / STEP_MIN) * STEP_MIN;
        return `${h < 10 ? '0' : ''}${h}:${m < 10 ? '0' : ''}${m}`;
    },
};
