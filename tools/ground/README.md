# 地面烘焙器（tools/bake_ground.py）

重新烤出三張戶外地圖的地面：森林（場景 `main`）、城鎮（`town`）、糖果鎮（`candy`）。
只用現有素材的色盤與原圖裡的路/河位置，全部程式產生；固定亂數種子，重跑結果一模一樣。

## 怎麼跑

```bash
python tools/bake_ground.py                       # 三張都烤（約 50 秒）
python tools/bake_ground.py town candy            # 只烤指定的（forest / town / candy）
python tools/bake_ground.py --preview <資料夾>     # 順便輸出「地面＋真實物件＋女巫」預覽
python tools/ground/compare.py <資料夾>            # 前後對照圖（整張縮圖、960×640 實際視野）
python tools/bake_ground.py --restore             # 還原：原圖蓋回去、刪掉新圖
```

需要 Python 3.9＋Pillow＋numpy。不用開 Unity。

## 產出與執行期怎麼接上

| 檔案 | 用途 |
|---|---|
| `Assets/Resources/art/ground/forest.png`（1408×896） | **遊戲實際用的**地面，半解析度 |
| `Assets/Resources/art/ground/town.png`（1600×1024） | 同上 |
| `Assets/Resources/art/ground/candy.png`（1600×1024） | 同上 |
| `Assets/Resources/art/ground-grass.png`（256×256） | 森林場景原本平鋪的草皮 → 換成城鎮草地風格的無縫像素草皮（編輯器裡看的墊底） |
| `Assets/Resources/art/town-ground.png`、`candy/candy-town.png`（3200×2048） | 同一份烘焙結果 ×2 放大（編輯器裡看的墊底） |

- **1 美術像素 ＝ 2 世界像素**（`common.py` 的 `ART_PX`，要跟 `BakedGround.ArtPixel` 一致）。
- `Assets/Scripts/Core/BakedGround.cs` 用 `[RuntimeInitializeOnLoadMethod]` 自己掛上
  `SceneManager.sceneLoaded`：場景一載入就把 `Ground` 的 sprite 換成 `art/ground/<map>`
  （PPU 0.5；drawMode 維持原樣 —— 森林是 Tiled，就把 size 設成新圖大小，**不能切成 Simple**，
  那會把地面放大 11×7 倍，見 PORTING.md 坑表），世界大小不變。換之前比對大小、換之後再驗
  中心與大小，不一樣就不換／整組還原、沿用原圖。
  不改場景檔、不改 PlayerController。
- 為什麼不直接蓋原檔就好：原圖 `.meta` 的 Max Size 是 **2048**，3200 寬的整張圖匯入時會被
  縮到 2048 再用 Point 拉回 3200，像素格子會糊、大小不一（原本城鎮/糖果鎮就是這樣顯示的）。
  半解析度 1600 寬的圖原尺寸匯入，格子銳利，記憶體也只有四分之一。
  原檔與它們的 `.meta` 都保留（只換了圖的內容），`.meta` 一個字都沒動。
- 新圖的 `.meta` 由 Unity 自動產生；`Editor/PixelArtImporter.cs` 會套 Point、無壓縮、
  不產 mipmap（路徑含 `/Resources/`）。預設 Max Size 2048 ≥ 1600，不會被縮。

## 每張圖的做法

共用（`grass.py`）：先算「色階索引」圖，斑塊（低頻雜訊量化）、樹蔭、地圖邊緣變深都是在
索引上加減，最後一次查色盤 → 只用色盤裡的顏色、沒有平滑漸層。草葉/三葉草是「相對色階」
圖章（樹蔭裡的草自動變暗），小花成群撒、石子零星撒。物件的落腳處（`objects.py`）從圖的
alpha 量出來，座標讀自 `Data/ForestLayout.cs`、`Data/TownLayout.cs`、`Data/Candy.cs`（只讀）。

- **森林**（`forest.py`）：**草地本體直接用城鎮那一套**（`import town`：同一個 `GRASS` 色盤、
  `STYLE` 斑塊參數、草葉/三葉草/花/石子，數量按面積換算，花再打八折），兩張地圖接起來是同一種草。
  森林感另外加：所有樹、灌木、樹籬、藥草叢、落葉堆腳下的橢圓接地暗色（外圈暗一階、中心暗兩階，
  往城鎮色盤下取階）；果樹下落果、花樹下落瓣、落葉堆旁散葉；四周一圈較深、草叢較密的邊緣
  （`edge_dark()`：寬度約 6～70 美術像素大幅起伏、內緣用草叢打散，東 y=0／北 x=0 出口留開口）。
  ⚠️ 想調森林的草，請改城鎮的 `STYLE`/`GRASS` 再兩張一起重烤，不要讓兩張分家。
  （歷程：第一版自己一套較暗的色盤＋兩階暗斑塊＋泥土小徑，像迷彩被退件；極簡單色版太平。）
- **城鎮**（`town.py`＋`townmask.py`）：從原圖以 32×32 為一格判讀出石板街/廣場鋪石/泥土/水
  （`python tools/ground/townmask.py` 可印出格子地圖），把直角修圓（模糊後取 0.5 等高線：
  直邊位置不變、只有角變圓），石頭用 Voronoi 畫成一顆顆圓石（`materials.stones`），
  廣場是較大較亮的鋪石＋兩道路緣石；泥土路邊緣較鬆散；河岸線修彎、加沙岸、深淺三階水色、
  波紋、岸邊陰影；橋（石頭跨過水）上下加欄杆邊、橋下水面陰影；噴泉腳下鋪一圈圓形鋪石；
  建築/灌木/路燈腳下壓暗。路與河的位置都照原圖（`Data/TownRoads.cs` 的村民路點都在路內）。
- **糖果鎮**（`candy.py`）：薄荷綠草地、粉白淡藍小花、彩色糖粒與小軟糖；十字黑巧克力磚路
  （磚縫對齊原本的路邊）修圓角，外圍一圈奶油糖霜（下緣往下滴）；廣場內圈牛奶巧克力，
  正中央一個薄荷糖漩渦地磚。

## 參數在哪調

| 想調什麼 | 位置 |
|---|---|
| 色盤 | 各檔最上面的 `GRASS` / `COBBLE` / `PAVER` / `DIRT` / `WATER` / `DARK_CHOCO`… |
| 草地斑塊大小與深淺 | `STYLE`（`patch_sigma`、`patch_steps`） |
| 草葉、花、石子數量 | `bake()` 裡 `add_tufts` / `add_flowers` / `add_pebbles` 的數量參數 |
| 路角圓的程度 | `round_mask(..., r, ...)` 的 `r`（美術像素） |
| 森林的樹蔭／四周深色邊緣 | `forest.py` 的 `bake()`（橢圓大小）、`edge_dark()`（邊緣寬度與出口） |
| 亂數種子 | 各檔的 `SEED` |

改完重跑 `bake_ground.py`，Unity 回到前景時會自動重新匯入。

## 還原

```bash
python tools/bake_ground.py --restore
```
會把 `tools/ground/orig/` 的三張原圖蓋回去，並刪掉 `Assets/Resources/art/ground/*.png`（含
`.meta`）。`BakedGround.cs` 找不到圖時只會印警告、沿用原圖；要完全移除就把它刪掉
（連同 `.meta`）。
