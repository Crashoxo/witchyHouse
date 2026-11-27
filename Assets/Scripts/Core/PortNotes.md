# 移植筆記（速查）

**完整紀錄在專案根目錄的 `PORTING.md`** —— 移植決策、踩過的坑、程式結構、
自動產生的資料怎麼重跑，都在那裡。這一張只留寫程式時最常要確認的幾條。

## 座標與尺寸

- **PPU = 1**：1 世界單位 ＝ 1 像素。原專案的座標全是手調的像素值，這樣才不用重算。
- **走圖切格一律走 `SheetSlicer.Cell()`** —— Cocos 的 rect 從左上算 y、Unity 從左下算，
  自己算會上下顛倒（畫面上「有在動、但動錯」，很難發現）。
- **腳底錨點**：Cocos 用錨點 `(0.5,0)`，Unity 的 Sprite 樞紐在正中心 →
  `SpriteRenderer` 掛在子物件上往上推半個身高，父物件的 position 才是落地點。
  **女巫走另一條路**：她的 `SpriteRenderer` 就掛在 `Player` 上、沒有那個子物件，
  所以是切圖時就把樞紐放到格子底邊（`SheetSlicer.Foot`）。結果一樣：`position` ＝ 落腳點。
  新增女巫的動作圖時**記得傳 `SheetSlicer.Foot`**，忘了她會整個往上跳半身高。
- **腳下影子**：`ShadowLayer.Follow(transform, 角色寬度, 落腳點偏移)`。重複呼叫＝更新尺寸，
  目標被銷毀會自動收掉。排序固定 -8500（地面之上、所有角色之下）。
- **場景 `contentSize` ≠ PNG 尺寸** ＝ 那個物件有隱含縮放，搬座標時要一起搬。
- **店裡「穿牆」有兩條，缺一不可**：圖的**底緣兩端要踩在地板菱形上**（`ShopRoom.RectOnFloor`，
  這條擋的是「架子埋進牆裡」），整張可見範圍不能凸出房間輪廓（`ShopRoom.Silhouette()`
  ＝地板＋兩面斜牆，跟 gen_shop_room.py 同一組點）。量的是 `Data.FurnitureBounds`
  的不透明範圍，不是整張 PNG（透明邊很大又不置中）。家具能不能放一律問 `RoomLayout.Check()`。

## 碰撞

- **戶外地圖（main/town/candy）、藥水室（brew）、店裡（shop）有、只擋玩家**：`Obstacles.Resolve(from, to)`，
  `PlayerController` 鍵盤與點地走路都過它。村民／顧客／小動物不套。8-bit 後花園（`GardenRoom.UsePixelGarden`）也是房間：
  可走範圍 `GardenRoomData.Walk`、樹與雨水桶由 `GardenRoom` 登記（`python tools/check_garden_walk.py`）；舊後花園只夾矩形。
  兩個房間的可走範圍是地板多邊形（藥水室 `BrewRoomLayout.Walk`、店裡 `ShopRoom.WalkFloor()`），家具由房間直接
  `Obstacles.AddPoly` 登記；店裡由 `ShopRoomView.Rebuild()` 每次重畫後 `ClearRegistered("shop_furniture")` 再整批登記，
  佔地每邊內縮 `ShopRoom.FurnitureInset`（一格走道才走得過，離線驗證 `python tools/check_shop_walk.py`）。
- 障礙是**掃場景裡的 SpriteRenderer**、用 sprite 名稱查 `Data.ArtFootprints`（`tools/gen_footprints.py` 量圖產生，
  不要手改）。形狀座標**相對圖片中心**、乘 scale。新圖沒進表 ＝ 不擋。執行期才擺出來的東西擺完要叫
  `Obstacles.MarkDirty()`（CandyTown 有）。
- 調範圍：改產生器的 `CATS` → 重跑 → `python tools/check_walkable.py <資料夾>` 看預覽與「走不到的互動點」。
  Python 檢查與 C# 讀的是同一份數值，不要在任一邊另寫常數。遊戲裡 `F3` 畫線框。
- **新增互動點**（按 E 的東西、門）要確定走得到：編輯器 Console 的 `[Obstacles]` 摘要會列出走不到的。
  門的觸發點被建築擋住時，`Obstacles` 會在那棟建築的範圍上挖一條 48px 的通道。建築的門最好放在範圍**底緣外面**
  （`doorX/doorY` 相對**圖片中心**，城鎮物件的 position 就是圖片中心），那樣不用挖。
- **防卡死**：在障礙裡時，往外走一律放行。改 `Resolve` 時不要拿掉這條。
- **藥水室自己擺的家具**（R 佈置，`HomeArrange`／`HomeFurnishings`／`HomePlacement`）登記成 `home_furnishing` 類別；
  規則與排序都在 `HomePlacement`（離線 `python tools/check_home_place.py`）。藥水室加新的互動點時，記得把它前面的站位加進 `HomePlacement.UseSpots`、
  可達性也要在 `HomePlacement.ReachOk` 補一行，不然擺家具可能把它圍起來。
