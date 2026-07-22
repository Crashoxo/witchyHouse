import { sys } from 'cc';

/**
 * 遊戲時間系統 —— 照星露谷（Stardew Valley）的邏輯：
 *
 * ● 一天 20 小時：每天 06:00 醒來，不睡覺的話 02:00（隔天）昏倒。玩家可隨時
 *   sleep() 提前結束當天、跳到隔天 06:00。
 * ● 幀精確、10 分鐘為最小刻度離散跳動：星露谷以 60fps 跑，時間不是連續累積而是
 *   「累積到 N 幀就跳 10 分鐘」，避免長時間累積誤差。
 *     - 正常：10 遊戲分鐘 = 438 幀 = 7.3 真實秒（1 小時 43.8 秒、一天 20h≈14分36秒）
 *     - 減速（骷髏洞穴式）：10 分鐘 = 563 幀 = 9.3833 秒（本作暫無洞穴，setSlow 備用）
 *   為了不綁死實際 fps，這裡累積的是「幀當量」＝ dt*60，換算與 60fps 一致但不受
 *   實際張數影響（掉幀不會讓時間變慢）。
 * ● 暫停：開選單/對話（UIState.modalOpen）時 Clock 會傳 paused=true，時間凍結，
 *   時鐘指針變灰閃爍（見 Clock.ts）。單人模式才暫停；本作單人。
 *
 * 時間存 module 變數（換場景保留）＋ localStorage（關遊戲再開接著走）。
 */
const KEY = 'witch.time';

const FPS = 60;
const FRAMES_NORMAL = 438;                // 10 遊戲分鐘（正常）
const FRAMES_SLOW = 563;                  // 10 遊戲分鐘（洞穴減速，備用）
const STEP_MIN = 10;                      // 最小時間刻度：10 分鐘

const DAY_START = 6 * 60;                 // 360 = 06:00 醒來
const DAY_END = 26 * 60;                  // 1560 = 隔天 02:00 昏倒
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
let tod = DAY_START;      // 一天內的分鐘（DAY_START..DAY_END）
let frameAcc = 0;         // 累積的幀當量，滿一步就跳 10 分鐘（不存檔，殘量<7.3秒）
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
    frameAcc = 0;
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
        frameAcc += dt * FPS;                     // 幀當量（與 60fps 一致、不受實際張數影響）
        const per = slow ? FRAMES_SLOW : FRAMES_NORMAL;
        let stepped = false;
        while (frameAcc >= per) {
            frameAcc -= per;
            tod += STEP_MIN;
            stepped = true;
            if (tod >= DAY_END) { rollToNextDay(); break; }   // 02:00 昏倒 → 隔天
        }
        if (stepped) save();
    },

    /** 睡覺：提前結束當天，跳到隔天 06:00。 */
    sleep(): void { rollToNextDay(); save(); },

    /** 切換洞穴減速模式（10 分鐘由 438 幀變 563 幀）。 */
    setSlow(v: boolean): void { slow = v; },

    /** 註冊「換新的一天」回呼（睡覺或昏倒都會觸發）。 */
    onNewDay(cb: () => void): void { newDayCbs.push(cb); },

    get hour(): number { return displayHour() % 24; },       // 0..23（25:00→1）
    get minute(): number { return tod % 60; },               // 只會是 0/10/20/30/40/50
    get day(): number { return (totalDays % DAYS_PER_MONTH) + 1; },
    get month(): number { return (Math.floor(totalDays / DAYS_PER_MONTH) % MONTHS_PER_YEAR) + 1; },
    get year(): number { return Math.floor(totalDays / (DAYS_PER_MONTH * MONTHS_PER_YEAR)) + 1; },

    /** 夜晚？（18:00 到隔天 02:00）。決定盤面日/月圖示，之後也可拿來做天色。 */
    get isNight(): boolean { return displayHour() >= SUNSET; },

    /** 一天過了幾成（0..1，06:00→02:00）。給天色漸變等用。 */
    get dayProgress(): number { return (tod - DAY_START) / (DAY_END - DAY_START); },

    /** 時針角度比例（0..1，12 小時制，含分鐘平滑量）。 */
    get hourFraction(): number { return ((displayHour() % 12) + this.minute / 60) / 12; },
    /** 分針角度比例（0..1）。 */
    get minuteFraction(): number { return (tod % 60) / 60; },

    /** "H:MM" 字串（10 分鐘刻度；tod 本來就是 10 的倍數）。 */
    clockText(): string {
        const h = displayHour() % 24, m = tod % 60;
        return `${h}:${m < 10 ? '0' : ''}${m}`;
    },
};
