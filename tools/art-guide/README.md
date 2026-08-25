# 店面美術規格（PixelLab）

用 [PixelLab](https://www.pixellab.ai/) 出圖取代程式生的 placeholder。
這個資料夾裡的圖是**參考框**，不是成品 —— 拿去當 init image / 對位用。

參考框要重生：`D:/python/python.exe tools/gen_art_guides.py`

---

## 0. 兩條總規則

**規則一：畫「來源解析度」，不是畫面上的大小。**
遊戲裡一格地磚是 64×32，但素材**畫 32×16**，程式會 ×2 NEAREST 放大。
理由：PixelLab 的等距磚原生就出 32×32，×2 之後的像素大小跟主角（原生 64px 高、
`WITCH_SCALE=1.6`）接近，整體才像同一款遊戲。

**規則二：家具圖的正下方中央＝佔地的「前角」。**
（前角＝佔地最靠畫面下方那一格的下角，參考框上的青色十字。）
節點錨點是 (0.5, 0)、擺在 `frontCorner()` 算出來的座標，這樣 YSort 的前後遮擋才會對。

---

## 1. 地板磚（已完成，換磚照這個流程）

> **地板 ＝ 磚原樣平鋪，不做任何後製**（使用者要的就是磚本來的樣子）。
>
> ⚠️ **同一張 sheet 的 16 格差很多，一定要平鋪比較過再挑**。
> 多數格子平鋪起來像編織紋或菱形棉被格（每塊磚自己中間亮邊緣暗，重複就成了格紋）；
> 只有少數幾格的板紋會**跨格接成連續的斜向長條**，那種才像木地板。
> 現在用的是來源格 **(0,0)**。挑法：切三四格出來各自鋪滿一片看，選接得起來的那格。


PixelLab → **Maps → Tiles → Isometric → + Create tiles**

| 欄位 | 值 |
|---|---|
| Tile shape | `Isometric` |
| Tile size | **`32px`** |
| View angle | **`28° · high top-down`** |
| Thickness | **`0%`**（有厚度的話每格會凸一塊） |
| Top/bottom pixels | `4px` |
| Outline mode | 無描邊 |

⚠️ **提示詞決定成敗**。這個工具的說明寫著 "variations of it make organic-looking ground"
—— 隨便寫會得到一堆有機地形碎塊，鋪起來很吵。要強調整齊無縫：

```
seamless wooden plank floor, long straight parallel planks, uniform vintage oak,
tidy shop interior, simple clean texture, no debris
```

現在用的那批（`_pixellab-sheet-3-darkwood.png`，16 格全是完整菱形、乾淨的 16 色深紅棕）：

```
A cozy magical wooden plank floor made of rich dark wood
```

⚠️ 一次花 **20 個生成額度**，所以提示詞值得先想清楚。

**輸出是一張 131×131**＝4×4 個 32×32 的變化，中間 1px 縫。挑完整的那幾格丟給：

```
D:/python/python.exe tools/import_floor_tiles.py <下載的png> 0,0 1,2 2,1
```

它會切格 → 用精確的 2:1 菱形遮罩取樣 → **抹掉最外圈**（PixelLab 的磚下緣有立體暗邊，
不抹掉鋪滿會出現明顯格線）→ 存成 `tools/art-src/shop-room/floor-N.png`。

最後跑 `tools/gen_shop_room.py` 組成房間底圖（**用 `floor-1.png` 平鋪**，所以要當地板
的那格切成第一格）。想微調木頭顏色改 `FLOOR_TINT`（逐通道相乘，1.0 ＝原色不動）。

⚠️ **整間房間畫在半解析度 480×320 再 ×2 NEAREST 放大** —— 480×320 才是這批美術
真正的像素網格。直接在 960×640 畫線會出現 1px 細節，跟角色的像素大小對不上、看起來糊。

⚠️ 地板變深之後**牆要跟著調**（`PLASTER_*`／`WOOD_*`），不然亮米白牆會比地板還搶眼。

---

## 2. 家具

PixelLab → **Objects**

> **貨架已完成（2026-08-25）** —— 十六款貨架已進遊戲，見本節最後的「已完成：貨架」。
>
> ⚠️ **桌椅那三件（長木桌／展示台／花草長凳）已經從遊戲裡拿掉了** —— 還是木頭方塊，
> 使用者要求花店只賣貨架。畫好之後要**把 `data/shopRoom.ts` 的 `FURNITURE` 那三筆貼回去
> （註解裡留著原文）＋ 把 `DecorShopPanel` 的「家具」分頁加回來**（照「貨架」分頁抄）。
> `sale_table` 販售桌沒拿掉（開店必需、本來就買不到），所以店裡還看得到那塊方塊。

| 檔名 | 佔地 | 畫布（寬×高） |
|---|---|---|
| `sale_table.png` 販售桌 | 2×1 | **70×48** |
| `long_table.png` 長木桌 | 3×1 | **102×56** |
| `round_stand.png` 展示台 | 1×1 | **38×40** |
| `flower_bench.png` 花草長凳 | 2×1 | **70×44** |

規則：

1. **寬度照表**；高度想畫高可以往上加。
2. 底座貼合參考框上的粉紅菱形。**菱形會偏左、不置中，那是對的**
   （前角在正下方中央，2×1 的佔地自然往左伸）。
3. 背景透明，**投影不要超出菱形**（會蓋到隔壁格）。菱形內畫接地陰影可以。
4. 不要加中文標籤、外框、地板。
5. 光源統一**左上**。

`sale_table` 的檯面**要留空** —— 上架的商品由程式疊在檯面正中央。

提示詞範例：

```
isometric wooden shop counter, 2:1 isometric view, warm oak,
cozy witch flower shop, soft top-left light, transparent background, no text
```

### 匯入：`tools/import_furniture.py`

畫好丟進 `tools/art-src/furniture/<分類>/`，在 `SOURCES` 表加一行（id、來源檔、佔地
格數），然後：

```
D:/python/python.exe tools/import_furniture.py --contact
```

它做**三**件事：

1. **自己量出佔地前角**，把圖重新對位成「正下方中央＝前角」。
   —— 所以**畫的時候不必自己把前角對到畫布正中央**，人物置中畫就好；
   有腳的家具就算前角那一點根本沒畫到也量得出來。
   原理：等距投影下佔地菱形的兩條下緣斜率恰好是 ±1/2，
   所以「底部輪廓碰得到、又盡量高的那個 2:1 V 形」的頂點就是前角。
2. **⚠️⚠️ 投影校正（PixelLab 的 Objects 不是真 2:1 等距）** ——
   實測十六款貨架的兩個地面軸是**不對稱**的：往左上（寬度）斜率只有 **1/3（18.4°）**，
   往右上（深度）是 **1/2（26.6°）**。而地板兩邊都是嚴格 1/2 → 擺進房間會覺得「角度很怪」，
   右半邊對得上、左半邊太平。
   修法是一個仿射校正 **x 不動、`y' = 0.1x + 1.2y`**（`correction()` 由三個常數自動解出來），
   解出來剛好兩個地面軸都變 1/2，而且 **(0,1)→(0,1.2) 仍是垂直的**：
   垂直邊不會歪，只是整體高 1.2 倍；**佔地的水平寬度完全不變**，所以佔地格數不受影響。
   NEAREST 重取樣，像素維持銳利。想關掉比較就把 `FIX_PROJECTION` 設成 False。
   **往後任何從 PixelLab Objects 匯入的家具都要走這一步。**
3. **×2 NEAREST 放大**（美術畫在來源解析度一格 32×16，遊戲內是 64×32）。

`--contact` 會多輸出 `tools/art-guide/furniture-contact.png`，
每件底下畫出佔地菱形 —— **匯入完看一眼這張，確認菱形貼在底座下面**。

新家具還要做兩件事（貨架那次的流程）：

- `assets/scripts/data/shopRoom.ts` 的 `FURNITURE` 加一筆（id、名稱、佔地、售價、說明）。
  `GameArt` 是跑這份目錄去載圖的，加進去就會自動載。
- Cocos 沒開的話跑 `D:/python/python.exe tools/gen_furniture_metas.py` 補 `.meta`
  （已有的沿用原 uuid，新的排在 `a9000000-00XX`）。

### 已完成：貨架（2026-08-25）

十六款，來源在 `tools/art-src/furniture/shelf/`（PixelLab Objects，
`Size` 72、單方向、每款一張 72×72）。全部佔地 **1×2 格**，
**背板朝畫面左上、開口朝右下 → 靠左後牆（gx=0 那排）擺最好看**。

十六款**全部是新 id**（`shelf_*`）。我原本程式生的那塊「靠牆貨架」placeholder
(`wall_shelf`) 已經整個移除、花店也買不到了。
花店面板為貨架多開了一個「貨架」分頁（4×4 剛好一頁）。

---

## 3. 牆面材質

店裡看得到兩面後牆。**畫正面平視的一張直條，不要自己畫成斜的** ——
等距斜切由 `gen_shop_room.paste_wall()` 做（等距斜率剛好 2:1 ＝逐欄整數位移，
乾淨的像素階梯；用 affine 變形會插值，糊掉）。左牆會自動壓暗（`WALL_SHADE_L`）。

| 項目 | 值 |
|---|---|
| 檔名 | `wall-panel.png` |
| 尺寸 | **96 × 96**（遊戲內 ×2 ＝ 192×192，牆高 `WALL_H2 = 96`） |
| 視角 | **正面平視**（不是等距） |
| 內容 | 整面牆：下方裙板／護牆板 + 上方牆面 |
| 背景 | **不透明**（牆有透明處會露出相機底色） |

### PixelLab 怎麼設（Objects → Create Object，實際欄位）

| 欄位 | 值 |
|---|---|
| Directions | `1 Direction` |
| Style Reference Images | 上傳 `floor-1.png` 或現在的 `shop-room.png`（**是風格參考，不是構圖底圖**） |
| Size | **128px**（滑桿 32–256，**只有一個值＝正方形**） |
| View | 選**非** Top-Down 的平視選項（Side 之類） |
| Object Description | 見下面的提示詞 |
| Describe each item | 逐格寫不同材質，一次比完再挑 |

⚠️⚠️ **上傳 Style Reference 之後，Size 滑桿與 View 下拉會消失** —— 輸出尺寸改成
跟著參考圖走（欄位標題會寫 `1/4 at this size`）。`wall-style-ref.png` 是 128×128，
所以自動就是 128px。**要換輸出尺寸＝改那張參考圖的尺寸**，不是找滑桿。

⚠️ **格數跟著 Size 走**（不是固定 16）：48px → 16 張 4×4；**128px → 4 張 2×2**。
兩者都花 20–40 個生成額度。

⚠️ **選 128px**。牆高是 96，從 128 裡**裁**一段 96 出來是 1:1 不縮放，像素最乾淨
（importer 會自動裁**底部** 96 列＝保留裙板）。選 64px 反而要放大 1.5 倍，像素會不均勻。
代價是一次只有 4 種，所以那 4 格要寫成差異最大的四款。

⚠️ Objects 出的是「物件」＝主體可能浮在透明背景中間。importer 會自動去透明邊，
但如果生出來是一塊小小的牆而不是填滿畫布的材質，就改用備案（見下）。

### ⚠️ 實際結果：Objects 出的是「物件」不是「材質」（2026-08-18 做完的紀錄）

四張全都是**主體浮在透明背景中間**，而且各壞各的：

| 來源 | 結果 | 用途 |
|---|---|---|
| `faded_floral_wallpaper_above_d` | 玫瑰實心、**壁紙底色透明**；裙板實心 | **壁紙來源** |
| `dark_blue_wallpaper_with_tiny` | 壁紙整片沒生出來，**裙板最乾淨** | **裙板來源** |
| `aged_cream_plaster_above_dark` | 灰泥破破爛爛；裙板可用 | 備料 |
| `deep_muted_green_painted_panel` | 只有三個空框 | 失敗 |

**沒有白花額度** —— 拆開各取所需就好。量出來的關鍵數字：

* 三張的裙板都在 **y=80..127（高 48）**，位置一致
* 水平重複週期 **32**（128 剛好 4 個嵌板），壁紙也是 32
  → **32 寬的一片就完美無縫平鋪，連 mirror/blend 都不用**
* 壁紙底色透明 → 底色由我們指定（`compose_wall.py` 的 `GROUND`，現在是灰藍）

### 匯入

素材下載後放 `tools/art-src/shop-room/wall-src/`（來源已收進 repo），然後：

```
D:/python/python.exe tools/compose_wall.py     # 拆壁紙+裙板、配底色、組成 32x96
D:/python/python.exe tools/gen_shop_room.py
```

`compose_wall.py` 會自動量裙板高度與重複週期並印出來，換新素材不用改常數；
要換的通常只有 `PAPER_SRC` / `WAINS_SRC` / `GROUND`。

**如果哪天拿到的是真正滿版的牆面材質**（不是物件），那就走比較簡單的
`tools/import_wall.py`（校高度／mirror／blend／裁底部 96 列）。

### 提示詞

```
seamless vintage wallpaper wall with dark wood wainscoting panel at the bottom,
cozy witch shop interior, front view flat texture, warm muted tones,
low contrast, even lighting, no objects
```

尾巴那幾個字是在擋「重複時會露餡」的坑，別刪：
**`even lighting`**（畫了明暗漸層，重複之後會變成一排規律亮點）、
**`no objects`**（窗戶／掛畫／壁燈畫進牆裡，會變成每 192px 就有一扇窗；那些是第 4 節的獨立裝飾）、
**`low contrast`**（細節多在 96px 上會糊成雜訊）。

### 備案

Objects 出來不理想的話，Docs 的 Map 分類下有 **Create texture** —— 專門生材質、
有 init image 與鎖色盤，缺點是**沒有尺寸選項**，官方定位是拿來餵 Create Tileset 的。

⚠️ **牆不能是畫面上最搶眼的東西**。之前那面亮米白牆就是敗在這 —— 它比深紅棕地板亮太多，
一進店眼睛先看到牆。目標是**中間調、低對比、低彩度**，讓角色與商品是最跳的。
牆不一定要比地板暗，但別亮太多；`palette.png` 裡有現在房間與主角的常用色可以鎖色。

---

## 4. 牆上裝飾（之後）

窗戶、掛畫、壁燈、乾燥花束、藥草串……

**畫正面平視就好**，不用自己畫成斜的 —— 等距斜切由程式做（2:1 整數斜切，
每往右 2px 往下 1px，是乾淨的階梯不會糊）。

---

## 5. 通用設定與交檔

* 背景：**transparent / no background**
* Outline：`selective outline`（等距家具全黑硬描邊會很重）
* Shading `medium`、Detail `low`~`medium`（小尺寸上細節太多會糊成一團）
* 用參考框當 init image / reference，強度調低保留輪廓
* `palette.png` 是主角＋房間的常用色，鎖色用

成品放 `tools/art-src/shop-room/`，檔名照表。
生出來沒對齊沒關係 —— importer 會自動去背、trim、照佔地縮放、把底部中央對到前角。
