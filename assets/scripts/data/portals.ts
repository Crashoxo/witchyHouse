/**
 * 地圖邊界上的傳送點（走出去換場景的那個「門」）。
 *
 * 原本走到那一側的**任何地方**都會換場景，玩家看不出邊界哪裡能走；改成整條邊只有
 * 一個定點會傳送，並由 PortalGlow 在那個點畫上光暈。這裡定的是「那個點在邊上的位置」：
 *   - 左右側的邊 → at 是 y 座標
 *   - 上下側的邊 → at 是 x 座標
 * span＝從那個點往兩邊各多寬算在門內（像素）。光暈畫得比 span 小一點，
 * 讓「看得到的地方一定走得過去」，不會有推了沒反應的挫折。
 *
 * 走哪一側、去哪個場景仍然是 Player 節點上 PlayerController 的 @property
 * (nextMapScene / nextMapEdge)；這裡只補「那一側的哪個位置」，放這邊是為了
 * 不用動場景檔（Cocos 開著時改場景會被編輯器存檔蓋掉）。
 */
export interface EdgePortal {
    scene: string;   // 這一張地圖
    side: string;    // 走出哪一側：left / right / top / bottom
    to: string;      // 走出去會到哪個場景
    at: number;      // 傳送點在邊上的位置（左右側＝y、上下側＝x）
    span: number;    // 門的半寬（像素）
    inset?: number;  // 光暈往地圖內縮多少（不填＝DEFAULT_INSET）
}

/**
 * 光暈往地圖內縮的預設值。刻意小於光圈半徑（PortalGlow.EDGE_RX = 78）——
 * 光圈會被畫面邊緣切掉一部分，那樣才像「邊界上的一道門」，而不是浮在地上的一團光。
 * 想讓某張地圖的傳送點退離邊界，就在下面那筆給它比較大的 inset。
 */
export const DEFAULT_INSET = 26;

export const EDGE_PORTALS: EdgePortal[] = [
    // 森林東側 → 城鎮：玩家出生在 (0,0)，這一段東側沒有樹擋著
    { scene: 'main', side: 'right', to: 'town', at: 0, span: 80 },
    // 森林北側 → 糖果鎮（森林上面那張地圖）
    { scene: 'main', side: 'top', to: 'candy', at: 0, span: 100 },
    // 城鎮西側 → 森林：對準往西的泥土路 road-dirt-v-a (y=-40)，也是玩家進城的抵達點
    { scene: 'town', side: 'left', to: 'main', at: -40, span: 80 },
    // 店內下方 → 城鎮：對準玩家從城鎮進店的抵達點＝店門口
    { scene: 'shop', side: 'bottom', to: 'town', at: -83, span: 80 },
    // 糖果鎮南側 → 回森林
    { scene: 'candy', side: 'bottom', to: 'main', at: 0, span: 100 },
];

export const DEFAULT_EDGE_PORTAL: EdgePortal = { scene: '', side: '', to: '', at: 0, span: 80 };

/** 某個場景的所有邊界出口（可以有好幾個，例：森林往東到城鎮、往北到糖果鎮）。 */
export function edgePortalsOf(scene: string): EdgePortal[] {
    return EDGE_PORTALS.filter(p => p.scene === scene);
}

/** 某個場景在某一側的出口；沒有就回 null。 */
export function edgePortalAt(scene: string, side: string): EdgePortal | null {
    return EDGE_PORTALS.find(p => p.scene === scene && p.side === side) ?? null;
}
