import { _decorator, Component, Node, UITransform, Widget, Sprite, SpriteFrame,
         Label, Color, Graphics, BlockInputEvents, UIOpacity, find, view, Vec3,
         EventTouch } from 'cc';
import { UIState } from './UIState';
import { GameArt } from './GameArt';
import { DecorCatalog, Placed } from './DecorCatalog';
const { ccclass } = _decorator;

interface Entry { node: Node; id: string; handlers?: Array<(e: EventTouch) => void>; }

/**
 * 店內裝飾佈置：掛在自己店（shop.scene）的 Props 上。
 *   - 進場：把 DecorCatalog 已擺的裝飾生成到 Props（吃 YSort 遮擋，錨點 (0.5,0)）。
 *   - 右下常駐「🌸 佈置」鈕 → 進佈置模式：底部托盤列出「買了但還沒擺」的裝飾，
 *     點一個先擺到房間中央，再用滑鼠拖到想要的位置；把裝飾拖到托盤區＝收回。
 *     「✓ 完成」存檔離開。佈置時 UIState.modalOpen＝true，角色/顧客不動。
 * 純裝飾、拖放自由擺放；座標存 Props 本地座標（跨進出店保留）。
 */
@ccclass('DecorRoom')
export class DecorRoom extends Component {
    private placedNodes: Entry[] = [];
    private spawned = false;
    private editing = false;

    private canvas: Node | null = null;
    private toggleBtn: Node | null = null;
    private toggleLabel: Label | null = null;
    private tray: Node | null = null;
    private hintNode: Node | null = null;
    private dragging: Node | null = null;

    private readonly trayH = 150;   // 底部托盤高度；拖到這區以下＝收回

    onLoad() {
        this.canvas = find('Canvas');
        GameArt.preload();
        GameArt.onReady(() => this.spawnPlaced());
        this.buildToggle();
    }

    // ---- 進場：生成已擺的裝飾 ----

    private spawnPlaced() {
        if (this.spawned) return;
        this.spawned = true;
        for (const p of DecorCatalog.placedList()) this.createDecorNode(p.id, p.x, p.y);
    }

    private createDecorNode(id: string, x: number, y: number): Entry {
        const n = new Node('decor-' + id);
        n.layer = this.node.layer;
        this.node.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setAnchorPoint(0.5, 0);
        const sp = n.addComponent(Sprite);
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.trim = false;
        const f = GameArt.decor(id);
        if (f) { sp.spriteFrame = f; ut.setContentSize(f.rect.width, f.rect.height); }
        else ut.setContentSize(64, 64);
        n.addComponent(UIOpacity);   // 拖曳時調透明度用
        n.setPosition(x, y, 0);
        const entry: Entry = { node: n, id };
        this.placedNodes.push(entry);
        return entry;
    }

    private countPlaced(id: string): number {
        return this.placedNodes.reduce((c, e) => c + (e.id === id ? 1 : 0), 0);
    }
    private unplaced(id: string): number {
        return Math.max(0, DecorCatalog.ownedCount(id) - this.countPlaced(id));
    }

    /** 把場上實際的裝飾節點寫回 DecorCatalog（存檔）。 */
    private syncPlaced() {
        const list: Placed[] = this.placedNodes.map(e => ({
            id: e.id, x: e.node.position.x, y: e.node.position.y,
        }));
        DecorCatalog.setPlaced(list);
    }

    // ---- 進出佈置模式 ----

    private toggle() {
        if (this.editing) this.exitEdit(); else this.enterEdit();
    }

    private enterEdit() {
        this.editing = true;
        UIState.modalOpen = true;
        if (this.toggleLabel) this.toggleLabel.string = '完成';
        this.placedNodes.forEach(e => this.makeDraggable(e));
        this.buildTray();
        this.buildHint();
    }

    private exitEdit() {
        this.editing = false;
        this.dragging = null;
        this.placedNodes.forEach(e => this.removeDraggable(e));
        this.syncPlaced();
        if (this.toggleLabel) this.toggleLabel.string = '佈置房間';
        if (this.tray) { this.tray.destroy(); this.tray = null; }
        if (this.hintNode) { this.hintNode.destroy(); this.hintNode = null; }
        UIState.modalOpen = false;
    }

    // ---- 拖放 ----

