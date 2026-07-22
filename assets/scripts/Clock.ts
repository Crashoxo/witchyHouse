import { _decorator, Component, Node, UITransform, Widget, Label, Sprite, SpriteFrame,
         UIOpacity, Color, Graphics, find } from 'cc';
import { TimeSystem } from './TimeSystem';
import { GameArt } from './GameArt';
import { UIState } from './UIState';
const { ccclass } = _decorator;

/**
 * 常駐時鐘 HUD：畫面右上角一個華麗盤面，顯示遊戲時間。
 * - 時針（華麗矛形）＋分針（細長）在羅馬數字圈上旋轉 → 一天的時間
 * - 中央 Month／Day 兩個卷軸框顯示當前月／日數字（畫在指針之上，永遠讀得到）
 * - 頂端徽章切換太陽／月亮 → 日夜
 * 仿 Hud/Inventory 的 ensure()：每個場景由 PlayerController.onLoad 叫出來，
 * 且它的 update() 是全遊戲唯一驅動 TimeSystem.tick 的地方（時間隨場景延續）。
 */

// 盤面顯示尺寸與版面比例（比例是對切好的 face.png 目視量測而來）
const D = 152;                 // 盤面顯示寬
const ASPECT = 670 / 674;      // face.png 高/寬
const Dh = D * ASPECT;
const R = D / 2;

// 指針美術：⚠️ 依「時鐘慣例」指派，非依檔名——時針用華麗矛形(hand-min)、
// 分針用細長(hand-day)；剩下的 hand-hour（樸素短針）暫不用。
// [檔名鍵, 原圖寬, 原圖高, 樞軸 anchorY(底部 knob 中心), 指尖伸到 R 的比例]
const HOUR = { key: 'hand-min', w: 37, h: 151, anchorY: 0.133, reach: 0.46 };
const MIN  = { key: 'hand-day', w: 35, h: 192, anchorY: 0.089, reach: 0.68 };

// 版面比例（face 分數座標，(0,0)＝盤心）
const MEDALLION_Y = 0.39;      // 頂端日月徽章：盤心往上 0.39*Dh
const BOX_Y = -0.05;           // Month/Day 框中心：盤心往下 0.05*Dh
const MONTH_X = -0.135;        // Month 框中心 x（*D）
const DAY_X = 0.145;           // Day 框中心 x（*D）
const ICON_H = 22;             // 日月圖示顯示高

@ccclass('Clock')
export class Clock extends Component {
    static instance: Clock | null = null;

    /** 取得時鐘；沒有的話自動在 Canvas 底下建一個（找不到 Canvas 回 null）。 */
    static ensure(): Clock | null {
        if (Clock.instance) return Clock.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[Clock] 找不到 Canvas，無法建立時鐘'); return null; }
        const node = new Node('Clock');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(Clock);
    }

    private faceSprite: Sprite | null = null;
    private hourNode: Node | null = null;
    private minNode: Node | null = null;
    private hourSprite: Sprite | null = null;
    private minSprite: Sprite | null = null;
    private handsOpacity: UIOpacity | null = null;
    private sunNode: Node | null = null;
    private moonNode: Node | null = null;
    private monthLabel: Label | null = null;
    private dayLabel: Label | null = null;

    private lastMonth = -1;
    private lastDay = -1;
    private lastNight: boolean | null = null;
    private warmed = false;      // 第一次 update 讓指針直接就位（不從 0 掃過去）
    private blinkT = 0;          // 暫停閃爍計時

    onLoad() {
        Clock.instance = this;
        this.build();
        GameArt.preload();
        GameArt.onReady(() => this.applyArt());
        if (GameArt.ready) this.applyArt();
    }
    onDestroy() {
        if (Clock.instance === this) Clock.instance = null;
    }

    update(dt: number) {
        // 開選單/對話時暫停時間（單人模式；星露谷式）
        const paused = UIState.modalOpen;

        // 全遊戲唯一的時間推進點
        TimeSystem.tick(dt, paused);

        // 指針轉：時間是 10 分鐘離散跳動，這裡用「最短路徑」朝目標角度快速補間，
        // 做出機械式 tick 而非硬跳（angle 正向為逆時針，時鐘要順時針故取負）。
        this.driveHand(this.hourNode, TimeSystem.hourFraction, dt);
        this.driveHand(this.minNode, TimeSystem.minuteFraction, dt);
        this.warmed = true;

        // 暫停時指針整組變灰閃爍（表示時間凍結）
        if (this.handsOpacity) {
            if (paused) {
                this.blinkT += dt;
                this.handsOpacity.opacity = Math.round(90 + 130 * (0.5 + 0.5 * Math.sin(this.blinkT * 7)));
            } else if (this.handsOpacity.opacity !== 255) {
                this.blinkT = 0;
                this.handsOpacity.opacity = 255;
            }
        }

        // 月/日數字有變才改
        const m = TimeSystem.month, d = TimeSystem.day;
        if (this.monthLabel && m !== this.lastMonth) { this.lastMonth = m; this.monthLabel.string = String(m); }
        if (this.dayLabel && d !== this.lastDay) { this.lastDay = d; this.dayLabel.string = String(d); }

        // 日夜切換太陽/月亮
        const night = TimeSystem.isNight;
        if (night !== this.lastNight) {
            this.lastNight = night;
            if (this.sunNode) this.sunNode.active = !night;
            if (this.moonNode) this.moonNode.active = night;
        }
    }

