import { resources, SpriteFrame, ImageAsset, Rect, director } from 'cc';
import { ITEM_FILES, POTION_ITEMS } from './data/items';

/**
 * 遊戲美術的執行期載入器：把 `assets/resources/` 底下的圖用 `resources.load`
 * （依路徑，不需 uuid）預載進 Map，供背包圖示、貨架、顧客、UI 共用。
 *
 * ── 分區載入（2026-07-24）──
 * 不再開機一次載「全部」，而是分成幾個「組」：
 *   common ── 每個場景都用得到（道具/藥水圖、時鐘、對話框、任務捲軸、公告板、女巫姿勢）。開機即載。
 *   portraits / decor / shop / brew ── 各區域專屬，進到需要的場景才載（見 SCENE_GROUPS）。
 * `preload()` 依「目前場景名」自動決定要載哪些組，所以**呼叫端一律 `preload()`、完全不用改**。
 * ⚠️ 保險：拿不到場景名或遇到未知場景，就退回「全部載入」＝跟舊行為一樣，寧可不省也不缺圖。
 *
 * 載入是非同步：`ready` ＝「目前已請求的組是否都載完」；用 `onReady()` 等它。
 * ⚠️ ES5 build 下 Map/Set 不能 spread／for...of（迭代器不展開）；一律 forEach 或 Object.keys＋陣列 for...of。
 */

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

/** 時鐘盤面零件（resources/ui/clock 底下）：盤面／日月圖示／指針。 */
const CLOCK_FILES = ['face', 'sun', 'moon', 'hand-hour', 'hand-min', 'hand-day'];

/** 鍋爐熬煮動畫幀數（resources/cauldron/f0..f5）。 */
const CAULDRON_FRAMES = 6;

/** 女巫採集動畫幀數（resources/witch/gather1..3：彎腰伸手→捏起→起身舉起）。 */
const GATHER_FRAMES = 3;

const items = new Map<string, SpriteFrame>();       // 材料/藥水名 → 圖
const customers = new Map<string, SpriteFrame>();   // 動物名 → 圖
const emotes = new Map<string, SpriteFrame[]>();    // 表情名 → 動畫幀陣列
const portraits = new Map<string, SpriteFrame>();   // 頭像名 → 圖
const decor = new Map<string, SpriteFrame>();       // 裝飾品 id → 圖
const clockParts = new Map<string, SpriteFrame>();  // 時鐘零件名 → 圖
const cauldron: SpriteFrame[] = [];                 // 鍋爐熬煮動畫幀
const gather: SpriteFrame[] = [];                   // 女巫採集動畫幀
let castFrame: SpriteFrame | null = null;           // 女巫施法姿勢（正面）
let sleepingFrame: SpriteFrame | null = null;       // 女巫睡覺立繪（含床）
let dialogueBoxFrame: SpriteFrame | null = null;    // 對話框外框
let brewRoomDayFrame: SpriteFrame | null = null;    // 藥水室背景（白天）
let brewRoomNightFrame: SpriteFrame | null = null;  // 藥水室背景（夜晚）
let questScrollFrame: SpriteFrame | null = null;    // 任務簿捲軸底板
let updateFrameArt: SpriteFrame | null = null;      // 更新公告板木框

/**
 * 取 Map 的所有 key。⚠️ 不要寫成 `[...map.keys()]` —— 建置會把程式降級成 ES5，
 * spread 變成 `[].concat(map.keys())`，迭代器不會被展開（編輯器預覽正常、線上就全壞）。
 */
function mapKeys<T>(m: Map<string, T>): string[] {
    const out: string[] = [];
    m.forEach((_v, k) => out.push(k));
    return out;
}

// ──────────── 分區載入機制 ────────────

/** 場景名 → 除了 common 之外還要載入的區域組。 */
const SCENE_GROUPS: Record<string, string[]> = {
    main: [],                       // 森林：只需 common
    town: ['portraits', 'decor'],   // 城鎮：NPC 頭像、花店裝飾目錄
    shop: ['shop', 'decor'],        // 自己的店：顧客/表情、擺出的裝飾
    brew: ['brew'],                 // 藥水室：鍋爐幀、房間背景
};
/** 保險用：全部區域組（拿不到場景名時退回全載）。 */
const ALL_AREA_GROUPS = ['portraits', 'decor', 'shop', 'brew'];

const requested: Record<string, boolean> = {};  // 已開始載入的組（idempotent 用）
let started = false;
let pending = 0;                                 // 尚在載入中的工作數
const readyCbs: Array<() => void> = [];

function jobDone(): void {
    if (pending > 0 && --pending === 0) {
        readyCbs.splice(0).forEach(cb => cb());
    }
}

