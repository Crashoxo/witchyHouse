import { resources, SpriteFrame, ImageAsset, Rect, director } from 'cc';
import { ITEM_FILES, POTION_ITEMS, CANDY_ITEMS } from './data/items';
import { FLOWERS } from './data/garden';
import { OUTFITS } from './data/outfits';
import { CANDY_NPCS, CANDY_CRITTERS, CANDY_BUILDINGS, CANDY_PROPS } from './data/candy';

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

/**
 * 換裝：`resources/witch/<造型 id>/` 底下放的是同一批姿勢的改色版。
 * 有載入造型時，下面這幾組會蓋掉預設那批（accessor 自己判斷），所以**呼叫端完全不用改**。
 * 走路/待機原本是 CharacterAnimator 在場景裡用 @property 指定的，因此多開 walk/idle 兩個。
 */
const WALK_FRAMES = 5;
const oWalk: SpriteFrame[] = [];
const oGather: SpriteFrame[] = [];
const oWater: SpriteFrame[] = [];
const oPick: SpriteFrame[] = [];
let oIdle: SpriteFrame | null = null;
let oCast: SpriteFrame | null = null;
let oSleeping: SpriteFrame | null = null;
let outfitId = '';                                  // ''＝預設造型（用原本那批圖）
let dialogueBoxFrame: SpriteFrame | null = null;    // 對話框外框
let brewRoomDayFrame: SpriteFrame | null = null;    // 藥水室背景（白天）
let brewRoomNightFrame: SpriteFrame | null = null;  // 藥水室背景（夜晚）
let gardenFrame: SpriteFrame | null = null;         // 後花園背景（草地＋柵欄）
let candyMapFrame: SpriteFrame | null = null;       // 糖果鎮地圖
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

/**
 * 同 loadSingle，但**載不到不當錯**（只留一行提示）。
 * 造型資料夾是「缺哪張就沿用預設哪張」的設計，之後手繪版只補幾張也不會噴一排紅字。
 */
function loadGuarded(path: string, set: (sf: SpriteFrame) => void): void {
    pending++;
    resources.load(path, ImageAsset, (err, img) => {
        if (!err && img) set(SpriteFrame.createWithImage(img));
        else console.log(`[GameArt] 造型缺圖，沿用預設：${path}`);
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
        loadSingle('rooms/candy-town', sf => { candyMapFrame = sf; });
        for (const n of CANDY_NPCS) loadImg(candyArt, n.art, `candy/${n.art}`);
        for (const c of CANDY_CRITTERS) loadImg(candyArt, c.art, `candy/${c.art}`);
        // 建築與裝飾（同名只載一次：requested 那層擋不到重複的 art，這裡自己去重）
        const seen: Record<string, boolean> = {};
        for (const b of CANDY_BUILDINGS.concat(CANDY_PROPS)) {
            if (seen[b.art]) continue;
            seen[b.art] = true;
            loadImg(candyArt, b.art, `candy/${b.art}`);
        }
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
        oWalk.length = 0; oGather.length = 0; oWater.length = 0; oPick.length = 0;
        oIdle = oCast = oSleeping = null;
        if (!id) return;

        started = true;
        const mine = () => outfitId === id;          // 換過造型就丟掉晚到的結果
        oWalk.length = WALK_FRAMES;
        for (let i = 0; i < WALK_FRAMES; i++) loadGuarded(`witch/${id}/walk${i + 1}`, sf => { if (mine()) oWalk[i] = sf; });
        oGather.length = GATHER_FRAMES;
        for (let i = 0; i < GATHER_FRAMES; i++) loadGuarded(`witch/${id}/gather${i + 1}`, sf => { if (mine()) oGather[i] = sf; });
        oWater.length = WATER_FRAMES;
        for (let i = 0; i < WATER_FRAMES; i++) loadGuarded(`witch/${id}/water${i + 1}`, sf => { if (mine()) oWater[i] = sf; });
        oPick.length = PICK_FRAMES;
        for (let i = 0; i < PICK_FRAMES; i++) loadGuarded(`witch/${id}/pick${i + 1}`, sf => { if (mine()) oPick[i] = sf; });
        loadGuarded(`witch/${id}/idle`, sf => { if (mine()) oIdle = sf; });
        loadGuarded(`witch/${id}/cast`, sf => { if (mine()) oCast = sf; });
        loadGuarded(`witch/${id}/sleeping`, sf => { if (mine()) oSleeping = sf; });
    },

    /** 造型的走路幀（預設造型回空陣列＝沿用場景裡指定的那批）。 */
    walkFrames(): SpriteFrame[] { return oWalk.filter(Boolean); },
    /** 造型的待機圖（預設造型回 null）。 */
    idle(): SpriteFrame | null { return oIdle; },

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
     * 側面一律朝左，往右走請把節點 scale.x 取負（同女巫的作法）。
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

    /** 女巫採集動畫幀（0..2；未載入回空陣列）。 */
    /** 採集三幀。有換造型就用造型版（下面 water/pick/cast/sleeping 同理）。 */
    gatherFrames(): SpriteFrame[] {
        return oGather.filter(Boolean).length ? oGather.filter(Boolean) : gather.filter(Boolean);
    },

    /** 女巫澆水動畫幀（0..3；未載入回空陣列）。 */
    waterFrames(): SpriteFrame[] {
        return oWater.filter(Boolean).length ? oWater.filter(Boolean) : water.filter(Boolean);
    },

    /** 女巫摘花動畫幀（0..3；未載入回空陣列）。 */
    pickFrames(): SpriteFrame[] {
        return oPick.filter(Boolean).length ? oPick.filter(Boolean) : pick.filter(Boolean);
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

    /** 糖果鎮地圖。 */
    candyMap(): SpriteFrame | null { return candyMapFrame; },
    /** 糖果鎮的角色/小動物圖（檔名同 resources/candy/）。 */
    candy(name: string): SpriteFrame | null { return candyArt.get(name) ?? null; },

    /** 女巫施法姿勢（正面；未載入回 null）。 */
    cast(): SpriteFrame | null { return oCast ?? castFrame; },

    /** 女巫睡覺立繪（含床，睡覺過場用；未載入回 null）。 */
    sleeping(): SpriteFrame | null { return oSleeping ?? sleepingFrame; },

    /** 藥水室背景（night=true 回夜晚版；未載入回 null）。 */
    brewRoom(night: boolean): SpriteFrame | null { return (night ? brewRoomNightFrame : brewRoomDayFrame); },

    /** 任務簿捲軸底板（未載入回 null）。 */
    questScroll(): SpriteFrame | null { return questScrollFrame; },

    /** 更新公告板木框（未載入回 null）。 */
    updateFrame(): SpriteFrame | null { return updateFrameArt; },
};
