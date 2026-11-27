#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UI 圖示（8-bit 像素風）產生器：佈置模式的鍵帽、滑鼠、動作象形圖、放不下的原因、開店／關店狀態、圖例色塊。

    python tools/gen_ui_icons.py                    # 輸出 Assets/Resources/ui/icons8/<名稱>.png
    python tools/gen_ui_icons.py --preview DIR      # 另外輸出總覽圖（深色底／淺色底、放大＋實際大小）
    python tools/gen_ui_icons.py --out DIR          # 圖改寫到 DIR（迭代時用，不碰 Assets）

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
    # ── 2026-11-27 工具列細修（鍵帽、招牌、鎖頭、木槌）：多一兩階、色相偏移，跟腰包／上方工具列同一套 ──
    'fk_w': '#fffdf6', 'fk': '#f8efda', 'fk_md': '#ecdfc0', 'fk_dk': '#d9c7a0',      # 鍵帽頂面
    'fk_s1': '#c9b38c', 'fk_s2': '#a8906c', 'fk_s3': '#7d6650',                      # 鍵帽前緣
    'fk_ink': '#3a2548', 'fk_sh': '#cdb994',                                         # 字、字下的淡陰影
    'fo_1': '#fffbe8', 'fo_2': '#fff0a6', 'fo_3': '#ffe06a', 'fo_4': '#ffc94c',      # 開店招牌的暖光
    'fo_5': '#f2aa3c', 'fo_6': '#d98a2e', 'fo_r': '#e57a26',
    'fn_1': '#221d44', 'fn_2': '#2d2756', 'fn_3': '#383066', 'fn_4': '#443b78',      # 關店招牌的夜空
    'fw_hi': '#c48a5a', 'fw': '#9a6440', 'fw_dk': '#6e4230', 'fw_dk2': '#4a2a26',     # 暖木（招牌框、木槌）
    'fi_hi': '#d6d2e0', 'fi': '#9a96ad', 'fi_dk': '#666179', 'fi_dk2': '#45405a',     # 鐵（橫桿、鎖環）
    'fg_w': '#fff6cc', 'fg_hi': '#fbe08a', 'fg': '#e6b955', 'fg_md': '#cf9a3e',       # 金（鎖身、月亮、槌箍）
    'fg_dk': '#a8722c', 'fg_dk2': '#764c20', 'fg_hole': '#3a2216',
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
    立體鍵帽（2026-11-27 細修）：圓一點的角（每角切 3 格）、頂面三階（上左亮邊、右下與最下兩列暗一階）、
    前緣厚邊三階、左右側面一亮一暗；字下面一列淡陰影（印上去的厚度）。glyphs＝[字…]，橫排、底對齊、置中。
    """
    ic = UiIcon(w, 24)
    x0, x1, y0, y1 = 2, w - 3, 2, 21
    cap = rect(x0, y0, x1, y1)
    for dx, dy in ((0, 0), (1, 0), (0, 1)):
        for p in ((x0 + dx, y0 + dy), (x1 - dx, y0 + dy), (x0 + dx, y1 - dy), (x1 - dx, y1 - dy)):
            cap.discard(p)
    fb = y1 - 5                                             # 頂面最下一列
    for x, y in cap:
        if y > fb:
            c = ('fk_s1', 'fk_s1', 'fk_s2', 'fk_s2', 'fk_s3')[y - fb - 1]
        else:
            c = 'fk_s1' if x == x0 else ('fk_s2' if x == x1 else 'fk')
        ic.px[(x, y)] = c
    face = {(x, y) for x, y in cap if y <= fb and x0 < x < x1}
    for x, y in face:
        if (x, y - 1) not in face or (x - 1, y) not in face:
            ic.px[(x, y)] = 'fk_w'
        elif y == fb:
            ic.px[(x, y)] = 'fk_dk'
        elif (x + 1, y) not in face or y >= fb - 2 or x >= x1 - 2:
            ic.px[(x, y)] = 'fk_md'
    ic.px[(x0, fb + 1)] = 'fk_s2'
    ic.px[(x1, fb + 1)] = 'fk_s3'
    total = sum(gw(g) for g in glyphs) + (len(glyphs) - 1)
    base = max(gh(g) for g in glyphs)
    fx0 = x0 + 1 + ((x1 - 1) - (x0 + 1) + 1 - total) // 2
    fy = y0 + 1 + (fb - (y0 + 1) + 1 - base) // 2 + 1
    pts = set()
    for g in glyphs:
        gy = fy + base - gh(g)
        for j, row in enumerate(GLYPHS[g]):
            for i, ch in enumerate(row):
                if ch == '#':
                    pts.add((fx0 + i, gy + j))
        fx0 += gw(g) + 1
    for x, y in pts:
        if (x, y + 1) not in pts and (x, y + 1) in face:
            ic.px[(x, y + 1)] = 'fk_sh'
    for p in pts:
        ic.px[p] = 'fk_ink'
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
    """佈置（HUD 用）：木槌 —— 暖木柄（上亮下暗、握把纏一段紫布）、圓木槌頭（三階木色＋兩端金箍）、旁邊一顆光點。"""
    ic = UiIcon()
    handle = sorted(line(4, 19, 12, 11))
    for x, y in handle:
        ic.px[(x, y)] = 'fw_hi'
        ic.px[(x, y + 1)] = 'fw_dk'
    for x, y in handle[:3]:
        ic.px[(x, y)] = 'pu_hi'
        ic.px[(x, y + 1)] = 'pu_dk'
    c = (15.5, 8.0)
    k = 1 / math.sqrt(2)
    for y in range(0, 18):
        for x in range(6, 24):
            dx, dy = x + 0.5 - c[0], y + 0.5 - c[1]
            u = (dx + dy) * k                                  # 槌頭長軸（左上→右下）
            v = (dx - dy) * k                                  # 短軸（負＝右上的受光面）
            if abs(u) <= 5.2 and abs(v) <= 3.0:
                if abs(u) > 3.9:
                    col = 'fg_hi' if v < -0.8 else ('fg' if v < 1.0 else 'fg_dk')
                else:
                    col = 'fw_hi' if v < -1.2 else ('fw' if v < 0.9 else 'fw_dk')
                ic.px[(x, y)] = col
    ic.sparkle(20, 2, col='go_hi')
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


def sign_board(ic):
    """掛著的小招牌（2026-11-27 細修）：鐵橫桿（左亮右暗）、兩條鍊子、暖木框（外亮內暗、四角金釘）。回傳板面遮罩。"""
    for x in range(1, 23):
        ic.px[(x, 2)] = 'fi_hi' if x < 12 else 'fi'
        ic.px[(x, 3)] = 'fi_dk' if 1 < x < 22 else ('fi' if x == 1 else 'fi_dk2')
    for x in (6, 17):
        ic.px[(x, 4)] = 'fi_hi'
        ic.px[(x, 5)] = 'fi_dk'
    for x, y in rect(2, 6, 21, 20):
        if y == 6 or x == 2:
            c = 'fw_hi'
        elif y == 20 or x == 21:
            c = 'fw_dk2'
        elif y == 19 or x == 20:
            c = 'fw_dk'
        else:
            c = 'fw'
        ic.px[(x, y)] = c
    ic.px[(2, 20)] = 'fw_dk'
    ic.px[(21, 6)] = 'fw'
    for p in ((3, 7), (20, 7), (3, 19), (20, 19)):
        ic.px[p] = 'fg_hi'
    return rect(4, 8, 19, 18)


def draw_shop_open():
    """開店中：板面由中心往外的暖光漸層（四階，框下一圈內陰影）、中間白芯小太陽＋八道細光、旁邊兩顆光點。"""
    ic = UiIcon()
    inner = sign_board(ic)
    cx, cy = 12.0, 13.5
    for x, y in inner:
        d = math.hypot(x + 0.5 - cx, (y + 0.5 - cy) * 1.25)
        c = 'fo_2' if d < 4.2 else ('fo_3' if d < 6.2 else ('fo_4' if d < 8.2 else 'fo_5'))
        ic.px[(x, y)] = 'fo_6' if (y == 8 or x == 4) else c
    for x, y in inner:
        if math.hypot(x + 0.5 - cx, y + 0.5 - cy) <= 2.6:
            ic.px[(x, y)] = 'fo_1'
    ic.px[(11, 12)] = 'wh'
    ic.px[(12, 12)] = 'wh'
    for ang in range(0, 360, 45):
        a = math.radians(ang)
        for r in (3.8, 4.8):
            p = (int(math.floor(cx + r * math.cos(a))), int(math.floor(cy + r * math.sin(a))))
            if p in inner:
                ic.px[p] = 'fo_r' if r > 4 else 'fo_5'
    ic.sparkle(1, 1, col='go_hi')
    ic.sparkle(22, 7, col='go_hi')
    return ic


def draw_shop_closed():
    """關店：深夜空（上暗下亮四階）、四階金弦月、一顆帶光暈的星＋一顆小星＋一點暗星。"""
    ic = UiIcon()
    inner = sign_board(ic)
    for x, y in inner:
        ic.px[(x, y)] = 'fn_1' if (y <= 9 or x == 4) else ('fn_2' if y <= 12 else ('fn_3' if y <= 15 else 'fn_4'))
    moon = ell(11.5, 13.0, 4.2, 4.2) - ell(13.9, 11.6, 3.5, 3.5)
    for x, y in moon:
        t = (x - 8) * 0.4 + (y - 9)
        ic.px[(x, y)] = 'fg_w' if t < 2 else ('fg_hi' if t < 5 else ('fg' if t < 7.5 else 'fg_md'))
    for p in ((16, 9), (15, 10), (17, 10), (16, 11), (6, 16)):
        ic.px[p] = 'fn_4'
    for p in ((16, 10), (17, 16)):
        ic.px[p] = 'n_star'
    return ic


def draw_lock():
    """鎖頭：鐵鎖環（左亮右暗三階、頂緣受光）、金鎖身（頂亮底暗、左右各一階、上方一道箍線）、鑰匙孔＋下緣反光、兩顆小鉚釘。"""
    ic = UiIcon()
    shackle = arc(12.0, 9.5, 5.0, 2.4, 180, 360) | rect(6, 9, 7, 12) | rect(16, 9, 17, 12)
    for x, y in shackle:
        top_edge = (x, y - 1) not in shackle and x < 14
        ic.px[(x, y)] = 'fi_hi' if (x <= 8 or top_edge) else ('fi' if x <= 14 else 'fi_dk')
    body = rect(4, 11, 19, 21) - {(4, 11), (19, 11), (4, 21), (19, 21)}
    for x, y in body:
        if y == 11:
            c = 'fg_w'
        elif y == 12:
            c = 'fg_hi'
        elif y >= 20:
            c = 'fg_dk2' if y == 21 else 'fg_dk'
        elif x == 4:
            c = 'fg_hi'
        elif x == 19:
            c = 'fg_dk'
        elif y >= 18:
            c = 'fg_md'
        else:
            c = 'fg'
        ic.px[(x, y)] = c
    for x in range(5, 19):
        ic.px[(x, 13)] = 'fg' if x == 5 else 'fg_md'
    for p in ell(11.5, 15.4, 1.6, 1.6) | rect(11, 16, 12, 18):
        ic.px[p] = 'fg_hole'
    ic.px[(11, 19)] = 'fg_hi'
    ic.px[(12, 19)] = 'fg_hi'
    for x, y in ((6, 15), (17, 15)):
        ic.px[(x, y)] = 'fg_w'
        ic.px[(x, y + 1)] = 'fg_dk'
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


# ═══════════════════════════════ 互動提示（2026-11-28）═══════════════════════════════
# 世界裡「走近就冒、按 E 做什麼」的提示改成 [E 鍵帽][動作圖]（Core/InteractHint.cs），不再寫句子。
# 畫法跟上面細修過的 key_*／lock／shop_open 一樣：fk／fw／fi／fg 那幾組多階色、左上受光、外輪廓由 finish_ui 補。
# 只**新增**，上面的圖一張都不動（gen 完逐檔比對 md5）。

def bubble(ic, fill=('wh', 'li_hi', 'li')):
    """對話泡泡：圓角方框（左上亮、右下暗一階）＋左下的小尾巴。回傳泡泡本體的遮罩。"""
    body = rect(2, 3, 21, 15) - {(2, 3), (21, 3), (2, 15), (21, 15), (3, 3), (2, 4), (20, 3), (21, 4),
                                (2, 14), (3, 15), (21, 14), (20, 15)}
    tail = tri(5.0, 15.0, 4.0, 21.0, 11.0, 15.0)
    m = body | tail
    for x, y in m:
        if (x, y - 1) not in m or (x - 1, y) not in m:
            c = fill[0]
        elif (x + 1, y) not in m or (x, y + 1) not in m:
            c = fill[2]
        else:
            c = fill[1]
        ic.px[(x, y)] = c
    return m


def draw_act_talk():
    """交談：白色對話泡泡＋三個點。"""
    ic = UiIcon()
    bubble(ic)
    for x in (6, 11, 16):
        ic.put(rect(x, 8, x + 1, 9), 'ink')
    return ic


def draw_act_quest():
    """有任務可以接：泡泡裡一個橘色的「！」。"""
    ic = UiIcon()
    bubble(ic, ('fo_1', 'fo_2', 'fo_4'))
    ic.put(rect(11, 5, 12, 10), 'sw_dk')
    ic.put(rect(11, 5, 11, 9), 'sw')
    ic.put(rect(11, 12, 12, 13), 'sw_dk')
    return ic


def draw_act_quest_done():
    """任務可以回報：泡泡裡一顆金星（平塗：左上亮、右下暗一階、深金描邊）。"""
    ic = UiIcon()
    bubble(ic, ('fo_1', 'fo_2', 'fo_4'))
    s5 = ia.star(11.5, 9.6, 6.2, 2.8)
    ic.put(s5, 'fg')
    ic.put(border(s5), 'fg_dk')
    ic.put({(x, y) for x, y in s5 if (x, y) not in border(s5) and x + y <= 19}, 'fg_hi')
    return ic


def draw_act_door():
    """門（換地方）：石框拱門、三片木板、鐵鉸鍊、金門把、門前一階石階。"""
    ic = UiIcon()
    frame = rect(5, 4, 18, 20) | ell(11.5, 5.5, 6.5, 4.2)
    for x, y in frame:
        ic.px[(x, y)] = 'st_hi' if x <= 6 or y <= 2 else ('st' if x <= 16 else 'st_dk')
    door = rect(7, 6, 16, 20) | ell(11.5, 7.0, 4.5, 3.2)
    ic.cyl(door, ('fw_hi', 'fw', 'fw_dk'))
    for x in (9, 12, 14):
        ic.put({(x, y) for y in range(5, 21) if (x, y) in door}, 'fw_dk2')
    for y in (9, 16):
        ic.put(rect(7, y, 9, y), 'fi_dk')
    ic.put(rect(14, 12, 15, 13), 'fg_hi')
    ic.px[(15, 13)] = 'fg_dk'
    ic.put(rect(3, 21, 20, 22), 'st')
    ic.put(rect(3, 21, 20, 21), 'st_hi')
    return ic


def house(ic, x0, x1, ytop, ywall, ybot, roof, wall=('pa_hi', 'pa', 'pa_dk'), win='fo_3'):
    """小房子：三角屋頂（roof 三階）＋米色牆＋門＋窗。x0..x1 是牆的寬。"""
    cx = (x0 + x1 + 1) / 2.0
    rf = tri(x0 - 2.0, ywall + 0.5, cx, ytop, x1 + 3.0, ywall + 0.5)
    w = rect(x0, ywall, x1, ybot)
    ic.flat(w, wall)
    ic.sphere(rf, roof, cx - 2, ytop + 2, (x1 - x0) * 0.8 + 2, (ywall - ytop) + 2)
    ic.put({(x, ywall) for x in range(x0 - 1, x1 + 2)}, roof[2])
    dx = int(cx) - 1
    ic.put(rect(dx, ybot - 3, dx + 2, ybot), 'fw_dk')
    ic.put(rect(dx, ybot - 3, dx, ybot), 'fw')
    return rf | w


def draw_dest_shop():
    """目的地：自己的店（紅屋頂小屋，窗裡亮著暖光、門邊掛一塊小招牌）。"""
    ic = UiIcon()
    ic.put(rect(15, 3, 17, 7), 'st')
    ic.put(rect(15, 3, 17, 3), 'st_hi')
    house(ic, 4, 19, 2, 11, 21, ('rd_hi', 'rd', 'rd_dk'))
    ic.put(rect(6, 13, 8, 15), 'fo_3')
    ic.px[(6, 13)] = 'fo_1'
    ic.put(rect(15, 13, 17, 15), 'fo_3')
    ic.px[(15, 13)] = 'fo_1'
    ic.put(rect(15, 17, 18, 19), 'fg')                       # 小招牌
    ic.put(rect(15, 19, 18, 19), 'fg_dk')
    return ic


def draw_dest_town():
    """目的地：城鎮（兩棟不同顏色屋頂的房子，一高一矮）。"""
    ic = UiIcon()
    house(ic, 12, 21, 3, 10, 21, ('bl_hi', 'bl', 'bl_dk'))
    ic.put(rect(17, 13, 19, 15), 'fo_3')
    house(ic, 2, 10, 8, 14, 21, ('gr_hi', 'gr', 'gr_dk'))
    ic.put(rect(3, 16, 4, 17), 'fo_3')
    return ic


def draw_dest_cauldron():
    """目的地：魔女的房間（黑鐵鍋、冒綠泡泡的藥水、底下一點火）。"""
    ic = UiIcon()
    pot = ell(12.0, 14.0, 9.0, 6.5) - rect(0, 0, 24, 9)
    ic.sphere(pot, ('fi', 'fi_dk', 'fi_dk2'), 9.0, 11.0, 9.0, 6.5)
    ic.put(rect(3, 8, 20, 9), 'fi_hi')
    ic.put(rect(3, 9, 20, 9), 'fi')
    ic.put(rect(5, 7, 18, 7), 'cr')
    ic.put(rect(6, 6, 9, 6), 'cr_hi')
    ic.put(rect(5, 19, 7, 21), 'fi_dk2')
    ic.put(rect(16, 19, 18, 21), 'fi_dk2')
    ic.put(rect(9, 20, 14, 21), 'fire_o')
    ic.put(rect(10, 20, 13, 20), 'fire_y')
    for x, y in ((8, 3), (14, 2), (11, 4)):
        ic.glow_dot(x, y, 'cr_hi')
    return ic


def draw_dest_tree():
    """目的地：森林（圓圓的樹冠、木頭樹幹、兩顆紅果子）。"""
    ic = UiIcon()
    ic.cyl(rect(10, 14, 13, 21), ('fw_hi', 'fw', 'fw_dk'))
    can = ell(12.0, 9.0, 9.0, 7.5)
    ic.sphere(can, ('gr_hi', 'gr', 'gr_dk', 'gr_dk2'), 12.0, 9.0, 9.0, 7.5)
    for x, y in ((8, 10), (15, 7)):
        ic.put(rect(x, y, x + 1, y + 1), 'rd')
        ic.px[(x, y)] = 'rd_hi'
    return ic


def draw_act_sleep():
    """睡覺：金色彎月＋右上一個淡紫的 Z。"""
    ic = UiIcon()
    moon = ell(10.5, 13.0, 8.0, 8.0) - ell(15.0, 10.0, 6.8, 6.8)
    for x, y in moon:
        ic.px[(x, y)] = 'fg_hi' if x <= 5 else ('fg' if y <= 15 else 'fg_md')
    ic.put({(x, y) for x, y in moon if (x + 1, y + 1) not in moon and y >= 17}, 'fg_dk')
    z = {(16, 2), (17, 2), (18, 2), (19, 2), (18, 3), (17, 4), (16, 5), (17, 5), (18, 5), (19, 5)}
    ic.put(z, 'vi_hi')
    ic.put({(13, 7), (14, 7), (14, 8), (13, 9), (14, 9)}, 'vi_hi')
    return ic


def draw_act_chest():
    """開倉庫：打開的木箱（蓋子往後翻、裡面金光閃閃）、金色箍、前面一個小鎖扣。"""
    ic = UiIcon()
    lid = poly([(3.0, 11.0), (21.0, 11.0), (22.0, 4.0), (5.0, 4.0)])
    ic.put(lid, 'fw_dk')
    ic.put({(x, y) for x, y in lid if y <= 5}, 'fw')
    inner = rect(4, 9, 19, 11)
    ic.put(inner, 'fw_dk2')
    body = rect(3, 12, 20, 21)
    ic.flat(body, ('fw_hi', 'fw', 'fw_dk'))
    for x in (6, 17):
        ic.put(rect(x, 12, x, 21), 'fg_md')
    ic.put(rect(3, 12, 20, 12), 'fg')
    ic.put(rect(11, 13, 12, 15), 'fg_hi')
    ic.px[(12, 15)] = 'fg_dk'
    for x, y in ((8, 10), (13, 9), (16, 10)):
        ic.px[(x, y)] = 'fg_hi'
    ic.sparkle(12, 6, col='go_hi')
    return ic


def draw_act_wardrobe():
    """換衣服：鐵衣架掛一件紫色洋裝（腰帶金色）。"""
    ic = UiIcon()
    hook = arc(12.5, 3.5, 1.8, 1.2, 180, 360) | {(14, 4), (14, 5)}
    ic.put(hook, 'fi_hi')
    hanger = line(12, 5, 3, 9) | line(13, 5, 21, 9) | line(3, 9, 21, 9)
    ic.put(hanger, 'fi')
    dress = poly([(8.5, 8.5), (15.5, 8.5), (16.0, 12.0), (20.5, 21.5), (3.5, 21.5), (8.0, 12.0)])
    for x, y in dress:
        ic.px[(x, y)] = 'pu_hi' if x <= 7 or (x <= 9 and y < 12) else ('pu' if x <= 14 else 'pu_dk')
    ic.put(rect(8, 12, 16, 12), 'fg')
    ic.put(rect(5, 21, 19, 21), 'pu_dk2')
    for x, y in ((10, 16), (13, 18), (8, 19)):
        ic.px[(x, y)] = 'vi_hi'
    return ic


def draw_act_brewing():
    """熬煮中：沙漏（木框、玻璃、金色的沙一半在上一半在下）。"""
    ic = UiIcon()
    ic.put(rect(4, 2, 19, 3), 'fw')
    ic.put(rect(4, 2, 19, 2), 'fw_hi')
    ic.put(rect(4, 20, 19, 21), 'fw_dk')
    ic.put(rect(4, 20, 19, 20), 'fw')
    glass = poly([(6.0, 4.0), (18.0, 4.0), (13.0, 12.0), (18.0, 20.0), (6.0, 20.0), (11.0, 12.0)])
    ic.put(glass, 'sb')
    ic.put({(x, y) for x, y in glass if x <= 8}, 'sb_hi')
    top = {(x, y) for x, y in glass if 8 <= y <= 10}
    bot = {(x, y) for x, y in glass if y >= 16}
    ic.put(top, 'go')
    ic.put(bot | {(11, 13), (12, 14), (11, 15)}, 'go_hi')
    ic.put({(x, y) for x, y in bot if y >= 18}, 'go')
    return ic


def draw_act_sell():
    """賣東西：兩枚金幣（後面那枚露一半；前面那枚有一圈壓邊、中間一顆星、左上高光）＋一點亮光。"""
    ic = UiIcon()

    def coin(cx, cy, r, face=True):
        m = ell(cx, cy, r, r)
        ic.put(m, 'fg')
        ic.put({(x, y) for x, y in m if x + y > cx + cy + r * 0.6}, 'fg_md')
        ic.put(border(m), 'fg_dk')
        if face:
            inner = ell(cx, cy, r - 2.0, r - 2.0)
            ic.put(border(inner), 'fg_md')
            ic.put(ia.star(cx, cy, r * 0.45, r * 0.2), 'fg_dk')
            ic.put({(int(cx - r * 0.55), int(cy - r * 0.55)), (int(cx - r * 0.55) + 1, int(cy - r * 0.55) - 1)}, 'fg_w')
        return m
    coin(15.5, 9.0, 6.5, face=False)
    front = ell(9.5, 14.0, 7.5, 7.5)
    ic.sep(front, 'fg_dk2')
    coin(9.5, 14.0, 7.5)
    ic.sparkle(20, 3, col='go_hi')
    return ic


def draw_act_pet():
    """摸摸：粉紅愛心（左上高光）＋右下一個白色小肉球。"""
    ic = UiIcon()
    heart = ell(7.5, 8.5, 5.0, 5.0) | ell(15.5, 8.5, 5.0, 5.0) | tri(2.6, 10.0, 20.4, 10.0, 11.5, 20.5)
    ic.sphere(heart, ('pk_hi', 'pink', 'rd', 'rd_dk'), 9.0, 9.0, 11.0, 11.0)
    ic.put({(5, 6), (6, 5), (5, 7)}, 'wh')
    paw = ell(18.5, 19.5, 2.4, 2.0)
    ic.sep(paw, 'rd_dk2')
    ic.put(paw, 'li_hi')
    for x, y in ((16, 16), (18, 15), (20, 15), (21, 17)):
        ic.px[(x, y)] = 'li_hi'
    return ic


def draw_act_clear():
    """清掉枯枝：土堆上一株枯掉垂頭的褐色小苗（就是要清掉的那個）＋右上一把小鐮刀（鋼刃彎月、木柄）。"""
    ic = UiIcon()
    mound = ell(9.5, 21.0, 7.0, 2.5) - rect(0, 22, 24, 24)
    ic.flat(mound, ('co_hi', 'co', 'co_dk'))
    stem = polyline([(9, 19), (9, 13), (8, 10), (6, 9)])
    ic.put(stem, 'au_br')
    ic.put({(5, 10), (4, 11)}, 'au_br')                         # 垂下來的頭
    ic.put(polyline([(10, 15), (12, 16), (13, 18)]), 'au')        # 兩片垂掉的葉子（細）
    ic.put(polyline([(8, 14), (6, 15), (5, 17)]), 'au')
    blade = (ell(17.0, 7.5, 5.5, 5.0) - ell(18.2, 9.0, 4.6, 4.2)) - rect(0, 9, 24, 24)
    blade |= {(11, 9), (12, 9)}
    for x, y in blade:
        ic.px[(x, y)] = 'fi_hi' if (x, y - 1) not in blade else 'fi'
    ic.put(rect(21, 7, 22, 14), 'fw')
    ic.put(rect(21, 7, 21, 14), 'fw_hi')
    ic.put(rect(21, 7, 22, 7), 'fi_dk')
    return ic


def draw_act_water():
    """澆水：藍色澆花器（把手、長壺嘴、蓮蓬頭）＋三滴水。"""
    ic = UiIcon()
    handle = arc(9.5, 11.0, 5.0, 1.8, 180, 360)
    ic.put(handle, 'ai_dk')
    spout = thick(line(14, 15, 19, 9), 1)
    ic.put(spout, 'ai')
    rose = rect(19, 6, 21, 9)
    ic.put(rose, 'ai_dk')
    ic.put(rect(20, 6, 21, 6), 'ai_hi')
    body = rect(3, 11, 15, 20) - {(3, 11), (15, 11), (3, 20), (15, 20)}
    ic.cyl(body, ('ai_hi', 'ai', 'ai_dk'))
    ic.put(rect(4, 13, 14, 13), 'ai_dk2')
    for x, y in ((21, 12), (22, 15), (20, 17)):
        ic.glow_dot(x, y, 'wa_hi')
        ic.glow_dot(x, y + 1, 'wa')
    return ic


INTERACT_ICONS = [
    ('act_talk', '交談（NPC）', draw_act_talk),
    ('act_quest', '交談：有任務可以接', draw_act_quest),
    ('act_quest_done', '交談：任務可以回報', draw_act_quest_done),
    ('act_door', '門（換地方）', draw_act_door),
    ('dest_shop', '目的地：自己的店', draw_dest_shop),
    ('dest_town', '目的地：城鎮', draw_dest_town),
    ('dest_cauldron', '目的地：魔女的房間（藥水室）', draw_dest_cauldron),
    ('dest_tree', '目的地：森林', draw_dest_tree),
    ('act_sleep', '睡覺（床）', draw_act_sleep),
    ('act_chest', '開倉庫（木箱）', draw_act_chest),
    ('act_wardrobe', '換衣服（衣櫃）', draw_act_wardrobe),
    ('act_brewing', '熬煮中（鍋爐忙著）', draw_act_brewing),
    ('act_sell', '賣東西（販售桌、雜貨鋪收購）', draw_act_sell),
    ('act_pet', '摸摸（貓）', draw_act_pet),
    ('act_clear', '清掉枯枝（花圃）', draw_act_clear),
    ('act_water', '澆水（花圃）', draw_act_water),
]


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
ICONS += INTERACT_ICONS                     # 2026-11-28 互動提示（只加在後面，前面的不動）


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
    out_dir = os.path.abspath(args[args.index('--out') + 1]) if '--out' in args else OUT_DIR   # 迭代用：輸出到別處，不碰 Assets
    arts = render_all()
    os.makedirs(out_dir, exist_ok=True)
    for fname, desc, im in arts:
        p = os.path.join(out_dir, fname + '.png')
        im.save(p, optimize=False)
        print(f'{fname:<14} {im.width}×{im.height}  {md5(p)[:8]}  {desc}')
    print(f'共 {len(arts)} 張')
    if preview_dir:
        for f in preview(arts, preview_dir):
            print('預覽', f)


if __name__ == '__main__':
    main()
