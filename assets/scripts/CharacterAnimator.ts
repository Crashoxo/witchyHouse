import { _decorator, Component, Sprite, SpriteFrame, Vec3 } from 'cc';
import { GameArt } from './GameArt';
const { ccclass, property } = _decorator;

/**
 * 走路動畫。
 *
 * 判斷方式是「這一幀節點有沒有移動」，所以完全不用改 PlayerController ——
 * 任何會移動節點的東西（之後的 NPC 也一樣）掛上去就會動。
 *
 * 走路的圖是側面、朝左，所以往右走時把 scale.x 翻成負的。
 * 待機圖是正面，翻面沒有意義（黑貓會跳到另一邊去），所以停下來時轉回正的。
 *
 * 另外提供 `playOneShot()` 讓別的腳本插播一段動作動畫（例如 GatherTree 採集時
 * 的彎腰→捏起→起身）。播放期間走路/待機不搶畫面；玩家一移動就自動取消。
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

    // 插播動畫（採集等）
    private shot: SpriteFrame[] = [];
    private shotTimer = -1;      // <0 ＝ 沒在插播
    private shotDur = 0;

    onLoad() {
        this.sprite = this.getComponent(Sprite);
        this.prev.set(this.node.position);
        GameArt.preload();
    }

    /**
     * 插播一段一次性動作動畫（等分幀、播完回到走路/待機）。
     * @param frames 動畫幀（空陣列＝不播）
     * @param dur    總長度（秒）
     * @param faceX  面向：>0 朝右、<0 朝左、0 維持原朝向
     * @param front  正面圖（施法、待機那種）＝一律不翻面，翻了貓會跑到另一邊
     */
    playOneShot(frames: SpriteFrame[], dur = 0.9, faceX = 0, front = false) {
        if (!this.sprite || frames.length === 0) return;
        this.shot = frames;
        this.shotDur = Math.max(0.1, dur);
        this.shotTimer = 0;
        const s = this.node.scale;
        if (front) {
            if (s.x < 0) this.node.setScale(-s.x, s.y, s.z);
        } else if (faceX !== 0) {   // 側面圖畫的是朝左，朝右要翻面
            const want = faceX > 0 ? -Math.abs(s.x) : Math.abs(s.x);
            if (want !== s.x) this.node.setScale(want, s.y, s.z);
        }
        this.sprite.spriteFrame = this.shot[0];
    }

    /** 現在是不是正在插播動作動畫。 */
    get busy(): boolean { return this.shotTimer >= 0; }

    /** 用 lateUpdate：PlayerController 是在 update 裡移動角色的，這裡才讀得到這一幀的位移 */
    lateUpdate(dt: number) {
        if (!this.sprite) return;

        const p = this.node.position;
        const dx = p.x - this.prev.x;
        const moving = dx !== 0 || p.y !== this.prev.y;
        this.prev.set(p);

        // 插播中：走路/待機讓位，玩家一動就取消（不然採集動作會卡住畫面）
        if (this.shotTimer >= 0) {
            if (moving) {
                this.shotTimer = -1;
            } else {
                this.shotTimer += dt;
                if (this.shotTimer >= this.shotDur) {
                    this.shotTimer = -1;
                } else {
                    const i = Math.min(this.shot.length - 1,
                                       Math.floor(this.shotTimer / this.shotDur * this.shot.length));
                    this.sprite.spriteFrame = this.shot[i];
                    return;
                }
            }
        }

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
