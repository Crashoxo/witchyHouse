/**
 * 裝飾品「內容」資料：花店販售的 16 種裝飾（id / 中文名 / 售價）。
 * 擁有/擺放的狀態（owned/placed）在 DecorCatalog.ts。
 */
export interface DecorDef { id: string; name: string; price: number; }

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
];
