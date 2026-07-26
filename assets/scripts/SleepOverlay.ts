import { _decorator, Component, Node, UITransform, Label, Sprite, Color, Graphics,
         UIOpacity, BlockInputEvents, director, view, tween, find } from 'cc';
import { GameArt } from './GameArt';
import { UIState } from './UIState';
import { TimeSystem } from './TimeSystem';
import { DaySummaryPanel } from './DaySummaryPanel';
import { SceneFade } from './SceneFade';
const { ccclass } = _decorator;

/**
 * 睡覺過場：淡入全螢幕深色幕，中央顯示睡覺中的女巫立繪（含她自己的小床，
 * 所以不會跟房間的床衝突），時間前進（白天睡→當晚、晚上睡→隔天早晨），
 * 顯示新的日期/時間，再淡出。仿其他 modal 的 ensure()；用完銷毀節點。
 *
 * 兩個入口：
 *   play()        —— 走到床邊按 E 主動睡覺（由本過場推進時間）。
 *   playCollapse()—— 撐到 02:00 昏倒。此時 TimeSystem 已經自己跳過日了，所以
 *                    **不再推進時間**，只演過場；而且醒來一定要在房間，
 *                    人不在 brew 場景時趁畫面全黑直接載入房間再淡入。
 * 昏倒的觸發靠 `arm()` 註冊 TimeSystem.onNewDay（由 PlayerController.onLoad 呼叫，
 * module 旗標保證整個遊戲只註冊一次）。
 */

/** 睡覺的房間場景名。 */
const ROOM_SCENE = 'brew';
let armed = false;

@ccclass('SleepOverlay')
export class SleepOverlay extends Component {
    static instance: SleepOverlay | null = null;

    /** 註冊「昏倒也要演睡覺過場」的回呼（整個遊戲只註冊一次）。 */
    static arm(): void {
        if (armed) return;
        armed = true;
        TimeSystem.onNewDay(cause => {
            if (cause !== 'collapse') return;      // 自己去睡的話，過場已經在演了
            const o = SleepOverlay.ensure();
            if (o) o.playCollapse();
            else DaySummaryPanel.showPending();     // 沒 Canvas 的極端狀況：至少別把結算吞掉
        });
    }

    static ensure(): SleepOverlay | null {
        if (SleepOverlay.instance) return SleepOverlay.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[SleepOverlay] 找不到 Canvas'); return null; }
        const n = new Node('SleepOverlay'); n.layer = canvas.layer; canvas.addChild(n);
        return n.addComponent(SleepOverlay);
    }

    private busy = false;
    onLoad() { SleepOverlay.instance = this; }
    onDestroy() {
        if (SleepOverlay.instance === this) SleepOverlay.instance = null;
        // 過場演到一半被換場景銷毀（極少見）時，別把 modalOpen 留在 true 讓玩家動不了；
        // 還沒顯示的結算會由新場景 PlayerController.onLoad 的 showPending() 補上。
        if (this.busy) UIState.modalOpen = false;
    }

    /** 上床睡覺（本過場負責推進時間）。 */
    play() { this.run(false); }

    /** 撐到 02:00 昏倒（時間已由 TimeSystem 跳過日；醒來會回到房間）。 */
    playCollapse() { this.run(true); }

