import { _decorator, Component, Sprite, UITransform, SpriteFrame } from 'cc';
import { GameArt } from './GameArt';
import { TimeSystem } from './TimeSystem';
const { ccclass } = _decorator;

/**
 * 藥水室背景：掛在 brew.scene 的 Ground 節點上，執行期把背景圖（resources 載入）
 * 設到自己的 Sprite。**有白天/夜晚兩張**，依 TimeSystem.isNight 切換（18:00 後換夜晚），
 * 兩張尺寸相同→切換不位移。用 runtime 設定，就不必為背景手工做 sprite-frame meta。
 */
@ccclass('BrewRoom')
export class BrewRoom extends Component {
    private ready = false;
    private lastNight: boolean | null = null;

    onLoad() {
        GameArt.preload();
        GameArt.onReady(() => {
            // 兩張同尺寸，先用白天版設好 contentSize（之後只換圖不改尺寸）
            const f = GameArt.brewRoom(false);
            const sp = this.getComponent(Sprite);
            const ut = this.getComponent(UITransform);
            if (f && sp) {
                sp.sizeMode = Sprite.SizeMode.CUSTOM;
                if (ut) ut.setContentSize(f.rect.width, f.rect.height);
            }
            this.ready = true;
            this.apply(TimeSystem.isNight);
        });
    }

    update() {
        if (!this.ready) return;
        const night = TimeSystem.isNight;
        if (night !== this.lastNight) this.apply(night);
    }

    private apply(night: boolean) {
        const f = GameArt.brewRoom(night);
        const sp = this.getComponent(Sprite);
        if (f && sp) { sp.spriteFrame = f; this.lastNight = night; }
    }
}
