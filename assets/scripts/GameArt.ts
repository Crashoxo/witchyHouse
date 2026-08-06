import { resources, SpriteFrame, ImageAsset, Rect, director } from 'cc';
import { ITEM_FILES, POTION_ITEMS, CANDY_ITEMS } from './data/items';
import { FLOWERS } from './data/garden';
import { OUTFITS } from './data/outfits';
import { CANDY_CRITTERS } from './data/candy';

/**
 * 遊戲美術的執行期載入器：把 `assets/resources/` 底下的圖用 `resources.load`
 * （依路徑，不需 uuid）預載進 Map，供背包圖示、貨架、顧客、UI 共用。
 *
 * ── 分區載入（2026-07-24）──
 * 不再開機一次載「全部」，而是分成幾個「組」：
 *   common ── 每個場景都用得到（道具/藥水圖、時鐘、對話框、任務捲軸、公告板、女巫姿勢）。開機即載。
 *   portraits / decor / shop / villagers / brew ── 各區域專屬，進到需要的場景才載（見 SCENE_GROUPS）。
 * `preload()` 依「目前場景名」自動決定要載哪些組，所以**呼叫端一律 `preload()`、完全不用改**。
 * ⚠️ 保險：拿不到場景名或遇到未知場景，就退回「全部載入」＝跟舊行為一樣，寧可不省也不缺圖。
 *
 * 載入是非同步：`ready` ＝「目前已請求的組是否都載完」；用 `onReady()` 等它。
 * ⚠️ ES5 build 下 Map/Set 不能 spread／for...of（迭代器不展開）；一律 forEach 或 Object.keys＋陣列 for...of。
 */

/**
 * 村民檔名（resources/villagers 底下）。每張是 4 欄 × 3 列的走路表：
 * 第 0 列朝下（正面）、第 1 列側面（一律朝左，往右走時把節點翻面）、第 2 列朝上（背面）。
 * 單格大小由圖檔尺寸算出（寬/4、高/3），所以每位角色可以有自己的畫布大小。
 */
const VILLAGER_FILES = ['frog', 'fox', 'rabbit', 'hedgehog', 'witch',
                        'deer', 'broomwitch', 'fairy', 'traveler', 'mage',
                        'rabbitwitch'];

/** 村民走路表的列（＝面向）。 */
export const VillagerDir = { DOWN: 0, SIDE: 1, UP: 2 };
const VILLAGER_COLS = 4;   // 每個面向的動畫幀數
const VILLAGER_ROWS = 3;   // 面向數（下／側／上）

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

/** 季節圖標（resources/ui/season 底下），索引＝TimeSystem.season（0 春 … 3 冬）。 */
const SEASON_FILES = ['spring', 'summer', 'autumn', 'winter'];

/** 鍋爐熬煮動畫幀數（resources/cauldron/f0..f5）。 */
const CAULDRON_FRAMES = 6;

/** 女巫採集動畫幀數（resources/witch/gather1..3：彎腰伸手→捏起→起身舉起）。 */
const GATHER_FRAMES = 3;

/** 後花園：土壤磚、澆水／摘花動作幀數。花的走圖名見 data/garden 的 FLOWERS。 */
const SOIL_FILES = ['soil-dry', 'soil-wet'];
const WATER_FRAMES = 4;
const PICK_FRAMES = 4;
/** 花的走圖：6 欄（成長階段）× 2 列（第 0 列健康、第 1 列枯萎）。 */
const FLOWER_COLS = 6;
const FLOWER_ROWS = 2;