    /** 播放睡覺過場（期間 UIState.modalOpen=true → 角色不動、時間暫停，只在中段前進一次）。 */
    private run(collapsed: boolean) {
        if (this.busy) return;
        this.busy = true;
        UIState.modalOpen = true;
        GameArt.preload();

        const layer = this.node.layer;
        const vs = view.getVisibleSize();
        const W = vs.width, H = vs.height;

        this.addComponent(UITransform)!.setContentSize(W, H);
        this.node.setPosition(0, 0, 0);
        this.addComponent(BlockInputEvents);
        const op = this.addComponent(UIOpacity)!; op.opacity = 0;

        // 全螢幕深色幕
        const g = this.addComponent(Graphics)!;
        g.fillColor = new Color(8, 6, 16, 255);
        g.rect(-W / 2, -H / 2, W, H); g.fill();

        // 睡覺立繪（等比縮到約 55% 螢幕高）
        const wn = new Node('witch'); wn.layer = layer; this.node.addChild(wn);
        const wut = wn.addComponent(UITransform);
        const sp = wn.addComponent(Sprite); sp.sizeMode = Sprite.SizeMode.CUSTOM;
        const wf = GameArt.sleeping();
        let ww = 242, wh = 254;
        if (wf) { ww = wf.rect.width; wh = wf.rect.height; sp.spriteFrame = wf; }
        const scale = Math.min(W * 0.5 / ww, H * 0.55 / wh);
        const dispH = wh * scale;
        wut.setContentSize(ww * scale, dispH);
        wn.setPosition(0, 20, 0);
        GameArt.onReady(() => { const f = GameArt.sleeping(); if (f && sp.isValid) sp.spriteFrame = f; });

        // Zzz（女巫上方）＋ 昏倒說明（上方）＋ 醒來訊息（下方）
        this.makeLabel('Zzz…', 40, new Color(225, 225, 255, 255), -ww * scale * 0.28, 20 + dispH / 2 + 4);
        if (collapsed) {
            this.makeLabel('你撐到半夜，就這樣睡著了…', 24, new Color(232, 170, 160, 255),
                0, H * 0.30);
        }
        const msg = this.makeLabel('', 28, new Color(255, 240, 200, 255), 0, -H * 0.32)
            .getComponent(Label)!;

        tween(op).to(0.45, { opacity: 255 }).start();
        this.scheduleOnce(() => {
            // 昏倒的話 TimeSystem 已經自己跳過日了，這裡只有主動睡覺要推進時間
            if (!collapsed) TimeSystem.sleep();                   // 白天→當晚 / 晚上→隔天早晨
            const period = TimeSystem.isNight ? '夜晚' : '早晨';
            msg.string = `— ${TimeSystem.dateTextFull()} ${period} ${TimeSystem.clockText()} —`;
        }, 0.7);
        this.scheduleOnce(() => this.finish(op, collapsed), 2.3);
    }

    private makeLabel(text: string, size: number, color: Color, x: number, y: number): Node {
        const n = new Node('lb'); n.layer = this.node.layer; this.node.addChild(n);
        n.addComponent(UITransform).setContentSize(640, size + 12);
        n.setPosition(x, y, 0);
        const lb = n.addComponent(Label);
        lb.string = text; lb.fontSize = size; lb.color = color;
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.enableOutline = true; lb.outlineColor = new Color(0, 0, 0, 180); lb.outlineWidth = 3;
        return n;
    }

    private finish(op: UIOpacity, collapsed: boolean) {
        // 昏倒醒來一定要在房間：畫面現在是全黑的，趁這時候直接載入 brew 再淡入，
        // 玩家不會看到切場景。本節點會隨舊場景一起銷毀，所以後續交給 module 層的閉包。
        if (collapsed && director.getScene()?.name !== ROOM_SCENE) {
            SceneFade.go(ROOM_SCENE, 0.4, {
                skipFadeOut: true,
                onArrive: () => {
                    // 新場景的 PlayerController.onLoad 通常已經把結算叫出來了；沒有的話這裡補。
                    DaySummaryPanel.showPending();
                    // 沒有結算面板擋著就把操作解凍（面板自己開著時 modalOpen 要維持 true）
                    if (!DaySummaryPanel.instance?.isOpen()) UIState.modalOpen = false;
                },
            });
            return;
        }
        tween(op).to(0.5, { opacity: 0 }).call(() => {
            UIState.modalOpen = false;
            this.busy = false;
            SleepOverlay.instance = null;
            this.node.destroy();
            // 睡到隔天的話，過場演完才跳當日結算（結算面板會自己再把 modalOpen 打開）
            DaySummaryPanel.showPending();
        }).start();
    }
}
