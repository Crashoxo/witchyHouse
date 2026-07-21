import { _decorator, Component, Node, Vec2, Vec3, input, Input, EventKeyboard, KeyCode,
         EventTouch, instantiate, Prefab, UITransform, director } from 'cc';
import { SpellProjectile } from './SpellProjectile';
import { UIState } from './UIState';
import { Inventory } from './Inventory';
import { Hud } from './Hud';
import { SceneFade } from './SceneFade';
import { QuestLog } from './QuestLog';
import { GameArt } from './GameArt';
import { CharacterAnimator } from './CharacterAnimator';
import { UpdatePanel } from './UpdatePanel';
const { ccclass, property } = _decorator;

/** 撞到地圖哪一側（給之後「切換下一張地圖」用）。 */
export type EdgeSide = 'left' | 'right' | 'top' | 'bottom';

/**
 * 俯視角魔女角色控制：
 *   WASD / 方向鍵 = 八方向移動
 *   滑鼠點地面    = 自動走過去（按方向鍵會立刻接手）
 *   J 或 空白鍵   = 往目前面向施放魔法彈
 *
 * 移動會被夾在地圖範圍內（走不出邊界）。邊界預設自動從同一層名叫 "Ground"
 * 的節點讀尺寸算出來；找不到就用底下的 worldHalfWidth / worldHalfHeight。
 * 撞到邊界時呼叫 onReachEdge()（目前只留接縫，之後接「進入下一張地圖」）。
 */
@ccclass('PlayerController')
export class PlayerController extends Component {
    @property moveSpeed = 200;                            // 移動速度（像素/秒）
    @property(Prefab) spellPrefab: Prefab | null = null;  // 拖入 Spell 預製體

    @property({ tooltip: '是否把角色夾在地圖範圍內（擋住邊界）' })
    clampToBounds = true;
    @property({ tooltip: '找不到 Ground 時用的地圖半寬（像素）' })
    worldHalfWidth = 1408;
    @property({ tooltip: '找不到 Ground 時用的地圖半高（像素）' })
    worldHalfHeight = 896;
    @property({ tooltip: '離邊界再往內縮多少（像素），避免角色圖貼齊切邊' })
    edgeMargin = 0;

    @property({ tooltip: "走到指定邊界要切換到的場景名稱（空字串＝先不切）。例：'town'" })
    nextMapScene = 'town';
    @property({ tooltip: "哪一側邊界會觸發切換：left / right / top / bottom" })
    nextMapEdge = 'right';

    private dir = new Vec2(0, 0);      // 目前移動方向
    private facing = new Vec2(1, 0);   // 最後面向（施法方向）
    private keys = new Set<number>();

    // 地圖邊界（World-local 座標）
    private minX = 0; private maxX = 0; private minY = 0; private maxY = 0;
    private switching = false;   // 已在切換地圖，避免重複觸發

    private ground: Node | null = null;      // 點擊移動的接收面
    private moveTarget: Vec3 | null = null;  // 點擊指定的目的地（null＝沒有）

