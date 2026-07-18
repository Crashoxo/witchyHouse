import { _decorator, Component, Sprite, UITransform } from 'cc';
import { GameArt } from './GameArt';
const { ccclass } = _decorator;

/**
 * 藥水室背景：掛在 brew.scene 的 Ground 節點上，執行期把背景圖（resources 載入）
 * 設到自己的 Sprite。用 runtime 設定，就不必為背景手工做 sprite-frame meta。
 */
@ccclass('BrewRoom')
export class BrewRoom extends Component {
    onLoad() {
        GameArt.preload();
        GameArt.onReady(() => {
            const f = GameArt.brewRoom();
            const sp = this.getComponent(Sprite);
            if (f && sp) {
                sp.sizeMode = Sprite.SizeMode.CUSTOM;
                sp.spriteFrame = f;
                const ut = this.getComponent(UITransform);
                if (ut) ut.setContentSize(f.rect.width, f.rect.height);
            }
        });
    }
}
