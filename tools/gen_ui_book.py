#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調配藥水面板（UI/BrewPanel.cs）的「魔法配方書」圖產生器＋離線預覽。

    python tools/gen_ui_book.py                 # 輸出 Assets/Resources/ui/skin8/book-*.png
    python tools/gen_ui_book.py --check         # 只比對 Skin8Book.uss 的九宮格數字跟這裡的常數
    python tools/gen_ui_book.py --preview DIR   # 照 Skin8Book.uss 的版面數字拼 mockup（不寫專案檔）

畫風、色盤、基元、×3 輸出全部沿用 tools/gen_ui_skin.py（import 進來用，**不改它**）：
  邏輯格一格一格點、1px 深棕紫外輪廓、光從左上來、NEAREST ×3 放大；九宮格的邊只在粗細方向有變化、中間單色。
  圖放在 skin8/ 底下 → PixelArtImporter 的例外把 PPU 設成 100（UI Toolkit 九宮格才不會 ×100），
  UiSkinImportGuard 也會自動修匯入競態（見那兩支的註解）。

── 書的組成（都在 Skin8Book.uss，由 BrewPanel 自己 styleSheets.Add）───────────────
  book-cover      皮革封面（九宮格 slice 10 格）：酒紅皮革＋金色燙線，四角是金色護角＋紫色小寶石
  book-page-l/r   左右書頁（九宮格）：外側與下緣是頁緣疊層、靠書脊那側是陰影漸層、書脊上緣微微下凹
  book-arrow-l/r  翻頁箭頭（固定尺寸，一般／滑過／按下）：紫布小鈕＋金色三角
  book-circle     成品底下的魔法陣（固定尺寸）
  book-moon／book-vine／book-star  書頁小裝飾（月亮＋星、藥草花邊、小星星）
  book-mark       絲帶書籤（固定尺寸，掛在書上緣）
  book-dot        下排目錄格的「做得出來」小綠寶石
  下排目錄格本身直接用 skin8 的 slot／slot-sel／slot-empty，底座用 hud-bar（不在這裡畫）。

