import { SaveManager } from './SaveManager';
import { TimeSystem } from './TimeSystem';
import { Wallet } from './Wallet';
import { Inventory } from './Inventory';
import { DailyLog } from './DailyLog';
import { Upgrades } from './Upgrades';
import { FLOWERS, flowerBySeed, GROW_MINUTES, DRY_MINUTES, WET_MINUTES, WILT_MINUTES,
         GROW_STAGES, WILT_STAGES, WILT_RESCUABLE,
         PLOT_COUNT, PLOT_COLS, PLOT_ROWS, PLOT_ORDER } from './data/garden';

/**
 * 後花園的種植狀態（純資料，仿 Wallet / ShopStock）。
 *
 * 每一格花圃記三件事：種了什麼、什麼時候種的、最後一次澆水是什麼時候。
 * 時間全部用 **TimeSystem 的總分鐘數**（遊戲時間），所以：
 *   - 睡一覺跳過的時間也算進成長，醒來花就長大了；
 *   - 關掉遊戲再回來不會平白長大（現實時間不計）。
 * 成長是純看時間；**澆水管的是不枯萎**（太久沒澆 → 開始枯 → 再拖下去就死了）。
 */

export interface Plot {
    seed: string;     // 種下的種子名（''＝空地）
    planted: number;  // 種下時的遊戲總分鐘
    watered: number;  // 最後一次澆水的遊戲總分鐘（0＝種下後還沒澆過）
}

/** 一格花圃現在的樣子（給畫面用）。 */
export interface PlotView {
    empty: boolean;
    art: string;      // 花的走圖名
    stage: number;    // 第幾格圖
    wilting: boolean; // true＝畫枯萎那一列
    dead: boolean;    // 枯死了，只能清掉
    ripe: boolean;    // 完全開花，可以收成
    wet: boolean;     // 土是濕的（畫深色土）
}

const KEY = 'witch.garden';
const plots: Plot[] = [];

/**
 * 目前的遊戲總分鐘（跨日累加）。
 * ⚠️ 不能用 `hour`：它把 25:00 顯示成 1:00，深夜會倒退。一天是 06:00 醒到 26:00 昏倒
 * ＝ 1200 分鐘，所以直接拿 `todHours` 換算，這樣才是單調遞增的。
 */
const MINUTES_PER_DAY = 1200;
const DAY_START = 6 * 60;
function now(): number {
    return (TimeSystem.totalDay - 1) * MINUTES_PER_DAY + (TimeSystem.todHours * 60 - DAY_START);
}

function blank(): Plot { return { seed: '', planted: 0, watered: 0 }; }

function load(): void {
    plots.length = 0;
    for (let i = 0; i < PLOT_COUNT; i++) plots.push(blank());
    const raw = SaveManager.getJSON<Plot[] | null>(KEY, null);
    if (!Array.isArray(raw)) return;
    for (let i = 0; i < PLOT_COUNT && i < raw.length; i++) {
        const p = raw[i];
        if (!p || typeof p !== 'object') continue;
        const seed = typeof p.seed === 'string' ? p.seed : '';
        if (seed && !flowerBySeed(seed)) continue;      // 防壞檔：認不得的種子當空地
        plots[i] = {
            seed,
            planted: typeof p.planted === 'number' ? p.planted : 0,
            watered: typeof p.watered === 'number' ? p.watered : 0,
        };
    }
}

function save(): void { SaveManager.setJSON(KEY, plots); }

load();

/**
 * 這格「上一次有水」是什麼時候 —— 沒澆過就算種下的那一刻。
 * ⚠️ 這跟「土看起來濕不濕」是兩回事：種下去土是**乾的**（要自己澆才會變深色），
 * 但枯萎的倒數還是從種下開始算，不然沒澆過的 watered=0 會被當成幾百天沒澆、種下就枯。
 */
function lastWet(p: Plot): number {
    return Math.max(p.watered, p.planted);
}

