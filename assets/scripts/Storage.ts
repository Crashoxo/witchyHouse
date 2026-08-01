import { SaveManager } from './SaveManager';
import { Stack } from './Inventory';

/**
 * 店裡的倉庫（純資料，仿 Inventory 的 module 層 stock）。
 *
 * 為什麼要有它：背包的上限是「能放幾**種**東西」（同名無限疊加），而遊戲裡的道具種類
 * 已經有二十幾種 —— 材料、種子、花、藥水。背包再怎麼升級也塞不下全部，所以採集回來的
 * 東西要有地方放。倉庫容量大得多，走到店裡左邊的櫥櫃按 E 就能存取。
 *
 * ⚠️ 上架與煉藥的材料仍然是從**背包**拿的（要用什麼就先從倉庫取回來），這樣「這趟出門
 * 要帶什麼」才有取捨。日後想讓貨架/鍋爐直接吃倉庫，改那幾支的取料來源即可。
 */

const KEY = 'witch.storage';
/** 倉庫能放幾種東西（同名一樣無限疊加）。 */
const CAPACITY = 40;

function load(): Stack[] {
    try {
        const v = SaveManager.getString(KEY);
        const arr = v ? JSON.parse(v) : [];
        return Array.isArray(arr)
            ? arr.filter(s => s && typeof s.name === 'string' && typeof s.count === 'number' && s.count > 0)
            : [];
    } catch { return []; }      // 壞檔就當空倉庫
}

const chest: Stack[] = load();

function save() { SaveManager.setString(KEY, JSON.stringify(chest)); }

export const Storage = {
    /** 種類上限。 */
    capacity(): number { return CAPACITY; },
    /** 現在放了幾種。 */
    types(): number { return chest.length; },
    /** 目前內容（複本，改它不會動到真資料）。 */
    list(): Stack[] { return chest.map(s => ({ ...s })); },
    /** 某樣東西在倉庫裡有幾個。 */
    count(name: string): number { return chest.find(s => s.name === name)?.count ?? 0; },
    /** 放得下嗎（已經有同名的就一定放得下）。 */
    canAdd(name: string): boolean {
        return chest.some(s => s.name === name) || chest.length < CAPACITY;
    },

    /** 存進倉庫；種類滿了回 false。 */
    add(name: string, qty = 1): boolean {
        if (qty <= 0) return false;
        const s = chest.find(s => s.name === name);
        if (s) {
            s.count += qty;
        } else {
            if (chest.length >= CAPACITY) return false;
            chest.push({ name, count: qty });
        }
        save();
        return true;
    },

    /** 從倉庫取出；數量不足回 false。 */
    remove(name: string, qty = 1): boolean {
        const i = chest.findIndex(s => s.name === name);
        if (i < 0 || chest[i].count < qty) return false;
        chest[i].count -= qty;
        if (chest[i].count === 0) chest.splice(i, 1);
        save();
        return true;
    },
};
