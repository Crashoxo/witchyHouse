import { _decorator, Component, Node, UITransform, Sprite, SpriteFrame, ImageAsset,
         Label, Color, Graphics, BlockInputEvents, UIOpacity, find, resources,
         input, Input, EventKeyboard, KeyCode, view, tween, Vec3 } from 'cc';
import { UIState } from './UIState';
import { GameArt } from './GameArt';
const { ccclass } = _decorator;

/**
 * 更新公告板：開遊戲時從畫面上方滑下來停在正中央，列出這次更新了什麼。
 * 底圖是 `resources/ui/update-frame`（木框＋UPDATE 招牌＋畫好的 OK 鈕），
 * 所以 OK 只要在畫上去的按鈕位置疊一個透明的可點區即可。
 *
 * 一次載入只跳一次（module 層 `shown`）——換場景不會再跳出來煩人。
 * 要改公告內容就改下面的 UPDATE_DATE / UPDATE_LINES。
 */

/** 這次更新的日期（顯示在公告最上方）。 */
const UPDATE_DATE = '2026 / 07 / 21';

/** 這次更新的內容，一行一條。 */
const UPDATE_LINES = [
    '· 城鎮大改建！地圖放大，鋪上石板街道與磚砌廣場',
    '· 廣場中央立起噴泉，西邊的路口多了一座城門',
    '· 東側多了一條溪流，三座橋通往對岸的草原',
    '· 路燈、柵欄、花圃點綴街道，走到景物後方會被擋住',
    '· 新增滑鼠移動：點一下地面就會走過去',
];

/** 底圖比例（切好的 update-frame.png 是 1031×647）。 */
const ART_ASPECT = 1031 / 647;
/** 底圖上「米色內裡」與「OK 鈕」的相對位置（量出來的）。 */
const INNER = { l: 0.099, r: 0.901, t: 0.284, b: 0.839 };
const OK_BTN = { l: 0.389, r: 0.610, t: 0.861, b: 0.972 };

let shown = false;   // 這次載入跳過了沒

@ccclass('UpdatePanel')
export class UpdatePanel extends Component {
    static instance: UpdatePanel | null = null;

    /** 每次載入只跳一次（換場景不重跳）。 */
    static showOnce(): void {
        if (shown) return;
        shown = true;
        const canvas = find('Canvas');
        if (!canvas) return;
        const node = new Node('UpdateUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        node.addComponent(UpdatePanel);
    }

    private root: Node | null = null;
    private panel: Node | null = null;
    private loading: Node | null = null;
    private hiddenY = 0;
    private closing = false;

    onLoad() {
        UpdatePanel.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        GameArt.preload();
        this.build();
        this.loadFrameArt();
    }

    /**
     * 先把底圖單獨載進來。
     * 不能等 `GameArt.onReady` —— 那要等上百張圖（商品、顧客、頭像、裝飾……）
     * 全部載完才會觸發，公告板會空等好幾秒。這裡直接 load 這一張，通常一眨眼就到。
     */
    private loadFrameArt() {
        const ready = GameArt.updateFrame();
        if (ready) { this.applyFrame(ready); return; }
        // 回呼可能在面板關掉之後才回來 —— 元件被銷毀後 this.node 會是 null，
        // 所以先確認還活著再動 UI。
        const alive = () => !!this.node && this.node.isValid;
        resources.load('ui/update-frame', ImageAsset, (err, img) => {
            if (!err && img && alive()) this.applyFrame(SpriteFrame.createWithImage(img));
        });
        GameArt.onReady(() => {                   // 保險：萬一上面那次失敗，整批載完再補
            const f = GameArt.updateFrame();
            if (f && alive()) this.applyFrame(f);
        });
    }

    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (UpdatePanel.instance === this) UpdatePanel.instance = null;
        UIState.modalOpen = false;
    }

    // ---- 建立 UI ----

