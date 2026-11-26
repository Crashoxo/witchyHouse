# 魔女商店 —— Cocos Creator → Unity 移植紀錄

原專案：`D:\Crash\witch-shop`（Cocos Creator 3.x / TypeScript）
本專案：`D:\Crash\witch-unity`（Unity 6.6 / C#）

| | Cocos | Unity |
|---|---|---|
| 程式 | 82 檔 / 13,287 行 TS | 86 檔 / 13,400 行 C# |
| UI | 純程式碼堆節點 | UI Toolkit（UXML + USS）5 檔 |
| 美術 | `assets/resources/` 260 張 | 原封搬到 `Assets/Resources/` |
| 場景 | 6 個（幾乎是空的） | 6 個（同樣幾乎是空的） |

---

## 一、怎麼跑起來

### 開專案
Unity Hub → Add → 選 `D:\Crash\witch-unity`。第一次開要等它匯入 260 張圖並建 Library。

### 建場景（改了場景產生程式才需要）
選單 **Witch Shop** 底下：

| 選單 | 產出 |
|---|---|
| 建立森林場景 | `main.unity` —— 84 個採集點 |
| 建立城鎮場景 | `town.unity` —— 71 個擺設、NPC、商店 |
| 建立商店場景 | `shop.unity` —— 等距房間 |
| 建立後花園場景 | `garden.unity` |
| 建立藥水室場景 | `brew.unity` |
| 建立糖果鎮場景 | `candy.unity` |
| **重新登記所有場景** | 把上面全部加進 Build Settings |
| 建立 UI 設定檔 | UI Toolkit 的 `PanelSettings`（**第一次一定要跑**）|
| 設定成 2D 專案 | 專案層級的 2D 模式旗標 |

⚠️ **平常切換地圖不要用這些選單** —— 它們是「從頭重蓋」。要換地圖就在 Project 視窗對 `.unity` 檔點兩下。

### 測試工具
`Witch Shop → 測試用`：塞道具進背包／倉庫、給 5000 金幣、塞一天的營業紀錄（睡一覺看每日結算）、
清空存檔、顯示存檔位置。

### 改了中文字串
`python tools/subset_font.py` —— 重新產生子集字型（見第三節第 6 點）。忘了跑，新加的字會是豆腐。

### 重產音效
`python tools/gen_sfx.py` —— 用程式合成整套 8-bit 佔位音效，輸出到 `Assets/Resources/audio/*.wav`
（純標準函式庫、固定亂數種子，重跑結果一樣）。⚠️ 會**覆蓋同名檔**：已經換成正式音檔的話別跑（見第九節 2026-11-19）。

### 重產音樂
`python tools/gen_bgm.py`（或只產一首：`… day` / `night` / `shop` / `candy`）—— 用程式合成四首無縫循環的
8-bit 背景音樂，輸出到 `Assets/Resources/audio/bgm/*.wav`（沿用 gen_sfx 的合成函式、固定種子，重跑位元組相同；
一首十幾秒以內跑完）。⚠️ 一樣會**覆蓋同名檔**：換成正式音樂之後別再跑（見第九節 2026-11-25）。

### 重烤戶外地面
`python tools/bake_ground.py`（或只烤一張：`… forest` / `town` / `candy`）—— 離線重新產生森林／城鎮／
糖果鎮的地面圖（Pillow＋numpy、固定種子，重跑位元組相同），不用開 Unity。
`--preview <資料夾>` 順便輸出疊上物件與女巫的預覽；`--restore` 還原原圖。細節見 `tools/ground/README.md`
與第九節 2026-11-19「戶外地面重烤」。

### 重產落地範圍（玩家碰撞）
`python tools/gen_footprints.py` —— 量森林／城鎮／糖果鎮擺出來的每張圖「貼地那一段」，依類別規則產生
`Assets/Scripts/Data/ArtFootprints.cs`（Pillow＋numpy，只讀圖、重跑結果一樣）。**換了物件美術、新增物件種類、
或要調某一類的碰撞範圍**（改產生器裡的 `CATS`）都要重跑。接著
`python tools/check_walkable.py <資料夾>` —— 用同一份規則離線做 flood fill 可達性檢查（互動點、門、邊界出口、
村民路點），並在資料夾裡輸出每張地圖的障礙俯視預覽。走不到的互動點清單要是空的（有的話結束碼是 1）。
見第九節 2026-11-25「碰撞與地圖邊緣」。

### 重畫魔女的房間（藥水室）
`python tools/gen_brew_room.py` —— 用程式組 SVG 畫整間房與每一件家具，轉成像素風 PNG
（`Assets/Resources/rooms/brew/`，SVG 原稿留在 `tools/brew_room/svg/`），並產生配置表
`Assets/Scripts/Data/BrewRoomLayout.cs`（Pillow＋numpy＋本機的無頭 Chrome 當 SVG 轉檔器，固定種子可重跑）。
`--preview <資料夾>` 輸出白天／夜晚／碰撞範圍的合成預覽；`--check` 只跑互動點與可走範圍檢查。
**搬家具、改互動距離、改碰撞都改產生器裡的常數**，不要手改 `BrewRoomLayout.cs`。
見第九節 2026-11-25「魔女的房間改用 SVG 重畫」。

### 改完程式想先確認編得過
`bash tools/typecheck.sh` —— 用 Unity 內附的 Roslyn 離線編一次，不用開 Unity。

⚠️ **Unity 開著的時候專案是鎖住的**，`Unity.exe -batchmode -quit` 會直接以 exit code 1 結束、
log 只有 60 行也沒有任何錯誤訊息 —— 看起來很像「編過了」，其實根本沒編。

### 網頁版
`Witch Shop → 建置 → 網頁版（建好直接開瀏覽器）`。
第一次要 15～40 分鐘（IL2CPP 把 C# 翻成 C++ 再編成 WebAssembly）。

⚠️ **不能直接點兩下 `index.html`** —— 瀏覽器的 `file://` 擋掉 WebAssembly 的載入方式，畫面會全黑。一定要走伺服器。

### 更新線上版（GitHub Pages）

線上位置 <https://crashoxo.github.io/witchyHouse/>，來源是 `main` 分支的 `/docs`。

```
① 改程式（先在編輯器裡玩過）
② 選單 Witch Shop → 建置 → 網頁版（給 GitHub Pages）    ← 少了這步網站不會變
③ git add -A && git commit -m "..."
④ git push
⑤ 等約一分鐘，Pages 自己重新發布
```

⚠️ **改程式 ≠ 網站更新**：網站吃的是 `docs/`，那是**建置產物**。只 commit 原始碼，線上還是舊的。

不開 Unity 也能建（要先確認**沒有 Unity 行程在跑**，專案會被鎖住）：

```
"C:\Program Files\Unity\Hub\Editor\6000.6.0f1\Editor\Unity.exe" ^
  -batchmode -quit -nographics -projectPath "D:\Crash\witch-unity" ^
  -executeMethod WebBuilder.BuildForPages -logFile build.log
```

### ⚠️ RAV（ReasonLabs）會擋掉 Unity 的建置

這台機器上的防毒把 Unity 呼叫 dotnet 的命令列判成「Obfuscated command line execution」。
症狀是 log 出現

```
##### Failed because this command failed to write the following output files:
Library\BuildPlayerData\Editor\TypeDb-All.json
```

之後**整個卡死、CPU 歸零、完全沒有錯誤訊息** —— 看起來很像還在跑，其實已經死了
（量一下那個行程的累計 CPU 時間就知道：跑了半小時卻只有十幾秒）。

解法：RAV 視窗 → **Threats** 分頁 → 勾起那兩條（`powershell.exe` 與 Unity 的 `cmd.exe`）
→ 按 **Allow**。⚠️ 不要按 Remove，那會把 Windows 的 PowerShell 跟 Unity 的建置工具當病毒清掉。

同一個毛病也會咬**從命令列跑的 `python`**（例如 `tools/subset_font.py`）：指令卡住不動、
沒有輸出也沒有效果。一樣去 Threats 分頁 Allow。

---

## 二、操作

| 鍵 | 功能 |
|---|---|
| `WASD` / 方向鍵 | 走路（按住 `Shift` 衝刺）|
| 滑鼠點地面 | 自動走過去 |
| `E` | 採集／交談／進門／櫃台／睡覺／澆花／開倉庫／換衣服 |
| `J` / 空白 | 施法（射出魔法彈）|
| `B` | 背包 |
| `Q` | 任務簿（右側捲軸，只列進行中的）|
| `Tab` / `I` | 女巫的手札（任務／物品／村民／日曆）|
| `R` | 店內佈置模式 |
| `O` | 設定（音樂／音效音量、靜音；左上角 HUD 底下的「設定 (O)」也能開）|
| `M` | 聲音靜音／開啟（音樂與音效一起，記在存檔裡）|
| `F3` | 除錯：顯示／隱藏碰撞範圍（紅＝落地範圍、青＝女巫腳底的碰撞圓、黃＝可走範圍；只在戶外地圖）|
| `Esc` | 關閉面板 |

**佈置模式**（店裡按 `R`）：點托盤放進房間／左鍵拖曳搬位置／右鍵收回托盤／`F` 轉向／`T` 換基準點／`R` 完成／`Esc` 取消還原。

放不下的地方會**停在最後一個合法位置**（像撞到牆），擋住的格子標成紅色、原因寫在托盤那行提示上。
擋的規則有五條：超出地板／跟別的東西重疊／門口保留格（紅格）／貨架前的走道（藍格）／圖會穿出牆外。

---

## 三、關鍵移植決策

### 1. Pixels Per Unit = 1
原專案 13k 行裡的座標全是手調出來的**像素值**（`FENCE_WALK = {x:-660,y:250}`、花圃的 `HALF_W = 43`⋯）。PPU 設 1 → 1 世界單位＝1 像素，**這些數字一個都不用改**。

代價是世界座標數值偏大（森林 ±1408），但這專案沒有物理，不影響。設定由 `Editor/PixelArtImporter.cs` 在匯入時自動套用，260 張圖不用手點。

### 2. 場景沿用 Cocos 的檔名
`main` / `town` / `shop` / `brew` / `garden` / `candy`。

`GameArt` 的分區載入與 `Data.Portals` 都用場景名當 key，沿用同樣的名字那些資料才能原封不動用。所以森林叫 `main.unity` 而不是 `Forest.unity`。

### 3. 資源載入從非同步變同步
Cocos 的 `resources.load` 是非同步的，所以 `GameArt.ts` 有一整套 `pending` / `jobDone()` / `onReady()` 的計數與回呼，還要用 `w8Seq` 擋「換裝的回呼晚到、把新造型蓋回舊的」這種競態。

Unity 的 `Resources.Load` 是**同步**的 —— 那些全部不需要，連同競態一起消失。但 `Ready` / `OnReady()` 這兩個對外 API 特意保留，其他 50 幾個檔的呼叫端一行都不用改。

### 4. 存檔後端從 localStorage 改成 JSON 檔
沒用 `PlayerPrefs`（localStorage 最直接的對應）—— 它在 Windows 上是寫**登錄檔**，16 個 key 塞整包 JSON 進去難備份、玩家壞檔救不回、也接不上 Steam 雲端存檔。

改成 `Application.persistentDataPath/save.json`。對外 API（`GetString`/`SetString`）跟原版一模一樣，16 個模組都不用改。原專案的註解本來就寫著「上 Steam 時只要換掉 backend 三個方法」—— 等於把那一步先做掉了。

### 5. UI 改用 UI Toolkit
原版所有面板都是純程式碼堆節點，每顆按鈕的位置是手算的 offset（`-246 + i * 164`、`leftX + 240`、`panelW/2 - 68`⋯），顏色是散在各處的 `new Color(118, 92, 58, 255)`。

改成 UXML（結構）+ USS（外觀）+ C#（資料繫結），位置交給 flexbox，**沒有任何手算座標**。順帶砍掉背包面板的翻頁機制（`ScrollView` 是內建的）。

### 6. 中文字型必須包進專案
UI Toolkit 的預設字型（Unity 6 是 Inter）**完全沒有中文字**，而且不報錯 —— 畫面就是一片空。

最初用 `Font.CreateDynamicFontFromOSFont` 跟系統借微軟正黑體，但那在 **WebGL 完全不能用**（瀏覽器沒有 OS 字型），而且包 Windows 字型散布有授權問題。

現在用 `Assets/Resources/ui/fonts/NotoSansTC.ttf`（**SIL Open Font License，可合法散布**），OS 字型只留作退路。見 `CjkFont.cs` 與同資料夾的 `LICENSE-NOTE.txt`。

那個 .ttf 是**子集化過的**（11.4 MB → 428 KB）：完整字型放在 Assets 外面的 `tools/fonts/NotoSansTC-full.ttf`（不會進 build），`tools/subset_font.py` 掃過 Assets 底下所有原始碼與版面檔，只留真的出現過的字。

⚠️ **加了新的中文字串就要重跑 `python tools/subset_font.py`**，不然沒收到的字會變成豆腐（而且一樣不報錯）。

⚠️ 來源是**可變字型**，wght 軸的預設值是 **100 ＝ Thin** —— 不處理的話整個遊戲的中文是用髮絲細體在畫。子集化時會先把它定在 `WEIGHT = 400`（Regular），順便甩掉 fvar/gvar。

### 7. 時間系統獨立於 UI
原版是讓時鐘 HUD 順便驅動 `TimeSystem.tick()`。那樣**時鐘 UI 一旦沒生出來，整個遊戲的時間就停掉**（花不長、顧客不來），而且症狀（「花種下去永遠不發芽」）完全指不到原因。

拆成獨立的 `TimeDriver`，由 `PlayerController` 喚起，跟 UI 無關。

### 8. `DailyLog` 用 `[RuntimeInitializeOnLoadMethod]`
原版靠 ES module 的載入副作用註冊跨日結算（`TimeSystem.onNewDay(rollover)`）。C# 的 static 類別是**惰性初始化**的 —— 沒人碰就不會跑，照抄會變成「都沒人賣東西的那幾天不會結算」。

---

## 四、踩過的坑（都不是「翻譯錯誤」，是兩邊約定不同）