const items = new Map<string, SpriteFrame>();       // 材料/藥水名 → 圖
const villagers = new Map<string, SpriteFrame[][]>();  // 村民名 → [面向][幀]
const emotes = new Map<string, SpriteFrame[]>();    // 表情名 → 動畫幀陣列
const portraits = new Map<string, SpriteFrame>();   // 頭像名 → 圖
const decor = new Map<string, SpriteFrame>();       // 裝飾品 id → 圖
const clockParts = new Map<string, SpriteFrame>();  // 時鐘零件名 → 圖
const seasonIcons = new Map<string, SpriteFrame>(); // 季節圖標名 → 圖
const cauldron: SpriteFrame[] = [];                 // 鍋爐熬煮動畫幀
const gather: SpriteFrame[] = [];                   // 女巫採集動畫幀
const water: SpriteFrame[] = [];                    // 女巫澆水動畫幀
const pick: SpriteFrame[] = [];                     // 女巫摘花動畫幀
const soil = new Map<string, SpriteFrame>();        // 土壤磚（乾/濕）
const flowers = new Map<string, SpriteFrame[][]>(); // 花名 → [健康/枯萎][階段]
let castFrame: SpriteFrame | null = null;           // 女巫施法姿勢（正面）
let sleepingFrame: SpriteFrame | null = null;       // 女巫睡覺立繪（含床）

// ──────────── 女巫本人（chibi 像素圖集）────────────

/**
 * `resources/witch8/<造型>.png` 的排法（由 tools/export_witch8.py 產生）：
 *   列 0       站姿，欄＝方向
 *   列 1..8    走路，列 1+d ＝方向 d，欄＝動畫幀
 *   列 9..16   跑步，列 9+d ＝方向 d，欄＝動畫幀
 *   列 17..24  施法，列 17+d ＝方向 d，欄＝動畫幀（6 幀）＝施法／澆水共用
 *   列 25      蹲下 5 幀（只有正面）＝採集／摘花／種花共用
 * 方向索引見 WitchDir。睡覺立繪（含床）是另一張 `witch8/<造型>-sleep.png`。
 *
 * ⚠️ 蹲下那一列還是**前一位（紫袍）女巫**的動畫 —— 新角色還沒做這段，
 * 等新圖進來再換（見 tools/export_witch8.py 的 legacy_pose 那段）。
 */
const W8_COLS = 8;
const W8_ROWS = 26;
const W8_ROW_WALK = 1;
const W8_ROW_RUN = 9;
const W8_ROW_CAST = 17;
const W8_ROW_CROUCH = 25;
const W8_CAST_FRAMES = 6;
const W8_CROUCH_FRAMES = 5;

/**
 * 方向索引：0 南（下）起、每 45° 逆時針一格。
 * 對應圖集的欄：south, south-east, east, north-east, north, north-west, west, south-west。
 */
export const WITCH_DIRS = 8;
export const WitchDir = { SOUTH: 0, EAST: 2, NORTH: 4, WEST: 6 };

/**
 * 女巫節點的縮放：新角色的格子 66px 高、可見身高 64px，**直接 1:1 畫**（像素才不會糊，
 * 前一位是 46px 身高硬放大 1.5 倍）。畫面上 64px，跟村民與前一位的 69px 差不到一成，
 * 所以場景裡調好的互動半徑/可走範圍都不用重調。**場景檔裡的 scale 由程式覆蓋**
 * （CharacterAnimator 套用），六個場景一個都不用改。
 */
export const WITCH_SCALE = 1.0;

let w8Idle: SpriteFrame[] = [];        // [方向]
let w8Walk: SpriteFrame[][] = [];      // [方向][幀]
let w8Run: SpriteFrame[][] = [];       // [方向][幀]（衝刺）
let w8Cast: SpriteFrame[][] = [];      // [方向][幀]（施法／澆水）
let w8Crouch: SpriteFrame[] = [];      // 蹲下（採集/摘花/種花）
let w8Sleep: SpriteFrame | null = null;

/**
 * 換裝：`resources/witch8/<造型 id>.png` 是同一張圖集的袍子改色版。
 * 換裝時整張圖集換掉，所以下面的 accessor 一律直接讀 w8*，呼叫端完全不用改。
 * （舊手繪女巫的三套造型圖 `resources/witch/{green,brown,ivory}/` 已經不再載入。）
 */
