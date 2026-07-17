import { _decorator, Component, Node, UITransform, Color, Graphics, CCString,
         CCInteger, input, Input, EventKeyboard, KeyCode, Vec3, Label } from 'cc';
import { ShopPanel, BuyEntry, DEFAULT_BUY } from './ShopPanel';
import { UIState } from './UIState';
const { ccclass, property } = _decorator;

/**
 * 商店建築：掛在城鎮的建築節點上。玩家走近顯示「按 E 收購」，按 E 開收購面板。
 *
 * 建築和 Player 都在 Props 底下 → 直接找兄弟節點抓 Player（同 GatherTree）。
 * 收購清單 buyItems/buyPrices 留空時，用 ShopPanel 的 DEFAULT_BUY（收購全材料）。
 */
@ccclass('ShopBuilding')
export class ShopBuilding extends Component {
    @property({ tooltip: '面板標題' })
    shopTitle = '雜貨鋪 · 收購';
    @property({ tooltip: '玩家離多近才能互動（像素）' })
    interactRange = 220;
    @property({ type: [CCString], tooltip: '收購的材料名稱，與 buyPrices 一一對應（留空＝用預設清單）' })
    buyItems: string[] = [];
    @property({ type: [CCInteger], tooltip: '各材料單價，與 buyItems 一一對應' })
    buyPrices: number[] = [];

    private player: Node | null = null;
    private hint: Node | null = null;   // 「按 E 收購」浮動提示
    private inRange = false;

    onLoad() {
        this.player = this.node.parent?.getChildByName('Player') ?? null;
        this.buildHint();
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }

    private entries(): BuyEntry[] {
        if (this.buyItems.length === 0) return DEFAULT_BUY;
        return this.buyItems.map((name, i) => ({ name, price: this.buyPrices[i] ?? 0 }));
    }

    private onKeyDown(e: EventKeyboard) {
        if (e.keyCode !== KeyCode.KEY_E) return;
        if (!this.inRange || UIState.modalOpen) return;   // 已開著別重複觸發
        ShopPanel.ensure()?.open(this.shopTitle, this.entries());
    }

    update() {
        if (!this.player) return;
        this.inRange = Vec3.distance(this.player.position, this.node.position) <= this.interactRange;
        // 只有在範圍內、且沒有開著視窗時才顯示提示
        if (this.hint) this.hint.active = this.inRange && !UIState.modalOpen;
    }

    /** 在建築上方建一個「按 E 收購」文字提示（預設隱藏）。 */
    private buildHint() {
        const ut = this.getComponent(UITransform);
        const topY = ut ? ut.contentSize.height + 24 : 120;

        const n = new Node('ShopHint');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.addComponent(UITransform).setContentSize(180, 32);
        n.setPosition(0, topY, 0);

        const g = n.addComponent(Graphics);
        g.fillColor = new Color(20, 16, 28, 210);
        g.strokeColor = new Color(210, 190, 230, 220);
        g.lineWidth = 2;
        this.pill(g, -90, -16, 180, 32, 16);
        g.fill(); g.stroke();

        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(180, 32);
        const lb = t.addComponent(Label);
        lb.string = '按 E 收購';
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
        g.lineTo(x + w - r, y);
        g.arc(x + w - r, y + r, r, -H, 0, false);
        g.lineTo(x + w, y + h - r);
        g.arc(x + w - r, y + h - r, r, 0, H, false);
        g.lineTo(x + r, y + h);
        g.arc(x + r, y + h - r, r, H, Math.PI, false);
        g.lineTo(x, y + r);
        g.arc(x + r, y + r, r, Math.PI, Math.PI + H, false);
        g.close();
    }
}
