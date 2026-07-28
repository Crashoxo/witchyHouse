import { _decorator, Component, Node, UITransform, UIOpacity, Graphics, Color, Vec3, Label,
         find } from 'cc';
import { SceneDoor } from './SceneDoor';
import { UIState } from './UIState';
const { ccclass } = _decorator;

/**
 * 傳送點發光（仿 RO 的傳送陣）：讓不熟遊戲的人一眼看出「這裡可以走過去」。
 *
 * 本作有兩種換場景的方式，過去都沒有遠看得到的提示：
 *   ① 門（SceneDoor）  ── 走近才冒出「按 E 進入」，遠看只是一棟房子。
 *   ② 走出地圖邊界      ── 森林右側→城鎮、城鎮左側→森林、店裡下方→城鎮，
 *                          完全沒有任何視覺，不知道的人根本不會往那邊走。
 * 這裡替兩者都加上會呼吸的青色光暈：門是地上的光圈，邊界是沿著那一側的光幕，
 * 並在玩家靠近邊界時顯示「前往 ○○」指示牌（箭頭用 Graphics 畫，避免缺字）。
 *
 * 畫在哪：同 LampGlow —— 夜色色板（DayNightTint）是整片蓋在世界上把場景壓暗的，
 * 所以光要畫在色板**之上**才不會被夜色吃掉，於是在 Canvas 另開一層，插在色板上方、
 * HUD 下方。世界會隨鏡頭捲動，故每幀把光暈用世界座標對回門／邊界的位置。
 *
 * 安裝同 Clock/LampGlow：PlayerController.onLoad 呼叫 ensure()，把玩家節點與
 * 「走到哪一側會換場景」一起傳進來（免得反過來 import PlayerController 形成循環相依）。
 * 門則是自己從場景樹掃出來的 → 整套零場景改動，之後在 Cocos 新增的門也會自動發光。
 */

const GLOW = { r: 168, g: 214, b: 255 };          // 冷青色：跟城鎮路燈的暖黃區隔＝「這是通道」
const SCENE_LABEL: Record<string, string> = { main: '森林', town: '城鎮', shop: '店裡', brew: '房間' };

const DOOR_RX = 58;          // 門口地上光圈的半徑
const DOOR_RY = 23;          // 壓扁＝貼在地上（俯視角）
const DOOR_SPREAD = 26;      // 門口光點左右散開範圍
const BEAM_H = 96;           // 門口往上的光柱高度（讓遠處也看得到）
const BEAM_W = 40;
const BAND_DEPTH = 110;      // 邊界光幕往地圖內延伸多深
const EDGE_SPREAD = 300;     // 邊界光點沿著邊線散在玩家附近多大範圍
const SPARK_RISE = 78;       // 光點往上飄多高
const SPARK_PER_DOOR = 5;
const SPARK_PER_EDGE = 10;
const LABEL_RANGE = 460;     // 玩家離邊界多近才顯示指示牌
// 指示牌擺在邊界往內多遠：要比玩家「發現邊界時的站位」更靠邊，否則會蓋在角色身上
const LABEL_INSET = 56;

interface Spark {
    node: Node;
    op: UIOpacity;
    ax: number;      // 沿著散開軸的位移
    rise: number;    // 上飄進度 0..1
    speed: number;
}

interface Portal {
    op: UIOpacity;
    src: Node;                  // 對位用的世界節點（門節點，或邊界用的 Ground）
    srcUT: UITransform | null;
    local: Vec3;                // 相對 src 錨點的位移（邊界＝那條邊的中點）
    sparks: Spark[];
    inward: number;             // 邊界往地圖內的方向（±1）；門＝0
    vertical: boolean;          // 邊界是左右側（光幕直的）還是上下側
    spread: number;             // 光點散開範圍的一半
    base: number;               // 濃度基準（0..1）
}

@ccclass('PortalGlow')
export class PortalGlow extends Component {
    static instance: PortalGlow | null = null;

