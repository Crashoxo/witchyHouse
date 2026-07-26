/**
 * 道具「內容」資料：有哪些基礎材料、每個道具對應的美術檔名。
 * （道具的「價格」在 data/prices.ts；藥水「配方」在 data/recipes.ts。）
 */

/** 8 種可採集的基礎材料（固定顯示順序）。 */
export const MATERIALS: string[] = ['木材', '樹枝', '漿果', '落葉', '藥草', '黑莓', '金蘋果', '藍莓'];

/** 材料名稱 → resources/items 底下的檔名。 */
export const ITEM_FILES: Record<string, string> = {
    木材: 'wood', 樹枝: 'twig', 漿果: 'berry', 落葉: 'leaf',
    藥草: 'herb', 黑莓: 'blackberry', 金蘋果: 'goldapple', 藍莓: 'blueberry',
};

/** 道具說明（玩家資訊面板 Tab → 物品頁顯示）。沒列到的用預設一句帶過。 */
export const ITEM_DESC: Record<string, string> = {
    木材: '從樹上採下的結實木料，做掃帚的骨架少不了它。',
    樹枝: '隨處可撿的細枝，燒起來很快，也能綁成掃帚尾。',
    漿果: '酸甜多汁的紅色小果，村民拿它做果醬。',
    落葉: '乾燥的落葉，磨碎後是暗系藥水的基底。',
    藥草: '帶著清香的綠葉，幾乎所有藥水都用得到。',
    黑莓: '味道濃烈的深色莓果，染料與藥水都愛用。',
    金蘋果: '偶爾才結一顆的金色果實，光是擺著就很值錢。',
    藍莓: '夏天森林裡最甜的小果，冰涼系藥水的關鍵。',
    清涼藥水: '喝一口從喉嚨涼到指尖，夏天賣得最好。',
    戀愛藥水: '粉紅色的甜香藥水。效果如何，店主不負責。',
    暗影藥水: '喝下後腳步聲會消失一小段時間。',
    烈焰藥水: '瓶身摸起來是溫的，冬天鎮上的人搶著買。',
    溫暖熱可可: '不是藥水，是真的很好喝的熱可可。',
    蜂蜜藥劑: '金黃黏稠，喝完連指尖都暖起來。',
    黃金藥劑: '傳說中能讓人一整天好運的高級藥劑。',
    夜影掃帚: '夜裡飛行不會被看見的黑色掃帚。',
    星光掃帚: '掃帚尾會拖出一道淡淡的星光。',
    羽翼掃帚: '掃帚柄上綁著羽毛，飛得又穩又快。',
};

/** 沒有專屬說明時的預設句。 */
export const DEFAULT_ITEM_DESC = '一件在森林裡採到的材料。';

/** 藥水成品：中文名 → resources/potions 底下的檔名。載進 items map，圖示查找同材料。 */
export const POTION_ITEMS: Record<string, string> = {
    清涼藥水: 'potion_blue', 戀愛藥水: 'potion_pink', 暗影藥水: 'potion_dark',
    烈焰藥水: 'potion_red', 溫暖熱可可: 'cocoa_mug', 蜂蜜藥劑: 'amber_jug',
    黃金藥劑: 'gold_bottle', 夜影掃帚: 'broom_purple', 星光掃帚: 'broom_blue',
    羽翼掃帚: 'broom_white',
};
