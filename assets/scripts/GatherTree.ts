import { _decorator, Component, Node, Sprite, Color, input, Input,
         EventKeyboard, KeyCode, Vec3, UITransform, UIOpacity, Graphics,
         Label, tween } from 'cc';
import { Inventory } from './Inventory';
import { UIState } from './UIState';
import { Quests } from './Quests';
import { GameArt } from './GameArt';
import { CharacterAnimator } from './CharacterAnimator';
const { ccclass, property } = _decorator;

/**
 * 採集樹：玩家走近、按 E 採集 → 產出材料、進入冷卻（樹變暗）、一段時間後長回來。
 *
 * 掛在「每一棵樹」的節點上。玩家參照會自動從同一層（World 底下）
 * 名叫 "Player" 的節點抓，所以複製出來的樹不用一個一個拖。
 *
 * 目前「產出材料」只是印到 Console；之後有背包系統時，把 gather() 裡
 * 的 console.log 換成「加進背包」即可。
 */
@ccclass('GatherTree')
export class GatherTree extends Component {
    @property gatherRange = 120;    // 玩家離多近才採得到（像素）
    @property cooldown = 5;         // 採完幾秒後長回來
    @property itemName = '木材';     // 這棵樹產出什麼材料
    @property({ tooltip: '每次最少採到幾個' }) minYield = 1;
    @property({ tooltip: '每次最多採到幾個' }) maxYield = 3;
    @property({ tooltip: '額外稀有掉落的物品名（空＝沒有）' }) rareItem = '';
    @property({ tooltip: '掉到稀有物的機率（0~1）' }) rareChance = 0.15;

    private player: Node | null = null;
    private sprite: Sprite | null = null;
    private original = new Color();  // 記住原本的顏色，冷卻結束後還原
    private ready = true;            // true = 可採，false = 冷卻中
    private timer = 0;

