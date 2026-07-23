import { Inventory } from './Inventory';
import { Recipe, RECIPES } from './data/recipes';

/**
 * 藥水配方的「製作邏輯」。型別 Recipe 與配方內容 RECIPES 已搬到 data/recipes.ts 集中管理，
 * 這裡 re-export 供既有 import（BrewPanel / BrewCauldron）使用，呼叫端完全不用改。
 */
export type { Recipe };
export { RECIPES };

export const PotionRecipes = {
    all: RECIPES,

    get(name: string): Recipe | undefined { return RECIPES.find(r => r.name === name); },

    /** 材料是否足夠製作。 */
    canCraft(r: Recipe): boolean {
        const inv = Inventory.ensure();
        if (!inv) return false;
        return Object.keys(r.inputs).every(mat => inv.countOf(mat) >= r.inputs[mat]);
    },

    /** 只扣材料（開始熬煮時呼叫）。材料不足回 false、不扣。 */
    consume(r: Recipe): boolean {
        const inv = Inventory.ensure();
        if (!inv) return false;
        if (!Object.keys(r.inputs).every(mat => inv.countOf(mat) >= r.inputs[mat])) return false;
        Object.keys(r.inputs).forEach(mat => inv.remove(mat, r.inputs[mat]));
        return true;
    },

    /** 只把成品加進背包（熬煮動畫結束時呼叫）。 */
    produce(r: Recipe): void {
        Inventory.ensure()?.add(r.name);
    },

    /** 一次做完：扣料＋產出（consume 成功才 produce）。 */
    craft(r: Recipe): boolean {
        if (!this.consume(r)) return false;
        this.produce(r);
        return true;
    },
};
