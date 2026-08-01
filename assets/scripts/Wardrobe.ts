import { _decorator, Component, Node, UITransform, Color, Graphics,
         input, Input, EventKeyboard, KeyCode, Vec3, Label } from 'cc';
import { WardrobePanel } from './WardrobePanel';
import { UIState } from './UIState';
const { ccclass, property } = _decorator;

/**
 * 衣櫃：藥水室（女巫房間）左邊那座雕花木櫃。走近顯示「按 E 換衣服」，按 E 開衣櫃面板。
 * 節點本身沒有圖（櫃子是背景畫好的），只是個隱形觸發 —— 同倉庫木箱、天蓬床的作法。
 * 位置與「不要跟別的 E 撞在一起」的算法見 Doorways.install()。
 */
@ccclass('Wardrobe')
export class Wardrobe extends Component {
    @property({ tooltip: '玩家離多近才能互動（像素）' })
    interactRange = 150;

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
        WardrobePanel.ensure()?.open();
    }

    update() {
        if (!this.player) return;
        this.inRange = Vec3.distance(this.player.position, this.node.position) <= this.interactRange;
        if (this.hint) this.hint.active = this.inRange && !UIState.modalOpen;
    }

    private buildHint() {
        const ut = this.getComponent(UITransform);
        const topY = ut ? ut.contentSize.height / 2 + 28 : 90;

        const n = new Node('WardrobeHint');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.addComponent(UITransform).setContentSize(200, 32);
        n.setPosition(0, topY, 0);

        const g = n.addComponent(Graphics);
        g.fillColor = new Color(20, 16, 28, 210);
        g.strokeColor = new Color(224, 196, 150, 220);
        g.lineWidth = 2;
        g.rect(-100, -16, 200, 32);
        g.fill(); g.stroke();

        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(200, 32);
        const lb = t.addComponent(Label);
        lb.string = '按 E 換衣服';
        lb.fontSize = 20;
        lb.color = new Color(248, 240, 224, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;

        n.active = false;
        this.hint = n;
    }
}
