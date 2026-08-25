import { _decorator, Component, Node, UITransform, Widget, Sprite, SpriteFrame,
         Label, Color, Graphics, BlockInputEvents, UIOpacity, find, view, Vec3,
         EventTouch, Camera, color, input, Input, EventKeyboard, KeyCode } from 'cc';
import { UIState } from './UIState';
import { GameArt } from './GameArt';
import { DecorCatalog, Placed } from './DecorCatalog';
import { RoomLayout, PlacedFurniture } from './RoomLayout';
import { ShopShelf } from './ShopShelf';
import { TILE_W, TILE_H, GRID_W, GRID_H, ROOM_W, ROOM_H,
         tileCenter, tileFront, frontCorner, worldToTile, inGrid, clampCell,
         furnitureDef, reservedCells } from './data/shopRoom';
import { ShopCounter } from './ShopCounter';
const { ccclass } = _decorator;

/** 場上一件擺出來的東西（家具或裝飾）。裝飾一律當 1×1。 */
interface Entry {
    node: Node;
    id: string;
    kind: 'furn' | 'decor';
    gx: number; gy: number;
    w: number; h: number;
    /** 左右翻面（靠右後牆的貨架要翻過來背才貼牆）。錨點在正下方中央 → scale.x = -1 就好。 */
    flip?: boolean;
    handlers?: boolean;
}

/**
 * 店內房間管理＋佈置（掛在 shop.scene 的 Props 上）。
 *
 *   - 進場：把地板底圖套到 Ground（等距房間，見 data/shopRoom.ts），
 *     再把 RoomLayout 的家具與 DecorCatalog 的裝飾生成到 Props（吃 YSort 遮擋）。
 *   - **東西一律放在地磚格上**：一塊磚＝一格，家具可以佔好幾格（販售桌 2×1 等），
 *     同一格不能塞兩件。拖曳時會吸附到最近的格子，放不下就顯示紅色不給放。
 *   - 右下常駐「佈置房間」鈕 → 佈置模式：底部托盤列出買了還沒擺的家具與裝飾，
 *     點一個擺出來、拖到想要的格子；拖回托盤＝收回。「完成」存檔離開。
 *
 * 販售桌是特別的一件：上架商品會陳列在它的檯面上（Shelf 節點會被移過去），
 * 顧客也是走到它前面買東西 —— 所以搬動販售桌，整個店的動線就跟著變。
 */
@ccclass('DecorRoom')
export class DecorRoom extends Component {
    private entries: Entry[] = [];
    private spawned = false;
    private editing = false;

    private canvas: Node | null = null;
    private toggleBtn: Node | null = null;
    private toggleLabel: Label | null = null;
    private toggleWidget: Widget | null = null;
    private tray: Node | null = null;
    private hintNode: Node | null = null;
    private gridNode: Node | null = null;
    private gridGfx: Graphics | null = null;
    private lastTouched: Entry | null = null;
    private shadeNode: Node | null = null;
    private shadeGfx: Graphics | null = null;
    private dragging: Entry | null = null;

    private readonly trayH = 150;   // 底部托盤高度；拖到這區以下＝收回
    // 裝飾原圖是「概念圖」解析度，要縮到跟世界比例一致；0.4 讓它跟一格地磚差不多大。
    private readonly decorScale = 0.4;

    onLoad() {
        this.canvas = find('Canvas');
        this.applyRoomArt();
        GameArt.preload();
        GameArt.onReady(() => { this.applyRoomArt(); this.spawnAll(); });
        this.buildToggle();
    }

    // ---- 房間底圖 ----

