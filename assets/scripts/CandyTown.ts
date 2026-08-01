import { _decorator, Component, Node, UITransform, Sprite, find } from 'cc';
import { GameArt } from './GameArt';
import { TalkNpc } from './TalkNpc';
import { GoodsShop } from './GoodsShop';
import { CandyFolk } from './CandyFolk';
import { ShadowLayer } from './ShadowLayer';
import { CANDY_NPCS, CANDY_GOODS } from './data/candy';
const { ccclass } = _decorator;

/**
 * 糖果鎮（candy.scene）：森林北邊那張地圖。
 *
 * 場景檔只有 Canvas/World/Ground/Props/Player 這棵空樹，地圖背景、鎮上的角色、
 * 街上的小東西全部在這裡執行期裝起來（同 GardenRoom / BrewRoom 的作法）——
 * 不用改場景檔，也不用替每張圖手工做 spriteFrame 的 meta。
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

    private built = false;

    onLoad() {
        CandyTown.instance = this;
        GameArt.preload();
        GameArt.onReady(() => { if (this.isValid) this.build(); });
        this.build();
        CandyFolk.ensure();          // 街上晃來晃去的軟糖鱷與芽苗
    }

    onDestroy() {
        if (CandyTown.instance === this) CandyTown.instance = null;
    }

    private build() {
        this.applyBackground();
        if (this.built) return;
        if (!GameArt.candy(CANDY_NPCS[0].art)) return;   // 美術還沒好，等 onReady 再來
        this.built = true;
        for (const def of CANDY_NPCS) this.buildNpc(def);
    }

    /** 地圖背景在執行期塞給 Ground（避免手工做 spriteFrame 的 meta）。 */
    private applyBackground() {
        const ground = find('Canvas/World/Ground');
        const frame = GameArt.candyMap();
        if (!ground || !frame) return;
        const sp = ground.getComponent(Sprite);
        if (sp && sp.spriteFrame !== frame) sp.spriteFrame = frame;
        ground.getComponent(UITransform)?.setContentSize(frame.rect.width, frame.rect.height);
    }

    private buildNpc(def: typeof CANDY_NPCS[0]) {
        const frame = GameArt.candy(def.art);
        if (!frame) return;
        const n = new Node(def.id);
        n.layer = this.node.layer;
        this.node.addChild(n);
        n.setPosition(def.x, def.y, 0);

        const ut = n.addComponent(UITransform);
        ut.setAnchorPoint(0.5, 0);                       // 錨點在腳底 → 吃 YSort 遮擋
        const w = (frame.rect.width || frame.originalSize.width) * def.scale;
        const h = (frame.rect.height || frame.originalSize.height) * def.scale;
        ut.setContentSize(w, h);
        const sp = n.addComponent(Sprite);
        sp.sizeMode = Sprite.SizeMode.CUSTOM;
        sp.trim = false;
        sp.spriteFrame = frame;
        ShadowLayer.follow(n, w);

        if (def.shopTitle) {
            // 商店：按 E 開購買面板（貨品清單在 data/candy）
            const shop = n.addComponent(GoodsShop);
            shop.shopTitle = def.shopTitle;
            shop.goods = CANDY_GOODS.slice();
            shop.interactRange = 150;
        } else {
            const talk = n.addComponent(TalkNpc);
            talk.npcName = def.name;
            talk.lines = def.lines.slice();
            talk.interactRange = 150;
        }
    }
}
