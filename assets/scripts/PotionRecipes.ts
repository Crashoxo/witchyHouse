import { Inventory } from './Inventory';
import { Storage } from './Storage';
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

    /**
     * 材料是否足夠製作。
     * ⚠️ 算的是**背包＋倉庫**：材料一進城鎮就自動歸位到倉庫，只看背包的話回到鍋爐前
     * 會變成什麼都做不了（倉庫就在同一個房間的木箱裡）。
     */
    canCraft(r: Recipe): boolean {
        return Object.keys(r.inputs).every(mat => Storage.availableOf(mat) >= r.inputs[mat]);
    },

    /** 只扣材料（開始熬煮時呼叫）。材料不足回 false、不扣。先扣背包再扣倉庫。 */
    consume(r: Recipe): boolean {
        Inventory.ensure();
        if (!this.canCraft(r)) return false;
        Object.keys(r.inputs).forEach(mat => Storage.takeAny(mat, r.inputs[mat]));
        return true;
    },

    /** 只把成品加進背包（熬煮動畫結束時呼叫）；背包種類滿了就先放進倉庫，別弄丟。 */
    produce(r: Recipe): void {
        if (!Inventory.ensure()?.add(r.name)) Storage.add(r.name, 1);
    },

    /** 一次做完：扣料＋產出（consume 成功才 produce）。 */
    craft(r: Recipe): boolean {
        if (!this.consume(r)) return false;
        this.produce(r);
        return true;
    },
};
