import { _decorator, Component, Sprite, SpriteFrame, Vec3 } from 'cc';
const { ccclass, property } = _decorator;

/**
 * 走路動畫。
 *
 * 判斷方式是「這一幀節點有沒有移動」，所以完全不用改 PlayerController ——
 * 任何會移動節點的東西（之後的 NPC 也一樣）掛上去就會動。
 *
 * 走路的圖是側面、朝左，所以往右走時把 scale.x 翻成負的。
 * 待機圖是正面，翻面沒有意義（黑貓會跳到另一邊去），所以停下來時轉回正的。
 */
@ccclass('CharacterAnimator')
export class CharacterAnimator extends Component {
    @property(SpriteFrame) idle: SpriteFrame | null = null;   // 待機圖（正面）
    @property([SpriteFrame]) walk: SpriteFrame[] = [];        // 走路循環（側面朝左）
    @property walkFps = 10;                                   // 每秒播幾格

    private sprite: Sprite | null = null;
    private prev = new Vec3();
    private timer = 0;
    private frame = 0;

    onLoad() {
        this.sprite = this.getComponent(Sprite);
        this.prev.set(this.node.position);
    }

    /** 用 lateUpdate：PlayerController 是在 update 裡移動角色的，這裡才讀得到這一幀的位移 */
    lateUpdate(dt: number) {
        if (!this.sprite) return;

        const p = this.node.position;
        const dx = p.x - this.prev.x;
        const moving = dx !== 0 || p.y !== this.prev.y;
        this.prev.set(p);

        const s = this.node.scale;

        if (!moving || this.walk.length === 0) {
            this.timer = 0;
            this.frame = 0;
            if (this.idle) this.sprite.spriteFrame = this.idle;
            if (s.x < 0) this.node.setScale(-s.x, s.y, s.z);   // 正面圖不翻面
            return;
        }

        if (dx !== 0) {                          // 純上下走時維持原本朝向
            const want = dx > 0 ? -Math.abs(s.x) : Math.abs(s.x);
            if (want !== s.x) this.node.setScale(want, s.y, s.z);
        }

        this.timer += dt;
        const step = 1 / Math.max(1, this.walkFps);
        while (this.timer >= step) {
            this.timer -= step;
            this.frame = (this.frame + 1) % this.walk.length;
        }
        this.sprite.spriteFrame = this.walk[this.frame];
    }
}
