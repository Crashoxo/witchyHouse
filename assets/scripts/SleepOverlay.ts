import { _decorator, Component, Node, UITransform, Label, Sprite, Color, Graphics,
         UIOpacity, BlockInputEvents, view, tween, find } from 'cc';
import { GameArt } from './GameArt';
import { UIState } from './UIState';
import { TimeSystem } from './TimeSystem';
const { ccclass } = _decorator;

/**
 * 睡覺過場：淡入全螢幕深色幕，中央顯示睡覺中的女巫立繪（含她自己的小床，
 * 所以不會跟房間的床衝突），時間前進（白天睡→當晚、晚上睡→隔天早晨），
 * 顯示新的日期/時間，再淡出。仿其他 modal 的 ensure()；用完銷毀節點。
 */
@ccclass('SleepOverlay')
export class SleepOverlay extends Component {
    static instance: SleepOverlay | null = null;

    static ensure(): SleepOverlay | null {
        if (SleepOverlay.instance) return SleepOverlay.instance;
        const canvas = find('Canvas');
        if (!canvas) { console.warn('[SleepOverlay] 找不到 Canvas'); return null; }
        const n = new Node('SleepOverlay'); n.layer = canvas.layer; canvas.addChild(n);
        return n.addComponent(SleepOverlay);
    }

    private busy = false;
    onLoad() { SleepOverlay.instance = this; }
    onDestroy() { if (SleepOverlay.instance === this) SleepOverlay.instance = null; }

    /** 播放睡覺過場（期間 UIState.modalOpen=true → 角色不動、時間暫停，只在中段前進一次）。 */
    play() {
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

        // Zzz（女巫上方）＋ 醒來訊息（下方）
        this.makeLabel('Zzz…', 40, new Color(225, 225, 255, 255), -ww * scale * 0.28, 20 + dispH / 2 + 4);
        const msg = this.makeLabel('', 28, new Color(255, 240, 200, 255), 0, -H * 0.32)
            .getComponent(Label)!;

        tween(op).to(0.45, { opacity: 255 }).start();
        this.scheduleOnce(() => {
            TimeSystem.sleep();                                   // 白天→當晚 / 晚上→隔天早晨
            const period = TimeSystem.isNight ? '夜晚' : '早晨';
            msg.string = `— 第 ${TimeSystem.day} 天 ${period} ${TimeSystem.clockText()} —`;
        }, 0.7);
        this.scheduleOnce(() => this.finish(op), 2.3);
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

    private finish(op: UIOpacity) {
        tween(op).to(0.5, { opacity: 0 }).call(() => {
            UIState.modalOpen = false;
            this.busy = false;
            SleepOverlay.instance = null;
            this.node.destroy();
        }).start();
    }
}
