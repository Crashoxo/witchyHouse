# 城鎮美術規格（PixelLab）

> ⚠️ **城鎮是俯視角（top-down），不是店裡那種等距（isometric）。**
> `README.md` 第 2 節家具那套「前角在正下方中央 + 2:1 投影校正」**不適用**這裡，別照抄。
> 城鎮的規則單純很多：**圖的正下方中央＝落腳點**（節點錨點 (0.5,0)，YSort 靠這個排前後）。

---

## 0. 尺寸換算（先把這張表記起來）

設計解析度 960×640（fitHeight），所以量到的 px 就是玩家看到的 px。

| | 你在 PixelLab 畫 | 遊戲內（×2 NEAREST） |
|---|---|---|
| 一格地磚 | **32 × 32** | 64 × 64 |
| 一個畫面 | 15 × 10 格 | 960 × 640 |
| 整個城鎮 | **50 × 32 格** | 3200 × 2048 |
| 主角（已完成） | 64px 高 | 106px ≈ **1.65 格** |

比例參考：星露谷農夫也差不多是 1.75 格高。所以「主角約 1.6 格」就是對的。

⚠️ **一律畫來源解析度，程式幫你 ×2。** 直接畫 64px 的磚會讓像素比主角細一半，
擺在一起就露餡。這跟店裡地板同一條規則。

---

## 1. 總共要出幾批（照這個順序做）

| 批次 | 內容 | PixelLab 分頁 | Size | 約略額度 |
|---|---|---|---|---|
| 1 | 地面磚 ×4：草地／泥土路／石板街／溪流 | Maps → Tiles → **Square top-down** | 32px | 20 × 4 = **80** |
| 2 | 六棟店鋪 | **Objects** | 192px | 2–3 批 × 20–40 |
| 3 | 景物：噴泉／拱門／路燈／柵欄／花台／灌木 | **Objects** | 64–128px | 1–2 批 |

**先做第 1 批就好。** 地面佔畫面面積最大，換掉之後整體感覺馬上不一樣，
而且它是後面兩批的風格基準（房子要拿地磚當 Style Reference，顏色才會是同一個世界）。

---

## 2. 第一批：地面磚 ✅ 草地已完成（2026-08-26）

PixelLab → **Maps → Tiles → Square top-down → + Create tiles**

### 設定（實測確認過，四種地形都要一模一樣）

| 欄位 | 值 |
|---|---|
| Tile shape | **`Square top-down`**（不是 Isometric，那是店裡地板用的） |
| Tile size | **`32px`** |
| **View angle** | **`90° · top-down`（滑桿拉到最右）** |
| **Thickness** | **`0%`（滑桿拉到最左）** |
| Outline mode | **`No outline`** |

⚠️⚠️ **`Shape Controls` 那三個滑桿選了 Square top-down 之後不會消失**，而且預設停在
`28° / 10%` —— 那是等距用的。不改的話出來是「斜著看的板子」：上面被垂直壓扁、
下緣還多一條暗色正面厚度，**鋪滿就是滿滿的格線**。
判斷法：看 Shape Controls 的預覽縮圖，**要是完整的正方形**，不是有前緣的板子。

⚠️ 四種地形一定要用**同一組** Shape Controls，不然彼此的透視角度對不上。

### ⚠️⚠️ 提示詞：正面描述 > 負面排除（這是最重要的一條）

**我第一次寫的（失敗）** —— 整句都在講「不要什麼」：

```
seamless top-down grass ground, short even turf, uniform soft green, cozy storybook village,
simple clean texture, no flowers, no debris
```

結果 **16 格裡有 11 格幾乎是純色**，最好的一格只有 3 個顏色，其餘不是斜線就是網格花紋。
`simple clean texture` + `no debris` + `uniform` 三個詞疊起來，把細節整個壓光了。
（那組字是從店裡地板抄來的 —— **木地板要「乾淨」是對的，草地要的是「密而細」**。）

**使用者自己寫的（成功，就是現在用的這批）** —— 整句都在講「要什麼」，**一個否定詞都沒有**：

```
Detailed pixel art grass ground tile, rich organic texture, scattered tiny individual grass blades,
subtle two-tone green dithering and micro-clusters, high pixel density,
vibrant yet cozy RPG town aesthetic, seamless tileable
```

