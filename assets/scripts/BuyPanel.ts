import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, Sprite, SpriteFrame, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity } from 'cc';
import { UIState } from './UIState';
import { Wallet } from './Wallet';
import { Inventory } from './Inventory';
import { DailyLog } from './DailyLog';
import { GameArt } from './GameArt';
import { ITEM_DESC, DEFAULT_ITEM_DESC } from './data/items';
import { BASE_PRICE } from './data/prices';
const { ccclass } = _decorator;

/** 一項商品。 */
export interface Goods { name: string; price: number; }

/**
 * 通用的「跟 NPC 買東西」面板（modal，ensure 自動生）。
 *
 * 跟 ShopPanel 剛好相反：那個是雜貨鋪**收購**玩家的材料，這個是玩家**花錢買進**。
 * 糖果鎮的商行用它；之後別的鎮要開店，`open(標題, 貨品清單)` 就能直接用。
 *
 * 每一列都寫出「自己店裡賣得掉多少」（BASE_PRICE），因為這些貨的意義就是進來轉賣，
 * 玩家要看得到價差才知道值不值得。
 */
@ccclass('BuyPanel')
export class BuyPanel extends Component {
    static instance: BuyPanel | null = null;

    static ensure(): BuyPanel | null {
        if (BuyPanel.instance) return BuyPanel.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[BuyPanel] 找不到 Canvas'); return null; }
        const node = new Node('BuyUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(BuyPanel);
    }

    private root: Node | null = null;
    private rowsBox: Node | null = null;
    private titleLabel: Label | null = null;
    private goldLabel: Label | null = null;
    private goods: Goods[] = [];
    private waitingArt = false;

    private readonly panelW = 720;
    private readonly headerH = 92;
    private readonly rowH = 62;
    private readonly footerH = 34;
    private readonly maxRows = 7;

    onLoad() {
        BuyPanel.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (BuyPanel.instance === this) BuyPanel.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    /** ⚠️ 只吃 Esc 關閉（開啟的那一下 E 同一幀還會被讀到）。 */
    private onKeyDown(e: EventKeyboard) {
        if (this.root?.active && e.keyCode === KeyCode.ESCAPE) this.close();
    }

    open(title: string, goods: Goods[]) {
        Inventory.ensure();
        this.goods = goods.slice(0, this.maxRows);
        if (!this.root) this.build();
        this.root!.active = true;
        UIState.modalOpen = true;
        if (this.titleLabel) this.titleLabel.string = title;
        if (!GameArt.ready && !this.waitingArt) {
            this.waitingArt = true;
            GameArt.onReady(() => {
                this.waitingArt = false;
                if (this.isValid && this.root?.active) this.refresh();
            });
        }
        this.refresh();
    }

    close() {
        if (this.root) this.root.active = false;
        UIState.modalOpen = false;
    }

    private refresh() {
        if (this.goldLabel) this.goldLabel.string = `金幣 ${Wallet.gold}`;
        const box = this.rowsBox;
        if (!box) return;
        box.removeAllChildren();
        this.goods.forEach((g, i) => this.row(box, g, -20 - i * this.rowH));
    }

    private row(parent: Node, g: Goods, y: number) {
        const layer = this.node.layer;
        const leftX = -this.panelW / 2 + 26;
        const have = Inventory.countOf(g.name);
        const afford = Wallet.gold >= g.price;

        const row = new Node('goods-' + g.name);
        row.layer = layer;
        parent.addChild(row);
        row.addComponent(UITransform);
        row.setPosition(0, y, 0);

        const icon = new Node('icon');
        icon.layer = layer;
        row.addChild(icon);
        icon.addComponent(UITransform).setContentSize(44, 44);
        icon.setPosition(leftX + 22, 0, 0);
        const sp = icon.addComponent(Sprite);
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.trim = false;
        const f = GameArt.item(g.name);
        if (f) this.fit(sp, f, 44, 44);

        this.makeLabel(row, g.name, 20, new Color(244, 238, 228, 255),
            leftX + 54, 12, 190, Label.HorizontalAlign.LEFT);
        this.makeLabel(row, ITEM_DESC[g.name] ?? DEFAULT_ITEM_DESC, 13,
            new Color(176, 168, 158, 255), leftX + 54, -12, 300, Label.HorizontalAlign.LEFT);

        // 自己店裡賣得掉多少 —— 這些貨就是進來轉賣的，價差要看得見
        const resale = BASE_PRICE[g.name] ?? 0;
        this.makeLabel(row, resale ? `店裡可賣 ${resale}` : '', 15,
            new Color(168, 206, 168, 255), 0, 12, 150, Label.HorizontalAlign.CENTER, true, 176);
        this.makeLabel(row, have > 0 ? `持有 ${have}` : '', 14,
            new Color(150, 176, 200, 255), 0, -12, 150, Label.HorizontalAlign.CENTER, true, 176);

        this.makeLabel(row, `${g.price} 金`, 19,
            afford ? new Color(255, 224, 130, 255) : new Color(150, 130, 110, 255),
            0, 0, 110, Label.HorizontalAlign.RIGHT, false, this.panelW / 2 - 126);
        this.makeButton(row, '購買', 88, 40, this.panelW / 2 - 70, 0,
            afford ? new Color(78, 118, 92, 255) : new Color(70, 66, 62, 255),
            () => this.buy(g));
    }

    private buy(g: Goods) {
        if (Wallet.gold < g.price) return;
        const inv = Inventory.ensure();
        if (!inv || !inv.add(g.name, 1)) return;      // 背包種類滿了就不扣錢
        Wallet.add(-g.price);
        DailyLog.recordSpend(g.price);
        this.refresh();
    }

    // ---- 骨架 ----

    private build() {
        const layer = this.node.layer;
        const panelH = this.headerH + this.maxRows * this.rowH + this.footerH;

        const root = new Node('Root');
        root.layer = layer;
        this.node.addChild(root);
        root.addComponent(UITransform).setContentSize(4000, 3000);
        root.addComponent(BlockInputEvents);
        const dim = root.addComponent(Graphics);
        dim.fillColor = new Color(0, 0, 0, 150);
        dim.rect(-2000, -1500, 4000, 3000); dim.fill();
        const rw = root.addComponent(Widget);
        rw.isAlignHorizontalCenter = rw.isAlignVerticalCenter = true;
        rw.horizontalCenter = rw.verticalCenter = 0; rw.updateAlignment();
        this.root = root;

        const panel = new Node('Panel');
        panel.layer = layer;
        root.addChild(panel);
        panel.addComponent(UITransform).setContentSize(this.panelW, panelH);
        const pg = panel.addComponent(Graphics);
        pg.lineWidth = 4;
        pg.fillColor = new Color(48, 34, 44, 248);
        pg.strokeColor = new Color(238, 190, 210, 235);
        pg.rect(-this.panelW / 2, -panelH / 2, this.panelW, panelH);
        pg.fill(); pg.stroke();

        const topY = panelH / 2;
        this.titleLabel = this.makeLabel(panel, '', 26, new Color(252, 236, 244, 255),
            -this.panelW / 2 + 26, topY - 36, 320, Label.HorizontalAlign.LEFT);
        this.goldLabel = this.makeLabel(panel, '', 22, new Color(255, 224, 130, 255),
            0, topY - 36, 200, Label.HorizontalAlign.RIGHT, false, this.panelW / 2 - 64);
        this.makeButton(panel, '✕', 40, 40, this.panelW / 2 - 30, topY - 34,
            new Color(120, 60, 70, 255), () => this.close());
        this.makeLabel(panel, 'Esc 關閉 · 買回去的東西可以擺到自己店裡賣（價差就是利潤）', 15,
            new Color(190, 176, 184, 255),
            -this.panelW / 2 + 26, -panelH / 2 + 16, 620, Label.HorizontalAlign.LEFT);

        const rows = new Node('Rows');
        rows.layer = layer;
        panel.addChild(rows);
        rows.addComponent(UITransform);
        rows.setPosition(0, topY - this.headerH, 0);
        this.rowsBox = rows;
    }

    // ---- 小工具（比照 ShopManagePanel）----

    private fit(sp: Sprite, frame: SpriteFrame, maxW: number, maxH: number) {
        const rw = frame.rect.width || frame.originalSize.width;
        const rh = frame.rect.height || frame.originalSize.height;
        const k = Math.min(maxW / rw, maxH / rh);
        sp.spriteFrame = frame;
        sp.getComponent(UITransform)!.setContentSize(rw * k, rh * k);
    }

    private makeLabel(parent: Node, text: string, size: number, color: Color,
                      x: number, y: number, width: number, align: number,
                      centered = false, cx?: number): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, size + 8);
        ut.setAnchorPoint(centered || align === Label.HorizontalAlign.CENTER ? 0.5
                        : align === Label.HorizontalAlign.RIGHT ? 1 : 0, 0.5);
        n.setPosition(cx !== undefined ? cx : x, y, 0);
        const lb = n.addComponent(Label);
        lb.string = text; lb.fontSize = size; lb.lineHeight = size + 4; lb.color = color;
        lb.horizontalAlign = align; lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;
        return lb;
    }

    private makeButton(parent: Node, text: string, w: number, h: number,
                       x: number, y: number, fill: Color, onClick: () => void) {
        const layer = this.node.layer;
        const n = new Node('btn');
        n.layer = layer;
        parent.addChild(n);
        n.addComponent(UITransform).setContentSize(w, h);
        n.setPosition(x, y, 0);
        const g = n.addComponent(Graphics);
        g.lineWidth = 2; g.fillColor = fill; g.strokeColor = new Color(238, 214, 226, 190);
        g.rect(-w / 2, -h / 2, w, h); g.fill(); g.stroke();
        const tn = new Node('t');
        tn.layer = layer; n.addChild(tn);
        tn.addComponent(UITransform).setContentSize(w, h);
        const lb = tn.addComponent(Label);
        lb.string = text; lb.fontSize = Math.min(22, h - 16);
        lb.color = new Color(248, 240, 244, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        const op = n.addComponent(UIOpacity);
        n.on(Node.EventType.TOUCH_START, () => { op.opacity = 170; });
        n.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; onClick(); });
        n.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
    }
}
