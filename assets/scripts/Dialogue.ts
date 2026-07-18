import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity } from 'cc';
import { UIState } from './UIState';
const { ccclass } = _decorator;

/**
 * 一句對話。`speaker` 省略時沿用 NPC 名。
 *
 * `choices` 目前先預留、還沒實作——之後要做「分支/選項對話」時，讓某一句帶
 * 選項（例如 問好／問商品／離開），選了就跳到對應的後續。屆時只要在 advance()
 * 裡處理 choices，其餘 UI/流程都不用動。
 */
export interface DialogueLine {
    speaker?: string;
    text: string;
    // choices?: DialogueChoice[];   // 之後做分支對話時啟用
}

/** open() 可以吃純字串（＝一句台詞）或完整的 DialogueLine。 */
export type DialogueInput = string | DialogueLine;

/**
 * NPC 對話框（modal）：全域唯一，走近 NPC 按 E 開，畫面下方跳出對話框，
 * 一句一句往下讀。仿 ShopPanel 的 ensure() 自動生 UI，場景不用預先擺。
 *
 * 推進用「空白鍵 / Enter / 點對話框」，關閉/跳過用 Esc——
 * 刻意不吃 E，避免開啟的那一次 E 在同一幀又被當成推進（同 ShopPanel 的考量）。
 */
@ccclass('Dialogue')
export class Dialogue extends Component {
    static instance: Dialogue | null = null;

    /** 取得對話框；沒有的話自動在 Canvas 底下建一個（找不到 Canvas 回 null）。 */
    static ensure(): Dialogue | null {
        if (Dialogue.instance) return Dialogue.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[Dialogue] 找不到 Canvas，無法建立對話框'); return null; }
        const node = new Node('DialogueUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(Dialogue);
    }

    private lines: DialogueLine[] = [];
    private idx = 0;
    private defaultName = '';

    private root: Node | null = null;       // 整個對話框（含背板），關閉時隱藏
    private nameLabel: Label | null = null;
    private textLabel: Label | null = null;

    private readonly boxW = 860;
    private readonly boxH = 190;
    private readonly bottomGap = 40;        // 對話框離畫面底部的距離

    onLoad() {
        Dialogue.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (Dialogue.instance === this) Dialogue.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    /** 開始一段對話。name＝NPC 名（每句沒指定 speaker 時用它）。 */
    open(name: string, lines: DialogueInput[]) {
        this.defaultName = name;
        this.lines = (lines.length ? lines : ['……']).map(
            l => typeof l === 'string' ? { text: l } : l);
        this.idx = 0;
        if (!this.root) this.build();
        this.root!.active = true;
        UIState.modalOpen = true;
        this.show();
    }

    close() {
        if (this.root) this.root.active = false;
        UIState.modalOpen = false;
    }

    isOpen(): boolean { return !!this.root?.active; }

    private onKeyDown(e: EventKeyboard) {
        if (!this.root?.active) return;
        switch (e.keyCode) {
            case KeyCode.SPACE:
            case KeyCode.ENTER:
            case KeyCode.NUM_ENTER:
                this.advance();
                break;
            case KeyCode.ESCAPE:
                this.close();   // 跳過整段
                break;
        }
    }

    private advance() {
        this.idx++;
        if (this.idx >= this.lines.length) this.close();
        else this.show();
    }

    /** 顯示目前這一句。 */
    private show() {
        const line = this.lines[this.idx];
        if (this.nameLabel) this.nameLabel.string = line.speaker || this.defaultName;
        if (this.textLabel) this.textLabel.string = line.text;
    }

    // ---- 建對話框骨架（只建一次，之後重複開關）----

    private build() {
        const layer = this.node.layer;

        // 透明背板：擋住後面世界的點擊，點它就推進到下一句
        const root = new Node('Root');
        root.layer = layer;
        this.node.addChild(root);
        root.addComponent(UITransform).setContentSize(3000, 2000);
        root.addComponent(BlockInputEvents);
        const rw = root.addComponent(Widget);
        rw.isAlignHorizontalCenter = rw.isAlignVerticalCenter = true;
        rw.horizontalCenter = rw.verticalCenter = 0;
        rw.updateAlignment();
        root.on(Node.EventType.TOUCH_END, this.advance, this);
        this.root = root;

        // 對話框本體，靠畫面底部置中
        const box = new Node('Box');
        box.layer = layer;
        root.addChild(box);
        box.addComponent(UITransform).setContentSize(this.boxW, this.boxH);
        const bw = box.addComponent(Widget);
        bw.isAlignHorizontalCenter = true; bw.horizontalCenter = 0;
        bw.isAlignBottom = true; bw.bottom = this.bottomGap;
        bw.updateAlignment();

        const bg = box.addComponent(Graphics);
        bg.lineWidth = 4;
        bg.fillColor = new Color(38, 30, 52, 245);
        bg.strokeColor = new Color(210, 190, 230, 235);
        this.roundRect(bg, -this.boxW / 2, -this.boxH / 2, this.boxW, this.boxH, 18);
        bg.fill(); bg.stroke();

        const topY = this.boxH / 2;
        const leftX = -this.boxW / 2 + 32;

        // 說話者名牌（左上角一個小圓角標籤）
        const tabW = 200, tabH = 44;
        const tab = new Node('NameTab');
        tab.layer = layer;
        box.addChild(tab);
        tab.addComponent(UITransform).setContentSize(tabW, tabH);
        tab.setPosition(leftX + tabW / 2 - 4, topY - 2, 0);
        const tg = tab.addComponent(Graphics);
        tg.lineWidth = 3;
        tg.fillColor = new Color(96, 72, 128, 255);
        tg.strokeColor = new Color(210, 190, 230, 235);
        this.roundRect(tg, -tabW / 2, -tabH / 2, tabW, tabH, 12);
        tg.fill(); tg.stroke();
        this.nameLabel = this.makeLabel(tab, '', 24, new Color(250, 244, 255, 255),
            0, 0, tabW - 20, Label.HorizontalAlign.CENTER, 0);

        // 台詞（名牌下方，靠左，自動縮排）
        this.textLabel = this.makeLabel(box, '', 26, new Color(240, 238, 246, 255),
            0, 6, this.boxW - 64, Label.HorizontalAlign.LEFT, leftX);
        this.textLabel.verticalAlign = Label.VerticalAlign.CENTER;
        this.textLabel.overflow = Label.Overflow.RESIZE_HEIGHT;
        this.textLabel.enableWrapText = true;

        // 底部提示
        this.makeLabel(box, '空白鍵 / 點擊 繼續 · Esc 跳過', 16,
            new Color(180, 174, 190, 255),
            0, -this.boxH / 2 + 20, 400, Label.HorizontalAlign.RIGHT,
            this.boxW / 2 - 232);
    }

    // ---- 小工具（比照 ShopPanel）----

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
        lb.lineHeight = size + 6;
        lb.color = color;
        lb.horizontalAlign = align;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;
        return lb;
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
