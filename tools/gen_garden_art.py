# -*- coding: utf-8 -*-
"""
後花園的 8-bit 重畫 —— 程式畫、固定結果、可重跑。
同時產生後花園的幾何資料 Assets/Scripts/Data/GardenRoomData.cs（C# 不自己寫常數）。

    python tools/gen_garden_art.py                  # 畫圖 → Assets/Resources/rooms/garden8*.png，寫 Data/GardenRoomData.cs
    python tools/gen_garden_art.py --preview DIR    # 另外輸出：整張合成（花圃、花、女巫、路人）、路人路網除錯圖、
                                                    #   鏡頭實際看到的 1:1 畫面、各處 2 倍放大
    python tools/gen_garden_art.py --out DIR        # 全部輸出寫到 DIR（不碰專案；調圖時用）

舊圖 rooms/garden.png 不動（GardenRoom.UsePixelGarden=false 時還在用）。
離線檢查：python tools/check_garden_walk.py（讀這支寫出來的 GardenRoomData.cs）。

── 版本 ───────────────────────────────────────────────────────
  第一版：64×32 格、×3 粗像素、暗色樹林。
  第二版：88×44 格（舊花圃畫面上約 84×55）、×2 像素、照城鎮 cottage-home 的木板＋茅草小屋。
  第三版（這一版）：使用者「要可愛一點」「路人要在外面隨機走」「花園再大一點」——
    · 16×12 格（草地 1232×616），畫布 1904×1104；
    · 明亮的春天色：淺綠草地、外面是開闊的花草地＋圓滾滾的樹（開花的、結果的）、香菇、小池塘，
      一條奶油色小路繞花園一圈（路人走的），幾條岔路走出畫面；
    · 圍牆改成矮石基＋白色尖頭柵欄（原本那張畫風花園就是白柵欄）、柱頭有小燈籠、牆上掛三角旗；
    · 小屋：茅草屋頂、木板牆（跟城鎮那間同一套）、紫色圓頂門、愛心鏤空的百葉窗、窗台上的黑貓、爬牆玫瑰、
      歪歪的煙囪冒一朵煙；
    · 圍牆內的擺設：角落的花樹、雨水桶、長椅、戴女巫帽的稻草人、小鳥浴盆、南瓜堆（各佔一格、都是障礙）。

── 輸出與排序（路人要前後正確）───────────────────────────────────
  rooms/garden8.png        底圖（-10000），**整張完整畫面**（所有東西都畫進去，其他圖層缺了也不會破洞）。
  rooms/garden8-back.png   後景層（BackOrder -8000）：後面兩道牆＋柵欄、三根後柱、小屋（含屋頂、煙、貓、玫瑰），
                           以及「小路與後牆之間」的東西。走在這些東西後面的路人排 FolkBackOrder（-8100）→ 被蓋住；
                           女巫、花圃（-y，約 -650..650）永遠在它上面。影子層是 -8500，也在它下面（路人躲在小屋後時影子不會透出來）。
  rooms/garden8-front.png  前景牆（FrontOrder 3000）：前面兩道牆＋柵欄＋最前面的柱子。女巫走到後面只露上半身。
  rooms/garden8-fore.png   最前景（ForeOrder 6000）：小路「外側」的樹叢與花（在路人前面）。
                           其他路人排 FolkFrontOrder - y（3300..4700）：在前牆之上、最前景之下。
  三張圖層只保留「在完整畫面裡露出來的那些像素」（同一次 z-buffer 算的），裁成最小矩形，位置寫進 Layers。
  路人該排哪一層：從腳底沿視線往玩家那邊（u+t, v+t）走，碰到 BackRects（後景層物件的地面範圍）＝在它們後面。

── 座標 ───────────────────────────────────────────────────────
  格 (gx, gy) 中心 = ( OX + (gx-gy)*HALF_W , OY - (gx+gy)*HALF_H )；gx＝u 往畫面右下、gy＝v 往左下、z 往上（世界 px）。

── 畫法 ───────────────────────────────────────────────────────
  · 邏輯像素 ×2（女巫是原生 1px ×1.6）。牆、柱、小屋、屋頂、煙囪、花箱是凸多面體，每個邏輯像素打一條等距視線取最近的面。
  · 柵欄木條、樹、花盆、燈籠、旗子、貓、煙是「立牌」（垂直於視線的平面，深度看底座 u+v），一樣進 z-buffer。
  · 長春藤、玫瑰、花、草叢、香菇、踏腳石是「貼花」：只貼在指定物件（或地面）露出來的像素上。
  · 光從左上來：頂面最亮、朝 +v（畫面左下）的面次之、朝 +u（右下）的面最暗；色階暗部偏冷、亮部偏暖。
  · 建物描邊 #2a1b24（同 villagers8／items8）；植物用深綠描邊（柔和一點）。所有變化都是固定種子，重跑逐 byte 一樣。
"""
import os
import sys
import math

import numpy as np
from PIL import Image

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, 'Assets', 'Resources')
CS_OUT = os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'GardenRoomData.cs')

# ═══════════════════════════════ 尺寸與格盤 ═══════════════════════════════

S = 2
IMG_W, IMG_H = 1904, 1104
LW, LH = IMG_W // S, IMG_H // S

HALF_W, HALF_H = 44.0, 22.0
COLS, ROWS = 16, 12
OX, OY = -150.0, 220.0
PERP = 2 * HALF_W * HALF_H / math.hypot(HALF_W, HALF_H)

PLAYER_R = 11.0
WALK_INSET = 0.30
DOOR = (11, 0)
DOOR_FRONT = (11, 1)
SPAWN = (11, 2)
DOOR_RANGE = 70.0
PLOT_BLOCK = (6, 6)

BG_ORDER = -10000
BACK_ORDER = -8000
FOLK_BACK_ORDER = -8100
FRONT_ORDER = 3000
FOLK_FRONT_ORDER = 4000
FORE_ORDER = 6000
FOLK_COUNT = 4

WALL_T = 0.24
BASE_H = 20.0
CAP_H = 8.0
FENCE_H = 36.0
FRONT_BASE_H = 14.0
FRONT_CAP_H = 6.0
FRONT_FENCE_H = 26.0
PILLAR = 0.2
CAP_O = 0.05

COTTAGE_U0 = 7.5
COTTAGE_VB = -3.4
COTTAGE_H = 190.0
ROOF_S = 78.0
ROOF_TH = 14.0
ROOF_VE = -0.15
FOUND_H = 26.0

PATH_HALF = 0.55
P_BACK = -0.5 - 2.6          # 後面的小路離牆遠一點：路人的腳要在柵欄頂上面才看得到（44px/格 × 2.6 > 柵欄高 64）
P_FRONT_V = ROWS - 0.5 + 1.4
P_FRONT_U = COLS - 0.5 + 1.4
P_COT = COTTAGE_VB - 1.4

OUTLINE = '#2a1b24'


def hexrgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.uint8)


def ramp(*hs):
    return np.stack([hexrgb(h) for h in hs])


STONE = ramp('#6e5a5e', '#8a7069', '#a68873', '#bf9f82', '#d4b693', '#e3caa6', '#eedcbb', '#f7ebd2', '#fff7e8')
STONE_B = ramp('#665d6a', '#80757c', '#9b8e8e', '#b4a69f', '#c9bcb0', '#dacfc1', '#e8dfd2', '#f3ece2', '#fdf9f2')
STONE_R = ramp('#74585a', '#916c64', '#ad8370', '#c69a7e', '#d9b08e', '#e7c4a1', '#f1d6b6', '#f9e6cd', '#fff3e4')
MORTAR = hexrgb('#9a7f72')
MOSS = ramp('#3d7a45', '#4f9150', '#63a75a', '#7bbb65', '#96cd73', '#b2dc86', '#cde99d')
IVY = ramp('#2e6040', '#3a7a47', '#4c934f', '#62ab59', '#7dc165', '#9bd476', '#bbe48e')
GRASS = ramp('#3f8a4c', '#4b9a51', '#58aa56', '#66b85b', '#76c561', '#88d06a', '#9cda75', '#b3e386', '#cbec9e')
MEADOW = ramp('#57994d', '#66a652', '#76b258', '#87be60', '#99c96a', '#acd377', '#c0dd88', '#d3e79c')
PLANK = ramp('#5a2414', '#7a3216', '#9a4518', '#b8581c', '#d06c22', '#e3842e', '#f09c44', '#f7b766', '#fcd08c')
TIMBER = ramp('#3a1a12', '#552a18', '#70391d', '#8c4d25', '#a6622f', '#bf7a3c', '#d4934c')
THATCH = ramp('#6e4320', '#8f5a24', '#ad7228', '#c78a30', '#dba23e', '#eab856', '#f4cd74', '#fbe09a', '#fff0c4', '#fff8e0')
GLASS = ramp('#2f4a6e', '#41648c', '#5b84aa', '#7fa6c6', '#a9c8de', '#d3e7f0', '#f4fbfb')
LEAD = hexrgb('#3a3048')
METAL = ramp('#2c2933', '#423e4a', '#5c5764', '#7c7684', '#a49dab', '#cfc8d2', '#f2eef4')
GLOW = ramp('#e8903a', '#ffb24a', '#ffd06e', '#ffe7a6', '#fff8dc')
WATER = ramp('#3b74b0', '#4a8ac2', '#5da2d2', '#7bbbe0', '#a3d4ec', '#cdeaf5', '#f2fbfd')
FOLI = ramp('#2c5a3c', '#357046', '#41864e', '#509c56', '#62b05e', '#78c269', '#92d277', '#afe08c', '#cdeda6')
FOLI_Y = ramp('#3d6438', '#4c7c3e', '#5e9545', '#73ac4d', '#8bc157', '#a4d264', '#bde076', '#d4eb90', '#e8f4b2')
FOLI_OUT = hexrgb('#24452f')
TRUNK = ramp('#3e2419', '#583322', '#74462c', '#8f5b37', '#a87245', '#c08a58')
BLOSSOM = ramp('#a0507a', '#c86e96', '#e692b2', '#f6b6cc', '#ffd6e2', '#fff2f6')
WBLOSSOM = ramp('#9a90b0', '#bcb6cc', '#dad6e6', '#f0eef6', '#ffffff', '#ffffff')
APPLE = ramp('#7a1f2c', '#b02a35', '#dc4148', '#f26e66', '#ffb0a2')
ORANGE = ramp('#8a3e12', '#c0601a', '#e8862a', '#f6a64a', '#ffd08a')
PATH = ramp('#a88660', '#bc9b72', '#cdae86', '#dcc09a', '#e7d0ad', '#f0dfc2', '#f7ecd7', '#fdf7ec')
PICKET = ramp('#5f5a7a', '#9d9bb8', '#c4c5da', '#e2e4ef', '#f6f7fc', '#ffffff')
DOORC = ramp('#3a2650', '#563a76', '#73529a', '#9070ba', '#ae92d4', '#ccb6e8')
SHUTTER = ramp('#2f6066', '#438088', '#5ca2a6', '#7fc0c0', '#a9dad6', '#d4eeea')
POT = ramp('#6a2e20', '#93432b', '#b85d39', '#d47a4c', '#e89a66', '#f6be8e')
PUMPKIN = ramp('#7a2e10', '#a8441a', '#d06222', '#ec8530', '#f8a84c', '#ffd08a')
FLAGS = [hexrgb(h) for h in ('#f29ab4', '#ffd36e', '#8fd0e8', '#b8a2e6', '#9ee08e', '#ffb08a')]
FL_WHITE = hexrgb('#fffaf0')
FL_YEL = hexrgb('#ffd84a')
FL_VIO = hexrgb('#a98ae8')
FL_PINK = hexrgb('#ff8fb6')
FL_BLUE = hexrgb('#79b8ff')
FL_RED = hexrgb('#f0506a')
FL_ORANGE = hexrgb('#ffa64a')
CREAM = hexrgb('#fffbef')
OUT = hexrgb(OUTLINE)

UNIT_PX = HALF_W / S


def g2w(u, v, z=0.0):
    return OX + (u - v) * HALF_W, OY - (u + v) * HALF_H + z


def w2g(x, y):
    a = (x - OX) / HALF_W
    b = (OY - y) / HALF_H
    return (a + b) / 2.0, (b - a) / 2.0


def w2lp(x, y):
    return (x + IMG_W / 2.0) / S - 0.5, (IMG_H / 2.0 - y) / S - 0.5


def g2lp(u, v, z=0.0):
    return w2lp(*g2w(u, v, z))


def cell_center(gx, gy):
    return g2w(gx, gy)


_I = np.arange(LW)
_J = np.arange(LH)
II, JJ = np.meshgrid(_I, _J)
WX = -IMG_W / 2.0 + S * II + S / 2.0
WY = IMG_H / 2.0 - S * JJ - S / 2.0
UG, VG = w2g(WX, WY)


def h32(*arrs):
    h = np.uint64(1469598103934665603)
    out = np.full(np.broadcast(*[np.asarray(a) for a in arrs]).shape, h, dtype=np.uint64)
    with np.errstate(over='ignore'):
        for a in arrs:
            a = np.asarray(a).astype(np.int64).astype(np.uint64)
            out = (out ^ a) * np.uint64(1099511628211)
            out ^= out >> np.uint64(29)
            out = out * np.uint64(0x9E3779B97F4A7C15)
            out ^= out >> np.uint64(31)
    return (out % np.uint64(1 << 24)).astype(np.float64) / float(1 << 24)


def hs(*v):
    return float(h32(*[np.array(int(round(x * 1000)) if isinstance(x, float) else int(x)) for x in v]))


def vnoise_at(x, y, cell, seed):
    fx = np.asarray(x, dtype=np.float64) / cell
    fy = np.asarray(y, dtype=np.float64) / cell
    x0 = np.floor(fx)
    y0 = np.floor(fy)
    tx = fx - x0
    ty = fy - y0
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    a = h32(x0, y0, seed)
    b = h32(x0 + 1, y0, seed)
    c = h32(x0, y0 + 1, seed)
    d = h32(x0 + 1, y0 + 1, seed)
    return (a + (b - a) * tx) + ((c + (d - c) * tx) - (a + (b - a) * tx)) * ty


def fbm(x, y, cell, seed, oct=3):
    tot = 0.0
    amp = 1.0
    norm = 0.0
    for k in range(oct):
        tot = tot + amp * vnoise_at(x, y, cell / (2 ** k), seed + k * 17)
        norm += amp
        amp *= 0.5
    return tot / norm


# ═══════════════════════════════ 路人的路網（小路）═══════════════════════════════

_GRAPH = None


def folk_graph():
    """
    繞花園一圈的小路（含小屋後面）＋幾條走出畫面的岔路。回傳 (nodes[(u,v)], edges[(a,b)], exits[idx])。
    每段大約 2.6 格一個節點：路人在節點上隨機挑下一段（不立刻走回頭），偶爾停下、偶爾走出畫面再回來。
    """
    global _GRAPH
    if _GRAPH is not None:
        return _GRAPH
    corners = [(P_BACK, P_BACK), (P_BACK, P_FRONT_V), (P_FRONT_U, P_FRONT_V), (P_FRONT_U, P_COT),
               (COTTAGE_U0 - 1.0, P_COT), (COTTAGE_U0 - 2.0, P_BACK)]
    nodes = []
    loop_idx = []
    for k in range(len(corners)):
        a = corners[k]
        b = corners[(k + 1) % len(corners)]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(round(L / 2.6)))
        for s in range(n):
            t = s / n
            nodes.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            loop_idx.append(len(nodes) - 1)
    edges = [(loop_idx[k], loop_idx[(k + 1) % len(loop_idx)]) for k in range(len(loop_idx))]

    def nearest(p):
        return min(loop_idx, key=lambda i: (nodes[i][0] - p[0]) ** 2 + (nodes[i][1] - p[1]) ** 2)

    exits = []
    for at, far in (((P_BACK, P_FRONT_V), (P_BACK - 9.0, P_FRONT_V + 1.0)),
                    ((P_FRONT_U, P_FRONT_V), (P_FRONT_U + 5.5, P_FRONT_V + 5.5)),
                    ((P_FRONT_U, 4.0), (P_FRONT_U + 12.0, 2.0)),
                    ((P_BACK, P_BACK), (P_BACK - 6.0, P_BACK - 6.0)),
                    ((12.0, P_COT), (14.0, P_COT - 9.0))):
        i = nearest(at)
        nodes.append(far)
        e = len(nodes) - 1
        edges.append((i, e))
        exits.append(e)
    _GRAPH = (nodes, edges, exits)
    return _GRAPH


