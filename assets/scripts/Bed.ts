import { _decorator, Component, Node, UITransform, Label, Color, Graphics,
         input, Input, EventKeyboard, KeyCode, Vec3 } from 'cc';
import { UIState } from './UIState';
import { SleepOverlay } from './SleepOverlay';
const { ccclass, property } = _decorator;

/**
 * 床：掛在 brew.scene 的 Bed 節點（擺在房間天蓬床的位置，無 sprite＝隱形觸發點）。
 * 走近顯示「按 E 睡覺」，按 E 播睡覺過場（SleepOverlay）。比對兄弟 "Player" 距離。
 */
@ccclass('Bed')
export class Bed extends Component {
    @property({ tooltip: '玩家離多近才能睡覺（像素）' })
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

    update() {
        if (!this.player) return;
        this.inRange = Vec3.distance(this.player.position, this.node.position) <= this.interactRange;
        if (this.hint) this.hint.active = this.inRange && !UIState.modalOpen;
    }

    private onKeyDown(e: EventKeyboard) {
        if (e.keyCode !== KeyCode.KEY_E) return;
        if (!this.inRange || UIState.modalOpen) return;
        SleepOverlay.ensure()?.play();
    }

    private buildHint() {
        const n = new Node('BedHint'); n.layer = this.node.layer; this.node.addChild(n);
        n.addComponent(UITransform).setContentSize(200, 32);
        n.setPosition(0, 90, 0);
        const g = n.addComponent(Graphics);
        g.fillColor = new Color(20, 16, 28, 210);
        g.strokeColor = new Color(210, 190, 230, 220);
        g.lineWidth = 2;
        g.rect(-100, -16, 200, 32); g.fill(); g.stroke();
        const t = new Node('t'); t.layer = this.node.layer; n.addChild(t);
        t.addComponent(UITransform).setContentSize(200, 32);
        const lb = t.addComponent(Label);
        lb.string = '按 E 睡覺'; lb.fontSize = 20; lb.color = new Color(245, 240, 250, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        n.active = false;
        this.hint = n;
    }
}
