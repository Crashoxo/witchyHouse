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
  art-src/witch-v2/cast/animations/Fireball/<dir> 施法 8 方向 ×6 幀（澆水也用這組）
  tools/legacy_pose.png                           前一位女巫的蹲下 5 幀
                                                  （新圖還沒做，先頂著；見下面 LEGACY 那段）

⚠️ 同一組動畫有時會匯出兩份方向（PixelLab 的重生成）：跑步的 north 取 `north-71d078af`
   （`north-f030d599` 整組是疊影壞圖）、施法的 north-west 取 `north-west-969deef6`
   （`north-west-fe5a5dbc` 每幀的帽子與身體都在跳）。

輸出（resources/witch8/）
  base.png    8 欄 × 26 列，格子大小一致：
                列 0       = 站姿，欄＝方向（south, SE, E, NE, N, NW, W, SW）
                列 1..8    = 走路，列 1+d ＝方向 d，欄＝幀
                列 9..16   = 跑步，列 9+d ＝方向 d，欄＝幀
                列 17..24  = 施法，列 17+d ＝方向 d，欄＝幀（0..5）
                列 25      = 蹲下 5 幀（欄 0..4）  ← 還是前一位女巫
  green/brown/ivory.png    換裝造型（緋紅緞邊改色版）

  睡覺立繪 `sleep.png` / `*-sleep.png` **這支腳本不再產生**：新角色沒有躺床的圖，
  磁碟上那幾張還是前一位女巫的，先留著（GameArt 照樣載得到）。新圖來了再補。

152 張來源都是同一個 116×116 畫布，所以**全部用同一個裁切框**裁，
角色的腳底與左右中心自動保持對齊，不用逐格對位。
"""
import os, sys, colorsys
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
ROW_WALK, ROW_RUN, ROW_CAST, ROW_CROUCH = 1, 9, 17, 25
ROWS = 26
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

# ── 前一位女巫的蹲下（暫用）──
# 新角色還沒有蹲下（採集／摘花／種花）的圖。這段動畫的來源資料夾已經被刪掉，只剩
# legacy_pose.png，所以從那裡讀、**等比放大到跟新角色一樣高**再置中貼進格子裡
# （不放大的話，一按 E 採集人就縮水一截）。新圖做好後，把這段連同 legacy_pose.png
# 一起刪掉。（legacy_pose.png 的列 0 是前一位女巫的施法，現在用不到了。）
LEGACY = os.path.join(TOOLS, "legacy_pose.png")
legacy_crouch = []
if os.path.exists(LEGACY):
    strip = load(LEGACY)
    lw, lh = strip.width // COLS, strip.height // 2
    cells = [strip.crop((c * lw, r * lh, (c + 1) * lw, (r + 1) * lh))
             for r in range(2) for c in range(COLS)]
    lb = [im.getbbox() for im in cells if im.getbbox()]
    ux0, uy0 = min(b[0] for b in lb), min(b[1] for b in lb)
    ux1, uy1 = max(b[2] for b in lb), max(b[3] for b in lb)
    k = body / (uy1 - uy0)                       # 放大倍率：舊身高 → 新身高
    print(f"舊姿勢格子 {lw}x{lh}、身高 {uy1-uy0}px → 放大 {k:.2f} 倍")

    def fit(im):
        """把舊格子裁到內容、等比放大、置中且腳底對齊新格子。"""
        crop = im.crop((ux0, uy0, ux1, uy1))
        w, h = max(1, round(crop.width * k)), max(1, round(crop.height * k))
        crop = crop.resize((w, h), Image.NEAREST)
        cell = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        cell.paste(crop, ((CW - w) // 2, foot - h))
        return cell

    legacy_crouch = [fit(cells[COLS + c]) for c in range(5)]     # 列 1 的前 5 格
else:
    print("（沒有 legacy_pose.png，蹲下留白）")

def build_sheet():
    sh = Image.new("RGBA", (COLS * CW, ROWS * CH), (0, 0, 0, 0))
    def put_raw(im, c, r):                  # 已經是格子大小
        sh.paste(im, (c * CW, r * CH))
    def put(im, c, r):                      # 116x116 來源，用共同裁切框裁
        put_raw(im.crop((x0, y0, x1, y1)), c, r)
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
    for c, im in enumerate(legacy_crouch):
        put_raw(im, c, ROW_CROUCH)
    return sh

base = build_sheet()

# ── 換裝：把緞邊的緋紅改色 ──
# 新角色是黑袍，舊那套「紫色轉色相」完全沒東西可轉。這張圖只有 18 個顏色，
# 紅色家族（H 335~360、S>0.35：帽帶、披風、緞帶、滾邊、寶石）佔 11%，改它最有效：
# 黑袍與黑描邊不動（描邊被染色像素畫會很髒），皮膚是暖色 H<30 也不在區間內。
RED_H = (335, 12)      # 跨過 0° 的區間：H>=335 或 H<=12
RED_S = 0.35

def recolor(im, hue, sat_mul=1.0, val_mul=1.0):
    out = im.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 8:
                continue
            hh, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            deg = hh * 360
            if not (deg >= RED_H[0] or deg <= RED_H[1]):
                continue                       # 不是緋紅：黑袍、描邊、銀髮、皮膚
            if ss < RED_S:
                continue                       # 帶點紅的灰（陰影）：留著
            ss = min(1.0, ss * sat_mul)
            vv = min(1.0, vv * val_mul)
            nr, ng, nb = colorsys.hsv_to_rgb(hue / 360.0, ss, vv)
            px[x, y] = (round(nr * 255), round(ng * 255), round(nb * 255), a)
    return out

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
