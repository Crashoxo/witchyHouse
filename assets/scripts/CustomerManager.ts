import { _decorator, Component, Node, UITransform, Sprite, Label, Color, Graphics,
         Vec3, SpriteFrame } from 'cc';
import { ShopStock } from './ShopStock';
import { Wallet } from './Wallet';
import { GameArt } from './GameArt';
const { ccclass, property } = _decorator;

/** 顧客的行為狀態。 */
enum St { ENTER, BROWSE, LEAVE }

interface Customer {
    node: Node;
    display: number;      // 顯示高度（用來擺對話泡）
    state: St;
    timer: number;
    want: string;         // 想買的材料名
    target: Vec3;
    bubble: Node | null;
    faceRight: boolean;
    emoteFrames: SpriteFrame[] | null;   // 成交後的表情動畫幀
    emoteSprite: Sprite | null;
    emoteTimer: number;
    emoteIdx: number;
}

/**
 * 顧客系統（Phase 2）：定時生一位動物顧客走進店裡，看中一件上架商品就買下
 * （ShopStock.sellOne → Wallet.add），冒對話泡，然後離開。掛在 shop.scene 的
 * Props 節點上（顧客生成為 Props 子節點，跟著 YSortLayer 做前後遮擋）。
 */
@ccclass('CustomerManager')
export class CustomerManager extends Component {
    @property({ tooltip: '每隔幾秒嘗試生一位顧客' })
    spawnInterval = 6;
    @property({ tooltip: '同時最多幾位顧客' })
    maxConcurrent = 3;
    @property({ tooltip: '顧客走路速度（像素/秒）' })
    walkSpeed = 120;
    @property({ tooltip: '顧客顯示高度（像素）' })
    displayHeight = 150;

    private readonly entrance = new Vec3(0, -330, 0);   // 進出口（畫面下方，靠出口）
    // 桌子（展示商品的長木凳）在世界座標中心約 (-260,-100)；顧客走到桌前挑貨
    private readonly tableFrontY = -185;
    private customers: Customer[] = [];
    private spawnTimer = 0;

    onLoad() {
        GameArt.preload();
    }

    update(dt: number) {
        // 生成
        this.spawnTimer += dt;
        if (this.spawnTimer >= this.spawnInterval) {
            this.spawnTimer = 0;
            if (GameArt.ready && ShopStock.listings.length > 0 && this.customers.length < this.maxConcurrent) {
                this.spawn();
            }
        }
        // 推進每位顧客
        for (let i = this.customers.length - 1; i >= 0; i--) {
            if (this.step(this.customers[i], dt)) {
                this.customers[i].node.destroy();
                this.customers.splice(i, 1);
            }
        }
    }

    // ---- 生成一位顧客 ----

    private spawn() {
        const names = GameArt.customerNames();
        if (names.length === 0) return;
        const animal = names[Math.floor(Math.random() * names.length)];
        const frame = GameArt.customer(animal);
        if (!frame) return;

        const list = ShopStock.listings;
        const want = list[Math.floor(Math.random() * list.length)].name;

        const node = new Node('Customer-' + animal);
        node.layer = this.node.layer;
        this.node.addChild(node);
        node.setPosition(this.entrance);

        // 立繪（依原圖比例縮到 displayHeight，錨點底部中央）
        const r = frame.rect;
        const w = this.displayHeight * (r.width / r.height);
        const ut = node.addComponent(UITransform);
        ut.setContentSize(w, this.displayHeight);
        ut.setAnchorPoint(0.5, 0);
        const sp = node.addComponent(Sprite);
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.type = Sprite.Type.SIMPLE;
        sp.spriteFrame = frame;

        // 走到桌前的隨機位置（桌子在左側，x 約 -360..-140）挑貨
        const browseX = -360 + Math.random() * 220;
        this.customers.push({
            node, display: this.displayHeight, state: St.ENTER, timer: 0,
            want, target: new Vec3(browseX, this.tableFrontY, 0), bubble: null, faceRight: true,
            emoteFrames: null, emoteSprite: null, emoteTimer: 0, emoteIdx: 0,
        });
    }

    // ---- 推進一位顧客；回傳 true＝該離場銷毀 ----

    private step(c: Customer, dt: number): boolean {
        this.animateEmote(c, dt);
        switch (c.state) {
            case St.ENTER:
                if (this.moveTo(c, c.target, dt)) {
                    c.state = St.BROWSE; c.timer = 0;
                    this.showBubble(c, GameArt.item(c.want), `想要 ${c.want}`);
                }
                return false;

            case St.BROWSE:
                c.timer += dt;
                if (c.timer >= 1.2) {
                    // 嘗試購買：想要的還在架上就成交
                    const price = ShopStock.sellOne(c.want);
                    if (price > 0) {
                        Wallet.add(price);
                        this.showEmote(c, price);   // 成交冒隨機表情泡泡
                    } else {
                        this.showBubble(c, null, '沒貨…下次吧', new Color(150, 120, 120, 235));
                    }
                    c.state = St.LEAVE; c.timer = 0;
                }
                return false;

            case St.LEAVE:
                c.timer += dt;
                if (c.timer < 1.0) return false;   // 成交後停一下再走
                return this.moveTo(c, this.entrance, dt);   // 走到出口就銷毀
        }
        return false;
    }

