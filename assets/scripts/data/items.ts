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

/** 藥水成品：中文名 → resources/potions 底下的檔名。載進 items map，圖示查找同材料。 */
export const POTION_ITEMS: Record<string, string> = {
    清涼藥水: 'potion_blue', 戀愛藥水: 'potion_pink', 暗影藥水: 'potion_dark',
    烈焰藥水: 'potion_red', 溫暖熱可可: 'cocoa_mug', 蜂蜜藥劑: 'amber_jug',
    黃金藥劑: 'gold_bottle', 夜影掃帚: 'broom_purple', 星光掃帚: 'broom_blue',
    羽翼掃帚: 'broom_white',
};
