import { resources, SpriteFrame, ImageAsset, Rect } from 'cc';

/**
 * 遊戲美術的執行期載入器：把 `assets/resources/` 底下的商品圖、顧客圖
 * 用 `resources.load`（依路徑，不需知道 uuid）預載進 Map，供背包圖示、
 * 店內貨架、顧客共用。載入是非同步 —— 呼叫 preload() 後用 onReady() 等完成。
 */

/** 材料名稱 → resources/items 底下的檔名。 */
const ITEM_FILES: Record<string, string> = {
    木材: 'wood', 樹枝: 'twig', 漿果: 'berry', 落葉: 'leaf',
    藥草: 'herb', 黑莓: 'blackberry', 金蘋果: 'goldapple', 藍莓: 'blueberry',
};

/** 顧客（動物）檔名。 */
const CUSTOMER_FILES = ['badger', 'owl', 'fox', 'hedgehog', 'rabbit', 'deer',
                        'raccoon', 'bear', 'squirrel', 'wolf', 'mouse', 'otter'];

/** 表情動畫：檔名 → [單幀寬, 單幀高, 幀數]（橫向 strip）。 */
const EMOTE_INFO: Record<string, [number, number, number]> = {
    emo18: [33, 30, 28], emo3: [29, 26, 29], emo2: [43, 30, 29],
    emo32: [57, 48, 28], emo51: [29, 55, 28],
};

/** NPC / 對話頭像檔名（resources/portraits 底下）。動物那組也可當顧客立繪。 */
const PORTRAIT_FILES = ['gnome', 'witch', 'elf', 'forestboy',
                        'badger', 'fox', 'hedgehog', 'rabbit',
                        'bear', 'squirrel', 'wolf', 'mouse'];

/** 裝飾品圖檔名（resources/decor 底下）。 */
const DECOR_FILES = ['succulent', 'daisypot', 'violetpot', 'birdcage_small', 'bonsai',
                     'ivy_hanging', 'roses_vase', 'lily_vase', 'sunflower_vase', 'autumn_vase',
                     'potted_fern', 'window_box', 'birdcage_large', 'blue_urn',
                     'wildflower_basket', 'flower_case'];

/** 藥水成品：中文名 → resources/potions 底下的檔名。載進 items map，圖示查找同材料。 */
const POTION_ITEMS: Record<string, string> = {
    清涼藥水: 'potion_blue', 戀愛藥水: 'potion_pink', 暗影藥水: 'potion_dark',
    烈焰藥水: 'potion_red', 溫暖熱可可: 'cocoa_mug', 蜂蜜藥劑: 'amber_jug',
    黃金藥劑: 'gold_bottle', 夜影掃帚: 'broom_purple', 星光掃帚: 'broom_blue',
    羽翼掃帚: 'broom_white',
};

/** 時鐘盤面零件（resources/ui/clock 底下）：盤面／日月圖示／指針。 */
const CLOCK_FILES = ['face', 'sun', 'moon', 'hand-hour', 'hand-min', 'hand-day'];

/** 鍋爐熬煮動畫幀數（resources/cauldron/f0..f5）。 */
const CAULDRON_FRAMES = 6;

/** 女巫採集動畫幀數（resources/witch/gather1..3：彎腰伸手→捏起→起身舉起）。 */
const GATHER_FRAMES = 3;

const items = new Map<string, SpriteFrame>();       // 材料名 → 圖
const customers = new Map<string, SpriteFrame>();   // 動物名 → 圖
const emotes = new Map<string, SpriteFrame[]>();    // 表情名 → 動畫幀陣列
const portraits = new Map<string, SpriteFrame>();   // 頭像名 → 圖
const decor = new Map<string, SpriteFrame>();       // 裝飾品 id → 圖
const clockParts = new Map<string, SpriteFrame>();  // 時鐘零件名 → 圖
const cauldron: SpriteFrame[] = [];                 // 鍋爐熬煮動畫幀
const gather: SpriteFrame[] = [];                   // 女巫採集動畫幀
let castFrame: SpriteFrame | null = null;           // 女巫施法姿勢（正面）
let sleepingFrame: SpriteFrame | null = null;       // 女巫睡覺立繪（含床，睡覺過場用）
let dialogueBoxFrame: SpriteFrame | null = null;    // 對話框外框
let brewRoomDayFrame: SpriteFrame | null = null;    // 藥水室背景（白天）
let brewRoomNightFrame: SpriteFrame | null = null;  // 藥水室背景（夜晚）
let questScrollFrame: SpriteFrame | null = null;    // 任務簿捲軸底板
let updateFrameArt: SpriteFrame | null = null;      // 更新公告板木框

