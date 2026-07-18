import { _decorator, Component, Node, UITransform, Color, Graphics, CCString,
         input, Input, EventKeyboard, KeyCode, Vec3, Label } from 'cc';
import { Dialogue } from './Dialogue';
import { UIState } from './UIState';
const { ccclass, property } = _decorator;

/**
 * 可交談的 NPC：掛在城鎮的 NPC / 建築節點上。玩家走近顯示「按 E 交談」，
 * 按 E 跳出對話框，一句一句往下讀（比照 ShopBuilding 的互動慣例）。
 *
 * NPC 和 Player 都在 Props 底下 → 直接找兄弟節點抓 Player（同 GatherTree/ShopBuilding）。
 * lines 留空時用內建的預設台詞，方便還沒在 inspector 填字時也能測。
 */
@ccclass('TalkNpc')
export class TalkNpc extends Component {
    @property({ tooltip: 'NPC 名字（對話框顯示）' })
    npcName = '村民';
    @property({ type: [CCString], tooltip: '對話內容，一句一格，走近按 E 依序顯示（留空＝用預設台詞）' })
    lines: string[] = [];
    @property({ tooltip: '玩家離多近才能交談（像素）' })
    interactRange = 200;

    /** 沒在 inspector 填台詞時的預設對話。 */
    private static readonly DEFAULT_LINES = [
        '嗨，旅行者！歡迎來到魔法小鎮。',
        '往東邊的森林去採些材料，回你的店裡上架，客人自然會上門喔。',
        '有空再來找我聊聊吧！',
    ];

    private player: Node | null = null;
    private hint: Node | null = null;   // 「按 E 交談」浮動提示
    private inRange = false;

    onLoad() {
        this.player = this.node.parent?.getChildByName('Player') ?? null;
        this.buildHint();
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }

    private onKeyDown(e: EventKeyboard) {
        if (e.keyCode !== KeyCode.KEY_E) return;
        if (!this.inRange || UIState.modalOpen) return;   // 已開著別重複觸發
        const lines = this.lines.length ? this.lines : TalkNpc.DEFAULT_LINES;
        Dialogue.ensure()?.open(this.npcName, lines);
    }

    update() {
        if (!this.player) return;
        this.inRange = Vec3.distance(this.player.position, this.node.position) <= this.interactRange;
        // 只有在範圍內、且沒有開著視窗時才顯示提示
        if (this.hint) this.hint.active = this.inRange && !UIState.modalOpen;
    }

    /** 在 NPC 上方建一個「按 E 交談」文字提示（預設隱藏）。 */
    private buildHint() {
        const ut = this.getComponent(UITransform);
        const topY = ut ? ut.contentSize.height + 24 : 120;

        const n = new Node('TalkHint');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.addComponent(UITransform).setContentSize(180, 32);
        n.setPosition(0, topY, 0);

        const g = n.addComponent(Graphics);
        g.fillColor = new Color(20, 16, 28, 210);
        g.strokeColor = new Color(210, 190, 230, 220);
        g.lineWidth = 2;
        this.pill(g, -90, -16, 180, 32, 16);
        g.fill(); g.stroke();

        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(180, 32);
        const lb = t.addComponent(Label);
        lb.string = '按 E 交談';
        lb.fontSize = 20;
        lb.color = new Color(245, 240, 250, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;

        n.active = false;
        this.hint = n;
    }

    private pill(g: Graphics, x: number, y: number, w: number, h: number, r: number) {
        const H = Math.PI / 2;
        g.moveTo(x + r, y);
        g.lineTo(x + w - r, y);
        g.arc(x + w - r, y + r, r, -H, 0, false);
        g.lineTo(x + w, y + h - r);
        g.arc(x + w - r, y + h - r, r, 0, H, false);
        g.lineTo(x + r, y + h);
        g.arc(x + r, y + h - r, r, H, Math.PI, false);
        g.lineTo(x, y + r);
        g.arc(x + r, y + r, r, Math.PI, Math.PI + H, false);
        g.close();
    }
}