    /** 把等距房間底圖套到 Ground（同 BrewRoom 的作法，不必手工做 spriteFrame meta）。 */
    private applyRoomArt() {
        // ⚠️ 相機底色要跟房間的暗底一致。設計解析度 960×640 是 fitHeight，在 16:9 的
        // 視窗上看得到的寬度約 1138 > 房間的 960 —— 兩側露出的那截若還是預設的深綠，
        // 看起來就像房間浮在草地上。改成同一個暗色，露出來的部分就像房間外的暗處。
        const cam = find('Canvas/Camera')?.getComponent(Camera);
        if (cam) cam.clearColor = color(34, 27, 24, 255);
        const ground = this.node.parent?.getChildByName('Ground');
        if (!ground) return;
        const ut = ground.getComponent(UITransform);
        if (ut) ut.setContentSize(ROOM_W, ROOM_H);
        const sp = ground.getComponent(Sprite);
        if (!sp) return;
        const f = GameArt.shopRoom();
        // ⚠️ 底圖是 GameArt 非同步載完才有的，onLoad 這次呼叫一定拿不到。場景檔的 Ground
        // 上還存著**舊版的店內裝潢圖**（shop-interior），什麼都不做的話進店會先閃一下舊店面。
        // 所以還沒載好就先清空 —— 露出的是相機那個暗底色，看起來只是房間還沒亮燈。
        if (!f) { sp.spriteFrame = null; return; }
        sp.type = Sprite.Type.SIMPLE;
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.spriteFrame = f;
    }

    // ---- 進場：生成已擺的家具與裝飾 ----

    private spawnAll() {
        if (this.spawned) return;
        this.spawned = true;
        for (const p of RoomLayout.placedList()) {
            const d = furnitureDef(p.id);
            if (d) this.createEntry(p.id, 'furn', p.gx, p.gy, d.w, d.h, p.flip);
        }
        // 裝飾存的是像素座標（舊格式沿用），進場時吸到最近的空格上
        for (const p of DecorCatalog.placedList()) {
            const c = this.freeCellNear(p.x, p.y, 1, 1);
            if (c) this.createEntry(p.id, 'decor', c.gx, c.gy, 1, 1);
        }
        this.syncAll();
        this.updateSaleSpot();
        this.drawShades();
    }

    private createEntry(id: string, kind: 'furn' | 'decor', gx: number, gy: number,
                        w: number, h: number, flip = false): Entry {
        const n = new Node((kind === 'furn' ? 'furn-' : 'decor-') + id);
        n.layer = this.node.layer;
        this.node.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setAnchorPoint(0.5, 0);
        const sp = n.addComponent(Sprite);
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.trim = false;
        const f = kind === 'furn' ? GameArt.furniture(id) : GameArt.decor(id);
        if (f) {
            sp.spriteFrame = f;
            // 家具圖已是最終大小；裝飾品預設縮 decorScale，但目錄可以逐筆覆寫
            const k = kind === 'furn' ? 1 : (DecorCatalog.def(id)?.scale ?? this.decorScale);
            ut.setContentSize(f.rect.width * k, f.rect.height * k);
        } else {
            ut.setContentSize(TILE_W / 2, TILE_H);
        }
        n.addComponent(UIOpacity);
        const e: Entry = { node: n, id, kind, gx, gy, w, h, flip };
        n.setScale(flip ? -1 : 1, 1, 1);
        this.moveEntry(e, gx, gy);
        this.entries.push(e);
        return e;
    }

    /** 把一件東西放到某一格（家具對前角、裝飾對格子下角）。 */
    private moveEntry(e: Entry, gx: number, gy: number) {
        e.gx = gx; e.gy = gy;
        const p = e.kind === 'furn' ? frontCorner(gx, gy, e.w, e.h) : tileFront(gx, gy);
        e.node.setPosition(p.x, p.y, 0);
        this.drawShades();
    }

    // ---- 格子佔用 ----

    private occupied(skip?: Entry): Set<string> {
        const s = new Set<string>();
        for (const c of reservedCells()) s.add(`${c.gx},${c.gy}`);   // 門口不給擺
        for (const e of this.entries) {
            if (e === skip) continue;
            for (let c = 0; c < e.w; c++) {
                for (let r = 0; r < e.h; r++) s.add(`${e.gx + c},${e.gy + r}`);
            }
        }
        return s;
    }

    private canPlaceAt(gx: number, gy: number, w: number, h: number, skip?: Entry): boolean {
        if (!inGrid(gx, gy) || !inGrid(gx + w - 1, gy + h - 1)) return false;
        const taken = this.occupied(skip);
        for (let c = 0; c < w; c++) {
            for (let r = 0; r < h; r++) {
                if (taken.has(`${gx + c},${gy + r}`)) return false;
            }
        }
        return true;
    }

