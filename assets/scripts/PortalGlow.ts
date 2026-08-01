import { _decorator, Component, Node, UITransform, UIOpacity, Graphics, Color, Vec3, Label,
         find, director } from 'cc';
import { SceneDoor } from './SceneDoor';
import { UIState } from './UIState';
import { edgePortalOf, DEFAULT_INSET } from './data';
const { ccclass } = _decorator;

/**
 * 傳送點發光（仿 RO 的傳送陣）：讓不熟遊戲的人一眼看出「這裡可以走過去」。
 *
 * 本作有兩種換場景的方式，過去都沒有遠看得到的提示：
 *   ① 門（SceneDoor）  ── 走近才冒出提示，遠看只是一棟房子。
 *   ② 走出地圖邊界      ── 森林東側→城鎮、城鎮西側→森林、店裡下方→城鎮，
 *                          完全沒有任何視覺，不知道的人根本不會往那邊走。
 * 兩者都畫上會呼吸的青色光暈：地上的光圈＋往上的光柱＋飄起的光點，
 * 邊界的那個還多一塊「前往 ○○」指示牌（箭頭用 Graphics 畫，避免字型缺 ↑↓←→）。
 *
 * ⚠️ 邊界傳送**只有那一個點會過去**（見 PlayerController.onReachEdge 與 data/portals.ts），
 * 所以光暈畫得比實際的門略小一點 —— 寧可「看得到的一定走得過去」，
 * 也不要讓玩家推著一個發光處卻沒反應。
 *
 * 畫在哪：同 LampGlow —— 夜色色板（DayNightTint）是整片蓋在世界上把場景壓暗的，
 * 所以光要畫在色板**之上**才不會被夜色吃掉，於是在 Canvas 另開一層，插在色板上方、
 * HUD 下方。世界會隨鏡頭捲動，故每幀把光暈用世界座標對回門／傳送點的位置。
 *
 * 安裝同 Clock/LampGlow：PlayerController.onLoad 呼叫 ensure()，把玩家節點與
 * 「走到哪一側會換場景」一起傳進來（免得反過來 import PlayerController 形成循環相依）。
 * 門則是自己從場景樹掃出來的 → 整套零場景改動，之後在 Cocos 新增的門也會自動發光。
 */

const GLOW = { r: 168, g: 214, b: 255 };          // 冷青色：跟城鎮路燈的暖黃區隔＝「這是通道」
const SCENE_LABEL: Record<string, string> = { main: '森林', town: '城鎮', shop: '店裡', brew: '房間', garden: '後花園' };

const DOOR_RX = 58;          // 門口地上光圈的半徑
const DOOR_RY = 23;          // 壓扁＝貼在地上（俯視角）
const EDGE_RX = 78;          // 邊界傳送點的光圈大一些（那是一道門不是門檻）
const EDGE_RY = 30;
// 光圈往地圖內縮多少由 data/portals.ts 的 inset 決定（想貼著邊界就調小，會被切到一點）
const BEAM_H = 96;           // 往上的光柱高度（讓遠處也看得到）
const BEAM_W = 40;
const SPARK_RISE = 78;       // 光點往上飄多高
const SPARK_PER_PORTAL = 5;
const LABEL_RANGE = 460;     // 玩家離傳送點多近才顯示指示牌
// 太近反而藏起來：牌子在光柱上方，玩家站到傳送點前面時剛好被牌子蓋住頭。
// 走到這麼近的人早就看到牌子了，藏掉不影響引導。
const LABEL_NEAR = 130;
const LABEL_SHIFT = 54;      // 左右側的牌子往地圖內挪，免得被畫面邊緣切掉
// 牌子（含箭頭）從中心到外緣要留的距離：傳送點越貼著邊界，牌子就得往內挪越多
const LABEL_EDGE_CLEAR = 91;

interface Spark {
    node: Node;
    op: UIOpacity;
    ax: number;      // 左右散開的位移
    rise: number;    // 上飄進度 0..1
    speed: number;
}

interface Portal {
    op: UIOpacity;
    src: Node;                  // 對位用的世界節點（門節點，或邊界用的 Ground）
    srcUT: UITransform | null;
    local: Vec3;                // 相對 src 錨點的位移
    sparks: Spark[];
    spread: number;             // 光點左右散開範圍的一半
    label: Node | null;         // 只有邊界傳送點有「前往 ○○」
}

@ccclass('PortalGlow')
export class PortalGlow extends Component {
    static instance: PortalGlow | null = null;

