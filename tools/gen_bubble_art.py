"""
顧客對話泡泡的細畫版美術（2026-11-28）—— 確定性產生器（Pillow + numpy）。

    python tools/gen_bubble_art.py                 # 寫進 Assets/Resources/bubbles8/
    python tools/gen_bubble_art.py --out DIR       # 改寫到別的資料夾（試畫用）
    python tools/gen_bubble_art.py --preview DIR   # 出預覽圖（九宮格模擬、店內／花園示意、彈出動畫格）
    python tools/gen_bubble_art.py --restore       # 刪掉 bubbles8（遊戲會退回舊的程式生成圓角泡泡）

風格跟女巫 witch8 同一套：**1 px 原生像素**、遊戲裡顯示 ×1.6（SpeechBubble 用 PPU 0.625 建 Sprite），
深梅紫外輪廓、暖奶油底、多階柔和陰影、底下一道小落影。

── 圖的種類 ──────────────────────────────────────────────
  frame-<kind>.png     泡泡本體的九宮格「樣板」：左帶＋一格中央＋右帶（上下同理）。
                       Sliced 類（normal / happy / sad）中央是平塗；
                       Tiled 類（think 雲朵 / shout 爆炸框）邊上有週期花樣，Unity 用 SpriteDrawMode.Tiled 重複中央那一格，
                       程式把尺寸對齊到「整數格」，所以花樣永遠接得上（見 SpeechBubble.Frames）。
  tail-<kind>-c.png    置中的尾巴（尖端在正中間）
  tail-<kind>-s.png    斜的尾巴（尖端往左歪；泡泡被畫面邊緣推開時用，程式 flipX 讓尖端指回說話的人）
  dot-s/m/l.png        想事情泡泡的三顆小圓點（取代尾巴）
  orn-*.png            角落小裝飾：heart（開心）、sparkle（喊）、sweat（失望的汗珠）
  glyph-*.png          純圖示泡泡用的大一點的符號：heart、note、dots（…）、coin（+金額）

⚠️ 九宮格邊界、內距、尾巴重疊列數寫死在 Assets/Scripts/Core/SpeechBubble.cs 的 Frames 表 ——
   改了這裡的 SPECS 要一起改那邊（跑這支會印出那張表，貼過去對一下）。
⚠️ 這些圖放在 Resources/ 底下，PixelArtImporter 會自動設 Point、PPU 1、不壓縮（PPU 在程式建 Sprite 時另給）。
"""
import argparse
import math
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, 'Assets', 'Resources')
OUT_DEFAULT = os.path.join(RES, 'bubbles8')
FONT = os.path.join(RES, 'ui', 'fonts', 'NotoSansTC.ttf')

PX = 1.6        # 遊戲裡 1 原生像素 = 1.6 世界 px（同 GameArt.WitchScale）


def hx(s, a=255):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


SHADOW = '#2a1428'
SHADOW_A = (0.36, 0.17)      # 落影兩列（第 1、2 列）的不透明度

# 每一種泡泡的色盤：ol 外輪廓、hi 頂部高光、fill 底色、s1/s2 底部兩階陰影、rim 內圈飾邊（沒有就 None）、ink 字色
PAL = {
    'normal': dict(ol='#3a2238', hi='#fffdf6', fill='#fff6e2', s1='#f4e3c3', s2='#e6cfa4', rim=None, ink='#4a2a35'),
    'happy':  dict(ol='#4a2340', hi='#fffaf6', fill='#fff3ee', s1='#fbe0dc', s2='#eec3c4', rim='#f4a3bb', ink='#4a2a35'),
    'think':  dict(ol='#3a2a4a', hi='#ffffff', fill='#fbf7fb', s1='#ebe2f0', s2='#d8cbe2', rim=None, ink='#40304e'),
    'sad':    dict(ol='#3b3352', hi='#f8f6fb', fill='#ebe7f2', s1='#dcd5e7', s2='#c7bed9', rim=None, ink='#3a3048'),
    'shout':  dict(ol='#4a2a20', hi='#fffbe4', fill='#fff1bd', s1='#f8dd8c', s2='#e9bd5a', rim='#f2c75a', ink='#5a2a14'),
}

# 九宮格規格（原生 px）。L/R/T/B ＝ 左右上下帶寬（B 含 2 列落影）；P/PV ＝ 中央一格的寬／高（Tiled 類就是花樣週期）；
# pad ＝ 文字區離樣板邊緣的距離（左右, 上, 下；下含落影）；mode ＝ Unity 的 drawMode。
SPECS = {
    'normal': dict(L=6, R=6, T=6, B=8, P=2, PV=2, pad=(7, 5, 7), mode='Sliced'),
    'happy':  dict(L=6, R=6, T=6, B=8, P=2, PV=2, pad=(7, 5, 7), mode='Sliced'),
    'sad':    dict(L=6, R=6, T=6, B=8, P=2, PV=2, pad=(7, 5, 7), mode='Sliced'),
    'think':  dict(L=11, R=11, T=11, B=13, P=11, PV=2, pad=(8, 7, 9), mode='Tiled'),
    'shout':  dict(L=12, R=12, T=11, B=13, P=12, PV=2, pad=(9, 8, 10), mode='Tiled'),
}
SHADOW_ROWS = 2
# 尾巴最上面幾列疊在泡泡底帶上（蓋掉那一段外輪廓＋落影；多疊兩列底色當安全邊，像素沒對齊也不會露縫）
TAIL_OVERLAP = 5


