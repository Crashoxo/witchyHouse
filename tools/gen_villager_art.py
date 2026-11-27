#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
路人（村民／顧客）走路圖產生器：11 位居民全部用程式點陣畫，**精細度對齊主角女巫（witch8）**。

    python tools/gen_villager_art.py                    # 輸出 Assets/Resources/villagers8/<名字>.png
    python tools/gen_villager_art.py --preview DIR      # 另外輸出排排站、放大走路表、GIF、實景合成到 DIR
    python tools/gen_villager_art.py --out DIR          # 走路表改寫到 DIR（迭代時用，不碰 Assets）
    python tools/gen_villager_art.py --restore          # 刪掉 villagers8/（GameArt 會自動退回舊圖）

── 為什麼又重畫（2026-11-27 第二版）────────────────────────────────────
  第一版是 28×36 邏輯格 ×3 的粗像素 Q 版（兩頭身），站在女巫旁邊像別的遊戲。使用者：「路人要畫得更精緻」。
  這一版照女巫的做法：**原生 1px 像素、遊戲裡跟女巫一樣 ×1.6**（像素大小完全一樣），
  約三頭身、身高跟女巫差不多；每種材質 5 階＋內描線的色相偏移色階（亮部偏暖黃、暗部偏藍紫），
  整隻外圍一圈近黑外輪廓、部件之間是「後面那個部件的深色」內描線（跟女巫一樣是有顏色的內線）。

── 規格（⚠️ GameArt.cs／VillagerAnim.cs 依賴這個，改之前先看 GameArt.UsePixelVillagers 的說明）────
  * 每格 **56×72** 原生像素；一張 4 欄 × 3 列 ＝ **224×216**。11 位全部同一個格子，輸出不放大（PPU 1、Point）。
  * 列 0 朝下、列 1 側面（朝左）、列 2 朝上；欄 0～3 ＝ 站—左腳前—站（擺動相位不同）—右腳前（第 0 欄兼站姿）。
  * 角色水平置中（中線在第 27／28 欄之間）；**鞋底外輪廓在第 68 列，69～71 列留空 → 鞋底在格子底邊往上 3px**
    （跟女巫 witch8 一樣是 3），所有角色、所有幀都一樣（check_cell 會檢查）。騎掃帚的魔女是唯一例外：整個人浮在空中。
  * 走路：跨步那兩幀身體往下沉 1px、後腳抬 2px（正背面）或腳前後擺 ±4px（側面），手反向擺；
    耳朵／尾巴／披風下襬／辮子／翅膀用 Rig.sway、Rig.lag 做跟隨擺動（第 0 與第 2 欄身體一樣、這些不一樣）。
  * 騎掃帚的魔女：腳不著地、整個人＋掃帚上下浮 1px、鬃毛擺動 —— VillagerAnim 對她**站著也會播**（GameArt.VillagerHovers）。
  * 可見高（原生 px → ×1.6 的畫面 px）：主角女巫 58 → 93。小魔女含帽 59、騎掃帚 58、法師含法杖 61、旅人 48；
    兔子 54、兔子魔女 53（含耳朵）、小鹿含角 52、狐狸含耳朵 49、妖精含帽 46、青蛙含釣竿 44、刺蝟 41。
    騎掃帚的魔女鞋底離基準線約 9px（浮在影子上方）。
  * 結果是確定的：沒有亂數（星星位置寫死），重跑 md5 相同。

── 畫法 ──────────────────────────────────────────────────────────
  * 形狀都是 numpy 布林遮罩（ell 橢圓、cap 膠囊、bez 加粗貝茲曲線、poly 多邊形），Fr.fill(遮罩, 材質, 打光) 一層層往上蓋。
  * 打光：'soft'（遮罩模糊後的法線 · 左上前方的光）、'ball'（橢球）、'cyl'（每列當圓柱）；量化成 5 階後去掉孤立雜點。
  * Fr.render()：部件 A 貼著後畫的部件 B（不同 group、B.line=True）→ A 那一圈畫成 A 的描線色；最後整隻外圍補一圈 OUT。
  * Fr.paint 是在已畫的像素上加細節（髮絲、皺褶、星星）；Fr.put 可以往外加像素；Fr.overlay 在外輪廓之後才畫（釣線、光點、提燈光暈）。
  * 側面一律畫「朝左」，往右走由 VillagerAnim 把 scale.x 取負 —— 所以側面不要畫字或只能朝一邊的標記。
