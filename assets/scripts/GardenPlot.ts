import { _decorator, Component, Node, UITransform, Sprite, Label, Color, Graphics,
         Vec3, tween, UIOpacity } from 'cc';
import { GameArt } from './GameArt';
import { Garden } from './Garden';
import { PLOT_SCALE, FLOWER_SCALE } from './data/garden';
const { ccclass } = _decorator;

/**
 * 一塊花圃：底下是土壤磚（澆過水就換成深色那張），上面長花。
 * 花畫成子節點，因為 Cocos 先畫父節點自己再畫子節點 —— 這樣花才會蓋在土上面。
 */
@ccclass('GardenPlot')
export class GardenPlot extends Component {
    index = 0;

    private soil: Sprite | null = null;
    private plant: Node | null = null;
    private plantSprite: Sprite | null = null;
    private hint: Node | null = null;
    private hintLabel: Label | null = null;
    private dryMark: Node | null = null;
    private lastKey = '';

    onLoad() {
        const ut = this.node.getComponent(UITransform) ?? this.node.addComponent(UITransform);
        ut.setAnchorPoint(0.5, 0.5);
        this.soil = this.node.addComponent(Sprite);
        this.soil.sizeMode = Sprite.SizeMode.CUSTOM;
        this.soil.type = Sprite.Type.SIMPLE;

        this.plant = new Node('plant');
        this.plant.layer = this.node.layer;
        this.node.addChild(this.plant);
        const put = this.plant.addComponent(UITransform);
        put.setAnchorPoint(0.5, 0);
        this.plant.setPosition(0, -6, 0);      // 從磚面偏下一點長出來
        this.plantSprite = this.plant.addComponent(Sprite);
        this.plantSprite.sizeMode = Sprite.SizeMode.CUSTOM;
        this.plantSprite.type = Sprite.Type.SIMPLE;

        this.buildHint();
        this.buildDryMark();
        GameArt.onReady(() => { if (this.isValid) this.refresh(true); });
        this.refresh(true);
    }

    update() {
        this.refresh();   // 時間會讓花自己長大 / 枯萎，所以每幀比對一次狀態
    }

    /** 依 Garden 的狀態重畫。狀態沒變就什麼都不做。 */
    refresh(force = false) {
        const v = Garden.view(this.index);
        const thirsty = Garden.needsWater(this.index);
        const key = `${v.art}|${v.stage}|${v.wilting}|${v.wet}|${v.empty}|${thirsty}`;
        if (key === this.lastKey && !force) return;
        this.lastKey = key;

        // 快沒水了就在花圃上冒個小標，不用走近也看得到哪一塊該澆
        if (this.dryMark) this.dryMark.active = thirsty;

        const soilFrame = GameArt.soil(v.wet);
        if (this.soil && soilFrame) {
            this.soil.spriteFrame = soilFrame;
            this.node.getComponent(UITransform)?.setContentSize(
                soilFrame.rect.width * PLOT_SCALE, soilFrame.rect.height * PLOT_SCALE);
        }

        const frame = v.empty ? null : GameArt.flower(v.art, v.stage, v.wilting);
        if (this.plant && this.plantSprite) {
            this.plant.active = !!frame;
            if (frame) {
                this.plantSprite.spriteFrame = frame;
                this.plant.getComponent(UITransform)?.setContentSize(
                    frame.rect.width * FLOWER_SCALE, frame.rect.height * FLOWER_SCALE);
            }
        }
        if (this.hintLabel) this.hintLabel.string = this.hintText(v);
    }

    private hintText(v: ReturnType<typeof Garden.view>): string {
        if (v.dead) return '按 E 清理';
        if (v.empty) return '按 E 種下';
        if (v.ripe) return '按 E 採收';
        return '按 E 澆水';
    }

    showHint(on: boolean) {
        if (this.hint) this.hint.active = on;
    }

