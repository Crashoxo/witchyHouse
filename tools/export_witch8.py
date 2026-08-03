# -*- coding: utf-8 -*-
"""
把使用者做的 chibi 女巫（桌面四個資料夾）打包成遊戲用的圖集。可重跑。

來源
  Desktop/Idle                    rotations 8 方向站姿 ＋ Running 8 方向 ×8 幀
  Desktop/新增資料夾 (2)/…/Fireball   施法 6 幀（只有 south）
  Desktop/新增資料夾 (3)/…/Picking_Up 蹲下撿東西 5 幀（只有 south）＝採集／摘花／澆水共用
  Desktop/新增資料夾/same_witch_girl_lyi  睡在床上的 8 個角度

輸出（resources/witch8/）
  base.png    8 欄 × 11 列，格子大小一致：
                列 0      = 站姿，欄＝方向（south, SE, E, NE, N, NW, W, SW）
                列 1..8   = 走路，列 1+d ＝方向 d，欄＝幀
                列 9      = 施法 6 幀（欄 0..5）
                列 10     = 蹲下 5 幀（欄 0..4）
  sleep.png   睡覺立繪（含床），單張
  green/brown/ivory.png ＋ *-sleep.png   換裝造型（袍子改色版）

72+11 張都是同一個 92×92 畫布，所以**全部用同一個裁切框**裁，
角色的腳底與左右中心自動保持對齊，不用逐格對位。
"""
import os, sys, colorsys
from PIL import Image
sys.stdout.reconfigure(encoding='utf-8')

D = r"C:\Users\user\Desktop"
DST = r"D:\Crash\witch-shop\assets\resources\witch8"
PREVIEW = os.path.dirname(os.path.abspath(__file__))

DIRS = ["south", "south-east", "east", "north-east", "north", "north-west", "west", "south-west"]
ROT = os.path.join(D, "Idle", "rotations")
RUN = os.path.join(D, "Idle", "animations", "Running")
FIRE = os.path.join(D, "新增資料夾 (2)", "Idle_copy_2", "animations", "Fireball", "south")
PICK = os.path.join(D, "新增資料夾 (3)", "Idle_copy", "animations", "Picking_Up", "south")
BED = os.path.join(D, "新增資料夾", "same_witch_girl_lyi", "rotations")
BED_PICK = "south-west"   # 睡覺立繪用哪個角度：臉看得到、黑貓在旁邊、還有一支蠟燭

COLS = 8
PAD = 1

def load(p):
    return Image.open(p).convert("RGBA")

def frames(folder):
    return [load(os.path.join(folder, f)) for f in sorted(os.listdir(folder)) if f.endswith(".png")]

rot = [load(os.path.join(ROT, d + ".png")) for d in DIRS]
walk = [frames(os.path.join(RUN, d)) for d in DIRS]
cast = frames(FIRE)
crouch = frames(PICK)
print(f"站姿 {len(rot)}／走路 {[len(v) for v in walk]}／施法 {len(cast)}／蹲下 {len(crouch)}")

# ── 共同裁切框（所有角色幀一起算，對齊才不會跑掉）──
allf = rot + [im for v in walk for im in v] + cast + crouch
boxes = [im.getbbox() for im in allf]
W0, H0 = rot[0].size
x0 = max(0, min(b[0] for b in boxes) - PAD)
y0 = max(0, min(b[1] for b in boxes) - PAD)
x1 = min(W0, max(b[2] for b in boxes) + PAD)
y1 = min(H0, max(b[3] for b in boxes) + PAD)
CW, CH = x1 - x0, y1 - y0
foot = max(b[3] for b in boxes) - y0
print(f"格子 {CW}x{CH}（裁 {x0},{y0},{x1},{y1}）腳底 y={foot}，離底部 {CH-foot}px")

