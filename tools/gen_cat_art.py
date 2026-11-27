#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
藥水室的貓（魔女的使魔）—— 走路／坐／理毛／睡覺／被摸／伸懶腰／嚇一跳的動畫表，全部用程式點陣畫。

    python tools/gen_cat_art.py                    # 輸出 Assets/Resources/cat8/cat.png
    python tools/gen_cat_art.py --out DIR          # 改寫到 DIR（迭代時用，不碰 Assets）
    python tools/gen_cat_art.py --preview DIR      # 另外輸出放大的動畫表（木地板／夜晚）、GIF、跟女巫的排排站、房間合成

── 規格（⚠️ Core/RoomCat.cs 依賴這個，改之前先看那邊的 Sheet 常數）────────────────
  * 一張 **240×360** ＝ 6 欄 × 10 列，每格 **40×36** 原生像素（PPU 1、Point），遊戲裡跟女巫一樣 **×1.6**（GameArt.WitchScale）。
  * 貓水平置中（中線在第 19／20 欄之間）；**腳底外輪廓在第 32 列，33～35 列留空 → 腳底在格子底邊往上 3px**
    （跟女巫、路人一樣是 3；check_cell 逐格檢查）。嚇一跳那一格（列 7 欄 2）是跳在空中、故意離地。
  * 列（從上往下）與欄：
      0 WALK_DOWN  4 幀  朝下走
      1 WALK_SIDE  4 幀  側面**朝左**走（往右由 RoomCat 用 flipX 翻）
      2 WALK_UP    4 幀  朝上走（背影）
      3 SIT        6 幀  0 坐好、1／2 尾巴左右甩、3 眨眼、4 耳朵抖一下、5 抬頭看（瞳孔偏左；看右邊時 flipX）
      4 GROOM      4 幀  舉起前腳舔毛（1、3 有舌頭）
      5 SLEEP      4 幀  捲成一團呼吸（0→1→2→1，3 ＝耳朵抖一下）
      6 HAPPY      4 幀  被摸：眼睛 ^ ^、往手那邊靠、尾巴豎直搖、臉紅
      7 ACT        6 幀  0／1 伸懶腰（側面朝左）、2 嚇一跳跳起來、3 落地蹲、4 睡眼惺忪、5 打哈欠
      8 FX         6 格  0 愛心、1 小愛心、2 小 z、3 大 Z、4 音符、5 問號（**格子正中央**當樞紐）
      9 PROPS      1 格  0 貓窩坐墊（沒有房間美術畫的貓窩時 RoomCat 自己擺；樞紐＝坐墊落地中心，見 CUSHION_FOOT）
  * 大小（含耳朵與外輪廓，原生）：站著 24、坐著 25、睡著 15 高 → 畫面上約 38／40／24px，女巫 58 → 93px（約四成）。大頭的 Q 版比例。

── 畫法（照女巫 witch8／路人 villagers8 的成品感）──────────────────────────
  * 原生 1px 像素；每種材質 5 階色相偏移色階（亮部偏暖、暗部偏藍紫）＋部件之間的內描線＋整隻外圍一圈近黑外輪廓。
  * 黑貓不能畫成一團黑：毛色是帶藍紫的深灰黑，左上受光面亮到藍紫色、右下輪廓內緣再加一圈冷藍的背光（rim light）
    → 在深色木地板、夜晚的房間裡輪廓都讀得出來。
  * 大大的黃綠色眼睛（直立的瞳孔＋白色反光點）、粉紅鼻子與耳朵內側、紫色緞帶項圈＋金色小鈴鐺。
  * 結果是確定的：沒有亂數，重跑 md5 相同。
