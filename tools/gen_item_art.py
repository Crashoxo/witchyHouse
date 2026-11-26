#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
道具圖示（8-bit 像素風）產生器：材料、藥水成品、糖果鎮商品、種子、花、水滴，全部用程式點陣畫。

    python tools/gen_item_art.py                    # 輸出 Assets/Resources/items8/<檔名>.png
    python tools/gen_item_art.py --preview DIR      # 另外輸出總覽圖（深色底／淺色底／實際大小）
    python tools/gen_item_art.py --restore          # 刪掉 items8/（GameArt 會自動退回舊圖）

── 為什麼直接在 24×24 的格子上畫，而不是畫大圖再縮小 ─────────────────────────
  縮小一定會內插出中間色、邊緣半透明、細節糊成一團 —— 那正是「8-bit 感」的反面。
  早期掌機／FC RPG 的道具圖示是「一格一格點出來的」：少少幾個顏色、1px 深色外框、
  左上打光、一個白色高光點。這裡照那個做法：在 24×24 的邏輯格上用幾個繪圖基元
  （橢圓、多邊形、線、葉片形）把「形狀」標出來，每個形狀自己依打光方向分 3～4 階色，
  最後自動補 1px 外輪廓，再用 NEAREST 放大 4 倍輸出 96×96。
  所以成品的每一格都是純色、alpha 只有 0 或 255、不會有任何抗鋸齒。

── 規格（⚠️ 別的程式依賴這個，改之前先看 GameArt.cs 的 UsePixelItems 說明）────────
  * 每張都是 96×96（邏輯 24×24 × 4），所有道具同一尺寸 —— UI 格子才排得整齊，
    貨架那邊也是把 GameArt.Item() 的圖「等比縮到約 24px 高」直接擺上去。
  * 圖案（含外輪廓）水平置中、**底部貼齊第 22 列**（最底下那一列 23 留空）、四周至少留 1 格。
    → 擺在貨架上時「東西坐在板子上」，不會每件浮在不同高度。
  * 內容最大 22×22 邏輯格；超過就 assert 失敗（外輪廓被裁掉是最常見的錯）。
  * 結果是確定的：沒有亂數（要「隨機感」的地方都用固定的座標表），重跑 md5 相同。

── 色盤 ──────────────────────────────────────────────────────────────
  基底直接 import tools/gen_brew_room.py 的 PAL（魔女房間那套：暖棕木、紫布、金、深藍、
  銅、米白、綠草、藥水青綠／桃紅／琥珀），外輪廓也用它的 'outline'（深棕紫，不是純黑），
  道具擺進房間跟店裡才是同一個世界。房間色盤偏灰暖，道具要「一眼認得」需要更飽和的
  果實／糖果色，所以下面 EXTRA 補了紅莓、黑莓紫、藍莓藍、楓葉橘、冰藍、火焰、糖果彩虹等。

⚠️ 陷阱
  * 外輪廓用 4 鄰接（上下左右），不用 8 鄰接：8 鄰接在斜線（掃帚柄、法杖）兩側會長出
    一坨一坨的角，像鋸齒；4 鄰接的斜線輪廓才是乾淨的階梯。
  * 「發光」類的小星星／蒸氣／粉塵畫在 glow 層，**不補外輪廓**（補了就變成一個個黑框十字）。
    glow 層也算進內容範圍，一樣要留在 22×22 裡。
  * 前後重疊的同色小球（漿果、藍莓）要靠 sep()：前面那顆在「已經畫了東西」的鄰格描一圈
    深色，不然整串會糊成一大塊同色。只描在已有內容的地方 —— 描在空白處會讓外框變 2px 粗。
  * Unity 那邊這個資料夾一樣走 PixelArtImporter（路徑含 /Resources/ → Point、不壓縮、無 mipmap）。
    新檔沒有 .meta，Unity 第一次匯入時套用；如果哪天手動改過某張的匯入設定，刪掉它的 .meta 重匯。
