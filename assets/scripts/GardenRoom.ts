import { _decorator, Component, Node, UITransform, Sprite,
         Vec3, input, Input, EventKeyboard, KeyCode, find } from 'cc';
import { GameArt } from './GameArt';
import { Garden } from './Garden';
import { Inventory } from './Inventory';
import { UIState } from './UIState';
import { CharacterAnimator } from './CharacterAnimator';
import { SceneDoor } from './SceneDoor';
import { GardenPlot } from './GardenPlot';
import { SeedPicker } from './SeedPicker';
import { TownFolk } from './TownFolk';
import { Quests } from './Quests';
import { plotPos, FENCE_WALK, GARDEN_TO_SHOP } from './data/garden';
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
/** 澆花器壺口相對女巫腳底的位置（見 spoutPos 的算法；未翻面時壺在她左手邊）。 */
const SPOUT_DX = (22 - 110.5) * 0.35;      // ≈ -31
const SPOUT_DY = (196 - 166) * 0.35;       // ≈ +10.5

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
        // 只做出已開墾的那幾塊；其餘是荒地，要在店裡升級「花圃」才開得出來。
        // （升級在店裡進行，再走進花園時這裡就會重建，所以不用即時刷新。）
        for (const i of Garden.unlockedPlots()) {
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
        // ⚠️ 門預設 200px 內按 E 就走 —— 但花圃離這道門也才 200px 出頭，站在最靠近
        // 房子那塊花圃前按 E 種花時，人離門只有約 150px，門會跟著收到同一個 E 把人
        // 送回店裡。縮到剛好比 autoRange 大一點：提示照樣會冒，但按 E 不會隔空觸發，
        // 而且走上去自動過圖那條路本來就還在。
        door.interactRange = 90;
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
            // 有哪幾種種子讓玩家自己挑（面板是 modal，挑完才回來種）
            if (SeedPicker.seedsInBag().length === 0) { plot.popup('沒有種子…'); return; }
            SeedPicker.ensure()?.open(seed => this.plantSeed(plot, seed));
        } else if (v.ripe) {
            const got = Garden.harvest(plot.index);
            if (got) {
                Inventory.ensure()?.add(got.name, got.count);
                Quests.record('gather', got.name, got.count);
                anim?.playOneShot(GameArt.pickFrames(), 0.9, faceX, true);
                plot.popup(`＋${got.name} ×${got.count}`);
            }
        } else {
            // 澆水壺升級後一次澆得到旁邊幾塊（Garden.waterTargets 算範圍）。
            // 空地也會被澆濕（土變深色），但只有「有種東西」的才算進訊息裡。
            let n = 0;
            const watered: number[] = [];
            for (const i of Garden.waterTargets(plot.index)) {
                const planted = !Garden.view(i).empty;
                if (Garden.water(i)) { watered.push(i); if (planted) n++; }
            }
            if (n > 0) {
                // ⚠️ 澆水這段要翻面（front=false）：圖裡的澆花器畫在她左手邊，朝右邊的
                // 花圃澆時整張翻過來，壺口才會對著花圃（施法那種正面圖才不翻）。
                anim?.playOneShot(GameArt.waterFrames(), 0.9, faceX, false);
                plot.popup(n > 1 ? `澆了 ${n} 塊` : '澆好水了');
                // 灑水特效：水從她手上澆花器的壺口出來，澆到的每一塊都來一份
                const spout = this.spoutPos();
                for (const i of watered) {
                    const p = this.plotAt(i);
                    p?.playWater(spout.x - p.node.position.x, spout.y - p.node.position.y);
                }
            } else {
                plot.popup('救不回來了…');
            }
            for (const p of this.plots) p.refresh();   // 波及到的花圃也要跟著換濕土
        }
        plot.refresh();
    }

    /** 挑好種子之後真的種下去（面板已經關掉了）。 */
    private plantSeed(plot: GardenPlot, seed: string) {
        if (!Garden.view(plot.index).empty) return;        // 挑的時候狀態變了就算了
        if (!Inventory.ensure()?.remove(seed, 1)) return;
        if (!Garden.plant(plot.index, seed)) {
            Inventory.ensure()?.add(seed, 1);              // 種不下去要把種子還回去
            return;
        }
        const anim = this.player?.getComponent(CharacterAnimator);
        const faceX = this.player ? plot.node.position.x - this.player.position.x : 0;
        anim?.playOneShot(GameArt.pickFrames(), 0.7, faceX, true);
        plot.popup(`種下 ${seed}`);
        plot.refresh();
    }

    /**
     * 澆花器壺口現在在哪（Props 座標，跟花圃同一層）。
     *
     * 女巫的圖是 221×196 的畫布、錨點在腳底正中、節點 scale 0.35。澆水第 3 幀（把壺
     * 傾倒的那格）壺嘴量到在畫布的 (22, 166) → 距離腳底 ((22-110.5), (196-166)) 像素，
     * 乘上 0.35 就是節點座標的偏移。朝右時整個節點是翻面的（scale.x < 0），x 要跟著鏡射。
     */
    private spoutPos(): Vec3 {
        const p = this.player;
        if (!p) return new Vec3();
        const flip = p.scale.x < 0 ? -1 : 1;
        return new Vec3(p.position.x + flip * SPOUT_DX, p.position.y + SPOUT_DY, 0);
    }

    private plotAt(index: number): GardenPlot | null {
        for (const p of this.plots) if (p.index === index) return p;
        return null;
    }
}
