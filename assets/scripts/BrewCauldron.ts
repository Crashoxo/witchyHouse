import { _decorator, Component, Node, Sprite, SpriteFrame, UITransform, Label,
         Color, Graphics, UIOpacity, input, Input, EventKeyboard, KeyCode, Vec3, tween } from 'cc';
import { GameArt } from './GameArt';
import { UIState } from './UIState';
import { BrewPanel } from './BrewPanel';
import { PotionRecipes, Recipe } from './PotionRecipes';
import { Quests } from './Quests';
const { ccclass, property } = _decorator;

/**
 * 藥水室的鍋爐：掛在 brew.scene 的 Cauldron 節點上。
 *   - 執行期把自己的 Sprite 設成鍋爐 idle 圖（f0），走近顯示「按 E 調配藥水」。
 *   - 按 E 開 BrewPanel 選配方；選了就先扣材料、播 6 幀熬煮動畫，結束把成品加進背包。
 * 錨點 (0.5,0)＋在 Props 底下＝吃 YSort 遮擋。
 */
@ccclass('BrewCauldron')
export class BrewCauldron extends Component {
    @property({ tooltip: '玩家離多近才能製作（像素）' })
    interactRange = 200;
    @property({ tooltip: '鍋爐顯示縮放（原圖幀 224x343）' })
    displayScale = 0.55;

    private player: Node | null = null;
    private sprite: Sprite | null = null;
    private frames: SpriteFrame[] = [];
    private hint: Node | null = null;
    private inRange = false;
    private brewing = false;
    private timer = 0;
    private brewDur = 1;
    private pending: Recipe | null = null;

    onLoad() {
        this.player = this.node.parent?.getChildByName('Player') ?? null;
        this.sprite = this.getComponent(Sprite) ?? this.addComponent(Sprite);
        if (this.sprite) this.sprite.sizeMode = Sprite.SizeMode.CUSTOM;
        this.getComponent(UITransform)?.setAnchorPoint(0.5, 0);
        GameArt.preload();
        GameArt.onReady(() => { this.frames = GameArt.cauldronFrames(); this.showFrame(0); });
        this.buildHint();
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }

    private showFrame(i: number) {
        if (!this.sprite || !this.frames.length) return;
        const f = this.frames[Math.max(0, Math.min(i, this.frames.length - 1))];
        if (!f) return;
        this.sprite.spriteFrame = f;
        const ut = this.getComponent(UITransform);
        if (ut) { ut.setContentSize(f.rect.width * this.displayScale, f.rect.height * this.displayScale); ut.setAnchorPoint(0.5, 0); }
    }

    private onKeyDown(e: EventKeyboard) {
        if (e.keyCode !== KeyCode.KEY_E) return;
        if (!this.inRange || UIState.modalOpen || this.brewing) return;
        BrewPanel.ensure()?.open(this);
    }

    /** 由 BrewPanel 呼叫：開始熬煮（先扣料，播動畫，結束產出）。 */
    startBrew(r: Recipe) {
        if (this.brewing) return;
        if (!PotionRecipes.consume(r)) return;   // 保險：材料不足不做
        this.brewing = true; this.pending = r; this.timer = 0; this.brewDur = Math.max(0.4, r.brewSeconds);
    }

    isBrewing(): boolean { return this.brewing; }

    update(dt: number) {
        if (this.player) {
            this.inRange = Vec3.distance(this.player.position, this.node.position) <= this.interactRange;
            if (this.hint) this.hint.active = this.inRange && !UIState.modalOpen && !this.brewing;
        }
        if (this.brewing) {
            this.timer += dt;
            const p = Math.min(1, this.timer / this.brewDur);
            this.showFrame(Math.floor(p * this.frames.length));
            if (this.timer >= this.brewDur) {
                this.brewing = false;
                const r = this.pending; this.pending = null;
                if (r) { PotionRecipes.produce(r); Quests.record('brew', r.name, 1); this.popup(`＋${r.name}`); }
                this.showFrame(0);
            }
        }
    }

    /** 完成時在鍋爐上方冒一個「＋成品」浮字，往上飄淡出。 */
    private popup(text: string) {
        const n = new Node('BrewPopup');
        n.layer = this.node.layer;
        this.node.addChild(n);
        const ut = this.getComponent(UITransform);
        const topY = ut ? ut.contentSize.height + 20 : 160;
        n.addComponent(UITransform).setContentSize(220, 34);
        n.setPosition(0, topY, 0);
        const lb = n.addComponent(Label);
        lb.string = text; lb.fontSize = 24; lb.color = new Color(150, 240, 170, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.enableOutline = true; lb.outlineColor = new Color(30, 24, 40, 220); lb.outlineWidth = 3;
        const op = n.addComponent(UIOpacity);
        tween(n).by(1.2, { position: new Vec3(0, 60, 0) }).start();
        tween(op).delay(0.5).to(0.7, { opacity: 0 }).call(() => n.destroy()).start();
    }

    private buildHint() {
        const n = new Node('BrewHint');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.addComponent(UITransform).setContentSize(220, 32);
        n.setPosition(0, 210, 0);
        const g = n.addComponent(Graphics);
        g.fillColor = new Color(20, 16, 28, 210);
        g.strokeColor = new Color(210, 190, 230, 220);
        g.lineWidth = 2;
        this.pill(g, -110, -16, 220, 32, 16); g.fill(); g.stroke();
        const t = new Node('t'); t.layer = this.node.layer; n.addChild(t);
        t.addComponent(UITransform).setContentSize(220, 32);
        const lb = t.addComponent(Label);
        lb.string = '按 E 調配藥水'; lb.fontSize = 20; lb.color = new Color(245, 240, 250, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        n.active = false;
        this.hint = n;
    }

    private pill(g: Graphics, x: number, y: number, w: number, h: number, r: number) {
        g.rect(x, y, w, h);   // 一般方框（不圓角）
    }
}