    /**
     * @param player      玩家節點（判斷遠近、指示牌跟著玩家沿邊線移動）
     * @param edgeScene   走到邊界會換去的場景名（空字串＝這張地圖沒有邊界出口）
     * @param edgeSide    哪一側：left / right / top / bottom
     */
    static ensure(player: Node | null, edgeScene: string, edgeSide: string): PortalGlow | null {
        if (PortalGlow.instance && PortalGlow.instance.isValid) return PortalGlow.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[PortalGlow] 找不到 Canvas'); return null; }
        const node = new Node('PortalGlow');
        node.layer = canvas.layer;
        canvas.addChild(node);
        // 疊在夜色色板之上（沒有色板就放在 World 之上）、HUD 之下。
        const tint = canvas.getChildByName('DayNightTint');
        const world = canvas.getChildByName('World');
        const base = tint ?? world;
        node.setSiblingIndex(base ? base.getSiblingIndex() + 1 : 1);

        const comp = node.addComponent(PortalGlow);
        comp.setup(player, edgeScene, edgeSide);
        return comp;
    }

    private layerUT: UITransform | null = null;
    private player: Node | null = null;
    private portals: Portal[] = [];
    private label: Node | null = null;
    private labelPortal: Portal | null = null;
    private time = 0;
    private tmp = new Vec3();
    private tmpB = new Vec3();

    onLoad() { PortalGlow.instance = this; }
    onDestroy() { if (PortalGlow.instance === this) PortalGlow.instance = null; }

    private setup(player: Node | null, edgeScene: string, edgeSide: string) {
        this.player = player;
        this.layerUT = this.getComponent(UITransform) ?? this.addComponent(UITransform);

        const world = find('Canvas/World');
        if (world) this.collectDoors(world);
        if (edgeScene) this.buildEdge(edgeScene, edgeSide);
    }

    /** 掃出場景裡所有掛了 SceneDoor 的節點，各給一圈地上光暈。 */
    private collectDoors(root: Node) {
        const door = root.getComponent(SceneDoor);
        if (door && door.targetScene) this.buildDoor(root);
        for (const child of root.children) this.collectDoors(child);
    }

    private buildDoor(doorNode: Node) {
        const root = new Node('doorGlow');
        root.layer = this.node.layer;
        root.addComponent(UITransform);
        this.node.addChild(root);

        // 地上的光圈（壓扁的同心橢圓，中心疊得越多越亮）
        const gn = new Node('ring');
        gn.layer = this.node.layer;
        gn.addComponent(UITransform);
        const g = gn.addComponent(Graphics);
        const rings = 10;
        for (let i = rings; i >= 1; i--) {
            const k = i / rings;
            g.fillColor = new Color(GLOW.r, GLOW.g, GLOW.b, 30);
            g.ellipse(0, 0, DOOR_RX * k, DOOR_RY * k);
            g.fill();
        }
        // 中間再疊一圈偏白的亮核心
        for (let i = 4; i >= 1; i--) {
            const k = i / 4;
            g.fillColor = new Color(226, 244, 255, 34);
            g.ellipse(0, 0, DOOR_RX * 0.42 * k, DOOR_RY * 0.42 * k);
            g.fill();
        }
        // 往上的光柱（下寬上窄）：房間另一頭／街上遠處也看得到這裡是入口
        const steps = 8;
        for (let i = 0; i < steps; i++) {
            const t = i / steps;
            const hgt = BEAM_H * (1 - t);
            const wid = BEAM_W * (1 - t * 0.55);
            g.fillColor = new Color(GLOW.r, GLOW.g, GLOW.b, 20);
            g.rect(-wid / 2, 0, wid, hgt);
            g.fill();
        }
        root.addChild(gn);

        const p: Portal = {
            op: root.addComponent(UIOpacity),
            src: doorNode,
            srcUT: doorNode.getComponent(UITransform),
            local: new Vec3(0, 0, 0),
            sparks: [],
            inward: 0,
            vertical: false,
            spread: DOOR_SPREAD,
            base: 1,
        };
        this.addSparks(p, root, SPARK_PER_DOOR, 4);
        this.portals.push(p);
    }

