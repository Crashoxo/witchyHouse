#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UI 外觀（skin8）的離線預覽：用 Pillow 把九宮格圖照 Skin8.uss 的尺寸拼出幾個面板的示意圖。

    python tools/preview_ui_skin.py OUTDIR

⚠️ 為什麼要有這支：UI Toolkit 沒辦法離線渲染（要開 Unity），而 Unity 開著專案又是鎖住的。
   不先拼出來看，就只能「寫 uss → 開遊戲 → 截圖 → 改」一輪一輪試。

⚠️ 這裡的版面數字**必須跟 Assets/Resources/ui/Skin8.uss（＋面板原本的 ShopManageStyle／BagPanelStyle 欄寬）一致**——
   下面每個常數旁邊都註明它對應 uss 的哪一條。改 uss 就要改這裡，不然預覽會騙人。
   這不是排版引擎：只照「flex 橫排、置中對齊、固定欄寬＋一個 flex-grow 欄」手算座標，夠用來看比例、配色與節奏。

輸出（都是參考解析度 1:1，也就是 UIPanelSettings 的高 640；16:9 時邏輯寬 1138）：
  mock_brew.png          製作清單（BrewPanel）
  mock_brew_720p.png     同一張用 ×1.125 最近鄰放大（720p 的實際縮放）→ 看像素粗細不均的程度
  mock_shop_stock.png    經營商店：上架定價
  mock_shop_upgrade.png  經營商店：升級
  mock_bag.png           倉庫模式的背包面板
  mock_town.png          花店（種子分頁）
  mock_hud.png           下排背包 HUD 格子
  mock_overview.png      以上縮小拼一張
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_ui_skin as S          # noqa: E402
from gen_item_art import ITEMS   # noqa: E402

RES = os.path.join(ROOT, 'Assets', 'Resources')
FONT_FULL = os.path.join(HERE, 'fonts', 'NotoSansTC-full.ttf')         # 可變字型：用 wght 軸挑字重
FONT_SUB = os.path.join(RES, 'ui', 'fonts', 'NotoSansTC.ttf')          # 遊戲裡實際那份（已定在 400）

SCREEN_W, SCREEN_H = 1138, 640     # 參考高 640、16:9

# ── 色（＝ Skin8.uss 的文字色）──
INK = (74, 47, 37)
INK_SOFT = (122, 90, 68)
INK_HEAD = (150, 116, 84)
INK_DIM = (176, 160, 138)
GOLD_INK = (146, 94, 16)
GREEN_INK = (63, 122, 44)
GREEN_SOFT = (63, 110, 44)
RED_INK = (179, 38, 58)
CREAM = (255, 248, 230)
GOLD_CREAM = (255, 226, 140)
OUTLINE = (42, 27, 36)

_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        if os.path.exists(FONT_FULL):
            f = ImageFont.truetype(FONT_FULL, size)
            # Unity 的 -unity-font-style: bold 是假粗體（在 400 上描粗）；這裡用 700 近似
            f.set_variation_by_axes([700 if bold else 400])
        else:
            f = ImageFont.truetype(FONT_SUB, size)
        _fonts[key] = f
    return _fonts[key]


SKIN = {name: im for name, im, _ in S.render_all()}
# 另一支產生器的圖示（96×96），Skin8.uss 顯示成 24×24
for _n in ('lock', 'st_ok', 'arrow'):
    _p = os.path.join(RES, 'ui', 'icons8', _n + '.png')
    if os.path.exists(_p):
        SKIN['i8-' + _n] = Image.open(_p).convert('RGBA').resize((24, 24), Image.NEAREST)
SLICE_PX = {name: tuple(v * S.SCALE for v in sl) for name, sl in S.SLICES.items()}
ITEM_FILE = {name: fname for name, fname, _ in ITEMS}


def item(name):
    p = os.path.join(RES, 'items8', ITEM_FILE[name] + '.png')
    return Image.open(p).convert('RGBA')


def nine(name, w, h):
    """照 Unity 的 9-slice：四角原尺寸、邊沿單一方向拉長、中間拉滿；-unity-slice-scale 1px。"""
    im = SKIN[name]
    l, t, r, b = SLICE_PX[name]
    W, H = im.size
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    xs = [(0, l, 0, l), (l, W - r, l, w - r), (W - r, W, w - r, w)]
    ys = [(0, t, 0, t), (t, H - b, t, h - b), (H - b, H, h - b, h)]
    for sx0, sx1, dx0, dx1 in xs:
        for sy0, sy1, dy0, dy1 in ys:
            if sx1 <= sx0 or sy1 <= sy0 or dx1 <= dx0 or dy1 <= dy0:
                continue
            piece = im.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.NEAREST)
            out.alpha_composite(piece, (dx0, dy0))
    return out