"""
import colorsys
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('WITCH_UNITY_ROOT') or os.path.dirname(HERE)
RES = os.path.join(ROOT, 'Assets', 'Resources')
OUT_DIR = os.path.join(RES, 'cat8')

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

W, H = 40, 36            # 一格
COLS, ROWS = 6, 10
CX = 20.0                # 中線（第 19／20 欄之間）
FOOT = 32                # 腳底外輪廓所在的列（身體最下面一列 = 31）
PAD = H - 1 - FOOT       # 3
GAME_SCALE = 1.6         # = GameArt.WitchScale

ROW_WALK_DOWN, ROW_WALK_SIDE, ROW_WALK_UP, ROW_SIT, ROW_GROOM, ROW_SLEEP, ROW_HAPPY, ROW_ACT, ROW_FX, ROW_PROPS = range(10)
# 貓窩坐墊的落地中心（格子內座標，像素中心）：RoomCat 的 CushionPivot 要跟這個一致
CUSHION_FOOT = (20, 29)

YY, XX = np.mgrid[0:H, 0:W]
PX = XX + 0.5
PY = YY + 0.5
Z = np.zeros((H, W), bool)

OUT = (9, 6, 16)          # 外輪廓


def hx(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


class Mat:
    """一種材質：0 最暗 … 4 最亮，'ln' ＝ 部件之間的內描線。"""

    def __init__(self, cols, ln):
        self.c = {i: hx(v) for i, v in enumerate(cols)}
        self.c['ln'] = hx(ln)

    def dark(self, n=1):
        m = Mat.__new__(Mat)
        m.c = {i: self.c[max(0, i - n)] for i in range(5)}
        m.c['ln'] = self.c['ln']
        return m

    def __getitem__(self, k):
        return self.c[k]


# 毛色：帶藍紫的黑。亮部一路轉到藍紫（受光）—— 不是灰
FUR = Mat(['#120e1f', '#1c1730', '#29223f', '#3b3560', '#5a5794'], '#07040d')
FUR_BACK = FUR.dark(1)                    # 後面那側的腳、遠的耳朵
RIM = hx('#353f74')                       # 右側的冷藍背光
RIM_HI = hx('#6f6db4')                    # 左上最亮的一圈（只點在頭頂、背脊）
LID = hx('#c9c4ff')                       # 閉眼的弧線（^ ^／U）：要夠亮，黑毛上才看得到
EYE = Mat(['#2f4a10', '#6fa424', '#a9dc3c', '#d8f468', '#f4ffc0'], '#1a2208')
PUPIL = hx('#0d0814')
GLINT = hx('#ffffff')
PINK = Mat(['#7a2e58', '#a8487c', '#d86f9e', '#f293bd', '#ffc2da'], '#4a1838')
BLUSH = hx('#8c4c86')
RIBBON = Mat(['#3c1a6e', '#5a2a9a', '#7c44c8', '#a26ee8', '#c9a2ff'], '#22093f')
GOLD = Mat(['#6a4210', '#a8701c', '#dba63a', '#f6d46a', '#fff4b8'], '#3a2208')
MOUTH = hx('#6a5f9e')
WHISKER = (176, 172, 222, 150)
CUSH = Mat(['#3a1e5a', '#56307e', '#7446a2', '#9468c4', '#b892e0'], '#1c0c30')
CUSH_TOP = Mat(['#4a2a6e', '#6a3e94', '#8a5cb8', '#ab80d6', '#cba6ee'], '#1c0c30')


# ───────────── 形狀 ─────────────

def ell(cx, cy, rx, ry):
    return ((PX - cx) / rx) ** 2 + ((PY - cy) / ry) ** 2 <= 1.0


def rect(x0, y0, x1, y1):
    return (XX >= x0) & (XX <= x1) & (YY >= y0) & (YY <= y1)


def cap(x0, y0, x1, y1, r):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else np.clip(((PX - x0) * dx + (PY - y0) * dy) / L2, 0, 1)
    qx, qy = x0 + t * dx, y0 + t * dy
    return (PX - qx) ** 2 + (PY - qy) ** 2 <= r * r


def bez(pts, r0, r1=None, n=40):
    if r1 is None:
        r1 = r0
    m = Z.copy()
    P = np.array(pts, float)
    for i in range(n + 1):
        t = i / n
        if len(P) == 3:
            q = (1 - t) ** 2 * P[0] + 2 * (1 - t) * t * P[1] + t * t * P[2]
        elif len(P) == 4:
            q = ((1 - t) ** 3 * P[0] + 3 * (1 - t) ** 2 * t * P[1] + 3 * (1 - t) * t * t * P[2] + t ** 3 * P[3])
        else:
            q = (1 - t) * P[0] + t * P[1]
        r = r0 + (r1 - r0) * t
        m |= (PX - q[0]) ** 2 + (PY - q[1]) ** 2 <= r * r
    return m


def poly(pts):
    im = Image.new('L', (W, H), 0)
    ImageDraw.Draw(im).polygon([(x, y) for x, y in pts], fill=1)
    return np.array(im, bool)


def shiftm(m, dx, dy):
    o = np.zeros_like(m)
    ys, xs = np.nonzero(m)
    xs2, ys2 = xs + dx, ys + dy
    k = (xs2 >= 0) & (xs2 < W) & (ys2 >= 0) & (ys2 < H)
    o[ys2[k], xs2[k]] = True
    return o


def dil(m, n=1):
    for _ in range(n):
        o = m.copy()
        o[1:, :] |= m[:-1, :]
        o[:-1, :] |= m[1:, :]
        o[:, 1:] |= m[:, :-1]
        o[:, :-1] |= m[:, 1:]
        m = o
    return m


def edge(m, side):
    dx, dy = {'t': (0, -1), 'b': (0, 1), 'l': (-1, 0), 'r': (1, 0)}[side]
    return m & ~shiftm(m, -dx, -dy)


# ───────────── 打光 ─────────────

LIGHT = np.array([-0.5, -0.62, 0.95])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
TH = (0.28, 0.52, 0.80, 0.94)


def _blur(m, r):
    im = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, np.float32) / 255.0


def shade(m, mode='soft', blur=1.4, k=3.0, bias=0.0, c=None, r=None):
    if mode == 'mid':
        return np.full(m.shape, 2, np.int8)
    if mode == 'ball':
        ys, xs = np.nonzero(m)
        if c is None:
            c = ((xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2)
        if r is None:
            r = ((xs.max() - xs.min() + 1) / 2, (ys.max() - ys.min() + 1) / 2)
        nx = (PX - c[0]) / r[0]
        ny = (PY - c[1]) / r[1]
        nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0.02, 1))
        n = np.stack([nx, ny, nz], -1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        I = n @ LIGHT
    else:
        h = _blur(m, blur)
        gx = np.zeros_like(h)
        gy = np.zeros_like(h)
        gx[:, 1:-1] = h[:, 2:] - h[:, :-2]
        gy[1:-1, :] = h[2:, :] - h[:-2, :]
        n = np.stack([-gx * k, -gy * k, np.ones_like(h)], -1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        I = n @ LIGHT
    lv = np.zeros(m.shape, np.int8)
    for t in TH:
        lv += ((I + bias) >= t)
    return _clean(lv, m)


def _clean(lv, m):
    lv = lv.copy()
    ys, xs = np.nonzero(m)
    for y, x in zip(ys, xs):
        nb = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, yy = x + dx, y + dy
            if 0 <= xx < W and 0 <= yy < H and m[yy, xx]:
                nb.append(lv[yy, xx])
        if len(nb) >= 3 and all(v != lv[y, x] for v in nb):
            vals, cnt = np.unique(nb, return_counts=True)
            lv[y, x] = vals[np.argmax(cnt)]
    return lv


# ───────────── 畫布 ─────────────

class Fr:
    def __init__(self):
        self.rgb = np.zeros((H, W, 3), np.int16)
        self.a = Z.copy()
        self.pid = np.full((H, W), -1, np.int32)
        self.parts = []
        self.fur = Z.copy()          # 毛的像素（背光要畫在這上面）
        self.over = {}

    def fill(self, m, mat, sh='soft', group=None, line=True, lv=None, fur=None, **kw):
        m = m & True
        if not m.any():
            return m
        if lv is None:
            lv = shade(m, sh, **kw)
        idx = len(self.parts)
        self.parts.append((mat, group if group is not None else idx, line))
        for i in range(5):
            self.rgb[m & (lv == i)] = mat[i]
        self.a |= m
        self.pid[m] = idx
        isfur = fur if fur is not None else (mat is FUR or mat is FUR_BACK)
        if isfur:
            self.fur |= m
        else:
            self.fur &= ~m
        return m

    def put(self, pts, rgb, fur=False):
        if isinstance(rgb, str):
            rgb = hx(rgb)
        for x, y in pts:
            x, y = int(x), int(y)
            if 0 <= x < W and 0 <= y < H:
                self.rgb[y, x] = rgb
                if not self.a[y, x]:
                    self.a[y, x] = True
                    self.pid[y, x] = len(self.parts) - 1
                if not fur:
                    self.fur[y, x] = False

    def stamp(self, x0, y0, rows, cmap, mirror=False):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch in ' .':
                    continue
                xx = x0 + (len(row) - 1 - i if mirror else i)
                self.put([(xx, y0 + j)], cmap[ch])

    def overlay(self, pts, rgba):
        for x, y in pts:
            x, y = int(x), int(y)
            if 0 <= x < W and 0 <= y < H:
                self.over[(x, y)] = rgba

    def render(self, rim=True):
        rgb = self.rgb.copy()
        pid = self.pid
        gid = {}
        groups = np.array([gid.setdefault(repr(g), len(gid)) for _, g, _ in self.parts] + [-99], np.int64)
        lines = np.array([ln for _, _, ln in self.parts] + [False])
        mark = Z.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = np.full((H, W), -1, np.int32)
            ys0, ys1 = max(0, -dy), H - max(0, dy)
            xs0, xs1 = max(0, -dx), W - max(0, dx)
            q[ys0:ys1, xs0:xs1] = pid[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
            ok = (pid >= 0) & (q > pid)
            ok &= lines[q] & (groups[q] != groups[np.maximum(pid, 0)])
            mark |= ok
        if rim:
            # 背光：輪廓內緣、右側與下側那圈毛 → 冷藍；左上那圈 → 最亮的藍紫（只在頭頂／背上）
            a = self.a
            right = a & ~shiftm(a, -1, 0)
            below = a & ~shiftm(a, 0, -1)
            top = a & ~shiftm(a, 0, 1)
            left = a & ~shiftm(a, 1, 0)
            f = self.fur & ~mark
            rgb[right & f & ~top & ~left] = RIM
            hi = (top | left) & f & ~right & ~below
            # 最亮只點在已經是亮部（3 階以上）的毛上，暗面的上緣維持原色
            bright = np.all(rgb == np.array(FUR[4]), -1) | np.all(rgb == np.array(FUR[3]), -1)
            rgb[hi & bright] = RIM_HI
        ys, xs = np.nonzero(mark)
        for y, x in zip(ys, xs):
            rgb[y, x] = self.parts[pid[y, x]][0]['ln']
        out = np.zeros((H, W, 4), np.uint8)
        out[..., :3] = np.clip(rgb, 0, 255)
        out[..., 3] = np.where(self.a, 255, 0)
        ol = dil(self.a) & ~self.a
        out[ol, :3] = OUT
        out[ol, 3] = 255
        for (x, y), c in self.over.items():
            if out[y, x, 3] == 0 or c[3] == 255:
                if out[y, x, 3] == 0:
                    out[y, x] = c
                else:
                    out[y, x, :3] = c[:3]
            else:
                al = c[3] / 255
                out[y, x, :3] = np.round(np.array(c[:3]) * al + out[y, x, :3] * (1 - al))
        return Image.fromarray(out)


# ───────────── 部件 ─────────────

def eye_px(fr, x0, y0, kind, mirror=False, look=0):
    """一隻眼睛（左上角 x0,y0；3 寬 × 4 高）。kind：open／wide／half／closed／happy／squint。look：瞳孔偏移（-1 左、+1 右）。"""
    E = EYE
    if kind == 'open':
        # 上排深一點（上眼皮的影子）、中間最亮、直立的黑瞳孔、白色反光
        rows = ['aba', 'cPc', 'dPc', 'bcb']
        cmap = {'a': E[1], 'b': E[2], 'c': E[3], 'd': E[4], 'P': PUPIL}
        pcol = 1 + look
        out = []
        for row in rows:
            r = list(row)
            if 'P' in r:
                r = [ch if ch != 'P' else 'c' for ch in r]
                r[max(0, min(2, pcol))] = 'P'
            out.append(''.join(r))
        fr.stamp(x0, y0, out, cmap, mirror and look == 0)
        # 反光：在瞳孔的另一側上方（看左邊時在右上）
        gx = x0 + (2 if look < 0 else 0)
        if look == 0 and mirror:
            gx = x0 + 2
        fr.put([(gx, y0 + 1)], GLINT)
    elif kind == 'wide':
        rows = ['bccb', 'cdPc', 'cPPc', 'bccb']
        cmap = {'b': E[2], 'c': E[3], 'd': E[4], 'P': PUPIL}
        xx = x0 - (1 if mirror else 0)
        fr.stamp(xx, y0, rows, cmap)
        fr.put([(xx + 1, y0 + 1)], GLINT)
    elif kind == 'half':
        rows = ['LLL', 'bPb', 'cPc']
        cmap = {'L': LID, 'b': E[2], 'c': E[3], 'P': PUPIL}
        fr.stamp(x0, y0 + 1, rows, cmap)
    elif kind == 'closed':
        # 安心閉眼：往下彎的弧（U），用亮的淡紫，黑毛上才看得到
        fr.put([(x0, y0 + 1), (x0 + 1, y0 + 2), (x0 + 2, y0 + 1)], LID)
    elif kind == 'happy':
        # ^ ^：往上彎的弧
        fr.put([(x0, y0 + 2), (x0 + 1, y0 + 1), (x0 + 2, y0 + 2)], LID)
    elif kind == 'squint':
        # > <（打哈欠、伸懶腰）
        if not mirror:
            fr.put([(x0, y0), (x0 + 1, y0 + 1), (x0 + 2, y0 + 1), (x0, y0 + 2)], LID)
        else:
            fr.put([(x0 + 2, y0), (x0 + 1, y0 + 1), (x0, y0 + 1), (x0 + 2, y0 + 2)], LID)


def head_front(fr, cx, cy, eyes='open', look=0, ear_l=0, ear_r=0, mouth='w', blush=False, back=False):
    """正面的頭（cx,cy＝頭的中心；約 14×11）。ear_l/ear_r：耳朵往下壓幾 px（抖耳朵、被摸時貼平）。"""
    head = ell(cx, cy, 6.3, 5.2) | ell(cx, cy + 1.3, 6.9, 3.8)
    el = poly([(cx - 6.9, cy - 0.2 + ear_l * 0.5), (cx - 5.6 + ear_l * 0.6, cy - 8.8 + ear_l * 1.5), (cx - 1.3, cy - 4.6)])
    er = poly([(cx + 6.9, cy - 0.2 + ear_r * 0.5), (cx + 5.6 - ear_r * 0.6, cy - 8.8 + ear_r * 1.5), (cx + 1.3, cy - 4.6)])
    fr.fill(el, FUR, group='head')
    fr.fill(er, FUR, group='head')
    fr.fill(head, FUR, group='head', blur=1.5)
    if back:
        return
    inner_cut = ell(cx, cy + 0.3, 5.4, 4.6)
    il = poly([(cx - 5.7, cy - 1.8 + ear_l * 0.5), (cx - 5.1 + ear_l * 0.5, cy - 7.0 + ear_l * 1.4), (cx - 2.8, cy - 4.2)]) & ~inner_cut
    ir = poly([(cx + 5.7, cy - 1.8 + ear_r * 0.5), (cx + 5.1 - ear_r * 0.5, cy - 7.0 + ear_r * 1.4), (cx + 2.8, cy - 4.2)]) & ~inner_cut
    fr.fill(il, PINK, line=False, lv=np.full((H, W), 2, np.int8), fur=False)
    fr.fill(ir, PINK, line=False, lv=np.full((H, W), 1, np.int8), fur=False)
    ix = int(np.floor(cx))
    iy = int(np.floor(cy))
    # 眼睛：左眼 ix-5..ix-3、右眼 ix+2..ix+4（對稱於中線）
    eye_px(fr, ix - 5, iy - 2, eyes, False, look)
    eye_px(fr, ix + 2, iy - 2, eyes, True, look)
    # 鼻子（2px 粉紅）＋嘴
    fr.put([(ix - 1, iy + 2), (ix, iy + 2)], PINK[3])
    if mouth == 'w':
        fr.put([(ix - 2, iy + 3), (ix + 1, iy + 3)], MOUTH)
    elif mouth == 'open':
        fr.put([(ix - 1, iy + 3), (ix, iy + 3)], PINK[1])
    elif mouth == 'smile':
        fr.put([(ix - 2, iy + 3), (ix + 1, iy + 3)], MOUTH)
        fr.put([(ix - 1, iy + 3), (ix, iy + 3)], PINK[2])
    elif mouth == 'yawn':
        fr.put([(ix - 1, iy + 3), (ix, iy + 3), (ix - 1, iy + 4), (ix, iy + 4)], PINK[1])
        fr.put([(ix - 1, iy + 3)], hx('#fff4fa'))
    if blush:
        fr.put([(ix - 6, iy + 2), (ix - 5, iy + 2)], BLUSH)
        fr.put([(ix + 4, iy + 2), (ix + 5, iy + 2)], BLUSH)
    # 鬍鬚（外輪廓之外的半透明細線）
    fr.overlay([(ix - 8, iy + 1), (ix - 9, iy + 1), (ix - 8, iy + 3), (ix - 9, iy + 4)], WHISKER)
    fr.overlay([(ix + 7, iy + 1), (ix + 8, iy + 1), (ix + 7, iy + 3), (ix + 8, iy + 4)], WHISKER)


def collar_front(fr, cx, y):
    """項圈（y＝項圈那一列）：紫色緞帶＋畫面左側的蝴蝶結＋正中間的金色小鈴鐺。"""
    ix = int(np.floor(cx))
    band = rect(ix - 4, y, ix + 3, y) & fr.a
    fr.fill(band, RIBBON, lv=np.full((H, W), 3, np.int8), line=True, group='collar', fur=False)
    fr.put([(x, y + 1) for x in range(ix - 3, ix + 3)], RIBBON[1])
    # 蝴蝶結
    fr.put([(ix - 5, y - 1), (ix - 6, y - 1), (ix - 5, y + 1), (ix - 6, y + 1)], RIBBON[3])
    fr.put([(ix - 5, y)], RIBBON[1])
    # 鈴鐺（2×2，左上亮、右下暗）
    fr.put([(ix - 1, y + 1)], GOLD[4])
    fr.put([(ix, y + 1)], GOLD[3])
    fr.put([(ix - 1, y + 2)], GOLD[2])
    fr.put([(ix, y + 2)], GOLD[1])


def tail_mask(pts, r0=1.5, r1=1.1):
    return bez(pts, r0, r1)


def legs_front(fr, cx, top, bl, br, mat=None, group='body'):
    """兩隻前腳（同一個 group：不畫成一根根柱子）＋腳掌亮點＋兩腳之間一條暗縫。bl/br：左右腳最下面那列的 y。"""
    mat = mat or FUR
    m = cap(cx - 1.9, top, cx - 1.9, bl - 0.5, 1.35) | cap(cx + 1.9, top, cx + 1.9, br - 0.5, 1.35)
    fr.fill(m, mat, group=group, blur=0.8)
    ix = int(np.floor(cx))
    fr.put([(ix - 3, int(bl)), (ix - 2, int(bl))], mat[3], fur=True)
    fr.put([(ix + 1, int(br)), (ix + 2, int(br))], mat[3], fur=True)
    gap_bottom = int(min(bl, br))
    fr.put([(ix - 1, y) for y in range(int(top) + 2, gap_bottom + 1)] +
           [(ix, y) for y in range(int(top) + 2, gap_bottom + 1)], mat[0], fur=True)


def pose_sit(eyes='open', look=0, tail=0, ear_l=0, ear_r=0, mouth='w', blush=False, dy=0, paw=None,
             tongue=False, head_dy=0, head_dx=0, tail_up=None, puff=False, squash=0):
    """正面坐姿（坐、眨眼、理毛、被摸、嚇一跳、打哈欠都從這裡變化）。dy：整隻往上移（跳）。"""
    fr = Fr()
    cx = CX
    base = 31 - dy                # 身體最下面一列
    if tail_up is not None:
        w = tail_up
        tm = tail_mask([(cx + 3.5, base - 3), (cx + 8.5, base - 5), (cx + 8 + w, base - 12), (cx + 5.5 + w * 2, base - 17)],
                       1.9 if puff else 1.5, 1.5 if puff else 1.1)
        fr.fill(tm, FUR, group='tail', blur=1.0)
    else:
        tx = (0, 2, -2)[tail]
        tm = tail_mask([(cx + 3.5, base - 1), (cx + 9.0, base + 0.2), (cx + 9.3, base - 5), (cx + 7.5 + tx, base - 8.5 + abs(tx) * 0.4)])
        fr.fill(tm, FUR, group='tail', blur=1.0)
    by = base - 4.2 + squash * 0.5
    # 身體＋兩側後腿（同一個 group：圓圓一團，不要一根根柱子）
    body = (ell(cx, by, 5.3, 4.7 - squash * 0.5) | ell(cx, base - 2.0, 5.9, 2.6)
            | ell(cx - 4.0, base - 1.9, 2.7, 2.5) | ell(cx + 4.0, base - 1.9, 2.7, 2.5))
    fr.fill(body, FUR, group='body', blur=1.8)
    hy = base - 13 + head_dy
    if paw is None:
        legs_front(fr, cx, base - 4.2, base, base, group='legs')
    else:
        m = cap(cx + 1.9, by - 1.5, cx + 1.9, base - 0.5, 1.35)
        fr.fill(m, FUR, group='legs', blur=0.8)
        fr.put([(int(cx) + 1, base), (int(cx) + 2, base)], FUR[3], fur=True)
    ixc = int(np.floor(cx))
    fr.put([(ixc - 1, int(by) - 3), (ixc, int(by) - 3), (ixc - 1, int(by) - 2)], FUR[3], fur=True)
    if puff:
        ix = int(np.floor(cx))
        fr.put([(ix - 6, int(by) - 1), (ix - 7, int(by) + 1), (ix + 5, int(by) - 1), (ix + 6, int(by) + 1)], FUR[2], fur=True)
    head_front(fr, cx + head_dx, hy, eyes=eyes, look=look, ear_l=ear_l, ear_r=ear_r, mouth=mouth, blush=blush)
    collar_front(fr, cx + head_dx * 0.5, int(np.floor(hy)) + 5)
    if paw is not None:
        # 理毛：左前腳舉到嘴邊（舔的那一下有粉紅舌頭）
        px, py = paw
        fr.fill(cap(cx - 1.9, by - 1, px, py, 1.5), FUR, group='paw', blur=0.8)
        fr.put([(int(px) - 1, int(py) - 1), (int(px), int(py) - 1)], FUR[4], fur=True)
        if tongue:
            fr.put([(int(px) + 1, int(py))], PINK[3])
    return fr


def pose_walk_down(f):
    """朝下走：f=0..3（0 站、1 左腳前、2 站、3 右腳前）。"""
    fr = Fr()
    cx = CX
    step = (0, 1, 0, -1)[f]
    bob = 1 if step else 0
    sway = (0, 1, 0, -1)[f]
    tm = tail_mask([(cx + 2, 26 + bob), (cx + 5.5, 24 + bob), (cx + 6.5 + sway, 18 + bob), (cx + 4.5 + sway * 2, 14.5 + bob)])
    fr.fill(tm, FUR, group='tail', blur=1.0)
    fr.fill(cap(cx - 3.6, 26 + bob, cx - 3.7, 30.6 - (step < 0), 1.3), FUR_BACK, group='bl')
    fr.fill(cap(cx + 3.6, 26 + bob, cx + 3.7, 30.6 - (step > 0), 1.3), FUR_BACK, group='br')
    fr.fill(ell(cx, 25.8 + bob, 4.8, 3.8), FUR, group='body', blur=1.4)
    legs_front(fr, cx, 25 + bob, 31 if step >= 0 else 30, 31 if step <= 0 else 30, group='legs')
    hy = 19.0 + bob
    head_front(fr, cx, hy)
    collar_front(fr, cx, int(np.floor(hy)) + 5)
    return fr


def pose_walk_up(f):
    """朝上走（背影）：耳朵背面、後腦勺、尾巴豎起來在中間搖。"""
    fr = Fr()
    cx = CX
    step = (0, 1, 0, -1)[f]
    bob = 1 if step else 0
    sway = (0, 1, 0, -1)[f]
    fr.fill(cap(cx - 2.0, 25 + bob, cx - 2.0, 30.6 - (step > 0), 1.3), FUR_BACK, group='fl')
    fr.fill(cap(cx + 2.0, 25 + bob, cx + 2.0, 30.6 - (step < 0), 1.3), FUR_BACK, group='fr')
    hy = 19.0 + bob
    head_front(fr, cx, hy, back=True)
    fr.fill(ell(cx, 26.0 + bob, 5.0, 3.9), FUR, group='body', blur=1.4)
    fr.fill(cap(cx - 3.4, 27 + bob, cx - 3.5, (31 if step >= 0 else 30) - 0.4, 1.45), FUR, group='bl', blur=0.8)
    fr.fill(cap(cx + 3.4, 27 + bob, cx + 3.5, (31 if step <= 0 else 30) - 0.4, 1.45), FUR, group='br', blur=0.8)
    ix = int(np.floor(cx))
    y = int(np.floor(hy)) + 5
    fr.put([(x, y) for x in range(ix - 3, ix + 3)], RIBBON[2])
    fr.put([(ix + 3, y - 1), (ix + 4, y - 1), (ix + 3, y + 1), (ix + 4, y + 1)], RIBBON[3])
    fr.put([(ix + 3, y)], RIBBON[1])
    tm = tail_mask([(cx + 0.5, 29 + bob), (cx + 2.5, 26 + bob), (cx + 6 + sway, 24 + bob), (cx + 7 + sway * 2, 19 + bob)], 1.5, 1.1)
    fr.fill(tm, FUR, group='tail', blur=1.0)
    return fr


def side_head(fr, cx, cy, eyes='open', mouth='w', ears_dn=0):
    """3/4 偏側朝左的頭：近的眼睛 3×4、遠的眼睛 2×4 靠臉的左緣、鼻子在最左邊。"""
    ear_far = poly([(cx + 0.4, cy - 4.8), (cx + 3.2, cy - 9.0 + ears_dn), (cx + 6.0, cy - 1.6)])
    fr.fill(ear_far, FUR_BACK, group='earf')
    ear_near = poly([(cx - 6.4, cy - 0.8), (cx - 5.4, cy - 9.0 + ears_dn), (cx - 1.0, cy - 4.8)])
    head = ell(cx, cy, 6.1, 5.2) | ell(cx - 0.4, cy + 1.3, 6.7, 3.8)
    fr.fill(ear_near, FUR, group='head')
    fr.fill(head, FUR, group='head', blur=1.5)
    inner = poly([(cx - 5.2, cy - 2.2), (cx - 4.8, cy - 7.2 + ears_dn), (cx - 2.4, cy - 4.4)]) & ~ell(cx, cy + 0.3, 5.2, 4.6)
    fr.fill(inner, PINK, line=False, lv=np.full((H, W), 2, np.int8), fur=False)
    ix, iy = int(np.floor(cx)), int(np.floor(cy))
    if eyes == 'open':
        eye_px(fr, ix - 1, iy - 2, 'open', False, -1)
        E = EYE
        fr.stamp(ix - 5, iy - 2, ['ab', 'Pc', 'Pd', 'bb'], {'a': E[1], 'b': E[2], 'c': E[3], 'd': E[4], 'P': PUPIL})
    else:
        eye_px(fr, ix - 1, iy - 2, eyes, False)
        eye_px(fr, ix - 5, iy - 2, eyes, False)
    fr.put([(ix - 6, iy + 2), (ix - 5, iy + 2)], PINK[3])
    if mouth == 'open':
        fr.put([(ix - 5, iy + 3), (ix - 4, iy + 3)], PINK[1])
    else:
        fr.put([(ix - 5, iy + 3)], MOUTH)
    fr.put([(ix - 2, iy + 2), (ix - 1, iy + 2)], BLUSH)
    fr.overlay([(ix - 8, iy + 1), (ix - 9, iy + 1), (ix - 8, iy + 3), (ix - 9, iy + 4)], WHISKER)
    return ix, iy


def pose_walk_side(f):
    """側面朝左走。"""
    fr = Fr()
    step = (0, 1, 0, -1)[f]
    bob = 1 if step else 0
    sway = (0, -1, 0, 1)[f]
    tm = tail_mask([(27.5, 24 + bob), (31, 22.5 + bob), (32 + sway, 17.5 + bob), (30.5 + sway * 2, 14 + bob)])
    fr.fill(tm, FUR, group='tail', blur=1.0)
    a = 1.6 * step
    fr.fill(cap(17.5, 26 + bob, 17.5 - a, 30.6 - (step < 0), 1.25), FUR_BACK, group='fl2')
    fr.fill(cap(25.5, 26 + bob, 25.5 + a, 30.6 - (step > 0), 1.25), FUR_BACK, group='bl2')
    fr.fill(ell(21.8, 25.4 + bob, 6.8, 3.7), FUR, group='body', blur=1.5)
    fr.fill(cap(16.2, 26 + bob, 16.2 + a, 30.6 - (step > 0), 1.4), FUR, group='fl', blur=0.8)
    fr.fill(cap(26.8, 26 + bob, 26.8 - a, 30.6 - (step < 0), 1.45), FUR, group='bl', blur=0.8)
    fr.fill(ell(26.2, 25.6 + bob, 2.8, 3.0), FUR, group='hip', blur=1.0)
    ix, iy = side_head(fr, 13.0, 19.5 + bob)
    y = iy + 5
    band = rect(ix - 3, y, ix + 4, y) & fr.a
    fr.fill(band, RIBBON, lv=np.full((H, W), 3, np.int8), group='collar', fur=False)
    fr.put([(ix + 5, y - 1), (ix + 6, y - 1), (ix + 5, y + 1), (ix + 6, y + 1)], RIBBON[3])
    fr.put([(ix + 5, y)], RIBBON[1])
    fr.put([(ix - 2, y + 1)], GOLD[4])
    fr.put([(ix - 1, y + 1)], GOLD[2])
    return fr


def pose_sleep(f):
    """捲成一團睡：頭靠在左前方、尾巴繞到前面。f：0..2 呼吸（身體起伏）、3 耳朵抖。"""
    fr = Fr()
    br = (0.0, 0.5, 0.9, 0.0)[f]
    fr.fill(ell(21.5, 27.6 - br * 0.5, 9.0, 3.8 + br * 0.5), FUR, group='body', blur=1.8)
    cx, cy = 14.6, 26.8
    tw = 1 if f == 3 else 0
    e2 = poly([(cx - 0.4, cy - 3.6), (cx + 2.4, cy - 7.4), (cx + 4.8, cy - 2.2)])
    fr.fill(e2, FUR_BACK, group='e2')
    e1 = poly([(cx - 5.4, cy + 0.2), (cx - 5.8 + tw, cy - 6.8 + tw), (cx - 1.8, cy - 3.6)])
    fr.fill(e1, FUR, group='head')
    head = ell(cx, cy, 5.5, 4.2) | ell(cx - 0.3, cy + 1.0, 5.9, 3.2)
    fr.fill(head, FUR, group='head', blur=1.4)
    inner = poly([(cx - 4.6, cy - 1.0), (cx - 4.9 + tw, cy - 5.2 + tw), (cx - 2.6, cy - 3.0)]) & ~ell(cx, cy + 0.3, 4.6, 3.6)
    fr.fill(inner, PINK, line=False, lv=np.full((H, W), 1, np.int8), fur=False)
    ix, iy = int(np.floor(cx)), int(np.floor(cy))
    eye_px(fr, ix - 4, iy - 1, 'closed')
    eye_px(fr, ix + 1, iy - 1, 'closed', True)
    fr.put([(ix - 1, iy + 2)], PINK[3])
    fr.put([(ix - 4, iy + 2), (ix + 2, iy + 2)], BLUSH)
    tm = tail_mask([(29.5, 29.2), (28.5, 32.2), (22.0, 32.0), (18.0, 30.8)], 1.5, 1.2) & (YY <= 31)
    fr.fill(tm, FUR, group='tail', blur=0.9)
    fr.put([(ix + 3, iy + 4), (ix + 4, iy + 4)], RIBBON[2])
    fr.put([(ix + 4, iy + 5)], GOLD[3])
    return fr


def pose_stretch(f):
    """伸懶腰（側面朝左）：前腳往前伸、胸口貼地、屁股翹高、尾巴豎直。"""
    fr = Fr()
    deep = 1.0 if f == 1 else 0.4
    tm = tail_mask([(28, 22 - deep * 2), (31, 19 - deep * 2), (31.5, 14 - deep), (30, 10 - deep)])
    fr.fill(tm, FUR, group='tail', blur=1.0)
    fr.fill(cap(25.0, 24, 25.2, 30.6, 1.25), FUR_BACK, group='bl2')
    fr.fill(cap(27.2, 24, 27.4, 30.6, 1.45), FUR, group='bl', blur=0.8)
    fr.fill(cap(16.5, 27.0 + deep, 25.5, 23.0 - deep, 3.4), FUR, group='body', blur=1.5)
    fr.fill(cap(15, 30.0, 7.5 - deep * 2, 30.5, 1.25), FUR_BACK, group='fl2')
    fr.fill(cap(16, 30.2, 9.0 - deep * 2, 30.6, 1.35), FUR, group='fl', blur=0.7)
    ix, iy = side_head(fr, 12.5, 24.8 + deep, eyes='squint' if f == 1 else 'closed', mouth='open' if f == 1 else 'w', ears_dn=1)
    return fr


# ───────────── 特效小圖（格子正中央） ─────────────

def fx_icon(rows, cmap):
    fr = Fr()
    h = len(rows)
    w = max(len(r) for r in rows)
    x0 = int(CX - w / 2)
    y0 = int(H / 2 - h / 2)
    fr.stamp(x0, y0, rows, cmap)
    return fr


HEART = ['.ab.ab.', 'acddbbb', 'aedcccb', 'acccccb', '.acccb.', '..acb..', '...b...']
HEART_S = ['ab.ab', 'eccbb', 'acccb', '.acb.', '..b..']
HMAP = {'a': hx('#d84a7c'), 'b': hx('#b8336a'), 'c': hx('#f06a98'), 'd': hx('#ff9cbc'), 'e': hx('#ffffff')}
ZS = ['aaaa', '..b.', '.b..', 'bbbb']
ZB = ['aaaaa', '...b.', '..b..', '.b...', 'bbbbb']
ZMAP = {'a': hx('#d6d2ff'), 'b': hx('#a6a0ee')}
NOTE = ['..aa', '..ab', '..a.', '..a.', 'cca.', 'cdc.', '.cc.']
NMAP = {'a': hx('#f6d46a'), 'b': hx('#dba63a'), 'c': hx('#dba63a'), 'd': hx('#fff4b8')}
QM = ['.aa.', 'a..b', '...b', '..b.', '.b..', '....', '.b..']
QMAP = {'a': hx('#fff4b8'), 'b': hx('#f6d46a')}


def pose_cushion():
    """貓窩：紫色圓坐墊（頂面＋側面一圈、金色滾邊與四個流蘇小點）。"""
    fr = Fr()
    fx, fy = CUSHION_FOOT
    cx = fx + 0.5
    side = ell(cx, fy - 0.5, 14.2, 5.0) | (rect(int(cx - 14), fy - 5, int(cx + 13), fy - 1) & (np.abs(PX - cx) <= 14.2))
    fr.fill(side, CUSH, sh='soft', blur=1.0, fur=False)
    top = ell(cx, fy - 3.5, 13.6, 4.8)
    fr.fill(top, CUSH_TOP, sh='soft', blur=2.2, k=2.0, bias=0.12, fur=False)
    # 頂面中間凹下去一點（貓睡的位置）
    dip = ell(cx + 0.5, fy - 3.0, 8.0, 2.6)
    fr.rgb[dip & top] = np.array(CUSH_TOP[1])
    fr.rgb[ell(cx + 0.5, fy - 3.4, 6.5, 1.7) & top] = np.array(CUSH_TOP[0])
    # 金色滾邊（頂面邊緣下方一圈）
    rimm = top & ~shiftm(top, 0, -1) & (PY > fy - 3.5)
    fr.rgb[rimm] = np.array(GOLD[2])
    # 側面的縫線小點
    for x in range(int(cx - 11), int(cx + 12), 4):
        yy = int(fy - 0.5 + 4.0 * np.sqrt(max(0.0, 1 - ((x + 0.5 - cx) / 14.2) ** 2))) - 1
        if 0 <= yy < H and fr.a[yy, x]:
            fr.rgb[yy, x] = np.array(GOLD[3])
    return fr


# ───────────── 組表 ─────────────

def build_frames():
    """回傳 {(row, col): Image}。"""
    F = {}
    for c in range(4):
        F[(ROW_WALK_DOWN, c)] = pose_walk_down(c).render()
        F[(ROW_WALK_SIDE, c)] = pose_walk_side(c).render()
        F[(ROW_WALK_UP, c)] = pose_walk_up(c).render()
    # 坐
    F[(ROW_SIT, 0)] = pose_sit().render()
    F[(ROW_SIT, 1)] = pose_sit(tail=1).render()
    F[(ROW_SIT, 2)] = pose_sit(tail=2).render()
    F[(ROW_SIT, 3)] = pose_sit(eyes='closed').render()
    F[(ROW_SIT, 4)] = pose_sit(ear_r=2).render()
    F[(ROW_SIT, 5)] = pose_sit(look=-1, head_dy=-1).render()
    # 理毛
    F[(ROW_GROOM, 0)] = pose_sit(eyes='closed', paw=(18.6, 22.6), head_dy=1).render()
    F[(ROW_GROOM, 1)] = pose_sit(eyes='closed', paw=(18.6, 22.6), head_dy=1, tongue=True, mouth='none').render()
    F[(ROW_GROOM, 2)] = pose_sit(eyes='closed', paw=(18.6, 23.4), head_dy=2, mouth='none').render()
    F[(ROW_GROOM, 3)] = pose_sit(eyes='closed', paw=(18.6, 23.4), head_dy=2, tongue=True, mouth='none').render()
    # 睡
    for c in range(4):
        F[(ROW_SLEEP, c)] = pose_sleep(c).render()
    # 被摸
    F[(ROW_HAPPY, 0)] = pose_sit(eyes='happy', blush=True, mouth='smile', head_dx=-1, ear_l=1, ear_r=1, tail_up=0).render()
    F[(ROW_HAPPY, 1)] = pose_sit(eyes='happy', blush=True, mouth='smile', head_dx=-2, head_dy=1, ear_l=2, ear_r=2, tail_up=1).render()
    F[(ROW_HAPPY, 2)] = pose_sit(eyes='happy', blush=True, mouth='smile', head_dx=-2, head_dy=1, ear_l=2, ear_r=2, tail_up=-1).render()
    F[(ROW_HAPPY, 3)] = pose_sit(eyes='happy', blush=True, mouth='open', head_dx=-1, ear_l=1, ear_r=1, tail_up=0).render()
    # 伸懶腰／嚇一跳／睡眼惺忪／打哈欠
    F[(ROW_ACT, 0)] = pose_stretch(0).render()
    F[(ROW_ACT, 1)] = pose_stretch(1).render()
    F[(ROW_ACT, 2)] = pose_sit(eyes='wide', dy=4, puff=True, tail_up=0, mouth='open').render()
    F[(ROW_ACT, 3)] = pose_sit(eyes='wide', squash=2, head_dy=1, mouth='w').render()
    F[(ROW_ACT, 4)] = pose_sit(eyes='half', ear_l=1, ear_r=1).render()
    F[(ROW_ACT, 5)] = pose_sit(eyes='squint', mouth='yawn', ear_l=2, ear_r=2, head_dy=-1).render()
    # 特效
    F[(ROW_FX, 0)] = fx_icon(HEART, HMAP).render(rim=False)
    F[(ROW_FX, 1)] = fx_icon(HEART_S, HMAP).render(rim=False)
    F[(ROW_FX, 2)] = fx_icon(ZS, ZMAP).render(rim=False)
    F[(ROW_FX, 3)] = fx_icon(ZB, ZMAP).render(rim=False)
    F[(ROW_FX, 4)] = fx_icon(NOTE, NMAP).render(rim=False)
    F[(ROW_FX, 5)] = fx_icon(QM, QMAP).render(rim=False)
    F[(ROW_PROPS, 0)] = pose_cushion().render(rim=False)
    return F


def check_cell(img, r, c):
    """腳底基準線：除了在空中的那格與特效／道具，最下面不透明的一列一定是 FOOT。"""
    a = np.asarray(img)[..., 3] > 0
    rows = np.nonzero(a.any(1))[0]
    if len(rows) == 0:
        return f'({r},{c}) 是空的'
    if r in (ROW_FX, ROW_PROPS) or (r, c) == (ROW_ACT, 2):
        return None
    if rows.max() != FOOT:
        return f'({r},{c}) 腳底在第 {rows.max()} 列（應該是 {FOOT}）'
    cols = np.nonzero(a.any(0))[0]
    if cols.min() < 1 or cols.max() > W - 2 or rows.min() < 1:
        return f'({r},{c}) 貼到格子邊了'
    return None


def build_sheet(F):
    sheet = Image.new('RGBA', (W * COLS, H * ROWS), (0, 0, 0, 0))
    errs = []
    for (r, c), im in F.items():
        e = check_cell(im, r, c)
        if e:
            errs.append(e)
        sheet.alpha_composite(im, (c * W, r * H))
    return sheet, errs


# ───────────── 預覽 ─────────────

WOOD = (120, 78, 48)
NIGHT_FLOOR = (52, 40, 58)
ROW_LEN = {ROW_WALK_DOWN: 4, ROW_WALK_SIDE: 4, ROW_WALK_UP: 4, ROW_SIT: 6, ROW_GROOM: 4, ROW_SLEEP: 4,
           ROW_HAPPY: 4, ROW_ACT: 6, ROW_FX: 6, ROW_PROPS: 1}


def wood_bg(w, h, night=False):
    """木地板（橫向木條＋縫）。night：乘 BrewRoomLayout.NightTint。"""
    base = np.array([150, 98, 60], float)
    img = np.zeros((h, w, 3), float)
    for y in range(h):
        band = (y // 22) % 3
        tone = base * (0.92 + 0.06 * band)
        img[y, :] = tone
        if y % 22 == 0:
            img[y, :] = base * 0.62
    if night:
        img *= np.array([0.56, 0.55, 0.76])
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert('RGBA')


def preview(F, sheet, out):
    os.makedirs(out, exist_ok=True)
    S = 6
    big = sheet.resize((sheet.width * S, sheet.height * S), Image.NEAREST)
    for name, night in (('sheet_wood', False), ('sheet_night', True)):
        bg = wood_bg(big.width, big.height, night)
        # 格線
        d = ImageDraw.Draw(bg)
        for c in range(COLS + 1):
            d.line([(c * W * S, 0), (c * W * S, big.height)], fill=(0, 0, 0, 90))
        for r in range(ROWS + 1):
            d.line([(0, r * H * S), (big.width, r * H * S)], fill=(0, 0, 0, 90))
            d.line([(0, r * H * S + (FOOT + 1) * S), (big.width, r * H * S + (FOOT + 1) * S)], fill=(255, 220, 120, 60))
        bg.alpha_composite(big)
        bg.convert('RGB').save(os.path.join(out, name + '.png'))

    # GIF：放大 6 倍、木地板，照 RoomCat 的速度
    def gif(name, seq, fps, flip=False, night=False):
        frames = []
        for (r, c) in seq:
            im = F[(r, c)]
            if flip:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            bg = wood_bg(W * S, H * S, night)
            bg.alpha_composite(im.resize((W * S, H * S), Image.NEAREST))
            frames.append(bg.convert('P', palette=Image.ADAPTIVE))
        frames[0].save(os.path.join(out, name + '.gif'), save_all=True, append_images=frames[1:],
                       duration=int(1000 / fps), loop=0, disposal=2)

    gif('gif_walk_down', [(ROW_WALK_DOWN, c) for c in range(4)], 8)
    gif('gif_walk_side', [(ROW_WALK_SIDE, c) for c in range(4)], 8)
    gif('gif_walk_side_right', [(ROW_WALK_SIDE, c) for c in range(4)], 8, flip=True)
    gif('gif_walk_up', [(ROW_WALK_UP, c) for c in range(4)], 8)
    gif('gif_sit', [(ROW_SIT, i) for i in (0, 0, 1, 1, 0, 0, 2, 2, 0, 3, 0, 0, 4, 0)], 5)
    gif('gif_groom', [(ROW_GROOM, i) for i in (0, 1, 0, 1, 2, 3, 2, 3)], 5)
    gif('gif_sleep', [(ROW_SLEEP, i) for i in (0, 1, 2, 2, 1, 0, 0, 3, 0)], 3, night=True)
    gif('gif_petted', [(ROW_HAPPY, i) for i in (0, 1, 2, 1, 2, 3)], 5)
    gif('gif_wake', [(ROW_SLEEP, 0), (ROW_ACT, 4), (ROW_ACT, 4), (ROW_ACT, 5), (ROW_ACT, 5), (ROW_ACT, 4), (ROW_SIT, 3), (ROW_SIT, 0)], 4)
    gif('gif_hop_stretch', [(ROW_SIT, 0), (ROW_ACT, 2), (ROW_ACT, 3), (ROW_SIT, 0), (ROW_ACT, 0), (ROW_ACT, 1), (ROW_ACT, 1), (ROW_ACT, 0)], 5)

    lineup(F, out)
    room_mock(F, out)


def witch_cells():
    p = os.path.join(RES, 'witch8', 'base.png')
    if not os.path.exists(p):
        return []
    im = Image.open(p).convert('RGBA')
    cw, ch = im.width // 8, im.height // 25
    return [im.crop((c * cw, 0, (c + 1) * cw, ch)) for c in (0, 2, 4)]


def scale_img(im, k):
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.NEAREST)


def lineup(F, out):
    """跟女巫並排：1:1（遊戲畫面大小 ×1.6）與 3 倍。"""
    wc = witch_cells()
    cats = [F[(ROW_SIT, 0)], F[(ROW_WALK_SIDE, 0)], F[(ROW_WALK_DOWN, 1)], F[(ROW_HAPPY, 1)], F[(ROW_SLEEP, 0)], F[(ROW_GROOM, 1)]]
    for k, name in ((1, 'lineup_1x'), (3, 'lineup_3x')):
        items = [scale_img(w, GAME_SCALE * k) for w in wc[:1]] + [scale_img(c, GAME_SCALE * k) for c in cats]
        wtot = sum(i.width for i in items) + 10 * k * len(items) + 20 * k
        hmax = max(i.height for i in items) + 16 * k
        for night in (False, True):
            bg = wood_bg(wtot, hmax, night)
            x = 10 * k
            for it in items:
                # 腳底對齊：女巫格子底邊往上 3px、貓也是 3px
                bg.alpha_composite(it, (x, hmax - 8 * k - it.height))
                x += it.width + 10 * k
            bg.convert('RGB').save(os.path.join(out, f'{name}{"_night" if night else ""}.png'))


# ───────────── 房間合成預覽（讀 BrewRoomLayout.cs，跟 BrewRoom.PlayerOrder 同一個排序）─────────────

def _layout():
    import re
    src = open(os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'BrewRoomLayout.cs'), encoding='utf-8').read()
    N = r'(-?\d+(?:\.\d+)?)f'
    pieces = []
    pat = (r'new BrewPiece\("([^"]+)",\s*new\[\]\s*\{\s*"([^"]+)"[^}]*\},\s*' + N + r',\s*(?:null|new\[\]\s*\{[^}]*\}),\s*BrewKind\.(\w+),\s*'
           + r',\s*'.join([N] * 4) + r',\s*(-?\d+),\s*' + r',\s*'.join([N] * 8))
    for m in re.finditer(pat, src, re.S):
        g = m.groups()
        pieces.append(dict(name=g[0], frame=g[1], kind=g[3], x=float(g[4]), y=float(g[5]), px=float(g[6]), py=float(g[7]),
                           order=int(g[8]), u0=float(g[9]), u1=float(g[10]), v0=float(g[11]), v1=float(g[12]),
                           rx0=float(g[13]), ry0=float(g[14]), rx1=float(g[15]), ry1=float(g[16])))
    return pieces


def _uv(x, y):
    dx, dy = x + 100.0, 162.5 - y
    return dy + dx * 0.5, dy - dx * 0.5


def _order(pieces, fx, fy, w, h):
    u, v = _uv(fx, fy)
    x0, x1, y0, y1 = fx - w * 0.35, fx + w * 0.35, fy, fy + h * 0.9
    lo, hi = None, None
    for p in pieces:
        if p['kind'] != 'Stand' or p['name'] == 'cat':
            continue
        if x1 <= p['rx0'] or p['rx1'] <= x0 or y1 <= p['ry0'] or p['ry1'] <= y0:
            continue
        if u >= p['u1'] or v >= p['v1']:
            front = True
        elif u <= p['u0'] or v <= p['v0']:
            front = False
        else:
            front = u + v > (p['u0'] + p['u1'] + p['v0'] + p['v1']) / 2
        if front:
            lo = p['order'] if lo is None else max(lo, p['order'])
        else:
            hi = p['order'] if hi is None else min(hi, p['order'])
    if lo is None and hi is None:
        return round(-fy)
    if lo is None:
        return hi - 1
    return lo + 1


def _cat_consts():
    """從 RoomCat.cs 讀兩個貓窩位置（細畫房間畫好的／自己擺坐墊的）與睡在畫好的貓窩裡的抬高量。"""
    import re
    src = open(os.path.join(ROOT, 'Assets', 'Scripts', 'Core', 'RoomCat.cs'), encoding='utf-8').read()

    def v(name):
        m = re.search(name + r'\s*=\s*new\(\s*(-?[\d.]+)f\s*,\s*(-?[\d.]+)f', src)
        return float(m.group(1)), float(m.group(2))
    m = re.search(r'DrawnBedLift\s*=\s*(-?[\d.]+)f', src)
    return v('DrawnBedAt'), v('OwnBedAt'), float(m.group(1)) if m else 0.0


def _glows():
    import re
    src = open(os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'BrewRoomLayout.cs'), encoding='utf-8').read()
    N = r'(-?\d+(?:\.\d+)?)f'
    return [tuple(float(x) for x in m.groups()) for m in re.finditer(r'new BrewGlow\(' + r',\s*'.join([N] * 4), src)]


def room_mock(F, out):
    """
    藥水室合成（用專案裡現在的房間美術：細畫版 rooms/brew8/ 有的那張就用它，跟 GameArt.BrewTex 一樣逐張退回 rooms/brew/）：
      room_day_pet／room_night_pet    貓坐在女巫旁邊、頭上 E＋愛心提示
      room_day_petted                 被摸的那一刻
      room_day_sleep／room_night_sleep 在貓窩睡覺（細畫版地毯畫好的貓窩；沒有就是 RoomCat 自己擺的紫坐墊）
    每張都出 _1x（遊戲畫面原大小的裁切）、_3x（放大）與 _full（整間）。夜晚：家具乘 NightTint、加上光暈（同 BrewRoom）。
    """
    pieces = _layout()
    brew8 = os.path.join(RES, 'rooms', 'brew8')

    def room_png(name):
        p8 = os.path.join(brew8, name + '.png')
        return p8 if os.path.exists(p8) else os.path.join(RES, 'rooms', 'brew', name + '.png')

    drawn_bed = os.path.exists(os.path.join(brew8, 'rug-hearth.png'))
    (dbx, dby), (obx, oby), drawn_lift = _cat_consts()
    bx, by = (dbx, dby) if drawn_bed else (obx, oby)
    lift = drawn_lift if drawn_bed else 2.0

    key = Image.open(os.path.join(RES, 'ui', 'icons8', 'key_e.png')).convert('RGBA')
    key = key.resize((round(key.width * 0.3), round(key.height * 0.3)), Image.NEAREST)
    NT = np.array([0.56, 0.55, 0.76, 1.0])
    glow_src = Image.open(room_png('glow')).convert('RGBA')

    def tint(im, night):
        if not night:
            return im
        a = np.asarray(im).astype(float) * NT
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    def scene(name, night, items, crop):
        shell = Image.open(room_png('shell-night' if night else 'shell-day')).convert('RGBA')
        Wd, Hd = shell.size

        def toi(wx, wy):
            return wx + Wd / 2, Hd / 2 - wy

        layers = []
        for p in pieces:
            if p['name'] == 'cat':
                continue
            im = Image.open(room_png(p['frame'].split('/')[-1])).convert('RGBA')
            lit = p['name'].startswith('candle') or p['name'] == 'fireplace-fire'
            if not lit:
                im = tint(im, night)
            left, top = toi(p['x'] - p['px'], p['y'] + im.height - p['py'])
            layers.append((p['order'] if p['kind'] == 'Stand' else -9500, 0, im, left, top))
        if night:
            for gx, gy, rad, strength in _glows():
                size = max(2, round(rad * 2))
                g = np.asarray(glow_src.resize((size, size), Image.BILINEAR)).astype(float)
                g[..., 0], g[..., 1], g[..., 2] = 255, 196, 120
                g[..., 3] *= 0.6 * strength
                gi = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8))
                l, t = toi(gx - size / 2, gy + size / 2)
                layers.append((8000, 0, gi, l, t))
        for it in items:
            layers.append(it(toi))
        for o, z, im, l, t in sorted(layers, key=lambda q: (q[0], -q[1])):
            shell.alpha_composite(im, (int(round(l)), int(round(t))))
        x0, y0 = toi(crop[0], crop[3])
        x1, y1 = toi(crop[2], crop[1])
        c = shell.crop((int(x0), int(y0), int(x1), int(y1)))
        c.convert('RGB').save(os.path.join(out, name + '_1x.png'))
        c.resize((c.width * 3, c.height * 3), Image.NEAREST).convert('RGB').save(os.path.join(out, name + '_3x.png'))
        shell.convert('RGB').save(os.path.join(out, name + '_full.png'))

    def sprite(im, wx, wy, pivx, pivy, k, order=None, z=0):
        def f(toi):
            big = scale_img(im, k)
            l, t = toi(wx - pivx * k, wy + (im.height - pivy) * k)
            o = order if order is not None else _order(pieces, wx, wy, big.width, big.height)
            return (o, z, big, l, t)
        return f

    def shadow(wx, wy, w):
        def f(toi):
            rx, ry = max(4, w * 0.36), max(2, w * 0.125)
            im = Image.new('RGBA', (int(rx * 2 + 4), int(ry * 2 + 4)), (0, 0, 0, 0))
            ImageDraw.Draw(im).ellipse([2, 2, 2 + rx * 2, 2 + ry * 2], fill=(24, 22, 30, 110))
            l, t = toi(wx - rx - 2, wy + ry * 0.6 + ry + 2)
            return (-8500, 0, im, l, t)
        return f

    wim = Image.open(os.path.join(RES, 'witch8', 'base.png')).convert('RGBA')
    cw, ch = wim.width // 8, wim.height // 25
    witch = wim.crop((0, 0, cw, ch))
    witch_w = wim.crop((6 * cw, 0, 7 * cw, ch))   # 朝西（看向左邊的貓）

    # 貓坐在女巫旁邊（她站著不動 → 貓抬頭看她；看右邊要翻面）＋頭上的 E＋愛心
    wx, wy = 104.0, -150.0
    cx_, cy_ = 62.0, -156.0
    cat_look = F[(ROW_SIT, 5)].transpose(Image.FLIP_LEFT_RIGHT)
    base = [shadow(wx, wy + 3 * GAME_SCALE, 49 * GAME_SCALE), sprite(witch_w, wx, wy, cw / 2, 0, GAME_SCALE), shadow(cx_, cy_, 26)]
    hint = [sprite(key, cx_ - 9, cy_ + 54, key.width / 2, key.height / 2, 1, order=9400),
            sprite(F[(ROW_FX, 0)], cx_ + 11, cy_ + 54, 20, 18, GAME_SCALE, order=9401)]
    pet_crop = (-40, -230, 180, -60)
    for night in (False, True):
        scene('room_%s_pet' % ('night' if night else 'day'), night,
              base + [sprite(cat_look, cx_, cy_, 20, PAD, GAME_SCALE, z=1)] + hint, pet_crop)
    scene('room_day_petted', False, base + [
        sprite(F[(ROW_HAPPY, 1)].transpose(Image.FLIP_LEFT_RIGHT), cx_, cy_, 20, PAD, GAME_SCALE, z=1),
        sprite(F[(ROW_FX, 0)], cx_ + 2, cy_ + 50, 20, 18, GAME_SCALE, order=9300),
        sprite(F[(ROW_FX, 1)], cx_ - 10, cy_ + 64, 20, 18, GAME_SCALE, order=9300)], pet_crop)

    # 在貓窩睡覺（白天、晚上）；女巫站在旁邊
    sleep_crop = (200, -250, 450, -60)
    for night in (False, True):
        items = []
        if not drawn_bed:
            items.append(sprite(tint(F[(ROW_PROPS, 0)], night), bx, by, 20.5, 6.5, GAME_SCALE, order=-9000))
        items += [shadow(bx, by, 34), sprite(F[(ROW_SLEEP, 1)], bx, by + lift * GAME_SCALE, 20, PAD, GAME_SCALE),
                  sprite(F[(ROW_FX, 2)], bx - 14, by + 28, 20, 18, GAME_SCALE, order=9300),
                  sprite(F[(ROW_FX, 3)], bx - 22, by + 46, 20, 18, GAME_SCALE, order=9300),
                  shadow(240, -205 + 3 * GAME_SCALE, 49 * GAME_SCALE), sprite(witch, 240, -205, cw / 2, 0, GAME_SCALE)]
        scene('room_%s_sleep' % ('night' if night else 'day'), night, items, sleep_crop)
    print(f'  房間合成：{"細畫版地毯上畫好的貓窩" if drawn_bed else "自己擺的紫坐墊"} @ ({bx:g}, {by:g})、抬高 {lift:g} 原生 px')


def main():
    args = sys.argv[1:]
    out_dir = OUT_DIR
    prev = None
    if '--out' in args:
        i = args.index('--out')
        out_dir = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    if '--preview' in args:
        i = args.index('--preview')
        prev = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    F = build_frames()
    sheet, errs = build_sheet(F)
    if errs:
        print('⚠️ 格子檢查沒過：')
        for e in errs:
            print('   ', e)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'cat.png')
    sheet.save(path)
    print(f'cat.png {sheet.width}×{sheet.height} → {path}')
    if prev:
        preview(F, sheet, prev)
        print(f'預覽 → {prev}')
    if errs:
        sys.exit(1)


if __name__ == '__main__':
    main()