    /** 沿著會換場景的那一側畫一道光幕（亮度在邊線上最強，往地圖內淡出）。 */
    private buildEdge(targetScene: string, side: string) {
        const ground = this.findGround();
        const ut = ground?.getComponent(UITransform);
        if (!ground || !ut) { console.warn('[PortalGlow] 找不到 Ground，略過邊界光幕'); return; }

        const w = ut.contentSize.width, h = ut.contentSize.height;
        const ax = ut.anchorPoint.x, ay = ut.anchorPoint.y;
        // Ground 的可走矩形（相對它自己的錨點）
        const left = -ax * w, right = (1 - ax) * w;
        const bottom = -ay * h, top = (1 - ay) * h;
        const midX = (left + right) / 2, midY = (bottom + top) / 2;

        const vertical = side === 'left' || side === 'right';
        // 往地圖內是哪個方向：右／上側要往負向，左／下側往正向
        const inward = (side === 'right' || side === 'top') ? -1 : 1;
        const half = vertical ? h / 2 : w / 2;

        let local: Vec3;
        if (side === 'right') local = new Vec3(right, midY, 0);
        else if (side === 'left') local = new Vec3(left, midY, 0);
        else if (side === 'top') local = new Vec3(midX, top, 0);
        else local = new Vec3(midX, bottom, 0);

        const root = new Node('edgeGlow');
        root.layer = this.node.layer;
        root.addComponent(UITransform);
        this.node.addChild(root);

        const gn = new Node('band');
        gn.layer = this.node.layer;
        gn.addComponent(UITransform);
        const g = gn.addComponent(Graphics);
        const layers = 12;
        for (let i = layers; i >= 1; i--) {
            const d = BAND_DEPTH * (i / layers);
            g.fillColor = new Color(GLOW.r, GLOW.g, GLOW.b, 15);
            // 每層都貼著邊線、往內延伸不同深度 → 疊出「邊線最亮、往內淡出」
            if (vertical) g.rect(inward > 0 ? 0 : -d, -half, d, half * 2);
            else          g.rect(-half, inward > 0 ? 0 : -d, half * 2, d);
            g.fill();
        }
        root.addChild(gn);

        const p: Portal = {
            op: root.addComponent(UIOpacity),
            src: ground,
            srcUT: ut,
            local,
            sparks: [],
            inward,
            vertical,
            spread: half,
            base: 0.85,
        };
        this.addSparks(p, root, SPARK_PER_EDGE, 4);
        this.portals.push(p);

        this.labelPortal = p;
        this.label = this.buildLabel(SCENE_LABEL[targetScene] ?? targetScene, vertical, inward);
    }

    private addSparks(p: Portal, root: Node, count: number, radius: number) {
        for (let i = 0; i < count; i++) {
            const n = new Node('spark');
            n.layer = this.node.layer;
            n.addComponent(UITransform);
            const g = n.addComponent(Graphics);
            g.fillColor = new Color(232, 246, 255, 255);
            g.circle(0, 0, radius);
            g.fill();
            root.addChild(n);

            const s: Spark = {
                node: n,
                op: n.addComponent(UIOpacity),
                ax: 0,
                rise: i / count,          // 錯開，不要一起飄
                speed: 0.28 + Math.random() * 0.22,
            };
            s.ax = this.pickAx(p, 0);
            p.sparks.push(s);
        }
    }

