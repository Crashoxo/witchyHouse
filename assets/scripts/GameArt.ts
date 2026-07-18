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

const items = new Map<string, SpriteFrame>();       // 材料名 → 圖
const customers = new Map<string, SpriteFrame>();   // 動物名 → 圖
const emotes = new Map<string, SpriteFrame[]>();    // 表情名 → 動畫幀陣列
const portraits = new Map<string, SpriteFrame>();   // 頭像名 → 圖
const decor = new Map<string, SpriteFrame>();       // 裝飾品 id → 圖
let dialogueBoxFrame: SpriteFrame | null = null;    // 對話框外框

let loaded = false;
let loading = false;
const readyCbs: Array<() => void> = [];

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
        const emoteNames = Object.keys(EMOTE_INFO);

        const total = singleJobs.length + emoteNames.length + 1;   // +1 = 對話框外框
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
    customerNames(): string[] { return [...customers.keys()]; },

    /** 表情動畫幀陣列（未載入回 null）。 */
    emote(name: string): SpriteFrame[] | null { return emotes.get(name) ?? null; },

    /** 所有已載入的表情名（給隨機挑選用）。 */
    emoteNames(): string[] { return [...emotes.keys()]; },

    /** NPC / 對話頭像（未載入回 null）。 */
    portrait(name: string): SpriteFrame | null { return portraits.get(name) ?? null; },

    /** 對話框外框（未載入回 null）。 */
    dialogueBox(): SpriteFrame | null { return dialogueBoxFrame; },

    /** 裝飾品圖（未載入回 null）。 */
    decor(id: string): SpriteFrame | null { return decor.get(id) ?? null; },
};