    /** 朝 target 移動；到達回 true。 */
    private moveTo(c: Customer, target: Vec3, dt: number): boolean {
        const p = c.node.position;
        const dx = target.x - p.x, dy = target.y - p.y;
        const dist = Math.hypot(dx, dy);
        const step = this.walkSpeed * dt;
        if (dist <= step) { c.node.setPosition(target.x, target.y, 0); return true; }
        c.node.setPosition(p.x + dx / dist * step, p.y + dy / dist * step, 0);
        // 面向移動方向（立繪預設朝右→往左翻）
        const goRight = dx >= 0;
        if (goRight !== c.faceRight) {
            c.faceRight = goRight;
            const s = c.node.scale;
            c.node.setScale(goRight ? Math.abs(s.x) : -Math.abs(s.x), s.y, s.z);
        }
        return false;
    }

    // ---- 對話泡 ----

    private showBubble(c: Customer, icon: SpriteFrame | null, text: string, bg = new Color(30, 24, 40, 230)) {
        if (c.bubble) { c.bubble.destroy(); c.bubble = null; }
        const layer = this.node.layer;
        const W = 150, H = 46;

        const b = new Node('bubble');
        b.layer = layer;
        c.node.addChild(b);
        b.addComponent(UITransform).setContentSize(W, H);
        // 立繪錨點在底部 → 對話泡擺到頭頂上方
        b.setPosition(0, c.display + 30, 0);
        // 反轉父節點翻面的影響，讓泡泡文字不會鏡像
        const px = c.node.scale.x;
        if (px < 0) b.setScale(-1, 1, 1);

        const g = b.addComponent(Graphics);
        g.fillColor = bg;
        g.strokeColor = new Color(230, 220, 240, 220);
        g.lineWidth = 2;
        this.roundRect(g, -W / 2, -H / 2, W, H, 12);
        g.fill(); g.stroke();
        // 小尾巴
        g.fillColor = bg;
        g.moveTo(-8, -H / 2); g.lineTo(8, -H / 2); g.lineTo(0, -H / 2 - 10); g.close(); g.fill();

        let textX = 0, textW = W - 16;
        if (icon) {
            const iconNode = new Node('i');
            iconNode.layer = layer;
            b.addChild(iconNode);
            iconNode.addComponent(UITransform).setContentSize(32, 32);
            iconNode.setPosition(-W / 2 + 24, 0, 0);
            const sp = iconNode.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM;
            sp.type = Sprite.Type.SIMPLE;
            sp.spriteFrame = icon;
            textX = 20; textW = W - 52;
        }

        const tn = new Node('t');
        tn.layer = layer;
        b.addChild(tn);
        tn.addComponent(UITransform).setContentSize(textW, H);
        tn.setPosition(textX, 0, 0);
        const lb = tn.addComponent(Label);
        lb.string = text;
        lb.fontSize = 18;
        lb.color = new Color(245, 242, 250, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;

        c.bubble = b;
    }

    /** 成交：在顧客頭頂冒一個隨機動畫表情泡泡 + 「＋N 金」。 */
    private showEmote(c: Customer, price: number) {
        if (c.bubble) { c.bubble.destroy(); c.bubble = null; }
        const layer = this.node.layer;

        const b = new Node('emote');
        b.layer = layer;
        c.node.addChild(b);
        b.addComponent(UITransform);
        b.setPosition(0, c.display + 40, 0);
        if (c.node.scale.x < 0) b.setScale(-1, 1, 1);   // 反轉父節點翻面，泡泡不鏡像

        // 隨機挑一個表情
        const names = GameArt.emoteNames();
        const frames = names.length ? GameArt.emote(names[Math.floor(Math.random() * names.length)]) : null;

        const en = new Node('e');
        en.layer = layer;
        b.addChild(en);
        const eut = en.addComponent(UITransform);
        const sp = en.addComponent(Sprite);
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.type = Sprite.Type.SIMPLE;
        if (frames && frames.length) {
            const f0 = frames[0];
            const k = 72 / Math.max(f0.rect.width, f0.rect.height);
            eut.setContentSize(f0.rect.width * k, f0.rect.height * k);
            sp.spriteFrame = f0;
        } else {
            eut.setContentSize(56, 56);
        }

        // ＋N 金（表情下方）
        const tn = new Node('g');
        tn.layer = layer;
        b.addChild(tn);
        tn.addComponent(UITransform).setContentSize(96, 22);
        tn.setPosition(0, -38, 0);
        const lb = tn.addComponent(Label);
        lb.string = `＋${price} 金`;
        lb.fontSize = 18;
        lb.color = new Color(255, 224, 130, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;

        c.bubble = b;
        c.emoteSprite = sp;
        c.emoteFrames = frames;
        c.emoteTimer = 0;
        c.emoteIdx = 0;
    }

    /** 推進表情動畫（約 15fps 循環）。 */
    private animateEmote(c: Customer, dt: number) {
        if (!c.emoteFrames || !c.emoteSprite || c.emoteFrames.length === 0) return;
        c.emoteTimer += dt;
        const idx = Math.floor(c.emoteTimer * 15) % c.emoteFrames.length;
        if (idx !== c.emoteIdx) {
            c.emoteIdx = idx;
            c.emoteSprite.spriteFrame = c.emoteFrames[idx];
        }
    }

    private roundRect(g: Graphics, x: number, y: number, w: number, h: number, r: number) {
        const HP = Math.PI / 2;
        g.moveTo(x + r, y);
        g.lineTo(x + w - r, y);
        g.arc(x + w - r, y + r, r, -HP, 0, false);
        g.lineTo(x + w, y + h - r);
        g.arc(x + w - r, y + h - r, r, 0, HP, false);
        g.lineTo(x + r, y + h);
        g.arc(x + r, y + h - r, r, HP, Math.PI, false);
        g.lineTo(x, y + r);
        g.arc(x + r, y + r, r, Math.PI, Math.PI + HP, false);
        g.close();
    }
}
