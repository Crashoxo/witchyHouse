import { Node, UITransform, Label, Color, Graphics, UIOpacity, Vec3, tween, find, view } from 'cc';

/**
 * 畫面上方冒一行字、飄一下就淡掉的小提示（例如「材料已收進倉庫」）。
 *
 * 是純 module 不是 Component —— 它只是生一個節點跑 tween，沒有需要每幀更新的狀態，
 * 也就不必像 Hud/Inventory 那樣做 ensure()。任何腳本 `Toast.show('…')` 就好。
 */
export const Toast = {
    show(text: string, seconds = 1.8): void {
        const canvas = find('Canvas');
        if (!canvas) return;

        const visH = view.getVisibleSize().height || 640;
        const w = Math.max(220, text.length * 20 + 48);
        const h = 40;

        const n = new Node('Toast');
        n.layer = canvas.layer;
        canvas.addChild(n);
        n.setPosition(0, visH / 2 - 96, 0);
        n.addComponent(UITransform).setContentSize(w, h);

        const g = n.addComponent(Graphics);
        g.lineWidth = 2;
        g.fillColor = new Color(28, 24, 20, 226);
        g.strokeColor = new Color(224, 200, 160, 220);
        g.rect(-w / 2, -h / 2, w, h);
        g.fill(); g.stroke();

        const t = new Node('t');
        t.layer = canvas.layer;
        n.addChild(t);
        t.addComponent(UITransform).setContentSize(w - 16, h);
        const lb = t.addComponent(Label);
        lb.string = text;
        lb.fontSize = 20;
        lb.color = new Color(248, 238, 220, 255);
        lb.horizontalAlign = Label.HorizontalAlign.CENTER;
        lb.verticalAlign = Label.VerticalAlign.CENTER;
        lb.overflow = Label.Overflow.SHRINK;

        const op = n.addComponent(UIOpacity);
        op.opacity = 0;
        tween(op).to(0.18, { opacity: 255 })
                 .delay(Math.max(0.2, seconds - 0.5))
                 .to(0.32, { opacity: 0 })
                 .call(() => n.destroy())
                 .start();
        tween(n).by(seconds, { position: new Vec3(0, 18, 0) }).start();
    },
};
