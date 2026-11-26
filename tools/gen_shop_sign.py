# -*- coding: utf-8 -*-
"""
店門口的「開店／關店」招牌＋風鈴（Core/ShopSignPost.cs 擺、Core/ShopSign.cs 管狀態）—— 程式點陣畫。
招牌站在**城鎮**裡、自家小屋（cottage-home）門口外面（Core/Doorways.cs 的 CottageSign），店裡沒有招牌。

    python tools/gen_shop_sign.py                  # 輸出 Assets/Resources/shopsign/*.png
    python tools/gen_shop_sign.py --preview DIR    # 另外輸出：放大總覽、疊在城鎮實景（小屋門口）的合成預覽
                                                   #   開店／關店 × 白天／夜色，各一張

固定結果、可重跑（沒有亂數）。畫風＝道具圖示那套（tools/gen_item_art.py，使用者說「很可愛」）：
**import 它的繪圖基元與色盤**（rect／ell／poly／line／border、PAL、外輪廓色），不複製、也不改它的輸出。

── 尺寸與像素密度 ─────────────────────────────────────────────
  在 1/2 解析度的邏輯格上點（一格＝2×2 世界像素），最後 NEAREST ×2 輸出。
  輸出圖 1 px ＝ 1 世界像素（PPU 1，Unity 不縮放）—— 城鎮地面烤圖也是「1 美術像素＝2 世界像素」，
  所以招牌的像素顆粒跟地面一樣大；高 94 ≈ 女巫（×1.6）一個身高，站在小屋旁邊比例剛好。

── 圖層（全部同一張畫布大小 CANVAS，疊起來就是完整的招牌）─────────────
  post.png          木柱＋橫桿＋頂端的星星＋底座＋接地陰影（不動）
  board-open.png    開店那一面：奶油色木牌、太陽、綠色 OPEN
  board-closed.png  關店那一面：深藍木牌、金色月亮與小星星、CLOSED
  chime.png         掛在橫桿末端的風鈴（三根金屬管＋撞錘＋小星星風鈴片）
  同一張畫布的好處：C# 只要把每層放在同一個位置就對齊；要轉動的那幾層（木牌、風鈴）
  只需要知道「掛點」在畫布上的位置（PIVOTS，印出來抄進 ShopSignPost.cs）。

── 錨點約定（ShopSignPost.cs 依賴，改了要一起改）──────────────────────
  FOOT ＝ 木柱底部中央（落地點），輸出時印出它在畫布上的像素座標。
  C# 把招牌根物件放在落地點、畫布往上推，讓 FOOT 剛好落在根物件原點；排序用 -落地點 y（戶外那一套）。
  BOARD_PIVOT ＝ 木牌兩條鍊子之間、橫桿下緣的中點（翻面以它的 x 為軸、搖晃以它為圓心）。
  CHIME_PIVOT ＝ 風鈴掛繩頂端（搖晃的圓心）。

⚠️ 陷阱
  * 外輪廓用 4 鄰接（跟 gen_item_art 一樣）。每一層**各自**描邊 —— 木牌轉動時邊框要跟著它走。
  * 接地陰影是半透明的（SHADOW_RGBA 跟店裡家具同一個值），不參與描邊。
  * 鍊子只有 1 格寬，描邊後是 3 格寬的深色細線 —— 這是刻意的（遠看才看得到）。
  * 新增的 PNG 沒有 .meta：Unity 第一次匯入時由 PixelArtImporter（路徑含 /Resources/）套 Point、不壓縮。
"""
import hashlib
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gen_item_art as ia                               # noqa: E402  （main 有 __name__ 保護，import 不會重畫道具）
from gen_item_art import rect, ell, poly, line, border  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUT_DIR = os.path.join(ROOT, 'Assets', 'Resources', 'shopsign')
SCALE = 2                     # 邏輯格 → 世界像素
LW, LH = 50, 47               # 畫布（邏輯格）
CANVAS = (LW * SCALE, LH * SCALE)

