import { SaveManager } from './SaveManager';
import { Wallet } from './Wallet';
import { DailyLog } from './DailyLog';
import { FURNITURE, FurnitureDef, furnitureDef, fits, frontCorner, footprintCenter,
         DEFAULT_SALE_CELL, Pt } from './data/shopRoom';

/**
 * 店內家具的資料層（module + SaveManager，仿 DecorCatalog/Wallet 中央化）。
 *   - owned：每種家具買了幾件。
 *   - placed：擺出來的實例（家具 id + 放在哪一格）。**格座標，不是像素座標** ——
 *     這樣之後房間放大縮小、底圖重畫，家具還是待在同一格。
 *
 * 販售桌（def.sale）比較特別：上架的商品陳列在它的檯面上、顧客也走到它前面買，
 * 所以開新檔時直接送一張並擺好（沒有它店就沒辦法做生意）。
 */

/**
 * `flip`＝左右翻面。等距房間有兩面後牆，而家具圖只畫了一個朝向（背板朝畫面左上），
 * 靠右後牆時要水平鏡像才會背貼牆。錨點是 (0.5, 0)、前角就在圖的正下方中央，
 * 所以鏡像＝`node.scale.x = -1`，位置完全不用改。
 * ⚠️ 光源會從左上翻到右上 —— 實際擺出來看不太出來（比對過），比再生一組八朝向划算。
 */
export interface PlacedFurniture { id: string; gx: number; gy: number; flip?: boolean; }

const KEY = 'witch.room';

interface SaveShape { owned: Record<string, number>; placed: PlacedFurniture[]; }

function blank(): SaveShape {
    // 新開的店：送一張販售桌並擺在預設位置
    return { owned: { sale_table: 1 }, placed: [{ id: 'sale_table', ...DEFAULT_SALE_CELL }] };
}

function load(): SaveShape {
    try {
        const raw = SaveManager.getString(KEY);
        if (raw) {
            const o = JSON.parse(raw);
            if (o && typeof o === 'object') {
                const owned: Record<string, number> = {};
                const src = o.owned;
                if (src && typeof src === 'object') {
                    for (const k of Object.keys(src)) {
                        if (furnitureDef(k) && typeof src[k] === 'number') owned[k] = src[k];
                    }
                }
                const placed: PlacedFurniture[] = [];
                if (Array.isArray(o.placed)) {
                    for (const p of o.placed) {
                        const d = p && furnitureDef(p.id);
                        if (!d || typeof p.gx !== 'number' || typeof p.gy !== 'number') continue;
                        if (!fits(p.gx, p.gy, d.w, d.h)) continue;   // 房間改過大小的舊存檔
                        placed.push({ id: d.id, gx: p.gx, gy: p.gy, flip: !!p.flip });
                    }
                }
                // 舊檔沒有販售桌就補一張，不然店開不了
                if (!placed.some(p => furnitureDef(p.id)?.sale)) {
                    owned.sale_table = Math.max(1, owned.sale_table ?? 0);
                    placed.push({ id: 'sale_table', ...DEFAULT_SALE_CELL });
                }
                return { owned, placed };
            }
        }
    } catch (e) { /* 壞檔就當新的 */ }
    return blank();
}

let data: SaveShape = load();

function save() { SaveManager.setString(KEY, JSON.stringify(data)); }

/** 某件家具佔的所有格子。 */
function cellsOf(p: PlacedFurniture): string[] {
    const d = furnitureDef(p.id);
    if (!d) return [];
    const out: string[] = [];
    for (let c = 0; c < d.w; c++) {
        for (let r = 0; r < d.h; r++) out.push(`${p.gx + c},${p.gy + r}`);
    }
    return out;
}

export const RoomLayout = {
    catalog: FURNITURE,

    def(id: string): FurnitureDef | undefined { return furnitureDef(id); },

    ownedCount(id: string): number { return data.owned[id] ?? 0; },

    placedList(): PlacedFurniture[] { return data.placed.slice(); },

    placedCountOf(id: string): number { return data.placed.reduce((n, p) => n + (p.id === id ? 1 : 0), 0); },

    /** 買了但還沒擺出來的數量（＝托盤裡可以拿出來擺的）。 */
    unplaced(id: string): number {
        return Math.max(0, this.ownedCount(id) - this.placedCountOf(id));
    },

    /** 花金幣買一件（錢不夠回 false）。 */
    buy(id: string): boolean {
        const d = furnitureDef(id);
        if (!d || d.price <= 0 || Wallet.gold < d.price) return false;
        Wallet.add(-d.price);
        DailyLog.recordSpend(d.price);
        data.owned[id] = (data.owned[id] ?? 0) + 1;
        save();
        return true;
    },

    /**
     * 這件家具放得進 (gx,gy) 嗎：整塊要在地板上，而且不能跟別件重疊。
     * @param skip 搬動中的那一件（檢查時要忽略它自己原本佔的格子）
     */
    canPlace(id: string, gx: number, gy: number, skip?: PlacedFurniture): boolean {
        const d = furnitureDef(id);
        if (!d || !fits(gx, gy, d.w, d.h)) return false;
        const taken = new Set<string>();
        for (const p of data.placed) {
            if (skip && p === skip) continue;
            for (const c of cellsOf(p)) taken.add(c);
        }
        for (const c of cellsOf({ id, gx, gy })) {
            if (taken.has(c)) return false;
        }
        return true;
    },

    /** 整批覆寫（佈置模式按「完成」時用）。 */
    setPlaced(list: PlacedFurniture[]) {
        data.placed = list.map(p => ({ id: p.id, gx: p.gx, gy: p.gy, flip: !!p.flip }));
        save();
    },

    /** 目前的販售桌（沒有回 null）。 */
    saleTable(): PlacedFurniture | null {
        return data.placed.find(p => furnitureDef(p.id)?.sale) ?? null;
    },

    /** 販售桌檯面中心（商品陳列位置）；沒有販售桌回 null。 */
    saleTop(): Pt | null {
        const t = this.saleTable();
        const d = t && furnitureDef(t.id);
        if (!t || !d) return null;
        const c = footprintCenter(t.gx, t.gy, d.w, d.h);
        return { x: c.x, y: c.y + SALE_TOP_H };
    },

    /** 顧客站在販售桌前挑東西的位置；沒有販售桌回 null。 */
    saleFront(): Pt | null {
        const t = this.saleTable();
        const d = t && furnitureDef(t.id);
        if (!t || !d) return null;
        const f = frontCorner(t.gx, t.gy, d.w, d.h);
        return { x: f.x, y: f.y - SALE_STAND_GAP };
    },
};

/** 販售桌檯面離地多高（跟 tools/gen_shop_room.py 裡 sale_table 的 height 一致）。 */
const SALE_TOP_H = 20;
/** 顧客站在桌前角再往畫面下方多遠（不要跟桌子疊在一起）。 */
const SALE_STAND_GAP = 26;