class Canvas:
    def __init__(self, w=SCREEN_W, h=SCREEN_H, bg=None):
        self.im = Image.new('RGBA', (w, h), (30, 24, 30, 255))
        if bg is not None:
            self.im.alpha_composite(bg)
        self.d = ImageDraw.Draw(self.im)

    def nine(self, name, x, y, w, h):
        self.im.alpha_composite(nine(name, int(w), int(h)), (int(x), int(y)))

    def img(self, im, x, y, w=None, h=None, alpha=1.0):
        if isinstance(im, str):
            im = SKIN[im]
        if w is not None:
            im = im.resize((int(w), int(h)), Image.NEAREST)
        if alpha < 1.0:
            im = im.copy()
            a = im.getchannel('A').point(lambda v: int(v * alpha))
            im.putalpha(a)
        self.im.alpha_composite(im, (int(x), int(y)))

    def tw(self, s, size, bold=False):
        return self.d.textlength(s, font=font(size, bold))

    def text(self, x, y, s, size, color, bold=False, shadow=None, align='l', w=0, h=0):
        """在 (x, y, w, h) 的框裡畫字：垂直置中；align 是水平對齊（l／c／r）。shadow＝(dy, 色)。"""
        f = font(size, bold)
        tw = self.d.textlength(s, font=f)
        asc, desc = f.getmetrics()
        th = asc + desc
        tx = x if align == 'l' else (x + (w - tw) / 2 if align == 'c' else x + w - tw)
        ty = y + (h - th) / 2 if h else y
        if shadow:
            self.d.text((tx, ty + shadow[0]), s, font=f, fill=shadow[1])
        self.d.text((tx, ty), s, font=f, fill=color)
        return tw


# ═══════════════════════════════ 共用零件（數字＝ Skin8.uss）═══════════════════════════════

