import { _decorator, Component, Node, Vec3, UITransform, view } from 'cc';
const { ccclass, property } = _decorator;

/**
 * 相機跟隨（用「捲動世界」的方式實現）。
 *
 * 做法：把這支腳本掛在 World 容器節點上（Player 和所有場景物件都是 World 的子節點）。
 *       每一幀把 World 移到 -target 的位置，讓 target（角色）永遠停在畫面正中央，
 *       周圍的地標就會相對捲動 —— 看起來就像相機跟著角色走。
 *
 * clampToMap＝true 時，會把「相機中心」夾在地圖範圍往內縮半個畫面的區域內：
 *   角色走到地圖邊緣時，世界停住、改由角色往畫面邊緣移動，就不會捲過頭而
 *   露出地圖外的相機底色。地圖比畫面小時則置中。地圖範圍讀同層子節點 "Ground"。
 *
 * 用 lateUpdate：確保在 PlayerController 移動完角色「之後」才更新，畫面不會抖。
 */
@ccclass('CameraFollow')
export class CameraFollow extends Component {
    @property(Node) target: Node | null = null;   // 要跟隨的目標（把 Player 拖進來）
    @property({ tooltip: '是否把相機夾在地圖內（貼邊不露底色）' })
    clampToMap = true;

    private _p = new Vec3();

    lateUpdate() {
        if (!this.target) return;
        const t = this.target.position;
        let cx = t.x, cy = t.y;

        if (this.clampToMap) {
            const ground = this.node.getChildByName('Ground');
            const gut = ground?.getComponent(UITransform);
            if (ground && gut) {
                // 地圖矩形（World-local）：用 Ground 的錨點換算左下角
                const w = gut.contentSize.width, h = gut.contentSize.height;
                const ax = gut.anchorPoint.x, ay = gut.anchorPoint.y;
                const left = ground.position.x - ax * w;
                const bottom = ground.position.y - ay * h;

                // 畫面（視窗）大小＝設計解析度；World 在 Canvas 下，單位＝UI px
                const vs = view.getVisibleSize();
                const halfVW = vs.width / 2, halfVH = vs.height / 2;

                cx = this.clampCenter(cx, left, left + w, halfVW);
                cy = this.clampCenter(cy, bottom, bottom + h, halfVH);
            }
        }

        this._p.set(-cx, -cy, this.node.position.z);
        this.node.setPosition(this._p);
    }

    /** 把相機中心夾在 [lo+half, hi-half]；地圖比畫面小則取中點。 */
    private clampCenter(c: number, lo: number, hi: number, half: number): number {
        const min = lo + half, max = hi - half;
        if (min > max) return (lo + hi) / 2;   // 地圖比畫面窄 → 置中
        return c < min ? min : c > max ? max : c;
    }
}