    /** 從某個世界座標往外找一個放得下的格子（進場時把舊座標的裝飾收攏進格子用）。 */
    private freeCellNear(x: number, y: number, w: number, h: number): { gx: number; gy: number } | null {
        const t = clampCell(worldToTile(x, y).gx, worldToTile(x, y).gy, w, h);
        if (this.canPlaceAt(t.gx, t.gy, w, h)) return t;
        for (let d = 1; d <= GRID_W + GRID_H; d++) {
            for (let dx = -d; dx <= d; dx++) {
                for (let dy = -d; dy <= d; dy++) {
                    if (Math.abs(dx) !== d && Math.abs(dy) !== d) continue;
                    const gx = t.gx + dx, gy = t.gy + dy;
                    if (this.canPlaceAt(gx, gy, w, h)) return { gx, gy };
                }
            }
        }
        return null;
    }

    private firstFreeCell(w: number, h: number) { return this.freeCellNear(0, 0, w, h); }

    // ---- 存檔 ----

    private syncAll() {
        const furn: PlacedFurniture[] = [];
        const decor: Placed[] = [];
        for (const e of this.entries) {
            if (e.kind === 'furn') furn.push({ id: e.id, gx: e.gx, gy: e.gy, flip: e.flip });
            else {
                const p = tileFront(e.gx, e.gy);
                decor.push({ id: e.id, x: p.x, y: p.y });
            }
        }
        RoomLayout.setPlaced(furn);
        DecorCatalog.setPlaced(decor);
    }

    /**
     * 販售桌搬家時，把跟著它跑的兩個節點一起搬：
     *   Shelf   ── 上架商品的陳列（畫在檯面上）
     *   Counter ── 「按 E 經營商店」的觸發（站到桌前就能上架，不用另外找櫃台）
     * 顧客的挑貨位置是 CustomerManager 每次生成時問 RoomLayout，不用在這裡處理。
     */
    private updateSaleSpot() {
        const top = RoomLayout.saleTop();
        const front = RoomLayout.saleFront();
        const table = this.entries.find(e => e.kind === 'furn' && furnitureDef(e.id)?.sale);
        const shelf = this.node.getChildByName('Shelf') ?? this.node.parent?.getChildByName('Shelf');
        if (shelf && top && table) {
            // ⚠️ Shelf 不能留在 Props 底下：YSortLayer 是照 position.y 由大到小畫，
            // 檯面（y 較大）會排在桌子（前角 y 較小）之前 → 商品被桌子整個蓋住。
            // 改成掛在桌子節點底下：子節點一定畫在父節點的圖之後，就穩穩坐在檯面上。
            shelf.parent = table.node;
            const f = frontCorner(table.gx, table.gy, table.w, table.h);
            shelf.setPosition(top.x - f.x, top.y - f.y, 0);
            const sh = shelf.getComponent(ShopShelf);
            if (sh) { sh.slotSize = 44; sh.spacing = 52; }   // 一格桌面塞得下的大小
        }
        const counter = this.node.getChildByName('Counter') ?? this.node.parent?.getChildByName('Counter');
        if (counter && front) {
            counter.setPosition(front.x, front.y, 0);
            const c = counter.getComponent(ShopCounter);
            if (c) c.interactRange = 130;   // 收小一點，跟門的感應圈分開
        }
    }

    private countPlaced(id: string, kind: 'furn' | 'decor'): number {
        return this.entries.reduce((c, e) => c + (e.id === id && e.kind === kind ? 1 : 0), 0);
    }
    private unplacedFurn(id: string): number {
        return Math.max(0, RoomLayout.ownedCount(id) - this.countPlaced(id, 'furn'));
    }
    private unplacedDecor(id: string): number {
        return Math.max(0, DecorCatalog.ownedCount(id) - this.countPlaced(id, 'decor'));
    }

    // ---- 進出佈置模式 ----

