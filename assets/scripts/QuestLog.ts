import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, BlockInputEvents, UIOpacity, find, input, Input,
         EventKeyboard, KeyCode, view } from 'cc';
import { UIState } from './UIState';
import { Quests } from './Quests';
const { ccclass } = _decorator;

/**
 * 任務簿（modal）：任何場景按 Q 開，列出「已接」的任務（進行中＋可回報）與進度。
 * 仿 ShopPanel 的 ensure() 自動生 UI，場景不用預先擺。
 *
 * 開啟由 PlayerController 的 Q 鍵負責（且只有沒開著其他視窗時才開）；關閉只吃
 * Esc 或右上角 ✕——不吃 Q，避免開啟那一下的 Q 又被當成關閉（同 ShopPanel 用 Esc
 * 的考量）。資料全來自 Quests module，換場景／重開都在。
 */
@ccclass('QuestLog')
export class QuestLog extends Component {
    static instance: QuestLog | null = null;

    /** 取得任務簿；沒有的話自動在 Canvas 底下建一個（找不到 Canvas 回 null）。 */
    static ensure(): QuestLog | null {
        if (QuestLog.instance) return QuestLog.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[QuestLog] 找不到 Canvas，無法建立任務簿'); return null; }
        const node = new Node('QuestLogUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(QuestLog);
    }

    private root: Node | null = null;      // 背板（含背景），關閉時隱藏
    private panel: Node | null = null;      // 面板本體（每次 open 依任務數重建）

    private readonly panelW = 660;
    private readonly headerH = 84;
    private readonly rowH = 84;
    private readonly footerH = 40;
    private readonly rightMargin = 30;   // 面板離畫面右緣的距離（靠右彈出）

    onLoad() {
        QuestLog.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (QuestLog.instance === this) QuestLog.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    private onKeyDown(e: EventKeyboard) {
        if (this.root?.active && e.keyCode === KeyCode.ESCAPE) this.close();
    }

    open() {
        if (!this.root) this.buildRoot();
        this.rebuild();               // 依目前任務重建面板
        this.root!.active = true;
        UIState.modalOpen = true;
    }

    close() {
        if (this.root) this.root.active = false;
        UIState.modalOpen = false;
    }

    isOpen(): boolean { return !!this.root?.active; }

    // ---- 背板（只建一次）----

    private buildRoot() {
        const layer = this.node.layer;
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
    }

    // ---- 面板本體（每次 open 重建，反映最新進度）----

    private rebuild() {
        if (this.panel) { this.panel.destroy(); this.panel = null; }
        const layer = this.node.layer;
        const ids = Quests.acceptedIds();
        const rows = Math.max(1, ids.length);
        const panelH = this.headerH + rows * this.rowH + this.footerH;

        const panel = new Node('Panel');
        panel.layer = layer;
        this.root!.addChild(panel);
        panel.addComponent(UITransform).setContentSize(this.panelW, panelH);
        // root 置中＝畫面中心；用可見畫面寬把面板推到右側（垂直仍置中）
        const vis = view.getVisibleSize();
        panel.setPosition(vis.width / 2 - this.panelW / 2 - this.rightMargin, 0, 0);
        const pg = panel.addComponent(Graphics);
        pg.lineWidth = 4;
        pg.fillColor = new Color(38, 30, 52, 245);
        pg.strokeColor = new Color(210, 190, 230, 235);
        this.roundRect(pg, -this.panelW / 2, -panelH / 2, this.panelW, panelH, 18);
        pg.fill(); pg.stroke();
        this.panel = panel;

        const topY = panelH / 2;

        // 標題
        this.makeLabel(panel, '任務簿', 28, new Color(245, 235, 255, 255),
            -this.panelW / 2 + 28, topY - 36, this.panelW - 140, Label.HorizontalAlign.LEFT);
        // 關閉 ✕
        this.makeButton(panel, '✕', 40, 40, this.panelW / 2 - 34, topY - 34,
            new Color(120, 60, 70, 255), () => this.close());
        // 底部提示
        this.makeCenterLabel(panel, 'Q / Esc 關閉', 16, new Color(180, 174, 190, 255),
            0, -panelH / 2 + 18);

        if (ids.length === 0) {
            this.makeCenterLabel(panel, '目前沒有進行中的任務。\n去城鎮找頭頂有「！」的 NPC 聊聊吧！',
                22, new Color(210, 205, 220, 255), 0, topY - this.headerH - this.rowH / 2);
            return;
        }

        ids.forEach((id, i) => {
            const y = topY - this.headerH - i * this.rowH - this.rowH / 2;
            this.buildRow(panel, id, y);
        });
    }

    private buildRow(parent: Node, id: string, y: number) {
        const d = Quests.def(id);
        if (!d) return;
        const layer = this.node.layer;
        const leftX = -this.panelW / 2 + 30;
        const ready = Quests.statusOf(id) === 'ready';

        const row = new Node('row-' + id);
        row.layer = layer;
        parent.addChild(row);
        row.addComponent(UITransform);
        row.setPosition(0, y, 0);

        // 分隔線
        const line = row.addComponent(Graphics);
        line.strokeColor = new Color(255, 255, 255, 28);
        line.lineWidth = 1;
        line.moveTo(leftX, this.rowH / 2 - 2);
        line.lineTo(this.panelW / 2 - 30, this.rowH / 2 - 2);
        line.stroke();

        // 任務名（上排左）
        this.makeLabel(row, d.title, 23, new Color(245, 240, 250, 255),
            leftX, 20, 320, Label.HorizontalAlign.LEFT);
        // 狀態標籤（上排右）
        this.makeRightLabel(row, ready ? `可回報 · 找${d.giver}` : '進行中', 18,
            ready ? new Color(140, 240, 150, 255) : new Color(170, 165, 185, 255),
            this.panelW / 2 - 30, 20, 320);

        // 目標 + 進度（下排左）
        this.makeLabel(row, `${Quests.objectiveText(d)}   ${Quests.progressText(id)}`, 19,
            new Color(210, 220, 235, 255), leftX, -14, 360, Label.HorizontalAlign.LEFT);
        // 獎勵（下排右）
        this.makeRightLabel(row, `獎勵 ${Quests.rewardText(d)}`, 18,
            new Color(255, 224, 130, 255), this.panelW / 2 - 30, -14, 300);
    }

    // ---- 小工具（比照 ShopPanel）----

    private makeLabel(parent: Node, text: string, size: number, color: Color,
                      leftX: number, y: number, width: number, align: number): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, size + 8);
        ut.setAnchorPoint(0, 0.5);
        n.setPosition(leftX, y, 0);
        const lb = n.addComponent(Label);
        lb.string = text; lb.fontSize = size; lb.lineHeight = size + 4; lb.color = color;
        lb.horizontalAlign = align; lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;
        return lb;
    }

    private makeRightLabel(parent: Node, text: string, size: number, color: Color,
                           rightX: number, y: number, width: number): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, size + 8);
        ut.setAnchorPoint(1, 0.5);
        n.setPosition(rightX, y, 0);
        const lb = n.addComponent(Label);
        lb.string = text; lb.fontSize = size; lb.lineHeight = size + 4; lb.color = color;
        lb.horizontalAlign = Label.HorizontalAlign.RIGHT; lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;
        return lb;
    }

    private makeCenterLabel(parent: Node, text: string, size: number, color: Color,
                            x: number, y: number): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(this.panelW - 80, (size + 8) * 2);
        ut.setAnchorPoint(0.5, 0.5);
        n.setPosition(x, y, 0);
        const lb = n.addComponent(Label);
        lb.string = text; lb.fontSize = size; lb.lineHeight = size + 6; lb.color = color;
        lb.horizontalAlign = Label.HorizontalAlign.CENTER; lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK; lb.enableWrapText = true;
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
        lb.string = text; lb.fontSize = Math.min(24, h - 16);
        lb.color = new Color(245, 245, 250, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER; lb.verticalAlign = Label.VerticalAlign.CENTER;
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
