import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, Sprite, SpriteFrame, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity, view } from 'cc';
import { UIState } from './UIState';
import { Wallet } from './Wallet';
import { DecorCatalog } from './DecorCatalog';
import { Inventory } from './Inventory';
import { Garden } from './Garden';
import { GameArt } from './GameArt';
import { FLOWERS } from './data/garden';
import { BASE_PRICE } from './data/prices';
const { ccclass } = _decorator;

type Mode = 'decor' | 'seed';

/**
 * 花店的購買面板（modal，ensure 自動生，仿 ShopPanel），兩個分頁：
 *   裝飾品 —— 買回去擺在自己店裡（DecorCatalog.buy → Wallet 扣款）。
 *   花種子 —— 買回去種在後花園（Garden.buySeed → 扣款 ＋ 進背包）。
 * 兩頁都是「點格子就買一個」，內容每次 refresh 重畫，數量/金幣直接反映最新狀態。
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
    private tabBox: Node | null = null;
    private contentBox: Node | null = null;
    private titleLabel: Label | null = null;
    private goldLabel: Label | null = null;
    private hintLabel: Label | null = null;
    private mode: Mode = 'decor';
    private waitingArt = false;

    private readonly cols = 4;
    private readonly maxCell = 158;
    private readonly minCell = 100;
    private readonly pad = 24;
    private readonly headerH = 128;      // 標題列 ＋ 分頁按鈕列
    private cell = 158;                  // 實際格子大小（build 時依畫面高度算）
    private panelW = 0;
    private gridW = 0;

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
        Inventory.ensure();          // 買種子要進背包，先確定背包在
        if (!this.root) this.build();
        this.root!.active = true;
        UIState.modalOpen = true;
        // 圖示可能還在載，載完補畫一次（重複註冊沒意義，用旗標擋掉）
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

    private setMode(m: Mode) { this.mode = m; this.refresh(); }

    private refresh() {
        if (this.goldLabel) this.goldLabel.string = `金幣 ${Wallet.gold}`;
        if (this.titleLabel) {
            this.titleLabel.string = this.mode === 'decor' ? '花店 · 裝飾品' : '花店 · 花種子';
        }
        if (this.hintLabel) {
            this.hintLabel.string = this.mode === 'decor'
                ? 'Esc 關閉 · 點裝飾品購買（回自己店裡按「佈置房間」擺出來）'
                : 'Esc 關閉 · 點種子購買（回後花園走到花圃按 E 種下）';
        }
        this.buildTabs();
        const box = this.contentBox;
        if (!box) return;
        box.removeAllChildren();
        if (this.mode === 'decor') this.renderDecor(box);
        else this.renderSeeds(box);
    }

    // ---- 骨架 ----

    private build() {
        const layer = this.node.layer;
        const rows = Math.ceil(DecorCatalog.catalog.length / this.cols);

        // ⚠️ 16 個裝飾排成 4×4，格子若用滿 158px 整張面板會有 784 高 —— 比 640 的畫面
        // 還高，標題與底下那行提示就被切在畫面外。改成依實際畫面高度回推格子大小。
        const visH = view.getVisibleSize().height || 640;
        const room = Math.min(visH, 640) - 24 - this.headerH - this.pad;
        this.cell = Math.round(Math.max(this.minCell, Math.min(this.maxCell, room / rows)));

        this.gridW = this.cols * this.cell;
        const gridH = rows * this.cell;
        this.panelW = this.gridW + this.pad * 2;
        const panelW = this.panelW;
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
        this.titleLabel = this.makeLabel(panel, '', 26, new Color(245, 235, 255, 255),
            -panelW / 2 + 26, topY - 40, 300, Label.HorizontalAlign.LEFT);
        // 靠右擺在 ✕ 左邊（面板寬度會隨格子大小變，所以位置從右緣回推）
        this.goldLabel = this.makeLabel(panel, '', 24, new Color(255, 224, 130, 255),
            panelW / 2 - 64, topY - 40, 200, Label.HorizontalAlign.RIGHT);
        this.makeButton(panel, '✕', 40, 40, panelW / 2 - 34, topY - 34,
            new Color(120, 60, 70, 255), () => this.close());
        this.hintLabel = this.makeLabel(panel, '', 15, new Color(180, 174, 190, 255),
            -panelW / 2 + 26, -panelH / 2 + 16, 560, Label.HorizontalAlign.LEFT);

        const tabBox = new Node('Tabs');
        tabBox.layer = layer;
        panel.addChild(tabBox);
        tabBox.addComponent(UITransform);
        tabBox.setPosition(0, topY - 90, 0);
        this.tabBox = tabBox;

        const content = new Node('Content');
        content.layer = layer;
        panel.addChild(content);
        content.addComponent(UITransform);
        content.setPosition(0, topY - this.headerH, 0);
        this.contentBox = content;
    }

    private buildTabs() {
        const box = this.tabBox;
        if (!box) return;
        box.removeAllChildren();
        const active = new Color(96, 74, 128, 255);
        const idle = new Color(54, 46, 68, 255);
        this.makeButton(box, '裝飾品', 150, 40, -84, 0,
            this.mode === 'decor' ? active : idle, () => this.setMode('decor'));
        this.makeButton(box, '花種子', 150, 40, 84, 0,
            this.mode === 'seed' ? active : idle, () => this.setMode('seed'));
    }

    // ---- 裝飾品分頁 ----

    private renderDecor(box: Node) {
        const left = -this.gridW / 2;
        DecorCatalog.catalog.forEach((d, i) => {
            const cx = left + (i % this.cols) * this.cell + this.cell / 2;
            const cy = -Math.floor(i / this.cols) * this.cell - this.cell / 2;
            const owned = DecorCatalog.ownedCount(d.id);
            this.buildCell(box, cx, cy, {
                icon: () => GameArt.decor(d.id),
                name: d.name,
                price: d.price,
                owned: owned > 0 ? `擁有 ${owned}` : '',
                onBuy: () => { if (DecorCatalog.buy(d.id)) this.refresh(); },
            });
        });
    }

    // ---- 花種子分頁 ----

    private renderSeeds(box: Node) {
        const left = -(FLOWERS.length * this.cell) / 2;
        FLOWERS.forEach((f, i) => {
            const cx = left + i * this.cell + this.cell / 2;
            const bag = Inventory.countOf(f.seed);
            this.buildCell(box, cx, -this.cell / 2, {
                icon: () => GameArt.item(f.seed),
                name: f.seed,
                price: f.seedPrice,
                owned: bag > 0 ? `背包 ${bag}` : '',
                onBuy: () => { if (Garden.buySeed(f.seed)) this.refresh(); },
            });
        });

        // 種子頁下面補一段說明：種出來是什麼、收幾朵、賣多少
        FLOWERS.forEach((f, i) => {
            const worth = BASE_PRICE[f.flower] ?? 0;
            this.makeLabel(box, `${f.flower} ×${f.yield}（一朵 ${worth} 金）`, 16,
                new Color(206, 226, 200, 255),
                -(FLOWERS.length * this.cell) / 2 + i * this.cell + this.cell / 2,
                -this.cell - 18, this.cell, Label.HorizontalAlign.CENTER, true);
            this.makeLabel(box, `${f.flower}：${f.desc}`, 15, new Color(170, 164, 182, 255),
                0, -this.cell - 56 - i * 26, this.panelW - 80, Label.HorizontalAlign.CENTER, true);
        });
    }

    // ---- 一格商品 ----

    private buildCell(parent: Node, cx: number, cy: number, opt: {
        icon: () => SpriteFrame | null; name: string; price: number;
        owned: string; onBuy: () => void;
    }) {
        const layer = this.node.layer;
        const s = this.cell - 12;
        const cell = new Node('cell-' + opt.name);
        cell.layer = layer;
        parent.addChild(cell);
        cell.addComponent(UITransform).setContentSize(s, s);
        cell.setPosition(cx, cy, 0);
        const afford = Wallet.gold >= opt.price;
        const g = cell.addComponent(Graphics);
        g.lineWidth = 2;
        g.fillColor = new Color(58, 48, 74, 255);
        g.strokeColor = afford ? new Color(150, 130, 170, 200) : new Color(96, 88, 104, 160);
        this.roundRect(g, -s / 2, -s / 2, s, s, 10);
        g.fill(); g.stroke();

        // 圖示（格子會依畫面縮，所以內部排版都用比例）
        const iw = Math.round(s * 0.68), ih = Math.round(s * 0.5);
        const icon = new Node('icon');
        icon.layer = layer;
        cell.addChild(icon);
        icon.addComponent(UITransform).setContentSize(iw, ih);
        icon.setPosition(0, Math.round(s * 0.12), 0);
        const sp = icon.addComponent(Sprite);
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.trim = false;
        const f = opt.icon();
        if (f) this.fit(sp, f, iw, ih);

        // 名稱、售價、已有的數量
        const fs = Math.max(13, Math.round(s * 0.123));
        this.makeLabel(cell, opt.name, fs, new Color(240, 236, 248, 255),
            0, -s / 2 + Math.round(s * 0.3), s - 12, Label.HorizontalAlign.CENTER, true);
        this.makeLabel(cell, `${opt.price} 金`, fs - 1,
            afford ? new Color(255, 224, 130, 255) : new Color(150, 130, 110, 255),
            0, -s / 2 + Math.round(s * 0.15), s - 12, Label.HorizontalAlign.CENTER, true);
        this.makeLabel(cell, opt.owned, Math.max(12, fs - 4), new Color(150, 220, 160, 255),
            0, s / 2 - Math.round(s * 0.11), s - 12, Label.HorizontalAlign.CENTER, true);

        // 整格可點＝買一個
        const op = cell.addComponent(UIOpacity);
        cell.on(Node.EventType.TOUCH_START, () => { op.opacity = 180; });
        cell.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; opt.onBuy(); });
        cell.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
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
                      x: number, y: number, width: number, align: number,
                      centered = false): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, size + 8);
        ut.setAnchorPoint(centered || align === Label.HorizontalAlign.CENTER ? 0.5
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
        g.rect(x, y, w, h);   // 一般方框（不圓角）
    }
}
