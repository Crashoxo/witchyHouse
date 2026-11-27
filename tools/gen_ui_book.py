#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調配藥水面板（UI/BrewPanel.cs）的「魔法配方書」圖產生器＋離線預覽。

    python tools/gen_ui_book.py                 # 輸出 Assets/Resources/ui/skin8/book-*.png
    python tools/gen_ui_book.py --check         # 只比對 Skin8Book.uss 的九宮格數字跟這裡的常數
    python tools/gen_ui_book.py --preview DIR   # 照 Skin8Book.uss 的版面數字拼 mockup（不寫專案檔）

── 2026-11-28 細畫版（使用者：「這個也要更精緻」）──────────────────────────────
  跟下排腰包、上方工具列同一套：**1 px 原生像素直接畫**（Px＝gen_ui_skin 的 _TbPx，不經 ×3 放大），
  色相偏移的多階漸層，基準是女巫走路圖（witch8 ×1.6）。色盤：BOOK_PAL（羊皮紙、梅紫皮革、綠、紅、藤蔓）
  ＋ gen_ui_skin 的 BELT_PAL（紫 c1～c8、金 g0～g5）。
  圖放在 skin8/ 底下 → PixelArtImporter 的例外把 PPU 設成 100，UiSkinImportGuard 也會自動修匯入競態。
  ⚠️ 尺寸固定的元素一律畫成**整張原尺寸的圖、不切九宮格**（封面 840×420、書頁 396×369、熬鈕 108×42、
     目錄條 768×78、格子 60×60）——這樣紙紋、燙金、針腳、書脊都可以畫滿，不怕被拉長。
     只有寬度會變的標題緞帶（book-ribbon）與材料卡（book-card，窄卡版會變寬）還是九宮格。

── 書的組成（都在 Skin8Book.uss，由 BrewPanel 自己 styleSheets.Add）───────────────
  book-cover        840×420  梅紫皮革封面：雙金框線＋金珠、四角金護角（紫寶石）、書脊（上下露出的皮帶、金箍、縫線、堵頭布）、落地陰影
  book-page-l/r     396×369  書頁：外側與下緣頁緣疊層、書脊側柔和陰影、上緣近書脊微凹、極淡纖維紋、淡印刷框線；右頁右下摺角
  book-arrow-l/r    45×51    翻頁箭頭（一般／滑過／按下）：紫皮牌＋金三角＋小金菱形
  book-circle       156      成品金絲框（雙金線、金點環、蕾絲弧、八方位小星、內圈暖光）；成品圖 96 疊在正中
  book-moon／-vine／-star  書頁小裝飾（燙金弦月、藥草花邊、細長四角星）
  book-mark         24×96    紫緞絲帶書籤（金邊、燕尾、金星吊飾）
  book-ribbon       66×51    標題緞帶（slice 27／15／27／15，同 skin8/ribbon；別的面板的 ribbon 不動）
  book-close        36×36    關閉鈕（一般／滑過／按下）：圓形紫皮金邊＋米白 ×
  book-card(-short) 21×21    材料卡（slice 9）：夠＝米白卡淡金邊、不夠＝淡紅卡玫瑰邊
  book-plus         15       材料之間的燙金「＋」
  book-brew-a／-b（＋-hover／-down）、book-brew-off  108×42  熬 1（紫皮金邊）／熬 N（金牌）／做不出來（灰藕石＋淡斜紋）
  book-shelf        768×78   目錄條（梅紫皮帶、金滾邊、針腳、兩端金釘）
  book-slot(-sel／-off／-empty)  60×60  目錄格：一般／目前這頁／做不出來／空位（最後一頁補滿用）
  book-sarrow-l/r（＋-hover／-down／-off）  33×33  目錄條兩端的小翻頁鈕
  book-dot          15       目錄格「做得出來」的小綠寶石

