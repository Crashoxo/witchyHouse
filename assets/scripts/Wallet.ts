import { SaveManager } from './SaveManager';

/**
 * 玩家錢包（金幣）。金額存在 module 變數（換場景 `director.loadScene` 保留），
 * 並透過 `SaveManager` 存檔 —— 關掉遊戲再開，金幣還在。
 * ShopPanel 賣東西時 add()，Hud 常駐顯示讀 gold。
 */
const KEY = 'witch.gold';

function load(): number {
    const v = SaveManager.getString(KEY);
    const n = v ? parseInt(v, 10) : 0;
    return Number.isFinite(n) ? n : 0;
}

let gold = load();

function save() {
    SaveManager.setString(KEY, String(gold));
}

export const Wallet = {
    get gold(): number { return gold; },
    add(amount: number): void { gold += amount; save(); },
    set(amount: number): void { gold = amount; save(); },
};
