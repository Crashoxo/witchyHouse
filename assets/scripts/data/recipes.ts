/**
 * 藥水配方「內容」資料。成品名同時是背包/貨架用的物品名，圖示由 GameArt.item() 提供
 * （藥水圖已用中文名載進 items map）。材料都是採集得到的（見 data/items.ts 的 MATERIALS）。
 * 製作邏輯（扣料/產出）在 PotionRecipes.ts。
 */
export interface Recipe {
    name: string;                     // 成品中文名
    inputs: Record<string, number>;   // 材料名 → 需要數量
    sellPrice: number;                // 賣給顧客的建議售價（也塞進 data/prices 的 BASE_PRICE）
    brewSeconds: number;              // 熬煮動畫長度
}

export const RECIPES: Recipe[] = [
    { name: '清涼藥水',   inputs: { 藍莓: 2, 藥草: 1 },            sellPrice: 35,  brewSeconds: 2.2 },
    { name: '戀愛藥水',   inputs: { 漿果: 2, 黑莓: 1 },            sellPrice: 40,  brewSeconds: 2.2 },
    { name: '暗影藥水',   inputs: { 落葉: 3, 黑莓: 1 },            sellPrice: 42,  brewSeconds: 2.4 },
    { name: '烈焰藥水',   inputs: { 藥草: 2, 樹枝: 2 },            sellPrice: 45,  brewSeconds: 2.4 },
    { name: '溫暖熱可可', inputs: { 金蘋果: 1, 漿果: 2 },          sellPrice: 30,  brewSeconds: 2.0 },
    { name: '蜂蜜藥劑',   inputs: { 金蘋果: 2, 藥草: 1 },          sellPrice: 55,  brewSeconds: 2.6 },
    { name: '黃金藥劑',   inputs: { 金蘋果: 2, 藍莓: 2 },          sellPrice: 70,  brewSeconds: 2.8 },
    { name: '夜影掃帚',   inputs: { 木材: 3, 樹枝: 2, 黑莓: 1 },   sellPrice: 120, brewSeconds: 3.0 },
    { name: '星光掃帚',   inputs: { 木材: 3, 樹枝: 2, 藍莓: 2 },   sellPrice: 140, brewSeconds: 3.0 },
    { name: '羽翼掃帚',   inputs: { 木材: 3, 樹枝: 3, 金蘋果: 1 }, sellPrice: 160, brewSeconds: 3.2 },
];
