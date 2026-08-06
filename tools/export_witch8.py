# -*- coding: utf-8 -*-
"""
把使用者做的哥德女巫（PixelLab 匯出）打包成遊戲用的圖集。可重跑。

── 2026-08-07 換人 ──
主角換成新的一位（黑／暗紅哥德蘿莉、銀髮、紅眼、紅水晶木杖），來源改成
`tools/art-src/witch-v2/`（從 Downloads 的兩個資料夾複製進 repo —— 上一位女巫的
來源放在桌面，後來被刪掉就再也重跑不了，所以這次收進版控）。

來源
  art-src/witch-v2/walk/rotations                 8 方向站姿
  art-src/witch-v2/walk/animations/Walking/<dir>  走路 8 方向 ×8 幀
  art-src/witch-v2/run/animations/Running/<dir>   跑步 8 方向 ×8 幀
  art-src/witch-v2/cast/animations/Fireball/<dir> 施法 8 方向 ×6 幀
                                                  （**澆水／採集／摘花／種花全部共用這組** ——
                                                    新角色沒有蹲下的圖，使用者指定就用這組）

⚠️ 同一組動畫有時會匯出兩份方向（PixelLab 的重生成）：跑步的 north 取 `north-71d078af`
   （`north-f030d599` 整組是疊影壞圖）、施法的 north-west 取 `north-west-969deef6`
   （`north-west-fe5a5dbc` 每幀的帽子與身體都在跳）。

輸出（resources/witch8/）
  base.png    8 欄 × 25 列，格子大小一致：
                列 0       = 站姿，欄＝方向（south, SE, E, NE, N, NW, W, SW）
                列 1..8    = 走路，列 1+d ＝方向 d，欄＝幀
                列 9..16   = 跑步，列 9+d ＝方向 d，欄＝幀
                列 17..24  = 施法，列 17+d ＝方向 d，欄＝幀（0..5）

  `tools/legacy_pose.png` 是前一位（紫袍）女巫的施法＋蹲下 11 幀，**已經沒有人用了**，
  留著純粹是因為她的來源資料夾早就被刪掉，那是僅存的一份。
  green/brown/ivory.png    換裝造型（緋紅緞邊改色版）

  睡覺立繪 `sleep.png` / `*-sleep.png` **這支腳本不再產生**：新角色沒有躺床的圖，
  磁碟上那幾張還是前一位女巫的，先留著（GameArt 照樣載得到）。新圖來了再補。

152 張來源都是同一個 116×116 畫布，所以**全部用同一個裁切框**裁，
角色的腳底與左右中心自動保持對齊，不用逐格對位。
"""
import os, sys, colorsys
import numpy as np
from scipy import ndimage
from PIL import Image
sys.stdout.reconfigure(encoding='utf-8')

TOOLS = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(TOOLS, "art-src", "witch-v2")
DST = r"D:\Crash\witch-shop\assets\resources\witch8"
PORTRAITS = r"D:\Crash\witch-shop\assets\resources\portraits"
PREVIEW = TOOLS

DIRS = ["south", "south-east", "east", "north-east", "north", "north-west", "west", "south-west"]
RUN_DIRS = dict((d, d) for d in DIRS)
RUN_DIRS["north"] = "north-71d078af"             # 另一份 north-f030d599 是疊影壞圖
CAST_DIRS = dict((d, d) for d in DIRS)
CAST_DIRS["north-west"] = "north-west-969deef6"  # 另一份 north-west-fe5a5dbc 每幀都在跳

COLS = 8
ROW_WALK, ROW_RUN, ROW_CAST = 1, 9, 17
ROWS = 25
PAD = 1

def load(p):
    return Image.open(p).convert("RGBA")

def frames(folder):
    return [load(os.path.join(folder, f)) for f in sorted(os.listdir(folder)) if f.endswith(".png")]

