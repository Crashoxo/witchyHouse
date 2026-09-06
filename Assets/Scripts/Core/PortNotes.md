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

## 資源

- 路徑一律**小寫** `ui/`、`items/`⋯ —— `AssetDatabase` 的路徑區分大小寫，
  但 Windows 檔名不分，寫錯會靜默掉進別的資料夾。
- `Resources.Load` 是同步的，`GameArt` 的 `Ready`/`OnReady` 只是保留 API 形狀。

## UI

- **中文字型要用 `CjkFont`** —— UI Toolkit 預設字型沒有中文，而且不報錯。
- ⚠️ **新增中文字串之後要跑 `python tools/subset_font.py`** —— 專案裡的字型是子集化過的
  （只留掃得到的字），沒重跑的話新字會是豆腐，一樣不報錯。
- 字型裡**沒有** `✕`(U+2715)、`✔`(U+2714)；要打叉打勾用 `×`(U+00D7)、`✓`(U+2713)。
- 深色底配亮字、羊皮紙配深墨色。挑錯就是「東西沒顯示」。
- 建構失敗時 **`built` 旗標要保持 false**，不然 `Update()` 會每幀丟 NullReference。

## 場景

- 場景檔名沿用 Cocos 的：`main` / `town` / `shop` / `brew` / `garden` / `candy`。
- 新場景要 `SceneBuildUtil.Register()` 進 Build Settings，否則執行期 `LoadScene` 會丟錯。
- 各場景的子系統由 `PlayerController.Awake()` 依場景名喚起，不用改場景檔。

## 效能與生命週期

- **`Destroy()` 是延遲的**（該幀結束才刪）。每幀重畫的東西要**重複使用物件**，
  不要清空再重建 —— 新舊會疊在同一幀。
- 一個互動點吃一顆 E。兩個感應圈重疊時 Unity 不保證 `Update` 順序，會隨機觸發。
