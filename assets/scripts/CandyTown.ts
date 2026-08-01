import { _decorator, Component, find } from 'cc';
import { GameArt } from './GameArt';
import { GoodsShop } from './GoodsShop';
import { CandyFolk } from './CandyFolk';
import { CANDY_GOODS } from './data/candy';
const { ccclass } = _decorator;

/**
 * 糖果鎮（candy.scene）：森林北邊那張地圖。
 *
 * ⚠️ 地圖、房子、裝飾、NPC **都是 candy.scene 裡的真節點**（使用者要能在 Cocos 裡
 * 自己拖），所以這支不再生成任何東西。它只做兩件執行期才做得到的事：
 *   ① 把貨品清單交給場景裡那個商店節點（清單是 TS 資料，不適合序列化進場景）
 *   ② 叫出街上晃來晃去的路人（那些會動，必須執行期生成）
 *
 * 進出是「走到地圖邊界」：森林北側 → 糖果鎮、糖果鎮南側 → 森林，兩邊都登記在
 * data/portals.ts，PortalGlow 會在那個點畫光圈。
 */
@ccclass('CandyTown')
export class CandyTown extends Component {
    static instance: CandyTown | null = null;

    /** 掛到 candy.scene 既有的 Props 節點上（重複呼叫安全）。 */
    static ensure(): CandyTown | null {
        if (CandyTown.instance && CandyTown.instance.isValid) return CandyTown.instance;
        const props = find('Canvas/World/Props');
        if (!props) { console.warn('[CandyTown] 找不到 World/Props'); return null; }
        return props.getComponent(CandyTown) ?? props.addComponent(CandyTown);
    }

    onLoad() {
        CandyTown.instance = this;
        GameArt.preload();
        this.wireShop();
        CandyFolk.ensure();          // 街上晃來晃去的軟糖鱷與薑餅人
    }

    onDestroy() {
        if (CandyTown.instance === this) CandyTown.instance = null;
    }

    /** 場景裡的商店節點只存了店名與感應範圍，貨品清單在這裡補上。 */
    private wireShop() {
        const node = this.node.getChildByName('tamer');
        const shop = node?.getComponent(GoodsShop);
        if (shop) shop.goods = CANDY_GOODS.slice();
        else console.warn('[CandyTown] 場景裡找不到掛著 GoodsShop 的 tamer 節點');
    }
}