rot = [load(os.path.join(SRC, "walk", "rotations", d + ".png")) for d in DIRS]
walk = [frames(os.path.join(SRC, "walk", "animations", "Walking", d)) for d in DIRS]
run = [frames(os.path.join(SRC, "run", "animations", "Running", RUN_DIRS[d])) for d in DIRS]
cast = [frames(os.path.join(SRC, "cast", "animations", "Fireball", CAST_DIRS[d])) for d in DIRS]
print(f"站姿 {len(rot)}／走路 {[len(v) for v in walk]}／跑步 {[len(v) for v in run]}"
      f"／施法 {[len(v) for v in cast]}")

# ── 共同裁切框（所有角色幀一起算，對齊才不會跑掉）──
allf = (rot + [im for v in walk for im in v] + [im for v in run for im in v]
        + [im for v in cast for im in v])
boxes = [im.getbbox() for im in allf]
W0, H0 = rot[0].size
x0 = max(0, min(b[0] for b in boxes) - PAD)
y0 = max(0, min(b[1] for b in boxes) - PAD)
x1 = min(W0, max(b[2] for b in boxes) + PAD)
y1 = min(H0, max(b[3] for b in boxes) + PAD)
CW, CH = x1 - x0, y1 - y0
foot = max(b[3] for b in boxes) - y0
body = foot - (min(b[1] for b in boxes) - y0)
print(f"格子 {CW}x{CH}（裁 {x0},{y0},{x1},{y1}）身高 {body}px、腳底 y={foot}（離底部 {CH-foot}px）")

def build_sheet():
    sh = Image.new("RGBA", (COLS * CW, ROWS * CH), (0, 0, 0, 0))
    def put(im, c, r):                      # 116x116 來源，用共同裁切框裁
        sh.paste(im.crop((x0, y0, x1, y1)), (c * CW, r * CH))
    for i, im in enumerate(rot):
        put(im, i, 0)
    for d, v in enumerate(walk):
        for c, im in enumerate(v):
            put(im, c, ROW_WALK + d)
    for d, v in enumerate(run):
        for c, im in enumerate(v):
            put(im, c, ROW_RUN + d)
    for d, v in enumerate(cast):
        for c, im in enumerate(v):
            put(im, c, ROW_CAST + d)
    return sh

base = build_sheet()

# ── 換裝：把緞邊的緋紅改色 ──
# 新角色是黑袍，舊那套「紫色轉色相」完全沒東西可轉。這張圖只有 18 個顏色，
# 紅色家族（H 335~12、S>0.35：帽帶、披風、緞帶、滾邊、寶石）佔 11%，改它最有效：
# 黑袍與黑描邊不動（描邊被染色像素畫會很髒），皮膚是暖色 H<50 也不在區間內。
#
# ⚠️ **眼睛與嘴巴用的是跟緞邊一模一樣的那幾個紅**（量過：#4f1727/#622635/#901e33/#f75e73
# 兩邊都出現），所以光看顏色分不出來，得靠位置與大小：**一整塊紅色，又小又碰得到皮膚
# ＝五官，整塊留原色**（使用者要求換衣服不要換眼睛顏色）。
# 只用「貼著皮膚」不夠 —— 眼睛外角那一格貼的是頭髮，會被漏掉染成綠色（踩過）；
# 只用「往外長 2 圈」則會連領口的滾邊一起保住。所以是「連通塊」＋大小上限。
RED_H = (335, 12)      # 跨過 0° 的區間：H>=335 或 H<=12
RED_S = 0.35
SKIN_H = (5, 50)       # 皮膚：暖色、不太飽和、夠亮
SKIN_S = (0.12, 0.75)
SKIN_V = 0.40
FACE_BLOB_MAX = 14     # 一隻眼睛/一張嘴大概幾格；緞邊那些塊都比這大很多

def _hsv(a):
    """RGBA uint8 陣列 → (H 0..360, S, V)，全部向量化。"""
    rgb = a[..., :3].astype(np.float32) / 255.0
    mx, mn = rgb.max(2), rgb.min(2)
    d = np.maximum(mx - mn, 1e-6)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(mx)
    m = mx == r; h[m] = ((g - b)[m] / d[m]) % 6
    m = (mx == g) & (mx != r); h[m] = ((b - r)[m] / d[m]) + 2
    m = (mx == b) & (mx != r) & (mx != g); h[m] = ((r - g)[m] / d[m]) + 4
    return h * 60, np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0), mx

