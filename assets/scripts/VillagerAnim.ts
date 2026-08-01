import { _decorator, Component, Sprite, SpriteFrame, UITransform } from 'cc';
import { GameArt, VillagerDir } from './GameArt';
import { ShadowLayer } from './ShadowLayer';
const { ccclass } = _decorator;

/**
 * 村民走路動畫：把 `resources/villagers/*.png`（4 幀 × 3 面向）接到一個節點上。
 * 店裡的顧客（CustomerManager）和城鎮街上走動的村民（TownFolk）共用這支。
 *
 * 用法：生一個空節點 → `addComponent(VillagerAnim).init('frog')` → 每幀餵
 * `setMove(dx, dy)`（不動就餵 0,0），面向與播放交給它。
 *
 * 面向：走路表只有下／側／上三列，側面一律朝左 → 往右走時把節點 scale.x 取負
 * （同女巫 CharacterAnimator 的作法）。⚠️ 節點被翻面時，掛在它底下的對話泡要自己
 * 反轉回來（見 CustomerManager.showBubble），否則文字會變鏡像。
 *
 * 美術是非同步載入的：init() 當下可能還沒好，會用 GameArt.onReady 補上。
 */
@ccclass('VillagerAnim')
export class VillagerAnim extends Component {
    /** 每秒播幾幀（走路循環）。 */
    static readonly FPS = 8;
    /**
     * 原圖縮到畫面上的比例。0.8 時身高約 69~88px —— 比女巫的 69px 高一點點，
     * 大人站在小女巫旁邊本來就該高一些（0.7 看起來太小隻）。
     */
    static readonly SCALE = 0.8;

    private villager = '';
    private scale = VillagerAnim.SCALE;
    private sprite: Sprite | null = null;
    private ut: UITransform | null = null;
    private frames: SpriteFrame[] = [];
    private dir = VillagerDir.DOWN;
    private faceRight = false;
    private moving = false;
    private timer = 0;
    private idx = -1;

    /** 顯示高度（像素）—— 對話泡要擺在頭頂時用。美術還沒載入時先給個估計值。 */
    get displayHeight(): number {
        return this.ut ? this.ut.contentSize.height : 70;
    }

    /**
     * 指定要演哪位村民。name 取自 `GameArt.villagerNames()`。
     * @param scale 原圖縮放比（預設 VillagerAnim.SCALE）
     */
    init(name: string, scale = VillagerAnim.SCALE): void {
        this.villager = name;
        this.scale = scale;
        this.ut = this.node.getComponent(UITransform) ?? this.node.addComponent(UITransform);
        this.ut.setAnchorPoint(0.5, 0);     // 錨點在腳底 → 吃 YSortLayer 的前後遮擋
        this.sprite = this.node.getComponent(Sprite) ?? this.node.addComponent(Sprite);
        this.sprite.sizeMode = Sprite.SizeMode.CUSTOM;
        this.sprite.type = Sprite.Type.SIMPLE;
        this.applyDir(VillagerDir.DOWN, true);
        if (!this.frames.length) GameArt.onReady(() => {
            if (this.isValid) this.applyDir(this.dir, true);
        });
    }

    /**
     * 餵目前的移動方向（不必正規化；0,0 ＝站著）。
     * 橫向為主就走側面（往右走翻面），否則依上下決定背面/正面。
     */
    setMove(dx: number, dy: number): void {
        this.moving = Math.abs(dx) > 0.001 || Math.abs(dy) > 0.001;
        if (!this.moving) return;
        if (Math.abs(dx) >= Math.abs(dy)) {
            this.applyDir(VillagerDir.SIDE);
            this.setFacing(dx > 0);
        } else {
            this.applyDir(dy > 0 ? VillagerDir.UP : VillagerDir.DOWN);
        }
    }

    /** 站定時要面向哪邊（不播動畫，只換圖）。 */
    faceTo(dx: number, dy: number): void {
        this.setMove(dx, dy);
        this.moving = false;
    }

    update(dt: number) {
        if (!this.frames.length) return;
        if (!this.moving) { this.showFrame(0); this.timer = 0; return; }
        this.timer += dt;
        this.showFrame(Math.floor(this.timer * VillagerAnim.FPS) % this.frames.length);
    }

    // ---- 內部 ----

    private applyDir(dir: number, force = false): void {
        if (dir === this.dir && !force && this.frames.length) return;
        this.dir = dir;
        const frames = GameArt.villagerFrames(this.villager, dir);
        if (!frames.length) return;
        this.frames = frames;
        this.idx = -1;                       // 換面向 → 強制重畫一次
        const r = frames[0].rect;
        this.ut?.setContentSize(r.width * this.scale, r.height * this.scale);
        ShadowLayer.follow(this.node, r.width * this.scale);   // 腳下的影子（尺寸確定後才叫得準）
        this.showFrame(this.moving ? Math.floor(this.timer * VillagerAnim.FPS) % frames.length : 0);
    }

    private setFacing(right: boolean): void {
        if (right === this.faceRight) return;
        this.faceRight = right;
        const s = this.node.scale;
        this.node.setScale(right ? -Math.abs(s.x) : Math.abs(s.x), s.y, s.z);
    }

    private showFrame(i: number): void {
        if (i === this.idx || !this.sprite || !this.frames.length) return;
        this.idx = i;
        this.sprite.spriteFrame = this.frames[i];
    }
}
