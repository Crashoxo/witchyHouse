import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, Sprite, SpriteFrame, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity } from 'cc';
import { UIState } from './UIState';
import { Wallet } from './Wallet';
import { DecorCatalog, DecorDef } from './DecorCatalog';
import { GameArt } from './GameArt';
const { ccclass } = _decorator;

/**
 * 花店的裝飾品購買面板（modal，ensure 自動生，仿 ShopPanel）。
 * 格狀列出目錄，點格子花金幣買一個（DecorCatalog.buy → Wallet 扣款）。
 * 買來的裝飾進「擁有數」，之後回自己店裡佈置時從托盤取用。
 */
@ccclass('DecorShopPanel')
export class DecorShopPanel extends Component {
    static instance: DecorShopPanel | null = null;

    static ensure(): DecorShopPanel | null {
        if (DecorShopPanel.instance) return DecorShopPanel.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[DecorShopPanel] 找不到 Canvas'); return null; }
        const node = new Node('DecorShopUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(DecorShopPanel);
    }

    private root: Node | null = null;
    private goldLabel: Label | null = null;
    private ownLabels: Record<string, Label> = {};

    private readonly cols = 4;
    private readonly cell = 158;
    private readonly pad = 24;
    private readonly headerH = 78;

    onLoad() {
        DecorShopPanel.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (DecorShopPanel.instance === this) DecorShopPanel.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    private onKeyDown(e: EventKeyboard) {
        if (this.root?.active && e.keyCode === KeyCode.ESCAPE) this.close();
    }

    open() {
        if (!this.root) this.build();
        this.root!.active = true;
        UIState.modalOpen = true;
        if (!GameArt.ready) GameArt.onReady(() => this.refreshIcons());
        this.refresh();
    }

    close() {
        if (this.root) this.root.active = false;
        UIState.modalOpen = false;
    }

    private refresh() {
        if (this.goldLabel) this.goldLabel.string = `金幣 ${Wallet.gold}`;
        for (const d of DecorCatalog.catalog) {
            const lb = this.ownLabels[d.id];
            if (lb) lb.string = DecorCatalog.ownedCount(d.id) > 0 ? `擁有 ${DecorCatalog.ownedCount(d.id)}` : '';
        }
    }

    private refreshIcons() {
        // 圖示載好後補上（build 時可能還沒 ready）
        this.iconSprites.forEach(({ sp, id }) => {
            const f = GameArt.decor(id);
            if (f) this.fit(sp, f, this.cell - 54, this.cell - 78);
        });
    }

    private iconSprites: Array<{ sp: Sprite; id: string }> = [];

    private build() {
        const layer = this.node.layer;
        const rows = Math.ceil(DecorCatalog.catalog.length / this.cols);
        const gridW = this.cols * this.cell;
        const gridH = rows * this.cell;
        const panelW = gridW + this.pad * 2;
        const panelH = gridH + this.headerH + this.pad;

        // 半透明背板
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

        // 面板本體
        const panel = new Node('Panel');
        panel.layer = layer;
        root.addChild(panel);
        panel.addComponent(UITransform).setContentSize(panelW, panelH);
        const pg = panel.addComponent(Graphics);
        pg.lineWidth = 4;
        pg.fillColor = new Color(40, 32, 54, 248);
        pg.strokeColor = new Color(214, 190, 232, 235);
        this.roundRect(pg, -panelW / 2, -panelH / 2, panelW, panelH, 18);
        pg.fill(); pg.stroke();

        const topY = panelH / 2;
        this.makeLabel(panel, '花店 · 裝飾品', 26, new Color(245, 235, 255, 255),
            -panelW / 2 + 26, topY - 40, 300, Label.HorizontalAlign.LEFT);
        this.goldLabel = this.makeLabel(panel, '', 24, new Color(255, 224, 130, 255),
            panelW / 2 - 244, topY - 40, 200, Label.HorizontalAlign.RIGHT);
        this.makeButton(panel, '✕', 40, 40, panelW / 2 - 34, topY - 34,
            new Color(120, 60, 70, 255), () => this.close());
        this.makeLabel(panel, 'Esc 關閉 · 點裝飾品購買', 15, new Color(180, 174, 190, 255),
            -panelW / 2 + 26, -panelH / 2 + 16, 400, Label.HorizontalAlign.LEFT);

        // 格子
        const gridLeft = -gridW / 2;
        const gridTop = topY - this.headerH;
        DecorCatalog.catalog.forEach((d, i) => {
            const cx = gridLeft + (i % this.cols) * this.cell + this.cell / 2;
            const cy = gridTop - Math.floor(i / this.cols) * this.cell - this.cell / 2;
            this.buildCell(panel, d, cx, cy);
        });
    }

    private buildCell(parent: Node, d: DecorDef, cx: number, cy: number) {
        const layer = this.node.layer;
        const s = this.cell - 12;
        const cell = new Node('cell-' + d.id);
        cell.layer = layer;
        parent.addChild(cell);
        cell.addComponent(UITransform).setContentSize(s, s);
        cell.setPosition(cx, cy, 0);
        const g = cell.addComponent(Graphics);
        g.lineWidth = 2;
        g.fillColor = new Color(58, 48, 74, 255);
        g.strokeColor = new Color(150, 130, 170, 200);
        this.roundRect(g, -s / 2, -s / 2, s, s, 10);
        g.fill(); g.stroke();

        // 圖示
        const icon = new Node('icon');
        icon.layer = layer;
        cell.addChild(icon);
        icon.addComponent(UITransform).setContentSize(this.cell - 54, this.cell - 78);
        icon.setPosition(0, 18, 0);
        const sp = icon.addComponent(Sprite);
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.trim = false;
        const f = GameArt.decor(d.id);
        if (f) this.fit(sp, f, this.cell - 54, this.cell - 78);
        this.iconSprites.push({ sp, id: d.id });

        // 名稱、售價、擁有數
        this.makeLabel(cell, d.name, 18, new Color(240, 236, 248, 255),
            0, -s / 2 + 44, s - 12, Label.HorizontalAlign.CENTER);
        this.makeLabel(cell, `${d.price} 金`, 17, new Color(255, 224, 130, 255),
            0, -s / 2 + 22, s - 12, Label.HorizontalAlign.CENTER);
        this.ownLabels[d.id] = this.makeLabel(cell, '', 14, new Color(150, 220, 160, 255),
            0, s / 2 - 16, s - 12, Label.HorizontalAlign.CENTER);

        // 整格可點＝買一個
        const op = cell.addComponent(UIOpacity);
        cell.on(Node.EventType.TOUCH_START, () => { op.opacity = 180; });
        cell.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; this.tryBuy(d); });
        cell.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
    }

