/**
 * 全域 UI 狀態旗標（跨腳本共用）。
 *
 * modalOpen＝目前有沒有開著擋操作的視窗（商店、對話…）。開著時
 * PlayerController 不移動 / 不施法、GatherTree 不採集，避免操作穿透到世界。
 * 用一個純物件而不是某個元件的 static，是為了讓各腳本都能引用又不互相牽連。
 */
export const UIState = {
    modalOpen: false,
};