def seg_dist(pu, pv, a, b):
    au, av = a
    bu, bv = b
    du, dv = bu - au, bv - av
    l2 = du * du + dv * dv
    t = np.clip(((pu - au) * du + (pv - av) * dv) / max(l2, 1e-9), 0, 1)
    qu, qv = au + du * t, av + dv * t
    return np.sqrt((pu - qu) ** 2 + (pv - qv) ** 2)


def path_dist(pu, pv):
    nodes, edges, _ex = folk_graph()
    d = np.full(np.shape(pu), np.inf)
    for a, b in edges:
        d = np.minimum(d, seg_dist(pu, pv, nodes[a], nodes[b]))
    return d


# ═══════════════════════════════ 光線求交的立體 ═══════════════════════════════

D = np.array([1.0, 1.0, 2.0 * HALF_H])


class Prim:
    def __init__(self, name, planes, mat, layer='bg'):
        self.name = name
        self.planes = planes
        self.mat = mat
        self.layer = layer


def box(name, u0, u1, v0, v1, z0, z1, mat, layer='bg'):
    return Prim(name, [
        ((1, 0, 0), u1, '+u'), ((-1, 0, 0), -u0, '-u'),
        ((0, 1, 0), v1, '+v'), ((0, -1, 0), -v0, '-v'),
        ((0, 0, 1), z1, 'top'), ((0, 0, -1), -z0, 'bot'),
    ], mat, layer)


def raycast(prim):
    tu = np.full(UG.shape, np.inf)
    tl = np.full(UG.shape, -np.inf)
    face = np.full(UG.shape, -1, dtype=np.int16)
    ok = np.ones(UG.shape, dtype=bool)
    for k, (a, b, _f) in enumerate(prim.planes):
        a = np.asarray(a, dtype=np.float64)
        ap = a[0] * UG + a[1] * VG
        ad = float(a @ D)
        if abs(ad) < 1e-9:
            ok &= ap <= b
            continue
        t = (b - ap) / ad
        if ad > 0:
            better = t < tu
            tu = np.where(better, t, tu)
            face = np.where(better, k, face)
        else:
            tl = np.maximum(tl, t)
    hit = ok & (tl <= tu) & np.isfinite(tu) & (tu >= 0)
    return np.where(hit, tu, -np.inf), face


class Billboard:
    def __init__(self, name, rgba, x0, y0, base_uv, layer='bg', outline=False):
        self.name = name
        self.rgba = rgba
        self.x0, self.y0 = int(x0), int(y0)
        self.base = base_uv
        self.layer = layer
        self.outline = outline


class Scene:
    def __init__(self, prims, bills, ground_rgb):
        self.prims = prims
        self.bills = bills
        self.names = {}
        self.layer_of = {0: 'bg'}
        zbuf = np.zeros(UG.shape)
        ids = np.zeros(UG.shape, dtype=np.int32)
        rgba = np.zeros((LH, LW, 4), dtype=np.uint8)
        rgba[..., :3] = ground_rgb
        rgba[..., 3] = 255
        hits = []
        for n, p in enumerate(prims, start=1):
            t, face = raycast(p)
            win = t > zbuf
            zbuf = np.where(win, t, zbuf)
            ids = np.where(win, n, ids)
            hits.append((t, face))
            self.names[p.name] = n
            self.layer_of[n] = p.layer
        nb = len(prims)
        for m, b in enumerate(bills, start=nb + 1):
            self.names[b.name] = m
            self.layer_of[m] = b.layer
            h, w = b.rgba.shape[:2]
            x0, y0 = b.x0, b.y0
            xa, ya = max(0, x0), max(0, y0)
            xb, yb = min(LW, x0 + w), min(LH, y0 + h)
            if xa >= xb or ya >= yb:
                continue
            sub = b.rgba[ya - y0:yb - y0, xa - x0:xb - x0]
            bu, bv = b.base
            tb = ((bu + bv) - (UG[ya:yb, xa:xb] + VG[ya:yb, xa:xb])) / 2.0
            win = (sub[..., 3] > 0) & (tb > zbuf[ya:yb, xa:xb])
            zbuf[ya:yb, xa:xb] = np.where(win, tb, zbuf[ya:yb, xa:xb])
            ids[ya:yb, xa:xb] = np.where(win, m, ids[ya:yb, xa:xb])
            for c in range(3):
                rgba[ya:yb, xa:xb, c] = np.where(win, sub[..., c], rgba[ya:yb, xa:xb, c])
        for n, (p, (t, face)) in enumerate(zip(prims, hits), start=1):
            m = ids == n
            if not m.any():
                continue
            tt = t[m]
            u = UG[m] + tt
            v = VG[m] + tt
            z = 2.0 * HALF_H * tt
            fn = np.array([p.planes[k][2] for k in face[m]])
            rgba[m, :3] = p.mat(fn, u, v, z, II[m], JJ[m])
        self.rgba, self.ids, self.zbuf, self.nb = rgba, ids, zbuf, nb

    def outline(self):
        ids, zbuf, rgba = self.ids, self.zbuf, self.rgba
        out = np.zeros(UG.shape, dtype=bool)
        mine = (ids >= 1) & (ids <= self.nb)
        for m, b in enumerate(self.bills, start=self.nb + 1):
            if b.outline:
                mine |= ids == m
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nid = np.roll(np.roll(ids, dy, 0), dx, 1)
            nz = np.roll(np.roll(zbuf, dy, 0), dx, 1)
            out |= mine & (nid != ids) & ((nz < zbuf - 0.04) | (nid == 0))
        out[0, :] = False
        out[-1, :] = False
        out[:, 0] = False
        out[:, -1] = False
        rgba[out, :3] = OUT

    def mask(self, *names):
        m = np.zeros(UG.shape, dtype=bool)
        for n in names:
            if n in self.names:
                m |= self.ids == self.names[n]
        return m

    def layer_mask(self, layer):
        keys = [k for k, l in self.layer_of.items() if l == layer and k != 0]
        return np.isin(self.ids, keys)


# ═══════════════════════════════ 材質 ═══════════════════════════════

def face_ah(fn, u, v, z):
    a = np.where(fn == '+u', -v, u) * UNIT_PX
    return a, z / S


def stones(a, h, sx, sy, seed, stagger=True):
    rows = np.floor(h / sy)
    best1 = np.full(a.shape, np.inf)
    best2 = np.full(a.shape, np.inf)
    oa = np.zeros(a.shape)
    oh = np.zeros(a.shape)
    sid = np.zeros(a.shape)
    for dr in (-1, 0, 1):
        r = rows + dr
        off = (r % 2) * (sx * 0.5) if stagger else 0.0
        cols = np.floor((a - off) / sx)
        for dc in (-1, 0, 1):
            c = cols + dc
            ja = 0.5 + (h32(c, r, seed) - 0.5) * 0.5
            jh = 0.5 + (h32(c, r, seed + 1) - 0.5) * 0.4
            pa = (c + ja) * sx + off
            ph = (r + jh) * sy
            da = a - pa
            dh = (h - ph) * (sx / sy) * 0.8
            d = np.sqrt(da * da + dh * dh)
            closer = d < best1
            best2 = np.where(closer, best1, np.minimum(best2, d))
            best1 = np.where(closer, d, best1)
            oa = np.where(closer, a - pa, oa)
            oh = np.where(closer, h - ph, oh)
            sid = np.where(closer, h32(c, r, seed + 7), sid)
    return best2 - best1, oa, oh, sid


def stone_colors(edge, oa, oh, sid, base, sx, sy, seed, I, J, mortar_w=1.0):
    """圓潤的暖色石頭：每顆色相不同、左上亮右下暗、亮緣、偶爾的小裂縫；石縫是暖灰。"""
    pal_pick = np.where(sid < 0.5, 0, np.where(sid < 0.8, 1, 2))
    tone = base + np.where(h32(np.floor(sid * 9973), 3) > 0.7, 1, 0) - np.where(h32(np.floor(sid * 7919), 5) > 0.8, 1, 0)
    nrm = (-oa / sx) * 0.7 + (oh / sy) * 0.9
    tone = tone + np.where(nrm > 0.4, 1, 0) - np.where(nrm < -0.6, 1, 0)
    rim = edge < 2.0
    tone = np.where(rim & (nrm > 0.0), tone + 1, tone)
    tone = np.where(rim & (nrm <= -0.2), tone - 1, tone)
    speck = h32(I, J, seed + 3)
    tone = np.where(speck > 0.95, tone + 1, tone)
    crack = (h32(np.floor(sid * 5003), 9) > 0.92) & (np.abs(oa * 0.55 - oh) < 0.5) & (np.abs(oa) < sx * 0.25)
    tone = np.where(crack, base - 2, tone)
    tone = np.clip(tone, 0, 8).astype(int)
    col = np.where((pal_pick == 0)[:, None], STONE[tone], np.where((pal_pick == 1)[:, None], STONE_B[tone], STONE_R[tone]))
    col = np.where((edge < mortar_w)[:, None], MORTAR, col)
    return col


