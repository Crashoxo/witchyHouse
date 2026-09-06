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

### 改完程式想先確認編得過
`bash tools/typecheck.sh` —— 用 Unity 內附的 Roslyn 離線編一次，不用開 Unity。

⚠️ **Unity 開著的時候專案是鎖住的**，`Unity.exe -batchmode -quit` 會直接以 exit code 1 結束、
log 只有 60 行也沒有任何錯誤訊息 —— 看起來很像「編過了」，其實根本沒編。

### 網頁版
`Witch Shop → 建置 → 網頁版（建好直接開瀏覽器）`。
第一次要 15～40 分鐘（IL2CPP 把 C# 翻成 C++ 再編成 WebAssembly）。

⚠️ **不能直接點兩下 `index.html`** —— 瀏覽器的 `file://` 擋掉 WebAssembly 的載入方式，畫面會全黑。一定要走伺服器。

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
│   └── DayNightTint / LampGlow / PortalGlow / CameraFollow / FloatAway
│
├── UI/        全部走 UI Toolkit
│   ├── CjkFont            中文字型（見第三節第 6 點）
│   ├── InventoryHud / ClockHud / CornerHud / Toast / SceneFade
│   ├── BagPanel / ShopManagePanel / BrewPanel / SeedPicker
│   ├── TownShopPanels     雜貨鋪 / 花店 / 糖果鎮商行
│   ├── QuestPanel / PlayerInfoPanel / WardrobePanel
│   ├── Dialogue / SleepOverlay / DaySummaryPanel / ShopRoomTray
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
  - 平衡旋鈕：`AwayShop.AwayRate`（1 ＝ 跟你站在店裡一樣快；調低就是沒人顧店比較慢）。

### 還沒做

- 魔法彈的正式美術（需要美術資源）
