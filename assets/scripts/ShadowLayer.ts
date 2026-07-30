import { _decorator, Component, Node, UITransform, Graphics, Color, Vec3, find } from 'cc';
const { ccclass } = _decorator;

/**
 * 角色腳下的影子（女巫主角、店裡的顧客、街上的村民都用這個）。
 *
 * ⚠️ 影子**不能**做成角色節點的子節點 —— Cocos 的繪製順序是「先父節點自己、再子節點」，
 * 掛成子節點會蓋在角色身上。所以改成在 World 底下插一層 `Shadows`，位置排在 **Props 之前**
 * （四個場景的 World 都是 `Ground →（Roads）→ Props`），於是影子畫在地面/路面之上、
 * 所有角色與道具之下；夜晚也會跟著 DayNightTint 一起變暗，不用另外處理。
 *
 * 用法：`ShadowLayer.follow(node, width)` —— 之後每幀自動跟著那個節點的位置畫一個扁橢圓。
 * 同一個節點重複呼叫＝更新大小（美術非同步載入時，尺寸確定後再叫一次就好）。
 * 節點被銷毀（顧客離場、換場景）會自動從清單移除，呼叫端不用收尾。
 */

const COLOR = new Color(24, 22, 30, 95);   // 柔和的深色，不用純黑免得太重
const RX_RATIO = 0.36;                      // 橢圓半寬 ÷ 角色寬
const RY_RATIO = 0.125;                     // 橢圓半高 ÷ 角色寬（壓扁＝俯視角地面）

interface Caster { node: Node; rx: number; ry: number; }

@ccclass('ShadowLayer')
export class ShadowLayer extends Component {
    static instance: ShadowLayer | null = null;

    /** 建立（或取得）影子層。插在 World 底下、Props 之前。 */
    static ensure(): ShadowLayer | null {
        if (ShadowLayer.instance && ShadowLayer.instance.isValid) return ShadowLayer.instance;
        const world = find('Canvas/World');
        if (!world) { console.warn('[ShadowLayer] 找不到 Canvas/World'); return null; }
        // 場景裡已經有一層就接手（別多生一層 —— 兩層疊起來影子會變兩倍黑）
        let node = world.getChildByName('Shadows');
        if (!node) {
            node = new Node('Shadows');
            node.layer = world.layer;
            world.addChild(node);
            const props = world.getChildByName('Props');
            if (props) node.setSiblingIndex(props.getSiblingIndex());   // 排在 Props 前面＝畫在角色下方
        }
        // ⚠️ instance 要在這裡就設好：addComponent 之後 onLoad 不一定已經跑過，
        // 只靠 onLoad 設的話，下一個呼叫 ensure() 的人會看到 null 而再生一層。
        const layer = node.getComponent(ShadowLayer) ?? node.addComponent(ShadowLayer);
        ShadowLayer.instance = layer;
        return layer;
    }

    /** 讓某個角色節點腳下出現影子；width＝角色在畫面上的寬度（像素）。 */
    static follow(target: Node, width: number): void {
        ShadowLayer.ensure()?.add(target, width);
    }

    private g: Graphics | null = null;
    private ut: UITransform | null = null;
    private casters: Caster[] = [];
    private tmp = new Vec3();

    onLoad() {
        ShadowLayer.instance = this;
        // ⚠️ addComponent 的型別是 T|null，strict 下要用 ! 收尾，否則整包 build 會失敗
        this.ut = this.addComponent(UITransform)!;
        this.g = this.addComponent(Graphics)!;
        this.g.fillColor = COLOR;
    }

    onDestroy() {
        if (ShadowLayer.instance === this) ShadowLayer.instance = null;
    }

    /** 登記一個投影者；同一個節點再叫一次＝更新大小。 */
    add(target: Node, width: number): void {
        const rx = Math.max(4, width * RX_RATIO);
        const ry = Math.max(2, width * RY_RATIO);
        for (const c of this.casters) {
            if (c.node === target) { c.rx = rx; c.ry = ry; return; }
        }
        this.casters.push({ node: target, rx, ry });
    }

    update() {
        const g = this.g;
        if (!g || !this.ut) return;
        g.clear();
        for (let i = this.casters.length - 1; i >= 0; i--) {
            const c = this.casters[i];
            if (!c.node || !c.node.isValid) { this.casters.splice(i, 1); continue; }
            // 角色錨點在腳底 → 世界座標就是落腳點；換算到影子層的座標系再畫
            this.ut.convertToNodeSpaceAR(c.node.worldPosition, this.tmp);
            g.ellipse(this.tmp.x, this.tmp.y + c.ry * 0.6, c.rx, c.ry);
        }
        g.fill();
    }
}
