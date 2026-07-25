import { _decorator, Component, Node, UITransform, UIOpacity, Graphics, Color, Vec3, find } from 'cc';
import { TimeSystem } from './TimeSystem';
const { ccclass } = _decorator;

/**
 * 城鎮路燈的夜間發光（town.scene 用）。
 *
 * 天色色板（DayNightTint）是整片蓋在世界之上把場景壓暗，所以「發光」必須畫在色板
 * **之上**才不會被夜色吃掉。這裡另外在 Canvas 建一層 GlowLayer（插在色板上方、HUD
 * 下方），為每盞路燈放一個暖色光暈；濃度依時間：傍晚漸亮 → 整夜全亮 → 清晨熄滅。
 *
 * 路燈是 World/Props 底下的節點、會隨鏡頭捲動，所以每幀把光暈用世界座標對回燈頭位置。
 * 安裝同 Clock/DayNightTint：由 PlayerController.onLoad 在 town 場景呼叫 ensure()。
 */

// 各種路燈的光暈設定：match＝節點名（含即算）、offX/offY＝相對節點底部中心的燈頭位移、radius＝光暈半徑。
const LAMPS = [
    { match: 'town-lamp-post',  offX: 0, offY: 118, radius: 40 },
    { match: 'town-lamp-small', offX: 0, offY: 74,  radius: 30 },
    { match: 'town-fence-lamp', offX: 0, offY: 58,  radius: 34 },
];
const GLOW_COLOR = { r: 255, g: 208, b: 120 };   // 暖黃燈光
const MAX_OPACITY = 0.5;                          // 深夜最亮時的濃度（0..1）

interface Glow { op: UIOpacity; lampUT: UITransform; offX: number; offY: number; }

@ccclass('LampGlow')
export class LampGlow extends Component {
    static instance: LampGlow | null = null;

    static ensure(): LampGlow | null {
        if (LampGlow.instance && LampGlow.instance.isValid) return LampGlow.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[LampGlow] 找不到 Canvas'); return null; }
        const node = new Node('LampGlow');
        node.layer = canvas.layer;
        canvas.addChild(node);
        // 疊在天色色板之上（沒有色板就退而放在 World 之上）、HUD 之下。
        const tint = canvas.getChildByName('DayNightTint');
        const world = canvas.getChildByName('World');
        const base = tint ?? world;
        node.setSiblingIndex(base ? base.getSiblingIndex() + 1 : 1);
        return node.addComponent(LampGlow);
    }

    private layerUT: UITransform | null = null;
    private glows: Glow[] = [];
    private tmp = new Vec3();
    private lastFactor = -1;

    onLoad() {
        LampGlow.instance = this;
        this.layerUT = this.addComponent(UITransform);

        const props = find('Canvas/World/Props');
        if (!props) { console.warn('[LampGlow] 找不到 World/Props，無法建立路燈光暈'); return; }

        for (const lamp of props.children) {
            const cfg = LAMPS.find(l => lamp.name.includes(l.match));
            if (!cfg) continue;
            const lampUT = lamp.getComponent(UITransform);
            if (!lampUT) continue;

            const gn = new Node('glow');
            gn.layer = this.node.layer;
            gn.addComponent(UITransform);
            const g = gn.addComponent(Graphics);
            drawGlow(g, cfg.radius);
            const op = gn.addComponent(UIOpacity);
            op.opacity = 0;
            this.node.addChild(gn);

            this.glows.push({ op, lampUT, offX: cfg.offX, offY: cfg.offY });
        }
    }
    onDestroy() { if (LampGlow.instance === this) LampGlow.instance = null; }

    update() {
        if (!this.layerUT) return;
        const factor = lampOn(TimeSystem.todHours);

        // 濃度沒明顯變化就不改 opacity（但位置每幀都要追，因為鏡頭在捲動）。
        const changed = Math.abs(factor - this.lastFactor) > 0.004;
        if (changed) this.lastFactor = factor;

        for (const glow of this.glows) {
            if (!glow.lampUT.isValid) continue;
            // 燈頭世界座標 → 本層座標（World 捲動時燈的螢幕位置會變，故每幀對位）
            glow.lampUT.convertToWorldSpaceAR(this.tmp.set(glow.offX, glow.offY, 0), this.tmp);
            this.layerUT.convertToNodeSpaceAR(this.tmp, this.tmp);
            glow.op.node.setPosition(this.tmp);
            if (changed) glow.op.opacity = Math.round(255 * MAX_OPACITY * factor);
        }
    }
}

/** 依當日時數算路燈亮度（0..1）：傍晚漸亮、整夜全亮、清晨熄滅、白天全暗。 */
function lampOn(h: number): number {
    if (h >= 19.5) return 1;              // 19:30–02:00 全亮
    if (h >= 17.5) return (h - 17.5) / 2; // 17:30–19:30 漸亮
    if (h <= 7.0)  return (7.0 - h) * 0.6; // 06:00–07:00 清晨殘留漸滅（06:00≈0.6）
    return 0;                             // 白天全暗
}

/** 用同心圓疊出柔和的放射狀光暈（一般 alpha，中心疊得越多越亮）。畫一次即可，之後只調 UIOpacity。 */
function drawGlow(g: Graphics, radius: number) {
    const rings = 12;
    for (let i = rings; i >= 1; i--) {
        const r = radius * (i / rings);
        g.fillColor = new Color(GLOW_COLOR.r, GLOW_COLOR.g, GLOW_COLOR.b, 26);
        g.circle(0, 0, r);
        g.fill();
    }
}