    onLoad() {
        input.on(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        input.on(Input.EventType.KEY_UP, this.onKeyUp, this);
        this.computeBounds();
        // 點擊移動的事件掛在 Ground 上而不是全域 —— Ground 底下什麼都沒有，
        // 上面的 UI 面板（有 BlockInputEvents）會先接走點擊，所以按按鈕不會誤走。
        this.ground?.on(Node.EventType.TOUCH_END, this.onGroundClick, this);
        // 每個場景都有 Player → 在這裡叫出背包和金幣 HUD，讓它們永遠顯示
        Inventory.ensure();
        Hud.ensure();
        UpdatePanel.showOnce();   // 開遊戲第一個場景跳更新公告（換場景不重跳）
    }

    onDestroy() {
        input.off(Input.EventType.KEY_DOWN, this.onKeyDown, this);
        input.off(Input.EventType.KEY_UP, this.onKeyUp, this);
        // ⚠️ 一定要檢查 isValid：換場景時整棵樹一起銷毀，Ground 可能已經沒了。
        // 被銷毀的節點物件仍然是 truthy（`?.` 擋不掉），呼叫 off() 會踩到內部
        // 已成 null 的 _eventProcessor 而丟例外，連帶把場景的銷毀流程打斷。
        if (this.ground && this.ground.isValid) {
            this.ground.off(Node.EventType.TOUCH_END, this.onGroundClick, this);
        }
        this.ground = null;
        this.moveTarget = null;
    }

    /** 點地面 → 記下目的地，update 每幀走過去。 */
    private onGroundClick(e: EventTouch) {
        if (UIState.modalOpen) return;                        // 開著視窗時不接受點擊移動
        const ut = this.node.parent?.getComponent(UITransform);
        if (!ut) return;
        const ui = e.getUILocation();
        const p = ut.convertToNodeSpaceAR(new Vec3(ui.x, ui.y, 0));
        // 目的地夾在邊界內縮一點 —— 自動走到底不該把人帶去別張地圖，
        // 換場景仍然只由玩家自己按方向鍵推到邊界觸發。
        const m = 4;
        this.moveTarget = new Vec3(
            Math.min(Math.max(p.x, this.minX + m), this.maxX - m),
            Math.min(Math.max(p.y, this.minY + m), this.maxY - m), 0);
    }

    private onKeyDown(e: EventKeyboard) {
        this.keys.add(e.keyCode);
        if (UIState.modalOpen) return;                       // 開著視窗時不施法、不開任務簿
        if (e.keyCode === KeyCode.KEY_Q) { QuestLog.ensure()?.open(); return; }   // Q 開任務簿
        if (e.keyCode === KeyCode.KEY_J || e.keyCode === KeyCode.SPACE) this.cast();
    }
    private onKeyUp(e: EventKeyboard) { this.keys.delete(e.keyCode); }

    update(dt: number) {
        if (UIState.modalOpen) { this.moveTarget = null; return; }   // 開著視窗時角色不動
        const k = this.keys;
        let x = (k.has(KeyCode.KEY_D) || k.has(KeyCode.ARROW_RIGHT) ? 1 : 0)
              - (k.has(KeyCode.KEY_A) || k.has(KeyCode.ARROW_LEFT)  ? 1 : 0);
        let y = (k.has(KeyCode.KEY_W) || k.has(KeyCode.ARROW_UP)    ? 1 : 0)
              - (k.has(KeyCode.KEY_S) || k.has(KeyCode.ARROW_DOWN)  ? 1 : 0);

        if (x !== 0 || y !== 0) this.moveTarget = null;       // 鍵盤一動就接手，取消點擊移動
        else if (this.moveTarget) {
            const p = this.node.position;
            const tx = this.moveTarget.x - p.x, ty = this.moveTarget.y - p.y;
            const dist = Math.sqrt(tx * tx + ty * ty);
            if (dist <= Math.max(this.moveSpeed * dt, 2)) {   // 到了：貼齊目的地就收工
                this.node.setPosition(this.moveTarget.x, this.moveTarget.y, p.z);
                this.moveTarget = null;
                return;
            }
            x = tx / dist; y = ty / dist;
        }

        this.dir.set(x, y);
        if (this.dir.lengthSqr() > 0) {
            this.dir.normalize();
            this.facing.set(this.dir);                       // 記住最後移動方向當作面向
            const p = this.node.position;
            let nx = p.x + this.dir.x * this.moveSpeed * dt;
            let ny = p.y + this.dir.y * this.moveSpeed * dt;

            if (this.clampToBounds) {
                if (nx < this.minX) { nx = this.minX; this.onReachEdge('left'); }
                else if (nx > this.maxX) { nx = this.maxX; this.onReachEdge('right'); }
                if (ny < this.minY) { ny = this.minY; this.onReachEdge('bottom'); }
                else if (ny > this.maxY) { ny = this.maxY; this.onReachEdge('top'); }
            }
            this.node.setPosition(nx, ny, p.z);
        }
    }

    /** 從同一層的 "Ground" 節點算出可走範圍；沒有就用 worldHalfWidth/Height。 */
    private computeBounds() {
        let halfW = this.worldHalfWidth, halfH = this.worldHalfHeight, cx = 0, cy = 0;
        // Ground 不一定是玩家的兄弟（本專案 Player 在 Props 下、Ground 在 World 下），
        // 所以從父層往上一路找名叫 "Ground" 的子節點。
        let n: Node | null = this.node.parent;
        let ground: Node | null = null;
        while (n && !ground) { ground = n.getChildByName('Ground'); n = n.parent; }
        this.ground = ground;                    // 點擊移動也用這個節點當接收面
        const ut = ground?.getComponent(UITransform);
        if (ground && ut) {
            halfW = ut.contentSize.width / 2;
            halfH = ut.contentSize.height / 2;
            cx = ground.position.x;
            cy = ground.position.y;
        }
        this.minX = cx - halfW + this.edgeMargin;
        this.maxX = cx + halfW - this.edgeMargin;
        this.minY = cy - halfH + this.edgeMargin;
        this.maxY = cy + halfH - this.edgeMargin;
    }

    /**
     * 撞到地圖邊界時呼叫（持續推邊會每幀觸發）。
     * 之後要做「走到邊界進入下一張地圖」，就在這裡依 side 換場景 / 換地圖資料。
     */
    private onReachEdge(side: EdgeSide) {
        // 只有設定了 nextMapScene、而且撞的是指定那一側時，才切換到下一張地圖。
        if (this.switching || !this.nextMapScene || side !== this.nextMapEdge) return;
        this.switching = true;
        SceneFade.go(this.nextMapScene);   // 淡出→切場景→淡入
    }

    private cast() {
        if (!this.spellPrefab) return;
        const spell = instantiate(this.spellPrefab);
        this.node.parent!.addChild(spell);                   // 生在角色的同一層
        spell.setPosition(this.node.position);
        spell.getComponent(SpellProjectile)?.fire(this.facing);
        // 施法姿勢（正面圖，不翻面）；一移動就自動取消
        const f = GameArt.cast();
        if (f) this.getComponent(CharacterAnimator)?.playOneShot([f], 0.4, 0, true);
    }
}