亮度從 134 → 95（深綠，角色跳得出來），一次就湊出「一主＋二變化＋一點綴」。

### 可以套用到任何地磚的公式

```
Detailed pixel art <這是什麼> tile, rich organic texture, <細節長什麼樣>,
subtle two-tone <顏色> dithering and micro-clusters, high pixel density,
vibrant yet cozy RPG town aesthetic, seamless tileable
```

三個關鍵字別漏：

| 關鍵字 | 作用 |
|---|---|
| **`dithering`** | 像素畫專有詞。`grass-base` 只有 2 色卻不死板，就是這個字換來的 |
| **`micro-clusters`** | 要到「小簇」而不是大團。散生小草叢就是它 |
| **`high pixel density`** | 直接對抗留白 |

其他心得：

* **不要寫 `no XXX`。** 想擋掉某個東西，改成「正面描述你要的替代品」
  （不想要石頭 → 寫 `fine soil speckles`，不要寫 `no rocks`）。
* `seamless tileable` 放句尾也有效 —— **位置不重要，有沒有寫才重要**。
* `vibrant yet cozy RPG town aesthetic` 這種「氣氛句」要固定不動，
  才是四種地形能拼在一起的原因。**換地形只換前半段，氣氛句照抄。**

### 輸出格式（實測）

**一張 131×131 ＝ 4×4 個 32×32、中間 1px 透明縫**（`x = c*33, y = r*33`），
跟等距那次同規格。一次 **20 額度**。

### 挑格：`tools/pick_tile.py`

```
D:/python/python.exe tools/pick_tile.py <下載的sheet.png> --name 草地
```

會在桌面產兩張圖：**16 格各鋪 3×3 的對照圖**（附接縫/格紋/色數分數）與
**前四名放進 480×320 遊戲比例配主角**。分數規則：接縫（左右/上下接得起來嗎）、
格紋（鋪 6×6 後有沒有週期性明暗帶，>1.0 就看得出來）、色數（越多層次越好）。

⚠️ **不要只挑一格。** 目標是「**一主 ＋ 二到三變化 ＋ 一點綴**」，
鋪的時候依比例隨機混、每格再隨機鏡射 —— 這樣兩萬格的草地才不會看出重複。
挑的時候四格的**亮度要接近**（差 1~2 以內），不然混起來會斑駁。

**已選定（存在 `tools/art-src/town/`）**：

| 檔名 | 來源格 | 內容 | 混鋪比例 |
|---|---|---|---|
| `grass-base.png` | (2,2) | 全平底色，2 色，接縫 0.00 格紋 0.03 | 主體 |
| `grass-var1.png` | (3,1) | 稀疏小草點，6 色 | 變化 |
| `grass-var2.png` | (1,0) | 散生小草叢，12 色 | 變化 |
| `grass-accent.png` | (1,3) | 三葉草叢，7 色（單獨鋪會看出格陣，只能少量散佈） | 點綴 |

## 3. 地圖佈局：你塗 `town-map.png`

`tools/art-guide/town-map.png` **50×32**，一個像素＝遊戲裡一格 64×64。
我已經從現在的城鎮生好底稿了，直接在上面塗改就好，不用從白紙開始。
（`town-map-guide.png` 是放大 12 倍＋格線＋粉紅框標出六棟房子位置的對照圖，只給你看的。）

用小畫家或 Aseprite 開，**鉛筆工具、關閉消除鋸齒**，用這五個顏色塗：

| 地形 | RGB | 現在佔比 |
|---|---|---|
| 草地 | `94,155,73` | 62.8% |
| 泥土路 | `150,111,68` | 15.5% |
| 石板街 | `150,150,158` | 11.0% |
| 磚道／廣場 | `176,124,104` | 7.9% |
| 溪流 | `60,120,190` | 2.8% |

⚠️ **只能用這五個顏色**，差一階都會被當成沒定義。塗完存回同一個檔名。

塗完丟給我，我跑 `tools/gen_town_ground.py`（等你的地磚到位我才寫得出來）
把它鋪成 3200×2048 的 `town-ground.png`，接邊、隨機鏡射避免重複花紋都由程式處理。
**之後想改路網＝改這張小圖重跑，十秒的事。**

