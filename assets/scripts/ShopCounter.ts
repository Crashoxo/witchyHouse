import { _decorator, Component, Node, UITransform, Color, Graphics,
         input, Input, EventKeyboard, KeyCode, Vec3, Label } from 'cc';
import { ShopManagePanel } from './ShopManagePanel';
import { UIState } from './UIState';
const { ccclass, property } = _decorator;

/**
 * 店內櫃台：玩家走近顯示「按 E 經營商店」，按 E 開上架/定價管理面板。
 * 掛在店內場景（shop.scene）的 Counter 節點上，Player 需為同層（Props）的兄弟節點。
 */
@ccclass('ShopCounter')
export class ShopCounter extends Component {
    @property({ tooltip: '玩家離多近才能互動（像素）' })
    interactRange = 200;

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
        ShopManagePanel.ensure()?.open();
    }

    update() {
        if (!this.player) return;
        this.inRange = Vec3.distance(this.player.position, this.node.position) <= this.interactRange;
        if (this.hint) this.hint.active = this.inRange && !UIState.modalOpen;
    }

    private buildHint() {
        const ut = this.getComponent(UITransform);
        const topY = ut ? ut.contentSize.height / 2 + 28 : 90;

        const n = new Node('CounterHint');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.addComponent(UITransform).setContentSize(200, 32);
        n.setPosition(0, topY, 0);

        const g = n.addComponent(Graphics);
        g.fillColor = new Color(20, 16, 28, 210);
        g.strokeColor = new Color(224, 196, 150, 220);
        g.lineWidth = 2;
        this.pill(g, -100, -16, 200, 32, 16);
        g.fill(); g.stroke();

        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(200, 32);
        const lb = t.addComponent(Label);
        lb.string = '按 E 經營商店';
        lb.fontSize = 20;
        lb.color = new Color(248, 240, 224, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;

        n.active = false;
        this.hint = n;
    }

    private pill(g: Graphics, x: number, y: number, w: number, h: number, r: number) {
        g.rect(x, y, w, h);   // 一般方框（不圓角）
    }
}