    /**
     * 澆水特效：水從女巫那一側的壺口潑成一道弧線灑到土上，落點濺開一圈水花。
     * 全部是程式畫的（Graphics ＋ tween），不需要美術。
     * faceX ＝ 花圃相對玩家的方向（>0 代表玩家在左邊，水就從左邊過來）。
     */
    playWater(sx: number, sy: number) {
        const layer = this.node.layer;
        const side = sx >= 0 ? 1 : -1;             // 壺口在花圃的哪一側
        const DROPS = 14;
        const GAP = 0.028;
        // 澆水動畫第 3 幀（0.45~0.675 秒）才是把壺傾倒的那格，水要那時候才出來
        const START = 0.32;

        for (let i = 0; i < DROPS; i++) {
            const t = i / (DROPS - 1);
            const long = i % 3 === 1;              // 每三滴拉長一條，看起來才像連續的水柱

            const n = new Node('drop');
            n.layer = layer;
            this.node.addChild(n);
            n.setPosition(sx, sy, 0);
            const w = 4, h = long ? 18 : 9;
            n.addComponent(UITransform).setContentSize(w, h);
            const g = n.addComponent(Graphics);
            g.fillColor = long ? new Color(176, 220, 246, 170) : new Color(158, 210, 240, 235);
            g.rect(-w / 2, -h / 2, w, h);
            g.fill();
            const op = n.addComponent(UIOpacity);
            op.opacity = 0;                        // 輪到它之前先藏著，不然會在壺口疊成一坨

            // 落點從近到遠鋪滿土面 —— 水柱像掃過去一樣
            const ex = side * 22 - side * t * 46 + (Math.random() - 0.5) * 6;
            const ey = -6 - Math.random() * 7;
            const midX = sx + (ex - sx) * 0.45;
            const midY = Math.max(sy, ey) + 10;    // 拋物線頂點略高於壺口（拋太高會變噴泉）

            tween(n)
                .delay(START + i * GAP)
                .to(0.15, { position: new Vec3(midX, midY, 0) }, { easing: 'sineOut' })
                .to(0.15, { position: new Vec3(ex, ey, 0) }, { easing: 'sineIn' })
                .call(() => { if (i % 2 === 0) this.splash(ex, ey); })   // 每兩滴濺一次就夠熱鬧
                .start();
            tween(op)
                .delay(START + i * GAP)
                .to(0.04, { opacity: 255 })
                .delay(0.22)
                .to(0.08, { opacity: 0 })
                .call(() => n.destroy())
                .start();
        }
    }

    /** 落點的一圈小水花，擴散後淡出。 */
    private splash(x: number, y: number) {
        const n = new Node('splash');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.setPosition(x, y, 0);
        n.addComponent(UITransform).setContentSize(20, 12);
        const g = n.addComponent(Graphics);
        g.lineWidth = 2;
        g.strokeColor = new Color(186, 224, 246, 220);
        g.ellipse(0, 0, 5, 2.5);
        g.stroke();
        const op = n.addComponent(UIOpacity);
        tween(n).to(0.3, { scale: new Vec3(1.9, 1.9, 1) }, { easing: 'quadOut' }).start();
        tween(op).to(0.3, { opacity: 0 }).call(() => n.destroy()).start();
    }

    /** 操作完在花圃上方冒一行字，往上飄再淡出。 */
    popup(text: string) {
        const n = new Node('pop');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.setPosition(0, 30, 0);
        n.addComponent(UITransform).setContentSize(180, 24);
        const lb = n.addComponent(Label);
        lb.string = text;
        lb.fontSize = 17;
        lb.color = new Color(255, 246, 214, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        const op = n.addComponent(UIOpacity);
        tween(n).by(1.0, { position: new Vec3(0, 34, 0) }).start();
        tween(op).delay(0.35).to(0.65, { opacity: 0 }).call(() => n.destroy()).start();
    }

    /** 「缺水」小標（枯萎前的警告，離很遠也看得到）。 */
    private buildDryMark() {
        const n = new Node('dry');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.setPosition(0, 32, 0);
        n.addComponent(UITransform).setContentSize(58, 22);
        const g = n.addComponent(Graphics);
        g.fillColor = new Color(122, 74, 32, 210);
        g.rect(-29, -11, 58, 22);
        g.fill();
        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(56, 20);
        const lb = t.addComponent(Label);
        lb.string = '缺水';
        lb.fontSize = 14;
        lb.color = new Color(255, 226, 168, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        n.active = false;
        this.dryMark = n;
    }

    private buildHint() {
        const n = new Node('hint');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.setPosition(0, 54, 0);
        n.addComponent(UITransform).setContentSize(96, 26);
        const g = n.addComponent(Graphics);
        g.fillColor = new Color(30, 26, 22, 200);
        g.rect(-48, -13, 96, 26);
        g.fill();
        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(92, 24);
        const lb = t.addComponent(Label);
        lb.string = '按 E 種下';
        lb.fontSize = 15;
        lb.color = new Color(245, 240, 230, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        this.hintLabel = lb;
        n.active = false;
        this.hint = n;
    }
}