# ═══════════════════════ 形狀（遮罩） ═══════════════════════

def disk(m, cx, cy, r):
    h, w = m.shape
    ys, xs = np.mgrid[0:h, 0:w]
    m |= (xs - cx) ** 2 + (ys - cy) ** 2 <= r * r + r * 0.6


def rrect(m, x0, y0, x1, y1, r):
    h, w = m.shape
    ys, xs = np.mgrid[0:h, 0:w]
    dx = np.maximum(np.maximum(x0 + r - xs, 0), xs - (x1 - r))
    dy = np.maximum(np.maximum(y0 + r - ys, 0), ys - (y1 - r))
    inside = (xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)
    m |= inside & (dx * dx + dy * dy <= r * r + r * 0.5)


def tri(m, pts):
    """填一個三角形（像素中心在內就算）。"""
    h, w = m.shape
    ys, xs = np.mgrid[0:h, 0:w]
    (ax, ay), (bx, by), (cx, cy) = pts

    def side(px, py, qx, qy):
        return (qx - px) * (ys - py) - (qy - py) * (xs - px)
    d1 = side(ax, ay, bx, by); d2 = side(bx, by, cx, cy); d3 = side(cx, cy, ax, ay)
    neg = (d1 < 0) | (d2 < 0) | (d3 < 0)
    pos = (d1 > 0) | (d2 > 0) | (d3 > 0)
    m |= ~(neg & pos)


def body_mask(kind, kx, ky):
    """kx×ky 格中央的泡泡本體遮罩（不含落影；高 = 本體高，落影另加）。"""
    sp = SPECS[kind]
    W = sp['L'] + kx * sp['P'] + sp['R']
    Hb = sp['T'] + ky * sp['PV'] + sp['B'] - SHADOW_ROWS
    m = np.zeros((Hb, W), bool)
    L, T, P, PV = sp['L'], sp['T'], sp['P'], sp['PV']
    if kind in ('normal', 'happy', 'sad'):
        rrect(m, 0, 0, W - 1, Hb - 1, 4)
    elif kind == 'think':
        # 雲朵：上下一排圓滾滾的凸起（每格一顆），左右是直的短邊＋四角小圓 —— 左右不做凸起，
        # 高度才能一列一列地長（PV＝2），一行字的雲不會被「整數格」撐得太高。
        a, sd = 5, 1                                # 上下的邊線離樣板邊 5 px、左右 1 px
        rrect(m, sd, a - 1, W - 1 - sd, Hb - a, 4)
        r = 5.3
        # 位置以「中央格起點 L」為基準 → 不管重複幾格，左右帶裡的那顆都在同一個相對位置
        for k in range(-1, kx + 1):
            x = L + P / 2 + k * P - 0.5
            if x - r >= sd + 1:
                disk(m, x, a + 0.4, r)
                disk(m, x, Hb - 1 - a - 0.4, r)
        # 四角的圓（⚠️ 不能伸進中央格那一欄／那一列，否則重複的格子接不上）
        for cx in (sd + 4.5, W - 1 - sd - 4.5):
            for cy in (a + 0.5, Hb - 1 - a - 0.5):
                disk(m, cx, cy, 4.4)
    elif kind == 'shout':
        # 爆炸框：上下一排長尖刺（每格一根）＋四角斜刺，左右直邊
        a, sd = 6, 4
        rrect(m, sd, a, W - 1 - sd, Hb - 1 - a, 1)
        hw = 4.4                                    # 尖刺底寬的一半
        for k in range(-1, kx + 1):
            x = L + P / 2 + k * P - 0.5
            if x - hw >= sd + 2 and x + hw <= W - 1 - sd - 2:
                tri(m, [(x - hw, a + 1.0), (x + hw, a + 1.0), (x, -0.9)])
                tri(m, [(x - hw, Hb - 1 - a - 1.0), (x + hw, Hb - 1 - a - 1.0), (x, Hb - 1 + 0.9)])
        for (cx, cy, dx, dy) in ((sd + 1, a + 1, -1, -1), (W - 2 - sd, a + 1, 1, -1),
                                 (sd + 1, Hb - 2 - a, -1, 1), (W - 2 - sd, Hb - 2 - a, 1, 1)):
            tri(m, [(cx + 3.0 * dx, cy - 3.0 * dy), (cx - 3.0 * dx, cy + 3.0 * dy),
                    (cx + 5.2 * dx, cy + 5.2 * dy)])
    return m


# ═══════════════════════ 上色 ═══════════════════════

