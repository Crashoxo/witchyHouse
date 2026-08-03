# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 這是什麼專案

Cocos Creator 3.8.8 的 2D 俯視角遊戲（女巫採集 × 商店經營），程式全為 TypeScript，放在 `assets/scripts/`。
遊戲說明、玩法與逐日更新紀錄在 `README.md`（繁體中文），改動玩法前先讀那份。

## 工具鏈：沒有 npm / 測試 / lint

- `package.json` 是 **Cocos 專案描述檔**，不是 npm 專案：沒有 `scripts`、沒有 `dependencies`、沒有 `tsconfig.json`、沒有測試框架、沒有 CI。
  **不要跑 `npm install` / `npm test` / `npx tsc`**，都不會有作用。
- 唯一的驗證方式是用 Cocos Creator 3.8.8 開啟專案實際跑起來。在無編輯器的環境（例如純命令列 session）能做的是靜態閱讀與改碼，**改完要明說沒辦法實測**。
- `library/`、`temp/`、`build/`、`.creator/` 都在 `.gitignore`，clone 下來不會有；第一次用編輯器開會重建，會花一段時間。

## 建置與發佈

編輯器建置 web-mobile，或命令列：

```
CocosCreator.exe --project <專案路徑> --build "configPath=buildConfig-web-mobile.json"
```

然後把 `build/web-mobile/` 的內容覆蓋到 `docs/`（保留 `.nojekyll`）並提交 —— GitHub Pages 由 `docs/` 發佈。
`docs/` 全是建置產物，**不要手改**。

⚠️ `buildConfig-web-mobile.json` 的 `scenes` 只列了 4 個場景（brew / main / town / shop），但實際發佈出去的建置含全部 6 個（`docs/assets/main/config.json` 可以看到另有 garden、candy）。**重建時務必把 6 個場景都納入**，漏了的話走去後花園或糖果鎮會載不到場景。

## 程式風格

- 註解與所有 UI 文字都是**繁體中文**，而且註解寫的是「為什麼這樣做／踩過什麼坑」而不是「這行在做什麼」。延續這個風格，別換成英文或流水帳註解。
- **ES5 build 限制**：`Map` / `Set` 不能 spread、不能 `for...of`（迭代器不展開）。一律用 `forEach` 或 `Object.keys` ＋ 陣列 `for...of`（`GameArt.ts` 開頭有註記）。
- 一個檔一個 `@ccclass`，檔名＝類別名。每個 `.ts` 旁邊有 `.meta`，裡面的 uuid 是場景檔引用腳本的依據 —— **新增／刪除／改名腳本時 `.meta` 必須一起處理**。

## 架構

### 跨場景狀態放在 module 層

換場景走 `director.loadScene`，JS 模組不會重跑，所以要跨場景保留的狀態一律放 **module 變數**：`Inventory` 的 `stock`、`TimeSystem` 的 `totalDays`/`tod`、`Wallet`、`Storage`、`Quests`、`Upgrades`…。場景裡的元件只負責把這份資料畫出來。**不要**把這類狀態放進元件的實例欄位。

### 存檔：`SaveManager.ts` 是唯一出入口

- 所有 key 都是 `witch.*`，集中列在 `SAVE_KEYS` —— **新增一種存檔就要補進那個陣列**。
- `SAVE_VERSION` ＋ `MIGRATIONS`：改任一 key 的資料結構時版本 +1 並補一條 migration。`migrate()` 在 module 被 import 時的 top-level 就跑完，所以各模組讀到的必定是已升級的存檔。
- `backend` 的三個方法是**整個遊戲唯一碰 `localStorage` 的地方**（將來要換成 Electron 寫檔只動這裡）。各模組自己保留壞檔防護（解析失敗就回預設值）。

### 內容資料集中在 `assets/scripts/data/`

配方、任務、價格、裝飾、台詞、季節/節日、村民、傳送點、花草、糖果鎮貨品都在這裡，`data/index.ts` 是 barrel。
調數值或加內容**先看這裡**，不要硬寫在元件裡。這層是「設計內容」，玩家進度走 `SaveManager`，兩者不要混。

`data/portals.ts` 是刻意的例外設計：邊界傳送點的座標放在程式碼而不是場景檔，因為**編輯器開著時改場景檔會被它存檔蓋掉**。同理，需要頻繁調的參數優先放 data/，不要塞進場景。

### UI 幾乎全靠程式生成