    /**
     * @param player      玩家節點（判斷遠近，決定指示牌出不出現）
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
        if (edgeScene) this.buildEdgePortal(edgeScene, edgeSide);
    }

    /** 掃出場景裡所有掛了 SceneDoor 的節點，各給一個門口光暈。 */
    private collectDoors(root: Node) {
        const door = root.getComponent(SceneDoor);
        if (door && door.targetScene) {
            // 光圈畫在「門口」而不是節點原點 —— 整棟房子當一個節點時，原點在房子正中央
            this.buildPortal(root, root.getComponent(UITransform),
                             new Vec3(door.doorX, door.doorY, 0),
                             DOOR_RX, DOOR_RY, null, '');
        }
        for (const child of root.children) this.collectDoors(child);
    }

    /**
     * 邊界上那個唯一能過去的點。位置來自 data/portals.ts（左右側的邊＝y、上下側＝x），
     * 跟 PlayerController.onReachEdge 判定用的是同一份資料，所以光暈一定畫在真的能走的地方。
     */
    private buildEdgePortal(targetScene: string, side: string) {
        const ground = this.findGround();
        const ut = ground?.getComponent(UITransform);
        if (!ground || !ut) { console.warn('[PortalGlow] 找不到 Ground，略過邊界傳送點'); return; }

        const gate = edgePortalOf(director.getScene()?.name ?? '');

        const w = ut.contentSize.width, h = ut.contentSize.height;
        const ax = ut.anchorPoint.x, ay = ut.anchorPoint.y;
        // Ground 的可走矩形（相對它自己的錨點）
        const left = -ax * w, right = (1 - ax) * w;
        const bottom = -ay * h, top = (1 - ay) * h;

        const inset = gate.inset ?? DEFAULT_INSET;
        let local: Vec3;
        if (side === 'right')      local = new Vec3(right - inset, gate.at, 0);
        else if (side === 'left')  local = new Vec3(left + inset, gate.at, 0);
        else if (side === 'top')   local = new Vec3(gate.at, top - inset, 0);
        else                       local = new Vec3(gate.at, bottom + inset, 0);

        this.buildPortal(ground, ut, local, EDGE_RX, EDGE_RY,
                         SCENE_LABEL[targetScene] ?? targetScene, side, inset);
    }

    /** 一個傳送點：地上光圈＋亮核心＋往上的光柱＋上飄光點（＋邊界的指示牌）。 */
    private buildPortal(src: Node, srcUT: UITransform | null, local: Vec3,
                        rx: number, ry: number, labelText: string | null, side: string,
                        inset: number = DEFAULT_INSET) {
        const root = new Node('portal');
        root.layer = this.node.layer;
        root.addComponent(UITransform);
        this.node.addChild(root);

        const gn = new Node('glow');
        gn.layer = this.node.layer;
        gn.addComponent(UITransform);
        const g = gn.addComponent(Graphics);

        // 地上的光圈：同心壓扁橢圓，中心疊得越多越亮
        const rings = 10;
        for (let i = rings; i >= 1; i--) {
            const k = i / rings;
            g.fillColor = new Color(GLOW.r, GLOW.g, GLOW.b, 30);
            g.ellipse(0, 0, rx * k, ry * k);
            g.fill();
        }
        // 中間再疊一圈偏白的亮核心
        for (let i = 4; i >= 1; i--) {
            const k = i / 4;
            g.fillColor = new Color(226, 244, 255, 34);
            g.ellipse(0, 0, rx * 0.42 * k, ry * 0.42 * k);
            g.fill();
        }
        // 往上的光柱（下寬上窄）：房間另一頭／街上遠處也看得到這裡是入口
        const steps = 8;
        for (let i = 0; i < steps; i++) {
            const t = i / steps;
            g.fillColor = new Color(GLOW.r, GLOW.g, GLOW.b, 20);
            g.rect(-BEAM_W * (1 - t * 0.55) / 2, 0, BEAM_W * (1 - t * 0.55), BEAM_H * (1 - t));
            g.fill();
        }
        root.addChild(gn);

        const p: Portal = {
            op: root.addComponent(UIOpacity),
            src, srcUT, local,
            sparks: [],
            spread: rx * 0.45,
            label: null,
        };
        this.addSparks(p, root, SPARK_PER_PORTAL);
        // 指示牌掛在傳送點底下 → 跟著一起移動，不用每幀自己對位
        if (labelText) {
            p.label = this.buildLabel(labelText, side, inset);
            root.addChild(p.label);
        }
        this.portals.push(p);
    }