let outfitId = '';                                  // ''＝預設造型
let dialogueBoxFrame: SpriteFrame | null = null;    // 對話框外框
let brewRoomDayFrame: SpriteFrame | null = null;    // 藥水室背景（白天）
let brewRoomNightFrame: SpriteFrame | null = null;  // 藥水室背景（夜晚）
let gardenFrame: SpriteFrame | null = null;         // 後花園背景（草地＋柵欄）
const candyArt = new Map<string, SpriteFrame>();    // 糖果鎮的角色/小動物圖
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
    main: [],                                     // 森林：只需 common
    town: ['portraits', 'decor', 'villagers'],    // 城鎮：NPC 頭像、花店裝飾目錄、街上走動的村民
    shop: ['shop', 'decor', 'villagers'],         // 自己的店：表情、擺出的裝飾、上門的顧客
    brew: ['brew'],                               // 藥水室：鍋爐幀、房間背景
    garden: ['garden', 'villagers'],              // 後花園：土壤/花/澆水姿勢、柵欄外經過的村民
    candy: ['candy'],                             // 糖果鎮：地圖、鎮上的角色與路人
};
/** 保險用：全部區域組（拿不到場景名時退回全載）。 */
const ALL_AREA_GROUPS = ['portraits', 'decor', 'shop', 'villagers', 'garden', 'brew', 'candy'];

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

/**
 * 載入女巫圖集，依 W8_* 的排法切成站姿/走路/施法/蹲下。
 * @param id 造型 id（''＝預設那張 base.png）
 *
 * ⚠️ 用 w8Seq 擋掉晚到的回呼：預載（base）與換裝（造型）可能同時在飛，
 * 沒擋的話先發後到的 base 會把剛換好的造型蓋回去。
 */
let w8Seq = 0;
function loadWitch8(id: string): void {
    const file = id || 'base';
    const seq = ++w8Seq;
    const mine = () => w8Seq === seq;
    pending++;
    resources.load(`witch8/${file}`, ImageAsset, (err, img) => {
        if (!err && img && mine()) {
            const tex = SpriteFrame.createWithImage(img).texture;
            const cw = img.width / W8_COLS, ch = img.height / W8_ROWS;
            const cut = (c: number, r: number) => {
                const sf = new SpriteFrame();
                sf.texture = tex;
                sf.rect = new Rect(c * cw, r * ch, cw, ch);
                return sf;
            };
            const idle: SpriteFrame[] = [], walk: SpriteFrame[][] = [],
                  run: SpriteFrame[][] = [], cast: SpriteFrame[][] = [];
            for (let d = 0; d < WITCH_DIRS; d++) {
                idle.push(cut(d, 0));
                const fr: SpriteFrame[] = [], rn: SpriteFrame[] = [], ca: SpriteFrame[] = [];
                for (let c = 0; c < W8_COLS; c++) fr.push(cut(c, W8_ROW_WALK + d));
                for (let c = 0; c < W8_COLS; c++) rn.push(cut(c, W8_ROW_RUN + d));
                for (let c = 0; c < W8_CAST_FRAMES; c++) ca.push(cut(c, W8_ROW_CAST + d));
                walk.push(fr);
                run.push(rn);
                cast.push(ca);
            }
            const crouch: SpriteFrame[] = [];
            for (let c = 0; c < W8_CROUCH_FRAMES; c++) crouch.push(cut(c, W8_ROW_CROUCH));
            w8Idle = idle; w8Walk = walk; w8Run = run; w8Cast = cast; w8Crouch = crouch;
        } else if (err) console.warn(`[GameArt] 載入失敗 witch8/${file}`, err);
        jobDone();
    });
    // 睡覺立繪是另一張（含床，裁切框跟角色不一樣）
    const sleepFile = id ? `${id}-sleep` : 'sleep';
    pending++;
    resources.load(`witch8/${sleepFile}`, ImageAsset, (err, img) => {
        if (!err && img && mine()) w8Sleep = SpriteFrame.createWithImage(img);
        else if (err) console.warn(`[GameArt] 載入失敗 witch8/${sleepFile}`, err);
        jobDone();
    });
}

