import { sys } from 'cc';

/**
 * 中央存檔管理：所有 `witch.*` 存檔都經過這裡，帶「格式版本號」＋ migration。
 *
 * 為什麼要這層：
 *  1. **版本號**：日後改動任一存檔的資料結構時，舊玩家的存檔不會壞——在
 *     `MIGRATIONS` 補一條「舊版→新版」的搬移即可，開檔時自動升級。
 *  2. **單一進出點**：目前後端是 `sys.localStorage`。之後上 Steam 包 Electron
 *     要把存檔寫進「玩家電腦的檔案」時，**只要換掉下面 `backend` 的三個方法**
 *     （改成走 Electron 的 fs / IPC），其他所有模組（Wallet/Inventory/…）完全不用動。
 *
 * 各模組仍保有自己的「防壞檔驗證」邏輯——這層只負責 read/write 字串與版本，
 * 不碰各自的資料格式。
 */

/** 存檔格式版本。改變任一 key 的資料結構時 +1，並在 MIGRATIONS 補一條升級。 */
export const SAVE_VERSION = 1;

/** 版本號自己的存放 key。 */
const VER_KEY = 'witch.save.version';

/** 所有已知存檔 key（給版本偵測／清檔用）。**新增存檔 key 時記得補進這裡。** */
export const SAVE_KEYS: string[] = [
    'witch.gold',            // Wallet：金幣
    'witch.stock',           // Inventory：背包堆疊
    'witch.shop.listings',   // ShopStock：貨架上架
    'witch.time',            // TimeSystem：日期/時刻
    'witch.quests.state',    // Quests：已接/已領
    'witch.quests.counters', // Quests：目標累計計數
    'witch.upgrades',        // Upgrades：升級等級
    'witch.decor.owned',     // DecorCatalog：擁有的裝飾
    'witch.decor.placed',    // DecorCatalog：擺出的裝飾
];

/**
 * 存檔後端 —— **整個遊戲唯一真正碰儲存的地方**。
 * 上 Steam / Electron 時把這三個方法改成寫玩家硬碟檔案即可，其餘不動。
 */
const backend = {
    get(key: string): string | null { return sys.localStorage.getItem(key); },
    set(key: string, val: string): void { sys.localStorage.setItem(key, val); },
    remove(key: string): void { sys.localStorage.removeItem(key); },
};

/**
 * 版本升級表：key＝來源版本 v，值＝把「v 版的存檔」就地改寫成「v+1 版」。
 * v0（沒有版本號的舊存檔）→ v1：現行格式即 v1 基準，不需搬資料。
 * 之後例如把某 key 換結構時：`MIGRATIONS[1] = () => { ...讀舊寫新... }` 並把 SAVE_VERSION 改 2。
 */
const MIGRATIONS: Record<number, () => void> = {
    0: () => { /* v0 → v1：現行格式就是 v1 基準，無需轉換 */ },
};

/** 讀目前存檔的版本；沒有版本號時：已有任何存檔＝舊檔(v0)，全新遊戲＝視為最新版。 */
function readVersion(): number {
    const raw = backend.get(VER_KEY);
    if (raw != null) {
        const n = parseInt(raw, 10);
        if (Number.isFinite(n)) return n;
    }
    for (let i = 0; i < SAVE_KEYS.length; i++) {
        if (backend.get(SAVE_KEYS[i]) != null) return 0; // 升級前的舊存檔
    }
    return SAVE_VERSION; // 全新遊戲
}

/** 逐版套用 migration，最後把版本號蓋成最新。 */
function migrate(): void {
    let v = readVersion();
    while (v < SAVE_VERSION) {
        const step = MIGRATIONS[v];
        if (step) {
            try { step(); }
            catch (e) { console.warn('[SaveManager] migration', v, '失敗', e); }
        }
        v++;
    }
    backend.set(VER_KEY, String(SAVE_VERSION));
}

// ⚠️ import 本模組時「立刻」跑一次 migration。ES module 保證：本模組會在任何
// `import` 它的模組（Wallet/Inventory/…）執行自己 top-level 的 load() 之前先跑完，
// 所以各模組讀到的一定是已升級到最新版的存檔。
migrate();

export const SaveManager = {
    /** 目前存檔格式版本。 */
    version: SAVE_VERSION,

    /** 讀原始字串（無值回 null）——各模組沿用自己的解析/驗證。 */
    getString(key: string): string | null { return backend.get(key); },

    /** 寫原始字串。 */
    setString(key: string, val: string): void { backend.set(key, val); },

    /** 讀 JSON（無值或解析失敗回 fallback）。給新程式用；舊模組沿用 getString。 */
    getJSON<T>(key: string, fallback: T): T {
        const raw = backend.get(key);
        if (raw == null) return fallback;
        try {
            const o = JSON.parse(raw);
            return o == null ? fallback : (o as T);
        } catch { return fallback; }
    },

    /** 寫 JSON。 */
    setJSON(key: string, val: unknown): void { backend.set(key, JSON.stringify(val)); },

    /** 刪一個 key。 */
    remove(key: string): void { backend.remove(key); },

    /** 清掉所有存檔（開新遊戲用），並把版本號設為最新。 */
    wipe(): void {
        for (let i = 0; i < SAVE_KEYS.length; i++) backend.remove(SAVE_KEYS[i]);
        backend.set(VER_KEY, String(SAVE_VERSION));
    },
};