    private addSparks(p: Portal, root: Node, count: number) {
        for (let i = 0; i < count; i++) {
            const n = new Node('spark');
            n.layer = this.node.layer;
            n.addComponent(UITransform);
            const g = n.addComponent(Graphics);
            g.fillColor = new Color(232, 246, 255, 255);
            g.circle(0, 0, 4);
            g.fill();
            root.addChild(n);

            p.sparks.push({
                node: n,
                op: n.addComponent(UIOpacity),
                ax: (Math.random() * 2 - 1) * p.spread,
                rise: i / count,                      // 錯開，不要一起飄
                speed: 0.28 + Math.random() * 0.22,
            });
        }
    }

    /** 指示牌：方框＋「前往 ○○」＋往外指的箭頭（箭頭用畫的，避免字型缺 ↑↓←→）。 */
    private buildLabel(sceneName: string, side: string, inset: number): Node {
        const boxW = 140, boxH = 36, arrow = 13;

        const n = new Node('PortalLabel');
        n.layer = this.node.layer;
        n.addComponent(UITransform).setContentSize(boxW, boxH);
        // 擺在光柱上方；左右側的傳送點貼著畫面邊，牌子要往內挪才不會被切掉。
        // 光圈可以被切（那樣才像邊界上的門），但字被切就看不懂了，所以挪的量要跟著 inset 補。
        const mag = Math.max(LABEL_SHIFT, LABEL_EDGE_CLEAR - inset);
        const shift = side === 'right' ? -mag : (side === 'left' ? mag : 0);
        n.setPosition(shift, BEAM_H + 32, 0);

        const g = n.addComponent(Graphics);
        g.fillColor = new Color(16, 26, 40, 214);
        g.strokeColor = new Color(GLOW.r, GLOW.g, GLOW.b, 235);
        g.lineWidth = 2;
        g.rect(-boxW / 2, -boxH / 2, boxW, boxH);     // 一律方框（本專案 UI 慣例）
        g.fill(); g.stroke();

        // 箭頭指向地圖外＝玩家該走的方向
        g.fillColor = new Color(GLOW.r, GLOW.g, GLOW.b, 245);
        if (side === 'left' || side === 'right') {
            const out = side === 'right' ? 1 : -1;
            const tipX = out * (boxW / 2 + arrow + 4), baseX = out * (boxW / 2 + 4);
            g.moveTo(tipX, 0); g.lineTo(baseX, arrow); g.lineTo(baseX, -arrow);
        } else {
            const out = side === 'top' ? 1 : -1;
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
        if (UIState.modalOpen) {
            for (const p of this.portals) if (p.label) p.label.active = false;
            return;
        }

        this.time += dt;
        const pulse = 0.62 + 0.38 * Math.sin(this.time * 2.1);   // 呼吸

        let playerWorld: Vec3 | null = null;
        if (this.player && this.player.isValid) playerWorld = this.player.getWorldPosition(this.tmpB);

        for (const p of this.portals) {
            if (!p.src.isValid) continue;
            // 傳送點的世界座標 → 本層座標（鏡頭在捲動，每幀都要對位）
            if (p.srcUT) p.srcUT.convertToWorldSpaceAR(p.local, this.tmp);
            else p.src.getWorldPosition(this.tmp);
            const wx = this.tmp.x, wy = this.tmp.y;
            this.layerUT.convertToNodeSpaceAR(this.tmp, this.tmp);
            p.op.node.setPosition(this.tmp);
            p.op.opacity = Math.round(255 * pulse);

            for (const s of p.sparks) {
                s.rise += dt * s.speed;
                if (s.rise >= 1) { s.rise -= 1; s.ax = (Math.random() * 2 - 1) * p.spread; }
                s.node.setPosition(s.ax, s.rise * SPARK_RISE, 0);
                // 淡入快、淡出慢
                const f = s.rise < 0.25 ? s.rise / 0.25 : (1 - s.rise) / 0.75;
                s.op.opacity = Math.round(215 * f);
            }

            if (p.label) {
                let show = false;
                if (playerWorld) {
                    const dx = playerWorld.x - wx, dy = playerWorld.y - wy;
                    const d2 = dx * dx + dy * dy;
                    show = d2 < LABEL_RANGE * LABEL_RANGE && d2 > LABEL_NEAR * LABEL_NEAR;
                }
                p.label.active = show;
            }
        }
    }
}