/** 載入一位村民的走路表，切成 [列][欄] 的 SpriteFrame（列＝面向，欄＝動畫幀）。 */
function loadVillager(name: string): void {
    pending++;
    resources.load(`villagers/${name}`, ImageAsset, (err, img) => {
        if (!err && img) {
            const tex = SpriteFrame.createWithImage(img).texture;
            const cw = img.width / VILLAGER_COLS, ch = img.height / VILLAGER_ROWS;
            const rows: SpriteFrame[][] = [];
            for (let r = 0; r < VILLAGER_ROWS; r++) {
                const arr: SpriteFrame[] = [];
                for (let c = 0; c < VILLAGER_COLS; c++) {
                    const sf = new SpriteFrame();
                    sf.texture = tex;
                    sf.rect = new Rect(c * cw, r * ch, cw, ch);
                    arr.push(sf);
                }
                rows.push(arr);
            }
            villagers.set(name, rows);
        } else console.warn(`[GameArt] 載入失敗 villagers/${name}`, err);
        jobDone();
    });
}

/**
 * 載入一種花的走圖，切成 [列][階段]（列 0 健康、列 1 枯萎）。
 * 順便把「開花那一格」登記成該花的道具圖示，背包/貨架/顧客就都有圖可用。
 */
function loadFlower(art: string, flowerName: string): void {
    pending++;
    resources.load(`garden/${art}`, ImageAsset, (err, img) => {
        if (!err && img) {
            const tex = SpriteFrame.createWithImage(img).texture;
            const cw = img.width / FLOWER_COLS, ch = img.height / FLOWER_ROWS;
            const rows: SpriteFrame[][] = [];
            for (let r = 0; r < FLOWER_ROWS; r++) {
                const arr: SpriteFrame[] = [];
                for (let c = 0; c < FLOWER_COLS; c++) {
                    const sf = new SpriteFrame();
                    sf.texture = tex;
                    sf.rect = new Rect(c * cw, r * ch, cw, ch);
                    arr.push(sf);
                }
                rows.push(arr);
            }
            flowers.set(art, rows);
            items.set(flowerName, rows[0][FLOWER_COLS - 2]);   // 盛開那一格＝道具圖示
        } else console.warn(`[GameArt] 載入失敗 garden/${art}`, err);
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
        // 糖果鎮進的貨也要在背包/貨架/顧客那邊看得到圖 → 放 common
        for (const key of Object.keys(CANDY_ITEMS)) loadImg(items, key, `candy/${CANDY_ITEMS[key]}`);
        for (const file of CLOCK_FILES) loadImg(clockParts, file, `ui/clock/${file}`);
        for (const file of SEASON_FILES) loadImg(seasonIcons, file, `ui/season/${file}`);
        loadSingle('ui/dialogue-box', sf => { dialogueBoxFrame = sf; });
        loadSingle('ui/quest-scroll', sf => { questScrollFrame = sf; });
        loadSingle('ui/update-frame', sf => { updateFrameArt = sf; });
        // 女巫本人：站姿/走路/施法/蹲下/睡覺，一張圖集。
        // ⚠️ 要看 w8Seq —— PlayerController.onLoad 的 Outfits.apply() 比 CharacterAnimator
        //    的 preload() **早**跑（元件順序），造型已經在載了就不能再發一次 base 把它蓋掉。
        if (w8Seq === 0) loadWitch8(outfitId);
        // 舊手繪女巫的施法/睡覺/採集姿勢：只在圖集載不到時墊底
        loadSingle('witch/cast', sf => { castFrame = sf; });
        loadSingle('witch/sleeping', sf => { sleepingFrame = sf; });
        gather.length = GATHER_FRAMES;
        for (let i = 0; i < GATHER_FRAMES; i++) loadIndexed(gather, i, `witch/gather${i + 1}`);
        // 花與種子的圖示要在每個場景都拿得到（背包、貨架、顧客想要的東西都會用到），
        // 所以放 common；只有後花園會用到的土壤磚與澆水姿勢才留在 garden 組。
        for (const f of FLOWERS) {
            loadFlower(f.art, f.flower);
            loadImg(items, f.seed, `garden/${f.art}-seed`);
        }
    } else if (name === 'portraits') {
        for (const file of PORTRAIT_FILES) loadImg(portraits, file, `portraits/${file}`);
    } else if (name === 'decor') {
        for (const file of DECOR_FILES) loadImg(decor, file, `decor/${file}`);
    } else if (name === 'shop') {
        for (const key of Object.keys(EMOTE_INFO)) loadEmote(key);
    } else if (name === 'villagers') {
        for (const file of VILLAGER_FILES) loadVillager(file);
    } else if (name === 'garden') {
        for (const file of SOIL_FILES) loadImg(soil, file, `garden/${file}`);
        water.length = WATER_FRAMES;
        for (let i = 0; i < WATER_FRAMES; i++) loadIndexed(water, i, `witch/water${i + 1}`);
        pick.length = PICK_FRAMES;
        for (let i = 0; i < PICK_FRAMES; i++) loadIndexed(pick, i, `witch/pick${i + 1}`);
        loadSingle('rooms/garden', sf => { gardenFrame = sf; });
    } else if (name === 'candy') {
        // ⚠️ 地圖與房子/裝飾**已經是 candy.scene 裡的節點**（圖在 assets/art/candy，
        //    由場景用 uuid 參照），所以這裡不載 —— 只載執行期才生成的 NPC 與路人。
        for (const c of CANDY_CRITTERS) loadImg(candyArt, c.art, `candy/${c.art}`);
    } else if (name === 'brew') {
        cauldron.length = CAULDRON_FRAMES;
        for (let i = 0; i < CAULDRON_FRAMES; i++) loadIndexed(cauldron, i, `cauldron/f${i}`);
        loadSingle('rooms/brew-room-day', sf => { brewRoomDayFrame = sf; });
        loadSingle('rooms/brew-room-night', sf => { brewRoomNightFrame = sf; });
        // 造型立繪只有房間裡的衣櫃會用到，所以掛在 brew 組，不佔 common
        for (const o of OUTFITS) if (o.portrait) loadImg(portraits, o.portrait, `portraits/${o.portrait}`);
    }
}

export const GameArt = {
    /** 目前已請求的所有組是否都載入完成。 */
    get ready(): boolean { return started && pending === 0; },

    /**
     * 換上某套造型的圖：id ＝ `resources/witch/<id>/` 的資料夾名，空字串＝回到預設那批。
     * 載入中舊圖還在（accessor 只在陣列有東西時才用造型版），所以不會閃一下空白。
     * ⚠️ 載入是非同步的，中途又換一套時要用 outfitId 擋掉晚到的舊回呼。
     */
    applyOutfit(id: string): void {
        if (id === outfitId) return;
        outfitId = id;
        started = true;
        loadWitch8(id);          // 造型＝同一張圖集的改色版，整張換掉
    },

    /** 女巫圖集載好了沒（沒好的話 CharacterAnimator 會先用場景指定的舊圖）。 */
    witchReady(): boolean { return w8Idle.length > 0; },

    /** 某個方向的站姿（dir 見 WitchDir；未載入回 null）。 */
    witchIdle(dir: number): SpriteFrame | null {
        return w8Idle[((dir % WITCH_DIRS) + WITCH_DIRS) % WITCH_DIRS] ?? null;
    },

    /** 某個方向的走路幀（未載入回空陣列）。 */
    witchWalk(dir: number): SpriteFrame[] {
        return w8Walk[((dir % WITCH_DIRS) + WITCH_DIRS) % WITCH_DIRS] ?? [];
    },

    /** 某個方向的跑步幀（衝刺用；未載入回空陣列 → 呼叫端自己退回走路）。 */
    witchRun(dir: number): SpriteFrame[] {
        return w8Run[((dir % WITCH_DIRS) + WITCH_DIRS) % WITCH_DIRS] ?? [];
    },

    /**
     * 某個方向的施法動畫幀（新圖 8 方向各 6 幀；沒有圖集時退回舊的單張姿勢）。
     * @param dir 面向（見 WitchDir）
     */
    castFrames(dir = WitchDir.SOUTH): SpriteFrame[] {
        const v = w8Cast[((dir % WITCH_DIRS) + WITCH_DIRS) % WITCH_DIRS];
        if (v && v.length) return v;
        const f = castFrame;
        return f ? [f] : [];
    },


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

    /**
     * 村民某個面向的走路幀（VillagerDir.DOWN / SIDE / UP；未載入回空陣列）。
     * 側面一律朝左，往右走請把節點 scale.x 取負。
     * （女巫本人已改用八方向圖集，不再翻面 —— 村民這批仍是三向＋翻面。）
     */
    villagerFrames(name: string, dir: number): SpriteFrame[] {
        const rows = villagers.get(name);
        return rows ? (rows[dir] ?? rows[0]) : [];
    },

    /** 所有已載入的村民名（給隨機挑選用）。 */
    villagerNames(): string[] { return mapKeys(villagers); },

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

    /** 季節圖標（依 TimeSystem.season 索引 0..3；未載入回 null）。 */
    seasonIcon(season: number): SpriteFrame | null {
        return seasonIcons.get(SEASON_FILES[season] ?? '') ?? null;
    },

    /** 鍋爐熬煮動畫幀（0..5；未載入回空陣列）。 */
    cauldronFrames(): SpriteFrame[] { return cauldron.filter(Boolean); },

    /**
     * 採集動畫幀。「蹲下」5 幀是採集／摘花／種花共用的（pick 回同一批）；
     * 沒有圖集時才退回各自的舊手繪幀。
     * ⚠️ 這 5 幀還是前一位（紫袍）女巫 —— 新角色的蹲下圖還沒做。
     */
    gatherFrames(): SpriteFrame[] {
        return w8Crouch.length ? w8Crouch : gather.filter(Boolean);
    },

    /**
     * 女巫澆水動畫幀 ＝ **借施法那組**（使用者指定：兩個動作共用一套八方向的圖）。
     * @param dir 面向（見 WitchDir）
     */
    waterFrames(dir = WitchDir.SOUTH): SpriteFrame[] {
        const v = w8Cast[((dir % WITCH_DIRS) + WITCH_DIRS) % WITCH_DIRS];
        if (v && v.length) return v;
        return water.filter(Boolean);
    },

    /** 女巫摘花動畫幀。 */
    pickFrames(): SpriteFrame[] {
        return w8Crouch.length ? w8Crouch : pick.filter(Boolean);
    },

    /** 土壤磚（'soil-dry' / 'soil-wet'；未載入回 null）。 */
    soil(wet: boolean): SpriteFrame | null {
        return soil.get(wet ? 'soil-wet' : 'soil-dry') ?? null;
    },

    /** 花的某一階圖（wilting=true 取枯萎那一列；未載入回 null）。 */
    flower(art: string, stage: number, wilting: boolean): SpriteFrame | null {
        const rows = flowers.get(art);
        if (!rows) return null;
        const row = rows[wilting ? 1 : 0] ?? rows[0];
        return row[Math.max(0, Math.min(row.length - 1, stage))] ?? null;
    },

    /** 後花園背景（未載入回 null）。 */
    garden(): SpriteFrame | null { return gardenFrame; },

    /** 糖果鎮的角色/小動物圖（檔名同 resources/candy/）。 */
    candy(name: string): SpriteFrame | null { return candyArt.get(name) ?? null; },

    /** 女巫施法姿勢（正面第一幀；未載入回 null）。動畫請用 castFrames(dir)。 */
    cast(): SpriteFrame | null { return w8Cast[WitchDir.SOUTH]?.[0] ?? castFrame; },

    /** 女巫睡覺立繪（含床，睡覺過場用；未載入回 null）。 */
    sleeping(): SpriteFrame | null { return w8Sleep ?? sleepingFrame; },

    /** 藥水室背景（night=true 回夜晚版；未載入回 null）。 */
    brewRoom(night: boolean): SpriteFrame | null { return (night ? brewRoomNightFrame : brewRoomDayFrame); },

    /** 任務簿捲軸底板（未載入回 null）。 */
    questScroll(): SpriteFrame | null { return questScrollFrame; },

    /** 更新公告板木框（未載入回 null）。 */
    updateFrame(): SpriteFrame | null { return updateFrameArt; },
};