/** 載入一張圖到 map。 */
function loadImg(map: Map<string, SpriteFrame>, key: string, path: string): void {
    pending++;
    resources.load(path, ImageAsset, (err, img) => {
        if (!err && img) map.set(key, SpriteFrame.createWithImage(img));
        else console.warn(`[GameArt] 載入失敗 ${path}`, err);
        jobDone();
    });
}

/** 載入單張圖，用 setter 收（給 castFrame 等單一 frame 用）。 */
function loadSingle(path: string, set: (sf: SpriteFrame) => void): void {
    pending++;
    resources.load(path, ImageAsset, (err, img) => {
        if (!err && img) set(SpriteFrame.createWithImage(img));
        else console.warn(`[GameArt] 載入失敗 ${path}`, err);
        jobDone();
    });
}

/** 載入一張圖到陣列指定索引（給鍋爐/採集幀用，保持順序）。 */
function loadIndexed(arr: SpriteFrame[], idx: number, path: string): void {
    pending++;
    resources.load(path, ImageAsset, (err, img) => {
        if (!err && img) arr[idx] = SpriteFrame.createWithImage(img);
        else console.warn(`[GameArt] 載入失敗 ${path}`, err);
        jobDone();
    });
}

/** 載入表情 strip，切成每幀一個 SpriteFrame。 */
function loadEmote(name: string): void {
    const info = EMOTE_INFO[name];
    const fw = info[0], fh = info[1], n = info[2];
    pending++;
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
        jobDone();
    });
}

/** 載入一個區域組（idempotent —— 已請求過就跳過）。 */
function loadGroup(name: string): void {
    if (requested[name]) return;
    requested[name] = true;

    if (name === 'common') {
        for (const key of Object.keys(ITEM_FILES)) loadImg(items, key, `items/${ITEM_FILES[key]}`);
        for (const key of Object.keys(POTION_ITEMS)) loadImg(items, key, `potions/${POTION_ITEMS[key]}`);
        for (const file of CLOCK_FILES) loadImg(clockParts, file, `ui/clock/${file}`);
        loadSingle('ui/dialogue-box', sf => { dialogueBoxFrame = sf; });
        loadSingle('ui/quest-scroll', sf => { questScrollFrame = sf; });
        loadSingle('ui/update-frame', sf => { updateFrameArt = sf; });
        loadSingle('witch/cast', sf => { castFrame = sf; });
        loadSingle('witch/sleeping', sf => { sleepingFrame = sf; });
        gather.length = GATHER_FRAMES;
        for (let i = 0; i < GATHER_FRAMES; i++) loadIndexed(gather, i, `witch/gather${i + 1}`);
    } else if (name === 'portraits') {
        for (const file of PORTRAIT_FILES) loadImg(portraits, file, `portraits/${file}`);
    } else if (name === 'decor') {
        for (const file of DECOR_FILES) loadImg(decor, file, `decor/${file}`);
    } else if (name === 'shop') {
        for (const file of CUSTOMER_FILES) loadImg(customers, file, `customers/${file}`);
        for (const key of Object.keys(EMOTE_INFO)) loadEmote(key);
    } else if (name === 'brew') {
        cauldron.length = CAULDRON_FRAMES;
        for (let i = 0; i < CAULDRON_FRAMES; i++) loadIndexed(cauldron, i, `cauldron/f${i}`);
        loadSingle('rooms/brew-room-day', sf => { brewRoomDayFrame = sf; });
        loadSingle('rooms/brew-room-night', sf => { brewRoomNightFrame = sf; });
    }
}

export const GameArt = {
    /** 目前已請求的所有組是否都載入完成。 */
    get ready(): boolean { return started && pending === 0; },

    /**
     * 開始預載（重複呼叫安全）。依「目前場景名」載入 common ＋該場景的區域組；
     * 換場景後各元件於 onLoad 再呼叫一次，就會補載新場景需要的組。
     * ⚠️ 拿不到場景名或未知場景 → 退回全部載入（等同舊行為，寧可不省也不缺圖）。
     */
    preload(): void {
        started = true;
        loadGroup('common');
        const scene = director.getScene();
        const groups = scene ? SCENE_GROUPS[scene.name] : undefined;
        const toLoad = groups !== undefined ? groups : ALL_AREA_GROUPS;
        for (const g of toLoad) loadGroup(g);
    },

    /** 註冊「（目前請求的組）載入完成」回呼；已完成則立即呼叫。 */
    onReady(cb: () => void): void {
        if (started && pending === 0) cb(); else readyCbs.push(cb);
    },

    /** 材料/藥水圖（未載入回 null）。 */
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
