import { Upgrades } from './Upgrades';
import { SaveManager } from './SaveManager';
import { BASE_PRICE } from './data/prices';

/**
 * 玩家商店的「貨架」資料：把背包材料上架、定價，等顧客上門買（顧客在 Phase 2）。
 * 資料存 module 層並用 `sys.localStorage` 存檔（key `witch.shop.listings`），
 * 換場景 / 關遊戲都保留。純資料模組，不含 UI（面板在 ShopManagePanel）。
 */
export interface Listing { name: string; price: number; count: number; }

// BASE_PRICE（建議售價表）已搬到 data/prices.ts，見頂部 import。

const KEY = 'witch.shop.listings';

function load(): Listing[] {
    try {
        const v = SaveManager.getString(KEY);
        const arr = v ? JSON.parse(v) : [];
        return Array.isArray(arr)
            ? arr.filter(l => l && typeof l.name === 'string'
                              && typeof l.price === 'number'
                              && typeof l.count === 'number' && l.count > 0)
            : [];
    } catch { return []; }
}

const listings: Listing[] = load();

function save() {
    SaveManager.setString(KEY, JSON.stringify(listings));
}

export const ShopStock = {
    /** 目前貨架上的所有上架品（唯讀取用；改動請用下面的方法）。 */
    get listings(): Listing[] { return listings; },

    /** 某材料的建議售價。 */
    suggestedPrice(name: string): number { return BASE_PRICE[name] ?? 10; },

    /** 能不能再上架這個？（同名可疊加；新種類受貨架上限限制） */
    canAdd(name: string): boolean {
        if (listings.some(l => l.name === name)) return true;
        return listings.length < Upgrades.shelfCap();
    },

    /** 上架一個：同名疊加、否則新增（新增時用建議售價）。超過貨架上限回 false。 */
    add(name: string): boolean {
        const l = listings.find(l => l.name === name);
        if (l) { l.count += 1; }
        else {
            if (listings.length >= Upgrades.shelfCap()) return false;
            listings.push({ name, price: this.suggestedPrice(name), count: 1 });
        }
        save();
        return true;
    },

    /** 撤下一個：數量歸零就移除。回傳是否成功。 */
    removeOne(name: string): boolean {
        const i = listings.findIndex(l => l.name === name);
        if (i < 0) return false;
        listings[i].count -= 1;
        if (listings[i].count <= 0) listings.splice(i, 1);
        save();
        return true;
    },

    /** 調整某上架品的售價（最低 1）。 */
    setPrice(name: string, price: number): void {
        const l = listings.find(l => l.name === name);
        if (!l) return;
        l.price = Math.max(1, Math.round(price));
        save();
    },

    /** 賣掉一個（Phase 2 顧客成交用）：回傳售價，賣不掉回 0。 */
    sellOne(name: string): number {
        const l = listings.find(l => l.name === name);
        if (!l || l.count <= 0) return 0;
        const price = l.price;
        this.removeOne(name);
        return price;
    },
};
