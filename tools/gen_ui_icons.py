#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UI 圖示（8-bit 像素風）產生器：佈置模式的鍵帽、滑鼠、動作象形圖、放不下的原因、開店／關店狀態、圖例色塊。

    python tools/gen_ui_icons.py                    # 輸出 Assets/Resources/ui/icons8/<名稱>.png
    python tools/gen_ui_icons.py --preview DIR      # 另外輸出總覽圖（深色底／淺色底、放大＋實際大小）

── 為什麼要這批圖 ─────────────────────────────────────────────────────
  使用者實機回饋：「解釋擺放東西不用要字，用圖文的方式，解釋的文字太多了」。
  佈置模式原本的托盤提示列、物件頭上的標籤、Toast 全是句子 —— 這批圖讓它們換成「圖示組」
  （例如 [F 鍵帽][轉向]、[紅叉][門口]），C# 那邊由 UI/UiIcons.cs 依名稱取圖。

── 畫風（跟道具圖示同一套，使用者說那批「畫得很可愛」）──────────────────────
  直接 import tools/gen_item_art.py 的繪圖基元（ell／rect／poly／line／leaf…）、Icon 的打光方法
  與色盤 PAL（房間色盤＋道具補色），**不改它的輸出**。下面 UI_EXTRA 只補幾個 UI 才需要的亮色
  （勾的綠、叉的紅、走道的藍那幾階），外輪廓一樣用 'outline'（深棕紫）、4 鄰接自動補 1px。

── 規格（⚠️ C# 依賴這個）────────────────────────────────────────────────
  * 邏輯格 24×24（鍵帽 Esc 是 34×24 的寬鍵），NEAREST ×4 輸出 → 96×96（Esc 136×96）。
  * 跟道具圖示不同：圖案**上下左右置中**（道具是貼底，因為要坐在貨架上；UI 圖示是排成一列的）。
  * 內容（含外輪廓）一定要落在畫布裡 —— 超出就 assert 失敗、一次列出全部。
  * 結果是確定的：沒有亂數，重跑 md5 相同。
  * Unity 那邊走 PixelArtImporter（路徑含 /Resources/ → Point、不壓縮、無 mipmap），不用寫 .meta。

⚠️ 陷阱
  * 鍵帽上的字母是手點的 2px 粗體點陣字（下面 GLYPHS），**不要改用字型畫** —— 字型縮到 24 格一定糊。
  * 顯示大小盡量是 24 的倍數或 ≥ 28px：24 格的圖縮到 20px 以下，2px 的筆畫會被 NEAREST 吃掉一半。
  * 發光（滑鼠按下的放射線、招牌的光點）畫在 glow 層、不補外輪廓，跟道具圖示同一個做法。
