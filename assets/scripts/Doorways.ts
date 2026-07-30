import { Node, UITransform, find } from 'cc';
import { SceneDoor } from './SceneDoor';
import { SHOP_TO_GARDEN } from './data/garden';

/**
 * 執行期補上的場景門。
 *
 * 店裡右邊通往後花園的那道門是這樣裝的，而不是直接存進 shop.scene —— 這樣加新出入口
 * 就不用動場景檔（使用者的 Cocos 常常開著，改場景檔會被編輯器存檔蓋掉）。裝好之後
 * PortalGlow 會自己掃到它（它是掃 SceneDoor 元件），所以門一樣會發光、一樣走上去就過。
 *
 * 之後想在 Cocos 裡改門的位置，把節點做進場景檔、再把這裡的 install 拿掉即可。
 */
export const Doorways = {
    /** 在目前場景補上該有的門（重複呼叫安全）。 */
    install(): void {
        const props = find('Canvas/World/Props');
        if (!props || props.getChildByName('GardenDoor')) return;
        const node = new Node('GardenDoor');
        node.layer = props.layer;
        props.addChild(node);
        node.setPosition(SHOP_TO_GARDEN.x, SHOP_TO_GARDEN.y, 0);
        node.addComponent(UITransform).setContentSize(80, 40);
        const door = node.addComponent(SceneDoor);
        door.targetScene = 'garden';
        door.hintText = '到後花園';
    },
};
