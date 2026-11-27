#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
花圃（像素風、跟女巫同一個精細度）產生器：土壤磚（乾／濕）＋ 三種花的成長／枯萎走圖，全部程式點陣畫。

    python tools/gen_garden_plants.py                    # 輸出 Assets/Resources/garden8/*.png
    python tools/gen_garden_plants.py --preview DIR      # 另外輸出預覽（放大走圖＋假花園實景合成）
    python tools/gen_garden_plants.py --restore          # 刪掉 garden8/（GameArt 會自動退回 garden/ 舊圖）
    （--out DIR 改輸出位置、--force 有格子超框也照樣輸出 —— 都只給調圖時用）

舊圖（Resources/garden/）一張都沒動；GameArt.UsePixelPlants 開關決定讀哪一份。

── 精細度：對齊女巫（witch8）────────────────────────────────────────────
  女巫是 1px 原生像素、遊戲裡 ×1.6 顯示、多階柔和明暗、深色描邊。這裡照同一套做：
  * 花：1px 原生像素畫，遊戲裡跟女巫一樣 ×1.6（GardenData.FlowerScale）→ 一格像素在畫面上跟她的一樣大。
  * 土：1px 原生像素、遊戲裡 ×1（頂面要剛好等於等距格子 88×44，88/1.6 不是整數）。
    土的紋理本來就碎，像素比女巫細一點反而像土；結構（土塊、犁溝）都做成 2～4px 大，不會變成雜訊。
  * 每種材質 6～7 階、色相偏移（亮部偏黃暖、暗部偏藍紫），描邊用材質自己最暗那階（不是一律黑框），
    受光那側的描邊亮一階（sel-out）——女巫的頭髮與裙子就是這樣畫的。

── 規格（⚠️ GameArt.cs／GardenPlot.cs／Data/Garden.cs 依賴這個）────────────────
  * soil-dry.png / soil-wet.png：88×62。頂面菱形 88×44 佔第 9～52 列，下面 9px 是土床側面，
    上面對稱留 9px（邊緣的小草會長進去）→ 圖片「正中心」＝ 頂面菱形中心：置中樞紐、縮放 1 放在花圃座標上。
  * <花>.png：234×96 ＝ 6 欄 × 2 列，每格 39×48（原生 px，遊戲裡 ×1.6 ≈ 62×77）。
    列 0 成長：0 種子土丘＋芽 → 1 幼苗 → 2 長葉 → 3 花苞 → 4 盛開（＝收成那格）→ 5 開完的乾穗
    列 1 枯萎：0~3 越來越垂、越來越黃褐 → 4 褐色枯枝 → 5 倒在地上的死枝
    （跟舊圖同一個排法，GameArt.Flower 的切法不用改；成長只用前 5 欄，見 GardenData.GrowStages）
  * 每一格莖的入土點都在第 GY 列、水平正中（第 GX 欄，格子寬 39 是奇數）→ 換階段不會跳。
    入土點到格子底邊 FOOT_PX＝3px（縮放前）＝ GameArt.PixelFlowerFootPadPx。
  * 盛開高約 41px × 1.6 ≈ 66px、寬不超過 37px × 1.6 ≈ 59px（女巫可見約 93px；格子 88 寬，左右鄰格不會擠在一起）。
  * 結果是確定的：沒有亂數（雜點用座標雜湊），重跑 md5 相同。