def run_len(inside, axis, rev):
    """每個像素沿某方向往外走幾步才離開 inside（1 ＝ 緊貼邊）。"""
    a = inside.copy()
    if rev:
        a = np.flip(a, axis)
    out = np.zeros(a.shape, int)
    n = a.shape[axis]
    prev = np.zeros(a.shape[1 - axis] if axis == 0 else a.shape[0], int)
    for i in range(n):
        cur = a[i, :] if axis == 0 else a[:, i]
        prev = np.where(cur, prev + 1, 0)
        if axis == 0:
            out[i, :] = prev
        else:
            out[:, i] = prev
    if rev:
        out = np.flip(out, axis)
    return out


def neighbors_out(m):
    """在 m 裡、但四鄰有一格不在 m 的像素（外輪廓）。"""
    p = np.pad(m, 1, constant_values=False)
    return m & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])


def paint(mask, pal, extra_rows=SHADOW_ROWS, shadow=True):
    """遮罩 → RGBA：外輪廓、飾邊、上高光、下兩階陰影、右側一階陰影、底下落影。"""
    Hb, W = mask.shape
    H = Hb + extra_rows
    m = np.zeros((H, W), bool)
    m[:Hb] = mask
    img = np.zeros((H, W, 4), np.uint8)

    ol = neighbors_out(m)
    inner = m & ~ol
    d_top = run_len(inner, 0, False)
    d_bot = run_len(inner, 0, True)
    d_lft = run_len(inner, 1, False)
    d_rgt = run_len(inner, 1, True)
    dmin = np.minimum(np.minimum(d_top, d_bot), np.minimum(d_lft, d_rgt))

    c = {k: hx(v) for k, v in pal.items() if v and k != 'ink'}
    img[inner] = c['fill']
    if pal['rim']:
        img[inner & (d_rgt == 2) & (d_bot > 2)] = c['s1']
        img[inner & (d_top == 2)] = c['hi']
        img[inner & (d_bot == 2)] = c['s1']
        img[inner & (dmin == 1)] = c['rim']
        img[inner & (d_bot == 1)] = c['s2']
    else:
        img[inner & (d_rgt == 1) & (d_top > 1)] = c['s1']
        img[inner & (d_top == 1)] = c['hi']
        img[inner & (d_bot == 2)] = c['s1']
        img[inner & (d_bot == 1)] = c['s2']
    img[ol] = c['ol']

    if shadow:
        sc = hx(SHADOW)
        taken = m.copy()
        for i, a in enumerate(SHADOW_A, start=1):
            sh = np.zeros_like(m)
            sh[i:] = m[:-i]
            sh &= ~taken
            img[sh] = (sc[0], sc[1], sc[2], int(round(255 * a)))
            taken |= sh
    return img


def frame_full(kind, kx, ky):
    return paint(body_mask(kind, kx, ky), PAL[kind])


def frame_template(kind):
    """九宮格樣板：用 3×3 格畫一張完整的，再切出「左帶＋中間那格＋右帶」—— 保證重複幾格都接得上。"""
    sp = SPECS[kind]
    full = frame_full(kind, 3, 3)
    L, R, T, B, P, PV = sp['L'], sp['R'], sp['T'], sp['B'], sp['P'], sp['PV']
    cols = list(range(0, L)) + list(range(L + P, L + 2 * P)) + list(range(L + 3 * P, L + 3 * P + R))
    rows = list(range(0, T)) + list(range(T + PV, T + 2 * PV)) + list(range(T + 3 * PV, T + 3 * PV + B))
    return full[np.ix_(rows, cols)]


# ═══════════════════════ 尾巴 ═══════════════════════

# 尾巴形狀：每列 (左, 右)（含外輪廓），第 0 列＝泡泡外輪廓那一列。上面再疊 2 列底色（TAIL_OVERLAP 的安全邊）。
TAIL_ROWS = {
    'c': [(0, 8), (1, 7), (2, 6), (2, 5), (3, 5), (3, 4)],                 # 置中、尖端微微往左收（手繪感）
    's': [(1, 9), (1, 7), (0, 5), (0, 4), (0, 2), (0, 1)],                 # 斜：尖端往左
}
SHOUT_TAIL = {   # 爆炸框的尾巴＝一根比邊上尖刺更長的大刺（要伸出底下那排尖刺）
    'c': [(0, 12), (1, 11), (2, 10), (2, 10), (3, 9), (3, 9), (4, 8), (4, 8), (5, 7), (5, 7), (6, 6), (6, 6)],
    's': [(3, 13), (2, 11), (2, 10), (1, 9), (1, 8), (1, 7), (0, 6), (0, 5), (0, 4), (0, 3), (0, 2), (0, 1)],
}
# 尾巴圖最上面一列離泡泡樣板底邊幾列（樣板底邊含 2 列落影）：= 落影 2 ＋ 尖刺區 ＋ 外輪廓 1 ＋ 疊上去的 2 列
TAIL_AT = {'normal': TAIL_OVERLAP, 'happy': TAIL_OVERLAP, 'sad': TAIL_OVERLAP, 'shout': SHADOW_ROWS + 6 + 3}
TAIL_TIP = {}   # (kind, variant) → 尖端 x（相對尾巴圖中心，原生 px；給 C# 對位）


