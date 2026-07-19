import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, find } from 'cc';
import { Wallet } from './Wallet';
const { ccclass } = _decorator;

/**
 * 常駐抬頭顯示（HUD）：畫面左上角常駐一個金幣數字，隨時反映 Wallet.gold。
 * 仿 Inventory 的 ensure() 自動生 UI —— 每個場景由 PlayerController.onLoad
 * 呼叫 Hud.ensure()，所以走到哪都看得到金幣（不用逐場景擺 UI）。
 */
@ccclass('Hud')
export class Hud extends Component {
    static instance: Hud | null = null;

    /** 取得 HUD；沒有的話自動在 Canvas 底下建一個（找不到 Canvas 回 null）。 */
    static ensure(): Hud | null {
        if (Hud.instance) return Hud.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[Hud] 找不到 Canvas，無法建立 HUD'); return null; }
        const node = new Node('Hud');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(Hud);
    }

    private goldLabel: Label | null = null;
    private lastGold = -1;

    onLoad() {
        Hud.instance = this;
        this.build();
    }
    onDestroy() {
        if (Hud.instance === this) Hud.instance = null;
    }

    update() {
        // 金幣有變才更新文字
        if (this.goldLabel && Wallet.gold !== this.lastGold) {
            this.lastGold = Wallet.gold;
            this.goldLabel.string = `金幣 ${Wallet.gold}`;
        }
    }

    /** 左上角一個圓角底板 + 金幣文字。 */
    private build() {
        const w = 168, h = 44;
        const layer = this.node.layer;

        // 貼齊畫面左上角
        const ut = this.addComponent(UITransform)!;
        ut.setAnchorPoint(0, 1);
        ut.setContentSize(w, h);
        const widget = this.addComponent(Widget)!;
        widget.isAlignTop = true;
        widget.isAlignLeft = true;
        widget.top = 16;
        widget.left = 16;
        widget.alignMode = Widget.AlignMode.ON_WINDOW_RESIZE;
        widget.updateAlignment();

        // 底板（圓角）
        const g = this.addComponent(Graphics)!;
        g.lineWidth = 3;
        g.fillColor = new Color(30, 24, 40, 200);
        g.strokeColor = new Color(255, 224, 130, 220);
        this.roundRect(g, 0, -h, w, h, 12);
        g.fill(); g.stroke();

        // 金幣圓點（左側）
        const coin = this.addComponent(Graphics)!;
        coin.fillColor = new Color(255, 208, 92, 255);
        coin.strokeColor = new Color(180, 130, 40, 255);
        coin.lineWidth = 2;
        coin.circle(24, -h / 2, 11);
        coin.fill(); coin.stroke();

        // 金幣文字
        const tn = new Node('goldText');
        tn.layer = layer;
        this.node.addChild(tn);
        const tut = tn.addComponent(UITransform);
        tut.setAnchorPoint(0, 0.5);
        tut.setContentSize(w - 46, h);
        tn.setPosition(42, -h / 2, 0);
        const lb = tn.addComponent(Label);
        lb.string = `金幣 ${Wallet.gold}`;
        lb.fontSize = 22;
        lb.color = new Color(255, 240, 200, 255);
        lb.horizontalAlign = Label.HorizontalAlign.LEFT;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;
        this.goldLabel = lb;
        this.lastGold = Wallet.gold;
    }

    private roundRect(g: Graphics, x: number, y: number, w: number, h: number, r: number) {
        g.rect(x, y, w, h);   // 一般方框（不圓角）
    }
}
