import { _decorator, Component, Sprite, SpriteFrame, UITransform, Vec3 } from 'cc';
import { GameArt, WITCH_DIRS, WITCH_SCALE } from './GameArt';
import { ShadowLayer } from './ShadowLayer';
const { ccclass, property } = _decorator;

/**
 * 女巫的走路動畫。
 *
 * 判斷方式是「這一幀節點有沒有移動」，所以完全不用改 PlayerController ——
 * 任何會移動節點的東西掛上去就會動。
 *
 * ── 八方向（2026-08-03）──
 * `GameArt.witchReady()` 為真時走新的 chibi 圖集：每個方向都有自己的站姿與 8 幀走路，
 * **不再翻面**（八個方向都畫好了，翻面反而會把帽子與手上的杖照鏡子），
 * 節點縮放也由這裡統一設成 WITCH_SCALE，所以六個場景檔一個都不用改。
 * 圖集還沒載到（或載失敗）時退回底下 @property 指定的舊圖，走路照樣會動。
 *
 * ── 跑步（2026-08-07）──
 * 新角色八個方向各多了 8 幀跑步。要不要播跑步是**看這一幀移動得多快**算出來的
 * （超過 RUN_SPEED 就換跑步圖），不用 PlayerController 通知 —— 跟上面「靠位移判斷」
 * 同一套想法，之後不管是衝刺、加速道具還是被推著跑，動畫都會自己對。
 *
 * 另外提供 `playOneShot()` 讓別的腳本插播一段動作動畫（採集、施法、澆水）。
 * 播放期間走路/待機不搶畫面；玩家一移動就自動取消。
 */
/**
 * 移動速度超過這個值（像素/秒）就播跑步。
 * PlayerController 走路 200、按住 Shift 衝刺 ×1.7 ＝ 340，取中間值當門檻，
 * 點擊自動尋路（用的是走路速度）就不會誤判成在跑。
 */
const RUN_SPEED = 260;

@ccclass('CharacterAnimator')
export class CharacterAnimator extends Component {
    @property(SpriteFrame) idle: SpriteFrame | null = null;   // 待機圖（舊圖：正面）
    @property([SpriteFrame]) walk: SpriteFrame[] = [];        // 走路循環（舊圖：側面朝左）
    @property walkFps = 10;                                   // 每秒播幾格

    private sprite: Sprite | null = null;
    private prev = new Vec3();
    private timer = 0;
    private frame = 0;
    private dir = 0;              // 目前面向（見 GameArt 的 WitchDir）
    private scaled = false;       // 已依圖集調過節點縮放

    // 插播動畫（採集等）
    private shot: SpriteFrame[] = [];
    private shotTimer = -1;      // <0 ＝ 沒在插播
    private shotDur = 0;

    onLoad() {
        this.sprite = this.getComponent(Sprite);
        this.prev.set(this.node.position);
        GameArt.preload();
    }

    /** 目前面向（0 南、2 東、4 北、6 西；每 45° 一格）。 */
    get facingDir(): number { return this.dir; }

    /**
     * 插播一段一次性動作動畫（等分幀、播完回到走路/待機）。
     * @param frames 動畫幀（空陣列＝不播）
     * @param dur    總長度（秒）
     * @param faceX  面向：>0 朝右、<0 朝左、0 維持原朝向。**只有舊圖會用到**
     *               （新圖的動作幀只有正面，翻面只會讓她背對玩家）
     * @param front  正面圖＝一律不翻面。同樣只有舊圖會用到
     */
    playOneShot(frames: SpriteFrame[], dur = 0.9, faceX = 0, front = false) {
        if (!this.sprite || frames.length === 0) return;
        this.shot = frames;
        this.shotDur = Math.max(0.1, dur);
        this.shotTimer = 0;
        if (!GameArt.witchReady()) {
            const s = this.node.scale;
            if (front) {
                if (s.x < 0) this.node.setScale(-s.x, s.y, s.z);
            } else if (faceX !== 0) {   // 側面圖畫的是朝左，朝右要翻面
                const want = faceX > 0 ? -Math.abs(s.x) : Math.abs(s.x);
                if (want !== s.x) this.node.setScale(want, s.y, s.z);
            }
        }
        this.sprite.spriteFrame = this.shot[0];
    }