⚠️ 已知取捨（你選的）：路面變成烤進底圖 → **在 Cocos 裡點不到、拖不動**
（1600 格不可能都當節點）。房子／噴泉／拱門／路燈這些有高度的東西**仍然是節點，照樣可以拖**。

---

## 4. 第二批：六棟店鋪

PixelLab → **Objects → Create Object**

| 欄位 | 值 |
|---|---|
| Directions | `1 Direction` |
| View | **`low top-down`**（不要選正上方 —— 要看得到正面牆與門，像星露谷那樣） |
| Size | **`192`**（大棟的）／`128`（scroll-shop 這種小的） |
| Style Reference | **等第 1 批地磚出好，拿草地＋石板那張當參考**，顏色才會同一個世界 |
| Object Description | **留空**，或寫一個你真的想要的物件 |
| Describe each item | 每棟一句，見下 |

各棟現在的大小（照現況換算，±1 格都可以，不用剛好）：

| 檔名 | 遊戲內 | ＝格數 | 你畫（來源） |
|---|---|---|---|
| `cottage-home.png` 小屋（進自己店的入口） | 389×295 | 6.1 × 4.6 | ~195×148 |
| `potion-shop.png` 藥水鋪（地精老闆，有任務） | 327×217 | 5.1 × 3.4 | ~164×109 |
| `flower-shop.png` 花店（買種子/裝飾/貨架） | 345×190 | 5.4 × 3.0 | ~173×95 |
| `general-store.png` 雜貨鋪（收購材料） | 264×162 | 4.1 × 2.5 | ~132×81 |
| `spell-shop.png` 法術鋪（魔法貓，有任務） | 291×175 | 4.5 × 2.7 | ~146×88 |
| `scroll-shop.png` 卷軸鋪（精靈書商，有任務） | 223×223 | 3.5 × 3.5 | ~112×112 |

Size 是單一值＝正方形畫布，房子畫在裡面就好，**四周留透明**。
匯入器會自動去透明邊、對位，**你不用自己把房子擺到畫布正中央**。

### ⚠️ 錨點約定（俯視角版，跟家具不一樣）

**圖的正下方中央＝房子的落腳點**（門口那條地面線）。
節點錨點是 (0.5,0)，YSort 依 `position.y` 排前後 —— 所以「圖的最底部」要剛好是
房子最前緣的地面，**不要在底下留一片影子或草地**，會讓遮擋算錯。
接地陰影可以畫，但要貼著牆腳、不要往下延伸。

### 提示詞

⚠️⚠️ **視角詞要寫進「每一句 item 描述」裡，不能只寫在上面那格。**
貨架那次實測過：Style Reference 只管風格（顏色／描邊／打光），
**角度是各自的描述決定的** —— 有寫的那批角度就對，沒寫的全歪。

```
cozy potion shop building, top-down view, front facade visible,
crooked timber walls, hanging sign with a bottle, warm lantern light,
storybook witch village, transparent background, no text, no ground
```

尾巴那幾個字別刪：`no text`（生成器很愛加標籤）、`no ground`（畫了地面會蓋掉我們的地磚）。

---

## 5. 第三批：景物

有高度、會遮住角色的東西。同樣 Objects、`low top-down`、每句都要帶 `top-down view`。

| 檔名 | 遊戲內 | Size 建議 |
|---|---|---|
| `fountain.png` 噴泉（中央廣場） | 209×209 | 128 |
| `arch.png` 城門拱門 | 364×348 | 192 |
| `lamp-post.png` 路燈（入夜會發光） | 32×138 | 64 |
| `fence-white.png` 白柵欄（一段） | 236×66 | 128 |
| `planter.png` 花台 | 200×46 | 64 |
| `bush-green/pink/white.png` 灌木 ×3 | ~60×60 | 64 |

路燈那支要留意：`LampGlow.ts` 會在入夜時在燈頭位置疊一圈暖黃光暈，
所以**燈頭畫在圖的上方中央附近**最好對位。

---

## 6. 通用的坑（前幾次踩出來的，別再踩）

1. **視角／投影是「提示詞」決定的，不是 Style Reference。**
   參考圖只管木色、描邊、打光那些風格。角度要自己每句都寫。
2. **`Object Description` 那格本身就是一個物件。** 想放風格句就留空，
   風格詞塞進每個 item 的描述裡 —— 否則它會照那句多生一個你不要的東西（浪費額度）。
