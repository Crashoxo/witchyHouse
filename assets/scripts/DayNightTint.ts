import { _decorator, Component, Node, UITransform, Graphics, Color, view, find } from 'cc';
import { TimeSystem } from './TimeSystem';
const { ccclass } = _decorator;

/**
 * 戶外天色色板（森林 main.scene／城鎮 town.scene 用）。
 *
 * 房間（brew）是「一張完整背景圖」，所以 BrewRoom 直接換白天/夜晚兩張圖；但森林
 * 和城鎮是一堆節點（樹、路面、噴泉、路燈…）拼的，逐一出圖不切實際。這裡改用一層
 * 全螢幕半透明色板疊在世界之上、HUD 之下，顏色與濃度依 TimeSystem 連續變化，
 * 就得到 白天→黃昏→夜晚→拂曉 的平滑天色，且黃昏/中間色都免費、隨時可調。
 *
 * 安裝方式同 Clock/Hud：由 PlayerController.onLoad 依場景名呼叫 ensure()（只在
 * main/town 裝，室內 brew/shop 不裝），不必手動在編輯器掛節點。色板不吃輸入，
 * 玩家照常走動、點地面移動。混合用一般 alpha（同 SleepOverlay 的深色幕），不需材質。
 */

// 天色關鍵幀：[當日時數 6..26, R, G, B, alpha(0..1)]。相鄰幀之間線性內插。
// alpha=0 的那幾幀顏色不影響畫面（全透明），純粹當「白天」錨點。要調天色改這裡即可。
type Key = [number, number, number, number, number];
const KEYS: Key[] = [
    [6.0,   30,  45, 100, 0.42],  // 06:00 拂曉：冷藍微光（剛醒）
    [8.0,  255, 240, 200, 0.00],  // 08:00 天亮：全透明
    [16.5, 255, 240, 200, 0.00],  // 16:30 白天：全透明
    [18.0, 240, 120,  40, 0.22],  // 18:00 黃昏：暖橘（時鐘此時換月亮）
    [19.5, 110,  70, 120, 0.38],  // 19:30 暮色：偏紫
    [21.0,  25,  35,  90, 0.50],  // 21:00 入夜：深藍
    [26.0,  18,  26,  72, 0.55],  // 02:00 深夜（昏倒前最暗）
];

@ccclass('DayNightTint')
export class DayNightTint extends Component {
    static instance: DayNightTint | null = null;

    /** 在 Canvas、World 正上方建一層天色色板；已存在就沿用（同 Clock.ensure）。 */
    static ensure(): DayNightTint | null {
        if (DayNightTint.instance && DayNightTint.instance.isValid) return DayNightTint.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[DayNightTint] 找不到 Canvas，無法建立天色色板'); return null; }

        const node = new Node('DayNightTint');
        node.layer = canvas.layer;
        canvas.addChild(node);
        // 插在 World 正上方 → 蓋住整個世界，但仍在 HUD（Clock/Hud/Wallet，接在其後）之下。
        const world = canvas.getChildByName('World');
        node.setSiblingIndex(world ? world.getSiblingIndex() + 1 : 1);
        return node.addComponent(DayNightTint);
    }

    private g: Graphics | null = null;
    private lastKey = '';        // 節流：量化後的色值沒變就不重畫
    private w = 0;               // 色板尺寸（蓋滿視窗）
    private h = 0;

    onLoad() {
        DayNightTint.instance = this;

        const vs = view.getVisibleSize();
        this.w = vs.width * 1.4;   // 放大 1.4 倍，避免視窗尺寸/縮放模式差異露出邊
        this.h = vs.height * 1.4;
        this.addComponent(UITransform)!.setContentSize(this.w, this.h);
        this.node.setPosition(0, 0, 0);
        this.g = this.addComponent(Graphics);

        this.redraw();
    }
    onDestroy() { if (DayNightTint.instance === this) DayNightTint.instance = null; }

    update() { this.redraw(); }

    /** 依現在時刻算天色並（必要時）重畫。 */
    private redraw() {
        if (!this.g) return;

        const c = sample(TimeSystem.todHours);
        // 量化節流：色值/濃度沒有明顯變化就跳過重畫
        const key = `${Math.round(c.r / 3)},${Math.round(c.g / 3)},${Math.round(c.b / 3)},${Math.round(c.a * 60)}`;
        if (key === this.lastKey) return;
        this.lastKey = key;

        const g = this.g;
        g.clear();
        if (c.a <= 0.002) return;                       // 全透明就不畫
        g.fillColor = new Color(Math.round(c.r), Math.round(c.g), Math.round(c.b), Math.round(c.a * 255));
        g.rect(-this.w / 2, -this.h / 2, this.w, this.h);
        g.fill();
    }
}

/** 在 KEYS 上依當日時數線性內插出 {r,g,b,a}。 */
function sample(h: number): { r: number; g: number; b: number; a: number } {
    if (h <= KEYS[0][0]) { const k = KEYS[0]; return { r: k[1], g: k[2], b: k[3], a: k[4] }; }
    const last = KEYS[KEYS.length - 1];
    if (h >= last[0]) return { r: last[1], g: last[2], b: last[3], a: last[4] };
    for (let i = 0; i < KEYS.length - 1; i++) {
        const a = KEYS[i], b = KEYS[i + 1];
        if (h >= a[0] && h <= b[0]) {
            const t = (h - a[0]) / (b[0] - a[0]);
            return {
                r: a[1] + (b[1] - a[1]) * t,
                g: a[2] + (b[2] - a[2]) * t,
                b: a[3] + (b[3] - a[3]) * t,
                a: a[4] + (b[4] - a[4]) * t,
            };
        }
    }
    return { r: last[1], g: last[2], b: last[3], a: last[4] };
}