| 坑 | 症狀 | 對策 |
|---|---|---|
| **rect 原點上下相反** | 走圖有在動，但動錯（朝下變朝上） | Cocos rect 的 y 從左上算、Unity 從左下算。統一收在 `SheetSlicer.Cell()`，呼叫端沿用原本的列編號 |
| **場景 `contentSize` ≠ PNG 尺寸** | 鍋爐大了一倍又下沉 | 那代表物件有**隱含縮放**存在場景檔裡（224×343 的圖被設成 123×189）。只搬座標會錯 |
| **錨點約定不同** | 村民/家具的前後遮擋排錯 | Cocos 用錨點 `(0.5,0)`＝腳底；Unity 的 Sprite 樞紐在正中心。村民/家具/糖果鎮讓 `SpriteRenderer` 掛在子物件上往上推半身高；**女巫沒有那個子物件**（圖直接掛在 `Player` 上），改成切圖時就把樞紐放到格子底邊（`SheetSlicer.Foot`）—— 兩種做法的結果一樣：`position` ＝ 落腳點 |
| **深色字印在深色底** | 時鐘的日期「沒顯示」（其實一直在）| 盤面格子是深藍近黑，原版用米金色 `(244,228,176)`。任務簿的羊皮紙則相反，要用深墨色 |
| **類別撞名** | `foreach cannot operate on a method group` —— 完全看不出是撞名 | `Core.Outfits`（狀態）撞 `Data.Outfits`（資料表）。資料表改名 `OutfitCatalog`，同 `Decor` / `DecorCatalog` 的命名原則 |
| **`Destroy()` 是延遲的** | 拖曳時提示格錯亂 | 延到該幀結束才真的刪，「每幀清空再重畫」會讓新舊同時出現。改成**重複使用**物件。**這個坑踩了兩次**（佔地預覽、格線）|
| **兩個 E 感應圈重疊** | 按 E 隨機觸發其中一個 | Unity 不保證元件的 `Update` 順序。商店改成做在對話的選項裡，一顆 E 一件事 |
| **旋轉方向相反** | 時鐘會倒著走 | Cocos 的 `angle` 正向逆時針，UI Toolkit 的 `rotate` 正向順時針 |
| **`AssetDatabase` 路徑區分大小寫** | 建出來的資產跑到別的地方 | Windows 檔名不分大小寫，`Resources/UI` 會靜默掉進既有的 `Resources/ui`。全專案統一小寫 `ui/` |
| **場景要登記 Build Settings** | `LoadScene` 執行期直接丟錯 | Cocos 只要檔案在就能切。而且剛 `SaveScene` 的場景還沒進 `AssetDatabase`，馬上登記會**靜默失敗** —— 要先 `Refresh()` |
| **初始化失敗卻設了旗標** | `Update()` 每幀狂丟 NullReference | `built = true` 一定要放在建構**成功之後**，失敗時保持 false 下次才會重試 |
| **房間不是矩形** | 貨架貼右後牆時圖穿出牆外，卻沒被擋下來 | 原本拿**底圖的矩形**（±480/±320）當「有沒有穿牆」的邊界。房間其實是菱形地板＋兩面斜牆，牆外到圖邊還有一大塊深色的「房間外」。改成用真正的輪廓多邊形 `ShopRoom.Silhouette()` 判 —— 輪廓是凸的，檢查圖的四個角就等於檢查整張圖 |
| **「在輪廓內」不等於「站在地板上」** | 架子整個埋進右邊的牆裡 | 基準角（`T`）會把圖搬到佔地的另一個角，配錯翻面狀態時整張圖平移到牆面上 —— 但四個角都還在「地板＋牆」的輪廓內，只驗輪廓擋不掉。真正的判準是**圖的底緣兩端要踩在地板菱形上**（`ShopRoom.RectOnFloor`）；往上長到牆上才是可以的 |
| **圖的透明邊不是對稱的** | 用整張 PNG 的矩形判，左邊誤擋、右邊漏擋 | `shelf_box` 圖寬 176，實際只畫在 x=62..172。改用 `Data.FurnitureBounds`（離線量出來的不透明範圍，見第六節）|
| **規則改嚴，舊存檔不會自己變好** | 修好之後進店，那個架子還是埋在牆裡 | 能不能放是**放的時候**檢查的。加了 `RoomLayout.RepairPlacements()`，進店時掃一次：先原地換基準角／翻面，再找最近的合法格，都不行才原樣留著（不刪玩家的東西）|
| **場景裡沒有 AudioListener** | 音效全部呼叫了、卻一點聲音都沒有（Console 只有一行容易漏看的警告）| Cocos 不需要 Listener；我們的場景是產生器 `AddComponent<Camera>()` 建的，不會像 Unity 選單那樣順便帶一個。由 `Sfx` 的常駐物件自己掛，場景裡若之後有了別的 Listener 會自動讓開 |
| **大圖被 Max Size 靜默縮小** | 城鎮/糖果鎮的地面糊糊的、像素格子大小不一 | 3200×2048 的整張地面圖，`.meta` 的 Max Size 是 2048 —— Unity 匯入時先縮到 2048 寬再用 Point 拉回 3200，**不會有任何警告**。改成烤半解析度（1600 寬）的圖，執行期用 PPU 0.5 貼回去（`BakedGround`）。之後新增超過 2048 的圖都要注意 |
| **執行期把 Tiled 切成 Simple** | 森林地面每個美術像素變成約 22×14 的大方塊（放大 11×7 倍），樹與女巫正常 | 森林的 Ground 是 Tiled（256 的磚、size 2816×1792）。`BakedGround` 曾經先 `drawMode = Simple` 再換上 2816 的整張圖 —— 推測 Unity 切模式時把 size 換算進了 `localScale`（2816/256＝11、1792/256＝7，倍數吻合），新圖又被放大一次。改成**不切 drawMode**：Tiled 就把 `size` 設成新圖大小（FullRect，剛好鋪一格），`localScale` 一律還原，換完再驗 `bounds` 的中心與大小，不對就整組還原 |
| **擋下來卻不說為什麼** | 拖不過去，玩家以為卡住了 | 規則收進 `RoomLayout.Check()`，回傳**是哪一條擋的**；擋住的格子標紅（sortingOrder 要在家具之上，不然被家具蓋住看不到），原因即時寫在托盤那行提示 |

---

## 五、程式結構

```
Assets/Scripts/
├── Data/      純資料表，沒有 Unity 相依（除了 Vector2）
│   ├── Items / Prices / Recipes / Seasons / Garden / Decor
│   ├── Outfits(OutfitCatalog) / Villagers / Furniture / Candy / Quests
│   ├── ShopRoom          等距格盤的幾何（唯一的自訂座標系）
│   ├── ForestLayout / TownLayout / TownRoads   ← 自動產生，見第六節
│   └── ArtFootprints     物件的落地範圍＋碰撞常數（tools/gen_footprints.py 產生，不要手改）
│
├── Core/      遊戲邏輯
│   ├── GameArt            美術載入（分區、切走圖）
│   ├── SheetSlicer        走圖切格（含 rect 上下翻轉的修正）
│   ├── SaveManager        存檔中樞（版本 migration）
│   ├── TimeSystem         遊戲時間 ＋ TimeDriver
│   ├── PlayerController   移動、換場、各場景子系統的喚起點
│   ├── Obstacles          戶外地圖的玩家碰撞（掃場景建障礙清單、分軸滑動、防卡死、編輯器裡的可達性自我檢查）
│   ├── ObstacleDebugView  F3 畫出落地範圍與玩家碰撞圓
│   ├── CharacterAnimator  女巫八方向動畫
│   ├── VillagerAnim       村民/顧客動畫
│   ├── Inventory / Storage / Wallet / Upgrades / ShopStock
│   ├── QuestLog / Reputation / DailyLog / Friendship
│   ├── GatherTree         採集（含搖晃、星星、飄字）
│   ├── ShopRoomView       店裡的渲染
│   ├── ShopRoomEditor     店裡的佈置模式
│   ├── RoomLayout / DecorCatalog   家具與裝飾的擺放狀態
│   ├── CustomerManager / SaleCounter
│   ├── GardenRoom / GardenPlot / Garden
│   ├── BrewRoom / BrewCauldron / PotionRecipes / RoomFixtures
│   ├── CandyTown / TownFolk / Doorways / SceneDoor / TalkNpc
│   ├── DayNightTint / LampGlow / PortalGlow / CameraFollow / FloatAway
│   ├── Sfx                音效（常駐、自帶 AudioListener；音檔在 Resources/audio/）＋音量／靜音設定
│   ├── Bgm                背景音樂（常駐、依場景＋日夜選曲、交叉淡變；音檔在 Resources/audio/bgm/）
│   └── BakedGround        戶外地面換成烤好的半解析度圖（Resources/art/ground/，PPU 0.5）
│
├── UI/        全部走 UI Toolkit
│   ├── CjkFont            中文字型（見第三節第 6 點）
│   ├── InventoryHud / ClockHud / CornerHud / Toast / SceneFade
│   ├── BagPanel / ShopManagePanel / BrewPanel / SeedPicker
│   ├── TownShopPanels     雜貨鋪 / 花店 / 糖果鎮商行
│   ├── QuestPanel / PlayerInfoPanel / WardrobePanel
│   ├── SettingsPanel      設定（O）：音樂／音效音量、靜音
│   ├── Dialogue / SleepOverlay / DaySummaryPanel / ShopRoomTray
│   ├── UIAnim             面板開關動效 ＋ HUD 彈一下（樣式在 Resources/ui/AnimStyle.uss）
│   └── (UXML/USS 在 Assets/Resources/ui/)
│
└── Editor/    只在編輯器裡跑
    ├── PixelArtImporter   匯入時自動套像素風設定
    ├── BgmImporter        背景音樂匯入時壓成 Vorbis（只管 Resources/audio/bgm/）
    ├── *SceneBuilder      六個場景的產生器
    ├── SceneBuildUtil     共用工具 ＋ 重新登記所有場景
    ├── CreateUISettings / Setup2DProject
    ├── DevTools           測試用
    └── WebBuilder         網頁版建置
```

專案根目錄的 `tools/` 放離線工具：`typecheck.sh`（不開 Unity 編一次）、`subset_font.py`（中文字型子集化）、
`gen_furniture_bounds.py`（家具不透明範圍）、`gen_footprints.py`（戶外物件的落地範圍＝碰撞規則的唯一來源）、
`check_walkable.py`（碰撞的離線可達性檢查＋預覽）、`gen_sfx.py`（合成 8-bit 音效）、`gen_bgm.py`（合成 8-bit 背景音樂）、
`bake_ground.py` ＋ `ground/`（戶外地面烘焙器；原圖備份在 `ground/orig/`，說明見 `ground/README.md`）。

**各場景的子系統由 `PlayerController.Awake()` 依場景名喚起** —— 沿用原專案的做法，好處是加東西不用改場景檔。

---

## 六、自動產生的資料（改了原專案要重跑）

這三個檔是**從 Cocos 的場景/資料檔轉出來的**，不要手改：

| 檔案 | 來源 | 內容 |
|---|---|---|
| `Data/ForestLayout.cs` | `main.scene` | 84 個採集點的座標、產出、冷卻、稀有掉落 |
| `Data/TownLayout.cs` | `town.scene` | 71 個擺設的座標（含父層位移累加）|
| `Data/TownRoads.cs` | `data/townRoads.ts` | 110 個路點 ＋ 傳送點 |
| `Data/Quests.cs` | `data/quests.ts` | 9 個任務與全部台詞 |
| `Data/FurnitureBounds.cs` | `Assets/Resources/furniture/*.png` | 每張家具圖「真正畫到東西」的範圍。產生器在**本專案**：`tools/gen_furniture_bounds.py`，換家具美術要重跑 |
| `Data/ArtFootprints.cs` | 戶外物件圖（從 `ForestLayout`／`TownLayout`／`Candy` 收集）| 每張圖的落地範圍與碰撞形狀、玩家半徑、邊緣內縮。產生器在**本專案**：`tools/gen_footprints.py`，換物件美術或調碰撞要重跑 |

轉換的做法：用 Python 解析 Cocos 的場景 JSON，用 `.meta` 把 Sprite 的 uuid 反查回圖檔名，再輸出 C#。原專案改了內容就重跑一次。

⚠️ 抽座標時要注意：**節點可能掛在父層底下**（城鎮的橋掛在 `Roads` 下），要把父層位移累加進去；**`contentSize` 跟 PNG 尺寸不一樣時代表有隱含縮放**，那個也要一起搬。

---

## 七、跟原版刻意不同的地方

| 項目 | 原版 | 這裡 | 理由 |
|---|---|---|---|
| 背包面板 | 一頁 7 列 + 翻頁鈕 | `ScrollView` 捲動 | Cocos 沒有現成的捲動容器才要翻頁 |
| 貨架佔地 | 全部 1×2 | 四層高架 1×2、其餘 1×3 | 依美術實際圖寬（164px 以上擺 2 格會凸出去）|
| 貨架前方 | 沒有限制 | 留一排走道，不能擺東西（藍格）| 玩家要走得過去 |
| 穿牆判定 | 沒有 | 圖不能凸出房間輪廓 | 貨架的圖比牆裙高、也比一格寬，貼到牆角會穿出去 |
| 家具基準點 | 固定前角 | 前角 / 左上 / 右上 可切換 | 靠牆的貨架要貼得住牆 |
| `DecorRoom.ts` | 636 行一個檔 | 拆成 `ShopRoomView` + `ShopRoomEditor` | 渲染是常駐的、編輯只在按 R 時存在 |
| 魔法彈 | 拖 Prefab | 程式生成的發光小球 | 原 prefab 不在搬過來的資產裡 |
| 每日結算 | 沒有 | 睡醒時在黑幕上顯示帳單（`DaySummaryPanel`）| `DailyLog` 一直有記帳，卻沒有任何地方看得到 |
| 不在店裡時 | 完全不做生意 | 照常有客人買（`AwayShop`）| 顧客只由 `CustomerManager` 產生，而它是進 shop 場景才生出來的 —— 玩家一去採集就等於關門 |

---

## 八、還沒實測過的常數

以下是照公式或比例推的，**沒有實機驗證**，畫面不對就先調這幾個：

