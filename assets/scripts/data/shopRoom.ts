/**
 * 店內等距房間：格子座標系與家具目錄。
 *
 * 地板是 GRID_W × GRID_H 的等距菱形磚，**一塊磚＝一個家具放置格**。格子座標 (gx, gy)
 * 的 gx 往畫面右下、gy 往畫面左下：
 *
 *      tile(gx,gy) 中心 = ( ORIGIN_X + (gx-gy)*TILE_W/2 , ORIGIN_Y - (gx+gy)*TILE_H/2 )
 *
 * ⚠️ 這套數學跟 `tools/gen_shop_room.py`（畫底圖與家具圖的產生器）是同一套，
 *    改任何一個常數都要兩邊一起改，否則家具會跟磚縫對不齊。
 *
 * 家具圖的錨點約定：**圖的正下方中央＝佔地的「前角」**（＝佔地最靠畫面下方那格的下角）。
 * 所以節點用錨點 (0.5, 0)、位置擺在 frontCorner() 算出來的座標即可，
 * 而且 position.y 剛好是佔地的最前緣 → YSortLayer 的前後遮擋自然就對。
 */

// ⚠️ 磚的尺寸是配合美術來源訂的：PixelLab 的等距磚原生輸出 32x32（菱形 32x16），
//    我們 x2 NEAREST 放大＝遊戲內一格 64x32。改這裡等於要重出所有地板/家具素材。
export const TILE_W = 64;       // 一格的寬（等距 2:1）
export const TILE_H = 32;       // 一格的高
export const GRID_W = 14;       // 橫向格數（gx: 0..GRID_W-1）
export const GRID_H = 10;       // 縱向格數（gy: 0..GRID_H-1）
export const ORIGIN_X = -64;    // tile(0,0) 中心的世界座標（讓地板中心落在 (0,-68)）
export const ORIGIN_Y = 108;
export const ROOM_W = 960;      // 底圖尺寸（＝Ground 的 contentSize）
export const ROOM_H = 640;

export interface Cell { gx: number; gy: number; }
export interface Pt { x: number; y: number; }

/** 格子中心的世界座標。 */
export function tileCenter(gx: number, gy: number): Pt {
    return { x: ORIGIN_X + (gx - gy) * TILE_W / 2, y: ORIGIN_Y - (gx + gy) * TILE_H / 2 };
}

/** 格子的「下角」＝落地點（家具/裝飾的錨點對在這裡）。 */
export function tileFront(gx: number, gy: number): Pt {
    return { x: ORIGIN_X + (gx - gy) * TILE_W / 2, y: ORIGIN_Y - (gx + gy) * TILE_H / 2 - TILE_H / 2 };
}

/** 佔地 fw×fh 的家具擺在 (gx,gy)（左上角那格）時，前角的世界座標。 */
export function frontCorner(gx: number, gy: number, fw: number, fh: number): Pt {
    return tileFront(gx + fw - 1, gy + fh - 1);
}

