import { SaveManager } from './SaveManager';
import { GameArt } from './GameArt';
import { OUTFITS, OutfitDef, outfitById } from './data/outfits';

/**
 * 現在穿哪一套（純資料 module，仿 Wallet/Upgrades）。
 *
 * 換裝的實際效果只有一件事：叫 `GameArt.applyOutfit()` 換掉那批姿勢圖。之後所有拿女巫
 * 圖的地方（走路、採集、澆水、摘花、施法、睡覺）都是透過 GameArt 的 accessor 拿，
 * 所以**呼叫端一個都不用改**。
 */

const KEY = 'witch.outfit';

let current = load();

function load(): string {
    const v = SaveManager.getString(KEY);
    return v && outfitById(v).id === v ? v : OUTFITS[0].id;   // 防壞檔：認不得就回預設
}

export const Outfits = {
    all(): OutfitDef[] { return OUTFITS; },
    currentId(): string { return current; },
    currentDef(): OutfitDef { return outfitById(current); },

    /** 換上某一套（id 認不得就當預設）。 */
    set(id: string): void {
        const def = outfitById(id);
        current = def.id;
        SaveManager.setString(KEY, current);
        GameArt.applyOutfit(def.art);
    },

    /**
     * 把存檔裡那套套用到美術上。每個場景載入時呼叫一次（PlayerController.onLoad），
     * 因為 GameArt 的造型圖不像 module 資料那樣跨場景留著。
     */
    apply(): void {
        GameArt.applyOutfit(outfitById(current).art);
    },
};
