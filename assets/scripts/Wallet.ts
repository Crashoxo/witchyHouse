/**
 * 玩家錢包（金幣）。金額存在 module 變數，`director.loadScene` 換場景時會保留
 * （JS 模組不重跑）。ShopPanel 賣東西時 add()，Hud 常駐顯示讀 gold。
 * 尚無存檔（關掉遊戲會歸零）。
 */
let gold = 0;

export const Wallet = {
    get gold(): number { return gold; },
    add(amount: number): void { gold += amount; },
    set(amount: number): void { gold = amount; },
};
