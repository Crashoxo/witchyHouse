import { Wallet } from './Wallet';
import { SaveManager } from './SaveManager';
import { DecorDef, DECOR_CATALOG } from './data/decor';

/**
 * 裝飾品的資料層（module + localStorage，仿 ShopStock/Wallet 中央化）：
 *   - 目錄 DECOR_CATALOG：花店賣的 16 種裝飾（id / 中文名 / 售價）。
 *   - owned：每種買了幾個（花錢從花店買來的）。
 *   - placed：目前擺在自己店裡的實例（id + 房間內座標 x,y）。
 * 「托盤裡可擺的數量」= owned - 已擺出的同 id 數量。純裝飾，暫不影響數值。
 */
// DecorDef / DECOR_CATALOG 已搬到 data/decor.ts；re-export 供既有 import（如 DecorShopPanel）使用。
export type { DecorDef };
export { DECOR_CATALOG };
export interface Placed { id: string; x: number; y: number; }

const OWN_KEY = 'witch.decor.owned';
const PLACED_KEY = 'witch.decor.placed';

function loadOwned(): Record<string, number> {
    try {
        const raw = SaveManager.getString(OWN_KEY);
        if (raw) {
            const o = JSON.parse(raw);
            if (o && typeof o === 'object') return o as Record<string, number>;
        }
    } catch (e) { /* 壞檔就當空的 */ }
    return {};
}

function loadPlaced(): Placed[] {
    try {
        const raw = SaveManager.getString(PLACED_KEY);
        if (raw) {
            const arr = JSON.parse(raw);
            if (Array.isArray(arr)) {
                return arr.filter(p => p && typeof p.id === 'string'
                    && typeof p.x === 'number' && typeof p.y === 'number');
            }
        }
    } catch (e) { /* 壞檔就當空的 */ }
    return [];
}

let owned: Record<string, number> = loadOwned();
let placed: Placed[] = loadPlaced();

function saveOwned() { SaveManager.setString(OWN_KEY, JSON.stringify(owned)); }
function savePlaced() { SaveManager.setString(PLACED_KEY, JSON.stringify(placed)); }

export const DecorCatalog = {
    catalog: DECOR_CATALOG,

    def(id: string): DecorDef | undefined { return DECOR_CATALOG.find(d => d.id === id); },

    ownedCount(id: string): number { return owned[id] ?? 0; },

    placedCountOf(id: string): number { return placed.reduce((n, p) => n + (p.id === id ? 1 : 0), 0); },

    /** 托盤裡（買了但還沒擺出去）可用的數量。 */
    unplacedCount(id: string): number {
        return Math.max(0, this.ownedCount(id) - this.placedCountOf(id));
    },

    /** 從花店買一個：金幣夠才成交。 */
    buy(id: string): boolean {
        const d = this.def(id);
        if (!d || Wallet.gold < d.price) return false;
        Wallet.add(-d.price);
        owned[id] = this.ownedCount(id) + 1;
        saveOwned();
        return true;
    },

    /** 目前擺出來的清單（複製，外部別直接改）。 */
    placedList(): Placed[] { return placed.map(p => ({ ...p })); },

    /** 整批覆寫已擺清單並存檔（佈置模式結束時，用場上實際的裝飾節點寫回）。 */
    setPlaced(list: Placed[]): void {
        placed = list.map(p => ({ id: p.id, x: p.x, y: p.y }));
        savePlaced();
    },

    /** 擺一個到房間（需托盤還有存貨）；回傳新實例的 index，失敗回 -1。 */
    place(id: string, x: number, y: number): number {
        if (this.unplacedCount(id) <= 0) return -1;
        placed.push({ id, x, y });
        savePlaced();
        return placed.length - 1;
    },

    /** 移動已擺出的實例。 */
    move(index: number, x: number, y: number): void {
        const p = placed[index];
        if (!p) return;
        p.x = x; p.y = y;
        savePlaced();
    },

    /** 收回一個已擺出的實例（回到托盤，不退錢）。 */
    removeAt(index: number): void {
        if (index < 0 || index >= placed.length) return;
        placed.splice(index, 1);
        savePlaced();
    },
};
