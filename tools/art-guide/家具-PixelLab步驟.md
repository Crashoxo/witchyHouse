# 家具怎麼用 PixelLab 畫

規格總表在同資料夾的 `README.md` 第 2 節，這份是**照著做的操作步驟**。
每件家具流程完全一樣，只有畫布尺寸與提示詞不同。

> **貨架已經照這套流程做完了**（2026-08-25，十六款）——
> 出圖時 `Size` 選 72、單方向，每款一張 72×72，直接就能用。
> 剩下的是販售桌／長木桌／展示台／花草長凳四件。

---

## 1. 這張圖是什麼

| 項目 | 值 |
|---|---|
| 存到 | `tools/art-src/furniture/<分類>/`（貨架那批在 `furniture/shelf/`） |
| 佔地 | 見下面第 6 節的表 |
| 畫布 | **來源解析度**（程式 ×2 NEAREST 放大進遊戲，一格 32×16 → 64×32） |
| 背景 | 透明 |

**錨點不用你煩惱** —— `tools/import_furniture.py` 會自己量出佔地前角再重新對位，
所以照 PixelLab 的習慣把東西畫在畫布中間就好（有腳的家具就算前角那點沒畫到也量得出來）。

參考框在 `tools/art-guide/<檔名>-guide.png`（粉紅菱形＝它該踩的地），是給你自己看比例的。

⚠️ **參考框不要當 init image** —— 粉紅色會被生成器當成圖案畫進去（做牆的時候踩過）。

---

## 2. PixelLab 操作

`www.pixellab.ai` → 上方 nav 的 **Objects** → **Create Object**

| 欄位 | 選什麼 | 為什麼 |
|---|---|---|
| **Style Reference Images** | **留空** | ⚠️ 一上傳參考圖，**`Size` 滑桿與 `View` 下拉會整個消失**，輸出尺寸被鎖成參考圖的尺寸 |
| **Directions** | `1 Direction` | 家具只要一個角度 |
| **Size** | **72**（拉不到就 `64`） | 滑桿只有**一個值＝正方形**。要的 70×72 幾乎是正方形，72 剛好 1:1 不用縮放 |
| **View** | 等距／`high top-down`（跟地磚的 **28°** 同一款） | 要跟地板的 2:1 菱形對得上 |
| **Outline** | `selective outline` | 全黑硬描邊在這個尺寸會很重 |
| **Shading / Detail** | `medium` / `low`~`medium` | 70px 上塞太多細節會糊成一團 |

⚠️ **不要選 128px**。128 生出來的貨架約 115px 高，縮到 72＝縮 0.63 倍，
非整數倍縮放會把像素弄糊。72（或 64）才是 1:1 或接近 1:1。

⚠️ **格數跟著 Size 走**：48px → 16 張（4×4）、128px → 4 張（2×2），72 大概落在中間。
**一次花 20–40 個生成額度**，提示詞先想好再按。

---

## 3. 提示詞

```
isometric wooden wall shelf, tall shelving unit with a back panel,
2:1 isometric view, dark walnut wood, cozy witch flower shop interior,
empty shelves, soft top-left light, transparent background,
no floor, no text, no shadow outside the base
```

**這幾個字別刪**：

* `transparent background` —— 不然會附一塊背景底
* `no floor` —— Objects 很愛自己畫一塊地
* `empty shelves` —— 架上有東西會跟上架的商品打架
* `no shadow outside the base` —— 投影超出菱形會蓋到隔壁格

想更貼現在的店：`dark walnut wood` 換成 `rich dark red-brown wood`（配現在的深紅棕地板）。
色調參考 `tools/art-guide/palette.png`。

---

## 4. 挑圖的檢查清單

1. **底座是菱形不是方形** —— 方形底座擺進等距房間會歪
2. **背板往上長、主體別太寬** —— 佔地只有 1 格寬，太胖會壓到隔壁格
3. **沒有地板、沒有文字、沒有外框**
4. **投影貼在底座附近**，不要拖很長

不確定就下載兩三張都留著，組進房間比過再決定。

---

## 5. 畫完之後

1. 存進 `tools/art-src/furniture/<分類>/`
2. 跟我說一聲
3. 我負責：`tools/import_furniture.py` 的 `SOURCES` 加一行 → 它會**自己量出佔地前角、
   對位、×2 NEAREST 放大** → 輸出 `assets/resources/furniture/<id>.png`
   → 出對照圖（`--contact`）與房間預覽圖給你確認
4. 再把 `data/shopRoom.ts` 的 `FURNITURE` 加一筆（名稱／佔地／售價／說明），
   Cocos 沒開的話跑 `tools/gen_furniture_metas.py` 補 meta

**換掉既有的一件時**，記得從 `tools/gen_shop_room.py` 的 `PIECES` 把它刪掉，
否則誰重跑那支就會把手繪圖蓋回木頭方塊。

---

## 6. 其他四件的畫布尺寸

同樣流程，只換畫布與提示詞主體：

| 檔名 | 佔地 | 畫布 | Size 選 |
|---|---|---|---|
| `sale_table.png` 販售桌 | 2×1 | 70×48 | 72（**檯面要留空**，商品由程式疊上去） |
| `long_table.png` 長木桌 | 3×1 | 102×56 | 104 或 96 |
| `round_stand.png` 展示台 | 1×1 | 38×40 | 40 |
| `flower_bench.png` 花草長凳 | 2×1 | 70×44 | 72 |

畫布比 Size 小沒關係（Objects 本來就把主體浮在畫布中間），importer 會 trim 掉四周空白。
