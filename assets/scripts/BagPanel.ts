import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, Sprite, SpriteFrame, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity } from 'cc';
import { UIState } from './UIState';
import { Inventory } from './Inventory';
import { Storage } from './Storage';
import { Upgrades } from './Upgrades';
import { GameArt } from './GameArt';
import { Toast } from './Toast';
import { MATERIALS, POTION_ITEMS } from './data/items';
import { FLOWERS } from './data/garden';
const { ccclass } = _decorator;

/** 分頁：全部／材料／花與種子／藥水。 */
type Tab = 'all' | 'mat' | 'flower' | 'potion';
/** 面板模式：純看背包（B 鍵）／在櫥櫃前跟倉庫搬東西（E）。 */
type Mode = 'bag' | 'storage';

const POTIONS: string[] = Object.keys(POTION_ITEMS);
const GARDEN_ITEMS: string[] = (() => {
    const out: string[] = [];
    for (const f of FLOWERS) { out.push(f.seed); out.push(f.flower); }
    return out;
})();

function tabOf(name: string): Tab {
    if (MATERIALS.indexOf(name) >= 0) return 'mat';
    if (GARDEN_ITEMS.indexOf(name) >= 0) return 'flower';
    if (POTIONS.indexOf(name) >= 0) return 'potion';
    return 'all';          // 認不得的東西只在「全部」看得到
}

/**
 * 背包／倉庫面板（modal，ensure 自動生，仿 ShopManagePanel）。
 *
 * 兩種開法共用同一張列表，因為欄位幾乎一樣，分成兩支 UI 只會重複一遍：
 *   `open()`        ── 任何場景按 B：只看背包裡有什麼、還剩幾格。
 *   `openStorage()` ── 店裡走到左邊櫥櫃按 E：多出倉庫那一欄與存入/取回按鈕。
 *
 * ⚠️ 背包的上限是「幾**種**東西」（同名無限疊加），所以列表是一種一列、右邊寫數量，
 * 而不是一格一個。倉庫模式也會列出「只有倉庫裡有」的品項，才拿得回來。
 */
@ccclass('BagPanel')
export class BagPanel extends Component {
    static instance: BagPanel | null = null;