"""
import hashlib
import math
import os
import shutil
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, 'Assets', 'Resources', 'items8')

sys.path.insert(0, HERE)
from gen_brew_room import PAL as ROOM_PAL   # noqa: E402  只 import 色盤，不跑它的管線

G = 24          # 邏輯格大小
SCALE = 4       # 輸出放大倍數（NEAREST）→ 96×96
MAXC = 22       # 內容（含外輪廓）最大邊長：四周至少留 1 格
BOTTOM = 22     # 內容最底下那一列（第 23 列留空）

# ═══════════════════════════════ 色盤 ═══════════════════════════════
EXTRA = {
    'wh': '#fffbef',                                          # 高光點（微暖白，不是純白）
    # 紅莓／糖蘋果
    'rd_hi': '#ff7f6c', 'rd': '#dc3344', 'rd_dk': '#9c1f3c', 'rd_dk2': '#62143a',
    # 黑莓（深紫）
    'bk_hi': '#9a6cc4', 'bk': '#5a3683', 'bk_dk': '#3a2156', 'bk_dk2': '#26153c',
    # 藍莓
    'bb_hi': '#93b3ff', 'bb': '#5272dc', 'bb_dk': '#3446a2', 'bb_pale': '#cfdcff',
    # 金（補一階最暗）
    'go_dk2': '#75501f',
    # 楓葉（落葉）
    'au_hi': '#ffd068', 'au': '#f08f30', 'au_dk': '#b8541f', 'au_br': '#8a4a26',
    # 綠（補一階最暗）
    'gr_dk2': '#2e4a26',
    # 冰藍（清涼藥水）
    'ic_hi': '#d8fbff', 'ic': '#6cd6f5', 'ic_dk': '#3290cc',
    # 粉（戀愛藥水）
    'pk_hi': '#ffb6d4',
    # 火（烈焰藥水）
    'fr_dk': '#a8301f',
    # 暗影（深紫黑）
    'sh_hi': '#7d68a8', 'sh': '#45346c', 'sh_dk': '#281d44',
    # 紫（安眠）
    'vi_hi': '#d8c0ff', 'vi_dk': '#6c4aae',
    # 可可
    'co_hi': '#a3653c', 'co': '#6e3f26', 'co_dk': '#4a2818',
    # 蜂蜜
    'hn_hi': '#ffd76c', 'hn': '#f2a52a', 'hn_dk': '#b86d1a',
    # 糖果彩虹
    'cy_r': '#f24b5c', 'cy_o': '#ff9b3d', 'cy_y': '#ffe35a', 'cy_g': '#6fd15a',
    'cy_b': '#58aef8', 'cy_p': '#bb78ef',
    'cy_r2': '#b52d45', 'cy_o2': '#cf6a24', 'cy_y2': '#d9b232', 'cy_g2': '#3e9a3d',
    'cy_b2': '#3474c8', 'cy_p2': '#8247b8',
    # 時晶
    'cr_hi': '#e6fff4', 'cr': '#6ce6c2', 'cr_dk': '#2c9f86',
    # 玻璃（補暗階）
    'gl_dk': '#7c9db8',
    # 羊皮紙
    'pa_hi': '#f6e6bf', 'pa': '#ddc28e', 'pa_dk': '#b0905d',
    # 薰衣草
    'lav_hi': '#c8a6ff', 'lav': '#8d61d4', 'lav_dk': '#5c3a9c',
    # 毛地黃
    'fx_hi': '#ffb9e6', 'fx': '#e070c0', 'fx_dk': '#a24292',
    # 星鈴花
    'sb_hi': '#ffffff', 'sb': '#d2e8ff', 'sb_dk': '#86ace4',
    # 水滴
    'wa_hi': '#e2f6ff', 'wa': '#78c6f4', 'wa_dk': '#3a84cf',
}
PAL = dict(ROOM_PAL)
PAL.update(EXTRA)
OL = 'outline'


def rgb(key):
    h = PAL[key]
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


# ═══════════════════════════════ 形狀（遮罩＝格子座標的集合）═══════════════════════════════
# 座標：x 往右、y 往下，(x, y) 是一格；連續座標的格子中心是 (x+0.5, y+0.5)。
# 畫的時候不用管邊界（存在 dict 裡），最後 finish() 才量範圍、置中、貼底。

def ell(cx, cy, rx, ry):
    """橢圓：格子中心落在橢圓內的格子。cx/cy 用連續座標（要左右對稱就給 .0 結尾配奇數寬…自己挑）。"""
    out = set()
    for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0:
                out.add((x, y))
    return out


def rect(x0, y0, x1, y1):
    """矩形（含兩端）。"""
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


def poly(pts):
    """多邊形（偶奇規則，測格子中心）。"""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    out = set()
    n = len(pts)
    for y in range(int(min(ys)) - 1, int(max(ys)) + 2):
        for x in range(int(min(xs)) - 1, int(max(xs)) + 2):
            px, py = x + 0.5, y + 0.5
            inside = False
            j = n - 1
            for i in range(n):
                xi, yi = pts[i]
                xj, yj = pts[j]
                if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                    inside = not inside
                j = i
            if inside:
                out.add((x, y))
    return out


def line(x0, y0, x1, y1):
    """Bresenham 直線（整數端點）—— 像素風的斜線要用它，不能用「點到線距離」，那會出現雙格鋸齒。"""
    out = set()
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        out.add((x0, y0))
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


def leaf(ax, ay, bx, by, w, sharp=0.8):
    """葉片形（兩端尖、中間寬）：從 A 到 B，最寬 w。也拿來畫羽毛、花瓣。"""
    out = set()
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    for y in range(int(min(ay, by) - w) - 1, int(max(ay, by) + w) + 2):
        for x in range(int(min(ax, bx) - w) - 1, int(max(ax, bx) + w) + 2):
            px, py = x + 0.5 - ax, y + 0.5 - ay
            t = (px * ux + py * uy) / L
            if not 0.0 <= t <= 1.0:
                continue
            d = abs(px * -uy + py * ux)
            if d <= (w / 2.0) * (math.sin(math.pi * t) ** sharp):
                out.add((x, y))
    return out


def star(cx, cy, ro, ri, n=5, rot=-90.0):
    pts = []
    for i in range(n * 2):
        r = ro if i % 2 == 0 else ri
        a = math.radians(rot + i * 180.0 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return poly(pts)


def shift(m, dx, dy):
    return {(x + dx, y + dy) for x, y in m}


def dilate(m):
    out = set(m)
    for x, y in m:
        out |= {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)}
    return out


def border(m):
    """遮罩自己最外圈的格子（4 鄰接有一邊在外面）。"""
    return {(x, y) for x, y in m
            if not {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} <= m}


# ═══════════════════════════════ 畫布 ═══════════════════════════════

class Icon:
    """一張道具圖示。px：主體層（會補外輪廓）；glow：發光層（星星、蒸氣，不補外輪廓、最後疊上）。"""

    def __init__(self):
        self.px = {}
        self.glow = {}

    # ── 上色 ──
    def put(self, m, col):
        for p in m:
            self.px[p] = col

    def dot(self, x, y, col):
        self.px[(x, y)] = col

    def glow_dot(self, x, y, col):
        self.glow[(x, y)] = col

    def sparkle(self, x, y, big=False, col='go_hi', core='wh'):
        """發光十字星（glow 層）。big＝五格十字＋外延，否則就是一點加四鄰。"""
        self.glow[(x, y)] = core
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            self.glow[(x + d[0], y + d[1])] = col
        if big:
            for d in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                self.glow[(x + d[0], y + d[1])] = col

    def sep(self, m, col):
        """在 m 的外圍、但**已經有東西**的格子描深色 —— 前後重疊的同色球體才分得開。"""
        for p in dilate(m) - m:
            if p in self.px:
                self.px[p] = col

    # ── 打光（光從左上來）──
    def sphere(self, m, ramp, cx, cy, rx, ry, cuts=None):
        """球體明暗：依表面法線跟光的夾角分階。ramp 由亮到暗，3 或 4 階。"""
        lx, ly, lz = -0.55, -0.62, 0.56
        n = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / n, ly / n, lz / n
        if cuts is None:
            cuts = {3: (0.80, 0.30), 4: (0.82, 0.45, 0.05)}[len(ramp)]
        for x, y in m:
            nx = (x + 0.5 - cx) / rx
            ny = (y + 0.5 - cy) / ry
            z = math.sqrt(max(0.0, 1.0 - nx * nx - ny * ny))
            i = nx * lx + ny * ly + z * lz
            k = len(ramp) - 1
            for j, c in enumerate(cuts):
                if i > c:
                    k = j
                    break
            self.px[(x, y)] = ramp[k]

    def cyl(self, m, ramp, lo=0.28, hi=0.72):
        """直立圓柱明暗：每一列左邊亮、右邊暗（瓶頸、杯身、圓木身）。"""
        rows = {}
        for x, y in m:
            rows.setdefault(y, []).append(x)
        for y, xs in rows.items():
            a, b = min(xs), max(xs)
            for x in xs:
                t = (x - a) / max(1, b - a)
                k = 0 if t < lo else (len(ramp) - 1 if t > hi else 1)
                self.px[(x, y)] = ramp[k]

    def flat(self, m, ramp):
        """平面物件：左上邊亮、右下邊暗、中間底色（紙、布、袋子）。ramp＝(亮, 中, 暗)。"""
        for x, y in m:
            if (x + 1, y) not in m or (x, y + 1) not in m:
                self.px[(x, y)] = ramp[2]
            elif (x - 1, y) not in m or (x, y - 1) not in m:
                self.px[(x, y)] = ramp[0]
            else:
                self.px[(x, y)] = ramp[1]

    def stick(self, pts, hi, dk):
        """2 格粗的棍子：沿 Bresenham 線，上面那格亮、下面那格暗（光從上來）。"""
        for x, y in pts:
            self.px[(x, y)] = hi
            self.px[(x, y + 1)] = dk

    # ── 收尾 ──
    def finish(self, name):
        """補外輪廓 → 量範圍 → 水平置中、貼底 → 回傳 24×24 的 [列][欄] 色鍵表（None＝透明）。"""
        body = dict(self.px)
        for x, y in list(self.px):
            for p in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if p not in self.px:
                    body[p] = OL
        for p, c in self.glow.items():
            if p not in body or body[p] == OL:
                body[p] = c
        xs = [p[0] for p in body]
        ys = [p[1] for p in body]
        w = max(xs) - min(xs) + 1
        h = max(ys) - min(ys) + 1
        assert w <= MAXC and h <= MAXC, f'{name}: 內容 {w}×{h} 超過 {MAXC}×{MAXC}'
        ox = (G - w) // 2 - min(xs)
        oy = BOTTOM - max(ys)
        grid = [[None] * G for _ in range(G)]
        for (x, y), c in body.items():
            grid[y + oy][x + ox] = c
        return grid


# ═══════════════════════════════ 共用畫法 ═══════════════════════════════

def cork(ic, x0, y0, w, h, ramp=('le_hi', 'le', 'le_dk')):
    m = rect(x0, y0, x0 + w - 1, y0 + h - 1)
    ic.cyl(m, ramp)
    return m


def glass_body(ic, m, liquid, cx, cy, rx, ry, level, ramp_glass=('gl_hi', 'gl', 'gl_dk')):
    """玻璃瓶身：液面（level 那一列）以下是液體（球體打光），以上是空玻璃；液面頂一列用液體的最亮色。"""
    liq = {p for p in m if p[1] >= level}
    air = m - liq
    ic.cyl(air, ramp_glass)
    ic.sphere(liq, liquid, cx, cy, rx, ry)
    for x, y in liq:
        if (x, y - 1) in air:
            ic.px[(x, y)] = liquid[0]
    return liq


def glint(ic, pts, col='wh'):
    """玻璃反光：一串白點（通常是瓶身左上一道直的）。"""
    for x, y in pts:
        ic.px[(x, y)] = col


def broom(ic, bristle, band, handle=('wd_hi', 'wd_dk')):
    """
    掃帚：柄從右上斜到左下，掃帚尾在左下呈扇形。三把共用同一個骨架，靠尾巴顏色＋配件分辨。
    回傳掃帚尾的遮罩（配件要避開它）。
    """
    ic.stick(line(20, 2, 10, 12), *handle)
    # 掃帚尾：綁帶下方往左下張開的扇形
    tail = poly([(10.5, 11.0), (13.5, 14.0), (10.0, 19.5), (5.0, 22.0), (2.0, 21.5), (2.5, 17.0), (6.0, 12.5)])
    ic.flat(tail, bristle)
    # 一根根的草：從綁帶往外放射的深色線（隔一條畫一條，才有「束」的感覺）
    for ex, ey in ((3, 18), (4, 20), (6, 21), (9, 19)):
        for p in line(9, 14, ex, ey):
            if p in tail and p not in border(tail):
                ic.px[p] = bristle[2]
    # 綁帶：斜的兩格寬
    for p in line(7, 12, 11, 16):
        ic.px[p] = band[1]
        ic.px[(p[0] + 1, p[1] - 1)] = band[0]
    return tail


def packet(ic, tint, art):
    """種子紙包：直立的小紙袋、上緣鋸齒封口，正面畫那種花，右下撒出兩三顆種子。"""
    body = rect(6, 5, 17, 20)
    ic.flat(body, tint)
    # 封口鋸齒（上緣交錯缺格）＋一條壓痕
    for x in range(6, 18):
        if x % 2 == 0:
            ic.px.pop((x, 5), None)
    for x in range(6, 18):
        ic.px[(x, 7)] = tint[2]
    # 正面的白色圖框
    frame = rect(8, 9, 15, 17)
    ic.put(frame, 'li_hi')
    ic.put(border(frame), 'li_dk')
    art(ic)
    # 撒出來的種子
    ic.put({(19, 19), (20, 19), (19, 20), (20, 20)}, 'le')
    ic.px[(19, 19)] = 'le_hi'
    ic.px[(20, 20)] = 'le_dk'


# ═══════════════════════════════ 各道具 ═══════════════════════════════
# 每個函式回傳一個 Icon。座標大致落在 2..21 之間；finish() 會再置中貼底。

# ── 材料 ──────────────────────────────────────────

def draw_wood():
    """木材：三根圓木堆成金字塔，切口朝前（年輪），身體往右後方延伸 —— 跟細細的樹枝分得開。"""
    ic = Icon()
    ends = [(10.5, 10.0), (6.5, 17.0), (14.5, 17.0)]          # 先畫上面那根（在後面）
    for cx, cy in ends:
        body = set()
        for t in range(0, 5):
            body |= ell(cx + t, cy - t * 0.6, 3.8, 3.8)
        ic.flat(body, ('wd_hi', 'wd', 'wd_dk'))
        # 樹皮紋：幾條橫的深色短線
        for k, (dx, dy) in enumerate(((3, -3), (5, -1), (4, 1))):
            p = (int(cx) + dx, int(cy) + dy)
            if p in body and p not in border(body):
                ic.px[p] = 'wd_dk2'
                ic.px[(p[0] + 1, p[1])] = 'wd_dk2'
        face = ell(cx, cy, 3.8, 3.8)
        ic.sep(face, 'wd_dk2')
        ic.put(face, 'pa')
        ic.put(border(face), 'le')                              # 樹皮那一圈
        inner = ell(cx, cy, 2.2, 2.2)
        ic.put(border(inner), 'pa_dk')                          # 年輪
        ic.dot(int(cx), int(cy), 'pa_dk')
        ic.dot(int(cx) - 2, int(cy) - 2, 'pa_hi')
    return ic


def draw_twig():
    """樹枝：三根細枝交叉成一小束，帶分岔與一顆綠芽。"""
    ic = Icon()
    ic.stick(line(3, 17, 20, 7), 'le_hi', 'le_dk')
    ic.stick(line(4, 9, 19, 18), 'le', 'wd_dk')
    ic.stick(line(6, 19, 15, 4), 'le_hi', 'le')
    # 分岔（1 格粗）
    for p in line(14, 10, 18, 4):
        ic.px[p] = 'le'
    for p in line(8, 11, 5, 5):
        ic.px[p] = 'le_dk'
    for p in line(15, 15, 20, 13):
        ic.px[p] = 'le_dk'
    # 綠芽
    ic.put(leaf(18, 4, 21, 2, 2.4), 'gr')
    ic.dot(19, 3, 'gr_hi')
    return ic


def _berry(ic, cx, cy, r, ramp, sep):
    m = ell(cx, cy, r, r)
    ic.sep(m, sep)
    ic.sphere(m, ramp, cx, cy, r, r)
    ic.dot(int(cx - r * 0.45), int(cy - r * 0.45), 'wh')
    return m


def draw_berry():
    """漿果：一簇紅色小圓果（後面先畫），頂上兩片綠葉。"""
    ic = Icon()
    ic.put(leaf(12, 7, 5, 4, 4.0), 'gr')
    ic.put(leaf(12, 7, 19, 3, 4.0), 'gr_dk')
    for p in line(12, 4, 12, 8):
        ic.px[p] = 'gr_dk2'
    ramp = ('rd_hi', 'rd', 'rd_dk')
    for cx, cy in ((9.0, 11.0), (15.5, 10.5), (6.5, 16.0), (12.5, 15.0), (18.0, 15.5), (9.5, 19.5), (15.5, 19.5)):
        _berry(ic, cx, cy, 3.3, ramp, 'rd_dk2')
    return ic


def draw_leaf():
    """
    落葉：一片五裂的橘紅楓葉（葉脈從中心放射到每個裂片尖）、左後方露出一片褐黃的橢圓小葉。
    ⚠️ 前兩版是「一片光滑／鋸齒邊的橢圓葉」，縮小後被看成橘色的魚、玉米。
       五裂楓葉的剪影是「秋天落葉」最不會認錯的形狀，24 格也畫得出來。
    """
    ic = Icon()
    back = leaf(3, 19, 10, 4, 7.0)
    ic.flat(back, ('cy_y', 'cy_y2', 'au_br'))
    for p in line(4, 18, 9, 6):
        if p in back and p not in border(back):
            ic.px[p] = 'au_br'
    cx, cy = 13.0, 11.5
    # 楓葉＝五角星（裂片），中間再墊一個圓讓葉身飽滿；裂片尖朝上、左上、右上、左下、右下
    front = star(cx, cy, 9.0, 5.6, rot=-90.0) | ell(cx, cy + 0.5, 5.6, 5.0)
    # 裂片邊緣的小鋸齒：每個裂片兩側各挖一格，才不會被看成一顆星星
    front -= {(x, y) for x, y in border(front) if (x * 3 + y * 2) % 7 == 0}
    ic.sep(front, 'au_br')
    ic.flat(front, ('au_hi', 'au', 'au_dk'))
    for k in range(5):
        a = math.radians(-90.0 + k * 72.0)
        tx, ty = int(round(cx - 0.5 + 7.0 * math.cos(a))), int(round(cy - 0.5 + 7.0 * math.sin(a)))
        for p in line(int(cx), int(cy), tx, ty):
            if p in front and p not in border(front):
                ic.px[p] = 'au_dk'
    # 葉柄：從中心往下
    for p in line(int(cx), int(cy) + 1, int(cx) + 1, int(cy) + 9):
        ic.px[p] = 'au_br'
    return ic


def draw_herb():
    """藥草：一束綠色枝葉、往上散開，下半段用麻繩綁起來。"""
    ic = Icon()
    stems = [((12, 21), (6, 6)), ((12, 21), (12, 3)), ((12, 21), (18, 6))]
    for (ax, ay), (bx, by) in stems:
        for p in line(ax, ay, bx, by):
            ic.px[p] = 'gr_dk2'
    # 葉片：沿每根莖左右交錯
    leaves = [
        ((7, 8), (3, 6)), ((7, 9), (10, 6)), ((8, 12), (4, 11)), ((9, 13), (6, 15)),
        ((12, 5), (9, 2)), ((12, 6), (15, 3)), ((12, 9), (9, 8)), ((12, 11), (15, 9)),
        ((17, 8), (20, 5)), ((17, 9), (14, 7)), ((16, 12), (20, 11)), ((15, 13), (18, 15)),
    ]
    for i, (a, b) in enumerate(leaves):
        m = leaf(a[0] + 0.5, a[1] + 0.5, b[0] + 0.5, b[1] + 0.5, 3.0)
        ic.flat(m, ('gr_hi', 'gr', 'gr_dk') if i % 2 == 0 else ('gr', 'gr_dk', 'gr_dk2'))
    # 麻繩
    for x in range(10, 15):
        ic.px[(x, 16)] = 'pa_hi'
        ic.px[(x, 17)] = 'pa_dk'
    return ic


def draw_blackberry():
    """黑莓：深紫色、一粒粒小核果組成的長圓莓，頂上綠色花萼，旁邊一片鋸齒葉。"""
    ic = Icon()
    lf = leaf(2, 9, 12, 3, 7.0)
    ic.flat(lf, ('gr_hi', 'gr', 'gr_dk'))
    for p in line(3, 9, 11, 4):
        ic.px[p] = 'gr_dk'

    def drupe_berry(cx, cy, rx, ry):
        m = ell(cx, cy, rx, ry)
        ic.sep(m, 'bk_dk2')
        ic.sphere(m, ('bk_hi', 'bk', 'bk_dk', 'bk_dk2'), cx, cy, rx, ry)
        # 小核果：每隔一格的格點打亮一階 → 一顆顆的顆粒感
        up = {'bk_dk2': 'bk_dk', 'bk_dk': 'bk', 'bk': 'bk_hi', 'bk_hi': 'pu_hi'}
        for x, y in m:
            if (x + (y // 2)) % 2 == 0 and y % 2 == 0 and (x, y) not in border(m):
                ic.px[(x, y)] = up[ic.px[(x, y)]]
        ic.dot(int(cx - rx * 0.5), int(cy - ry * 0.55), 'wh')
        # 花萼
        top = int(cy - ry)
        for dx in (-2, -1, 0, 1, 2):
            ic.px[(int(cx) + dx, top)] = 'gr' if abs(dx) < 2 else 'gr_dk'
        ic.px[(int(cx), top - 1)] = 'gr_dk'
        ic.px[(int(cx), top - 2)] = 'gr_dk2'
        return m

    drupe_berry(16.0, 11.5, 4.0, 5.0)
    drupe_berry(10.5, 15.5, 5.0, 6.0)
    return ic


def draw_goldapple():
    """金蘋果：飽滿的蘋果形（頂部凹一點）、金黃四階、褐梗綠葉，旁邊一顆閃光。"""
    ic = Icon()
    m = ell(9.5, 14.0, 6.0, 6.5) | ell(14.5, 14.0, 6.0, 6.5) | ell(12.0, 16.0, 7.5, 5.5)
    m -= {(11, 7), (12, 7), (11, 8), (12, 8)}
    ic.sphere(m, ('go_hi', 'go', 'go_dk', 'go_dk2'), 12.0, 14.0, 8.5, 7.5)
    ic.dot(7, 11, 'wh')
    ic.dot(8, 10, 'wh')
    ic.dot(7, 10, 'go_hi')
    for p in line(12, 9, 13, 5):
        ic.px[p] = 'le_dk'
    lf = leaf(13.5, 6.5, 19.5, 3.5, 4.0)
    ic.flat(lf, ('gr_hi', 'gr', 'gr_dk'))
    ic.sparkle(20, 9, col='go_hi')
    return ic


def draw_blueberry():
    """藍莓：一只米白小碗裝得滿滿，碗口堆出一顆顆藍莓（每顆頂上一個深色小冠）。"""
    ic = Icon()
    ramp = ('bb_hi', 'bb', 'bb_dk')
    for cx, cy in ((12.0, 9.0), (8.5, 10.5), (15.5, 10.5), (5.5, 13.5), (10.0, 13.0), (14.0, 13.0), (18.5, 13.5)):
        m = _berry(ic, cx, cy, 2.9, ramp, 'bl_dk2')
        ic.dot(int(cx), int(cy), 'bb_dk')
    # 碗：下半個橢圓
    bowl = {p for p in ell(12.0, 15.0, 10.0, 6.5) if p[1] >= 15}
    ic.sep(bowl, 'bl_dk2')
    ic.cyl(bowl, ('li_hi', 'li', 'li_dk'), lo=0.3, hi=0.75)
    for x in range(2, 23):
        if (x, 15) in bowl:
            ic.px[(x, 15)] = 'li_hi'
    for x in range(3, 22):
        if (x, 17) in bowl:
            ic.px[(x, 17)] = 'bl' if x % 3 else 'bl_hi'       # 碗上的一圈藍花紋
    return ic


# ── 藥水成品 ──────────────────────────────────────

def draw_potion_blue():
    """清涼藥水：圓底長頸燒瓶、冰藍色液體、軟木塞；液體裡一塊冰。"""
    ic = Icon()
    body = ell(12.0, 15.0, 7.0, 6.5)
    neck = rect(10, 4, 13, 9)
    ic.cyl(neck, ('gl_hi', 'gl', 'gl_dk'))
    ic.put({(9, 4), (14, 4)}, 'gl_dk')
    glass_body(ic, body, ('ic_hi', 'ic', 'ic_dk'), 12.0, 15.0, 7.0, 6.5, level=12)
    cork(ic, 10, 1, 4, 3)
    glint(ic, [(8, 13), (8, 14), (7, 15)])
    # 冰塊
    ice = rect(13, 15, 15, 17)
    ic.put(ice, 'ic_hi')
    ic.put({(15, 17), (14, 17), (15, 16)}, 'gl')
    return ic


def draw_potion_pink():
    """戀愛藥水：愛心形的瓶子裝粉紅液體、短頸軟木塞。"""
    ic = Icon()
    heart = ell(8.5, 12.0, 4.6, 4.6) | ell(15.5, 12.0, 4.6, 4.6) | poly([(4.0, 13.0), (20.0, 13.0), (12.0, 21.5)])
    neck = rect(11, 5, 12, 8)
    ic.cyl(neck, ('gl_hi', 'gl', 'gl_dk'))
    ic.sphere(heart, ('pk_hi', 'pink', 'pink_dk'), 10.5, 13.0, 8.5, 8.5)
    for x, y in list(heart):
        if y <= 8:
            ic.px[(x, y)] = 'gl'
    cork(ic, 10, 3, 4, 2, ('pk_hi', 'pink', 'pink_dk'))
    glint(ic, [(6, 10), (6, 11), (7, 9)])
    ic.sparkle(19, 5, col='pk_hi')
    return ic


def draw_potion_dark():
    """暗影藥水：矮胖的深色玻璃瓶、紫黑液體裡有幾縷暗紫的漩渦，瓶口封紅色蠟。"""
    ic = Icon()
    body = ell(12.0, 15.5, 8.0, 6.0)
    neck = rect(10, 7, 13, 10)
    ic.cyl(neck, ('sh_hi', 'sh', 'sh_dk'))
    ic.sphere(body, ('sh_hi', 'sh', 'sh_dk'), 12.0, 15.5, 8.0, 6.0, cuts=(0.85, 0.40))
    for x, y in ((9, 14), (10, 13), (11, 13), (12, 14), (14, 16), (15, 17), (16, 17), (13, 15)):
        ic.px[(x, y)] = 'violet'
    # 紅蠟封：蓋住瓶口並往下滴
    wax = rect(9, 5, 14, 7) | {(9, 8), (13, 8), (13, 9)}
    ic.flat(wax, ('rd_hi', 'rd', 'rd_dk'))
    # 瓶身上半圈描一道亮紫的玻璃邊：瓶子本身很暗，擺在深色 UI 底上會跟外輪廓一起消失
    for x, y in border(body):
        if y <= 15:
            ic.px[(x, y)] = 'pu_hi'
    glint(ic, [(6, 14), (6, 15), (7, 13)], 'sh_hi')
    ic.dot(7, 13, 'wh')
    return ic


def draw_potion_red():
    """
    烈焰藥水：寬底三角錐瓶、黑色瓶塞；瓶裡的液體本身就是火 —— 液面不是平的，而是往上竄的火舌，
    由下往上暗紅→紅→橘→黃。瓶外飄幾顆火星。
    ⚠️ 第一版是「錐瓶＋瓶口冒火苗」，縮小後整個看起來像一根蠟燭。火要關在瓶子裡、瓶口要有塞子才像藥水。
    """
    ic = Icon()
    flask = poly([(9.5, 8.0), (14.5, 8.0), (14.5, 11.0), (21.0, 21.0), (3.0, 21.0), (9.5, 11.0)])
    # 每一欄火舌的頂端（由左到右高低交錯）
    tops = {4: 18, 5: 16, 6: 14, 7: 15, 8: 12, 9: 13, 10: 11, 11: 12, 12: 9, 13: 11,
            14: 12, 15: 10, 16: 13, 17: 14, 18: 15, 19: 17, 20: 18}
    for x, y in flask:
        if y < tops.get(x, 99):
            c = 'gl_dk' if x >= 13 else 'gl'
        elif y - tops[x] <= 1 or y < 13:
            c = 'fire_y'
        elif y < 16:
            c = 'fire_o'
        elif y < 19:
            c = 'fire_r'
        else:
            c = 'fr_dk'
        ic.px[(x, y)] = c
    cork(ic, 10, 5, 4, 3, ('ir_hi', 'ir', 'ir_dk'))
    glint(ic, [(9, 12), (8, 13)], 'gl_hi')
    ic.glow_dot(17, 6, 'fire_o')
    ic.glow_dot(18, 4, 'fire_y')
    ic.glow_dot(6, 7, 'fire_o')
    return ic


def draw_cocoa():
    """溫暖熱可可：米白馬克杯（紅色條紋、右邊把手），杯口一圈可可、浮一塊棉花糖，上面冒熱氣。"""
    ic = Icon()
    handle = ell(18.0, 14.5, 3.5, 4.0) - ell(18.0, 14.5, 1.6, 2.1)
    ic.flat(handle, ('li_hi', 'li', 'li_dk'))
    mug = rect(5, 9, 16, 20) - {(5, 20), (16, 20)}
    ic.sep(mug, 'li_dk')
    ic.cyl(mug, ('li_hi', 'li', 'li_dk'))
    for x in range(5, 17):
        ic.px[(x, 16)] = 'rd' if x < 14 else 'rd_dk'
        ic.px[(x, 17)] = 'rd_dk'
    top = rect(6, 9, 15, 10)
    ic.put(top, 'co')
    ic.put({(6, 10), (7, 10), (8, 10)}, 'co_hi')
    ic.put({(12, 9), (13, 9), (13, 10), (12, 10)}, 'wh')
    ic.px[(13, 10)] = 'li_dk'
    # 熱氣（glow 層：不補外輪廓）
    for x, y in ((8, 7), (9, 6), (8, 5), (9, 4), (12, 6), (13, 5), (12, 4), (13, 3)):
        ic.glow_dot(x, y, 'st_hi')
    return ic


def draw_amber_jug():
    """蜂蜜藥劑：圓胖的玻璃罐裝滿琥珀色蜂蜜，罐口綁米白布蓋，蜂蜜從罐口滴下來。"""
    ic = Icon()
    jar = ell(12.0, 15.0, 8.0, 6.5) | rect(7, 8, 16, 12)
    ic.sphere(jar, ('hn_hi', 'hn', 'hn_dk'), 11.5, 14.5, 8.5, 7.5)
    # 標籤
    lab = rect(9, 14, 15, 17)
    ic.put(lab, 'pa_hi')
    ic.put(border(lab), 'pa_dk')
    ic.put({(11, 15), (12, 15), (13, 16)}, 'hn_dk')
    # 布蓋：比罐口寬、下緣波浪
    cloth = rect(5, 6, 18, 9) - {(5, 9), (8, 9), (11, 9), (14, 9), (18, 9), (18, 6), (5, 6)}
    ic.flat(cloth, ('li_hi', 'li', 'li_dk'))
    for x in range(6, 18):
        ic.px[(x, 8)] = 'rd' if x % 2 else 'rd_dk'
    # 滴下來的蜂蜜
    ic.put({(16, 10), (16, 11), (17, 11), (17, 12)}, 'hn_hi')
    glint(ic, [(6, 13), (6, 14), (7, 12)])
    return ic


def draw_gold_bottle():
    """黃金藥劑：細高的方肩瓶裝金色液體、金蓋，液體裡浮著閃光。"""
    ic = Icon()
    body = rect(8, 9, 15, 20) - {(8, 9), (15, 9), (8, 20), (15, 20)}
    neck = rect(10, 6, 13, 8)
    ic.cyl(neck, ('gl_hi', 'gl', 'gl_dk'))
    liq = {p for p in body if p[1] >= 11}
    ic.cyl(body - liq, ('gl_hi', 'gl', 'gl_dk'))
    ic.cyl(liq, ('go_hi', 'go', 'go_dk'))
    for x in range(8, 16):
        if (x, 11) in liq:
            ic.px[(x, 11)] = 'go_hi'
    cap = rect(9, 3, 14, 5)
    ic.cyl(cap, ('go_hi', 'go', 'go_dk'))
    ic.px[(10, 2)] = 'go'
    ic.px[(11, 2)] = 'go_hi'
    ic.px[(12, 2)] = 'go'
    ic.px[(13, 2)] = 'go_dk'
    glint(ic, [(9, 12), (9, 13), (9, 14), (9, 16)])
    ic.put({(12, 14), (13, 17), (11, 19)}, 'wh')
    ic.sparkle(19, 7, big=True)
    return ic


def draw_broom_purple():
    """夜影掃帚：深紫的掃帚尾、金色綁帶、深色柄；柄上方掛一彎小月亮。"""
    ic = Icon()
    broom(ic, ('pu_hi', 'pu', 'pu_dk2'), ('go_hi', 'go'), ('wd_dk', 'wd_dk2'))
    moon = ell(18.0, 13.0, 3.2, 3.2) - ell(19.5, 12.0, 2.6, 2.6)
    ic.put(moon, 'go_hi')
    return ic


def draw_broom_blue():
    """星光掃帚：淡藍白的掃帚尾、藍色綁帶，掃帚尾後面拖出一串金色小星（glow 層）。"""
    ic = Icon()
    broom(ic, ('bb_pale', 'bb_hi', 'bl'), ('bb_pale', 'bl'))
    ic.sparkle(16, 18, big=True)
    ic.sparkle(20, 13)
    ic.sparkle(14, 20)
    ic.glow_dot(22, 9, 'go_hi')
    return ic


def draw_broom_white():
    """
    羽翼掃帚：自然稻草色的掃帚尾，柄的上半往左上展開三根白羽毛（像一邊翅膀）。
    ⚠️ 第一版把兩根羽毛畫在柄的兩側、跟柄垂直 —— 縮小後變成一個「×」，像螺旋槳。
       羽毛要全部擺在同一側、扇形展開，才讀得出「翅膀」。
    """
    ic = Icon()
    broom(ic, ('pa_hi', 'pa', 'pa_dk'), ('rd_hi', 'rd'))
    # 由下往上畫（上面那根蓋住下面那根的根部），彼此之間用外輪廓色分開 —— 用灰色分的話三根糊成一團灰
    for (ax, ay), (bx, by), w in (((14, 9), (4, 9), 5.0), ((16, 7), (9, 2), 5.0)):
        f = leaf(ax + 0.5, ay + 0.5, bx + 0.5, by + 0.5, w, sharp=0.5)
        ic.sep(f, 'outline')
        ic.flat(f, ('wh', 'li_hi', 'st'))
        for p in line(ax, ay, bx, by):
            if p in f and p not in border(f):
                ic.px[p] = 'li_dk'
    ic.stick(line(20, 2, 13, 9), 'wd_hi', 'wd_dk')     # 柄整段蓋回羽毛上面（羽毛綁在柄「後面」，柄要看得到）
    return ic


def draw_potion_lavender():
    """安眠藥水：洋蔥形（上尖下圓）的瓶子裝紫色液體，瓶身印一彎淡黃月亮。"""
    ic = Icon()
    body = ell(12.0, 15.5, 7.0, 6.0) | poly([(6.0, 13.0), (18.0, 13.0), (13.5, 8.0), (10.5, 8.0)])
    neck = rect(10, 5, 13, 8)
    ic.cyl(neck, ('gl_hi', 'gl', 'gl_dk'))
    glass_body(ic, body, ('vi_hi', 'violet', 'vi_dk'), 12.0, 15.0, 7.0, 6.5, level=11)
    cork(ic, 10, 2, 4, 3)
    moon = ell(13.0, 16.0, 3.0, 3.0) - ell(14.3, 15.0, 2.4, 2.4)
    ic.put(moon, 'n_star')
    glint(ic, [(7, 14), (7, 15), (8, 13)])
    # 「Zz」小字在右上（glow 層）
    for x, y in ((17, 3), (18, 3), (18, 4), (17, 5), (18, 5), (20, 1), (21, 1), (20, 2)):
        ic.glow_dot(x, y, 'vi_hi')
    return ic


def draw_perfume_rose():
    """花香水：八角形的香水瓶裝毛地黃粉紫色、金色瓶頸，側邊接一顆按壓噴頭球。"""
    ic = Icon()
    body = rect(5, 10, 16, 21) - {(5, 10), (6, 10), (5, 11), (16, 10), (15, 10), (16, 11),
                                  (5, 21), (6, 21), (5, 20), (16, 21), (15, 21), (16, 20)}
    ic.sphere(body, ('fx_hi', 'fx', 'fx_dk'), 10.5, 15.5, 7.0, 7.0)
    # 切面：中間一道直的亮線
    for y in range(12, 20):
        ic.px[(8, y)] = 'fx_hi'
    ic.put({(7, 12), (7, 13)}, 'wh')
    collar = rect(8, 6, 13, 9)
    ic.cyl(collar, ('go_hi', 'go', 'go_dk'))
    # 噴頭的管子 → 球
    for p in line(14, 7, 17, 7):
        ic.px[p] = 'go_dk'
    bulb = ell(19.0, 9.0, 2.6, 3.2)
    ic.sphere(bulb, ('rd_hi', 'rd', 'rd_dk'), 19.0, 9.0, 2.6, 3.2)
    ic.put({(19, 12), (19, 13), (18, 14), (20, 14)}, 'go')     # 流蘇
    ic.dot(10, 5, 'go_dk')
    ic.dot(11, 5, 'go')
    return ic


def draw_potion_star():
    """星光藥劑：圓底燒瓶裝夜空藍液體、裡面滿是小星，瓶底一層亮沙；瓶塞是一顆金星。"""
    ic = Icon()
    body = ell(12.0, 15.0, 7.0, 6.5)
    neck = rect(10, 6, 13, 9)
    ic.cyl(neck, ('gl_hi', 'gl', 'gl_dk'))
    glass_body(ic, body, ('bl_hi', 'bl', 'bl_dk', 'bl_dk2'), 12.0, 15.0, 7.0, 6.5, level=10)
    for x, y in ((9, 13), (14, 12), (12, 16), (16, 15), (8, 17)):
        ic.px[(x, y)] = 'n_star'
    for x in range(8, 17):
        if (x, 20) in body:
            ic.px[(x, 20)] = 'go_hi' if x % 2 else 'go'
    glint(ic, [(7, 13), (7, 14), (8, 12)], 'gl_hi')
    st = star(12.0, 4.0, 4.2, 1.9)
    ic.put(st, 'go')
    ic.put({(11, 3), (11, 4), (12, 2)}, 'go_hi')
    ic.put({(13, 5), (14, 5)}, 'go_dk')
    return ic


# ── 糖果鎮商品 ──────────────────────────────────────

def draw_candy_apple():
    """焦糖蘋果棒：紅蘋果上半裹一層焦糖、往下滴，頂上插一根木棒 —— 跟金蘋果靠「棒子＋紅色」分開。"""
    ic = Icon()
    apple = ell(12.0, 15.5, 7.5, 6.0)
    ic.sphere(apple, ('rd_hi', 'rd', 'rd_dk', 'rd_dk2'), 12.0, 15.5, 7.5, 6.0)
    drip = {(6, 15), (6, 16), (9, 15), (9, 16), (9, 17), (13, 15), (16, 15), (16, 16), (17, 15)}
    coat = {p for p in apple if p[1] <= 14} | (drip & apple)
    ic.sphere(coat, ('cu_hi', 'cu', 'cu_dk'), 12.0, 15.5, 7.5, 6.0)
    ic.dot(8, 11, 'wh')
    ic.dot(9, 11, 'cu_hi')
    ic.dot(8, 17, 'rd_hi')
    stick = rect(11, 2, 12, 9)
    ic.cyl(stick, ('pa_hi', 'pa', 'pa_dk'), lo=0.5, hi=0.5)
    return ic


def draw_gator_bag():
    """
    鱷魚軟糖袋：上緣折起的紙袋、紅色封條，正面印一顆綠色鱷魚頭（側面、張嘴露白牙）。
    ⚠️ 第一版是「透明窗裡看得到一堆彩色軟糖」：24 格裡每顆軟糖只有 2～4 格，縮小後只剩一團雜色。
       一個大大的鱷魚頭才一眼看得出「鱷魚軟糖」。
    """
    ic = Icon()
    bag = poly([(5.0, 6.0), (19.0, 6.0), (20.0, 22.0), (4.0, 22.0)])
    ic.flat(bag, ('li_hi', 'li', 'li_dk'))
    fold = {p for p in bag if p[1] <= 8}
    ic.put(fold, 'pa')
    for x in range(4, 21):
        if (x, 8) in bag:
            ic.px[(x, 8)] = 'pa_dk'
    for x in range(10, 14):
        for y in (5, 6, 7, 8, 9):
            ic.px[(x, y)] = 'cy_r' if x < 13 else 'cy_r2'
    # 鱷魚頭（面向右）：後腦＋眼睛凸起＋長吻；上下顎之間一條嘴線、上下交錯的白牙
    head = (rect(6, 12, 10, 18) - {(6, 12), (6, 18)}) | rect(8, 10, 10, 11) | rect(11, 13, 18, 15) \
        | rect(11, 16, 17, 18) - {(18, 13)}
    ic.put(head, 'cy_g')
    for x, y in head:
        if (x, y + 1) not in head or (x + 1, y) not in head:
            ic.px[(x, y)] = 'cy_g2'
    ic.put({(8, 10), (9, 10)}, 'gr_hi')
    ic.px[(9, 11)] = 'wh'
    ic.px[(10, 11)] = 'outline'
    for x in range(11, 18):
        ic.px[(x, 16)] = 'gr_dk2'                 # 嘴線
    for x in (12, 14, 16):
        ic.px[(x, 16)] = 'wh'                     # 上排牙
    for x in (13, 15):
        ic.px[(x, 17)] = 'wh'                     # 下排牙
    ic.px[(17, 13)] = 'gr_dk2'                    # 鼻孔
    return ic


def draw_gobstopper():
    """永恆彩球糖：一顆彩虹橫紋的大圓糖球（每條色帶自己分亮暗），一大一小兩個高光。"""
    ic = Icon()
    cx, cy, r = 12.0, 12.5, 9.0
    ball = ell(cx, cy, r, r)
    bands = [('cy_p', 'cy_p2'), ('cy_b', 'cy_b2'), ('cy_g', 'cy_g2'), ('cy_y', 'cy_y2'), ('cy_o', 'cy_o2'), ('cy_r', 'cy_r2')]
    top = min(p[1] for p in ball)
    for x, y in ball:
        i = min(len(bands) - 1, (y - top) // 3)
        lit, dk = bands[len(bands) - 1 - i]
        nx, ny = (x + 0.5 - cx) / r, (y + 0.5 - cy) / r
        ic.px[(x, y)] = dk if nx + ny * 0.6 > 0.45 else lit
    ic.put({(7, 7), (8, 7), (7, 8), (6, 9)}, 'wh')
    ic.dot(9, 6, 'wh')
    return ic


def draw_map():
    """糖李礦坑地圖：攤開的羊皮紙、左右各一捲軸；紅色虛線路徑通到 ×，× 旁邊畫一顆紫色糖李。"""
    ic = Icon()
    sheet = rect(4, 6, 19, 18)
    ic.flat(sheet, ('pa_hi', 'pa', 'pa_dk'))
    for x0 in (2, 19):
        roll = rect(x0, 5, x0 + 2, 19)
        ic.cyl(roll, ('pa', 'pa_dk', 'le'), lo=0.34, hi=0.66)
    # 小山（礦坑）
    for p in line(6, 11, 8, 9) | line(8, 9, 10, 11):
        ic.px[p] = 'le_dk'
    ic.dot(8, 10, 'ir')
    # 虛線路徑
    path = [(7, 15), (8, 15), (10, 15), (11, 14), (12, 12), (13, 11), (15, 10)]
    for x, y in path:
        ic.px[(x, y)] = 'rd'
    # ×
    for d in (-1, 0, 1):
        ic.px[(16 + d, 13 + d)] = 'rd_dk'
        ic.px[(16 + d, 13 - d)] = 'rd_dk'
    plum = ell(16.0, 9.0, 1.6, 1.6)
    ic.put(plum, 'cy_p')
    ic.dot(15, 8, 'vi_hi')
    return ic


def draw_pixiedust():
    """妖精粉小袋：淡紫的束口布袋、金色抽繩，袋口溢出會發光的粉（glow 層的星星點點）。"""
    ic = Icon()
    sack = ell(11.5, 16.0, 7.0, 5.5) | poly([(8.0, 12.0), (15.0, 12.0), (13.5, 10.0), (9.5, 10.0)])
    ic.sphere(sack, ('vi_hi', 'violet', 'vi_dk'), 11.0, 15.0, 7.5, 6.5)
    ruffle = ell(11.5, 8.0, 4.0, 2.0)
    ic.sep(ruffle, 'vi_dk')
    ic.flat(ruffle, ('vi_hi', 'violet', 'vi_dk'))
    for x in range(9, 15):
        ic.px[(x, 10)] = 'go'
    ic.put({(15, 10), (16, 11), (16, 12)}, 'go_dk')
    ic.dot(8, 13, 'wh')
    # 粉：從袋口往右上飄
    ic.sparkle(16, 5, big=True, col='pk_hi')
    ic.sparkle(20, 9, col='ic_hi')
    ic.sparkle(9, 3, col='go_hi')
    for x, y in ((13, 6), (18, 3), (21, 5), (19, 13), (6, 6)):
        ic.glow_dot(x, y, 'pk_hi' if (x + y) % 2 else 'ic_hi')
    return ic


def draw_staff():
    """時晶法杖：木杖從左下斜到右上，金色杖箍，杖頭嵌一大塊青綠時晶（左亮右暗兩個切面）。"""
    ic = Icon()
    ic.stick(line(4, 20, 14, 10), 'le_hi', 'le_dk')
    collar = {(14, 9), (15, 9), (15, 8), (13, 10), (14, 10), (16, 8)}
    ic.put(collar, 'go')
    ic.put({(13, 9), (14, 8)}, 'go_hi')
    crystal = poly([(15.0, 7.0), (17.0, 2.0), (21.5, 2.5), (20.5, 7.5), (17.5, 10.0)])
    for x, y in crystal:
        # 對角線分兩個切面：左上亮、右下暗，中間一道最亮的稜
        s = (x - 15) - (y - 1) * 0.2
        ic.px[(x, y)] = 'cr_hi' if s < 2.0 else ('cr' if s < 4.4 else 'cr_dk')
    ic.dot(18, 3, 'wh')
    ic.sparkle(9, 6, col='cr')
    ic.glow_dot(6, 10, 'cr_hi')
    return ic


# ── 種子（紙包）與花 ──────────────────────────────────────

def _lav_art(ic):
    for p in line(12, 16, 12, 11):
        ic.px[p] = 'gr_dk'
    for x, y in ((11, 10), (12, 10), (12, 11), (11, 12), (13, 12), (12, 13), (11, 14), (13, 14)):
        ic.px[(x, y)] = 'lav'
    ic.px[(12, 9)] = 'lav_hi'


def _fox_art(ic):
    for p in line(11, 16, 11, 10):
        ic.px[p] = 'gr_dk'
    for x, y in ((12, 10), (12, 11), (13, 12), (13, 13), (12, 14), (12, 15), (10, 13), (9, 13), (10, 12)):
        ic.px[(x, y)] = 'fx'
    ic.px[(13, 11)] = 'fx_hi'


def _star_art(ic):
    st = star(11.5, 13.0, 3.6, 1.6)
    ic.put(st, 'bl_hi')
    ic.put({(11, 12), (11, 13), (12, 13)}, 'go_hi')


def draw_seed_lavender():
    ic = Icon()
    packet(ic, ('vi_hi', 'violet', 'vi_dk'), _lav_art)
    return ic


def draw_seed_foxglove():
    ic = Icon()
    packet(ic, ('fx_hi', 'fx', 'fx_dk'), _fox_art)
    return ic


def draw_seed_starbell():
    ic = Icon()
    packet(ic, ('bl_hi', 'bl', 'bl_dk'), _star_art)
    return ic


def draw_lavender():
    """薰衣草：三根花穗一束（紫色一粒粒交錯的小花）、下面紮一條米白緞帶。"""
    ic = Icon()
    tops = ((6, 4), (12, 2), (18, 4))
    for tx, ty in tops:
        for p in line(12, 20, tx, ty + 7):
            ic.px[p] = 'gr_dk'
        for k in range(8):
            y = ty + k
            # 花穗往下會稍微往中間收（沿著莖的方向）
            x = tx + round((12 - tx) * k / 18.0)
            ic.px[(x, y)] = 'lav' if k % 2 else 'lav_hi'
            if k % 2 == 0:
                ic.px[(x + 1, y)] = 'lav_dk'
            else:
                ic.px[(x - 1, y)] = 'lav'
                ic.px[(x + 1, y)] = 'lav_dk'
        ic.px[(tx, ty - 1)] = 'lav_hi'
    for lf in (leaf(11.5, 18.0, 7.0, 14.0, 2.6), leaf(12.5, 18.0, 17.0, 14.0, 2.6)):
        ic.put(lf, 'gr')
    for x in range(10, 15):
        ic.px[(x, 17)] = 'li_hi'
    ic.put({(9, 18), (15, 18), (9, 19), (15, 19)}, 'li')
    return ic


def draw_foxglove():
    """毛地黃：一根高花莖，兩側交錯掛著往下垂的粉紫鐘形花（花口有深色斑點），根部兩片大葉。"""
    ic = Icon()
    for p in line(12, 20, 12, 3):
        ic.px[p] = 'gr_dk'
    for lf in (leaf(12.0, 19.5, 4.0, 15.0, 4.0), leaf(12.0, 19.5, 20.0, 16.0, 4.0)):
        ic.flat(lf, ('gr_hi', 'gr', 'gr_dk'))
    bells = [(9, 13, 3), (15, 11, 3), (9, 8, 2), (15, 6, 2), (11, 3, 1)]
    for bx, by, s in bells:
        m = leaf(bx + 0.5, by - 0.5, bx + 0.5, by + s + 1.5, s * 1.6 + 1.2, sharp=0.35)
        m = {p for p in m if p[1] <= by + s}
        ic.sep(m, 'gr_dk2')
        ic.flat(m, ('fx_hi', 'fx', 'fx_dk'))
        # 花口：最底一列中間一點深色
        ic.px[(bx, by + s)] = 'pu_dk'
    ic.dot(12, 2, 'gr')
    return ic


def draw_starbell():
    """星鈴花：三朵五瓣星形的藍白小花（金黃花心）在綠莖上，四周有微光（glow 層）。"""
    ic = Icon()
    for a, b in (((12, 21), (8, 9)), ((12, 21), (16, 7)), ((12, 21), (13, 14))):
        for p in line(a[0], a[1], b[0], b[1]):
            ic.px[p] = 'gr_dk'
    for lf in (leaf(12.0, 19.0, 5.0, 16.0, 3.0), leaf(12.5, 19.0, 19.0, 17.0, 3.0)):
        ic.put(lf, 'gr')
    for cx, cy, r in ((8.0, 8.0, 5.0), (16.0, 6.5, 4.6), (13.5, 14.0, 4.2)):
        st = star(cx, cy, r, r * 0.48)
        ic.sep(st, 'sb_dk')
        ic.sphere(st, ('sb_hi', 'sb', 'sb_dk'), cx, cy, r, r, cuts=(0.75, 0.15))
        ic.put({(int(cx), int(cy)), (int(cx) - 1, int(cy))}, 'go_hi')
    ic.sparkle(3, 13, col='sb')
    ic.sparkle(20, 12, col='sb')
    return ic


def draw_water_drop():
    """水滴：上尖下圓的水滴、左上高光（花圃澆水的水花用）。"""
    ic = Icon()
    m = ell(12.0, 15.0, 5.5, 5.5) | poly([(6.8, 14.0), (17.2, 14.0), (12.0, 4.0)])
    ic.sphere(m, ('wa_hi', 'wa', 'wa_dk'), 12.0, 14.0, 6.0, 7.5)
    ic.put({(9, 13), (9, 14), (10, 12)}, 'wh')
    return ic


# ═══════════════════════════════ 道具表 ═══════════════════════════════
# (中文名, 檔名, 畫法)。檔名照 Data/Items.cs 與 Data/Garden.cs 的舊檔名（GameArt 換資料夾就好）；
# 花＝<Art>、種子＝<Art>-seed、水滴＝water-drop。
# ⚠️ 糖果鎮的舊檔名是歷史包袱：item-lollipop 其實是「焦糖蘋果棒」、item-gobstopper 才是彩球糖。
ITEMS = [
    ('木材', 'wood', draw_wood),
    ('樹枝', 'twig', draw_twig),
    ('漿果', 'berry', draw_berry),
    ('落葉', 'leaf', draw_leaf),
    ('藥草', 'herb', draw_herb),
    ('黑莓', 'blackberry', draw_blackberry),
    ('金蘋果', 'goldapple', draw_goldapple),
    ('藍莓', 'blueberry', draw_blueberry),
    ('清涼藥水', 'potion_blue', draw_potion_blue),
    ('戀愛藥水', 'potion_pink', draw_potion_pink),
    ('暗影藥水', 'potion_dark', draw_potion_dark),
    ('烈焰藥水', 'potion_red', draw_potion_red),
    ('溫暖熱可可', 'cocoa_mug', draw_cocoa),
    ('蜂蜜藥劑', 'amber_jug', draw_amber_jug),
    ('黃金藥劑', 'gold_bottle', draw_gold_bottle),
    ('夜影掃帚', 'broom_purple', draw_broom_purple),
    ('星光掃帚', 'broom_blue', draw_broom_blue),
    ('羽翼掃帚', 'broom_white', draw_broom_white),
    ('安眠藥水', 'potion_lavender', draw_potion_lavender),
    ('花香水', 'perfume_rose', draw_perfume_rose),
    ('星光藥劑', 'potion_star', draw_potion_star),
    ('焦糖蘋果棒', 'item-lollipop', draw_candy_apple),
    ('鱷魚軟糖袋', 'item-treats', draw_gator_bag),
    ('永恆彩球糖', 'item-gobstopper', draw_gobstopper),
    ('糖李礦坑地圖', 'item-map', draw_map),
    ('妖精粉小袋', 'item-pixiedust', draw_pixiedust),
    ('時晶法杖', 'item-staff', draw_staff),
    ('薰衣草種子', 'lavender-seed', draw_seed_lavender),
    ('毛地黃種子', 'foxglove-seed', draw_seed_foxglove),
    ('星鈴花種子', 'starbell-seed', draw_seed_starbell),
    ('薰衣草', 'lavender', draw_lavender),
    ('毛地黃', 'foxglove', draw_foxglove),
    ('星鈴花', 'starbell', draw_starbell),
    ('水滴', 'water-drop', draw_water_drop),
]


# ═══════════════════════════════ 輸出 ═══════════════════════════════

def to_image(grid):
    """24×24 色鍵表 → RGBA（alpha 只有 0／255）→ NEAREST 放大成 96×96。"""
    im = Image.new('RGBA', (G, G), (0, 0, 0, 0))
    pix = im.load()
    for y in range(G):
        for x in range(G):
            c = grid[y][x]
            if c is not None:
                pix[x, y] = rgb(c) + (255,)
    return im.resize((G * SCALE, G * SCALE), Image.NEAREST)


def render_all():
    out, errs = [], []
    for name, fname, fn in ITEMS:
        try:
            grid = fn().finish(name)
        except AssertionError as e:          # 一次列出所有超框的，不要改一張跑一次
            errs.append(str(e))
            continue
        colors = {c for row in grid for c in row if c is not None}
        out.append((name, fname, grid, to_image(grid), len(colors)))
    if errs:
        sys.exit('\n'.join(errs))
    return out


def find_font(size):
    for f in ('C:/Windows/Fonts/msjh.ttc', 'C:/Windows/Fonts/msjhbd.ttc', 'C:/Windows/Fonts/mingliu.ttc'):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def preview(arts, outdir):
    """
    總覽圖：
      items_dark.png / items_light.png —— 每張放大 6 倍（144px）＋下方名字、色數，深色底與淺色底各一張；
      items_actual.png —— 同一排看 96px（輸出 1:1）、46／34／26px（UI 格子的 NEAREST 縮小）、24px（邏輯 1:1）。
    """
    os.makedirs(outdir, exist_ok=True)
    font = find_font(15)
    cols = 9
    cw, chh = 160, 184
    rows = (len(arts) + cols - 1) // cols
    files = []
    for tag, bg, fg in (('dark', (38, 30, 44), (236, 228, 214)), ('light', (236, 226, 204), (50, 36, 40))):
        sheet = Image.new('RGBA', (cols * cw, rows * chh), bg + (255,))
        d = ImageDraw.Draw(sheet)
        for i, (name, fname, grid, im, ncol) in enumerate(arts):
            x0, y0 = (i % cols) * cw, (i // cols) * chh
            big = im.resize((G * 6, G * 6), Image.NEAREST)
            sheet.alpha_composite(big, (x0 + (cw - big.width) // 2, y0 + 4))
            label = f'{name}  {ncol}色'
            tw = d.textlength(label, font=font)
            d.text((x0 + (cw - tw) / 2, y0 + 152), label, fill=fg, font=font)
        p = os.path.join(outdir, f'items_{tag}.png')
        sheet.save(p)
        files.append(p)

    sizes = (96, 46, 34, 26, 24)
    rowh = [s + 8 for s in sizes]
    W = len(arts) * 100 + 20
    for tag, bg in (('dark', (38, 30, 44)), ('light', (236, 226, 204))):
        sheet = Image.new('RGBA', (W, sum(rowh) + 10), bg + (255,))
        y = 5
        for s, rh in zip(sizes, rowh):
            for i, (_, _, _, im, _) in enumerate(arts):
                small = im if s == 96 else im.resize((s, s), Image.NEAREST)
                sheet.alpha_composite(small, (10 + i * 100 + (96 - s) // 2, y))
            y += rh
        p = os.path.join(outdir, f'items_actual_{tag}.png')
        sheet.save(p)
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
        print(f'已刪除 {OUT_DIR}（GameArt 找不到 items8 的圖時會自動退回舊圖；要完全關掉請把 GameArt.UsePixelItems 設 false）')
        return

    preview_dir = args[args.index('--preview') + 1] if '--preview' in args else None
    arts = render_all()
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, fname, grid, im, ncol in arts:
        p = os.path.join(OUT_DIR, fname + '.png')
        im.save(p, optimize=False)
        print(f'{name:<8} → items8/{fname}.png  {ncol} 色  {md5(p)[:8]}')
    print(f'共 {len(arts)} 張')
    if preview_dir:
        for f in preview(arts, preview_dir):
            print('預覽', f)


if __name__ == '__main__':
    main()