/** 佔地的中心（商品要畫在檯面正中央時用）。 */
export function footprintCenter(gx: number, gy: number, fw: number, fh: number): Pt {
    const a = tileCenter(gx, gy);
    const b = tileCenter(gx + fw - 1, gy + fh - 1);
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

/** 世界座標 → 連續格座標（會是小數，也可能落在格子外）。 */
export function toGrid(x: number, y: number): Pt {
    const a = (x - ORIGIN_X) / (TILE_W / 2);
    const b = (ORIGIN_Y - y) / (TILE_H / 2);
    return { x: (a + b) / 2, y: (b - a) / 2 };
}

/** 世界座標 → 最近的那一格。 */
export function worldToTile(x: number, y: number): Cell {
    const g = toGrid(x, y);
    return { gx: Math.round(g.x), gy: Math.round(g.y) };
}

/** 這一格在不在地板上。 */
export function inGrid(gx: number, gy: number): boolean {
    return gx >= 0 && gx < GRID_W && gy >= 0 && gy < GRID_H;
}

/** 佔地 fw×fh 擺在 (gx,gy) 時整塊都在地板上嗎。 */
export function fits(gx: number, gy: number, fw: number, fh: number): boolean {
    return inGrid(gx, gy) && inGrid(gx + fw - 1, gy + fh - 1);
}

/** 把 (gx,gy) 夾到「整件家具都放得下」的範圍內。 */
export function clampCell(gx: number, gy: number, fw: number, fh: number): Cell {
    return {
        gx: Math.min(GRID_W - fw, Math.max(0, gx)),
        gy: Math.min(GRID_H - fh, Math.max(0, gy)),
    };
}

/**
 * 把落腳點夾在地板菱形內。
 * ⚠️ 等距房間**不能**用 PlayerController 原本的矩形夾邊 —— 塞得進這個菱形的最大矩形
 * 只有地板的一小塊（地板本身是 768×384），玩家會被關在正中間。所以改成換算成格
 * 座標後夾住 col/row，再換算回來。margin 是離最外圈磚緣留幾格（避免整個人站到磚外）。
 */
export function clampToFloor(x: number, y: number, margin = 0.18): Pt {
    const g = toGrid(x, y);
    const lo = -0.5 + margin;
    const c = Math.min(GRID_W - 0.5 - margin, Math.max(lo, g.x));
    const r = Math.min(GRID_H - 0.5 - margin, Math.max(lo, g.y));
    return { x: ORIGIN_X + (c - r) * TILE_W / 2, y: ORIGIN_Y - (c + r) * TILE_H / 2 };
}

// ──────────── 家具目錄 ────────────

export interface FurnitureDef {
    id: string;          // 對應 resources/furniture/<id>.png
    name: string;        // 顯示名稱
    w: number;           // 佔地寬（格）
    h: number;           // 佔地深（格）
    price: number;       // 售價（0＝開店就有，買不到）
    desc: string;
    /** true＝販售桌：上架的商品會陳列在它的檯面上，顧客也是走到它前面來買。 */
    sale?: boolean;
    /** true＝貨架：花店裡另開一個分頁賣，不跟桌椅擠在同一頁。 */
    shelf?: boolean;
}

/**
 * 貨架（PixelLab 手繪，來源在 `tools/art-src/furniture/shelf/`，由
 * `tools/import_furniture.py` 匯入成 `resources/furniture/<id>.png`）。
 *
 * 十六款全部佔地 **1×2 格**（背板朝畫面左上、開口朝右下 → 靠左後牆那排最好看）。
 * ⚠️ 舊的程式生 placeholder「靠牆貨架」(`wall_shelf`) **已整個移除、也買不到**
 *    （使用者要求十六款全用新 id）。舊存檔裡若有 `wall_shelf`，`RoomLayout` 的
 *    sanitize 查不到定義就會直接丟掉，不會壞檔、但那張架子與花掉的金幣不退。
 *
 * 下面只列每款不一樣的欄位，w/h/shelf 由 SHELVES 統一補上。
 */
const SHELF_STYLES: { id: string; name: string; price: number; desc: string }[] = [
    { id: 'shelf_narrow',  name: '三層細架',   price: 200, desc: '細長的三層開放架，牆邊塞哪裡都不佔位。' },
    { id: 'shelf_tall',    name: '四層高架',   price: 240, desc: '瘦高的四層架，往上長比較省地。' },
    { id: 'shelf_cross',   name: '交叉撐架',   price: 260, desc: '背後打了交叉木撐，粗獷耐看。' },
    { id: 'shelf_plank',   name: '厚板木架',   price: 280, desc: '厚實的原木層板，帶點灰調的舊木色。' },
    { id: 'shelf_box',     name: '素面方架',   price: 300, desc: '方方正正的木箱式貨架，什麼都好搭。' },
    { id: 'shelf_slat',    name: '木條背板架', price: 320, desc: '背板是一根根木條，透光又通風。' },
    { id: 'shelf_back',    name: '封背貨架',   price: 320, desc: '整面實心背板，擺小東西不會掉到牆縫裡。' },
    { id: 'shelf_round',   name: '圓角貨架',   price: 340, desc: '四角磨圓的箱型架，線條柔和。' },
    { id: 'shelf_deep',    name: '深底貨架',   price: 340, desc: '最下層特別深，重的東西往下擺。' },
    { id: 'shelf_curve',   name: '曲線頂長架', price: 360, desc: '頂板做成波浪曲線，像老家具行的樣品架。' },
    { id: 'shelf_two',     name: '雙層抽屜架', price: 380, desc: '兩層層板加一個下抽屜，收納最實用。' },
    { id: 'shelf_scallop', name: '波浪簷貨架', price: 400, desc: '頂上一排扇貝花邊，很有店面的味道。' },
    { id: 'shelf_peak',    name: '尖頂小屋架', price: 420, desc: '尖屋頂造型，擺在角落像一間小房子。' },
    { id: 'shelf_arch',    name: '拱頂貨架',   price: 440, desc: '半圓拱頂，最像藥草鋪會有的那種櫃子。' },
    { id: 'shelf_cabinet', name: '附櫃貨架',   price: 460, desc: '下方多一個對開小櫃，藏東西剛好。' },
    { id: 'shelf_drawer',  name: '抽屜貨架',   price: 500, desc: '底下六個小抽屜，最貴也最有份量。' },
];

const SHELVES: FurnitureDef[] = SHELF_STYLES.map(d =>
    ({ id: d.id, name: d.name, price: d.price, desc: d.desc, w: 1, h: 2, shelf: true }));

/**
 * 店裡買得到的家具＝**只有貨架**（使用者要求：桌椅那幾件還是程式生的木頭方塊，
 * 先整個拿掉，等手繪圖畫好再放回來）。
 *
 * `sale_table` 販售桌**一定要留在目錄裡** —— 它是開店就送的（price 0 ＝買不到，
 * 花店不會列出來），上架的商品陳列與顧客結帳都靠它，`RoomLayout` 找不到它會開不了店。
 *
 * ⚠️ 用 `concat` 不用陣列展開 —— Cocos 建置會把程式降到 ES5，展開語法在這個專案
 *    踩過雷（`GameArt.customerNames()` 那次），陣列串接寫 concat 最保險。
 *
 * ── 畫好桌椅美術之後，把下面這三筆貼回陣列裡就會重新上架 ──
 *    { id: 'long_table',   name: '長木桌',   w: 3, h: 1, price: 260,
 *      desc: '佔三格的大桌子，擺在店中央很有氣勢。' },
 *    { id: 'round_stand',  name: '展示台',   w: 1, h: 1, price: 120,
 *      desc: '一格大的小檯子，塞角落剛剛好。' },
 *    { id: 'flower_bench', name: '花草長凳', w: 2, h: 1, price: 180,
 *      desc: '淺綠色的長凳，放盆栽或給客人坐都行。' },
 *    （同時要把 DecorShopPanel 的「家具」分頁加回去 —— 作法照「貨架」分頁抄。）
 */
export const FURNITURE: FurnitureDef[] = ([
    { id: 'sale_table', name: '販售桌', w: 2, h: 1, price: 0, sale: true,
      desc: '上架的商品會擺在這張桌上，顧客走到桌前挑東西。' },
] as FurnitureDef[]).concat(SHELVES);


/**
 * 門口那幾格不給擺東西（擺上去會把出口堵住、光圈也會被蓋掉）。
 * 一格只有 64×32，光一格擋不住整個門，所以連同上下左右四格一起保留。
 */
export function reservedCells(): Cell[] {
    const out: Cell[] = [];
    for (const d of [DOOR_TOWN, DOOR_BREW, DOOR_GARDEN]) {
        for (const [dx, dy] of [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]]) {
            const gx = d.gx + dx, gy = d.gy + dy;
            if (inGrid(gx, gy)) out.push({ gx, gy });
        }
    }
    return out;
}

export function furnitureDef(id: string): FurnitureDef | undefined {
    return FURNITURE.find(f => f.id === id);
}

/** 開店時就送的第一張販售桌擺在哪一格（沒有它就沒辦法賣東西）。 */
export const DEFAULT_SALE_CELL: Cell = { gx: 5, gy: 2 };

/**
 * 玩家從城鎮進店時的抵達點。
 * ⚠️ 要離 DOOR_TOWN 夠遠：門是「走上去就過圖」的（autoRange 70），出生點若太近，
 * 一進店往前走兩步就會被彈回城鎮（藥水室那道門踩過同樣的坑）。這裡相距 148px。
 */
export const PLAYER_SPAWN: Cell = { gx: 6, gy: 5 };
export const DOOR_TOWN: Cell = { gx: 11, gy: 9 };   // 前方（畫面下）走出去回城鎮
export const DOOR_BREW: Cell = { gx: 13, gy: 0 };   // 右角落 → 藥水室（房間）
export const DOOR_GARDEN: Cell = { gx: 0, gy: 9 };  // 左角落 → 後花園
