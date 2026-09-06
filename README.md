# 魔女商店（Unity 版）

從 Cocos Creator 移植過來的 2D 俯視角經營遊戲。原專案在 `D:\Crash\witch-shop`。

**Unity 6.6 (6000.6.0f1)** · C# 86 檔 / 13,400 行 · 六張地圖

## 開起來

1. Unity Hub → Add → 選這個資料夾
2. 第一次開要等它匯入 260 張圖並建 Library
3. 選單 **Witch Shop → 建立 UI 設定檔**（第一次一定要跑）
4. 選單 **Witch Shop → 重新登記所有場景**
5. Project 視窗開 `Assets/Scenes/main.unity` → ▶ Play

⚠️ 切換地圖是在 Project 視窗對 `.unity` 檔點兩下 ——
**「建立◯◯場景」那些選單是從頭重蓋**，平常不要按。

## 玩什麼

森林採集 → 進城賣掉或帶回自己的店上架 → 顧客上門買 → 賺錢升級招牌貨架
→ 藥水室煉藥、後花園種花 → 糖果鎮進貨賺價差 → 接任務、經營名聲 → 睡覺看當日結算、跳到隔天

| 鍵 | 功能 |
|---|---|
| `WASD` / 方向鍵 | 走路（`Shift` 衝刺）|
| `E` | 採集／交談／進門／櫃台／睡覺／澆花 |
| `J` / 空白 | 施法 |
| `B` | 背包 |
| `Q` | 任務簿 |
| `Tab` / `I` | 女巫的手札 |
| `R` | 店內佈置模式 |

## 文件

- **`PORTING.md`** —— 移植紀錄：決策、踩過的坑、程式結構、資料轉換器
- `Assets/Scripts/Core/PortNotes.md` —— 寫程式時的速查
- `Assets/Resources/ui/fonts/LICENSE-NOTE.txt` —— 字型授權

## 網頁版

`Witch Shop → 建置 → 網頁版（建好直接開瀏覽器）`。第一次 15～40 分鐘。
⚠️ 不能直接點 `index.html`，一定要走伺服器。