"""
import hashlib
import math
import os
import shutil
import sys

from PIL import Image, ImageDraw

HERE = os.environ.get('GARDEN_TOOLS_DIR') or os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, 'Assets', 'Resources')
OUT_DIR = os.path.join(RES, 'garden8')

# ── 花的格子（原生 px）──
FW, FH = 39, 48
GX, GY = 19, 44                  # 入土點：莖最下面那格
FOOT_PX = FH - 1 - GY            # 3
FLOWER_SCALE = 1.6               # 遊戲裡的顯示倍數（＝ GameArt.WitchScale；改了要同步 GardenData.FlowerScale）
# ── 土壤磚 ──
SW, SD = 88, 44                  # 頂面菱形
SIDE = 9                         # 側面厚度
SH = SD + 2 * SIDE               # 62

LIGHT2 = (-0.6, -0.8)            # 光從左上來（螢幕座標，y 往下）
ERRS = []


# ═══════════════════════════════ 顏色 ═══════════════════════════════

def H(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def R(*hexes):
    return [H(h) for h in hexes]


def rmix(r1, r2, t):
    t = max(0.0, min(1.0, t))
    return [lerp(a, b, t) for a, b in zip(r1, r2)]


def hsh(x, y, k=0):
    """座標雜湊 → 0..1（確定的「隨機」）。"""
    v = (x * 73856093) ^ (y * 19349663) ^ (k * 83492791)
    v = (v ^ (v >> 13)) * 1274126177 & 0xffffffff
    v ^= v >> 16
    return (v & 0xffff) / 65535.0


# 6 階：0 最亮（偏黃暖）… 4 最暗的面、5 描邊（偏藍紫）
LEAF = R('#e4f2a2', '#b4d878', '#7fb95a', '#559346', '#376b3f', '#1f4532')
SAGE = R('#e6edbe', '#bccc98', '#90aa79', '#69875f', '#48654c', '#2b4236')     # 薰衣草的銀綠葉
FOXLEAF = R('#d8eb98', '#a2cc6c', '#6fa654', '#4c8048', '#335c40', '#1d3b30')
STEM = R('#c4dc8a', '#8fba62', '#5f9248', '#436f3c', '#2f5034', '#1d3528')
LAV = R('#f4e4ff', '#d0adff', '#a882ea', '#8160cc', '#5d40a0', '#3a2468')
FOX = R('#fff2f7', '#ffc4e1', '#f191c7', '#d466ab', '#a2448c', '#682660')
FOX_IN = R('#fff4d8', '#f6d2b0', '#b0587e', '#7c2f62', '#5a1f4a', '#3c1235')    # 花喉：米白唇、深色斑
SB = R('#ffffff', '#eef7ff', '#cbe2ff', '#9ec0f2', '#7092d2', '#4a64a8')
GOLD = R('#fff6b8', '#ffe17a', '#f4be4c', '#c88a30', '#94601f', '#5e3a14')
DRY = R('#eedcae', '#d6b886', '#b8935e', '#94703f', '#6c4e2c', '#45301b')     # 乾穗（稻草褐）
WITHER = R('#e6d58c', '#cdb560', '#a99440', '#7e7232', '#5a5228', '#3a361c')   # 發黃的葉
BROWN = R('#d9b585', '#b98d5c', '#97693f', '#744d2e', '#53361f', '#352214')
DEAD = R('#b39070', '#8f6c50', '#6e5039', '#53392a', '#3b281d', '#271912')
SHADOW = (24, 12, 28, 88)


# ═══════════════════════════════ 植物畫布 ═══════════════════════════════

class Cv:
    def __init__(self, w=FW, h=FH):
        self.w, self.h = w, h
        self.px = {}
        self.glow = {}          # (x,y) → (r,g,b,a)：半透明光暈（只疊在透明處）
        self.spark = {}         # 不透明的小亮點（不描邊）
        self.oob = 0

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h - 1:
            self.px[(x, y)] = c
        else:
            self.oob += 1

    def image(self, name, shadow=True):
        if self.oob:
            ERRS.append(f'{name}: {self.oob} 格超出格子')
        im = Image.new('RGBA', (self.w, self.h), (0, 0, 0, 0))
        pix = im.load()
        if shadow:
            for y in range(GY - 1, GY + 4):
                for x in range(GX - 10, GX + 11):
                    if ((x + 0.5 - (GX + 0.5)) / 9.5) ** 2 + ((y + 0.5 - (GY + 1.2)) / 2.2) ** 2 <= 1 and 0 <= y < self.h:
                        pix[x, y] = SHADOW
        for (x, y), c in self.glow.items():
            if (x, y) not in self.px and 0 <= x < self.w and 0 <= y < self.h:
                pix[x, y] = c
        for (x, y), c in self.px.items():
            pix[x, y] = c + (255,)
        # 外輪廓：整株外面補 1px 深色（鄰格顏色壓暗、偏藍紫）—— 女巫的剪影就是這樣一圈深邊，
        # 擺在草地上才「跳」得出來。只描透明處（光暈、影子會被蓋掉），不描進格子最底那列。
        for (x, y) in self.outline_cells():
            # 取一個鄰格（固定順序，色數才不會爆）的顏色壓暗
            nb = next(self.px[p] for p in ((x, y + 1), (x + 1, y), (x - 1, y), (x, y - 1)) if p in self.px)
            pix[x, y] = lerp(nb, (26, 18, 36), 0.72) + (255,)
        for (x, y), c in self.spark.items():
            if 0 <= x < self.w and 0 <= y < self.h and (x, y) not in self.px:
                pix[x, y] = c + (255,)
        return im


def _outline_cells(self):
    out = set()
    for x, y in self.px:
        for p in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if p not in self.px and 0 <= p[0] < self.w and 0 <= p[1] < self.h - 1:
                out.add(p)
    return out


Cv.outline_cells = _outline_cells


def edge_cells(mask):
    return {p for p in mask if any((p[0] + dx, p[1] + dy) not in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}


def outline_col(mask, p, ramp):
    """描邊色：外側朝左上（受光）的描邊亮一階（sel-out），其餘用最暗那階。"""
    x, y = p
    open_l, open_r = (x - 1, y) not in mask, (x + 1, y) not in mask
    open_u, open_d = (x, y - 1) not in mask, (x, y + 1) not in mask
    if (open_l or open_u) and not (open_r or open_d):
        return ramp[4]
    return ramp[5]


def q(b, ramp, lo=0, hi=4):
    """亮度 b（0..1）→ ramp 的第 lo..hi 階。"""
    i = round((1.0 - max(0.0, min(1.0, b))) * (hi - lo)) + lo
    return ramp[i]


# ── 形狀 ──

def leaf_mask(ax, ay, bx, by, w, sharp=0.8):
    """葉片：A→B、最寬 w。回傳 {(x,y): (t 沿葉長 0..1, dn 橫向 -1..1)}。"""
    out = {}
    L = math.hypot(bx - ax, by - ay) or 1.0
    ux, uy = (bx - ax) / L, (by - ay) / L
    px_, py_ = -uy, ux
    for y in range(int(min(ay, by) - w) - 1, int(max(ay, by) + w) + 2):
        for x in range(int(min(ax, bx) - w) - 1, int(max(ax, bx) + w) + 2):
            cx, cy = x + 0.5 - ax, y + 0.5 - ay
            t = (cx * ux + cy * uy) / L
            if not 0.0 <= t <= 1.0:
                continue
            d = cx * px_ + cy * py_
            half = (w / 2.0) * math.sin(math.pi * t) ** sharp
            if half > 0.05 and abs(d) <= half:
                out[(x, y)] = (t, d / half)
    return out, (px_, py_)


def paint_leaf(cv, ax, ay, bx, by, w, ramp, sharp=0.8, vein=True, bright=0.0, maxy=None):
    m, (px_, py_) = leaf_mask(ax, ay, bx, by, w, sharp)
    if maxy is not None:
        m = {p: v for p, v in m.items() if p[1] <= maxy}
    if not m:
        return set()
    cells = set(m)
    thin = w < 3.2
    shadow_ring(cv, cells, ramp[4] if thin else ramp[5])
    edge = edge_cells(cells)
    side_l = -(px_ * LIGHT2[0] + py_ * LIGHT2[1])       # +dn 那半面朝光的程度
    for p, (t, dn) in m.items():
        if thin:
            # 細葉（薰衣草、草）：不描黑邊 —— 2～3px 寬的葉子描了邊就只剩一條黑線。
            # 改成受光那側亮、背光那側暗一階，尖端最亮。
            sgn = 1 if dn >= 0 else -1
            b = 0.34 + 0.35 * sgn * side_l + 0.35 * (t - 0.5) + bright
            if p in edge and sgn * side_l < 0:
                b -= 0.25
            b += (hsh(*p, 5) - 0.5) * 0.1
            cv.set(*p, q(b, ramp, 0, 4))
            continue
        if p in edge:
            cv.set(*p, outline_col(cells, p, ramp))
            continue
        sgn = 1 if dn >= 0 else -1
        b = 0.5 + 0.38 * sgn * side_l - 0.22 * abs(dn) ** 2 + 0.15 * (0.5 - abs(t - 0.45)) + bright
        if vein and w >= 3.2 and abs(dn) < 0.2 and 0.08 < t < 0.8:
            b += 0.28
        b += (hsh(*p, 5) - 0.5) * 0.12
        cv.set(*p, q(b, ramp, 0, 4))
    return cells


def line(x0, y0, x1, y1):
    out = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        out.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
    return out


def stalk(x0, y0, x1, y1, droop=0.0, side=None):
    """
    莖：(x0,y0) 往 (x1,y1)，回傳由下往上的格子清單（8 鄰接）。
    droop＞0 讓尖端越往上越往外彎、垂下來（枯萎；弧度，1.5 ≈ 垂到水平）；垂到格子邊就截斷。
    """
    L = math.hypot(x1 - x0, y1 - y0)
    a0 = math.atan2(x1 - x0, -(y1 - y0))
    if side is None:
        side = 1 if x1 >= x0 else -1
    pts = [(x0, y0)]
    x, y = x0 + 0.5, y0 + 0.5
    steps = max(1, int(L * 4))
    for i in range(steps):
        t = i / steps
        a = a0 + side * droop * t * t
        nx, ny = x + math.sin(a) * L / steps, y - math.cos(a) * L / steps
        if not 3 <= nx < FW - 3 or ny > GY:
            break
        x, y = nx, ny
        c = (int(math.floor(x)), int(math.floor(y)))
        if c != pts[-1]:
            for p in line(*pts[-1], *c)[1:]:
                pts.append(p)
    return pts


def paint_stem(cv, pts, ramp, width=2):
    """莖：2px 寬時左邊受光、右邊暗；1px 用中暗階。"""
    for i, (x, y) in enumerate(pts):
        if width >= 2:
            nx, ny = pts[min(len(pts) - 1, i + 1)]
            px_, py_ = pts[max(0, i - 1)]
            if abs(nx - px_) > abs(ny - py_) * 1.5:
                cv.set(x, y, ramp[2])
                cv.set(x, y + 1, ramp[4])
            else:
                cv.set(x, y, ramp[2])
                cv.set(x + 1, y, ramp[4])
        else:
            cv.set(x, y, ramp[3])


def ball(cv, cx, cy, rx, ry, ramp, outline=True, lo=0, hi=4):
    m = set()
    for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0:
                m.add((x, y))
    edge = edge_cells(m) if outline else set()
    for p in m:
        if p in edge:
            cv.set(*p, outline_col(m, p, ramp))
            continue
        nx, ny = (p[0] + 0.5 - cx) / rx, (p[1] + 0.5 - cy) / ry
        z = math.sqrt(max(0.0, 1 - nx * nx - ny * ny))
        b = 0.5 * (nx * -0.55 + ny * -0.65 + z * 0.55) + 0.45
        cv.set(*p, q(b, ramp, lo, hi))
    return m


def shadow_ring(cv, cells, dark):
    """在 cells 外圍、已經有東西的地方描一圈暗色 —— 前面的東西跟後面的分得開。"""
    for x, y in cells:
        for p in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if p not in cells and p in cv.px:
                cv.px[p] = dark


def sparkle(cv, x, y, col=(236, 246, 255), arm=(186, 214, 255), big=False):
    cv.spark[(x, y)] = col
    for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        cv.spark[(x + d[0], y + d[1])] = arm
    if big:
        for d in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            cv.spark[(x + d[0], y + d[1])] = arm


def halo(cv, cells, rings=((1, 2, 96), (3, 4, 44))):
    """柔光：cells 外面一圈一圈的半透明淡藍（越外越淡）。只落在透明處（Cv.image 處理）。"""
    col = (214, 234, 255)
    seen = set(cells)
    frontier = set(cells)
    dist = {}
    for d in range(1, max(r[1] for r in rings) + 1):
        nxt = set()
        for x, y in frontier:
            for p in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if p not in seen:
                    seen.add(p)
                    nxt.add(p)
                    dist[p] = d
        frontier = nxt
    for p, d in dist.items():
        for a, b, alpha in rings:
            if a <= d <= b:
                old = cv.glow.get(p)
                if old is None or old[3] < alpha:
                    cv.glow[p] = col + (alpha,)


# ── 共用部件 ──

def basal(cv, specs, ramp, droop=0.0, sharp=0.8):
    """根部葉叢：specs＝[(尖端 x, 尖端 y, 寬)]，從入土點長出去；droop 讓尖端往外往下掉。先畫後面（高的）。"""
    for tx, ty, w in sorted(specs, key=lambda s: s[1]):
        dx = tx - (GX + 0.5)
        ty2 = min(GY - 0.5, ty + droop * 5.0 * (1.0 if abs(dx) > 3 else 0.6))
        tx2 = min(max(tx + (1 if dx > 0 else -1) * droop * 2.0, 2.0), FW - 2.0)
        paint_leaf(cv, GX + 0.5, GY + 0.5, tx2, ty2, w, ramp, sharp, maxy=GY)   # 葉子不長到入土點下面


def mound(cv):
    """種子土丘：一小坨翻過的土。"""
    soil = R('#d8b386', '#b98f62', '#966d48', '#755236', '#573b27', '#3c281b')
    m = ball(cv, GX + 0.5, GY + 0.3, 6.5, 2.8, soil)
    for p in list(m):
        if p[1] > GY + 1:
            cv.px.pop(p, None)
    for x, y in ((GX - 3, GY - 1), (GX + 2, GY), (GX + 4, GY - 1)):
        cv.set(x, y, soil[3])
    cv.set(GX - 2, GY - 2, soil[0])


def sprout(cv, ramp, h=4, w=3.0):
    pts = [(GX, GY - i) for i in range(h + 1)]
    paint_stem(cv, pts, STEM, 1)
    paint_leaf(cv, GX + 0.5, GY - h + 0.5, GX - 3.5, GY - h - 1.5, w, ramp, vein=False)
    paint_leaf(cv, GX + 0.5, GY - h + 0.5, GX + 4.5, GY - h - 2.5, w, ramp, vein=False)


def dead_pile(cv):
    """死透：幾根褐色枯枝倒在土上，兩片捲起的枯葉。"""
    for (ex, ey) in ((GX - 9, GY - 6), (GX + 8, GY - 8), (GX + 2, GY - 11), (GX - 4, GY - 9)):
        paint_stem(cv, line(GX, GY, ex, ey), DEAD, 1)
        cv.set(ex, ey - 1, DEAD[1])
    paint_leaf(cv, GX + 0.5, GY + 0.5, GX - 9.5, GY - 1.0, 4.0, DEAD, vein=False)
    paint_leaf(cv, GX + 0.5, GY + 0.5, GX + 10.5, GY - 0.5, 3.6, DEAD, vein=False)


# ── 階段參數 ──
GROW = [
    dict(kind='seed'),
    dict(kind='seedling'),
    dict(kind='leafy'),
    dict(kind='plant', h=0.72, flower='bud', fade=0.0, droop=0.0, leaf=0.0),
    dict(kind='plant', h=1.0, flower='bloom', fade=0.0, droop=0.0, leaf=0.0),
    dict(kind='plant', h=1.0, flower='dry', fade=0.0, droop=0.0, leaf=0.45),
]
WILT = [
    dict(kind='plant', h=0.97, flower='bloom', fade=0.2, droop=0.3, leaf=0.25),
    dict(kind='plant', h=0.93, flower='bloom', fade=0.45, droop=0.6, leaf=0.5),
    dict(kind='plant', h=0.88, flower='bloom', fade=0.75, droop=0.95, leaf=0.75),
    dict(kind='plant', h=0.82, flower='dry', fade=1.0, droop=1.25, leaf=1.0),
    dict(kind='plant', h=0.72, flower='none', fade=1.0, droop=1.6, leaf=1.25),
    dict(kind='dead'),
]


def leaf_ramp(base, w):
    """葉色：0 健康 → 0.5 發黃 → 1 褐 → 1.25 死褐。"""
    if w <= 0:
        return base
    if w <= 0.5:
        return rmix(base, WITHER, w / 0.5)
    if w <= 1.0:
        return rmix(WITHER, BROWN, (w - 0.5) / 0.5)
    return rmix(BROWN, DEAD, (w - 1.0) / 0.25)


def stem_ramp(w):
    return leaf_ramp(STEM, w)


# ═══════════════════════════════ 薰衣草 ═══════════════════════════════
# 一叢銀綠細葉，七根細莖散開，每根頂端一串一輪一輪的小花（每朵 1～2px、左上亮右下暗、花與花之間露出深紫的花萼）。

LAV_TIPS = ((6, 11), (12, 5), (19, 2), (26, 5), (32, 11))
LAV_LEAVES = ((4, 37, 2.6), (34, 37, 2.6), (7, 32, 2.4), (31, 32, 2.4), (10, 28, 2.3), (28, 28, 2.3),
              (14, 26, 2.2), (24, 26, 2.2), (19, 25, 2.2), (2, 41, 2.4), (36, 41, 2.4))


def lav_spike(cv, pts, n, ramp, bud=False):
    """花穗：沿莖最上面 n 格，每兩格一輪小花。"""
    top = pts[-n:][::-1]                      # 由尖端往下
    for k, (x, y) in enumerate(top):
        cv.set(x, y, ramp[4])                 # 花萼／穗軸
        cv.set(x + 1, y, ramp[5])
    for k, (x, y) in enumerate(top):
        if bud:
            if k % 2 == 0:
                cv.set(x, y, ramp[2] if k > 1 else ramp[1])
                cv.set(x + 1, y, STEM[3])
            continue
        size = 0 if k < 2 else 1
        if k % 2 == 0:
            cv.set(x, y, ramp[0] if k % 4 == 0 else ramp[1])
            cv.set(x + 1, y, ramp[2])
            if size >= 1:
                cv.set(x - 1, y, ramp[2])
            if size >= 2:
                cv.set(x - 2, y + 1, ramp[3])
                cv.set(x + 2, y + 1, ramp[3])
        else:
            if size >= 1:
                cv.set(x - 1, y, ramp[1])
                cv.set(x + 2, y, ramp[3])
            if size >= 2:
                cv.set(x - 2, y, ramp[2])
                cv.set(x + 3, y, ramp[4])
                cv.set(x - 1, y + 1, ramp[4])
    tx, ty = top[0]
    if not bud:
        cv.set(tx, ty - 1, ramp[1])


def draw_lavender(st):
    cv = Cv()
    k = st['kind']
    if k == 'seed':
        mound(cv)
        sprout(cv, SAGE, 3, 2.4)
    elif k == 'seedling':
        basal(cv, ((11, 36, 2.2), (27, 36, 2.2), (14, 32, 2.0), (24, 32, 2.0), (19, 31, 2.0)), SAGE)
    elif k == 'leafy':
        for tx, ty in ((12, 20), (19, 17), (26, 20)):
            paint_stem(cv, line(GX, GY - 4, tx, ty), STEM, 1)
            paint_leaf(cv, tx + 0.5, ty + 4.5, tx + 0.5, ty - 1.0, 2.2, SAGE, vein=False)
        basal(cv, LAV_LEAVES[:9], SAGE)
    elif k == 'dead':
        dead_pile(cv)
    else:
        w = st['leaf']
        lr = leaf_ramp(SAGE, w)
        sr = stem_ramp(w)
        fl, h = st['flower'], st['h']
        tips = LAV_TIPS if fl != 'none' else LAV_TIPS[1:4]
        spikes = []
        for i, (tx, ty) in enumerate(tips):
            tyh = GY - (GY - ty) * h
            side = -1 if tx < GX else (1 if tx > GX else (1 if i % 2 else -1))
            pts = stalk(GX, GY - 1, tx, tyh, st['droop'], side)
            paint_stem(cv, pts, sr, 1)
            spikes.append(pts)
        basal(cv, LAV_LEAVES, lr, st['droop'])
        for pts in spikes:
            if fl == 'bloom':
                lav_spike(cv, pts, 14 if st['fade'] < 0.6 else 10, rmix(LAV, DRY, st['fade']))
            elif fl == 'bud':
                lav_spike(cv, pts, 9, rmix(LAV, STEM, 0.35), bud=True)
            elif fl == 'dry':
                lav_spike(cv, pts, 11, rmix(rmix(LAV, DEAD, 0.7), BROWN, st['fade'] * 0.5))
    return cv


# ═══════════════════════════════ 毛地黃 ═══════════════════════════════
# 根部一圈寬大的深綠葉（有葉脈），中間一根高花莖，一串往下垂的粉紫鐘形花：
# 筒身朝光那側亮，花口朝外下方、看得到裡面的深色喉嚨與米白下唇；越往上越小，頂端是綠色小花苞。

FOX_LEAVES = ((3, 38, 7.0), (35, 38, 7.0), (6, 31, 6.0), (32, 31, 6.0), (11, 37, 5.0), (27, 37, 5.0))
FOX_BELLS_MAIN = ((0.33, 1, 4), (0.42, -1, 4), (0.51, 1, 4), (0.60, -1, 3), (0.68, 1, 3),
                  (0.76, -1, 2), (0.84, 1, 2), (0.91, -1, 1))
FOX_BELLS_SIDE = ((0.42, -1, 3), (0.58, 1, 2), (0.72, -1, 2), (0.85, 1, 1))


def fox_bell(cv, x, y, side, s, ramp, inner):
    """
    一朵垂下的鐘：從莖上 (x,y) 往外下方掛出去。s＝2..4 → 長 6..9、口寬 5..7。
    筒身沿軸做圓柱明暗（朝光那側亮），口是一個橢圓：深色喉嚨＋下緣米白唇＋斑點。
    """
    L = 3 + s * 1.5
    r0, r1 = 0.9 + s * 0.25, 1.5 + s * 0.6
    ang = math.radians(34 + s * 5) * side
    ux, uy = math.sin(ang), math.cos(ang)             # 軸：往下、往外
    px_, py_ = uy, -ux                                # 橫向
    ax, ay = x + 0.5 + side * 1.0, y + 0.5
    body = {}
    for yy in range(int(ay - 3), int(ay + L + r1 + 3)):
        for xx in range(int(ax - L - r1 - 3), int(ax + L + r1 + 3)):
            cx, cy = xx + 0.5 - ax, yy + 0.5 - ay
            t = (cx * ux + cy * uy) / L
            d = cx * px_ + cy * py_
            if 0 <= t <= 1.0:
                r = r0 + (r1 - r0) * t ** 1.6
                if abs(d) <= r:
                    body[(xx, yy)] = (t, d / r)
    if not body:
        return
    xs = [p[0] for p in body]
    sh = max(0, 1 - min(xs)) - max(0, max(xs) - (FW - 2))
    if sh:
        body = {(p[0] + sh, p[1]): v for p, v in body.items()}
        ax += sh
    cells = set(body)
    shadow_ring(cv, cells, LEAF[5])
    edge = edge_cells(cells)
    lit = -(px_ * LIGHT2[0] + py_ * LIGHT2[1])
    for p, (t, dn) in body.items():
        if p in edge:
            cv.set(*p, outline_col(cells, p, ramp))
            continue
        b = 0.5 + 0.5 * dn * lit - 0.2 * dn * dn + 0.15 * (1 - t)
        if 0.3 < dn * lit < 0.75 and 0.2 < t < 0.85:
            b = 1.0                                    # 筒身受光那側一道高光
        cv.set(*p, q(b, ramp, 0, 4))
    if s >= 2:
        mx, my = ax + ux * L, ay + uy * L
        rr = r1 * 0.85
        for yy in range(int(my - 3), int(my + 3)):
            for xx in range(int(mx - rr - 2), int(mx + rr + 2)):
                cx, cy = xx + 0.5 - mx, yy + 0.5 - my
                a = cx * px_ + cy * py_
                bb = cx * ux + cy * uy
                if (a / rr) ** 2 + (bb / max(0.9, rr * 0.45)) ** 2 <= 1.0:
                    if bb > 0.15:
                        cv.set(xx, yy, inner[0] if a * side < 0.5 else inner[1])
                    else:
                        cv.set(xx, yy, inner[3] if hsh(xx, yy, 9) < 0.7 else inner[2])
        for k in (0.55, 0.75):
            sx, sy = ax + ux * L * k - px_ * 0.4, ay + uy * L * k - py_ * 0.4
            p = (int(sx), int(sy))
            if p in body and p not in edge:
                cv.set(*p, ramp[3] if s < 4 else inner[2])
    cv.set(x + side, y, STEM[3])


def fox_pod(cv, x, y, side, ramp):
    """乾掉的蒴果：莖旁一顆尖卵形小褐果。"""
    x0 = x + 2 * side
    cv.set(x + side, y, ramp[3])
    m = {(x0, y), (x0, y + 1), (x0 + side, y + 1), (x0, y + 2), (x0 + side, y + 2), (x0, y + 3)}
    shadow_ring(cv, m, ramp[5])
    for p in m:
        dx = (p[0] - x0) * side
        cv.set(*p, ramp[1] if dx == 0 and p[1] <= y + 1 else (ramp[2] if dx == 0 else ramp[3]))
    cv.set(x0, y + 3, ramp[4])


def draw_foxglove(st):
    cv = Cv()
    k = st['kind']
    if k == 'seed':
        mound(cv)
        sprout(cv, FOXLEAF, 3, 3.2)
    elif k == 'seedling':
        basal(cv, ((9, 39, 5.0), (30, 39, 5.0), (19, 33, 4.4)), FOXLEAF)
    elif k == 'leafy':
        basal(cv, FOX_LEAVES + ((19, 24, 5.0),), FOXLEAF)
    elif k == 'dead':
        dead_pile(cv)
    else:
        w = st['leaf']
        lr = leaf_ramp(FOXLEAF, w)
        sr = stem_ramp(w)
        fl, h = st['flower'], st['h']
        basal(cv, FOX_LEAVES[:4], lr, st['droop'])
        stems = [((GX, 3), FOX_BELLS_MAIN, 1, 2)]
        if fl != 'none':
            stems.insert(0, ((GX + 9, 15), FOX_BELLS_SIDE, 1, 1))
        for (tx, ty), bells, side, wd in stems:
            tyh = GY - (GY - ty) * h
            pts = stalk(GX, GY - 1, tx, tyh, st['droop'] * (1.0 if tx == GX else 1.2), side)
            paint_stem(cv, pts, sr, wd)
            n = len(pts)
            for frac, sd, s in sorted(bells, key=lambda b: -b[0]):
                i = min(n - 1, int(round(frac * (n - 1))))
                x, y = pts[i]
                if fl == 'bloom':
                    if st['fade'] >= 0.6 and s == 1:
                        continue
                    if s == 1:
                        ball(cv, x + sd * 1.5 + 0.5, y + 1.0, 1.3, 1.6, rmix(FOX, FOXLEAF, 0.45))
                    else:
                        fox_bell(cv, x, y, sd, s, rmix(FOX, DRY, st['fade']), rmix(FOX_IN, DRY, st['fade']))
                elif fl == 'bud':
                    if s >= 2:
                        bx_ = x + sd * 2
                        cv.set(x + sd, y, sr[3])
                        ball(cv, bx_ + 0.5, y + 1.5, 1.3, 1.8, FOXLEAF if s < 4 else rmix(FOXLEAF, FOX, 0.45))
                        cv.set(bx_, y + 2, FOX[2] if s >= 3 else FOXLEAF[2])
                elif fl == 'dry':
                    fox_pod(cv, x, y, sd, rmix(DRY, BROWN, st['fade'] * 0.6))
            tx2, ty2 = pts[-1]
            cv.set(tx2, ty2 - 1, sr[1] if fl in ('bloom', 'bud') else sr[3])
        basal(cv, FOX_LEAVES[4:], lr, st['droop'])
    return cv


# ═══════════════════════════════ 星鈴花 ═══════════════════════════════
# 幾片中綠葉，四根細莖頂端各開一朵五瓣星形花：花瓣由花心（淡藍影）往瓣尖變白，瓣中一條淺折痕，
# 金黃花心；花外兩圈半透明的淡藍柔光，旁邊幾個十字小亮點 ——「夜裡會泛著微光」。

SB_LEAVES = ((4, 38, 5.0), (34, 38, 5.0), (8, 32, 4.4), (30, 32, 4.4), (19, 29, 3.8))
SB_FLOWERS = ((8.0, 12.0, 6.2), (19.5, 6.5, 6.6), (30.5, 11.0, 6.2), (24.5, 22.0, 5.0))


def star_flower(cv, cx, cy, R0, ramp, glow=True, gold=True, rot=-90.0):
    """五瓣星形花：每瓣是從花心到瓣尖的圓頭三角，花瓣與花瓣之間微凹。"""
    m = {}
    for y in range(int(cy - R0) - 1, int(cy + R0) + 2):
        for x in range(int(cx - R0) - 1, int(cx + R0) + 2):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            r = math.hypot(dx, dy)
            a = math.degrees(math.atan2(dy, dx)) - rot
            ph = ((a % 72.0) + 72.0) % 72.0 - 36.0
            lim = R0 * (0.46 + 0.54 * (1 - abs(ph) / 36.0) ** 1.4)
            if r <= lim:
                m[(x, y)] = (r / R0, ph / 36.0)
    cells = set(m)
    shadow_ring(cv, cells, ramp[4])
    edge = edge_cells(cells)
    for p, (rn, ph) in m.items():
        if p in edge:
            cv.set(*p, outline_col(cells, p, ramp))
            continue
        dx, dy = p[0] + 0.5 - cx, p[1] + 0.5 - cy
        lit = -(dx * LIGHT2[0] + dy * LIGHT2[1]) / max(1.0, math.hypot(dx, dy))
        b = 0.35 + 0.6 * rn + 0.15 * lit
        if abs(ph) < 0.12 and 0.3 < rn < 0.8:
            b -= 0.22
        cv.set(*p, q(b, ramp, 0, 3))
    ix, iy = int(cx), int(cy)
    if gold:
        for (x, y), c in (((ix - 1, iy - 1), GOLD[0]), ((ix, iy - 1), GOLD[1]), ((ix - 1, iy), GOLD[1]),
                          ((ix, iy), GOLD[2]), ((ix + 1, iy), GOLD[3]), ((ix, iy + 1), GOLD[3])):
            cv.set(x, y, c)
    else:
        cv.set(ix, iy, ramp[3])
        cv.set(ix - 1, iy, ramp[2])
    if glow:
        halo(cv, cells)
    return cells


def draw_starbell(st):
    cv = Cv()
    k = st['kind']
    if k == 'seed':
        mound(cv)
        sprout(cv, LEAF, 3, 2.8)
        cv.spark[(GX + 5, GY - 8)] = (220, 236, 255)
    elif k == 'seedling':
        paint_stem(cv, [(GX, GY - i) for i in range(10)], STEM, 1)
        for yy, ln in ((2, 6.0), (6, 4.5)):
            y = GY - yy
            paint_leaf(cv, GX + 0.5, y + 0.5, GX + 0.5 - ln, y - ln * 0.5, 3.0, LEAF, vein=False)
            paint_leaf(cv, GX + 0.5, y + 0.5, GX + 0.5 + ln, y - ln * 0.5, 3.0, LEAF, vein=False)
        sparkle(cv, GX + 7, GY - 13)
    elif k == 'leafy':
        for tx, ty in ((11, 22), (28, 20)):
            pts = stalk(GX, GY - 3, tx, ty)
            paint_stem(cv, pts, STEM, 1)
            paint_leaf(cv, tx + 0.5, ty + 0.5, tx + (4.5 if tx > GX else -3.5), ty - 3.0, 3.0, LEAF, vein=False)
        basal(cv, SB_LEAVES, LEAF)
        sparkle(cv, 6, 18)
    elif k == 'dead':
        dead_pile(cv)
    else:
        w = st['leaf']
        lr = leaf_ramp(LEAF, w)
        sr = stem_ramp(w)
        fl, h = st['flower'], st['h']
        fade = st['fade']
        flowers = SB_FLOWERS if fl != 'none' else SB_FLOWERS[:3]
        heads = []
        for cx, cy, r in flowers:
            tyh = GY - (GY - cy) * h
            side = -1 if cx < GX else 1
            pts = stalk(GX, GY - 1, int(cx), int(tyh) + 3, st['droop'], side)
            paint_stem(cv, pts, sr, 1)
            heads.append((pts[-1], r))
        basal(cv, SB_LEAVES, lr, st['droop'])
        glow = fl == 'bloom' and fade < 0.5
        for (x, y), r in heads:
            if fl == 'bloom':
                rr = r * (1.0 - 0.3 * fade)
                fx = min(max(x + 0.5, rr + 1.5), FW - rr - 1.5)
                star_flower(cv, fx, max(rr + 1.5, y - rr + 2.5), rr, rmix(SB, DRY, fade), glow=glow,
                            gold=fade < 0.8, rot=-90.0 + 12.0 * (1 if x > GX else -1) * (1 + st['droop']))
            elif fl == 'bud':
                bm = ball(cv, x + 0.5, y - 1.0, 2.2, 3.0, SB)
                halo(cv, bm, ((1, 2, 70),))
            elif fl == 'dry':
                rr = r * 0.62
                fx = min(max(x + 0.5, rr + 1.5), FW - rr - 1.5)
                star_flower(cv, fx, y - rr + 2.5, rr, rmix(DRY, BROWN, fade * 0.5), glow=False, gold=False)
        if glow:
            for sx, sy in ((2, 22), (36, 19), (13, 2), (27, 3), (34, 30)):
                if (sx, sy) not in cv.px:
                    sparkle(cv, sx, sy)
        elif fl == 'bud':
            sparkle(cv, 5, 18)
            sparkle(cv, 33, 16)
    return cv


FLOWERS = [('lavender', draw_lavender), ('foxglove', draw_foxglove), ('starbell', draw_starbell)]


def render_flower(name, fn):
    sheet = Image.new('RGBA', (FW * 6, FH * 2), (0, 0, 0, 0))
    for r, (rows, tag) in enumerate(((GROW, '成長'), (WILT, '枯萎'))):
        for c, st in enumerate(rows):
            sheet.paste(fn(st).image(f'{name} {tag}{c}'), (c * FW, r * FH))
    return sheet


# ═══════════════════════════════ 土壤磚 ═══════════════════════════════
# 用「高度場＋打光」畫：犁溝（沿等距 s 軸的一條條土壟）＋一顆顆土塊＋細碎顆粒 → 算法線、
# 跟左上的光做點積 → 依分位數分到 7 階色（保證亮暗比例好看）。濕土換一組更暗偏冷的色、
# 朝反射方向的一小撮補水光、溝底積幾段水。邊緣一圈略高的床緣，下面 9px 側面（左亮右暗、夾小石子）。
# ⚠️ 頂面菱形不描外框：相鄰兩塊花圃頂面貼著頂面，描框會變成一條粗黑線；只有側面下緣與兩端描框。

SOIL = {
    False: dict(top=R('#ecd2a6', '#d4b183', '#b99262', '#9c774c', '#7f5d3b', '#62462d', '#45301f'),
                side=R('#a37b52', '#8a6442', '#704f35', '#573c29', '#3f2b1e')),
    True: dict(top=R('#b49378', '#93705a', '#775746', '#5f4337', '#4a332a', '#37251f', '#261915'),
               side=R('#6e5040', '#5a4033', '#473229', '#352620', '#251a16'),
               water=R('#d6e6f2', '#9fb6c8', '#6f8699', '#506273', '#3a4756')),
}
PEB = R('#f0ebe0', '#cfc6b7', '#a79d8f', '#7e7469', '#58504a', '#3a332f')
GRASS = R('#d4ec8e', '#9fd06a', '#6fae50', '#4b8a42', '#336636', '#1f4530')
OUTLINE = H('#2a1b24')
PEBBLES = ((-0.30, -0.12, 3.3, 2.2), (0.26, -0.30, 2.6, 1.8), (0.12, 0.30, 3.0, 2.0), (-0.05, 0.02, 2.2, 1.5))
TUFTS = ((-0.47, -0.20), (-0.15, -0.47), (0.30, -0.47), (0.47, 0.05), (-0.47, 0.32))   # (s, t)


def _top_mask():
    cx, cy = SW / 2.0, SIDE + SD / 2.0
    m = set()
    for y in range(SIDE, SIDE + SD):
        r = y - SIDE
        rr = r if r < SD // 2 else SD - 1 - r
        hw = 2 * (rr + 1)
        for x in range(SW // 2 - hw, SW // 2 + hw):
            m.add((x, y))
    return m, cx, cy


def iso(x, y, cx, cy):
    px, py = x + 0.5 - cx, y + 0.5 - cy
    return px / SW + py / SD, -px / SW + py / SD


def soil_height(x, y, cx, cy):
    s, t = iso(x, y, cx, cy)
    e = 0.5 - max(abs(s), abs(t))
    ridge = 0.5 + 0.5 * math.cos(2 * math.pi * (t + 0.5) * 4.0 + math.pi)
    ridge = ridge ** 0.8
    fade = min(1.0, max(0.0, (e - 0.035) / 0.05))
    h = ridge * 2.4 * fade
    h += 1.3 * max(0.0, 1.0 - e / 0.05) if e < 0.05 else 0.0
    best = 0.0
    gx0, gy0 = int(x // 4), int(y // 3)
    for gy in range(gy0 - 1, gy0 + 2):
        for gx in range(gx0 - 1, gx0 + 2):
            if hsh(gx, gy, 31) < 0.45:
                continue
            ox = gx * 4 + hsh(gx, gy, 32) * 4
            oy = gy * 3 + hsh(gx, gy, 33) * 3
            rad = 1.1 + hsh(gx, gy, 34) * 1.4
            dd = ((x + 0.5 - ox) / rad) ** 2 + ((y + 0.5 - oy) / (rad * 0.8)) ** 2
            if dd < 1:
                best = max(best, (0.5 + hsh(gx, gy, 35) * 0.7) * (1 - dd) ** 0.6)
    h += best * (0.45 + 0.3 * fade)
    h += (hsh(x // 2, y, 36) - 0.5) * 0.35
    return h, ridge, fade, s, t


def soil_tile(wet):
    P = SOIL[wet]
    top, cx, cy = _top_mask()
    hmap = {}
    for y in range(SIDE - 1, SIDE + SD + 1):
        for x in range(-1, SW + 1):
            hmap[(x, y)] = soil_height(x, y, cx, cy)
    L = (-0.5, -0.7, 0.75)
    n0 = math.sqrt(sum(v * v for v in L))
    L = tuple(v / n0 for v in L)
    Hh = (L[0], L[1], L[2] + 1.0)
    n1 = math.sqrt(sum(v * v for v in Hh))
    Hh = tuple(v / n1 for v in Hh)
    lum, spec = {}, {}
    for (x, y) in top:
        h = hmap[(x, y)][0]
        dx = (hmap[(x + 1, y)][0] - hmap[(x - 1, y)][0]) / 2
        dy = (hmap[(x, y + 1)][0] - hmap[(x, y - 1)][0]) / 2
        n = (-dx, -dy, 1.0)
        nn = math.sqrt(sum(v * v for v in n))
        n = tuple(v / nn for v in n)
        lum[(x, y)] = sum(a * b for a, b in zip(n, L)) + 0.2 * h
        spec[(x, y)] = sum(a * b for a, b in zip(n, Hh)) + 0.05 * h
    order = sorted(top, key=lambda p: (-lum[p], p))
    cuts = [0.03, 0.13, 0.33, 0.62, 0.84, 0.96, 1.01]
    cells = {}
    N = len(order)
    for i, p in enumerate(order):
        f = i / N
        k = next(j for j, c in enumerate(cuts) if f < c)
        cells[p] = P['top'][k]
    if wet:
        so = sorted(top, key=lambda p: (-spec[p], p))
        for i, p in enumerate(so[:int(N * 0.014)]):
            cells[p] = P['water'][0] if i < N * 0.004 else P['water'][1]
        for p in top:
            h, ridge, fade, s, t = hmap[p]
            if fade > 0.9 and ridge < 0.06 and int((s + 0.5) * 14) % 3 != 1:
                cells[p] = P['water'][3] if hsh(p[0], p[1], 41) < 0.6 else P['water'][2]
                if hsh(p[0], p[1], 42) < 0.18:
                    cells[p] = P['water'][1]
    for ss, tt, rx, ry in PEBBLES:
        px = (ss - tt) * SW / 2 + cx
        py = (ss + tt) * SD / 2 + cy
        m = set()
        for y in range(int(py - ry) - 1, int(py + ry) + 2):
            for x in range(int(px - rx) - 1, int(px + rx) + 2):
                if ((x + 0.5 - px) / rx) ** 2 + ((y + 0.5 - py) / ry) ** 2 <= 1 and (x, y) in top:
                    m.add((x, y))
        edge = edge_cells(m)
        for x, y in m:
            for p in ((x + 1, y + 1), (x, y + 1)):
                if p not in m and p in top:
                    cells[p] = P['top'][6]
        for p in m:
            nx, ny = (p[0] + 0.5 - px) / rx, (p[1] + 0.5 - py) / ry
            if p in edge and (nx > 0.2 or ny > 0.2):
                cells[p] = PEB[4]                     # 只有右下描暗邊，左上直接是受光面
                continue
            b = 0.55 + 0.5 * (-nx * 0.6 - ny * 0.8)
            cells[p] = q(b, PEB, 0, 3)
            if wet and b > 0.8:
                cells[p] = P['water'][0]
    edge = edge_cells(top)
    for (x, y) in edge:
        cells[(x, y)] = P['top'][1] if y < cy else P['top'][2]
    side = {}
    for x in range(SW):
        yb = max(y for (xx, y) in top if xx == x)
        for d in range(1, SIDE + 1):
            side[(x, yb + d)] = d
    for (x, y), d in side.items():
        base = 1 if x < SW // 2 else 3
        if d == 1:
            base -= 1
        v = hsh(x // 2, y, 51)
        if v < 0.18:
            base += 1
        elif v > 0.9:
            base -= 1
        if d in (4, 5) and hsh(x, 0, 52) < 0.5:
            base += 1
        cells[(x, y)] = P['side'][max(0, min(4, base))]
    for sx in (9, 30, 57, 74):
        yb = max(y for (xx, y) in top if xx == sx)
        for (x, y), c in (((sx, yb + 6), PEB[1]), ((sx + 1, yb + 6), PEB[2]), ((sx + 1, yb + 7), PEB[3]),
                          ((sx, yb + 7), PEB[3])):
            if (x, y) in side:
                cells[(x, y)] = c
    allm = top | set(side)
    for (x, y) in side:
        if (x, y + 1) not in allm or x in (0, SW - 1):
            cells[(x, y)] = OUTLINE
    for ss, tt in TUFTS:
        bx = int((ss - tt) * SW / 2 + cx)
        by = int((ss + tt) * SD / 2 + cy)
        for k, (dx, hgt, lean) in enumerate(((-2, 4, -1), (0, 6, 0), (1, 5, 1), (3, 3, 1), (-1, 3, -1))):
            for i in range(hgt):
                x = bx + dx + round(lean * i * i / (hgt * 2.2))
                y = by - i
                if 0 <= x < SW and 0 <= y < SH:
                    cells[(x, y)] = GRASS[4] if i == 0 else (GRASS[1] if i >= hgt - 2 else GRASS[2 + (k % 2)])
            tip = (bx + dx + round(lean * (hgt - 1) ** 2 / (hgt * 2.2)), by - hgt)
            if 0 <= tip[0] < SW and 0 <= tip[1]:
                cells[tip] = GRASS[0] if k == 1 else GRASS[1]
    im = Image.new('RGBA', (SW, SH), (0, 0, 0, 0))
    pix = im.load()
    for (x, y), c in cells.items():
        if 0 <= x < SW and 0 <= y < SH:
            pix[x, y] = c + (255,)
    return im


# ═══════════════════════════════ 預覽 ═══════════════════════════════

def scaled(im, k):
    return im.resize((round(im.width * k), round(im.height * k)), Image.NEAREST)


def preview(sheets, soils, outdir):
    os.makedirs(outdir, exist_ok=True)
    files = []
    Z = 5
    for tag, bg in (('grass', (96, 148, 72)), ('dark', (38, 30, 44))):
        W = 6 * FW * Z + 20
        H = len(sheets) * 2 * FH * Z + 30 + SH * 3 + 20
        out = Image.new('RGBA', (W, H), bg + (255,))
        d = ImageDraw.Draw(out)
        y = 10
        for name, sh in sheets:
            out.alpha_composite(scaled(sh, Z), (10, y))
            for r in range(2):
                for c in range(6):
                    x0, y0 = 10 + c * FW * Z, y + r * FH * Z
                    d.rectangle([x0, y0, x0 + FW * Z - 1, y0 + FH * Z - 1], outline=(255, 255, 255, 90))
                    fy = y0 + (GY + 1) * Z
                    d.line([x0 + GX * Z - 8, fy, x0 + (GX + 1) * Z + 8, fy], fill=(255, 0, 0, 150))
            y += sh.height * Z
        x = 10
        for s in soils:
            out.alpha_composite(scaled(s, 3), (x, y + 10))
            d.rectangle([x, y + 10 + SIDE * 3, x + SW * 3 - 1, y + 10 + (SIDE + SD) * 3 - 1], outline=(255, 255, 255, 90))
            x += SW * 3 + 20
        p = os.path.join(outdir, f'sheets_{tag}.png')
        out.save(p)
        files.append(p)

    # 假花園：草地＋兩塊 4×3 花圃（88×44 等距格；左邊混合階段、右邊全部盛開）＋女巫（×1.6）
    W, H = 900, 330
    scene = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    sp = scene.load()
    for yy in range(H):
        for xx in range(W):
            v = hsh(xx // 2, yy // 2, 99)
            sp[xx, yy] = (104, 158, 76, 255) if v < 0.85 else ((92, 142, 66, 255) if v < 0.95 else (124, 176, 88, 255))
    sheetd = dict(sheets)
    names = ('lavender', 'foxglove', 'starbell')

    def frame(fl, col, row):
        return sheetd[fl].crop((col * FW, row * FH, (col + 1) * FW, (row + 1) * FH))

    def block(ox, oy, plan):
        plots = [(i % 4, i // 4) + plan(i) for i in range(12)]
        sprites = []
        for c, r, wet, fl, stg, wl in plots:
            x, y = ox + (c - r) * 44, oy + (c + r) * 22
            scene.alpha_composite(soils[1 if wet else 0], (x - SW // 2, y - SH // 2))
        for c, r, wet, fl, stg, wl in plots:
            if fl is None:
                continue
            x, y = ox + (c - r) * 44, oy + (c + r) * 22
            f = scaled(frame(fl, stg, 1 if wl else 0), FLOWER_SCALE)
            foot = round(FOOT_PX * FLOWER_SCALE)
            sprites.append((y, f, (x - f.width // 2, y + foot - f.height)))
        return sprites

    mixed = [(False, 'lavender', 4, False), (True, 'foxglove', 4, False), (True, 'starbell', 4, False), (False, None, 0, False),
             (True, 'starbell', 3, False), (False, 'lavender', 2, False), (True, 'foxglove', 3, False), (False, 'foxglove', 1, True),
             (True, 'lavender', 0, False), (False, 'starbell', 1, False), (False, 'lavender', 3, True), (True, 'foxglove', 5, False)]
    sprites = block(250, 70, lambda i: mixed[i])
    sprites += block(640, 70, lambda i: ((i % 3) == 0, names[(i + i // 4) % 3], 4, False))
    wt = Image.open(os.path.join(RES, 'witch8', 'base.png')).convert('RGBA')
    wc = scaled(wt.crop((0, 0, wt.width // 8, wt.height // 25)), 1.6)
    fx, fy = 430, 250
    sprites.append((fy, wc, (fx - wc.width // 2, fy - wc.height + round(3 * 1.6))))
    for _, im, pos in sorted(sprites, key=lambda t: t[0]):
        scene.alpha_composite(im, pos)
    for z in (1, 2):
        p = os.path.join(outdir, f'garden_mock_{z}x.png')
        scene.resize((W * z, H * z), Image.NEAREST).save(p)
        files.append(p)
    return files


def md5(p):
    with open(p, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def main():
    args = sys.argv[1:]
    if '--restore' in args:
        if os.path.isdir(OUT_DIR):
            shutil.rmtree(OUT_DIR)
        meta = OUT_DIR + '.meta'
        if os.path.exists(meta):
            os.remove(meta)
        print(f'已刪除 {OUT_DIR}（GameArt 找不到 garden8 的圖時會自動退回 garden/ 舊圖；'
              '要完全關掉請把 GameArt.UsePixelPlants 設 false）')
        return
    preview_dir = args[args.index('--preview') + 1] if '--preview' in args else None
    out_dir = args[args.index('--out') + 1] if '--out' in args else OUT_DIR

    sheets = [(name, render_flower(name, fn)) for name, fn in FLOWERS]
    if ERRS:
        print('\n'.join(ERRS))
        if '--force' not in args:
            sys.exit('有格子超框（--force 照樣輸出，只給調圖時用）')
    soils = [soil_tile(False), soil_tile(True)]
    os.makedirs(out_dir, exist_ok=True)
    for name, sh in sheets:
        p = os.path.join(out_dir, name + '.png')
        sh.save(p, optimize=False)
        ncol = len({c for c in sh.getdata() if c[3] == 255})
        print(f'{name:<9} → {p}  {sh.width}×{sh.height}（每格 {FW}×{FH}）  {ncol} 色  {md5(p)[:8]}')
    for wet, s in zip((False, True), soils):
        p = os.path.join(out_dir, ('soil-wet' if wet else 'soil-dry') + '.png')
        s.save(p, optimize=False)
        print(f'{"濕土" if wet else "乾土"}      → {p}  {s.width}×{s.height}  {md5(p)[:8]}')
    if preview_dir:
        for f in preview(sheets, soils, preview_dir):
            print('預覽', f)


if __name__ == '__main__':
    main()