POST_X0, POST_X1 = 4, 6       # 木柱（3 格寬）
ARM_Y0, ARM_Y1 = 8, 9         # 橫桿（2 格厚）
ARM_X1 = 46                   # 橫桿右端
GROUND = 44                   # 地面那一列（木柱最底下一列）
BOARD = (10, 13, 36, 29)      # 木牌 x0, y0, x1, y1（27×17）
CHAINS = (14, 32)             # 兩條鍊子的 x
CHIME_X = 42                  # 風鈴掛繩的 x

FOOT = ((POST_X0 + POST_X1 + 1) / 2.0, GROUND + 1)                 # 邏輯連續座標
BOARD_PIVOT = ((BOARD[0] + BOARD[2] + 1) / 2.0, ARM_Y1 + 1)
CHIME_PIVOT = (CHIME_X + 0.5, ARM_Y1 + 1)

SHADOW_RGBA = (24, 12, 28, 92)   # 跟 gen_brew_room / 店內家具的接地陰影同一個值
OL = ia.OL

PAL = dict(ia.PAL)
PAL.update({
    # 開店木牌（奶油木）＋綠字
    'cr_hi': '#fff6dc', 'cr': '#f4e2b4', 'cr_dk': '#d9bf86',
    'ok': '#3f8f45', 'ok_dk': '#2b6a35',
    # 關店木牌（夜藍）＋金字
    'nt_hi': '#4a5aa0', 'nt': '#34407c', 'nt_dk': '#252e5c',
    # 風鈴管（亮銀藍）
    'mt_hi': '#f2fbff', 'mt': '#b8d4e6', 'mt_dk': '#7d9cb8',
})

# ═══════════════════════ 3×5 點陣字（N 用 4 寬才認得出來）═══════════════════════
GLYPHS = {
    'O': ['010', '101', '101', '101', '010'],
    'P': ['110', '101', '110', '100', '100'],
    'E': ['111', '100', '110', '100', '111'],
    'N': ['1001', '1101', '1011', '1001', '1001'],
    'C': ['011', '100', '100', '100', '011'],
    'L': ['100', '100', '100', '100', '111'],
    'S': ['011', '100', '010', '001', '110'],
    'D': ['110', '101', '101', '101', '110'],
}


def text_cells(s, x0, y0):
    out = set()
    x = x0
    for ch in s:
        g = GLYPHS[ch]
        for yy, row in enumerate(g):
            for xx, c in enumerate(row):
                if c == '1':
                    out.add((x + xx, y0 + yy))
        x += len(g[0]) + 1
    return out


def text_width(s):
    return sum(len(GLYPHS[c][0]) + 1 for c in s) - 1


def text_shadow(s, x0, y0):
    """
    字的右下陰影：每一格往 (+1,+1) 投影，但**只落在字自己的外框外面**。
    ⚠️ 不限制的話 O 的中空、D 的肚子裡也會被投進一格陰影，O 看起來變成「Ø」。
    """
    out = set()
    x = x0
    for ch in s:
        g = GLYPHS[ch]
        gw, gh = len(g[0]), len(g)
        for yy, row in enumerate(g):
            for xx, c in enumerate(row):
                # 只有最右一欄、最底一列的筆畫投得出外框
                if c == '1' and (xx + 1 >= gw or yy + 1 >= gh):
                    out.add((x + xx + 1, y0 + yy + 1))
        x += gw + 1
    return out


# ═══════════════════════ 圖層 ═══════════════════════

