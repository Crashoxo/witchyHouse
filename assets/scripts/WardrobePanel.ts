import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, Sprite, SpriteFrame, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity } from 'cc';
import { UIState } from './UIState';
import { GameArt } from './GameArt';
import { Outfits } from './Outfits';
import { OutfitDef } from './data/outfits';
const { ccclass } = _decorator;

/**
 * 衣櫃（modal，ensure 自動生）：左邊一排造型、右邊看立繪與說明，按「換上」就換。
 * 換裝的實際效果在 Outfits.set() → GameArt.applyOutfit()：整批姿勢圖換掉，
 * 所以場景裡的小人（走路／採集／澆水／摘花／施法／睡覺）全部一起換。
 *
 * ⚠️ 只吃 Esc/✕ 關閉，不吃 E —— 開啟的那一下 E 同一幀還會被讀到（同 ShopPanel 老坑）。
 */
@ccclass('WardrobePanel')
export class WardrobePanel extends Component {
    static instance: WardrobePanel | null = null;

    static ensure(): WardrobePanel | null {
        if (WardrobePanel.instance) return WardrobePanel.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[WardrobePanel] 找不到 Canvas'); return null; }
        const node = new Node('WardrobeUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(WardrobePanel);
    }

    private root: Node | null = null;
    private listBox: Node | null = null;
    private previewBox: Node | null = null;
    private picked = '';
    private waitingArt = false;

    private readonly panelW = 760;
    private readonly panelH = 560;
    private readonly listW = 260;
    private readonly rowH = 74;

    onLoad() {
        WardrobePanel.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (WardrobePanel.instance === this) WardrobePanel.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    private onKeyDown(e: EventKeyboard) {
        if (this.root?.active && e.keyCode === KeyCode.ESCAPE) this.close();
    }

    open() {
        if (!this.root) this.build();
        this.picked = Outfits.currentId();
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

    private refresh() {
        this.renderList();
        this.renderPreview();
    }

    // ---- 左邊：造型清單 ----

    private renderList() {
        const box = this.listBox;
        if (!box) return;
        box.removeAllChildren();
        Outfits.all().forEach((o, i) => {
            const y = -20 - i * this.rowH;
            const worn = Outfits.currentId() === o.id;
            const sel = this.picked === o.id;
            const w = this.listW - 24, h = this.rowH - 12;

            const row = new Node('outfit-' + o.id);
            row.layer = this.node.layer;
            box.addChild(row);
            row.addComponent(UITransform).setContentSize(w, h);
            row.setPosition(0, y, 0);
            const g = row.addComponent(Graphics);
            g.lineWidth = 2;
            g.fillColor = sel ? new Color(96, 76, 54, 255) : new Color(56, 48, 42, 255);
            g.strokeColor = sel ? new Color(240, 214, 160, 235) : new Color(140, 126, 110, 190);
            g.rect(-w / 2, -h / 2, w, h);
            g.fill(); g.stroke();

            this.makeLabel(row, o.name, 22, new Color(246, 238, 224, 255),
                -w / 2 + 16, 10, w - 32, Label.HorizontalAlign.LEFT);
            this.makeLabel(row, worn ? '穿著中' : '', 16, new Color(168, 210, 160, 255),
                -w / 2 + 16, -14, w - 32, Label.HorizontalAlign.LEFT);

            const op = row.addComponent(UIOpacity);
            row.on(Node.EventType.TOUCH_START, () => { op.opacity = 190; });
            row.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
            row.on(Node.EventType.TOUCH_END, () => {
                op.opacity = 255; this.picked = o.id; this.refresh();
            });
        });
    }

    // ---- 右邊：立繪＋說明＋換上 ----

    private renderPreview() {
        const box = this.previewBox;
        if (!box) return;
        box.removeAllChildren();
        const o: OutfitDef = Outfits.all().filter(x => x.id === this.picked)[0] ?? Outfits.all()[0];
        const w = this.panelW - this.listW - 60;

        // 立繪（載不到就畫個框，不開天窗）
        const frame = o.portrait ? GameArt.portrait(o.portrait) : null;
        const maxH = 320, maxW = w - 40;
        const holder = new Node('portrait');
        holder.layer = this.node.layer;
        box.addChild(holder);
        holder.setPosition(0, 30, 0);
        if (frame) {
            const ut = holder.addComponent(UITransform);
            const rw = frame.rect.width || frame.originalSize.width;
            const rh = frame.rect.height || frame.originalSize.height;
            const k = Math.min(maxW / rw, maxH / rh);
            ut.setContentSize(rw * k, rh * k);
            const sp = holder.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM;
            sp.trim = false;
            sp.spriteFrame = frame;
        } else {
            holder.addComponent(UITransform).setContentSize(maxW * 0.6, maxH);
            const g = holder.addComponent(Graphics);
            g.lineWidth = 2;
            g.fillColor = new Color(48, 42, 38, 255);
            g.strokeColor = new Color(150, 134, 116, 200);
            g.rect(-maxW * 0.3, -maxH / 2, maxW * 0.6, maxH);
            g.fill(); g.stroke();
            this.makeLabel(holder, '（沒有立繪）', 18, new Color(160, 150, 140, 255),
                0, 0, maxW * 0.6, Label.HorizontalAlign.CENTER, true);
        }

        this.makeLabel(box, o.name, 26, new Color(250, 238, 220, 255),
            0, -170, w, Label.HorizontalAlign.CENTER, true);
        this.makeLabel(box, o.desc, 17, new Color(196, 186, 172, 255),
            0, -202, w - 20, Label.HorizontalAlign.CENTER, true);

        const worn = Outfits.currentId() === o.id;
        this.makeButton(box, worn ? '穿著中' : '換上', 160, 46, 0, -252,
            worn ? new Color(70, 66, 62, 255) : new Color(108, 88, 56, 255), () => {
                if (worn) return;
                Outfits.set(o.id);
                this.refresh();
            });
    }

    // ---- 骨架 ----

    private build() {
        const layer = this.node.layer;

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
        panel.addComponent(UITransform).setContentSize(this.panelW, this.panelH);
        const pg = panel.addComponent(Graphics);
        pg.lineWidth = 4;
        pg.fillColor = new Color(42, 36, 32, 248);
        pg.strokeColor = new Color(220, 198, 160, 235);
        pg.rect(-this.panelW / 2, -this.panelH / 2, this.panelW, this.panelH);
        pg.fill(); pg.stroke();

        const topY = this.panelH / 2;
        this.makeLabel(panel, '衣櫃', 26, new Color(250, 238, 220, 255),
            -this.panelW / 2 + 26, topY - 36, 200, Label.HorizontalAlign.LEFT);
        this.makeButton(panel, '✕', 40, 40, this.panelW / 2 - 30, topY - 34,
            new Color(120, 60, 70, 255), () => this.close());
        this.makeLabel(panel, 'Esc 關閉 · 換上之後，場景裡的小人也會跟著換衣服', 15,
            new Color(184, 176, 166, 255),
            -this.panelW / 2 + 26, -this.panelH / 2 + 16, 620, Label.HorizontalAlign.LEFT);

        const list = new Node('List');
        list.layer = layer;
        panel.addChild(list);
        list.addComponent(UITransform);
        list.setPosition(-this.panelW / 2 + this.listW / 2 + 16, topY - 74, 0);
        this.listBox = list;

        const preview = new Node('Preview');
        preview.layer = layer;
        panel.addChild(preview);
        preview.addComponent(UITransform);
        preview.setPosition((this.listW + 16) / 2, 22, 0);
        this.previewBox = preview;
    }

    // ---- 小工具（比照 ShopManagePanel）----

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
        g.lineWidth = 2; g.fillColor = fill; g.strokeColor = new Color(228, 216, 198, 190);
        g.rect(-w / 2, -h / 2, w, h); g.fill(); g.stroke();
        const tn = new Node('t');
        tn.layer = layer; n.addChild(tn);
        tn.addComponent(UITransform).setContentSize(w, h);
        const lb = tn.addComponent(Label);
        lb.string = text; lb.fontSize = Math.min(22, h - 16);
        lb.color = new Color(244, 240, 232, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        const op = n.addComponent(UIOpacity);
        n.on(Node.EventType.TOUCH_START, () => { op.opacity = 170; });
        n.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; onClick(); });
        n.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
    }
}