| 位置 | 常數 | 說明 |
|---|---|---|
| `GatherTree.CharSize` / `TextFontSize` | 4.5 / 44 | `TextMesh` 的世界大小 ≈ `fontSize × characterSize ÷ 10`，這個係數是憑印象寫的 |
| `PortalGlow.DoorRx/EdgeRx/PeakAlpha` | 76 / 108 / 0.85 | 比原版放大加亮過，覺得太搶眼就調小 |
| `ClockHud` 的 `HandSpec` | AnchorY / Reach | 指針樞軸與長度的比例，抄自原版但沒實測 |
| `Furniture` 的貨架深度 | 2 / 3 格 | 依圖寬推的，換美術要跟著調 |
| `ShopRoom.ArtInsideRoom` 的 margin | 4px | 「貨架不能穿牆」的邊界寬容值 |
| `ShadowLayer.RxRatio/RyRatio` | 0.36 / 0.125 | 影子半徑 ÷ 角色寬（沿用原版）。量的是**整格**寬度，女巫實際只佔 49 格裡的 43 —— 覺得影子太寬就調 RxRatio |
| `CharacterAnimator.FootPad` | 3px | 女巫圖集裡鞋底到格子底緣的透明邊，量 `witch8/base.png` 得到 |

### 女巫的樞紐（做影子時發現、當天修掉）

發現的問題：女巫的 `SpriteRenderer` 直接掛在 `Player` 上、樞紐在正中心，可是村民/家具/
糖果鎮全走「圖掛子物件往上推半身高」＝腳底錨點，而搬過來的座標（出生點、門、採集點、
店裡的菱形夾取）都是照 Cocos 的腳底錨點訂的 —— 等於女巫整個人比原版**往下畫了約 48px**。

修法（見第九節）：`SheetSlicer` 加 pivot 參數，`GameArt` 切女巫那幾格時改用 `SheetSlicer.Foot`
（格子底邊）。場景檔與所有呼叫端都不用動。

## 九、進度與待辦

### 做到哪了

**2026-09-05（移植收尾）** —— 程式面的移植 TODO 清零，六張場景都會跑。

**2026-09-06**
- **每日結算畫面**（`UI/DaySummaryPanel.cs`）。資料本來就記在 `DailyLog` 裡卻沒地方看得到。
  接在睡覺過場「時間推進之後、黑幕淡出之前」，玩家按鍵才繼續。
  想直接看效果：`Witch Shop → 測試用 → 塞一天的營業紀錄`，再進遊戲睡一覺。
- **店內佈置的擺放規則**（`RoomLayout.Check` / `ShopRoom` / `ShopRoomEditor`）。**已實機確認**：
  - 規則收成一支 `Check()`，回傳**是哪一條擋的**；拖曳、翻面、換基準點、從托盤放進來都走它
    （以前四個入口各檢查各的：`F` 翻面漏了走道、門口紅格用拖的可以拖進去）
  - 擋住的格子標紅色、原因即時寫在托盤那行提示、鬆手再 Toast 一次
  - 穿牆改成兩條判準（見第四節），並用 `RepairPlacements()` 修掉舊存檔裡已經卡在牆裡的家具
- **腳下影子**（`Core/ShadowLayer.cs`）。女巫、店裡的顧客、街上的村民、糖果鎮的小動物
  腳下各一片扁橢圓，角色才像「站」在地上而不是「貼」在背景上。
  - 排序固定 `-8500`：地面（-10000）之上、所有角色與道具（YSort 的 -y，量級幾千）之下，
    也比傳送點光圈（-9000）高一點，站在傳送點上影子才看得見。夜晚不用另外處理 ——
    `DayNightTint` 的色板在 20000，會一起壓暗。
  - 原版是一個 `Graphics` 每幀重畫全部橢圓，而且**不能**掛成角色的子節點（Cocos 先父後子，
    影子會蓋在角色身上）。Unity 的繪製順序看 `sortingOrder`、跟階層無關，那套排序技巧
    整個不需要；橢圓改成程式生成的一張柔邊圓貼圖，每幀只更新位置。
  - 影子仍然**不掛成角色的子物件**：角色的 transform 帶著縮放、面向又靠 `localScale.x`
    正負翻面，掛進去要一路把縮放除回來。獨立一層便宜得多。
  - 女巫要多傳一個落腳點偏移（`CharacterAnimator.FootPad`）—— 鞋底到格子底邊還有 3px 透明邊。
- **女巫的樞紐改成腳底**（`SheetSlicer.Foot` ＋ `GameArt`）。做影子時發現她比原版往下畫了
  約 48px，原因見第八節。
  - `SheetSlicer.Cell/Row/Whole` 加了選用的 `pivot` 參數（預設仍是正中心，其他呼叫端不受影響），
    `GameArt.LoadWitch8` 與**所有會貼到 `Player` 身上的舊手繪動作圖**
    （`witch/cast`、`gather*`、`water*`、`pick*`）一律改用 `Foot`。
    漏掉舊圖的話，圖集載不到而墊底時女巫會整個往上跳半身高。
  - `witch/sleeping` 例外維持正中心 —— 那是 `SleepOverlay` 的立繪，不掛在 `Player` 上。
  - 順帶修好的：店裡的 `ShopRoom.ClampToFloor` 夾的是 `position`，以前夾的是她的腰，
    腳其實可以踩出菱形地板外。
  - 影響到的畫面：鏡頭是對準 `position` 的，所以現在女巫會落在畫面中央**偏上**半身
    —— 這跟 Cocos 版一致（原版鏡頭也是跟腳底），覺得不順眼再幫 `CameraFollow` 加 Y 偏移。

- **更新公告板**（`UI/UpdatePanel.cs` ＋ `Data/UpdateNotes.cs`）。開遊戲時從上方滑下來，
  一次執行只跳一次。公告內容獨立成 `UpdateNotes`，改公告不用碰版面。
  - 底圖 `ui/update-frame` 上的 OK 是**畫上去的**，所以只在那個位置疊一個透明可點區。
  - Cocos 版為了底圖有一整套非同步流程（先畫素框＋「載入中…」、單獨 load 這一張、
    回呼裡確認元件還活著）—— Unity 的 `Resources.Load` 是同步的，那整套直接消失。
  - 版面從「照底圖比例硬算子節點座標」改成 **USS 的百分比絕對定位**（`left: 9.9%` …），
    滑入/滑出從 `tween` 改成 USS transition（`ease-out-back` / `ease-in-back`）。
- **中文字型子集化**：11.4 MB → **428 KB**（見第三節第 6 點）。順帶發現兩件事：
  - 來源字型是**可變字型且預設 Thin** —— 中文一直是細體在畫，現在定在 Regular。
  - `✕`（U+2715）與 `✔`（U+2714）**不在 Noto Sans TC 裡**，七個面板的關閉鈕與任務清單
    的完成標記其實一直是缺字。改用字型裡有的 `×`（U+00D7）與 `✓`（U+2713）。

- **不在店裡時店照常做生意**（`Core/AwayShop.cs`）。原本顧客只由 `CustomerManager` 產生，
  而它是進 shop 場景才生出來的 —— 玩家一去採集/逛街/煉藥，架上的東西一件也賣不掉。
  - 用**跟在場時完全一樣的規則**：招牌等級 × 名聲 × 節日的來客間隔、08:00–20:00 的營業時間、
    架上有貨才成交。差別只是沒有走進來的那位村民與對話泡。
  - 成交統一走 `CustomerManager.CompleteSale()`（從原本 inline 的那段抽出來）——
    收錢、記今日營收、加名聲、記任務進度四件事兩邊一致，不會出現
    「離店賣掉的不算任務進度」這種落差。
  - 回到店裡時用一則 Toast 報告賣了幾件、賺了多少；帳本身早就進 `DailyLog`，
    所以每日結算也看得到。
  - 刻意**不做離線收益**：這個遊戲的時間只在遊玩時前進（`TimeDriver` 每幀推 `TimeSystem`），
    關掉遊戲時間就停 —— 「關著也在賣」會跟時鐘、花的成長、日夜全部對不起來。
  - 平衡旋鈕：`AwayShop.AwayRate`，**現在是 0.7**（沒人顧店時來客速度慢三成）。
    全速（1.0）的話待在店裡就完全沒好處，玩家最佳解會變成一直在外面跑。

- **村民縮小**（`VillagerAnim.Scale` 1.28 → 1.0）。原本的 1.28 是「舊值 0.8 跟著女巫一起
  ×1.6」推出來的，但**等比放大只有在兩邊原圖比例一樣時才成立** —— 女巫的格子 66px、
  村民的格子 100px。量「真的畫到東西」的高度：女巫可見 58px × 1.6 ＝ 畫面上 93px；
  村民十一張平均可見 98px × 1.28 ＝ 125px，高了 34%，站在一起大人像巨人。
  改成 ×1.0 ＝ 98px，比女巫高約 5%，維持「大人比小女巫高一點點」的原意。
  （試過 0.85 ＝ 83px，太小、不像大人。）這個常數同時是店裡顧客的預設值。
- **公告板的內文會溢出**（實機才看到）。六條公告因為中文自動換行變成十行，撐出米色內裡、
  壓到木框上，最後一條被切掉 —— 字級是照「幾條」算的，沒有考慮換行。
  UI Toolkit 沒有 Cocos 的 `Label.Overflow.SHRINK`，所以自己做一個收斂迴圈
  （太高就把字級縮 8%，縮完 layout 會再觸發一次回呼，直到塞得下或碰到下限；
  `fitPasses` 擋住萬一收斂不了的無窮迴圈），另外 `.update-inner` 補 `overflow: hidden` 當保險。

**上線（2026-09-06）** —— Unity 版**取代了 GitHub 上的 Cocos 版**。

- 專案進了 git（`git init`，branch `main`），remote 接上原本那個 repo
  <https://github.com/Crashoxo/witchyHouse>，force push 換掉 `main`。
  **動 main 之前先把 Cocos 版的完整歷史推成 `cocos-legacy` 分支**，一個 commit 都沒少；
  本機 `D:\Crash\witch-shop` 也原封不動留著當對照。
  ⚠️ 那個資料夾的 `origin` 還指著同一個 repo，在那邊 `git push -f` 會把網站打回 Cocos 版。
- 加了 `Witch Shop → 建置 → 網頁版（給 GitHub Pages）`（`Editor/WebBuilder.cs`）：
  直接建到 `docs/`、順便寫 `.nojekyll`。壓縮設定跟本機測試那個目標**刻意不同** ——
  Pages 是純靜態空間、**不能設 `Content-Encoding`**，一般的 Brotli 建置放上去會直接
  載不起來，所以開 `decompressionFallback`（改由 Unity 產的 JS 在瀏覽器端自己解壓）。
  而且不壓的 `.data` 動輒上百 MB，會撞到 **GitHub 單檔 100 MB 的硬上限**。
  實際產出 27 MB、最大單檔 22 MB。
- ⚠️ **`.gitignore` 的忽略規則要用 `/` 釘在根目錄**（`/[Bb]uild/`）—— 沒有斜線的 pattern
  會比對**任何一層**，而 WebGL 輸出裡就有 `docs/Build/`（`.wasm`/`.data` 全在裡面）。
  照原本的寫法推上去，網站只剩一個空殼 `index.html`，**而且 git 完全不會提醒你**。
- README 從開發筆記改寫成 repo 首頁（線上試玩連結、操作表、內容介紹在前，開發設定在後）。
- 已用瀏覽器實際開過確認：載入 → 進店裡的場景 → HUD／時鐘／背包欄都在、
  中文全部顯示正常（字型子集化沒掉字）、Console 無錯誤。

**2026-11-19（音效）** —— 遊戲原本**完全沒有聲音**（沒有 AudioSource、沒有音檔）。

- **音效系統**（`Core/Sfx.cs`）。呼叫端一行 `Sfx.Play("coin")`，不用在場景掛任何東西：
  `[RuntimeInitializeOnLoadMethod]` 生一個 `DontDestroyOnLoad` 的物件，上面一池 10 個 AudioSource，
  AudioClip 照檔名 `Resources.Load("audio/…")` 載入後快取。
  - **找不到檔就靜默略過**（同名只警告一次），任何例外都吞在裡面 —— 音效壞掉不能讓遊戲跟著壞。
  - **最短重播間隔**：同一個音效在間隔內（預設 0.05 秒）再叫會被丟掉。一次搬一整排、同一幀成交好幾筆，
    才不會疊成一聲爆音。
  - **變體輪播**：`Play("step")` 在 `step-1..3` 之間隨機挑、不連續重複；腳步、對話 blip 這類
    還會加一點隨機 pitch，聽起來不像機關槍。
  - **總音量／靜音**存進存檔（key `witch.audio`，**刻意不列進 `SaveKeys`**：那是偏好不是進度，
    開新遊戲不該把音量重設）。`Sfx.Volume` / `Sfx.Muted` 是給之後設定介面接的公開屬性。
    **`M` 鍵切換靜音**（確認過沒有別的功能佔用）並冒 Toast。
  - ⚠️ **場景裡根本沒有 AudioListener**（見第四節）—— 由 Sfx 的物件自己掛；換場時若發現場景
    已經有別的 Listener 就把自己的關掉。
  - 不受 `Time.timeScale` 影響（AudioSource 本來就不吃，重播間隔用 `unscaledTime` 量）。
    專案目前也沒有任何地方動 `timeScale`。
- **UI 按鈕的 click 音是共用的**：各面板 Build 時呼叫一次 `Sfx.BindClicks(root)`，在根節點收冒泡上來的
  `ClickEvent`，不用逐顆按鈕貼。click 會**延到下一幀**才決定要不要響 —— 同一幀已經有更具體的音效
  （ui-close／buy／deny／ui-tab…）就不再疊一聲。
- **面板開關音**一律加在各面板 `Open()`/`Close()`（BagPanel 是 `Show()`）裡，**一行、註解寫
  「音效：面板打開／關閉」**，之後改開關動畫的人很好找。
- **掛點的原則：掛在事件真正發生的那一處**，不掛在會被讀檔／批次呼叫到的底層函式。
  例如收錢掛在 `CustomerManager` 顧客成交的那個分支，**不掛在 `CompleteSale()`** ——
  `AwayShop` 離店成交也走它，玩家不在店裡時每一筆都叮會很吵；回店時那則彙總 Toast 響一次 coin。
  `Inventory.Add` 也沒掛（讀檔、搬倉庫、領獎都會呼叫）。
- **腳步**：`PlayerController.LateUpdate` 量這一幀的實際位移，每走 64px 響一步 —— 鍵盤、點地面自動走、
  衝刺都一樣（衝刺時同樣步幅走得快，自然變密）；站著或推著牆走不動就不響；一幀跳超過 40px 當作瞬移不算。