let loaded = false;
let loading = false;
const readyCbs: Array<() => void> = [];

/**
 * 取 Map 的所有 key。⚠️ 不要寫成 `[...map.keys()]` —— 建置會把程式降級成 ES5，
 * spread 變成 `[].concat(map.keys())`，迭代器不會被展開，結果是「長度 1、內容是
 * 迭代器物件」的爛陣列（編輯器預覽正常、線上就全壞）。forEach 最保險。
 */
function mapKeys<T>(m: Map<string, T>): string[] {
    const out: string[] = [];
    m.forEach((_v, k) => out.push(k));
    return out;
}

export const GameArt = {
    get ready(): boolean { return loaded; },

    /** 開始預載（重複呼叫安全）。 */
    preload(): void {
        if (loaded || loading) return;
        loading = true;

        // 載入原始 ImageAsset（不論 png 被匯入成 texture 或 sprite-frame 都存在），
        // 執行期自己包成 SpriteFrame —— 不依賴匯入型別，最穩。
        const singleJobs: Array<[Map<string, SpriteFrame>, string, string]> = [];
        for (const name of Object.keys(ITEM_FILES)) singleJobs.push([items, name, `items/${ITEM_FILES[name]}`]);
        for (const file of CUSTOMER_FILES) singleJobs.push([customers, file, `customers/${file}`]);
        for (const file of PORTRAIT_FILES) singleJobs.push([portraits, file, `portraits/${file}`]);
        for (const file of DECOR_FILES) singleJobs.push([decor, file, `decor/${file}`]);
        for (const file of CLOCK_FILES) singleJobs.push([clockParts, file, `ui/clock/${file}`]);
        // 藥水成品：載進 items map（key 用中文名），圖示查找就跟材料同一套
        for (const name of Object.keys(POTION_ITEMS)) singleJobs.push([items, name, `potions/${POTION_ITEMS[name]}`]);
        const emoteNames = Object.keys(EMOTE_INFO);

        // +1 對話框外框、+2 藥水室背景(日/夜)、+1 任務簿捲軸、+1 施法姿勢、+1 更新公告板
        // 、+1 睡覺立繪、+鍋爐幀、+採集幀
        const total = singleJobs.length + emoteNames.length + 7 + CAULDRON_FRAMES + GATHER_FRAMES;
        let done = 0;
        const finish = () => {
            if (++done >= total) {
                loaded = true; loading = false;
                readyCbs.splice(0).forEach(cb => cb());
            }
        };

        for (const [map, key, path] of singleJobs) {
            resources.load(path, ImageAsset, (err, img) => {
                if (!err && img) map.set(key, SpriteFrame.createWithImage(img));
                else console.warn(`[GameArt] 載入失敗 ${path}`, err);
                finish();
            });
        }
        // 表情：載入 strip，切成每幀一個 SpriteFrame
        for (const name of emoteNames) {
            const [fw, fh, n] = EMOTE_INFO[name];
            resources.load(`emotes/${name}`, ImageAsset, (err, img) => {
                if (!err && img) {
                    const tex = SpriteFrame.createWithImage(img).texture;
                    const arr: SpriteFrame[] = [];
                    for (let i = 0; i < n; i++) {
                        const sf = new SpriteFrame();
                        sf.texture = tex;
                        sf.rect = new Rect(i * fw, 0, fw, fh);
                        arr.push(sf);
                    }
                    emotes.set(name, arr);
                } else console.warn(`[GameArt] 載入失敗 emotes/${name}`, err);
                finish();
            });
        }
        // 對話框外框（單張）
        resources.load('ui/dialogue-box', ImageAsset, (err, img) => {
            if (!err && img) dialogueBoxFrame = SpriteFrame.createWithImage(img);
            else console.warn('[GameArt] 載入失敗 ui/dialogue-box', err);
            finish();
        });
        // 藥水室背景（白天／夜晚各一張，尺寸相同→切換不位移）
        resources.load('rooms/brew-room-day', ImageAsset, (err, img) => {
            if (!err && img) brewRoomDayFrame = SpriteFrame.createWithImage(img);
            else console.warn('[GameArt] 載入失敗 rooms/brew-room-day', err);
            finish();
        });
        resources.load('rooms/brew-room-night', ImageAsset, (err, img) => {
            if (!err && img) brewRoomNightFrame = SpriteFrame.createWithImage(img);
            else console.warn('[GameArt] 載入失敗 rooms/brew-room-night', err);
            finish();
        });
        // 任務簿捲軸底板（單張）
        resources.load('ui/quest-scroll', ImageAsset, (err, img) => {
            if (!err && img) questScrollFrame = SpriteFrame.createWithImage(img);
            else console.warn('[GameArt] 載入失敗 ui/quest-scroll', err);
            finish();
        });
        // 鍋爐熬煮動畫幀（f0..f5，各一張，保持順序）
        cauldron.length = CAULDRON_FRAMES;
        for (let i = 0; i < CAULDRON_FRAMES; i++) {
            const idx = i;
            resources.load(`cauldron/f${idx}`, ImageAsset, (err, img) => {
                if (!err && img) cauldron[idx] = SpriteFrame.createWithImage(img);
                else console.warn(`[GameArt] 載入失敗 cauldron/f${idx}`, err);
                finish();
            });
        }
        // 更新公告板木框（單張）
        resources.load('ui/update-frame', ImageAsset, (err, img) => {
            if (!err && img) updateFrameArt = SpriteFrame.createWithImage(img);
            else console.warn('[GameArt] 載入失敗 ui/update-frame', err);
            finish();
        });
        // 女巫施法姿勢（正面，單張）
        resources.load('witch/cast', ImageAsset, (err, img) => {
            if (!err && img) castFrame = SpriteFrame.createWithImage(img);
            else console.warn('[GameArt] 載入失敗 witch/cast', err);
            finish();
        });
        // 女巫睡覺立繪（含床，睡覺過場用，單張）
        resources.load('witch/sleeping', ImageAsset, (err, img) => {
            if (!err && img) sleepingFrame = SpriteFrame.createWithImage(img);
            else console.warn('[GameArt] 載入失敗 witch/sleeping', err);
            finish();
        });
        // 女巫採集動畫幀（gather1..3，順序＝播放順序）
        gather.length = GATHER_FRAMES;
        for (let i = 0; i < GATHER_FRAMES; i++) {
            const idx = i;
            resources.load(`witch/gather${idx + 1}`, ImageAsset, (err, img) => {
                if (!err && img) gather[idx] = SpriteFrame.createWithImage(img);
                else console.warn(`[GameArt] 載入失敗 witch/gather${idx + 1}`, err);
                finish();
            });
        }
    },

    /** 註冊「載入完成」回呼；已完成則立即呼叫。 */
    onReady(cb: () => void): void {
        if (loaded) cb(); else readyCbs.push(cb);
    },

    /** 材料圖（未載入回 null）。 */
    item(name: string): SpriteFrame | null { return items.get(name) ?? null; },

    /** 顧客圖（未載入回 null）。 */
    customer(name: string): SpriteFrame | null { return customers.get(name) ?? null; },

    /** 所有已載入的顧客名（給隨機挑選用）。 */
    customerNames(): string[] { return mapKeys(customers); },

    /** 表情動畫幀陣列（未載入回 null）。 */
    emote(name: string): SpriteFrame[] | null { return emotes.get(name) ?? null; },

    /** 所有已載入的表情名（給隨機挑選用）。 */
    emoteNames(): string[] { return mapKeys(emotes); },

    /** NPC / 對話頭像（未載入回 null）。 */
    portrait(name: string): SpriteFrame | null { return portraits.get(name) ?? null; },

    /** 對話框外框（未載入回 null）。 */
    dialogueBox(): SpriteFrame | null { return dialogueBoxFrame; },

    /** 裝飾品圖（未載入回 null）。 */
    decor(id: string): SpriteFrame | null { return decor.get(id) ?? null; },

    /** 時鐘零件圖（face/sun/moon/hand-hour/hand-min/hand-day；未載入回 null）。 */
    clockArt(name: string): SpriteFrame | null { return clockParts.get(name) ?? null; },

    /** 鍋爐熬煮動畫幀（0..5；未載入回空陣列）。 */
    cauldronFrames(): SpriteFrame[] { return cauldron.filter(Boolean); },

    /** 女巫採集動畫幀（0..2；未載入回空陣列）。 */
    gatherFrames(): SpriteFrame[] { return gather.filter(Boolean); },

    /** 女巫施法姿勢（正面；未載入回 null）。 */
    cast(): SpriteFrame | null { return castFrame; },

    /** 女巫睡覺立繪（含床，睡覺過場用；未載入回 null）。 */
    sleeping(): SpriteFrame | null { return sleepingFrame; },

    /** 藥水室背景（night=true 回夜晚版；未載入回 null）。 */
    brewRoom(night: boolean): SpriteFrame | null { return (night ? brewRoomNightFrame : brewRoomDayFrame); },

    /** 任務簿捲軸底板（未載入回 null）。 */
    questScroll(): SpriteFrame | null { return questScrollFrame; },

    /** 更新公告板木框（未載入回 null）。 */
    updateFrame(): SpriteFrame | null { return updateFrameArt; },
};
