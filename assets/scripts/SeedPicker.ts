import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, Sprite, SpriteFrame, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity } from 'cc';
import { UIState } from './UIState';
import { Inventory } from './Inventory';
import { GameArt } from './GameArt';
import { FLOWERS } from './data/garden';
const { ccclass } = _decorator;

/**
 * 「要種什麼？」——站在空花圃前按 E 時跳出來，列出背包裡有的花種子讓玩家挑一種。
 * 仿 ShopPanel 的 ensure() 自動生 UI；modal 期間 UIState.modalOpen＝true，
 * 角色不動、GardenRoom 也收不到 E。
 *
 * ⚠️ 關閉只吃 Esc 與 ✕，**不吃 E** —— 開啟的那一下 E 會在同一幀又被讀到（同 ShopPanel
 * 的老坑）。選好種子是「先 close() 再跑 callback」，順序反了會被 close 蓋掉 modalOpen。
 */
@ccclass('SeedPicker')
export class SeedPicker extends Component {
    static instance: SeedPicker | null = null;

    static ensure(): SeedPicker | null {
        if (SeedPicker.instance) return SeedPicker.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[SeedPicker] 找不到 Canvas'); return null; }
        const node = new Node('SeedPickerUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(SeedPicker);
    }

    private root: Node | null = null;
    private rowsBox: Node | null = null;
    private onPick: ((seed: string) => void) | null = null;

    private readonly panelW = 360;
    private readonly headerH = 66;
    private readonly rowH = 62;
    private readonly footerH = 34;

    onLoad() {
        SeedPicker.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (SeedPicker.instance === this) SeedPicker.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    private onKeyDown(e: EventKeyboard) {
        if (this.root?.active && e.keyCode === KeyCode.ESCAPE) this.close();
    }

    /** 打開挑選畫面；選了哪一種就把種子名交給 cb（沒選就不會呼叫）。 */
    open(cb: (seed: string) => void) {
        this.onPick = cb;
        if (!this.root) this.build();
        this.root!.active = true;
        UIState.modalOpen = true;
        this.renderRows();
    }

    close() {
        if (this.root) this.root.active = false;
        UIState.modalOpen = false;
        this.onPick = null;
    }

    /** 背包裡現在有的花種子（依 FLOWERS 的固定順序）。 */
    static seedsInBag(): string[] {
        const out: string[] = [];
        for (const f of FLOWERS) if (Inventory.countOf(f.seed) > 0) out.push(f.seed);
        return out;
    }

    private build() {
        const layer = this.node.layer;
        // 高度以「三種種子都有」為準，實際列數少時下面留白即可（免得每次重建面板）
        const panelH = this.headerH + FLOWERS.length * this.rowH + this.footerH;

        const root = new Node('Root');
        root.layer = layer;
        this.node.addChild(root);
        root.addComponent(UITransform).setContentSize(4000, 3000);
        root.addComponent(BlockInputEvents);
        const dim = root.addComponent(Graphics);
        dim.fillColor = new Color(0, 0, 0, 140);
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
        pg.fillColor = new Color(38, 44, 34, 248);
        pg.strokeColor = new Color(196, 216, 176, 235);
        pg.rect(-this.panelW / 2, -panelH / 2, this.panelW, panelH);
        pg.fill(); pg.stroke();

        const topY = panelH / 2;
        this.makeLabel(panel, '要種什麼？', 24, new Color(238, 246, 228, 255),
            -this.panelW / 2 + 22, topY - 36, 220, Label.HorizontalAlign.LEFT);
        this.makeButton(panel, '✕', 36, 36, this.panelW / 2 - 30, topY - 32,
            new Color(96, 68, 52, 255), () => this.close());
        this.makeLabel(panel, 'Esc 取消', 14, new Color(176, 186, 166, 255),
            -this.panelW / 2 + 22, -panelH / 2 + 16, 200, Label.HorizontalAlign.LEFT);

        const rows = new Node('Rows');
        rows.layer = layer;
        panel.addChild(rows);
        rows.addComponent(UITransform);
        rows.setPosition(0, topY - this.headerH, 0);
        this.rowsBox = rows;
    }

    private renderRows() {
        const box = this.rowsBox;
        if (!box) return;
        box.removeAllChildren();
        SeedPicker.seedsInBag().forEach((seed, i) => this.buildRow(box, seed, -i * this.rowH - this.rowH / 2));
    }

    private buildRow(parent: Node, seed: string, y: number) {
        const layer = this.node.layer;
        const w = this.panelW - 44, h = this.rowH - 10;
        const row = new Node('seed-' + seed);
        row.layer = layer;
        parent.addChild(row);
        row.addComponent(UITransform).setContentSize(w, h);
        row.setPosition(0, y, 0);
        const g = row.addComponent(Graphics);
        g.lineWidth = 2;
        g.fillColor = new Color(56, 64, 48, 255);
        g.strokeColor = new Color(140, 168, 120, 200);
        g.rect(-w / 2, -h / 2, w, h);
        g.fill(); g.stroke();

        // 種子圖示
        const icon = new Node('icon');
        icon.layer = layer;
        row.addChild(icon);
        icon.addComponent(UITransform).setContentSize(40, 40);
        icon.setPosition(-w / 2 + 30, 0, 0);
        const sp = icon.addComponent(Sprite);
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.trim = false;
        const f = GameArt.item(seed);
        if (f) this.fit(sp, f, 40, 40);

        this.makeLabel(row, seed, 20, new Color(238, 244, 230, 255),
            -w / 2 + 60, 0, 160, Label.HorizontalAlign.LEFT);
        this.makeLabel(row, `×${Inventory.countOf(seed)}`, 18, new Color(206, 226, 190, 255),
            w / 2 - 16, 0, 80, Label.HorizontalAlign.RIGHT);

        const op = row.addComponent(UIOpacity);
        row.on(Node.EventType.TOUCH_START, () => { op.opacity = 180; });
        row.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
        row.on(Node.EventType.TOUCH_END, () => {
            op.opacity = 255;
            const cb = this.onPick;
            this.close();          // 先關再回呼（close 會把 onPick 清掉，所以先接起來）
            cb?.(seed);
        });
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
        g.lineWidth = 2; g.fillColor = fill; g.strokeColor = new Color(220, 230, 210, 200);
        g.rect(-w / 2, -h / 2, w, h); g.fill(); g.stroke();
        const tn = new Node('t');
        tn.layer = layer; n.addChild(tn);
        tn.addComponent(UITransform).setContentSize(w, h);
        const lb = tn.addComponent(Label);
        lb.string = text; lb.fontSize = Math.min(22, h - 14);
        lb.color = new Color(240, 246, 236, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        const op = n.addComponent(UIOpacity);
        n.on(Node.EventType.TOUCH_START, () => { op.opacity = 170; });
        n.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; onClick(); });
        n.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
    }
}