"""
import colorsys
import hashlib
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('WITCH_UNITY_ROOT') or os.path.dirname(HERE)   # 在別處迭代時用環境變數指回專案
RES = os.path.join(ROOT, 'Assets', 'Resources')
OUT_DIR = os.path.join(RES, 'villagers8')
sys.path.insert(0, HERE)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


W, H = 56, 72
CX = 28.0
FB = 67
DOWN, SIDE, UP = 0, 1, 2
OUT = (16, 9, 18)

YY, XX = np.mgrid[0:H, 0:W]
PX = XX + 0.5
PY = YY + 0.5
Z = np.zeros((H, W), bool)


def hx(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _toward(h, target, deg):
    d = (target - h + 0.5) % 1.0 - 0.5
    step = deg / 360.0
    if abs(d) < step:
        return target
    return (h + step * (1 if d > 0 else -1)) % 1.0


def shift(rgb, dh, dv, ds):
    """HSV 調色：dh 正＝往暖黃轉、負＝往藍紫轉（度）；dv、ds 是乘數（1＝不變）。"""
    r, g, b = [v / 255 for v in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if dh > 0:
        h = _toward(h, 55 / 360, dh)
    elif dh < 0:
        h = _toward(h, 262 / 360, -dh)
    v = min(1.0, max(0.03, v * dv))
    s = min(1.0, max(0.0, s * ds))
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (round(r * 255), round(g * 255), round(b * 255))


class Mat:
    """一種材質的 6 色：0 最暗 … 4 最亮，'ln' ＝ 部件之間的內描線（同色相更深）。"""

    def __init__(self, base, k=1.0, cols=None, ln=None):
        if cols is not None:
            self.c = {i: hx(v) for i, v in enumerate(cols)}
            self.c['ln'] = hx(ln) if ln else shift(self.c[0], -8, 0.75, 1.05)
            return
        b = hx(base)
        sp = {4: (10, 1.10, 0.55), 3: (5, 1.05, 0.80), 2: (0, 1, 1),
              1: (-8, 0.85, 1.12), 0: (-15, 0.69, 1.22), 'ln': (-22, 0.50, 1.25)}
        self.c = {key: shift(b, dh * k, 1 + (dv - 1) * k, 1 + (ds - 1) * k) for key, (dh, dv, ds) in sp.items()}

    def dark(self, n=1):
        m = Mat.__new__(Mat)
        m.c = {i: self.c[max(0, i - n)] for i in range(5)}
        m.c['ln'] = self.c['ln']
        if n:
            m.c[0] = shift(self.c[0], -6, 0.88, 1.05)
        return m

    def __getitem__(self, k):
        return self.c[k]


# ───────────── 形狀（回傳 H×W 布林遮罩）─────────────

def ell(cx, cy, rx, ry):
    return ((PX - cx) / rx) ** 2 + ((PY - cy) / ry) ** 2 <= 1.0


def rect(x0, y0, x1, y1):
    return (XX >= x0) & (XX <= x1) & (YY >= y0) & (YY <= y1)


def cap(x0, y0, x1, y1, r):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        t = 0
    else:
        t = np.clip(((PX - x0) * dx + (PY - y0) * dy) / L2, 0, 1)
    qx, qy = x0 + t * dx, y0 + t * dy
    return (PX - qx) ** 2 + (PY - qy) ** 2 <= r * r


def bez(pts, r0, r1=None, n=48):
    """二次／三次貝茲曲線加粗（半徑 r0→r1 漸變）。"""
    if r1 is None:
        r1 = r0
    m = Z.copy()
    P = np.array(pts, float)
    for i in range(n + 1):
        t = i / n
        if len(P) == 3:
            q = (1 - t) ** 2 * P[0] + 2 * (1 - t) * t * P[1] + t * t * P[2]
        elif len(P) == 4:
            q = ((1 - t) ** 3 * P[0] + 3 * (1 - t) ** 2 * t * P[1]
                 + 3 * (1 - t) * t * t * P[2] + t ** 3 * P[3])
        else:
            q = (1 - t) * P[0] + t * P[1]
        r = r0 + (r1 - r0) * t
        m |= (PX - q[0]) ** 2 + (PY - q[1]) ** 2 <= r * r
    return m


def bezpts(pts, n=60):
    P = np.array(pts, float)
    out = []
    for i in range(n + 1):
        t = i / n
        if len(P) == 3:
            q = (1 - t) ** 2 * P[0] + 2 * (1 - t) * t * P[1] + t * t * P[2]
        elif len(P) == 4:
            q = ((1 - t) ** 3 * P[0] + 3 * (1 - t) ** 2 * t * P[1]
                 + 3 * (1 - t) * t * t * P[2] + t ** 3 * P[3])
        else:
            q = (1 - t) * P[0] + t * P[1]
        p = (int(np.floor(q[0])), int(np.floor(q[1])))
        if not out or out[-1] != p:
            out.append(p)
    return out


def poly(pts):
    im = Image.new('L', (W, H), 0)
    ImageDraw.Draw(im).polygon([(x, y) for x, y in pts], fill=1)
    return np.array(im, bool)


def flip(m):
    return m[:, ::-1]


def sym(m):
    return m | m[:, ::-1]


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


def ero(m, n=1):
    return ~dil(~m, n)


def edge(m, side):
    """遮罩靠某一邊的那一圈像素（'t' 上、'b' 下、'l' 左、'r' 右）。"""
    dx, dy = {'t': (0, -1), 'b': (0, 1), 'l': (-1, 0), 'r': (1, 0)}[side]
    return m & ~shiftm(m, -dx, -dy)


# ───────────── 打光 ─────────────

LIGHT = np.array([-0.45, -0.60, 1.0])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
TH = (0.30, 0.52, 0.80, 0.93)


def _q(I, th=TH):
    lv = np.zeros(I.shape, np.int8)
    for t in th:
        lv += (I >= t)
    return lv


def _blur(m, r):
    im = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, np.float32) / 255.0


def shade(m, mode='soft', blur=1.6, k=3.2, c=None, r=None, bias=0.0, vgrad=0.0, th=TH):
    """回傳 0..4 的明暗階（只有 m 內有意義）。"""
    if mode == 'flat':
        lv = np.full(m.shape, 2, np.int8)
        lv[edge(m, 'b') | edge(m, 'r')] = 1
        lv[edge(m, 't')] = 3
        return lv
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
    elif mode == 'cyl':
        I = np.zeros(m.shape, np.float32)
        for y in range(H):
            xs = np.nonzero(m[y])[0]
            if len(xs) == 0:
                continue
            a, b2 = xs.min(), xs.max() + 1
            cx, rx = (a + b2) / 2, max(1.0, (b2 - a) / 2)
            nx = np.clip((PX[y] - cx) / rx, -1, 1)
            nz = np.sqrt(np.clip(1 - nx * nx, 0.02, 1))
            I[y] = nx * LIGHT[0] + nz * LIGHT[2] - 0.12
        I = I + 0.0
    else:
        h = _blur(m, blur)
        gx = np.zeros_like(h)
        gy = np.zeros_like(h)
        gx[:, 1:-1] = h[:, 2:] - h[:, :-2]
        gy[1:-1, :] = h[2:, :] - h[:-2, :]
        n = np.stack([-gx * k, -gy * k, np.ones_like(h)], -1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        I = n @ LIGHT
    if vgrad:
        ys = np.nonzero(m)[0]
        y0, y1 = ys.min(), ys.max() + 1
        I = I - vgrad * ((PY - y0) / max(1, y1 - y0) - 0.5)
    lv = _q(I + bias, th)
    return _clean(lv, m)


def _clean(lv, m):
    """同一部件裡孤立的單一像素階數改成鄰居多數（避免雜點）。"""
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
        self.lv = np.zeros((H, W), np.int8)
        self.parts = []   # (mat, group, line)
        self.over = {}    # 外輪廓之後才畫的像素（釣線、光點）：不描邊

    def fill(self, m, mat, sh='soft', group=None, line=True, lv=None, **kw):
        m = m & True
        if not m.any():
            return m
        if lv is None:
            lv = shade(m, sh, **kw)
        idx = len(self.parts)
        self.parts.append((mat, group if group is not None else idx, line))
        for i in range(5):
            sel = m & (lv == i)
            self.rgb[sel] = mat[i]
        self.a |= m
        self.pid[m] = idx
        self.lv[m] = lv[m]
        return m

    def paint(self, m, mat, key):
        """細節：直接上色，不改部件編號（不會產生內描線）。m 可以是遮罩或座標串列。"""
        if isinstance(m, np.ndarray):
            sel = m & self.a
            self.rgb[sel] = mat[key]
        else:
            for x, y in m:
                x, y = int(x), int(y)
                if 0 <= x < W and 0 <= y < H and self.a[y, x]:
                    self.rgb[y, x] = mat[key]

    def put(self, pts, rgb):
        """細節：可以畫在透明處（新增像素，歸到最上層的部件）。"""
        if isinstance(rgb, str):
            rgb = hx(rgb)
        for x, y in pts:
            x, y = int(x), int(y)
            if 0 <= x < W and 0 <= y < H:
                self.rgb[y, x] = rgb
                if not self.a[y, x]:
                    self.a[y, x] = True
                    self.pid[y, x] = len(self.parts) - 1

    def overlay(self, pts, rgb, a=255):
        if isinstance(rgb, str):
            rgb = hx(rgb)
        for x, y in pts:
            x, y = int(x), int(y)
            if 0 <= x < W and 0 <= y < H:
                self.over[(x, y)] = tuple(rgb) + (a,)

    def stamp(self, x0, y0, rows, cmap, mirror=False):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch in ' .':
                    continue
                xx = x0 + (len(row) - 1 - i if mirror else i)
                self.put([(xx, y0 + j)], cmap[ch])

    def render(self):
        rgb = self.rgb.copy()
        # 部件之間的內描線：畫在「後面那個部件」貼著前面部件的那圈像素上，用它自己的描線色
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
            if c[3] == 255 or out[y, x, 3] == 0:
                out[y, x] = c
            else:
                a = c[3] / 255
                out[y, x, :3] = np.round(np.array(c[:3]) * a + out[y, x, :3] * (1 - a))
        return Image.fromarray(out)


class Rig:
    """方向 d、幀 f 的走路參數。step：0 站、+1／-1 兩邊跨步；bob：跨步時身體往下沉 1。"""

    def __init__(self, d, f):
        self.d, self.f = d, f
        self.step = (0, 1, 0, -1)[f]
        self.bob = 1 if self.step else 0
        self.sway = (0, 1, 0, -1)[f]
        self.lag = (0, -1, 1, -1)[f]


SKIN = Mat('#fcd6bc', cols=['#c98a7a', '#e8a990', '#fcd6bc', '#ffe6d2', '#fff3e6'], ln='#9a5a58')
BLUSH = hx('#f48a92')
BLUSH2 = hx('#f9b3ae')
WHITE = hx('#fffdf6')
INK = hx('#1e1018')
MOUTH = hx('#a8444e')
DARK_IRIS = Mat('#3a2a34')


# ───────────── 眼睛 ─────────────

def eye_l(fr, x0, y, iris, shape='human'):
    """左眼（畫面左邊那隻）：x0 ＝最外側那欄。shape：human 4×4、bead 動物的圓眼。"""
    iris = iris or DARK_IRIS
    cm = {'k': INK, 'd': iris[0], 'm': iris[2], 'l': iris[4], 'w': WHITE}
    if shape == 'human':
        rows = ['kkkk',
                '.wdk',
                '.dmd',
                '..ml']
    elif shape == 'bead':        # 3×4 黑豆眼＋白高光
        rows = ['.kk.',
                'kwkk',
                'kkdk',
                '.kk.']
        cm['d'] = iris[2]
    elif shape == 'bead_s':
        rows = ['kk',
                'wk',
                'kk']
    elif shape == 'closed':
        rows = ['.kk.',
                'k..k']
    fr.stamp(x0, y, rows, cm)
    return rows


def eye_r(fr, x1, y, iris, shape='human'):
    """右眼：x1 ＝最外側那欄（最右）；圖案是左眼左右鏡射，但高光留在同一邊（光從左上來）。"""
    iris = iris or DARK_IRIS
    cm = {'k': INK, 'd': iris[0], 'm': iris[2], 'l': iris[4], 'w': WHITE}
    if shape == 'human':
        rows = ['kkkk',
                'kwd.',
                'dmd.',
                'lm..']
    elif shape == 'bead':
        rows = ['.kk.',
                'kwkk',
                'kkdk',
                '.kk.']
        cm['d'] = iris[2]
    elif shape == 'bead_s':
        rows = ['kk',
                'wk',
                'kk']
    elif shape == 'closed':
        rows = ['.kk.',
                'k..k']
    fr.stamp(x1 - len(rows[0]) + 1, y, rows, cm)


def blush(fr, pts, strong=True):
    fr.put(pts[:2], BLUSH)
    if len(pts) > 2:
        fr.put(pts[2:], BLUSH2)


# ───────────── 人的頭 ─────────────

def under_shadow(fr, base_mask, over_mask, mat, lv=1, depth=1):
    """over_mask 正下方 depth 列（落在 base_mask 上）畫成陰影 —— 瀏海、帽簷下的影子。"""
    sh = Z.copy()
    for k in range(1, depth + 1):
        sh |= shiftm(over_mask, 0, k)
    sh &= base_mask & ~over_mask
    fr.paint(sh, mat, lv)


def strands(fr, mask, mat, xs, y0, y1, lv=0, slant=0.0):
    """在頭髮上畫幾條髮絲分隔線（暗）。"""
    for x in xs:
        pts = []
        for y in range(y0, y1 + 1):
            xx = int(round(x + slant * (y - y0)))
            if mask[y, xx] if 0 <= xx < W and 0 <= y < H else False:
                pts.append((xx, y))
        fr.paint(pts, mat, lv)


def sheen(fr, mask, mat, cx, cy, rx, ry, y_max, lv=4, lv2=3, split=None):
    """頭髮的光澤圈：一段弧，左半最亮、右半次亮。"""
    ring = ell(cx, cy, rx, ry) & ~ell(cx + 0.3, cy + 1.2, rx, ry) & mask & (PY < y_max)
    split = cx - 1 if split is None else split
    fr.paint(ring & (PX < split), mat, lv)
    fr.paint(ring & (PX >= split), mat, lv2)


def face_lv(face, jaw_dark=True):
    lv = np.full(face.shape, 2, np.int8)
    if jaw_dark:
        lv[edge(face, 'b') | edge(face, 'r')] = 1
    return lv


def head_front(fr, hy, skin, hair, iris, *, mouth='smile', bang_tips=(21.5, 25, 28.5, 31.5, 34.5),
               bang_y=1.0, hair_rx=10.8, hair_ry=9.2, face_rx=7.0, face_ry=6.8, locks=2,
               lock_len=7, eye_dy=0, ears=False, eye_shape='human', blush_on=True, bang_drop=None):
    """正面的人頭（後面的長髮另外在身體前先畫）。hy ＝頭的中心列。回傳 (臉, 頭髮) 遮罩。"""
    face = ell(CX, hy + 2.6, face_rx, face_ry)
    if ears:
        fr.fill(sym(ell(CX - face_rx - 0.3, hy + 3.5, 1.4, 1.9)), skin, 'ball', group='face')
    fr.fill(face, skin, lv=face_lv(face), group='face')
    cap_ = ell(CX, hy - 0.4, hair_rx, hair_ry) & (PY < hy - 1.5)
    hm = cap_.copy()
    drops = bang_drop or [0.0] * len(bang_tips)
    for i, x in enumerate(bang_tips):
        tip = hy + bang_y + drops[i]
        hm |= bez([(x + (0.8 if x < CX else -0.8), hy - 3.5), (x, tip - 1.5), (x + (-0.4 if x < CX else 0.4), tip)], 2.4, 0.6)
    # 兩側的鬢髮
    for side in (-1, 1):
        for j in range(locks):
            x0 = CX + side * (hair_rx - 1.6 - j * 1.6)
            hm |= bez([(x0, hy - 3), (x0 + side * 0.9, hy + 2 + lock_len * 0.4), (x0 + side * 0.2 - side * j * 0.6, hy + 1 + lock_len - j * 1.5)], 2.2 - j * 0.4, 0.7)
    hm &= (PY < hy + 2 + lock_len)
    fr.fill(hm, hair, 'soft', blur=1.5, k=3.2, group='hair')
    under_shadow(fr, face, hm, skin, 1)
    # 瀏海的髮絲線：每兩撮之間
    for a, bb in zip(bang_tips[:-1], bang_tips[1:]):
        m = (a + bb) / 2
        strands(fr, hm, hair, [m], int(hy - 3), int(hy + bang_y + 1), 0)
    sheen(fr, hm, hair, CX - 0.5, hy - 2.0, hair_rx - 2.6, hair_ry - 3.4, hy - 2.5)
    # 五官
    ey = int(hy + 1 + eye_dy)
    if eye_shape == 'human':
        eye_l(fr, 22, ey, iris)
        eye_r(fr, 33, ey, iris)
    else:
        eye_l(fr, 22, ey, iris, eye_shape)
        eye_r(fr, 33, ey, iris, eye_shape)
    if blush_on:
        fr.put([(21, ey + 4), (22, ey + 4)], BLUSH)
        fr.put([(33, ey + 4), (34, ey + 4)], BLUSH)
    my = ey + 6
    if mouth == 'smile':
        fr.put([(27, my), (28, my)], MOUTH)
    elif mouth == 'open':
        fr.put([(27, my), (28, my)], hx('#6a2032'))
        fr.put([(27, my + 1), (28, my + 1)], hx('#e8707e'))
    elif mouth == 'grin':
        fr.put([(26, my), (29, my)], MOUTH)
        fr.put([(27, my + 1), (28, my + 1)], MOUTH)
    return face, hm


def head_side(fr, hy, skin, hair, iris, *, hx_=CX, mouth=True, hair_rx=10.5, hair_ry=9.2,
              face_rx=6.6, face_ry=6.8, lock_len=7, bang_y=1.0, ear=True, blush_on=True):
    """側面（朝左）的人頭。hx_ ＝頭的中心欄。"""
    back = ell(hx_ + 1.0, hy - 0.4, hair_rx, hair_ry) & (PY < hy + 2 + lock_len)
    face = ell(hx_ - 2.2, hy + 2.6, face_rx, face_ry)
    face |= ell(hx_ - 7.6, hy + 3.6, 1.6, 1.4)          # 鼻尖／臉頰往前凸一點
    face &= ~(back & (PX > hx_ + 0.5))
    fr.fill(back, hair, 'soft', blur=1.5, k=3.2, group='hair')
    fr.fill(face, skin, lv=face_lv(face), group='face')
    if ear:
        er = ell(hx_ + 1.2, hy + 3.6, 1.6, 2.0)
        fr.fill(er, skin, 'ball', group='ear')
        fr.paint([(int(hx_ + 1), int(hy + 4))], skin, 1)
    # 瀏海：從頭頂往前額垂下
    bang = ell(hx_ - 0.5, hy - 1.0, hair_rx - 0.4, hair_ry - 0.8) & (PY < hy - 1)
    for x, dy in ((hx_ - 8.0, 0.0), (hx_ - 5.0, 0.5), (hx_ - 2.2, 0.0)):
        bang |= bez([(x + 1.0, hy - 3.5), (x, hy - 0.5), (x - 0.6, hy + bang_y + dy)], 2.3, 0.6)
    # 耳前的鬢髮
    bang |= bez([(hx_ + 0.2, hy - 2), (hx_ - 0.6, hy + 3), (hx_ - 0.8, hy + lock_len - 1)], 1.8, 0.7)
    fr.fill(bang, hair, 'soft', blur=1.5, k=3.2, group='hair')
    under_shadow(fr, face, bang, skin, 1)
    strands(fr, bang, hair, [hx_ - 6.5, hx_ - 3.6], int(hy - 3), int(hy + bang_y + 1), 0)
    strands(fr, back, hair, [hx_ + 4.5, hx_ + 7.0], int(hy), int(hy + lock_len + 1), 0, slant=0.15)
    sheen(fr, bang | back, hair, hx_ + 0.5, hy - 2.0, hair_rx - 2.8, hair_ry - 3.4, hy - 2.5, split=hx_)
    ey = int(hy + 1)
    fr.stamp(int(hx_ - 8), ey, ['kkk.', 'wdk.', 'dmd.', 'ml..'],
             {'k': INK, 'd': iris[0], 'm': iris[2], 'l': iris[4], 'w': WHITE})
    if blush_on:
        fr.put([(int(hx_ - 6), ey + 4), (int(hx_ - 5), ey + 4)], BLUSH)
    if mouth:
        fr.put([(int(hx_ - 8), ey + 6)], MOUTH)
    return face, back | bang


def head_back(fr, hy, hair, *, hair_rx=10.8, hair_ry=9.2, lock_len=7, skin=None, ears=False):
    """背面：整顆都是頭髮。"""
    if ears and skin is not None:
        fr.fill(sym(ell(CX - 7.5, hy + 3.5, 1.4, 1.9)), skin, 'ball', group='ear')
    hm = ell(CX, hy - 0.4, hair_rx, hair_ry)
    bot = hy + 2 + lock_len
    # 下緣是一撮一撮的髮尾（波浪）
    n = 5
    for i in range(n):
        x = CX - hair_rx + 2.2 + i * (2 * hair_rx - 4.4) / (n - 1)
        yb = bot - 1.2 - abs(x - CX) * 0.12
        hm |= bez([(x, hy), (x + (x - CX) * 0.08, yb - 2), (x + (x - CX) * 0.05, yb)], 2.6, 1.0)
    hm |= ell(CX, hy + 2, hair_rx - 0.6, lock_len * 0.55 + 2) & (PY < bot - 2)
    fr.fill(hm, hair, 'soft', blur=1.6, k=3.0, group='hair', vgrad=0.15)
    for i in range(n - 1):
        x = CX - hair_rx + 2.2 + (i + 0.5) * (2 * hair_rx - 4.4) / (n - 1)
        pts = bezpts([(CX + (x - CX) * 0.25, hy - 6), (x - (x - CX) * 0.05, hy), (x + (x - CX) * 0.08, bot - 1)], 30)
        fr.paint([p for p in pts if p[1] > hy - 3], hair, 0)
        fr.paint([p for p in pts if p[1] <= hy - 3], hair, 1)
    sheen(fr, hm, hair, CX - 0.5, hy - 2.0, hair_rx - 2.6, hair_ry - 3.4, hy - 2.5)
    return hm


# ───────────── 腿、手 ─────────────

def legs_front(fr, r, hip, sep, w, pant, shoe, shoe_rx=2.6, shoe_ry=1.9, shoe_dx=0.3, up=False):
    """正／背面的腿＋鞋。跨步幀：後腳抬起 2 格、腳色暗一階。"""
    for side in (-1, 1):
        lifted = (r.step == side)
        fy = FB - (2 if lifted else 0)
        x = CX + side * sep
        leg = rect(int(np.floor(x - w / 2 + 0.5)), hip, int(np.floor(x + w / 2 - 0.5)), fy - 1)
        fr.fill(leg, pant if not lifted else pant.dark(1), 'cyl', group=('leg', side))
        sm = ell(x + side * shoe_dx, fy + 1 - shoe_ry + 0.5, shoe_rx, shoe_ry) & (PY <= fy + 1)
        lv = shade(sm, 'ball')
        if up:
            lv = np.minimum(lv, 2)
        fr.fill(sm, shoe if not lifted else shoe.dark(1), lv=lv, group=('shoe', side))


def legs_side(fr, r, hip, hx_, pant, shoe, w=1.6, stride=4, toe=2.0, far_first=True, which=(False, True)):
    """側面（朝左）兩條腿：遠側（較暗）先畫、近側後畫。"""
    out = {}
    for near in which:
        off = (-stride * r.step) if near else (stride * r.step)
        fx = hx_ + off
        lift = 1 if off > 0 else 0
        pm = pant if near else pant.dark(1)
        sm = shoe if near else shoe.dark(1)
        fr.fill(cap(hx_ + 0.5, hip, fx + 0.5, FB - 2 - lift, w), pm, 'cyl', group=('leg', near))
        fm = ell(fx + 0.5 - toe * 0.5, FB + 0.5 - 1.6 - lift, 2.1 + toe * 0.5, 1.8) & (PY <= FB + 1 - lift)
        fr.fill(fm, sm, 'ball', group=('shoe', near))
        out[near] = fx
    return out


def arm_front(fr, r, side, sx, sy, length, sleeve, hand, rad=2.2, rad2=1.7, hand_r=1.75, swing=1,
              d=DOWN, cuff=None, puff=0.0):
    """正／背面的手：side -1 ＝畫面左邊。往前擺的那隻手往內、往下 1；往後擺往上 1。回傳手的位置。"""
    if d == DOWN:
        fwd, back = r.step == side, r.step == -side
    else:
        fwd, back = r.step == -side, r.step == side
    dx = dy = 0
    if fwd:
        dx, dy = -side * swing, 1
    elif back:
        dx, dy = side * 0.5, -1
    ex, ey = sx + side * 1.0 + dx, sy + length + dy
    m = bez([(sx, sy), (sx + side * 0.6, (sy + ey) / 2), (ex, ey - 1)], rad, rad2)
    if puff:
        m |= ell(sx + side * 0.4, sy + 1.2, rad + puff, rad + puff * 0.8)
    fr.fill(m, sleeve, 'soft', blur=1.0, k=3.0, group=('arm', side))
    if cuff is not None:
        cm = m & (PY >= ey - 2.2)
        fr.fill(cm, cuff, 'cyl', group=('cuff', side), line=False)
    if hand is not None:
        fr.fill(ell(ex, ey + 0.6, hand_r, hand_r), hand, 'ball', group=('hand', side))
    return ex, ey


def arm_side(fr, r, sx, sy, length, sleeve, hand, near=True, rad=2.2, rad2=1.7, hand_r=1.75, swing=3,
             cuff=None, fixed=None, puff=0.0):
    """側面（朝左）的手：近側的手跟近側的腳反向擺（近腳往前 → 近手往後）。fixed＝手固定伸到 (dx, dy)。"""
    if fixed is not None:
        ex, ey = sx + fixed[0], sy + fixed[1]
    else:
        off = swing * r.step if near else -swing * r.step
        ex, ey = sx + off, sy + length - abs(off) * 0.2
    sl = sleeve if near else sleeve.dark(1)
    m = bez([(sx, sy), ((sx + ex) / 2 + 0.3, (sy + ey) / 2), (ex, ey - 1)], rad, rad2)
    if puff:
        m |= ell(sx, sy + 1.2, rad + puff, rad + puff * 0.8)
    fr.fill(m, sl, 'soft', blur=1.0, k=3.0, group=('arm', near))
    if cuff is not None:
        cm = m & (((PX - ex) ** 2 + (PY - ey) ** 2) < 3.2 ** 2)
        fr.fill(cm, cuff if near else cuff.dark(1), 'cyl', group=('cuff', near), line=False)
    if hand is not None:
        fr.fill(ell(ex, ey + 0.6, hand_r, hand_r), hand if near else hand.dark(1), 'ball', group=('hand', near))
    return ex, ey


# ───────────── 衣服 ─────────────

def gown(sh, hem, top_w, hem_w, cx=CX, round_sh=2.5):
    """梯形的衣服（正背面）：肩寬 top_w、下襬寬 hem_w，肩膀圓。"""
    m = poly([(cx - top_w / 2, sh + 1), (cx + top_w / 2, sh + 1), (cx + hem_w / 2, hem + 1), (cx - hem_w / 2, hem + 1)])
    m |= ell(cx, sh + round_sh, top_w / 2, round_sh + 0.5)
    m |= ell(cx, hem + 0.2, hem_w / 2, 1.6)
    return m


def folds(fr, mask, mat, xs, y0, y1, lit=True):
    """裙褶：一條暗線，左邊一條亮線（光從左上）。"""
    for x in xs:
        x = int(x)
        dark = [(x, y) for y in range(y0, y1 + 1) if mask[y, x]]
        fr.paint(dark, mat, 1)
        if lit:
            fr.paint([(x - 1, y) for y in range(y0 + 1, y1 + 1) if mask[y, x - 1]], mat, 3)


def hem_band(fr, mask, mat, lv=0, rows=1):
    bm = mask.copy()
    e = Z.copy()
    for _ in range(rows):
        b = edge(bm, 'b')
        e |= b
        bm &= ~b
    fr.paint(e, mat, lv)


def witch_hat(fr, hx_, by, brim_rx, tall, mat, band, d=DOWN, tip=6.0, buckle=True, droop=3.0, brim_ry=3.2,
              base_r=7.0, star=None, under=None):
    """尖帽：帽簷 → 帽身（往後彎的錐，尖端下垂）→ 帽簷前半蓋住帽身底。by ＝帽簷中線。"""
    if d == SIDE:
        tip_x = hx_ + tip + 2
    elif d == UP:
        tip_x = hx_ - tip * 0.6
    else:
        tip_x = hx_ + tip
    brim = ell(hx_, by, brim_rx, brim_ry)
    if d == SIDE:
        brim = ell(hx_ + 0.5, by, brim_rx, brim_ry - 0.6)
    fr.fill(brim, mat, 'soft', group='brim', bias=0.05, blur=1.2)
    cone = bez([(hx_, by - 0.5), (hx_ + (tip_x - hx_) * 0.15, by - tall * 0.55),
                (hx_ + (tip_x - hx_) * 0.6, by - tall), (tip_x, by - tall + droop)], base_r, 0.9, n=80)
    cone &= PY <= by + 0.5
    fr.fill(cone, mat, 'soft', group='cone', blur=1.5, k=3.8, bias=0.04)
    # 帽身的皺褶
    fr.paint([(int(hx_ + 2 + (y - by) * -0.05), y) for y in range(int(by - tall * 0.45), int(by - 4))], mat, 1)
    # 帽帶
    bm = cone & (PY > by - 4.2) & (PY <= by - 1.2)
    fr.paint(bm, band, 2)
    fr.paint(bm & edge(bm, 't'), band, 4)
    fr.paint(bm & edge(bm, 'b'), band, 0)
    fr.paint(bm & edge(bm, 'r'), band, 1)
    if buckle and d != UP:
        bx = int(hx_ - 2) if d == DOWN else int(hx_ - 4)
        by_ = int(by - 4)
        fr.put([(bx, by_ + 1), (bx + 1, by_ + 1), (bx + 2, by_ + 1), (bx, by_ + 2), (bx + 2, by_ + 2), (bx, by_ + 3), (bx + 1, by_ + 3), (bx + 2, by_ + 3)], band[4])
        fr.put([(bx + 1, by_ + 2)], band[0])
    front = brim & (PY >= by - 0.3)
    lv = shade(front, 'soft', blur=1.0, bias=0.08)
    fr.fill(front, mat, lv=lv, group='brim')
    fr.paint(edge(front, 'b'), mat, 0)
    if star is not None:
        sx, sy = int(tip_x), int(by - tall + droop + 1)
        fr.put([(sx, sy), (sx - 1, sy + 1), (sx, sy + 1), (sx + 1, sy + 1), (sx, sy + 2)], star)
    return brim | cone


# ═══════════════ 小魔女（witch）═══════════════
W_HAIR = Mat('#8e4f30')
W_HAT = Mat('#5b3f94')
W_DRESS = Mat('#33427e')
W_BAND = Mat('#f2b04a')
W_STOCK = Mat('#4b3563')
W_BOOT = Mat('#7a4630')
W_PUMP = Mat('#f28a2c')
W_STEM = Mat('#4f8a3a')
W_COLLAR = Mat('#f6eedf')
W_BOW = Mat('#d8404e')
W_IRIS = Mat('#6a4a9a')
W_FRILL = Mat('#7d6cc0')


def pumpkin_bucket(fr, x, y, d=DOWN):
    """南瓜糖果桶：x,y ＝提把頂（手的位置）。"""
    cx, cy = x + 0.5, y + 6.2
    body = ell(cx, cy, 4.6, 3.8)
    fr.fill(body, W_PUMP, 'ball', group='pump')
    for dx in (-2, 2):
        fr.paint([(int(cx + dx), yy) for yy in range(int(cy - 2), int(cy + 3))], W_PUMP, 1)
    fr.paint(edge(body, 't') & (PX > cx - 3) & (PX < cx + 3), W_PUMP, 0)
    # 糖果
    fr.put([(int(cx - 2), int(cy - 4)), (int(cx - 1), int(cy - 4))], hx('#f06a9a'))
    fr.put([(int(cx + 1), int(cy - 4))], hx('#7ad0f0'))
    if d != UP:
        ink = hx('#4a1c10')
        fr.put([(int(cx - 2), int(cy - 1)), (int(cx + 1), int(cy - 1))], hx('#ffd65a'))
        fr.put([(int(cx - 1), int(cy + 1)), (int(cx), int(cy + 1)), (int(cx + 1), int(cy + 1)), (int(cx - 2), int(cy))], ink)
    # 提把
    fr.put([(int(cx - 3), int(cy - 3)), (int(cx - 3), int(cy - 4)), (int(cx - 2), int(cy - 5)),
            (int(cx + 2), int(cy - 5)), (int(cx + 3), int(cy - 4)), (int(cx + 3), int(cy - 3))], hx('#3a2a30'))


def stripes(fr, mask, mat, every=2, lv=0):
    ys = np.nonzero(mask.any(1))[0]
    for y in ys:
        if y % every == 0:
            fr.paint(mask & (YY == y), mat, lv)


def draw_witch(fr, r):
    b = r.bob
    hy = 33 + b
    sh = 43 + b
    hem = 58 + b
    d = r.d
    hat_y = hy - 6.5
    if d == DOWN:
        for side in (-1, 1):   # 低馬尾（在身後）
            pig = bez([(CX + side * 8.5, hy + 4), (CX + side * 12.5, hy + 8), (CX + side * 11 + r.lag * 0.6, hy + 14 + r.lag * 0.4)], 3.0, 1.8)
            fr.fill(pig, W_HAIR, 'soft', group=('pig', side))
            strands(fr, pig, W_HAIR, [CX + side * 11.5], int(hy + 7), int(hy + 14), 0)
        legs_front(fr, r, hem - 2, 2.6, 3, W_STOCK, W_BOOT)
        # 條紋襪：只畫在兩條腿的部件上
        legs_ids = [i for i, p in enumerate(fr.parts) if p[1] in (('leg', -1), ('leg', 1))]
        stripes(fr, np.isin(fr.pid, legs_ids) & (YY >= hem) & (YY < FB - 2), W_STOCK, 2, 4)
        dress = gown(sh, hem, 12, 21)
        fr.fill(dress, W_DRESS, 'soft', vgrad=0.35, blur=1.8)
        folds(fr, dress, W_DRESS, [23, 33], hem - 6, hem + 1)
        folds(fr, dress, W_DRESS, [28], hem - 4, hem + 1)
        # 下襬荷葉邊
        frill = dress & (PY > hem - 0.5)
        fr.fill(frill, W_FRILL, 'flat', group='frill')
        fr.paint([(x, hem + 1) for x in range(18, 39) if x % 3 == 0], W_FRILL, 1)
        # 星星補丁
        fr.put([(31, hem - 7), (30, hem - 6), (31, hem - 6), (32, hem - 6), (31, hem - 5)], W_BAND[3])
        fr.put([(31, hem - 6)], W_BAND[4])
        # 衣領＋蝴蝶結
        col = sym(ell(CX - 2.6, sh + 0.8, 3.4, 2.0))
        fr.fill(col, W_COLLAR, 'soft', group='col')
        bow = sym(poly([(28, sh + 2.5), (24.5, sh + 0.8), (24.5, sh + 4.5)]))
        fr.fill(bow, W_BOW, 'soft', group='bow')
        fr.put([(27, sh + 2), (28, sh + 2), (27, sh + 3), (28, sh + 3)], W_BOW[3])
        arm_front(fr, r, -1, CX - 6.0, sh + 2, 8, W_DRESS, SKIN, cuff=W_COLLAR, puff=0.8)
        ex, ey = arm_front(fr, r, 1, CX + 6.0, sh + 2, 8, W_DRESS, SKIN, cuff=W_COLLAR, puff=0.8)
        pumpkin_bucket(fr, int(ex), int(ey), d)
        head_front(fr, hy, SKIN, W_HAIR, W_IRIS)
        witch_hat(fr, CX, hat_y, 13.5, 15, W_HAT, W_BAND, d, star=hx('#ffe27a'))
    elif d == SIDE:
        hx_ = CX - 1
        pig = bez([(hx_ + 7, hy + 3), (hx_ + 10.5, hy + 8), (hx_ + 9.5 + r.lag * 0.8, hy + 14)], 3.0, 1.8)
        fr.fill(pig, W_HAIR, 'soft', group='pig')
        arm_side(fr, r, hx_ + 1, sh + 2, 8, W_DRESS, SKIN, near=False, cuff=W_COLLAR)
        legs_side(fr, r, hem - 2, hx_, W_STOCK, W_BOOT)
        dress = poly([(hx_ - 4, sh + 1), (hx_ + 4, sh + 1), (hx_ + 8 + r.step * 0.0, hem + 1), (hx_ - 7, hem + 1)])
        dress |= ell(hx_, sh + 2.5, 4.5, 3) | ell(hx_ + 0.5, hem + 0.2, 7.5, 1.6)
        fr.fill(dress, W_DRESS, 'soft', vgrad=0.35, blur=1.8)
        folds(fr, dress, W_DRESS, [hx_ - 3, hx_ + 3], hem - 5, hem + 1)
        frill = dress & (PY > hem - 0.5)
        fr.fill(frill, W_FRILL, 'flat', group='frill')
        fr.fill(ell(hx_ - 2, sh + 1, 3.2, 1.8), W_COLLAR, 'soft', group='col')
        fr.fill(ell(hx_ - 4.5, sh + 2.2, 1.8, 1.6), W_BOW, 'ball', group='bow')
        head_side(fr, hy, SKIN, W_HAIR, W_IRIS, hx_=hx_)
        witch_hat(fr, hx_ + 1, hat_y, 12.5, 15, W_HAT, W_BAND, d, star=hx('#ffe27a'))
        ex, ey = arm_side(fr, r, hx_ - 0.5, sh + 2, 8, W_DRESS, SKIN, near=True, cuff=W_COLLAR, puff=0.8, fixed=(-3, 7))
        pumpkin_bucket(fr, int(ex), int(ey), d)
    else:
        legs_front(fr, r, hem - 2, 2.6, 3, W_STOCK, W_BOOT, up=True)
        dress = gown(sh, hem, 12, 21)
        fr.fill(dress, W_DRESS, 'soft', vgrad=0.35, blur=1.8)
        folds(fr, dress, W_DRESS, [24, 28, 32], hem - 7, hem + 1)
        frill = dress & (PY > hem - 0.5)
        fr.fill(frill, W_FRILL, 'flat', group='frill')
        ex, ey = arm_front(fr, r, -1, CX - 6.0, sh + 2, 8, W_DRESS, SKIN, cuff=W_COLLAR, puff=0.8, d=UP)
        pumpkin_bucket(fr, int(ex), int(ey), d)
        arm_front(fr, r, 1, CX + 6.0, sh + 2, 8, W_DRESS, SKIN, cuff=W_COLLAR, puff=0.8, d=UP)
        head_back(fr, hy, W_HAIR)
        for side in (-1, 1):
            pig = bez([(CX + side * 6, hy + 5), (CX + side * 10, hy + 9), (CX + side * 9.5 + r.lag * 0.6, hy + 14)], 3.0, 1.8)
            fr.fill(pig, W_HAIR, 'soft', group=('pig', side))
        witch_hat(fr, CX, hat_y, 13.5, 15, W_HAT, W_BAND, d, buckle=False, star=hx('#ffe27a'))


NOSE = hx('#3a2228')
PINK = Mat('#f4a3b4')
GOLD = Mat('#f2c04e')
WOOD = Mat('#9a6a42')
STRAW = Mat('#e8c46a')


def w_mouth(fr, x, y, col=None):
    c = col or hx('#6a3640')
    fr.put([(x - 1, y), (x, y + 1), (x + 1, y + 1), (x + 2, y)], c)


def animal_front(fr, hy, fur, *, rx=9.5, ry=8.0, muzzle=None, mz=(4.2, 3.0, 3.2), eye_y=1, eye_x=(21, 34),
                 nose=NOSE, mouth=True, blush_on=True, eye_shape='bead', extra=None, shade_mode='ball'):
    head = ell(CX, hy, rx, ry)
    if extra is not None:
        head |= extra
    fr.fill(head, fur, shade_mode, group='head', c=(CX - 1.5, hy - 1.5), r=(rx + 2.5, ry + 2.5)) if shade_mode == 'ball' \
        else fr.fill(head, fur, shade_mode, group='head')
    if muzzle is not None:
        mzm = ell(CX, hy + mz[2], mz[0], mz[1]) & head
        fr.fill(mzm, muzzle, 'soft', group='head', bias=0.05)
    ey = int(hy + eye_y)
    eye_l(fr, eye_x[0], ey, Mat('#2a1a22'), eye_shape)
    eye_r(fr, eye_x[1], ey, Mat('#2a1a22'), eye_shape)
    ny = int(hy + mz[2] - 1)
    if nose is not None:
        fr.put([(27, ny), (28, ny)], nose)
    if mouth:
        w_mouth(fr, 27, ny + 1)
    if blush_on:
        fr.put([(eye_x[0] - 1, ey + 4), (eye_x[0], ey + 4)], BLUSH)
        fr.put([(eye_x[1], ey + 4), (eye_x[1] + 1, ey + 4)], BLUSH)
    return head


def animal_side(fr, hy, hx_, fur, *, rx=9.0, ry=8.0, snout=(4.0, 2.8), muzzle=None, eye_y=1, nose=NOSE,
                mouth=True, blush_on=True, eye_shape='bead', snout_dy=3.0, extra=None):
    head = ell(hx_ + 0.5, hy, rx, ry)
    sn = ell(hx_ - rx + snout[0] * 0.6, hy + snout_dy, snout[0], snout[1])
    head |= sn
    if extra is not None:
        head |= extra
    fr.fill(head, fur, 'ball', group='head', c=(hx_ - 2, hy - 1.5), r=(rx + 3, ry + 2.5))
    if muzzle is not None:
        mzm = (sn | ell(hx_ - rx + 3.5, hy + snout_dy + 1, 4.0, 2.6)) & head
        fr.fill(mzm, muzzle, 'soft', group='head', bias=0.05)
    ey = int(hy + eye_y)
    ex = int(hx_ - rx + 5)
    if eye_shape == 'bead':
        fr.stamp(ex, ey, ['.kk', 'kwk', 'kkd', '.kk'], {'k': INK, 'w': WHITE, 'd': hx('#5a4048')})
    else:
        fr.stamp(ex, ey, ['kk', 'wk', 'kk'], {'k': INK, 'w': WHITE})
    tipx = int(np.nonzero(sn.any(0))[0].min())
    if nose is not None:
        fr.put([(tipx, int(hy + snout_dy - 1)), (tipx + 1, int(hy + snout_dy - 1))], nose)
    if mouth:
        fr.put([(tipx + 2, int(hy + snout_dy + 1)), (tipx + 3, int(hy + snout_dy + 2))], hx('#6a3640'))
    if blush_on:
        fr.put([(ex + 2, ey + 4), (ex + 3, ey + 4)], BLUSH)
    return head


def animal_back(fr, hy, fur, rx=9.5, ry=8.0, hx_=CX):
    head = ell(hx_, hy, rx, ry)
    fr.fill(head, fur, 'ball', group='head', c=(hx_ - 1.5, hy - 1.5), r=(rx + 2.5, ry + 2.5))
    return head


def ear(fr, base, tip, w, fur, inner=None, tipcol=None, group='ear', inner_w=0.45):
    m = bez([base, ((base[0] + tip[0]) / 2, (base[1] + tip[1]) / 2), tip], w, 0.6)
    fr.fill(m, fur, 'soft', group=group, blur=1.0)
    if inner is not None:
        im = bez([(base[0], base[1] - 0.5), ((base[0] + tip[0]) / 2, (base[1] + tip[1]) / 2 + 0.5), tip], w * inner_w, 0.3) & ero(m)
        fr.fill(im, inner, 'soft', group=group, line=False)
    if tipcol is not None:
        tm = m & (((PX - tip[0]) ** 2 + (PY - tip[1]) ** 2) < 3.2 ** 2)
        fr.fill(tm, tipcol, 'soft', group=group, line=False)
    return m


def star_dots(fr, mask, pts, col=GOLD):
    for (x, y, big) in pts:
        x, y = int(x), int(y)
        if not (0 <= y < H and 0 <= x < W and mask[y, x]):
            continue
        if big:
            fr.paint([(x, y - 1), (x - 1, y), (x + 1, y), (x, y + 1)], col, 2)
            fr.paint([(x, y)], col, 4)
        else:
            fr.paint([(x, y)], col, 3)


def stars_in(mask, seed, n, big_every=3):
    """在遮罩裡挑幾個確定性的位置撒星星（不用亂數：固定的 hash）。"""
    ys, xs = np.nonzero(ero(mask, 2))
    if len(xs) == 0:
        return []
    out = []
    for i in range(n):
        k = (seed * 7919 + i * 104729) % len(xs)
        out.append((int(xs[k]), int(ys[k]), i % big_every == 0))
    return out


def tail_bush(fr, base, mid, tip, r0, r1, fur, tipmat, group='tail'):
    m = bez([base, mid, tip], r0, r1)
    m |= ell(mid[0], mid[1], r0 + 0.6, r0 + 0.2)
    fr.fill(m, fur, 'soft', group=group, blur=1.6)
    tm = m & (((PX - tip[0]) ** 2 + (PY - tip[1]) ** 2) < (r1 + 2.6) ** 2)
    fr.fill(tm, tipmat, 'soft', group=group, line=False)
    return m


# ═══════════════ 青蛙（frog）：黃雨衣＋釣竿 ═══════════════
F_SKIN = Mat('#78c25e')
F_BELLY = Mat('#dcefa4')
F_COAT = Mat('#f7cd3c')
F_COAT_D = Mat('#e0a62a')
F_ROD = Mat('#a8754a')
F_EYEW = Mat('#fffaf0', cols=['#b8c4c0', '#dfe6e0', '#fbfaf2', '#ffffff', '#ffffff'], ln='#5a6a60')


def fishing_rod(fr, hand, tip, sway=0):
    pts = bezpts([hand, ((hand[0] + tip[0]) / 2 + 1, (hand[1] + tip[1]) / 2), tip], 80)
    for i, (x, y) in enumerate(pts):
        fr.put([(x, y)], F_ROD[2] if i % 5 else F_ROD[3])
    # 釣線＋浮標
    tx, ty = pts[-1]
    lx = tx + (1 if tip[0] >= hand[0] else -1) + sway
    for y in range(ty + 1, ty + 9):
        fr.overlay([(lx if y > ty + 3 else tx + (lx - tx) * (y - ty) // 4, y)], hx('#e8f0f4'))
    by = ty + 9
    fr.put([(lx - 1, by), (lx, by), (lx + 1, by)], hx('#e8404a'))
    fr.put([(lx - 1, by + 1), (lx, by + 1), (lx + 1, by + 1)], hx('#fff6ec'))
    fr.put([(lx, by - 1)], hx('#e8404a'))
    fr.put([(lx, by + 2)], hx('#c8d0d8'))
    # 捲線器
    fr.put([(hand[0] + (1 if tip[0] >= hand[0] else -1) * 0, hand[1] - 3)], hx('#c0c8d0'))


def frog_eyes_front(fr, hy):
    for side in (-1, 1):
        cx = CX + side * 6.0
        wm = ell(cx, hy - 5.0, 2.7, 2.6)
        fr.fill(wm, F_EYEW, 'ball', group='eyew', line=True)
        px_ = int(cx - 0.5) + (0 if side < 0 else 0)
        fr.put([(px_ - 1 + (1 if side > 0 else 0), int(hy - 6)), (px_ + (1 if side > 0 else 0), int(hy - 6)),
                (px_ - 1 + (1 if side > 0 else 0), int(hy - 5)), (px_ + (1 if side > 0 else 0), int(hy - 5)),
                (px_ - 1 + (1 if side > 0 else 0), int(hy - 4)), (px_ + (1 if side > 0 else 0), int(hy - 4))], INK)
        fr.put([(px_ - 1 + (1 if side > 0 else 0), int(hy - 6))], WHITE)


def draw_frog(fr, r):
    b = r.bob
    hy = 41 + b
    sh = 47 + b
    hem = 61 + b
    d = r.d
    if d in (DOWN, UP):
        up = d == UP
        legs_front(fr, r, hem - 2, 3.2, 3, F_SKIN, F_SKIN, shoe_rx=3.1, shoe_ry=1.9, up=up)
        if not up:
            for side in (-1, 1):   # 腳趾
                lifted = r.step == side
                y = FB - (2 if lifted else 0)
                x = int(CX + side * 3.2 + side * 0.3)
                fr.paint([(x - 1, y), (x + 1, y)], F_SKIN, 1)
        hood = ell(CX, sh + 1.5, 10.5, 3.6)
        fr.fill(hood, F_COAT_D, 'soft', group='hood')
        coat = gown(sh, hem, 16, 22)
        fr.fill(coat, F_COAT, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, coat, F_COAT, [22, 34], hem - 6, hem + 1)
        hem_band(fr, coat, F_COAT, 1)
        if not up:
            fr.paint([(28, y) for y in range(sh + 3, hem + 2)], F_COAT, 1)
            fr.paint([(27, y) for y in range(sh + 3, hem + 2)], F_COAT, 3)
            for y in (sh + 5, sh + 9, sh + 13):
                fr.put([(29, y)], hx('#fff4d0'))
                fr.put([(29, y + 1)], F_COAT[0])
            # 口袋
            fr.paint([(x, hem - 5) for x in (20, 21, 22, 23)], F_COAT, 0)
            fr.paint([(x, hem - 5) for x in (32, 33, 34, 35)], F_COAT, 0)
            # 鈕扣領片
            fr.paint(sym(cap(24, sh + 1, 27, sh + 4, 0.8)) & coat, F_COAT, 1)
        else:
            fr.fill(ell(CX, sh + 3, 7.5, 4.0), F_COAT_D, 'soft', group='hood2')
            fr.paint([(CX - 0.5 + dx, sh + 6) for dx in range(-4, 5)], F_COAT_D, 0)
        hand_side = -1 if up else 1
        arm_front(fr, r, -hand_side, CX - hand_side * 7.5, sh + 2, 8, F_COAT, F_SKIN, d=d, rad=2.4)
        ex, ey = arm_front(fr, r, hand_side, CX + hand_side * 7.5, sh + 2, 8, F_COAT, F_SKIN, d=d, rad=2.4)
        # 釣竿
        if not up:
            fishing_rod(fr, (int(ex), int(ey)), (int(ex + 7), int(ey - 31)), r.sway)
        else:
            fishing_rod(fr, (int(ex), int(ey)), (int(ex - 7), int(ey - 31)), -r.sway)
        fr.fill(ell(ex, ey + 0.6, 1.75, 1.75), F_SKIN, 'ball', group='hand2')
        # 頭
        head = ell(CX, hy, 11.6, 7.4)
        domes = sym(ell(CX - 6.0, hy - 4.8, 3.9, 3.7))
        fr.fill(head | domes, F_SKIN, 'ball', group='head', c=(CX - 2, hy - 3), r=(14, 11))
        if not up:
            chin = ell(CX, hy + 4.6, 8.5, 3.4) & head
            fr.fill(chin, F_BELLY, 'soft', group='head', bias=0.05)
            frog_eyes_front(fr, hy)
            mouth = [(21, hy + 1), (22, hy + 2), (23, hy + 2)] + [(x, hy + 3) for x in range(24, 32)] + [(32, hy + 2), (33, hy + 2), (34, hy + 1)]
            fr.paint(mouth, F_SKIN, 'ln')
            fr.put([(26, hy - 1), (29, hy - 1)], F_SKIN['ln'])
            fr.put([(19, hy + 1), (20, hy + 1), (35, hy + 1), (36, hy + 1)], BLUSH)
            fr.put([(19, hy + 2), (36, hy + 2)], BLUSH2)
            # 背上的斑點
        else:
            spots = [(23, hy - 1), (24, hy - 1), (31, hy + 1), (32, hy + 1), (28, hy - 4), (27, hy + 3)]
            fr.paint(spots, F_SKIN, 1)
            fr.paint(edge(head, 'b'), F_SKIN, 0)
    else:
        hx_ = CX - 1
        arm_side(fr, r, hx_ + 2, sh + 2, 8, F_COAT, F_SKIN, near=False, rad=2.4)
        legs_side(fr, r, hem - 2, hx_, F_SKIN, F_SKIN, toe=3.0)
        hood = ell(hx_ + 5, sh + 2, 4.0, 4.5)
        fr.fill(hood, F_COAT_D, 'soft', group='hood')
        coat = poly([(hx_ - 5, sh + 1), (hx_ + 5, sh + 1), (hx_ + 8, hem + 1), (hx_ - 8, hem + 1)])
        coat |= ell(hx_, sh + 2.5, 5.5, 3) | ell(hx_, hem + 0.2, 8, 1.6)
        fr.fill(coat, F_COAT, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, coat, F_COAT, [hx_ + 3, hx_ - 3], hem - 6, hem + 1)
        hem_band(fr, coat, F_COAT, 1)
        fr.paint([(hx_ - 6 + (y - sh) * -0.1, y) for y in range(sh + 3, hem + 1)], F_COAT, 1)
        head = ell(hx_ + 0.5, hy, 10.5, 7.2) | ell(hx_ - 8.5, hy + 1.5, 3, 4.5)
        dome_f = ell(hx_ - 4.0, hy - 4.8, 3.8, 3.7)
        dome_b = ell(hx_ + 2.5, hy - 5.0, 3.4, 3.4)
        fr.fill(dome_b, F_SKIN.dark(1), 'ball', group='dome_b')
        fr.fill(head | dome_f, F_SKIN, 'ball', group='head', c=(hx_ - 3, hy - 3), r=(13, 11))
        chin = ell(hx_ - 3, hy + 4.6, 8, 3.2) & head
        fr.fill(chin, F_BELLY, 'soft', group='head', bias=0.05)
        wm = ell(hx_ - 4.5, hy - 5.0, 2.5, 2.5)
        fr.fill(wm, F_EYEW, 'ball', group='eyew')
        ex0 = int(hx_ - 6)
        fr.put([(ex0, int(hy - 6)), (ex0 + 1, int(hy - 6)), (ex0, int(hy - 5)), (ex0 + 1, int(hy - 5)), (ex0, int(hy - 4)), (ex0 + 1, int(hy - 4))], INK)
        fr.put([(ex0, int(hy - 6))], WHITE)
        mouth = [(int(hx_ - 9), hy + 2)] + [(x, hy + 3) for x in range(int(hx_ - 8), int(hx_ + 1))] + [(int(hx_ + 1), hy + 2)]
        fr.paint(mouth, F_SKIN, 'ln')
        fr.put([(int(hx_ - 10), hy - 1)], F_SKIN['ln'])
        fr.put([(int(hx_ - 5), hy + 1), (int(hx_ - 4), hy + 1)], BLUSH)
        ex, ey = arm_side(fr, r, hx_ - 1, sh + 2, 8, F_COAT, F_SKIN, near=True, rad=2.4, fixed=(-5, 5))
        fishing_rod(fr, (int(ex), int(ey)), (int(ex - 13), int(ey - 27)), -r.sway)
        fr.fill(ell(ex, ey + 0.6, 1.75, 1.75), F_SKIN, 'ball', group='hand2')


# ═══════════════ 共用道具 ═══════════════
BASKET = Mat('#c08a52')
CLOTH = Mat('#e2565c')
APPLE = Mat('#e8443e')


def basket(fr, x, y, d=DOWN):
    """竹籃：x,y ＝手（提把頂）。"""
    x = int(x)
    y = int(y)
    body = poly([(x - 4.5, y + 3.5), (x + 5.5, y + 3.5), (x + 4.5, y + 9), (x - 3.5, y + 9)]) | ell(x + 0.5, y + 8.6, 4, 1.4)
    fr.fill(ell(x - 1, y + 3.4, 2.6, 1.8), CLOTH, 'ball', group='bk_in')
    fr.paint([(x - 2, y + 3), (x, y + 3)], CLOTH, 4)
    fr.fill(ell(x + 2.2, y + 2.8, 1.9, 1.9), APPLE, 'ball', group='bk_ap')
    fr.put([(x + 2, y)], hx('#5a3a20'))
    fr.fill(body, BASKET, 'soft', group='bk')
    for yy in range(y + 5, y + 10):
        for xx in range(x - 5, x + 7):
            if 0 <= yy < H and body[yy, xx] and (xx + yy * 2) % 4 == 0:
                fr.paint([(xx, yy), (xx + 1, yy)], BASKET, 1)
    rim = body & (YY <= y + 4)
    fr.paint(rim, BASKET, 3)
    fr.paint(rim & (PX < x - 1), BASKET, 4)
    for p in [(x - 4, y + 3), (x - 3, y + 1), (x - 2, y), (x - 1, y - 1), (x, y - 1), (x + 1, y - 1), (x + 2, y), (x + 3, y + 1), (x + 4, y + 2), (x + 5, y + 3)]:
        fr.put([p], BASKET[0])


def tail_cotton(fr, cx, cy, mat, rr=2.8):
    m = ell(cx, cy, rr, rr * 0.92)
    fr.fill(m, mat, 'ball', group='tail')
    return m


# ═══════════════ 狐狸（fox）：星空斗篷＋竹籃 ═══════════════
X_FUR = Mat('#ef8a3c')
X_CREAM = Mat('#fcf2e0')
X_CLOAK = Mat('#30407c')
X_LEG = Mat('#4c302c')
X_INNER = Mat('#f6c6a8')


def fox_ears(fr, hy, hx_=CX, d=DOWN, lag=0):
    if d == SIDE:
        ear(fr, (hx_ + 3.5, hy - 5), (hx_ + 6 + lag * 0.4, hy - 14), 3.0, X_FUR.dark(1), None, X_LEG, group='earb')
        ear(fr, (hx_ - 0.5, hy - 5), (hx_ + 0.5 + lag * 0.4, hy - 14.5), 3.2, X_FUR, X_INNER, X_LEG, group='earf')
        return
    for side in (-1, 1):
        ear(fr, (CX + side * 5.0, hy - 5), (CX + side * 8.0, hy - 14 + (lag if side > 0 else 0) * 0.5), 3.3,
            X_FUR, X_INNER if d == DOWN else None, X_LEG, group=('ear', side))


def draw_fox(fr, r):
    b = r.bob
    hy = 35 + b
    sh = 45 + b
    hem = 62 + b
    d = r.d
    if d == DOWN:
        tail_bush(fr, (CX + 6, hem - 3), (CX + 13 + r.sway * 0.6, hem - 7), (CX + 14 + r.sway, hem - 15), 3.4, 2.4, X_FUR, X_CREAM)
        legs_front(fr, r, hem - 2, 2.6, 3, X_LEG, X_LEG)
        cloak = gown(sh, hem, 15, 24)
        fr.fill(cloak, X_CLOAK, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, cloak, X_CLOAK, [21, 35], hem - 8, hem + 1)
        fr.paint([(28, y) for y in range(sh + 3, hem + 2)], X_CLOAK, 0)
        hem_band(fr, cloak, GOLD, 2)
        star_dots(fr, cloak, [(22, hem - 4, True), (33, hem - 9, True), (25, sh + 8, False), (31, sh + 5, False), (24, hem - 10, False), (32, hem - 2, False), (36, hem - 4, False)])
        ex, ey = arm_front(fr, r, -1, CX - 7, sh + 2, 8, X_CLOAK, X_LEG, d=d, rad=2.4)
        basket(fr, ex, ey)
        arm_front(fr, r, 1, CX + 7, sh + 2, 8, X_CLOAK, X_LEG, d=d, rad=2.4)
        hood = ell(CX, hy + 0.5, 11.6, 10.2) & (PY < hy + 10)
        fr.fill(hood, X_CLOAK, 'soft', group='hood', blur=1.4)
        fox_ears(fr, hy, d=d, lag=r.lag)
        hood_rim = hood & ~ell(CX, hy + 1.5, 9.6, 8.6)
        fr.fill(hood_rim & (PY < hy + 8), X_CLOAK, 'soft', group='hood2', blur=1.2, bias=0.05)
        animal_front(fr, hy + 1, X_FUR, rx=9.0, ry=7.6, muzzle=X_CREAM, mz=(4.3, 3.0, 3.6), mouth=False, nose=None, blush_on=False)
        cheeks = sym(poly([(CX - 3, hy + 3), (CX - 11, hy + 5), (CX - 8.5, hy + 6.5), (CX - 10, hy + 7.5), (CX - 4, hy + 8.4)]))
        fr.fill(cheeks & ~ell(CX, hy + 4.6, 4.3, 3.0), X_CREAM, 'soft', group='head')
        eye_l(fr, 21, hy + 2, None, 'bead')
        eye_r(fr, 34, hy + 2, None, 'bead')
        fr.put([(27, hy + 3), (28, hy + 3)], NOSE)
        w_mouth(fr, 27, hy + 4)
        fr.put([(20, hy + 6), (21, hy + 6), (34, hy + 6), (35, hy + 6)], BLUSH)
        fr.fill(ell(CX, sh + 2, 1.8, 1.6), GOLD, 'ball', group='clasp')
    elif d == SIDE:
        hx_ = CX - 2
        tail_bush(fr, (hx_ + 5, hem - 4), (hx_ + 13, hem - 6 + r.sway * 0.5), (hx_ + 17, hem - 13 + r.sway), 3.6, 2.6, X_FUR, X_CREAM)
        arm_side(fr, r, hx_ + 2, sh + 2, 8, X_CLOAK, X_LEG, near=False, rad=2.4)
        legs_side(fr, r, hem - 2, hx_, X_LEG, X_LEG, toe=2.5)
        cloak = poly([(hx_ - 5, sh + 1), (hx_ + 5, sh + 1), (hx_ + 10, hem + 1), (hx_ - 8, hem + 1)])
        cloak |= ell(hx_, sh + 2.5, 5.5, 3) | ell(hx_ + 1, hem + 0.2, 9, 1.6)
        fr.fill(cloak, X_CLOAK, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, cloak, X_CLOAK, [hx_ + 4, hx_ - 2], hem - 7, hem + 1)
        hem_band(fr, cloak, GOLD, 2)
        star_dots(fr, cloak, [(hx_ + 5, hem - 4, True), (hx_ - 3, hem - 8, True), (hx_, sh + 6, False), (hx_ + 7, hem - 9, False), (hx_ - 5, hem - 2, False)])
        hood = ell(hx_ + 2.5, hy + 0.5, 10, 10.2) & (PY < hy + 10)
        fr.fill(hood, X_CLOAK, 'soft', group='hood', blur=1.4)
        fox_ears(fr, hy, hx_=hx_, d=d, lag=r.lag)
        hood_f = ell(hx_ + 3.5, hy + 0.5, 8.6, 10.2) & (PY < hy + 10) & ~ell(hx_ - 1.5, hy + 1.5, 7.5, 8.2)
        animal_side(fr, hy + 1, hx_, X_FUR, rx=8.0, ry=7.4, snout=(4.6, 2.6), muzzle=X_CREAM, snout_dy=3.2)
        fr.fill(hood_f & (PX > hx_ + 1), X_CLOAK, 'soft', group='hood2', blur=1.2)
        fr.fill(ell(hx_ - 2, sh + 2, 1.8, 1.6), GOLD, 'ball', group='clasp')
        ex, ey = arm_side(fr, r, hx_ - 1, sh + 2, 8, X_CLOAK, X_LEG, near=True, rad=2.4, fixed=(-3, 7))
        basket(fr, ex, ey)
    else:
        legs_front(fr, r, hem - 2, 2.6, 3, X_LEG, X_LEG, up=True)
        cloak = gown(sh, hem, 15, 24)
        fr.fill(cloak, X_CLOAK, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, cloak, X_CLOAK, [22, 28, 34], hem - 8, hem + 1)
        hem_band(fr, cloak, GOLD, 2)
        star_dots(fr, cloak, [(23, hem - 5, True), (33, sh + 7, True), (26, sh + 4, False), (31, hem - 3, False), (36, hem - 8, False), (21, sh + 9, False)])
        arm_front(fr, r, -1, CX - 7, sh + 2, 8, X_CLOAK, X_LEG, d=d, rad=2.4)
        ex, ey = arm_front(fr, r, 1, CX + 7, sh + 2, 8, X_CLOAK, X_LEG, d=d, rad=2.4)
        basket(fr, ex, ey, d)
        tail_bush(fr, (CX, sh + 9), (CX + 2 + r.sway * 0.6, hem - 4), (CX - 1 + r.sway, hem + 1), 3.8, 2.6, X_FUR, X_CREAM)
        fox_ears(fr, hy, d=d, lag=r.lag)
        hood = ell(CX, hy + 0.5, 11.6, 10.2) | ell(CX, hy + 6, 8, 6)
        hood &= PY < sh + 6
        fr.fill(hood, X_CLOAK, 'soft', group='hood', blur=1.6, vgrad=0.1)
        fr.paint([(28, y) for y in range(int(hy - 8), int(hy + 2))], X_CLOAK, 1)
        star_dots(fr, hood, [(24, hy - 3, True), (32, hy + 2, False), (30, hy - 6, False)])


# ═══════════════ 兔子（rabbit）：吊帶褲＋斜背包 ═══════════════
R_FUR = Mat('#f7eddc')
R_SHIRT = Mat('#fdfcf6', cols=['#b8bcc8', '#dfe0e6', '#fbfbf6', '#ffffff', '#ffffff'], ln='#8a8c9c')
R_OVER = Mat('#5c8fd2')
R_BOW = Mat('#e0464e')
R_BAG = Mat('#ae6e3e')


def rabbit_ears(fr, hy, fur, inner, d, lag, hx_=CX, tall=15, spread=1.0):
    if d == SIDE:
        ear(fr, (hx_ + 3.5, hy - 6), (hx_ + 7 + lag * 0.5, hy - 6 - tall + 1), 2.6, fur.dark(1), None, group='earb')
        ear(fr, (hx_ + 0.5, hy - 6), (hx_ + 4 + lag * 0.5, hy - 6 - tall), 2.9, fur, inner, group='earf', inner_w=0.5)
        return
    for side in (-1, 1):
        tip = (CX + side * (4.5 + spread) + (lag * 0.5 if side > 0 else 0), hy - 6 - tall + (abs(lag) * 0.5 if side < 0 else 0))
        ear(fr, (CX + side * 3.6, hy - 5.5), tip, 2.9, fur, inner if d == DOWN else None, group=('ear', side), inner_w=0.5)


def satchel(fr, x, y, d=DOWN):
    bag = rect(int(x - 3), int(y), int(x + 3), int(y + 5)) | ell(x + 0.5, y + 5, 3.6, 1.2)
    fr.fill(bag, R_BAG, 'soft', group='bag')
    flap = bag & (YY <= y + 2)
    fr.fill(flap, R_BAG, 'soft', group='bag', bias=0.1, line=False)
    fr.paint(edge(flap, 'b'), R_BAG, 0)
    fr.put([(int(x), int(y + 3))], GOLD[3])


def draw_rabbit(fr, r):
    b = r.bob
    hy = 38 + b
    sh = 47 + b
    hem = 60 + b
    d = r.d
    if d in (DOWN, UP):
        up = d == UP
        legs_front(fr, r, hem - 1, 3.0, 4, R_FUR, R_FUR, shoe_rx=3.2, shoe_ry=2.0, up=up)
        shirt = gown(sh, hem - 2, 12, 15)
        fr.fill(shirt, R_SHIRT, 'soft', blur=1.6)
        over = (gown(sh, hem, 12, 16) & (PY >= sh + 7))
        if not up:
            over |= rect(24, sh + 3, 31, sh + 7)
        over |= rect(22, hem - 1, 26, hem + 1) | rect(29, hem - 1, 33, hem + 1)
        fr.fill(over, R_OVER, 'soft', vgrad=0.2)
        fr.paint([(27, y) for y in range(hem - 3, hem + 2)], R_OVER, 0)
        if not up:
            fr.paint(rect(26, sh + 4, 29, sh + 5), R_OVER, 1)
            fr.paint([(x, sh + 4) for x in range(26, 30)], R_OVER, 0)
            fr.fill(sym(cap(23.0, sh + 1, 24.5, sh + 4, 0.9)), R_OVER, 'soft', group='strap')
            fr.put([(24, sh + 4), (31, sh + 4)], GOLD[4])
            fr.fill(sym(poly([(28, sh + 1.5), (24.5, sh - 0.2), (24.5, sh + 3.2)])), R_BOW, 'soft', group='bow')
            fr.put([(27, sh + 1), (28, sh + 1)], R_BOW[3])
            fr.paint(cap(22, sh + 1, 33, sh + 9, 0.6), R_BAG, 1)
        else:
            fr.fill(cap(23, sh + 1, 32, sh + 7, 0.9) | cap(32, sh + 1, 23, sh + 7, 0.9), R_OVER, 'soft', group='strap')
            tail_cotton(fr, CX, hem - 4, R_FUR)
        bag_side = -1 if up else 1
        arm_front(fr, r, -1, CX - 6.5, sh + 2, 7, R_SHIRT, R_FUR, d=d, puff=0.8, rad2=1.6)
        arm_front(fr, r, 1, CX + 6.5, sh + 2, 7, R_SHIRT, R_FUR, d=d, puff=0.8, rad2=1.6)
        satchel(fr, CX + bag_side * 9.5, hem - 6, d)
        if not up:
            animal_front(fr, hy, R_FUR, rx=9.6, ry=8.0, muzzle=R_SHIRT, mz=(3.6, 2.4, 3.6), nose=PINK[1])
        else:
            animal_back(fr, hy, R_FUR, 9.6, 8.0)
        rabbit_ears(fr, hy, R_FUR, PINK, d, r.lag)
    else:
        hx_ = CX - 1
        arm_side(fr, r, hx_ + 2, sh + 2, 7, R_SHIRT, R_FUR, near=False)
        legs_side(fr, r, hem - 1, hx_, R_FUR, R_FUR, w=2.0, toe=3.0)
        tail_cotton(fr, hx_ + 6.5, hem - 4, R_FUR)
        shirt = poly([(hx_ - 4, sh + 1), (hx_ + 4, sh + 1), (hx_ + 5, hem - 1), (hx_ - 5, hem - 1)]) | ell(hx_, sh + 2.5, 4.5, 3)
        fr.fill(shirt, R_SHIRT, 'soft')
        over = (poly([(hx_ - 5, sh + 6), (hx_ + 5, sh + 6), (hx_ + 6, hem + 1), (hx_ - 6, hem + 1)])) | rect(int(hx_ - 5), sh + 3, int(hx_ - 2), sh + 6)
        fr.fill(over, R_OVER, 'soft', vgrad=0.2)
        fr.fill(cap(hx_ - 3, sh + 1, hx_ - 3.5, sh + 4, 0.9), R_OVER, 'soft', group='strap')
        fr.fill(ell(hx_ - 4.5, sh + 1.5, 1.8, 1.4), R_BOW, 'ball', group='bow')
        animal_side(fr, hy, hx_, R_FUR, rx=9.0, ry=7.8, snout=(3.4, 2.6), muzzle=R_SHIRT, snout_dy=3.4, nose=PINK[1])
        rabbit_ears(fr, hy, R_FUR, PINK, d, r.lag, hx_=hx_)
        fr.paint(cap(hx_ - 4, sh + 1, hx_ + 3, sh + 9, 0.6), R_BAG, 1)
        satchel(fr, hx_ - 0.5, hem - 6, d)
        arm_side(fr, r, hx_ - 0.5, sh + 2, 7, R_SHIRT, R_FUR, near=True, puff=0.8)


# ═══════════════ 刺蝟（hedgehog）：貝雷帽＋圍巾 ═══════════════
H_SPINE = Mat('#8c5e3e')
H_FACE = Mat('#f2dcc0')
H_BERET = Mat('#b83c4c')
H_SCARF = Mat('#5ea2de')
H_FOOT = Mat('#7a4e3a')


def spiky(cx, cy, rx, ry, n=18, sp=3.0, a0=0, a1=360, phase=0.0):
    m = ell(cx, cy, rx - 1.5, ry - 1.5)
    for i in range(n):
        a = np.radians(a0 + (a1 - a0) * (i + 0.5 + phase) / n)
        ca, sa = np.cos(a), np.sin(a)
        tip = (cx + ca * (rx + sp * 0.4), cy + sa * (ry + sp * 0.4))
        w = 2.2
        b1 = (cx + ca * (rx - 3) - sa * w, cy + sa * (ry - 3) + ca * w)
        b2 = (cx + ca * (rx - 3) + sa * w, cy + sa * (ry - 3) - ca * w)
        m |= poly([b1, tip, b2])
    return m


def spine_detail(fr, m, cx, cy):
    """刺：外圈亮尖、往中心的放射暗線。"""
    fr.paint(m & ~ero(m) & (PY < cy), H_SPINE, 3)
    ys, xs = np.nonzero(m & ero(m, 1))
    for y, x in zip(ys, xs):
        ang = np.arctan2(y + 0.5 - cy, x + 0.5 - cx)
        # 沿放射方向的短刺：依角度與半徑錯開，不排成車輪
        rr = np.hypot(x + 0.5 - cx, y + 0.5 - cy)
        k = int(np.degrees(ang) / 13 + 400) + int(rr / 3.2) * 7
        t = (np.degrees(ang) / 13) % 1.0
        if k % 3 == 0 and t < 0.35:
            fr.paint([(x, y)], H_SPINE, 0 if y > cy else 1)
        elif k % 3 == 1 and t > 0.6 and y < cy + 4:
            fr.paint([(x, y)], H_SPINE, 3)


def beret(fr, cx, cy, d=DOWN):
    m = ell(cx, cy, 8.0, 3.2) | ell(cx + 1.5, cy - 1.0, 6.5, 3.0)
    fr.fill(m, H_BERET, 'soft', group='beret', blur=1.3, bias=0.03)
    fr.paint(edge(m, 'b'), H_BERET, 0)
    fr.fill(ell(cx + 1, cy - 4, 1.0, 1.4), H_BERET, 'ball', group='nub')


def draw_hedgehog(fr, r):
    b = r.bob
    hy = 42 + b
    d = r.d
    if d == DOWN:
        sp = spiky(CX, hy + 6, 14.0, 13.5, n=20, sp=3.2, phase=r.sway * 0.15) & (PY < 62 + b)
        fr.fill(sp, H_SPINE, 'soft', blur=1.8)
        spine_detail(fr, sp, CX, hy + 6)
        legs_front(fr, r, 60 + b, 3.4, 3, H_FACE, H_FOOT, shoe_rx=2.8)
        body = ell(CX, 54.5 + b, 9.4, 7.6)
        fr.fill(body, H_FACE, 'soft', vgrad=0.2)
        arm_front(fr, r, -1, CX - 7.5, 50 + b, 5, H_FACE, H_FOOT, d=d, rad=1.9, hand_r=1.5)
        arm_front(fr, r, 1, CX + 7.5, 50 + b, 5, H_FACE, H_FOOT, d=d, rad=1.9, hand_r=1.5)
        face = ell(CX, hy + 1.5, 9.0, 7.6)
        fr.fill(face, H_FACE, 'ball', group='face', c=(CX - 1.5, hy), r=(12, 10))
        fore = (ell(CX, hy - 3.5, 8.6, 4.0) & (PY < hy - 2)) | sym(poly([(CX - 6, hy - 4), (CX - 4.5, hy + 0.5), (CX - 3, hy - 4)])) | poly([(CX - 1.5, hy - 4), (CX, hy - 0.5), (CX + 1.5, hy - 4)])
        fr.fill(fore & face, H_SPINE, 'soft', group='fore', blur=1.2)
        fr.paint(edge(fore & face, 't') & (PX < CX), H_SPINE, 3)
        fr.fill(ell(CX, hy + 4.4, 3.4, 2.4), H_FACE, 'soft', group='face', bias=0.12)
        eye_l(fr, 21, hy + 1, None, 'bead')
        eye_r(fr, 34, hy + 1, None, 'bead')
        fr.put([(27, hy + 3), (28, hy + 3), (27, hy + 4), (28, hy + 4)], NOSE)
        fr.put([(27, hy + 3)], hx('#8a6a70'))
        fr.put([(27, hy + 6), (28, hy + 6)], hx('#8a4a50'))
        fr.put([(20, hy + 5), (21, hy + 5), (34, hy + 5), (35, hy + 5)], BLUSH)
        scarf = ell(CX, hy + 10.2, 8.2, 2.2)
        fr.fill(scarf, H_SCARF, 'soft', group='scarf')
        fr.paint([(x, int(hy + 10)) for x in range(21, 36) if x % 3 == 0], H_SCARF, 4)
        tail = rect(22, int(hy + 11), 24, int(hy + 17 + abs(r.sway)))
        fr.fill(tail, H_SCARF, 'soft', group='scarf2')
        fr.paint([(22, int(hy + 13)), (23, int(hy + 13)), (24, int(hy + 13))], H_SCARF, 4)
        beret(fr, CX + 1, hy - 8)
    elif d == SIDE:
        hx_ = CX
        sp = spiky(hx_ + 3, hy + 6, 12.5, 13.5, n=18, sp=3.2, a0=-110, a1=150, phase=r.sway * 0.2) & (PY < 62 + b)
        sp &= ~(ell(hx_ - 4, hy + 8, 6, 9) & (PX < hx_ - 3))
        arm_side(fr, r, hx_ - 1, 50 + b, 5, H_FACE, H_FOOT, near=False, rad=1.9, hand_r=1.5)
        fr.fill(sp, H_SPINE, 'soft', blur=1.8)
        spine_detail(fr, sp, hx_ + 3, hy + 6)
        legs_side(fr, r, 60 + b, hx_ - 1, H_FACE, H_FOOT, w=1.8, toe=2.4, stride=3)
        body = ell(hx_ - 2, 54.5 + b, 6.5, 7.4)
        fr.fill(body, H_FACE, 'soft', vgrad=0.2)
        head = animal_side(fr, hy + 1, hx_ - 1, H_FACE, rx=8.0, ry=7.2, snout=(5.2, 2.6), snout_dy=3.0)
        fore = (ell(hx_ + 1, hy - 3, 8.5, 4.5) & (PY < hy - 1.5)) | poly([(hx_ - 4, hy - 4), (hx_ - 2.5, hy + 0.5), (hx_ - 1, hy - 4)])
        fr.fill(fore & head, H_SPINE, 'soft', group='fore', blur=1.2)
        scarf = ell(hx_ - 1, hy + 10, 6.5, 2.2)
        fr.fill(scarf, H_SCARF, 'soft', group='scarf')
        tail = bez([(hx_ + 4, hy + 10), (hx_ + 8 + r.sway * 0.6, hy + 12), (hx_ + 9 + r.sway, hy + 15)], 1.4, 1.2)
        fr.fill(tail, H_SCARF, 'soft', group='scarf2')
        beret(fr, hx_ + 1, hy - 7)
        arm_side(fr, r, hx_ - 3, 50 + b, 5, H_FACE, H_FOOT, near=True, rad=1.9, hand_r=1.5)
    else:
        legs_front(fr, r, 60 + b, 3.4, 3, H_FACE, H_FOOT, shoe_rx=2.8, up=True)
        arm_front(fr, r, -1, CX - 8.5, 50 + b, 5, H_FACE, H_FOOT, d=d, rad=1.9, hand_r=1.5)
        arm_front(fr, r, 1, CX + 8.5, 50 + b, 5, H_FACE, H_FOOT, d=d, rad=1.9, hand_r=1.5)
        sp = spiky(CX, hy + 6, 14.0, 13.5, n=20, sp=3.2, phase=r.sway * 0.15) & (PY < 62 + b)
        fr.fill(sp, H_SPINE, 'soft', blur=1.8, vgrad=0.15)
        spine_detail(fr, sp, CX, hy + 6)
        scarf = ell(CX, hy + 10, 8.0, 2.0)
        fr.fill(scarf, H_SCARF, 'soft', group='scarf')
        tail = rect(30, int(hy + 11), 32, int(hy + 16 + abs(r.sway)))
        fr.fill(tail, H_SCARF, 'soft', group='scarf2')
        beret(fr, CX - 1, hy - 8)


# ═══════════════ 小鹿（deer）：花冠＋葉子披肩 ═══════════════
D_FUR = Mat('#c98a52')
D_CREAM = Mat('#fbeedc')
D_LEAF = Mat('#5fa04a')
D_ANT = Mat('#efdcb4')
D_HOOF = Mat('#4c3028')
D_INNER = Mat('#f2b6a4')
FL_PINK = Mat('#f590b4')
FL_WHITE = Mat('#fffaf0', cols=['#c8c0c8', '#e8e2e6', '#fffaf0', '#ffffff', '#ffffff'], ln='#8a7a8a')
FL_YEL = Mat('#ffd24a')


def flower(fr, x, y, mat, center=None):
    x, y = int(x), int(y)
    fr.put([(x, y - 1), (x - 1, y), (x + 1, y), (x, y + 1)], mat[2])
    fr.put([(x - 1, y - 1)], mat[3])
    fr.put([(x, y)], (center or FL_YEL)[3])


def antlers(fr, hx_, hy, d, side_view=False):
    pts = []
    if d == SIDE:
        specs = [(hx_ + 1, 1), (hx_ + 4, 1)]
    else:
        specs = [(CX - 4, -1), (CX + 4, 1)]
    for x0, s in specs:
        m = cap(x0, hy - 6, x0 + s * 1.5, hy - 14, 0.9)
        m |= cap(x0 + s * 1.0, hy - 10.5, x0 + s * 4.5, hy - 13, 0.85)
        m |= cap(x0 + s * 1.5, hy - 14, x0 + s * 0.5, hy - 16.5, 0.8)
        mat = D_ANT if not (d == SIDE and x0 > hx_ + 2) else D_ANT.dark(1)
        fr.fill(m, mat, 'soft', group=('ant', x0), blur=0.8)


def deer_ears(fr, hx_, hy, d, lag):
    if d == SIDE:
        ear(fr, (hx_ + 3, hy - 3), (hx_ + 10, hy - 6 + lag * 0.5), 2.4, D_FUR, D_INNER, group='ear', inner_w=0.5)
        return
    for s in (-1, 1):
        ear(fr, (CX + s * 6.5, hy - 3), (CX + s * 13, hy - 5 + (lag * 0.5 if s > 0 else 0)), 2.4, D_FUR,
            D_INNER if d == DOWN else None, group=('ear', s), inner_w=0.5)


def flower_crown(fr, hx_, hy, d):
    if d == SIDE:
        xs = [hx_ - 5, hx_ - 2, hx_ + 1, hx_ + 4]
        ys = [hy - 6, hy - 7, hy - 7, hy - 6]
    else:
        xs = [21, 24, 28, 32, 35] if d == DOWN else [22, 26, 30, 34]
        ys = [hy - 5 + ((x - CX) / 6.0) ** 2 * 1.5 - 1 for x in xs]
    leaves = []
    for x, y in zip(xs, ys):
        leaves += [(int(x) + 2, int(y)), (int(x) + 2, int(y) + 1)]
    fr.put(leaves, D_LEAF[2])
    cols = [FL_PINK, FL_WHITE, FL_PINK, FL_WHITE, FL_PINK]
    for i, (x, y) in enumerate(zip(xs, ys)):
        flower(fr, x, y, cols[i % len(cols)])


D_LEAF2 = Mat('#8cc456')


def leaf_cape(fr, cx, sh, w, d):
    """葉子披肩：底下一層深綠，上面一片片尖葉（深淺交錯、彼此有描線分開），下緣是葉尖。"""
    base = ell(cx, sh + 1.5, w, 5.6) & (PY >= sh - 1.5)
    fr.fill(base, D_LEAF.dark(1), 'soft', group='cape', blur=1.3)
    n = max(2, int(round(w * 2 / 4.6)))
    order = sorted(range(n + 1), key=lambda i: -abs(i - n / 2))     # 外側先畫、中間的蓋在上面
    out = base.copy()
    for i in order:
        x = cx - w + 1.2 + i * (2 * w - 2.4) / n
        tip = (x + (x - cx) * 0.22, sh + 9.5 - abs(x - cx) * 0.22)
        lf = bez([(x - (x - cx) * 0.1, sh), (x + (x - cx) * 0.05, sh + 5), tip], 3.1, 0.5)
        mat = D_LEAF2 if i % 2 else D_LEAF
        fr.fill(lf, mat, 'soft', group=('leaf', i), blur=1.0)
        fr.paint(bezpts([(x, sh + 3), tip], 8)[:-1], mat, 1)
        fr.paint([(int(x) - 1, int(sh + 3))], mat, 4)
        out |= lf
    return out


def draw_deer(fr, r):
    b = r.bob
    hy = 35 + b
    sh = 45 + b
    hip = 58 + b
    d = r.d
    if d in (DOWN, UP):
        up = d == UP
        legs_front(fr, r, hip, 2.8, 3, D_FUR, D_HOOF, shoe_rx=2.0, shoe_ry=1.8, up=up)
        body = gown(sh, hip + 1, 11, 13)
        fr.fill(body, D_FUR, 'soft', vgrad=0.2)
        if up:
            tail_cotton(fr, CX, hip - 1, D_CREAM, 2.0)
            for p in [(24, sh + 9), (31, sh + 10), (27, sh + 12)]:
                fr.paint([p, (p[0] + 1, p[1])], D_CREAM, 3)
        arm_front(fr, r, -1, CX - 6, sh + 3, 7, D_FUR, D_HOOF, d=d, rad=1.8, hand_r=1.4)
        arm_front(fr, r, 1, CX + 6, sh + 3, 7, D_FUR, D_HOOF, d=d, rad=1.8, hand_r=1.4)
        leaf_cape(fr, CX, sh, 10.5, d)
        if not up:
            flower(fr, CX - 6, sh + 3, FL_PINK)
            flower(fr, CX + 6, sh + 4, FL_WHITE)
        deer_ears(fr, CX, hy, d, r.lag)
        antlers(fr, CX, hy, d)
        if not up:
            animal_front(fr, hy, D_FUR, rx=8.6, ry=7.6, muzzle=D_CREAM, mz=(3.4, 2.5, 4.4), eye_x=(22, 33), eye_y=0)
            fr.paint([(27, hy - 4), (28, hy - 4), (28, hy - 3)], D_CREAM, 3)
        else:
            animal_back(fr, hy, D_FUR, 8.6, 7.6)
        flower_crown(fr, CX, hy, d)
    else:
        hx_ = CX - 1
        tail = ell(hx_ + 6, hip - 2 + r.lag * 0.3, 1.8, 2.4)
        fr.fill(tail, D_CREAM, 'ball', group='tail')
        arm_side(fr, r, hx_ + 1, sh + 3, 7, D_FUR, D_HOOF, near=False, rad=1.8, hand_r=1.4)
        legs_side(fr, r, hip, hx_, D_FUR, D_HOOF, w=1.5, toe=1.0)
        body = poly([(hx_ - 4, sh + 1), (hx_ + 4, sh + 1), (hx_ + 5, hip + 1), (hx_ - 5, hip + 1)]) | ell(hx_, sh + 2.5, 4.5, 3)
        fr.fill(body, D_FUR, 'soft', vgrad=0.2)
        fr.fill(ell(hx_ - 3.5, sh + 6, 2.2, 4), D_CREAM, 'soft', group='chest', line=False)
        for p in [(hx_ + 2, sh + 9), (hx_ + 4, sh + 12)]:
            fr.paint([p], D_CREAM, 3)
        arm_side(fr, r, hx_ - 1, sh + 3, 7, D_FUR, D_HOOF, near=True, rad=1.8, hand_r=1.4)
        leaf_cape(fr, hx_ + 0.5, sh, 7.5, d)
        antlers(fr, hx_, hy, d)
        animal_side(fr, hy, hx_, D_FUR, rx=8.0, ry=7.4, snout=(4.0, 3.0), muzzle=D_CREAM, snout_dy=3.6)
        deer_ears(fr, hx_, hy, d, r.lag)
        flower_crown(fr, hx_, hy, d)


# ═══════════════ 騎掃帚的魔女（broomwitch）：一直在飄 ═══════════════
B_HAIR = Mat('#e8803c')
B_DRESS = Mat('#c0424e')
B_HAT = Mat('#3e3560')
B_BAND = Mat('#e8566a')
B_STOCK = Mat('#fbf4ea', cols=['#a8a0b0', '#d8d0d8', '#f6f0ea', '#ffffff', '#ffffff'], ln='#6a6078')
B_SHOE = Mat('#3a2a3a')
B_IRIS = Mat('#3e8a6a')
B_APRON = Mat('#f6ecd8')


def broom(fr, y, x0, x1, bristle_right=True, sway=0, d=DOWN):
    """橫放的掃帚：x0→x1 是柄，鬃毛在 bristle 那一端。"""
    hand = cap(x0, y, x1, y, 1.45)
    fr.fill(hand, WOOD, 'cyl', group='broom')
    s = 1 if bristle_right else -1
    bx = x1 if bristle_right else x0
    br = poly([(bx, y - 2.2), (bx, y + 2.2), (bx + s * 11, y + 4.2 + sway * 0.5), (bx + s * 12, y + 0.5 + sway), (bx + s * 11, y - 3.2 + sway * 0.5)])
    br |= ell(bx + s * 1.5, y, 2.0, 2.4)
    fr.fill(br, STRAW, 'soft', group='bristle', blur=1.0)
    for k in (-2, 0, 2):
        fr.paint(bezpts([(bx + s * 3, y + k * 0.5), (bx + s * 11, y + k * 1.3 + sway * 0.6)], 12), STRAW, 1)
    fr.paint(bezpts([(bx + s * 3, y - 1), (bx + s * 10, y - 2 + sway * 0.4)], 10), STRAW, 4)
    band = br & (PX * s >= (bx + s * 1.5) * s - 0.5) & (PX * s <= (bx + s * 3) * s)
    fr.fill(band, B_BAND, 'cyl', group='bband')


def draw_broomwitch(fr, r):
    hov = (0, -1, -1, 0)[r.f]
    lift = 8
    o = -lift + hov
    hy = 33 + o
    sh = 43 + o
    by_ = 57 + o          # 掃帚柄的高度
    d = r.d
    sw = (0, 1, 0, -1)[r.f]
    if d in (DOWN, UP):
        up = d == UP
        # 掃帚在身體後面一半：先畫
        broom(fr, by_, 9, 41, bristle_right=not up, sway=sw) if not up else broom(fr, by_, 15, 47, bristle_right=False, sway=sw)
        # 垂下來的腳（坐在掃帚上，腳在前面晃）
        for side in (-1, 1):
            k = sw * side * 0.6
            lx = CX + side * 2.6
            leg = cap(lx, by_ + 1, lx + side * 0.6 + k, by_ + 7, 1.5)
            fr.fill(leg, B_STOCK, 'cyl', group=('leg', side))
            fr.fill(ell(lx + side * 0.9 + k, by_ + 8, 2.3, 1.7), B_SHOE, 'ball', group=('shoe', side))
        skirt = gown(sh, by_ + 2, 12, 20)
        fr.fill(skirt, B_DRESS, 'soft', vgrad=0.3, blur=1.6)
        folds(fr, skirt, B_DRESS, [23, 33], by_ - 4, by_ + 3)
        if not up:
            apron = gown(sh + 6, by_ + 1, 8, 11)
            fr.fill(apron, B_APRON, 'soft', group='apron')
            fr.paint(edge(apron, 'b'), B_APRON, 1)
            fr.fill(sym(ell(CX - 2.5, sh + 0.8, 3.0, 1.8)), B_APRON, 'soft', group='col')
        hem_band(fr, skirt, B_DRESS, 0)
        # 雙手握著掃帚柄
        for side in (-1, 1):
            hxp = CX + side * 4.5
            m = bez([(CX + side * 6, sh + 2), (CX + side * 7.5, sh + 7), (hxp, by_ - 1)], 2.2, 1.7)
            fr.fill(m, B_DRESS, 'soft', group=('arm', side))
            fr.fill(ell(hxp, by_ - 0.2, 1.8, 1.7), SKIN, 'ball', group=('hand', side))
        if not up:
            head_front(fr, hy, SKIN, B_HAIR, B_IRIS, mouth='open', locks=2, lock_len=6)
        else:
            head_back(fr, hy, B_HAIR, lock_len=6)
        witch_hat(fr, CX, hy - 6.5, 13.5, 15, B_HAT, B_BAND, d, tip=7, star=hx('#ffe27a'), buckle=not up)
    else:
        hx_ = CX
        broom(fr, by_, 4, 33, bristle_right=True, sway=sw)
        for near in (False, True):
            k = sw * (0.8 if near else -0.8)
            lx = hx_ + (0.5 if near else 2.0)
            mat = B_STOCK if near else B_STOCK.dark(1)
            leg = bez([(lx, by_), (lx - 3.5, by_ + 1), (lx - 3 + k, by_ + 7)], 1.6, 1.4)
            fr.fill(leg, mat, 'cyl', group=('leg', near))
            fr.fill(ell(lx - 4 + k, by_ + 8, 2.6, 1.6), B_SHOE if near else B_SHOE.dark(1), 'ball', group=('shoe', near))
        skirt = poly([(hx_ - 4, sh + 1), (hx_ + 4, sh + 1), (hx_ + 6, by_ + 2), (hx_ - 7, by_ + 2)]) | ell(hx_, sh + 2.5, 4.5, 3)
        fr.fill(skirt, B_DRESS, 'soft', vgrad=0.3)
        fr.fill(poly([(hx_ - 4.5, sh + 6), (hx_ - 1, sh + 6), (hx_ - 2, by_ + 1), (hx_ - 7, by_ + 1)]), B_APRON, 'soft', group='apron')
        head_side(fr, hy, SKIN, B_HAIR, B_IRIS, hx_=hx_, lock_len=6)
        witch_hat(fr, hx_ + 1, hy - 6.5, 12.5, 15, B_HAT, B_BAND, d, tip=7, star=hx('#ffe27a'))
        m = bez([(hx_ - 1, sh + 2), (hx_ - 3, sh + 7), (hx_ - 7, by_ - 1)], 2.2, 1.7)
        fr.fill(m, B_DRESS, 'soft', group='arm')
        fr.fill(ell(hx_ - 7, by_ - 0.2, 1.8, 1.7), SKIN, 'ball', group='hand')


# ═══════════════ 妖精（fairy）：蘑菇帽＋翅膀 ═══════════════
FY_HAIR = Mat('#e0a860')
FY_CAP = Mat('#dc4440')
FY_GILL = Mat('#f6e4c8')
FY_DRESS = Mat('#6cae4c')
FY_WING = Mat('#c8eef8', cols=['#86bcd8', '#a8dcec', '#cdf0f8', '#eafaff', '#ffffff'], ln='#5a8aa8')
FY_IRIS = Mat('#3e9a6a')
FY_SHOE = Mat('#7a5a3a')


def wings(fr, cx, sh, f, d):
    flap = (0, 1, 0, 1)[f]
    out = Z.copy()
    for s in (-1, 1):
        if d == SIDE and s < 0:
            continue
        ox = cx + s * (0.5 if d != SIDE else 1.5)
        up_ = ell(ox + s * (8.5 - flap * 1.5), sh - 1 - flap, 6.0 - flap * 1.2, 4.2) | cap(ox, sh + 2, ox + s * (8 - flap), sh - 1, 1.6)
        lo = ell(ox + s * (6.0 - flap), sh + 6, 4.0 - flap * 0.6, 3.2) | cap(ox, sh + 3, ox + s * 5, sh + 6, 1.4)
        m = up_ | lo
        fr.fill(m, FY_WING if d != SIDE else FY_WING, 'soft', group=('wing', s), blur=1.4, bias=0.12)
        # 翅脈＋亮點
        fr.paint(bezpts([(ox, sh + 1), (ox + s * (11 - flap * 2), sh - 3 - flap)], 14), FY_WING, 1)
        fr.paint(bezpts([(ox, sh + 3), (ox + s * (8 - flap), sh + 7)], 10), FY_WING, 1)
        fr.paint([(int(ox + s * (7 - flap)), int(sh - 3 - flap)), (int(ox + s * (8 - flap)), int(sh - 3 - flap))], FY_WING, 4)
        out |= m
    return out


def mushroom_cap(fr, hx_, hy, d):
    dome = ell(hx_, hy - 3.6, 13.0, 8.2) & (PY < hy - 2.2)
    if d == SIDE:
        dome = ell(hx_ + 0.5, hy - 3.6, 12.0, 8.2) & (PY < hy - 2.2)
    if d != UP:
        gill = ell(hx_, hy - 2.4, 12.4, 1.8) & (PY >= hy - 2.6)
        fr.fill(gill, FY_GILL, 'soft', group='gill')
        for x in range(int(hx_ - 11), int(hx_ + 12), 2):
            fr.paint([(x, int(hy - 2))], FY_GILL, 1)
    fr.fill(dome, FY_CAP, 'ball', group='cap', c=(hx_ - 3, hy - 8), r=(15, 9))
    dots = [(-6, -6, 1.8), (0, -9, 1.6), (6, -6.5, 1.7), (-10, -4, 1.2), (10, -3.8, 1.2), (-2, -4.5, 1.1), (3, -3.8, 1.0)]
    if d == SIDE:
        dots = [(-7, -5.5, 1.6), (-1, -8.5, 1.7), (5, -6.5, 1.5), (9, -3.8, 1.2), (-3, -3.6, 1.1)]
    elif d == UP:
        dots = [(-5, -7, 1.7), (2, -9, 1.5), (7, -5.5, 1.6), (-10, -3.5, 1.2), (0, -4.5, 1.4), (10, -3.6, 1.1)]
    for dx, dy, rr in dots:
        dm = ell(hx_ + dx, hy + dy, rr, rr * 0.85) & dome
        fr.paint(dm, FL_WHITE, 2)
        fr.paint(dm & edge(dm, 'b'), FL_WHITE, 1)


def wand(fr, x, y, dx, dy, f):
    pts = bezpts([(x, y), (x + dx, y + dy)], 12)
    for p in pts:
        fr.put([p], WOOD[2])
    tx, ty = pts[-1]
    tw = f % 2
    fr.overlay([(tx, ty - 2), (tx - 1, ty - 1), (tx, ty - 1), (tx + 1, ty - 1), (tx - 2 + tw, ty - 1 + 0), (tx + 2 - tw, ty - 1)], hx('#ffe88a'))
    fr.overlay([(tx, ty - 1)], hx('#ffffff'))
    fr.overlay([(tx, ty - 3 - tw), (tx, ty)], hx('#ffd04a'))
    fr.overlay([(tx + 3, ty - 4 + tw)], hx('#fff6c0'))


def draw_fairy(fr, r):
    b = r.bob
    hy = 38 + b
    sh = 48 + b
    hem = 58 + b
    d = r.d
    if d in (DOWN, UP):
        up = d == UP
        if not up:
            wings(fr, CX, sh, r.f, d)
        legs_front(fr, r, hem - 1, 2.2, 2, SKIN, FY_SHOE, shoe_rx=2.2, shoe_ry=1.7, up=up)
        dress = gown(sh, hem, 9, 16)
        notch = Z.copy()
        for x in range(19, 38, 3):
            notch |= poly([(x + 0.2, hem + 2), (x + 1.5, hem - 0.5), (x + 2.8, hem + 2)])
        dress &= ~notch
        fr.fill(dress, FY_DRESS, 'soft', vgrad=0.25)
        folds(fr, dress, FY_DRESS, [24, 32], hem - 4, hem + 1)
        fr.paint([(28, y) for y in range(sh + 3, hem + 1)], FY_DRESS, 1)
        fr.fill(ell(CX, sh + 5, 4.6, 1.0), FY_SHOE, 'flat', group='belt', line=False)
        ex1, ey1 = arm_front(fr, r, -1, CX - 5, sh + 2, 6, SKIN, SKIN, d=d, rad=1.5, rad2=1.3, hand_r=1.5)
        ex, ey = arm_front(fr, r, 1, CX + 5, sh + 2, 6, SKIN, SKIN, d=d, rad=1.5, rad2=1.3, hand_r=1.5)
        if not up:
            wand(fr, ex, ey, 3, -8, r.f)
            head_front(fr, hy, SKIN, FY_HAIR, FY_IRIS, mouth='smile', locks=2, lock_len=8, hair_rx=10.4)
        else:
            head_back(fr, hy, FY_HAIR, lock_len=8)
            wings(fr, CX, sh, r.f, d)
            wand(fr, ex1, ey1, -3, -8, r.f)
        mushroom_cap(fr, CX, hy - 2, d)
    else:
        hx_ = CX - 1
        wings(fr, hx_, sh, r.f, d)
        arm_side(fr, r, hx_ + 1, sh + 2, 6, SKIN, SKIN, near=False, rad=1.5, rad2=1.3, hand_r=1.5)
        legs_side(fr, r, hem - 1, hx_, SKIN, FY_SHOE, w=1.2, toe=1.6, stride=3)
        dress = poly([(hx_ - 3.5, sh + 1), (hx_ + 3.5, sh + 1), (hx_ + 6, hem + 1), (hx_ - 6, hem + 1)]) | ell(hx_, sh + 2.5, 4, 2.6)
        notch = Z.copy()
        for x in range(int(hx_ - 7), int(hx_ + 7), 3):
            notch |= poly([(x + 0.2, hem + 2), (x + 1.5, hem - 0.5), (x + 2.8, hem + 2)])
        fr.fill(dress & ~notch, FY_DRESS, 'soft', vgrad=0.25)
        head_side(fr, hy, SKIN, FY_HAIR, FY_IRIS, hx_=hx_, lock_len=8)
        mushroom_cap(fr, hx_ + 1, hy - 2, d)
        ex, ey = arm_side(fr, r, hx_ - 0.5, sh + 2, 6, SKIN, SKIN, near=True, rad=1.5, rad2=1.3, hand_r=1.5, fixed=(-3, 5))
        wand(fr, ex, ey, -4, -8, r.f)


# ═══════════════ 旅人（traveler）：眼鏡＋大背包＋提燈 ═══════════════
T_HAIR = Mat('#6e4a32')
T_ROBE = Mat('#946446')
T_PACK = Mat('#7c8a4e')
T_ROLL = Mat('#c85a4a')
T_BOOT = Mat('#4e3428')
T_BELT = Mat('#5a3a2a')
T_IRIS = Mat('#4a6a8e')
T_PANT = Mat('#5e5a6e')
T_GLASS = hx('#4a2e22')
METAL = Mat('#5c5868')
LAMP = Mat('#ffd860', cols=['#e89a30', '#f8c040', '#ffe070', '#fff4b0', '#ffffff'], ln='#a86020')


def lantern(fr, x, y, f):
    """手提燈：x,y ＝手。"""
    x, y = int(x), int(y)
    fr.put([(x, y + 1)], METAL[1])
    body = rect(x - 2, y + 3, x + 2, y + 7)
    fr.fill(body, LAMP, 'ball', group='lamp')
    fr.fill(rect(x - 2, y + 2, x + 2, y + 2) | rect(x - 1, y + 1, x + 1, y + 1), METAL, 'flat', group='lampm')
    fr.fill(rect(x - 2, y + 8, x + 2, y + 8), METAL, 'flat', group='lampb')
    fr.paint([(x, yy) for yy in range(y + 3, y + 8)], METAL, 1)
    fr.paint([(x - 1, y + 4)], LAMP, 4)
    # 光暈（不描邊、半透明）
    g = (f % 2)
    ring = ell(x + 0.5, y + 5.5, 5.0 + g * 0.5, 5.0 + g * 0.5) & ~ell(x + 0.5, y + 5.5, 3.6, 3.6)
    ys, xs = np.nonzero(ring)
    fr.overlay(list(zip(xs, ys)), hx('#ffe88a'), 70)


def glasses(fr, ey, xs=(24, 31)):
    """圓眼鏡：框在眼睛外圍一圈。"""
    for cx in xs:
        ring = ell(cx + 0.5, ey + 2.0, 3.2, 2.9) & ~ell(cx + 0.5, ey + 2.0, 2.2, 1.9)
        ys, xs_ = np.nonzero(ring)
        fr.put(list(zip(xs_, ys)), T_GLASS)
        fr.put([(cx - 1, ey + 1)], hx('#e8f4ff'))
    fr.put([(27, ey + 1), (28, ey + 1)], T_GLASS)


def backpack_back(fr, hy, sh, hem):
    pack = rect(19, sh - 1, 36, sh + 13) | ell(CX, sh + 13, 9, 2)
    fr.fill(pack, T_PACK, 'soft', group='pack', blur=1.5)
    flap = rect(20, sh - 1, 35, sh + 4) | ell(CX, sh + 4, 8, 1.6)
    fr.fill(flap, T_PACK, 'soft', group='flap', bias=0.08)
    for x in (23, 32):
        fr.fill(rect(x, sh + 3, x + 1, sh + 7), T_BELT, 'flat', group=('buckle', x))
        fr.put([(x, sh + 6)], GOLD[3])
    pocket = rect(23, sh + 8, 32, sh + 12)
    fr.fill(pocket, T_PACK, 'soft', group='pocket', bias=-0.05)
    fr.paint(edge(pocket, 't'), T_PACK, 0)
    roll = cap(17.5, sh - 3, 38.5, sh - 3, 2.6)
    fr.fill(roll, T_ROLL, 'cyl', group='roll')
    for x in (21, 34):
        fr.paint([(x, y) for y in range(sh - 6, sh)], T_BELT, 1)
    fr.paint([(x, sh - 4) for x in range(18, 38) if x % 4 == 0], T_ROLL, 4)


def draw_traveler(fr, r):
    b = r.bob
    hy = 31 + b
    sh = 41 + b
    hem = 60 + b
    d = r.d
    if d == DOWN:
        # 背包從肩後露出來（上方的捲毯、兩側）
        fr.fill(cap(16.5, sh - 2, 39.5, sh - 2, 2.6), T_ROLL, 'cyl', group='roll')
        fr.paint([(x, sh - 3) for x in range(17, 39) if x % 4 == 0], T_ROLL, 4)
        fr.fill(rect(17, sh, 38, sh + 10), T_PACK, 'soft', group='pack')
        legs_front(fr, r, hem - 2, 2.8, 3, T_PANT, T_BOOT, shoe_rx=2.8)
        robe = gown(sh, hem, 15, 21)
        fr.fill(robe, T_ROBE, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, robe, T_ROBE, [23, 33], hem - 7, hem + 1)
        fr.paint([(28, y) for y in range(sh + 9, hem + 2)], T_ROBE, 0)
        fr.paint([(27, y) for y in range(sh + 9, hem + 2)], T_ROBE, 3)
        hem_band(fr, robe, T_ROBE, 0)
        belt = robe & (YY >= sh + 8) & (YY <= sh + 9)
        fr.fill(belt, T_BELT, 'flat', group='belt')
        fr.put([(27, sh + 8), (28, sh + 8), (27, sh + 9), (28, sh + 9)], GOLD[3])
        fr.fill(rect(31, sh + 10, 34, sh + 13), T_BELT, 'soft', group='pouch')
        # 背包肩帶
        for s in (-1, 1):
            fr.fill(cap(CX + s * 5, sh, CX + s * 5.5, sh + 7, 0.9), T_BELT, 'flat', group=('strap', s))
        # 兜帽（放下來、堆在脖子後）
        fr.fill(ell(CX, sh + 0.5, 8, 2.2), T_ROBE, 'soft', group='hood', bias=0.06)
        fr.paint([(x, int(sh + 1)) for x in range(23, 33)], T_ROBE, 0)
        arm_front(fr, r, -1, CX - 7.5, sh + 2, 10, T_ROBE, SKIN, d=d, rad=2.3, rad2=2.0)
        ex, ey = arm_front(fr, r, 1, CX + 7.5, sh + 2, 10, T_ROBE, SKIN, d=d, rad=2.3, rad2=2.0)
        lantern(fr, ex, ey, r.f)
        fr.fill(ell(ex, ey + 0.6, 1.75, 1.75), SKIN, 'ball', group='hand2')
        head_front(fr, hy, SKIN, T_HAIR, T_IRIS, locks=1, lock_len=3, bang_tips=(21.5, 25, 28.5, 32, 35),
                   bang_drop=[-0.5, -1.5, -0.6, -1.8, -0.4], blush_on=True, hair_rx=10.2, hair_ry=8.8)
        glasses(fr, int(hy + 1))
    elif d == SIDE:
        hx_ = CX - 3
        arm_side(fr, r, hx_ + 2, sh + 2, 10, T_ROBE, SKIN, near=False, rad=2.3, rad2=2.0)
        legs_side(fr, r, hem - 2, hx_, T_PANT, T_BOOT, w=1.8, toe=2.6)
        robe = poly([(hx_ - 5, sh + 1), (hx_ + 5, sh + 1), (hx_ + 8, hem + 1), (hx_ - 7, hem + 1)]) | ell(hx_, sh + 2.5, 5.5, 3) | ell(hx_ + 0.5, hem + 0.2, 7.5, 1.6)
        fr.fill(robe, T_ROBE, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, robe, T_ROBE, [hx_ - 3, hx_ + 3], hem - 7, hem + 1)
        hem_band(fr, robe, T_ROBE, 0)
        fr.fill(robe & (YY >= sh + 8) & (YY <= sh + 9), T_BELT, 'flat', group='belt')
        # 側面的大背包
        pack = rect(int(hx_ + 4), sh - 1, int(hx_ + 11), sh + 13) | ell(hx_ + 7.5, sh + 13, 3.8, 1.6)
        fr.fill(pack, T_PACK, 'soft', group='pack', blur=1.4)
        fr.fill(rect(int(hx_ + 9), sh + 6, int(hx_ + 12), sh + 11), T_PACK, 'soft', group='pocket', bias=-0.05)
        fr.fill(ell(hx_ + 7.5, sh - 3, 4.2, 3.0), T_ROLL, 'ball', group='roll')
        fr.paint([(int(hx_ + 7), y) for y in range(sh - 5, sh - 1)], T_ROLL, 1)
        fr.fill(cap(hx_ + 3.5, sh, hx_ + 3.5, sh + 8, 0.9), T_BELT, 'flat', group='strap')
        fr.fill(ell(hx_ + 3, sh + 0.5, 3.5, 2.4), T_ROBE, 'soft', group='hood')
        head_side(fr, hy, SKIN, T_HAIR, T_IRIS, hx_=hx_, lock_len=3, hair_rx=10.0, hair_ry=8.8, bang_y=0.0)
        ey = int(hy + 1)
        ring = ell(hx_ - 6.5, ey + 2.0, 2.6, 2.7) & ~ell(hx_ - 6.5, ey + 2.0, 1.6, 1.7)
        ys, xs = np.nonzero(ring)
        fr.put(list(zip(xs, ys)), T_GLASS)
        fr.put([(int(hx_ - 4), ey + 1), (int(hx_ - 3), ey + 1), (int(hx_ - 2), ey + 1)], T_GLASS)
        ex, ey2 = arm_side(fr, r, hx_ - 0.5, sh + 2, 10, T_ROBE, SKIN, near=True, rad=2.3, rad2=2.0, fixed=(-4, 8))
        lantern(fr, ex, ey2, r.f)
        fr.fill(ell(ex, ey2 + 0.6, 1.75, 1.75), SKIN, 'ball', group='hand2')
    else:
        legs_front(fr, r, hem - 2, 2.8, 3, T_PANT, T_BOOT, shoe_rx=2.8, up=True)
        robe = gown(sh, hem, 15, 21)
        fr.fill(robe, T_ROBE, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, robe, T_ROBE, [23, 28, 33], hem - 6, hem + 1)
        hem_band(fr, robe, T_ROBE, 0)
        ex, ey = arm_front(fr, r, -1, CX - 7.5, sh + 2, 10, T_ROBE, SKIN, d=d, rad=2.3, rad2=2.0)
        lantern(fr, ex, ey, r.f)
        fr.fill(ell(ex, ey + 0.6, 1.75, 1.75), SKIN, 'ball', group='hand2')
        arm_front(fr, r, 1, CX + 7.5, sh + 2, 10, T_ROBE, SKIN, d=d, rad=2.3, rad2=2.0)
        head_back(fr, hy, T_HAIR, lock_len=3, hair_rx=10.2, hair_ry=8.8)
        backpack_back(fr, hy, sh + 1, hem)


# ═══════════════ 法師（mage）：藍色星星兜帽＋法杖 ═══════════════
M_HOOD = Mat('#3554a6')
M_ROBE = Mat('#2c4290')
M_HAIR = Mat('#f2cc6a')
M_IRIS = Mat('#3a7ad8')
M_ORB = Mat('#9ae8ff', cols=['#3a8ad0', '#5ab8f0', '#9ae8ff', '#d4f8ff', '#ffffff'], ln='#20508a')
M_SHOE = Mat('#3a2e4a')


def staff(fr, x, y_hand, top, f, lean=0):
    x = int(x)
    for yy in range(top + 6, min(FB + 1, y_hand + 12)):
        xx = x + int(round(lean * (yy - y_hand) / 30))
        fr.put([(xx, yy)], WOOD[2] if yy % 6 else WOOD[3])
        fr.put([(xx + 1, yy)], WOOD[1])
    tx = x + int(round(lean * (top - y_hand) / 30))
    # 月牙＋寶珠
    moon = (ell(tx + 0.5, top + 3.5, 3.6, 3.6) & ~ell(tx + 2.0, top + 2.6, 3.0, 3.0))
    fr.fill(moon, GOLD, 'soft', group='moon')
    orb = ell(tx + 1.5, top + 4.0, 1.9, 1.9)
    fr.fill(orb, M_ORB, 'ball', group='orb')
    tw = f % 2
    fr.overlay([(tx + 4, top - 1 + tw), (tx + 4, top + 1 + tw), (tx + 3, top + tw), (tx + 5, top + tw)], hx('#d4f8ff'))
    fr.overlay([(tx + 4, top + tw)], hx('#ffffff'))
    fr.overlay([(tx - 3, top + 7 - tw)], hx('#9ae8ff'))


def mage_hood(fr, hx_, hy, d, part='back', sway=0):
    """兜帽：尖端往後垂。part='back' 畫整顆（臉之前），'rim' 只畫臉框（臉之後）。"""
    if d == SIDE:
        hood = ell(hx_ + 1.5, hy - 0.5, 11.2, 10.6) | bez([(hx_ + 4, hy - 8), (hx_ + 10, hy - 10), (hx_ + 14 + sway * 0.5, hy - 5)], 3.4, 1.2)
        win = ell(hx_ - 2.6, hy + 2.2, 7.6, 8.2)
    else:
        hood = ell(CX, hy - 0.5, 11.8, 10.6) | bez([(CX + 2, hy - 9), (CX + 7, hy - 12), (CX + 11 + sway * 0.5, hy - 9)], 3.4, 1.2)
        win = ell(CX, hy + 2.6, 8.2, 8.0)
    hood |= ell(hx_ if d == SIDE else CX, hy + 8, 9.5, 3.5)
    if part == 'back':
        fr.fill(hood, M_HOOD, 'soft', group='hood', blur=1.6)
        return hood
    rim = hood & ~win if d != UP else hood
    fr.fill(rim, M_HOOD, 'soft', group='hoodr', blur=1.4, bias=0.03)
    trim = rim & dil(win) & ~win if d != UP else Z
    fr.paint(trim, GOLD, 2)
    star_dots(fr, rim & ~trim, [(int(hx_ - 6), int(hy - 5), True), (int(hx_ + 5), int(hy - 7), False), (int(hx_ + 7), int(hy + 4), True), (int(hx_ - 2), int(hy - 9), False)])
    return rim


def draw_mage(fr, r):
    b = r.bob
    hy = 31 + b
    sh = 42 + b
    hem = 62 + b
    d = r.d
    if d in (DOWN, UP):
        up = d == UP
        legs_front(fr, r, hem - 2, 2.6, 3, M_SHOE, M_SHOE, up=up)
        robe = gown(sh, hem, 15, 23)
        fr.fill(robe, M_ROBE, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, robe, M_ROBE, [22, 34] if not up else [22, 28, 34], hem - 9, hem + 1)
        hem_band(fr, robe, GOLD, 2)
        fr.paint(edge(robe, 'b'), GOLD, 1)
        if not up:
            fr.paint([(27, y) for y in range(sh + 3, hem + 2)], GOLD, 2)
            fr.paint([(28, y) for y in range(sh + 3, hem + 2)], GOLD, 1)
        star_dots(fr, robe, [(22, hem - 4, True), (33, sh + 9, True), (24, sh + 6, False), (31, hem - 3, False), (36, hem - 7, False), (20, hem - 10, False)])
        sash = robe & (YY >= sh + 7) & (YY <= sh + 8)
        fr.fill(sash, Mat('#c8506a'), 'flat', group='sash')
        side_staff = -1 if not up else 1
        ex, ey = arm_front(fr, r, side_staff, CX + side_staff * 7.5, sh + 2, 9, M_ROBE, SKIN, d=d, rad=2.4, rad2=2.1)
        staff(fr, ex - 0.5, int(ey), 9 + b, r.f)
        fr.fill(ell(ex, ey + 0.6, 1.75, 1.75), SKIN, 'ball', group='hand2')
        arm_front(fr, r, -side_staff, CX - side_staff * 7.5, sh + 2, 9, M_ROBE, SKIN, d=d, rad=2.4, rad2=2.1)
        mage_hood(fr, CX, hy, d, 'back', r.sway)
        if not up:
            head_front(fr, hy + 0.5, SKIN, M_HAIR, M_IRIS, locks=2, lock_len=9, bang_tips=(22, 25.5, 29, 32.5))
        mage_hood(fr, CX, hy, d, 'rim', r.sway)
        if not up:
            fr.fill(ell(CX, sh + 1, 2.0, 1.6), GOLD, 'ball', group='clasp')
    else:
        hx_ = CX - 1
        arm_side(fr, r, hx_ + 2, sh + 2, 9, M_ROBE, SKIN, near=False, rad=2.4, rad2=2.1)
        legs_side(fr, r, hem - 2, hx_, M_SHOE, M_SHOE, toe=2.4)
        robe = poly([(hx_ - 5, sh + 1), (hx_ + 5, sh + 1), (hx_ + 9, hem + 1), (hx_ - 8, hem + 1)]) | ell(hx_, sh + 2.5, 5.5, 3) | ell(hx_ + 0.5, hem + 0.2, 8.5, 1.6)
        fr.fill(robe, M_ROBE, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, robe, M_ROBE, [hx_ - 3, hx_ + 4], hem - 8, hem + 1)
        hem_band(fr, robe, GOLD, 2)
        star_dots(fr, robe, [(hx_ + 4, hem - 4, True), (hx_ - 4, sh + 8, True), (hx_ + 2, sh + 5, False), (hx_ - 5, hem - 3, False)])
        fr.fill(robe & (YY >= sh + 7) & (YY <= sh + 8), Mat('#c8506a'), 'flat', group='sash')
        mage_hood(fr, hx_, hy, d, 'back', r.sway)
        head_side(fr, hy + 0.5, SKIN, M_HAIR, M_IRIS, hx_=hx_, lock_len=9)
        mage_hood(fr, hx_, hy, d, 'rim', r.sway)
        ex, ey = arm_side(fr, r, hx_ - 0.5, sh + 2, 9, M_ROBE, SKIN, near=True, rad=2.4, rad2=2.1, fixed=(-9, 5))
        staff(fr, ex - 0.5, int(ey), 9 + b, r.f, lean=-1)
        fr.fill(ell(ex, ey + 0.6, 1.75, 1.75), SKIN, 'ball', group='hand2')


# ═══════════════ 兔子魔女（rabbitwitch）：紫帽（耳朵穿出來）＋魔法書 ═══════════════
RW_FUR = Mat('#fbf6f0', cols=['#b8aab8', '#ddd2d8', '#f8f2ec', '#fffcf8', '#ffffff'], ln='#857088')
RW_HAT = Mat('#6a4aa6')
RW_ROBE = Mat('#a48ade')
RW_BOOK = Mat('#c4404e')
RW_COLLAR = Mat('#fffaf2', cols=['#c0b8c8', '#e4dee6', '#fffaf2', '#ffffff', '#ffffff'], ln='#8a7a98')


def book(fr, x, y, open_=False):
    x, y = int(x), int(y)
    m = rect(x - 3, y, x + 3, y + 5)
    fr.fill(m, RW_BOOK, 'soft', group='book')
    fr.paint([(x - 3, yy) for yy in range(y, y + 6)], RW_BOOK, 0)
    fr.fill(rect(x + 3, y + 1, x + 3, y + 5), RW_COLLAR, 'flat', group='pages', line=False)
    fr.put([(x, y + 2), (x - 1, y + 3), (x, y + 3), (x + 1, y + 3), (x, y + 4)], GOLD[3])


def draw_rabbitwitch(fr, r):
    b = r.bob
    hy = 39 + b
    sh = 48 + b
    hem = 62 + b
    d = r.d
    if d in (DOWN, UP):
        up = d == UP
        legs_front(fr, r, hem - 2, 2.8, 3, RW_FUR, RW_FUR, shoe_rx=2.9, up=up)
        robe = gown(sh, hem, 13, 21)
        fr.fill(robe, RW_ROBE, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, robe, RW_ROBE, [23, 33] if not up else [23, 28, 33], hem - 6, hem + 1)
        hem_band(fr, robe, RW_HAT, 2, rows=2)
        star_dots(fr, robe & (YY >= hem - 1), [(21, hem, False), (26, hem, False), (31, hem, False), (35, hem, False)])
        if up:
            tail_cotton(fr, CX, hem - 3, RW_FUR, 2.4)
        else:
            fr.fill(sym(ell(CX - 2.6, sh + 0.8, 3.4, 2.0)), RW_COLLAR, 'soft', group='col')
            fr.put([(27, sh + 2), (28, sh + 2)], GOLD[3])
        if not up:
            # 雙手捧書
            for s in (-1, 1):
                m = bez([(CX + s * 6, sh + 2), (CX + s * 7, sh + 6), (CX + s * 4.2, sh + 8 + (r.step * s * 0.0))], 2.2, 1.8)
                fr.fill(m, RW_ROBE, 'soft', group=('arm', s))
            book(fr, CX - 0.5, sh + 5 + (1 if r.step else 0))
            for s in (-1, 1):
                fr.fill(ell(CX + s * 3.8, sh + 8.4, 1.7, 1.6), RW_FUR, 'ball', group=('hand', s))
        else:
            arm_front(fr, r, -1, CX - 6.5, sh + 2, 7, RW_ROBE, RW_FUR, d=d)
            arm_front(fr, r, 1, CX + 6.5, sh + 2, 7, RW_ROBE, RW_FUR, d=d)
        if not up:
            animal_front(fr, hy, RW_FUR, rx=9.4, ry=7.8, muzzle=RW_COLLAR, mz=(3.6, 2.4, 3.6), nose=PINK[1])
        else:
            animal_back(fr, hy, RW_FUR, 9.4, 7.8)
        witch_hat(fr, CX, hy - 6.0, 12.0, 12, RW_HAT, GOLD, d, tip=-5 if not up else 5, droop=4.5, buckle=False, star=hx('#ffe27a'), base_r=5.6)
        # 耳朵從帽子穿出來
        for side in (-1, 1):
            tip = (CX + side * 7.0 + (r.lag * 0.6 if side > 0 else 0), hy - 22 + (abs(r.lag) * 0.6 if side < 0 else 0))
            ear(fr, (CX + side * 4.2, hy - 7), tip, 2.7, RW_FUR, PINK if not up else None, group=('ear', side), inner_w=0.5)
    else:
        hx_ = CX - 1
        arm_side(fr, r, hx_ + 2, sh + 2, 7, RW_ROBE, RW_FUR, near=False)
        legs_side(fr, r, hem - 2, hx_, RW_FUR, RW_FUR, w=1.8, toe=2.8)
        tail_cotton(fr, hx_ + 7.5, hem - 3, RW_FUR, 2.4)
        robe = poly([(hx_ - 4.5, sh + 1), (hx_ + 4.5, sh + 1), (hx_ + 8, hem + 1), (hx_ - 7, hem + 1)]) | ell(hx_, sh + 2.5, 5, 3) | ell(hx_ + 0.5, hem + 0.2, 7.5, 1.6)
        fr.fill(robe, RW_ROBE, 'soft', vgrad=0.3, blur=1.8)
        folds(fr, robe, RW_ROBE, [hx_ - 3, hx_ + 3], hem - 6, hem + 1)
        hem_band(fr, robe, RW_HAT, 2, rows=2)
        fr.fill(ell(hx_ - 2, sh + 1, 3.2, 1.8), RW_COLLAR, 'soft', group='col')
        animal_side(fr, hy, hx_, RW_FUR, rx=8.8, ry=7.6, snout=(3.4, 2.6), muzzle=RW_COLLAR, snout_dy=3.4, nose=PINK[1])
        ear(fr, (hx_ + 3.5, hy - 7), (hx_ + 10 + r.lag * 0.5, hy - 19), 2.5, RW_FUR.dark(1), None, group='earb')
        witch_hat(fr, hx_ + 1, hy - 6.0, 11.0, 12, RW_HAT, GOLD, d, tip=-9, droop=4.5, buckle=False, star=hx('#ffe27a'), base_r=5.6)
        ear(fr, (hx_ + 1.5, hy - 7), (hx_ + 6 + r.lag * 0.5, hy - 21), 2.8, RW_FUR, PINK, group='earf', inner_w=0.5)
        ex, ey = arm_side(fr, r, hx_ - 0.5, sh + 2, 7, RW_ROBE, RW_FUR, near=True, fixed=(-4, 5))
        book(fr, ex - 1, ey - 2)
        fr.fill(ell(ex, ey + 0.6, 1.75, 1.75), RW_FUR, 'ball', group='hand2')


CHARS = ['frog', 'fox', 'rabbit', 'hedgehog', 'witch', 'deer', 'broomwitch', 'fairy', 'traveler', 'mage', 'rabbitwitch']
DRAW = {n: globals()['draw_' + n] for n in CHARS}


# ═══════════════════════════════ 輸出 ═══════════════════════════════

COLS, ROWS = 4, 3


def render(name):
    """一位角色的走路表（原生 1px，W*4 × H*3）＋每格的圖。"""
    sheet = Image.new('RGBA', (W * COLS, H * ROWS), (0, 0, 0, 0))
    cells = {}
    for d in (DOWN, SIDE, UP):
        for f in range(COLS):
            fr = Fr()
            DRAW[name](fr, Rig(d, f))
            im = fr.render()
            check_cell(name, d, f, im)
            cells[(d, f)] = im
            sheet.alpha_composite(im, (f * W, d * H))
    colors = {p[:3] for p in sheet.getdata() if p[3]}
    return sheet, cells, len(colors)


def check_cell(name, d, f, im):
    """四周至少留 1px 透明；最底下 FOOT_PAD 列一定是空的；站在地上的角色鞋底外輪廓剛好在第 FB+1 列。"""
    a = np.asarray(im)[..., 3]
    ys, xs = np.nonzero(a)
    assert xs.min() >= 1 and xs.max() <= W - 2 and ys.min() >= 1, f'{name}[{d},{f}] 超出格子 {xs.min()},{xs.max()},{ys.min()}'
    assert ys.max() <= FB + 1, f'{name}[{d},{f}] 腳底超過基準線（{ys.max()}）'
    if name not in HOVER:
        assert ys.max() == FB + 1, f'{name}[{d},{f}] 腳底沒踩在基準線上（{ys.max()}）'


HOVER = {'broomwitch'}


def render_all():
    out = []
    errs = []
    for name in CHARS:
        try:
            sheet, cells, nc = render(name)
        except AssertionError as e:
            errs.append(str(e))
            continue
        out.append((name, sheet, cells, nc))
    if errs:
        sys.exit('\n'.join(errs))
    return out


def md5(p):
    with open(p, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


# ─────────── 預覽 ───────────

GRASS = (112, 158, 82)
DARKBG = (38, 30, 44)
GAME_SCALE = 1.6     # ＝ GameArt.WitchScale（村民與女巫同一個倍數，像素一樣大）


def up(im, k):
    """照遊戲內的 Point 取樣放大（非整數倍時像素一格寬一格窄，跟 Unity 一樣）。"""
    return im.resize((round(im.width * k), round(im.height * k)), Image.NEAREST)


def witch_cell(row=0, col=0):
    w = Image.open(os.path.join(RES, 'witch8', 'base.png')).convert('RGBA')
    cw, chh = w.width // 8, w.height // 25
    return w.crop((col * cw, row * chh, (col + 1) * cw, (row + 1) * chh))


def preview(arts, outdir):
    os.makedirs(outdir, exist_ok=True)
    files = []
    try:
        from gen_item_art import find_font
        font = find_font(14)
    except Exception:
        font = None

    # (a) 11 位朝下站姿 ＋ 女巫，遊戲倍數 ×1.6；1:1 與再 ×3
    wi = up(witch_cell(), GAME_SCALE)
    cells = [up(a[2][(DOWN, 0)], GAME_SCALE) for a in arts]
    gap = 4
    lw = wi.width + sum(c.width for c in cells) + gap * (len(cells) + 2)
    lh = max(c.height for c in cells) + 8
    line = Image.new('RGBA', (lw, lh), GRASS + (255,))
    x = gap
    line.alpha_composite(wi, (x, lh - 4 - wi.height))
    x += wi.width + gap
    for c in cells:
        line.alpha_composite(c, (x, lh - 4 - c.height))
        x += c.width + gap
    # 腳底基準線（女巫的鞋底＝格子底往上 3px×1.6）
    p = os.path.join(outdir, 'lineup_1x.png')
    line.save(p)
    files.append(p)
    p = os.path.join(outdir, 'lineup_3x.png')
    line.resize((lw * 3, lh * 3), Image.NEAREST).save(p)
    files.append(p)

    # (b) 每張走路表放大 ×4，草地底；另一張全部 ×2 總覽
    for name, sheet, cl, nc in arts:
        bg = Image.new('RGBA', (sheet.width * 4, sheet.height * 4), GRASS + (255,))
        bg.alpha_composite(sheet.resize((sheet.width * 4, sheet.height * 4), Image.NEAREST))
        p = os.path.join(outdir, f'sheet_{name}.png')
        bg.save(p)
        files.append(p)
    per = 4
    sw, sh = W * COLS * 2, H * ROWS * 2
    rows = (len(arts) + per - 1) // per
    big = Image.new('RGBA', (per * (sw + 12) + 12, rows * (sh + 24) + 8), GRASS + (255,))
    dr = ImageDraw.Draw(big)
    for i, (name, sheet, cl, nc) in enumerate(arts):
        x0, y0 = 12 + (i % per) * (sw + 12), 8 + (i // per) * (sh + 24)
        big.alpha_composite(sheet.resize((sw, sh), Image.NEAREST), (x0, y0))
        dr.text((x0, y0 + sh + 3), f'{name}  {nc} colours', fill=(20, 30, 20), font=font)
    p = os.path.join(outdir, 'sheets_grass.png')
    big.save(p)
    files.append(p)

    # (c) 走路 GIF（×4）：每位、每個方向；全部人朝下走一張
    gz = 4
    for name, sheet, cl, nc in arts:
        for di, dn in ((DOWN, 'down'), (SIDE, 'side'), (UP, 'up')):
            frames = []
            for f in range(COLS):
                fr = Image.new('RGBA', (W * gz, H * gz), GRASS + (255,))
                fr.alpha_composite(cl[(di, f)].resize((W * gz, H * gz), Image.NEAREST))
                frames.append(fr.convert('RGB'))
            p = os.path.join(outdir, f'gif_{name}_{dn}.gif')
            frames[0].save(p, save_all=True, append_images=frames[1:], duration=125, loop=0)
            files.append(p)
    gz = 3
    frames = []
    for f in range(COLS):
        fr = Image.new('RGBA', (len(arts) * W * gz, H * gz), GRASS + (255,))
        for i, (name, sheet, cl, nc) in enumerate(arts):
            fr.alpha_composite(cl[(DOWN, f)].resize((W * gz, H * gz), Image.NEAREST), (i * W * gz, 0))
        frames.append(fr.convert('RGB'))
    p = os.path.join(outdir, 'all_down.gif')
    frames[0].save(p, save_all=True, append_images=frames[1:], duration=125, loop=0)
    files.append(p)
    strip = Image.new('RGB', (frames[0].width, frames[0].height * COLS), GRASS)
    for f, fr in enumerate(frames):
        strip.paste(fr, (0, f * frames[0].height))
    p = os.path.join(outdir, 'all_down_frames.png')
    strip.save(p)
    files.append(p)
    # 側面走路的 4 幀並排（看腿有沒有擺、有沒有殘影）
    strip = Image.new('RGBA', (COLS * W * gz, len(arts) * H * gz), GRASS + (255,))
    for i, (name, sheet, cl, nc) in enumerate(arts):
        for f in range(COLS):
            strip.alpha_composite(cl[(SIDE, f)].resize((W * gz, H * gz), Image.NEAREST), (f * W * gz, i * H * gz))
    p = os.path.join(outdir, 'all_side_frames.png')
    strip.save(p)
    files.append(p)

    files += scene_preview(arts, outdir)
    return files


def scene_preview(arts, outdir):
    """實景合成：村民與女巫都 ×1.6（遊戲內倍數），站在城鎮地面與後花園；另存 ×2 放大版。"""
    files = []
    lookup = {a[0]: a for a in arts}

    def cell(name, d=DOWN, f=0):
        return up(lookup[name][2][(d, f)], GAME_SCALE)

    def place(bg, im, fx, fy, flip=False):
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        bg.alpha_composite(im, (int(fx - im.width / 2), int(fy - im.height)))

    def shadow(bg, fx, fy, w):
        sh = Image.new('RGBA', bg.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((fx - w * 0.5, fy - w * 0.14, fx + w * 0.5, fy + w * 0.14), fill=(20, 30, 20, 70))
        bg.alpha_composite(sh)

    wi = up(witch_cell(), GAME_SCALE)
    pad = 3 * GAME_SCALE
    layouts = {
        'town': (os.path.join(RES, 'art', 'town-ground.png'), (1250, 820, 2010, 1300)),
        'garden': (os.path.join(RES, 'rooms', 'garden8.png'), (520, 420, 1280, 900)),
    }
    spots = [('witch8', DOWN, 0, 90, 230, False), ('frog', DOWN, 0, 170, 235, False), ('fox', SIDE, 1, 270, 225, False),
             ('rabbit', DOWN, 2, 360, 238, False), ('hedgehog', SIDE, 3, 450, 230, True), ('witch', DOWN, 1, 540, 236, False),
             ('deer', UP, 1, 630, 230, False), ('broomwitch', SIDE, 0, 120, 400, True), ('fairy', DOWN, 0, 230, 405, False),
             ('traveler', SIDE, 1, 340, 400, False), ('mage', DOWN, 0, 450, 410, False), ('rabbitwitch', UP, 0, 560, 400, False)]
    for tag, (path, box) in layouts.items():
        if not os.path.exists(path):
            continue
        bg = Image.open(path).convert('RGBA').crop(box)
        for name, d, f, x, y, flip in sorted(spots, key=lambda s: s[4]):
            if name == 'witch8':
                shadow(bg, x, y - pad, W * GAME_SCALE * 0.875 * 0.55)
                place(bg, wi, x, y)
            else:
                shadow(bg, x, y - pad, W * GAME_SCALE * SHADOW_RATIO * 0.55)
                place(bg, cell(name, d, f), x, y, flip)
        p = os.path.join(outdir, f'scene_{tag}.png')
        bg.save(p)
        files.append(p)
        p = os.path.join(outdir, f'scene_{tag}_2x.png')
        bg.resize((bg.width * 2, bg.height * 2), Image.NEAREST).save(p)
        files.append(p)
    return files


SHADOW_RATIO = 0.85    # ＝ GameArt.VillagerShadowRatio（新圖）


def main():
    args = sys.argv[1:]
    if '--restore' in args:
        if os.path.isdir(OUT_DIR):
            shutil.rmtree(OUT_DIR)
        meta = OUT_DIR + '.meta'
        if os.path.exists(meta):
            os.remove(meta)
        print(f'已刪除 {OUT_DIR}（GameArt 找不到 villagers8 的圖時會自動退回舊圖；要完全關掉請把 GameArt.UsePixelVillagers 設 false）')
        return
    out_dir = args[args.index('--out') + 1] if '--out' in args else OUT_DIR
    preview_dir = args[args.index('--preview') + 1] if '--preview' in args else None
    arts = render_all()
    os.makedirs(out_dir, exist_ok=True)
    for name, sheet, cells, nc in arts:
        p = os.path.join(out_dir, name + '.png')
        sheet.save(p, optimize=False)
        print(f'{name:<12} → {name}.png  {sheet.width}×{sheet.height}  {nc} 色  {md5(p)[:8]}')
    print(f'共 {len(arts)} 張')
    if preview_dir:
        for f in preview(arts, preview_dir):
            print('預覽', f)


if __name__ == '__main__':
    main()
