import { _decorator, Component, Node, UITransform, Widget, Label, Color,
         Graphics, BlockInputEvents, find, input, Input,
         EventKeyboard, KeyCode, UIOpacity, Vec3, tween } from 'cc';
import { UIState } from './UIState';
import { Wallet } from './Wallet';
import { Reputation } from './Reputation';
import { DailyLog, DayRecord } from './DailyLog';
import { TimeSystem } from './TimeSystem';
const { ccclass } = _decorator;

/**
 * 每日結算（Phase 3 每日循環）：一天結束（睡覺或 02:00 昏倒）時跳出來，
 * 回顧今天賺了多少、賣了什麼、採集/煉製多少、名聲長了幾點，然後開始新的一天。
 *
 * 觸發方式：`arm()` 向 TimeSystem 註冊「換日」回呼（由 PlayerController.onLoad
 * 呼叫，module 旗標保證整個遊戲只註冊一次）。
 *   昏倒 → 當場跳出來。
 *   睡覺 → 先讓 SleepOverlay 的過場演完，由它在淡出後呼叫 showPending()。
 * 面板本身仿 ShopPanel 的 ensure() 自動生 UI，完全不需要場景改動。
 */

/** 已經結算完、等著顯示的那一天（睡覺時要等過場演完才給看）。 */
let pending: DayRecord | null = null;
let armed = false;

@ccclass('DaySummaryPanel')
export class DaySummaryPanel extends Component {
    static instance: DaySummaryPanel | null = null;

    static ensure(): DaySummaryPanel | null {
        if (DaySummaryPanel.instance) return DaySummaryPanel.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[DaySummaryPanel] 找不到 Canvas'); return null; }
        const node = new Node('DaySummaryUI');
        node.layer = canvas.layer;
        canvas.addChild(node);
        return node.addComponent(DaySummaryPanel);
    }

    /** 註冊換日回呼（整個遊戲只會註冊一次）。 */
    static arm(): void {
        if (armed) return;
        armed = true;
        TimeSystem.onNewDay(cause => {
            // DailyLog 也註冊了 onNewDay，而且比這裡早（它在被 import 時就註冊），
            // 所以這時 DailyLog.last 已經是剛結算完的那一天。
            pending = DailyLog.last;
            if (cause !== 'sleep') DaySummaryPanel.showPending();   // 昏倒：當場跳
        });
    }

    /** 有待顯示的結算就打開（睡覺過場結束時由 SleepOverlay 呼叫）。 */
    static showPending(): void {
        if (!pending) return;
        const rec = pending;
        pending = null;
        DaySummaryPanel.ensure()?.open(rec);
    }

    private root: Node | null = null;
    private readonly panelW = 620;

    onLoad() {
        DaySummaryPanel.instance = this;
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        if (DaySummaryPanel.instance === this) DaySummaryPanel.instance = null;
        if (this.root) UIState.modalOpen = false;
    }

    private onKeyDown(e: EventKeyboard) {
        if (!this.root) return;
        if (e.keyCode === KeyCode.ESCAPE || e.keyCode === KeyCode.ENTER || e.keyCode === KeyCode.SPACE) {
            this.close();
        }
    }

    /** 顯示某一天的結算。面板每次重建（內容每天都不一樣）。 */
    open(rec: DayRecord) {
        if (this.root) { this.root.destroy(); this.root = null; }
        UIState.modalOpen = true;
        this.build(rec);
    }

    close() {
        if (this.root) { this.root.destroy(); this.root = null; }
        UIState.modalOpen = false;
    }

    // ---- 版面 ----