    private makeDraggable(entry: Entry) {
        const n = entry.node;
        const props = this.node.getComponent(UITransform)!;
        const op = n.getComponent(UIOpacity);
        const onStart = (_e: EventTouch) => { this.dragging = n; if (op) op.opacity = 200; };
        const onMove = (e: EventTouch) => {
            if (this.dragging !== n) return;
            const ui = e.getUILocation();
            const lp = props.convertToNodeSpaceAR(new Vec3(ui.x, ui.y, 0));
            n.setPosition(lp.x, lp.y, 0);
        };
        const onEnd = (e: EventTouch) => {
            if (this.dragging !== n) return;
            this.dragging = null;
            if (op) op.opacity = 255;
            const ui = e.getUILocation();
            if (ui.y < this.trayH) this.removePlaced(entry);   // 拖回托盤＝收回
            this.syncPlaced();
            this.refreshTray();
        };
        n.on(Node.EventType.TOUCH_START, onStart, this);
        n.on(Node.EventType.TOUCH_MOVE, onMove, this);
        n.on(Node.EventType.TOUCH_END, onEnd, this);
        n.on(Node.EventType.TOUCH_CANCEL, onEnd, this);
        entry.handlers = [onStart, onMove, onEnd];
    }

    private removeDraggable(entry: Entry) {
        entry.node.off(Node.EventType.TOUCH_START);
        entry.node.off(Node.EventType.TOUCH_MOVE);
        entry.node.off(Node.EventType.TOUCH_END);
        entry.node.off(Node.EventType.TOUCH_CANCEL);
        entry.handlers = undefined;
    }

    private removePlaced(entry: Entry) {
        const i = this.placedNodes.indexOf(entry);
        if (i >= 0) this.placedNodes.splice(i, 1);
        entry.node.destroy();
    }

    private placeFromTray(id: string) {
        if (this.unplaced(id) <= 0) return;
        const vis = view.getVisibleSize();
        const props = this.node.getComponent(UITransform)!;
        const lp = props.convertToNodeSpaceAR(new Vec3(vis.width / 2, vis.height * 0.52, 0));
        const entry = this.createDecorNode(id, lp.x, lp.y);
        this.makeDraggable(entry);
        this.syncPlaced();
        this.refreshTray();
    }

    // ---- UI：常駐鈕 / 托盤 / 提示 ----

