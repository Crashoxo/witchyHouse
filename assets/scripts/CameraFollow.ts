import { _decorator, Component, Node, Vec3 } from 'cc';
const { ccclass, property } = _decorator;

/**
 * 相機跟隨（用「捲動世界」的方式實現）。
 *
 * 做法：把這支腳本掛在 World 容器節點上（Player 和所有場景物件都是 World 的子節點）。
 *       每一幀把 World 移到 -target 的位置，讓 target（角色）永遠停在畫面正中央，
 *       周圍的地標就會相對捲動 —— 看起來就像相機跟著角色走。
 *
 * 用 lateUpdate：確保在 PlayerController 移動完角色「之後」才更新，畫面不會抖。
 */
@ccclass('CameraFollow')
export class CameraFollow extends Component {
    @property(Node) target: Node | null = null;   // 要跟隨的目標（把 Player 拖進來）

    private _p = new Vec3();

    lateUpdate() {
        if (!this.target) return;
        const t = this.target.position;
        this._p.set(-t.x, -t.y, this.node.position.z);
        this.node.setPosition(this._p);
    }
}