"""
import hashlib
import math
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, 'Assets', 'Resources', 'ui', 'icons8')

sys.path.insert(0, HERE)
import gen_item_art as ia                                         # noqa: E402  只借基元與色盤，不跑它的 main
from gen_item_art import Icon, ell, rect, poly, line, dilate, border   # noqa: E402

SCALE = 4
OL = 'outline'

# ═══════════════════════════════ 色盤 ═══════════════════════════════
# 房間＋道具色盤偏暖偏灰；UI 的「行／不行／走道」要一眼分得出來，補幾階飽和的綠紅藍。
UI_EXTRA = {
    'ok_hi': '#c8ffb0', 'ok': '#5fd65a', 'ok_dk': '#2f9a3e', 'ok_dk2': '#1d6a2e',
    'no_hi': '#ffb0a0', 'no': '#ec4545', 'no_dk': '#b0263a', 'no_dk2': '#741a32',
    'ai_hi': '#d4ecff', 'ai': '#5aa8f4', 'ai_dk': '#2f6fc4', 'ai_dk2': '#22468a',
    'sw_hi': '#ffe0a0', 'sw': '#ffa43a', 'sw_dk': '#c86a1c',
    'key_face': '#fbf4e4',
    'ink': '#3a2548',                                   # 鍵帽上的字（深紫，比外輪廓亮一點才分得出邊）
    'night': '#3c3466', 'night_dk': '#2a2448', 'night_hi': '#575092',
}
PAL = ia.PAL                                            # 同一個 dict：補色後 gen_item_art.rgb() 也認得
for _k, _v in UI_EXTRA.items():
    assert _k not in PAL, f'UI_EXTRA 的 {_k} 跟原色盤撞名'
    PAL[_k] = _v
rgb = ia.rgb


# ═══════════════════════════════ 小工具 ═══════════════════════════════

def thick(pts, r=1):
    """把一串格子加粗：r=1 → 4 鄰接膨脹一次（約 3 格粗）。"""
    m = set(pts)
    for _ in range(r):
        m = dilate(m)
    return m


def polyline(pts):
    out = set()
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        out |= line(x0, y0, x1, y1)
    return out


def arc(cx, cy, r, w, a0, a1):
    """圓弧（角度用度、0°＝右、順時針為正，因為 y 往下）。w＝線寬。"""
    out = set()
    R = int(r + w) + 2
    for y in range(int(cy) - R, int(cy) + R + 1):
        for x in range(int(cx) - R, int(cx) + R + 1):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            d = math.hypot(dx, dy)
            if abs(d - r) > w / 2.0:
                continue
            a = math.degrees(math.atan2(dy, dx)) % 360.0
            lo, hi = a0 % 360.0, (a0 % 360.0) + ((a1 - a0) % 360.0 or 360.0)
            if lo <= a <= hi or lo <= a + 360.0 <= hi:
                out.add((x, y))
    return out


def diamond(cx, cy, hw, hh):
    """等距菱形（2:1）：格子中心的「曼哈頓距離」≤ 1。"""
    out = set()
    for y in range(int(cy - hh) - 1, int(cy + hh) + 2):
        for x in range(int(cx - hw) - 1, int(cx + hw) + 2):
            if abs(x + 0.5 - cx) / hw + abs(y + 0.5 - cy) / hh <= 1.0:
                out.add((x, y))
    return out


def tri(ax, ay, bx, by, cx, cy):
    return poly([(ax, ay), (bx, by), (cx, cy)])


GLYPHS = {
    # 2px 粗體點陣字（鍵帽用）。'#'＝筆畫。
    'R': ['######..',
          '#######.',
          '##...##.',
          '##...##.',
          '#######.',
          '######..',
          '##.###..',
          '##..###.',
          '##...###',
          '##....##'],
    'F': ['#######',
          '#######',
          '##.....',
          '##.....',
          '######.',
          '######.',
          '##.....',
          '##.....',
          '##.....',
          '##.....'],
    'T': ['########',
          '########',
          '...##...',
          '...##...',
          '...##...',
          '...##...',
          '...##...',
          '...##...',
          '...##...',
          '...##...'],
    'E': ['#######',
          '#######',
          '##.....',
          '##.....',
          '######.',
          '######.',
          '##.....',
          '##.....',
          '#######',
          '#######'],
    # P：工具列開關店按鈕的熱鍵（CornerHud）。跟 R 同一個上半部，下半只剩一根直筆
    'P': ['######..',
          '#######.',
          '##...##.',
          '##...##.',
          '#######.',
          '######..',
          '##......',
          '##......',
          '##......',
          '##......'],
    # Esc：大寫 E 8 列、小寫 s／c 6 列（底對齊）
    'E8': ['######',
           '######',
           '##....',
           '#####.',
           '#####.',
           '##....',
           '######',
           '######'],
    's': ['.####',
          '##...',
          '.###.',
          '...##',
          '...##',
          '####.'],
    'c': ['.####',
          '##...',
          '##...',
          '##...',
          '##...',
          '.####'],
}


def glyph(ic, key, x0, y0, col='ink'):
    for j, row in enumerate(GLYPHS[key]):
        for i, ch in enumerate(row):
            if ch == '#':
                ic.px[(x0 + i, y0 + j)] = col


def gw(key):
    return len(GLYPHS[key][0])


def gh(key):
    return len(GLYPHS[key])


# ═══════════════════════════════ 畫布 ═══════════════════════════════

class UiIcon(Icon):
    """一張 UI 圖示。跟道具圖示的差別只在收尾：畫布大小可變、上下左右置中。"""

    def __init__(self, w=24, h=24):
        super().__init__()
        self.w, self.h = w, h

    def finish_ui(self, name):
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
        assert w <= self.w and h <= self.h, f'{name}: 內容 {w}×{h} 超過畫布 {self.w}×{self.h}'
        ox = (self.w - w) // 2 - min(xs)
        oy = (self.h - h) // 2 - min(ys)
        grid = [[None] * self.w for _ in range(self.h)]
        for (x, y), c in body.items():
            grid[y + oy][x + ox] = c
        return grid


# ═══════════════════════════════ 共用畫法 ═══════════════════════════════

def keycap(glyphs, w=24):
    """
    立體鍵帽：亮米白的頂面、往下的厚邊（前緣）、右側暗一階。
    頂面左上一圈打亮、字母深紫置中。glyphs＝[(字, 下緣對齊用的高度差)]，橫排。
    """
    ic = UiIcon(w, 24)
    x0, x1 = 2, w - 3
    y0, y1 = 2, 21
    cap = rect(x0, y0, x1, y1)
    # 去掉四個角（圓角）
    for p in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        cap.discard(p)
    ic.put(cap, 'li_dk')                                    # 前緣／側面
    face = rect(x0 + 1, y0, x1 - 1, y1 - 5)
    for p in ((x0 + 1, y0), (x1 - 1, y0)):
        face.discard(p)
    ic.put(face, 'key_face')
    for x, y in face:                                       # 頂面左上亮邊、右下一階暗
        if (x, y - 1) not in face or (x - 1, y) not in face:
            ic.px[(x, y)] = 'wh'
        elif (x + 1, y) not in face:
            ic.px[(x, y)] = 'li'
    for x in range(x0 + 1, x1):                             # 前緣最下面一列更暗（立體感）
        ic.px[(x, y1)] = 'st_dk'
    ic.px[(x0, y1 - 1)] = 'st_dk'
    ic.px[(x1, y1 - 1)] = 'st_dk'
    # 字母：整串置中在頂面、底對齊
    total = sum(gw(g) for g in glyphs) + (len(glyphs) - 1)
    base = max(gh(g) for g in glyphs)
    fx0 = x0 + 1 + ((x1 - 1) - (x0 + 1) + 1 - total) // 2
    fy = y0 + 1 + ((y1 - 5) - (y0 + 1) + 1 - base) // 2 + 1
    for g in glyphs:
        glyph(ic, g, fx0, fy + base - gh(g))
        fx0 += gw(g) + 1
    return ic


def mouse(ic, cx, cy, rx, ry, lit=None, split=None):
    """滑鼠本體：米白圓殼、上半分左右鍵、中間一條縫。lit＝'L'／'R' 那一顆亮起（金黃）。"""
    m = ell(cx, cy, rx, ry)
    ic.sphere(m, ('li_hi', 'li', 'li_dk'), cx - 0.5, cy - 1.0, rx * 1.1, ry * 1.1)
    split = int(cy + ry * 0.05) if split is None else split          # 左右鍵的下緣
    mid = int(cx)
    btn_l = {p for p in m if p[1] < split and p[0] < mid}
    btn_r = {p for p in m if p[1] < split and p[0] > mid}
    if lit == 'L':
        ic.sphere(btn_l, ('go_hi', 'cy_y', 'go'), cx - rx * 0.5, cy - ry * 0.6, rx * 0.7, ry * 0.7)
    if lit == 'R':
        ic.sphere(btn_r, ('go_hi', 'cy_y', 'go'), cx + rx * 0.5, cy - ry * 0.6, rx * 0.7, ry * 0.7)
    for p in m:
        if p[0] == mid and p[1] < split:
            ic.px[p] = 'st_dk2'
        if p[1] == split:
            ic.px[p] = 'st_dk2'
    return m


def rays(ic, cx, cy, side):
    """按下的放射線（glow 層）：從亮起的那顆鍵往外三條短線。side＝-1 左、+1 右。"""
    for dx, dy in ((0, -1), (1, -1), (1, 0)):
        dx *= side
        for k in (2, 3):
            ic.glow[(int(cx + dx * k), int(cy + dy * k))] = 'go_hi'


def arrow_head(ic, tip, direction, size, col):
    """實心三角箭頭：tip＝尖端、direction＝(dx,dy) 單位方向、size＝長度。"""
    tx, ty = tip
    dx, dy = direction
    bx, by = tx - dx * size, ty - dy * size
    nx, ny = -dy, dx
    m = tri(tx + dx * 0.6, ty + dy * 0.6, bx + nx * size * 0.9, by + ny * size * 0.9,
            bx - nx * size * 0.9, by - ny * size * 0.9)
    ic.put(m, col)
    return m


def tile(ic, cx, cy, hw, hh, inner, edge):
    """等距菱形格：內側本色、外圈一層亮邊（跟遊戲畫面上的格子同一個長相）。"""
    m = diamond(cx, cy, hw, hh)
    ic.put(m, inner)
    ic.put(border(m), edge)
    return m


def crate(ic, x0, y0, x1, y1, ramp=('wd_hi', 'wd', 'wd_dk')):
    """小木箱：木板面＋一條橫木紋。"""
    m = rect(x0, y0, x1, y1)
    ic.flat(m, ramp)
    for x in range(x0 + 1, x1):
        ic.px[(x, (y0 + y1) // 2)] = ramp[2]
    return m


def shelf(ic, x0, y0, w, h):
    """正面看的小貨架：兩根腳柱、三層板、層板上兩個小東西。"""
    ic.put(rect(x0, y0, x0 + 1, y0 + h - 1), 'wd_dk')
    ic.put(rect(x0 + w - 2, y0, x0 + w - 1, y0 + h - 1), 'wd_dk')
    ic.put(rect(x0 + 2, y0 + 1, x0 + w - 3, y0 + h - 2), 'wd_dk2')         # 背板（暗）
    for k in range(3):
        y = y0 + k * (h - 1) // 2
        ic.put(rect(x0, y, x0 + w - 1, y), 'wd_hi')
    # 層板上的兩罐小東西
    mid = y0 + (h - 1) // 2
    ic.put(rect(x0 + 3, mid - 2, x0 + 4, mid - 1), 'teal')
    ic.put(rect(x0 + w - 5, mid - 2, x0 + w - 4, mid - 1), 'pink')
    return rect(x0, y0, x0 + w - 1, y0 + h - 1)


# ═══════════════════════════════ 鍵帽 ═══════════════════════════════

def draw_key_r():
    return keycap(['R'])


def draw_key_f():
    return keycap(['F'])


def draw_key_t():
    return keycap(['T'])


def draw_key_e():
    return keycap(['E'])


def draw_key_p():
    return keycap(['P'])


def draw_key_esc():
    return keycap(['E8', 's', 'c'], w=34)


# ═══════════════════════════════ 滑鼠 ═══════════════════════════════

def draw_mouse_left():
    ic = UiIcon()
    mouse(ic, 13.0, 12.5, 6.5, 9.0, lit='L')
    rays(ic, 6, 4, -1)
    return ic


def draw_mouse_right():
    ic = UiIcon()
    mouse(ic, 11.0, 12.5, 6.5, 9.0, lit='R')
    rays(ic, 17, 4, +1)
    return ic


def draw_mouse_drag():
    """左鍵按住拖曳：小滑鼠（左鍵亮）＋四向箭頭。"""
    ic = UiIcon()
    mouse(ic, 12.0, 12.0, 4.5, 6.0, lit='L', split=11)
    cx, cy = 12, 12
    for (dx, dy) in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        tip = (cx + 0.5 + dx * 10.0, cy + 0.5 + dy * 10.0)
        arrow_head(ic, tip, (dx, dy), 3.0, 'go_hi')
    return ic


# ═══════════════════════════════ 動作 ═══════════════════════════════

def draw_act_rotate():
    """轉向：四分之三圈的弧形箭頭（青綠）。"""
    ic = UiIcon()
    cx, cy, r = 12.0, 12.5, 7.0
    # 從右邊（0°）順時針繞過下、左、上，停在正上方（275°）；缺口留在右上，箭頭接在弧的尾端往右
    m = arc(cx, cy, r, 3.0, 10, 275)
    ic.sphere(m, ('teal_hi', 'teal', 'teal_dk'), cx, cy, r + 2, r + 2)
    arrow_head(ic, (cx + 5.5, cy - r), (1, 0), 5.0, 'teal_hi')
    return ic


def draw_anchor(which):
    """基準角：一塊等距佔地（地板色），標記的那一角插一根金色小旗。which：0 前角、1 左角、2 右角。"""
    def fn():
        ic = UiIcon()
        cx, cy, hw, hh = 12.0, 16.0, 10.5, 5.5
        tile(ic, cx, cy, hw, hh, 'fl', 'fl_hi')
        # 三個角：前（下）、左、右
        corner = {0: (12, 21), 1: (2, 16), 2: (21, 16)}[which]
        x, y = corner
        # 角上的金色亮點（3×2）＋旗竿＋三角旗
        ic.put(rect(x - 1, y - 1, x + 1, y), 'go_hi')
        ic.put(rect(x, y - 14, x, y - 2), 'wd_dk')
        side = -1 if which == 2 else 1
        flag = tri(x + 0.5, y - 14.5, x + 0.5, y - 7.5, x + 0.5 + side * 8, y - 11.0)
        ic.put(flag, 'no')
        ic.put({p for p in flag if p[1] <= y - 12}, 'no_hi')
        return ic
    return fn


def draw_act_stash():
    """收回托盤：箭頭往下進木箱。"""
    ic = UiIcon()
    crate(ic, 4, 13, 19, 21)
    ic.put(rect(5, 13, 18, 13), 'wd_dk2')                   # 箱口
    ic.put(rect(10, 1, 13, 7), 'go_hi')
    arrow_head(ic, (12.0, 14.0), (0, 1), 6.0, 'go_hi')
    ic.put(rect(10, 1, 10, 7), 'cy_y')
    return ic


def draw_act_unstash():
    """從托盤拿出來：箭頭往上離開木箱。"""
    ic = UiIcon()
    crate(ic, 4, 14, 19, 21)
    ic.put(rect(5, 14, 18, 14), 'wd_dk2')
    ic.put(rect(10, 7, 13, 13), 'go_hi')
    arrow_head(ic, (12.0, 1.0), (0, -1), 6.0, 'go_hi')
    ic.put(rect(10, 7, 10, 13), 'cy_y')
    return ic


def draw_act_done():
    """完成：粗綠勾。"""
    ic = UiIcon()
    pts = polyline([(4, 12), (9, 17), (19, 5)])
    m = thick(pts, 1)
    ic.put(m, 'ok')
    ic.put({(x, y) for x, y in m if (x, y + 1) not in m or (x + 1, y) not in m}, 'ok_dk')
    ic.put({(x, y - 1) for x, y in pts if (x, y - 1) in m}, 'ok_hi')
    return ic


def draw_act_cancel():
    """取消：粗紅叉。"""
    ic = UiIcon()
    a = line(5, 5, 18, 18)
    b = line(18, 5, 5, 18)
    m = thick(a | b, 1)
    ic.put(m, 'no')
    ic.put({(x, y) for x, y in m if (x, y + 1) not in m}, 'no_dk')
    ic.put({(x, y - 1) for x, y in a | b if (x, y - 1) in m}, 'no_hi')
    return ic


def draw_act_move():
    """搬去別處：左下一個木箱 → 右上一個虛線框（目的地）。"""
    ic = UiIcon()
    crate(ic, 1, 13, 9, 21)
    # 虛線框（白，隔一格畫一格）＝要搬去的地方
    box = border(rect(13, 1, 21, 9))
    ic.put({(x, y) for x, y in box if (x + y) % 4 < 2}, 'li_hi')
    # 斜的粗箭頭：從箱子往虛線框
    ic.put(thick(line(8, 13, 12, 9), 1) - box, 'go_hi')
    arrow_head(ic, (15.5, 6.5), (0.707, -0.707), 4.5, 'go_hi')
    return ic


def draw_act_swap():
    """交換：上面往右、下面往左的兩支橘色箭頭。"""
    ic = UiIcon()
    ic.put(rect(3, 6, 15, 8), 'sw')
    ic.put(rect(3, 6, 15, 6), 'sw_hi')
    arrow_head(ic, (21.0, 7.5), (1, 0), 6.0, 'sw')
    ic.put(rect(8, 15, 20, 17), 'sw_dk')
    ic.put(rect(8, 15, 20, 15), 'sw')
    arrow_head(ic, (2.0, 16.5), (-1, 0), 6.0, 'sw_dk')
    return ic


def draw_act_return():
    """回原位：一個白圈（原本的位子）＋從右上繞回來的弧形箭頭。"""
    ic = UiIcon()
    ring = ell(7.5, 18.5, 5.0, 3.6) - ell(7.5, 18.5, 2.6, 1.6)
    ic.put(ring, 'li')
    ic.put({p for p in ring if p[0] >= 8 and p[1] >= 19}, 'st_dk')
    # 上半圈的弧（右邊起、左邊落），箭頭在左端往下指進圈裡
    cx, cy, r = 13.5, 8.5, 6.0
    m = arc(cx, cy, r, 2.8, 180, 360) | rect(18, 8, 20, 13)
    ic.put(m, 'go_hi')
    ic.put({p for p in m if p[0] >= 18}, 'go')
    arrow_head(ic, (7.5, 13.5), (0, 1), 4.0, 'go_hi')
    return ic


def draw_act_walk():
    """走道：兩個藍色腳印（一前一後）。"""
    ic = UiIcon()
    # 每個腳印＝前掌（大橢圓）＋分開一格的腳跟（小圓）＋三顆腳趾，一左一右、一前一後
    for (cx, cy) in ((7.5, 12.5), (16.5, 7.5)):
        ball = ell(cx, cy, 3.0, 3.4)
        heel = ell(cx, cy + 5.0, 2.2, 1.8)
        ic.sphere(ball, ('ai_hi', 'ai', 'ai_dk'), cx, cy, 3.2, 3.6)
        ic.sphere(heel, ('ai_hi', 'ai', 'ai_dk'), cx, cy + 5.5, 2.4, 2.2)
        for dx in (-2, 0, 2):
            ic.px[(int(cx) + dx, int(cy - 5))] = 'ai'
    return ic


def draw_act_edit():
    """佈置（HUD 用）：一把小木槌斜放。"""
    ic = UiIcon()
    ic.stick(line(4, 19, 13, 10), 'wd_hi', 'wd_dk')
    c = (15.5, 8.0)
    u = (5.0 / math.sqrt(2), 5.0 / math.sqrt(2))
    v = (2.8 / math.sqrt(2), -2.8 / math.sqrt(2))
    head = poly([(c[0] + u[0] + v[0], c[1] + u[1] + v[1]), (c[0] + u[0] - v[0], c[1] + u[1] - v[1]),
                 (c[0] - u[0] - v[0], c[1] - u[1] - v[1]), (c[0] - u[0] + v[0], c[1] - u[1] + v[1])])
    ic.flat(head, ('ir_hi', 'ir', 'ir_dk'))
    ic.sparkle(20, 3, col='go_hi')
    return ic


def draw_arrow():
    """連環圖之間的箭頭（米白）。"""
    ic = UiIcon()
    ic.put(rect(3, 10, 13, 13), 'li_hi')
    ic.put(rect(3, 13, 13, 13), 'li_dk')
    arrow_head(ic, (21.0, 12.0), (1, 0), 7.0, 'li_hi')
    return ic


# ═══════════════════════════════ 放不下的原因（PlaceBlock）═══════════════════════════════
# 每張都只畫「情況」，紅色標出出問題的地方；世界標籤上會再配一個紅叉（st_no）。

def draw_blk_offfloor():
    """超出地板：一塊地板菱形，一個箱子有一半懸在地板外，懸空那半是紅的。"""
    ic = UiIcon()
    fl = tile(ic, 9.0, 14.0, 8.5, 4.5, 'fl', 'fl_hi')
    # 箱子：左半踩在地板上（木色），右半伸到地板外（紅）＋往下掉的虛線
    box = rect(10, 4, 21, 13)
    ic.flat(box, ('wd_hi', 'wd', 'wd_dk'))
    out = {p for p in box if p[0] >= 16}
    ic.flat(out, ('no_hi', 'no', 'no_dk'))
    for y in (16, 18, 20):
        ic.put({(18, y), (20, y)}, 'no')
    del fl
    return ic


def draw_blk_overlap():
    """跟別的東西重疊：兩個方塊交疊，疊到的那一塊是紅的。"""
    ic = UiIcon()
    a = rect(2, 2, 13, 13)
    b = rect(9, 9, 21, 21)
    ic.flat(a, ('wd_hi', 'wd', 'wd_dk'))
    ic.flat(b, ('pu_hi', 'pu', 'pu_dk'))
    both = a & b
    ic.flat(both, ('no_hi', 'no', 'no_dk'))
    ic.sep(b - a, 'outline')
    return ic


def draw_blk_door():
    """門口：拱門木門，門前一格紅色地磚。"""
    ic = UiIcon()
    frame = rect(5, 4, 18, 17) | ell(11.5, 5.5, 6.5, 4.0)
    ic.put(frame, 'st_dk')
    door = rect(7, 6, 16, 17) | ell(11.5, 7.0, 4.5, 3.0)
    ic.cyl(door, ('wd_hi', 'wd', 'wd_dk'))
    ic.put({(11, y) for y in range(5, 18)}, 'wd_dk2')
    ic.put(rect(14, 11, 15, 12), 'go_hi')                      # 門把
    tile(ic, 11.5, 19.0, 10.0, 2.8, 'no', 'no_hi')
    return ic


def draw_blk_aisle():
    """壓到別人的走道：藍色走道格（腳印）上放了一個箱子，箱子染紅。"""
    ic = UiIcon()
    tile(ic, 12.0, 16.0, 10.5, 5.5, 'ai', 'ai_hi')
    for (cx, cy) in ((6.0, 16.5), (18.0, 16.5)):
        ic.put(ell(cx, cy, 1.6, 2.2), 'ai_dk2')
    box = rect(8, 3, 15, 16)
    ic.flat(box, ('no_hi', 'no', 'no_dk'))
    for x in range(9, 15):
        ic.px[(x, 9)] = 'no_dk'
    return ic


def draw_blk_noaisle():
    """自己前面沒走道：貨架，它前面那一格（本來該是藍色走道）被紅色堵住。"""
    ic = UiIcon()
    shelf(ic, 6, 1, 12, 13)
    tile(ic, 12.0, 18.0, 10.5, 4.5, 'no', 'no_hi')
    ic.put(rect(10, 15, 13, 19), 'no_dk2')                     # 堵在走道上的東西（深紅塊）
    ic.put(rect(10, 15, 13, 15), 'no_dk')
    return ic


def draw_blk_wall():
    """卡進牆裡：磚牆，一個貨架有一半陷在牆裡（陷進去的部分紅色）。"""
    ic = UiIcon()
    wall = rect(1, 1, 10, 21)
    ic.put(wall, 'st')
    for y in range(1, 22):                                       # 磚縫
        if y % 4 == 0:
            for x in range(1, 11):
                ic.px[(x, y)] = 'mortar'
        else:
            off = 0 if (y // 4) % 2 == 0 else 3
            ic.px[(1 + off + 1, y)] = 'mortar' if off else ic.px[(2, y)]
            ic.px[(7 + off - 3 if off else 6, y)] = 'mortar'
    ic.put({(1, y) for y in range(1, 22)}, 'st_hi')
    sh = shelf(ic, 7, 4, 13, 15)
    inwall = {p for p in sh if p[0] <= 10}
    ic.flat(inwall, ('no_hi', 'no', 'no_dk'))
    ic.put({(10, y) for y in range(1, 22)}, 'no_dk2')
    return ic


# ═══════════════════════════════ 狀態 ═══════════════════════════════

def draw_st_ok():
    """可以放：綠色圓章＋白勾。"""
    ic = UiIcon()
    disc = ell(12.0, 12.0, 10.0, 10.0)
    ic.sphere(disc, ('ok_hi', 'ok', 'ok_dk', 'ok_dk2'), 12, 12, 10, 10)
    pts = polyline([(6, 12), (10, 16), (17, 7)])
    ic.put(thick(pts, 1) & disc, 'wh')
    return ic


def draw_st_no():
    """不可以放：紅色圓章＋白叉。"""
    ic = UiIcon()
    disc = ell(12.0, 12.0, 10.0, 10.0)
    ic.sphere(disc, ('no_hi', 'no', 'no_dk', 'no_dk2'), 12, 12, 10, 10)
    a = line(7, 7, 16, 16) | line(16, 7, 7, 16)
    ic.put(thick(a, 1) & disc, 'wh')
    return ic


def sign_board(ic, face, edge):
    """掛著的小招牌：上方一根橫桿、兩條鍊子、木框板子。回傳板面遮罩。"""
    ic.put(rect(2, 2, 21, 3), 'wd_dk')
    ic.put(rect(2, 2, 21, 2), 'wd_hi')
    for x in (6, 17):
        ic.put({(x, 4), (x, 5)}, 'ir_hi')
    board = rect(2, 6, 21, 20)
    ic.flat(board, ('wd_hi', 'wd', 'wd_dk'))
    inner = rect(4, 8, 19, 18)
    ic.put(inner, face)
    ic.put(border(inner) & {(x, y) for x, y in inner if x == 4 or y == 8}, edge)
    return inner


def draw_shop_open():
    """開店中：亮黃的招牌、中間一顆太陽、旁邊有光點。"""
    ic = UiIcon()
    sign_board(ic, 'cy_y', 'go_hi')
    sun = ell(11.5, 13.0, 3.5, 3.5)
    ic.sphere(sun, ('wh', 'fire_y', 'fire_o'), 11.5, 13.0, 3.5, 3.5)
    for dx, dy in ((0, -5), (0, 5), (-5, 0), (5, 0), (-4, -4), (4, -4), (-4, 4), (4, 4)):
        ic.px[(11 + dx + (1 if dx > 0 else 0), 12 + dy + (1 if dy > 0 else 0))] = 'fire_o'
    ic.sparkle(1, 1, col='go_hi')
    ic.sparkle(22, 7, col='go_hi')
    return ic


def draw_shop_closed():
    """關店：暗藍紫的招牌、一彎金色月亮。"""
    ic = UiIcon()
    sign_board(ic, 'night', 'night_hi')
    moon = ell(11.5, 13.0, 4.0, 4.0) - ell(13.8, 11.6, 3.4, 3.4)
    ic.put(moon, 'go_hi')
    ic.put({p for p in moon if p[1] >= 14}, 'go')
    ic.put({(16, 10), (17, 15)}, 'n_star')
    return ic


def draw_lock():
    """鎖頭：金色鎖身、鐵色鎖環、鑰匙孔。"""
    ic = UiIcon()
    shackle = arc(12.0, 9.5, 5.0, 2.4, 180, 360) | rect(6, 9, 7, 12) | rect(16, 9, 17, 12)
    ic.put(shackle, 'ir_hi')
    ic.put({p for p in shackle if p[0] >= 13}, 'ir')
    body = rect(4, 11, 19, 21)
    ic.flat(body, ('go_hi', 'go', 'go_dk'))
    ic.put(ell(11.5, 15.0, 1.6, 1.6) | rect(11, 15, 12, 18), 'go_dk2')
    return ic


# ═══════════════════════════════ 圖例 ═══════════════════════════════

def draw_tile(inner, edge):
    def fn():
        ic = UiIcon()
        tile(ic, 12.0, 12.0, 11.0, 6.0, inner, edge)
        return ic
    return fn


def draw_ring(col, dk):
    """陳列位的圈（拖商品時畫面上那種）。"""
    def fn():
        ic = UiIcon()
        ring = ell(12.0, 12.0, 8.5, 8.5) - ell(12.0, 12.0, 5.0, 5.0)
        ic.put(ring, col)
        ic.put({p for p in ring if p[0] + p[1] >= 26}, dk)
        return ic
    return fn


# ═══════════════════════════════ 清單 ═══════════════════════════════
# (檔名, 用途說明, 畫法)。檔名就是 C# 那邊 UiIcons.Get() 的名字。
ICONS = [
    ('key_r', '鍵帽 R（進出佈置模式）', draw_key_r),
    ('key_f', '鍵帽 F（轉向）', draw_key_f),
    ('key_t', '鍵帽 T（換基準角）', draw_key_t),
    ('key_e', '鍵帽 E（販售桌等「走近按 E」的互動）', draw_key_e),
    ('key_p', '鍵帽 P（工具列的開店／關店熱鍵）', draw_key_p),
    ('key_esc', '鍵帽 Esc（取消）', draw_key_esc),
    ('mouse_left', '滑鼠左鍵（點托盤的東西）', draw_mouse_left),
    ('mouse_right', '滑鼠右鍵（收回托盤）', draw_mouse_right),
    ('mouse_drag', '左鍵按住拖曳', draw_mouse_drag),
    ('act_rotate', '轉向', draw_act_rotate),
    ('anchor_0', '基準角：前角', draw_anchor(0)),
    ('anchor_1', '基準角：左角（靠左後牆）', draw_anchor(1)),
    ('anchor_2', '基準角：右角（靠右後牆）', draw_anchor(2)),
    ('act_stash', '收回托盤', draw_act_stash),
    ('act_unstash', '從托盤拿出來', draw_act_unstash),
    ('act_done', '完成', draw_act_done),
    ('act_cancel', '取消', draw_act_cancel),
    ('act_move', '搬去別處', draw_act_move),
    ('act_swap', '交換位置', draw_act_swap),
    ('act_return', '回原位', draw_act_return),
    ('act_walk', '走道（腳印）', draw_act_walk),
    ('act_edit', '佈置（木槌）', draw_act_edit),
    ('arrow', '連環圖箭頭', draw_arrow),
    ('blk_offfloor', '放不下：超出地板', draw_blk_offfloor),
    ('blk_overlap', '放不下：跟別的東西重疊', draw_blk_overlap),
    ('blk_door', '放不下：門口', draw_blk_door),
    ('blk_aisle', '放不下：壓到別人的走道', draw_blk_aisle),
    ('blk_noaisle', '放不下：自己前面沒走道', draw_blk_noaisle),
    ('blk_wall', '放不下：卡進牆裡', draw_blk_wall),
    ('st_ok', '可以放', draw_st_ok),
    ('st_no', '不可以放', draw_st_no),
    ('shop_open', '開店中', draw_shop_open),
    ('shop_closed', '關店', draw_shop_closed),
    ('lock', '鎖頭', draw_lock),
    ('tile_green', '圖例：綠格（放得下）', draw_tile('ok', 'ok_hi')),
    ('tile_red', '圖例：紅格（放不下／門口）', draw_tile('no', 'no_hi')),
    ('tile_blue', '圖例：藍格（走道）', draw_tile('ai', 'ai_hi')),
    ('ring_green', '陳列位：空位', draw_ring('ok', 'ok_dk')),
    ('ring_orange', '陳列位：會交換', draw_ring('sw', 'sw_dk')),
]


# ═══════════════════════════════ 輸出 ═══════════════════════════════

def to_image(grid):
    h, w = len(grid), len(grid[0])
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    pix = im.load()
    for y in range(h):
        for x in range(w):
            c = grid[y][x]
            if c is not None:
                pix[x, y] = rgb(c) + (255,)
    return im.resize((w * SCALE, h * SCALE), Image.NEAREST)


def render_all():
    out, errs = [], []
    for fname, desc, fn in ICONS:
        try:
            grid = fn().finish_ui(fname)
        except AssertionError as e:
            errs.append(str(e))
            continue
        out.append((fname, desc, to_image(grid)))
    if errs:
        sys.exit('\n'.join(errs))
    return out


def preview(arts, outdir):
    """
    總覽圖：
      icons_dark.png／icons_light.png —— 每張放大 5 倍＋名稱，深色底與淺色底；
      icons_actual.png —— 深淺兩條，同一排看 48／32／24px（遊戲裡實際會用的大小）。
    """
    os.makedirs(outdir, exist_ok=True)
    font = ia.find_font(13)
    cols = 8
    cw, chh = 190, 150
    rows = (len(arts) + cols - 1) // cols
    files = []
    for tag, bg, fg in (('dark', (38, 30, 44), (236, 228, 214)), ('light', (236, 226, 204), (50, 36, 40))):
        sheet = Image.new('RGBA', (cols * cw, rows * chh), bg + (255,))
        d = ImageDraw.Draw(sheet)
        for i, (fname, desc, im) in enumerate(arts):
            x0, y0 = (i % cols) * cw, (i // cols) * chh
            big = im.resize((im.width // SCALE * 5, im.height // SCALE * 5), Image.NEAREST)
            sheet.alpha_composite(big, (x0 + (cw - big.width) // 2, y0 + 4))
            tw = d.textlength(fname, font=font)
            d.text((x0 + (cw - tw) / 2, y0 + 126), fname, fill=fg, font=font)
        p = os.path.join(outdir, f'icons_{tag}.png')
        sheet.save(p)
        files.append(p)

    sizes = (48, 32, 24)
    W = sum(im.width // SCALE * 2 + 8 for _, _, im in arts) + 20
    H = (sum(sizes) + 8 * len(sizes)) * 2 + 20
    sheet = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    y = 5
    for bg in ((38, 30, 44), (236, 226, 204)):
        band = sum(sizes) + 8 * len(sizes)
        ImageDraw.Draw(sheet).rectangle((0, y - 5, W, y + band + 2), fill=bg + (255,))
        for s in sizes:
            x = 10
            for _, _, im in arts:
                sw = im.width * s // im.height
                small = im.resize((sw, s), Image.NEAREST)
                sheet.alpha_composite(small, (x, y))
                x += im.width // SCALE * 2 + 8
            y += s + 8
        y += 10
    p = os.path.join(outdir, 'icons_actual.png')
    sheet.save(p)
    files.append(p)
    return files


def md5(p):
    with open(p, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def main():
    args = sys.argv[1:]
    preview_dir = args[args.index('--preview') + 1] if '--preview' in args else None
    arts = render_all()
    os.makedirs(OUT_DIR, exist_ok=True)
    for fname, desc, im in arts:
        p = os.path.join(OUT_DIR, fname + '.png')
        im.save(p, optimize=False)
        print(f'{fname:<14} {im.width}×{im.height}  {md5(p)[:8]}  {desc}')
    print(f'共 {len(arts)} 張')
    if preview_dir:
        for f in preview(arts, preview_dir):
            print('預覽', f)


if __name__ == '__main__':
    main()