    onLoad() {
        this.sprite = this.getComponent(Sprite);
        if (this.sprite) this.original.set(this.sprite.color);
        GameArt.preload();   // 採集動畫幀 / 材料圖示
        // 樹和 Player 都是 World 的子節點 → 直接找兄弟節點
        this.player = this.node.parent?.getChildByName('Player') ?? null;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }

    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }

    private onKeyDown(e: EventKeyboard) {
        if (e.keyCode !== KeyCode.KEY_E) return;
        if (UIState.modalOpen) return;                  // 開著視窗時不採集
        if (!this.ready || !this.player) return;
        // 兩者都是 World 的子節點 → 比 local position 的距離即可（不受相機捲動影響）
        if (Vec3.distance(this.player.position, this.node.position) > this.gatherRange) return;
        this.gather();
    }

    private gather() {
        const inv = Inventory.ensure();   // 沒有背包 UI 時會自動在 Canvas 底下生一個
        // 隨機數量（min~max）
        const lo = Math.min(this.minYield, this.maxYield);
        const hi = Math.max(this.minYield, this.maxYield);
        const qty = lo + Math.floor(Math.random() * (hi - lo + 1));
        inv?.add(this.itemName, qty);
        Quests.record('gather', this.itemName, qty);   // 累積「採集」任務進度
        this.playFx(this.itemName, qty);
        // 機率額外掉稀有物
        if (this.rareItem && Math.random() < this.rareChance) {
            inv?.add(this.rareItem, 1);
            Quests.record('gather', this.rareItem, 1);
            this.scheduleOnce(() => this.popItem(this.rareItem, 1, 46), 0.35);   // 慢一拍再冒
        }
        this.ready = false;
        this.timer = 0;
        if (this.sprite) this.sprite.color = new Color(80, 80, 80, 255); // 變暗＝採光了
    }

    // ---- 採集特效 ----

    /** 女巫彎腰採集 + 樹搖晃 + 星星 + 材料飄出來。 */
    private playFx(item: string, qty: number) {
        // 女巫：彎腰伸手 → 捏起 → 起身舉起（面向這棵樹）
        const anim = this.player?.getComponent(CharacterAnimator);
        if (anim) {
            const dirX = this.node.position.x - (this.player?.position.x ?? 0);
            anim.playOneShot(GameArt.gatherFrames(), 0.9, dirX);
        }
        // 樹：以樹根為軸左右擺（錨點是 (0.5,0)）
        tween(this.node)
            .to(0.07, { angle: -4 }).to(0.12, { angle: 3.5 })
            .to(0.1, { angle: -1.5 }).to(0.07, { angle: 0 })
            .start();
        // 星星：從樹冠散開往上飄
        for (let i = 0; i < 6; i++) this.spark(i);
        this.popItem(item, qty, 0);
    }

    /** 樹冠冒一顆往上飄的小星星。 */
    private spark(i: number) {
        const host = this.node.parent;
        if (!host) return;
        const size = this.getComponent(UITransform);
        const w = (size?.width ?? 100) * Math.abs(this.node.scale.x);
        const h = (size?.height ?? 120) * Math.abs(this.node.scale.y);
        const n = new Node('spark');
        n.layer = this.node.layer;
        host.addChild(n);
        n.setPosition(this.node.position.x + (Math.random() - 0.5) * w * 0.7,
                      this.node.position.y + h * (0.45 + Math.random() * 0.35), 0);
        n.addComponent(UITransform).setContentSize(12, 12);
        const g = n.addComponent(Graphics);
        g.fillColor = new Color(255, 240, 170, 255);
        g.circle(0, 0, 2 + Math.random() * 2.5);
        g.fill();
        const op = n.addComponent(UIOpacity);
        const dur = 0.5 + Math.random() * 0.3;
        tween(n).by(dur, { position: new Vec3((Math.random() - 0.5) * 40, 34 + Math.random() * 26, 0) }).start();
        tween(op).delay(dur * 0.35).to(dur * 0.65, { opacity: 0 }).call(() => n.destroy()).start();
    }

    /** 採到的材料：圖示＋數量從樹上飄出來、往上淡出。 */
    private popItem(item: string, qty: number, extraY: number) {
        const host = this.node.parent;
        if (!host) return;
        const size = this.getComponent(UITransform);
        const h = (size?.height ?? 120) * Math.abs(this.node.scale.y);
        const n = new Node('pop');
        n.layer = this.node.layer;
        host.addChild(n);
        n.setPosition(this.node.position.x, this.node.position.y + h * 0.62 + extraY, 0);
        n.addComponent(UITransform).setContentSize(80, 40);
        const op = n.addComponent(UIOpacity);

        const frame = GameArt.item(item);
        if (frame) {   // 有圖示就圖示在左、數量在右
            const icon = new Node('i');
            icon.layer = this.node.layer;
            n.addChild(icon);
            const k = 34 / Math.max(frame.rect.width, frame.rect.height);
            icon.addComponent(UITransform).setContentSize(frame.rect.width * k, frame.rect.height * k);
            icon.setPosition(-16, 0, 0);
            const sp = icon.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM;
            sp.type = Sprite.Type.SIMPLE;
            sp.spriteFrame = frame;
        }
        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(64, 30);
        t.setPosition(frame ? 16 : 0, 0, 0);
        const lb = t.addComponent(Label);
        lb.string = frame ? `×${qty}` : `${item} ×${qty}`;
        lb.fontSize = 22;
        lb.color = new Color(255, 246, 214, 255);
        lb.enableOutline = true;
        lb.outlineColor = new Color(60, 40, 30, 220);
        lb.outlineWidth = 3;
        lb.horizontalAlign = frame ? Label.HorizontalAlign.LEFT : Label.HorizontalAlign.CENTER;

        tween(n).by(0.9, { position: new Vec3(0, 52, 0) }).start();
        tween(op).delay(0.45).to(0.45, { opacity: 0 }).call(() => n.destroy()).start();
    }

    update(dt: number) {
        if (this.ready) return;
        this.timer += dt;
        if (this.timer >= this.cooldown) {
            this.ready = true;
            if (this.sprite) this.sprite.color = this.original; // 長回原本的綠色
        }
    }
}