- **佔位音檔**：`tools/gen_sfx.py` 用 Python 標準函式庫（不靠 numpy）做 sfxr 風格的合成 ——
  方波／三角波／雜訊、頻率滑動、ADSR、琶音，方波一律過一階低通磨圓（要 cozy、不要刺耳），
  峰值統一正規化留 headroom、頭尾 2ms/8ms 淡入淡出。24 個檔、16-bit mono 22050 Hz、共約 307 KB。
  亂數種子固定（每個音效以名字當種子），重跑逐 byte 一致。
- **換成正式音檔**：把新的音檔用**同樣的檔名**蓋掉 `Assets/Resources/audio/` 裡的 .wav 就好，程式不用改
  （副檔名可以換成 .ogg —— `Resources.Load` 不看副檔名，但同名的舊 .wav 要刪掉，不然會載到哪個不一定）。
  蓋掉之後**就別再跑 `gen_sfx.py`**，它會把同名檔覆蓋回去；只想重產其中幾個就把其他名字從腳本的 `SOUNDS` 表拿掉。
  音量要調：個別的在呼叫端第二個參數，整體的在 `gen_sfx.py` 的 `PEAK` 與各音效的 gain。
- `Packages/manifest.json` 補上 `com.unity.modules.audio`。原本其實是靠 `com.unity.ugui` **間接**帶進來的
  （`packages-lock.json` 裡 depth 1），所以以前沒出事 —— 但直接用到的模組要自己列，不要賭別人的相依。
  ⚠️ `tools/typecheck.sh` 引用全部 `UnityEngine*.dll`，**抓不到**少了模組這種問題。

| 音效 | 掛在哪 |
|---|---|
| `step`（1..3）| `PlayerController.LateUpdate` 依位移 |
| `cast` / `spell-hit` | `PlayerController.Cast` / `SpellProjectile` 壽命到（**在畫面內**才響；目前沒有命中判定）|
| `gather` / `pickup` | `GatherTree.PlayFx`（＋花圃清枯枝）/ `GatherTree.PopItem`（材料、稀有物、種子冒出來的那一刻）、佈置模式收回托盤 |
| `water` / `plant` / `harvest` | `GardenRoom.Water` / `PlantSeed` / `Act` 收成分支 |
| `coin` | 店裡顧客成交、`AwayShop.ReportOnReturn`、雜貨鋪收購 |
| `buy` / `upgrade` / `deny` | 花店、商行買東西 / 經營面板升級 / 錢不夠、背包滿、放不下、規則擋住、沒種子… |
| `ui-open` / `ui-close` / `ui-tab` / `ui-click` | 各面板 `Open()`/`Close()` / 分頁鈕 / `Sfx.BindClicks` |
| `talk` | `Dialogue.ShowLine`（開對話與換句都走它）|
| `door` | `SceneFade.Go`（所有換場都經過這裡）|
| `brew` / `quest-done` / `new-day` | `BrewCauldron` 熬好 / `TalkNpc` 回報成功 / `SleepOverlay` 醒來那一刻 |
| `place` | 佈置模式：從托盤放進房間、拖曳換了位置、轉向／換基準點成功 |

**2026-11-19（UI 動效）** —— 除了公告板，所有面板原本都是 `display` 一切**瞬間出現／消失**。

- **共用 helper `UI/UIAnim.cs`** ＋ 樣式 `Resources/ui/AnimStyle.uss`（helper 自己掛到面板的根上 ——
  各面板原本載的是 BagPanelStyle／ShopManageStyle／HudExtraStyle 三張不同的表，靠呼叫端記得 Add 一定會漏）。
  各面板只改了三處：Build 裡建一個 `anim`、`Open()` 的 `display = Flex` 換成 `anim.Show()`、
  `Close()` 的 `display = None` 換成 `anim.Hide()`；音效那一行沒動（**按下的那一刻**就響，不等動畫）。

  | 動效 | 面板 |
  |---|---|
  | `UIAnim.Pop`：淡入＋0.94→1 放大 0.15s ease-out，暗幕只淡入；關閉 0.10s 淡出 | 背包、玩家資訊、衣櫃、調配藥水、經營商店、城鎮商店（共用基底）、種子選單、每日結算（只動帳單，黑幕是 SleepOverlay 的）|
  | `UIAnim.SlideRight`：從右邊 48px 滑進來＋淡入 | 任務簿（貼右邊的捲軸，縮放看起來像從半空中冒出來，不對）|
  | `UIAnim.SlideUp`：從下面 26px 滑上來＋淡入 | 對話框、佈置模式托盤（換句不重播 —— 只有 Open/Close 會碰動畫）|
  | `UIAnim.Bump`：1→1.18→1，約 0.2s | 下排背包 HUD 某格數量**變多**時；左上角金幣變動時（多了閃綠、少了閃紅）|

  SleepOverlay、SceneFade、UpdatePanel 原本就有自己的過場，沒動。
  Toast 原本就有淡入淡出，只是線性的：改成 ease-out 滑上來、ease-in 飄走，位移從每幀改 `top`
  換成 `translate`（不觸發重新排版）。
- ⚠️ **陷阱 1：「開著沒」不能再看 `root.style.display`。** 關閉動畫要等淡出跑完才 display:none，
  這段期間它還是 Flex —— 而 `IsOpen`、`OnDestroy` 裡解除 `ModalOpen`、`Update` 裡的 Esc、
  `SleepOverlay` 等帳單關掉⋯⋯原本全是看 display。全部改看 `anim.IsOpen`（`Show()`/`Hide()` 當下就翻過去），
  `grep DisplayStyle` 逐一查過，剩下的只有子元素的顯示切換與 Build 裡的初始隱藏。
  所以按 Esc 的那一幀 `ModalOpen` 就解除、人馬上能走、同一顆鍵馬上能再開；淡出只是視覺殘影。
- ⚠️ **陷阱 2：剛從 display:none 變 flex 的那一輪加 class 不會播 transition**（沒有「前一個樣式」可以比）。
  open class 用**巢狀兩層 `schedule.Execute`** 才加：排程回呼裡再排的東西一定落到下一輪面板更新，
  中間保證有一次樣式解析把「關閉狀態」解析過。UpdatePanel 的 `StartingIn(16)` 是同一招，但吃幀率。
- ⚠️ **陷阱 3：快速連按（開→關→開）。** 延後的動作（加 class、收 display）都記著，`Show`/`Hide` 一進來先
  `Pause()` 掉，回呼裡再比對流水號 —— 不會「重開之後被上一次的延後隱藏關掉」。
  同一幀關了又開（對話選項：先關這段、馬上開下一段）直接把 class 掛回去，不會閃一下重播進場。
- ⚠️ **陷阱 4：面板可能在換場景時被 Destroy（延遲的）。** 排程回呼只碰 VisualElement、不碰 MonoBehaviour；
  UIDocument 一停用根就離開面板，排程本來就不跑了。
- 關閉中的面板**不收點擊**：根上掛 trickle-down 攔截 `PointerDown`／`Click`。沒用 `SetEnabled(false)` ——
  那會套上 `.btn:disabled`（半透明），淡出時看得到按鈕閃一下。世界的點擊（點地走路）本來就不看 UI，不受影響。
- HUD 彈一下**只在數量增加時**：`InventoryHud` 記著上次畫的每種數量，第一次畫（開場／讀檔）只記不彈；
  HUD 跨場景常駐，換場不會重建所以也不會誤彈。金幣同理（`lastGold` 還是初值時不跳）。
  ⚠️ 被 Bump 的元素上**別的 class 不要再寫 `transition-property`** —— 同一個屬性只有一條規則勝出，
  會把 scale 動畫蓋掉；要變色就把顏色寫在帶進去的 class 裡（`.uia-bump` 已經會 transition color）。
- 時間全走 USS transition 與 `schedule`（毫秒、真實時間），不受 `Time.timeScale` 影響；沒有執行緒。
- **順便修掉「同一顆鍵開了又關」**（上一位回報、讀程式確認是真的）：任務簿（`Q`）與玩家資訊（`Tab`/`I`）
  「開」寫在 `PlayerController.Update`、「關」寫在面板自己的 `Update`，Unity 不保證誰先跑 ——
  玩家先跑：開的那一幀面板又讀到同一下按鍵 → 開了立刻關；面板先跑：關掉並解除 `ModalOpen` 後，
  玩家同一幀又讀到 → 關了立刻重開。兩個方向都擋：面板 `Update` 跳過 `anim.OpenedThisFrame`，
  `Open()` 擋掉 `anim.ClosedThisFrame`。
  **對話框是同一類**：最後一句按 `E` 關掉，同一幀 `TalkNpc` 若排在後面會用同一下 `E` 再開一次 ——
  `TalkNpc` 加看 `Dialogue.ClosedThisFrame`（開的方向本來就有 `openedFrame` 擋著）。
  背包（`B` 開、只有 `Esc` 關）、其他只吃 `Esc` 關的面板沒有這個問題。

**2026-11-19（戶外地面重烤）** —— 森林／城鎮／糖果鎮的地面原本很醜：

- **為什麼**：森林是一張 256×256 的**模糊雜訊磚**平鋪，跟像素風的物件對不上、重複紋路明顯；
  城鎮與糖果鎮是 3200×2048 的整張圖，路是方塊直接拼（直角鋸齒、草與路沒有過渡、河是一條直藍帶），
  而且 **`.meta` 的 Max Size 是 2048** —— 匯入時被縮到 2048 再用 Point 拉回 3200，格子糊掉、大小不一
  （第四節坑表）。
- **做法**：離線烘焙器 `tools/bake_ground.py`（Pillow＋numpy，固定種子）只用現有素材的色盤程式作畫，
  路與河的位置從原圖抽出來（只把直角修圓，`TownRoads` 的村民路點都還在路內）。輸出**半解析度**
  `Resources/art/ground/{forest,town,candy}.png`（1 美術像素＝2 世界像素，最大 1600 寬，原尺寸匯入）；
  `Core/BakedGround` 用 `[RuntimeInitializeOnLoadMethod]` 掛 `sceneLoaded`，場景一載入就把 `Ground`
  的 sprite 換成它（PPU 0.5，**drawMode 維持原樣**：森林的 Tiled 把 size 設成新圖大小、城鎮/糖果鎮的
  Simple 只換 sprite）。**世界大小不變**（換之前比對 `bounds`、換之後再驗中心與大小，不對就整組還原），
  可走範圍、攝影機邊界、邊界傳送點都不受影響。⚠️ 第一版在這裡把森林的 Tiled 切成 Simple，地面被放大
  11×7 倍（第四節坑表「執行期把 Tiled 切成 Simple」）；那個狀態下 `PortalGlow`（在 `Start` 讀 bounds）
  的邊界光圈也會擺錯，`PlayerController`／`CameraFollow` 在 `Awake` 讀、在換圖之前，不受影響。不改場景檔、不改 `PlayerController`、排序仍是 -10000。
  原檔名的三張圖（`ground-grass` / `town-ground` / `candy-town`）同尺寸換成同風格的墊底版，只給編輯器看，
  `.meta` 沒動。
  - 城鎮：Voronoi 圓石街、較大較亮的廣場鋪石＋路緣石、泥土路鬆散邊緣、彎曲河岸＋沙岸＋三階水色、
    橋欄與橋下陰影、噴泉腳下一圈鋪石、建築/灌木腳下壓暗。
  - 糖果鎮：薄荷綠草、糖粒與小軟糖；巧克力磚路修圓角＋奶油糖霜（下緣滴落）；廣場內圈牛奶巧克力、
    中央薄荷糖漩渦地磚。
  - 森林的取捨：第一版自己一套較暗的色盤、兩階暗斑塊、往出口的泥土小徑 → **像迷彩、太花，被退件**；
    改出的極簡版（幾乎單色＋小草葉記號）**太平、像塑膠地板**；最後定案：**草地直接用城鎮同一套**
    （同一個色盤與斑塊參數，兩張地圖接起來是同一種草），再加所有樹/灌木/樹籬/落葉堆腳下兩階接地暗色、
    果樹下落果、花樹下落瓣、落葉堆旁散葉，以及四周一圈寬度不規則、內緣用草叢打散的較深邊緣
    （東、北出口留開口）。
- **重烤**：`python tools/bake_ground.py`（或 `forest` / `town` / `candy` 只烤一張），重跑結果位元組相同。
  參數與做法見 `tools/ground/README.md`。
- **還原原圖**：`python tools/bake_ground.py --restore`（從 `tools/ground/orig/` 蓋回三張原圖、刪掉
  `Resources/art/ground/`）；要完全拿掉再刪 `Core/BakedGround.cs`。
- 開場的**更新公告板**內容（`Data/UpdateNotes.cs`）已換成 2026-11-19 這一版（音效、新地面、面板動效等六條），並重跑字型子集化。

**2026-11-25（背景音樂與音量設定）** —— 有音效之後，剩下「安靜得很空」：沒有背景音樂、音量也沒地方調。