    private toggle() { if (this.editing) this.exitEdit(); else this.enterEdit(); }

    private enterEdit() {
        this.editing = true;
        UIState.modalOpen = true;
        if (this.toggleLabel) this.toggleLabel.string = '完成';
        this.entries.forEach(e => this.makeDraggable(e));
        this.buildGrid();
        this.drawGrid(null);
        this.buildTray();
        this.buildHint();
        input.on(Input.EventType.KEY_DOWN, this.onEditKey, this);
        // 把「完成」鈕移到托盤上方並提到最上層，別被托盤蓋住（不然關不掉）
        if (this.toggleWidget) { this.toggleWidget.bottom = this.trayH + 16; this.toggleWidget.updateAlignment(); }
        if (this.toggleBtn && this.canvas) this.toggleBtn.setSiblingIndex(this.canvas.children.length - 1);
    }

    /**
     * 佈置模式的 R ＝ 把最後點到的家具左右翻面。
     * ⚠️ 只在佈置模式掛鍵盤（`enterEdit` 掛、`exitEdit` 解），不然平常走路按 R 也會翻。
     */
    private onEditKey(ev: EventKeyboard) {
        if (!this.editing || ev.keyCode !== KeyCode.KEY_R) return;
        const e = this.lastTouched;
        // ⚠️ 這個專案的 target 是 ES2015，沒有 Array.includes（同 Object.entries 那個老坑）
        if (!e || this.entries.indexOf(e) < 0) return;
        e.flip = !e.flip;
        e.node.setScale(e.flip ? -1 : 1, 1, 1);
        this.syncAll();
    }

    private exitEdit() {
        this.editing = false;
        this.dragging = null;
        input.off(Input.EventType.KEY_DOWN, this.onEditKey, this);
        this.lastTouched = null;
        this.entries.forEach(e => this.removeDraggable(e));
        this.syncAll();
        this.updateSaleSpot();
        if (this.toggleLabel) this.toggleLabel.string = '佈置房間';
        if (this.toggleWidget) { this.toggleWidget.bottom = 20; this.toggleWidget.updateAlignment(); }
        if (this.tray) { this.tray.destroy(); this.tray = null; }
        if (this.hintNode) { this.hintNode.destroy(); this.hintNode = null; }
        if (this.gridNode) { this.gridNode.destroy(); this.gridNode = null; this.gridGfx = null; }
        UIState.modalOpen = false;
    }

    // ---- 家具的接地影子 ----

    /**
     * 家具/裝飾原本沒有影子（`ShadowLayer` 只跟角色），擺在木地板上會像浮著。
     * 這裡在**地板之上、家具之下**畫一片佔地菱形的暗影 —— 東西就「坐」在格子上了。
     *
     * ⚠️ 一個節點只能有一個 Graphics（`Hud` 那次踩過），所以全部影子共用一個 Graphics、
     *    每次重畫先 clear()；非零環繞規則讓相鄰的影子重疊處不會加倍變黑。
     */
    private buildShade() {
        const world = this.node.parent;
        if (!world || this.shadeNode) return;
        const n = new Node('RoomShade');
        n.layer = this.node.layer;
        world.addChild(n);
        n.setSiblingIndex(this.node.getSiblingIndex());
        n.addComponent(UITransform).setContentSize(ROOM_W, ROOM_H);
        this.shadeGfx = n.addComponent(Graphics);
        this.shadeNode = n;
    }

