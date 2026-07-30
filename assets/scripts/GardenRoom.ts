import { _decorator, Component, Node, UITransform, Sprite,
         Vec3, input, Input, EventKeyboard, KeyCode, find } from 'cc';
import { GameArt } from './GameArt';
import { Garden } from './Garden';
import { Inventory } from './Inventory';
import { UIState } from './UIState';
import { CharacterAnimator } from './CharacterAnimator';
import { SceneDoor } from './SceneDoor';
import { GardenPlot } from './GardenPlot';
import { TownFolk } from './TownFolk';
import { Quests } from './Quests';
import { FLOWERS, PLOT_COUNT, plotPos,
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