def recolor(im, hue, sat_mul=1.0, val_mul=1.0):
    a = np.array(im).copy()
    h, s, v = _hsv(a)
    op = a[..., 3] > 8
    red = op & ((h >= RED_H[0]) | (h <= RED_H[1])) & (s > RED_S)
    skin = (op & (h > SKIN_H[0]) & (h < SKIN_H[1])
            & (s > SKIN_S[0]) & (s < SKIN_S[1]) & (v > SKIN_V))
    # 五官：紅色連通塊裡「又小又碰得到皮膚」的那些，整塊保留
    near_skin = ndimage.binary_dilation(skin, iterations=1)
    lab, n = ndimage.label(red, structure=np.ones((3, 3), bool))
    face = np.zeros_like(red)
    if n:
        sizes = ndimage.sum(red, lab, range(1, n + 1))
        touches = ndimage.sum(near_skin & red, lab, range(1, n + 1))
        keep = {i + 1 for i in range(n) if sizes[i] <= FACE_BLOB_MAX and touches[i] > 0}
        if keep:
            face = np.isin(lab, list(keep))
    target = red & ~face
    # 只有幾個紅色 → 查表換算，不必逐像素跑 colorsys
    for col in np.unique(a[target][:, :3], axis=0):
        _, ss, vv = colorsys.rgb_to_hsv(*(col / 255.0))
        nr, ng, nb = colorsys.hsv_to_rgb(hue / 360.0,
                                         min(1.0, ss * sat_mul), min(1.0, vv * val_mul))
        m = target & np.all(a[..., :3] == col, axis=2)
        a[m, 0], a[m, 1], a[m, 2] = round(nr * 255), round(ng * 255), round(nb * 255)
    return Image.fromarray(a)

# 對應 data/outfits.ts 既有的三個 id（存檔相容，只有顯示名稱換了）
OUTFITS = {
    'green': dict(hue=142, sat_mul=0.95, val_mul=1.05),   # 苔綠緞邊
    'brown': dict(hue=34,  sat_mul=0.95, val_mul=1.20),   # 琥珀緞邊
    'ivory': dict(hue=210, sat_mul=0.22, val_mul=1.45),   # 霜白緞邊
}

os.makedirs(DST, exist_ok=True)
def save(im, name):
    p = os.path.join(DST, name)
    im.quantize(colors=128, method=Image.FASTOCTREE).save(p, optimize=True)
    print(f"  {name:22s} {im.size[0]}x{im.size[1]}  {os.path.getsize(p)/1024:.0f}KB")

print("寫出：")
save(base, "base.png")
variants = {'': base}
for oid, kw in OUTFITS.items():
    v = recolor(base, **kw)
    variants[oid] = v
    save(v, f"{oid}.png")

# 衣櫃面板的造型立繪：各造型的正面站姿放大。面板 maxH 320 → 4×66=264 不會再被縮放。
PSCALE = 4
for oid, v in variants.items():
    cell = v.crop((0, 0, CW, CH))
    big = cell.resize((CW * PSCALE, CH * PSCALE), Image.NEAREST)
    name = f"outfit8-{oid or 'default'}.png"
    p = os.path.join(PORTRAITS, name)
    big.quantize(colors=128, method=Image.FASTOCTREE).save(p, optimize=True)
    print(f"  portraits/{name:24s} {big.size[0]}x{big.size[1]}  {os.path.getsize(p)/1024:.0f}KB")

# ── 預覽 ──
S = 3
base.resize((base.size[0] * S, base.size[1] * S), Image.NEAREST).save(os.path.join(PREVIEW, "witch8_sheet.png"))
strip = Image.new("RGBA", ((CW * 4 + 8) * 4, CH * 4 + 8), (40, 38, 48, 255))
for i, oid in enumerate([''] + list(OUTFITS)):
    cell = variants[oid].crop((0, 0, CW, CH))
    strip.alpha_composite(cell.resize((CW * 4, CH * 4), Image.NEAREST), (4 + i * (CW * 4 + 8), 4))
strip.save(os.path.join(PREVIEW, "witch8_outfits.png"))
print("預覽 -> witch8_sheet.png / witch8_outfits.png")