def background():
    """遊戲畫面當底（魔女房間）＋ .dim 的 rgba(0,0,0,0.59) 暗幕。"""
    p = os.path.join(RES, 'rooms', 'brew', 'shell-day.png')
    bg = Image.new('RGBA', (SCREEN_W, SCREEN_H), (60, 50, 44, 255))
    if os.path.exists(p):
        room = Image.open(p).convert('RGBA')
        k = SCREEN_W / room.width
        room = room.resize((SCREEN_W, int(room.height * k)), Image.NEAREST)
        bg.alpha_composite(room, (0, (SCREEN_H - room.height) // 2))
    return bg


def dim(c):
    c.im.alpha_composite(Image.new('RGBA', c.im.size, (0, 0, 0, int(255 * 0.59))))


PANEL_PAD = (30, 30, 24, 30)        # .sk .panel padding: 30 30 24 30（上 右 下 左）
HEADER_MT, HEADER_H, HEADER_MB = -40, 36, 9   # .sk .header
MAX_H = int(SCREEN_H * 0.88)        # .panel max-height: 88%


def panel_frame(c, x, y, w, h, title, gold=None, cap=None):
    """面板框＋標題緞帶＋右上角（金幣袋／容量膠囊、關閉鈕）。回傳內容區的 (x, y, w)。"""
    c.nine('panel', x, y, w, h)
    pt, pr, pb, pl = PANEL_PAD
    cx, cw = x + pl, w - pl - pr
    hy = y + pt + HEADER_MT                    # header 的上緣
    # 關閉鈕：36×36、margin-right -21 → 右緣在 內容右緣 + 21
    close_x = cx + cw + 21 - 36
    c.img('close', close_x, hy + (HEADER_H - 36) / 2)
    right = close_x - 6                         # .sk .close margin-left 6
    # 金幣袋：.sk .gold-box  高 30、padding 0 12 0 6、margin-right 6；[金幣 21][3][數字 18 粗]
    if gold is not None:
        s = str(gold)
        bw = 6 + 21 + 3 + c.tw(s, 18, True) + 12
        bx = right - 6 - bw
        by = hy + (HEADER_H - 30) / 2
        c.nine('badge', bx, by, bw, 30)
        c.img('coin', bx + 6, by + (30 - 21) / 2)
        c.text(bx + 6 + 21 + 3, by, s, 18, GOLD_CREAM, bold=True, h=30)
        right = bx
    if cap is not None:                          # .sk .cap：高 30、padding 0 12、字 15 米白
        bw = 12 + c.tw(cap, 15) + 12
        bx = right - 6 - bw
        by = hy + (HEADER_H - 30) / 2
        c.nine('badge', bx, by, bw, 30)
        c.text(bx, by, cap, 15, CREAM, w=bw, h=30, align='c')
    # 標題緞帶：.sk .title  絕對定位、left 50% translate -50%、top -9、高 51、padding 0 36 6 36、字 21 粗
    tw = c.tw(title, 21, True)
    rw = max(150, 36 + tw + 36)
    rx = x + pl + (cw - rw) / 2
    ry = hy - 9
    c.nine('ribbon', rx, ry, rw, 51)
    c.text(rx, ry, title, 21, CREAM, bold=True, shadow=(2, OUTLINE), w=rw, h=51 - 6, align='c')
    content_y = y + pt + HEADER_MT + HEADER_H + HEADER_MB
    return cx, content_y, cw


def tabs(c, x, y, w, labels, active):
    """.sk .tabs：高 39（含 3px 底線）＋ margin-bottom 9；.tab flex-grow 1、margin-right 6；
    沒選 33 高（6..39）、選中 36 高（3..39）。"""
    c.d.rectangle([x, y + 36, x + w - 1, y + 38], fill=(112, 63, 41))
    inner_x, inner_w = x + 6, w - 12            # .sk .tabs padding 0 6
    n = len(labels)
    tw = (inner_w - 6 * n) / n
    for i, lab in enumerate(labels):
        tx = inner_x + i * (tw + 6)
        on = i == active
        hgt = 36 if on else 33
        ty = y + 39 - hgt
        c.nine('tab-on' if on else 'tab', tx, ty, tw, hgt)
        c.text(tx, ty, lab, 17 if on else 16, INK if on else INK_SOFT, bold=on, w=tw, h=hgt - 3, align='c')
    return y + 39 + 9


def footer(c, x, y, w, keys, action, info='', extra_keys=()):
    """UiSkin.Footer：分隔線（15 高、margin-top 3）＋ 30 高的一列 [鍵帽][短字] … [資訊]。回傳底列下緣 y。"""
    c.nine('divider', x, y + 3, w, 15)
    fy = y + 18
    kx = x
    for k in keys:                               # .sk .sk-key：min-width 36、高 27、padding 0 6 3 6、字 12 粗
        kw = max(36, 6 + c.tw(k, 12, True) + 6)
        c.nine('keycap', kx, fy + 1.5, kw, 27)
        c.text(kx, fy + 1.5, k, 12, INK, bold=True, w=kw, h=24, align='c')
        kx += kw + 3
    c.text(kx + 3, fy, action, 14, INK_SOFT, h=30)
    ix = x + w
    if info:
        ix -= c.tw(info, 14)
        c.text(ix, fy, info, 14, INK_SOFT, h=30)
    for k in extra_keys:
        kw = max(36, 6 + c.tw(k, 12, True) + 6)
        ix -= kw + 3
        c.nine('keycap', ix, fy + 1.5, kw, 27)
        c.text(ix, fy + 1.5, k, 12, INK, bold=True, w=kw, h=24, align='c')
    return fy + 30


def scrollbar(c, x, y, h, frac_top, frac_len):
    """.sk .unity-scroller--vertical：寬 15、margin-left 6；軌道九宮格、把手九宮格（min-height 36）。"""
    c.nine('scroll-track', x, y, 15, h)
    th = max(36, int(h * frac_len))
    c.nine('scroll-thumb', x, y + int((h - th) * frac_top), 15, th)


def money(c, x, y, h, n, size=17, color=GOLD_INK):
    """UiSkin.Money：[金幣 21][margin 3][數字 17 粗]，垂直置中。回傳寬。"""
    c.img('coin', x, y + (h - 21) / 2)
    tw = c.text(x + 24, y, str(n), size, color, bold=True, h=h)
    return 24 + tw


def money_w(c, n, size=17):
    return 24 + c.tw(str(n), size, True)


def button(c, x, y, w, label, kind='wood', state='n', h=36, dark_text=None):
    """.sk .btn：高 36、padding 0 9 3 9、字 15 粗米白＋落影；金色鈕用深色字。"""
    name = {'n': f'btn-{kind}', 'h': f'btn-{kind}-hover', 'd': f'btn-{kind}-down', 'x': 'btn-off'}[state]
    c.nine(name, x, y, w, h)
    if label:
        dark = (kind == 'gold') if dark_text is None else dark_text
        if state == 'x':
            col, sh = (244, 238, 226), (1, (143, 132, 116))
        elif dark:
            col, sh = INK, (1, (255, 240, 190))
        else:
            col, sh = CREAM, (1, OUTLINE)
        oy = 3 if state == 'd' else 0
        c.text(x, y + oy, label, 15, col, bold=True, shadow=sh, w=w, h=h - 3, align='c')


def row_card(c, x, y, w, h=57, kind='row'):
    """.sk .row：高 57（卡面 54＋落影 3）、margin-bottom 3、padding 0 12 3 9。回傳 (內容 x, 內容中線 y, 內容右緣)。"""
    c.nine(kind, x, y, w, h)
    return x + 9, y + (h - 3) / 2, x + w - 12


def badge(c, x, cy, s, size=14, minw=27, h=24):
    """.sk .sk-badge：min-width 27、高 24、padding 0 7、字 14 粗米白。回傳寬。"""
    bw = max(minw, 7 + c.tw(s, size, True) + 7)
    c.nine('badge', x, cy - h / 2, bw, h)
    c.text(x, cy - h / 2, s, size, CREAM, bold=True, w=bw, h=h, align='c')
    return bw


# ═══════════════════════════════ 製作清單 ═══════════════════════════════
# 一列：[成品 48 + 9] [名稱 108] [材料小卡 flex-grow] [價格 66] [熬 1：btn-list 72] [熬 N：btn-buy 88]（按鈕 margin-left 6）

RECIPES = [   # (名稱, 售價, [(材料, 需要)])  ＝ Data/Recipes.cs
    ('清涼藥水', 35, [('藍莓', 2), ('藥草', 1)]),
    ('戀愛藥水', 40, [('漿果', 2), ('黑莓', 1)]),
    ('暗影藥水', 42, [('落葉', 3), ('黑莓', 1)]),
    ('烈焰藥水', 45, [('藥草', 2), ('樹枝', 2)]),
    ('溫暖熱可可', 30, [('金蘋果', 1), ('漿果', 2)]),
    ('蜂蜜藥劑', 55, [('金蘋果', 2), ('藥草', 1)]),
    ('黃金藥劑', 70, [('金蘋果', 2), ('藍莓', 2)]),
    ('夜影掃帚', 120, [('木材', 3), ('樹枝', 2), ('黑莓', 1)]),
    ('星光掃帚', 140, [('木材', 3), ('樹枝', 2), ('藍莓', 2)]),
]
HAVE = {'藍莓': 5, '藥草': 3, '漿果': 4, '黑莓': 0, '落葉': 7, '樹枝': 6, '金蘋果': 1, '木材': 9}


def chip(c, x, cy, mat, need):
    """.sk .sk-chip：高 33、padding 0 7 0 3、margin-right 6；[材料 24][3][持有/需要 15 粗]。回傳寬（不含 margin）。"""
    have = HAVE.get(mat, 0)
    ok = have >= need
    s = f'{have}/{need}'
    w = 3 + 24 + 3 + c.tw(s, 15, True) + 7
    c.nine('chip' if ok else 'chip-short', x, cy - 16.5, w, 33)
    c.img(item(mat), x + 3, cy - 12, 24, 24)
    c.text(x + 30, cy - 16.5, s, 15, GREEN_INK if ok else RED_INK, bold=True, h=33)
    return w


def mock_brew(outdir):
    c = Canvas(bg=background())
    dim(c)
    W = 760                                       # .panel width 760（ShopManageStyle）
    H = MAX_H
    x, y = (SCREEN_W - W) // 2, (SCREEN_H - H) // 2
    cx, cy, cw = panel_frame(c, x, y, W, H, '調配藥水')
    foot_h = 18 + 30
    rows_h = (y + H - PANEL_PAD[2]) - foot_h - cy
    list_w = cw - 21                              # 捲軸 15 ＋ margin-left 6
    scrollbar(c, cx + cw - 15, cy, rows_h, 0.0, rows_h / (len(RECIPES) * 60 + 4 * 60))
    clip = Canvas(list_w, rows_h)
    clip.im = Image.new('RGBA', (list_w, rows_h), (0, 0, 0, 0))
    clip.d = ImageDraw.Draw(clip.im)
    ry = 0
    tip_at = None
    for i, (name, price, inputs) in enumerate(RECIPES):
        mx = min(HAVE.get(m, 0) // n for m, n in inputs)
        off = mx < 1
        kind = 'row-alt' if i % 2 else 'row'       # 做不出來的列不換卡（實機回饋：整列淡掉看不清楚）
        if i == 3:
            kind = 'row-hover'
        x0, mid, xr = row_card(clip, 0, ry, list_w, 57, kind)
        clip.img(item(name), x0, mid - 24, 48, 48, alpha=0.7 if off else 1.0)   # .sk .sk-off .brew-icon opacity .7
        clip.text(x0 + 57, mid - 15, name, 17, INK, bold=True, h=30)
        # 右邊固定欄，由右往左排
        bx = xr - 88
        button(clip, bx, mid - 18, 88, f'熬 {mx}' if mx > 0 else '熬最大', 'gold', 'n' if not off else 'x')
        bx -= 6 + 72
        button(clip, bx, mid - 18, 72, '熬 1', 'green', 'n' if not off else 'x')
        px = bx - 6 - 66
        mw = money_w(clip, price)
        money(clip, px + (66 - mw) / 2, mid - 15, 30, price)
        # 材料小卡
        chx = x0 + 57 + 108
        for m, n in inputs:
            w = chip(clip, chx, mid, m, n)
            if i == 2 and m == '黑莓':
                tip_at = (chx + w / 2, ry + mid + 16.5 + 3, f'{m}　有 {HAVE.get(m, 0)}／要 {n}')
            chx += w + 6
        ry += 60
    c.im.alpha_composite(clip.im, (int(cx), int(cy)))
    # 浮動說明（滑鼠移到「黑莓 0/1」上）：.sk .sk-tip  padding 4 10 6 10、字 14、badge 底，translate -50%
    if tip_at:
        tx, ty, s = tip_at
        tw = 10 + c.tw(s, 14) + 10
        th = 4 + 21 + 6
        c.nine('badge', cx + tx - tw / 2, cy + ty, tw, th)
        c.text(cx + tx - tw / 2, cy + ty + 4, s, 14, CREAM, w=tw, h=21, align='c')
    footer(c, cx, y + H - PANEL_PAD[2] - foot_h, cw, ['Esc'], '關閉', '材料＝背包＋倉庫')
    p = os.path.join(outdir, 'mock_brew.png')
    c.im.save(p)
    big = c.im.resize((int(SCREEN_W * 1.125), int(SCREEN_H * 1.125)), Image.NEAREST)
    big.save(os.path.join(outdir, 'mock_brew_720p.png'))
    return p


# ═══════════════════════════════ 經營商店 ═══════════════════════════════
# 上架列：[道具 48+9] [col-name 130] [col-bag 70] [col-shelf 70] [－ 33] [col-price 74] [＋ 33] [上架 72] [撤下 72]

STOCK = [('清涼藥水', 4, 2, 38), ('藍莓', 5, 0, 7), ('薰衣草', 2, 3, 26), ('戀愛藥水', 0, 1, 42), ('樹枝', 6, 0, 5),
         ('金蘋果', 1, 0, 60)]


def panel_h(rows_h, tabs_on=True):
    """面板沒有固定高度：＝ padding＋標題列＋分頁＋清單＋底列，超過 max-height 88% 才截（清單捲動）。"""
    h = PANEL_PAD[0] + HEADER_MT + HEADER_H + HEADER_MB + (48 if tabs_on else 0) + rows_h + 48 + PANEL_PAD[2]
    return min(MAX_H, h)


def shop_shell(c, tab, rows_h):
    W, H = 760, panel_h(rows_h)
    x, y = (SCREEN_W - W) // 2, (SCREEN_H - H) // 2
    cx, cy, cw = panel_frame(c, x, y, W, H, '經營商店', gold=1280)
    cy = tabs(c, cx, cy, cw, ['上架定價', '升級'], tab)
    return x, y, W, H, cx, cy, cw


def mock_shop_stock(outdir):
    c = Canvas(bg=background())
    dim(c)
    x, y, W, H, cx, cy, cw = shop_shell(c, 0, 24 + len(STOCK) * 60)
    list_w = cw          # 6 列塞得下 → 不出捲軸
    # 欄位標頭：.sk .head-row 高 24、padding 0 12 0 9、字 13
    hx = cx + 9 + 57
    for lab, w in (('品項', 130), ('可用', 70), ('架上', 70)):
        c.text(hx, cy, lab, 13, INK_HEAD, w=w, h=24, align='l' if lab == '品項' else 'c')
        hx += w
    c.text(hx + 39, cy, '售價', 13, INK_HEAD, w=74, h=24, align='c')
    ry = cy + 24
    for i, (name, avail, shelf, price) in enumerate(STOCK):
        x0, mid, xr = row_card(c, cx, ry, list_w, 57, 'row-alt' if i % 2 else 'row')
        c.img(item(name), x0, mid - 24, 48, 48)
        xx = x0 + 57
        c.text(xx, mid - 15, name, 17, INK, bold=True, h=30)
        xx += 130
        c.text(xx, mid - 15, str(avail), 17, INK if avail else INK_DIM, w=70, h=30, align='c')
        xx += 70
        c.text(xx, mid - 15, str(shelf), 17, INK if shelf else INK_DIM, w=70, h=30, align='c')
        xx += 70
        c.img('step-minus' if shelf else 'step-minus-off', xx + 6, mid - 16.5)
        xx += 39
        mw = money_w(c, price)
        money(c, xx + (74 - mw) / 2, mid - 15, 30, price)
        xx += 74
        c.img('step-plus' if shelf else 'step-plus-off', xx + 6, mid - 16.5)
        xx += 39
        button(c, xx + 6, mid - 18, 72, '上架', 'green', 'n' if avail else 'x')
        xx += 78
        button(c, xx + 6, mid - 18, 72, '撤下', 'wood', 'n' if shelf else 'x')
        ry += 60
    footer(c, cx, y + H - PANEL_PAD[2] - 48, cw, ['Esc'], '關閉', '貨架 3/5 種')
    p = os.path.join(outdir, 'mock_shop_stock.png')
    c.im.save(p)
    return p


UPG = [('招牌', 1, '顧客來得更快、同時更多人', '每 5 秒 · 同時 2 人', '每 4 秒 · 同時 3 人', 250),
       ('背包', 0, '採集能攜帶更多材料', '12 格', '15 格', 80),
       ('貨架', 1, '桌上能展示更多種商品', '5 種', '7 種', 300),
       ('花圃', 2, '把後花園的荒地開墾成花圃', '3 塊', None, None),
       ('澆水壺', 0, '一次澆得到更多塊花圃', '1 塊', '3 塊', 180)]


def mock_shop_upgrade(outdir):
    c = Canvas(bg=background())
    dim(c)
    x, y, W, H, cx, cy, cw = shop_shell(c, 1, len(UPG) * 60)
    ry = cy
    gold = 1280
    for i, (name, lv, desc, now, nxt, cost) in enumerate(UPG):
        x0, mid, xr = row_card(c, cx, ry, cw, 57, 'row-alt' if i % 2 else 'row')
        # [名稱＋Lv 徽章 120] [說明 flex] [效果 210] [費用 90] [升級 btn-buy 88]
        tw = c.text(x0, mid - 15, name, 17, INK, bold=True, h=30)
        badge(c, x0 + tw + 6, mid, f'Lv.{lv}')
        bx = xr - 88
        can = cost is not None and gold >= cost
        button(c, bx, mid - 18, 88, '升級', 'gold', 'n' if can else 'x')
        kx = bx - 6 - 90
        if cost is None:
            cwid = 24 + 2 + c.tw('滿級', 14, True)
            c.img('i8-st_ok', kx + (90 - cwid) / 2, mid - 12)
            c.text(kx + (90 - cwid) / 2 + 26, mid - 15, '滿級', 14, GREEN_SOFT, bold=True, h=30)
        else:
            mw = money_w(c, cost)
            money(c, kx + (90 - mw) / 2, mid - 15, 30, cost)
        # 效果欄 .sk .up-effect-box：寬 210、flex-wrap，字 13；放不下就 [現在 →] / [下一級] 兩行
        ex = kx - 210
        if nxt is None:
            c.text(ex, mid - 15, now, 13, GREEN_SOFT, w=210, h=30, align='c')
        else:
            a = c.tw(now, 13)
            b = c.tw(nxt, 13, True)
            tot = a + 3 + 24 + 3 + b
            if tot <= 210:
                sx = ex + (210 - tot) / 2
                c.text(sx, mid - 15, now, 13, INK_SOFT, h=30)
                c.img('i8-arrow', sx + a + 3, mid - 12)
                c.text(sx + a + 30, mid - 15, nxt, 13, GREEN_INK, bold=True, h=30)
            else:
                l1 = a + 3 + 24 + 3
                sx = ex + (210 - l1) / 2
                c.text(sx, mid - 22, now, 13, INK_SOFT, h=22)
                c.img('i8-arrow', sx + a + 3, mid - 23)
                c.text(ex, mid, nxt, 13, GREEN_INK, bold=True, w=210, h=21, align='c')
        # 說明 .up-desc：flex-grow、white-space normal（放不下會折行），字 13
        dx, dw = x0 + 120, ex - (x0 + 120) - 6
        lines, cur = [], ''
        for ch in desc:
            if c.tw(cur + ch, 13) > dw:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
        lh = 19
        top = mid - lh * len(lines) / 2
        for k, ln in enumerate(lines):
            c.text(dx, top + k * lh, ln, 13, INK_SOFT, h=lh)
        ry += 60
    footer(c, cx, y + H - PANEL_PAD[2] - 48, cw, ['Esc'], '關閉', '升級立即生效')
    p = os.path.join(outdir, 'mock_shop_upgrade.png')
    c.im.save(p)
    return p


# ═══════════════════════════════ 背包（倉庫模式）═══════════════════════════════
# 列：[道具 48+9] [row-name 150] [row-side 92] [存入 62] [[1] 40] [取回 62] [[1] 40] [row-side 92]（按鈕 margin-left 6）

BAG = [('木材', 9, 12), ('漿果', 4, 0), ('藥草', 3, 6), ('薰衣草', 2, 0), ('毛地黃種子', 1, 2), ('清涼藥水', 0, 3),
       ('星光藥劑', 1, 0)]


def mock_bag(outdir):
    c = Canvas(bg=background())
    dim(c)
    W, H = 720, MAX_H                              # BagPanelStyle .panel width 720
    x, y = (SCREEN_W - W) // 2, (SCREEN_H - H) // 2
    cx, cy, cw = panel_frame(c, x, y, W, H, '倉庫', cap='背包 7/12 種　倉庫 9/20 種')
    cy = tabs(c, cx, cy, cw, ['全部', '材料', '花與種子', '藥水'], 0)
    foot_h = 18 + 30
    rows_h = (y + H - PANEL_PAD[2]) - foot_h - cy
    list_w = cw - 21
    scrollbar(c, cx + cw - 15, cy, rows_h, 0.0, rows_h / (len(BAG) * 60 + 120))
    clip = Canvas(list_w, rows_h)
    clip.im = Image.new('RGBA', (list_w, rows_h), (0, 0, 0, 0))
    clip.d = ImageDraw.Draw(clip.im)
    ry = 0
    for i, (name, bag, kept) in enumerate(BAG):
        x0, mid, xr = row_card(clip, 0, ry, list_w, 57, 'row-alt' if i % 2 else 'row')
        clip.img(item(name), x0, mid - 24, 48, 48)
        xx = x0 + 57
        clip.text(xx, mid - 15, name, 17, INK, bold=True, h=30)
        xx += 150 - 6        # 寬度總和比內容多 1～6 px → flex-shrink 會把文字欄擠一點（這裡近似）
        clip.text(xx, mid - 15, f'背包 {bag}', 15, GREEN_SOFT if bag else INK_DIM, w=86, h=30, align='c')
        xx += 86
        for lab, w, kind, ok in (('存入', 62, 'green', bag > 0), ('[1]', 40, 'green', bag > 0),
                                 ('取回', 62, 'wood', kept > 0), ('[1]', 40, 'wood', kept > 0)):
            button(clip, xx + 6, mid - 18, w, lab, kind, 'n' if ok else 'x')
            xx += w + 6
        clip.text(xx, mid - 15, f'倉庫 {kept}', 15, GOLD_INK if kept else INK_DIM, w=86, h=30, align='c')
        ry += 60
    c.im.alpha_composite(clip.im, (int(cx), int(cy)))
    fy = y + H - PANEL_PAD[2] - foot_h
    end = footer(c, cx, fy, cw, ['Esc'], '關閉', '[1] ＝只搬一個')
    # 底列的「全部存入」鈕（UXML 的 stashAll，排在鍵帽與短字後面）
    kx = cx + 36 + 3 + 3 + c.tw('關閉', 14) + 9
    button(c, kx, fy + 18 - 3, 96, '全部存入', 'green')
    p = os.path.join(outdir, 'mock_bag.png')
    c.im.save(p)
    return p


# ═══════════════════════════════ 花店（種子）═══════════════════════════════
# 列：[道具 48+9] [名稱 120] [說明 flex，字 13] [收成：花 24 ＋ ×2，寬 150] [col-price 74] [買 1：btn-buy 88]

SEEDS = [('薰衣草種子', '薰衣草', 2, 25, '一串串的紫色小花，香味安神，藥水鋪常來收。'),
         ('毛地黃種子', '毛地黃', 2, 35, '粉紫色的鐘形花，開得又高又艷，但別亂入藥。'),
         ('星鈴花種子', '星鈴花', 1, 60, '夜裡會泛著微光的藍白鈴花，稀少而值錢。')]


def mock_town(outdir):
    c = Canvas(bg=background())
    dim(c)
    W = 760
    rows_h = len(SEEDS) * 60
    H = panel_h(rows_h)
    x, y = (SCREEN_W - W) // 2, (SCREEN_H - H) // 2
    cx, cy, cw = panel_frame(c, x, y, W, H, '花店', gold=46)
    cy = tabs(c, cx, cy, cw, ['種子', '裝飾', '家具', '貨架'], 0)
    ry = cy
    gold = 46
    for i, (seed, flower, yld, price, desc) in enumerate(SEEDS):
        x0, mid, xr = row_card(c, cx, ry, cw, 57, 'row-alt' if i % 2 else 'row')
        c.img(item(seed), x0, mid - 24, 48, 48)
        c.text(x0 + 57, mid - 15, seed, 17, INK, bold=True, h=30)
        bx = xr - 88
        button(c, bx, mid - 18, 88, '買 1', 'gold', 'n' if gold >= price else 'x')
        px = bx - 6 - 74
        mw = money_w(c, price)
        money(c, px + (74 - mw) / 2, mid - 15, 30, price)
        yx = px - 150
        s = f'×{yld}'
        tot = 24 + 2 + c.tw(s, 15, True)
        c.img(item(flower), yx + (150 - tot) / 2, mid - 12, 24, 24)
        c.text(yx + (150 - tot) / 2 + 26, mid - 15, s, 15, INK, bold=True, h=30)
        dx0 = x0 + 57 + 120
        # 說明一行放不下就截斷（uss 沒開 white-space: normal 的欄位是單行）
        txt = desc
        while c.tw(txt, 13) > yx - dx0 - 6 and len(txt) > 2:
            txt = txt[:-1]
        c.text(dx0, mid - 15, txt, 13, INK_SOFT, h=30)
        ry += 60
    footer(c, cx, ry, cw, ['Esc'], '關閉', '種在後花園')
    p = os.path.join(outdir, 'mock_town.png')
    c.im.save(p)
    return p


# ═══════════════════════════════ 下排 HUD ═══════════════════════════════
# .sk .slot 66×66、margin 3；圖示 48；數量徽章 min-width 24、高 24、right/bottom -3

def mock_hud(outdir):
    """
    .hud：bottom 12、整條寬、置中；.hud-bar：九宮格 slice 18、padding 9 12；
    .slot 66×66、margin 3（一格佔 72）；圖示 48 置中；.slot-count 徽章 right/bottom -6、min-width 24、高 24、字 13。
    """
    c = Canvas(bg=background())
    stacks = [('木材', 9), ('漿果', 4), ('藥草', 3), ('藍莓', 12), ('清涼藥水', 2), ('薰衣草', 1), ('金蘋果', 1)]
    n = 12
    bw, bh = 12 + n * 72 + 12, 9 + 72 + 9
    bx = (SCREEN_W - bw) // 2
    by = SCREEN_H - 12 - bh
    c.nine('hud-bar', bx, by, bw, bh)
    for i in range(n):
        sx = bx + 12 + i * 72 + 3
        sy = by + 9 + 3
        if i < len(stacks):
            c.nine('slot', sx, sy, 66, 66)
            name, cnt = stacks[i]
            c.img(item(name), sx + 9, sy + 9, 48, 48)
            if cnt > 1:
                s_ = str(cnt)
                w = max(24, 6 + c.tw(s_, 13, True) + 6)
                c.nine('badge', sx + 66 + 6 - w, sy + 66 + 6 - 24, w, 24)
                c.text(sx + 66 + 6 - w, sy + 66 + 6 - 24, s_, 13, CREAM, bold=True, w=w, h=24, align='c')
        else:
            c.nine('slot-empty', sx, sy, 66, 66)
    p = os.path.join(outdir, 'mock_hud.png')
    c.im.save(p)
    im = c.im.crop((bx - 20, by - 30, bx + bw + 20, SCREEN_H)).resize(((bw + 40) * 2, (SCREEN_H - by + 30) * 2), Image.NEAREST)
    im.save(os.path.join(outdir, 'mock_hud_zoom.png'))
    return p


def overview(paths, outdir):
    ims = [Image.open(p) for p in paths]
    tw, th = SCREEN_W // 2, SCREEN_H // 2
    cols = 2
    rows = (len(ims) + 1) // 2
    sheet = Image.new('RGBA', (cols * tw, rows * th), (20, 16, 20, 255))
    for i, im in enumerate(ims):
        sheet.alpha_composite(im.resize((tw, th), Image.LANCZOS), ((i % cols) * tw, (i // cols) * th))
    p = os.path.join(outdir, 'mock_overview.png')
    sheet.save(p)
    return p


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    paths = [mock_brew(outdir), mock_shop_stock(outdir), mock_shop_upgrade(outdir), mock_bag(outdir),
             mock_town(outdir), mock_hud(outdir)]
    paths.append(overview(paths, outdir))
    S.sheet([(n, im, S.SLICES.get(n)) for n, im in SKIN.items()], outdir)
    for p in paths:
        print(p)


if __name__ == '__main__':
    main()