    /** 依現在擺著的東西重畫全部影子。 */
    private drawShades() {
        this.buildShade();
        const g = this.shadeGfx;
        if (!g) return;
        g.clear();
        // ⚠️ 影子要**比佔地大一點**才看得到 —— 等距視角下家具自己的圖幾乎把佔地菱形整個蓋住，
        //    畫在裡面等於白畫。三圈由外而內疊出柔邊（Graphics 沒有模糊可用）。
        const RINGS: [number, number][] = [[1.30, 40], [1.15, 45], [1.00, 55]];
        for (const [k, alpha] of RINGS) {
            g.fillColor = new Color(14, 9, 12, alpha);
            for (const e of this.entries) {
                const c0 = tileCenter(e.gx, e.gy);
                const c1 = tileCenter(e.gx + e.w - 1, e.gy + e.h - 1);
                const cx = (c0.x + c1.x) / 2, cy = (c0.y + c1.y) / 2;
                const rx = (e.w + e.h) * TILE_W / 4 * k;
                const ry = (e.w + e.h) * TILE_H / 4 * k;
                g.moveTo(cx, cy - ry);
                g.lineTo(cx + rx, cy);
                g.lineTo(cx, cy + ry);
                g.lineTo(cx - rx, cy);
                g.close();
            }
            g.fill();   // 同一圈用非零環繞，相鄰家具重疊處不會加倍變黑
        }
    }

    // ---- 格線 ----

    /**
     * 格線畫在 World 底下、Props 之前（＝地板之上、人物與家具之下），
     * 跟 ShadowLayer 同一招；掛在 Props 底下會被 YSortLayer 每幀重排。
     */
    private buildGrid() {
        const world = this.node.parent;
        if (!world || this.gridNode) return;
        const n = new Node('RoomGrid');
        n.layer = this.node.layer;
        world.addChild(n);
        n.setSiblingIndex(this.node.getSiblingIndex());
        n.addComponent(UITransform).setContentSize(ROOM_W, ROOM_H);
        this.gridGfx = n.addComponent(Graphics);
        this.gridNode = n;
    }

    /** 畫全部格線；hover 那幾格另外上色（綠＝放得下、紅＝擋到別的東西）。 */
    private drawGrid(hover: { gx: number; gy: number; w: number; h: number; ok: boolean } | null) {
        const g = this.gridGfx;
        if (!g) return;
        g.clear();
        g.lineWidth = 2;
        g.strokeColor = new Color(255, 255, 255, 90);
        for (let gx = 0; gx < GRID_W; gx++) {
            for (let gy = 0; gy < GRID_H; gy++) {
                const c = tileCenter(gx, gy);
                g.moveTo(c.x, c.y + TILE_H / 2);
                g.lineTo(c.x + TILE_W / 2, c.y);
                g.lineTo(c.x, c.y - TILE_H / 2);
                g.lineTo(c.x - TILE_W / 2, c.y);
                g.close();
            }
        }
        g.stroke();
        if (!hover) return;
        g.fillColor = hover.ok ? new Color(120, 230, 140, 110) : new Color(235, 90, 90, 110);
        for (let c = 0; c < hover.w; c++) {
            for (let r = 0; r < hover.h; r++) {
                const t = tileCenter(hover.gx + c, hover.gy + r);
                if (!inGrid(hover.gx + c, hover.gy + r)) continue;
                g.moveTo(t.x, t.y + TILE_H / 2);
                g.lineTo(t.x + TILE_W / 2, t.y);
                g.lineTo(t.x, t.y - TILE_H / 2);
                g.lineTo(t.x - TILE_W / 2, t.y);
                g.close();
            }
        }
        g.fill();
    }

    // ---- 拖放（吸附到格子） ----