- **佔位音樂**：`tools/gen_bgm.py` 直接 `from gen_sfx import tone / note / lowpass / write_wav / SR`，
  同一套柔和的低通方波／三角波。四首，旋律與和弦進行全是**手寫的資料表**（一小節一串「音名:拍數」，
  腳本會檢查每小節拍數對不對、寫錯一拍直接報錯），亂數只用在打點的雜訊顆粒、以曲名當種子：

  | 曲 | 用在 | 速度／拍號／調 | 長度 |
  |---|---|---|---|
  | `day` | 森林、城鎮的白天 | 108 BPM、4/4、G 大調（短促的撥弦主奏、七和弦、咚–恰 bass＋刺點；見下面「day 重寫」）| 35.6 s |
  | `night` | 森林、城鎮、糖果鎮的夜晚 | 74 BPM、3/4、A 小調（三角波主奏、長回音、慢慢浮起的和弦墊底，沒有打點）| 38.9 s |
  | `shop` | 店裡、藥水室、後花園（不分日夜）| 104 BPM、4/4、F 大調（oom-pah bass、往上跳的琶音）| 36.9 s |
  | `candy` | 糖果鎮的白天 | 120 BPM、4/4、G 大調（斷奏、八度跳的 bass、16 分音符琶音）| 32.0 s |

  每首 16 小節、四句（問–答–對比–回主音，最後一兩拍是接回開頭的弱起）。16-bit mono 22050 Hz，
  wav 每首約 1.4～1.7 MB；匯入時由 `Editor/BgmImporter.cs` 壓成 Vorbis（quality 0.5、CompressedInMemory、
  forceToMono），網頁版每首只會是幾百 KB。峰值正規化到 0.5（音效是 0.8 × gain）—— 音樂要墊在底下、不搶戲。
  - ⚠️ **無縫循環是這支最重要的事。** 總長固定是整數小節；音符的 release、回音、低通的餘韻超出結尾的部分
    **繞回開頭疊進去**（環狀緩衝 `add_wrapped`），頭尾**不加淡入淡出**。低通、去直流、回音也都做成環狀的
    （先拿結尾那 4096 個取樣暖機）—— 一階濾波器有狀態，直接從 0 開始濾的話，接點兩邊的狀態不一樣，
    循環時會「喀」一聲。驗證：四首的 `|最後一個取樣 − 第一個取樣|` 都在一般相鄰取樣差距的量級以內。
  - 速度：`tone()` 是逐取樣的純 Python，所以同一個音（長度／音高／音色都相同）只合成一次、快取起來重複疊
    （琶音與 bass 重複得很兇），四首合計 20 秒以內。
- **播放**：`Core/Bgm.cs`，仿 Sfx 的常駐物件（`AfterSceneLoad` 喚起、`DontDestroyOnLoad`、`SubsystemRegistration`
  清靜態）。**不另外掛 AudioListener**（Sfx 那個就夠）。兩個 loop 的 AudioSource 輪流當「新的那首」，
  1.2 秒交叉淡變（`unscaledDeltaTime`），淡出完就 Stop。
  - 選曲在 `Bgm.Choose()`：`main`（森林，確認過 `BakedGround`／`PortalGlow` 都把 main 當森林）／`town` → 白天 `day`、
    夜晚 `night`；`candy` → `candy`／`night`；`shop`／`brew`／`garden` → `shop`；其他場景名淡出不播。
    換場景掛 `sceneLoaded`；日夜在 `Update` 比 `TimeSystem.IsNight`，**變了才重選**（室內場景連看都不看）。
  - **要換的曲跟現在的一樣就完全不動** —— 森林走進城鎮、店裡進藥水室，音樂不斷也不從頭來。
    剛淡出的那首又被選回來（進門馬上出來）就直接拉回來，不重播。
  - 音量 ＝ `Sfx.MusicVolume` × 淡變係數，`Sfx.Muted` 時壓到 0（**照樣在播**，解除靜音接著響）；
    訂閱 `Sfx.Changed` 才重套，不是每幀設。找不到檔一樣是同名只警告一次、絕不丟例外。
- **設定擴充在 `Sfx` 裡**（存檔 key 仍是 `witch.audio`）：`Settings` 多一個 `music`（預設 0.5），
  舊存檔沒有這欄 —— JsonUtility 對缺的欄位保留預設值，不用 migration。`Volume` 從「總音量」改名成**音效音量**，
  新增 `MusicVolume`；**`Muted` 現在同時靜音音樂與音效**，M 鍵的 Toast 改成「聲音：靜音／開啟」。
  新增 `Sfx.Changed`（三個值任一變了就發，`ResetStatics` 清掉）。
  - ⚠️ **音量的存檔要防抖**：`SaveManager.SetString` 每次都整包寫檔，原本的 setter 每改一下就寫一次 ——
    設定面板連按 ＋ 會連寫十次。改成 setter 只改記憶體＋發 `Changed`＋記 dirty，`Sfx.Update` 在**最後一次變動後
    0.5 秒**（unscaledTime）才寫；`OnDestroy`／`OnApplicationQuit` 時還 dirty 就補寫。`Muted` 維持立刻寫
    （順便把沒寫的音量一起帶走）。值沒變的 set 什麼都不做（不發事件、不寫檔）。
- **設定面板** `UI/SettingsPanel.cs`（WardrobePanel 的寫法）：音樂／音效兩列「− ＋ 10 格音量條＋百分比」，
  每下 ±10%（也可以直接點方塊跳到那一格；已經是那格再點＝少一格，才調得到 0）；音效調完播一聲 `pickup`。
  靜音鈕顯示「已靜音／有聲音」，跟 M 鍵是同一個開關（面板訂閱 `Sfx.Changed` 重畫）。
  - ⚠️ **不用 UI Toolkit 內建的 `Slider`**：執行期沒有預設主題樣式表，拖曳鈕跟軌道整個看不到。
    音量條是 10 個小 VisualElement，樣式加在 `ShopManageStyle.uss` 尾端（`.set-*`，沒動既有規則）。
  - **`O` 開關**（`grep KeyCode.O` 確認過沒人用）、`Esc` 也能關。開在 `PlayerController`、關在面板的 `Update`，
    照 QuestPanel 擋同一幀開了又關／關了又開。
- **HUD 入口**：`CornerHud` 底下一顆小小的「設定 (O)」（`.hud-settings`，在 `HudExtraStyle.uss`）。整塊 HUD 仍是
  `PickingMode.Ignore`，只有這顆按鈕吃滑鼠。
  - ⚠️ **點這顆不能順便點地面走路**：點地走路讀的是 `Input.GetMouseButtonDown`，**完全不看 UI**（以前所有 HUD 都
    Ignore、可點的面板都會設 `ModalOpen`，所以沒事）；而按鈕的 click 要放開才觸發 —— 按下那一刻人就往左上角走了。
    最小的防護：`CornerHud.BlocksWorldClick(mousePosition)` 用 `RuntimePanelUtils.ScreenToPanel`（y 要先翻）
    換到面板座標、看是不是落在按鈕的 `worldBound` 裡，`PlayerController` 點地前先問一句。量的是實際範圍，
    不靠 UI 事件與 `Update` 誰先跑。之後 HUD 再加可點的東西，加進這支就好。
  - 按鈕在別的視窗開著時（例如不蓋暗幕的對話框）不疊開設定 —— 不然關設定時會把對話框的 `ModalOpen` 一起解掉。
- 開場的**更新公告板**（`Data/UpdateNotes.cs`）加了兩條（背景音樂、O 鍵設定），日期改 2026 / 11 / 25，並重跑字型子集化。
- **`day` 重寫**：被說「森林的歌像武俠遊戲」—— 旋律幾乎只用 C D E G A 的五聲音階、
  三四度跳進，主奏又是抖音＋回音＋低八度疊音的長音，聽起來像二胡／笛子。改成 **G 大調、108 BPM、35.6 s**：
  完整自然大調、Fa（C）與 Ti（F#）放在強拍與樂句轉折（佔音符 29%）、多級進加兩個半音經過音，附點／切分／休止；
  主奏改短促的撥弦音色（gate 0.58、sustain 0.22、**沒有抖音**、回音只剩一階 0.10、拿掉低八度疊音，
  加一點高八度正弦的「叮」）；和弦換七和弦（Gmaj7–Em7–Am7–D7、ii–V–I 終止），bass 咚–恰＋2、4 拍的和弦刺點，
  拿掉琶音。為此 `gen_bgm.py` 多了：`CHORDS` 的七和弦、lead 的 `bell`、新的 `stab` 聲部、`arp` 可省略 ——
  全是選用欄位，`night`／`shop`／`candy` 重產後 md5 逐 byte 不變。
- **衣櫃面板改兩欄**（被說「破版、要有預覽圖」）：舊版一列擠 44×52 小圖＋名稱＋長說明＋按鈕，說明塞不下。
  現在面板寬 640：左欄 200 是造型清單（只有名稱，身上那套標「穿著中」、選取中暖棕底＋亮框），右欄是 196×264
  **原尺寸**立繪（墊亮一階的底色框）＋名稱＋完整換行的說明＋「換上」鈕。**點左欄只是預覽**，按「換上」才換。
  清單項目 Build 時建一次、Refresh 只改 class 與文字（不會疊事件）。樣式 `.wd-*` 加在 `ShopManageStyle.uss` 尾端。
  ⚠️ `UIPanelSettings` 是依高度縮放、參考 640 → 邏輯高度恆為 640，`.panel` 的 88% ＝ 563，面板算下來約 532。
- 夜晚曲 `night` 也重寫了（使用者聽到的武俠味其實是它：A 小調＋長音；改成大調系的音樂盒搖籃曲）。

**2026-11-25（碰撞與地圖邊緣）** —— 被回報「人物走動會穿邊邊跟穿物件（要撞到樹那些要停下來不能穿過去）」。
原本專案**沒有任何碰撞**：`PlayerController.Update` 直接改 `transform.position`，只夾在 Ground 的矩形裡；
女巫的樞紐在腳底，所以走到上緣整個人畫在地面外、左右緣半個身體凸出去。

- **落地範圍是離線量的**（仿 `gen_furniture_bounds.py`）：`tools/gen_footprints.py` 從 `ForestLayout`／`TownLayout`／
  `Candy.cs`（資料夾取 `CandyTown.ArtDir`）用正規表示式收集實際擺出來的 61 張圖，量每張圖不透明範圍最底下 15%
  （「貼地那一段」）的左右範圍 —— 只算那一段裡至少 35% 的列有畫到的欄（花店右邊那種細雜線不會把寬度灌大）；
  樹另外取那一段每列寬度的中位數（＝樹幹，樹根往外張、樹冠垂下來都被中位數濾掉）。
  依 art 路徑分類（`RULES`），每類一組形狀係數（`CATS`），輸出 `Data/ArtFootprints.cs`：
  sprite 名稱 → 形狀（相對圖片中心、原圖像素，用的時候乘 scale、翻面取負）。
  - 形狀只有兩種：**軸對齊橢圓**（樹幹、灌木、路燈、噴泉、石頭類）與**軸對齊矩形**（建築、樹籬、圍籬、花台）。
    玩家是腳底半徑 11 的圓，碰撞時把形狀往外長 11（矩形就變成圓角矩形、扁的時候就是膠囊）。
  - 擋路：樹（只擋樹幹的小橢圓，能繞到樹冠後面）、灌木、樹籬、建築（底部整個寬、**深到圖高一半**：牆面走不進去，
    屋頂那半可以從旁邊繞到後面）、圍籬、花台、路燈、噴泉、糖果鎮的樹林／石頭／樹樁／寶箱／水晶。
    不擋：橋、拱門、地上的糖果盤、藥草叢、落葉堆（要走上去採）、小糖果裝飾、糖果鎮的 NPC。
- **碰撞系統** `Core/Obstacles.cs`（純資料、不靠物理）：`PlayerController.Awake` 依場景叫 `Obstacles.Begin()`
  （只記場景、可走範圍、出生點；只有 main／town／candy 開），**第一次移動時才掃場景**建清單 ——
  掃的是場景裡實際的 `SpriteRenderer`（sprite 名稱查表，位置／scale／翻面都是真的；圖片中心用
  `TransformPoint(sprite.bounds.center)`，樞紐在中心〔森林、城鎮〕或在腳底〔糖果鎮〕都對）。
  糖果鎮的建築是 `CandyTown` 在 `Start` 才擺的，擺完呼叫 `Obstacles.MarkDirty()`，下一次查詢重建。
  - 查詢 `Resolve(from, to)`：整步可走就走 → 沿擋住的那個障礙的切線滑（斜著推樹幹會繞過去）→ 只走 X → 只走 Y → 不動。
    128px 切格，只看玩家所在那一格；每幀不配置記憶體。
  - **防卡死**：「擋」的判準是「to 插進某個障礙、而且比 from 插得更深」—— 本來就在裡面時，往外走一律放行；
    同時插在兩個裡面、三種走法都不行時，只要**總穿入深度**變小就放行。
  - **門口挖開**：門（`SceneDoor`）的觸發點落在建築範圍裡、或在它正後方自動觸發距離內時，那棟建築拆成左右兩塊，
    中間留 48px 的通道（`DoorGapHalf` 24）。觸發點在範圍**底緣以下**（正面）時不挖 —— 本來就走得到。
  - **小屋的門（修正）**：原本觸發點在 `(-631, 402)`，落在左牆半腰的屋簷上，碰撞只好在牆上挖通道、玩家要從左牆走上去才進得了門。
    原因是 `Doorways.CottageDoor` 照「原點在房子底部」寫成 `(-93, 12)`，但城鎮物件的 position 是**圖片中心**。
    對著 `cottage-home.png`（290×258）量：拱門約圖上 x 63~103、門前圓石階 x 36~115／y 218~254 —— 改成 `(-65, -135)`
    ＝ 世界 `(-603, 255)`，石階正下方、落地範圍底緣（y 261）外 6px。現在不挖通道，從正面走上石階就進門。
    城鎮只有這一扇 `SceneDoor`（NPC／商店是 `TalkNpc`／`ActionPoint`，位置＝物件本身）。
    回城鎮的出生點仍是場景檔的固定 `(-1200, -40)`，不是門口，不會一出來就被吸回去（`SceneDoor.armed` 也還在）。
- **接進 `PlayerController`**：鍵盤與點地自動走都先夾邊、再 `Obstacles.Resolve`；店裡（`isoRoom`）照舊只夾菱形地板。
  點地自動走連續 0.35 秒幾乎沒有更接近目的地（每幀前進不到一步的 15%）就取消 `moveTarget`（不做尋路）；
  走到目的地的「貼齊」也過碰撞。腳步聲量的是實際位移，被擋住自然不響。
- **地圖邊緣（「穿邊邊」）**：戶外地圖的可走範圍往內縮 —— 上 64（一個身高）、左右 22（半個身寬）、下 6；
  拿掉節點上的 `edgeMargin`（場景檔裡殘留的序列化值 Unity 會忽略），數值在 `ArtFootprints.EdgeTop/EdgeSide/EdgeBottom`。
  - **換場景**：仍是「推到邊界」觸發，改成夾邊前記下想走出哪一側、碰撞解算後**真的站在新邊界上**才呼叫 `OnReachEdge`。
    點地走路的目的地夾邊（內縮 4px，不會自動走出地圖）直接用新的 minX…maxY。出生點：森林 (0,0)、城鎮 (-1200,-40)、
    糖果鎮 (0,-820)，都離新邊界很遠、也不在任何障礙裡（離線檢查有驗）—— 不會一進來就再觸發一次。
  - `PortalGlow` 的上緣光圈原本在地圖邊往內 26px，腳踩不到圈心；改成往內 `EdgeTop − 10` ＝ 54px。左右、下緣維持 26。
  - 森林地面烤圖四周那圈深色灌木邊緣（`bake_ground.py` 的 `edge_dark`）寬度約 12～140 世界像素、平均約 60，
    起伏很大：上緣 64 大致吻合，左右 22／下緣 6 比視覺邊緣窄 —— 女巫可以走進左右與下方那圈深色草裡。沒改烤圖。
