import { _decorator, Component, Node, UITransform, Widget, Sprite, SpriteFrame,
         Label, Color, Graphics, CCString, find } from 'cc';
const { ccclass, property } = _decorator;

/**
 * 背包「資料」放在 module 層，`director.loadScene` 換場景時會保留（JS 模組不重跑），
 * 所以在森林採到的東西走到城鎮還在。每個場景的背包 UI 只是把這份資料畫出來。
 * 只存非空的堆疊、依取得順序排列。
 */
interface Stack { name: string; count: number; }
const stock: Stack[] = [];

/** 一格背包的畫面元件（純顯示，資料在 stock）。 */
interface Cell {
    icon: Sprite;          // 物品圖示（沒設圖示時隱藏）
    nameLabel: Label;      // 沒有圖示時，改用文字顯示物品名
    countLabel: Label;     // 右下角數量（>1 才顯示）
}

/**
 * 背包系統：畫面下排一排格子，採集到的東西往裡面放、可疊加數量。
 *
 * 用法有兩種：
 *   1) 什麼都不用做 —— 任何腳本呼叫 `Inventory.ensure()?.add('蘋果')`，
 *      沒有背包時會自動在 Canvas 底下生一個出來（見 GatherTree）。
 *   2) 想在編輯器裡調外觀 / 拖入物品圖示 —— 在 Canvas 下建一個空節點掛上本腳本，
 *      把 iconNames 和 icons 一一對應填好（例：iconNames[0]='蘋果' ↔ icons[0]=蘋果圖）。
 *      沒填圖示的物品就用名字的文字顯示，一樣能用。
 */
@ccclass('Inventory')
export class Inventory extends Component {
    /** 全域唯一的背包，讓任何腳本都能拿到。 */
    static instance: Inventory | null = null;

    /** 取得背包；沒有的話自動在 Canvas 底下建一個。找不到 Canvas 時回傳 null。 */
    static ensure(): Inventory | null {
        if (Inventory.instance) return Inventory.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[Inventory] 找不到 Canvas，無法建立背包 UI'); return null; }
        const node = new Node('InventoryUI');
        node.layer = canvas.layer;                 // 跟 Canvas 同一個 UI 圖層才會被畫出來
        canvas.addChild(node);
        return node.addComponent(Inventory);       // addComponent 會觸發 onLoad → 設好 instance
    }

    @property({ tooltip: '格子數量（下排幾格）' })
    slotCount = 8;
    @property({ tooltip: '每格邊長（像素）' })
    slotSize = 64;
    @property({ tooltip: '格子之間的間距（像素）' })
    gap = 8;
    @property({ tooltip: '整排離畫面底部的距離（像素）' })
    bottomMargin = 24;
    @property({ type: [CCString], tooltip: '物品名稱，與 icons 一一對應' })
    iconNames: string[] = [];
    @property({ type: [SpriteFrame], tooltip: '物品圖示，與 iconNames 一一對應' })
    icons: SpriteFrame[] = [];

    private cells: Cell[] = [];

    onLoad() {
        Inventory.instance = this;
        this.build();
        this.renderAll();          // 把 module 層既有的資料畫出來（跨場景帶過來的東西）
    }

    onDestroy() {
        if (Inventory.instance === this) Inventory.instance = null;
    }

    // ---- 對外 API（都是操作 module 層的 stock，換場景保留）----

    /** 加入物品：先找同名的堆疊疊加，沒有就新增一堆；格子滿了回傳 false。 */
    add(name: string, qty = 1): boolean {
        const s = stock.find(s => s.name === name);
        if (s) {
            s.count += qty;
        } else {
            if (stock.length >= this.slotCount) { console.warn(`[Inventory] 背包滿了，${name} 放不下`); return false; }
            stock.push({ name, count: qty });
        }
        this.renderAll();
        return true;
    }

    /** 取出物品（商店賣東西用）：數量不足回傳 false。 */
    remove(name: string, qty = 1): boolean {
        const i = stock.findIndex(s => s.name === name);
        if (i < 0 || stock[i].count < qty) return false;
        stock[i].count -= qty;
        if (stock[i].count === 0) stock.splice(i, 1);
        this.renderAll();
        return true;
    }

    /** 背包裡某物品的總數量。 */
    countOf(name: string): number {
        return stock.find(s => s.name === name)?.count ?? 0;
    }

    // ---- 建 UI ----

    private build() {
        const totalW = this.slotCount * this.slotSize + (this.slotCount - 1) * this.gap;

        const ut = this.getComponent(UITransform) ?? this.addComponent(UITransform)!;
        ut.setAnchorPoint(0.5, 0.5);
        ut.setContentSize(totalW, this.slotSize);

        // 靠畫面底部、水平置中
        const widget = this.getComponent(Widget) ?? this.addComponent(Widget)!;
        widget.isAlignBottom = true;
        widget.isAlignHorizontalCenter = true;
        widget.bottom = this.bottomMargin;
        widget.horizontalCenter = 0;
        widget.alignMode = Widget.AlignMode.ON_WINDOW_RESIZE;
        widget.updateAlignment();

        const startX = -(totalW - this.slotSize) / 2;   // 第一格中心的 x
        for (let i = 0; i < this.slotCount; i++) {
            this.cells.push(this.buildCell(i, startX + i * (this.slotSize + this.gap)));
        }
    }