ROWS = 1 + len(DIRS) + 2
def build_sheet():
    sh = Image.new("RGBA", (COLS * CW, ROWS * CH), (0, 0, 0, 0))
    def put(im, c, r):
        sh.paste(im.crop((x0, y0, x1, y1)), (c * CW, r * CH))
    for i, im in enumerate(rot):
        put(im, i, 0)
    for d, v in enumerate(walk):
        for c, im in enumerate(v):
            put(im, c, 1 + d)
    for c, im in enumerate(cast):
        put(im, c, 9)
    for c, im in enumerate(crouch):
        put(im, c, 10)
    return sh

base = build_sheet()

# ── 睡覺立繪 ──
beds = {d: load(os.path.join(BED, d + ".png")) for d in DIRS}
bed = beds[BED_PICK]
bb = bed.getbbox()
bed = bed.crop((max(0, bb[0] - PAD), max(0, bb[1] - PAD),
                min(W0, bb[2] + PAD), min(H0, bb[3] + PAD)))
print(f"睡覺立繪（{BED_PICK}）{bed.size}")

# ── 換裝：把袍子/帽子的紫色轉成別的色相 ──
# 頭髮也是淡紫（同色相）→ 用「飽和度低且很亮」把頭髮排除在外。
# 皮膚、靴子、木杖是暖色（H<60），本來就不在紫色區間裡。
HAIR_S, HAIR_V = 0.36, 0.68
ROBE_H = (250, 315)

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
            if not (ROBE_H[0] <= deg <= ROBE_H[1]):
                continue                       # 不是紫的：皮膚、靴子、木杖、黑描邊
            if ss < HAIR_S and vv > HAIR_V:
                continue                       # 淡紫頭髮：留著
            ss = min(1.0, ss * sat_mul)
            vv = min(1.0, vv * val_mul)
            nr, ng, nb = colorsys.hsv_to_rgb(hue / 360.0, ss, vv)
            px[x, y] = (round(nr * 255), round(ng * 255), round(nb * 255), a)
    return out

# 對應 data/outfits 既有的三套：綠洋裝／褐大衣／米白長袍
OUTFITS = {
    'green': dict(hue=138, sat_mul=1.0, val_mul=1.0),
    'brown': dict(hue=24,  sat_mul=0.85, val_mul=1.12),
    'ivory': dict(hue=38,  sat_mul=0.35, val_mul=1.5),
}

os.makedirs(DST, exist_ok=True)
def save(im, name):
    p = os.path.join(DST, name)
    im.quantize(colors=128, method=Image.FASTOCTREE).save(p, optimize=True)
    print(f"  {name:22s} {im.size[0]}x{im.size[1]}  {os.path.getsize(p)/1024:.0f}KB")

print("寫出：")
save(base, "base.png")
save(bed, "sleep.png")
variants = {'': base}
for oid, kw in OUTFITS.items():
    v = recolor(base, **kw)
    variants[oid] = v
    save(v, f"{oid}.png")
    save(recolor(bed, **kw), f"{oid}-sleep.png")

# 衣櫃面板的造型立繪：拿各造型的正面站姿放大 4 倍（原本那批是舊手繪女巫的立繪，
# 人已經換掉了，留著會變成「面板裡是另一個人」）。
PORTRAITS = r"D:\Crash\witch-shop\assets\resources\portraits"
PSCALE = 6            # 6×53=318 ≈ 面板的 maxH 320 → 面板不再縮放，像素維持方正
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
for i, oid in enumerate(['base'] + list(OUTFITS)):
    im = base if oid == 'base' else recolor(base.crop((0, 0, CW, CH)), **OUTFITS[oid])
    cell = base.crop((0, 0, CW, CH)) if oid == 'base' else im
    strip.alpha_composite(cell.resize((CW * 4, CH * 4), Image.NEAREST), (4 + i * (CW * 4 + 8), 4))
strip.save(os.path.join(PREVIEW, "witch8_outfits.png"))
print("預覽 -> witch8_sheet.png / witch8_outfits.png")