    /** 指針朝目標角度以最短路徑補間；第一次（未 warmed）直接就位。 */
    private driveHand(node: Node | null, fraction: number, dt: number) {
        if (!node) return;
        const target = -fraction * 360;
        if (!this.warmed) { node.angle = target; return; }
        const cur = node.angle;
        const diff = ((target - cur + 540) % 360) - 180;   // (-180,180] 最短角差
        node.angle = cur + diff * Math.min(1, dt * 12);
    }

    /** 建好節點結構（美術之後 applyArt 補上）。 */
    private build() {
        const layer = this.node.layer;

        // 本節點貼齊畫面右上角（anchor 右上，rect 往左下延伸）
        const ut = this.addComponent(UITransform)!;
        ut.setAnchorPoint(1, 1);
        ut.setContentSize(D, Dh);
        const widget = this.addComponent(Widget)!;
        widget.isAlignTop = true;
        widget.isAlignRight = true;
        widget.top = 14;
        widget.right = 14;
        widget.alignMode = Widget.AlignMode.ON_WINDOW_RESIZE;
        widget.updateAlignment();

        // dial 容器擺在 rect 正中央 → 底下所有東西都以盤心 (0,0) 為原點
        const dial = new Node('dial');
        dial.layer = layer;
        this.node.addChild(dial);
        dial.addComponent(UITransform);
        dial.setPosition(-D / 2, -Dh / 2, 0);

        const add = (name: string): Node => {
            const n = new Node(name); n.layer = layer; dial.addChild(n);
            n.addComponent(UITransform);
            return n;
        };
        const sizedSprite = (n: Node, w: number, h: number): Sprite => {
            const u = n.getComponent(UITransform)!;
            u.setContentSize(w, h);
            const sp = n.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM;
            sp.type = Sprite.Type.SIMPLE;
            return sp;
        };

        // 後備底盤（美術沒載到時不開天窗）：深色圓盤 + 金邊
        const bg = add('bg');
        const g = bg.addComponent(Graphics)!;
        g.fillColor = new Color(24, 22, 40, 255);
        g.strokeColor = new Color(190, 158, 82, 255);
        g.lineWidth = 4;
        g.circle(0, 0, R - 2); g.fill(); g.stroke();

        // 盤面
        const face = add('face');
        this.faceSprite = sizedSprite(face, D, Dh);

        // 指針容器（掛 UIOpacity，暫停時整組閃爍變灰）
        const hands = add('hands');
        hands.setPosition(0, 0, 0);
        this.handsOpacity = hands.addComponent(UIOpacity);

        // 時針、分針（樞軸在底部 knob → anchor(0.5, anchorY)，擺盤心，往上指）
        const makeHand = (spec: typeof HOUR): [Node, Sprite] => {
            const reach = spec.reach * R;
            const dispH = reach / (1 - spec.anchorY);
            const dispW = dispH * spec.w / spec.h;
            const n = new Node('hand-' + spec.key); n.layer = layer; hands.addChild(n);
            const u = n.addComponent(UITransform);
            u.setContentSize(dispW, dispH);
            u.setAnchorPoint(0.5, spec.anchorY);
            const sp = n.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM;
            sp.type = Sprite.Type.SIMPLE;
            return [n, sp];
        };
        [this.minNode, this.minSprite] = makeHand(MIN);     // 先加分針（在下層）
        [this.hourNode, this.hourSprite] = makeHand(HOUR);  // 時針疊在分針上

        // 頂端日月徽章（兩個 sprite 疊在同位置，依日夜切 active）
        const sun = add('sun');
        sizedSprite(sun, ICON_H, ICON_H);                   // 太陽 80x80 ≈ 正方
        sun.setPosition(0, MEDALLION_Y * Dh, 0);
        this.sunNode = sun;
        const moon = add('moon');
        sizedSprite(moon, ICON_H * 52 / 64, ICON_H);        // 月亮 52x64
        moon.setPosition(0, MEDALLION_Y * Dh, 0);
        this.moonNode = moon;

        // Month／Day 數字（畫在最上層，指針掃過也讀得到）
        this.monthLabel = this.makeNumber(dial, MONTH_X * D, BOX_Y * Dh);
        this.dayLabel = this.makeNumber(dial, DAY_X * D, BOX_Y * Dh);
    }

    private makeNumber(parent: Node, x: number, y: number): Label {
        const n = new Node('num'); n.layer = this.node.layer; parent.addChild(n);
        const u = n.addComponent(UITransform);
        u.setContentSize(0.2 * D, 0.16 * Dh);
        u.setAnchorPoint(0.5, 0.5);
        n.setPosition(x, y, 0);
        const lb = n.addComponent(Label);
        lb.string = '';
        lb.fontSize = Math.round(D * 0.15);
        lb.lineHeight = Math.round(D * 0.16);
        lb.color = new Color(244, 228, 176, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;
        lb.isBold = true;
        return lb;
    }

    /** 美術載好後把圖填上（沒載到就維持後備底盤/隱形指針）。 */
    private applyArt() {
        const set = (sp: Sprite | null, sf: SpriteFrame | null) => { if (sp && sf) sp.spriteFrame = sf; };
        set(this.faceSprite, GameArt.clockArt('face'));
        set(this.hourSprite, GameArt.clockArt(HOUR.key));
        set(this.minSprite, GameArt.clockArt(MIN.key));
        set(this.sunNode?.getComponent(Sprite) ?? null, GameArt.clockArt('sun'));
        set(this.moonNode?.getComponent(Sprite) ?? null, GameArt.clockArt('moon'));
    }
}