結果是確定的：沒有亂數（纖維紋用固定種子的雜湊），重跑 md5 相同。
"""
import hashlib
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gen_ui_skin as S                 # noqa: E402  基元、色盤（只讀，不改）
from gen_ui_skin import edge            # noqa: E402

OUT_DIR = S.OUT_DIR
USS_PATH = os.path.join(ROOT, 'Assets', 'Resources', 'ui', 'Skin8Book.uss')
SCALE = S.SCALE          # 只用在 SLICES 換算（SLICES 照 gen_ui_skin 的慣例寫邏輯格，×3 才是 px）

# ═══════════════════════════════ 色盤與畫布 ═══════════════════════════════
BOOK_PAL = {
    # 羊皮紙（暖、亮部偏奶油、暗部偏棕紅）
    'p0': '#fffaee', 'p1': '#fbf0d6', 'p2': '#f6e7c8', 'p3': '#eedab5', 'p4': '#e2c79d', 'p5': '#d0b083',
    'p6': '#b48d63', 'p7': '#8e6a4c', 'p8': '#6a4a3c', 'pf1': '#f3e3c3', 'pf2': '#fffcf3',
    # 封面皮革（深梅紫）
    'l0': '#1c0a1c', 'l1': '#2b1028', 'l2': '#3b1636', 'l3': '#4d1e45', 'l4': '#602853', 'l5': '#753463',
    'l6': '#8f4676', 'l7': '#aa5e8a',
    # 綠（做得出來）
    'e1': '#2a5e36', 'e2': '#438a45', 'e3': '#76bb5e', 'e4': '#b8e890', 'e5': '#e6fbcf',
    # 紅（不夠）
    'r0': '#6e2030', 'r1': '#a23446', 'r2': '#d46874', 'r3': '#f0b7b2', 'r4': '#f9dcd4', 'r5': '#fcebe5',
    # 藤蔓與小花
    'v1': '#3d6438', 'v2': '#5d8c48', 'v3': '#8cbc68', 'v4': '#c3e39a', 'f1': '#d9708f', 'f2': '#f2a7bd', 'f3': '#fde0e8',
    'fy': '#f7d96a',
    # 停用的按鈕（灰藕石）
    'x1': '#5f5868', 'x2': '#7b7385', 'x3': '#968ea0', 'x4': '#b1aab9', 'x5': '#cbc5d1', 'x6': '#e2dde6',
    # 印刷線（燙金在紙上，用棕金不用外輪廓）
    'ink_g': '#a67a3c',
}


class Px(S._TbPx):
    def put(self, x, y, c):
        super().put(x, y, BOOK_PAL.get(c, c))

    def shade(self, x, y, c, a):
        super().shade(x, y, BOOK_PAL.get(c, c), a)


def h01(x, y, seed=0):
    """確定的雜湊亂數 0～1。"""
    v = (x * 73856093) ^ (y * 19349663) ^ (seed * 83492791)
    v = (v ^ (v >> 13)) * 1274126177
    v ^= v >> 16
    return (v & 0xffff) / 65535.0


def lcg(seed):
    s = seed & 0x7fffffff
    while True:
        s = (s * 1103515245 + 12345) & 0x7fffffff
        yield s / 0x7fffffff


# ═══════════════════════ 封面 840×420（固定，不切）═══════════════════════
COVER_W, COVER_H = 840, 420


def _guard(px, flip_x, flip_y):
    """四角金護角（以左上為準畫，再鏡射）：圓弧內緣、外輪廓、多階金、刻花、紫寶石、兩顆鉚釘。"""
    W, H = COVER_W, COVER_H
    R = 40

    def P(x, y):
        return (W - 1 - x if flip_x else x, H - 1 - y if flip_y else y)
    shape = set()
    for y in range(R):
        for x in range(R):
            # 外角直角、內緣是一段往外凸的弧（像書角包銅）
            if x + y < R + 4 and (x - R) ** 2 + (y - R) ** 2 >= (R - 10) ** 2 and x < R and y < R:
                if (x, y) in ((0, 0), (1, 0), (0, 1)):
                    continue
                shape.add((x, y))
    L, inner = S._tb_layers(shape, 2)
    for x, y in shape:
        t = (x + y) / (2.0 * R)
        c = 'g5' if t < 0.12 else ('g4' if t < 0.3 else ('g3' if t < 0.52 else 'g2'))
        px.put(*P(x, y), c)
    for x, y in L[1]:
        px.put(*P(x, y), 'g4' if (x <= 2 or y <= 2) else 'g1')
    for x, y in L[0]:
        px.put(*P(x, y), 'l0')
    # 刻花：沿內弧一條細線
    for x, y in shape:
        d = math.hypot(x - R, y - R)
        if R - 7.6 < d <= R - 6.6 and x > 3 and y > 3:
            px.put(*P(x, y), 'g2')
        if R - 6.6 < d <= R - 5.8 and x > 3 and y > 3:
            px.put(*P(x, y), 'g5')
    # 紫寶石＋金托
    gx, gy = 11, 11
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            dd = abs(dx) + abs(dy)
            if dd == 3:
                px.put(*P(gx + dx, gy + dy), 'g1')
            elif dd <= 2:
                s = dx + dy
                px.put(*P(gx + dx, gy + dy), 'c8' if s <= -2 else ('c7' if s <= 0 else ('c5' if s <= 1 else 'c4')))
    px.put(*P(gx - 1, gy - 1), 'wh')
    for rx, ry in ((24, 5), (5, 24)):
        px.put(*P(rx, ry), 'g5'); px.put(*P(rx + 1, ry), 'g3'); px.put(*P(rx, ry + 1), 'g3'); px.put(*P(rx + 1, ry + 1), 'g1')


def draw_cover():
    W, H = COVER_W, COVER_H
    px = Px(W, H)
    body_h = H - 4
    m = S._tb_rounded(W, body_h, 10)
    for x, y in m:
        n = h01(x, y, 1)
        c = 'l4'
        if n < 0.06:
            c = 'l3'
        elif n > 0.95:
            c = 'l5'
        px.put(x, y, c)
    L, _ = S._tb_layers(m, 4)
    for x, y in L[0]:
        px.put(x, y, 'l0')
    for x, y in L[1]:
        px.put(x, y, 'l7' if (y <= 2 or x <= 2) and x < W - 3 and y < body_h - 3 else 'l2')
    for x, y in L[2]:
        px.put(x, y, 'l6' if (y <= 3 or x <= 3) and x < W - 4 and y < body_h - 4 else 'l3')
    for x, y in L[3]:
        px.put(x, y, 'l5' if (y <= 4 or x <= 4) and x < W - 5 and y < body_h - 5 else 'l4')
    # 燙金：外框線（inset 7）＋內框細線（inset 11），中間一排金珠
    for inset, hi, lo in ((7, 'g4', 'g2'), (11, 'g3', 'g1')):
        x0, y0, x1, y1 = inset, inset, W - 1 - inset, body_h - 1 - inset
        for x in range(x0 + 2, x1 - 1):
            px.put(x, y0, hi); px.put(x, y1, lo)
            px.put(x, y0 + 1, 'l2'); px.put(x, y1 + 1, 'l6')
        for y in range(y0 + 2, y1 - 1):
            px.put(x0, y, hi); px.put(x1, y, lo)
            px.put(x0 + 1, y, 'l2'); px.put(x1 + 1, y, 'l6')
        for cx, cy in ((x0 + 1, y0 + 1), (x1 - 1, y0 + 1), (x0 + 1, y1 - 1), (x1 - 1, y1 - 1)):
            px.put(cx, cy, hi)
    for x in range(14, W - 14, 5):
        for y in (9, body_h - 10):
            px.put(x, y, 'g4' if y == 9 else 'g3')
    for y in range(14, body_h - 14, 5):
        for x in (9, W - 10):
            px.put(x, y, 'g4' if x == 9 else 'g3')
    # 書脊（中間）：上下露出的地方是一條隆起的皮帶＋金箍＋縫線，上緣一點堵頭布
    cx = W // 2
    for y in list(range(0, 22)) + list(range(389, body_h)):
        for x in range(cx - 14, cx + 14):
            if (x, y) not in m:
                continue
            d = x - (cx - 14)
            c = 'l6' if d < 3 else ('l5' if d < 8 else ('l4' if d < 20 else ('l3' if d < 25 else 'l2')))
            px.put(x, y, c)
        if (cx - 15, y) in m:
            px.put(cx - 15, y, 'l1')
            px.put(cx + 14, y, 'l1')
    for y in (5, 16, 395, 406):
        for x in range(cx - 14, cx + 14):
            px.put(x, y, 'g4' if x < cx else 'g2')
            px.put(x, y + 1, 'g2' if x < cx else 'g1')
    for y in list(range(8, 15, 3)) + list(range(398, 405, 3)):
        px.put(cx - 1, y, 'g5'); px.put(cx, y, 'g3')
    for x in range(cx - 13, cx + 13):                  # 堵頭布（紫金相間）
        px.put(x, 19, 'c7' if (x // 2) % 2 else 'g3')
        px.put(x, 20, 'c5' if (x // 2) % 2 else 'g2')
    for fx in (False, True):
        for fy in (False, True):
            _guard(px, fx, fy)
    # 落地陰影
    for x in range(W):
        ys = [y for y in range(body_h) if (x, y) in m]
        if ys:
            for i, a in enumerate((0.45, 0.28, 0.14, 0.05)):
                px.shade(x, max(ys) + 1 + i, '#140a1c', a)
    return px


# ═══════════════════════ 書頁 396×369（固定，不切）═══════════════════════
PAGE_W, PAGE_H = 396, 369


def draw_page(side):
    """左頁（右頁＝鏡射＋右下摺角）：外側頁緣疊層、下緣厚疊層、書脊側柔和陰影（帶 1 px 交錯過渡）、
    上緣在書脊附近微微下凹、極淡的纖維紋、內側一圈很淡的印刷框線與四角小花。"""
    W, H = PAGE_W, PAGE_H
    px = Px(W, H)
    top_of = {}
    for x in range(W):
        d_in = W - 1 - x
        top_of[x] = 0 if d_in > 40 else int(round(3.0 * ((40 - d_in) / 40.0) ** 2))
    stack_x = ['p7', 'p3', 'p5', 'p2', 'p5', 'p2', 'p4']          # 外側：由外往內
    stack_y = ['p8', 'p4', 'p6', 'p3', 'p6', 'p3', 'p5', 'p2', 'p4', 'p2', 'p4']   # 下緣
    spine = [('p7', 1), ('p6', 2), ('p5', 3), ('p4', 4), ('p3', 5), ('p2', 7)]     # 書脊陰影：顏色、寬
    sp_cols = []
    for c, w in spine:
        sp_cols += [c] * w
    for y in range(H):
        for x in range(W):
            t = top_of[x]
            if y < t:
                continue
            d_out, d_bot, d_in = x, H - 1 - y, W - 1 - x
            if d_out == 0 and (y <= t + 1 or d_bot <= 1):
                continue
            c = None
            if d_bot < len(stack_y) and d_out < len(stack_x):
                c = stack_y[d_bot] if d_bot <= d_out else stack_x[d_out]
            elif d_bot < len(stack_y):
                c = stack_y[d_bot]
            elif d_out < len(stack_x):
                c = stack_x[d_out]
            elif y == t:
                c = 'p6'
            elif d_in < len(sp_cols):
                c = sp_cols[d_in]
                # 相鄰兩階交錯一欄（細緻的漸層）
                if 0 < d_in < len(sp_cols) - 1 and sp_cols[d_in] != sp_cols[d_in - 1] and (y % 2 == 0):
                    c = sp_cols[d_in - 1]
            elif y == t + 1:
                c = 'p0'
            else:
                # 內緣 6 px 的淡暗邊（紙的厚度感）
                dd = min(d_out - len(stack_x), d_bot - len(stack_y), y - t - 2)
                c = 'p2' if dd < 3 else 'p1'
                if dd == 3 and (x + y) % 2 == 0:
                    c = 'p2'
                n = h01(x, y, 7)
                if c == 'p1':
                    if n < 0.012:
                        c = 'pf1'
                    elif n > 0.992:
                        c = 'pf2'
            px.put(x, y, c)
    # 纖維：短短的細線
    rnd = lcg(42 if side == 'l' else 43)
    for _ in range(70):
        x0 = 14 + int(next(rnd) * (W - 50))
        y0 = 12 + int(next(rnd) * (H - 34))
        L = 3 + int(next(rnd) * 5)
        dy = next(rnd) - 0.5
        for k in range(L):
            x, y = x0 + k, int(round(y0 + dy * k))
            if px.px[x, y][:3] == S._bc(BOOK_PAL['p1']):
                px.put(x, y, 'pf1')
    # 很淡的印刷框線＋四角小花
    fx0, fy0, fx1, fy1 = 15, 11, W - 1 - 24, H - 1 - 18
    for x in range(fx0 + 6, fx1 - 5):
        px.put(x, fy0, 'p3'); px.put(x, fy1, 'p3')
    for y in range(fy0 + 6, fy1 - 5):
        px.put(fx0, y, 'p3'); px.put(fx1, y, 'p3')
    for cx, cy, sx, sy in ((fx0, fy0, 1, 1), (fx1, fy0, -1, 1), (fx0, fy1, 1, -1), (fx1, fy1, -1, -1)):
        for k in range(1, 5):
            px.put(cx + sx * k, cy + sy * 1, 'p4')
            px.put(cx + sx * 1, cy + sy * k, 'p4')
        px.put(cx + sx * 2, cy + sy * 2, 'ink_g')
        px.put(cx, cy, 'p4')
    if side == 'r':
        out = Px(W, H)
        for y in range(H):
            for x in range(W):
                p = px.px[x, y]
                if p[3]:
                    out.px[W - 1 - x, y] = p
        px = out
        _dog_ear(px)
    return px


def _dog_ear(px):
    """右頁右下角的小摺角（22 px）：折走的角透明、紙背暗兩階、摺痕一條亮、底下落一點影。"""
    W, H = px.w, px.h
    D = 22
    for y in range(H - D - 1, H):
        for x in range(W - D - 1, W):
            dx, dy = W - 1 - x, H - 1 - y
            s = dx + dy
            if s < D:
                px.px[x, y] = (0, 0, 0, 0)
    for k in range(D + 1):
        x, y = W - 1 - D + k, H - 1 - k
        px.put(x, y, 'p6')
    # 紙背（三角形，往左上翻起）
    for y in range(H - D, H):
        for x in range(W - D, W):
            dx, dy = W - 1 - x, H - 1 - y
            if dx + dy >= D + 1 and dx <= D and dy <= D:
                pass
    for j in range(1, D - 1):
        for i in range(1, D - j):
            # 翻起來的那片：直角在 (W-1-D, H-1-D)，貼著摺痕
            x, y = W - 1 - D + i, H - 1 - D + j
            if i + j < D - 1:
                c = 'p4' if (i + j) > D - 5 else ('p3' if (i + j) > 6 else 'p2')
                px.put(x, y, c)
    for i in range(D - 1):
        px.put(W - 1 - D + i, H - 1 - D, 'p6')
        px.put(W - 1 - D, H - 1 - D + i, 'p6')
    for k in range(1, D):
        px.put(W - 1 - D + k, H - 1 - k + 1, 'p5')


# ═══════════════════════ 魔法陣（成品框）156 ═══════════════════════

def _star4(px, cx, cy, r, core='g5', arm='g3', tip='g2'):
    px.put(cx, cy, 'wh' if r >= 3 else core)
    for k in range(1, r + 1):
        c = core if k == 1 else (arm if k < r else tip)
        for dx, dy in ((k, 0), (-k, 0), (0, k), (0, -k)):
            px.put(cx + dx, cy + dy, c)
    if r >= 3:
        for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            px.put(cx + dx, cy + dy, 'g4')


def draw_circle():
    """成品的金絲框：兩圈細金線（中間一圈金點）、外圈淡淡的蕾絲弧、八方位小星、內圈一點暖光。成品圖 96 疊在正中。"""
    N = 156
    px = Px(N, N)
    c = (N - 1) / 2.0
    for y in range(N):
        for x in range(N):
            r = math.hypot(x - c, y - c)
            ang = math.atan2(y - c, x - c)
            lt = math.cos(ang + math.radians(135))          # 左上 1、右下 -1
            if r <= 47:
                px.put(x, y, 'p0' if r <= 30 else ('pf2' if r <= 40 else 'p1'))
            elif 52.4 < r <= 53.6:
                px.put(x, y, 'g2' if lt < 0 else 'g3')
            elif 56.9 < r <= 58.1:
                px.put(x, y, 'g4' if lt > 0.3 else ('g3' if lt > -0.4 else 'g2'))
            elif 58.1 < r <= 59.0 and lt < -0.2:
                px.put(x, y, 'g1')
    for k in range(48):                                    # 金點環
        a = 2 * math.pi * k / 48
        x, y = int(round(c + 55.3 * math.cos(a))), int(round(c + 55.3 * math.sin(a)))
        px.put(x, y, 'g4' if k % 2 == 0 else 'g2')
    for k in range(24):                                    # 外圈蕾絲：小弧＋點
        a0 = 2 * math.pi * k / 24
        for t in range(-6, 7):
            a = a0 + t * 0.018
            rr = 63.5 + 2.6 * math.cos(t / 6.0 * math.pi / 2)
            x, y = int(round(c + rr * math.cos(a))), int(round(c + rr * math.sin(a)))
            px.put(x, y, 'p4')
        x, y = int(round(c + 69 * math.cos(a0))), int(round(c + 69 * math.sin(a0)))
        px.put(x, y, 'p5')
    for k in range(8):
        a = math.pi / 4 * k - math.pi / 2
        x, y = int(round(c + 66 * math.cos(a))), int(round(c + 66 * math.sin(a)))
        big = k % 2 == 0
        _star4(px, x, y, 4 if big else 2)
    return px


# ═══════════════════════ 小裝飾 ═══════════════════════

def draw_moon():
    """月亮 39：燙金弦月（多階、棕金描邊不用黑），旁邊兩顆小星。"""
    N = 39
    px = Px(N, N)
    cx, cy, R = 17.0, 19.0, 13.0
    pts = set()
    for y in range(N):
        for x in range(N):
            d1 = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            d2 = math.hypot(x + 0.5 - cx - 6.5, y + 0.5 - cy + 4.0)
            if d1 <= R and d2 > R - 1.5:
                pts.add((x, y))
    for x, y in pts:
        t = (x - cx) * 0.5 + (y - cy)
        px.put(x, y, 'g5' if t < -8 else ('g4' if t < -1 else ('g3' if t < 6 else 'g2')))
    for x, y in pts:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in pts:
                px.put(x + dx, y + dy, 'ink_g')
    _star4(px, 31, 10, 3)
    _star4(px, 33, 24, 1, core='g4')
    px.put(27, 30, 'g3')
    return px


def draw_vine():
    """藥草花邊 81×33：彎彎的細莖（1 px）、兩色飽滿小葉上下交錯、尾端兩朵五瓣粉花（黃芯）＋一顆花苞。"""
    W, H = 81, 33
    px = Px(W, H)
    stem = []
    for x in range(2, 62):
        y = 21 + 4.5 * math.sin(x / 10.0) - x * 0.08
        stem.append((x, int(round(y))))
    for i, (x, y) in enumerate(stem):
        px.put(x, y, 'v1')
        if i and abs(stem[i - 1][1] - y) > 1:
            px.put(x, (y + stem[i - 1][1]) // 2, 'v1')

    def leaf(x, y, up, L):
        sgn = -1 if up else 1
        cells = {}
        for k in range(L):
            t = k / (L - 1.0)
            w = 1.6 * math.sin(math.pi * t) + 0.4
            yc = y + sgn * (1 + k * 0.55)
            for yy in range(int(math.floor(yc - w)), int(math.ceil(yc + w)) + 1):
                if abs(yy - yc) <= w:
                    cells[(x + k, yy)] = 'v3' if (yy - yc) * sgn < 0 else 'v2'
        for (cx_, cy_), c in cells.items():
            px.put(cx_, cy_, c)
        for k in range(1, L - 1):                      # 葉脈
            px.put(x + k, int(round(y + sgn * (1 + k * 0.55))), 'v4' if k < L // 2 else 'v3')
    for i, (x, y) in enumerate(stem):
        if i % 8 == 3:
            leaf(x, y, (i // 8) % 2 == 0, 8 if i < 36 else 6)

    def flower(cx, cy):
        for a in range(5):
            ang = -math.pi / 2 + a * 2 * math.pi / 5
            px_, py_ = cx + 2.4 * math.cos(ang), cy + 2.4 * math.sin(ang)
            for ex in (0, 1):
                for ey in (0, 1):
                    X, Y = int(math.floor(px_)) + ex - 1 + 1, int(math.floor(py_)) + ey - 1 + 1
                    px.put(X, Y, 'f2' if ey == 0 else 'f1')
            px.put(int(math.floor(px_)), int(math.floor(py_)), 'f3')
        px.put(cx, cy, 'fy'); px.put(cx + 1, cy, 'fy'); px.put(cx, cy + 1, 'g3'); px.put(cx + 1, cy + 1, 'g2')
    ex, ey = stem[-1]
    flower(ex + 6, ey - 3)
    flower(ex - 4, ey - 11)
    px.put(ex + 14, ey + 3, 'f2'); px.put(ex + 14, ey + 2, 'f3'); px.put(ex + 15, ey + 3, 'f1')
    px.put(ex + 13, ey + 4, 'v2'); px.put(ex + 12, ey + 4, 'v1'); px.put(ex + 11, ey + 3, 'v1')
    for x in range(ex, ex + 4):
        px.put(x, ey - (x - ex) // 2, 'v1')
    return px


def draw_star():
    """小星 15：細長四角星（燙金），中心一點白。"""
    N = 15
    px = Px(N, N)
    _star4(px, 7, 7, 6, core='g4', arm='g3', tip='g2')
    for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        px.put(7 + dx, 7 + dy, 'g3')
    px.put(6, 6, 'g5')
    return px


def draw_dot():
    """做得出來的小綠寶石 15：外輪廓、金托、四階綠、亮點。"""
    N = 15
    px = Px(N, N)
    c = 7.0
    for y in range(N):
        for x in range(N):
            d = math.hypot(x - c, y - c)
            if d > 6.6:
                continue
            lt = (x - c) + (y - c)
            if d > 5.7:
                px.put(x, y, 'l0')
            elif d > 4.6:
                px.put(x, y, 'g4' if lt < 0 else 'g2')
            else:
                px.put(x, y, 'e4' if lt < -4 else ('e3' if lt < 0 else ('e2' if lt < 4 else 'e1')))
    px.put(5, 5, 'wh'); px.put(6, 5, 'e5')
    return px


def draw_mark():
    """絲帶書籤 24×96：紫緞（橫向六階、一條亮帶）、兩側金邊、燕尾、上端 4 列塞進書裡的暗部、一顆金星吊飾。"""
    W, H = 24, 96
    px = Px(W, H)
    x0, x1 = 4, 19
    body = set()
    for y in range(H):
        for x in range(x0, x1 + 1):
            body.add((x, y))
    for y in range(H - 9, H):
        k = y - (H - 9)
        for x in range(x0, x1 + 1):
            if abs(x - (x0 + x1) / 2.0) < k * 0.95:
                body.discard((x, y))
    ramp = ['c4', 'c6', 'c7', 'c8', 'c7', 'c6', 'c6', 'c5', 'c5', 'c4', 'c4', 'c3']
    for x, y in body:
        i = x - x0 - 2
        c = ramp[max(0, min(len(ramp) - 1, i))] if 0 <= i < len(ramp) else 'c3'
        if y < 5:
            c = {'c8': 'c5', 'c7': 'c4', 'c6': 'c4'}.get(c, 'c3')
        px.put(x, y, c)
    for y in range(H):
        if (x0 + 1, y) in body:
            px.put(x0 + 1, y, 'g3' if y >= 5 else 'g1')
        if (x1 - 1, y) in body:
            px.put(x1 - 1, y, 'g2' if y >= 5 else 'g1')
    for x, y in body:
        for dx, dy in ((1, 0), (-1, 0), (0, 1)):
            if (x + dx, y + dy) not in body:
                px.put(x, y, 'l0')
    for x in range(x0, x1 + 1):
        px.put(x, 5, 'c2')
    # 金星吊飾（掛在燕尾上方）
    _star4(px, 11, 70, 3)
    px.put(11, 66, 'g2'); px.put(12, 66, 'g2')
    return px


# ═══════════════════════ 按鈕類 ═══════════════════════

def _tab(px, W, H, ramp, down, r=6):
    """立體圓角牌（共用：翻頁箭頭、熬鈕）：外輪廓、雙圈邊（左上亮）、面板上淺下深、3 px 厚邊（按下收掉）。
    ramp＝(邊亮, 邊, 邊暗, 面最亮, 面亮, 面, 面中, 面暗, 厚邊 1, 厚邊 2, 厚邊 3)。回傳 (面遮罩, top, face_bot)。"""
    rim_hi, rim, rim_dk, fh2, fh, f, fm, fd, e1, e2, e3 = ramp
    top = 3 if down else 0
    body = S._tb_rounded(W, H - top, r, 0, top)
    face_bot = H - 1 - (1 if down else 4)
    for x, y in body:
        px.put(x, y, e1 if y == face_bot + 1 else (e2 if y < H - 2 else e3))
    face = {(x, y) for x, y in body if y <= face_bot}
    L, inner = S._tb_layers(face, 3)
    n = face_bot - top
    for x, y in inner | L[2]:
        rr = y - top
        px.put(x, y, fh2 if rr <= 3 else (fh if rr <= n * 0.3 else (f if rr <= n * 0.7 else (fm if rr <= n - 3 else fd))))
    for x, y in L[2]:
        if x <= 2:
            px.put(x, y, fh)
        elif x >= W - 3:
            px.put(x, y, fm)
    for x, y in L[0]:
        if y >= face_bot - 1 or x >= W - 2:
            px.put(x, y, rim_dk)
        else:
            px.put(x, y, rim_hi if (y <= top + 1 or x <= 1) else rim)
    for x, y in L[1]:
        px.put(x, y, rim_hi if (y <= top + 2 and x < W - 3) else (rim if (x <= 2 and y < face_bot - 2) else rim_dk))
    for x, y in edge(body):
        px.put(x, y, 'ol')
    return face, top, face_bot


RAMP_PU = ('g4', 'g3', 'g1', 'c8', 'c7', 'c6', 'c5', 'c4', 'c3', 'c2', 'c1')
RAMP_PU_H = ('g5', 'g4', 'g2', '#c493c8', 'c8', 'c7', 'c6', 'c5', 'c3', 'c2', 'c1')
RAMP_GO = ('wh', 'g5', 'g2', '#fff7d6', 'g5', '#f7d77c', 'g4', '#e2b453', 'g2', 'g1', '#4e2c14')
RAMP_GO_H = ('wh', 'wh', 'g3', 'wh', '#fff7d6', 'g5', '#f7d77c', 'g4', 'g2', 'g1', '#4e2c14')
RAMP_OFF = ('x6', 'x5', 'x2', 'x6', 'x5', 'x4', 'x4', 'x3', 'x2', 'x1', '#3e3948')


def draw_arrow(side, state):
    """翻頁箭頭 45×51：紫皮牌＋金邊，中間一個飽滿的金三角（上緣一條高光、下半暗一階、落影），尾端一顆小金菱形。"""
    W, H = 45, 51
    px = Px(W, H)
    face, top, fb = _tab(px, W, H, RAMP_PU_H if state == 'h' else RAMP_PU, state == 'd', r=8)
    cy = top + (fb - top) // 2
    tri = set()
    for x in range(13, 27):
        hh = (x - 13) * 0.68
        for y in range(cy - 10, cy + 11):
            if abs(y - cy) <= hh:
                tri.add((x, y))
    dia = {(31 + dx, cy + dy) for dx in range(-2, 3) for dy in range(-2, 3) if abs(dx) + abs(dy) <= 2}
    if side == 'r':
        tri = {(W - 1 - x, y) for x, y in tri}
        dia = {(W - 1 - x, y) for x, y in dia}
    shape = tri | dia
    for x, y in shape:
        if (x + 1, y + 1) not in shape:
            px.put(x + 1, y + 1, 'c2')
    for x, y in shape:
        px.put(x, y, 'g4' if y < cy else ('g3' if y < cy + 4 else 'g2'))
    for x, y in tri:
        if (x, y - 1) not in tri:
            px.put(x, y, 'g5')
    for x, y in dia:
        if (x, y - 1) not in dia or (x - 1, y) not in dia:
            px.put(x, y, 'g5')
    tip = (13, cy) if side == 'l' else (W - 14, cy)
    px.put(*tip, 'wh')
    return px


def draw_brew(kind, state):
    """熬鈕 108×42（固定，不切）：'a'＝紫皮金邊（熬 1）、'b'＝金牌（熬 N）、'off'＝灰藕石（做不出來，字照樣看得清）。
    四角各一顆小鉚釘；左右兩端各一顆小星（a／b）。"""
    W, H = 108, 42
    px = Px(W, H)
    if kind == 'off':
        ramp = RAMP_OFF
    elif kind == 'a':
        ramp = RAMP_PU_H if state == 'h' else RAMP_PU
    else:
        ramp = RAMP_GO_H if state == 'h' else RAMP_GO
    face, top, fb = _tab(px, W, H, ramp, state == 'd', r=7)
    for cx, cy in ((5, top + 5), (W - 6, top + 5), (5, fb - 5), (W - 6, fb - 5)):
        px.put(cx, cy, ramp[0]); px.put(cx + 1, cy, ramp[1]); px.put(cx, cy + 1, ramp[1]); px.put(cx + 1, cy + 1, ramp[2])
    if kind != 'off':
        my = top + (fb - top) // 2
        for sx in (10, W - 11):
            col = ('g5', 'g3') if kind == 'a' else ('#fff7d6', 'g2')
            px.put(sx, my, col[0])
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                px.put(sx + dx, my + dy, col[1])
    else:
        # 停用：面板上一條淡淡的斜紋（像蒙了一層灰，不髒）
        for x, y in face:
            if (x + y) % 6 == 0 and top + 4 < y < fb - 3 and 6 < x < W - 7:
                px.put(x, y, 'x5')
    return px


def draw_close(state):
    """關閉鈕 36×36：圓形紫皮金邊鈕＋米白細 ×（兩階），滑過亮一階、按下沉 2。"""
    N = 36
    px = Px(N, N)
    dn = 2 if state == 'd' else 0
    c = (N - 1) / 2.0
    face_r = 14.5
    ramp = RAMP_PU_H if state == 'h' else RAMP_PU
    # 厚邊（底下）
    for y in range(N):
        for x in range(N):
            d = math.hypot(x - c, y - (c - 1 + dn))
            d2 = math.hypot(x - c, y - (c + 2 - (dn * 1.5)))
            if d2 <= face_r + 1.5 and not d <= face_r + 1.5:
                px.put(x, y, ramp[9])
    for y in range(N):
        for x in range(N):
            d = math.hypot(x - c, y - (c - 1 + dn))
            if d > face_r + 1.5:
                continue
            lt = ((x - c) + (y - c)) / max(d, 0.01)
            if d > face_r + 0.5:
                px.put(x, y, 'ol')
            elif d > face_r - 0.7:
                px.put(x, y, ramp[0] if lt < -0.3 else (ramp[1] if lt < 0.6 else ramp[2]))
            elif d > face_r - 1.8:
                px.put(x, y, ramp[1] if lt < 0 else ramp[2])
            else:
                rr = y - (c - 1 + dn) + face_r
                px.put(x, y, ramp[3] if rr < 6 else (ramp[4] if rr < 11 else (ramp[5] if rr < 19 else ramp[6])))
    for y in range(N):
        for x in range(N):
            d2 = math.hypot(x - c, y - (c + 2 - dn * 1.5))
            d = math.hypot(x - c, y - (c - 1 + dn))
            if face_r + 1.5 < d2 <= face_r + 2.5 and d > face_r + 1.5:
                px.put(x, y, 'ol')
    cx, cy = int(c), int(c - 1 + dn)
    for k in range(-5, 6):
        for (x, y) in ((cx + k, cy + k), (cx + k, cy - k)):
            px.put(x, y, 'wh' if k < 0 else '#f3e6d6')
            px.put(x + 1, y, '#f3e6d6' if k < 0 else '#d8c4cf')
    for k in range(-5, 6):
        px.put(cx + k + 1, cy + k + 1, 'c2')
    return px


def draw_ribbon():
    """標題緞帶 66×51（slice 27／15／27／15，同 skin8/ribbon）：紫緞中帶（橫向一致：上金邊、亮帶、中、暗、下金邊）、
    兩端往後折的燕尾（暗一階、V 形缺口）、落一點影。"""
    W, H = 66, 51
    px = Px(W, H)
    band_top, band_bot = 3, 41
    tail_top, tail_bot = 13, 49
    # 尾巴（在後面）：x 0..20 與 W-21..W-1
    for side in (0, 1):
        for y in range(tail_top, tail_bot + 1):
            for x in range(0, 22):
                notch = (y - (tail_top + tail_bot) / 2.0)
                if x < 7 - abs(notch) * 0.38 * 1.0 and abs(notch) < 18:
                    continue
                X = x if side == 0 else W - 1 - x
                c = 'c3' if y < tail_top + 3 else ('c4' if y < tail_bot - 4 else 'c2')
                if y in (tail_top + 1, tail_bot - 1):
                    c = 'g1'
                px.put(X, y, c)
    # 折角陰影（尾巴與中帶接縫）
    for side in (0, 1):
        for y in range(band_bot - 1, tail_bot):
            for x in (18, 19, 20):
                X = x if side == 0 else W - 1 - x
                px.put(X, y, 'c1')
    # 中帶
    rows = {}
    for y in range(band_top, band_bot + 1):
        r = y - band_top
        n = band_bot - band_top
        if r == 1:
            c = 'g4'
        elif r == 2:
            c = 'g2'
        elif r == n - 1:
            c = 'g2'
        elif r == n - 2:
            c = 'g3'
        elif r <= 6:
            c = 'c8'
        elif r <= 12:
            c = 'c7'
        elif r <= n - 12:
            c = 'c6'
        elif r <= n - 6:
            c = 'c5'
        else:
            c = 'c4'
        rows[y] = c
    for y in range(band_top, band_bot + 1):
        for x in range(9, W - 9):
            px.put(x, y, rows[y])
    # 中帶兩端微微捲起（斜切的端面）
    for y in range(band_top, band_bot + 1):
        for k, X in ((0, 9), (0, W - 10)):
            px.put(X, y, 'c3' if X > W / 2 else 'c7')
    # 外輪廓
    occ = {(x, y) for y in range(H) for x in range(W) if px.px[x, y][3]}
    for x, y in occ:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in occ and 0 <= q[0] < W and 0 <= q[1] < H:
                px.put(q[0], q[1], 'ol')
    return px


def draw_card(kind):
    """材料卡 21×21（slice 9）：'ok'＝米白卡＋淡金邊、四角小金點；'short'＝淡紅卡＋玫瑰邊。下 1 列淡影。中間單色。"""
    N = 21
    px = Px(N, N)
    H = N - 1
    m = S._tb_rounded(N, H, 5)
    if kind == 'ok':
        rim_o, rim_hi, rim_lo, f_hi, f = 'p6', 'p0', 'p4', 'p0', 'p1'
        dot = 'g3'
    else:
        rim_o, rim_hi, rim_lo, f_hi, f = 'r1', 'r5', 'r2', 'r5', 'r4'
        dot = 'r2'
    for x, y in m:
        px.put(x, y, f)
    L, _ = S._tb_layers(m, 3)
    for x, y in L[0]:
        px.put(x, y, rim_o)
    for x, y in L[1]:
        px.put(x, y, rim_hi if (y <= 2 or x <= 2) and x < N - 3 and y < H - 3 else rim_lo)
    for x, y in L[2]:
        px.put(x, y, f_hi if (y <= 3 or x <= 3) and x < N - 4 and y < H - 4 else f)
    for cx, cy in ((4, 4), (N - 5, 4), (4, H - 5), (N - 5, H - 5)):
        px.put(cx, cy, dot)
    for x in range(N):
        ys = [y for (xx, y) in m if xx == x]
        if ys:
            px.shade(x, max(ys) + 1, '#5a3a2a', 0.22)
    return px


def draw_plus():
    """材料之間的「＋」15：燙金十字（上左亮）、棕金描邊。"""
    N = 15
    px = Px(N, N)
    pts = {(x, y) for x in range(5, 10) for y in range(2, 13) if 6 <= x <= 8} | \
          {(x, y) for x in range(2, 13) for y in range(6, 9)}
    for x, y in pts:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in pts:
                px.put(x + dx, y + dy, 'ink_g')
    for x, y in pts:
        px.put(x, y, 'g5' if (x == 6 or y == 6) else ('g4' if x + y < 15 else 'g3'))
    return px


# ═══════════════════════ 下排目錄 ═══════════════════════
SHELF_W, SHELF_H = 768, 78


def draw_shelf():
    """目錄條 768×78（固定）：深梅皮帶、上下金滾邊＋針腳（固定尺寸，針腳不會被拉長）、兩端圓頭各一顆金釘、落地陰影。"""
    W, H = SHELF_W, SHELF_H
    px = Px(W, H)
    bh = H - 3
    m = S._tb_rounded(W, bh, 9)
    for x, y in m:
        n = h01(x, y, 3)
        px.put(x, y, 'l3' if n < 0.05 else ('l5' if n > 0.97 else 'l4'))
    L, _ = S._tb_layers(m, 6)
    for x, y in L[0]:
        px.put(x, y, 'l0')
    for x, y in L[1]:
        px.put(x, y, 'l7' if (y <= 2 or x <= 2) and x < W - 3 and y < bh - 3 else 'l2')
    for x, y in L[2]:
        px.put(x, y, 'l6' if (y <= 3 or x <= 3) and x < W - 4 and y < bh - 4 else 'l3')
    for x, y in L[3]:
        px.put(x, y, 'g4' if (y <= 4 or x <= 4) and x < W - 5 and y < bh - 5 else 'g2')
    for x, y in L[4]:
        px.put(x, y, 'g2' if (y <= 5 or x <= 5) and x < W - 6 and y < bh - 6 else 'g1')
    for x, y in L[5]:
        px.put(x, y, 'l2' if (y <= 6 or x <= 6) and x < W - 7 and y < bh - 7 else 'l5')
    # 針腳（上下各一排，週期 4：亮、中、空、空）
    for x in range(14, W - 14):
        ph = x % 4
        if ph < 2:
            px.put(x, 9, 'g5' if ph == 0 else 'g3')
            px.put(x, bh - 10, 'g4' if ph == 0 else 'g2')
    for cx in (8, W - 9):
        S._tb_stud(px, cx, bh // 2)
    for x in range(W):
        ys = [y for (xx, y) in m if xx == x]
        if ys:
            for i, a in enumerate((0.42, 0.24, 0.10)):
                px.shade(x, max(ys) + 1 + i, '#140a1c', a)
    return px


def draw_slot(kind):
    """目錄格 60×60（固定）：
    'n'   做得出來／一般：凹進皮帶的小窗（梅紫底、上左內陰影），細金框；
    'off' 做不出來：框是暗金、底更暗一階（圖由 uss 淡化），仍看得出是一格；
    'sel' 目前這頁：亮金雙框＋四角金星＋暖光底；
    'empty' 空位（最後一頁補滿用）：只有一圈很淡的虛線框，不搶眼。"""
    N = 60
    px = Px(N, N)
    m = S._tb_rounded(N, N, 7)
    if kind == 'empty':
        # 空位：一個淺淺的凹槽（比一般格暗、沒有金框），四角一點淡金，看得出「這裡還沒有東西」
        for x, y in m:
            px.put(x, y, 'l3')
        L, _ = S._tb_layers(m, 3)
        for x, y in L[0]:
            px.put(x, y, 'l1')
        for x, y in L[1]:
            px.put(x, y, 'l2' if (y <= 2 or x <= 2) else 'l5')
        for x, y in L[2]:
            if y <= 3 or x <= 3:
                px.put(x, y, 'l2')
        for cx, cy in ((7, 7), (N - 8, 7), (7, N - 8), (N - 8, N - 8)):
            px.put(cx, cy, 'g1')
        return px
    if kind == 'sel':
        rim = ('l0', 'g5', 'g4', 'g3', 'g2')
        floor = ('#a2577e', '#8f4676', '#7c3a6a', '#6c3060')
    elif kind == 'off':
        rim = ('l0', 'g2', 'g1', 'l2', 'l2')
        floor = ('l3', 'l3', 'l2', 'l2')
    else:
        rim = ('l0', 'g4', 'g2', 'g1', 'l1')
        floor = ('l5', 'l4', 'l4', 'l3')
    for x, y in m:
        d = math.hypot(x - 29.5, y - 27)
        px.put(x, y, floor[0] if d < 14 else (floor[1] if d < 22 else (floor[2] if d < 28 else floor[3])))
    L, _ = S._tb_layers(m, 5)
    for x, y in L[0]:
        px.put(x, y, rim[0])
    for x, y in L[1]:
        px.put(x, y, rim[1] if (y <= 2 or x <= 2) and x < N - 3 and y < N - 3 else rim[2])
    for x, y in L[2]:
        px.put(x, y, rim[2] if (y <= 3 or x <= 3) and x < N - 4 and y < N - 4 else rim[3])
    for x, y in L[3]:                         # 內陰影：上左暗（凹下去）
        px.put(x, y, 'l1' if (y <= 4 or x <= 4) else floor[2])
    for x, y in L[4]:
        if y <= 5 or x <= 5:
            px.put(x, y, 'l2')
    if kind == 'sel':
        for cx, cy in ((6, 6), (N - 7, 6), (6, N - 7), (N - 7, N - 7)):
            _star4(px, cx, cy, 2)
    return px


def draw_sarrow(side, state):
    """目錄條兩端的小翻頁鈕 33×33：圓形紫皮金邊、金三角；停用＝暗梅、三角暗（不刺眼）。"""
    N = 33
    px = Px(N, N)
    dn = 2 if state == 'd' else 0
    ramp = {'n': RAMP_PU, 'h': RAMP_PU_H, 'd': RAMP_PU,
            'x': ('l4', 'l3', 'l2', 'l4', 'l4', 'l3', 'l3', 'l2', 'l2', 'l1', 'l0')}[state]
    c = 16.0
    R = 13.0
    for y in range(N):
        for x in range(N):
            d = math.hypot(x - c, y - (c - 1 + dn))
            d2 = math.hypot(x - c, y - (c + 1.5))
            if d > R + 1.5 and d2 <= R + 1.5 and not dn:
                px.put(x, y, ramp[9])
    for y in range(N):
        for x in range(N):
            d = math.hypot(x - c, y - (c - 1 + dn))
            if d > R + 1.5:
                continue
            lt = ((x - c) + (y - c)) / max(d, 0.01)
            if d > R + 0.5:
                px.put(x, y, 'ol')
            elif d > R - 0.7:
                px.put(x, y, ramp[0] if lt < -0.3 else (ramp[1] if lt < 0.6 else ramp[2]))
            else:
                rr = y - (c - 1 + dn) + R
                px.put(x, y, ramp[3] if rr < 5 else (ramp[4] if rr < 10 else (ramp[5] if rr < 18 else ramp[6])))
    occ = {(x, y) for y in range(N) for x in range(N) if px.px[x, y][3]}
    for x, y in occ:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in occ and 0 <= q[0] < N and 0 <= q[1] < N:
                px.put(q[0], q[1], 'ol')
    cy = int(c - 1 + dn)
    tri = set()
    for i in range(7):
        x = 11 + i
        for y in range(cy - i, cy + i + 1):
            if abs(y - cy) <= i * 0.8:
                tri.add((x, y))
    if side == 'r':
        tri = {(N - 1 - x, y) for x, y in tri}
    off = state == 'x'
    for x, y in tri:
        if (x + 1, y + 1) not in tri:
            px.put(x + 1, y + 1, 'l1' if off else 'c2')
    for x, y in tri:
        if off:
            px.put(x, y, 'l6' if y <= cy else 'l5')
        else:
            px.put(x, y, 'g5' if y < cy - 1 else ('g4' if y <= cy else ('g3' if y < cy + 3 else 'g2')))
    return px


def all_images():
    out = {
        'book-cover': draw_cover(),
        'book-page-l': draw_page('l'),
        'book-page-r': draw_page('r'),
        'book-circle': draw_circle(),
        'book-moon': draw_moon(),
        'book-vine': draw_vine(),
        'book-star': draw_star(),
        'book-dot': draw_dot(),
        'book-mark': draw_mark(),
        'book-ribbon': draw_ribbon(),
        'book-plus': draw_plus(),
        'book-card': draw_card('ok'),
        'book-card-short': draw_card('short'),
        'book-shelf': draw_shelf(),
    }
    for side in ('l', 'r'):
        for st, suf in (('n', ''), ('h', '-hover'), ('d', '-down')):
            out[f'book-arrow-{side}{suf}'] = draw_arrow(side, st)
        for st, suf in (('n', ''), ('h', '-hover'), ('d', '-down'), ('x', '-off')):
            out[f'book-sarrow-{side}{suf}'] = draw_sarrow(side, st)
    for st, suf in (('n', ''), ('h', '-hover'), ('d', '-down')):
        out[f'book-close{suf}'] = draw_close(st)
        out[f'book-brew-a{suf}'] = draw_brew('a', st)
        out[f'book-brew-b{suf}'] = draw_brew('b', st)
    out['book-brew-off'] = draw_brew('off', 'n')
    for k, suf in (('n', ''), ('sel', '-sel'), ('off', '-off'), ('empty', '-empty')):
        out[f'book-slot{suf}'] = draw_slot(k)
    return {k: v.im for k, v in out.items()}


# ═══════════════════════════════ 清單 ═══════════════════════════════
# (檔名, 畫法, slice)：slice＝None 表示原尺寸顯示（不切），否則是 (左, 上, 右, 下) 邏輯格（×3＝px）。

def _books():
    out = [
        ('book-cover', draw_cover, None),
        ('book-page-l', lambda: draw_page('l'), None),
        ('book-page-r', lambda: draw_page('r'), None),
    ]
    for side in ('l', 'r'):
        for st, suf in (('n', ''), ('h', '-hover'), ('d', '-down')):
            out.append((f'book-arrow-{side}{suf}', lambda a=side, s=st: draw_arrow(a, s), None))
    out += [
        ('book-circle', draw_circle, None),
        ('book-moon', draw_moon, None),
        ('book-vine', draw_vine, None),
        ('book-star', draw_star, None),
        ('book-dot', draw_dot, None),
        ('book-mark', draw_mark, None),
        # ── 2026-11-28 細畫版新增（只往尾巴加）──
        ('book-ribbon', draw_ribbon, (9, 5, 9, 5)),
        ('book-plus', draw_plus, None),
        ('book-card', lambda: draw_card('ok'), (3, 3, 3, 3)),
        ('book-card-short', lambda: draw_card('short'), (3, 3, 3, 3)),
        ('book-shelf', draw_shelf, None),
    ]
    for st, suf in (('n', ''), ('h', '-hover'), ('d', '-down')):
        out.append((f'book-close{suf}', lambda s=st: draw_close(s), None))
    for k in ('a', 'b'):
        for st, suf in (('n', ''), ('h', '-hover'), ('d', '-down')):
            out.append((f'book-brew-{k}{suf}', lambda k=k, s=st: draw_brew(k, s), None))
    out.append(('book-brew-off', lambda: draw_brew('off', 'n'), None))
    for k, suf in (('n', ''), ('sel', '-sel'), ('off', '-off'), ('empty', '-empty')):
        out.append((f'book-slot{suf}', lambda k=k: draw_slot(k), None))
    for side in ('l', 'r'):
        for st, suf in (('n', ''), ('h', '-hover'), ('d', '-down'), ('x', '-off')):
            out.append((f'book-sarrow-{side}{suf}', lambda a=side, s=st: draw_sarrow(a, s), None))
    return out


BOOKS = _books()
SLICES = {name: sl for name, _, sl in BOOKS if sl is not None}


def render_all():
    return [(name, fn().image(), sl) for name, fn, sl in BOOKS]


def md5(p):
    with open(p, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def check_uss():
    """Skin8Book.uss 裡每個寫了 resource("ui/skin8/…") 又寫了 -unity-slice-* 的區塊，數字要等於 SLICES×3；
    原尺寸顯示的 book 圖（不在 SLICES）不該寫 slice。"""
    if not os.path.exists(USS_PATH):
        print('找不到', USS_PATH)
        return 1
    src = re.sub(r'/\*.*?\*/', '', open(USS_PATH, encoding='utf-8').read(), flags=re.S)
    allslices = dict(S.SLICES)
    allslices.update(SLICES)
    book_names = {name for name, _, _ in BOOKS}
    bad = 0
    for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', src):
        for name in re.findall(r'resource\("ui/skin8/([\w-]+)"\)', body):
            if not os.path.exists(os.path.join(OUT_DIR, name + '.png')):
                print(f'✗ {sel.strip()}：skin8/{name}.png 不存在')
                bad += 1
                continue
            sides = re.findall(r'-unity-slice-(left|top|right|bottom)\s*:\s*(\d+)', body)
            if name not in allslices:
                if name in book_names and any(int(v) for _, v in sides):
                    print(f'✗ {sel.strip()}：{name} 是原尺寸圖，不該寫非 0 的 slice')
                    bad += 1
                continue
            want = dict(zip(('left', 'top', 'right', 'bottom'), (v * SCALE for v in allslices[name])))
            for side, v in sides:
                if int(v) != want[side]:
                    print(f'✗ {sel.strip()}：{name} 的 slice-{side} 寫 {v}，應該是 {want[side]}')
                    bad += 1
    print('Skin8Book.uss 九宮格數字檢查：', '全部一致' if bad == 0 else f'{bad} 處不一致')
    return 1 if bad else 0


# ═══════════════════════════════ 離線預覽 ═══════════════════════════════
# ⚠️ 下面的數字**必須跟 Skin8Book.uss 一致**。改 uss 就要改這裡。

BOOK_W, BOOK_H = 840, 420              # .bk-book
BOOK_PAD = (21, 24, 30, 24)            # .bk-book padding（上 右 下 左）
PG_W, PG_H = 396, 369                  # .bk-page
PG_PAD_OUT, PG_PAD_IN, PG_PAD_T, PG_PAD_B = 36, 30, 21, 21     # .bk-leaf--l/--r padding
HERO_CIRCLE, HERO_ICON = 156, 96       # .bk-hero / .bk-hero-icon（道具圖 24 格 ×4，每格 4 px）
TILE_H = 108                           # .bk-mat
STRIP_PER = 10                         # BrewPanel.StripPer
SHELF_W, SHELF_H, SHELF_PAD_T, SHELF_PAD_X = 768, 78, 7, 12    # .bk-shelf
SLOT, SLOT_GAP, SARROW = 60, 6, 33     # .bk-slot（margin-right 6）、.bk-sarrow
FOOT_INK = (236, 222, 196)

# (名稱, 售價, [(材料, 需要)]) ＝ Data/Recipes.cs
RECIPES = [
    ('清涼藥水', 35, [('藍莓', 2), ('藥草', 1)]),
    ('戀愛藥水', 40, [('漿果', 2), ('黑莓', 1)]),
    ('暗影藥水', 42, [('落葉', 3), ('黑莓', 1)]),
    ('烈焰藥水', 45, [('藥草', 2), ('樹枝', 2)]),
    ('溫暖熱可可', 30, [('金蘋果', 1), ('漿果', 2)]),
    ('蜂蜜藥劑', 55, [('金蘋果', 2), ('藥草', 1)]),
    ('黃金藥劑', 70, [('金蘋果', 2), ('藍莓', 2)]),
    ('夜影掃帚', 120, [('木材', 3), ('樹枝', 2), ('黑莓', 1)]),
    ('星光掃帚', 140, [('木材', 3), ('樹枝', 2), ('藍莓', 2)]),
    ('羽翼掃帚', 160, [('木材', 3), ('樹枝', 3), ('金蘋果', 1)]),
    ('安眠藥水', 110, [('薰衣草', 2), ('藥草', 1)]),
    ('花香水', 125, [('毛地黃', 2), ('漿果', 1)]),
    ('星光藥劑', 175, [('星鈴花', 1), ('藍莓', 2)]),
]
DESC = {
    '清涼藥水': '喝一口從喉嚨涼到指尖，夏天賣得最好。',
    '暗影藥水': '喝下後腳步聲會消失一小段時間。',
    '夜影掃帚': '夜裡飛行不會被看見的黑色掃帚。',
    '星光藥劑': '星鈴花與藍莓調的夜空色藥劑，瓶底沉著會亮的細砂，搖一搖整瓶都在閃，是收藏家最愛的一瓶。',
}
HAVE = {'藍莓': 5, '藥草': 3, '漿果': 4, '黑莓': 0, '落葉': 7, '樹枝': 6, '金蘋果': 1, '木材': 9, '星鈴花': 1}


def preview(outdir):
    from PIL import Image
    import preview_ui_skin as P
    os.makedirs(outdir, exist_ok=True)
    arts = render_all()
    IM = {name: im for name, im, _ in arts}
    INK, SOFT, GOLD, GREEN, RED, CREAM = P.INK, P.INK_SOFT, P.GOLD_INK, P.GREEN_INK, P.RED_INK, P.CREAM

    def img(n):
        return IM[n] if n in IM else P.SKIN[n]

    def nine(n, sl, w, h):
        im = img(n)
        l, t, r, b = sl
        W, H = im.size
        w, h = int(w), int(h)
        out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        xs = [(0, l, 0, l), (l, W - r, l, w - r), (W - r, W, w - r, w)]
        ys = [(0, t, 0, t), (t, H - b, t, h - b), (H - b, H, h - b, h)]
        for sx0, sx1, dx0, dx1 in xs:
            for sy0, sy1, dy0, dy1 in ys:
                if sx1 > sx0 and sy1 > sy0 and dx1 > dx0 and dy1 > dy0:
                    out.alpha_composite(im.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.NEAREST), (dx0, dy0))
        return out

    def item(name, s):
        return P.item(name).resize((s, s), Image.NEAREST)

    def maxc(inputs):
        return min(10, min(HAVE.get(m, 0) // n for m, n in inputs))

    def put(c, im, x, y, a=1.0):
        if a < 1:
            im = im.copy()
            im.putalpha(im.getchannel('A').point(lambda v: int(v * a)))
        c.im.alpha_composite(im, (int(round(x)), int(round(y))))

    def wrap(c, s, size, w):
        lines, cur = [], ''
        for ch in s:
            if c.tw(cur + ch, size) > w:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines

    def left(c, x, y, idx):
        name, price, inputs = RECIPES[idx]
        put(c, img('book-star'), x + PG_W - 48 - 15, y + 36)          # .bk-star--a
        put(c, img('book-star'), x + 45, y + 177)                     # .bk-star--b
        put(c, img('book-star'), x + PG_W - 57 - 15, y + 216)         # .bk-star--c
        cx0, cw = x + PG_PAD_OUT, PG_W - PG_PAD_OUT - PG_PAD_IN
        col_h = HERO_CIRCLE + 36 + 42 + 6 + 30
        top = y + PG_PAD_T + (PG_H - PG_PAD_T - PG_PAD_B - col_h) / 2
        hx = cx0 + (cw - HERO_CIRCLE) / 2
        put(c, img('book-circle'), hx, top)
        o = (HERO_CIRCLE - HERO_ICON) / 2
        put(c, item(name, HERO_ICON), hx + o, top + o)
        ty = top + HERO_CIRCLE
        c.text(cx0, ty, name, 24, INK, bold=True, w=cw, h=36, align='c')
        ty += 36
        lines = wrap(c, DESC.get(name, '一瓶用心熬出來的好東西。'), 14, 294)
        if len(lines) > 2:                                             # .bk-desc：兩行、超出「…」
            lines = lines[:2]
            lines[1] = lines[1][:-1] + '…'
        for k, ln in enumerate(lines):
            c.text(cx0, ty + k * 21, ln, 14, SOFT, w=cw, h=21, align='c')
        ty += 42 + 6
        mw = 24 + c.tw(str(price), 20, True)
        put(c, img('coin'), cx0 + (cw - mw) / 2, ty + 4.5)
        c.text(cx0 + (cw - mw) / 2 + 24, ty, str(price), 20, GOLD, bold=True, h=30)
        c.text(x, y + PG_H - 15 - 21, f'{idx + 1} / {len(RECIPES)}', 13, SOFT, w=PG_W, h=21, align='c')

    def right(c, x, y, idx, inputs=None):
        name, price, ins = RECIPES[idx]
        inputs = inputs or ins
        put(c, img('book-moon'), x + PG_W - 21 - 39, y + 18)
        put(c, img('book-vine'), x + PG_W - 42 - 81, y + PG_H - 27 - 33)
        cx0, cw = x + PG_PAD_IN, PG_W - PG_PAD_OUT - PG_PAD_IN
        mx = maxc(inputs)
        col_h = 36 + TILE_H + 21 + 30 + 18 + 42
        top = y + PG_PAD_T + (PG_H - PG_PAD_T - PG_PAD_B - col_h) / 2
        hw = c.tw('材料', 15, True)
        hx = cx0 + (cw - hw) / 2
        c.text(hx, top, '材料', 15, SOFT, bold=True, h=27)
        put(c, img('book-star'), hx - 9 - 15, top + 6)
        put(c, img('book-star'), hx + hw + 9, top + 6)
        top += 36
        n = len(inputs)
        tile_w, plus_w, icon, fs = (90, 24, 48, 20) if n <= 3 else ((63, 15, 48, 20) if n == 4 else (54, 6, 36, 16))
        row_w = n * tile_w + (n - 1) * plus_w
        tx = cx0 + (cw - row_w) / 2
        for i, (m, need) in enumerate(inputs):
            have = HAVE.get(m, 0)
            ok = have >= need
            put(c, nine('book-card' if ok else 'book-card-short', (9, 9, 9, 9), tile_w, TILE_H), tx, top)
            put(c, item(m, icon), tx + (tile_w - icon) / 2, top + 15)
            c.text(tx, top + 15 + icon + 3, f'{have}/{need}', fs, GREEN if ok else RED, bold=True, w=tile_w, h=30, align='c')
            tx += tile_w
            if i < n - 1:
                if plus_w >= 15:
                    put(c, img('book-plus'), tx + (plus_w - 15) / 2, top + (TILE_H - 15) / 2)
                tx += plus_w
        cy = top + TILE_H + 21
        s = f'×{mx}'
        w = 27 + c.tw(s, 20, True)
        sx = cx0 + (cw - w) / 2
        put(c, item(name, 24), sx, cy + 3)
        c.text(sx + 27, cy, s, 20, GREEN if mx else RED, bold=True, h=30)
        by = cy + 30 + 18
        bx = cx0 + (cw - (108 * 2 + 12)) / 2
        ok = mx >= 1
        for i, (label, kind) in enumerate((('熬 1', 'a'), (f'熬 {mx}' if mx else '熬最大', 'b'))):
            x0 = bx + i * 120
            put(c, img(f'book-brew-{kind}' if ok else 'book-brew-off'), x0, by)
            if not ok:
                col, sh = (108, 99, 118), (1, (232, 228, 236))           # .bk .bk-brew:disabled
            elif kind == 'b':
                col, sh = INK, (1, (255, 244, 205))
            else:
                col, sh = CREAM, (1, P.OUTLINE)
            c.text(x0, by, label, 17, col, bold=True, shadow=sh, w=108, h=39, align='c')

    def strip(c, x, y, sel, spage):
        put(c, img('book-shelf'), x, y)
        n = len(RECIPES)
        pages = (n + STRIP_PER - 1) // STRIP_PER
        ay = y + SHELF_PAD_T + (SLOT - SARROW) / 2
        if pages > 1:
            put(c, img('book-sarrow-l' + ('-off' if spage == 0 else '')), x + SHELF_PAD_X, ay)
            put(c, img('book-sarrow-r' + ('-off' if spage == pages - 1 else '')), x + SHELF_W - SHELF_PAD_X - SARROW, ay)
        sx = x + SHELF_PAD_X + SARROW + 12
        for i in range(STRIP_PER):
            idx = spage * STRIP_PER + i
            if idx >= n:
                put(c, img('book-slot-empty'), sx, y + SHELF_PAD_T)
            else:
                name, price, inputs = RECIPES[idx]
                can = maxc(inputs) >= 1
                is_sel = idx == sel
                lift = 6 if is_sel else 0
                put(c, img('book-slot-sel' if is_sel else ('book-slot' if can else 'book-slot-off')), sx, y + SHELF_PAD_T - lift)
                put(c, item(name, 48), sx + 6, y + SHELF_PAD_T - lift + 6, 1.0 if (can or is_sel) else 0.55)
                if can:
                    put(c, img('book-dot'), sx + SLOT - 15 + 3, y + SHELF_PAD_T - lift - 3)
            sx += SLOT + SLOT_GAP

    def mock(fname, idx, spage=None, inputs=None):
        c = P.Canvas(bg=P.background())
        P.dim(c)
        total_h = 15 + BOOK_H + 9 + SHELF_H + 6 + 27
        bx = (P.SCREEN_W - BOOK_W) // 2
        by = (P.SCREEN_H - total_h) // 2 + 15
        put(c, img('book-cover'), bx, by)
        lx, py = bx + BOOK_PAD[3], by + BOOK_PAD[0]
        put(c, img('book-page-l'), lx, py)
        put(c, img('book-page-r'), lx + PG_W, py)
        left(c, lx, py, idx)
        right(c, lx + PG_W, py, idx, inputs)
        put(c, img('book-mark'), bx + 78, by - 9)
        title = '調配藥水'
        rw = max(150, 72 + c.tw(title, 21, True))
        put(c, nine('book-ribbon', (27, 15, 27, 15), rw, 51), bx + (BOOK_W - rw) / 2, by - 15)
        c.text(bx + (BOOK_W - rw) / 2, by - 15, title, 21, CREAM, bold=True, shadow=(2, P.OUTLINE), w=rw, h=45, align='c')
        put(c, img('book-close'), bx + BOOK_W - 36 + 12, by - 12)
        put(c, img('book-arrow-l'), bx - 27, by + 183)
        put(c, img('book-arrow-r'), bx + BOOK_W + 27 - 45, by + 183)
        sy = by + BOOK_H + 9
        strip(c, bx + (BOOK_W - SHELF_W) // 2, sy, idx, idx // STRIP_PER if spage is None else spage)
        fy = sy + SHELF_H + 6
        parts = [('key', 'Esc'), ('txt', '關閉'), ('gap', 18), ('key', '←'), ('key', '→'), ('txt', '翻頁')]
        tot = sum((max(36, 12 + c.tw(v, 12, True)) + 3) if k == 'key' else (c.tw(v, 14) + 3 if k == 'txt' else v)
                  for k, v in parts)
        fx = bx + (BOOK_W - tot) / 2
        for k, v in parts:
            if k == 'key':
                kw = max(36, 12 + c.tw(v, 12, True))
                put(c, nine('keycap', (9, 9, 9, 12), kw, 27), fx, fy)
                c.text(fx, fy, v, 12, INK, bold=True, w=kw, h=24, align='c')
                fx += kw + 3
            elif k == 'txt':
                c.text(fx, fy, v, 14, FOOT_INK, shadow=(1, P.OUTLINE), h=27)
                fx += c.tw(v, 14) + 3
            else:
                fx += v
        p = os.path.join(outdir, fname + '.png')
        c.im.save(p)
        c.im.resize((1280, 720), Image.NEAREST).save(os.path.join(outdir, fname + '_720p.png'))
        return p

    out = [mock('book_ok', 0), mock('book_short', 2), mock('book_strip_p2', 12),
           mock('book_strip_p1_from_p2', 12, spage=0),
           mock('book_4mats', 7, inputs=[('木材', 3), ('樹枝', 2), ('黑莓', 1), ('藍莓', 1)])]
    sheet = Image.new('RGBA', (1200, 900), (214, 196, 160, 255))
    x = y = 8
    rowh = 0
    for name, im, sl in arts:
        if name in ('book-cover', 'book-page-l', 'book-page-r', 'book-shelf'):
            continue
        if x + im.width > 1190:
            x, y = 8, y + rowh + 8
            rowh = 0
        sheet.alpha_composite(im, (x, y))
        x += im.width + 8
        rowh = max(rowh, im.height)
    p = os.path.join(outdir, 'book_sheet.png')
    sheet.crop((0, 0, 1200, y + rowh + 8)).save(p)
    out.append(p)
    return out


def main():
    args = sys.argv[1:]
    if '--check' in args:
        sys.exit(check_uss())
    if '--preview' in args:
        for p in preview(args[args.index('--preview') + 1]):
            print(p)
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, im, sl in render_all():
        p = os.path.join(OUT_DIR, name + '.png')
        im.save(p, optimize=False)
        s = f'slice {",".join(str(v * SCALE) for v in sl)}' if sl else '原尺寸'
        print(f'{name:<22} {im.width:>3}×{im.height:<3} {s:<22} {md5(p)[:8]}')
    print(f'共 {len(BOOKS)} 張 → {OUT_DIR}')


if __name__ == '__main__':
    main()