    static ensure(): BagPanel | null {
        if (BagPanel.instance) return BagPanel.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[BagPanel] 找不到 Canvas'); return null; }
        const node = new Node('BagUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(BagPanel);
    }

    private root: Node | null = null;
    private titleLabel: Label | null = null;
    private capLabel: Label | null = null;
    private tabBox: Node | null = null;
    private rowsBox: Node | null = null;
    private pageBox: Node | null = null;
    private hintLabel: Label | null = null;
    private tab: Tab = 'all';
    private mode: Mode = 'bag';
    private page = 0;
    private waitingArt = false;

    private readonly panelW = 720;
    private readonly headerH = 128;
    private readonly rowH = 54;
    private readonly perPage = 7;
    private readonly pagerH = 40;
    private readonly footerH = 34;

    onLoad() {
        BagPanel.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (BagPanel.instance === this) BagPanel.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    /** ⚠️ 只吃 Esc 關閉，不吃 B/E —— 開啟的那一下按鍵同一幀還會再被讀到。 */
    private onKeyDown(e: EventKeyboard) {
        if (this.root?.active && e.keyCode === KeyCode.ESCAPE) this.close();
    }

    /** B 鍵：看背包。 */
    open() { this.show('bag'); }
    /** 櫥櫃前按 E：跟倉庫搬東西。 */
    openStorage() { this.show('storage'); }

    private show(mode: Mode) {
        Inventory.ensure();
        this.mode = mode;
        this.page = 0;
        if (!this.root) this.build();
        this.root!.active = true;
        UIState.modalOpen = true;
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

    // ---- 內容 ----

    /** 這一頁要列的品項：背包有的 ＋（倉庫模式）倉庫有的，材料→花→藥水的順序。 */
    private items(): string[] {
        const seen: Record<string, boolean> = {};
        const all: string[] = [];
        const push = (n: string) => { if (!seen[n]) { seen[n] = true; all.push(n); } };
        for (const s of Inventory.list()) push(s.name);
        if (this.mode === 'storage') for (const s of Storage.list()) push(s.name);

        const order = MATERIALS.concat(GARDEN_ITEMS).concat(POTIONS);
        all.sort((a, b) => {
            const ia = order.indexOf(a), ib = order.indexOf(b);
            return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib);
        });
        return this.tab === 'all' ? all : all.filter(n => tabOf(n) === this.tab);
    }

    private refresh() {
        const bagTypes = Inventory.list().length;
        if (this.titleLabel) {
            this.titleLabel.string = this.mode === 'storage' ? '倉庫' : '背包';
        }
        if (this.capLabel) {
            this.capLabel.string = this.mode === 'storage'
                ? `背包 ${bagTypes}/${Upgrades.bagSlots()} 種　倉庫 ${Storage.types()}/${Storage.capacity()} 種`
                : `${bagTypes}/${Upgrades.bagSlots()} 種`;
        }
        if (this.hintLabel) {
            this.hintLabel.string = this.mode === 'storage'
                ? 'Esc 關閉 · 存入／取回整疊搬，[1] 只搬一個 · 全部存入＝把這一頁的東西都放進去'
                : 'Esc 關閉 · 背包裝不下時，把東西放進店裡左邊的櫥櫃';
        }
        this.buildTabs();

        const box = this.rowsBox;
        if (!box) return;
        box.removeAllChildren();
        const items = this.items();
        const pages = Math.max(1, Math.ceil(items.length / this.perPage));
        this.page = Math.min(Math.max(0, this.page), pages - 1);

        if (items.length === 0) {
            this.makeLabel(box, this.tab === 'all' ? '空空如也 —— 去森林採點東西吧' : '這一類目前沒有東西',
                20, new Color(200, 192, 184, 255), 0, -70, this.panelW - 120, Label.HorizontalAlign.CENTER, true);
        } else {
            const from = this.page * this.perPage;
            items.slice(from, from + this.perPage).forEach((name, i) =>
                this.row(box, name, -20 - i * this.rowH));
        }
        this.buildPager(pages);
    }

    private row(parent: Node, name: string, y: number) {
        const layer = this.node.layer;
        const leftX = -this.panelW / 2 + 26;
        const bag = Inventory.countOf(name);
        const kept = Storage.count(name);

        const row = new Node('row-' + name);
        row.layer = layer;
        parent.addChild(row);
        row.addComponent(UITransform);
        row.setPosition(0, y, 0);

        // 圖示
        const icon = new Node('icon');
        icon.layer = layer;
        row.addChild(icon);
        icon.addComponent(UITransform).setContentSize(38, 38);
        icon.setPosition(leftX + 19, 0, 0);
        const sp = icon.addComponent(Sprite);
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.trim = false;
        const f = GameArt.item(name);
        if (f) this.fit(sp, f, 38, 38);

        this.makeLabel(row, name, 20, new Color(244, 238, 228, 255),
            leftX + 48, 0, 150, Label.HorizontalAlign.LEFT);

        if (this.mode === 'bag') {
            this.makeLabel(row, bag > 0 ? `×${bag}` : '—', 20,
                bag > 0 ? new Color(220, 230, 210, 255) : new Color(130, 126, 120, 255),
                leftX + 240, 0, 90, Label.HorizontalAlign.LEFT);
            return;
        }

        // 倉庫模式：背包數 ─ 存入／取回 ─ 倉庫數
        this.makeLabel(row, `背包 ${bag}`, 18,
            bag > 0 ? new Color(220, 230, 210, 255) : new Color(130, 126, 120, 255),
            0, 0, 110, Label.HorizontalAlign.CENTER, true, leftX + 250);

        // 右半邊的欄位間距抓過了：存入/[1]/取回/[1] 各自不重疊，最右邊留給「倉庫 N」
        const canKeep = bag > 0 && Storage.canAdd(name);
        this.makeButton(row, '存入', 62, 34, 6, 0,
            canKeep ? new Color(78, 108, 122, 255) : new Color(70, 66, 62, 255),
            () => { if (canKeep) { this.moveToStorage(name, bag); } });
        this.makeButton(row, '[1]', 40, 34, 70, 0,
            canKeep ? new Color(62, 84, 96, 255) : new Color(70, 66, 62, 255),
            () => { if (canKeep) { this.moveToStorage(name, 1); } });

        const canTake = kept > 0;
        this.makeButton(row, '取回', 62, 34, 146, 0,
            canTake ? new Color(108, 92, 62, 255) : new Color(70, 66, 62, 255),
            () => { if (canTake) { this.moveToBag(name, kept); } });
        this.makeButton(row, '[1]', 40, 34, 210, 0,
            canTake ? new Color(88, 76, 54, 255) : new Color(70, 66, 62, 255),
            () => { if (canTake) { this.moveToBag(name, 1); } });

        this.makeLabel(row, `倉庫 ${kept}`, 18,
            kept > 0 ? new Color(255, 224, 160, 255) : new Color(130, 126, 120, 255),
            0, 0, 96, Label.HorizontalAlign.CENTER, true, this.panelW / 2 - 68);
    }

    /** 背包 → 倉庫（倉庫放得下才扣背包）。 */
    private moveToStorage(name: string, qty: number) {
        if (qty <= 0 || !Storage.canAdd(name)) return;
        if (!Inventory.instance?.remove(name, qty)) return;
        Storage.add(name, qty);
        this.refresh();
    }

    /** 倉庫 → 背包（背包種類滿了就搬不動，東西留在倉庫）。 */
    private moveToBag(name: string, qty: number) {
        if (qty <= 0 || Storage.count(name) < qty) return;
        const inv = Inventory.ensure();
        if (!inv || !inv.add(name, qty)) return;      // add 回 false ＝ 背包種類滿了
        Storage.remove(name, qty);
        this.refresh();
    }

    // ---- 骨架 ----

    private build() {
        const layer = this.node.layer;
        const panelH = this.headerH + this.perPage * this.rowH + this.pagerH + this.footerH;

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
        pg.fillColor = new Color(42, 36, 32, 248);
        pg.strokeColor = new Color(220, 198, 160, 235);
        pg.rect(-this.panelW / 2, -panelH / 2, this.panelW, panelH);
        pg.fill(); pg.stroke();

        const topY = panelH / 2;
        this.titleLabel = this.makeLabel(panel, '', 26, new Color(250, 238, 220, 255),
            -this.panelW / 2 + 26, topY - 36, 220, Label.HorizontalAlign.LEFT);
        this.capLabel = this.makeLabel(panel, '', 18, new Color(206, 196, 178, 255),
            this.panelW / 2 - 64, topY - 38, 420, Label.HorizontalAlign.RIGHT);
        this.makeButton(panel, '✕', 40, 40, this.panelW / 2 - 30, topY - 34,
            new Color(120, 60, 70, 255), () => this.close());
        this.hintLabel = this.makeLabel(panel, '', 15, new Color(184, 176, 166, 255),
            -this.panelW / 2 + 26, -panelH / 2 + 16, 620, Label.HorizontalAlign.LEFT);

        const tabs = new Node('Tabs');
        tabs.layer = layer;
        panel.addChild(tabs);
        tabs.addComponent(UITransform);
        tabs.setPosition(0, topY - 86, 0);
        this.tabBox = tabs;

        const rows = new Node('Rows');
        rows.layer = layer;
        panel.addChild(rows);
        rows.addComponent(UITransform);
        rows.setPosition(0, topY - this.headerH, 0);
        this.rowsBox = rows;

        const pager = new Node('Pager');
        pager.layer = layer;
        panel.addChild(pager);
        pager.addComponent(UITransform);
        pager.setPosition(0, -panelH / 2 + this.footerH + this.pagerH / 2, 0);
        this.pageBox = pager;
    }

    private buildTabs() {
        const box = this.tabBox;
        if (!box) return;
        box.removeAllChildren();
        const active = new Color(118, 92, 58, 255);
        const idle = new Color(64, 56, 50, 255);
        const defs: Array<[Tab, string]> = [
            ['all', '全部'], ['mat', '材料'], ['flower', '花與種子'], ['potion', '藥水'],
        ];
        defs.forEach(([t, label], i) => {
            this.makeButton(box, label, 148, 38, -246 + i * 164, 0,
                this.tab === t ? active : idle,
                () => { this.tab = t; this.page = 0; this.refresh(); });
        });
    }

    /**
     * 把「目前分頁裡、背包有的」東西一次全部存進倉庫。
     * 吃分頁是刻意的：在「全部」頁就是整個背包倒進去，切到「材料」頁就只倒材料，
     * 不必為了「只想存材料」再多做一顆按鈕。
     */
    private stashAllInTab() {
        let moved = 0;
        for (const name of this.items()) {
            const qty = Inventory.countOf(name);
            if (qty <= 0 || !Storage.canAdd(name)) continue;      // 倉庫種類滿了就跳過
            if (!Inventory.instance?.remove(name, qty)) continue;
            Storage.add(name, qty);
            moved++;
        }
        Toast.show(moved > 0 ? `已存入 ${moved} 種` : '沒有可以存入的東西');
        this.refresh();
    }

    private buildPager(pages: number) {
        const box = this.pageBox;
        if (!box) return;
        box.removeAllChildren();

        // 「全部存入」擺在翻頁列左邊（翻頁鈕在正中央 ±96，不會打架）
        if (this.mode === 'storage') {
            this.makeButton(box, '全部存入', 130, 34, -this.panelW / 2 + 95, 0,
                new Color(78, 108, 122, 255), () => this.stashAllInTab());
        }
        if (pages <= 1) return;
        if (this.page > 0) {
            this.makeButton(box, '<', 46, 32, -96, 0, new Color(72, 62, 54, 255),
                () => { this.page--; this.refresh(); });
        }
        this.makeLabel(box, `第 ${this.page + 1} / ${pages} 頁`, 17,
            new Color(218, 208, 192, 255), 0, 0, 160, Label.HorizontalAlign.CENTER, true);
        if (this.page < pages - 1) {
            this.makeButton(box, '>', 46, 32, 96, 0, new Color(72, 62, 54, 255),
                () => { this.page++; this.refresh(); });
        }
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
        g.lineWidth = 2; g.fillColor = fill; g.strokeColor = new Color(228, 216, 198, 190);
        g.rect(-w / 2, -h / 2, w, h); g.fill(); g.stroke();
        const tn = new Node('t');
        tn.layer = layer; n.addChild(tn);
        tn.addComponent(UITransform).setContentSize(w, h);
        const lb = tn.addComponent(Label);
        lb.string = text; lb.fontSize = Math.min(20, h - 14);
        lb.color = new Color(244, 240, 232, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;
        const op = n.addComponent(UIOpacity);
        n.on(Node.EventType.TOUCH_START, () => { op.opacity = 170; });
        n.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; onClick(); });
        n.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
    }
}
