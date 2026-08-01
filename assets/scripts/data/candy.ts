/**
 * 糖果鎮（森林北邊那張地圖）的「內容」資料：住在鎮上的角色、他們賣什麼、路人怎麼晃。
 *
 * 座標是 candy.scene 的世界座標（Ground 1408×768、原點在地圖正中央的噴泉）。
 * 場景檔只有骨架，這裡的東西全部由 CandyTown.ts 在執行期擺出來 —— 不用改場景檔，
 * 也不用替每張圖做 spriteFrame 的 meta。
 */

/** 鎮上的一位角色。 */
export interface CandyNpc {
    /** 節點名（也當識別用）。 */
    id: string;
    /** 顯示名字（對話框、提示都用它）。 */
    name: string;
    /** `resources/candy/<art>.png`。 */
    art: string;
    x: number;
    y: number;
    /** 原圖縮到畫面上的比例（原圖是立繪尺寸，直接放會比女巫大好幾倍）。 */
    scale: number;
    /** 走近按 E 講的話。 */
    lines: string[];
    /** 有填就是商店：按 E 開購買面板，賣下面 CANDY_GOODS 裡對應的東西。 */
    shopTitle?: string;
}

export const CANDY_NPCS: CandyNpc[] = [
    {
        id: 'tamer', name: '軟糖鱷馴養師', art: 'tamer', x: -210, y: 55, scale: 0.37,
        shopTitle: '軟糖鱷商行',
        lines: [
            '歡迎來到糖果鎮！這些軟糖鱷是我養的，別怕，牠們只咬糖。',
            '你手上那些藥水挺有意思的——不過先看看我的貨吧，都是森林那邊買不到的。',
        ],
    },
    {
        id: 'guard', name: '時晶守衛', art: 'guard', x: 150, y: -10, scale: 0.45,
        lines: [
            '止步……不，抱歉，看你不像來搗亂的。',
            '我守著這座噴泉，它下面就是糖李礦坑的入口。',
            '想下去？先去馴養師那裡買張地圖吧，沒有地圖的人都繞回原地了。',
        ],
    },
    {
        id: 'sproutling', name: '小芽苗', art: 'sproutling', x: -80, y: -150, scale: 0.30,
        lines: [
            '（它輕輕晃了晃頭上的花。）',
            '……嗯？你是森林來的女巫嗎？我聞得到藥草的味道。',
            '這裡的土是糖做的，種不出草藥喔。',
        ],
    },
];

/** 馴養師賣的東西（買進來可以擺自己店裡賣給顧客賺差價）。 */
export const CANDY_GOODS: Array<{ name: string; price: number }> = [
    { name: '焦糖蘋果棒', price: 45 },
    { name: '鱷魚軟糖袋', price: 60 },
    { name: '永恆彩球糖', price: 90 },
    { name: '糖李礦坑地圖', price: 150 },
    { name: '妖精粉小袋', price: 200 },
    { name: '時晶法杖', price: 400 },
];

/** 鎮上晃來晃去的小東西（軟糖鱷與芽苗）。 */
export const CANDY_CRITTERS: Array<{ art: string; scale: number }> = [
    // ⚠️ 縮放要照「原圖尺寸」回推身高，不能三隻用同一個值 —— 原圖大小差很多，
    //    同樣的 scale 會讓大鱷魚變成最小的那隻。目標身高：小 60、中 62、大 74、芽苗 52。
    { art: 'gator-small', scale: 0.45 },
    { art: 'gator-medium', scale: 0.40 },
    { art: 'gator-large', scale: 0.42 },
    { art: 'sproutling', scale: 0.28 },
];

/** 路人的路線（繞著中央廣場走，都落在鋪面上）。 */
export const CANDY_WALK: Array<{ x: number; y: number }> = [
    { x: -260, y: 130 }, { x: 0, y: 165 }, { x: 260, y: 130 },
    { x: 265, y: -110 }, { x: 0, y: -170 }, { x: -265, y: -110 },
];

/** 同時最多幾隻路人。 */
export const CANDY_CROWD = 5;