結果是確定的：沒有亂數，重跑 md5 相同。
"""
import hashlib
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gen_ui_skin as S                 # noqa: E402  基元、色盤、輸出倍率（只讀，不改）
from gen_ui_skin import Px, OL, rrect, edge, lit_side, button_face, from_rows   # noqa: E402

OUT_DIR = S.OUT_DIR
USS_PATH = os.path.join(ROOT, 'Assets', 'Resources', 'ui', 'Skin8Book.uss')
SCALE = S.SCALE

# ═══════════════════════════════ 色盤補充 ═══════════════════════════════
# 封面用酒紅皮革（跟紫色標題緞帶、金色護角都分得開；暖色系跟木框同一家）。
BOOK_EXTRA = {
    'lt_hi': '#b4505c',
    'lt': '#8a3442',
    'lt_dk': '#66233a',
    'lt_dk2': '#45172b',
    'pu_hv': '#a985c0',      # 紫鈕滑過的高光
}
for k, v in BOOK_EXTRA.items():
    S.PAL.setdefault(k, v)


# ═══════════════════════════════ 封面 ═══════════════════════════════
# 邏輯 30×30、slice 13。外輪廓 1 ＋ 皮革 bevel 1 ＋ 皮革 1 ＋ 金燙線 1 ＋ 皮革 1 ＋ 暗皮革 1 ＋ 皮革。
# 書頁蓋在上面（Skin8Book.uss 的 .bk-book padding 上 21、左右 24、下 30 ＝ 7／8／10 格），
# 所以露出來的是外圈 7～10 格；四角的金色護角（x+y ≤ 12 的三角形）有一部分會被書頁壓住，像真的書一樣。

COVER_N, COVER_SLICE = 30, 13


def draw_cover():
    N = COVER_N
    px = Px(N, N)
    m = rrect(0, 0, N - 1, N - 1, 2)
    for x, y in m:
        d = min(x, y, N - 1 - x, N - 1 - y)
        lit = lit_side(x, y, N, N)
        if d == 0:
            c = OL
        elif d == 1:
            c = 'lt_hi' if lit else 'lt_dk'
        elif d == 3:
            c = 'go' if lit else 'go_dk'          # 金色燙線
        elif d == 5:
            c = 'lt_dk'                           # 燙線內側一圈暗皮革 → 書頁像是嵌進封面裡
        else:
            c = 'lt'
        px.put(x, y, c)
    for x, y in edge(m):
        px.put(x, y, OL)
    for x, y in ((1, 1), (N - 2, 1), (1, N - 2), (N - 2, N - 2)):
        px.put(x, y, OL)
    # 四角護角：以左上角畫一個，再鏡射到另外三角
    tri = {(x, y) for x in range(N) for y in range(N) if x + y <= 12} & m
    te = {(x, y) for x, y in tri if not {(x + 1, y), (x, y + 1)} <= tri or x == 0 or y == 0}
    corner = {}
    for x, y in tri:
        if (x, y) in te or (x, y) in ((1, 1),):
            c = OL
        elif x == 1 or y == 1:
            c = 'go_hi'
        elif x + y == 11:
            c = 'go_dk'
        elif x + y == 10:
            c = 'go_dk2' if (x + y) % 2 else 'go'
        else:
            c = 'go'
        corner[(x, y)] = c
    # 紫色小寶石（3×3 菱形）＋金托
    for (gx, gy), c in {(4, 3): 'pu_hi', (3, 4): 'pu_hi', (4, 4): 'pu', (5, 4): 'pu_dk', (4, 5): 'pu_dk',
                        (3, 3): 'go_dk2', (5, 3): 'go_dk2', (3, 5): 'go_dk2', (5, 5): 'go_dk2',
                        (4, 2): 'go_dk2', (2, 4): 'go_dk2', (6, 4): 'go_dk2', (4, 6): 'go_dk2'}.items():
        corner[(gx, gy)] = c
    corner[(4, 4)] = 'pu_hi'
    corner[(3, 4)] = 'pu'
    corner[(4, 3)] = 'wh'
    for (x, y), c in corner.items():
        for fx, fy in ((x, y), (N - 1 - x, y), (x, N - 1 - y), (N - 1 - x, N - 1 - y)):
            px.put(fx, fy, c)
    return px


# ═══════════════════════════════ 書頁 ═══════════════════════════════
# 左頁（右頁＝水平鏡射）。邏輯 18×16，slice：外側 4、書脊側 5、上 3、下 6。
#   外側（x=0 那邊）：頁緣疊層 3 條（深線／亮／中）；下緣：疊層 5 條（書底比較厚）——兩者在外下角斜接。
#   書脊側：4 格漸層陰影（紙往書脊彎下去），最裡面一格是深色摺線；上緣在書脊附近往下凹 1～2 格。
#   中間單色（pp），拉多大都不會出條紋。

PAGE_W, PAGE_H = 18, 16
PAGE_SLICE_L = (4, 3, 5, 6)      # 左、上、右、下（左頁）
PAGE_SLICE_R = (5, 3, 9, 9)      # 右頁鏡射＋右下摺角（右、下要 ≥ DOG+2）

STACK = ['pa_dk', 'pp_hi', 'pp_dk', 'pp_hi', 'pp_dk']     # 頁緣疊層：由外往內
SPINE = ['pa_dk', 'pp_dk', 'pp_bg', 'pp_alt']             # 書脊陰影：由書脊往外


def draw_page_l():
    W, H = PAGE_W, PAGE_H
    px = Px(W, H)
    for y in range(H):
        for x in range(W):
            d_out, d_bot, d_top, d_in = x, H - 1 - y, y, W - 1 - x
            # 書脊附近上緣下凹：d_in 0 → 從第 2 列開始、1～2 → 第 1 列
            top = 2 if d_in == 0 else (1 if d_in <= 2 else 0)
            if y < top:
                continue
            if (x, y) == (0, 0) or (x, y) == (0, H - 1):
                continue                                   # 外側兩角小圓角
            c_out = STACK[d_out] if d_out < 3 else None
            c_bot = STACK[d_bot] if d_bot < 5 else None
            if c_out and c_bot:
                c = c_out if d_out <= d_bot else c_bot
            elif c_bot:
                c = c_bot
            elif y == top:
                c = 'pa_dk'                                # 上緣
            elif c_out:
                c = c_out
            elif d_in < 4:
                c = SPINE[d_in]
            elif y == top + 1:
                c = 'pp_hi'                                # 上緣下一列受光
            else:
                c = 'pp'
            px.put(x, y, c)
    return px


def mirror(px):
    out = Px(px.w, px.h)
    for (x, y), c in px.p.items():
        out.put(px.w - 1 - x, y, c)
    return out


DOG = 7          # 右頁右下角的摺角大小（邏輯格）


def draw_page_r():
    """右頁＝左頁鏡射，再在右下角折一個小摺角（像被翻過很多次，也暗示「從這裡翻頁」）。
    摺角只在九宮格的右下角裡（右 slice 6、下 slice 6 ≥ DOG+1），拉伸不會變形。"""
    px = mirror(draw_page_l())
    W, H = px.w, px.h
    for y in range(H):
        for x in range(W):
            dx, dy = W - 1 - x, H - 1 - y
            if dx > DOG or dy > DOG:
                continue
            s = dx + dy
            if s < DOG:
                px.p.pop((x, y), None)                     # 角被折走了
            elif s == DOG or dx == DOG or dy == DOG:
                px.put(x, y, 'pa_dk')                      # 摺角的邊
            elif s == DOG + 1:
                px.put(x, y, 'pp_hi')                      # 摺痕受光
            else:
                px.put(x, y, 'pp_dk' if (dx == DOG - 1 or dy == DOG - 1) else 'pp_bg')   # 紙背（比正面暗）
    # 摺角底下落一點陰影（沿著摺痕外側那條斜線的上一格／左一格）
    for k in range(1, DOG):
        x, y = W - 1 - (DOG + 1) + k - 1, H - 1 - k
        if px.p.get((x, y)) == 'pp':
            px.put(x, y, 'pp_alt')
    return px


# ═══════════════════════════════ 翻頁箭頭 ═══════════════════════════════
# 邏輯 15×17（45×51）：紫布小鈕（跟標題緞帶同色）＋金色三角。按下時三角跟著臉往下沉 1 格。

ARROW_W, ARROW_H = 15, 17
PU_RAMP = ('pu_hi', 'pu', 'pu_dk', 'pu_dk2')
PU_HOVER = ('pu_hv', 'pu_hi', 'pu', 'pu_dk2')


def draw_arrow(side, state):
    ramp = PU_HOVER if state == 'h' else PU_RAMP
    px = button_face(ARROW_W, ARROW_H, ramp, state, r=2)
    oy = 1 if state == 'd' else 0
    cy = 7 + oy
    tri = []
    for i in range(5):                 # 尖端在 x=4（左箭頭），往右每欄高 2i+1
        x = 4 + i
        for y in range(cy - i, cy + i + 1):
            tri.append((x, y))
    if side == 'r':
        tri = [(ARROW_W - 1 - x, y) for x, y in tri]
    pts = set(tri)
    for x, y in tri:
        if (x, y + 1) not in pts:
            px.put(x, y + 1, 'pu_dk2')                     # 落影
    for x, y in tri:
        px.put(x, y, 'go_hi' if y < cy else ('go' if y == cy else 'go_dk'))
    # 尖端一格最亮
    tip = (4, cy) if side == 'l' else (ARROW_W - 5, cy)
    px.put(*tip, 'wh')
    return px


# ═══════════════════════════════ 魔法陣 ═══════════════════════════════
# 邏輯 52×52（156×156）。成品圖（144）疊在正中央。淡淡的印刷線條，不搶成品圖的戲。

CIRCLE_N = 52


def draw_circle():
    N = CIRCLE_N
    px = Px(N, N)
    c0 = (N - 1) / 2
    for y in range(N):
        for x in range(N):
            r = math.hypot(x - c0, y - c0)
            if r <= 19.6:
                px.put(x, y, 'pp_hi')                      # 內圈微亮（像被藥水照亮）
            elif 20.2 < r <= 21.2:
                px.put(x, y, 'pp_dk')
            elif 24.0 < r <= 25.1:
                px.put(x, y, 'pp_dk')
    # 兩圈之間的「符文點」：8 個方向
    for k in range(8):
        a = math.pi / 4 * k + math.pi / 8
        x = int(round(c0 + 22.6 * math.cos(a)))
        y = int(round(c0 + 22.6 * math.sin(a)))
        px.put(x, y, 'pa_dk')
        px.put(x + 1, y, 'pa_dk')
    # 四個正方位：外圈上的小金菱形
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        cx = int(round(c0 + 24.5 * dx))
        cy = int(round(c0 + 24.5 * dy))
        for ex, ey in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            px.put(cx + ex, cy + ey, 'go_dk')
        px.put(cx, cy, 'go_hi')
    return px


# ═══════════════════════════════ 小裝飾 ═══════════════════════════════

def draw_moon():
    """月亮＋一顆小星（13×13）：金色，像燙金印在紙上。"""
    return from_rows([
        '....oooo.....',
        '..oohhgo.....',
        '.ohhgoo......',
        '.ohgo.....s..',
        'ohgo.....sSs.',
        'ohgo......s..',
        'ohgo.........',
        'ohggo........',
        '.ohggoo....oo',
        '.oddggoooodo.',
        '..oodddddoo..',
        '....oooo.....',
        '.............',
    ], {'o': 'go_dk2', 'h': 'go_hi', 'g': 'go', 'd': 'go_dk', 's': 'go', 'S': 'go_hi'})


def draw_vine():
    """藥草花邊（27×11 → 81×33）：一枝彎彎的藥草，葉子上下交錯，尾端一朵小粉花。"""
    return from_rows([
        '...................ll......',
        '.........ll.......lLLl..pp.',
        '........lLLl.......lll.pPPp',
        '..ll.....ll...ss....s..pPPp',
        '.lLLl....s...s..s..s....pp.',
        '..lls...s...s....ss........',
        'sss..sss...s......s........',
        '.......ll.s.......lll......',
        '......lLLl.......lLLl......',
        '.......ll.........ll.......',
        '...........................',
    ], {'s': 'gr_dk', 'l': 'gr', 'L': 'gr_hi', 'p': 'pink', 'P': 'pk_hi'})


def draw_star():
    """小星星（5×5）。"""
    return from_rows([
        '..o..',
        '.oho.',
        'ohHgo',
        '.ogo.',
        '..o..',
    ], {'o': 'go_dk', 'h': 'go_hi', 'H': 'wh', 'g': 'go'})


def draw_dot():
    """下排目錄格「做得出來」的小綠寶石（5×5 → 15×15）。"""
    return from_rows([
        '.ooo.',
        'oHgdo',
        'oggdo',
        'oddko',
        '.ooo.',
    ], {'o': OL, 'H': 'gr_hi', 'g': 'gr', 'd': 'gr_dk', 'k': 'gr_dk2'})


def draw_mark():
    """絲帶書籤（8×32 → 24×96）：紫布＋金邊，上端 3 格塞在書裡（深色），下端剪成燕尾。"""
    W, H = 8, 32
    px = Px(W, H)
    body = set()
    for y in range(H):
        for x in range(1, W - 1):
            body.add((x, y))
    # 燕尾：最下面 4 列中間凹進去
    for y in range(H - 4, H):
        k = y - (H - 4)
        for x in range(1, W - 1):
            if abs(x - 3.5) < k * 0.9:
                body.discard((x, y))
    e = {(x, y) for x, y in body if not {(x + 1, y), (x - 1, y), (x, y + 1)} <= body}
    for x, y in body:
        if (x, y) in e:
            c = OL
        elif x == 2:
            c = 'pu_hi'
        elif x == W - 3:
            c = 'pu_dk'
        else:
            c = 'pu'
        px.put(x, y, c)
    for y in range(0, H):
        if (0, y) not in body:
            pass
    # 一顆金色小星吊飾
    for x, y, c in ((3, 20, 'go_hi'), (4, 20, 'go'), (3, 21, 'go'), (4, 21, 'go_dk')):
        px.put(x, y, c)
    return px


# ═══════════════════════════════ 清單 ═══════════════════════════════

def _books():
    out = [
        ('book-cover', draw_cover, (COVER_SLICE,) * 4),
        ('book-page-l', draw_page_l, PAGE_SLICE_L),
        ('book-page-r', draw_page_r, PAGE_SLICE_R),
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
    ]
    return out


BOOKS = _books()
SLICES = {name: sl for name, _, sl in BOOKS if sl is not None}


def render_all():
    return [(name, fn().image(), sl) for name, fn, sl in BOOKS]


def md5(p):
    with open(p, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def check_uss():
    """Skin8Book.uss 裡每個寫了 resource("ui/skin8/book-…") 又寫了 -unity-slice-* 的區塊，數字要等於 SLICES×3。"""
    if not os.path.exists(USS_PATH):
        print('找不到', USS_PATH)
        return 1
    src = re.sub(r'/\*.*?\*/', '', open(USS_PATH, encoding='utf-8').read(), flags=re.S)
    allslices = dict(S.SLICES)
    allslices.update(SLICES)
    bad = 0
    for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', src):
        for name in re.findall(r'resource\("ui/skin8/([\w-]+)"\)', body):
            if not os.path.exists(os.path.join(OUT_DIR, name + '.png')):
                print(f'✗ {sel.strip()}：skin8/{name}.png 不存在')
                bad += 1
                continue
            if name not in allslices:
                continue
            want = dict(zip(('left', 'top', 'right', 'bottom'), (v * SCALE for v in allslices[name])))
            for side, v in re.findall(r'-unity-slice-(left|top|right|bottom)\s*:\s*(\d+)', body):
                if int(v) != want[side]:
                    print(f'✗ {sel.strip()}：{name} 的 slice-{side} 寫 {v}，應該是 {want[side]}')
                    bad += 1
    print('Skin8Book.uss 九宮格數字檢查：', '全部一致' if bad == 0 else f'{bad} 處不一致')
    return 1 if bad else 0


# ═══════════════════════════════ 離線預覽 ═══════════════════════════════
# ⚠️ 下面的數字**必須跟 Skin8Book.uss 一致**（每個常數旁註明對應的規則）。改 uss 就要改這裡。

BOOK_W, BOOK_H = 840, 420              # .bk-book width/height
BOOK_PAD = (21, 24, 30, 24)            # .bk-book padding（上 右 下 左）
PG_W, PG_H = 396, 369                  # .bk-page width/height（＝ (840-48)/2、420-51）
PG_PAD_OUT, PG_PAD_IN, PG_PAD_T, PG_PAD_B = 36, 30, 21, 21     # .bk-leaf--l/--r padding
TITLE_TOP = -15                        # .bk-title top
CLOSE_POS = (-12, -12)                 # .bk-close right/top
ARROW_W_PX, ARROW_H_PX, ARROW_OUT, ARROW_TOP = 45, 51, -27, 183   # .bk-arrow（left/right -27、top 183）
MARK_LEFT, MARK_TOP = 78, -9           # .bk-mark（left 78、top -9）
HERO_CIRCLE, HERO_ICON = 156, 144      # .bk-hero / .bk-hero-icon
NAME_SIZE, NAME_H = 24, 36             # .bk-name
DESC_SIZE, DESC_W, DESC_LH = 14, 294, 21       # .bk-desc（最多兩行）
PRICE_SIZE, PRICE_H = 20, 30           # .bk-price .bk-price-num
TILE_W, TILE_H, TILE_ICON, TILE_NUM = 90, 108, 48, 20   # .bk-mat
PLUS_W = 24                            # .bk-plus
HEAD_H = 36                            # .bk-head（小標「材料」高 27 ＋ margin-bottom 9）
CAN_ICON, CAN_SIZE = 24, 20            # .bk-can
BTN_W_PX, BTN_H_PX, BTN_GAP, BTN_FONT = 108, 42, 12, 17   # .bk-brew
SHELF_MT, SHELF_PAD_Y, SHELF_PAD_X = 9, 9, 12     # .bk-shelf
SLOT, SLOT_GAP, SLOT_ICON, SLOT_LIFT = 60, 3, 48, 6   # .bk-slot
FOOT_MT, FOOT_H = 6, 27                # .bk-foot

FOOT_INK = (236, 222, 196)             # .bk-foot-text 顏色（暗幕上用淺字）

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
    '星光藥劑': '星鈴花與藍莓調的夜空色藥劑，瓶底沉著會亮的細砂。',
}
HAVE = {'藍莓': 5, '藥草': 3, '漿果': 4, '黑莓': 0, '落葉': 7, '樹枝': 6, '金蘋果': 1, '木材': 9, '星鈴花': 1}


def preview(outdir):
    from PIL import Image
    import preview_ui_skin as P
    os.makedirs(outdir, exist_ok=True)
    for name, im, sl in render_all():
        P.SKIN[name] = im
        if sl:
            P.SLICE_PX[name] = tuple(v * SCALE for v in sl)

    INK, SOFT, GOLD, GREEN, RED, CREAM = P.INK, P.INK_SOFT, P.GOLD_INK, P.GREEN_INK, P.RED_INK, P.CREAM

    def maxc(inputs):
        return min(10, min(HAVE.get(m, 0) // n for m, n in inputs))

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

    def draw_left(c, x, y, idx):
        name, price, inputs = RECIPES[idx]
        c.img('book-star', x + PG_W - 30 - 33, y + 36)          # .bk-star--a（right 30+18、top 36）
        c.img('book-star', x + 45, y + 177)                     # .bk-star--b（left 45、top 177）
        c.img('book-star', x + PG_W - 72, y + 216)              # .bk-star--c（right 57、top 216）
        cx0 = x + PG_PAD_OUT
        cw = PG_W - PG_PAD_OUT - PG_PAD_IN
        # 欄：hero 156 / name 36 / desc 42 / price 30，整欄垂直置中（justify-content: center）；頁碼絕對定位
        col_h = HERO_CIRCLE + NAME_H + DESC_LH * 2 + 6 + PRICE_H
        inner_h = PG_H - PG_PAD_T - PG_PAD_B
        top = y + PG_PAD_T + (inner_h - col_h) / 2
        hx = cx0 + (cw - HERO_CIRCLE) / 2
        c.img('book-circle', hx, top)
        c.img(P.item(name), hx + 6, top + 6, HERO_ICON, HERO_ICON)
        ty = top + HERO_CIRCLE
        c.text(cx0, ty, name, NAME_SIZE, INK, bold=True, w=cw, h=NAME_H, align='c')
        ty += NAME_H
        lines = wrap(c, DESC.get(name, '一瓶用心熬出來的好東西。'), DESC_SIZE, DESC_W)[:2]
        for k, ln in enumerate(lines):
            c.text(cx0, ty + k * DESC_LH, ln, DESC_SIZE, SOFT, w=cw, h=DESC_LH, align='c')
        ty += DESC_LH * 2 + 6
        mw = 24 + c.tw(str(price), PRICE_SIZE, True)
        c.img('coin', cx0 + (cw - mw) / 2, ty + (PRICE_H - 21) / 2)
        c.text(cx0 + (cw - mw) / 2 + 24, ty, str(price), PRICE_SIZE, GOLD, bold=True, h=PRICE_H)
        # 頁碼：.bk-pageno 絕對定位 bottom 15、整頁寬置中、13px
        s = f'{idx + 1} / {len(RECIPES)}'
        c.text(x, y + PG_H - 15 - 21, s, 13, SOFT, w=PG_W, h=21, align='c')

    def draw_right(c, x, y, idx, hover_btn=None, tip_mat=None):
        name, price, inputs = RECIPES[idx]
        c.img('book-moon', x + PG_W - 21 - 39, y + 18)               # .bk-moon right 21 top 18
        c.img('book-vine', x + PG_W - 42 - 81, y + PG_H - 27 - 33)   # .bk-vine right 42 bottom 27
        cx0 = x + PG_PAD_IN
        cw = PG_W - PG_PAD_OUT - PG_PAD_IN
        mx = maxc(inputs)
        col_h = HEAD_H + TILE_H + 21 + 30 + 18 + BTN_H_PX
        inner_h = PG_H - PG_PAD_T - PG_PAD_B
        top = y + PG_PAD_T + (inner_h - col_h) / 2
        # 小標：[星] 材料 [星]（.bk-head：高 36、字 15 粗、次要墨色）
        hw = c.tw('材料', 15, True)
        hx = cx0 + (cw - hw) / 2
        c.text(hx, top, '材料', 15, SOFT, bold=True, h=27)
        c.img('book-star', hx - 9 - 15, top + 6)
        c.img('book-star', hx + hw + 9, top + 6)
        top += HEAD_H
        n = len(inputs)
        row_w = n * TILE_W + (n - 1) * PLUS_W
        tx = cx0 + (cw - row_w) / 2
        tip = None
        for i, (m, need) in enumerate(inputs):
            have = HAVE.get(m, 0)
            ok = have >= need
            c.nine('chip' if ok else 'chip-short', tx, top, TILE_W, TILE_H)
            c.img(P.item(m), tx + (TILE_W - TILE_ICON) / 2, top + 15, TILE_ICON, TILE_ICON)
            c.text(tx, top + 15 + 48 + 3, f'{have}/{need}', TILE_NUM, GREEN if ok else RED, bold=True,
                   w=TILE_W, h=30, align='c')
            if m == tip_mat:
                tip = (tx + TILE_W / 2, top + TILE_H + 3, f'{m}　有 {have}／要 {need}')
            tx += TILE_W
            if i < n - 1:
                c.text(tx, top, '+', 22, SOFT, bold=True, w=PLUS_W, h=TILE_H, align='c')
                tx += PLUS_W
        cy = top + TILE_H + 21
        s = f'×{mx}'
        w = CAN_ICON + 3 + c.tw(s, CAN_SIZE, True)
        sx = cx0 + (cw - w) / 2
        c.img(P.item(name), sx, cy + 3, CAN_ICON, CAN_ICON)
        c.text(sx + CAN_ICON + 3, cy, s, CAN_SIZE, GREEN if mx else RED, bold=True, h=30)
        by = cy + 30 + 18
        bx = cx0 + (cw - (BTN_W_PX * 2 + BTN_GAP)) / 2
        ok = mx >= 1

        def btn(x0, label, kind):
            st = 'n' if ok else 'x'
            nm = {'n': f'btn-{kind}', 'x': 'btn-off'}[st]
            c.nine(nm, x0, by, BTN_W_PX, BTN_H_PX)
            if not ok:
                col, sh = (244, 238, 226), (1, (143, 132, 116))
            elif kind == 'gold':
                col, sh = INK, (1, (255, 240, 190))
            else:
                col, sh = CREAM, (1, P.OUTLINE)
            c.text(x0, by, label, BTN_FONT, col, bold=True, shadow=sh, w=BTN_W_PX, h=BTN_H_PX - 3, align='c')

        btn(bx, '熬 1', 'green')
        btn(bx + BTN_W_PX + BTN_GAP, f'熬 {mx}' if mx else '熬最大', 'gold')
        return tip

    def mock(idx, fname, hover_slot=None, tip_mat=None, fold=None, arrow_hover=None):
        c = P.Canvas(bg=P.background())
        P.dim(c)
        total_h = -TITLE_TOP + BOOK_H + SHELF_MT + (SHELF_PAD_Y * 2 + SLOT) + FOOT_MT + FOOT_H
        bx = (P.SCREEN_W - BOOK_W) // 2
        by = (P.SCREEN_H - total_h) // 2 - TITLE_TOP
        # 書：封面 → 書頁（底下的空白頁＋上面的葉子）
        c.nine('book-cover', bx, by, BOOK_W, BOOK_H)
        lx, py = bx + BOOK_PAD[3], by + BOOK_PAD[0]
        rx = lx + PG_W
        c.nine('book-page-l', lx, py, PG_W, PG_H)
        c.nine('book-page-r', rx, py, PG_W, PG_H)
        if fold is None:
            draw_left(c, lx, py, idx)
        tip = None
        if fold is None:
            tip = draw_right(c, rx, py, idx, tip_mat=tip_mat)
        else:
            # 翻頁中段示意：右頁葉子壓扁到 fold 比例（以書脊為軸），左頁還是舊的
            draw_left(c, lx, py, idx)
            leaf = P.Canvas(PG_W, PG_H)
            leaf.im = Image.new('RGBA', (PG_W, PG_H), (0, 0, 0, 0))
            from PIL import ImageDraw
            leaf.d = ImageDraw.Draw(leaf.im)
            leaf.nine('book-page-r', 0, 0, PG_W, PG_H)
            draw_right(leaf, 0, 0, idx)
            from PIL import ImageChops
            tint = Image.new('RGBA', leaf.im.size, (225, 210, 185, 255))      # .bk-leaf--fold 的 tint
            leaf.im = ImageChops.multiply(leaf.im, tint)
            w = max(1, int(PG_W * fold))
            c.img(leaf.im.resize((w, PG_H), Image.NEAREST), rx, py)
        # 書籤、標題、關閉、箭頭
        c.img('book-mark', bx + MARK_LEFT, by + MARK_TOP)
        title = '調配藥水'
        tw = c.tw(title, 21, True)
        rw = max(150, 36 + tw + 36)
        rxx = bx + (BOOK_W - rw) / 2
        ryy = by + TITLE_TOP
        c.nine('ribbon', rxx, ryy, rw, 51)
        c.text(rxx, ryy, title, 21, CREAM, bold=True, shadow=(2, P.OUTLINE), w=rw, h=51 - 6, align='c')
        c.img('close', bx + BOOK_W - 36 - CLOSE_POS[0], by + CLOSE_POS[1])
        ay = by + ARROW_TOP
        c.img('book-arrow-l-hover' if arrow_hover == 'l' else 'book-arrow-l', bx + ARROW_OUT, ay)
        c.img('book-arrow-r-hover' if arrow_hover == 'r' else 'book-arrow-r', bx + BOOK_W - ARROW_OUT - ARROW_W_PX, ay)
        # 下排目錄格
        sy = by + BOOK_H + SHELF_MT
        sh_h = SHELF_PAD_Y * 2 + SLOT
        c.nine('hud-bar', bx, sy, BOOK_W, sh_h)
        sx = bx + SHELF_PAD_X
        for i, (name, price, inputs) in enumerate(RECIPES):
            can = maxc(inputs) >= 1
            sel = i == idx
            yy = sy + SHELF_PAD_Y - (SLOT_LIFT if sel else 0) - (3 if hover_slot == i and not sel else 0)
            kind = 'slot-sel' if sel else ('slot' if can else 'slot-empty')
            c.nine(kind, sx, yy, SLOT, SLOT)
            c.img(P.item(name), sx + 6, yy + 6, SLOT_ICON, SLOT_ICON, alpha=1.0 if (can or sel) else 0.55)
            if can:
                c.img('book-dot', sx + SLOT - 15 + 3, yy - 3)
            sx += SLOT + SLOT_GAP
        # 底部：[Esc] 關閉　[←][→] 翻頁（置中，暗幕上用淺色字）
        fy = sy + sh_h + FOOT_MT
        parts = [('key', 'Esc'), ('txt', '關閉'), ('gap', 18), ('key', '←'), ('key', '→'), ('txt', '翻頁')]
        tot = 0
        for k, v in parts:
            tot += (max(36, 12 + c.tw(v, 12, True)) + 3) if k == 'key' else (c.tw(v, 14) + 3 if k == 'txt' else v)
        fx = bx + (BOOK_W - tot) / 2
        for k, v in parts:
            if k == 'key':
                kw = max(36, 12 + c.tw(v, 12, True))
                c.nine('keycap', fx, fy, kw, 27)
                c.text(fx, fy, v, 12, INK, bold=True, w=kw, h=24, align='c')
                fx += kw + 3
            elif k == 'txt':
                c.text(fx, fy, v, 14, FOOT_INK, shadow=(1, P.OUTLINE), h=27)
                fx += c.tw(v, 14) + 3
            else:
                fx += v
        if tip:
            tx, ty, s = tip
            tw_ = 10 + c.tw(s, 14) + 10
            c.nine('badge', tx - tw_ / 2, ty, tw_, 31)
            c.text(tx - tw_ / 2, ty + 4, s, 14, CREAM, w=tw_, h=21, align='c')
        p = os.path.join(outdir, fname)
        c.im.save(p)
        return c, p

    out = []
    c, p = mock(0, 'book_ok.png', arrow_hover='r')
    out.append(p)
    big = c.im.resize((int(P.SCREEN_W * 1.125), int(P.SCREEN_H * 1.125)), Image.NEAREST)
    p = os.path.join(outdir, 'book_ok_720p.png')
    big.save(p)
    out.append(p)
    out.append(mock(2, 'book_short.png', tip_mat='黑莓', hover_slot=5)[1])
    out.append(mock(7, 'book_broom.png')[1])
    out.append(mock(12, 'book_long_desc.png')[1])
    out.append(mock(0, 'book_flip.png', fold=0.45)[1])
    # 圖檔總覽
    arts = render_all()
    sheet = Image.new('RGBA', (1000, 560), (239, 220, 178, 255))
    x = y = 10
    rowh = 0
    for name, im, sl in arts:
        k = 2 if im.width <= 60 else 1
        big = im.resize((im.width * k, im.height * k), Image.NEAREST)
        if x + big.width > 990:
            x, y = 10, y + rowh + 10
            rowh = 0
        sheet.alpha_composite(big, (x, y))
        x += big.width + 12
        rowh = max(rowh, big.height)
    p = os.path.join(outdir, 'book_sheet.png')
    sheet.save(p)
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
        s = f'slice {",".join(str(v * SCALE) for v in sl)}' if sl else '固定尺寸'
        print(f'{name:<22} {im.width:>3}×{im.height:<3} {s:<22} {md5(p)[:8]}')
    print(f'共 {len(BOOKS)} 張 → {OUT_DIR}')


if __name__ == '__main__':
    main()
