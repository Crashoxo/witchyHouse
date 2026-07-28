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
    scene: string;   // 場景名
    at: number;      // 傳送點在邊上的位置（左右側＝y、上下側＝x）
    span: number;    // 門的半寬（像素）
    inset?: number;  // 光暈往地圖內縮多少（不填＝DEFAULT_INSET）
}

/**
 * 光暈往地圖內縮的預設值。比光圈半徑（PortalGlow.EDGE_RX = 78）大一點，
 * 整圈才會完全落在地圖內；想讓傳送點更貼著邊界就把 inset 調小，
 * 光圈會被畫面邊緣切掉一部分，但看起來更像「邊界上的一道門」。
 */
export const DEFAULT_INSET = 82;

export const EDGE_PORTALS: EdgePortal[] = [
    // 森林東側 → 城鎮：玩家出生在 (0,0)，這一段東側沒有樹擋著。
    // inset 小＝光點更靠右（貼著地圖東緣），被切到一點沒關係
    { scene: 'main', at: 0, span: 80, inset: 26 },
    // 城鎮西側 → 森林：對準往西的泥土路 road-dirt-v-a (y=-40)，也是玩家進城的抵達點。
    // inset 小＝光點更靠左
    { scene: 'town', at: -40, span: 80, inset: 26 },
    // 店內下方 → 城鎮：對準玩家從城鎮進店的抵達點＝店門口
    { scene: 'shop', at: -83, span: 80 },
];

export const DEFAULT_EDGE_PORTAL: EdgePortal = { scene: '', at: 0, span: 80 };

/** 查某個場景的邊界傳送點；沒設定的場景給預設（邊的正中間）。 */
export function edgePortalOf(scene: string): EdgePortal {
    const found = EDGE_PORTALS.find(p => p.scene === scene);
    return found ?? DEFAULT_EDGE_PORTAL;
}
