import { director, find, Node, UITransform, Graphics, Color, UIOpacity, Widget,
         BlockInputEvents, tween } from 'cc';

/**
 * 場景切換淡入淡出：先在目前場景蓋一層黑幕淡出 → director.loadScene →
 * 在新場景蓋黑幕淡入。全部在 module 裡處理，不用逐場景擺元件。
 * 換場景就呼叫 `SceneFade.go('town')` 取代 director.loadScene。
 */
let busy = false;

/** 在目前 Canvas 底下蓋一層全螢幕黑幕（回傳它的 UIOpacity）。 */
function makeOverlay(): UIOpacity | null {
    const canvas = find('Canvas');
    if (!canvas) return null;
    const n = new Node('FadeOverlay');
    n.layer = canvas.layer;
    canvas.addChild(n);
    n.setSiblingIndex(9999);                 // 蓋在最上層
    n.addComponent(UITransform).setContentSize(4000, 3000);
    n.addComponent(BlockInputEvents);        // 淡出淡入期間擋操作
    const g = n.addComponent(Graphics);
    g.fillColor = new Color(0, 0, 0, 255);
    g.rect(-2000, -1500, 4000, 3000);
    g.fill();
    const w = n.addComponent(Widget);
    w.isAlignHorizontalCenter = w.isAlignVerticalCenter = true;
    w.horizontalCenter = w.verticalCenter = 0;
    w.updateAlignment();
    return n.addComponent(UIOpacity);
}

export const SceneFade = {
    /** 淡出 → 載入場景 → 淡入。dur＝單邊時間（秒）。 */
    go(sceneName: string, dur = 0.3): void {
        if (busy) return;
        busy = true;

        const op = makeOverlay();
        if (!op) { director.loadScene(sceneName); busy = false; return; }   // 沒 Canvas 就直接切

        op.opacity = 0;
        tween(op)
            .to(dur, { opacity: 255 })
            .call(() => {
                director.loadScene(sceneName, () => {
                    // 新場景已就緒 → 蓋黑幕淡入
                    const op2 = makeOverlay();
                    if (!op2) { busy = false; return; }
                    op2.opacity = 255;
                    tween(op2)
                        .to(dur, { opacity: 0 })
                        .call(() => { op2.node.destroy(); busy = false; })
                        .start();
                });
            })
            .start();
    },
};