3. **上傳 Style Reference 之後，`Size` 滑桿與 `View` 下拉會消失**，
   輸出尺寸改成跟著參考圖走。**要換尺寸＝換參考圖的尺寸。**
4. **額度是 `Size` 決定的，不是你填幾個描述。** 欄位底下那行會寫
   `Generates N frames at Xpx (n×n grid). Costs 20-40 generations.` —— 照它規劃批次，
   「只試一款」不會比較省。
5. **`Directions` 只有 1 與 8 兩個選項**（沒有 4）。房子景物用 1 就好。
6. **背景 transparent、不要中文標籤、不要外框、不要自帶地面。**
   （生成器很愛在下面加一條米色名牌，而且常跟主體連在一起，去背會很痛苦。）
7. **光源統一左上**，跟現有素材一致。
8. **來源檔一定要收進 repo**（`tools/art-src/town/`）。
   上一位女巫的來源放桌面，後來被刪光，匯出腳本再也重跑不了。

---

## 7. 交檔

下載的原始 sheet 丟 `tools/art-src/town/`，跟我說一聲，我負責：

* 寫 `tools/import_town_tiles.py`（切格／去暗邊／×2）與 `tools/gen_town_ground.py`（照你的小地圖鋪）
* 房子景物走 `tools/import_furniture.py` 的俯視角版（去背、trim、對到正下方中央）
* 補 `.meta`、換掉 town.scene 裡的引用、出 960×640 預覽圖給你看

---

## 8. 提示詞總表（直接複製用）

每一句都已經帶好視角詞與收尾的擋坑字，**整句貼進 `Describe each item` 的那一格**，不要刪尾巴。

### 地面磚（Maps → Tiles → Square top-down，32px／90°／0%／No outline）

**草地 —— 已完成，這是實際跑出好結果的那句（單獨跑一次，拿 16 格變化）：**

```
Detailed pixel art grass ground tile, rich organic texture, scattered tiny individual grass blades, subtle two-tone green dithering and micro-clusters, high pixel density, vibrant yet cozy RPG town aesthetic, seamless tileable
```

**⚠️ 編號寫法的實測結果（2026-08-26）**：`1) ... 2) ... 3) ... 4) ...` 出來是
**一直行一種地形 × 4 個變化**（不是說明寫的「各一格」），但**品質明顯不如單獨跑那次**：

| 行 | 地形 | 結果 |
|---|---|---|
| 1 | 泥土 | ✗ 第 1 列有烤進去的暗線（亮度 53 vs 88），左右還有 85→75 的漸層 → 鋪滿變規律亮暗帶 |
| 2 | 石板 | ✅ 四格都好，接得乾淨 → 已採用 |
| 3 | 磚道 | ✗ **只畫了磚縫線條，磚面是透明的**（不透明度僅 14~28%） |
| 4 | 水 | ✗ 左邊 2~3 欄整條透明；接縫明顯 |

**磚道那次直接砍掉** —— 廣場改用石板那行的米色格 `(1,1)`，跟主街的深灰 `(2,1)` 自然分色，
省一次生成。**已採用（存在 `tools/art-src/town/`）**：

| 檔名 | 來源格 | 用途 | 混鋪比例 |
|---|---|---|---|
| `cobble-1.png` | (2,1) | 石板街．深灰 | 70% |
| `cobble-2.png` | (0,1) | 石板街．亮灰 | 30% |
| `paver-1.png` | (1,1) | 廣場．米色磚 | 88% |
| `paver-2.png` | (3,1) | 廣場．大圓石點綴 | 12% |

**結論：一種地形單獨跑一次（拿 16 格挑），不要用編號擠在一次。**
編號只適合「這種地形不重要、隨便一格就好」的情況。

**泥土（待重跑，單獨一次）** —— 比上次多了 `even flat lighting`（專治明暗漸層與暗邊）：

```
Detailed pixel art packed dirt path tile, rich organic texture, fine soil grain with scattered tiny pebbles, subtle two-tone warm brown dithering and micro-clusters, high pixel density, even flat lighting across the whole tile, vibrant yet cozy RPG town aesthetic, seamless tileable
```

**水（待重跑，單獨一次）**：

