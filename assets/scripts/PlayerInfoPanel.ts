import { _decorator, Component, Node, UITransform, Widget, Label, Sprite, Color,
         Graphics, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity } from 'cc';
import { UIState } from './UIState';
import { Wallet } from './Wallet';
import { Inventory } from './Inventory';
import { GameArt } from './GameArt';
import { TimeSystem } from './TimeSystem';
import { Friendship } from './Friendship';
import { Reputation } from './Reputation';
import { MATERIALS, ITEM_DESC, DEFAULT_ITEM_DESC, POTION_ITEMS } from './data/items';
import { DEFAULT_BUY, BASE_PRICE } from './data/prices';
import { SEASONS } from './data/seasons';
const { ccclass } = _decorator;

/**
 * 玩家資訊面板（Tab 或 I 開）：三個分頁
 *   物品 —— 所有材料/藥水的圖示、持有數、收購價、建議售價與說明（翻頁）
 *   村民 —— 每位村民的頭像、住處、友誼度（心）與介紹
 *   日曆 —— 當季 28 天的月曆，標出今天與節日，附當季盛產材料
 * 仿 ShopPanel/QuestLog 的 ensure() 自動生 UI，完全不需要場景改動。
 */

/** 物品頁的完整清單：材料在前、藥水在後（同 ShopManagePanel 的順序慣例）。 */
const POTIONS: string[] = Object.keys(POTION_ITEMS);
const ALL_ITEMS: string[] = MATERIALS.concat(POTIONS);

/** 物品頁一頁幾列。 */
const PER_PAGE = 5;

type Tab = 'items' | 'villagers' | 'calendar';

@ccclass('PlayerInfoPanel')
export class PlayerInfoPanel extends Component {
    static instance: PlayerInfoPanel | null = null;

