import { SaveManager } from './SaveManager';
import { Inventory, Stack } from './Inventory';
import { MATERIALS } from './data/items';
import { FLOWERS } from './data/garden';

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

/**
 * 進城鎮時會自動歸位的東西＝採集材料與後花園的花。
 * 種子留在背包（要拿去種），藥水也留著（要拿去上架賣給顧客）。
 */
const AUTO_STASH: string[] = (() => {
    const out = MATERIALS.slice();
    for (const f of FLOWERS) out.push(f.flower);
    return out;
})();

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

    /**
     * 「手上能動用的量」＝背包 ＋ 倉庫。
     *
     * ⚠️ 材料一進城鎮就會自動歸位到倉庫（stashFromBag），所以**凡是要消耗材料的地方
     * （雜貨鋪收購、煉藥、上架）都要用這一組，不能只看背包**，否則材料才剛收好就變成
     * 「什麼都不能做」。背包上限限制的是「採集當下能扛多少種回來」，那個限制仍然在。
     */
    availableOf(name: string): number {
        return Inventory.countOf(name) + Storage.count(name);
    },

    /** 消耗 qty 個：先扣背包、不夠的再從倉庫補。任何一邊失敗就整筆退回。 */
    takeAny(name: string, qty = 1): boolean {
        if (qty <= 0) return false;
        const inv = Inventory.instance;
        const bag = Inventory.countOf(name);
        if (bag + Storage.count(name) < qty) return false;
        const fromBag = Math.min(bag, qty);
        if (fromBag > 0 && !inv?.remove(name, fromBag)) return false;
        const rest = qty - fromBag;
        if (rest > 0 && !Storage.remove(name, rest)) {
            if (fromBag > 0) inv?.add(name, fromBag);      // 退回去，不要吃掉玩家的東西
            return false;
        }
        return true;
    },

    /** 這樣東西進城鎮時會不會被自動收進倉庫。 */
    isMaterial(name: string): boolean {
        return AUTO_STASH.indexOf(name) >= 0;
    },

    /**
     * 把背包裡的**材料與花**整批收進倉庫，回傳收了幾種。
     * 一走進城鎮就會自動跑一次（見 PlayerController）—— 採集回來不必自己整理。
     * **藥水不收**（要拿去上架賣）、**種子不收**（要留著種），倉庫種類滿了就留在背包。
     */
    stashFromBag(): number {
        const inv = Inventory.instance;
        if (!inv) return 0;
        let moved = 0;
        for (const s of Inventory.list()) {              // list() 是複本，邊搬邊改也安全
            if (!Storage.isMaterial(s.name)) continue;
            if (!Storage.canAdd(s.name)) continue;       // 倉庫種類滿了 → 留在背包
            if (!inv.remove(s.name, s.count)) continue;
            Storage.add(s.name, s.count);
            moved++;
        }
        return moved;
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