- **排序（順帶修的）**：女巫的 `sortingOrder` 原本一直是場景產生器給的 0，跟所有物件的前後關係是固定的
  （中心 y < 0 的樹永遠蓋在她身上）—— 做碰撞時要「繞到樹冠後面被遮住」才發現。戶外改成每幀照腳底 y 排
  （`PlayerController.LateUpdate`）；物件在 `Obstacles` 建清單時一併從「圖片中心的 -y」改成「腳底的 -y」，
  橋與地上的糖果盤壓到 -8600（光圈之上、影子之下）。**城鎮建築不改**（`keep_order`）：門口的花台／灌木是貼著正面擺的，
  改成看腳底會被房子整個蓋掉；建築的範圍剛好深到圖片中心，女巫不是在中心以下就是以上，照中心排一樣對。
- **可達性自我檢查**：編輯器裡每次戶外場景建好障礙就跑一次（`#if UNITY_EDITOR`），Console 印一段 `[Obstacles] …`：
  障礙數、各類別數、可走面積、走不到的互動點（採集點、門〔自動觸發距離＋按 E 距離〕、NPC、商店、邊界出口）、
  城鎮落在障礙裡的村民路點。有走不到的就是 Warning。離線版 `tools/check_walkable.py` 用同一份規則做同樣的事＋預覽圖；
  目前三張地圖**走不到的互動點都是 0**。城鎮有 4 個村民路點落在建築範圍裡（村民不套碰撞，只是會走過房子正面的牆）。
- **除錯**：`F3`（`Core/ObstacleDebugView.cs`）畫出所有落地範圍（紅）、女巫腳底的碰撞圓（青）、可走範圍（黃），
  LineRenderer、排序 30000。預設關閉。
- **怎麼調某一類的範圍**：改 `tools/gen_footprints.py` 的 `CATS`（`wk`＝寬度係數、`depth`＝深度、`lift`＝底緣往上抬，
  `>=1` 是像素、`<1` 是圖高比例）→ `python tools/gen_footprints.py` → `python tools/check_walkable.py <資料夾>` 看預覽與清單。
  某一張圖要換類別就改 `RULES`。新增物件種類沒進表 ＝ 不擋（不會把人鎖住）。
- ⚠️ **陷阱**：
  - 形狀的座標是**相對圖片中心**，不是物件的 position —— 森林／城鎮的物件 position 就是圖片中心，糖果鎮的是腳底。
    直接拿 position 當中心，糖果鎮的範圍會整個往下掉半個圖高。
  - 圖都是**裁切到不透明範圍**的（量出來的整體範圍＝整張圖），所以重點全在「貼地那一段」，不是透明邊。
  - 樹的貼地那一段含樹根和垂下來的樹冠，用聯集寬度會是樹幹的兩倍；所以樹用每列寬度的中位數。
  - 城鎮 `TownLayout` 的三座橋座標在 x≈1790～1870，**在地圖外**（地圖只到 ±1600）；河上那幾段石橋是烤進地面圖的。

**2026-11-25（魔女的房間改用 SVG 重畫）** —— 藥水室原本是一整張背景圖：走得到鍋爐和床上、家具不會遮住人。
使用者同意捨棄原本那張圖、改用程式畫，並明確要求**物件要拆開**（可遮擋、可碰撞）；看過預覽後回「可以了」。

- **產生器是唯一的數字來源**：`tools/gen_brew_room.py` 畫房間殼（牆＋地板，日／夜兩張）與 24 件獨立物件
  （地毯三張、衣櫃、書櫃、書桌、凳子、木箱、鍊金桌、床頭櫃、床、壁爐＋爐火、扶手椅、貓、柴堆、藥水台、
  蠟燭與燭台、鍋爐六幀、盆栽），同時決定每件擺在哪、落地範圍、排序、夜晚光暈、五個互動點與距離、出生點、
  地板可走多邊形，輸出 `Data/BrewRoomLayout.cs`。C# 那邊不自己寫常數。
  - 座標：地板 uv（u 沿右後牆、v 沿左後牆）→ 等距 2:1 → 世界座標（房間圖中心＝原點），換算寫在產生器檔頭。
  - 畫法約定（光從左上的窗戶來、每種材質 4 階色、1px 內線、後處理補外輪廓與貼齊色盤）也在檔頭，加家具照著做。
  - 這台沒有 inkscape／cairosvg：全部 SVG 排在一張 HTML 上，用無頭 Chrome 截一次圖再切開。
- **執行期** `Core/BrewRoom.cs`：`UseSvgRoom`（預設 true）切新舊房間，false 退回整張舊圖與原座標（舊圖沒刪）。
  新房間照 `BrewRoomLayout.Pieces` 一件件擺；圖的樞紐放在落腳點、1:1 不縮放。貓與爐火用新的 `Core/FrameAnim.cs`
  （最小的循環幀動畫，可給播放順序與相位）；鍋爐只在熬煮時播，仍由 `BrewCauldron` 控制。
  夜晚換房間殼、家具乘 `NightTint`、蠟燭／壁爐／鍋爐火亮起光暈（`glow.png` 白色徑向漸層，顏色由 SpriteRenderer 給）。
- **碰撞**沿用 `Core/Obstacles.cs`，但走另一條路：可走範圍是**地板多邊形**（`Begin` 的 `walkPolygon`），
  家具由 `BrewRoom` 直接登記（`AddPoly` 平行四邊形／`AddEllipse`），不掃 SpriteRenderer。沒有邊緣內縮。
- **女巫的排序**：等距的長家具用單一 y 排不對 —— `BrewRoom.PlayerOrder` 只看跟她的圖重疊的家具，
  用落地範圍的 uv 盒子判斷她在前還是在後，插在「該在她後面的最大值」之上。家具彼此的靜態排序是產生器離線拓樸排序的（間隔 20）。
  跟產生器的 `player_order()` 是同一個算法，預覽圖就是用它疊的。
- **出生點**跟著配置表（`BrewRoomLayout.Spawn`），場景檔裡的 (0,-250) 是舊房間的。
- ⚠️ 互動點彼此要拉開（一顆 E 只能觸發一件事）：產生器會檢查「同時在兩個範圍內的可走位置」，目前為無。

**2026-11-26（城鎮的河要走橋）** —— 河是烤進地面圖的，場景裡沒有河的物件可以掃，原本可以直接踩過去。

- **做法**：離線產生矩形清單登記成障礙。`tools/gen_town_water.py` → `Data/TownWaterData.cs`（36 個軸對齊矩形，世界座標）；
  執行期 `Core/TownWater.Register()` 用 `Obstacles.AddPoly(…, "water")` 登記，`PlayerController.Awake` 在 `Obstacles.Begin` 之後呼叫。
- **為什麼碰撞跟畫面對得上**：遮罩直接取自 `tools/ground/town.py` 新抽出來的 `shape_masks()`，跟烤圖是同一份。
  橋（石頭）在遮罩裡本來就扣掉了，橋面不用另外挖開。抽函式後重烤，兩張城鎮地面圖的 md5 不變。
- **座標換算**：烤圖 1600×1024、1 美術像素＝2 世界像素、**y 軸相反**（row 0 是地圖最上緣）。
- **數值**：往內侵蝕 6（Obstacles 再往外長 11 → 腳底圓心停在離水約 5px 的沙岸或欄杆上；侵蝕 11 會有半隻腳畫在水上）；
  16px 粗格、格內水超過一半才擋；貪婪合併（直向先 41 個、橫向先 36 個，取少的）。
  三座橋的腳底通道：北 170／中 58／南 106px（算進橋上的灌木後中橋約 54），產生器規定至少 30、不夠會強制清掉橋面格。
- **驗證**：`tools/check_walkable.py` 的城鎮檢查會先不算水跑一次再比較 —— 可走面積 93.65% → 90.46%，
  少掉的全是水面本身、被切斷的岸 0 格；走不到的互動點 0、邊界出口走得到。預覽圖多了河的特寫。
- 森林與糖果鎮的烤圖沒有水域，不用做。
- ⚠️ **陷阱**：
  - `TownWater.Register()` 一定要在 `Obstacles.Begin` 之後（Begin 會清空登記）；`Obstacles.ClearRegistered()` 不帶類別會連河一起清掉。
  - 改了城鎮的路或河（`town.py`、`townmask.py`、種子）重烤之後，**一定要重跑 `gen_town_water.py`**，不然碰撞跟畫面錯開。
  - `town.shape_masks()` 會取亂數，`bake()` 必須最先呼叫它，否則烤圖會變；動它之後用 md5 對照烤圖。
  - 找橋不能用「石頭 & water_r」：北邊大石橋中間不在 water_r 裡，會被拆成兩條欄杆。

**2026-11-26（店裡的碰撞與前後排序）** —— 店裡原本只夾菱形地板：會穿過貨架與販售桌，女巫的排序固定是 0。

- **碰撞**：店裡改走跟藥水室同一套 `Obstacles`。可走範圍是 `ShopRoom.WalkFloor()`（地板菱形內縮 `FloorMargin` 0.18 格，
  跟舊的 `ClampToFloor` 是同一塊區域，隨機 20000 點比對 0 個不一致）；每件擺出來的家具登記一個 `AddPoly`
  （`ShopRoom.FootprintPoly`：佔地 w×h 格、每邊內縮 `FurnitureInset` 0.2 格的平行四邊形）。裝飾不擋。
  `PlayerController` 拿掉 shop 特例（`isoRoom`），鍵盤、點地、stall 取消、貼齊目的地全部共用藥水室那條路。
- **為什麼內縮**：一格兩條磚緣的垂直距離只有 28.6px、腳底圓半徑 11 —— 不內縮的話貨架前規定的一格走道只剩 6.6px；
  內縮後剩 18px。代價：兩件家具角碰角的角縫（12.8px）鑽不過去，要從旁邊繞（跟畫面一致）。
- **重登記**：`ShopRoomView.Rebuild()` 每次重畫先 `Obstacles.ClearRegistered("shop_furniture")`（新 API，只清指定類別）再整批登記。
  佈置模式只在放下／完成／翻面等時候才 `Rebuild`，不會每幀重建。佈置完站在家具裡靠防卡死走出來。
- **排序** `ShopRoomView.PlayerOrder`（仿 `BrewRoom.PlayerOrder`）：只看跟她身體重疊的家具，用格座標判斷前後
  （fx ≥ gx+w−0.5 或 fy ≥ gy+h−0.5 ＝她在前面）；取「她在前面的家具」最大 order＋1，只有「她在後面的」時取最小 order−1，
  都沒疊到用 −y。矛盾時保住腳底最近的那件。家具自己的 order 維持 −錨點 y（佈置模式、顧客都依賴它）。
- **檢查**：`Obstacles.SelfCheck` 多檢查販售桌前（`SaleCounter` 不是 `InteractPoint`）；有地板多邊形的房間改用 8px 取樣格。
  離線 `python tools/check_shop_walk.py`（從 C# 讀常數）：預設擺設＋四種刁鑽擺設各跑三趟 flood fill，
  門、販售桌、每格貨架走道都要走得到 —— 目前全過。**改 `FurnitureInset`／`FloorMargin` 之後要重跑。**
- 有地板多邊形的房間不觸發邊界換場景（那個矩形只是外接框，出口一律是地板上的門）。
- 開場公告板換成 2026 / 11 / 26 這一版（房間重畫、店裡碰撞、河要走橋），字型已重新子集化。
- ⚠️ **陷阱**：
  - `Obstacles.Begin` 會清空所有登記，而 `GameArt.OnReady` 是同步立刻執行的 —— 店裡第一次 `Rebuild` 一定要在
    `ShopRoomView.Start`；放 `Awake` 會登記完又被清掉，家具全部穿得過去。
  - 斜向一格走道淨寬只有約 18px，16px 的 flood 格子會誤報走不過去。
  - 排序在佔地格左右尖角只放寬「前面」的判斷（腳底最多踩進約 0.8px）；背面不能放寬，不然站在貨架後面會被畫到架子上。
  - `typecheck.sh` 沒定義 `UNITY_EDITOR`，`SelfCheck` 那段不會被編到（這次另外加 define 編過一次確認）。

**2026-11-26（道具圖示改 8-bit、店內家具重畫、商品擺上貨架）** —— 使用者要求：「店裡的貨架可不可以也幫我畫…
要販賣的掛上去的物品…道具也幫我畫…SVG 或點陣圖…那種 8BIT 感的」。全部**還沒實機看過、也還沒有使用者對成品的回饋**。

- **道具圖示** `tools/gen_item_art.py` → `Resources/items8/`（34 張：8 材料、13 藥水成品、6 糖果鎮商品、3 種子、3 花、水滴）。
  直接在 24×24 邏輯格上畫點陣（不是畫大圖再縮 —— 縮小會內插出中間色與半透明邊），3～4 階打光、自動補 1px 外輪廓、
  NEAREST ×4 成 96×96。色盤 import `gen_brew_room.PAL` 再補鮮豔的果實／糖果色。重跑 md5 相同。
  - 切換：`GameArt.UsePixelItems`（false＝舊圖；舊圖都沒刪）。檔名沿用舊檔名、只換資料夾，`items8` 缺哪張就退回那張舊圖。
    花的收成圖示改用新圖，成長走圖與土壤磚沒動。`--restore` 會刪掉 `items8/`。
  - ⚠️ 規格：每張 96×96、水平置中、底部貼齊（留 1 格）—— 貨架縮到約 24px 高時每件才會坐在同一條線上。
  - ⚠️ 新圖內容只佔整張約 80%：世界空間「最長邊縮到 N px」的地方要經 `GameArt.ItemIconWorld()`（採集飄字 34→40、顧客泡泡 32→37.6）。
  - ⚠️ 水滴（以前沒有這張圖、一直是小白點）的縮放依賴 `GardenPlot.DropContentFrac = 17/24`，重畫水滴要一起改；顏色不要再乘藍。
  - ⚠️ 產生器：外輪廓用四鄰接（八鄰接斜線會長鋸齒角）；發光物畫在 glow 層不補外輪廓；重疊的同色球要用 `sep()` 分開。
  - ⚠️ 糖果鎮的舊檔名是歷史包袱：`item-lollipop`＝焦糖蘋果棒，`item-gobstopper`＝永恆彩球糖。
  - 產生器自評偏弱的幾張：落葉（像星星）、羽翼掃帚（縮小後一團白）、暗影藥水、烈焰藥水、藍莓。