    private build() {
        UIState.modalOpen = true;
        const layer = this.node.layer;
        const vis = view.getVisibleSize();

        // 半透明背板（擋住世界的點擊）。固定大尺寸置中，不用巢狀 Widget 撐滿。
        const root = new Node('root');
        root.layer = layer;
        this.node.addChild(root);
        root.addComponent(UITransform).setContentSize(4000, 3000);
        root.addComponent(BlockInputEvents);
        const dim = root.addComponent(Graphics);
        dim.fillColor = new Color(20, 14, 26, 170);
        dim.rect(-2000, -1500, 4000, 3000);
        dim.fill();
        this.root = root;

        // 面板本體（等比縮放的底圖）
        const w = Math.min(vis.width * 0.88, 760);
        const h = w / ART_ASPECT;
        const panel = new Node('panel');
        panel.layer = layer;
        root.addChild(panel);
        panel.addComponent(UITransform).setContentSize(w, h);
        const sp = panel.addComponent(Sprite);
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.type = Sprite.Type.SIMPLE;
        this.panel = panel;

        // 內裡文字區（依底圖比例換算成面板本地座標）
        const innerX = (-0.5 + INNER.l) * w;
        const innerW = (INNER.r - INNER.l) * w;
        const innerTop = (0.5 - INNER.t) * h;
        const innerH = (INNER.b - INNER.t) * h;
        const pad = w * 0.03;

        // 日期（內裡最上方，置中）
        const dateNode = new Node('date');
        dateNode.layer = layer;
        panel.addChild(dateNode);
        dateNode.addComponent(UITransform).setContentSize(innerW, h * 0.09);
        dateNode.setPosition(innerX + innerW / 2, innerTop - h * 0.05, 0);
        const dl = dateNode.addComponent(Label);
        dl.string = UPDATE_DATE;
        dl.fontSize = Math.round(h * 0.062);
        dl.color = new Color(126, 76, 44, 255);
        dl.horizontalAlign = Label.HorizontalAlign.CENTER;
        dl.verticalAlign = Label.VerticalAlign.CENTER;

        // 更新內容（左上往下排，行距寬一點好讀）
        const bodyNode = new Node('body');
        bodyNode.layer = layer;
        panel.addChild(bodyNode);
        const bodyH = innerH - h * 0.16;
        const but = bodyNode.addComponent(UITransform);
        but.setContentSize(innerW - pad * 2, bodyH);
        but.setAnchorPoint(0, 1);
        bodyNode.setPosition(innerX + pad, innerTop - h * 0.12, 0);
        const bl = bodyNode.addComponent(Label);
        bl.string = UPDATE_LINES.join('\n');
        // 行高依行數自動收斂，條目多的時候才不會壓到底下的裝飾線與 OK 鈕
        const lineH = Math.min(h * 0.088, bodyH / Math.max(1, UPDATE_LINES.length));
        bl.fontSize = Math.round(Math.min(h * 0.052, lineH * 0.62));
        bl.lineHeight = Math.round(lineH);
        bl.color = new Color(74, 50, 38, 255);
        bl.horizontalAlign = Label.HorizontalAlign.LEFT;
        bl.verticalAlign = Label.VerticalAlign.TOP;
        bl.overflow = Label.Overflow.SHRINK;

        // OK：底圖已經畫好按鈕，這裡只疊一個透明可點區
        const ok = new Node('ok');
        ok.layer = layer;
        panel.addChild(ok);
        const okW = (OK_BTN.r - OK_BTN.l) * w;
        const okH = (OK_BTN.b - OK_BTN.t) * h;
        ok.addComponent(UITransform).setContentSize(okW, okH);
        ok.setPosition((-0.5 + (OK_BTN.l + OK_BTN.r) / 2) * w,
                       (0.5 - (OK_BTN.t + OK_BTN.b) / 2) * h, 0);
        const okOp = panel.addComponent(UIOpacity);   // 按下去時整個面板微暗＝按鈕回饋
        ok.on(Node.EventType.TOUCH_START, () => { okOp.opacity = 205; });
        ok.on(Node.EventType.TOUCH_CANCEL, () => { okOp.opacity = 255; });
        ok.on(Node.EventType.TOUCH_END, () => { okOp.opacity = 255; this.close(); });

        // 從畫面上方滑進來，停在正中央
        this.hiddenY = vis.height / 2 + h / 2 + 40;
        panel.setPosition(0, this.hiddenY, 0);
        const op = root.addComponent(UIOpacity);
        op.opacity = 0;
        tween(op).to(0.25, { opacity: 255 }).start();
        tween(panel)
            .to(0.55, { position: new Vec3(0, 0, 0) }, { easing: 'backOut' })
            .start();

        this.drawPlaceholder();
        this.buildLoading(h);
    }

    /** 底圖還沒到之前先畫個素框，不開天窗。 */
    private drawPlaceholder() {
        const ut = this.panel!.getComponent(UITransform)!;
        const g = this.panel!.getComponent(Graphics) ?? this.panel!.addComponent(Graphics);
        g.clear();
        g.lineWidth = 6;
        g.fillColor = new Color(238, 225, 196, 255);
        g.strokeColor = new Color(120, 74, 42, 255);
        g.rect(-ut.width / 2, -ut.height / 2, ut.width, ut.height);
        g.fill(); g.stroke();
    }

    /** 「載入中…」字樣，蓋在素框上，底圖到了就收掉。 */
    private buildLoading(h: number) {
        const n = new Node('loading');
        n.layer = this.node.layer;
        this.panel!.addChild(n);
        n.addComponent(UITransform).setContentSize(this.panel!.getComponent(UITransform)!.width, h * 0.12);
        const l = n.addComponent(Label);
        l.string = '載入中…';
        l.fontSize = Math.round(h * 0.055);
        l.color = new Color(150, 108, 76, 255);
        l.horizontalAlign = Label.HorizontalAlign.CENTER;
        l.verticalAlign = Label.VerticalAlign.CENTER;
        this.loading = n;
    }

    /** 底圖到了：貼上、清掉素框與「載入中…」。 */
    private applyFrame(f: SpriteFrame) {
        const sp = this.panel?.getComponent(Sprite);
        if (!sp || sp.spriteFrame) return;
        sp.spriteFrame = f;
        this.panel!.getComponent(Graphics)?.clear();   // 素框收掉，不然會從木框的透明處透出來
        if (this.loading?.isValid) this.loading.destroy();
        this.loading = null;
    }

    // ---- 關閉 ----

    private onKeyDown(e: EventKeyboard) {
        if (e.keyCode === KeyCode.ESCAPE || e.keyCode === KeyCode.ENTER ||
            e.keyCode === KeyCode.SPACE || e.keyCode === KeyCode.KEY_E) this.close();
    }

    /** 往上滑回去然後銷毀。 */
    private close() {
        if (this.closing || !this.panel) return;
        this.closing = true;
        UIState.modalOpen = false;
        const op = this.root?.getComponent(UIOpacity);
        if (op) tween(op).delay(0.1).to(0.25, { opacity: 0 }).start();
        tween(this.panel)
            .to(0.35, { position: new Vec3(0, this.hiddenY, 0) }, { easing: 'backIn' })
            .call(() => this.node.destroy())
            .start();
    }
}
