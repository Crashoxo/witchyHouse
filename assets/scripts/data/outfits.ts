/**
 * 造型（換裝）「內容」資料。
 *
 * 一套造型 ＝ 一整組女巫姿勢圖，放在 `resources/witch/<art>/`（走路 5 幀、待機、採集 3、
 * 施法、澆水 4、摘花 4、睡姿，共 19 張）。**不是把衣服疊成圖層** —— 這批圖的披風與裙襬
 * 本身就是角色輪廓，拆不開；而且只有三套完整造型，分層那種「多部位排列組合」的好處用不到。
 *
 * `art: ''` ＝預設造型，直接用場景/原本那批圖，不需要資料夾。
 * 造型資料夾裡**缺哪張就沿用預設哪張**（GameArt.loadGuarded），所以之後想手繪替換，
 * 丟幾張進去覆蓋就生效，不必一次補齊 19 張。
 */
export interface OutfitDef {
    /** 存檔用的 id。 */
    id: string;
    /** 衣櫃面板顯示的名稱。 */
    name: string;
    /** 一句話說明。 */
    desc: string;
    /** `resources/witch/<art>/` 的資料夾名；空字串＝預設那批圖。 */
    art: string;
    /** 立繪：`resources/portraits/<portrait>.png`；空字串＝沒有立繪（畫個色塊代替）。 */
    portrait: string;
}

export const OUTFITS: OutfitDef[] = [
    { id: 'default', name: '旅裝', art: '', portrait: 'outfit-default',
      desc: '綴著星月的藍帽配紅紋披風，出門採集最順手的一套。' },
    { id: 'green', name: '綠洋裝', art: 'green', portrait: 'outfit-green',
      desc: '綴滿金線與蕾絲的深綠洋裝，鎮上的節慶穿它最體面。' },
    { id: 'brown', name: '褐色大衣', art: 'brown', portrait: 'outfit-brown',
      desc: '厚實的褐色長大衣，書頁與符文繡在襬上，適合遠行。' },
    { id: 'ivory', name: '米白長袍', art: 'ivory', portrait: 'outfit-ivory',
      desc: '素色長袍罩著墨綠裙，調配藥水時最不怕沾上藥漬。' },
];

export function outfitById(id: string): OutfitDef {
    for (const o of OUTFITS) if (o.id === id) return o;
    return OUTFITS[0];
}