    private build(rec: DayRecord) {
        const layer = this.node.layer;

        // 今日賣出明細（金額高的排前面，最多 3 種）
        const names = Object.keys(rec.items);
        names.sort((a, b) => rec.items[b].g - rec.items[a].g);
        const detail = names.slice(0, 3);

        const lines = this.summaryLines(rec);
        const headerH = 116;
        const lineH = 34;
        const detailH = detail.length ? 26 + detail.length * 28 : 0;
        const warnH = rec.collapsed ? 34 : 0;
        const footerH = 86;
        const panelH = headerH + warnH + lines.length * lineH + detailH + footerH;

        // 半透明背板（擋住後面世界的點擊）
        const root = new Node('Root');
        root.layer = layer;
        this.node.addChild(root);
        root.addComponent(UITransform).setContentSize(3000, 2000);
        root.addComponent(BlockInputEvents);
        const dim = root.addComponent(Graphics);
        dim.fillColor = new Color(0, 0, 0, 165);
        dim.rect(-1500, -1000, 3000, 2000);
        dim.fill();
        const rw = root.addComponent(Widget);
        rw.isAlignHorizontalCenter = rw.isAlignVerticalCenter = true;
        rw.horizontalCenter = rw.verticalCenter = 0;
        rw.updateAlignment();
        this.root = root;

        // 面板本體（從稍微上方滑進來）
        const panel = new Node('Panel');
        panel.layer = layer;
        root.addChild(panel);
        panel.addComponent(UITransform).setContentSize(this.panelW, panelH);
        const pg = panel.addComponent(Graphics);
        pg.lineWidth = 4;
        pg.fillColor = new Color(38, 30, 52, 246);
        pg.strokeColor = new Color(224, 196, 150, 235);
        pg.rect(-this.panelW / 2, -panelH / 2, this.panelW, panelH);
        pg.fill(); pg.stroke();

        const op = panel.addComponent(UIOpacity); op.opacity = 0;
        panel.setPosition(0, 40, 0);
        tween(panel).to(0.28, { position: new Vec3(0, 0, 0) }).start();
        tween(op).to(0.28, { opacity: 255 }).start();

        const topY = panelH / 2;
        const leftX = -this.panelW / 2 + 34;
        const rightX = this.panelW / 2 - 34;

        // 標題：剛結束那天的日期 / 副標：新的一天（今天是節日就順便預告）
        const ft = TimeSystem.festivalToday();
        this.label(panel, `${TimeSystem.dateTextOf(rec.day)} 結算`, 30, new Color(250, 236, 214, 255),
            0, topY - 44, this.panelW - 68, Label.HorizontalAlign.CENTER);
        this.label(panel,
            ft ? `— ${TimeSystem.dateTextFull()}　今天是「${ft.name}」 —`
               : `— ${TimeSystem.dateTextFull()} 早晨 ${TimeSystem.clockText()} —`,
            19, ft ? new Color(226, 196, 255, 255) : new Color(198, 186, 214, 255),
            0, topY - 78, this.panelW - 68, Label.HorizontalAlign.CENTER);

        let y = topY - headerH;

        if (rec.collapsed) {
            this.label(panel, '你在外頭撐到半夜昏倒了…下次記得早點回房間睡覺。', 18,
                new Color(232, 150, 140, 255), 0, y - 16, this.panelW - 68, Label.HorizontalAlign.CENTER);
            y -= warnH;
        }

        // 統計列（左標題、右數值）
        for (let i = 0; i < lines.length; i++) {
            const ly = y - lineH / 2 - i * lineH;
            this.label(panel, lines[i].k, 21, new Color(214, 204, 226, 255),
                leftX, ly, 260, Label.HorizontalAlign.LEFT);
            this.label(panel, lines[i].v, 21, lines[i].c,
                rightX, ly, 320, Label.HorizontalAlign.RIGHT);
        }
        y -= lines.length * lineH;

        // 今日賣出明細
        if (detail.length) {
            this.label(panel, '今日賣出', 17, new Color(170, 162, 184, 255),
                leftX, y - 14, 200, Label.HorizontalAlign.LEFT);
            for (let i = 0; i < detail.length; i++) {
                const it = rec.items[detail[i]];
                const dy = y - 40 - i * 28;
                this.label(panel, `${detail[i]} ×${it.q}`, 18, new Color(230, 224, 238, 255),
                    leftX + 12, dy, 300, Label.HorizontalAlign.LEFT);
                this.label(panel, `${it.g} 金`, 18, new Color(255, 224, 130, 255),
                    rightX, dy, 200, Label.HorizontalAlign.RIGHT);
            }
        }

        // 開始新的一天
        this.button(panel, '開始新的一天', 220, 48, 0, -panelH / 2 + 46,
            new Color(78, 108, 84, 255), () => this.close());
        this.label(panel, 'Enter / 空白鍵 / Esc 關閉', 14, new Color(160, 152, 172, 255),
            0, -panelH / 2 + 14, 320, Label.HorizontalAlign.CENTER);
    }

    /** 組出統計列（沒發生的項目就不列，畫面才乾淨）。 */
    private summaryLines(rec: DayRecord): Array<{ k: string; v: string; c: Color }> {
        const gold = new Color(255, 224, 130, 255);
        const plain = new Color(236, 230, 244, 255);
        const rep = new Color(180, 220, 255, 255);
        const out: Array<{ k: string; v: string; c: Color }> = [];

        out.push({ k: '店裡營收', v: `${rec.revenue} 金（${rec.sales} 件）`, c: gold });
        if (rec.trade > 0) out.push({ k: '材料收購', v: `${rec.trade} 金`, c: gold });
        if (rec.spent > 0) out.push({ k: '支出', v: `-${rec.spent} 金`, c: new Color(232, 168, 160, 255) });
        out.push({ k: '採集 / 煉製', v: `${rec.gathered} 件 / ${rec.brewed} 瓶`, c: plain });

        const next = Reputation.nextNeed;
        const repTail = next === null ? '已滿級' : `${Reputation.points}/${next}`;
        out.push({
            k: '名聲',
            v: `＋${rec.rep}　Lv.${Reputation.level} ${Reputation.title}（${repTail}）`,
            c: rep,
        });
        out.push({ k: '目前金幣', v: `${Wallet.gold} 金`, c: gold });
        out.push({ k: '明日營業', v: DailyLog.hoursText(), c: plain });
        return out;
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
        lb.fontSize = 22;
        lb.color = new Color(245, 245, 250, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;

        const op = n.addComponent(UIOpacity);
        n.on(Node.EventType.TOUCH_START, () => { op.opacity = 170; });
        n.on(Node.EventType.TOUCH_END, () => { op.opacity = 255; onClick(); });
        n.on(Node.EventType.TOUCH_CANCEL, () => { op.opacity = 255; });
    }
}
