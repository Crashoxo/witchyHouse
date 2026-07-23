/**
 * 任務「內容」資料：型別 + 所有任務定義（QUEST_DEFS）。
 * 任務系統的狀態機、進度、存檔邏輯在 Quests.ts。
 *
 * 目標種類：
 *   gather / sell / brew —— 累積計數（採集/賣出/調配「總數」，只增不減）。item 留空＝任意種類。
 *   have   —— 目前背包持有 N 個（consume=true 時回報會扣掉＝送貨任務）。
 *   gold   —— 錢包金幣達到 N。
 */

export type ObjKind = 'gather' | 'sell' | 'brew' | 'have' | 'gold';

export interface QuestObjective {
    kind: ObjKind;
    item?: string;      // gather/sell/brew/have 的物品名；留空＝任意（gather/sell/brew）。gold 不用
    count: number;
    consume?: boolean;  // have 專用：回報時把物品扣掉（送貨任務）
}

export interface QuestDef {
    id: string;
    giver: string;          // 發任務的 NPC 名（＝TalkNpc.npcName，用來對應）
    title: string;
    objective: QuestObjective;
    rewardGold: number;
    rewardItem?: string;    // 額外物品獎勵（可省）
    rewardQty?: number;
    offerLines: string[];   // 提供任務時 NPC 說的話
    activeLines: string[];  // 進行中（還沒完成）
    readyLines: string[];   // 完成、可回報時
    doneLines: string[];    // 領獎後
    requires?: string;      // 前置任務 id（要先 claimed 才會解鎖）
}

/** 地精老闆的任務鏈（依 requires 串成前後接續）。 */
export const QUEST_DEFS: QuestDef[] = [
    {
        id: 'gather_wood', giver: '地精老闆', title: '收集木材',
        objective: { kind: 'gather', item: '木材', count: 5 },
        rewardGold: 30,
        offerLines: ['唉，我的藥架又搖搖晃晃了…',
                     '你能幫我到東邊森林採 5 個木材回來嗎？'],
        activeLines: ['木材採到 5 個了嗎？往東邊森林走，靠近樹按 E 就能採。'],
        readyLines: ['喔！木材都齊了，太感謝你了！'],
        doneLines: ['這 30 金幣是謝禮，拿去吧。'],
    },
    {
        id: 'sell_three', giver: '地精老闆', title: '第一批生意',
        objective: { kind: 'sell', count: 3 },
        rewardGold: 40, requires: 'gather_wood',
        offerLines: ['開店最重要的，就是把東西賣出去。',
                     '去把商品上架，賣出 3 件給上門的客人，讓我看看你的本事。'],
        activeLines: ['賣出 3 件商品了嗎？把材料或藥水擺上桌，客人自然會來。'],
        readyLines: ['生意做得有模有樣嘛！'],
        doneLines: ['這是給新手老闆的鼓勵，收下這 40 金。'],
    },
    {
        id: 'brew_two', giver: '地精老闆', title: '初嘗煉金',
        objective: { kind: 'brew', count: 2 },
        rewardGold: 60, requires: 'sell_three',
        offerLines: ['光賣原料利潤太薄了。',
                     '到店裡右上角的藥水室，調配 2 瓶藥水吧——附加價值高多了。'],
        activeLines: ['調好 2 瓶藥水了嗎？店面右上角進藥水室，走到鍋爐按 E。'],
        readyLines: ['我聞到藥香了！你有天份。'],
        doneLines: ['這瓶配方費 60 金給你，繼續加油。'],
    },
    {
        id: 'deliver_berry', giver: '地精老闆', title: '地精的點心',
        objective: { kind: 'have', item: '漿果', count: 5, consume: true },
        rewardGold: 50, rewardItem: '金蘋果', rewardQty: 1, requires: 'brew_two',
        offerLines: ['說來有點不好意思…我肚子餓了。',
                     '幫我帶 5 個漿果來，我請你吃一顆金蘋果！'],
        activeLines: ['漿果帶來了嗎？背包裡要有 5 個，我才收得下。'],
        readyLines: ['哇，新鮮的漿果！謝謝你～'],
        doneLines: ['說好的金蘋果給你，還有 50 金當跑腿費！'],
    },
    {
        id: 'gold_300', giver: '地精老闆', title: '小有積蓄',
        objective: { kind: 'gold', count: 300 },
        rewardGold: 100, rewardItem: '金蘋果', rewardQty: 2, requires: 'deliver_berry',
        offerLines: ['當老闆的目標是什麼？當然是賺錢！',
                     '等你存到 300 金幣，再來找我，有好東西給你。'],
        activeLines: ['存到 300 金幣了嗎？多調點藥水賣，錢很快就進來了。'],
        readyLines: ['300 金！你已經是像樣的老闆了。'],
        doneLines: ['這是給成功商人的賀禮：100 金，還有兩顆金蘋果！'],
    },

    // 精靈書商（scroll-shop）的支線——用採集/金幣目標，不跟地精的 sell/brew 累積衝突
    {
        id: 'eb_herbs', giver: '精靈書商', title: '古籍的配方',
        objective: { kind: 'gather', item: '藥草', count: 4 },
        rewardGold: 35,
        offerLines: ['這本舊書寫著一帖失傳的配方…', '幫我採 4 株藥草來，我想試著重現它。'],
        activeLines: ['藥草採到 4 株了嗎？森林的花圃裡就有。'],
        readyLines: ['正是這種藥草！書上畫的沒錯。'],
        doneLines: ['謝謝你，這 35 金是酬勞。'],
    },
    {
        id: 'eb_rich', giver: '精靈書商', title: '藏書的價值',
        objective: { kind: 'gold', count: 500 },
        rewardGold: 0, rewardItem: '金蘋果', rewardQty: 2, requires: 'eb_herbs',
        offerLines: ['知識是無價的，但書可不便宜。', '等你存到 500 金幣，我把珍藏的好東西分你一些。'],
        activeLines: ['存到 500 金幣了嗎？藥水利潤最高囉。'],
        readyLines: ['哇，你真的辦到了！'],
        doneLines: ['說好的珍藏——兩顆金蘋果，收下吧。'],
    },

    // 魔法貓（spell-shop）的支線——同樣用採集目標
    {
        id: 'cat_berries', giver: '魔法貓', title: '喵的點心',
        objective: { kind: 'gather', item: '黑莓', count: 3 },
        rewardGold: 30,
        offerLines: ['喵～我最愛黑莓了。', '去採 3 顆黑莓給我，我告訴你一個祕密，喵。'],
        activeLines: ['黑莓採到 3 顆了嗎？荊棘叢裡有喔，喵。'],
        readyLines: ['喵嗚～就是這個味道！'],
        doneLines: ['祕密是…東邊森林的樹會結金蘋果喔。這 30 金給你，喵。'],
    },
    {
        id: 'cat_leaves', giver: '魔法貓', title: '鋪窩大工程',
        objective: { kind: 'gather', item: '落葉', count: 6 },
        rewardGold: 40, requires: 'cat_berries',
        offerLines: ['本喵想鋪一個又軟又香的窩，喵。', '幫我收集 6 片落葉吧！'],
        activeLines: ['落葉撿到 6 片了嗎？樹下的落葉堆最多，喵。'],
        readyLines: ['蓬鬆鬆的，本喵很滿意，喵～'],
        doneLines: ['賞你 40 金，去買點好吃的吧，喵。'],
    },
];
