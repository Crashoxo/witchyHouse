import { _decorator, Component, Node, Sprite, Color, input, Input,
         EventKeyboard, KeyCode, Vec3 } from 'cc';
import { Inventory } from './Inventory';
const { ccclass, property } = _decorator;

/**
 * 採集樹：玩家走近、按 E 採集 → 產出材料、進入冷卻（樹變暗）、一段時間後長回來。
 *
 * 掛在「每一棵樹」的節點上。玩家參照會自動從同一層（World 底下）
 * 名叫 "Player" 的節點抓，所以複製出來的樹不用一個一個拖。
 *
 * 目前「產出材料」只是印到 Console；之後有背包系統時，把 gather() 裡
 * 的 console.log 換成「加進背包」即可。
 */
@ccclass('GatherTree')
export class GatherTree extends Component {
    @property gatherRange = 120;    // 玩家離多近才採得到（像素）
    @property cooldown = 5;         // 採完幾秒後長回來
    @property itemName = '木材';     // 這棵樹產出什麼材料

    private player: Node | null = null;
    private sprite: Sprite | null = null;
    private original = new Color();  // 記住原本的顏色，冷卻結束後還原
    private ready = true;            // true = 可採，false = 冷卻中
    private timer = 0;

    onLoad() {
        this.sprite = this.getComponent(Sprite);
        if (this.sprite) this.original.set(this.sprite.color);
        // 樹和 Player 都是 World 的子節點 → 直接找兄弟節點
        this.player = this.node.parent?.getChildByName('Player') ?? null;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }

    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }

    private onKeyDown(e: EventKeyboard) {
        if (e.keyCode !== KeyCode.KEY_E) return;
        if (!this.ready || !this.player) return;
        // 兩者都是 World 的子節點 → 比 local position 的距離即可（不受相機捲動影響）
        if (Vec3.distance(this.player.position, this.node.position) > this.gatherRange) return;
        this.gather();
    }

    private gather() {
        // 放進背包（沒有背包 UI 時會自動在 Canvas 底下生一個）
        Inventory.ensure()?.add(this.itemName);
        console.log(`採集到 ${this.itemName} x1`);
        this.ready = false;
        this.timer = 0;
        if (this.sprite) this.sprite.color = new Color(80, 80, 80, 255); // 變暗＝採光了
    }

    update(dt: number) {
        if (this.ready) return;
        this.timer += dt;
        if (this.timer >= this.cooldown) {
            this.ready = true;
            if (this.sprite) this.sprite.color = this.original; // 長回原本的綠色
        }
    }
}
