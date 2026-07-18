import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, Sprite, SpriteFrame, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, view } from 'cc';
import { UIState } from './UIState';
import { GameArt } from './GameArt';
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
 * 一句一句往下讀。用 GameArt 的木框美術當底、左側放說話者頭像；美術還沒載入
 * 時 fallback 畫一個米色框，不會開天窗。仿 ShopPanel 的 ensure() 自動生 UI。
 *
 * 推進用「空白鍵 / Enter / 點對話框」，關閉/跳過用 Esc——刻意不吃 E，避免開啟
 * 的那次 E 在同一幀又被當成推進（同 ShopPanel 的考量）。
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
    private portraitName = '';

    private root: Node | null = null;       // 整個對話框（含背板），關閉時隱藏
    private bgFallback: Node | null = null;  // 美術沒載入時的米色框
    private bgArt: Sprite | null = null;     // 木框美術
    private portrait: Sprite | null = null;
    private portraitBox = 0;                 // 頭像可用的方形邊長
    private nameLabel: Label | null = null;
    private textLabel: Label | null = null;

    // 對話框外框美術原圖 584x234；用同比例放大，米色內裡的內縮比例也是量出來的。
    private readonly boxW = 880;
    private readonly boxH = Math.round(880 * 234 / 584);   // ≈ 353
    private readonly insetL = 0.070;
    private readonly insetR = 0.067;
    private readonly insetT = 0.175;
    private readonly insetB = 0.137;
    private readonly bottomGap = 28;

    onLoad() {
        Dialogue.instance = this;
        GameArt.preload();
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (Dialogue.instance === this) Dialogue.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    /** 開始一段對話。name＝NPC 名；portraitName＝GameArt 頭像名（可省）。 */
    open(name: string, lines: DialogueInput[], portraitName = '') {
        this.defaultName = name;
        this.portraitName = portraitName;
        this.lines = (lines.length ? lines : ['……']).map(
            l => typeof l === 'string' ? { text: l } : l);
        this.idx = 0;
        if (!this.root) this.build();
        this.root!.active = true;
        UIState.modalOpen = true;
        // 美術可能還在載——載好再補上外框/頭像
        if (!GameArt.ready) GameArt.onReady(() => this.applyArt());
        this.applyArt();
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

    /** 外框美術與頭像載好後套上（沒載到就維持 fallback / 隱藏頭像）。 */
    private applyArt() {
        const boxFrame = GameArt.dialogueBox();
        if (boxFrame && this.bgArt) {
            this.bgArt.spriteFrame = boxFrame;
            this.bgArt.node.active = true;
            if (this.bgFallback) this.bgFallback.active = false;
        }
        // 頭像
        if (this.portrait) {
            const pf = this.portraitName ? GameArt.portrait(this.portraitName) : null;
            if (pf) {
                this.fit(this.portrait, pf, this.portraitBox, this.portraitBox);
                this.portrait.node.active = true;
            } else {
                this.portrait.node.active = false;
            }
        }
    }

    // ---- 建對話框骨架（只建一次，之後重複開關）----

    private build() {
        const layer = this.node.layer;

        // 透明背板：固定大尺寸並置中（同 ShopPanel，父節點 DialogueUI 沒有 UITransform，
        // 不能用「四邊撐滿」——會塌掉。置中對齊是靠 Canvas 算的，穩）。擋世界點擊、點它推進。
        const root = new Node('Root');
        root.layer = layer;
        this.node.addChild(root);
        root.addComponent(UITransform).setContentSize(4000, 3000);
        root.addComponent(BlockInputEvents);
        const rw = root.addComponent(Widget);
        rw.isAlignHorizontalCenter = rw.isAlignVerticalCenter = true;
        rw.horizontalCenter = rw.verticalCenter = 0;
        rw.updateAlignment();
        root.on(Node.EventType.TOUCH_END, this.advance, this);
        this.root = root;

        // 對話框容器：root 置中＝畫面中心，用可見畫面高度把它手動擺到底部中央。
        const vis = view.getVisibleSize();
        const box = new Node('Box');
        box.layer = layer;
        root.addChild(box);
        box.addComponent(UITransform).setContentSize(this.boxW, this.boxH);
        box.setPosition(0, -vis.height / 2 + this.boxH / 2 + this.bottomGap, 0);

        // 背景：fallback 米色框（美術沒載到時才顯示）
        const fb = new Node('Fallback');
        fb.layer = layer;
        box.addChild(fb);
        fb.addComponent(UITransform).setContentSize(this.boxW, this.boxH);
        const g = fb.addComponent(Graphics);
        g.lineWidth = 5;
        g.fillColor = new Color(236, 226, 202, 255);
        g.strokeColor = new Color(120, 84, 58, 255);
        this.roundRect(g, -this.boxW / 2, -this.boxH / 2, this.boxW, this.boxH, 22);
        g.fill(); g.stroke();
        this.bgFallback = fb;

        // 背景：木框美術（applyArt 時填入 spriteFrame）
        const art = new Node('Art');
        art.layer = layer;
        box.addChild(art);
        art.addComponent(UITransform).setContentSize(this.boxW, this.boxH);
        const artSp = art.addComponent(Sprite);
        artSp.sizeMode = Sprite.SizeMode.CUSTOM;
        artSp.trim = false;
        art.active = false;
        this.bgArt = artSp;

        // 米色內裡的矩形範圍（box 本地座標，box 中心為原點）
        const left = -this.boxW / 2 + this.insetL * this.boxW;
        const right = this.boxW / 2 - this.insetR * this.boxW;
        const top = this.boxH / 2 - this.insetT * this.boxH;
        const bottom = -this.boxH / 2 + this.insetB * this.boxH;
        const interiorH = top - bottom;
        const midY = (top + bottom) / 2;

        // 頭像（內裡左側的方形）
        this.portraitBox = interiorH - 6;
        const pNode = new Node('Portrait');
        pNode.layer = layer;
        box.addChild(pNode);
        pNode.addComponent(UITransform).setContentSize(this.portraitBox, this.portraitBox);
        pNode.setPosition(left + this.portraitBox / 2 + 4, midY, 0);
        this.portrait = pNode.addComponent(Sprite);
        this.portrait.sizeMode = Sprite.SizeMode.CUSTOM;
        this.portrait.trim = false;
        pNode.active = false;

        // 文字區（頭像右側）
        const textLeft = left + this.portraitBox + 26;
        const textW = right - textLeft;

        // 說話者名字（文字區頂端）
        this.nameLabel = this.makeLabel(box, '', 27, new Color(96, 56, 40, 255),
            textLeft, top - 22, textW, Label.HorizontalAlign.LEFT);
        // 台詞（名字正下方往下排、可換行）——錨點改成左上，長台詞才不會往下撞到提示
        this.textLabel = this.makeLabel(box, '', 25, new Color(58, 44, 38, 255),
            textLeft, top - 62, textW, Label.HorizontalAlign.LEFT);
        this.textLabel.verticalAlign = Label.VerticalAlign.TOP;
        this.textLabel.overflow = Label.Overflow.RESIZE_HEIGHT;
        this.textLabel.enableWrapText = true;
        const tut = this.textLabel.getComponent(UITransform)!;
        tut.setAnchorPoint(0, 1);
        tut.setContentSize(textW, interiorH - 76);

        // 底部提示
        this.makeLabel(box, '空白鍵 / 點擊 繼續 · Esc 跳過', 15,
            new Color(120, 100, 84, 255),
            textLeft, bottom + 12, textW, Label.HorizontalAlign.RIGHT);
    }

    /** 把 sprite 依原圖比例塞進 maxW×maxH（不變形）。 */
    private fit(sp: Sprite, frame: SpriteFrame, maxW: number, maxH: number) {
        const rw = frame.rect.width || frame.originalSize.width;
        const rh = frame.rect.height || frame.originalSize.height;
        const s = Math.min(maxW / rw, maxH / rh);
        sp.spriteFrame = frame;
        sp.getComponent(UITransform)!.setContentSize(rw * s, rh * s);
    }

    // ---- 小工具（比照 ShopPanel）----

    private makeLabel(parent: Node, text: string, size: number, color: Color,
                      leftX: number, y: number, width: number, align: number): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, size + 8);
        ut.setAnchorPoint(align === Label.HorizontalAlign.RIGHT ? 1 : 0, 0.5);
        n.setPosition(align === Label.HorizontalAlign.RIGHT ? leftX + width : leftX, y, 0);
        const lb = n.addComponent(Label);
        lb.string = text;
        lb.fontSize = size;
        lb.lineHeight = size + 6;
        lb.color = color;
        lb.horizontalAlign = align;
        lb.verticalAlign = Label.VerticalAlign.TOP;
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
