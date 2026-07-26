/**
 * 年曆與季節「內容」資料：**一個月 28 天、一年 12 個月（336 天），每 3 個月一季**。
 *   一～三月＝春　四～六月＝夏　七～九月＝秋　十～十二月＝冬
 *
 * 季節目前影響三件事，都是從這張表讀出來的：
 *   1. 天色 —— dawnShift / duskShift 把 DayNightTint 的曲線整段前後挪（冬天早黑晚亮）。
 *   2. 採集 —— bonusItems 是當季盛產的材料，採到會多給、稀有掉落機率也高一點。
 *   3. 節日 —— FESTIVALS 標在日曆上，當天客人特別多。
 * 要調整季節感就改這裡，程式不用動。
 */

export interface SeasonDef {
    /** 單字季名（時鐘盤面那個小框放得下的長度）。 */
    name: string;
    /** 完整季名（面板標題用）。 */
    label: string;
    /** 一句話的季節描述（日曆頁顯示）。 */
    desc: string;
    /** 天亮時刻偏移（小時，正＝亮得晚）。 */
    dawnShift: number;
    /** 天黑時刻偏移（小時，負＝黑得早）。 */
    duskShift: number;
    /** 當季盛產的材料（採集會多給、稀有掉落機率提高）。 */
    bonusItems: string[];
}

/** 四季，索引 0..3。 */
export const SEASONS: SeasonDef[] = [
    {
        name: '春', label: '春天', desc: '萬物冒芽，花草長得特別快。',
        dawnShift: 0, duskShift: 0,
        bonusItems: ['藥草', '漿果'],
    },
    {
        name: '夏', label: '夏天', desc: '日照最長的季節，莓果又甜又多。',
        dawnShift: -0.5, duskShift: 1.0,
        bonusItems: ['漿果', '黑莓', '藍莓'],
    },
    {
        name: '秋', label: '秋天', desc: '果實成熟、落葉滿地，收成的季節。',
        dawnShift: 0.4, duskShift: -0.7,
        bonusItems: ['落葉', '金蘋果'],
    },
    {
        name: '冬', label: '冬天', desc: '天黑得早，只有耐寒的枯枝與木材。',
        dawnShift: 1.0, duskShift: -1.5,
        bonusItems: ['木材', '樹枝'],
    },
];

/** 一個月 28 天、一年 12 個月，每 3 個月一季。 */
export const DAYS_PER_MONTH = 28;
export const MONTHS_PER_YEAR = 12;
export const MONTHS_PER_SEASON = 3;

/** 月份名稱（時鐘牛皮紙框與日曆頁顯示用）。 */
export const MONTH_NAMES: string[] = [
    '一月', '二月', '三月', '四月', '五月', '六月',
    '七月', '八月', '九月', '十月', '十一月', '十二月',
];

/** 節日：某個月的第幾天。當天客人特別多，日曆上會標出來。 */
export interface Festival {
    month: number;    // 1..12
    day: number;      // 1..28
    name: string;
    desc: string;
}

export const FESTIVALS: Festival[] = [
    { month: 1,  day: 7,  name: '播種祭',     desc: '村民互相分送種子，森林的藥草冒得特別旺。' },
    { month: 3,  day: 21, name: '花之祭典',   desc: '街上鋪滿花瓣，逛街的人潮一整天不斷。' },
    { month: 5,  day: 14, name: '仲夏螢火節', desc: '入夜後溪邊全是螢火蟲，鎮上熱鬧到很晚。' },
    { month: 6,  day: 18, name: '盛夏市集',   desc: '廣場擺滿攤子，連隔壁村的人都來逛。' },
    { month: 8,  day: 10, name: '月光茶會',   desc: '大家帶著自釀的飲品聚在廣場，藥水特別好賣。' },
    { month: 9,  day: 28, name: '豐收祭',     desc: '一年裡最盛大的市集，店門口大排長龍。' },
    { month: 11, day: 5,  name: '初雪祭',     desc: '第一場雪落下的日子，鎮上會煮熱飲請大家。' },
    { month: 12, day: 24, name: '星光節',     desc: '冬夜點起星燈，村民習慣在這天互送小禮物。' },
];