- 戶外的邊緣內縮（上 64／左右 22／下 6）在 `ArtFootprints.Edge*`；邊界換場景是「推到內縮後的邊」觸發。
- 戶外的**排序看腳底 y**：女巫每幀設、物件在建障礙清單時改（城鎮建築例外，維持圖片中心；橋壓到 -8600）。

## 資源

- 路徑一律**小寫** `ui/`、`items/`⋯ —— `AssetDatabase` 的路徑區分大小寫，
  但 Windows 檔名不分，寫錯會靜默掉進別的資料夾。
- `Resources.Load` 是同步的，`GameArt` 的 `Ready`/`OnReady` 只是保留 API 形狀。
- 匯入的 **Max Size 是 2048**，超過的圖會被靜默縮小。戶外地面因此改成半解析度的
  `art/ground/*.png`，由 `BakedGround` 執行期以 PPU 0.5 換上（重烤：`python tools/bake_ground.py`）。

## UI

- **中文字型要用 `CjkFont`** —— UI Toolkit 預設字型沒有中文，而且不報錯。
- ⚠️ **新增中文字串之後要跑 `python tools/subset_font.py`** —— 專案裡的字型是子集化過的
  （只留掃得到的字），沒重跑的話新字會是豆腐，一樣不報錯。
- 字型裡**沒有** `✕`(U+2715)、`✔`(U+2714)；要打叉打勾用 `×`(U+00D7)、`✓`(U+2713)。
- 深色底配亮字、羊皮紙配深墨色。挑錯就是「東西沒顯示」。
- 建構失敗時 **`built` 旗標要保持 false**，不然 `Update()` 會每幀丟 NullReference。
- **新面板要有開關動效**：Build 時 `anim = UIAnim.Pop(root, panel, dim)`（貼邊的用 `SlideRight`／`SlideUp`），
  開關改成 `anim.Show()`／`anim.Hide()`，**「開著沒」一律看 `anim.IsOpen`、不要看 `root.style.display`**
  （關閉動畫期間 display 還是 Flex）。樣式表 helper 自己會掛。HUD 數字彈一下：`UIAnim.Bump(元素)`。
- **同一顆鍵開關的面板**（Q、Tab/I）：`Update` 裡跳過 `anim.OpenedThisFrame`、`Open()` 擋掉
  `anim.ClosedThisFrame` —— 開在 PlayerController、關在面板，Unity 不保證誰先跑。

## 音效

- **`Sfx.Play("名字")`** 一行就響，檔案在 `Resources/audio/名字.wav`，找不到會靜默略過。
  掛在**事件真正發生的那一處**，不要掛在讀檔／批次會呼叫到的底層（`Inventory.Add`、`CompleteSale`⋯）。
- 新面板：Build 時 `Sfx.BindClicks(root)`（全部按鈕的 click 音），`Open()`/`Close()` 各一行
  `Sfx.Play("ui-open")` / `Sfx.Play("ui-close")`。
- 新音效：在 `tools/gen_sfx.py` 的 `SOUNDS` 表加一支、重跑；或直接丟一個同名音檔進 `Resources/audio/`。
- **背景音樂**是 `Bgm` 自己依場景＋日夜挑的，呼叫端什麼都不用做。選曲規則在 **`Bgm.Choose()`**；
  新曲子：`tools/gen_bgm.py` 的 `SONGS` 表加一首重跑，或丟一個同名音檔進 `Resources/audio/bgm/`
  （`Editor/BgmImporter` 會自動壓成 Vorbis），再到 `Choose()` 指派給場景。正式音樂要自己做好循環點。
- 音量／靜音都在 `Sfx`（`Volume`＝音效、`MusicVolume`＝音樂、`Muted` 兩者一起），變了發 `Sfx.Changed`；
  介面是 `UI/SettingsPanel`（O 鍵）。音量 setter 寫檔有防抖，**不要**在別處每幀 set。

## 場景

- 場景檔名沿用 Cocos 的：`main` / `town` / `shop` / `brew` / `garden` / `candy`。
- 新場景要 `SceneBuildUtil.Register()` 進 Build Settings，否則執行期 `LoadScene` 會丟錯。
- 各場景的子系統由 `PlayerController.Awake()` 依場景名喚起，不用改場景檔。

## 效能與生命週期

- **`Destroy()` 是延遲的**（該幀結束才刪）。每幀重畫的東西要**重複使用物件**，
  不要清空再重建 —— 新舊會疊在同一幀。
- 一個互動點吃一顆 E。兩個感應圈重疊時 Unity 不保證 `Update` 順序，會隨機觸發。