def tail_img(kind, var):
    pal = PAL[kind]
    rows = (SHOUT_TAIL if kind == 'shout' else TAIL_ROWS)[var]
    W = max(r for _, r in rows) + 1
    n = len(rows)
    H = 2 + n + SHADOW_ROWS
    m = np.zeros((H, W), bool)
    for i, (l, r) in enumerate(rows):
        m[2 + i, l:r + 1] = True
    img = np.zeros((H, W, 4), np.uint8)
    c = {k: hx(v) for k, v in pal.items() if v and k != 'ink'}
    # 外輪廓：左右緣與下緣（上面接泡泡，不畫）
    p = np.pad(m, 1, constant_values=False)
    p[0, :] = True
    p[1:3, 1:-1] = True                               # 疊在泡泡上的兩列當作「裡面」
    ol = m & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
    inner = m & ~ol
    img[inner] = c['s1']
    # 每列最右邊的內部像素加深一階（光從左上來）
    for y in range(H):
        xs = np.where(inner[y])[0]
        if len(xs) >= 2:
            img[y, xs[-1]] = c['s2']
    if pal['rim']:
        for y in range(H):
            xs = np.where(inner[y])[0]
            if len(xs) >= 3 and y > 2:
                img[y, xs[0]] = c['rim']
    img[ol] = c['ol']
    # 疊在泡泡底帶上的兩列：泡泡那裡是 s1、s2，照抄（外輪廓那列由 rows[0] 的內部蓋掉）
    l0, r0 = rows[0]
    img[0, l0:r0 + 1] = c['s1']
    img[1, l0:r0 + 1] = c['s2'] if not pal['rim'] else c['s2']
    if pal['rim']:
        img[0, l0:r0 + 1] = c['s1']
    # 尾巴自己的落影
    sc = hx(SHADOW)
    taken = m.copy(); taken[0:2, l0:r0 + 1] = True
    for i, a in enumerate(SHADOW_A, start=1):
        sh = np.zeros_like(m)
        sh[i:] = m[:-i]
        sh[:3] = False
        sh &= ~taken
        img[sh] = (sc[0], sc[1], sc[2], int(round(255 * a)))
        taken |= sh
    tip_l, tip_r = rows[-1]
    TAIL_TIP[(kind, var)] = ((tip_l + tip_r) / 2 + 0.5) - W / 2
    return img


# ═══════════════════════ 小圖：圓點、裝飾、符號 ═══════════════════════

def sprite_from(rows, colors):
    """用字元畫：rows 是字串列，colors 是 字元 → '#rrggbb' 或 (hex, alpha)。'.' 透明。"""
    H, W = len(rows), max(len(r) for r in rows)
    img = np.zeros((H, W, 4), np.uint8)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in colors:
                v = colors[ch]
                img[y, x] = hx(*v) if isinstance(v, tuple) else hx(v)
    return img


def dot(r, pal):
    s = int(math.ceil(r * 2)) + 1
    m = np.zeros((s, s), bool)
    disk(m, (s - 1) / 2, (s - 1) / 2, r)
    return paint(m, pal, extra_rows=1, shadow=True)


GLYPHS = {
    'orn-heart': (['.oo.oo.', 'oPPoPPo', 'oPhPPPo', 'oPPPPdo', '.oPPdo.', '..odo..', '...o...'],
                  {'o': '#5a1f3a', 'P': '#f27a9b', 'h': '#ffd6e2', 'd': '#cf5079'}),
    'orn-sparkle': (['...o...', '..oYo..', '.oYwYo.', 'oYwwwYo', '.oYwYo.', '..oYo..', '...o...'],
                    {'o': '#6e4220', 'Y': '#f0cb6a', 'w': '#fff6c8'}),
    'orn-sweat': (['..o..', '.oBo.', '.oBo.', 'oBwBo', 'oBBBo', 'obBbo', '.ooo.'],
                  {'o': '#2c3f6a', 'B': '#8fc3ee', 'w': '#e9f7ff', 'b': '#5d93cc'}),
    'glyph-heart': (['.ooo...ooo.', 'oPPPo.oPPPo', 'oPhhPoPPPPo', 'oPhPPPPPPdo', 'oPPPPPPPPdo',
                     '.oPPPPPPdo.', '..oPPPPdo..', '...oPPdo...', '....odo....', '.....o.....'],
                    {'o': '#5a1f3a', 'P': '#f27a9b', 'h': '#ffd6e2', 'd': '#cf5079'}),
    'glyph-note': (['......ooo..', '.....oNNNo.', '.....oNhNNo', '.....oNooNo', '.....oNo.oo', '.....oNo...',
                    '.....oNo...', '..oooNNo...', '.oNNNNNo...', 'oNhNNNNo...', 'oNNNNNo....', '.ooooo.....'],
                   {'o': '#3b2350', 'N': '#8a5cc4', 'h': '#c9a6f0'}),
    'glyph-dots': (['.oo....oo....oo.', 'oDDo..oDDo..oDDo', 'oDdo..oDdo..oDdo', '.oo....oo....oo.'],
                   {'o': '#3a2238', 'D': '#8a6a84', 'd': '#634660'}),
    'glyph-coin': (['...ooooo...', '.ooYYYYYoo.', '.oYwwYYYdo.', 'oYwYYYYYYdo', 'oYwYYsYYYdo', 'oYYYsssYYdo',
                    'oYYYYsYYYdo', 'oYYYYYYYddo', '.odYYYYddo.', '.oodddddoo.', '...ooooo...'],
                   {'o': '#5a3410', 'Y': '#f5cf5c', 'w': '#fff4c0', 'd': '#d39f45', 's': '#b07a26'}),
}