    private buildCell(index: number, x: number): Cell {
        const s = this.slotSize;
        const layer = this.node.layer;

        const slotNode = new Node('Slot' + index);
        slotNode.layer = layer;
        this.node.addChild(slotNode);
        const sut = slotNode.addComponent(UITransform);
        sut.setAnchorPoint(0.5, 0.5);
        sut.setContentSize(s, s);
        slotNode.setPosition(x, 0, 0);

        // 格子外框（圓角方框）
        const g = slotNode.addComponent(Graphics);
        g.lineWidth = 3;
        g.fillColor = new Color(30, 24, 40, 170);
        g.strokeColor = new Color(210, 190, 230, 220);
        this.roundRect(g, -s / 2, -s / 2, s, s, 10);
        g.fill();
        g.stroke();

        // 物品圖示
        const iconNode = new Node('icon');
        iconNode.layer = layer;
        slotNode.addChild(iconNode);
        iconNode.addComponent(UITransform).setContentSize(s * 0.72, s * 0.72);
        const icon = iconNode.addComponent(Sprite);
        icon.sizeMode = Sprite.SizeMode.CUSTOM;
        icon.type = Sprite.Type.SIMPLE;
        iconNode.active = false;

        // 沒有圖示時，用文字顯示物品名
        const nameNode = new Node('name');
        nameNode.layer = layer;
        slotNode.addChild(nameNode);
        nameNode.addComponent(UITransform).setContentSize(s - 6, s - 6);
        const nameLabel = nameNode.addComponent(Label);
        nameLabel.fontSize = 18;
        nameLabel.lineHeight = 20;
        nameLabel.color = new Color(240, 240, 245, 255);
        nameLabel.horizontalAlign = Label.HorizontalAlign.CENTER;
        nameLabel.verticalAlign = Label.VerticalAlign.CENTER;
        nameLabel.overflow = Label.Overflow.SHRINK;
        nameLabel.enableWrapText = true;
        nameLabel.string = '';

        // 右下角數量
        const countNode = new Node('count');
        countNode.layer = layer;
        slotNode.addChild(countNode);
        const cut = countNode.addComponent(UITransform);
        cut.setAnchorPoint(1, 0);
        cut.setContentSize(s, 22);
        countNode.setPosition(s / 2 - 5, -s / 2 + 4, 0);
        const countLabel = countNode.addComponent(Label);
        countLabel.fontSize = 20;
        countLabel.color = new Color(255, 245, 180, 255);
        countLabel.horizontalAlign = Label.HorizontalAlign.RIGHT;
        countLabel.verticalAlign = Label.VerticalAlign.BOTTOM;
        countLabel.string = '';

        return { icon, nameLabel, countLabel };
    }

    /** 依 module 層的 stock 重畫所有格子。 */
    private renderAll() {
        for (let i = 0; i < this.cells.length; i++) {
            this.renderCell(this.cells[i], stock[i] ?? null);
        }
    }

    /** 依一筆堆疊（或 null＝空格）更新一格的顯示。 */
    private renderCell(cell: Cell, s: Stack | null) {
        const frame = s ? this.iconFor(s.name) : null;
        if (s && frame) {
            cell.icon.spriteFrame = frame;
            cell.icon.node.active = true;
            cell.nameLabel.string = '';
        } else {
            cell.icon.node.active = false;
            cell.nameLabel.string = s ? s.name : '';
        }
        cell.countLabel.string = s && s.count > 1 ? 'x' + s.count : '';
    }

    private iconFor(name: string): SpriteFrame | null {
        const i = this.iconNames.indexOf(name);
        return (i >= 0 && i < this.icons.length) ? this.icons[i] : null;
    }

    /** 用線段＋圓弧畫一個圓角方框（Graphics 沒有現成的跨版本 roundRect）。 */
    private roundRect(g: Graphics, x: number, y: number, w: number, h: number, r: number) {
        const HALF_PI = Math.PI / 2;
        g.moveTo(x + r, y);
        g.lineTo(x + w - r, y);
        g.arc(x + w - r, y + r, r, -HALF_PI, 0, false);
        g.lineTo(x + w, y + h - r);
        g.arc(x + w - r, y + h - r, r, 0, HALF_PI, false);
        g.lineTo(x + r, y + h);
        g.arc(x + r, y + h - r, r, HALF_PI, Math.PI, false);
        g.lineTo(x, y + r);
        g.arc(x + r, y + r, r, Math.PI, Math.PI + HALF_PI, false);
        g.close();
    }
}