    /** 現在是不是正在插播動作動畫。 */
    get busy(): boolean { return this.shotTimer >= 0; }

    /**
     * 位移向量 → 方向索引。0 是南（往下），每 45° 逆時針加一。
     * 圖集的欄序是 south, south-east, east, …，剛好就是這個順序。
     */
    private static dirOf(dx: number, dy: number): number {
        const deg = Math.atan2(dy, dx) * 180 / Math.PI;      // 東＝0、北＝90
        return (Math.round((deg + 90) / 45) % WITCH_DIRS + WITCH_DIRS) % WITCH_DIRS;
    }

    /**
     * 圖集就緒後把節點調成新圖該有的大小（只做一次）。
     *
     * ⚠️ Sprite 一定要改成 **CUSTOM**：場景裡設的是 RAW，而圖集切出來的 SpriteFrame
     * 其 originalSize 是整張圖集（304×583），RAW 會把一小格拉伸成整張那麼大。
     * 同一張圖集的每一格都一樣大，所以量一次就好。
     * 順便重登記影子寬度 —— PlayerController 在 onLoad 量的是舊圖，那時圖集還沒載到。
     */
    private applyWitchScale() {
        if (this.scaled) return;
        const f = GameArt.witchIdle(0);
        if (!f || !this.sprite) return;
        this.scaled = true;
        this.sprite.sizeMode = Sprite.SizeMode.CUSTOM;
        this.node.getComponent(UITransform)?.setContentSize(f.rect.width, f.rect.height);
        this.node.setScale(WITCH_SCALE, WITCH_SCALE, 1);
        ShadowLayer.follow(this.node, f.rect.width * WITCH_SCALE);
    }

    /** 用 lateUpdate：PlayerController 是在 update 裡移動角色的，這裡才讀得到這一幀的位移 */
    lateUpdate(dt: number) {
        if (!this.sprite) return;

        const p = this.node.position;
        const dx = p.x - this.prev.x;
        const dy = p.y - this.prev.y;
        const moving = dx !== 0 || dy !== 0;
        this.prev.set(p);

        const eight = GameArt.witchReady();
        if (eight) this.applyWitchScale();
        if (moving) this.dir = CharacterAnimator.dirOf(dx, dy);

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

        // 跑得夠快就換跑步那組（新圖才有；沒有的話 witchRun 回空陣列，照樣走路）
        const running = eight && moving && dt > 0
            && Math.sqrt(dx * dx + dy * dy) / dt > RUN_SPEED
            && GameArt.witchRun(this.dir).length > 0;
        const walk = eight ? (running ? GameArt.witchRun(this.dir) : GameArt.witchWalk(this.dir)) : this.walk;
        const idle = eight ? GameArt.witchIdle(this.dir) : this.idle;
        const s = this.node.scale;

        if (!moving || walk.length === 0) {
            this.timer = 0;
            this.frame = 0;
            if (idle) this.sprite.spriteFrame = idle;
            // 舊圖的待機是正面圖，翻面沒有意義（黑貓會跳到另一邊去）
            if (!eight && s.x < 0) this.node.setScale(-s.x, s.y, s.z);
            return;
        }

        if (!eight && dx !== 0) {                // 舊圖：側面朝左，往右走翻面（純上下走時維持原朝向）
            const want = dx > 0 ? -Math.abs(s.x) : Math.abs(s.x);
            if (want !== s.x) this.node.setScale(want, s.y, s.z);
        }

        // 新圖一輪 8 幀（舊圖 5 幀），照場景裡的 10fps 播會顯得拖 → 八方向固定 13fps，
        // 跑步再快一點（16fps），腳步才跟得上速度
        this.timer += dt;
        const step = 1 / (eight ? (running ? 16 : 13) : Math.max(1, this.walkFps));
        while (this.timer >= step) {
            this.timer -= step;
            this.frame = (this.frame + 1) % walk.length;
        }
        this.sprite.spriteFrame = walk[this.frame % walk.length];
    }
}
