import { _decorator, Component, Node, UITransform, Sprite, Label, Color, Graphics,
         Vec3, input, Input, EventKeyboard, KeyCode, find, tween, UIOpacity } from 'cc';
import { GameArt } from './GameArt';
import { Garden } from './Garden';
import { Inventory } from './Inventory';
import { UIState } from './UIState';
import { CharacterAnimator } from './CharacterAnimator';
import { SceneDoor } from './SceneDoor';
import { TownFolk } from './TownFolk';
import { Quests } from './Quests';
import { FLOWERS, PLOT_COUNT, PLOT_SCALE, FLOWER_SCALE, plotPos,
         FENCE_WALK, GARDEN_TO_SHOP } from './data/garden';
const { ccclass } = _decorator;

/**
 * 後花園（garden.scene）。
 *
 * 場景檔本身只有 Canvas/World/Ground/Props/Player/WalkArea 這棵空樹，其餘全部在這裡
 * 執行期裝起來 —— 背景圖（同 BrewRoom 的作法，省掉手工 meta）、12 塊花圃、回店裡的門、
 * 還有沿著柵欄外那條石板路經過的村民。安裝方式同 TownFolk：由 PlayerController.onLoad
 * 在 garden 場景呼叫 `ensure()`，元件掛到既有的 Props 節點上。
 *
 * 互動集中在這裡而不是每塊花圃各自監聽鍵盤：12 塊花圃就是 12 個鍵盤監聽器，而且同一次
 * 按鍵會被每一塊都收到。這裡只認「離玩家最近且在範圍內」的那一塊。
 */

const REACH = 90;              // 玩家離花圃多近才能操作（像素）

@ccclass('GardenRoom')
export class GardenRoom extends Component {
    static instance: GardenRoom | null = null;

    /** 掛到 garden.scene 既有的 Props 節點上（重複呼叫安全）。 */
    static ensure(): GardenRoom | null {
        if (GardenRoom.instance && GardenRoom.instance.isValid) return GardenRoom.instance;
        const props = find('Canvas/World/Props');
        if (!props) { console.warn('[GardenRoom] 找不到 World/Props'); return null; }
        return props.getComponent(GardenRoom) ?? props.addComponent(GardenRoom);
    }

    private plots: GardenPlot[] = [];
    private player: Node | null = null;
    private active: GardenPlot | null = null;

    onLoad() {
        GardenRoom.instance = this;
        GameArt.preload();
        this.player = this.node.getChildByName('Player');

        this.buildPlots();
        this.buildDoor();
        TownFolk.ensure(FENCE_WALK, 2);   // 柵欄外經過的村民（路窄，兩個就夠熱鬧）

        GameArt.onReady(() => { if (this.isValid) this.applyBackground(); });
        this.applyBackground();
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }

    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (GardenRoom.instance === this) GardenRoom.instance = null;
    }

    update() {
        // 只讓最近的一塊花圃亮提示，免得站在中間時四塊一起冒字
        const p = this.player;
        if (!p) return;
        let best: GardenPlot | null = null, bestDist = REACH;
        for (const plot of this.plots) {
            const d = Vec3.distance(p.position, plot.node.position);
            if (d < bestDist) { bestDist = d; best = plot; }
        }
        if (best !== this.active) {
            this.active?.showHint(false);
            this.active = best;
        }
        this.active?.showHint(!UIState.modalOpen);
    }

    // ---- 場景組裝 ----

    /** 背景圖在執行期塞給 Ground（避免手工做 spriteFrame 的 meta）。 */
    private applyBackground() {
        const ground = find('Canvas/World/Ground');
        const frame = GameArt.garden();
        if (!ground || !frame) return;
        const sp = ground.getComponent(Sprite);
        if (sp) sp.spriteFrame = frame;
        ground.getComponent(UITransform)?.setContentSize(frame.rect.width, frame.rect.height);
    }

    private buildPlots() {
        for (let i = 0; i < PLOT_COUNT; i++) {
            const node = new Node('Plot' + i);
            node.layer = this.node.layer;
            this.node.addChild(node);
            const p = plotPos(i);
            node.setPosition(p.x, p.y, 0);
            const plot = node.addComponent(GardenPlot);
            plot.index = i;
            this.plots.push(plot);
        }
    }

    private buildDoor() {
        const node = new Node('ShopDoor');
        node.layer = this.node.layer;
        this.node.addChild(node);
        node.setPosition(GARDEN_TO_SHOP.x, GARDEN_TO_SHOP.y, 0);
        node.addComponent(UITransform).setContentSize(80, 40);
        const door = node.addComponent(SceneDoor);
        door.targetScene = 'shop';
        door.hintText = '回到店裡';
    }

    // ---- 操作：一顆 E 鍵，看花圃現在是什麼狀態決定做什麼 ----

    private onKeyDown(e: EventKeyboard) {
        if (e.keyCode !== KeyCode.KEY_E || UIState.modalOpen) return;
        const plot = this.active;
        if (!plot) return;

        const v = Garden.view(plot.index);
        const anim = this.player?.getComponent(CharacterAnimator);
        const faceX = this.player ? plot.node.position.x - this.player.position.x : 0;

        if (v.dead) {
            if (Garden.clear(plot.index)) plot.popup('清掉了枯枝');
        } else if (v.empty) {
            const seed = this.firstSeedInBag();
            if (!seed) { plot.popup('沒有種子…'); return; }
            if (Inventory.ensure()?.remove(seed, 1) && Garden.plant(plot.index, seed)) {
                anim?.playOneShot(GameArt.pickFrames(), 0.7, faceX, true);
                plot.popup(`種下 ${seed}`);
            }
        } else if (v.ripe) {
            const got = Garden.harvest(plot.index);
            if (got) {
                Inventory.ensure()?.add(got.name, got.count);
                Quests.record('gather', got.name, got.count);
                anim?.playOneShot(GameArt.pickFrames(), 0.9, faceX, true);
                plot.popup(`＋${got.name} ×${got.count}`);
            }
        } else {
            if (Garden.water(plot.index)) {
                anim?.playOneShot(GameArt.waterFrames(), 0.9, faceX, true);
                plot.popup('澆好水了');
            } else {
                plot.popup('救不回來了…');
            }
        }
        plot.refresh();
    }

    /** 背包裡第一種有的花種子。 */
    private firstSeedInBag(): string {
        for (const f of FLOWERS) {
            if (Inventory.countOf(f.seed) > 0) return f.seed;
        }
        return '';
    }
}

