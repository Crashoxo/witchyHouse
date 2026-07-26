/**
 * 村民「內容」資料：玩家資訊面板（Tab）的村民頁要顯示誰、頭像用哪張、住在哪。
 *
 * ⚠️ `name` 必須跟場景裡 TalkNpc 的 `npcName` 完全一致 —— 友誼度是用名字當 key 記的
 * （同 Quests 的 giver 對應方式），這樣新增村民只要「掛上 TalkNpc + 在這裡加一筆」。
 */

export interface VillagerDef {
    /** 名字（＝TalkNpc.npcName＝友誼度的 key）。 */
    name: string;
    /** GameArt portraits 的頭像名（留空＝面板畫一個代用圓框）。 */
    portrait: string;
    /** 住處／店名。 */
    place: string;
    /** 一句話介紹。 */
    desc: string;
}

export const VILLAGERS: VillagerDef[] = [
    { name: '地精老闆', portrait: 'gnome', place: '藥水鋪',
      desc: '鎮上開店最久的地精，嘴上唸個不停，其實很照顧新來的。' },
    { name: '精靈書商', portrait: 'elf', place: '卷軸鋪',
      desc: '賣卷軸與古書的精靈，對能背下配方的人特別有好感。' },
    { name: '魔法貓', portrait: 'fox', place: '法術鋪',
      desc: '看店的黑貓。沒人知道真正的店主是誰，牠也不打算說。' },
];

/** 每一顆心需要的友誼點數，以及最多幾顆心。 */
export const POINTS_PER_HEART = 50;
export const MAX_HEARTS = 5;

/** 每天第一次跟同一位村民交談可得的友誼點數。 */
export const TALK_POINTS = 8;
