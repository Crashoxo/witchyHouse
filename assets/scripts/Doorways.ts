import { Node, UITransform, find } from 'cc';
import { SceneDoor } from './SceneDoor';
import { StorageCabinet } from './StorageCabinet';
import { Wardrobe } from './Wardrobe';
import { SHOP_TO_GARDEN } from './data/garden';

/** 藥水室（女巫房間）左邊背景畫好的那口木箱 ＝ 倉庫的位置。 */
const CHEST = { x: -360, y: -125 };
/** 同一面牆上那座雕花木櫃 ＝ 衣櫃。離木箱 320px，兩個 E 不會打架。 */
const WARDROBE = { x: -505, y: 160 };

/**
 * 執行期補上的場景物件（門、倉庫）。
 *
 * 這些東西不直接存進場景檔 —— 使用者的 Cocos 常常開著，改場景檔會被編輯器存檔蓋掉。
 * 裝好之後 PortalGlow 會自己掃到門（它是掃 SceneDoor 元件），所以門一樣會發光、
 * 一樣走上去就過。之後想在 Cocos 裡自己擺，把節點做進場景檔再把這裡的安裝拿掉即可。
 */
export const Doorways = {
    /** 在指定場景補上該有的東西（重複呼叫安全）。 */
    install(scene: string): void {
        const props = find('Canvas/World/Props');
        if (!props) return;

        // 店裡右邊通往後花園的門
        if (scene === 'shop' && !props.getChildByName('GardenDoor')) {
            const node = new Node('GardenDoor');
            node.layer = props.layer;
            props.addChild(node);
            node.setPosition(SHOP_TO_GARDEN.x, SHOP_TO_GARDEN.y, 0);
            node.addComponent(UITransform).setContentSize(80, 40);
            const door = node.addComponent(SceneDoor);
            door.targetScene = 'garden';
            door.hintText = '到後花園';
        }

        // 房間裡的倉庫：背景左邊那口木箱上放一個隱形觸發（同 brew.scene 的床）。
        // ⚠️ 擺 (-360,-125)：鍋爐 (59,-135) 與出口 (0,-330) 的感應半徑都是 200，
        // 這裡離兩者都有 410px 以上，不會有兩個東西搶同一顆 E 的問題（花園的門踩過）。
        if (scene === 'brew' && !props.getChildByName('StorageChest')) {
            const node = new Node('StorageChest');
            node.layer = props.layer;
            props.addChild(node);
            node.setPosition(CHEST.x, CHEST.y, 0);
            node.addComponent(UITransform).setContentSize(110, 70);
            node.addComponent(StorageCabinet);
        }

        // 衣櫃（同一面牆再往上）：木箱感應 150、衣櫃 130，兩者相距 320px 才不會搶同一顆 E
        if (scene === 'brew' && !props.getChildByName('Wardrobe')) {
            const node = new Node('Wardrobe');
            node.layer = props.layer;
            props.addChild(node);
            node.setPosition(WARDROBE.x, WARDROBE.y, 0);
            node.addComponent(UITransform).setContentSize(110, 120);
            node.addComponent(Wardrobe).interactRange = 130;
        }
    },
};
