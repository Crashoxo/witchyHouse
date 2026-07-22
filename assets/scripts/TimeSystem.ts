import { sys } from 'cc';

/**
 * 遊戲時間系統 —— 照星露谷（Stardew Valley）的邏輯：
 *
 * ● 一天 20 小時：每天 06:00 醒來，不睡覺的話 02:00（隔天）昏倒。玩家可隨時
 *   sleep() 提前結束當天、跳到隔天 06:00。
 * ● 時間「連續」流動，指針平滑慢慢走（不是每 7.3 秒硬跳一格）。速率同星露谷：
 *     - 正常：10 遊戲分鐘 = 7.3 真實秒（＝438 幀@60fps；1 小時 43.8 秒、一天 20h≈14分36秒）
 *     - 減速（骷髏洞穴式）：10 分鐘 = 9.3833 秒（本作暫無洞穴，setSlow 備用）
 *   文字讀數 clockText() 才向下取整到 10 分（呈現同星露谷），指針吃連續值平滑轉。
 * ● 暫停：開選單/對話（UIState.modalOpen）時 Clock 會傳 paused=true，時間凍結，
 *   時鐘指針變灰閃爍（見 Clock.ts）。單人模式才暫停；本作單人。
 *
 * 時間存 module 變數（換場景保留）＋ localStorage（關遊戲再開接著走）。
 */
const KEY = 'witch.time';

// 星露谷速率：10 遊戲分鐘 = 7.3 真實秒（正常，＝438 幀@60fps）/ 9.3833 秒（洞穴減速）。
// ⚠️ 時間「連續」累積 → 指針平滑慢慢走，不是每 7.3 秒硬跳一格。速率與星露谷一致。
const SEC_PER_10MIN_NORMAL = 7.3;
const SEC_PER_10MIN_SLOW = 9.3833;
const STEP_MIN = 10;                      // 文字讀數 clockText 的顯示刻度（10 分鐘）

const DAY_START = 6 * 60;                 // 360 = 06:00 醒來
const DAY_END = 26 * 60;                  // 1560 = 隔天 02:00 昏倒
const NIGHT_SLEEP = 20 * 60;              // 1200 = 白天睡覺會跳到當晚 20:00
const SUNSET = 18;                        // 18:00 起算夜晚（盤面換月亮）

const DAYS_PER_MONTH = 28;               // 一個月 28 天（同星露谷一季天數）
const MONTHS_PER_YEAR = 12;              // 對應盤面羅馬數字 I..XII

interface Save { d: number; t: number; }
function load(): Save {
    try {
        const raw = sys.localStorage.getItem(KEY);
        if (raw) {
            const o = JSON.parse(raw);
            if (o && Number.isFinite(o.d) && Number.isFinite(o.t)) {
                const t = Math.min(Math.max(o.t, DAY_START), DAY_END);
                return { d: Math.max(0, Math.floor(o.d)), t };
            }
        }
    } catch (e) { /* 壞檔 → 重來 */ }
    return { d: 0, t: DAY_START };
}

let totalDays = 0;        // 從開檔起算的第幾天（0 起）
let tod = DAY_START;      // 一天內的分鐘（DAY_START..DAY_END，連續 float）
let sinceSave = 0;        // 距上次存檔的真實秒（節流用）
let slow = false;         // 減速模式（洞穴）
const newDayCbs: Array<() => void> = [];

{
    const s = load();
    totalDays = s.d; tod = s.t;
}

function save() {
    sys.localStorage.setItem(KEY, JSON.stringify({ d: totalDays, t: tod }));
}

/** 跳到隔天早上 06:00。 */
function rollToNextDay() {
    totalDays += 1;
    tod = DAY_START;
    newDayCbs.forEach(cb => cb());
}

/** 目前時刻的「顯示小時」（6..25，其中 24=00:00、25=01:00）。 */
function displayHour(): number { return Math.floor(tod / 60); }

export const TimeSystem = {
    /**
     * 推進時間。dt＝真實秒；paused＝是否凍結（開選單/對話時）。
     * 由 Clock HUD 每幀呼叫，是全遊戲唯一的時間來源。
     */
    tick(dt: number, paused: boolean): void {
        if (paused || !(dt > 0)) return;
        if (dt > 0.25) dt = 0.25;                 // 掉幀/剛換場景鉗住
        const per = slow ? SEC_PER_10MIN_SLOW : SEC_PER_10MIN_NORMAL;
        tod += dt * (STEP_MIN / per);             // 連續累積遊戲分鐘（平滑）
        if (tod >= DAY_END) rollToNextDay();      // 02:00 昏倒 → 隔天 06:00
        sinceSave += dt;
        if (sinceSave >= 4) { sinceSave = 0; save(); }   // 存檔節流
    },

    /**
     * 睡覺：白天睡 → 跳到當晚 20:00；晚上睡 → 跳到隔天 06:00。
     * 回傳 true 代表跨到了隔天（給睡覺畫面顯示「早上/晚上」用）。
     */
    sleep(): boolean {
        if (this.isNight) { rollToNextDay(); save(); return true; }
        tod = NIGHT_SLEEP; save(); return false;
    },

    /** 切換洞穴減速模式（10 分鐘由 438 幀變 563 幀）。 */
    setSlow(v: boolean): void { slow = v; },

    /** 註冊「換新的一天」回呼（睡覺或昏倒都會觸發）。 */
    onNewDay(cb: () => void): void { newDayCbs.push(cb); },

    get hour(): number { return displayHour() % 24; },       // 0..23（25:00→1）
    get minute(): number { return Math.floor(tod % 60); },   // 0..59（連續，取整）
    get day(): number { return (totalDays % DAYS_PER_MONTH) + 1; },
    get month(): number { return (Math.floor(totalDays / DAYS_PER_MONTH) % MONTHS_PER_YEAR) + 1; },
    get year(): number { return Math.floor(totalDays / (DAYS_PER_MONTH * MONTHS_PER_YEAR)) + 1; },

    /** 夜晚？（18:00 到隔天 02:00）。決定盤面日/月圖示，之後也可拿來做天色。 */
    get isNight(): boolean { return displayHour() >= SUNSET; },

    /** 一天過了幾成（0..1，06:00→02:00）。給天色漸變等用。 */
    get dayProgress(): number { return (tod - DAY_START) / (DAY_END - DAY_START); },

    /** 時針角度比例（0..1，12 小時制，連續含分鐘量→平滑）。 */
    get hourFraction(): number { return ((displayHour() % 12) + (tod % 60) / 60) / 12; },
    /** 分針角度比例（0..1，連續）。 */
    get minuteFraction(): number { return (tod % 60) / 60; },

    /** "H:MM" 字串，分鐘向下取整到 10（呈現同星露谷：6:00, 6:10…；指針本身連續轉）。 */
    clockText(): string {
        const h = displayHour() % 24;
        const m = Math.floor((tod % 60) / STEP_MIN) * STEP_MIN;
        return `${h}:${m < 10 ? '0' : ''}${m}`;
    },
};
