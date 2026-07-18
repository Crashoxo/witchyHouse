import { _decorator, Component, Node, UITransform, Sprite, Label, Color } from 'cc';
import { ShopStock } from './ShopStock';
import { GameArt } from './GameArt';
const { ccclass, property } = _decorator;

/**
 * 店內貨架顯示：把 ShopStock 上架的商品用圖示排成一排（數量 + 售價）。
 * 掛在 shop.scene 的 Shelf 節點上；清單有變動（或圖示載好）就重建。
 * 顧客系統會朝這些商品走過來購買。
 */
@ccclass('ShopShelf')
export class ShopShelf extends Component {
    @property({ tooltip: '每格商品的顯示大小（像素）' })
    slotSize = 80;
    @property({ tooltip: '格子間距（像素）' })
    spacing = 104;

    private sig = '';   // 目前畫出來的清單簽章，用來偵測變動

    onLoad() {
        GameArt.preload();
    }

    update() {
        const s = ShopStock.listings.map(l => `${l.name}:${l.count}:${l.price}`).join('|');
        if (s !== this.sig && GameArt.ready) { this.sig = s; this.rebuild(); }
    }

    private rebuild() {
        this.node.removeAllChildren();
        const layer = this.node.layer;
        const list = ShopStock.listings;
        // 置中排開
        const startX = -((list.length - 1) * this.spacing) / 2;

        list.forEach((l, i) => {
            const cell = new Node('item-' + l.name);
            cell.layer = layer;
            this.node.addChild(cell);
            cell.addComponent(UITransform);
            cell.setPosition(startX + i * this.spacing, 0, 0);

            // 商品圖示（保持原圖比例塞進 slotSize 方框，不變形）
            const iconNode = new Node('icon');
            iconNode.layer = layer;
            cell.addChild(iconNode);
            const iut = iconNode.addComponent(UITransform);
            const sp = iconNode.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM;
            sp.type = Sprite.Type.SIMPLE;
            const frame = GameArt.item(l.name);
            sp.spriteFrame = frame;
            if (frame) {
                const k = this.slotSize / Math.max(frame.rect.width, frame.rect.height);
                iut.setContentSize(frame.rect.width * k, frame.rect.height * k);
            } else {
                iut.setContentSize(this.slotSize, this.slotSize);
            }

            // 數量（右下）
            const cnt = new Node('cnt');
            cnt.layer = layer;
            cell.addChild(cnt);
            const cut = cnt.addComponent(UITransform);
            cut.setContentSize(this.slotSize, 22);
            cnt.setPosition(0, -this.slotSize / 2 - 4, 0);
            const cl = cnt.addComponent(Label);
            cl.string = `×${l.count}`;
            cl.fontSize = 20;
            cl.color = new Color(255, 245, 210, 255);
            cl.horizontalAlign = Label.HorizontalAlign.CENTER;

            // 售價（上方）
            const pr = new Node('price');
            pr.layer = layer;
            cell.addChild(pr);
            pr.addComponent(UITransform).setContentSize(this.slotSize + 20, 22);
            pr.setPosition(0, this.slotSize / 2 + 12, 0);
            const pl = pr.addComponent(Label);
            pl.string = `${l.price}金`;
            pl.fontSize = 18;
            pl.color = new Color(255, 224, 130, 255);
            pl.horizontalAlign = Label.HorizontalAlign.CENTER;
        });
    }
}