    private buildToggle() {
        if (!this.canvas) return;
        const n = new Node('DecorToggle');
        n.layer = this.canvas.layer;
        this.canvas.addChild(n);
        n.addComponent(UITransform).setContentSize(128, 48);
        const w = n.addComponent(Widget);
        w.isAlignRight = true; w.right = 20;
        w.isAlignBottom = true; w.bottom = 20;
        w.updateAlignment();
        const g = n.addComponent(Graphics);
        g.lineWidth = 3; g.fillColor = new Color(120, 78, 150, 255);
        g.strokeColor = new Color(230, 210, 245, 235);
        this.roundRect(g, -64, -24, 128, 48, 12); g.fill(); g.stroke();
        const t = new Node('t'); t.layer = this.canvas.layer; n.addChild(t);
        t.addComponent(UITransform).setContentSize(128, 48);
        const lb = t.addComponent(Label);
        lb.string = '佈置房間'; lb.fontSize = 22; lb.color = new Color(250, 244, 255, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        this.toggleLabel = lb;
        const op = n.addComponent(UIOpacity);
        n.on(Node.EventType.TOUCH_START, () => { op.opacity = 180; });
        n.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; this.toggle(); });
        n.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
        this.toggleBtn = n;
    }

    private buildHint() {
        if (!this.canvas) return;
        const n = new Node('DecorHint');
        n.layer = this.canvas.layer;
        this.canvas.addChild(n);
        n.addComponent(UITransform).setContentSize(560, 30);
        const w = n.addComponent(Widget);
        w.isAlignTop = true; w.top = 16; w.isAlignHorizontalCenter = true; w.horizontalCenter = 0;
        w.updateAlignment();
        const lb = n.addComponent(Label);
        lb.string = '點托盤的裝飾擺出來 · 拖曳移動 · 拖到底部托盤收回 · 按「完成」結束';
        lb.fontSize = 20; lb.color = new Color(255, 250, 235, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.enableOutline = true; lb.outlineColor = new Color(30, 24, 40, 220); lb.outlineWidth = 3;
        this.hintNode = n;
    }

    private buildTray() {
        if (!this.canvas) return;
        const tray = new Node('DecorTray');
        tray.layer = this.canvas.layer;
        this.canvas.addChild(tray);
        tray.addComponent(UITransform).setContentSize(4000, this.trayH);
        const w = tray.addComponent(Widget);
        w.isAlignLeft = w.isAlignRight = w.isAlignBottom = true;
        w.left = w.right = w.bottom = 0; w.updateAlignment();
        tray.addComponent(BlockInputEvents);
        const g = tray.addComponent(Graphics);
        g.fillColor = new Color(32, 26, 44, 235);
        g.rect(-2000, -this.trayH / 2, 4000, this.trayH); g.fill();
        this.tray = tray;
        this.refreshTray();
    }

    private refreshTray() {
        const tray = this.tray;
        if (!tray) return;
        // 清掉舊格子（保留 Graphics 背板）
        tray.children.slice().forEach(c => { if (c.name === 'slot') c.destroy(); });
        const items = DecorCatalog.catalog.filter(d => this.unplaced(d.id) > 0);
        const slot = 118, gap = 10;
        const totalW = items.length * (slot + gap);
        let x = -totalW / 2 + slot / 2 + gap / 2;
        if (items.length === 0) {
            const n = new Node('slot'); n.layer = tray.layer; tray.addChild(n);
            n.addComponent(UITransform).setContentSize(600, 40);
            const lb = n.addComponent(Label);
            lb.string = '沒有可擺放的裝飾——先去城鎮花店買一些吧';
            lb.fontSize = 20; lb.color = new Color(210, 200, 220, 255);
            lb.horizontalAlign = Label.HorizontalAlign.CENTER;
            return;
        }
        for (const d of items) {
            const n = new Node('slot'); n.layer = tray.layer; tray.addChild(n);
            n.addComponent(UITransform).setContentSize(slot, this.trayH - 20);
            n.setPosition(x, 0, 0); x += slot + gap;
            const bg = n.addComponent(Graphics);
            bg.lineWidth = 2; bg.fillColor = new Color(56, 46, 72, 255);
            bg.strokeColor = new Color(150, 130, 170, 200);
            this.roundRect(bg, -slot / 2, -(this.trayH - 20) / 2, slot, this.trayH - 20, 10);
            bg.fill(); bg.stroke();
            // 圖示
            const icon = new Node('icon'); icon.layer = tray.layer; n.addChild(icon);
            icon.addComponent(UITransform).setContentSize(slot - 28, this.trayH - 62);
            icon.setPosition(0, 12, 0);
            const sp = icon.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM; sp.trim = false;
            const f = GameArt.decor(d.id);
            if (f) this.fit(sp, f, slot - 28, this.trayH - 62);
            // 數量
            const cnt = new Node('cnt'); cnt.layer = tray.layer; n.addChild(cnt);
            cnt.addComponent(UITransform).setContentSize(slot, 22);
            cnt.setPosition(0, -(this.trayH - 20) / 2 + 14, 0);
            const clb = cnt.addComponent(Label);
            clb.string = `${d.name} ×${this.unplaced(d.id)}`;
            clb.fontSize = 14; clb.color = new Color(235, 230, 245, 255);
            clb.horizontalAlign = Label.HorizontalAlign.CENTER;
            clb.overflow = Label.Overflow.SHRINK;
            const op = n.addComponent(UIOpacity);
            n.on(Node.EventType.TOUCH_START, () => { op.opacity = 180; });
            n.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; this.placeFromTray(d.id); });
            n.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
        }
    }

    // ---- 小工具 ----

    private fit(sp: Sprite, frame: SpriteFrame, maxW: number, maxH: number) {
        const rw = frame.rect.width || frame.originalSize.width;
        const rh = frame.rect.height || frame.originalSize.height;
        const k = Math.min(maxW / rw, maxH / rh);
        sp.spriteFrame = frame;
        sp.getComponent(UITransform)!.setContentSize(rw * k, rh * k);
    }

    private roundRect(g: Graphics, x: number, y: number, w: number, h: number, r: number) {
        const H = Math.PI / 2;
        g.moveTo(x + r, y);
        g.lineTo(x + w - r, y); g.arc(x + w - r, y + r, r, -H, 0, false);
        g.lineTo(x + w, y + h - r); g.arc(x + w - r, y + h - r, r, 0, H, false);
        g.lineTo(x + r, y + h); g.arc(x + r, y + h - r, r, H, Math.PI, false);
        g.lineTo(x, y + r); g.arc(x + r, y + r, r, Math.PI, Math.PI + H, false);
        g.close();
    }
}
