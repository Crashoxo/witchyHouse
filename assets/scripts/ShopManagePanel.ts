import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity } from 'cc';
import { Inventory } from './Inventory';
import { ShopStock } from './ShopStock';
import { UIState } from './UIState';
import { Wallet } from './Wallet';
const { ccclass } = _decorator;

/** 可上架管理的材料清單（固定順序，跟 ShopStock 的建議售價一致）。 */
const MATERIALS = ['木材', '樹枝', '漿果', '落葉', '藥草', '黑莓', '金蘋果'];

/**
 * 店內「經營商店」管理面板（modal）：一列一種材料，可從背包上架、撤下、調售價。
 * 顧客上門購買在 Phase 2；這裡先把貨架備好。仿 ShopPanel 的 ensure() 自動生 UI。
 */
@ccclass('ShopManagePanel')
export class ShopManagePanel extends Component {
    static instance: ShopManagePanel | null = null;

    static ensure(): ShopManagePanel | null {
        if (ShopManagePanel.instance) return ShopManagePanel.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[ShopManagePanel] 找不到 Canvas'); return null; }
        const node = new Node('ShopManageUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(ShopManagePanel);
    }

    private root: Node | null = null;
    private rowsBox: Node | null = null;
    private goldLabel: Label | null = null;

    private readonly panelW = 720;
    private readonly headerH = 104;
    private readonly rowH = 54;
    private readonly footerH = 40;

    onLoad() {
        ShopManagePanel.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (ShopManagePanel.instance === this) ShopManagePanel.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    private onKeyDown(e: EventKeyboard) {
        if (this.root?.active && e.keyCode === KeyCode.ESCAPE) this.close();
    }

    open() {
        Inventory.ensure();
        if (!this.root) this.build();
        this.root!.active = true;
        UIState.modalOpen = true;
        this.refresh();
    }

    close() {
        if (this.root) this.root.active = false;
        UIState.modalOpen = false;
    }

    // ---- 建骨架 ----

    private build() {
        const layer = this.node.layer;
        const panelH = this.headerH + MATERIALS.length * this.rowH + this.footerH;

        const root = new Node('Root');
        root.layer = layer;
        this.node.addChild(root);
        root.addComponent(UITransform).setContentSize(3000, 2000);
        root.addComponent(BlockInputEvents);
        const dim = root.addComponent(Graphics);
        dim.fillColor = new Color(0, 0, 0, 140);
        dim.rect(-1500, -1000, 3000, 2000);
        dim.fill();
        const rw = root.addComponent(Widget);
        rw.isAlignHorizontalCenter = rw.isAlignVerticalCenter = true;
        rw.horizontalCenter = rw.verticalCenter = 0;
        rw.updateAlignment();
        this.root = root;

        const panel = new Node('Panel');
        panel.layer = layer;
        root.addChild(panel);
        panel.addComponent(UITransform).setContentSize(this.panelW, panelH);
        const pg = panel.addComponent(Graphics);
        pg.lineWidth = 4;
        pg.fillColor = new Color(46, 34, 30, 246);
        pg.strokeColor = new Color(224, 196, 150, 235);
        this.roundRect(pg, -this.panelW / 2, -panelH / 2, this.panelW, panelH, 18);
        pg.fill(); pg.stroke();

        const topY = panelH / 2;
        const leftX = -this.panelW / 2 + 28;

        this.makeLabel(panel, '經營商店 · 上架定價', 26, new Color(250, 236, 214, 255),
            topY - 34, this.panelW - 160, Label.HorizontalAlign.LEFT, leftX);
        this.goldLabel = this.makeLabel(panel, '', 24, new Color(255, 224, 130, 255),
            topY - 34, 200, Label.HorizontalAlign.RIGHT, this.panelW / 2 - 74);
        this.makeButton(panel, '✕', 40, 40, this.panelW / 2 - 34, topY - 34,
            new Color(120, 60, 70, 255), () => this.close());

        // 欄位標題
        const hy = topY - 76;
        this.makeLabel(panel, '材料', 18, new Color(200, 190, 178, 255), hy, 90, Label.HorizontalAlign.LEFT, leftX);
        this.makeLabel(panel, '背包', 18, new Color(200, 190, 178, 255), hy, 60, Label.HorizontalAlign.CENTER, -210, true);
        this.makeLabel(panel, '貨架', 18, new Color(200, 190, 178, 255), hy, 60, Label.HorizontalAlign.CENTER, -120, true);
        this.makeLabel(panel, '售價', 18, new Color(200, 190, 178, 255), hy, 90, Label.HorizontalAlign.CENTER, 20, true);
        this.makeLabel(panel, '操作', 18, new Color(200, 190, 178, 255), hy, 170, Label.HorizontalAlign.CENTER, 210, true);

        this.makeLabel(panel, 'Esc 關閉 · 上架的貨等顧客上門購買', 15, new Color(190, 180, 170, 255),
            -panelH / 2 + 18, this.panelW - 60, Label.HorizontalAlign.CENTER, 0, true);

        const rowsBox = new Node('Rows');
        rowsBox.layer = layer;
        panel.addChild(rowsBox);
        rowsBox.addComponent(UITransform);
        rowsBox.setPosition(0, topY - this.headerH, 0);
        this.rowsBox = rowsBox;
    }

    private refresh() {
        if (this.goldLabel) this.goldLabel.string = `金幣 ${Wallet.gold}`;
        const box = this.rowsBox;
        if (!box) return;
        box.removeAllChildren();
        MATERIALS.forEach((name, i) => this.buildRow(box, name, -i * this.rowH - this.rowH / 2 + 4));
    }

    private buildRow(parent: Node, name: string, y: number) {
        const layer = this.node.layer;
        const leftX = -this.panelW / 2 + 28;
        const inv = Inventory.instance;
        const bag = inv?.countOf(name) ?? 0;
        const listing = ShopStock.listings.find(l => l.name === name);
        const shelf = listing?.count ?? 0;
        const price = listing?.price ?? ShopStock.suggestedPrice(name);

        const row = new Node('row-' + name);
        row.layer = layer;
        parent.addChild(row);
        row.addComponent(UITransform);
        row.setPosition(0, y, 0);

        this.makeLabel(row, name, 22, new Color(244, 236, 224, 255), 0, 90, Label.HorizontalAlign.LEFT, leftX);
        this.makeLabel(row, `${bag}`, 20, new Color(220, 230, 210, 255), 0, 60, Label.HorizontalAlign.CENTER, -210, true);
        this.makeLabel(row, `${shelf}`, 20, new Color(255, 224, 160, 255), 0, 60, Label.HorizontalAlign.CENTER, -120, true);

        // 售價：[－] price [＋]
        this.makeButton(row, '－', 30, 34, -32, 0, new Color(80, 66, 60, 255), () => {
            ShopStock.setPrice(name, price - 1); this.refresh();
        });
        this.makeLabel(row, `${price}金`, 20, new Color(255, 224, 130, 255), 0, 64, Label.HorizontalAlign.CENTER, 20, true);
        this.makeButton(row, '＋', 30, 34, 72, 0, new Color(80, 66, 60, 255), () => {
            ShopStock.setPrice(name, price + 1); this.refresh();
        });

        // 操作：[上架] [撤下]
        this.makeButton(row, '上架', 78, 36, 168, 0,
            bag > 0 ? new Color(78, 118, 92, 255) : new Color(70, 66, 62, 255), () => {
                if (inv?.remove(name, 1)) { ShopStock.add(name); this.refresh(); }
            });
        this.makeButton(row, '撤下', 78, 36, 256, 0,
            shelf > 0 ? new Color(120, 90, 70, 255) : new Color(70, 66, 62, 255), () => {
                if (ShopStock.removeOne(name)) { inv?.add(name, 1); this.refresh(); }
            });
    }

    // ---- 小工具 ----

    /** centered 為 true 時 anchorX 當作「中心 x」，否則當作左緣/右緣 x。 */
    private makeLabel(parent: Node, text: string, size: number, color: Color,
                      y: number, width: number, align: number, anchorX: number,
                      centered = false): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, size + 8);
        ut.setAnchorPoint(centered ? 0.5 : (align === Label.HorizontalAlign.RIGHT ? 1 : 0), 0.5);
        n.setPosition(anchorX, y, 0);
        const lb = n.addComponent(Label);
        lb.string = text;
        lb.fontSize = size;
        lb.lineHeight = size + 4;
        lb.color = color;
        lb.horizontalAlign = align;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;
        return lb;
    }

    private makeButton(parent: Node, text: string, w: number, h: number,
                       x: number, y: number, fill: Color, onClick: () => void) {
        const layer = this.node.layer;
        const n = new Node('btn');
        n.layer = layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(w, h);
        ut.setAnchorPoint(0.5, 0.5);
        n.setPosition(x, y, 0);

        const g = n.addComponent(Graphics);
        g.lineWidth = 2;
        g.fillColor = fill;
        g.strokeColor = new Color(224, 208, 186, 200);
        this.roundRect(g, -w / 2, -h / 2, w, h, 8);
        g.fill(); g.stroke();

        const tn = new Node('t');
        tn.layer = layer;
        n.addChild(tn);
        tn.addComponent(UITransform).setContentSize(w, h);
        const lb = tn.addComponent(Label);
        lb.string = text;
        lb.fontSize = Math.min(22, h - 12);
        lb.color = new Color(245, 245, 240, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;

        const op = n.addComponent(UIOpacity);
        n.on(Node.EventType.TOUCH_START, () => { op.opacity = 170; });
        n.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; onClick(); });
        n.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
    }

    private roundRect(g: Graphics, x: number, y: number, w: number, h: number, r: number) {
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