```
Detailed pixel art shallow stream water tile, rich organic texture, fine gentle ripples spread evenly across the whole tile, subtle two-tone blue dithering and micro-clusters, high pixel density, even flat lighting across the whole tile, vibrant yet cozy RPG town aesthetic, seamless tileable
```

⚠️ **Style tiles 先不要傳。** 目前最好的一批（草地）就是**沒傳**的那次；傳了四張草地磚的那次
反而三行有問題。樣本數還不夠下定論，但顏色本來就可以寫進句子裡（`warm brown` / `blue`），
先照有效的那次做。

### 鋪地面：`tools/gen_town_ground.py`

```
D:/python/python.exe tools/gen_town_ground.py          # 只出預覽
D:/python/python.exe tools/gen_town_ground.py --apply  # 覆蓋 assets/art/town-ground.png
```

讀 `town-map.png` ＋ `art-src/town/` 的磚，依 `TERRAIN` 的比例隨機混、每格隨機鏡射，
路面疊在草地上、交界處隨機抖動避免 64px 硬直角。缺磚的地形先用純色頂著。

### 六棟店鋪（Objects → Create Object，1 Direction，View = low top-down）

⚠️ **Size 先設 192，然後看滑桿底下那行**（`Generates N frames at Xpx (n×n grid). Costs 20-40 generations.`）
—— **張數與花費是 Size 決定的**，照它顯示的數字規劃要分幾批。Style Reference 先不要傳。

```
Detailed pixel art cozy witch cottage, top-down RPG view with the front facade visible, thatched roof, timber walls, wooden door with a small porch, flower window boxes, subtle two-tone dithering, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```
```
Detailed pixel art cozy potion shop building, top-down RPG view with the front facade visible, crooked timber walls, hanging sign with a bottle, glowing lantern by the door, subtle two-tone dithering, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```
```
Detailed pixel art cozy flower shop building, top-down RPG view with the front facade visible, green glass roof, striped awning over a flower stall, planters along the wall, subtle two-tone dithering, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```
```
Detailed pixel art cozy general store building, top-down RPG view with the front facade visible, striped awning, crates and barrels beside the door, subtle two-tone dithering, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```
```
Detailed pixel art cozy spell shop building, top-down RPG view with the front facade visible, pointed tower roof, arched window with stained glass, subtle two-tone dithering, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```
```
Detailed pixel art cozy scroll and book shop, tall narrow timber house, top-down RPG view with the front facade visible, stacked scrolls in the window, subtle two-tone dithering, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```

### 景物（Objects，1 Direction，View = low top-down，Size 64~128）

```
Detailed pixel art stone village fountain, top-down RPG view with the front visible, round basin with flowing water, subtle two-tone dithering, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```
```
Detailed pixel art stone town gate archway, top-down RPG view with the front facade visible, weathered stone with climbing ivy, subtle two-tone dithering, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```
```
Detailed pixel art wrought iron street lamp post, top-down RPG view with the front visible, warm glowing lantern at the top, subtle two-tone dithering, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```
```
Detailed pixel art white picket fence section, top-down RPG view with the front visible, subtle two-tone dithering, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```
```
Detailed pixel art long wooden flower planter box, top-down RPG view with the front visible, blooming flowers, subtle two-tone dithering, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```
```
Detailed pixel art small round garden bush, top-down RPG view, dense leafy foliage, subtle two-tone green dithering and micro-clusters, high pixel density, vibrant yet cozy RPG town aesthetic, transparent background, no text
```

⚠️ 只留兩個否定詞 `transparent background` / `no text` —— 它們擋的是「多生一個不要的東西」
（米色名牌、自帶地面），跟「壓抑材質細節」的 `no debris` 不同類，可以留。
**描述質感的部分一律用正面詞。**

### 換句子的時候只改「中間那段」

每一句都是三段：

```
<這是什麼>, top-down view, front facade visible, <細節>, storybook witch village, transparent background, no text, no ground
   ↑ 你改這裡        ↑ 視角，不能刪            ↑ 你改這裡    ↑ 統一世界觀   ↑ 擋坑，不能刪
```

⚠️ 地磚那組沒有 `front facade visible`（地面沒有正面），改成 `seamless` 開頭＋
`simple clean texture, no debris` 收尾 —— **`seamless` 跟 `no debris` 是地磚的命脈**，
少了就會出一堆有機碎塊，鋪滿很吵。
