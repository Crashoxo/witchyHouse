/**
 * 價格「內容」資料：
 *   - DEFAULT_BUY：雜貨鋪「收購」玩家材料的預設單價（換金幣）。
 *   - BASE_PRICE：在「自己的店」賣給顧客的建議售價（比收購價高）。藥水價＝配方 sellPrice。
 */

/** 商店收購一項材料的定義：名稱 + 單價。 */
export interface BuyEntry { name: string; price: number; }

/** 沒在 inspector 指定時，雜貨鋪預設收購的材料與單價。 */
export const DEFAULT_BUY: BuyEntry[] = [
    { name: '木材', price: 5 },
    { name: '樹枝', price: 3 },
    { name: '漿果', price: 8 },
    { name: '落葉', price: 2 },
    { name: '藥草', price: 12 },
    { name: '黑莓', price: 10 },
    { name: '金蘋果', price: 50 },
];

/** 各材料/藥水的建議售價（賣給顧客，比雜貨鋪收購價高一些）。藥水價＝配方 sellPrice。 */
export const BASE_PRICE: Record<string, number> = {
    木材: 8, 樹枝: 5, 漿果: 12, 落葉: 3, 藥草: 18, 黑莓: 15, 金蘋果: 80, 藍莓: 14,
    // 藥水成品（PotionRecipes 的 sellPrice）
    清涼藥水: 35, 戀愛藥水: 40, 暗影藥水: 42, 烈焰藥水: 45, 溫暖熱可可: 30,
    蜂蜜藥劑: 55, 黃金藥劑: 70, 夜影掃帚: 120, 星光掃帚: 140, 羽翼掃帚: 160,
};
