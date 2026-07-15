import { _decorator, Component, Vec2, Vec3 } from 'cc';
const { ccclass, property } = _decorator;

/**
 * 魔法彈：被 PlayerController 生成後，呼叫 fire(dir) 決定飛行方向。
 * 之後要加「碰到敵人造成傷害」時，也是在這支腳本裡處理碰撞。
 */
@ccclass('SpellProjectile')
export class SpellProjectile extends Component {
    @property speed = 400;      // 飛行速度（像素/秒）
    @property lifeTime = 2;     // 幾秒後自動消失，避免無限累積

    private velocity = new Vec3();
    private age = 0;

    /** 由玩家角色呼叫，dir = 玩家當下面向 */
    fire(dir: Vec2) {
        this.velocity.set(dir.x, dir.y, 0);
        if (this.velocity.lengthSqr() === 0) this.velocity.set(1, 0, 0); // 保底：預設往右
        this.velocity.normalize().multiplyScalar(this.speed);
    }

    update(dt: number) {
        const p = this.node.position;
        this.node.setPosition(p.x + this.velocity.x * dt, p.y + this.velocity.y * dt, p.z);
        this.age += dt;
        if (this.age >= this.lifeTime) this.node.destroy();
    }
}