- **店內家具** `tools/gen_shop_art.py` → 覆蓋 `Resources/furniture/*.png`（16 款貨架＋販售桌，Id 與 .meta 不變）。
  import `gen_brew_room` 的 SVG 管線（等距畫法、色盤、無頭 Chrome、後處理），一支參數化的貨架函式組出 16 款
  （層數、背板、側板、頂飾、下櫃／抽屜、木色）。1 世界像素＝1 圖像素，架身只畫約半格厚、貼牆。
  錨點仍是「圖的正下方中央＝佔地前角」，由產生器裁切時對齊，C# 沒改。`ArtFits` 驗算結果跟原圖完全相同。
  原圖備份在 `tools/shop_art/orig/`，`--restore` 蓋回；`--preview <資料夾>` 出總覽與擺進店裡的合成圖（⚠️ 預覽裡的商品仍讀舊道具圖）。
  每次執行會自動重跑 `gen_furniture_bounds.py`。
- **商品陳列**：產生器同時輸出 `Data/ShopDisplaySlots.cs`（137 個陳列位：相對錨點的偏移＋最大寬高；記了圖尺寸，對不上就不擺）。
  `ShopRoomView.SpawnGoods` 依 `ShopStock.Listings()` 擺：先販售桌、再依家具擺出順序；數量 1／2～4／5 以上佔 1／2／3 個位子；
  圖等比縮到位子大小、底部中心對齊；sortingOrder＝家具＋1。新的 `ShopStock.Changed`（Add／RemoveOne 發，改價不發）一發就只重擺商品。
  - ⚠️ 商品掛在家具根物件、排在 `art` 之後：掛在 art 底下翻面時會被鏡像；排在前面編輯器的 HitTest／Tint 會抓到商品。
  - ⚠️ `PlayerOrder` 女巫在家具前面時改成 +2（+1 會跟商品同層亂蓋）。
  - ⚠️ 陳列位的寬高已扣掉近側板前緣、上一層層板前緣（商品永遠畫在家具上面，超出去會穿幫）。
  - ⚠️ 新色只能加在 `SHOP_EXTRA`，不能改 `PAL`（魔女房間的圖會變）。換家具圖一定要重跑產生器，陳列位才對得上。
  - 翻面靠右牆時光源變成從右邊來（既有的鏡像做法）。

**2026-11-26（佈置提示、商品換位、顧客改版）** —— 使用者看過 8-bit 圖後回「你畫得很可愛」，接著要求：
「擺放貨架的提示不夠明顯」「上架的東西我也想要可以改地方放」「客人不要一個一個進來，可以隨機好幾個、不同時間進來，進來可以泡泡說說話」。
全部**只編過、還沒實機看過**。

- **佈置提示**（規則 `RoomLayout.Check` 沒改，只改呈現）：店裡常駐「R 佈置店面」HUD 標籤（`CornerHud`、`.hud-edit*`），
  第一次進店跳一次 Toast（旗標 `witch.tips.shopedit`）。佈置模式地板壓暗；格線／門口／走道改實心粗邊（實際 alpha 約 0.05 → 0.4～0.75）；
  佔地預覽加粗並脈動，放不下時在想去的那格畫紅色殘影（以前放不下只剩綠格，紅色從沒出現過）；拖貨架時藍框預覽它自己的走道；
  被拖／被選的東西頭上有世界空間小標籤（原因、F／T／右鍵）；托盤提示放大加底色、按鍵與圖例上色。
- **商品換位**：`PlacedFurniture` 加持久 `uid`（存進 `witch.room`，舊存檔載入時補發並存回）；指定位置另存 `witch.shop.display`
  （`Core/ShopDisplay.cs`：商品名 → uid＋畫面順序的位子），`Listing` 沒動。`SpawnGoods` 先擺有指定的（不跨層、不壓別人、不夠就少擺），
  再照舊規則補空位；指定失效退回自動但不刪，下架／賣完才清。佈置模式裡拖商品：綠圈＝空位、橘圈＝交換、34px 內落到最近的位子，圈外回原位。
  Esc 會連商品位置一起還原。`ShopRoomView.BrowseSpotFor(item)` 回傳顧客看那樣商品該站的位置。
  - 順手修的舊 bug：Esc 快照是淺複本所以還原不了被拖過的家具；Esc 沒清拖曳狀態；拖曳中按 F／T 會 Rebuild 掉手上的物件；放回原位沒還原基準角。
  - ⚠️ `PlacedList()` 是淺複本，快照要用 `PlacedSnapshot()`；`SetPlaced` 會重建物件，複製一律用 `Clone()` 帶 uid，找家具一律用 uid。
  - ⚠️ `Load` 裡不能呼叫 `Save()`（遞迴），補發 uid 後直接寫 SaveManager。交換時被拖的那筆最後寫（排最前＝優先拿位子）。
  - ⚠️ 欄位不能叫 `tag`（蓋掉 `Component.tag`）。`ShopRoomEditor.cs` 這次整檔換行從 CRLF 變 LF，diff 是整檔。
- **顧客** `CustomerManager`：每 I×f 秒來一組（f＝0.35～1.75、偏短），25% 是 2～3 人結伴（錯開 0.6～2.5 秒進門）；
  每位約 68% 會買、其餘只逛不買 —— 購買機率＝E[f]／E[每組人數]，所以期望成交率仍是舊版的 1/I。
  同時上限 `Upgrades.CrowdCap()`＝ceil(舊上限×1.5)+2（5～14 人），滿了的那組在門外等。`CompleteSale` 與 `AwayShop`（0.7/I）沒動。
  `python tools/sim_customers.py`：新／舊成交件數 89%～100%（最低那檔是最高升級＋節日、12% 時間滿座）。**改來客或停留常數後要重跑。**
  - 台詞在 `Data/CustomerLines.cs`（招呼／想要／道謝／沒貨／逛逛／結伴對話，依時段、季節、節日加料，11 位村民各 3 句專屬）。
  - `SpeechBubble`：依字寬自動加寬、超過 196px 拆兩行、可給存在時間（淡出）、多顆錯開。
  - 走位：去 `BrowseSpotFor` 的位置並互相錯開；`Core/ShopPath.cs` 在 14×10 格盤上 BFS 繞過家具（只在設定目的地時算一次，找不到路退回直線）。
  - 排序：顧客改問 `ShopRoomView.PlayerOrder`（`VillagerAnim.orderOverride`，城鎮村民不受影響）；同 order 用 z 微調。
  - ⚠️ 泡泡的反鏡像要每幀做（角色說話中會轉身 —— 舊版只在出現那刻做一次，文字會變鏡像）；`Clear` 要先改名關掉再 Destroy。
  - ⚠️ 同 order 比 z 依賴內建管線＋正交攝影機＋女巫 z＝0。走到一半家具被搬動的那位會照舊路穿過去一次。
  - ⚠️ `typecheck.sh` 兩個人同時跑會互蓋 rsp 檔報假的 CS2011，要各自設 `TMPDIR`。
- 公告板更新成 8 條（今天全部的新東西），字型已重新子集化（475.6 KB）。

**2026-11-26（開店／關店、說明圖示化、UI 8-bit 外觀）** —— 使用者回饋：「關店才可以擺放貨架，所以要有關店跟開店」「開關店要有風鈴聲」
「解釋擺放東西不用要字，用圖文的方式，解釋的文字太多了」「遊戲的 LIST（製作清單這類）都很醜，也幫我出圖美化」；
看到第一版後又說「開關店要做在工具列上啦（上方）」「下排道具列很醜」。全部**只編過、修好後還沒實機看過**。

- **開店／關店** `Core/ShopSign.cs`：存檔 `witch.shop.sign`（沒存過＝開店，舊存檔不變）。`ShopSign.Serving`＝開著且在 08:00–20:00；
  `CustomerManager` 進客與 `AwayShop` 背景成交都看它，`DailyLog.IsShopOpen()` 語意沒動。不自動開店。
  `SetOpen` 播風鈴聲 `chime-open`／`chime-close`（`gen_sfx.py` 新的 `ring()`：正弦＋泛音、指數衰減；`python tools/gen_sfx.py <名字>` 可只產指定音效）。
  - **入口在上方工具列**（`UI/CornerHud.cs` 整支重寫成橫向工具列：金幣｜名聲｜開關店鈕＋店裡才有的 R 佈置提示｜設定），熱鍵 **P**，每個場景都能切。
    第一版是「門口招牌走近按 E」，被使用者改掉；門口招牌（`Core/ShopSignPost.cs`、`tools/gen_shop_sign.py`、保留格 `ShopRoom.SignCell (7,9)`）留著**純顯示**：翻面、搖風鈴、關店時輕晃。
  - **關店才能佈置**：開店中按 R 進不去 —— deny 音＋圖示 Toast（開店招牌 → 滑鼠點 → 關店招牌 → R）＋工具列按鈕抖一下閃紅框。
  - ⚠️ 點地走路不看 UI：HUD 上可點的東西都要落在 `CornerHud.BlocksWorldClick`（現在量整條工具列）。
  - ⚠️ UI Toolkit 按鈕被點過會拿到焦點，Space／Enter 會再觸發 —— 一律 `focusable = false`（不然施法鍵會把店關掉）。
  - ⚠️ 預設主題 `.unity-button:hover:active` 權重高，按鈕狀態規則要疊兩個 class 才蓋得過。會跳動的元素用 visibility 留位子、別用 display。
- **說明圖示化**：`tools/gen_ui_icons.py` → `Resources/ui/icons8/`（39 張：鍵帽、滑鼠、動作、六種放不下的原因、開關店、圖例；`UI/UiIcons.cs` 取圖，缺圖回 null）。
  佈置模式的托盤提示列改成依狀態顯示的圖示組（`ShopRoomTray.SetHint(HintMode…)`）、物件頭上的標籤改成圖示泡泡、十幾條文字 Toast 拿掉
  （改用 deny 音＋抖一下閃紅；`Toast.ShowIcons` 是帶圖示的版本）、第一次進店改成五格圖解卡 `UI/ShopEditIntroCard.cs`。
  只剩「還原」「空的 · 去花店買」兩處有字。`RoomLayout.BlockText` 已沒人呼叫（留著）。
  - ⚠️ 抖動是改物件本身的位置，結束／被抓起／離開佈置模式一定要放回（`StopShake`）。圖解卡關閉時 `ModalOpen` 要延一幀放開，不然同一個 R 直接進佈置。
- **UI 8-bit 外觀**：`tools/gen_ui_skin.py` → `Resources/ui/skin8/`（53 張九宮格與小圖，邏輯格 ×3）；`ui/Skin8.uss`（每條以 `.sk` 開頭，疊在舊樣式之後）＋
  `ui/SkinBase.uss`（新元素的排版）＋`UI/UiSkin.cs`（`Apply(root)`、總開關 `UiSkin.Enabled`、共用小零件與浮動說明 `Tip`）。舊樣式表沒動。
  已套：製作清單、經營商店、背包／倉庫、手札、城鎮商店、選種子、設定、衣櫃、下排背包列（多包一層 `.hud-bar` 當底座）。
  製作清單的材料改成「材料圖＋持有/需要」小卡（夠綠、不夠紅）、價格一律金幣圖示＋數字、做不出來的列不淡化只停用按鈕。
  `python tools/gen_ui_skin.py --check` 比對 uss 的 slice；`tools/preview_ui_skin.py` 出離線 mockup。
  - ⚠️ **最大的坑（實機才看得到）**：UI Toolkit 對 Sprite 背景的九宮格邊距與原尺寸會乘「參考 PPU 100 ÷ Sprite PPU」。專案的圖一律 PPU 1 → 邊框放大 100 倍、
    整個面板變成一塊塊色塊（使用者截圖回報「很醜」）。`PixelArtImporter` 對 `/Resources/ui/skin8/` 例外設 PPU 100＋FullRect，並直接改了既有 meta
    （改 importer 不會重匯入已有 meta 的圖）。`dialogue-box.png` 等舊 UI 圖仍是 PPU 1，拿去當九宮格會踩同一個坑。
  - ⚠️ inline `style.color` 優先權高於 uss，顏色一律用 class；執行期沒有 `tooltip`；USS 沒有 `:nth-child`／`:first-child`／`gap`／`box-shadow`。
  - ⚠️ UI 縮放不是整數倍（720p＝1.125），尺寸取 3 的倍數、道具圖顯示成 24 或 48。
  - 還沒套：任務簿、每日結算、對話框、公告板、Toast、時鐘、佈置托盤（樣式在 `HudExtraStyle.uss`）。做法：Build 時 `UiSkin.Apply(root)`＋通用 class `sk-panel`／`sk-card`／`sk-ink`。
- ⚠️ 流程教訓：使用者的 Unity 是開著的，子代理存的半成品會被即時載入、被當成成品評價。多個子代理同時跑 `typecheck.sh` 要各自設 `TMPDIR`。

**2026-11-26 深夜（外觀修好後的第二輪）** —— 九宮格的 PPU 問題其實修了兩次：第一次改 meta 後被**舊的已編譯 importer 重匯入打回 PPU 1**
（我沒複查就回報「修好了」，使用者又截到壞畫面）。第二次改回 100 並加 `Assets/Editor/UiSkinImportGuard.cs`（每次 domain reload 與 skin8 圖匯入後自動檢查、
不對就重匯入；選單 `Witch Shop/工具/重匯入 UI 外觀圖`）。之後使用者回「很可愛了」，並要求：調配藥水改成翻書、開關店的招牌不要放在店裡。以下**都只編過、還沒實機看過**。

