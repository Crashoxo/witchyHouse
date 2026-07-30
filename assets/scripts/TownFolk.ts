import { _decorator, Component, Node, Vec3, find } from 'cc';
import { GameArt } from './GameArt';
import { VillagerAnim } from './VillagerAnim';
import { UIState } from './UIState';
import { TimeSystem } from './TimeSystem';
const { ccclass } = _decorator;

/**
 * 城鎮街上走動的村民（town.scene 用）。
 *
 * 跟店裡的顧客是同一批人（resources/villagers ＋ VillagerAnim），在鎮上晃來晃去：
 * 走到一個路點 → 停一下 → 再挑下一個。**路點直接讀 town.scene 的 `World/Roads`
 * 子節點位置**，所以他們一定走在真的有路的地方；之後在 Cocos 裡搬動或增減路面，
 * 村民的動線會自動跟著改，不用回來改程式。
 *
 * 安裝方式同 LampGlow：由 PlayerController.onLoad 在 town 場景呼叫 `ensure()`，
 * 元件直接掛到既有的 Props 節點上（村民生成為 Props 的子節點 → 吃 YSortLayer
 * 的前後遮擋），**完全不用改場景檔**。
 */
@ccclass('TownFolk')
export class TownFolk extends Component {
    static instance: TownFolk | null = null;

    /** 白天街上幾個人；入夜後只剩 NIGHT_COUNT 個（其他人回家了）。 */
    static readonly DAY_COUNT = 6;
    static readonly NIGHT_COUNT = 2;

    /** 掛到 town.scene 既有的 Props 節點上（重複呼叫安全）。 */
    static ensure(): TownFolk | null {
        if (TownFolk.instance && TownFolk.instance.isValid) return TownFolk.instance;
        const props = find('Canvas/World/Props');
        if (!props) { console.warn('[TownFolk] 找不到 World/Props'); return null; }
        return props.getComponent(TownFolk) ?? props.addComponent(TownFolk);
    }

    private waypoints: Vec3[] = [];
    private folk: Walker[] = [];
    private retry = 0;

    onLoad() {
        TownFolk.instance = this;
        GameArt.preload();
        this.collectWaypoints();
    }

    onDestroy() {
        if (TownFolk.instance === this) TownFolk.instance = null;
    }

    update(dt: number) {
        if (UIState.modalOpen) return;      // 開著選單/對話時整個鎮上靜止（同時鐘暫停）
        if (this.waypoints.length < 2) return;

        // 人數：白天熱鬧、晚上剩零星幾個。美術還沒載完就先不生。
        const want = TimeSystem.isNight ? TownFolk.NIGHT_COUNT : TownFolk.DAY_COUNT;
        if (this.folk.length < want && GameArt.ready) {
            this.retry += dt;
            if (this.retry > 0.8) { this.retry = 0; this.spawn(); }
        } else if (this.folk.length > want) {
            const bye = this.folk.pop();
            bye?.node.destroy();
        }

        for (const w of this.folk) this.step(w, dt);
    }

    // ---- 路點 ----

    /** 從 World/Roads 的子節點位置收集路點（Roads 與 Props 都在 World 原點、無縮放）。 */
    private collectWaypoints() {
        const roads = find('Canvas/World/Roads');
        if (!roads) { console.warn('[TownFolk] 找不到 World/Roads，鎮上不生村民'); return; }
        for (const r of roads.children) {
            if (r.name.indexOf('puddle') >= 0) continue;   // 別站在水窪裡
            const p = r.position;
            this.waypoints.push(new Vec3(p.x + roads.position.x, p.y + roads.position.y, 0));
        }
    }

    private pickWaypoint(): Vec3 {
        const p = this.waypoints[Math.floor(Math.random() * this.waypoints.length)];
        // 加點偏移，免得所有人都走同一條線
        return new Vec3(p.x + (Math.random() - 0.5) * 90, p.y + (Math.random() - 0.5) * 60, 0);
    }

    // ---- 村民 ----

    private spawn() {
        const names = GameArt.villagerNames();
        if (names.length === 0) return;
        // 盡量不要跟街上現有的人重複
        const taken: Record<string, boolean> = {};
        for (const w of this.folk) taken[w.who] = true;
        const free = names.filter(n => !taken[n]);
        const pool = free.length ? free : names;
        const who = pool[Math.floor(Math.random() * pool.length)];

        const node = new Node('Folk-' + who);
        node.layer = this.node.layer;
        this.node.addChild(node);
        node.setPosition(this.pickWaypoint());
        const anim = node.addComponent(VillagerAnim);
        anim.init(who);

        this.folk.push({
            node, anim, who,
            target: this.pickWaypoint(),
            speed: 50 + Math.random() * 30,
            pause: Math.random() * 2,
        });
    }

    /** 推進一位村民：停頓中就站著，否則往目標走，到了就再挑一個。 */
    private step(w: Walker, dt: number) {
        if (w.pause > 0) {
            w.pause -= dt;
            w.anim.setMove(0, 0);
            return;
        }
        const p = w.node.position;
        const dx = w.target.x - p.x, dy = w.target.y - p.y;
        const dist = Math.hypot(dx, dy);
        const stepLen = w.speed * dt;
        if (dist <= stepLen) {
            w.node.setPosition(w.target.x, w.target.y, 0);
            w.anim.setMove(0, 0);
            w.target = this.pickWaypoint();
            w.pause = 1.5 + Math.random() * 2.5;
            return;
        }
        w.node.setPosition(p.x + dx / dist * stepLen, p.y + dy / dist * stepLen, 0);
        w.anim.setMove(dx / dist, dy / dist);
    }
}

interface Walker {
    node: Node;
    anim: VillagerAnim;
    who: string;
    target: Vec3;
    speed: number;
    pause: number;   // 還要站多久（秒）
}