    /** 指示牌：方框＋「前往 ○○」＋往外指的箭頭（箭頭用畫的，避免字型缺 ↑↓←→）。 */
    private buildLabel(sceneName: string, vertical: boolean, inward: number): Node {
        const boxW = 140, boxH = 36, arrow = 13;

        const n = new Node('PortalLabel');
        n.layer = this.node.layer;
        n.addComponent(UITransform).setContentSize(boxW, boxH);
        this.node.addChild(n);

        const g = n.addComponent(Graphics);
        g.fillColor = new Color(16, 26, 40, 214);
        g.strokeColor = new Color(GLOW.r, GLOW.g, GLOW.b, 235);
        g.lineWidth = 2;
        g.rect(-boxW / 2, -boxH / 2, boxW, boxH);     // 一律方框（本專案 UI 慣例）
        g.fill(); g.stroke();

        // 箭頭指向地圖外＝玩家該走的方向（inward 是往內，所以取反）
        const out = -inward;
        g.fillColor = new Color(GLOW.r, GLOW.g, GLOW.b, 245);
        if (vertical) {
            const tipX = out * (boxW / 2 + arrow + 4), baseX = out * (boxW / 2 + 4);
            g.moveTo(tipX, 0); g.lineTo(baseX, arrow); g.lineTo(baseX, -arrow);
        } else {
            const tipY = out * (boxH / 2 + arrow + 4), baseY = out * (boxH / 2 + 4);
            g.moveTo(0, tipY); g.lineTo(arrow, baseY); g.lineTo(-arrow, baseY);
        }
        g.close(); g.fill();

        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(boxW - 12, boxH);
        const lb = t.addComponent(Label);
        lb.string = '前往' + sceneName;
        lb.fontSize = 20;
        lb.color = new Color(238, 248, 255, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;

        n.active = false;
        return n;
    }

    /** 光點要散在哪：門＝門口左右；邊界＝玩家附近那一段邊線（不然整條邊只有零星幾點）。 */
    private pickAx(p: Portal, playerAlong: number): number {
        if (p.inward === 0) return (Math.random() * 2 - 1) * p.spread;
        const a = playerAlong + (Math.random() * 2 - 1) * EDGE_SPREAD;
        return Math.min(Math.max(a, -p.spread), p.spread);
    }

    /** 從玩家那層往上找名叫 "Ground" 的節點（同 PlayerController.computeBounds）。 */
    private findGround(): Node | null {
        let n: Node | null = this.player?.parent ?? null;
        let ground: Node | null = null;
        while (n && !ground) { ground = n.getChildByName('Ground'); n = n.parent; }
        return ground ?? find('Canvas/World/Ground');
    }

    update(dt: number) {
        if (!this.layerUT) return;
        // 開著面板／對話時整個世界都停著，光暈也跟著凍結（同時鐘暫停的處理）
        if (UIState.modalOpen) { if (this.label) this.label.active = false; return; }

        this.time += dt;
        const pulse = 0.62 + 0.38 * Math.sin(this.time * 2.1);   // 呼吸

        let playerWorld: Vec3 | null = null;
        if (this.player && this.player.isValid) playerWorld = this.player.getWorldPosition(this.tmpB);

        for (const p of this.portals) {
            if (!p.src.isValid) continue;
            // 門／邊界的世界座標 → 本層座標（鏡頭在捲動，每幀都要對位）
            if (p.srcUT) p.srcUT.convertToWorldSpaceAR(p.local, this.tmp);
            else p.src.getWorldPosition(this.tmp);
            const wx = this.tmp.x, wy = this.tmp.y;
            this.layerUT.convertToNodeSpaceAR(this.tmp, this.tmp);
            p.op.node.setPosition(this.tmp);
            p.op.opacity = Math.round(255 * p.base * pulse);

            // 玩家沿著邊線的位置（光點與指示牌都跟著他移動，才看得到）
            let along = 0;
            if (playerWorld) along = p.vertical ? playerWorld.y - wy : playerWorld.x - wx;

            for (const s of p.sparks) {
                s.rise += dt * s.speed;
                if (s.rise >= 1) { s.rise -= 1; s.ax = this.pickAx(p, along); }
                const up = s.rise * SPARK_RISE;
                if (p.inward === 0)       s.node.setPosition(s.ax, up, 0);
                else if (p.vertical)      s.node.setPosition(p.inward * 26, s.ax + up, 0);
                else                      s.node.setPosition(s.ax, p.inward * 26 + up, 0);
                // 淡入快、淡出慢
                const f = s.rise < 0.25 ? s.rise / 0.25 : (1 - s.rise) / 0.75;
                s.op.opacity = Math.round(215 * f);
            }

            // 指示牌：只在玩家靠近那一側時出現，並跟著他沿邊線滑動
            if (p === this.labelPortal && this.label) {
                if (!playerWorld) { this.label.active = false; continue; }
                const gap = p.vertical ? Math.abs(playerWorld.x - wx) : Math.abs(playerWorld.y - wy);
                const near = gap <= LABEL_RANGE;
                this.label.active = near;
                if (near) {
                    const clamped = Math.min(Math.max(along, -p.spread + 60), p.spread - 60);
                    if (p.vertical) this.label.setPosition(this.tmp.x + p.inward * LABEL_INSET, this.tmp.y + clamped, 0);
                    else            this.label.setPosition(this.tmp.x + clamped, this.tmp.y + p.inward * LABEL_INSET, 0);
                }
            }
        }
    }
}
