import { _decorator, Component, Node, UITransform, Widget, Label, Color, Sprite,
         Graphics, BlockInputEvents, UIOpacity, find, input, Input,
         EventKeyboard, KeyCode, view } from 'cc';
import { UIState } from './UIState';
import { Quests } from './Quests';
import { GameArt } from './GameArt';
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
    private panel: Node | null = null;      // 捲軸面板本體（每次 open 依任務數重建）
    private page = 0;                        // 目前頁（任務多於一頁時分頁）
    private readonly perPage = 3;            // 每頁顯示幾個任務

    // 捲軸底板是細長直式（原圖 141×325）；面板等比擺到畫面右側。
    private readonly scrollAspect = 141 / 325;   // 寬 / 高
    private readonly rightMargin = 24;           // 離畫面右緣的距離
    // 羊皮紙可寫字的內裡內縮比例（避開捲邊與藤蔓花邊；目視估）
    private readonly insetL = 0.13;
    private readonly insetR = 0.13;
    private readonly insetT = 0.15;
    private readonly insetB = 0.14;

    onLoad() {
        QuestLog.instance = this;
        GameArt.preload();
        // 捲軸美術載好後，若正開著就重畫換上底板
        GameArt.onReady(() => { if (this.isOpen()) this.rebuild(); });
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
        this.page = 0;                // 每次打開回第一頁
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

    // ---- 捲軸面板（每次 open 重建，反映最新進度）----

    private rebuild() {
        if (this.panel) { this.panel.destroy(); this.panel = null; }
        const layer = this.node.layer;
        const ids = Quests.acceptedIds();

        // 面板等比：高度盡量吃滿畫面（留邊），寬度依捲軸比例
        const vis = view.getVisibleSize();
        const panelH = Math.min(vis.height - 24, 600);
        const panelW = panelH * this.scrollAspect;

        const panel = new Node('Panel');
        panel.layer = layer;
        this.root!.addChild(panel);
        panel.addComponent(UITransform).setContentSize(panelW, panelH);
        // root 置中＝畫面中心；用可見畫面寬把捲軸推到右側（垂直置中）
        panel.setPosition(vis.width / 2 - panelW / 2 - this.rightMargin, 0, 0);
        this.panel = panel;

        // 底板：有捲軸美術就用，否則畫一張米色羊皮紙 fallback
        const frame = GameArt.questScroll();
        if (frame) {
            const sp = panel.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM;
            sp.type = Sprite.Type.SIMPLE;
            sp.trim = false;
            sp.spriteFrame = frame;
        } else {
            const pg = panel.addComponent(Graphics);
            pg.lineWidth = 4;
            pg.fillColor = new Color(226, 210, 170, 250);
            pg.strokeColor = new Color(120, 90, 60, 235);
            this.roundRect(pg, -panelW / 2, -panelH / 2, panelW, panelH, 16);
            pg.fill(); pg.stroke();
        }

        // 羊皮紙可寫字的內裡矩形（panel 本地座標）
        const iL = -panelW / 2 + this.insetL * panelW;
        const iR = panelW / 2 - this.insetR * panelW;
        const iT = panelH / 2 - this.insetT * panelH;
        const iB = -panelH / 2 + this.insetB * panelH;
        const iW = iR - iL;

        // 深墨色系（寫在羊皮紙上，不能用原本淺色）
        const inkTitle = new Color(88, 52, 32, 255);
        const inkText = new Color(96, 70, 48, 255);
        const inkSub = new Color(130, 104, 74, 255);

        // 標題（內裡頂端置中）
        this.makeCenterLabel(panel, '任務簿', 26, inkTitle, (iL + iR) / 2, iT - 18, iW);
        // 關閉 ✕（內裡右上角）
        this.makeButton(panel, '✕', 30, 30, iR - 12, iT - 14,
            new Color(150, 80, 70, 255), () => this.close());
        // 標題底線
        const titleLineY = iT - 40;
        const div = panel.addComponent(Graphics);
        div.strokeColor = new Color(120, 90, 60, 130);
        div.lineWidth = 2;
        div.moveTo(iL + 4, titleLineY); div.lineTo(iR - 4, titleLineY); div.stroke();
        // 底部提示（內裡底端置中）
        this.makeCenterLabel(panel, 'Q / Esc 關閉', 14, inkSub, (iL + iR) / 2, iB + 12, iW);

        // 分頁：每頁 perPage 個任務；超過一頁時底部留出翻頁列的高度
        const totalPages = Math.max(1, Math.ceil(ids.length / this.perPage));
        this.page = Math.max(0, Math.min(this.page, totalPages - 1));
        const multi = totalPages > 1;
        const navH = multi ? 34 : 0;

        // 任務條目區：標題底線之下 ~（翻頁列＋底部提示）之上
        const areaTop = titleLineY - 8;
        const areaBottom = iB + 30 + navH;
        const areaH = areaTop - areaBottom;

        if (ids.length === 0) {
            this.makeCenterLabelWrap(panel, '目前沒有\n進行中的任務。\n\n去城鎮找頭頂\n有「！」的\nNPC 聊聊吧！',
                18, inkText, (iL + iR) / 2, (areaTop + areaBottom) / 2, iW, areaH);
            return;
        }

        // 固定用 perPage 算條目高度，讓每一頁的排版一致
        const entryH = Math.min(88, areaH / this.perPage);
        const pageIds = ids.slice(this.page * this.perPage, this.page * this.perPage + this.perPage);
        pageIds.forEach((id, i) => {
            const cy = areaTop - i * entryH - entryH / 2;
            this.buildEntry(panel, id, iL, iR, cy, entryH);
        });

        // 翻頁列（上一頁 ‹ 頁碼 › 下一頁）
        if (multi) {
            const navY = iB + 30 + navH / 2;
            if (this.page > 0)
                this.makeButton(panel, '<', 30, 26, iL + 18, navY,
                    new Color(120, 90, 60, 255), () => { this.page--; this.rebuild(); });
            this.makeCenterLabel(panel, `${this.page + 1} / ${totalPages}`, 15,
                new Color(96, 70, 48, 255), (iL + iR) / 2, navY, iW * 0.5);
            if (this.page < totalPages - 1)
                this.makeButton(panel, '>', 30, 26, iR - 18, navY,
                    new Color(120, 90, 60, 255), () => { this.page++; this.rebuild(); });
        }
    }

    /** 一個任務條目（3 行：名稱／目標+進度／狀態+獎勵），排在內裡寬度內。 */
    private buildEntry(parent: Node, id: string, iL: number, iR: number, cy: number, h: number) {
        const d = Quests.def(id);
        if (!d) return;
        const layer = this.node.layer;
        const w = iR - iL;
        const ready = Quests.statusOf(id) === 'ready';

        const row = new Node('entry-' + id);
        row.layer = layer;
        parent.addChild(row);
        row.addComponent(UITransform);
        row.setPosition(0, cy, 0);

        // 條目間細分隔線（第一條之外）
        const line = row.addComponent(Graphics);
        line.strokeColor = new Color(120, 90, 60, 90);
        line.lineWidth = 1;
        line.moveTo(iL + 2, h / 2); line.lineTo(iR - 2, h / 2); line.stroke();

        // 名稱（上）
        this.makeLabel(row, d.title, 19, new Color(80, 48, 30, 255),
            iL, h / 2 - 20, w, Label.HorizontalAlign.LEFT);
        // 目標 + 進度（中）
        this.makeLabel(row, `${Quests.objectiveText(d)}  ${Quests.progressText(id)}`, 15,
            new Color(104, 78, 54, 255), iL, h / 2 - 44, w, Label.HorizontalAlign.LEFT);
        // 狀態（下左）＋獎勵（下右）——用顏色區分（綠＝可回報、灰＝進行中）
        this.makeLabel(row, ready ? '可回報！' : '進行中', 14,
            ready ? new Color(60, 130, 70, 255) : new Color(140, 110, 80, 255),
            iL, h / 2 - 66, w * 0.5, Label.HorizontalAlign.LEFT);
        this.makeRightLabel(row, `賞 ${Quests.rewardText(d)}`, 14,
            new Color(150, 96, 40, 255), iR, h / 2 - 66, w * 0.62);
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
                            x: number, y: number, width: number): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, size + 8);
        ut.setAnchorPoint(0.5, 0.5);
        n.setPosition(x, y, 0);
        const lb = n.addComponent(Label);
        lb.string = text; lb.fontSize = size; lb.lineHeight = size + 6; lb.color = color;
        lb.horizontalAlign = Label.HorizontalAlign.CENTER; lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;
        return lb;
    }

    /** 多行置中（給空清單提示用），指定可用寬高。 */
    private makeCenterLabelWrap(parent: Node, text: string, size: number, color: Color,
                                x: number, y: number, width: number, height: number): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, height);
        ut.setAnchorPoint(0.5, 0.5);
        n.setPosition(x, y, 0);
        const lb = n.addComponent(Label);
        lb.string = text; lb.fontSize = size; lb.lineHeight = size + 8; lb.color = color;
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