export const Garden = {
    /** 這格的狀態（給 GardenPlot 畫圖用）。 */
    view(i: number): PlotView {
        const p = plots[i];
        const blank: PlotView = { empty: true, art: '', stage: 0, wilting: false,
                                  dead: false, ripe: false, wet: false };
        if (!p || !p.seed) {
            // 空地澆了水也會是深色的（先澆再種也行）
            blank.wet = !!p && p.watered > 0 && now() - p.watered < WET_MINUTES;
            return blank;
        }
        const f = flowerBySeed(p.seed);
        if (!f) return blank;

        // 土的深淺只看「有沒有真的澆過水、澆多久了」；枯不枯則從 lastWet 算
        const wet = p.watered > 0 && now() - p.watered < WET_MINUTES;
        const dry = now() - lastWet(p);
        // ⚠️ 還沒澆過水就不會長 —— 乾土裡的種子不發芽（澆下去的那一刻才開始計時，見 water()）
        const grown = p.watered === 0 ? 0
                                      : Math.min(1, (now() - p.planted) / GROW_MINUTES);
        if (dry >= DRY_MINUTES) {
            const t = (dry - DRY_MINUTES) / WILT_MINUTES;
            const stage = Math.min(WILT_STAGES - 1, Math.floor(t * WILT_STAGES));
            // 水乾的那一刻長到哪就凍在哪。**已經開花的還是摘得到**（只要還沒枯過頭）——
            // 花開了卻晚幾分鐘回來就整株報銷，太苛了。
            const frozen = p.watered === 0 ? 0
                : Math.min(1, (lastWet(p) + DRY_MINUTES - p.planted) / GROW_MINUTES);
            return { empty: false, art: f.art, stage, wilting: true,
                     dead: stage >= WILT_STAGES - 1,
                     ripe: frozen >= 1 && stage <= WILT_RESCUABLE, wet };
        }
        // 前面幾階平均分配在成長時間裡，**最後一階（完全開花）剛好落在時間到的那一刻** ——
        // 這樣「種下一小時後開花可以摘」才是字面上的一小時，而不是 80% 就先開了。
        const stage = grown >= 1 ? GROW_STAGES - 1
                                 : Math.floor(grown * (GROW_STAGES - 1));
        return { empty: false, art: f.art, stage, wilting: false, dead: false,
                 ripe: stage >= GROW_STAGES - 1, wet };
    },

    /**
     * 種下一顆種子；回傳是否成功（格子要是空的、種子要認得）。
     * **不會順手澆水** —— 剛種下的土是乾的，玩家自己澆過才變成濕土。
     */
    plant(i: number, seed: string): boolean {
        const p = plots[i];
        if (!p || p.seed || !flowerBySeed(seed)) return false;
        p.seed = seed;
        p.planted = now();
        p.watered = 0;
        save();
        return true;
    },

    /** 澆水。枯萎還沒太嚴重的話會救回來（枯萎進度歸零、成長從現在續算）。 */
    water(i: number): boolean {
        const p = plots[i];
        if (!p) return false;
        const v = Garden.view(i);
        if (v.dead) return false;
        if (p.seed && p.watered === 0) {
            // 第一次澆水＝成長開始計時（種下到現在乾等的那段不算）
            p.planted = now();
        } else if (v.wilting) {
            if (v.stage > WILT_RESCUABLE) return false;    // 枯太久了，救不回來
            // 救回來：把「已經長到哪」保留下來，重新開始算成長時間
            const grown = Math.min(1, (lastWet(p) + DRY_MINUTES - p.planted) / GROW_MINUTES);
            p.planted = now() - grown * GROW_MINUTES;
        }
        p.watered = now();
        save();
        return true;
    },

    /** 收成：完全開花才收得到，回傳 [花名, 數量]；收不到回 null。 */
    harvest(i: number): { name: string; count: number } | null {
        const p = plots[i];
        if (!p || !p.seed) return null;
        const v = Garden.view(i);
        if (!v.ripe) return null;
        const f = flowerBySeed(p.seed);
        p.seed = '';
        save();
        return f ? { name: f.flower, count: f.yield } : null;
    },

    /** 清掉枯死的花，讓格子可以重種。 */
    clear(i: number): boolean {
        const p = plots[i];
        if (!p || !p.seed || !Garden.view(i).dead) return false;
        p.seed = '';
        save();
        return true;
    },

    /** 花圃快沒水了（花圃上會冒「缺水」提醒）。 */
    needsWater(i: number): boolean {
        const p = plots[i];
        return !!p && !!p.seed && now() - lastWet(p) >= DRY_MINUTES * 0.75;
    },

    /**
     * 現在開墾了幾塊花圃（其餘的還是荒地，要在店裡升級「花圃」才開得出來）。
     * GardenRoom 只會把這麼多塊做出來。
     */
    unlockedCount(): number { return Math.min(PLOT_COUNT, Upgrades.gardenPlots()); },

    /** 已開墾的花圃 index（照 PLOT_ORDER 的開墾順序）。 */
    unlockedPlots(): number[] { return PLOT_ORDER.slice(0, Garden.unlockedCount()); },

    /**
     * 澆一塊花圃時，跟著一起澆到的格子（澆水壺升級後一次澆得更多）。
     * 0＝只有自己；1＝十字相鄰；2＝整片花園。回傳的 index 都是已開墾的。
     */
    waterTargets(i: number): number[] {
        const open = Garden.unlockedPlots();
        const spread = Upgrades.waterSpread();
        if (spread >= 2) return open;
        if (spread <= 0) return [i];
        const col = i % PLOT_COLS, row = Math.floor(i / PLOT_COLS);
        const out = [i];
        const push = (c: number, r: number) => {
            if (c < 0 || c >= PLOT_COLS || r < 0 || r >= PLOT_ROWS) return;
            const k = r * PLOT_COLS + c;
            if (open.indexOf(k) >= 0) out.push(k);      // 還沒開墾的鄰居不算
        };
        push(col - 1, row); push(col + 1, row); push(col, row - 1); push(col, row + 1);
        return out;
    },

    /** 在花店買一包種子：扣金幣、進背包。金幣不夠或認不得的種子回 false。 */
    buySeed(seed: string): boolean {
        const f = flowerBySeed(seed);
        if (!f || Wallet.gold < f.seedPrice) return false;
        const inv = Inventory.ensure();
        if (!inv || !inv.add(seed, 1)) return false;     // 背包滿了就不扣錢
        Wallet.add(-f.seedPrice);
        DailyLog.recordSpend(f.seedPrice);
        return true;
    },

    /** 所有可以種的花（給面板/圖鑑用）。 */
    get flowers() { return FLOWERS; },
};
