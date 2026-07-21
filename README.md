# witchyHouse（女巫小店）

Cocos Creator 3.8 製作的俯視角女巫採集 × 商店經營遊戲。到森林採集材料、回自己的店裡上架定價、煉製藥水賣給上門的動物顧客，順便接 NPC 任務、升級店鋪、佈置房間。

## 線上試玩

<https://crashoxo.github.io/witchyHouse/>

建議用桌機瀏覽器（鍵盤操作）。

## 操作

| 按鍵 | 功能 |
| --- | --- |
| WASD / 方向鍵 | 移動 |
| J / 空白鍵 | 施放魔法彈 |
| E | 採集、交談、進門、開商店／鍋爐 |
| Q | 開任務簿 |
| 空白鍵 / Enter | 對話推進 |
| Esc | 關閉視窗 |

走到地圖邊緣會切換場景：森林 → 右邊 → 城鎮 → 小屋 → 自己的店 → 右上 → 煉藥室。

## 內容

- **森林**：蘋果樹、莓果叢、香草圃等採集點，隨機產量與稀有掉落
- **城鎮**：石板街道與噴泉廣場、西側城門、東側溪流與三座橋；雜貨鋪收購材料、花店買裝飾、三位 NPC 提供任務鏈
- **自己的店**：材料／藥水上架定價，動物顧客上門購買，自由拖放佈置房間
- **煉藥室**：10 種配方、6 幀熬煮動畫
- **系統**：背包、金幣、存檔（localStorage）、店鋪升級、任務系統、對話系統

## 專案結構

```
assets/scripts/        遊戲腳本（TypeScript）
assets/art/            場景與角色美術
assets/art/town-tiles/ 城鎮路面與景物素材，由 town.scene 的節點直接引用
assets/resources/      執行期載入的圖（商品／顧客／頭像／裝飾／藥水／UI）
docs/                  web-mobile 建置產物，GitHub Pages 由此發佈
```

城鎮的街道在 `town.scene` 的 `World/Roads` 底下（不做前後遮擋，永遠畫在角色下方），
噴泉、城門、路燈等景物在 `World/Props` 底下（依 y 座標排序，會擋住角色）。
兩者都是一般節點，直接在編輯器裡拖曳就能調整。

## 建置

用 Cocos Creator 3.8.8 開啟專案後建置 web-mobile（4 個場景都要勾），或用命令列：

```
CocosCreator.exe --project <專案路徑> --build "configPath=<buildConfig.json>"
```

再把 `build/web-mobile` 的內容覆蓋到 `docs/`（保留 `.nojekyll`）並提交。
