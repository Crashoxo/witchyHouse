import { _decorator, Component, Node, UITransform, Color, Graphics,
         input, Input, EventKeyboard, KeyCode, Vec3, Label } from 'cc';
import { UIState } from './UIState';
import { SceneFade } from './SceneFade';
const { ccclass, property } = _decorator;

/**
 * 門/入口：玩家**走上去就會換場景**（也還能按 E）。
 * 掛在當「門」的節點上（例：城鎮的小屋 → 進店內場景）。Player 需為同層兄弟節點。
 *
 * 為什麼是走上去而不是按 E：地圖邊界的傳送點本來就是走過去就換場景，門卻要按 E，
 * 同樣是發光的傳送點卻兩套規則反而最難懂；而且這樣按鍵分工才乾淨 ——
 * **E ＝跟東西互動（櫃台/鍋爐/NPC/採集），走上去＝換地方**。E 仍然保留可用。
 *
 * 兩個距離是分開的：
 *   interactRange ── 顯示浮動提示（大範圍，遠遠就看得到這裡是門）、也是按 E 的範圍
 *   autoRange     ── 真的把人送過去的範圍（小，跟 PortalGlow 畫的地上光圈差不多大）
 * 分開是必要的：提示範圍 140~200px，若拿它當自動觸發，在城鎮走過小屋旁邊就會被吸進店裡。
 */
@ccclass('SceneDoor')
export class SceneDoor extends Component {
    @property({ tooltip: '要進入的場景名稱，例：shop' })
    targetScene = '';
    @property({ tooltip: '提示文字' })
    hintText = '按 E 進入';
    @property({ tooltip: '玩家離多近才顯示提示 / 才能按 E（像素）' })
    interactRange = 200;
    @property({ tooltip: '走上去就自動換場景（關掉就變回只能按 E）' })
    autoEnter = true;
    @property({ tooltip: '走多近會自動換場景（像素）—— 跟地上那圈光暈差不多大' })
    autoRange = 70;
    /**
     * 門口相對節點原點的位移。整棟房子當一個節點時，節點原點在**房子正中央的底部**，
     * 而門通常不在正中央（小屋的拱門偏左）——沒有這個位移的話，地上的光圈會亮在
     * 房子中間、玩家也得走到房子中央才進得去。填「門在圖上的位置」即可。
     */
    @property({ tooltip: '門口相對節點原點的水平位移（像素，右為正）' })
    doorX = 0;
    @property({ tooltip: '門口相對節點原點的垂直位移（像素，上為正）' })
    doorY = 0;

    private player: Node | null = null;
    private hint: Node | null = null;
    private inRange = false;
    private switching = false;
    /**
     * 自動觸發是否已「解鎖」。⚠️ 從別的場景走進來時，玩家的出生點可能就落在門的
     * 觸發範圍內（藥水室出生點 (0,-250) 離 ExitDoor (0,-330) 只有 80px），那樣一載入
     * 就會立刻被彈回去、兩個場景無限來回。所以出生時若已站在範圍內就先鎖住，
     * 等玩家自己走出去一次才啟用。
     */
    private armed = true;

    onLoad() {
        this.player = this.node.parent?.getChildByName('Player') ?? null;
        this.armed = this.distToPlayer() > this.armThreshold();
        this.buildHint();
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }
    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
    }

    private onKeyDown(e: EventKeyboard) {
        if (e.keyCode !== KeyCode.KEY_E) return;
        // ⚠️ 按 E 也要看 armed，不能只有自動觸發看。出生點常常就落在門旁邊
        // （藥水室離門 80px、後花園離門 75px），只鎖自動觸發的話，玩家一進場景
        // 按 E 想做別的事（澆花、開櫃台）就被門送回上一個場景。
        if (!this.inRange || !this.armed) return;
        this.enter();
    }

    update() {
        if (!this.player) return;
        const dist = this.distToPlayer();
        this.inRange = dist <= this.interactRange;
        // 解鎖判定要在 autoEnter 之外做 —— 關掉自動過圖的門也要能解鎖，否則它會
        // 永遠停在上鎖狀態，連按 E 都進不去。
        if (!this.armed && dist > this.armThreshold()) this.armed = true;
        if (this.hint) this.hint.active = this.inRange && this.armed && !UIState.modalOpen;
        if (this.autoEnter && this.armed && dist <= this.autoRange) this.enter();
    }

    /**
     * 要走多遠才算「離開這道門」。比 autoRange 多留一段餘裕，一來免得剛好卡在
     * 邊界上一直開開關關，二來出生點若只比 autoRange 遠一點點（藥水室就是：出生
     * 離門 80px、觸發 70px），玩家一往下走幾步就被彈出去 —— 用這個門檻上鎖，
     * 就得先真的走進房間才會啟用。
     */
    private armThreshold(): number { return this.autoRange * 1.35; }

    /** 真的換場景（走上去或按 E 都走這裡）。 */
    private enter() {
        if (this.switching || UIState.modalOpen || !this.targetScene) return;
        this.switching = true;
        SceneFade.go(this.targetScene);   // 淡出→切場景→淡入
    }

    /** 門口的實際位置（節點原點 ＋ doorX/doorY）。 */
    doorPos(): Vec3 {
        const p = this.node.position;
        return new Vec3(p.x + this.doorX, p.y + this.doorY, p.z);
    }

    private distToPlayer(): number {
        if (!this.player) return Number.MAX_VALUE;
        return Vec3.distance(this.player.position, this.doorPos());
    }

    private buildHint() {
        const ut = this.getComponent(UITransform);
        // 提示掛在門口正上方（不是房子正中央上方）
        const topY = (ut ? ut.contentSize.height + 24 : 120) - this.doorY;

        const n = new Node('DoorHint');
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.addComponent(UITransform).setContentSize(200, 32);
        n.setPosition(this.doorX, topY, 0);

        const g = n.addComponent(Graphics);
        g.fillColor = new Color(20, 16, 28, 210);
        g.strokeColor = new Color(210, 190, 230, 220);
        g.lineWidth = 2;
        this.pill(g, -100, -16, 200, 32, 16);
        g.fill(); g.stroke();

        const t = new Node('t');
        t.layer = this.node.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(200, 32);
        const lb = t.addComponent(Label);
        lb.string = this.displayHint();
        lb.fontSize = 20;
        lb.color = new Color(245, 240, 250, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;

        n.active = false;
        this.hint = n;
    }

    /**
     * 自動觸發時把提示開頭的「按 E」拿掉（"按 E 進入店裡" → "進入店裡"）。
     * 場景檔裡存的字串還是舊的寫法，這裡在執行期修掉就不用去動場景。
     */
    private displayHint(): string {
        if (!this.autoEnter) return this.hintText;
        return this.hintText.replace(/^按\s*[EeＥ]\s*/, '');
    }

    private pill(g: Graphics, x: number, y: number, w: number, h: number, r: number) {
        g.rect(x, y, w, h);   // 一般方框（不圓角）
    }
}
