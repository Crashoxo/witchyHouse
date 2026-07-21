import { _decorator, Component, Node, UITransform, Sprite } from 'cc';
import { GameArt } from './GameArt';
const { ccclass } = _decorator;

/**
 * 城鎮的景物擺設：掛在 town.scene 的 Props 節點上。
 *
 * 城門、噴泉、路燈、柵欄、花箱、灌木這些「有高度」的東西在這裡用程式生成，
 * 生為 Props 的子節點、錨點 (0.5, 0)，所以自動吃 YSortLayer 的前後遮擋——
 * 玩家走到噴泉上方就會被擋住，走到下方就在前面。
 *
 * 路面、橋、水窪那些平的素材不在這裡：它們已經烤進 `town-ground.png`，
 * 不需要遮擋也不需要節點。要調整城鎮路網就重跑產圖腳本換掉那張底圖。
 *
 * 想搬動或增減景物就改下面的 LAYOUT——不用碰場景檔。
 */

/** 一件景物：[美術名(GameArt.town), x, y, 顯示縮放]。座標是 Props 的本地座標。 */
type Piece = [string, number, number, number];

const LAYOUT: Piece[] = [
    ['arch', -1350, -40, 2.0],          // 西側城門（通往森林的路口）
    ['fountain', 0, -70, 2.2],          // 中央廣場噴泉

    // 主幹道與東側大道的路燈
    ['lamp-post', -680, 90, 2.0],
    ['lamp-post', -390, 90, 2.0],
    ['lamp-post', -680, -180, 2.0],
    ['lamp-post', -390, -180, 2.0],
    ['lamp-post', 450, 90, 2.0],
    ['lamp-post', 860, -180, 2.0],

    // 北側石板大街的小燈
    ['lamp-small', -150, 330, 2.2],
    ['lamp-small', 150, 330, 2.2],
    ['lamp-small', -150, 900, 2.2],
    ['lamp-small', 150, 900, 2.2],

    // 廣場邊的帶燈柵欄
    ['fence-lamp', -300, 200, 2.0],
    ['fence-lamp', 300, 200, 2.0],
    ['fence-lamp', 0, -330, 2.0],

    // 溪流東岸草原的白柵欄
    ['fence-white', 1530, 430, 2.0],
    ['fence-white', 1530, -80, 2.0],
    ['fence-white', 1250, 900, 2.0],

    // 各店門口的花箱
    ['planter', -1050, 700, 2.0],
    ['planter', -430, 700, 2.0],
    ['planter', 420, 700, 2.0],
    ['planter', 800, 60, 2.0],

    // 灌木與花叢點綴
    ['bush-green', -1250, 260, 2.0],
    ['bush-green', -560, 260, 2.0],
    ['bush-green', 620, 260, 2.0],
    ['bush-green', 1000, 360, 2.0],
    ['bush-green', -640, -300, 2.0],
    ['bush-green', 300, -420, 2.0],
    ['bush-green', -180, -880, 2.0],
    ['bush-green', 700, -880, 2.0],
    ['bush-green', -1400, 420, 2.0],
    ['bush-green', 1560, -300, 2.0],
    ['bush-green', -1120, -180, 2.0],
    ['bush-green', -1420, -560, 2.0],
    ['bush-green', -300, 850, 2.0],
    ['bush-green', 950, -700, 2.0],
    ['bush-pink', -1200, 260, 2.0],
    ['bush-pink', -510, 240, 2.0],
    ['bush-pink', 670, 240, 2.0],
    ['bush-pink', -1330, 420, 2.0],
    ['bush-pink', -600, -300, 2.0],
    ['bush-pink', 350, -420, 2.0],
    ['bush-pink', 1540, -20, 2.0],
    ['bush-pink', -230, -880, 2.0],
    ['bush-pink', -1060, -200, 2.0],
    ['bush-pink', -1370, -600, 2.0],
    ['bush-pink', 280, 850, 2.0],
    ['bush-pink', 1050, -840, 2.0],
    ['bush-white', -1160, 240, 2.0],
    ['bush-white', -470, 260, 2.0],
    ['bush-white', 720, 260, 2.0],
    ['bush-white', -1270, 400, 2.0],
    ['bush-white', -560, -320, 2.0],
    ['bush-white', 400, -400, 2.0],
    ['bush-white', 1560, 120, 2.0],
    ['bush-white', 750, -880, 2.0],
    ['bush-white', -900, -260, 2.0],
    ['bush-white', -1280, -420, 2.0],
    ['bush-white', 900, 400, 2.0],
    ['bush-white', -820, 180, 2.0],
];

@ccclass('TownProps')
export class TownProps extends Component {
    private spawned = false;

    onLoad() {
        GameArt.preload();
        GameArt.onReady(() => this.spawn());
    }

    private spawn() {
        if (this.spawned || !this.node.isValid) return;
        this.spawned = true;
        for (const [art, x, y, scale] of LAYOUT) {
            const f = GameArt.town(art);
            if (!f) continue;                       // 圖沒載到就跳過，不開天窗
            const n = new Node('town-' + art);
            n.layer = this.node.layer;
            this.node.addChild(n);
            const ut = n.addComponent(UITransform);
            ut.setAnchorPoint(0.5, 0);              // 腳點對齊 → YSortLayer 依 y 排前後
            ut.setContentSize(f.rect.width * scale, f.rect.height * scale);
            const sp = n.addComponent(Sprite);
            sp.sizeMode = Sprite.SizeMode.CUSTOM;
            sp.trim = false;
            sp.spriteFrame = f;
            n.setPosition(x, y, 0);
        }
    }
}