class Layer:
    """一層：px（會描邊）、glow（發光點，不描邊）、shadow（半透明接地陰影，不描邊）。"""

    def __init__(self):
        self.px, self.glow, self.shadow = {}, {}, set()

    def put(self, m, col):
        for p in m:
            self.px[p] = col

    def flat(self, m, ramp):
        ic = ia.Icon()
        ic.flat(m, ramp)
        self.px.update(ic.px)

    def cyl(self, m, ramp, lo=0.28, hi=0.72):
        ic = ia.Icon()
        ic.cyl(m, ramp, lo, hi)
        self.px.update(ic.px)

    def sphere(self, m, ramp, cx, cy, rx, ry):
        ic = ia.Icon()
        ic.sphere(m, ramp, cx, cy, rx, ry)
        self.px.update(ic.px)

    def render(self, w=LW, h=LH):
        body = dict(self.px)
        for x, y in list(self.px):
            for p in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if p not in self.px:
                    body[p] = OL
        for p, c in self.glow.items():
            if p not in body or body[p] == OL:
                body[p] = c
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        for (x, y) in self.shadow:
            if 0 <= x < w and 0 <= y < h:
                im.putpixel((x, y), SHADOW_RGBA)
        for (x, y), c in body.items():
            assert 0 <= x < w and 0 <= y < h, f'畫出畫布：{(x, y)}'
            hx = PAL[c]
            im.putpixel((x, y), tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5)) + (255,))
        return im.resize((w * SCALE, h * SCALE), Image.NEAREST)


def star_cells(cx, cy, ro, ri):
    return ia.star(cx, cy, ro, ri)


def draw_post():
    L = Layer()
    # 接地陰影：橢圓，壓在底座下（不描邊、半透明）
    L.shadow = ell(5.5, GROUND + 1.0, 6.5, 1.6)
    # 底座：兩塊交叉的小木腳（正面看是一條寬木＋中間一塊）
    foot = rect(1, GROUND - 1, 9, GROUND)
    L.flat(foot, ('wd_hi', 'wd', 'wd_dk'))
    # 木柱
    post = rect(POST_X0, ARM_Y0 - 2, POST_X1, GROUND - 2)
    L.cyl(post, ('wd_hi', 'wd', 'wd_dk'))
    # 木紋：幾個深色短點
    for y in (16, 23, 31, 37):
        L.px[(POST_X1 - 1, y)] = 'wd_dk2'
    # 橫桿
    arm = rect(POST_X0, ARM_Y0, ARM_X1, ARM_Y1)
    for x, y in arm:
        L.px[(x, y)] = 'wd_hi' if y == ARM_Y0 else 'wd_dk'
    # 斜撐（柱子→橫桿）
    for p in line(POST_X1 + 1, ARM_Y1 + 5, POST_X1 + 5, ARM_Y1 + 1):
        L.px[p] = 'wd'
        L.px[(p[0], p[1] + 1)] = 'wd_dk'
    # 橫桿右端的金色小球
    knob = ell(ARM_X1 + 1.5, ARM_Y0 + 1.0, 1.6, 1.6)
    L.sphere(knob, ('go_hi', 'go', 'go_dk'), ARM_X1 + 1.5, ARM_Y0 + 1.0, 1.6, 1.6)
    # 柱頂：金色五角星（魔女的店）
    st = star_cells(5.5, 4.6, 3.6, 1.6)
    L.put(st, 'go')
    for p in border(st):
        if p[0] >= 6 or p[1] >= 6:
            L.px[p] = 'go_dk'
    L.px[(5, 3)] = "go_hi"
    L.px[(4, 4)] = "go_hi"
    return L


def chains(L):
    for cx in CHAINS:
        for y in range(ARM_Y1 + 1, BOARD[1]):
            L.px[(cx, y)] = 'ir_hi' if y % 2 else 'ir'


def board_frame(L, face):
    x0, y0, x1, y1 = BOARD
    outer = rect(x0, y0, x1, y1)
    inner = rect(x0 + 1, y0 + 1, x1 - 1, y1 - 1)
    # 木框：上、左亮，下、右暗
    for x, y in outer - inner:
        L.px[(x, y)] = 'wd_hi' if (y == y0 or x == x0) else 'wd_dk'
    L.flat(inner, face)
    # 掛環：鍊子接木框的地方一顆金屬點
    for cx in CHAINS:
        L.px[(cx, y0)] = 'ir_hi'
    return inner


