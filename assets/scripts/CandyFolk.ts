import { _decorator, Component, Node, UITransform, Sprite, Vec3, find } from 'cc';
import { GameArt } from './GameArt';
import { UIState } from './UIState';
import { ShadowLayer } from './ShadowLayer';
import { CANDY_CRITTERS, CANDY_WALK, CANDY_CROWD } from './data/candy';
const { ccclass } = _decorator;

/**
 * 糖果鎮街上晃來晃去的小東西（軟糖鱷、芽苗）。
 *
 * 跟 TownFolk 的差別：城鎮村民有 4×3 的走路表（VillagerAnim 播動畫），這裡的素材
 * **只有一張站姿**，所以改用「移動時上下輕輕彈跳」表現走路，往右走時把節點翻面。
 * 之後若補了走路表，換成 VillagerAnim 即可。
 *
 * 掛在 candy.scene 既有的 Props 節點上（由 CandyTown 安裝），生出來的小東西是 Props
 * 的子節點 → 吃 YSortLayer 的前後遮擋。
 */

interface Critter {
    node: Node;
    target: Vec3;
    speed: number;
    wait: number;       // 到點後停多久
    bob: number;        // 彈跳相位
    baseY: number;
}

@ccclass('CandyFolk')
export class CandyFolk extends Component {
    static instance: CandyFolk | null = null;

    static ensure(): CandyFolk | null {
        if (CandyFolk.instance && CandyFolk.instance.isValid) return CandyFolk.instance;
        const props = find('Canvas/World/Props');
        if (!props) { console.warn('[CandyFolk] 找不到 World/Props'); return null; }
        const c = props.getComponent(CandyFolk) ?? props.addComponent(CandyFolk);
        CandyFolk.instance = c;
        return c;
    }

    private critters: Critter[] = [];

    onLoad() {
        CandyFolk.instance = this;
        GameArt.preload();
        GameArt.onReady(() => { if (this.isValid) this.spawnAll(); });
        this.spawnAll();
    }

    onDestroy() {
        if (CandyFolk.instance === this) CandyFolk.instance = null;
    }

    private spawnAll() {
        if (this.critters.length >= CANDY_CROWD) return;
        for (let i = this.critters.length; i < CANDY_CROWD; i++) {
            const def = CANDY_CRITTERS[i % CANDY_CRITTERS.length];
            const frame = GameArt.candy(def.art);
            if (!frame) return;                        // 美術還沒載好，等 onReady 再來
            const n = new Node('critter-' + def.art);
            n.layer = this.node.layer;
            this.node.addChild(n);
            const start = CANDY_WALK[i % CANDY_WALK.length];
            n.setPosition(start.x, start.y, 0);
            const ut = n.addComponent(UITransform);
            ut.setAnchorPoint(0.5, 0);                 // 錨點在腳底 → 吃 YSort
            const w = (frame.rect.width || frame.originalSize.width) * def.scale;
            const h = (frame.rect.height || frame.originalSize.height) * def.scale;
            ut.setContentSize(w, h);
            const sp = n.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM;
            sp.trim = false;
            sp.spriteFrame = frame;
            ShadowLayer.follow(n, w);

            this.critters.push({
                node: n,
                target: this.pickTarget(start.x, start.y),
                speed: 26 + Math.random() * 22,
                wait: Math.random() * 2,
                bob: Math.random() * 6,
                baseY: start.y,
            });
        }
    }

    /** 隨機挑一個路點（不要挑到自己現在站的那個）。 */
    private pickTarget(x: number, y: number): Vec3 {
        for (let i = 0; i < 6; i++) {
            const p = CANDY_WALK[Math.floor(Math.random() * CANDY_WALK.length)];
            if (Math.abs(p.x - x) + Math.abs(p.y - y) > 80) return new Vec3(p.x, p.y, 0);
        }
        const p = CANDY_WALK[0];
        return new Vec3(p.x, p.y, 0);
    }

    update(dt: number) {
        if (UIState.modalOpen) return;                 // 開著視窗時整條街靜止
        for (const c of this.critters) {
            if (!c.node.isValid) continue;
            if (c.wait > 0) { c.wait -= dt; continue; }

            const p = c.node.position;
            const dx = c.target.x - p.x, dy = c.target.y - c.baseY;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 6) {                            // 到了：休息一下再挑下一個點
                c.baseY = c.target.y;
                c.node.setPosition(c.target.x, c.target.y, 0);
                c.target = this.pickTarget(c.target.x, c.target.y);
                c.wait = 1 + Math.random() * 3;
                continue;
            }
            const step = c.speed * dt;
            const nx = p.x + dx / dist * step;
            c.baseY += dy / dist * step;
            c.bob += dt * 9;
            // 走路的上下彈跳（只有在移動時才彈，停下來就站定）
            c.node.setPosition(nx, c.baseY + Math.abs(Math.sin(c.bob)) * 3, 0);

            const s = c.node.scale;
            const want = dx > 0 ? -Math.abs(s.x) : Math.abs(s.x);   // 圖朝左，往右走翻面
            if (want !== s.x) c.node.setScale(want, s.y, s.z);
        }
    }
}
