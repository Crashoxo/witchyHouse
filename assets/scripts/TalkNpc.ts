import { _decorator, Component, Node, UITransform, Color, Graphics, CCString,
         input, Input, EventKeyboard, KeyCode, Vec3, Label } from 'cc';
import { Dialogue, DialogueInput } from './Dialogue';
import { UIState } from './UIState';
import { Quests } from './Quests';
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
    @property({ tooltip: '頭像名（GameArt portraits：gnome/witch/elf/forestboy/動物名…；留空＝不顯示頭像）' })
    portrait = '';
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
    private marker: Node | null = null; // 頭頂任務標記（！可接／可回報）
    private markerLabel: Label | null = null;
    private inRange = false;

    onLoad() {
        this.player = this.node.parent?.getChildByName('Player') ?? null;
        this.buildHint();
        this.buildMarker();
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }

    private onKeyDown(e: EventKeyboard) {
        if (e.keyCode !== KeyCode.KEY_E) return;
        if (!this.inRange || UIState.modalOpen) return;   // 已開著別重複觸發
        // npcName 對得上任務 giver、而且此刻有任務可談 → 走任務對話；否則一般閒聊
        const qid = Quests.currentFor(this.npcName);
        if (qid) { this.openQuest(qid); return; }
        const lines = this.lines.length ? this.lines : TalkNpc.DEFAULT_LINES;
        Dialogue.ensure()?.open(this.npcName, lines, this.portrait);
    }

    /** 依任務狀態開對應對話：可接→提供＋接受/拒絕；進行中→提醒；可回報→領獎。 */
    private openQuest(qid: string) {
        const dlg = Dialogue.ensure();
        if (!dlg) return;
        const d = Quests.def(qid)!;
        const st = Quests.statusOf(qid);
        const name = this.npcName, portrait = this.portrait;

        if (st === 'available') {
            const lines: DialogueInput[] = d.offerLines.slice();
            lines.push({
                text: `任務：${d.title}（${Quests.objectiveText(d)}）\n獎勵：${Quests.rewardText(d)}`,
            });
            lines.push({
                text: '要接下這個任務嗎？',
                choices: [
                    { label: '接受', onPick: () => {
                        Quests.accept(qid);
                        Dialogue.ensure()?.open(name, ['好，就交給你了！（按 Q 可隨時查看任務）'], portrait);
                    } },
                    { label: '再想想' },
                ],
            });
            dlg.open(name, lines, portrait);
        } else if (st === 'active') {
            const lines: DialogueInput[] = d.activeLines.slice();
            lines.push({ text: `目前進度：${Quests.progressText(qid)}` });
            dlg.open(name, lines, portrait);
        } else if (st === 'ready') {
            const lines: DialogueInput[] = d.readyLines.slice();
            lines.push({
                text: '要現在回報領取獎勵嗎？',
                choices: [
                    { label: '回報', onPick: () => {
                        if (Quests.claim(qid)) {
                            const done: DialogueInput[] = d.doneLines.slice();
                            done.push({ text: `獲得：${Quests.rewardText(d)}` });
                            Dialogue.ensure()?.open(name, done, portrait);
                        }
                    } },
                    { label: '等一下' },
                ],
            });
            dlg.open(name, lines, portrait);
        }
    }

    update() {
        if (!this.player) return;
        this.inRange = Vec3.distance(this.player.position, this.node.position) <= this.interactRange;
        // 只有在範圍內、且沒有開著視窗時才顯示提示
        if (this.hint) this.hint.active = this.inRange && !UIState.modalOpen;
        this.updateMarker();
    }

    /** 依此 NPC 是否有任務可談，更新頭頂標記（可回報＝綠，可接＝黃，其餘隱藏）。 */
    private updateMarker() {
        if (!this.marker) return;
        if (UIState.modalOpen) { this.marker.active = false; return; }
        const qid = Quests.currentFor(this.npcName);
        if (!qid) { this.marker.active = false; return; }
        const ready = Quests.statusOf(qid) === 'ready';
        this.marker.active = true;
        if (this.markerLabel) this.markerLabel.color = ready
            ? new Color(140, 240, 150, 255)   // 可回報
            : new Color(255, 224, 110, 255);  // 可接／進行中
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

    /** 在 NPC 頭頂建一個任務標記「！」（可接／可回報時才顯示，顏色在 updateMarker 換）。 */
    private buildMarker() {
        const ut = this.getComponent(UITransform);
        const topY = ut ? ut.contentSize.height + 64 : 160;   // 比「按 E 交談」提示再高一點

        const n = new Node('QuestMark');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.addComponent(UITransform).setContentSize(40, 44);
        n.setPosition(0, topY, 0);

        const lb = n.addComponent(Label);
        lb.string = '！';
        lb.fontSize = 40;
        lb.color = new Color(255, 224, 110, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.enableOutline = true;
        lb.outlineColor = new Color(30, 22, 44, 235);
        lb.outlineWidth = 4;

        n.active = false;
        this.marker = n;
        this.markerLabel = lb;
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
