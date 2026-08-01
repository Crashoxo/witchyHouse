import { _decorator, Component, Node, UITransform, Color, Graphics,
         input, Input, EventKeyboard, KeyCode, Vec3, Label, CCString, CCInteger } from 'cc';
import { BuyPanel, Goods } from './BuyPanel';
import { UIState } from './UIState';
const { ccclass, property } = _decorator;

/**
 * 「跟這位 NPC 買東西」的觸發：走近顯示提示，按 E 開 BuyPanel。
 * 掛在 NPC 節點上（Player 需為同層兄弟節點），貨品清單由安裝它的人設定。
 */
@ccclass('GoodsShop')
export class GoodsShop extends Component {
    @property({ tooltip: '面板標題（店名）' })
    shopTitle = '商店';
    @property({ tooltip: '玩家離多近才能互動（像素）' })
    interactRange = 150;

    /**
     * 賣什麼。**存在場景裡**（兩個平行陣列，同雜貨鋪 ShopBuilding 的作法）——
     * ⚠️ 早期是由安裝者在執行期塞一個 Goods[] 進來，但那樣一旦安裝的那支沒跑到，
     * 商店就會變成「提示冒得出來、按 E 卻沒反應」，而且在 Cocos 裡也改不了價錢。
     */
    @property({ type: [CCString], tooltip: '賣哪些東西（與售價一一對應）' })
    itemNames: string[] = [];
    @property({ type: [CCInteger], tooltip: '售價（與上面一一對應）' })
    itemPrices: number[] = [];

    /** 執行期用的清單；沒填 itemNames 時才由安裝者塞（保留舊用法）。 */
    goods: Goods[] = [];

    private player: Node | null = null;
    private hint: Node | null = null;
    private inRange = false;

    onLoad() {
        // 場景裡填了就以它為準
        if (this.itemNames.length) {
            this.goods = this.itemNames.map((n, i) => ({ name: n, price: this.itemPrices[i] ?? 0 }));
        }
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
        if (this.goods.length === 0) {
            // 走到這裡代表安裝的人沒把貨品清單交進來（見 CandyTown.wireShop）
            console.warn(`[GoodsShop] ${this.shopTitle} 沒有貨品清單，開不了`);
            return;
        }
        BuyPanel.ensure()?.open(this.shopTitle, this.goods);
    }

    update() {
        if (!this.player) return;
        this.inRange = Vec3.distance(this.player.position, this.node.position) <= this.interactRange;
        if (this.hint) this.hint.active = this.inRange && !UIState.modalOpen;
    }

    private buildHint() {
        const ut = this.getComponent(UITransform);
        const topY = ut ? ut.contentSize.height + 22 : 90;

        const n = new Node('ShopHint');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.addComponent(UITransform).setContentSize(210, 32);
        n.setPosition(0, topY, 0);

        const g = n.addComponent(Graphics);
        g.fillColor = new Color(28, 18, 26, 214);
        g.strokeColor = new Color(238, 190, 210, 220);
        g.lineWidth = 2;
        g.rect(-105, -16, 210, 32);
        g.fill(); g.stroke();

        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(206, 32);
        const lb = t.addComponent(Label);
        lb.string = '按 E 看看貨';
        lb.fontSize = 20;
        lb.color = new Color(250, 240, 246, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;

        n.active = false;
        this.hint = n;
    }
}