    private tryBuy(d: DecorDef) {
        if (DecorCatalog.buy(d.id)) this.refresh();
        // 金幣不夠就不動作（refresh 也無妨）
    }

    // ---- 小工具（比照 ShopPanel）----

    private fit(sp: Sprite, frame: SpriteFrame, maxW: number, maxH: number) {
        const rw = frame.rect.width || frame.originalSize.width;
        const rh = frame.rect.height || frame.originalSize.height;
        const k = Math.min(maxW / rw, maxH / rh);
        sp.spriteFrame = frame;
        sp.getComponent(UITransform)!.setContentSize(rw * k, rh * k);
    }

    private makeLabel(parent: Node, text: string, size: number, color: Color,
                      x: number, y: number, width: number, align: number): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, size + 8);
        ut.setAnchorPoint(align === Label.HorizontalAlign.CENTER ? 0.5
                        : align === Label.HorizontalAlign.RIGHT ? 1 : 0, 0.5);
        n.setPosition(x, y, 0);
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
        g.lineWidth = 2; g.fillColor = fill; g.strokeColor = new Color(230, 220, 240, 200);
        this.roundRect(g, -w / 2, -h / 2, w, h, 8); g.fill(); g.stroke();
        const tn = new Node('t');
        tn.layer = layer; n.addChild(tn);
        tn.addComponent(UITransform).setContentSize(w, h);
        const lb = tn.addComponent(Label);
        lb.string = text; lb.fontSize = Math.min(24, h - 16);
        lb.color = new Color(245, 245, 250, 255);
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
        g.lineTo(x + w - r, y); g.arc(x + w - r, y + r, r, -H, 0, false);
        g.lineTo(x + w, y + h - r); g.arc(x + w - r, y + h - r, r, 0, H, false);
        g.lineTo(x + r, y + h); g.arc(x + r, y + h - r, r, H, Math.PI, false);
        g.lineTo(x, y + r); g.arc(x + r, y + r, r, Math.PI, Math.PI + H, false);
        g.close();
    }
}