def all_images():
    out = {}
    for k in SPECS:
        out[f'frame-{k}'] = frame_template(k)
        if k != 'think':
            for v in ('c', 's'):
                out[f'tail-{k}-{v}'] = tail_img(k, v)
    out['dot-l'] = dot(3.3, PAL['think'])
    out['dot-m'] = dot(2.4, PAL['think'])
    out['dot-s'] = dot(1.6, PAL['think'])
    for name, (rows, cols) in GLYPHS.items():
        out[name] = sprite_from(rows, cols)
    return out


def to_pil(a):
    return Image.fromarray(a, 'RGBA')


# ═══════════════════════ 九宮格模擬（跟 Unity 一樣切） ═══════════════════════

def nine(tpl, kind, wN, hN):
    """模擬 Unity：Sliced（中間拉伸）／Tiled（邊與中間重複）。wN、hN 已經對齊過。"""
    sp = SPECS[kind]
    L, R, T, B = sp['L'], sp['R'], sp['T'], sp['B']
    th, tw = tpl.shape[:2]
    cw, ch = tw - L - R, th - T - B

    def axis(n, a, b, c):
        mid = n - a - b
        idx = list(range(a))
        if sp['mode'] == 'Sliced':
            idx += [a + min(c - 1, int(i * c / max(mid, 1))) for i in range(mid)]
        else:
            idx += [a + (i % c) for i in range(mid)]
        idx += list(range(a + c, a + c + b))
        return idx
    cols = axis(wN, L, R, cw)
    rows = axis(hN, T, B, ch)
    return tpl[np.ix_(rows, cols)]


def snap(kind, wN, hN):
    """尺寸對齊（同 C# SpeechBubble.Snap）：Tiled 類中央要是整數格；至少一格。"""
    sp = SPECS[kind]
    cx = max(1, math.ceil((wN - sp['L'] - sp['R']) / sp['P']))
    cy = max(1, math.ceil((hN - sp['T'] - sp['B']) / sp['PV']))
    if sp['mode'] == 'Sliced':
        return max(wN, sp['L'] + sp['R'] + 1), max(hN, sp['T'] + sp['B'] + 1)
    return sp['L'] + sp['R'] + cx * sp['P'], sp['T'] + sp['B'] + cy * sp['PV']


# ═══════════════════════ 預覽 ═══════════════════════

EM = 16.2          # TextMesh：fontSize 36 × characterSize 4.5 ÷ 10
LINE_H = 20.0
MAX_LINE_W = 176.0
MIN_W = 44.0
ICON_W = 26.0      # 帶道具圖示時，圖示佔的寬（世界 px；圖示本身 ≈ 28 內容）


def font(size=16):
    return ImageFont.truetype(FONT, size)


def measure(s, f):
    return f.getlength(s)


def layout(text, f):
    if '\n' in text:
        parts = text.split('\n')
        return parts, max(measure(p, f) for p in parts)
    full = measure(text, f)
    if full <= MAX_LINE_W or len(text) < 4:
        return [text], full
    n = 2 if full <= MAX_LINE_W * 2 else 3
    best = None
    if n == 2:
        for i in range(1, len(text)):
            s = max(measure(text[:i], f), measure(text[i:], f))
            if best is None or s < best[0]:
                best = (s, [text[:i], text[i:]])
    else:
        for i in range(1, len(text) - 1):
            for j in range(i + 1, len(text)):
                ps = [text[:i], text[i:j], text[j:]]
                s = max(measure(p, f) for p in ps)
                if best is None or s < best[0]:
                    best = (s, ps)
    return best[1], best[0]


