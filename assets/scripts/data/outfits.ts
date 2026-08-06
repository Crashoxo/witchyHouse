/**
 * 造型（換裝）「內容」資料。
 *
 * 一套造型 ＝ 一整張女巫圖集 `resources/witch8/<art>.png`（站姿/走路/跑步/施法）
 * ＋ 一張 `<art>-sleep.png`。**不是把衣服疊成圖層** —— 帽子與披風本身就是角色輪廓，
 * 而且只有幾套完整造型，分層那種「多部位排列組合」的好處用不到。
 * 三套的圖是 tools/export_witch8.py 從預設那張改色生出來的（可重跑）。
 *
 * `art: ''` ＝預設造型，用 `witch8/base.png`。
 */
export interface OutfitDef {
    /** 存檔用的 id。 */
    id: string;
    /** 衣櫃面板顯示的名稱。 */
    name: string;
    /** 一句話說明。 */
    desc: string;
    /** `resources/witch8/<art>.png` 的檔名；空字串＝預設的 base.png。 */
    art: string;
    /** 立繪：`resources/portraits/<portrait>.png`；空字串＝沒有立繪（畫個色塊代替）。 */
    portrait: string;
}

// ⚠️ 2026-08-07 換角色後，換裝改成「把緞邊的緋紅改色」（黑袍本身不動）——
// 新角色是黑袍，舊那套「紫色轉色相」沒東西可轉。id 保持原樣，存檔才不會失效。
export const OUTFITS: OutfitDef[] = [
    { id: 'default', name: '緋紅緞邊', art: '', portrait: 'outfit8-default',
      desc: '黑帽黑袍配暗紅緞帶與滾邊，出門採集最順手的一套。' },
    { id: 'green', name: '苔綠緞邊', art: 'green', portrait: 'outfit8-green',
      desc: '緞帶染成森林苔綠，走在樹影底下幾乎看不見人。' },
    { id: 'brown', name: '琥珀緞邊', art: 'brown', portrait: 'outfit8-brown',
      desc: '琥珀金的緞帶與滾邊，適合遠行到糖果鎮進貨。' },
    { id: 'ivory', name: '霜白緞邊', art: 'ivory', portrait: 'outfit8-ivory',
      desc: '素白緞帶，調配藥水時最不怕沾上藥漬。' },
];

export function outfitById(id: string): OutfitDef {
    for (const o of OUTFITS) if (o.id === id) return o;
    return OUTFITS[0];
}
