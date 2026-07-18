import { _decorator, Component, Node, UITransform, Color, Graphics,
         input, Input, EventKeyboard, KeyCode, Vec3, Label } from 'cc';
import { DecorShopPanel } from './DecorShopPanel';
import { UIState } from './UIState';
const { ccclass, property } = _decorator;

/**
 * 花店：掛在城鎮的花店建築上。玩家走近顯示「按 E 逛花店」，按 E 開裝飾品購買面板
 * （比照 ShopBuilding 的互動慣例：找兄弟 "Player"、UIState.modalOpen 擋重複）。
 */
@ccclass('DecorShop')
export class DecorShop extends Component {
    @property({ tooltip: '玩家離多近才能互動（像素）' })
    interactRange = 220;

    private player: Node | null = null;
    private hint: Node | null = null;
    private inRange = false;

    onLoad() {
        this.player = this.node.parent?.getChildByName('Player') ?? null;
        this.buildHint();
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }

    private onKeyDown(e: EventKeyboard) {
        if (e.keyCode !== KeyCode.KEY_E) return;
        if (!this.inRange || UIState.modalOpen) return;
        DecorShopPanel.ensure()?.open();
    }

    update() {
        if (!this.player) return;
        this.inRange = Vec3.distance(this.player.position, this.node.position) <= this.interactRange;
        if (this.hint) this.hint.active = this.inRange && !UIState.modalOpen;
    }

    private buildHint() {
        const ut = this.getComponent(UITransform);
        const topY = ut ? ut.contentSize.height + 24 : 120;
        const n = new Node('ShopHint');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.addComponent(UITransform).setContentSize(200, 32);
        n.setPosition(0, topY, 0);
        const g = n.addComponent(Graphics);
        g.fillColor = new Color(20, 16, 28, 210);
        g.strokeColor = new Color(210, 190, 230, 220);
        g.lineWidth = 2;
        this.pill(g, -100, -16, 200, 32, 16);
        g.fill(); g.stroke();
        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(200, 32);
        const lb = t.addComponent(Label);
        lb.string = '按 E 逛花店';
        lb.fontSize = 20;
        lb.color = new Color(245, 240, 250, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        n.active = false;
        this.hint = n;
    }

    private pill(g: Graphics, x: number, y: number, w: number, h: number, r: number) {
        const H = Math.PI / 2;
        g.moveTo(x + r, y);
        g.lineTo(x + w - r, y); g.arc(x + w - r, y + r, r, -H, 0, false);
        g.lineTo(x + w, y + h - r); g.arc(x + w - r, y + h - r, r, 0, H, false);
        g.lineTo(x + r, y + h); g.arc(x + r, y + h - r, r, H, Math.PI, false);
        g.lineTo(x, y + r); g.arc(x + r, y + r, r, Math.PI, Math.PI + H, false);
        g.close();
    }
}
