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

### 重烤戶外地面
`python tools/bake_ground.py`（或只烤一張：`… forest` / `town` / `candy`）—— 離線重新產生森林／城鎮／
糖果鎮的地面圖（Pillow＋numpy、固定種子，重跑位元組相同），不用開 Unity。
`--preview <資料夾>` 順便輸出疊上物件與女巫的預覽；`--restore` 還原原圖。細節見 `tools/ground/README.md`
與第九節 2026-11-19「戶外地面重烤」。

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
| `M` | 音效靜音／開啟（記在存檔裡）|
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
│   └── ForestLayout / TownLayout / TownRoads   ← 自動產生，見第六節
│
├── Core/      遊戲邏輯
│   ├── GameArt            美術載入（分區、切走圖）
│   ├── SheetSlicer        走圖切格（含 rect 上下翻轉的修正）
│   ├── SaveManager        存檔中樞（版本 migration）
│   ├── TimeSystem         遊戲時間 ＋ TimeDriver
│   ├── PlayerController   移動、換場、各場景子系統的喚起點
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
│   ├── Sfx                音效（常駐、自帶 AudioListener；音檔在 Resources/audio/）
│   └── BakedGround        戶外地面換成烤好的半解析度圖（Resources/art/ground/，PPU 0.5）
│
├── UI/        全部走 UI Toolkit
│   ├── CjkFont            中文字型（見第三節第 6 點）
│   ├── InventoryHud / ClockHud / CornerHud / Toast / SceneFade
│   ├── BagPanel / ShopManagePanel / BrewPanel / SeedPicker
│   ├── TownShopPanels     雜貨鋪 / 花店 / 糖果鎮商行
│   ├── QuestPanel / PlayerInfoPanel / WardrobePanel
│   ├── Dialogue / SleepOverlay / DaySummaryPanel / ShopRoomTray
│   ├── UIAnim             面板開關動效 ＋ HUD 彈一下（樣式在 Resources/ui/AnimStyle.uss）
│   └── (UXML/USS 在 Assets/Resources/ui/)
│
└── Editor/    只在編輯器裡跑
    ├── PixelArtImporter   匯入時自動套像素風設定
    ├── *SceneBuilder      六個場景的產生器
    ├── SceneBuildUtil     共用工具 ＋ 重新登記所有場景
    ├── CreateUISettings / Setup2DProject
    ├── DevTools           測試用
    └── WebBuilder         網頁版建置
```

專案根目錄的 `tools/` 放離線工具：`typecheck.sh`（不開 Unity 編一次）、`subset_font.py`（中文字型子集化）、
`gen_furniture_bounds.py`（家具不透明範圍）、`gen_sfx.py`（合成 8-bit 音效）、
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

### 還沒做

- 新地面三張都**已實機確認**顯示正確（森林是修掉 Tiled→Simple 放大之後），還沒看過的只剩：
  夜晚 `DayNightTint` 色調下的樣子、網頁版的建置大小
- 網頁版（`docs/`）還是 2026-09-06 的舊建置，今天的改動尚未重建上線

- 音效**只編過、還沒實機聽過**：音量平衡、腳步密度（`PlayerController.StepStride`）都是憑估算的
- UI 動效**只編過、還沒實機看過**：進場有沒有真的播（陷阱 2）、時間與幅度順不順眼
  （`AnimStyle.uss` 調時間與幅度，關閉時間改長要連 `UIAnim.HideDelayMs` 一起改）
- 背景音樂（目前只有音效）、音量設定介面（`Sfx.Volume` 已經準備好）
- 魔法彈的正式美術（需要美術資源）
- `AwayShop`（離店營業）只編過、還沒實機玩過：上架 → 出門 → 回店看有沒有跳 Toast
