/**
 * 裝飾品「內容」資料：花店販售的 16 種裝飾（id / 中文名 / 售價）。
 * 擁有/擺放的狀態（owned/placed）在 DecorCatalog.ts。
 */
export interface DecorDef {
    id: string;
    name: string;
    price: number;
    /**
     * 顯示縮放。留空＝用 DecorRoom 的 decorScale（0.4）——最早那十六款是從大張 Gemini 圖
     * 切下來的，不縮會比房間還大。**新的美術直接畫在遊戲尺度上的就標 `scale: 1`。**
     */
    scale?: number;
}

export const DECOR_CATALOG: DecorDef[] = [
    { id: 'succulent',        name: '多肉盆栽',   price: 40 },
    { id: 'daisypot',         name: '雛菊小盆',   price: 45 },
    { id: 'violetpot',        name: '紫羅蘭盆',   price: 45 },
    { id: 'birdcage_small',   name: '花鳥籠',     price: 90 },
    { id: 'bonsai',           name: '松柏盆景',   price: 150 },
    { id: 'ivy_hanging',      name: '常春藤吊籃', price: 80 },
    { id: 'roses_vase',       name: '玫瑰花瓶',   price: 120 },
    { id: 'lily_vase',        name: '百合花瓶',   price: 130 },
    { id: 'sunflower_vase',   name: '向日葵瓶',   price: 110 },
    { id: 'autumn_vase',      name: '秋葉銅瓶',   price: 160 },
    { id: 'potted_fern',      name: '蕨葉盆栽',   price: 180 },
    { id: 'window_box',       name: '紫花窗台',   price: 140 },
    { id: 'birdcage_large',   name: '大花鳥籠',   price: 220 },
    { id: 'blue_urn',         name: '藍花石甕',   price: 260 },
    { id: 'wildflower_basket', name: '野花籃',    price: 300 },
    { id: 'flower_case',      name: '星光花櫃',   price: 500 },
    // PixelLab 出的三個展示架。⚠️ 雖然跟貨架畫在同一個 72px 畫布上，但畫的是**小擺飾**，
    // scale 1 會讓藥水瓶跟女巫一樣高（試過）——0.45 才是桌上擺飾該有的大小。
    { id: 'herb_shelf',     name: '乾燥花草架', price: 150, scale: 0.45 },
    { id: 'crystal_shelf',  name: '水晶展示架', price: 200, scale: 0.45 },
    { id: 'potion_shelf',   name: '藥水展示架', price: 240, scale: 0.45 },
];
