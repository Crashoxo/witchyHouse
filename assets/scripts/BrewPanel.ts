import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, Sprite, SpriteFrame, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity } from 'cc';
import { UIState } from './UIState';
import { GameArt } from './GameArt';
import { PotionRecipes, Recipe } from './PotionRecipes';
import { Inventory } from './Inventory';
import { Storage } from './Storage';
import { BrewCauldron } from './BrewCauldron';
const { ccclass } = _decorator;

/**
 * 調配藥水面板（modal，ensure 自動生，仿 ShopPanel）。列出所有配方：成品圖示、名稱、
 * 售價、所需材料（夠＝綠、不夠＝紅），以及 ×1／×5／最大 三顆份量鈕。按下＝關面板、
 * 鍋爐熬**一次**動畫、結束時一口氣產出那一批（做 10 份不用看 10 遍動畫）。
 * 「有幾個」與扣料都算**背包＋倉庫**（材料進城鎮會自動歸位到倉庫）。
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
    /** 一列：材料需求文字 ＋ 三顆份量鈕（×1／×5／最大）。 */
    private rows: Array<{
        r: Recipe;
        inputLbl: Label;
        btns: Array<{ batch: 1 | 5 | 0; g: Graphics; lbl: Label; w: number; h: number }>;
    }> = [];

    private readonly panelW = 660;
    private readonly headerH = 74;
    private readonly rowH = 62;
    private readonly footerH = 28;
    /**
     * 一頁最多幾條配方。配方一多，整張面板就會比 640 高的畫面還高（頭尾會被切掉），
     * 所以固定每頁 7 條、底下加一列翻頁鈕（同任務簿的作法）。
     */
    private readonly perPage = 7;
    private readonly pagerH = 40;
    private page = 0;
    private rowsBox: Node | null = null;
    private pageBox: Node | null = null;

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
        this.page = 0;
        this.renderPage();
    }

    close() {
        if (this.root) this.root.active = false;
        UIState.modalOpen = false;
    }

    // ---- 依現有材料更新每列（夠不夠、哪幾顆份量鈕亮得起來）----
    private refresh() {
        Inventory.ensure();
        for (const row of this.rows) {
            const max = PotionRecipes.maxCraftable(row.r);
            // ⚠️「有幾個」要算背包＋倉庫 —— 材料進城鎮會自動歸位到倉庫，只報背包的話
            // 會出現「明明做得出來卻寫材料不夠」。
            const parts = Object.keys(row.r.inputs).map(m =>
                `${m}×${row.r.inputs[m]}(有${Storage.availableOf(m)})`);
            row.inputLbl.string = parts.join('  ');
            row.inputLbl.color = max > 0 ? new Color(150, 220, 160, 255) : new Color(224, 150, 150, 255);

            for (const b of row.btns) {
                const qty = b.batch === 0 ? max : b.batch;      // batch 0 ＝「最大」那顆
                const ok = qty > 0 && PotionRecipes.canCraft(row.r, qty);
                b.lbl.string = b.batch === 0 ? `×${Math.max(1, max)}` : `×${b.batch}`;
                b.lbl.color = ok ? new Color(245, 245, 250, 255) : new Color(150, 145, 158, 255);
                b.g.fillColor = ok ? new Color(78, 118, 92, 255) : new Color(70, 66, 78, 255);
                b.g.clear();
                this.roundRect(b.g, -b.w / 2, -b.h / 2, b.w, b.h, 8);
                b.g.fill(); b.g.stroke();
            }
        }
    }

    private iconSprites: Array<{ sp: Sprite; name: string }> = [];
    private refreshIcons() {
        this.iconSprites.forEach(({ sp, name }) => {
            const f = GameArt.item(name);
            if (f) this.fit(sp, f, 46, 46);
        });
    }

    /** 換頁：把這一頁的配方重畫出來（列是每頁重建的，refresh 只更新字與按鈕）。 */
    private renderPage() {
        const box = this.rowsBox;
        if (!box) return;
        box.removeAllChildren();
        this.rows.length = 0;
        this.iconSprites.length = 0;

        const all = PotionRecipes.all;
        const pages = Math.max(1, Math.ceil(all.length / this.perPage));
        this.page = Math.min(Math.max(0, this.page), pages - 1);
        const from = this.page * this.perPage;
        all.slice(from, from + this.perPage).forEach((r, i) =>
            this.buildRow(box, r, -i * this.rowH - this.rowH / 2 + 6));

        this.buildPager(pages);
        this.refresh();
    }

    private buildPager(pages: number) {
        const box = this.pageBox;
        if (!box) return;
        box.removeAllChildren();
        if (pages <= 1) return;
        if (this.page > 0) {
            this.makeButton(box, '<', 46, 32, -96, 0, new Color(72, 60, 88, 255),
                () => { this.page--; this.renderPage(); });
        }
        this.makeLabel(box, `第 ${this.page + 1} / ${pages} 頁`, 17,
            new Color(214, 206, 226, 255), 0, 0, 160, Label.HorizontalAlign.CENTER);
        if (this.page < pages - 1) {
            this.makeButton(box, '>', 46, 32, 96, 0, new Color(72, 60, 88, 255),
                () => { this.page++; this.renderPage(); });
        }
    }

    private build() {
        const layer = this.node.layer;
        const rowsH = Math.min(PotionRecipes.all.length, this.perPage) * this.rowH;
        const paged = PotionRecipes.all.length > this.perPage;
        const panelH = this.headerH + rowsH + (paged ? this.pagerH : 0) + this.footerH;

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
        this.makeLabel(panel, 'Esc 關閉 · 材料夠才按得動；×N 是一次熬幾份（材料算背包＋倉庫）', 15, new Color(180, 174, 190, 255),
            -this.panelW / 2 + 26, -panelH / 2 + 15, 400, Label.HorizontalAlign.LEFT);

        const rowsBox = new Node('Rows');
        rowsBox.layer = layer;
        panel.addChild(rowsBox);
        rowsBox.addComponent(UITransform);
        rowsBox.setPosition(0, topY - this.headerH, 0);
        this.rowsBox = rowsBox;

        const pageBox = new Node('Pager');
        pageBox.layer = layer;
        panel.addChild(pageBox);
        pageBox.addComponent(UITransform);
        pageBox.setPosition(0, -panelH / 2 + this.footerH + this.pagerH / 2, 0);
        this.pageBox = pageBox;

        this.renderPage();
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
            leftX + 58, 11, 112, Label.HorizontalAlign.LEFT);
        this.makeLabel(row, `售價 ${r.sellPrice} 金`, 15, new Color(255, 224, 130, 255),
            leftX + 58, -13, 112, Label.HorizontalAlign.LEFT);

        // 材料需求（refresh 填字/上色）。寬度縮到 200，右邊要留給三顆份量鈕。
        const inputLbl = this.makeLabel(row, '', 16, new Color(200, 200, 210, 255),
            leftX + 176, 0, 264, Label.HorizontalAlign.LEFT);

        // 份量鈕：×1／×5／最大（最大那顆的字是實際能做的份數，refresh 時填）
        const btns = [
            this.craftButton(row, r, 1, 168, 48),
            this.craftButton(row, r, 5, 220, 48),
            this.craftButton(row, r, 0, 280, 58),
        ];

        this.rows.push({ r, inputLbl, btns });
    }

    /** 一顆份量鈕。batch 0 代表「最大」——按下時才去算現在能做幾份。 */
    private craftButton(row: Node, r: Recipe, batch: 1 | 5 | 0, x: number, w: number) {
        const layer = this.node.layer;
        const h = 36;
        const btn = new Node('btn' + batch); btn.layer = layer; row.addChild(btn);
        btn.addComponent(UITransform).setContentSize(w, h);
        btn.setPosition(x, 0, 0);
        const g = btn.addComponent(Graphics);
        g.lineWidth = 2; g.strokeColor = new Color(230, 220, 240, 160);
        g.fillColor = new Color(78, 118, 92, 255);
        this.roundRect(g, -w / 2, -h / 2, w, h, 8); g.fill(); g.stroke();
        const bt = new Node('t'); bt.layer = layer; btn.addChild(bt);
        bt.addComponent(UITransform).setContentSize(w, h);
        const lbl = bt.addComponent(Label);
        lbl.string = batch === 0 ? '×1' : `×${batch}`;
        lbl.fontSize = 19; lbl.color = new Color(245, 245, 250, 255);
        lbl.horizontalAlign = Label.HorizontalAlign.CENTER;
        lbl.verticalAlign = Label.VerticalAlign.CENTER;
        lbl.overflow = Label.Overflow.SHRINK;
        const op = btn.addComponent(UIOpacity);
        btn.on(Node.EventType.TOUCH_START, () => { op.opacity = 180; });
        btn.on(Node.EventType.TOUCH_END, () => {
            op.opacity = 255;
            this.tryCraft(r, batch === 0 ? PotionRecipes.maxCraftable(r) : batch);
        });
        btn.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
        return { batch, g, lbl, w, h };
    }

    private tryCraft(r: Recipe, qty: number) {
        if (qty <= 0 || !PotionRecipes.canCraft(r, qty)) { this.refresh(); return; }   // 材料不夠：不動作
        this.close();
        this.cauldron?.startBrew(r, qty);   // 關面板→鍋爐熬一次動畫→結束一次產出 qty 份
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
        g.rect(x, y, w, h);   // 一般方框（不圓角）
    }
}