/**
 * 一塊花圃：底下是土壤磚（澆過水就換成深色那張），上面長花。
 * 花畫成子節點，因為 Cocos 先畫父節點自己再畫子節點 —— 這樣花才會蓋在土上面。
 */
@ccclass('GardenPlot')
export class GardenPlot extends Component {
    index = 0;

    private soil: Sprite | null = null;
    private plant: Node | null = null;
    private plantSprite: Sprite | null = null;
    private hint: Node | null = null;
    private hintLabel: Label | null = null;
    private lastKey = '';

    onLoad() {
        const ut = this.node.getComponent(UITransform) ?? this.node.addComponent(UITransform);
        ut.setAnchorPoint(0.5, 0.5);
        this.soil = this.node.addComponent(Sprite);
        this.soil.sizeMode = Sprite.SizeMode.CUSTOM;
        this.soil.type = Sprite.Type.SIMPLE;

        this.plant = new Node('plant');
        this.plant.layer = this.node.layer;
        this.node.addChild(this.plant);
        const put = this.plant.addComponent(UITransform);
        put.setAnchorPoint(0.5, 0);
        this.plant.setPosition(0, -6, 0);      // 從磚面偏下一點長出來
        this.plantSprite = this.plant.addComponent(Sprite);
        this.plantSprite.sizeMode = Sprite.SizeMode.CUSTOM;
        this.plantSprite.type = Sprite.Type.SIMPLE;

        this.buildHint();
        GameArt.onReady(() => { if (this.isValid) this.refresh(true); });
        this.refresh(true);
    }

    update() {
        this.refresh();   // 時間會讓花自己長大 / 枯萎，所以每幀比對一次狀態
    }

    /** 依 Garden 的狀態重畫。狀態沒變就什麼都不做。 */
    refresh(force = false) {
        const v = Garden.view(this.index);
        const key = `${v.art}|${v.stage}|${v.wilting}|${v.wet}|${v.empty}`;
        if (key === this.lastKey && !force) return;
        this.lastKey = key;

        const soilFrame = GameArt.soil(v.wet);
        if (this.soil && soilFrame) {
            this.soil.spriteFrame = soilFrame;
            this.node.getComponent(UITransform)?.setContentSize(
                soilFrame.rect.width * PLOT_SCALE, soilFrame.rect.height * PLOT_SCALE);
        }

        const frame = v.empty ? null : GameArt.flower(v.art, v.stage, v.wilting);
        if (this.plant && this.plantSprite) {
            this.plant.active = !!frame;
            if (frame) {
                this.plantSprite.spriteFrame = frame;
                this.plant.getComponent(UITransform)?.setContentSize(
                    frame.rect.width * FLOWER_SCALE, frame.rect.height * FLOWER_SCALE);
            }
        }
        if (this.hintLabel) this.hintLabel.string = this.hintText(v);
    }

    private hintText(v: ReturnType<typeof Garden.view>): string {
        if (v.dead) return '按 E 清理';
        if (v.empty) return '按 E 種下';
        if (v.ripe) return '按 E 採收';
        return '按 E 澆水';
    }

    showHint(on: boolean) {
        if (this.hint) this.hint.active = on;
    }

    /** 操作完在花圃上方冒一行字，往上飄再淡出。 */
    popup(text: string) {
        const n = new Node('pop');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.setPosition(0, 30, 0);
        n.addComponent(UITransform).setContentSize(180, 24);
        const lb = n.addComponent(Label);
        lb.string = text;
        lb.fontSize = 17;
        lb.color = new Color(255, 246, 214, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        const op = n.addComponent(UIOpacity);
        tween(n).by(1.0, { position: new Vec3(0, 34, 0) }).start();
        tween(op).delay(0.35).to(0.65, { opacity: 0 }).call(() => n.destroy()).start();
    }

    private buildHint() {
        const n = new Node('hint');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.setPosition(0, 54, 0);
        n.addComponent(UITransform).setContentSize(96, 26);
        const g = n.addComponent(Graphics);
        g.fillColor = new Color(30, 26, 22, 200);
        g.rect(-48, -13, 96, 26);
        g.fill();
        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(92, 24);
        const lb = t.addComponent(Label);
        lb.string = '按 E 種下';
        lb.fontSize = 15;
        lb.color = new Color(245, 240, 230, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        this.hintLabel = lb;
        n.active = false;
        this.hint = n;
    }
}
