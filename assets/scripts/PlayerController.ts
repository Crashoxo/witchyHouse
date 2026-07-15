import { _decorator, Component, Vec2, input, Input, EventKeyboard, KeyCode,
         instantiate, Prefab } from 'cc';
import { SpellProjectile } from './SpellProjectile';
const { ccclass, property } = _decorator;

/**
 * 俯視角魔女角色控制：
 *   WASD / 方向鍵 = 八方向移動
 *   J 或 空白鍵   = 往目前面向施放魔法彈
 */
@ccclass('PlayerController')
export class PlayerController extends Component {
    @property moveSpeed = 200;                            // 移動速度（像素/秒）
    @property(Prefab) spellPrefab: Prefab | null = null;  // 拖入 Spell 預製體

    private dir = new Vec2(0, 0);      // 目前移動方向
    private facing = new Vec2(1, 0);   // 最後面向（施法方向）
    private keys = new Set<number>();

    onLoad() {
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        input.on(Input.EventType.KEY_UP, this.onKeyUp, this);
    }

    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        input.off(Input.EventType.KEY_UP, this.onKeyUp, this);
    }

    private onKeyDown(e: EventKeyboard) {
        this.keys.add(e.keyCode);
        if (e.keyCode === KeyCode.KEY_J || e.keyCode === KeyCode.SPACE) this.cast();
    }
    private onKeyUp(e: EventKeyboard) { this.keys.delete(e.keyCode); }

    update(dt: number) {
        const k = this.keys;
        const x = (k.has(KeyCode.KEY_D) || k.has(KeyCode.ARROW_RIGHT) ? 1 : 0)
                - (k.has(KeyCode.KEY_A) || k.has(KeyCode.ARROW_LEFT)  ? 1 : 0);
        const y = (k.has(KeyCode.KEY_W) || k.has(KeyCode.ARROW_UP)    ? 1 : 0)
                - (k.has(KeyCode.KEY_S) || k.has(KeyCode.ARROW_DOWN)  ? 1 : 0);
        this.dir.set(x, y);

        if (this.dir.lengthSqr() > 0) {
            this.dir.normalize();
            this.facing.set(this.dir);                       // 記住最後移動方向當作面向
            const p = this.node.position;
            this.node.setPosition(
                p.x + this.dir.x * this.moveSpeed * dt,
                p.y + this.dir.y * this.moveSpeed * dt,
                p.z);
        }
    }

    private cast() {
        if (!this.spellPrefab) return;
        const spell = instantiate(this.spellPrefab);
        this.node.parent!.addChild(spell);                   // 生在角色的同一層
        spell.setPosition(this.node.position);
        spell.getComponent(SpellProjectile)?.fire(this.facing);
    }
}