def render_bubble(imgs, kind, text, icon=None, f=None, icon_only=False):
    """畫一顆泡泡（世界 px，1:1）。回傳 (RGBA 圖, 尾巴尖端在圖裡的 x)。泡泡本體 ×1.6 用最近鄰放大，字用真的字型。"""
    f = f or font()
    pal = PAL[kind]
    sp = SPECS[kind]
    padx, padt, padb = sp['pad']
    if icon_only:
        lines, tw = [], 0.0
        cw, chh = float(icon.width), float(icon.height)
    else:
        lines, tw = layout(text, f)
        cw = tw + (ICON_W if icon is not None else 0)
        chh = EM + (len(lines) - 1) * LINE_H
    if icon_only:   # 純圖示：內距各少 2 px，比較圓胖（同 C# SpeechBubble.ShowIcon）
        wN = math.ceil(cw / PX) + 2 * (padx - 2)
        hN = math.ceil(chh / PX) + padt + padb - 2
    else:
        wN = math.ceil(max(MIN_W, cw + 2 * padx * PX) / PX)
        hN = math.ceil(chh / PX) + padt + padb
    wN, hN = snap(kind, wN, hN)
    body = nine(imgs[f'frame-{kind}'], kind, wN, hN)
    bw, bh = round(wN * PX), round(hN * PX)
    body_im = to_pil(body).resize((bw, bh), Image.NEAREST)

    # 尾巴
    if kind == 'think':
        tail_h = 27         # 同 C# SpeechBubble.ThinkDotsH
    else:
        t = imgs[f'tail-{kind}-c']
        tail_h = round((t.shape[0] - TAIL_AT[kind]) * PX)
    W = bw + 8
    H = bh + tail_h + 2      # 底邊＝根物件原點（尾巴尖端），疊到場景上就是頭頂上 TipGap
    can = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ox, oy = 4, 2
    can.alpha_composite(body_im, (ox, oy))
    cx = ox + bw / 2
    if kind == 'think':
        # 同 C# BubbleLife.AimTail：小圓點從頭頂（尾巴原點）連到雲的底邊，f＝0 頭頂、1 雲底
        origin_y = oy + bh + tail_h
        ay = tail_h + SHADOW_ROWS * PX - 1
        for name, f_ in (('dot-s', 0.1), ('dot-m', 0.4), ('dot-l', 0.74)):
            d = to_pil(imgs[name]); d = d.resize((round(d.width * PX), round(d.height * PX)), Image.NEAREST)
            cyy = origin_y - (ay * f_ + 2)
            can.alpha_composite(d, (round(cx + 9 * f_ - d.width / 2), round(cyy - d.height / 2)))   # DotLean 9
    else:
        t = to_pil(imgs[f'tail-{kind}-c'])
        t = t.resize((round(t.width * PX), round(t.height * PX)), Image.NEAREST)
        ty = oy + bh - round(TAIL_AT[kind] * PX)
        can.alpha_composite(t, (round(cx - t.width / 2), ty))

    # 內容
    d = ImageDraw.Draw(can)
    ink = hx(pal['ink'])
    top = oy + padt * PX
    bottom = oy + bh - padb * PX
    area_cy = (top + bottom) / 2
    if icon_only:
        ic = icon
        can.alpha_composite(ic, (round(cx - ic.width / 2), round(area_cy - ic.height / 2)))
    else:
        x0 = cx - cw / 2
        if icon is not None:
            can.alpha_composite(icon, (round(x0 + ICON_W / 2 - icon.width / 2), round(area_cy - icon.height / 2)))
            x0 += ICON_W
        ty0 = area_cy - chh / 2
        for i, ln in enumerate(lines):
            lw = measure(ln, f)
            # Noto 的字身：em 框上緣到基線約 0.88 em —— 用 anchor 'ls'（左基線）對齊比較準
            base = ty0 + i * LINE_H + EM * 0.86
            d.text((x0 + (tw - lw) / 2, base), ln, font=f, fill=ink, anchor='ls')
    # 裝飾
    orn = {'happy': 'orn-heart', 'shout': 'orn-sparkle', 'sad': 'orn-sweat'}.get(kind)
    if orn and not icon_only:
        o = to_pil(imgs[orn]); o = o.resize((round(o.width * PX), round(o.height * PX)), Image.NEAREST)
        can.alpha_composite(o, (round(ox + bw - o.width + 3 * PX), round(oy - 2 * PX)) if kind != 'sad'
                            else (round(ox + bw - o.width - 1 * PX), round(oy - 2 * PX)))
    return can, cx


def item_icon(name, world=28.0):
    """items8 圖示縮到「最長邊 world px」（遊戲用 GameArt.ItemIconWorld 同一套換算：×40/34）。"""
    im = Image.open(os.path.join(RES, 'items8', name + '.png')).convert('RGBA')
    k = world * 40 / 34 / max(im.size)
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.NEAREST)


def glyph(imgs, name):
    g = to_pil(imgs[name])
    return g.resize((round(g.width * PX), round(g.height * PX)), Image.NEAREST)


def villager(name, col=0, row=0):
    im = Image.open(os.path.join(RES, 'villagers8', name + '.png')).convert('RGBA')
    cell = im.crop((col * 56, row * 72, col * 56 + 56, row * 72 + 72))
    return cell.resize((round(56 * PX), round(72 * PX)), Image.NEAREST)


def witch():
    im = Image.open(os.path.join(RES, 'witch8', 'base.png')).convert('RGBA')
    cell = im.crop((0, 0, 49, 66))
    return cell.resize((round(49 * PX), round(66 * PX)), Image.NEAREST)


SAMPLES = [
    ('normal', '來逛逛～', None), ('happy', '想要 藥草', 'herb'), ('think', '嗯…再考慮一下', 'berry'),
    ('sad', '沒貨…下次吧', None), ('shout', '+120', 'coin'),
]
TEXTS = ['好棒', '今天有什麼新貨嗎？', '這個價錢…可以算便宜點嗎？']


