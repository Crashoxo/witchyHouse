import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity } from 'cc';
import { Inventory } from './Inventory';
import { UIState } from './UIState';
import { Wallet } from './Wallet';
const { ccclass } = _decorator;

/** 商店收購一項材料的定義：名稱 + 單價。 */
export interface BuyEntry { name: string; price: number; }

/** 沒在 inspector 指定時，雜貨鋪預設收購的材料與單價。 */
export const DEFAULT_BUY: BuyEntry[] = [
    { name: '木材', price: 5 },
    { name: '樹枝', price: 3 },
    { name: '漿果', price: 8 },
    { name: '落葉', price: 2 },
    { name: '藥草', price: 12 },
    { name: '黑莓', price: 10 },
    { name: '金蘋果', price: 50 },
];

/**
 * 收購面板（modal）：全域唯一，走近商店按 E 開，可把背包材料賣成金幣。
 * 仿 Inventory 的 ensure() 自動生 UI，場景不用預先擺。
 */
@ccclass('ShopPanel')
export class ShopPanel extends Component {
    static instance: ShopPanel | null = null;

    /** 取得面板；沒有的話自動在 Canvas 底下建一個（找不到 Canvas 回 null）。 */
    static ensure(): ShopPanel | null {
        if (ShopPanel.instance) return ShopPanel.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[ShopPanel] 找不到 Canvas，無法建立商店 UI'); return null; }
        const node = new Node('ShopUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(ShopPanel);
    }

    private title = '';
    private entries: BuyEntry[] = [];
    private root: Node | null = null;      // 整個面板（含背板），關閉時隱藏
    private rowsBox: Node | null = null;    // 材料列的容器，賣出後重建
    private goldLabel: Label | null = null;

    private readonly panelW = 600;
    private readonly headerH = 96;
    private readonly rowH = 60;
    private readonly footerH = 40;

    onLoad() {
        ShopPanel.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (ShopPanel.instance === this) ShopPanel.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    private onKeyDown(e: EventKeyboard) {
        // 只用 Esc（或右上角 ✕）關閉；不吃 E，避免同一次 E 被建築的 onKeyDown 又重新開啟
        if (this.root?.active && e.keyCode === KeyCode.ESCAPE) this.close();
    }

    /** 開啟收購面板，收購清單由呼叫端（商店建築）決定。 */
    open(title: string, entries: BuyEntry[]) {
        Inventory.ensure();          // 確保背包存在（城鎮還沒生過時，才讀得到跨場景帶來的材料）
        this.title = title;
        this.entries = entries;
        if (!this.root) this.build();
        this.root!.active = true;
        UIState.modalOpen = true;
        this.refresh();
    }

    close() {
        if (this.root) this.root.active = false;
        UIState.modalOpen = false;
    }

    isOpen(): boolean { return !!this.root?.active; }

    // ---- 建面板骨架（只建一次，之後重複開關）----

    private build() {
        const layer = this.node.layer;
        const rowsH = Math.max(1, this.entries.length) * this.rowH;
        const panelH = this.headerH + rowsH + this.footerH;

        // 半透明背板，擋住後面世界的點擊
        const root = new Node('Root');
        root.layer = layer;
        this.node.addChild(root);
        const rut = root.addComponent(UITransform);
        rut.setContentSize(3000, 2000);
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

        // 面板本體
        const panel = new Node('Panel');
        panel.layer = layer;
        root.addChild(panel);
        panel.addComponent(UITransform).setContentSize(this.panelW, panelH);
        const pg = panel.addComponent(Graphics);
        pg.lineWidth = 4;
        pg.fillColor = new Color(38, 30, 52, 245);
        pg.strokeColor = new Color(210, 190, 230, 235);
        this.roundRect(pg, -this.panelW / 2, -panelH / 2, this.panelW, panelH, 18);
        pg.fill(); pg.stroke();

        const topY = panelH / 2;

        // 標題
        this.makeLabel(panel, this.title, 26, new Color(245, 235, 255, 255),
            0, topY - 34, this.panelW - 140, Label.HorizontalAlign.LEFT, -this.panelW / 2 + 28);

        // 金幣顯示（右上）
        this.goldLabel = this.makeLabel(panel, '', 24, new Color(255, 224, 130, 255),
            0, topY - 34, 200, Label.HorizontalAlign.RIGHT, this.panelW / 2 - 228);

        // 關閉 X（右上角）
        this.makeButton(panel, '✕', 40, 40, this.panelW / 2 - 34, topY - 34,
            new Color(120, 60, 70, 255), () => this.close());

        // 底部小提示
        this.makeLabel(panel, 'Esc 關閉', 16, new Color(180, 174, 190, 255),
            0, -panelH / 2 + 18, 200, Label.HorizontalAlign.CENTER, 0);

        // 材料列容器（從標題下方往下排）
        const rowsBox = new Node('Rows');
        rowsBox.layer = layer;
        panel.addChild(rowsBox);
        rowsBox.addComponent(UITransform);
        rowsBox.setPosition(0, topY - this.headerH, 0);
        this.rowsBox = rowsBox;
    }

    /** 依目前背包狀態重建材料列 + 更新金幣。 */
    private refresh() {
        if (this.goldLabel) this.goldLabel.string = `金幣 ${Wallet.gold}`;
        const box = this.rowsBox;
        if (!box) return;
        box.removeAllChildren();

        const inv = Inventory.instance;
        const owned = this.entries.filter(e => (inv?.countOf(e.name) ?? 0) > 0);

        if (owned.length === 0) {
            this.makeLabel(box, '背包裡沒有可賣的材料', 22, new Color(200, 195, 210, 255),
                0, -this.rowH / 2, this.panelW - 80, Label.HorizontalAlign.CENTER, 0);
            return;
        }

        owned.forEach((e, i) => {
            const y = -i * this.rowH - this.rowH / 2 + 6;
            this.buildRow(box, e, y);
        });
    }

    private buildRow(parent: Node, e: BuyEntry, y: number) {
        const inv = Inventory.instance;
        const count = inv?.countOf(e.name) ?? 0;
        const layer = this.node.layer;
        const leftX = -this.panelW / 2 + 28;

        const row = new Node('row-' + e.name);
        row.layer = layer;
        parent.addChild(row);
        row.addComponent(UITransform);
        row.setPosition(0, y, 0);

        // 名稱 x 數量
        this.makeLabel(row, `${e.name}  ×${count}`, 22, new Color(240, 238, 246, 255),
            0, 0, 200, Label.HorizontalAlign.LEFT, leftX);
        // 單價
        this.makeLabel(row, `${e.price} 金`, 20, new Color(255, 224, 130, 255),
            0, 0, 120, Label.HorizontalAlign.LEFT, leftX + 210);

        // 賣 1 / 全賣
        this.makeButton(row, '賣 1', 78, 40, this.panelW / 2 - 190, 0,
            new Color(70, 96, 120, 255), () => this.sell(e, 1));
        this.makeButton(row, '全賣', 88, 40, this.panelW / 2 - 78, 0,
            new Color(78, 118, 92, 255), () => this.sell(e, count));
    }

    private sell(e: BuyEntry, qty: number) {
        const inv = Inventory.instance;
        if (!inv || qty <= 0) return;
        if (!inv.remove(e.name, qty)) return;   // 數量不足就不成交
        Wallet.add(e.price * qty);
        this.refresh();
    }

    // ---- 小工具 ----

    private makeLabel(parent: Node, text: string, size: number, color: Color,
                      x: number, y: number, width: number,
                      align: number, anchorX: number): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, size + 8);
        ut.setAnchorPoint(align === Label.HorizontalAlign.RIGHT ? 1
                        : align === Label.HorizontalAlign.CENTER ? 0.5 : 0, 0.5);
        n.setPosition(align === Label.HorizontalAlign.CENTER ? x : anchorX, y, 0);
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
        g.strokeColor = new Color(230, 220, 240, 200);
        this.roundRect(g, -w / 2, -h / 2, w, h, 8);
        g.fill(); g.stroke();

        const tn = new Node('t');
        tn.layer = layer;
        n.addChild(tn);
        tn.addComponent(UITransform).setContentSize(w, h);
        const lb = tn.addComponent(Label);
        lb.string = text;
        lb.fontSize = Math.min(24, h - 16);
        lb.color = new Color(245, 245, 250, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;

        // 按下時稍微變暗當回饋
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