    private makeDraggable(e: Entry) {
        if (e.handlers) return;
        const n = e.node;
        const props = this.node.getComponent(UITransform)!;
        const op = n.getComponent(UIOpacity);
        const cellUnder = (ev: EventTouch) => {
            const ui = ev.getUILocation();
            const lp = props.convertToNodeSpaceAR(new Vec3(ui.x, ui.y, 0));
            // 抓的是「手指下方那一格」，家具則以佔地左上角為準
            const t = worldToTile(lp.x, lp.y);
            return clampCell(t.gx - (e.w - 1), t.gy - (e.h - 1), e.w, e.h);
        };
        n.on(Node.EventType.TOUCH_START, () => {
            this.dragging = e;
            this.lastTouched = e;          // 按 R 翻的就是這一件
            if (op) op.opacity = 200;
        }, this);
        n.on(Node.EventType.TOUCH_MOVE, (ev: EventTouch) => {
            if (this.dragging !== e) return;
            const ui = ev.getUILocation();
            if (ui.y < this.trayH) {                    // 停在托盤上＝準備收回
                this.drawGrid(null);
                const lp = props.convertToNodeSpaceAR(new Vec3(ui.x, ui.y, 0));
                e.node.setPosition(lp.x, lp.y, 0);
                return;
            }
            const c = cellUnder(ev);
            const ok = this.canPlaceAt(c.gx, c.gy, e.w, e.h, e);
            this.drawGrid({ gx: c.gx, gy: c.gy, w: e.w, h: e.h, ok });
            if (ok) this.moveEntry(e, c.gx, c.gy);
        }, this);
        const end = (ev: EventTouch) => {
            if (this.dragging !== e) return;
            this.dragging = null;
            if (op) op.opacity = 255;
            this.drawGrid(null);
            if (ev.getUILocation().y < this.trayH) { this.removeEntry(e); }
            else this.moveEntry(e, e.gx, e.gy);          // 回到最後一個合法格
            this.syncAll();
            this.updateSaleSpot();
            this.refreshTray();
        };
        n.on(Node.EventType.TOUCH_END, end, this);
        n.on(Node.EventType.TOUCH_CANCEL, end, this);
        e.handlers = true;
    }

    private removeDraggable(e: Entry) {
        e.node.off(Node.EventType.TOUCH_START);
        e.node.off(Node.EventType.TOUCH_MOVE);
        e.node.off(Node.EventType.TOUCH_END);
        e.node.off(Node.EventType.TOUCH_CANCEL);
        e.handlers = false;
    }

    private removeEntry(e: Entry) {
        // 販售桌是整間店的核心（商品陳列＋顧客動線＋按 E 上架都靠它），收掉就沒得做生意；
        // 而且 Shelf 是掛在它底下的，節點一銷毀商品陳列也會跟著沒。搬得動但收不回。
        if (e.kind === 'furn' && furnitureDef(e.id)?.sale) {
            this.flashHint('販售桌是店的核心，只能搬不能收起來');
            this.moveEntry(e, e.gx, e.gy);
            return;
        }
        const i = this.entries.indexOf(e);
        if (i >= 0) this.entries.splice(i, 1);
        e.node.destroy();
        this.drawShades();
    }