    static ensure(): PlayerInfoPanel | null {
        if (PlayerInfoPanel.instance) return PlayerInfoPanel.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[PlayerInfoPanel] 找不到 Canvas'); return null; }
        const node = new Node('PlayerInfoUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(PlayerInfoPanel);
    }

    private root: Node | null = null;
    private tabBox: Node | null = null;
    private bodyBox: Node | null = null;
    private dateLabel: Label | null = null;
    private tab: Tab = 'items';
    private page = 0;

    private readonly panelW = 780;
    private readonly panelH = 520;
    private readonly headerH = 124;   // 標題 + 分頁列佔掉的高度

    onLoad() {
        PlayerInfoPanel.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        GameArt.preload();
        GameArt.onReady(() => { if (this.root?.active) this.refresh(); });   // 圖載好補畫
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (PlayerInfoPanel.instance === this) PlayerInfoPanel.instance = null;
        if (this.root?.active) UIState.modalOpen = false;
    }

    private onKeyDown(e: EventKeyboard) {
        if (!this.root?.active) return;
        // Tab / I 再按一次關閉：此時 modalOpen 已是 true，PlayerController 那邊會先 return，
        // 不會發生「同一下按鍵關掉又立刻開回來」（同 ShopPanel 的考量）。
        if (e.keyCode === KeyCode.ESCAPE || e.keyCode === KeyCode.TAB || e.keyCode === KeyCode.KEY_I) {
            this.close(); return;
        }
        if (e.keyCode === KeyCode.ARROW_LEFT) this.turn(-1);
        else if (e.keyCode === KeyCode.ARROW_RIGHT) this.turn(1);
    }

    open() {
        if (!this.root) this.build();
        this.root!.active = true;
        UIState.modalOpen = true;
        this.page = 0;
        this.refresh();
    }

    close() {
        if (this.root) this.root.active = false;
        UIState.modalOpen = false;
    }

    isOpen(): boolean { return !!this.root?.active; }

    private setTab(t: Tab) { this.tab = t; this.page = 0; this.refresh(); }

    private turn(d: number) {
        const max = this.pageCount();
        if (max <= 1) return;
        this.page = (this.page + d + max) % max;
        this.refresh();
    }

    private pageCount(): number {
        return this.tab === 'items' ? Math.ceil(ALL_ITEMS.length / PER_PAGE) : 1;
    }

    // ---- 骨架（只建一次）----

    private build() {
        const layer = this.node.layer;
        const W = this.panelW, H = this.panelH;

        const root = new Node('Root');
        root.layer = layer;
        this.node.addChild(root);
        root.addComponent(UITransform).setContentSize(3000, 2000);
        root.addComponent(BlockInputEvents);
        const dim = root.addComponent(Graphics);
        dim.fillColor = new Color(0, 0, 0, 150);
        dim.rect(-1500, -1000, 3000, 2000);
        dim.fill();
        const rw = root.addComponent(Widget);
        rw.isAlignHorizontalCenter = rw.isAlignVerticalCenter = true;
        rw.horizontalCenter = rw.verticalCenter = 0;
        rw.updateAlignment();
        this.root = root;

        const panel = new Node('Panel');
        panel.layer = layer;
        root.addChild(panel);
        panel.addComponent(UITransform).setContentSize(W, H);
        const pg = panel.addComponent(Graphics);
        pg.lineWidth = 4;
        pg.fillColor = new Color(38, 30, 52, 246);
        pg.strokeColor = new Color(224, 196, 150, 235);
        pg.rect(-W / 2, -H / 2, W, H);
        pg.fill(); pg.stroke();

        const topY = H / 2;
        const leftX = -W / 2 + 34;

        this.label(panel, '玩家資訊', 26, new Color(250, 236, 214, 255),
            leftX, topY - 36, 240, Label.HorizontalAlign.LEFT);
        this.dateLabel = this.label(panel, '', 20, new Color(206, 230, 255, 255),
            W / 2 - 84, topY - 36, 360, Label.HorizontalAlign.RIGHT);
        this.button(panel, '✕', 40, 40, W / 2 - 34, topY - 36,
            new Color(120, 60, 70, 255), () => this.close());

        const tabBox = new Node('Tabs');
        tabBox.layer = layer;
        panel.addChild(tabBox);
        tabBox.addComponent(UITransform);
        tabBox.setPosition(0, topY - 88, 0);
        this.tabBox = tabBox;

        const bodyBox = new Node('Body');
        bodyBox.layer = layer;
        panel.addChild(bodyBox);
        bodyBox.addComponent(UITransform);
        bodyBox.setPosition(0, topY - this.headerH, 0);   // 之後所有內容的 y 都是負的
        this.bodyBox = bodyBox;

        this.label(panel, 'Tab / I / Esc 關閉　←→ 翻頁', 15, new Color(170, 162, 184, 255),
            0, -H / 2 + 18, 400, Label.HorizontalAlign.CENTER);
    }

    private refresh() {
        if (this.dateLabel) {
            this.dateLabel.string = `${TimeSystem.dateTextFull()}　${TimeSystem.clockText()}`;
        }
        this.buildTabs();
        const box = this.bodyBox;
        if (!box) return;
        box.removeAllChildren();
        if (this.tab === 'items') this.renderItems(box);
        else if (this.tab === 'villagers') this.renderVillagers(box);
        else this.renderCalendar(box);
    }

    private buildTabs() {
        const box = this.tabBox;
        if (!box) return;
        box.removeAllChildren();
        const active = new Color(120, 92, 60, 255);
        const idle = new Color(66, 54, 48, 255);
        const w = 160, gap = 12;
        const tabs: Array<[Tab, string]> = [['items', '物品'], ['villagers', '村民'], ['calendar', '日曆']];
        const startX = -((tabs.length - 1) * (w + gap)) / 2;
        for (let i = 0; i < tabs.length; i++) {
            const [id, name] = tabs[i];
            this.button(box, name, w, 38, startX + i * (w + gap), 0,
                this.tab === id ? active : idle, () => this.setTab(id));
        }
    }

    // ---- 物品頁 ----

    private renderItems(box: Node) {
        const leftX = -this.panelW / 2 + 34;
        const colHave = 168, colBuy = 258, colSell = 348;
        const head = new Color(200, 190, 178, 255);
        this.label(box, '物品', 17, head, leftX, -14, 200, Label.HorizontalAlign.LEFT);
        this.label(box, '持有', 17, head, colHave, -14, 80, Label.HorizontalAlign.CENTER);
        this.label(box, '收購價', 17, head, colBuy, -14, 90, Label.HorizontalAlign.CENTER);
        this.label(box, '售價', 17, head, colSell, -14, 90, Label.HorizontalAlign.CENTER);

        const rowH = 58;
        const start = this.page * PER_PAGE;
        const slice = ALL_ITEMS.slice(start, start + PER_PAGE);
        for (let i = 0; i < slice.length; i++) {
            this.itemRow(box, slice[i], -52 - i * rowH, leftX, colHave, colBuy, colSell);
        }

        // 翻頁列
        const y = -52 - PER_PAGE * rowH + 2;
        const pages = this.pageCount();
        if (pages > 1) {
            this.button(box, '＜', 54, 34, -70, y, new Color(66, 54, 48, 255), () => this.turn(-1));
            this.label(box, `${this.page + 1} / ${pages}`, 18, new Color(220, 212, 232, 255),
                0, y, 120, Label.HorizontalAlign.CENTER);
            this.button(box, '＞', 54, 34, 70, y, new Color(66, 54, 48, 255), () => this.turn(1));
        }
    }

    private itemRow(box: Node, name: string, y: number, leftX: number,
                    colHave: number, colBuy: number, colSell: number) {
        const have = Inventory.countOf(name);
        const buy = this.buyPriceOf(name);
        const sell = BASE_PRICE[name] ?? 0;
        const dim = have > 0 ? 255 : 130;   // 沒有的物品整列變暗（仍看得到資料）

        // 圖示（等比塞進 44 見方）
        const frame = GameArt.item(name);
        const iconX = leftX + 22;
        if (frame) {
            const n = new Node('icon');
            n.layer = this.node.layer;
            box.addChild(n);
            const k = 44 / Math.max(frame.rect.width, frame.rect.height);
            n.addComponent(UITransform).setContentSize(frame.rect.width * k, frame.rect.height * k);
            n.setPosition(iconX, y + 4, 0);
            const sp = n.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM;
            sp.type = Sprite.Type.SIMPLE;
            sp.spriteFrame = frame;
            n.addComponent(UIOpacity).opacity = dim;
        }

        const textX = leftX + 52;
        this.label(box, name, 21, new Color(244, 236, 224, dim),
            textX, y + 12, 200, Label.HorizontalAlign.LEFT);
        this.label(box, ITEM_DESC[name] ?? DEFAULT_ITEM_DESC, 14, new Color(178, 170, 192, dim),
            textX, y - 12, 300, Label.HorizontalAlign.LEFT);

        this.label(box, have > 0 ? `×${have}` : '—', 20,
            new Color(220, 230, 210, dim), colHave, y, 80, Label.HorizontalAlign.CENTER);
        this.label(box, buy > 0 ? `${buy} 金` : '—', 19,
            new Color(230, 200, 150, dim), colBuy, y, 90, Label.HorizontalAlign.CENTER);
        this.label(box, sell > 0 ? `${sell} 金` : '—', 19,
            new Color(255, 224, 130, dim), colSell, y, 90, Label.HorizontalAlign.CENTER);
    }

    /** 雜貨鋪收購價（沒收的東西回 0）。 */
    private buyPriceOf(name: string): number {
        for (let i = 0; i < DEFAULT_BUY.length; i++) {
            if (DEFAULT_BUY[i].name === name) return DEFAULT_BUY[i].price;
        }
        return 0;
    }

    // ---- 村民頁 ----

    private renderVillagers(box: Node) {
        const leftX = -this.panelW / 2 + 34;
        const list = Friendship.villagers();
        const rowH = 100;

        this.label(box, `名聲 Lv.${Reputation.level} ${Reputation.title}　金幣 ${Wallet.gold}`,
            17, new Color(200, 190, 178, 255), leftX, -14, 460, Label.HorizontalAlign.LEFT);

        for (let i = 0; i < list.length; i++) {
            const v = list[i];
            const y = -76 - i * rowH;

            // 頭像（等比塞進 76 見方，沒圖就畫個框）
            const frame = GameArt.portrait(v.portrait);
            const px = leftX + 40;
            if (frame) {
                const n = new Node('portrait');
                n.layer = this.node.layer;
                box.addChild(n);
                const k = 76 / Math.max(frame.rect.width, frame.rect.height);
                n.addComponent(UITransform).setContentSize(frame.rect.width * k, frame.rect.height * k);
                n.setPosition(px, y, 0);
                const sp = n.addComponent(Sprite);
                sp.sizeMode = Sprite.SizeMode.CUSTOM;
                sp.type = Sprite.Type.SIMPLE;
                sp.spriteFrame = frame;
            } else {
                const n = new Node('portraitBox');
                n.layer = this.node.layer;
                box.addChild(n);
                n.addComponent(UITransform).setContentSize(76, 76);
                n.setPosition(px, y, 0);
                const g = n.addComponent(Graphics);
                g.lineWidth = 2;
                g.fillColor = new Color(58, 46, 74, 255);
                g.strokeColor = new Color(150, 136, 170, 200);
                g.rect(-38, -38, 76, 76); g.fill(); g.stroke();
            }

            const tx = leftX + 92;
            this.label(box, v.name, 22, new Color(244, 236, 224, 255),
                tx, y + 28, 220, Label.HorizontalAlign.LEFT);
            this.label(box, v.place, 15, new Color(178, 170, 192, 255),
                tx + 150, y + 28, 160, Label.HorizontalAlign.LEFT);
            this.label(box, v.desc, 15, new Color(198, 190, 210, 255),
                tx, y - 26, 420, Label.HorizontalAlign.LEFT);

            // 心（畫出來的，不吃字型）
            this.hearts(box, tx + 6, y + 2, Friendship.hearts(v.name));
            const talked = Friendship.talkedToday(v.name);
            this.label(box, talked ? '今天聊過了' : '今天還沒聊', 14,
                talked ? new Color(150, 200, 160, 255) : new Color(210, 190, 130, 255),
                this.panelW / 2 - 34, y + 2, 200, Label.HorizontalAlign.RIGHT);
            this.label(box, `友誼 ${Friendship.points(v.name)}`, 14, new Color(178, 170, 192, 255),
                this.panelW / 2 - 34, y + 28, 200, Label.HorizontalAlign.RIGHT);
        }
    }

    /** 一排心：filled 顆實心、其餘空心（用 Graphics 畫，避免字型缺字）。 */
    private hearts(box: Node, x: number, y: number, filled: number) {
        const n = new Node('hearts');
        n.layer = this.node.layer;
        box.addChild(n);
        n.addComponent(UITransform).setContentSize(200, 24);
        n.setPosition(x, y, 0);
        const g = n.addComponent(Graphics);
        const r = 8, gap = 24, lobeY = r * 0.34;
        const max = Friendship.maxHearts;
        g.lineWidth = 2;
        for (let i = 0; i < max; i++) {
            const cx = i * gap;
            const on = i < filled;
            g.fillColor = on ? new Color(232, 96, 120, 255) : new Color(70, 60, 84, 255);
            // 兩個圓（上方左右耳）+ 一個下尖角＝心形
            g.circle(cx - r * 0.45, lobeY, r * 0.55);
            g.circle(cx + r * 0.45, lobeY, r * 0.55);
            g.fill();
            g.moveTo(cx - r, r * 0.28);
            g.lineTo(cx + r, r * 0.28);
            g.lineTo(cx, -r);
            g.close();
            g.fill();
        }
    }

    // ---- 日曆頁 ----

    private renderCalendar(box: Node) {
        const leftX = -this.panelW / 2 + 34;
        const season = TimeSystem.season;
        const def = SEASONS[season];
        const today = TimeSystem.day;
        const days = TimeSystem.daysPerSeason;

        this.label(box, `第 ${TimeSystem.year} 年 · ${def.label}（一季 ${days} 天）`, 20,
            new Color(244, 236, 224, 255), leftX, -16, 420, Label.HorizontalAlign.LEFT);
        this.label(box, `當季盛產：${def.bonusItems.join('、')}`, 15,
            new Color(180, 220, 180, 255), this.panelW / 2 - 34, -16, 320, Label.HorizontalAlign.RIGHT);
        this.label(box, def.desc, 15, new Color(190, 182, 204, 255),
            leftX, -40, 700, Label.HorizontalAlign.LEFT);

        // 28 格月曆（7 欄 × 4 列）
        const cw = 74, ch = 46, gx = 8, gy = 8;
        const gridW = 7 * cw + 6 * gx;
        const x0 = -gridW / 2 + cw / 2;
        const yTop = -76;
        for (let d = 1; d <= days; d++) {
            const col = (d - 1) % 7, row = Math.floor((d - 1) / 7);
            const cx = x0 + col * (cw + gx);
            const cy = yTop - row * (ch + gy) - ch / 2;
            const fest = TimeSystem.festivalOn(season, d);
            const isToday = d === today;

            const cell = new Node('d' + d);
            cell.layer = this.node.layer;
            box.addChild(cell);
            cell.addComponent(UITransform).setContentSize(cw, ch);
            cell.setPosition(cx, cy, 0);
            const g = cell.addComponent(Graphics);
            g.lineWidth = isToday ? 3 : 2;
            g.fillColor = isToday ? new Color(120, 92, 60, 255)
                        : fest ? new Color(64, 48, 86, 255)
                        : new Color(52, 42, 66, 255);
            g.strokeColor = isToday ? new Color(255, 224, 130, 255)
                        : fest ? new Color(190, 150, 230, 220)
                        : new Color(96, 84, 112, 200);
            g.rect(-cw / 2, -ch / 2, cw, ch);
            g.fill(); g.stroke();

            this.label(cell, String(d), 18,
                new Color(250, 240, 220, d < today ? 130 : 255), -cw / 2 + 8, ch / 2 - 14, 30,
                Label.HorizontalAlign.LEFT);
            if (fest) {
                this.label(cell, fest.name, 13, new Color(226, 196, 255, 255),
                    0, -ch / 2 + 12, cw - 8, Label.HorizontalAlign.CENTER);
            }
        }

        // 今天／節日提示
        const listY = yTop - 4 * (ch + gy) - 14;
        const ft = TimeSystem.festivalToday();
        if (ft) {
            this.label(box, `今天是「${ft.name}」——${ft.desc}`, 16, new Color(226, 196, 255, 255),
                leftX, listY, 700, Label.HorizontalAlign.LEFT);
        } else {
            const next = this.nextFestival(season, today);
            this.label(box, next
                ? `下一個節日：${next.name}（${def.name} ${next.day} 日）——${next.desc}`
                : '這一季剩下的日子沒有節日了，好好做生意吧。',
                16, new Color(190, 182, 204, 255), leftX, listY, 700, Label.HorizontalAlign.LEFT);
        }
    }

    /** 這一季今天之後的下一個節日。 */
    private nextFestival(season: number, fromDay: number) {
        for (let d = fromDay + 1; d <= TimeSystem.daysPerSeason; d++) {
            const f = TimeSystem.festivalOn(season, d);
            if (f) return f;
        }
        return null;
    }

    // ---- 小工具 ----

    private label(parent: Node, text: string, size: number, color: Color,
                  x: number, y: number, width: number, align: number): Label {
        const n = new Node('label');
        n.layer = this.node.layer;
        parent.addChild(n);
        const ut = n.addComponent(UITransform);
        ut.setContentSize(width, size + 10);
        ut.setAnchorPoint(align === Label.HorizontalAlign.RIGHT ? 1
                        : align === Label.HorizontalAlign.CENTER ? 0.5 : 0, 0.5);
        n.setPosition(x, y, 0);
        const lb = n.addComponent(Label);
        lb.string = text;
        lb.fontSize = size;
        lb.lineHeight = size + 4;
        lb.color = color;
        lb.horizontalAlign = align;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;
        return lb;
    }

    private button(parent: Node, text: string, w: number, h: number,
                   x: number, y: number, fill: Color, onClick: () => void) {
        const layer = this.node.layer;
        const n = new Node('btn');
        n.layer = layer;
        parent.addChild(n);
        n.addComponent(UITransform).setContentSize(w, h);
        n.setPosition(x, y, 0);

        const g = n.addComponent(Graphics);
        g.lineWidth = 2;
        g.fillColor = fill;
        g.strokeColor = new Color(230, 220, 240, 200);
        g.rect(-w / 2, -h / 2, w, h);
        g.fill(); g.stroke();

        const tn = new Node('t');
        tn.layer = layer;
        n.addChild(tn);
        tn.addComponent(UITransform).setContentSize(w, h);
        const lb = tn.addComponent(Label);
        lb.string = text;
        lb.fontSize = Math.min(22, h - 14);
        lb.color = new Color(245, 245, 250, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;

        const op = n.addComponent(UIOpacity);
        n.on(Node.EventType.TOUCH_START, () => { op.opacity = 170; });
        n.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; onClick(); });
        n.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
    }
}