- **調配藥水 → 魔法配方書**（`UI/BrewPanel.cs` 重寫；`ui/Skin8Book.uss` 每條以 `.bk` 開頭、由面板自己加；`tools/gen_ui_book.py` → `skin8/book-*.png` 15 張；
  翻頁音 `python tools/gen_sfx.py page`）。一個跨頁一個配方：左頁成品大圖（144px）＋名稱＋說明＋售價＋頁碼，右頁材料卡＋可做幾份＋熬 1／熬 N；
  箭頭、←/→、A/D、滾輪翻頁（首尾循環、約 0.23 秒）；書下方一排 13 格配方目錄（目前頁金框浮起、做得出來有綠點、做不出來變暗仍可點）。記住上次的頁。
  按下「熬」面板照舊會關（看鍋爐），這點沒改。〔「下面是我可以選的道具」是我解讀成配方目錄，使用者未確認。〕
  - ⚠️ UI Toolkit 沒有 keyframes：翻頁是「壓扁 → 中點換內容 → 瞬間狀態 → transition 展開」，基礎規則 0s、只有 `--fold`／`--open` 有時間，加 `--open` 前要隔兩層 schedule。
  - ⚠️ 每邊是「靜態空白頁＋會翻的頁」兩層；翻頁中只記一個目標、滾輪要節流；13 格剛好 819/822，再多會換行。這個面板不支援 `UiSkin.Enabled=false`。
- **招牌搬到城鎮**：站在自家小屋門口右前方（世界 (−524, 246)，`Doorways.CottageSign (14,−144)` 相對小屋圖片中心，`InstallTown` 生成），仍是純顯示。
  排序照戶外 −腳底 y；柱腳登記 8×4 的小橢圓碰撞（`check_walkable.py` 讀同一組數字）。店內的 `ShopRoom.SignCell` 已刪、那格恢復可擺家具。
  `gen_shop_sign.py --preview` 出城鎮實景合成圖。
- **其餘介面套外觀**：任務簿（卷軸 `scroll-paper`、任務卡＝勾選框＋目標圖＋進度條＋獎勵圖）、每日結算（圖示小卡）、對話框（名字牌 `plate`、選項按鈕）、
  公告板（不用舊底圖）、Toast、時鐘下的時刻／日期膠囊（鐘面沒動）、佈置托盤、上方工具列（改用 skin 圖：hud-bar 底座、金／紫按鈕、齒輪＋O）。
  每個面板看 `UiSkin.On` 分新舊兩套；`HudExtraStyle.uss` 只動工具列段。新圖 14 張加在 `gen_ui_skin.py` 清單尾巴（原 53 張 md5 不變）；預覽 `tools/preview_ui_skin2.py`。
  - ⚠️ 工具列名聲進度條的 class 改名 `hud-rep-bar`（`hud-bar` 是背包列底座，同名會被蓋成一塊木頭）；任務簿標題樣式要寫 `.quest-scroll .quest-title`（手札也用 `.quest-title`）。
  - 還沒跟上風格：第一次進店的圖解卡 `ShopEditIntroCard`；世界空間的 TextMesh 提示（採集、花圃、鍋子、各種「E」、傳送門標籤、飄字）與客人泡泡 `SpeechBubble`。
- ⚠️ 流程教訓：改匯入設定之後要**等 Unity 重匯入完再複查 meta**，不能改完就回報；離線 mockup 驗不到匯入問題。

**2026-11-27 凌晨（腰包道具列、路人尋路、路人重畫）** —— 使用者：「下方道具欄不好看」→ 從四個方向裡選了「C 魔女腰包」；
「路人走路不要穿牆」；「幫我畫路人，用 8BIT 風格，現在的路人都很怪」。以下**都只編過、還沒實機看過**。

- **下排道具列＝魔女腰包**（`UI/InventoryHud.cs`，樣式在 `Skin8.uss` 的 `.hud-belt`／`belt-*`，圖是 `gen_ui_skin.py` 尾巴新增的 7 張 `skin8/belt-*.png`）：
  深紫布條＋上下金虛線針腳；固定尺寸的圖一個接一個排（左端 18＋口袋 51×N＋右端 18；12／15／18 格總寬 648／801／954，960 寬不換行），高 60（含流蘇 78）。
  有東西的口袋墊薰衣草襯裡（深色道具才看得清）、空口袋只有袋口弧線＋淡繡星、數量是金扣子徽章（1 件不顯示）、剛拿到的那格換奶油白襯裡＋冒星 1.2 秒（仍有 Bump）。
  - ⚠️ 布條不用九宮格拉伸（針腳拉長會變實線）。⚠️ `hud-bar`／`slot*` 圖與 class 沒動 —— 上方工具列、Toast、托盤、背包面板、翻書目錄還在用。`UiSkin` 關閉時退回舊的 `.hud-bar＋.slot`。
- **路人不穿牆**：新增 `Core/TownNav.cs`（戶外 NPC 用的 32px 格 A*；障礙沿用 `Obstacles`〔新增唯讀的 `IsFree(p, radius)`〕含河與招牌柱，NPC 半徑 12；
  八向不切角、邊上多驗取樣點；拉直路徑；城鎮偏好走路面〔草地代價 ×2〕；`Obstacles.Version` 變了才重建；只在挑目的地時算、一幀最多一人、緩衝重用；
  不連通就換目的地，**絕不退回直線**）。城鎮村民（`TownFolk`）與糖果鎮小動物（`CandyTown`）共用；糖果鎮另有只擋 NPC 的 `TownNav.Avoid`（中央噴泉、站樁 NPC）。
  城鎮吸附了 8 個站不住的路點（其中 4 個原本在店裡）。後花園沒有障礙資料：`GardenData.FenceWalk` 重量成石板路中線的有序折線，`TownFolk` 用 polyline 模式只沿相鄰點走。
  店裡顧客：`ShopPath.Find` 找不到路回 null（跳過商品／離開）；站位用更嚴的 `ShopPath.Standable`、亂數偏移後再驗一次；每 0.25 秒比擺設指紋，家具被搬就重算路／換位／離開。
  離線檢查 `python tools/check_npc_paths.py`（約 1 分鐘）：城鎮 5995 對路點全連通、路徑取樣落在障礙裡 0 次；F3 會多畫 NPC 路徑的綠線。
  - 仍會穿過：村民彼此與女巫（維持現況）、沒有落地範圍的小裝飾與城鎮站樁 NPC；後花園底圖換了要重量。
- **路人重畫** `tools/gen_villager_art.py` → `Resources/villagers8/`（11 張，檔名同舊圖；每格邏輯 28×36、×3＝84×108，一張 336×324＝4 幀 × 下／側〔朝左〕／上；
  鞋底一律在格子底邊往上 3px；共用 Q 版骨架＋耳朵／吻部／尾巴／帽子／衣服／翅膀／手持物的組件）。開關 `GameArt.UsePixelVillagers`，缺圖退回舊圖；`--restore` 還原。
  新圖在 `VillagerAnim.Scale` 之上再乘 `GameArt.PixelVillagerScale`（1.1；大人約 96～99px，女巫 93px）；影子寬打八折、對準鞋底。
  舊圖怪的原因：AI 厚塗風、11 張尺寸比例各異、均分切格切到隔壁幀的殘影、走路幀不連貫。
  - ⚠️ `GameArt.PixelVillagerScale` 與產生器的 `GAME_SCALE` 要一起改。`broomwitch` 是騎掃帚低空飄（腳不著地、站著也在飄）。
  - 頭像（`portraits/`）沒重畫：fox／hedgehog／rabbit／witch 同名但造型對不上；7 位有走路圖沒頭像、8 張頭像沒走路圖。
- 這一晚子代理中途撞到用量上限被中斷一次，額度恢復後用 SendMessage 續跑（中斷時沒有留下半成品）。

### 還沒做

- 凌晨這一輪待實機確認：腰包（新圖匯入後接縫與針腳對不對得上、徽章數字、冒星、12→15→18 格）；城鎮村民過河走橋、不站進店裡；糖果鎮小動物繞噴泉；
  後花園路人待在柵欄外；佈置時把貨架拖到客人腳下；新路人跟女巫並排的大小胖瘦（調 `PixelVillagerScale`）、腳底與影子、往右走的翻面、泡泡高度、夜晚看不看得清
- 頭像重畫成 8-bit 並跟走路圖對上（使用者還沒要求，但落差明顯）
- 深夜這一輪待實機確認：翻書（新圖第一次匯入有沒有變色塊、翻頁動畫與狂按、目錄格、深色成品在紫格裡看不看得清）；城鎮招牌（按 P 翻面、遮擋、夜晚的字）；
  任務簿／每日結算／對話框（有無頭像、有無名字、選項）／公告板／Toast／托盤／工具列四種狀態；`UiSkin.Enabled=false` 能不能退回
- 這一輪全部待實機確認：`skin8` 的 PPU 是 100、九宮格是細框不是色塊；各面板的捲軸把手位置、按鈕 hover／按下／停用、字的粗細；
  沒出 mockup 的雜貨鋪／家具頁／手札／衣櫃／設定／選種子；下排背包列升到 15／18 格會不會換行；工具列按鈕與 P 鍵、點按鈕人不會走、
  點過按鈕按 Space 不會關店；開店中按 R 的回饋；佈置模式四種狀態的圖示列與圖示看不看得懂；風鈴聲；關店後不來客、離店不成交
- 佈置提示／商品換位／顧客改版**都還沒實機看過**：HUD「R 佈置店面」與第一次進店的 Toast；佈置模式的格線、紅綠預覽、頭上標籤看不看得清楚；
  拖商品換位／交換／圈外回原位／Esc 還原／重進遊戲後位置還在；貨架翻面與收回再擺回後商品的位置；舊存檔的 uid 遷移；
  客人三三兩兩進門、結伴對話、泡泡不互蓋不鏡像、長句拆兩行；客人繞過貨架、門口被圍死時不卡住；客人與女巫在貨架前後的排序；
  開面板時客人與泡泡暫停；打烊後不再進客；升級面板的「同時 N 人」
- 新道具圖／新貨架／商品陳列**都只離線看過預覽**：`items8` 匯入有沒有套到 Point；各 UI 格子裡圖示大小；顧客泡泡與採集飄字；
  澆水的水滴；商品有沒有站在層板上、翻面貨架的商品順序；女巫在貨架前後跟商品的遮擋；佈置拖曳時商品跟著走；賣出／上下架即時更新
- 店裡的碰撞與排序**只離線檢查過、還沒實機看過**：進店 Console 的 `[Obstacles] shop` 摘要；F3 的框有沒有對齊磚縫；
  貨架圖比佔地寬很多，女巫疊到圖邊的觀感；在左牆貨架／右牆翻面貨架／販售桌前後繞一圈看排序、尖角會不會跳；
  佈置到站進家具裡能不能走出來；從藥水室／後花園進店的落點會不會在家具裡（離線只驗了 `PlayerSpawn`）；藥水室手感有沒有變
- 顧客沒有碰撞、照 −y 排：貨架擋在路線上會穿過去，靠近長貨架時可能排錯（未處理）
- 後花園**刻意不做花圃碰撞**：E 是作用在最近的那塊，花圃擋路的話開滿後中間幾塊永遠不是最近的。草地是菱形但仍夾 `WalkArea` 矩形
- 城鎮的河**只離線檢查過、還沒實機走過**：沿岸滑動會不會卡在 16px 鋸齒的凹角；停在岸邊時腳的位置；三座橋各走一遍
  （中橋最窄、西端橋面有一叢灌木）；F3 的水域框跟河對不對得上；點地走路點到對岸會推著河岸 0.35 秒後停下（不做尋路）
- 新地面三張都**已實機確認**顯示正確（森林是修掉 Tiled→Simple 放大之後），還沒看過的只剩：
  夜晚 `DayNightTint` 色調下的樣子、網頁版的建置大小

- 音效**只編過、還沒實機聽過**：音量平衡、腳步密度（`PlayerController.StepStride`）都是憑估算的
- UI 動效**只編過、還沒實機看過**：進場有沒有真的播（陷阱 2）、時間與幅度順不順眼
  （`AnimStyle.uss` 調時間與幅度，關閉時間改長要連 `UIAnim.HideDelayMs` 一起改）
- 背景音樂與設定面板**只編過、還沒實機聽過／看過**：四首的音量平衡（跟音效比會不會太大聲）、循環接點聽不聽得出來、
  交叉淡變 1.2 秒順不順、Vorbis 匯入設定有沒有套上（看 bgm 資料夾裡音檔的 Inspector）、網頁版第一次互動後
  有沒有出聲；設定面板的版面（一列塞得下嗎）、「設定 (O)」點了人會不會走
  （`CornerHud.BlocksWorldClick` 的座標換算）
- 新版 `day` 與兩欄衣櫃**只編過、還沒實機聽過／看過**：day 夠不夠「西式小鎮」、刺點與 bass 的音量平衡；
  衣櫃的高度有沒有被 88% 截掉、說明換行、立繪在 720p（縮放 1.125）下像素邊緣是否可接受
- 碰撞與地圖邊緣**只編過、還沒實機玩過**（離線檢查過可達性與預覽圖）：撞樹幹停下、斜推會不會順順地繞過去；
  建築深到圖高一半會不會太深（屋頂那半繞到後面時人整個被蓋住）；城鎮小屋從正面走到拱門前的石階會不會自動進店
  （門已移到真正的門口、牆上不再挖通道）、門口光圈會不會偏低（可把 `CottageDoor.y` 從 -135 往上調，最多到 -128）；
  點地走路撞到東西 0.35 秒後停下來的手感；邊界出口（森林東／北、城鎮西、糖果鎮南）推過去照常換場景、
  上緣光圈的新位置；女巫改成照腳底排序後，跟樹、灌木、村民、門口花台的前後關係；F3 的線框看不看得清楚；
  編輯器 Console 的 `[Obstacles]` 摘要裡走不到的互動點是不是 0
- 夜晚曲 `night` 重寫後**還沒有實機聽過的回饋**：使用者說「森林的歌像武俠」時遊戲內是晚上（存檔 21:28），
  聽到的其實是舊的 night；`day` 與 `night` 都已改成西式大調，兩首都待確認
- 森林左右與下緣的內縮（22／6）比烤圖那圈深色草叢窄，女巫走得進深色草裡；要不要加大待決定
- 魔法彈的正式美術（需要美術資源）
- `AwayShop`（離店營業）只編過、還沒實機玩過：上架 → 出門 → 回店看有沒有跳 Toast
