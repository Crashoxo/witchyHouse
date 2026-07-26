import { SaveManager } from './SaveManager';
import { SEASONS, FESTIVALS, DAYS_PER_MONTH, MONTHS_PER_YEAR,
         MONTHS_PER_SEASON, SeasonDef, Festival } from './data/seasons';

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

// 年曆結構在 data/seasons.ts：一個月 28 天、一年 12 個月（336 天）、每 3 個月一季。
const DAYS_PER_YEAR = DAYS_PER_MONTH * MONTHS_PER_YEAR;

interface Save { d: number; t: number; }
function load(): Save {
    try {
        const raw = SaveManager.getString(KEY);
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

/** 一天怎麼結束的：自己去睡 / 撐到 02:00 昏倒。給每日結算畫面分辨用。 */
export type DayEndCause = 'sleep' | 'collapse';

let totalDays = 0;        // 從開檔起算的第幾天（0 起）
let tod = DAY_START;      // 一天內的分鐘（DAY_START..DAY_END，連續 float）
let sinceSave = 0;        // 距上次存檔的真實秒（節流用）
let slow = false;         // 減速模式（洞穴）
const newDayCbs: Array<(cause: DayEndCause) => void> = [];

{
    const s = load();
    totalDays = s.d; tod = s.t;
}

function save() {
    SaveManager.setString(KEY, JSON.stringify({ d: totalDays, t: tod }));
}

/** 跳到隔天早上 06:00。 */
function rollToNextDay(cause: DayEndCause) {
    totalDays += 1;
    tod = DAY_START;
    newDayCbs.forEach(cb => cb(cause));
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
        if (tod >= DAY_END) rollToNextDay('collapse');   // 02:00 昏倒 → 隔天 06:00
        sinceSave += dt;
        if (sinceSave >= 4) { sinceSave = 0; save(); }   // 存檔節流
    },

    /**
     * 睡覺：白天睡 → 跳到當晚 20:00；晚上睡 → 跳到隔天 06:00。
     * 回傳 true 代表跨到了隔天（給睡覺畫面顯示「早上/晚上」用）。
     */
    sleep(): boolean {
        if (this.isNight) { rollToNextDay('sleep'); save(); return true; }
        tod = NIGHT_SLEEP; save(); return false;
    },

    /** 切換洞穴減速模式（10 分鐘由 438 幀變 563 幀）。 */
    setSlow(v: boolean): void { slow = v; },

    /** 註冊「換新的一天」回呼（睡覺或昏倒都會觸發，cause 分辨是哪一種）。 */
    onNewDay(cb: (cause: DayEndCause) => void): void { newDayCbs.push(cb); },

    /** 從開檔起算的第幾天（1 起，不受月份影響）——給每日結算標題用。 */
    get totalDay(): number { return totalDays + 1; },

    get hour(): number { return displayHour() % 24; },       // 0..23（25:00→1）
    get minute(): number { return Math.floor(tod % 60); },   // 0..59（連續，取整）
    get day(): number { return (totalDays % DAYS_PER_MONTH) + 1; },        // 當月第幾天 1..28
    get month(): number { return (Math.floor(totalDays / DAYS_PER_MONTH) % MONTHS_PER_YEAR) + 1; },
    get year(): number { return Math.floor(totalDays / DAYS_PER_YEAR) + 1; },
    /** 一個月幾天（日曆面板要用）。 */
    get daysPerMonth(): number { return DAYS_PER_MONTH; },


    /** 季節索引 0..3（一～三月＝春、四～六月＝夏…）。 */
    get season(): number { return this.seasonOfMonth(this.month); },
    seasonOfMonth(month: number): number {
        return Math.floor((month - 1) / MONTHS_PER_SEASON) % SEASONS.length;
    },
    /** 目前季節的定義（名稱、天色偏移、當季盛產材料）。 */
    get seasonDef(): SeasonDef { return SEASONS[this.season]; },
    /** 單字季名：春/夏/秋/冬。 */
    get seasonName(): string { return this.seasonDef.name; },

    /** 日期文字，例：「3 月 16 日」。 */
    dateText(): string { return `${this.month} 月 ${this.day} 日`; },
    /** 含年份與季節的日期文字，例：「第 1 年 3 月 16 日（春）」。 */
    dateTextFull(): string {
        return `第 ${this.year} 年 ${this.month} 月 ${this.day} 日（${this.seasonName}）`;
    },

    /**
     * 把「從開檔起算的第 N 天」（1 起，同 totalDay）換成日期文字。
     * 每日結算要顯示「剛結束的那一天」，那時 totalDay 已經跳到隔天了，所以需要這個。
     */
    dateTextOf(totalDay: number): string {
        const n = Math.max(0, Math.floor(totalDay) - 1);
        const m = (Math.floor(n / DAYS_PER_MONTH) % MONTHS_PER_YEAR) + 1;
        return `${m} 月 ${(n % DAYS_PER_MONTH) + 1} 日`;
    },

    /** 今天是節日的話回傳它，否則 null。 */
    festivalToday(): Festival | null { return this.festivalOn(this.month, this.day); },
    /** 某月某日的節日（日曆面板逐格查）。 */
    festivalOn(month: number, day: number): Festival | null {
        for (let i = 0; i < FESTIVALS.length; i++) {
            const f = FESTIVALS[i];
            if (f.month === month && f.day === day) return f;
        }
        return null;
    },

    /** 從某月某日之後算起，一年內的下一個節日（繞過年底；沒有回 null）。 */
    nextFestivalFrom(month: number, day: number): Festival | null {
        for (let step = 0; step < DAYS_PER_YEAR; step++) {
            const n = (month - 1) * DAYS_PER_MONTH + (day - 1) + 1 + step;
            const m = (Math.floor(n / DAYS_PER_MONTH) % MONTHS_PER_YEAR) + 1;
            const d = (n % DAYS_PER_MONTH) + 1;
            const f = this.festivalOn(m, d);
            if (f) return f;
        }
        return null;
    },

    /** 這一季的天黑時刻（小時）——冬天黑得早、夏天黑得晚。 */
    get sunsetHour(): number { return SUNSET + this.seasonDef.duskShift; },

    /** 夜晚？（天黑到隔天 02:00）。決定盤面日/月圖示、房間日夜背景、天色。 */
    get isNight(): boolean { return tod / 60 >= this.sunsetHour; },

    /** 一天過了幾成（0..1，06:00→02:00）。給天色漸變等用。 */
    get dayProgress(): number { return (tod - DAY_START) / (DAY_END - DAY_START); },

    /**
     * 連續的「當日時數」，範圍 6.0..26.0（含分鐘的小數）。跨午夜仍單調遞增
     * （24=00:00、25=01:00、26=02:00），故適合直接餵天色/色板曲線做插值。
     */
    get todHours(): number { return tod / 60; },

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
