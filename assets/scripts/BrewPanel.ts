import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, Sprite, SpriteFrame, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity } from 'cc';
import { UIState } from './UIState';
import { GameArt } from './GameArt';
import { PotionRecipes, Recipe } from './PotionRecipes';
import { Inventory } from './Inventory';
import { BrewCauldron } from './BrewCauldron';
const { ccclass } = _decorator;

/**
 * 調配藥水面板（modal，ensure 自動生，仿 ShopPanel）。列出所有配方：成品圖示、名稱、
 * 售價、所需材料（夠＝綠、不夠＝紅），材料足夠才能按「製作」。按下＝關面板、鍋爐開始熬煮動畫。
 */
@ccclass('BrewPanel')
export class BrewPanel extends Component {
    static instance: BrewPanel | null = null;

    static ensure(): BrewPanel | null {
        if (BrewPanel.instance) return BrewPanel.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[BrewPanel] 找不到 Canvas'); return null; }
        const node = new Node('BrewUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(BrewPanel);
    }

    private root: Node | null = null;
    private cauldron: BrewCauldron | null = null;
    private rows: Array<{ r: Recipe; inputLbl: Label; btn: Node; btnG: Graphics; btnLbl: Label }> = [];

    private readonly panelW = 660;
    private readonly headerH = 74;
    private readonly rowH = 62;
    private readonly footerH = 28;

    onLoad() {
        BrewPanel.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (BrewPanel.instance === this) BrewPanel.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    private onKeyDown(e: EventKeyboard) {
        if (this.root?.active && e.keyCode === KeyCode.ESCAPE) this.close();
    }

    open(cauldron: BrewCauldron) {
        this.cauldron = cauldron;
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

    // ---- 依背包材料更新每列（材料夠不夠、製作鈕亮不亮）----
    private refresh() {
        const inv = Inventory.ensure();
        for (const row of this.rows) {
            const ok = PotionRecipes.canCraft(row.r);
            const parts = Object.keys(row.r.inputs).map(m => {
                const have = inv?.countOf(m) ?? 0;
                return `${m}×${row.r.inputs[m]}(有${have})`;
            });
            row.inputLbl.string = parts.join('  ');
            row.inputLbl.color = ok ? new Color(150, 220, 160, 255) : new Color(224, 150, 150, 255);
            row.btnG.fillColor = ok ? new Color(78, 118, 92, 255) : new Color(70, 66, 78, 255);
            row.btnG.clear();
            this.roundRect(row.btnG, -46, -18, 92, 36, 8); row.btnG.fill(); row.btnG.stroke();
            row.btnLbl.color = ok ? new Color(245, 245, 250, 255) : new Color(150, 145, 158, 255);
        }
    }

    private iconSprites: Array<{ sp: Sprite; name: string }> = [];
    private refreshIcons() {
        this.iconSprites.forEach(({ sp, name }) => {
            const f = GameArt.item(name);
            if (f) this.fit(sp, f, 46, 46);
        });
    }

    private build() {
        const layer = this.node.layer;
        const rowsH = PotionRecipes.all.length * this.rowH;
        const panelH = this.headerH + rowsH + this.footerH;

        const root = new Node('Root');
        root.layer = layer;
        this.node.addChild(root);
        root.addComponent(UITransform).setContentSize(4000, 3000);
        root.addComponent(BlockInputEvents);
        const dim = root.addComponent(Graphics);
        dim.fillColor = new Color(0, 0, 0, 150); dim.rect(-2000, -1500, 4000, 3000); dim.fill();
        const rw = root.addComponent(Widget);
        rw.isAlignHorizontalCenter = rw.isAlignVerticalCenter = true;
        rw.horizontalCenter = rw.verticalCenter = 0; rw.updateAlignment();
        this.root = root;

        const panel = new Node('Panel');
        panel.layer = layer;
        root.addChild(panel);
        panel.addComponent(UITransform).setContentSize(this.panelW, panelH);
        const pg = panel.addComponent(Graphics);
        pg.lineWidth = 4; pg.fillColor = new Color(40, 32, 54, 248);
        pg.strokeColor = new Color(214, 190, 232, 235);
        this.roundRect(pg, -this.panelW / 2, -panelH / 2, this.panelW, panelH, 18);
        pg.fill(); pg.stroke();

        const topY = panelH / 2;
        this.makeLabel(panel, '調配藥水', 26, new Color(245, 235, 255, 255),
            -this.panelW / 2 + 26, topY - 40, 260, Label.HorizontalAlign.LEFT);
        this.makeButton(panel, '✕', 40, 40, this.panelW / 2 - 34, topY - 34,
            new Color(120, 60, 70, 255), () => this.close());
        this.makeLabel(panel, 'Esc 關閉 · 材料足夠才能製作', 15, new Color(180, 174, 190, 255),
            -this.panelW / 2 + 26, -panelH / 2 + 15, 400, Label.HorizontalAlign.LEFT);

        PotionRecipes.all.forEach((r, i) => this.buildRow(panel, r, topY - this.headerH - i * this.rowH - this.rowH / 2 + 6));
    }

    private buildRow(parent: Node, r: Recipe, y: number) {
        const layer = this.node.layer;
        const leftX = -this.panelW / 2 + 26;
        const row = new Node('row-' + r.name);
        row.layer = layer;
        parent.addChild(row);
        row.addComponent(UITransform);
        row.setPosition(0, y, 0);

        // 成品圖示
        const icon = new Node('icon'); icon.layer = layer; row.addChild(icon);
        icon.addComponent(UITransform).setContentSize(46, 46);
        icon.setPosition(leftX + 23, 0, 0);
        const sp = icon.addComponent(Sprite); sp.sizeMode = Sprite.SizeMode.CUSTOM; sp.trim = false;
        const f = GameArt.item(r.name); if (f) this.fit(sp, f, 46, 46);
        this.iconSprites.push({ sp, name: r.name });

        // 名稱 + 售價
        this.makeLabel(row, r.name, 20, new Color(240, 238, 246, 255),
            leftX + 58, 11, 150, Label.HorizontalAlign.LEFT);
        this.makeLabel(row, `售價 ${r.sellPrice} 金`, 15, new Color(255, 224, 130, 255),
            leftX + 58, -13, 150, Label.HorizontalAlign.LEFT);

        // 材料需求（refresh 填字/上色）
        const inputLbl = this.makeLabel(row, '', 16, new Color(200, 200, 210, 255),
            leftX + 214, 0, 280, Label.HorizontalAlign.LEFT);

        // 製作鈕
        const btn = new Node('btn'); btn.layer = layer; row.addChild(btn);
        btn.addComponent(UITransform).setContentSize(92, 36);
        btn.setPosition(this.panelW / 2 - 66, 0, 0);
        const btnG = btn.addComponent(Graphics);
        btnG.lineWidth = 2; btnG.strokeColor = new Color(230, 220, 240, 160);
        btnG.fillColor = new Color(78, 118, 92, 255);
        this.roundRect(btnG, -46, -18, 92, 36, 8); btnG.fill(); btnG.stroke();
        const bt = new Node('t'); bt.layer = layer; btn.addChild(bt);
        bt.addComponent(UITransform).setContentSize(92, 36);
        const btnLbl = bt.addComponent(Label);
        btnLbl.string = '製作'; btnLbl.fontSize = 20; btnLbl.color = new Color(245, 245, 250, 255);
        btnLbl.horizontalAlign = Label.HorizontalAlign.CENTER; btnLbl.verticalAlign = Label.VerticalAlign.CENTER;
        const op = btn.addComponent(UIOpacity);
        btn.on(Node.EventType.TOUCH_START, () => { op.opacity = 180; });
        btn.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; this.tryCraft(r); });
        btn.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });

        this.rows.push({ r, inputLbl, btn, btnG, btnLbl });
    }

    private tryCraft(r: Recipe) {
        if (!PotionRecipes.canCraft(r)) { this.refresh(); return; }   // 材料不夠：不動作
        this.close();
        this.cauldron?.startBrew(r);   // 關面板→鍋爐開始熬煮動畫→結束產出
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
        const n = new Node('label'); n.layer = this.node.layer; parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, size + 8);
        ut.setAnchorPoint(align === Label.HorizontalAlign.CENTER ? 0.5 : align === Label.HorizontalAlign.RIGHT ? 1 : 0, 0.5);
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
        const n = new Node('btn'); n.layer = layer; parent.addChild(n);
        n.addComponent(UITransform).setContentSize(w, h);
        n.setPosition(x, y, 0);
        const g = n.addComponent(Graphics);
        g.lineWidth = 2; g.fillColor = fill; g.strokeColor = new Color(230, 220, 240, 200);
        this.roundRect(g, -w / 2, -h / 2, w, h, 8); g.fill(); g.stroke();
        const tn = new Node('t'); tn.layer = layer; n.addChild(tn);
        tn.addComponent(UITransform).setContentSize(w, h);
        const lb = tn.addComponent(Label);
        lb.string = text; lb.fontSize = Math.min(24, h - 16); lb.color = new Color(245, 245, 250, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER; lb.verticalAlign = Label.VerticalAlign.CENTER;
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