def draw_board_open():
    L = Layer()
    chains(L)
    board_frame(L, ('cr_hi', 'cr', 'cr_dk'))
    cx = (BOARD[0] + BOARD[2] + 1) / 2.0
    # 太陽：圓＋四方向光芒點＋斜角短光
    sun = ell(cx, 18.0, 2.6, 2.6)
    L.sphere(sun, ('hn_hi', 'hn', 'hn_dk'), cx, 18.0, 2.6, 2.6)
    icx = int(cx)
    for dx, dy in ((0, -4), (0, 4), (-4, 0), (4, 0)):
        L.px[(icx + dx - (1 if dx > 0 else 0) + (0 if dx else 0), 18 + dy - (1 if dy > 0 else 0))] = 'hn'
    for dx, dy in ((-3, -3), (3, -3), (-3, 3), (3, 3)):
        L.px[(icx + dx - (1 if dx > 0 else 0), 18 + dy - (1 if dy > 0 else 0))] = 'hn_hi'
    # OPEN（綠，右下一格陰影字讓它浮起來）
    # ⚠️ 字本身只用一個顏色：試過「每個筆畫最底下一格用暗綠」，3×5 的字一加明暗就糊成一團（N 尤其認不出來）
    w = text_width('OPEN')
    tx = int(round(cx - w / 2.0))
    t = text_cells('OPEN', tx, 23)
    L.put(text_shadow('OPEN', tx, 23) - t, 'cr_dk')
    L.put(t, 'ok')
    # 太陽兩側的小愛心（cozy）—— 放在上排，不要跟字擠在同一排（擠在一起會讀成「♥OPEN♥」一串）
    for hx in (int(cx) - 9, int(cx) + 7):
        heart = {(hx, 17), (hx + 2, 17), (hx, 18), (hx + 1, 18), (hx + 2, 18), (hx + 1, 19)}
        L.put(heart, 'pink')
        L.px[(hx, 17)] = 'pk_hi'
    return L


def draw_board_closed():
    L = Layer()
    chains(L)
    board_frame(L, ('nt_hi', 'nt', 'nt_dk'))
    cx = (BOARD[0] + BOARD[2] + 1) / 2.0
    # 彎月：大圓減掉往右上偏的圓
    moon = ell(cx - 0.5, 18.5, 3.6, 3.6) - ell(cx + 1.3, 17.2, 3.0, 3.0)
    L.put(moon, 'go')
    for p in moon:
        if p[0] < cx - 2.5:
            L.px[p] = 'go_hi'
    # 小星星：直接點在木牌上（⚠️ 不能用 glow 層 —— glow 只畫在「空白或外輪廓」的格子，木牌面上會整個被吃掉）
    icx = int(cx)
    for sx, sy in ((icx + 4, 15), (icx - 7, 16), (icx + 7, 19)):
        L.px[(sx, sy)] = 'go_hi'
    for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        L.px[(icx + 4 + d[0], 15 + d[1])] = 'go_dk'
    # CLOSED（米金字，右下一格陰影；字本身單色，理由同 OPEN）
    w = text_width('CLOSED')
    tx = int(round(cx - w / 2.0))
    t = text_cells('CLOSED', tx, 23)
    L.put(text_shadow('CLOSED', tx, 23) - t, 'nt_dk')
    L.put(t, 'go_hi')
    return L


def draw_chime():
    L = Layer()
    x = CHIME_X
    # 掛繩
    for y in range(ARM_Y1 + 1, ARM_Y1 + 4):
        L.px[(x, y)] = 'li_dk'
    # 頂蓋（小小的銅色圓頂）
    top = ARM_Y1 + 4
    cap = rect(x - 3, top + 1, x + 3, top + 1) | rect(x - 2, top, x + 2, top)
    for p in cap:
        L.px[p] = 'cu_hi' if p[1] == top else 'cu'
    L.px[(x + 3, top + 1)] = 'cu_dk'
    # 三根管子（不同長度），中間空一格；每根左亮右暗
    for tx, ln in ((x - 3, 8), (x, 11), (x + 3, 7)):
        for y in range(top + 2, top + 2 + ln):
            L.px[(tx, y)] = 'mt_hi' if y < top + 4 else 'mt'
        L.px[(tx, top + 1 + ln)] = 'mt_dk'
    # 撞錘線＋小星星風鈴片
    for y in range(top + 13, top + 16):
        L.px[(x, y)] = 'li_dk'
    st = star_cells(x + 0.5, top + 18.0, 2.6, 1.2)
    L.put(st, 'pink')
    L.px[(x, top + 17)] = 'pk_hi'
    return L