def preview(out):
    os.makedirs(out, exist_ok=True)
    imgs = all_images()
    f = font()

    # ① 每種泡泡 × 三種長度（1:1 與 3×），底色兩種（店內暗木地板、戶外亮草地）
    for bgname, bgc in (('shop', (92, 64, 58, 255)), ('garden', (150, 196, 110, 255))):
        cells = []
        for kind in SPECS:
            row = []
            for t in TEXTS:
                b, _ = render_bubble(imgs, kind, t, f=f)
                row.append(b)
            ic = item_icon('herb') if kind in ('happy', 'think') else None
            b, _ = render_bubble(imgs, kind, '想要 藥草' if ic else '好棒', icon=ic, f=f)
            row.append(b)
            cells.append(row)
        W = 16 + sum(max(r[i].width for r in cells) + 14 for i in range(4))
        H = 16 + sum(max(b.height for b in r) + 12 for r in cells) + 70
        sheet = Image.new('RGBA', (W, H), bgc)
        y = 10
        for r in cells:
            x = 10
            for i, b in enumerate(r):
                sheet.alpha_composite(b, (x, y))
                x += max(rr[i].width for rr in cells) + 14
            y += max(b.height for b in r) + 12
        # 純圖示泡泡
        x = 10
        for kind, g in (('normal', glyph(imgs, 'glyph-heart')), ('think', item_icon('berry', 26)),
                        ('normal', glyph(imgs, 'glyph-note')), ('sad', glyph(imgs, 'glyph-dots')),
                        ('shout', glyph(imgs, 'glyph-coin'))):
            b, _ = render_bubble(imgs, kind, '', icon=g, f=f, icon_only=True)
            sheet.alpha_composite(b, (x, y)); x += b.width + 12
        sheet.save(os.path.join(out, f'kinds_{bgname}_1x.png'))
        sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST).save(os.path.join(out, f'kinds_{bgname}_3x.png'))

    # ② 九宮格樣板本身（放大 8 倍）
    names = sorted(imgs)
    W = sum(imgs[n].shape[1] * 8 + 8 for n in names) + 8
    H = max(imgs[n].shape[0] for n in names) * 8 + 16
    sh = Image.new('RGBA', (W, H), (120, 120, 140, 255))
    x = 8
    for n in names:
        im = to_pil(imgs[n]); im = im.resize((im.width * 8, im.height * 8), Image.NEAREST)
        sh.alpha_composite(im, (x, 8)); x += im.width + 8
    sh.save(os.path.join(out, 'templates_8x.png'))

    # ③ 店內示意：店底圖＋貨架＋三位客人（一位純圖示）＋兩顆疊起來的＋女巫
    shop = Image.open(os.path.join(RES, 'rooms', 'shop-room.png')).convert('RGBA')
    scene = shop.copy()
    def put(im, footx, footy):
        scene.alpha_composite(im, (round(footx - im.width / 2), round(footy - im.height)))
    for nm, fx, fy in (('shelf_tall', 300, 330), ('shelf_two', 520, 300), ('table_round', 640, 430)):
        p = os.path.join(RES, 'furniture8', nm + '.png')
        if os.path.exists(p):
            put(Image.open(p).convert('RGBA'), fx, fy)
    actors = [('fox', 360, 470), ('rabbit', 430, 470), ('frog', 600, 520), ('deer', 860, 500)]
    for nm, x, y in actors:
        put(villager(nm, 0, 0), x, y)
    put(witch(), 720, 560)
    headH = 72 * PX
    def bubble_at(kind, text, icon, x, y, lift=0, icon_only=False):
        b, tip = render_bubble(imgs, kind, text, icon=icon, f=f, icon_only=icon_only)
        scene.alpha_composite(b, (round(x - tip), round(y - headH - 2 - b.height - lift)))
        return b
    b1 = bubble_at('happy', '想要 藥草', item_icon('herb'), 360, 470)
    # 第二位站很近 → 往上疊（間距 4）
    bubble_at('normal', '哇，跟你說的一樣可愛', None, 430, 470, lift=b1.height - 14 + 4)
    bubble_at('think', '', item_icon('berry', 26), 600, 520, icon_only=True)
    bubble_at('shout', '+120', glyph(imgs, 'glyph-coin'), 860, 500)
    scene.save(os.path.join(out, 'scene_shop.png'))
    scene.crop((240, 160, 940, 600)).resize((700 * 2, 440 * 2), Image.NEAREST).save(os.path.join(out, 'scene_shop_2x.png'))

    # ④ 花園（亮背景）
    g = Image.open(os.path.join(RES, 'rooms', 'garden8.png')).convert('RGBA')
    gx0, gy0 = 600, 300
    scene = g.crop((gx0, gy0, gx0 + 960, gy0 + 640))
    for nm, x, y in actors:
        put(villager(nm, 0, 0), x, y)
    put(witch(), 720, 560)
    b1 = bubble_at('sad', '沒貨…下次吧', None, 360, 470)
    bubble_at('think', '嗯…再考慮一下', item_icon('berry'), 430, 470, lift=b1.height - 14 + 4)
    bubble_at('normal', '', glyph(imgs, 'glyph-note'), 600, 520, icon_only=True)
    bubble_at('shout', '+120', glyph(imgs, 'glyph-coin'), 860, 500)
    scene.save(os.path.join(out, 'scene_garden.png'))
    scene.crop((240, 160, 940, 600)).resize((700 * 2, 440 * 2), Image.NEAREST).save(os.path.join(out, 'scene_garden_2x.png'))

    # ⑤ 彈出動畫（同 C# BubbleLife：0.6 → 回彈 → 1，0.16 秒，以尾巴尖端為中心長大；
    #    想事情：小圓點每 0.05 秒冒一顆（由頭頂往上），0.12 秒起雲朵本體才從底邊彈出）
    bg = (92, 64, 58, 255)
    CW, CH = 200, 110
    frames = []
    for kind, text in (('normal', '來逛逛～'), ('happy', '謝謝魔女小姐～'), ('think', '嗯…再考慮一下')):
        full, tip = render_bubble(imgs, kind, text, f=f)
        body_h = full.height - (27 if kind == 'think' else 0) - 2
        for i in range(14):
            t = i / 60.0
            fr = Image.new('RGBA', (CW, CH), bg)
            ox, oy = round(CW / 2 - tip), CH - 6 - full.height
            if kind != 'think':
                s = pop_scale(t)
                v = full.resize((max(1, round(full.width * s)), max(1, round(full.height * s))), Image.NEAREST)
                fr.alpha_composite(v, (round(CW / 2 - tip * s), CH - 6 - v.height))
            else:
                dots = full.crop((0, body_h, full.width, full.height))
                n = min(3, 1 + int(t / 0.05))
                keep = [0.0, 0.45, 0.75, 1.0][n]            # 由下往上露出幾顆
                cut = round(dots.height * (1 - keep))
                d2 = dots.crop((0, cut, dots.width, dots.height))
                fr.alpha_composite(d2, (ox, oy + body_h + cut))
                tb = t - 0.12
                if tb >= 0:
                    s = pop_scale(tb)
                    body = full.crop((0, 0, full.width, body_h))
                    v = body.resize((max(1, round(body.width * s)), max(1, round(body.height * s))), Image.NEAREST)
                    fr.alpha_composite(v, (round(ox + full.width / 2 - v.width / 2), oy + body_h - v.height))
            frames.append(fr)
    strip = Image.new('RGBA', (CW * 14, CH * 3), bg)
    for i, fr in enumerate(frames):
        strip.alpha_composite(fr, ((i % 14) * CW, (i // 14) * CH))
    strip = strip.resize((strip.width * 2, strip.height * 2), Image.NEAREST)
    strip.crop((0, 0, CW * 2 * 7, strip.height)).save(os.path.join(out, 'pop_strip.png'))   # 前 7 幀（0～0.1 秒）
    strip.crop((CW * 2 * 7, 0, strip.width, strip.height)).save(os.path.join(out, 'pop_strip_b.png'))
    big = [fr.resize((CW * 2, CH * 2), Image.NEAREST) for fr in frames]
    big[0].save(os.path.join(out, 'pop.gif'), save_all=True, append_images=big[1:] + [big[-1]] * 20,
                duration=1000 // 60, loop=0)
    print('預覽 →', out)


def pop_scale(t):
    """同 C# BubbleLife.Pop：0.6 起跳、EaseOutBack（c1 = 2.4，大約回彈到 1.06）、0.16 秒。"""
    d = 0.16
    if t >= d:
        return 1.0
    x = t / d
    c1 = 2.4; c3 = c1 + 1
    e = 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
    return 0.6 + 0.4 * e


def print_table(imgs):
    print('── 給 SpeechBubble.cs 對照 ──')
    for k, sp in SPECS.items():
        t = imgs[f'frame-{k}']
        print(f"  {k:7s} 樣板 {t.shape[1]}×{t.shape[0]}  L{sp['L']} R{sp['R']} T{sp['T']} B{sp['B']}  "
              f"格 {sp['P']}×{sp['PV']}  pad {sp['pad']}  {sp['mode']}")
    for (k, v), tip in sorted(TAIL_TIP.items()):
        t = imgs[f'tail-{k}-{v}']
        print(f"  tail-{k}-{v}: {t.shape[1]}×{t.shape[0]}  接在樣板底邊上 {TAIL_AT[k]} 列  尖端 x {tip:+.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT_DEFAULT)
    ap.add_argument('--preview')
    ap.add_argument('--restore', action='store_true')
    a = ap.parse_args()
    if a.restore:
        if os.path.isdir(OUT_DEFAULT):
            shutil.rmtree(OUT_DEFAULT)
            meta = OUT_DEFAULT + '.meta'
            if os.path.exists(meta):
                os.remove(meta)
        print('已刪除', OUT_DEFAULT)
        return
    imgs = all_images()
    if a.preview:
        preview(a.preview)
        print_table(imgs)
        return
    os.makedirs(a.out, exist_ok=True)
    for n, im in sorted(imgs.items()):
        to_pil(im).save(os.path.join(a.out, n + '.png'), optimize=True)
    print(f'寫了 {len(imgs)} 張 → {a.out}')
    print_table(imgs)


if __name__ == '__main__':
    main()