def moss_over(col, mask, I, J, seed, light=0):
    if not mask.any():
        return col
    n = h32(I // 2, J, seed)
    t = np.where(n > 0.7, 4, np.where(n > 0.35, 3, 2)) + light
    t = np.where(h32(I, J, seed + 1) > 0.9, t + 1, t)
    c = MOSS[np.clip(t, 0, len(MOSS) - 1)]
    return np.where(mask[:, None], c, col)


def shade_of(fn):
    b = np.full(fn.shape, 5, dtype=np.int32)
    b[fn == 'top'] = 6
    b[fn == '+u'] = 3
    return b


def wall_body_mat(top_h, seed):
    def mat(fn, u, v, z, I, J):
        a, h = face_ah(fn, u, v, z)
        base = shade_of(fn)
        edge, oa, oh, sid = stones(a, h, 10.0, 6.0, seed)
        col = stone_colors(edge, oa, oh, sid, base, 10.0, 6.0, seed, I, J)
        vert = fn != 'top'
        sh = vert & (h > top_h / S - 1.5)
        col = np.where(sh[:, None], (col.astype(int) * 0.82).astype(np.uint8), col)
        mb = vert & (h < 2.0 + 2.0 * vnoise_at(a, 0 * a, 6, seed + 50)) & (h32(I, J, seed + 51) > 0.35)
        col = moss_over(col, mb, I, J, seed + 52, light=0)
        return col
    return mat


def cap_mat(seed):
    """圓潤的壓頂石：長石板、接縫、左緣亮；頂面有一點青苔。"""
    def mat(fn, u, v, z, I, J):
        vert = fn != 'top'
        a, h = face_ah(fn, u, v, z)
        al = np.where(vert, a, (u - v) * UNIT_PX)
        slab = np.floor(al / 14.0)
        fa = al - slab * 14.0
        base = np.where(fn == 'top', 7, np.where(fn == '+u', 4, 6))
        var = h32(slab, seed)
        t = base + np.where(var > 0.7, 1, 0) - np.where(var < 0.25, 1, 0)
        t = np.where((fa >= 1.0) & (fa < 2.2), t + 1, t)
        col = STONE[np.clip(t, 0, 8)]
        col = np.where((fa < 1.0)[:, None], MORTAR, col)
        mt = (fn == 'top') & (fbm(al, (u + v) * UNIT_PX * 2, 9, seed + 70, 2) > 0.62)
        col = moss_over(col, mt, I, J, seed + 71, light=2)
        return col
    return mat


def plank_colors(a, h, base, seed, I, J, width=4.0, pal=PLANK):
    pk = np.floor(a / width)
    fa = a - pk * width
    var = h32(pk, seed)
    tone = base + np.where(var > 0.72, 1, 0) - np.where(var < 0.22, 1, 0)
    grain = h32(np.floor(a), np.floor(h / 7.0 + h32(np.floor(a), seed + 2) * 3), seed + 1)
    tone = np.where(grain > 0.82, tone - 1, tone)
    tone = np.where((grain < 0.06) & (fa > 1), tone + 1, tone)
    knot_c = h32(pk, np.floor(h / 23.0), seed + 3) > 0.88
    kh = (h % 23.0) - 11.0
    knot = knot_c & ((fa - width / 2) ** 2 + (kh * 0.8) ** 2 < 1.4)
    tone = np.where(knot, base - 2, tone)
    tone = np.where(fa < 1.0, tone + 1, tone)
    tone = np.where(fa > width - 1.0, base - 2, tone)
    return pal[np.clip(tone, 0, len(pal) - 1)]


COT_DOOR_U = 11.0
COT_DOOR_W = 0.62
COT_DOOR_TOP = 104.0
COT_WINDOWS = [(9.0, 0.5, 74.0, 136.0), (13.3, 0.5, 74.0, 136.0)]
COT_POSTS_FRONT = [(COTTAGE_U0, COTTAGE_U0 + 0.2), (COLS - 0.7, COLS - 0.5)]
COT_POSTS_SIDE = [(-0.7, -0.5), (COTTAGE_VB, COTTAGE_VB + 0.2)]


HEART5 = np.array([[0, 1, 0, 1, 0], [1, 1, 1, 1, 1], [1, 1, 1, 1, 1], [0, 1, 1, 1, 0], [0, 0, 1, 0, 0]], dtype=bool)


def heart(x, y):
    x = np.abs(x)
    return (x * x + (y - np.sqrt(np.clip(x, 0, None)) * 0.9) ** 2) < 0.9


def cottage_mat(fn, u, v, z, I, J):
    out = np.zeros((len(fn), 3), dtype=np.uint8)
    front = fn == '+v'
    side = fn == '+u'
    a, h = face_ah(fn, u, v, z)
    lit = np.where(side, -2, 0)
    H = COTTAGE_H
    out[:] = plank_colors(a, h, 5 + lit, 11, I, J)

    found = z < FOUND_H
    edge, oa, oh, sid = stones(a, h, 10.0, 6.0, 31)
    sc = stone_colors(edge, oa, oh, sid, 5 + lit, 10.0, 6.0, 31, I, J)
    sc = moss_over(sc, (h < 2.0 + 2 * vnoise_at(a, 0 * a, 7, 33)) & (h32(I, J, 34) > 0.4), I, J, 35)
    out = np.where(found[:, None], sc, out)

    in_beam = ((z >= FOUND_H) & (z < FOUND_H + 10)) | ((z >= H - 12) & (z < H)) | ((z >= 146) & (z < 154))
    post = np.zeros(len(fn), dtype=bool)
    for p0, p1 in COT_POSTS_FRONT:
        post |= front & (u >= p0) & (u < p1)
    for p0, p1 in COT_POSTS_SIDE:
        post |= side & (v >= p0) & (v < p1)
    tb = TIMBER[np.clip(4 + lit // 2 - np.where(h32(np.floor(h), np.floor(a / 6), 13) > 0.8, 1, 0), 0, 6)]
    beam_m = in_beam & ~found
    out = np.where((beam_m | (post & ~found))[:, None], tb, out)
    beam_top = beam_m & (((z >= FOUND_H + 8) & (z < FOUND_H + 10)) | ((z >= H - 2) & (z < H)) | ((z >= 152) & (z < 154)))
    out = np.where(beam_top[:, None], TIMBER[np.clip(6 + lit // 2, 0, 6)], out)

    wins = [(front, wc, ww, z0, z1, True) for (wc, ww, z0, z1) in COT_WINDOWS]
    wins.append((side, -2.0, 0.42, 74.0, 130.0, True))
    wins.append((side, -2.0, 0.3, H + 30.0, H + 66.0, False))
    for face_m, wc, ww, z0, z1, shutters in wins:
        along = np.where(side, -v, u)
        du = (along - wc) * UNIT_PX
        hw = ww * UNIT_PX
        hz0, hz1 = z0 / S, z1 / S
        arch_top = hz1 + 0.6 * hw * np.sqrt(np.clip(1 - (du / (hw + 2)) ** 2, 0, 1))
        win = face_m & (np.abs(du) <= hw + 2) & (h >= hz0 - 2) & (h <= arch_top + 2)
        frame = win & ((np.abs(du) > hw - 1) | (h < hz0 + 1) | (h > arch_top - 1))
        glass = win & ~frame
        gx = du + hw
        gy = h - hz0
        lat = (((gx + gy) % 6.0) < 1.0) | (((gx - gy) % 6.0) < 1.0)
        gt = 3 + np.where(gy > (hz1 - hz0) * 0.55, 1, 0) + np.where(gx < hw * 0.6, 1, 0)
        refl = ((gx - gy * 0.7) % 14.0 < 2.2) & (gy > 3)
        gt = np.where(refl, 6, gt)
        gcol = GLASS[np.clip(gt + (lit // 2), 0, 6)]
        gcol = np.where(lat[:, None], LEAD, gcol)
        out = np.where(glass[:, None], gcol, out)
        out = np.where(frame[:, None], TIMBER[np.where(h > arch_top - 1.5, 6, 4)], out)
        sill = face_m & (np.abs(du) <= hw + 3) & (h >= hz0 - 4) & (h < hz0 - 1)
        out = np.where(sill[:, None], TIMBER[np.where(h > hz0 - 2, 6, 3)], out)
        if shutters:
            for sgn in (-1, 1):
                s0, s1 = hw + 3, hw + 3 + hw * 0.75
                sh = face_m & (sgn * du >= s0) & (sgn * du <= s1) & (h >= hz0) & (h <= hz1)
                sx = (sgn * du - s0) / (s1 - s0)
                sy = (h - hz0) / (hz1 - hz0)
                edge_s = (sx < 0.12) | (sx > 0.88) | (sy < 0.06) | (sy > 0.94)
                slat = ((h - hz0) % 4.0) < 1.0
                tone = np.where(edge_s, 1, np.where(slat, 2, 3)) + (lit // 2)
                # 愛心鏤空：5×5 的點陣，放在百葉窗上半部正中
                wpx = (s1 - s0)
                hx = np.floor(sgn * du - s0 - (wpx / 2 - 2.5)).astype(int)
                hy = np.floor((hz1 - h) - (hz1 - hz0) * 0.22).astype(int)
                inb = (hx >= 0) & (hx < 5) & (hy >= 0) & (hy < 5)
                ht = inb & HEART5[np.clip(hy, 0, 4), np.clip(hx, 0, 4)]
                col = SHUTTER[np.clip(tone, 0, 5)]
                col = np.where(ht[:, None], TIMBER[1], col)
                out = np.where(sh[:, None], col, out)

    du = (u - COT_DOOR_U) * UNIT_PX
    dw = COT_DOOR_W * UNIT_PX
    top = COT_DOOR_TOP / S
    arch = top + 0.95 * dw * np.sqrt(np.clip(1 - (du / dw) ** 2, 0, 1))
    door = front & (np.abs(du) <= dw) & (h <= arch)
    archf = top + 0.95 * (dw + 3) * np.sqrt(np.clip(1 - (du / (dw + 3)) ** 2, 0, 1)) + 1
    dframe = front & ~door & (np.abs(du) <= dw + 3) & (h <= archf)
    dcol = plank_colors(du + 40, h, 3, 17, I, J, width=5.0, pal=DOORC)
    hinge = ((np.abs(h - 12) < 1.4) | (np.abs(h - (top - 4)) < 1.4)) & (du < -dw * 0.2)
    dcol = np.where(hinge[:, None], METAL[np.where(np.abs(h - 12) < 0.5, 4, 3)], dcol)
    knob = ((du - dw * 0.58) ** 2 + (h - 30) ** 2) < 3.2
    dcol = np.where(knob[:, None], np.where(((du - dw * 0.58) + (h - 30) < 0)[:, None], hexrgb('#fff0a0'), hexrgb('#e8b040')), dcol)
    rw = ((du / (dw * 0.5)) ** 2 + ((h - (top + 4)) / 6.5) ** 2) <= 1.0
    rwl = (np.abs(du) < 0.6) | (np.abs(h - (top + 4)) < 0.6)
    dcol = np.where(rw[:, None], np.where(rwl[:, None], LEAD, GLASS[np.where(h > top + 4, 5, 3)]), dcol)
    hx = np.floor(du + 2.5).astype(int)
    hy = np.floor(64 - h).astype(int)
    hrt = (hx >= 0) & (hx < 5) & (hy >= 0) & (hy < 5) & HEART5[np.clip(hy, 0, 4), np.clip(hx, 0, 4)]
    dcol = np.where(hrt[:, None], DOORC[5], dcol)
    out = np.where(door[:, None], dcol, out)
    out = np.where(dframe[:, None], TIMBER[np.where(du < -dw - 1, 5, 3)], out)
    return out


def thatch_mat(fn, u, v, z, I, J):
    out = np.zeros((len(fn), 3), dtype=np.uint8)
    top = fn == 'top'
    q = (ROOF_VE - v)
    al = u * UNIT_PX
    qq = q / 0.26
    row = np.floor(qq)
    f = qq - row
    fr = 0.18 + 0.22 * h32(np.floor(al / 2), row, 5)
    tone = np.full(len(fn), 6)
    tone = np.where(f < fr, 4, tone)
    tone = np.where((f >= fr) & (f < fr + 0.12), 8, tone)
    tone = np.where(f > 0.85, 5, tone)
    streak = h32(np.floor(al), row, 7)
    tone = np.where(streak > 0.78, tone + 1, np.where(streak < 0.2, tone - 1, tone))
    tone = np.where((f < 0.08) & (h32(np.floor(al), row, 9) > 0.6), 3, tone)
    qr = (ROOF_VE - (COTTAGE_VB - 0.35 + ROOF_VE) / 2.0)
    ridge = q > qr - 0.18
    rt = np.where((np.floor(al) % 9) < 1, 4, np.where(q > qr - 0.08, 9, 7))
    tone = np.where(ridge, rt, tone)
    out[:] = THATCH[np.clip(tone, 0, 9)]
    et = np.where(fn == '+u', 4, 5) + np.where(h32(np.floor(z / 3), np.floor(u * 5), 3) > 0.6, 1, 0)
    out = np.where((~top)[:, None], THATCH[np.clip(et, 0, 9)], out)
    return out


def chimney_mat(fn, u, v, z, I, J):
    a, h = face_ah(fn, u, v, z)
    edge, oa, oh, sid = stones(a, h, 6.0, 4.0, 81)
    col = stone_colors(edge, oa, oh, sid, shade_of(fn), 6.0, 4.0, 81, I, J)
    col = np.where((fn == 'top')[:, None], METAL[1], col)
    return col


def wood_box_mat(base=5):
    def mat(fn, u, v, z, I, J):
        a, h = face_ah(fn, u, v, z)
        b = np.where(fn == 'top', base + 2, np.where(fn == '+u', base - 1, base))
        aa = np.where(fn == 'top', (u - v) * UNIT_PX, a)
        hh = np.where(fn == 'top', (u + v) * UNIT_PX, h)
        g = h32(np.floor(hh * 0.5), np.floor(aa / 7), 5)
        t = np.where(g > 0.8, b - 1, b)
        return PLANK[np.clip(t, 0, 8)]
    return mat


def stone_box_mat(seed):
    def mat(fn, u, v, z, I, J):
        a, h = face_ah(fn, u, v, z)
        aa = np.where(fn == 'top', (u - v) * UNIT_PX, a)
        hh = np.where(fn == 'top', (u + v) * UNIT_PX * 0.5, h)
        edge, oa, oh, sid = stones(aa, hh, 12.0, 6.0, seed)
        return stone_colors(edge, oa, oh, sid, shade_of(fn) + 1, 12.0, 6.0, seed, I, J)
    return mat


def metal_mat(fn, u, v, z, I, J):
    return METAL[np.where(fn == 'top', 5, np.where(fn == '+u', 3, 4))]


# ═══════════════════════════════ 小圖（立牌與貼花）═══════════════════════════════

def blank(w, h):
    return np.zeros((h, w, 4), dtype=np.uint8)


def put(img, x, y, rgb):
    h, w = img.shape[:2]
    x, y = int(x), int(y)
    if 0 <= x < w and 0 <= y < h:
        img[y, x, :3] = rgb
        img[y, x, 3] = 255


def outline_mask(m):
    e = m.copy()
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        sh = np.zeros_like(m)
        ys = slice(max(dy, 0), m.shape[0] + min(dy, 0))
        yd = slice(max(-dy, 0), m.shape[0] + min(-dy, 0))
        xs = slice(max(dx, 0), m.shape[1] + min(dx, 0))
        xd = slice(max(-dx, 0), m.shape[1] + min(-dx, 0))
        sh[yd, xd] = m[ys, xs]
        e &= sh
    return m & ~e


def add_outline(img, color=OUT):
    m = img[..., 3] > 0
    big = m.copy()
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        sh = np.zeros_like(m)
        ys = slice(max(dy, 0), m.shape[0] + min(dy, 0))
        yd = slice(max(-dy, 0), m.shape[0] + min(-dy, 0))
        xs = slice(max(dx, 0), m.shape[1] + min(dx, 0))
        xd = slice(max(-dx, 0), m.shape[1] + min(-dx, 0))
        sh[yd, xd] = m[ys, xs]
        big |= sh
    ring = big & ~m
    img[ring, :3] = color
    img[ring, 3] = 255
    return img


def shaded_ellipse(img, cx, cy, rx, ry, pal, base, light=(-0.6, -0.8), spec=True):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    dx = (xx - cx) / rx
    dy = (yy - cy) / ry
    d2 = dx * dx + dy * dy
    m = d2 <= 1.0
    lv = -(dx * light[0] + dy * light[1])
    t = base + np.where(lv > 0.45, 2, np.where(lv > 0.0, 1, 0)) - np.where(lv < -0.55, 1, 0)
    t = np.where(d2 > 0.75, np.minimum(t, base), t)
    if spec:
        t = np.where(((dx + 0.42) ** 2 + (dy + 0.45) ** 2) < 0.04, len(pal) - 1, t)
    t = np.clip(t, 0, len(pal) - 1)
    img[m, :3] = pal[t[m]]
    img[m, 3] = 255
    return m


def foliage(w, h, clusters, rmp, seed, outline=FOLI_OUT, fruit=None, blossoms=None, bloom=0.0):
    """圓滾滾的樹冠：幾團大葉團（各自受光、左上一點高光）；可加花或果子；外圈深綠描邊。"""
    img = blank(w, h)
    yy, xx = np.mgrid[0:h, 0:w]
    k = len(rmp)
    for ci in sorted(range(len(clusters)), key=lambda i: clusters[i][1]):
        cx, cy, r, lv = clusters[ci]
        dx = (xx - cx) / r
        dy = (yy - cy) / r
        d2 = dx * dx + dy * dy
        ang = np.arctan2(dy, dx)
        bump = 1.0 + 0.07 * np.sin(ang * 9 + ci * 1.7)
        m = d2 <= bump * bump
        if not m.any():
            continue
        light = -(dx * -0.55 + dy * -0.8)
        t = lv + np.where(light > 0.5, 2, np.where(light > 0.0, 1, 0)) - np.where(light < -0.55, 1, 0)
        leaf = h32(xx // 2, yy // 2, seed + 31 * ci)
        t = np.where((leaf > 0.85) & (light > 0.0), t + 1, t)
        t = np.where((leaf < 0.06), t - 1, t)
        t = np.where(((dx + 0.35) ** 2 + (dy + 0.45) ** 2) < 0.03, k - 1, t)
        t = np.clip(t, 1, k - 1)
        img[m, :3] = rmp[t[m]]
        img[m, 3] = 255
        rim = m & ~np.roll(m, 1, 0)
        img[rim & (img[..., 3] > 0), :3] = rmp[np.clip(lv - 1, 0, k - 1)]
    m = img[..., 3] > 0
    inner = m & ~outline_mask(m)
    if blossoms is not None and bloom > 0:
        for y in range(2, h - 2, 3):
            for x in range(2, w - 2, 3):
                jx = x + int(hs(x, y, seed + 8) * 3) - 1
                jy = y + int(hs(x, y, seed + 9) * 3) - 1
                if not (0 < jx < w - 1 and 0 < jy < h - 1) or not inner[jy, jx]:
                    continue
                if hs(x, y, seed + 5) > bloom:
                    continue
                for ddx, ddy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
                    if inner[jy + ddy, jx + ddx]:
                        img[jy + ddy, jx + ddx, :3] = blossoms[3 if ddx + ddy < 0 else 2]
                img[jy, jx, :3] = blossoms[5] if hs(x, y, seed + 10) > 0.4 else FL_YEL
    if fruit is not None:
        for y in range(3, h - 3, 5):
            for x in range(3, w - 3, 5):
                jx = x + int(hs(x, y, seed + 18) * 3) - 1
                jy = y + int(hs(x, y, seed + 19) * 3) - 1
                if not inner[jy, jx] or not inner[jy + 1, jx + 1] or hs(x, y, seed + 20) > 0.45:
                    continue
                img[jy, jx, :3] = fruit[3]
                img[jy, jx + 1, :3] = fruit[2]
                img[jy + 1, jx, :3] = fruit[2]
                img[jy + 1, jx + 1, :3] = fruit[1]
                img[jy - 1, jx, :3] = fruit[4]
    o = outline_mask(m)
    img[o, :3] = outline
    return img


def make_tree(r, seed, kind='green', trunk_h=10):
    rmp = FOLI_Y if kind == 'orange' else FOLI
    w = int(r * 2.3) + 8
    h = int(r * 2.0) + trunk_h + 8
    cx = w / 2.0
    base_y = h - 3
    cy = base_y - trunk_h - r * 0.9
    clusters = [(cx, cy, r * 0.86, 4)]
    for k in range(6):
        ang = (k / 6.0) * math.pi * 2 + seed
        clusters.append((cx + math.cos(ang) * r * 0.42, cy + math.sin(ang) * r * 0.34, r * (0.5 + 0.08 * hs(seed, k)),
                         4 + (1 if math.sin(ang) < 0 else 0)))
    clusters.append((cx - r * 0.25, cy - r * 0.35, r * 0.45, 6))
    blos = BLOSSOM if kind == 'pink' else (WBLOSSOM if kind == 'white' else None)
    fruit = APPLE if kind == 'apple' else (ORANGE if kind == 'orange' else None)
    img = foliage(w, h, clusters, rmp, seed, blossoms=blos, bloom=0.42 if blos is not None else 0.0, fruit=fruit)
    tw = max(4, int(r * 0.22))
    for yy in range(int(cy + r * 0.45), base_y + 1):
        spread = 1 if yy >= base_y - 2 else 0
        x0 = int(round(cx - tw / 2)) - spread
        x1 = int(round(cx + tw / 2)) + spread
        for xx in range(x0, x1 + 1):
            if img[yy, xx, 3] and yy < cy + r * 0.8:
                continue
            if xx in (x0, x1) or yy == base_y:
                put(img, xx, yy, hexrgb('#3a2418'))
            else:
                rel = (xx - x0) / max(1, x1 - x0)
                t = 4 if rel < 0.35 else (3 if rel < 0.7 else 2)
                if hs(xx, yy // 3, seed) > 0.8:
                    t -= 1
                put(img, xx, yy, TRUNK[t])
    return img, (cx, base_y)


def bush_img(r, seed, flowers=None, berries=False):
    w = int(r * 2.7) + 6
    h = int(r * 1.8) + 6
    cx = w / 2.0
    base_y = h - 3
    cy = base_y - r * 0.75
    clusters = [(cx - r * 0.55, cy + r * 0.15, r * 0.62, 4), (cx + r * 0.55, cy + r * 0.18, r * 0.6, 4),
                (cx, cy - r * 0.12, r * 0.75, 5)]
    img = foliage(w, h, clusters, FOLI, seed, fruit=APPLE if berries else None)
    if flowers is not None:
        m = img[..., 3] > 0
        inner = m & ~outline_mask(m)
        for y in range(2, h - 2, 3):
            for x in range(2, w - 2, 3):
                if inner[y, x] and hs(x, y, seed + 7) < 0.4 and y < cy + r * 0.4:
                    for ddx, ddy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
                        if inner[y + ddy, x + ddx]:
                            img[y + ddy, x + ddx, :3] = flowers
                    img[y, x, :3] = CREAM if np.array_equal(flowers, FL_YEL) else FL_YEL
    return img, (cx, base_y)


def bill_from(name, img, foot, u, v, z=0.0, layer='bg', outline=False):
    lx, ly = g2lp(u, v, z)
    return Billboard(name, img, round(lx - foot[0]), round(ly - foot[1]), (u, v), layer, outline)


def picket_img(h_lp):
    """一根白色尖頭柵欄木條（3 寬＋外框，尖頭）。"""
    w = 5
    img = blank(w, h_lp + 2)
    for y in range(h_lp + 2):
        for x in range(w):
            if y == 0 and x != 2:
                continue
            if y == 1 and x in (0, 4):
                continue
            edge = x in (0, 4) or y == h_lp + 1 or y == 0 or (y == 1 and x in (1, 3))
            if edge:
                put(img, x, y, PICKET[0])
            else:
                put(img, x, y, PICKET[5] if x == 1 else (PICKET[4] if x == 2 else PICKET[2]))
    put(img, 2, 1, PICKET[5])
    return img


def rail_img(p0, p1):
    x0, y0 = p0
    x1, y1 = p1
    xa, xb = int(math.floor(min(x0, x1))) - 1, int(math.ceil(max(x0, x1))) + 1
    ya, yb = int(math.floor(min(y0, y1))) - 2, int(math.ceil(max(y0, y1))) + 3
    img = blank(xb - xa + 1, yb - ya + 1)
    n = int(abs(x1 - x0)) + 1
    for k in range(n + 1):
        t = k / max(1, n)
        x = int(round(x0 + (x1 - x0) * t)) - xa
        y = int(round(y0 + (y1 - y0) * t)) - ya
        put(img, x, y - 1, PICKET[0])
        put(img, x, y, PICKET[5])
        put(img, x, y + 1, PICKET[3])
        put(img, x, y + 2, PICKET[0])
    return img, (xa, ya)


def lantern_img():
    rows = ['...OO...', '..OMMO..', '.OMMMMO.', 'OMgyygMO', 'OMyWWyMO', 'OMyWWyMO', 'OMgyygMO', '.OMMMMO.',
            '..OmmO..', '..OmmO..']
    cmap = {'O': OUT, 'M': METAL[4], 'm': METAL[3], 'g': GLOW[1], 'y': GLOW[2], 'W': GLOW[4]}
    img = blank(8, len(rows))
    for yy, row in enumerate(rows):
        for xx, ch in enumerate(row):
            if ch in cmap:
                put(img, xx, yy, cmap[ch])
    img[2, 3:5, :3] = METAL[6]
    return img, (3.5, len(rows) - 1)


def ball_img():
    img = blank(12, 11)
    shaded_ellipse(img, 5.5, 5.0, 4.0, 3.6, STONE, 5)
    add_outline(img)
    return img, (5.5, 9)


def pot_img(flower):
    rows = ['....f.f.f....', '...fFfgfFf...', '..gfLgfLgFg..', '.gLgGLgGLgLg.', '..gGlgGglGg..', '.ORRRRRRRRRO.',
            '.OrHHppppdoO.', '..OHpppppdO..', '..OhpppppdO..', '...OhppddO...', '....OOOOO....']
    cmap = {'O': OUT, 'R': POT[4], 'r': POT[5], 'H': POT[4], 'h': POT[3], 'p': POT[3], 'd': POT[1], 'o': POT[2],
            'g': IVY[3], 'G': IVY[4], 'L': IVY[5], 'l': IVY[2], 'f': flower, 'F': CREAM}
    img = blank(13, 11)
    for yy, row in enumerate(rows):
        for xx, ch in enumerate(row):
            if ch in cmap:
                put(img, xx, yy, cmap[ch])
    return img, (6, 10)


def flag_img(col, p0, p1):
    """一段三角旗：一條微微下垂的繩子＋中間一面小三角旗（左上半亮一點）。"""
    x0, y0 = p0
    x1, y1 = p1
    xa, xb = int(math.floor(min(x0, x1))) - 1, int(math.ceil(max(x0, x1))) + 1
    ya, yb = int(math.floor(min(y0, y1))) - 1, int(math.ceil(max(y0, y1))) + 11
    img = blank(xb - xa + 1, yb - ya + 1)
    n = int(abs(x1 - x0)) + 1
    pts = []
    for k in range(n + 1):
        t = k / max(1, n)
        sag = 3.0 * 4 * t * (1 - t)
        x = int(round(x0 + (x1 - x0) * t)) - xa
        y = int(round(y0 + (y1 - y0) * t + sag)) - ya
        put(img, x, y, hexrgb('#8a6a5a'))
        pts.append((x, y))
    mx, my = pts[len(pts) // 2]
    light = np.minimum(col.astype(int) + 40, 255).astype(np.uint8)
    for r in range(6):
        for c in range(-3 + r // 2, 4 - (r + 1) // 2):
            put(img, mx + c, my + 1 + r, light if (c < 0 and r < 3) else col)
    return img, (xa, ya)


def cat_img():
    rows = ['.O....O...', 'OkO..OkO..', 'OkkOOkkO..', 'OkkkkkkO..', 'OkYkkYkO..', 'OkkkpkkO..', '.OkkkkO...',
            'OkkkkkkO..', 'OkKkkkkO..', 'OkKkkkkOO.', 'OkkkkkkkkO', '.OOOOOOOkO', '........O.']
    cmap = {'O': OUT, 'k': hexrgb('#3a3048'), 'K': hexrgb('#5a4a70'), 'Y': hexrgb('#ffe066'), 'p': FL_PINK}
    img = blank(10, len(rows))
    for yy, row in enumerate(rows):
        for xx, ch in enumerate(row):
            if ch in cmap:
                put(img, xx, yy, cmap[ch])
    return img, (4, len(rows) - 2)


def smoke_img():
    img = blank(26, 22)
    yy, xx = np.mgrid[0:22, 0:26]
    for (cx, cy, r) in ((8, 17, 4.5), (13, 11, 5.5), (18, 5, 4.0)):
        m = ((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r
        lv = -((xx - cx) * -0.6 + (yy - cy) * -0.8) / r
        col = np.where((lv > 0.3)[..., None], hexrgb('#ffffff'), np.where((lv > -0.3)[..., None], hexrgb('#eeeaf4'), hexrgb('#cfcade')))
        img[m, :3] = col[m]
        img[m, 3] = 255
    o = outline_mask(img[..., 3] > 0)
    img[o, :3] = hexrgb('#a9a2bc')
    return img, (8, 21)


def stamp(sc, sprite, x0, y0, allowed):
    h, w = sprite.shape[:2]
    xa, ya = max(0, x0), max(0, y0)
    xb, yb = min(LW, x0 + w), min(LH, y0 + h)
    if xa >= xb or ya >= yb:
        return
    sub = sprite[ya - y0:yb - y0, xa - x0:xb - x0]
    m = (sub[..., 3] > 0) & allowed[ya:yb, xa:xb]
    for c in range(3):
        sc.rgba[ya:yb, xa:xb, c] = np.where(m, sub[..., c], sc.rgba[ya:yb, xa:xb, c])


LEAF_SHAPES = [['.ab', 'abc', 'bc.'], ['ab.', 'bcc', '.c.'], ['.a.', 'abb', 'bcc', '.c.']]


def ivy_leaf(seed, dark, rose=False):
    if rose and hs(seed, 4) > 0.55:
        img = blank(3, 3)
        for (x, y) in ((1, 0), (0, 1), (2, 1), (1, 2)):
            put(img, x, y, BLOSSOM[3])
        put(img, 1, 1, BLOSSOM[1])
        put(img, 0, 0, BLOSSOM[4])
        return img
    sh = LEAF_SHAPES[int(hs(seed) * 3) % 3]
    img = blank(3, len(sh))
    base = 4 - dark
    cm = {'a': IVY[min(6, base + 1)], 'b': IVY[base], 'c': IVY[max(1, base - 1)]}
    for yy, row in enumerate(sh):
        for xx, ch in enumerate(row):
            if ch in cm:
                put(img, xx, yy, cm[ch])
    return img


def vine_patch(sc, names, face, line_u, line_v, along0, along1, z_top, seed, max_len=24, density=1.0, rose=False, up=False):
    """長春藤（從牆頂垂下）或爬牆玫瑰（up=True：從牆腳往上爬）。"""
    allowed = sc.mask(*names)
    n = max(2, int((along1 - along0) * 5 * density))
    for k in range(n):
        al = along0 + (along1 - along0) * (k + hs(seed, k)) / n
        length = (0.35 + 0.65 * hs(seed, k, 1)) * max_len * (0.5 + 0.5 * math.sin((al - along0) / max(0.01, along1 - along0) * math.pi))
        zz = z_top + 2 if not up else 0.0
        x = 0.0
        steps = 0
        while (zz > z_top - length * S) if not up else (zz < length * S):
            u, v = (line_u, al) if face == '+u' else (al, line_v)
            lx, ly = g2lp(u, v, zz)
            leaf = ivy_leaf(seed * 1000 + k * 37 + steps, 1 if face == '+u' else 0, rose=rose)
            stamp(sc, leaf, round(lx - 1 + x), round(ly - 1), allowed)
            step = 3.0 + 2.0 * hs(seed, k, steps)
            zz = zz - step if not up else zz + step
            x += (hs(seed, k, steps, 3) - 0.5) * 1.2
            x = max(-2.0, min(2.0, x))
            steps += 1


# ═══════════════════════════════ 地面 ═══════════════════════════════

def floor_mask(u, v):
    return (u >= -0.5) & (u <= COLS - 0.5) & (v >= -0.5) & (v <= ROWS - 0.5)


POND = (-6.4, 6.5, 2.4, 1.6)      # 池塘：中心 u,v、半徑（格）


def ground():
    u, v = UG, VG
    floor = floor_mask(u, v)
    X = II.astype(float)
    Y = JJ.astype(float) * 2.0
    rgb = np.zeros((LH, LW, 3), dtype=np.uint8)

    n = fbm(X, Y, 46, 101, 3)
    val = 3.4 + (n - 0.5) * 2.8
    rgb[:] = MEADOW[np.clip(np.floor(val), 0, len(MEADOW) - 1).astype(int)]

    pu, pv, pru, prv = POND
    wob = (fbm(X, Y, 8, 107, 2) - 0.5) * 0.18
    pd = ((u - pu) / pru) ** 2 + ((v - pv) / prv) ** 2 + wob
    pond = pd < 1.0
    rim = (pd >= 1.0) & (pd < 1.22)
    wt = np.where(pd < 0.35, 1, np.where(pd < 0.75, 2, 3))
    wt = np.where(pd > 0.88, 4, wt)
    ripple = pond & (JJ % 4 == 0) & (h32(II // 5, JJ // 4, 108) > 0.82) & (pd < 0.8)
    wt = np.where(ripple, 5, wt)
    rgb = np.where(pond[..., None], WATER[wt], rgb)
    rgb = np.where(rim[..., None], np.where((h32(II // 2, JJ // 2, 109) > 0.5)[..., None], STONE[6], STONE[4]), rgb)

    pdist = path_dist(u, v)
    wob2 = (fbm(X, Y, 12, 103, 2) - 0.5) * 0.16
    path = (pdist + wob2 < PATH_HALF) & ~floor & ~pond
    pn = fbm(X, Y, 10, 104, 2)
    pi = np.clip(np.floor(4.4 + (pn - 0.5) * 2.0), 0, 7).astype(int)
    pi = np.where(h32(II, JJ, 105) > 0.95, pi + 2, pi)
    pi = np.where(h32(II, JJ, 106) < 0.04, pi - 2, pi)
    rgb = np.where(path[..., None], PATH[np.clip(pi, 0, 7)], rgb)
    pe = path & ~(np.roll(path, 1, 0) & np.roll(path, -1, 0) & np.roll(path, 1, 1) & np.roll(path, -1, 1))
    rgb = np.where(pe[..., None], PATH[1], rgb)

    n1 = fbm(X, Y, 50, 201, 3)
    n2 = fbm(X, Y, 18, 202, 2)
    val = 5.0 + (n1 - 0.5) * 2.6 + (n2 - 0.5) * 1.0
    chk = ((np.floor(u + 0.5) + np.floor(v + 0.5)) % 2) == 0
    val = val + np.where(chk, 0.22, -0.08)
    sh_w = 0.55 + (fbm(X, Y, 9, 205, 2) - 0.5) * 0.2
    val = np.where(floor & (u < -0.5 + sh_w), val - 1.5, val)
    val = np.where(floor & ((v < -0.5 + 0.18) | (u < -0.5 + 0.18)), val - 0.8, val)
    gi = np.clip(np.floor(val), 1, len(GRASS) - 2).astype(int)
    rgb = np.where(floor[..., None], GRASS[gi], rgb)
    return rgb, gi, floor, path, pond


def tuft_sprite(seed, tone, pal):
    img = blank(5, 4)
    blades = [(0, 2), (1, 3), (2, 4), (3, 3), (4, 2)]
    for i, (x, hh) in enumerate(blades):
        if not (hs(seed, i) > 0.3 or i == 2):
            continue
        hh = min(4, max(2, hh - (1 if hs(seed, x, 7) > 0.6 else 0)))
        for d in range(hh):
            t = tone + (1 if d == hh - 1 else 0) - (1 if d == 0 else 0)
            put(img, x, 3 - d, pal[int(np.clip(t, 0, len(pal) - 1))])
    return img


def clover_sprite(tone):
    rows = ['.a.a.', 'abcba', '.bcb.', '..d..']
    img = blank(5, 4)
    cm = {'a': GRASS[min(8, tone + 2)], 'b': GRASS[min(8, tone + 1)], 'c': GRASS[tone], 'd': GRASS[max(0, tone - 1)]}
    for yy, row in enumerate(rows):
        for xx, ch in enumerate(row):
            if ch in cm:
                put(img, xx, yy, cm[ch])
    return img


def flower_sprite(kind):
    pet, cen = [(FL_WHITE, FL_YEL), (FL_VIO, FL_YEL), (FL_PINK, CREAM), (FL_BLUE, CREAM), (FL_YEL, FL_ORANGE), (FL_RED, FL_YEL)][kind % 6]
    img = blank(3, 4)
    for (x, y) in ((1, 0), (0, 1), (2, 1), (1, 2)):
        put(img, x, y, pet)
    put(img, 1, 1, cen)
    put(img, 1, 3, GRASS[3])
    return img


def mushroom_sprite():
    rows = ['.OOOO.', 'ORrRRO', 'OrRwRO', '.OOOO.', '..Ow..', '..OO..']
    cmap = {'O': OUT, 'R': hexrgb('#e8505a'), 'r': hexrgb('#ff8a8a'), 'w': CREAM}
    img = blank(6, 6)
    for yy, row in enumerate(rows):
        for xx, ch in enumerate(row):
            if ch in cmap:
                put(img, xx, yy, cmap[ch])
    return img


def lily_sprite(seed):
    img = blank(7, 4)
    for y in range(4):
        for x in range(7):
            if ((x - 3) / 3.4) ** 2 + ((y - 1.5) / 1.9) ** 2 <= 1 and not (x == 3 and y < 2):
                put(img, x, y, IVY[4] if y < 2 else IVY[3])
    if hs(seed) > 0.4:
        put(img, 3, 0, FL_PINK)
        put(img, 2, 0, BLOSSOM[4])
    return img


def decorate_ground(sc, gi, floor, path, pond):
    ground_vis = sc.ids == 0
    on_floor = ground_vis & floor
    on_meadow = ground_vis & ~floor & ~path & ~pond
    on_pond = ground_vis & pond
    for j in range(0, LH, 3):
        for i in range(0, LW, 3):
            hsh = hs(i, j, 300)
            if floor[j, i]:
                if hsh > 0.87:
                    t = int(gi[j, i])
                    spr = tuft_sprite(int(hsh * 1e6), min(7, t + 1), GRASS) if hs(i, j, 301) > 0.35 else tuft_sprite(int(hsh * 1e6), max(1, t - 2), GRASS)
                    stamp(sc, spr, i - 2 + int(hs(i, j, 302) * 3), j - 3, on_floor)
                elif hsh < 0.025:
                    stamp(sc, clover_sprite(min(6, int(gi[j, i]) + 1)), i - 2, j - 2, on_floor)
            elif on_meadow[j, i] and hsh > 0.9:
                stamp(sc, tuft_sprite(int(hsh * 1e6), 5 if hs(i, j, 303) > 0.4 else 2, MEADOW), i - 2, j - 3, on_meadow)
    for k in range(90):
        gu = -0.2 + hs(k, 400) * (COLS - 0.6)
        gv = -0.2 + hs(k, 401) * (ROWS - 0.6)
        if PLOT_BLOCK[0] - 0.7 < gu < PLOT_BLOCK[0] + 3.7 and PLOT_BLOCK[1] - 0.7 < gv < PLOT_BLOCK[1] + 2.7:
            continue
        lx, ly = g2lp(gu, gv)
        kind = int(hs(k, 403) * 1000)
        for c in range(3 + int(hs(k, 402) * 4)):
            stamp(sc, flower_sprite(kind), round(lx + (hs(k, c, 404) - 0.5) * 10), round(ly + (hs(k, c, 405) - 0.5) * 5), on_floor)
    for k in range(80):
        gu = -12 + hs(k, 410) * (COLS + 24)
        gv = -12 + hs(k, 411) * (ROWS + 24)
        lx, ly = g2lp(gu, gv)
        kind = int(hs(k, 412) * 1000)
        for c in range(8 + int(hs(k, 413) * 10)):
            stamp(sc, flower_sprite(kind + (1 if c % 5 == 0 else 0)), round(lx + (hs(k, c, 414) - 0.5) * 22),
                  round(ly + (hs(k, c, 415) - 0.5) * 10), on_meadow)
    pu, pv, pru, prv = POND
    for k in range(6):
        lx, ly = g2lp(pu + (hs(k, 420) - 0.5) * pru * 1.2, pv + (hs(k, 421) - 0.5) * prv * 1.2)
        stamp(sc, lily_sprite(k), round(lx), round(ly), on_pond)
    du_ = DOOR[0]
    for k, (su, sv, scl) in enumerate([(du_ + 0.02, 0.78, 1.0), (du_ - 0.14, 1.62, 0.92), (du_ + 0.08, 2.45, 1.0),
                                       (du_ - 0.4, 3.3, 0.86), (du_ - 1.0, 4.1, 0.9)]):
        lx, ly = g2lp(su, sv)
        rx, ry = 8.5 * scl, 4.3 * scl
        x0, x1 = int(lx - rx - 3), int(lx + rx + 4)
        y0, y1 = int(ly - ry - 3), int(ly + ry + 4)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d = ((xx - lx) / rx) ** 2 + ((yy - ly) / ry) ** 2
        wob = 1.0 + 0.12 * np.sin(np.arctan2(yy - ly, xx - lx) * 3 + k)
        m = d <= wob
        allowed = sc.ids[y0:y1, x0:x1] == 0
        sub = sc.rgba[y0:y1, x0:x1]
        shadow = ~m & ((((xx - lx - 1) / rx) ** 2 + ((yy - ly - 1.2) / ry) ** 2) <= wob) & allowed
        sub[shadow, :3] = GRASS[2]
        mm = m & allowed
        nx = (xx - lx) / rx
        ny = (yy - ly) / ry
        lv = -nx * 0.6 - ny * 0.8
        tone = 5 + np.where(lv > 0.35, 1, 0) - np.where(lv < -0.45, 1, 0)
        tone = np.where(h32(xx, yy, 430 + k) > 0.93, tone + 1, tone)
        col = STONE_B[np.clip(tone, 0, 8)]
        ring = mm & (d > wob * 0.72)
        col = np.where((ring & (lv < 0))[..., None], STONE_B[3], col)
        col = np.where((ring & (lv >= 0))[..., None], STONE_B[7], col)
        sub[mm, :3] = col[mm]
        sub[mm & outline_mask(m) & (lv < 0.3), :3] = STONE_B[2]
    # 門前的愛心地墊
    lx, ly = g2lp(DOOR[0], 0.05)
    mat = blank(19, 8)
    for y in range(8):
        for x in range(19):
            if abs(x - 9) / 9.5 + abs(y - 3.5) / 4.0 <= 1.0:
                put(mat, x, y, DOORC[4] if (x + y) % 2 else DOORC[3])
    mat[outline_mask(mat[..., 3] > 0), :3] = DOORC[1]
    for (x, y) in ((8, 3), (10, 3), (8, 2), (10, 2), (9, 3), (9, 4)):
        put(mat, x, y, FL_PINK)
    stamp(sc, mat, round(lx - 9), round(ly - 4), ground_vis)


# ═══════════════════════════════ 場景 ═══════════════════════════════

def back_rects():
    """後景層物件的地面範圍（格座標 u0,u1,v0,v1）—— 路人站在它們後面就排到後景層下面。"""
    T, P = WALL_T, PILLAR
    c0 = -0.5 - T / 2
    return [
        (-0.5 - T - CAP_O, -0.5 + CAP_O, -0.5 - T, ROWS - 0.5),
        (-0.5 - T, COTTAGE_U0, -0.5 - T - CAP_O, -0.5 + CAP_O),
        (c0 - P - 0.06, c0 + P + 0.06, c0 - P - 0.06, c0 + P + 0.06),
        (c0 - P - 0.06, c0 + P + 0.06, ROWS - 0.5 + T / 2 - P - 0.06, ROWS - 0.5 + T / 2 + P + 0.06),
        (COLS - 0.5 + T / 2 - P - 0.06, COLS - 0.5 + T / 2 + P + 0.06, c0 - P - 0.06, c0 + P + 0.06),
        (COTTAGE_U0 - 0.25, COLS - 0.5 + 0.3, COTTAGE_VB - 0.35, -0.15),
    ]


def ray_hits(u, v, rects):
    for (u0, u1, v0, v1) in rects:
        lo = max(0.0, u0 - u, v0 - v)
        hi = min(u1 - u, v1 - v)
        if lo <= hi:
            return True
    return False


def scenery_layer(u, v):
    """
    牆外的樹叢該在哪一層：從它腳底往遠離玩家的方向（u-t, v-t）看，碰到小路＝它在小路前面 —
    再往玩家那邊（u+t, v+t）會碰到後景層物件＝它夾在小路與後牆之間 → back；否則 → fore。
    沒碰到小路＝它在小路後面 → bg（路人走在它前面）。
    """
    ts = np.arange(0.0, 9.0, 0.1)
    d = path_dist(u - ts, v - ts)
    if not (d < PATH_HALF + 0.4).any():
        return 'bg'
    return 'back' if ray_hits(u, v, back_rects()) else 'fore'


def box_flowers(name, u0, u1, v, z, seed):
    x0, y0 = g2lp(u0, v, z)
    x1, y1 = g2lp(u1, v, z)
    ox = int(math.floor(min(x0, x1))) - 2
    oy = int(math.floor(min(y0, y1))) - 9
    w = int(abs(x1 - x0)) + 6
    hgt = int(abs(y1 - y0)) + 14
    img = blank(w, hgt)
    n = int(abs(x1 - x0)) + 1
    for k in range(n):
        t = k / max(1, n - 1)
        xx = int(round(x0 + (x1 - x0) * t)) - ox
        yb = int(round(y0 + (y1 - y0) * t)) - oy
        hh = 2 + int(hs(k, seed) * 4)
        for d in range(hh):
            put(img, xx, yb - d, IVY[3 + (d % 2) - (1 if k % 3 == 0 else 0)])
        if hs(k, seed + 4) > 0.75:
            put(img, xx, yb + 1, IVY[3])
            put(img, xx, yb + 2, IVY[2])
        if hs(k, seed + 1) > 0.4:
            fc = [FL_PINK, FL_RED, FL_YEL, FL_WHITE, FL_VIO][int(hs(k, seed + 2) * 5) % 5]
            put(img, xx, yb - hh, fc)
            if hs(k, seed + 3) > 0.5:
                put(img, xx, yb - hh - 1, CREAM)
    return Billboard(name, img, ox, oy, ((u0 + u1) / 2, v + 0.01), 'back')


def build_scene():
    prims = []
    bills = []
    T, P = WALL_T, PILLAR
    c0 = -0.5 - T / 2

    def garden_wall(name, u0, u1, v0, v1, base, cap, fence, seed, layer, along_u, line):
        prims.append(box(name, u0, u1, v0, v1, 0, base, wall_body_mat(base, seed), layer))
        if along_u:
            cu0, cu1, cv0, cv1 = u0, u1, v0 - CAP_O, v1 + CAP_O
        else:
            cu0, cu1, cv0, cv1 = u0 - CAP_O, u1 + CAP_O, v0, v1
        prims.append(box(name + '-cap', cu0, cu1, cv0, cv1, base, base + cap, cap_mat(seed + 100), layer))
        z0 = base + cap
        a0, a1 = (u0, u1) if along_u else (v0, v1)
        a0 += 0.1
        a1 -= 0.1
        n = int((a1 - a0) / 0.3)
        hp = int(fence / S)
        pk = picket_img(hp)
        prev = None
        for k in range(n + 1):
            a = a0 + (a1 - a0) * k / max(1, n)
            uu, vv = (a, line) if along_u else (line, a)
            bills.append(bill_from(f'{name}-pk{k}', pk, (2, hp + 1), uu, vv, z0, layer))
            if prev is not None:
                pu, pv = prev
                for rz in (z0 + fence * 0.3, z0 + fence * 0.7):
                    img, (xa, ya) = rail_img(g2lp(pu, pv, rz), g2lp(uu, vv, rz))
                    bills.append(Billboard(f'{name}-rail{k}-{int(rz)}', img, xa, ya,
                                           ((pu + uu) / 2 - 0.02, (pv + vv) / 2 - 0.02), layer))
            prev = (uu, vv)

    def pillar(name, cu, cv, H, seed, layer, top='lamp'):
        prims.append(box(name, cu - P, cu + P, cv - P, cv + P, 0, H, wall_body_mat(H, seed), layer))
        prims.append(box(name + '-cap', cu - P - 0.06, cu + P + 0.06, cv - P - 0.06, cv + P + 0.06, H, H + 8,
                         cap_mat(seed + 100), layer))
        img, foot = lantern_img() if top == 'lamp' else ball_img()
        bills.append(bill_from(name + '-top', img, foot, cu, cv, H + 8, layer))

    BH = BASE_H + CAP_H + FENCE_H
    garden_wall('wall-back-left', -0.5 - T, -0.5, -0.5 + P - 0.05, ROWS - 0.5 - P + 0.05, BASE_H, CAP_H, FENCE_H, 1,
                'back', False, c0)
    garden_wall('wall-back-right', -0.5 + P - 0.05, COTTAGE_U0, -0.5 - T, -0.5, BASE_H, CAP_H, FENCE_H, 2,
                'back', True, c0)
    PH = BH + 4
    pillar('pillar-top', c0, c0, PH, 3, 'back')
    pillar('pillar-left', c0, ROWS - 0.5 + T / 2, PH, 4, 'back')
    pillar('pillar-right', COLS - 0.5 + T / 2, c0, PH, 5, 'back')
    garden_wall('wall-front-left', -0.5 - T / 2 + P - 0.05, COLS - 0.5 + T / 2 - P + 0.05, ROWS - 0.5, ROWS - 0.5 + T,
                FRONT_BASE_H, FRONT_CAP_H, FRONT_FENCE_H, 6, 'front', True, ROWS - 0.5 + T / 2)
    garden_wall('wall-front-right', COLS - 0.5, COLS - 0.5 + T, -0.5 - T / 2 + P - 0.05, ROWS - 0.5 + T / 2 - P + 0.05,
                FRONT_BASE_H, FRONT_CAP_H, FRONT_FENCE_H, 7, 'front', False, COLS - 0.5 + T / 2)
    pillar('pillar-bottom', COLS - 0.5 + T / 2, ROWS - 0.5 + T / 2, FRONT_BASE_H + FRONT_CAP_H + FRONT_FENCE_H + 4, 8,
           'front', top='ball')

    # 三角旗：左後牆的柵欄頂上掛一串
    zt = BH + 2
    for k in range(14):
        a = 0.3 + k * (ROWS - 1.6) / 14
        b = 0.3 + (k + 1) * (ROWS - 1.6) / 14
        img, (xa, ya) = flag_img(FLAGS[k % len(FLAGS)], g2lp(c0, a, zt), g2lp(c0, b, zt))
        bills.append(Billboard(f'flag-{k}', img, xa, ya, (c0 + 0.03, (a + b) / 2 + 0.03), 'back'))

    # ── 小屋 ──
    HC = COTTAGE_H
    vB = COTTAGE_VB
    prims.append(box('cottage', COTTAGE_U0, COLS - 0.5, vB, -0.5, 0, HC, cottage_mat, 'back'))
    prims.append(Prim('gable', [
        ((1, 0, 0), COLS - 0.5, '+u'), ((-1, 0, 0), -COTTAGE_U0, '-u'),
        ((0, 1, 0), -0.5, '+v'), ((0, -1, 0), -vB, '-v'),
        ((0, ROOF_S, 1), HC + ROOF_S * -0.5, 'top'),
        ((0, -ROOF_S, 1), HC - ROOF_S * vB, 'top2'),
        ((0, 0, -1), -(HC - 1), 'bot'),
    ], cottage_mat, 'back'))
    vE, vBe = ROOF_VE, vB - 0.35
    vR = (vE + vBe) / 2
    ua, ub = COTTAGE_U0 - 0.25, COLS - 0.5 + 0.3
    prims.append(Prim('roof-front', [
        ((1, 0, 0), ub, '+u'), ((-1, 0, 0), -ua, '-u'),
        ((0, 1, 0), vE, '+v'), ((0, -1, 0), -vR, '-v'),
        ((0, ROOF_S, 1), HC + ROOF_S * vE, 'top'),
        ((0, -ROOF_S, -1), -(HC + ROOF_S * vE - ROOF_TH), 'bot'),
    ], thatch_mat, 'back'))
    prims.append(Prim('roof-back', [
        ((1, 0, 0), ub, '+u'), ((-1, 0, 0), -ua, '-u'),
        ((0, 1, 0), vR, '+v'), ((0, -1, 0), -vBe, '-v'),
        ((0, -ROOF_S, 1), HC - ROOF_S * vBe, 'top'),
        ((0, ROOF_S, -1), -(HC - ROOF_S * vBe - ROOF_TH), 'bot'),
    ], thatch_mat, 'back'))
    # 歪歪的煙囪：三段，一段比一段往右偏
    cu0, cv0 = 13.6, -1.3
    zc = HC + 60
    for k, (du, hh) in enumerate(((0.0, 70), (0.08, 40), (0.16, 34))):
        prims.append(box(f'chimney-{k}', cu0 + du, cu0 + du + 0.55, cv0 - 0.55 + du * 0.3, cv0 + du * 0.3,
                         HC if k == 0 else zc, zc + hh, chimney_mat, 'back'))
        zc += hh
    prims.append(box('chimney-cap', cu0 + 0.1, cu0 + 0.79, cv0 - 0.56, cv0 + 0.11, zc, zc + 8, stone_box_mat(83), 'back'))
    sm, sf = smoke_img()
    bills.append(bill_from('smoke', sm, sf, cu0 + 0.45, cv0 - 0.25, zc + 14, 'back'))
    prims.append(box('step', DOOR[0] - 0.75, DOOR[0] + 0.75, -0.5, -0.24, 0, 8, stone_box_mat(84), 'back'))
    for k, (wc, ww, z0, _z1) in enumerate(COT_WINDOWS):
        prims.append(box(f'winbox-{k}', wc - ww - 0.08, wc + ww + 0.08, -0.5, -0.36, z0 - 22, z0 - 8, wood_box_mat(5), 'back'))
        bills.append(box_flowers(f'flowers-{k}', wc - ww - 0.06, wc + ww + 0.06, -0.43, z0 - 8, 41 + k))
    ci, cf = cat_img()
    bills.append(bill_from('cat', ci, cf, COT_WINDOWS[0][0] + 0.3, -0.42, COT_WINDOWS[0][2] - 8, 'back'))
    prims.append(box('downspout', COLS - 0.88, COLS - 0.78, -0.5, -0.42, 40, HC + 4, metal_mat, 'back'))
    for k, du in enumerate((-0.95, 0.95)):
        prims.append(box(f'sconce-{k}', DOOR[0] + du - 0.04, DOOR[0] + du + 0.04, -0.5, -0.38, 96, 100, metal_mat, 'back'))
        li, lf = lantern_img()
        bills.append(bill_from(f'lamp-door-{k}', li, lf, DOOR[0] + du, -0.4, 78, 'back'))
    bills.append(bill_from('pot-r1', *pot_img(FL_YEL), 2.2, c0, BH - 4, 'back'))
    bills.append(bill_from('pot-r2', *pot_img(FL_PINK), 5.6, c0, BH - 4, 'back'))

    # ── 外面：散開的圓樹（有的開花、有的結果）＋灌木；避開小路、池塘、花園、小屋 ──
    kinds = ['green', 'pink', 'apple', 'white', 'green', 'orange', 'pink', 'green']
    n = 0
    for gu in np.arange(-14.0, COLS + 14.0, 2.4):
        for gv in np.arange(-14.0, ROWS + 14.0, 2.4):
            u = float(gu + (hs(float(gu), float(gv), 500) - 0.5) * 1.6)
            v = float(gv + (hs(float(gu), float(gv), 501) - 0.5) * 1.6)
            if -1.0 < u < COLS + 0.4 and -1.0 < v < ROWS + 0.4:
                continue
            if COTTAGE_U0 - 0.8 < u < COLS + 0.8 and COTTAGE_VB - 0.9 < v < 0:
                continue
            if float(path_dist(np.array(u), np.array(v))) < PATH_HALF + 0.75:
                continue
            pu, pv, pru, prv = POND
            if ((u - pu) / (pru + 0.9)) ** 2 + ((v - pv) / (prv + 0.9)) ** 2 < 1:
                continue
            x, y = g2w(u, v)
            if not (-IMG_W / 2 - 80 < x < IMG_W / 2 + 80 and -IMG_H / 2 - 30 < y < IMG_H / 2 + 240):
                continue
            hsh = hs(u, v, 502)
            if hsh < 0.2:
                continue
            layer = scenery_layer(u, v)
            near_garden = (-2.6 < u < COLS + 2.0 and -2.6 < v < ROWS + 2.0)
            if hsh < 0.5 or near_garden:
                img, foot = bush_img(10 + int(hs(u, v, 503) * 5), 600 + n,
                                     flowers=[FL_PINK, FL_WHITE, FL_YEL, None][n % 4], berries=(n % 5 == 2))
            else:
                img, foot = make_tree(20 + int(hs(u, v, 504) * 8), 700 + n, kinds[n % len(kinds)], trunk_h=9)
            bills.append(bill_from(f'tree-{n}', img, foot, u, v, 0.0, layer))
            n += 1
    return prims, bills


def decorate(sc, gi, floor, path, pond):
    T = WALL_T
    decorate_ground(sc, gi, floor, path, pond)
    wl = ['wall-back-left', 'wall-back-left-cap']
    wr = ['wall-back-right', 'wall-back-right-cap']
    for a0, a1, s in ((0.6, 1.8, 1), (4.2, 5.6, 2), (8.4, 9.6, 3)):
        vine_patch(sc, wl, '+u', -0.5, None, a0, a1, BASE_H + CAP_H - 2, s, max_len=12)
    for a0, a1, s in ((0.9, 2.0, 5), (4.0, 5.2, 6)):
        vine_patch(sc, wr, '+v', None, -0.5, a0, a1, BASE_H + CAP_H - 2, s, max_len=12)
    for a0, a1, s in ((1.0, 2.4, 21), (7.0, 8.4, 22), (12.0, 13.2, 23)):
        vine_patch(sc, ['wall-front-left', 'wall-front-left-cap'], '+v', None, ROWS - 0.5 + T, a0, a1,
                   FRONT_BASE_H + FRONT_CAP_H - 2, s, max_len=8)
    for a0, a1, s in ((2.0, 3.2, 24), (7.2, 8.6, 25)):
        vine_patch(sc, ['wall-front-right', 'wall-front-right-cap'], '+u', COLS - 0.5 + T, None, a0, a1,
                   FRONT_BASE_H + FRONT_CAP_H - 2, s, max_len=8)
    for a0, a1, s in ((DOOR[0] - 1.0, DOOR[0] - 0.74, 31), (DOOR[0] + 0.74, DOOR[0] + 1.0, 32),
                      (COTTAGE_U0 + 0.05, COTTAGE_U0 + 0.6, 33)):
        vine_patch(sc, ['cottage'], '+v', None, -0.5, a0, a1, 0, s, max_len=60, density=2.2, rose=True, up=True)
    allowed = sc.mask('wall-back-left', 'wall-back-right', 'cottage', 'pillar-top', 'pillar-left', 'pillar-right') | (sc.ids == 0)
    for k in range(220):
        t = hs(k, 900)
        u, v = (-0.5, -0.5 + t * ROWS) if k % 2 == 0 else (-0.5 + t * COLS, -0.5)
        lx, ly = g2lp(u, v)
        stamp(sc, tuft_sprite(k, 5 if k % 3 else 3, GRASS), round(lx - 2), round(ly - 3), allowed)
    # 後牆腳一排小花（花圃擺上去會蓋掉，沒關係）
    on_floor = (sc.ids == 0) & floor
    for k in range(60):
        t = hs(k, 920)
        u, v = (-0.3, -0.2 + t * (ROWS - 0.6)) if k % 2 == 0 else (-0.2 + t * (COTTAGE_U0 - 0.4), -0.3)
        lx, ly = g2lp(u, v)
        kind = int(hs(k, 921) * 6)
        for c in range(3):
            stamp(sc, flower_sprite(kind), round(lx + (hs(k, c, 922) - 0.5) * 8), round(ly + (hs(k, c, 923) - 0.5) * 3), on_floor)
    meadow = (sc.ids == 0) & ~floor & ~path & ~pond
    for k in range(30):
        u = -12 + hs(k, 910) * (COLS + 24)
        v = -12 + hs(k, 911) * (ROWS + 24)
        lx, ly = g2lp(u, v)
        for c in range(1 + int(hs(k, 912) * 3)):
            stamp(sc, mushroom_sprite(), round(lx + c * 5), round(ly + (c % 2) * 2), meadow)


def lantern_glow(rgba, spots):
    for (u, v, z) in spots:
        lx, ly = g2lp(u, v, z)
        ly -= 5
        x0, x1 = int(lx - 18), int(lx + 19)
        y0, y1 = int(ly - 18), int(ly + 19)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d = np.sqrt((xx - lx) ** 2 + ((yy - ly) * 1.15) ** 2)
        sub = rgba[y0:y1, x0:x1]
        for rad, amt in ((14, 0.05), (9, 0.08), (5, 0.1)):
            m = (d < rad) & (sub[..., 3] > 0)
            c = sub[m, :3].astype(float)
            sub[m, :3] = np.clip(c * (1 - amt) + np.array([255, 224, 150]) * amt + 4, 0, 255).astype(np.uint8)


def shadows_on_ground(rgb, bills):
    """樹叢在草地上的柔和影子（往右下偏一點的扁橢圓）。"""
    for b in bills:
        if not b.name.startswith('tree-'):
            continue
        u, v = b.base
        lx, ly = g2lp(u, v)
        w = b.rgba.shape[1]
        rx, ry = w * 0.36, w * 0.13
        x0, x1 = max(0, int(lx - rx - 2)), min(LW, int(lx + rx + 6))
        y0, y1 = max(0, int(ly - ry - 2)), min(LH, int(ly + ry + 4))
        if x0 >= x1 or y0 >= y1:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        m = ((xx - lx - 3) / rx) ** 2 + ((yy - ly) / ry) ** 2 <= 1
        sub = rgb[y0:y1, x0:x1]
        sub[m] = (sub[m].astype(int) * np.array([0.8, 0.86, 0.84])).astype(np.uint8)


# ═══════════════════════════════ 圍牆內的擺設（各自一張圖）═══════════════════════════════

def soft_shadow(img, cx, cy, rx, ry):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    m = (((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1) & (img[..., 3] == 0)
    img[m, :3] = np.array([40, 80, 50], dtype=np.uint8)
    img[m, 3] = 70


def decor_tree():
    img, foot = make_tree(30, 777, 'pink', trunk_h=16)
    pad = blank(img.shape[1], img.shape[0] + 4)
    pad[:img.shape[0]] = img
    soft_shadow(pad, foot[0] + 3, foot[1], img.shape[1] * 0.33, 5)
    return pad, foot


def decor_barrel():
    w, h = 30, 38
    img = blank(w, h)
    cx = 14.5
    rx, ry = 12.0, 5.5
    top_y, bot_y = 7.0, 29.0
    yy, xx = np.mgrid[0:h, 0:w]
    dx = (xx - cx) / rx
    bulge = 1.0 + 0.06 * np.sin(np.clip((yy - top_y) / (bot_y - top_y), 0, 1) * math.pi)
    dxb = (xx - cx) / (rx * bulge)
    body = (np.abs(dxb) <= 1.0) & (yy >= top_y) & (yy <= bot_y + ry * np.sqrt(np.clip(1 - dx * dx, 0, 1)))
    topm = (dx ** 2 + ((yy - top_y) / ry) ** 2) <= 1.0
    m = body | topm
    st = np.floor((xx - (cx - rx)) / 3.0)
    lv = -dxb
    t = 5 + np.where(lv > 0.4, 2, np.where(lv > -0.1, 1, 0)) - np.where(lv < -0.6, 1, 0)
    t = np.where(h32(st, 3) > 0.7, t - 1, t)
    t = np.where(((xx - (cx - rx)) % 3.0) < 0.8, t - 2, t)
    col = PLANK[np.clip(t, 0, 8)]
    hoop = body & ((np.abs(yy - (top_y + 5)) < 1.0) | (np.abs(yy - (bot_y - 3)) < 1.0))
    col = np.where(hoop[..., None], METAL[np.where(lv > 0.5, 6, np.where(lv > 0, 4, 3))], col)
    img[m, :3] = col[m]
    img[m, 3] = 255
    inner = ((dx * 1.12) ** 2 + ((yy - top_y) / (ry * 0.8)) ** 2) <= 1.0
    img[topm & ~inner, :3] = PLANK[8]
    water = topm & inner
    wt = np.where((yy - top_y) < -1, 2, 3)
    wt = np.where(((xx - cx + 3) ** 2 / 9 + (yy - top_y + 1) ** 2) < 1.2, 5, wt)
    wt = np.where(((xx - cx - 4) ** 2 / 4 + (yy - top_y - 1) ** 2) < 0.8, 6, wt)
    img[water, :3] = WATER[wt][water]
    img[outline_mask(m), :3] = OUT
    soft_shadow(img, cx + 2, bot_y + ry - 0.5, 14, 3.2)
    return img, (cx, bot_y + ry - 0.5)


def _line(x0, y0, x1, y1):
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    return [(round(x0 + (x1 - x0) * k / n), round(y0 + (y1 - y0) * k / n)) for k in range(n + 1)]


def decor_bench():
    """長椅（靠左後牆、面朝花園）：木板椅背＋座位＋鐵腳；座位上一顆愛心靠墊。"""
    w, h = 42, 32
    img = blank(w, h)
    for k in range(3):
        for (x, y) in _line(6, 9 + k * 3, 30, -3 + k * 3 + 4):
            put(img, x, y, PLANK[7 - k])
            put(img, x, y + 1, PLANK[5 - k])
    for k in range(3):
        for (x, y) in _line(9 + k * 2, 19 + k, 33 + k * 2, 7 + k):
            put(img, x, y, PLANK[8 - k])
            put(img, x, y + 1, PLANK[6 - k])
    for (x, y) in ((10, 22), (34, 10), (14, 24), (38, 12)):
        for d in range(7):
            put(img, x, y + d, METAL[2] if d % 2 else METAL[3])
    for (x, y) in ((20, 12), (21, 11), (23, 11), (24, 12), (21, 12), (22, 12), (23, 12), (21, 13), (22, 13), (23, 13), (22, 14)):
        put(img, x, y, FL_PINK)
    put(img, 21, 11, BLOSSOM[4])
    add_outline(img)
    soft_shadow(img, 24, 27, 17, 3.5)
    return img, (24, 25)


def decor_scarecrow():
    """戴女巫帽的稻草人：十字木架、麻布頭縫一個笑臉、補丁衣服、袖口與下擺冒稻草。"""
    w, h = 34, 56
    img = blank(w, h)
    cx = 17
    for y in range(22, 54):
        put(img, cx, y, TRUNK[3])
        put(img, cx + 1, y, TRUNK[2])
    for x in range(4, 31):
        put(img, x, 26, TRUNK[4])
        put(img, x, 27, TRUNK[2])
    shaded_ellipse(img, cx + 0.5, 32, 7, 7.5, ramp('#2d4c8a', '#3d64a8', '#5a84c6', '#7ea4dc', '#a8c6ee', '#d0e2f8'), 2, spec=False)
    for (x, y) in ((cx - 3, 31), (cx - 2, 31), (cx - 3, 32), (cx - 2, 32)):
        put(img, x, y, hexrgb('#f2a24a'))
    for (x, y) in ((cx + 3, 35), (cx + 4, 35), (cx + 3, 36)):
        put(img, x, y, FL_PINK)
    for (x, y) in ((4, 25), (3, 27), (4, 28), (30, 25), (31, 27), (30, 28), (cx - 3, 40), (cx, 41), (cx + 3, 40), (cx + 1, 42)):
        put(img, x, y, THATCH[7])
        put(img, x, y + 1, THATCH[5])
    shaded_ellipse(img, cx + 0.5, 20, 5.2, 4.8, ramp('#8a6a3e', '#aa8650', '#c8a466', '#dcbd80', '#ecd6a0', '#f8ecc8'), 3, spec=False)
    put(img, cx - 1, 19, OUT)
    put(img, cx + 2, 19, OUT)
    for x in range(cx - 1, cx + 3):
        put(img, x, 22, OUT)
    put(img, cx - 2, 21, OUT)
    put(img, cx + 3, 21, OUT)
    put(img, cx - 3, 20, BLOSSOM[3])
    put(img, cx + 4, 20, BLOSSOM[3])
    hat = ramp('#2e2048', '#46306a', '#62468e', '#8064b0', '#a084cc', '#c4aae6')
    for x in range(cx - 8, cx + 10):
        put(img, x, 15, hat[2])
        put(img, x, 16, hat[1])
    for r in range(12):
        half = max(0, 5 - r // 2)
        for x in range(cx - half + r // 3, cx + half + 1 + r // 3):
            put(img, x, 14 - r, hat[3] if x < cx + r // 3 else hat[2])
    for x in range(cx - 4, cx + 6):
        put(img, x, 13, hexrgb('#f0c050'))
    put(img, cx + 4, 2, hexrgb('#fff0a0'))
    add_outline(img)
    soft_shadow(img, cx + 3, 53, 10, 2.4)
    return img, (cx, 53)


def decor_birdbath():
    """小鳥浴盆：石柱＋淺盆＋水面反光，盆緣站一隻小藍鳥。"""
    w, h = 30, 34
    img = blank(w, h)
    cx = 14.5
    for y in range(14, 29):
        hw = 2.5 if 16 < y < 26 else 4
        for x in range(int(cx - hw), int(cx + hw) + 1):
            put(img, x, y, STONE_B[7] if x < cx - 1 else (STONE_B[5] if x < cx + 1 else STONE_B[3]))
    for x in range(int(cx - 6), int(cx + 7)):
        for y in (28, 29, 30):
            put(img, x, y, STONE_B[6] if y == 28 else STONE_B[4])
    shaded_ellipse(img, cx, 12, 12, 4.6, STONE_B, 5, spec=False)
    yy, xx = np.mgrid[0:h, 0:w]
    water = ((xx - cx) / 9.5) ** 2 + ((yy - 11.4) / 3.2) ** 2 <= 1
    img[water, :3] = WATER[np.where((xx - cx) < -2, 4, 3)][water]
    img[water & ((xx - cx + 3) ** 2 / 4 + (yy - 11) ** 2 < 0.8), :3] = WATER[6]
    for (x, y, c) in ((cx + 6, 6, FL_BLUE), (cx + 7, 6, FL_BLUE), (cx + 8, 6, FL_BLUE), (cx + 6, 7, FL_BLUE), (cx + 7, 7, CREAM),
                      (cx + 8, 7, FL_BLUE), (cx + 9, 6, hexrgb('#ffb040')), (cx + 7, 5, FL_BLUE), (cx + 5, 7, hexrgb('#4a78d0'))):
        put(img, int(x), y, c)
    put(img, int(cx + 7), 5, OUT)
    add_outline(img)
    soft_shadow(img, cx + 2, 31, 9, 2.4)
    return img, (cx, 30)


def decor_pumpkins():
    """南瓜堆：一大兩小（瓣紋、綠蒂、葉子）。"""
    w, h = 40, 26
    img = blank(w, h)
    yy, xx = np.mgrid[0:h, 0:w]
    for (cx, cy, rx, ry) in ((12, 17, 7, 5.5), (28, 18, 6, 4.6), (20, 13, 9, 7)):
        m = shaded_ellipse(img, cx, cy, rx, ry, PUMPKIN, 2, spec=True)
        q = (xx - cx) / rx * 2.2
        rib = m & (np.abs(q - np.round(q)) < 0.12) & (np.abs(xx - cx) > 0.5)
        img[rib, :3] = PUMPKIN[1]
        put(img, cx, int(cy - ry), IVY[2])
        put(img, cx + 1, int(cy - ry) - 1, IVY[3])
    for (x, y) in ((4, 20), (5, 19), (6, 20), (34, 21), (35, 20), (36, 21), (33, 22)):
        put(img, x, y, IVY[4])
    add_outline(img)
    soft_shadow(img, 22, 23, 18, 3.0)
    return img, (20, 21)


DECOR = [
    ('tree', (0, 0), decor_tree, (14.0, 7.0)),
    ('barrel', (COLS - 1, 0), decor_barrel, (18.0, 9.0)),
    ('bench', (0, 6), decor_bench, (26.0, 11.0)),
    ('scarecrow', (2, ROWS - 4), decor_scarecrow, (12.0, 7.0)),
    ('birdbath', (COLS - 3, 4), decor_birdbath, (16.0, 8.0)),
    ('pumpkins', (4, 0), decor_pumpkins, (24.0, 11.0)),
]


def upscale(rgba, k=S):
    return np.repeat(np.repeat(rgba, k, axis=0), k, axis=1)


def decor_sprites():
    out = []
    for name, (gx, gy), fn, (hx, hy) in DECOR:
        img, (fx, fy) = fn()
        big = upscale(img)
        foot_x = (fx + 0.5) * S
        foot_y = (fy + 0.5) * S
        cx, cy = g2w(gx, gy)
        Wp, Hp = big.shape[1], big.shape[0]
        ox = Wp / 2.0 - foot_x
        oy = foot_y - Hp / 2.0
        center = (math.floor(cx + ox - Wp / 2.0 + 0.5) + Wp / 2.0,
                  math.floor(cy + oy - Hp / 2.0 + 0.5) + Hp / 2.0)
        out.append((name, (gx, gy), big, center, int(round(-cy)), (cx, cy, hx, hy)))
    return out


# ═══════════════════════════════ 幾何資料（給 C#）═══════════════════════════════

def walk_poly():
    lo = -0.5 + WALK_INSET
    hx = COLS - 0.5 - WALK_INSET
    hy = ROWS - 0.5 - WALK_INSET
    return [g2w(lo, lo), g2w(hx, lo), g2w(hx, hy), g2w(lo, hy)]


def floor_poly():
    return [g2w(-0.5, -0.5), g2w(COLS - 0.5, -0.5), g2w(COLS - 0.5, ROWS - 0.5), g2w(-0.5, ROWS - 0.5)]


def f(x):
    s = ('%.2f' % x).rstrip('0').rstrip('.')
    if s in ('-0', ''):
        s = '0'
    return s + 'f'


def write_cs(path, decors, layers):
    wp = walk_poly()
    fp = floor_poly()
    door = cell_center(*DOOR)
    spawn = cell_center(*SPAWN)
    nodes, edges, exits = folk_graph()
    L = []
    A = L.append
    A('// <auto-generated>')
    A('// ⚠️ 自動產生，不要手改。產生器：tools/gen_garden_art.py')
    A('//    重跑：python tools/gen_garden_art.py（再跑 python tools/check_garden_walk.py 驗可走範圍、可達性與路人路網）')
    A('//    要改格子大小、格數、門、裝飾、小路、圖層：改產生器，不是改這個檔。')
    A('// </auto-generated>')
    A('using UnityEngine;')
    A('')
    A('namespace WitchShop.Data')
    A('{')
    A('    /// <summary>後花園圍牆內的一件裝飾：一張圖、佔一格（不能擺花圃）、一個橢圓障礙。</summary>')
    A('    public readonly struct GardenDecor')
    A('    {')
    A('        public readonly string Name, Sprite;')
    A('        public readonly int Gx, Gy;')
    A('        /// <summary>圖片中心的世界座標（樞紐在中心、PPU 1、不縮放）。</summary>')
    A('        public readonly float X, Y;')
    A('        public readonly int Order;')
    A('        /// <summary>障礙：軸對齊橢圓（中心、半徑；世界座標）。</summary>')
    A('        public readonly float Cx, Cy, Hx, Hy;')
    A('')
    A('        public GardenDecor(string name, string sprite, int gx, int gy, float x, float y, int order,')
    A('                           float cx, float cy, float hx, float hy)')
    A('        {')
    A('            Name = name; Sprite = sprite; Gx = gx; Gy = gy; X = x; Y = y; Order = order;')
    A('            Cx = cx; Cy = cy; Hx = hx; Hy = hy;')
    A('        }')
    A('    }')
    A('')
    A('    /// <summary>底圖之上的一張圖層（裁成最小矩形）：圖、中心的世界座標、排序。</summary>')
    A('    public readonly struct GardenLayer')
    A('    {')
    A('        public readonly string Sprite;')
    A('        public readonly float X, Y;')
    A('        public readonly int Order;')
    A('        public GardenLayer(string sprite, float x, float y, int order) { Sprite = sprite; X = x; Y = y; Order = order; }')
    A('    }')
    A('')
    A('    /// <summary>')
    A('    /// 8-bit 後花園（GardenRoom.UsePixelGarden）的幾何：等距格盤、可走範圍、門、出生點、裝飾、圖層、路人路網、畫布大小。')
    A('    /// 格 (gx,gy) 中心 = ( OriginX + (gx-gy)*HalfW , OriginY - (gx+gy)*HalfH )；gx 往畫面右下、gy 往左下。')
    A('    /// 底圖 rooms/garden8 是 ImgW×ImgH、中心＝世界原點、排序 BgOrder；其上是 Layers（後景／前牆／最前景）。')
    A('    /// </summary>')
    A('    public static class GardenRoomData')
    A('    {')
    A('        public const string Background = "rooms/garden8";')
    A(f'        public const float ImgW = {f(IMG_W)}, ImgH = {f(IMG_H)};')
    A('')
    A('        /// <summary>')
    A('        /// 排序：底圖 BgOrder；後景層（後牆、小屋）BackOrder —— 影子層 -8500 在它下面、女巫與花圃（-y）在它上面；')
    A('        /// 走在後景層物件後面的路人 FolkBackOrder（被蓋住）；前牆 FrontOrder（蓋住走到牆後的女巫）；')
    A('        /// 其他路人 FolkFrontOrder - y（在前牆之上）；小路外側的樹叢 ForeOrder（在路人前面）。')
    A('        /// </summary>')
    A(f'        public const int BgOrder = {BG_ORDER}, BackOrder = {BACK_ORDER}, FolkBackOrder = {FOLK_BACK_ORDER};')
    A(f'        public const int FrontOrder = {FRONT_ORDER}, FolkFrontOrder = {FOLK_FRONT_ORDER}, ForeOrder = {FORE_ORDER};')
    A('')
    A('        public static readonly GardenLayer[] Layers =')
    A('        {')
    for sp, (x, y), order in layers:
        A(f'            new GardenLayer("{sp}", {f(x)}, {f(y)}, {order}),')
    A('        };')
    A('')
    A('        /// <summary>一格的寬高（等距 2:1）與一半。花圃的土壤磚頂面菱形就是一格。</summary>')
    A(f'        public const float TileW = {f(2 * HALF_W)}, TileH = {f(2 * HALF_H)};')
    A(f'        public const float HalfW = {f(HALF_W)}, HalfH = {f(HALF_H)};')
    A(f'        public const int Cols = {COLS}, Rows = {ROWS};')
    A(f'        public const float OriginX = {f(OX)}, OriginY = {f(OY)};')
    A('')
    A(f'        /// <summary>可走範圍＝地板菱形每邊內縮幾格（{WALK_INSET} 格 ≈ {WALK_INSET * PERP:.1f}px，腳底圓半徑 {PLAYER_R:g} 不壓到牆）。</summary>')
    A(f'        public const float WalkInset = {f(WALK_INSET)};')
    A('        /// <summary>女巫的可走範圍（凸多邊形，順時針：上、右、下、左）。給 Obstacles.Begin 的 walkPolygon。</summary>')
    A('        public static readonly Vector2[] Walk =')
    A('        {')
    A('            ' + ', '.join(f'new({f(x)}, {f(y)})' for x, y in wp) + ',')
    A('        };')
    A('        /// <summary>地板（草地）菱形的四個角（順時針：上、右、下、左）。</summary>')
    A('        public static readonly Vector2[] Floor =')
    A('        {')
    A('            ' + ', '.join(f'new({f(x)}, {f(y)})' for x, y in fp) + ',')
    A('        };')
    A('')
    A('        /// <summary>回店裡的門對著的那一格；門的觸發點＝這格中心（DoorAt）。</summary>')
    A(f'        public const int DoorGx = {DOOR[0]}, DoorGy = {DOOR[1]};')
    A('        /// <summary>門前那一格（跟門那格一樣不能擺花圃，免得把門口堵住）。</summary>')
    A(f'        public const int DoorFrontGx = {DOOR_FRONT[0]}, DoorFrontGy = {DOOR_FRONT[1]};')
    A(f'        public static readonly Vector2 DoorAt = new({f(door[0])}, {f(door[1])});')
    A('        /// <summary>門的自動觸發距離（提示與 E 也收成一樣大，跟店裡的門一樣，免得跟旁邊花圃的 E 打架）。</summary>')
    A(f'        public const float DoorRange = {f(DOOR_RANGE)};')
    A(f'        /// <summary>從店裡進來的落腳點（格 {SPAWN[0]},{SPAWN[1]} 中心；門前的踏腳石上）。</summary>')
    A(f'        public static readonly Vector2 Spawn = new({f(spawn[0])}, {f(spawn[1])});')
    A('')
    A('        /// <summary>預設花圃排法的左上角：第 i 塊 ＝ (PlotBlockGx + i%4, PlotBlockGy + i/4)，同舊的 4×3 排法。</summary>')
    A(f'        public const int PlotBlockGx = {PLOT_BLOCK[0]}, PlotBlockGy = {PLOT_BLOCK[1]};')
    A('')
    A('        public static readonly GardenDecor[] Decor =')
    A('        {')
    for name, (gx, gy), _img, (x, y), order, (cx, cy, hx, hy) in decors:
        A(f'            new GardenDecor("{name}", "rooms/garden8-{name}", {gx}, {gy}, {f(x)}, {f(y)}, {order}, '
          f'{f(cx)}, {f(cy)}, {f(hx)}, {f(hy)}),')
    A('        };')
    A('')
    A('        // ── 路人（GardenFolk）──')
    A('        /// <summary>白天同時幾位路人（晚上剩兩位）。</summary>')
    A(f'        public const int FolkCount = {FOLK_COUNT};')
    A('        /// <summary>小路上的節點（世界座標）。圍牆外繞一圈（含小屋後面）＋幾條走出畫面的岔路。</summary>')
    A('        public static readonly Vector2[] FolkNodes =')
    A('        {')
    for k in range(0, len(nodes), 4):
        A('            ' + ', '.join(f'new({f(g2w(*p)[0])}, {f(g2w(*p)[1])})' for p in nodes[k:k + 4]) + ',')
    A('        };')
    A('        /// <summary>相連的節點（兩兩一組：a, b）。</summary>')
    A('        public static readonly int[] FolkEdges =')
    A('        {')
    for k in range(0, len(edges), 8):
        A('            ' + ', '.join(f'{a}, {b}' for a, b in edges[k:k + 8]) + ',')
    A('        };')
    A('        /// <summary>畫面外的節點（走到這裡＝離開畫面，待一會兒再回來）。</summary>')
    A('        public static readonly int[] FolkExits = { ' + ', '.join(str(e) for e in exits) + ' };')
    A('        /// <summary>')
    A('        /// 後景層物件的地面範圍（格座標，每 4 個一組：u0, u1, v0, v1）。路人腳底沿視線往玩家那邊（u+t, v+t）走')
    A('        /// 碰到其中一塊＝他在那東西後面 → 排 FolkBackOrder（被後景層蓋住）。')
    A('        /// </summary>')
    A('        public static readonly float[] BackRects =')
    A('        {')
    for r in back_rects():
        A('            ' + ', '.join(f(x) for x in r) + ',')
    A('        };')
    A('')
    A('        /// <summary>格子中心的世界座標。</summary>')
    A('        public static Vector2 CellCenter(int gx, int gy) =>')
    A('            new(OriginX + (gx - gy) * HalfW, OriginY - (gx + gy) * HalfH);')
    A('')
    A('        /// <summary>世界座標 → 連續格座標（格子中心是整數、磚緣是 ±0.5）。</summary>')
    A('        public static Vector2 ToGrid(float x, float y)')
    A('        {')
    A('            float a = (x - OriginX) / HalfW, b = (OriginY - y) / HalfH;')
    A('            return new Vector2((a + b) * 0.5f, (b - a) * 0.5f);')
    A('        }')
    A('')
    A('        /// <summary>世界座標 → 最近的那一格（可能在格盤外，用 InGrid 驗）。</summary>')
    A('        public static Cell WorldToCell(float x, float y)')
    A('        {')
    A('            var g = ToGrid(x, y);')
    A('            return new Cell(Mathf.RoundToInt(g.x), Mathf.RoundToInt(g.y));')
    A('        }')
    A('')
    A('        public static bool InGrid(int gx, int gy) => gx >= 0 && gx < Cols && gy >= 0 && gy < Rows;')
    A('')
    A('        /// <summary>這一點（世界座標）在不在後景層物件（後牆、小屋）後面：沿視線往玩家那邊走會不會碰到 BackRects。</summary>')
    A('        public static bool BehindBack(Vector2 p)')
    A('        {')
    A('            var g = ToGrid(p.x, p.y);')
    A('            for (int i = 0; i + 3 < BackRects.Length; i += 4)')
    A('            {')
    A('                float lo = Mathf.Max(0f, Mathf.Max(BackRects[i] - g.x, BackRects[i + 2] - g.y));')
    A('                float hi = Mathf.Min(BackRects[i + 1] - g.x, BackRects[i + 3] - g.y);')
    A('                if (lo <= hi) return true;')
    A('            }')
    A('            return false;')
    A('        }')
    A('    }')
    A('}')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(L) + '\n')


# ═══════════════════════════════ 主程式 ═══════════════════════════════

LAYER_DEFS = [('back', 'garden8-back', BACK_ORDER), ('front', 'garden8-front', FRONT_ORDER), ('fore', 'garden8-fore', FORE_ORDER)]


def crop_layer(full, mask):
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return None
    x0, x1 = xs.min(), xs.max() + 1
    y0, y1 = ys.min(), ys.max() + 1
    if (x1 - x0) % 2:
        x1 += 1
    if (y1 - y0) % 2:
        y1 += 1
    out = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
    m = mask[y0:y1, x0:x1]
    out[m] = full[y0:y1, x0:x1][m]
    return out, ((x0 + x1) / 2.0 - IMG_W / 2.0, IMG_H / 2.0 - (y0 + y1) / 2.0)


def build():
    prims, bills = build_scene()
    g, gi, floor, path, pond = ground()
    shadows_on_ground(g, bills)
    sc = Scene(prims, bills, g)
    decorate(sc, gi, floor, path, pond)
    sc.outline()
    c0 = -0.5 - WALL_T / 2
    PH = BASE_H + CAP_H + FENCE_H + 4 + 8
    lantern_glow(sc.rgba, [(c0, c0, PH), (c0, ROWS - 0.5 + WALL_T / 2, PH), (COLS - 0.5 + WALL_T / 2, c0, PH),
                           (DOOR[0] - 0.95, -0.4, 78), (DOOR[0] + 0.95, -0.4, 78)])
    full = upscale(sc.rgba)[:IMG_H, :IMG_W]
    layers = []
    for lname, fname, order in LAYER_DEFS:
        m = upscale(sc.layer_mask(lname)[..., None].astype(np.uint8))[:IMG_H, :IMG_W, 0] > 0
        r = crop_layer(full, m)
        if r is not None:
            layers.append((fname, r[0], r[1], order))
    return Image.fromarray(full), layers, decor_sprites()


def save_all(outdir_rooms, cs_path):
    bg, layers, decors = build()
    os.makedirs(outdir_rooms, exist_ok=True)
    bg.save(os.path.join(outdir_rooms, 'garden8.png'))
    for fname, img, _c, _o in layers:
        Image.fromarray(img).save(os.path.join(outdir_rooms, fname + '.png'))
    for name, _cell, big, _c, _o, _e in decors:
        Image.fromarray(big).save(os.path.join(outdir_rooms, f'garden8-{name}.png'))
    write_cs(cs_path, decors, [('rooms/' + fn, c, o) for fn, _i, c, o in layers])
    return bg, layers, decors


# ═══════════════════════════════ 預覽 ═══════════════════════════════

def witch_frame():
    p = os.path.join(RES, 'witch8', 'base.png')
    if not os.path.exists(p):
        return None
    sh = Image.open(p).convert('RGBA')
    cw, ch = sh.width // 8, sh.height // 25
    return sh.crop((0, 0, cw, ch)).resize((round(cw * 1.6), round(ch * 1.6)), Image.NEAREST)


def villager_frame(name, row=0):
    """villagers8/<name>.png：4 欄 × 3 列（下／側／上），鞋底在格子底邊往上 3px；×1.1。"""
    p = os.path.join(RES, 'villagers8', name + '.png')
    if not os.path.exists(p):
        return None
    sh = Image.open(p).convert('RGBA')
    cw, ch = sh.width // 4, sh.height // 3
    fr = sh.crop((0, row * ch, cw, row * ch + ch))
    return fr.resize((round(cw * 1.1), round(ch * 1.1)), Image.NEAREST)


def plot_images():
    g8 = os.path.join(RES, 'garden8')
    soil = wet = None
    p = os.path.join(g8, 'soil-dry.png')
    if os.path.exists(p):
        im = Image.open(p).convert('RGBA')
        if im.width == 2 * HALF_W:
            soil = im
            pw = os.path.join(g8, 'soil-wet.png')
            wet = Image.open(pw).convert('RGBA') if os.path.exists(pw) else im
    if soil is None:
        W, H = int(2 * HALF_W), int(2 * HALF_H)
        soil = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        px = soil.load()
        for yy in range(H):
            for xx in range(W):
                d = abs(xx - (W - 1) / 2) / (W / 2) + abs(yy - (H - 1) / 2) / (H / 2)
                if d <= 1.0:
                    px[xx, yy] = (60, 40, 32, 255) if d > 0.9 else (122, 86, 62, 255)
        wet = soil
    flowers = []
    for art in ('lavender', 'foxglove', 'starbell'):
        fp = os.path.join(g8, art + '.png')
        if os.path.exists(fp):
            sh = Image.open(fp).convert('RGBA')
            cw, chh = sh.width // 6, sh.height // 2
            flowers.append([sh.crop((c * cw, 0, c * cw + cw, chh)) for c in range(6)])
    return soil, wet, flowers


VILLAGER_SPOTS = [('rabbit', (3.0, P_FRONT_V)), ('fox', (P_FRONT_U, 7.0)), ('frog', (P_BACK, 5.0)),
                  ('hedgehog', (4.0, P_BACK)), ('deer', (11.0, P_COT)), ('mage', (P_BACK, P_FRONT_V - 0.6)),
                  ('fairy', (P_FRONT_U, P_COT + 1.0)), ('traveler', (9.0, P_FRONT_V))]


def preview(bg, layers, decors, outdir):
    os.makedirs(outdir, exist_ok=True)
    W, H = IMG_W, IMG_H

    def wp(x, y):
        return x + W / 2.0, H / 2.0 - y

    comp = bg.copy().convert('RGBA')
    items = []
    soil, wet, flowers = plot_images()
    for i in range(12):
        gx, gy = PLOT_BLOCK[0] + i % 4, PLOT_BLOCK[1] + i // 4
        x, y = cell_center(gx, gy)
        items.append((int(round(-y)) - 1, wet if i % 3 == 0 else soil, (x, y)))
        if flowers and i % 4 != 3:
            fr = flowers[i % len(flowers)][min(4, 1 + i % 5)]
            items.append((int(round(-y)), fr, (x, y - 6 + fr.height / 2)))
    for name, _cell, big, (cx, cy), order, _e in decors:
        items.append((order, Image.fromarray(big), (cx, cy)))
    wf = witch_frame()
    if wf is not None:
        for (gx, gy) in [SPAWN, (3.5, 9.0), (8, ROWS - 0.5 - WALK_INSET), (COLS - 0.5 - WALK_INSET, 7.5),
                         (-0.5 + WALK_INSET, 3), (5.0, 2.0), (13.0, 9.5)]:
            x, y = g2w(gx, gy)
            items.append((int(round(-y)), wf, (x, y + wf.height / 2)))
    for name, (u, v) in VILLAGER_SPOTS:
        fr = villager_frame(name)
        if fr is None:
            continue
        x, y = g2w(u, v)
        order = FOLK_BACK_ORDER if ray_hits(u, v, back_rects()) else FOLK_FRONT_ORDER + int(round(-y))
        items.append((order, fr, (x, y - 3 * 1.1 + fr.height / 2)))
    for fname, img, (cx, cy), order in layers:
        items.append((order, Image.fromarray(img), (cx, cy)))
    items.sort(key=lambda t: t[0])
    for _o, im, (x, y) in items:
        px, py = wp(x, y)
        comp.alpha_composite(im, (int(round(px - im.width / 2)), int(round(py - im.height / 2))))
    outs = []
    p = os.path.join(outdir, 'full_composite.png')
    comp.save(p)
    outs.append(p)
    for nm, (gx, gy) in (('view_spawn', SPAWN), ('view_far_corner', (0.5, ROWS - 1.0)), ('view_bottom', (COLS - 1.5, ROWS - 1.5))):
        x, y = g2w(gx, gy)
        vw, vh = 1138, 640
        cxw = min(max(x, -W / 2 + vw / 2), W / 2 - vw / 2)
        cyw = min(max(y, -H / 2 + vh / 2), H / 2 - vh / 2)
        px, py = wp(cxw, cyw)
        p = os.path.join(outdir, nm + '.png')
        comp.crop((int(px - vw / 2), int(py - vh / 2), int(px + vw / 2), int(py + vh / 2))).save(p)
        outs.append(p)

    from PIL import ImageDraw
    nodes, edges, exits = folk_graph()
    dbg = comp.copy()
    dr = ImageDraw.Draw(dbg, 'RGBA')
    for gx in range(COLS):
        for gy in range(ROWS):
            pts = [wp(*g2w(gx - 0.5, gy - 0.5)), wp(*g2w(gx + 0.5, gy - 0.5)),
                   wp(*g2w(gx + 0.5, gy + 0.5)), wp(*g2w(gx - 0.5, gy + 0.5))]
            dr.polygon(pts, outline=(255, 255, 255, 60))
    dr.polygon([wp(*q) for q in floor_poly()], outline=(255, 255, 0, 255))
    dr.polygon([wp(*q) for q in walk_poly()], outline=(0, 200, 255, 255))
    for name, _cell, _big, _c, _o, (cx, cy, hx, hy) in decors:
        dr.ellipse([wp(cx - hx - PLAYER_R, cy + hy + PLAYER_R), wp(cx + hx + PLAYER_R, cy - hy - PLAYER_R)], outline=(255, 80, 80, 255))
    for a, b in edges:
        dr.line([wp(*g2w(*nodes[a])), wp(*g2w(*nodes[b]))], fill=(255, 0, 200, 255), width=3)
    for i, p_ in enumerate(nodes):
        x, y = wp(*g2w(*p_))
        c = (255, 120, 0, 255) if i in exits else (255, 0, 200, 255)
        dr.ellipse([x - 5, y - 5, x + 5, y + 5], fill=c)
    for r in back_rects():
        u0, u1, v0, v1 = r
        dr.polygon([wp(*g2w(u0, v0)), wp(*g2w(u1, v0)), wp(*g2w(u1, v1)), wp(*g2w(u0, v1))], outline=(80, 80, 255, 255))
    dx, dy = wp(*cell_center(*DOOR))
    dr.ellipse([dx - DOOR_RANGE, dy - DOOR_RANGE, dx + DOOR_RANGE, dy + DOOR_RANGE], outline=(255, 0, 255, 255))
    p = os.path.join(outdir, 'debug_graph.png')
    dbg.save(p)
    outs.append(p)

    def zoom(nm, cx, cy, w, h):
        px, py = wp(cx, cy)
        p = os.path.join(outdir, nm + '.png')
        comp.crop((int(px - w / 2), int(py - h / 2), int(px + w / 2), int(py + h / 2))).resize((w * 2, h * 2), Image.NEAREST).save(p)
        outs.append(p)

    zoom('zoom_door', *g2w(DOOR[0], -0.5, 100), 440, 300)
    zoom('zoom_back_fence', *g2w(-0.5, 5.0, 40), 440, 280)
    zoom('zoom_tree_bench', *g2w(0.5, 3.0, 40), 440, 300)
    zoom('zoom_front', *g2w(4.0, ROWS - 0.5, 30), 440, 280)
    zoom('zoom_corner_decor', *g2w(COLS - 2.0, ROWS - 2.0, 30), 440, 300)
    zoom('zoom_outside', *g2w(-5.5, 7.0, 30), 440, 300)
    zoom('zoom_roof', *g2w(12.5, -2.0, 220), 440, 300)
    return outs


def main():
    args = sys.argv[1:]
    if '--out' in args:
        d = args[args.index('--out') + 1]
        bg, layers, decors = save_all(os.path.join(d, 'rooms'), os.path.join(d, 'GardenRoomData.cs'))
        print('輸出 →', d)
    else:
        bg, layers, decors = save_all(os.path.join(RES, 'rooms'), CS_OUT)
        print('寫入 Assets/Resources/rooms/garden8*.png 與', os.path.relpath(CS_OUT, ROOT))
    for fname, img, c, o in layers:
        print(f'  圖層 {fname}: {img.shape[1]}×{img.shape[0]} 中心 ({c[0]:g},{c[1]:g}) 排序 {o}')
    if '--preview' in args:
        d = args[args.index('--preview') + 1]
        for p in preview(bg, layers, decors, d):
            print('預覽 →', p)


if __name__ == '__main__':
    main()