# ═══════════════════════ 輸出 ═══════════════════════

def md5(p):
    with open(p, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def render_all():
    return {
        'post': draw_post().render(),
        'board-open': draw_board_open().render(),
        'board-closed': draw_board_closed().render(),
        'chime': draw_chime().render(),
    }


def to_px(pt):
    """邏輯連續座標 → 輸出圖的像素座標（左上原點、y 往下）。"""
    return pt[0] * SCALE, pt[1] * SCALE


def town_sign_foot():
    """招牌落地點（世界座標）：小屋位置（Data/TownLayout.cs）＋Doorways.CottageSign，對齊偶數像素 ——
    跟 ShopSignPost.Ensure 一樣。另外回傳門的觸發點（預覽畫光圈用）與城鎮物件表。"""
    import re
    sys.path.insert(0, os.path.join(HERE, 'ground'))
    import layouts                                       # noqa: E402
    with open(os.path.join(ROOT, 'Assets', 'Scripts', 'Core', 'Doorways.cs'), encoding='utf-8') as f:
        src = f.read()

    def vec(name):
        m = re.search(name + r'\s*=\s*new\((-?[\d.]+)f,\s*(-?[\d.]+)f\)', src)
        return float(m.group(1)), float(m.group(2))
    objs = layouts.OBJECTS['town']()
    cot = next(o for o in objs if o.art.split('/')[-1] == 'cottage-home')
    ox, oy = vec('CottageSign')
    dx, dy = vec('CottageDoor')
    foot = (round((cot.x + ox) / 2) * 2, round((cot.y + oy) / 2) * 2)
    return foot, (cot.x + dx, cot.y + dy), objs


# 夜色：DayNightTint 21:00 那一幀（入夜，深藍 alpha 0.5）—— 整片蓋在世界之上
NIGHT_RGBA = (25, 35, 90, int(0.50 * 255))
DOOR_GLOW = (76, 30)          # PortalGlow 的門口光圈半徑（DoorRx, DoorRy）


def preview(ims, outdir):
    from PIL import ImageDraw
    import gen_footprints as G
    sys.path.insert(0, os.path.join(HERE, 'ground'))
    import layouts                                       # noqa: E402
    os.makedirs(outdir, exist_ok=True)
    files = []

    # ① 放大總覽：開／關兩種完整招牌 ×3（深底、淺底）
    def full(open_):
        im = Image.new('RGBA', CANVAS, (0, 0, 0, 0))
        for k in ('post', 'board-open' if open_ else 'board-closed', 'chime'):
            im.alpha_composite(ims[k])
        return im
    a, b = full(True), full(False)
    for bg, tag in (((40, 30, 36, 255), 'dark'), ((236, 226, 206, 255), 'light')):
        sheet = Image.new('RGBA', (CANVAS[0] * 2 + 30, CANVAS[1] + 20), bg)
        sheet.alpha_composite(a, (10, 10))
        sheet.alpha_composite(b, (CANVAS[0] + 20, 10))
        sheet = sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST)
        p = os.path.join(outdir, f'sign_sheet_{tag}.png')
        sheet.save(p)
        files.append(p)

    # ② 疊在城鎮實景：地面烤圖＋城鎮物件照世界座標拼（排序跟遊戲一樣：建築照圖片中心、其他照腳底），
    #    招牌照 Doorways.CottageSign 擺，門前石階下站一個女巫當身高參考
    foot, door, objs = town_sign_foot()
    W, H = layouts.SIZES['town']
    ground = Image.open(os.path.join(G.RES, 'art', 'ground', 'town.png')).convert('RGBA').resize((W, H), Image.NEAREST)

    def P(x, y):
        return x + W / 2.0, H / 2.0 - y

    try:
        w8 = Image.open(os.path.join(ROOT, 'Assets', 'Resources', 'witch8', 'base.png')).convert('RGBA')
        cw, ch = w8.width // 8, w8.height // 25
        witch = w8.crop((0, 0, cw, ch)).resize((int(cw * 1.6), int(ch * 1.6)), Image.NEAREST)
    except Exception as e:          # 預覽用，沒有也沒關係
        print('（女巫參考圖略過：', e, '）')
        witch = None
    witch_at = (door[0] + 10, door[1] - 14)

    fx, fy = to_px(FOOT)
    for open_ in (True, False):
        for night in (False, True):
            items = []
            for o in objs:
                fp = G.footprint(o.art)
                x0, y0, x1, y1 = G.image_rect(fp, o.x, o.y, o.scale, o.pivot)
                key = (y0 + y1) / 2 if (fp and fp.get('keep')) else y0
                items.append((key, 'obj', (o, (x0, y0, x1, y1))))
            items.append((foot[1], 'sign', None))
            if witch is not None:
                items.append((witch_at[1], 'witch', None))
            im = ground.copy()
            # 門口光圈（地上、所有物件之下）
            glow = Image.new('RGBA', im.size, (0, 0, 0, 0))
            gx, gy = P(*door)
            ImageDraw.Draw(glow).ellipse([gx - DOOR_GLOW[0], gy - DOOR_GLOW[1], gx + DOOR_GLOW[0], gy + DOOR_GLOW[1]],
                                         fill=(150, 220, 255, 80))
            im.alpha_composite(glow)
            for _, kind, data in sorted(items, key=lambda t: -t[0]):
                if kind == 'obj':
                    o, (x0, y0, x1, y1) = data
                    sp = Image.open(os.path.join(G.RES, o.art.replace('/', os.sep) + '.png')).convert('RGBA')
                    if o.scale != 1:
                        sp = sp.resize((max(1, round(sp.width * o.scale)), max(1, round(sp.height * o.scale))),
                                       Image.NEAREST)
                    px, py = P(x0, y1)
                    im.alpha_composite(sp, (int(round(px)), int(round(py))))
                elif kind == 'sign':
                    sx, sy = P(*foot)
                    im.alpha_composite(full(open_), (int(round(sx - fx)), int(round(sy - fy))))
                else:
                    wx, wy = P(*witch_at)
                    im.alpha_composite(witch, (int(wx - witch.width / 2), int(wy - witch.height + 6)))
            if night:
                im.alpha_composite(Image.new('RGBA', im.size, NIGHT_RGBA))
            cx, cy = P(foot[0] - 30, foot[1] + 70)
            crop = im.crop((int(cx - 260), int(cy - 170), int(cx + 260), int(cy + 170)))
            crop = crop.resize((crop.width * 2, crop.height * 2), Image.NEAREST)
            p = os.path.join(outdir, f'sign_town_{"open" if open_ else "closed"}_{"night" if night else "day"}.png')
            crop.convert('RGB').save(p)
            files.append(p)
    print(f'城鎮招牌落地點 ({foot[0]:g}, {foot[1]:g})；門的觸發點 ({door[0]:g}, {door[1]:g})；'
          f'離光圈中心 x 差 {foot[0] - door[0]:g}（光圈半寬 {DOOR_GLOW[0]}）')
    return files


def main():
    args = sys.argv[1:]
    preview_dir = args[args.index('--preview') + 1] if '--preview' in args else None
    ims = render_all()
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, im in ims.items():
        p = os.path.join(OUT_DIR, name + '.png')
        im.save(p, optimize=False)
        print(f'{name:<13} {im.width}×{im.height}  {md5(p)[:8]}')
    fx, fy = to_px(FOOT)
    bx, by = to_px(BOARD_PIVOT)
    cx, cy = to_px(CHIME_PIVOT)
    print(f'畫布 {CANVAS[0]}×{CANVAS[1]}；FOOT=({fx:g},{fy:g})  BOARD_PIVOT=({bx:g},{by:g})  CHIME_PIVOT=({cx:g},{cy:g})'
          '（像素，左上原點、y 往下 —— 抄進 ShopSignPost.cs）')
    if preview_dir:
        for f in preview(ims, preview_dir):
            print('預覽', f)


if __name__ == '__main__':
    main()