    private placeFromTray(id: string, kind: 'furn' | 'decor') {
        const d = kind === 'furn' ? furnitureDef(id) : undefined;
        const w = d ? d.w : 1, h = d ? d.h : 1;
        if (kind === 'furn' ? this.unplacedFurn(id) <= 0 : this.unplacedDecor(id) <= 0) return;
        const c = this.firstFreeCell(w, h);
        if (!c) { this.flashHint('房間放不下了，先收掉一些吧'); return; }
        const e = this.createEntry(id, kind, c.gx, c.gy, w, h);
        this.makeDraggable(e);
        this.syncAll();
        this.updateSaleSpot();
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
        this.toggleWidget = w;
        const g = n.addComponent(Graphics);
        g.lineWidth = 3; g.fillColor = new Color(120, 78, 150, 255);
        g.strokeColor = new Color(230, 210, 245, 235);
        g.rect(-64, -24, 128, 48); g.fill(); g.stroke();
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
        n.addComponent(UITransform).setContentSize(620, 30);
        const w = n.addComponent(Widget);
        w.isAlignTop = true; w.top = 16; w.isAlignHorizontalCenter = true; w.horizontalCenter = 0;
        w.updateAlignment();
        const lb = n.addComponent(Label);
        lb.string = '點托盤的東西擺出來 · 拖曳吸到地磚格 · 拖回托盤＝收回 · 點一下再按 R 左右翻面 · 「完成」結束';
        lb.fontSize = 20; lb.color = new Color(255, 250, 235, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.enableOutline = true; lb.outlineColor = new Color(30, 24, 40, 220); lb.outlineWidth = 3;
        this.hintNode = n;
    }

    private flashHint(msg: string) {
        const lb = this.hintNode?.getComponent(Label);
        if (lb) lb.string = msg;
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

        // 常駐提示：托盤＝收回區（不叫 'slot'，refreshTray 不會清掉它）
        const tip = new Node('trayhint');
        tip.layer = tray.layer;
        tray.addChild(tip);
        tip.addComponent(UITransform).setContentSize(150, this.trayH - 20);
        const tw = tip.addComponent(Widget);
        tw.isAlignLeft = true; tw.left = 14; tw.isAlignVerticalCenter = true; tw.verticalCenter = 0;
        tw.updateAlignment();
        const tlb = tip.addComponent(Label);
        tlb.string = '把擺出來的東西\n拖回這裡＝收回';
        tlb.fontSize = 16; tlb.lineHeight = 22; tlb.color = new Color(200, 190, 214, 255);
        tlb.horizontalAlign = Label.HorizontalAlign.LEFT;
        tlb.verticalAlign = Label.VerticalAlign.CENTER;

        this.refreshTray();
    }

    private refreshTray() {
        const tray = this.tray;
        if (!tray) return;
        tray.children.slice().forEach(c => { if (c.name === 'slot') c.destroy(); });

        interface Item { id: string; kind: 'furn' | 'decor'; name: string; n: number; }
        const items: Item[] = [];
        for (const f of RoomLayout.catalog) {
            const n = this.unplacedFurn(f.id);
            if (n > 0) items.push({ id: f.id, kind: 'furn', name: f.name, n });
        }
        for (const d of DecorCatalog.catalog) {
            const n = this.unplacedDecor(d.id);
            if (n > 0) items.push({ id: d.id, kind: 'decor', name: d.name, n });
        }

        const slot = 118, gap = 10;
        if (items.length === 0) {
            const n = new Node('slot'); n.layer = tray.layer; tray.addChild(n);
            n.addComponent(UITransform).setContentSize(700, 40);
            const lb = n.addComponent(Label);
            lb.string = '沒有可擺放的東西——去城鎮花店買家具與裝飾吧';
            lb.fontSize = 20; lb.color = new Color(210, 200, 220, 255);
            lb.horizontalAlign = Label.HorizontalAlign.CENTER;
            return;
        }
        const totalW = items.length * (slot + gap);
        let x = -totalW / 2 + slot / 2 + gap / 2;
        for (const it of items) {
            const n = new Node('slot'); n.layer = tray.layer; tray.addChild(n);
            n.addComponent(UITransform).setContentSize(slot, this.trayH - 20);
            n.setPosition(x, 0, 0); x += slot + gap;
            const bg = n.addComponent(Graphics);
            bg.lineWidth = 2;
            bg.fillColor = it.kind === 'furn' ? new Color(70, 54, 44, 255) : new Color(56, 46, 72, 255);
            bg.strokeColor = new Color(150, 130, 170, 200);
            bg.rect(-slot / 2, -(this.trayH - 20) / 2, slot, this.trayH - 20);
            bg.fill(); bg.stroke();
            const icon = new Node('icon'); icon.layer = tray.layer; n.addChild(icon);
            icon.addComponent(UITransform).setContentSize(slot - 28, this.trayH - 62);
            icon.setPosition(0, 12, 0);
            const sp = icon.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM; sp.trim = false;
            const f = it.kind === 'furn' ? GameArt.furniture(it.id) : GameArt.decor(it.id);
            if (f) this.fit(sp, f, slot - 28, this.trayH - 62);
            const cnt = new Node('cnt'); cnt.layer = tray.layer; n.addChild(cnt);
            cnt.addComponent(UITransform).setContentSize(slot, 22);
            cnt.setPosition(0, -(this.trayH - 20) / 2 + 14, 0);
            const clb = cnt.addComponent(Label);
            clb.string = `${it.name} ×${it.n}`;
            clb.fontSize = 14; clb.color = new Color(235, 230, 245, 255);
            clb.horizontalAlign = Label.HorizontalAlign.CENTER;
            clb.overflow = Label.Overflow.SHRINK;
            const op = n.addComponent(UIOpacity);
            n.on(Node.EventType.TOUCH_START, () => { op.opacity = 180; });
            n.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; this.placeFromTray(it.id, it.kind); });
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
}
