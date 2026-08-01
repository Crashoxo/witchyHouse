/**
 * 後花園「內容」資料：種哪些花、花圃擺在哪、長大與枯萎要多久。
 * （狀態＝哪一格種了什麼、澆了沒，在 Garden.ts，走 SaveManager 存檔。）
 */

/** 一種可以種的花。 */
export interface FlowerDef {
    /** GameArt 的走圖名（resources/garden/<art>.png，6 階成長 ＋ 6 階枯萎）。 */
    art: string;
    /** 種子的道具名（背包裡拿的東西）。 */
    seed: string;
    /** 收成後拿到的花的道具名。 */
    flower: string;
    /** 收成幾朵。 */
    yield: number;
    /**
     * 花店賣這包種子的價錢。
     * 抓法：一包種子要比「收成後拿去雜貨鋪賣」便宜一點（種了才划算），
     * 但星鈴花刻意訂在雜貨鋪收購價上下 —— 稀有花要自己開店賣給顧客才有賺頭。
     */
    seedPrice: number;
    /** 圖鑑說明。 */
    desc: string;
}

export const FLOWERS: FlowerDef[] = [
    { art: 'lavender', seed: '薰衣草種子', flower: '薰衣草', yield: 2, seedPrice: 25,
      desc: '一串串的紫色小花，香味安神，藥水鋪常來收。' },
    { art: 'foxglove', seed: '毛地黃種子', flower: '毛地黃', yield: 2, seedPrice: 35,
      desc: '粉紫色的鐘形花，開得又高又艷，但別亂入藥。' },
    { art: 'starbell', seed: '星鈴花種子', flower: '星鈴花', yield: 1, seedPrice: 60,
      desc: '夜裡會泛著微光的藍白鈴花，稀少而值錢。' },
];

export function flowerBySeed(seed: string): FlowerDef | null {
    for (const f of FLOWERS) if (f.seed === seed) return f;
    return null;
}

/**
 * 成長與枯萎的時間，單位是**遊戲時間的分鐘**。
 *
 * 換算：正常速度下 10 遊戲分鐘 ≈ 7.3 現實秒 → 1 現實小時 ≈ 4930 遊戲分鐘
 * （約 4 個遊戲日）。所以下面的預設值＝「種下去約 45 分鐘（現實）開花、
 * 澆完水約 1 小時（現實）後開始枯萎」。想更快看到效果就把數字改小。
 *
 * 用遊戲時間而不是現實時間有兩個好處：睡覺跳過的時間也算進去（睡一覺花就長大了），
 * 而且關掉遊戲再回來不會平白長大。
 */
export const GROW_MINUTES = 3600;      // 種下 → 完全開花
export const DRY_MINUTES = 4800;       // 最後一次澆水 → 開始枯萎
export const WILT_MINUTES = 2400;      // 開始枯萎 → 完全枯死（中途澆水還救得回來）

/** 成長／枯萎各有幾階（對應美術的 6 格）。 */
export const GROW_STAGES = 6;
export const WILT_STAGES = 6;
/** 枯萎超過這一階就救不回來了。 */
export const WILT_RESCUABLE = 3;

/**
 * 花圃的位置（garden.scene 的世界座標，錨點在磚的中心）。
 * 底圖的草地是等距菱形，所以花圃也照等距排：往右下一格 (+HALF_W, -HALF_H)、
 * 往左下一格 (-HALF_W, -HALF_H)。
 */
export const PLOT_SCALE = 0.55;        // 土壤磚原圖 153x100 → 約 84x55
/** 花畫在磚上的縮放（原圖一株盛開約 68px，跟主角一樣高，縮一點才像庭園花草）。 */
export const FLOWER_SCALE = 0.78;
const HALF_W = 43, HALF_H = 27;
const ORIGIN_X = 0, ORIGIN_Y = 50;
export const PLOT_COLS = 4;
export const PLOT_ROWS = 3;

/** 第 i 格花圃的位置（i ＝ row * PLOT_COLS + col）。 */
export function plotPos(i: number): { x: number; y: number } {
    const col = i % PLOT_COLS, row = Math.floor(i / PLOT_COLS);
    return {
        x: ORIGIN_X + (col - row) * HALF_W,
        y: ORIGIN_Y - (col + row) * HALF_H,
    };
}

export const PLOT_COUNT = PLOT_COLS * PLOT_ROWS;

/**
 * 花圃的開墾順序（在店裡升級「花圃」會一次多開幾塊）。
 * 刻意不是 0,1,2,3… —— 那樣會先開滿第一排，剩下的變成缺一角的形狀。
 * 照這個順序開出來的是完整的小菱形：6 塊＝3×2、9 塊＝3×3、12 塊＝整片 4×3。
 */
export const PLOT_ORDER: number[] = [0, 1, 2, 4, 5, 6, 8, 9, 10, 3, 7, 11];

/**
 * 柵欄「外面」那條石板路上的路點 —— 村民沿著這條路經過花園，不會走進來。
 * 座標從底圖量出來的：左上角那條斜斜的石板大道。
 */
export const FENCE_WALK: Array<{ x: number; y: number }> = [
    { x: -660, y: 250 }, { x: -520, y: 300 }, { x: -380, y: 350 },
    { x: -600, y: 150 }, { x: -680, y: 60 },
];

/** 從店裡進花園的門（裝在 shop.scene）與回程門（裝在 garden.scene）的位置。 */
export const SHOP_TO_GARDEN = { x: 600, y: -150 };
export const GARDEN_TO_SHOP = { x: 250, y: 130 };