- 整個專案只有一個 prefab（`assets/prefabs/Spell.prefab`）。所有面板／HUD 都是在程式裡用 `Graphics`／`Label`／`Sprite` 畫出來的。
- 共同慣例：`static instance` ＋ `static ensure()`（拿不到就自己在 `Canvas` 底下建一個節點掛上元件）。約 24 個腳本都是這個模式。要加新面板就照抄現成的（`BagPanel.ts`、`PlayerInfoPanel.ts` 是比較完整的範例）。
- `UIState.modalOpen` 是全域「擋操作」旗標：面板開著時 `PlayerController` 不移動不施法、`GatherTree` 不採集、時鐘凍結。**新面板一定要在開關時維護它**，否則操作會穿透到世界。

### 美術：`GameArt.ts` 執行期載入

- `assets/resources/` 底下的圖用 `resources.load` **依路徑**載入（不吃 uuid），檔名表寫在 `GameArt.ts` 上半部。
- 分組載入：`common` 開機就載，其餘依 `SCENE_GROUPS` 按目前場景名決定。新增場景或素材要同步補 `SCENE_GROUPS` 與對應的檔名常數；拿不到場景名時會退回全載（寧可不省也不缺圖）。
- 載入是非同步：呼叫端一律 `GameArt.preload()` ＋ `GameArt.onReady(cb)`，不要假設圖已經在。
- 村民走路表固定是 4 欄 × 3 列（下／側／上，側面一律朝左，往右走靠翻面）。

### 場景與換場景

6 個場景：`brew`（藥水室）、`main`（森林）、`town`（城鎮）、`shop`（自己的店）、`garden`（後花園）、`candy`（糖果鎮）。

⚠️ 起始場景目前三處對不上：README 與 `buildConfig-web-mobile.json` 的 `startScene` 都是 `brew`（女巫的房間），但已發佈的 `docs/` 建置 `launchScene` 是 `db://assets/main.scene`（森林），程式裡也沒有開場轉場的程式碼。動到開場流程前先確認想要的是哪一個。

兩種傳送方式：

1. **地圖邊界** —— 走哪一側、去哪裡定在 Player 節點上 `PlayerController` 的 `nextMapScene` / `nextMapEdge`；那一側的哪個定點能過去定在 `data/portals.ts`。
2. **門** —— `SceneDoor` 掛在當門的節點上，走上去就換場景（`E` 仍可用）。`interactRange`（顯示提示）與 `autoRange`（真的傳送）刻意分開，別把兩者調成一樣，否則走過房子旁邊就會被吸進去。出生點若落在門的範圍內，會先上鎖等玩家走開一次才啟用（不然兩個場景無限來回）。

`PortalGlow` 在執行期從場景樹掃出所有門來畫光暈，**新增的門會自動發光，不必額外設定**。光暈畫得比判定範圍略小，維持「看得到的地方一定走得過去」。

按鍵分工是刻意的：**`E` ＝跟東西互動（櫃台／鍋爐／NPC／採集），走上去＝換地方**。

### 場景樹慣例

- `World/Roads`：路面，不做前後遮擋，永遠畫在角色下方。
- `World/Props`：噴泉、城門、路燈等，掛 `YSortLayer` 每幀依 y 由大到小重排 siblingIndex 做遮擋 —— **前提是每個物件的錨點都是 (0.5, 0)**。
- 疊層順序：`DayNightTint`（全螢幕天色色板）疊在世界之上、HUD 之下，只套用在 `main` / `town`；`ShadowLayer`、`LampGlow`、`PortalGlow` 各自 `ensure()` 生成。

### 時間系統

`TimeSystem.ts` 照星露谷節奏：10 遊戲分鐘 = 7.3 真實秒、連續累積（指針平滑走，不是每 7.3 秒跳一格），一天 06:00 起 02:00 昏倒。年曆是 28 天 × 12 月 × 4 季，定在 `data/seasons.ts`。
每日結算由 newDay callback 驅動（`DailyLog` 記帳 → `DaySummaryPanel` 顯示 → `Reputation` 累積名聲）。`UIState.modalOpen` 為 true 時時間凍結。

## 改完之後

作者的慣例是功能改動要同步更新兩處玩家看得到的說明：`README.md` 的「更新紀錄」章節，以及遊戲內公告板 `UpdatePanel.ts` 的 `UPDATE_LINES`（＋上方的日期）。做了玩家有感的改動時記得一起改。

## Git

`origin` 是 `amux2048/witchyHouse`，這是 `Crashoxo/witchyHouse` 的 fork。要送回上游時 base 選 `Crashoxo/witchyHouse:main`、head 選本 fork 的分支。
