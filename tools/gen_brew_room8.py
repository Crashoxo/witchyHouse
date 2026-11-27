# -*- coding: utf-8 -*-
"""
魔女的房間（藥水室 brew）—— 細畫像素版（標竿：女巫走路圖 witch8）。程式畫、固定結果、可重跑。

    python tools/gen_brew_room8.py                  # 畫圖 → Assets/Resources/rooms/brew8/*.png
    python tools/gen_brew_room8.py --out DIR        # 圖寫到 DIR（不碰專案；調圖時用）
    python tools/gen_brew_room8.py --preview DIR    # 另外輸出預覽：日／夜合成（含女巫）、新舊對照、
                                                    #   床／鍋爐／壁爐／書櫃角落 2 倍放大、鍋爐與爐火 GIF、碰撞對位圖

── 跟舊版（tools/gen_brew_room.py，SVG）的關係 ─────────────────────────────
  · **幾何一律不動**：每張圖的檔名、畫布大小、樞紐、幀數都跟 rooms/brew/ 一模一樣，
    所以 Data/BrewRoomLayout.cs（舊產生器寫的）的落腳點、落地範圍、可走多邊形、互動點、排序全部照用。
    這支**只讀** BrewRoomLayout.cs 與 rooms/brew/*.png 的尺寸，不寫任何 C#。
  · 每件家具在自己的區域座標裡畫（落地範圍 u∈[0,du]、v∈[0,dv]、z 往上），區域原點在圖上的位置
    由樞紐反推：樞紐＝落地範圍中心 → 原點 ＝ 樞紐 −((du−dv)/2, (du+dv)/4)。
  · 貓（cat-0/1/2）不畫：房間裡的活貓另外做。壁爐前的圓毯上畫了一個空的貓窩（CAT_BED_UV）。
  · 開關在 Core/BrewRoom.UsePixelRoom：開著時 GameArt 先讀 rooms/brew8/，缺圖再退回 rooms/brew/。

── 座標 ─────────────────────────────────────────────────────────
  地板 uv：u 沿「右後牆」往右下、v 沿「左後牆」往左下、z 往上。等距 2:1：
      房間圖 x = OX + u − v，y = OY + (u + v)/2 − z（y 朝下）；世界 x = 房間圖 x − 541、世界 y = 358.5 − 房間圖 y。

── 畫法 ─────────────────────────────────────────────────────────
  · 邏輯像素 ×2（女巫是原生 1px ×1.6），格線對齊整間房的偶數像素（每件圖用自己在房間圖上的左上角對齊），
    少數小細節（玻璃反光、星星閃光）用 ×1 原生像素補。
  · 立體：方塊／圓柱（可挖空成環）／橢球（可切頂）—— 每個邏輯像素打一條等距視線（u,v,z 同步 +t），
    取最靠鏡頭的面；小東西（瓶子、書、藥草、火焰）是「立牌」，一樣進 z-buffer。
  · 光從左上（右後牆的窗）來：頂面最亮、朝左下（+v）的面次之、朝右下（+u）的面最暗；
    每種材質 7～9 階色相偏移色（暗部偏紫、亮部偏暖），邊角有倒角亮線、底部收暗。
  · 外輪廓 #2a1b24（同 witch8／villagers8／garden8）；物件內部的前後交界用「自己顏色的深一階」描（選擇性描邊）。
  · 夜晚：家具在遊戲裡乘 NightTint；房間殼另畫一張 —— 壓暗偏藍紫，但壁爐、蠟燭附近一圈一圈暖光（色階，不是漸層），
    窗外星空與月亮、地上一塊月光。
"""
import math
import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('WITCH_ROOT') or os.path.dirname(HERE)
if not os.path.isdir(os.path.join(ROOT, 'Assets')):
    ROOT = r'D:\Crash\witch-unity'
RES = os.path.join(ROOT, 'Assets', 'Resources')
OLD_DIR = os.path.join(RES, 'rooms', 'brew')
OUT_DIR = os.path.join(RES, 'rooms', 'brew8')
LAYOUT_CS = os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'BrewRoomLayout.cs')

S = 2                                   # 邏輯像素
CANVAS_W, CANVAS_H = 1082, 717
OX, OY = 441, 196
ROOM_U, ROOM_V = 600, 400
WALL_H = 176
WALL_T = 12
RIM = 14
EXIT_UV = (548, 368)
CAT_BED_UV = (503, 98)                  # 貓窩中心（地板 uv）＝世界 (305, -138)，畫在 rug-hearth 上
#   活貓 RoomCat.CatBed 想要 (300, -138)；但貓窩外圈半寬 22px＋描邊，在那裡左緣會超出 rug-hearth 的畫布（差 3～5px），
#   所以取最近、整個放得進畫布的位置：同一高度往右 5px。扶手椅左扶手在 x≥337，貓窩右緣 x≈329，不會被擋。
CAT_BED_R = 15.5                        # 貓窩外圈半徑（uv）：畫面上約 44×22px，剛好裝下 40×20 的睡貓
NIGHT_MUL = (0.56, 0.55, 0.76)          # 跟 BrewRoomLayout.NightTint 一樣
GLOW_COLOR = (255, 196, 120)
GLOW_ALPHA = 0.6


def room_px(u, v, z=0.0):
    return OX + u - v, OY + (u + v) * 0.5 - z


def px_to_world(x, y):
    return x - CANVAS_W / 2, CANVAS_H / 2 - y


def world_to_uv(wx, wy):
    x, y = wx + CANVAS_W / 2, CANVAS_H / 2 - wy
    dx, dy = x - OX, y - OY
    return dy + dx / 2, dy - dx / 2


# ═══════════════════════════════ 色盤 ═══════════════════════════════

def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def ramp(*hs):
    return np.array([hexrgb(h) for h in hs], dtype=np.uint8)


OUTLINE = '#2a1b24'
OUT = np.array(hexrgb(OUTLINE), dtype=np.uint8)

# 家具木（蜂蜜紅棕）
WOOD = ramp('#2c1216', '#43191c', '#5e2422', '#7a3226', '#96442c', '#ae5833', '#c4703e', '#d68c50', '#e6ac6c', '#f2cc96')
# 深木（樑、框）
TIMBER = ramp('#22121a', '#32191e', '#462322', '#5c3028', '#743f2e', '#8c5236', '#a5683f', '#bc8250')
# 地板木（亮一點的蜂蜜色，跟家具分得開）
FLOOR = ramp('#3e2526', '#55332d', '#6c4333', '#82553b', '#966745', '#a97a50', '#ba8c5c', '#c99f6b', '#d8b47f', '#e6ca98')
# 灰泥（暖奶油）
PLASTER = ramp('#5e4552', '#7a5c63', '#967672', '#b09082', '#c6a893', '#d7bea4', '#e5d0b5', '#efe0c8', '#f7eedc', '#fdf8ee')
# 石頭（暖灰、偏紫的暗部）
STONE = ramp('#3a2e3c', '#4f4150', '#665664', '#7e6d77', '#96858a', '#ad9d9c', '#c2b4ae', '#d6cac0', '#e8dfd4')
# 深石（壁爐）
WSTONE = ramp('#4a3436', '#634642', '#7c5a50', '#946e5f', '#ab8470', '#c09a83', '#d2b098', '#e2c6ad', '#efdac5')
DSTONE = ramp('#2a2232', '#3a3042', '#4c4152', '#5f5464', '#746977', '#8a7f8a', '#a2979e', '#bab0b2', '#d2c9c6')
PURPLE = ramp('#1f1430', '#2e1d45', '#40285c', '#543573', '#6a448a', '#8158a3', '#9a71bb', '#b48fd0', '#ceb2e3', '#e6d6f2')
PLUM = ramp('#2c1426', '#431d36', '#5c2848', '#77365a', '#91466c', '#ab5b7e', '#c47592', '#da94a9', '#ecb8c4')
GOLD = ramp('#4a2c14', '#6e4318', '#97621e', '#c08a2c', '#ddb04a', '#f0cf6c', '#fbe79a', '#fff6cc')
BLUE = ramp('#121633', '#1a2148', '#232e62', '#2e3e7e', '#3b519a', '#4e68b4', '#6a85cb', '#90a8de', '#bccdee')
TEAL = ramp('#0f3236', '#164a4a', '#1d6461', '#26807a', '#329c90', '#46b7a4', '#66cfb6', '#92e3cb', '#c4f4e2', '#effff8')
PINK = ramp('#4a1630', '#6e2242', '#953259', '#b84a72', '#d4688c', '#e78ba6', '#f4b0c2', '#fdd5df', '#fff1f4')
ROSE = ramp('#3e1220', '#5a1a2c', '#7a2438', '#9a3044', '#b64252', '#cc5c62', '#de7c78', '#eca296', '#f6c8b8')
IRON = ramp('#100d16', '#19151f', '#221d2a', '#2d2737', '#3a3345', '#4a4256', '#5d5469', '#756b80', '#958aa0', '#bdb3c6')
COPPER = ramp('#3e1a14', '#5c2818', '#7e381e', '#a04c26', '#be6430', '#d6813e', '#e8a258', '#f4c47e', '#fde2b0')
BRASS = ramp('#3c2a12', '#5a3e16', '#7a561c', '#9c7024', '#bc8c30', '#d6aa44', '#e9c662', '#f6e092', '#fff4cc')
LINEN = ramp('#6a5866', '#857077', '#a08a8a', '#b9a49e', '#cfbcb0', '#e0d1c2', '#ede2d4', '#f7efe4', '#fdf9f2', '#ffffff')
LEAF = ramp('#1e3a2c', '#264a32', '#305e3a', '#3c7442', '#4a8a4a', '#5ca052', '#74b45c', '#90c66a', '#b0d87e', '#d0e9a0')
TERRA = ramp('#3e1a16', '#5c2618', '#7e361e', '#a04a28', '#bc6034', '#d27a44', '#e29a5c', '#eebc80', '#f8dcaa')
FIRE = ramp('#7a1e16', '#a82e1a', '#d24a1e', '#ee6e24', '#fb962e', '#ffbb44', '#ffd866', '#fff09a', '#fffbe0')
GLASS = ramp('#2c3a5a', '#3c5478', '#527096', '#6e90b2', '#90b0cc', '#b4cfe2', '#d6e8f2', '#f2fafc')
SKY = ramp('#4f86c6', '#64a0d8', '#7ab6e4', '#96caee', '#b4dcf4', '#d4ecf8', '#f2fafe')
NSKY = ramp('#0c0f26', '#121838', '#19224c', '#222e60', '#2c3c74', '#384c88')
CREAM = np.array(hexrgb('#fff8e6'), np.uint8)
STAR = np.array(hexrgb('#fff3b8'), np.uint8)
BUNT = [ramp(*c) for c in (('#8a2f56', '#d4688c', '#f4b0c2'), ('#97621e', '#ddb04a', '#fbe79a'),
                           ('#1d6461', '#46b7a4', '#92e3cb'), ('#40285c', '#8158a3', '#b48fd0'),
                           ('#2e3e7e', '#6a85cb', '#bccdee'))]

# 光：從左上（右後牆的窗）來
LIGHT = np.array([0.32, 0.62, 1.0])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


# ═══════════════════════════════ 雜湊與雜訊（固定結果）═══════════════════════════════

def h32(*arrs):
    h = np.uint64(1469598103934665603)
    out = np.full(np.broadcast(*[np.asarray(a) for a in arrs]).shape, h, dtype=np.uint64)
    with np.errstate(over='ignore'):
        for a in arrs:
            a = np.asarray(np.floor(np.asarray(a, dtype=np.float64))).astype(np.int64).astype(np.uint64)
            out = (out ^ a) * np.uint64(1099511628211)
            out ^= out >> np.uint64(29)
            out = out * np.uint64(0x9E3779B97F4A7C15)
            out ^= out >> np.uint64(31)
    return (out % np.uint64(1 << 24)).astype(np.float64) / float(1 << 24)


def hs(*v):
    return float(h32(*[np.array(x) for x in v]))


def vnoise(x, y, cell, seed):
    fx = np.asarray(x, dtype=np.float64) / cell
    fy = np.asarray(y, dtype=np.float64) / cell
    x0, y0 = np.floor(fx), np.floor(fy)
    tx, ty = fx - x0, fy - y0
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    a, b = h32(x0, y0, seed), h32(x0 + 1, y0, seed)
    c, d = h32(x0, y0 + 1, seed), h32(x0 + 1, y0 + 1, seed)
    return (a + (b - a) * tx) + ((c + (d - c) * tx) - (a + (b - a) * tx)) * ty


def fbm(x, y, cell, seed, oct=3):
    tot, amp, norm = 0.0, 1.0, 0.0
    for k in range(oct):
        tot = tot + amp * vnoise(x, y, cell / (2 ** k), seed + k * 17)
        norm += amp
        amp *= 0.5
    return tot / norm


BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float64) / 16.0 - 0.47


# ═══════════════════════════════ 配置表（只讀）═══════════════════════════════

def parse_layout():
    """讀 Data/BrewRoomLayout.cs：每件的名字、幀、落腳點、樞紐、排序、uv 盒子、世界矩形、夜晚乘色、碰撞。"""
    src = open(LAYOUT_CS, encoding='utf-8').read()
    pieces = []
    for m in re.finditer(r'new BrewPiece\("([^"]+)", new\[\] \{ ([^}]*) \}, ([^,]+), (null|new\[\] \{[^}]*\}), BrewKind\.(\w+),\s*'
                         r'([^\n]+)\n\s*([^\n]+)\n\s*([^\n]+)\n\s*(true|false),\s*\n\s*BrewShape\.(\w+), ([^\n]+)\),', src):
        name, frames, fps, seq, kind, l1, l2, l3, tint, shape, rest = m.groups()
        fl = lambda s: [float(x.strip().rstrip('f')) for x in s.strip().rstrip(',').split(',')]  # noqa: E731
        a = fl(l1)
        u0, u1, v0, v1 = fl(l2)
        rx0, ry0, rx1, ry1 = fl(l3)
        poly = None
        pm = re.search(r'new Vector2\[\] \{ (.*) \}', rest)
        if pm:
            poly = [tuple(float(t.rstrip('f')) for t in p.split(', ')) for p in re.findall(r'new\(([^)]*)\)', pm.group(1))]
        nums = [float(x.rstrip('f')) for x in re.findall(r'-?[\d.]+f', rest.split('new Vector2')[0])]
        pieces.append(dict(name=name, frames=[f.strip().strip('"') for f in frames.split(',')], fps=float(fps.rstrip('f')),
                           kind=kind, x=a[0], y=a[1], px=a[2], py=a[3], order=int(a[4]),
                           U0=u0, U1=u1, V0=v0, V1=v1, rect=(rx0, ry0, rx1, ry1), tint=tint == 'true',
                           shape=shape, ell=nums[:4] if shape == 'Ellipse' else None, poly=poly))
    walk = [tuple(float(t.rstrip('f')) for t in p.split(', '))
            for p in re.findall(r'new\(([^)]*)\)', re.search(r'Walk = \{([^}]*)\}', src).group(1))]
    glows = [tuple(float(t.rstrip('f')) if t.strip() not in ('true', 'false') else t.strip() == 'true' for t in g.split(', '))
             for g in re.findall(r'new BrewGlow\(([^)]*)\)', src)]
    pts = {}
    for k in ('Bed', 'Wardrobe', 'Chest', 'Cauldron', 'Exit'):
        mm = re.search(k + r'At = new\(([^)]*)\);\s*public const float ' + k + r'Range = ([\d.]+)f', src)
        pts[k.lower()] = (tuple(float(t.rstrip('f')) for t in mm.group(1).split(', ')), float(mm.group(2)))
    spawn = tuple(float(t.rstrip('f')) for t in re.search(r'Spawn = new\(([^)]*)\)', src).group(1).split(', '))
    return dict(pieces=pieces, walk=walk, glows=glows, points=pts, spawn=spawn)


LAYOUT = parse_layout()


def art_name(path):
    return path.split('/')[-1]


def piece_geo(name):
    """一張圖的幾何：畫布大小、區域原點在圖上的位置（全解析度像素）、對齊房間偶數格的偏移。"""
    p = next(q for q in LAYOUT['pieces'] if q['name'] == name or name in [art_name(f) for f in q['frames']])
    im = Image.open(os.path.join(OLD_DIR, art_name(p['frames'][0]) + '.png'))
    W, H = im.size
    du, dv = p['U1'] - p['U0'], p['V1'] - p['V0']
    cx, cy = p['px'], H - p['py']                      # 落地範圍中心在圖上（y 朝下）
    ox, oy = cx - (du - dv) / 2.0, cy - (du + dv) / 4.0
    left = round(p['x'] - p['px'] + CANVAS_W / 2)
    top = round(CANVAS_H / 2 - (p['y'] - p['py']) - H)
    return dict(W=W, H=H, ox=ox, oy=oy, du=du, dv=dv, gx=left % 2, gy=top % 2, piece=p)


# ═══════════════════════════════ 光線求交的小場景 ═══════════════════════════════

F_TOP, F_U, F_V, F_SIDE, F_CAP, F_BB = 0, 1, 2, 3, 4, 5


class Ctx:
    """材質函式拿到的東西（只含這個立體贏了的像素）。"""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def shade(rmp, base, c, k=3.6, extra=0, dither=0.0):
    """依法線受光挑色階：base 是 +v 面附近的色階。"""
    lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
    f = base + (lit - 0.5) * k + extra
    if dither:
        f = f + BAYER4[c.J % 4, c.I % 4] * dither
    return rmp[np.clip(np.round(f).astype(int), 0, len(rmp) - 1)]


def tone_idx(c, base, k=3.6, extra=0, dither=0.0):
    lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
    f = base + (lit - 0.5) * k + extra
    if dither:
        f = f + BAYER4[c.J % 4, c.I % 4] * dither
    return np.round(f).astype(int)


def pick(rmp, idx):
    return rmp[np.clip(np.asarray(idx).astype(int), 0, len(rmp) - 1)]


class Prim:
    def __init__(self, mat, edge=True, name=''):
        self.mat, self.edge, self.name = mat, edge, name


class Box(Prim):
    def __init__(self, u0, u1, v0, v1, z0, z1, mat, **kw):
        super().__init__(mat, **kw)
        self.b = (u0, u1, v0, v1, z0, z1)

    def hit(self, U, V):
        u0, u1, v0, v1, z0, z1 = self.b
        tu_u, tu_v, tu_z = u1 - U, v1 - V, np.full(U.shape, float(z1))
        tl = np.maximum(np.maximum(u0 - U, v0 - V), z0)
        tu = np.minimum(np.minimum(tu_u, tu_v), tu_z)
        face = np.where(tu == tu_z, F_TOP, np.where(tu == tu_u, F_U, F_V))
        ok = tl <= tu
        nx = (face == F_U).astype(float)
        ny = (face == F_V).astype(float)
        nz = (face == F_TOP).astype(float)
        return np.where(ok, tu, -np.inf), face, nx, ny, nz


class Cyl(Prim):
    """直立（橢圓）柱：中心 (cu,cv)、半徑 r（或 ru, rv）、z0..z1；r_in > 0 時是中空的環（看得到裡面）。"""
    def __init__(self, cu, cv, r, z0, z1, mat, r_in=0.0, rv=None, **kw):
        super().__init__(mat, **kw)
        self.c = (cu, cv, r, rv if rv is not None else r, z0, z1, r_in)

    @staticmethod
    def _roots(a, b, ru, rv):
        # ((a+t)/ru)^2 + ((b+t)/rv)^2 = 1
        A = 1 / ru ** 2 + 1 / rv ** 2
        B = 2 * (a / ru ** 2 + b / rv ** 2)
        C = a * a / ru ** 2 + b * b / rv ** 2 - 1
        disc = B * B - 4 * A * C
        sq = np.sqrt(np.maximum(disc, 0))
        return (-B - sq) / (2 * A), (-B + sq) / (2 * A), disc >= 0

    def hit(self, U, V):
        cu, cv, ru, rv, z0, z1, rin = self.c
        a, b = U - cu, V - cv
        t1, t2, ok = self._roots(a, b, ru, rv)
        tl = np.maximum(t1, z0)
        tu = np.minimum(t2, z1)
        ok = ok & (tl <= tu)
        face = np.where(tu >= z1 - 1e-9, F_TOP, F_SIDE)
        if rin > 0:
            i1, i2, iok = self._roots(a, b, rin * ru / max(ru, rv), rin * rv / max(ru, rv))
            inhole = iok & (tu > i1) & (tu < i2)
            tu = np.where(inhole, i1, tu)
            face = np.where(inhole, F_CAP, face)
            ok = ok & (tu >= tl)
        t = tu
        pu, pv = (a + t) / ru ** 2, (b + t) / rv ** 2
        rr = np.maximum(np.hypot(pu, pv), 1e-9)
        nx = np.where(face == F_SIDE, pu / rr, np.where(face == F_CAP, -pu / rr, 0.0))
        ny = np.where(face == F_SIDE, pv / rr, np.where(face == F_CAP, -pv / rr, 0.0))
        nz = (face == F_TOP).astype(float)
        return np.where(ok, t, -np.inf), face, nx, ny, nz


class HCyl(Prim):
    """橫躺的（橢圓）柱：axis='v' 時沿 v 方向（截面在 u–z），axis='u' 時沿 u（截面在 v–z）。
    c＝截面中心（u 或 v）、cz＝截面中心高、r／rz＝半徑、lo..hi＝沿軸的範圍；端面是 F_CAP。"""
    def __init__(self, axis, c, cz, r, lo, hi, mat, rz=None, zmin=None, **kw):
        super().__init__(mat, **kw)
        self.p = (axis, c, cz, r, rz if rz is not None else r, lo, hi, zmin)

    def hit(self, U, V):
        axis, cc, cz, r, rz, lo, hi, zmin = self.p
        a = (U - cc) if axis == 'v' else (V - cc)
        along = V if axis == 'v' else U
        c = -cz
        A = 1 / r ** 2 + 1 / rz ** 2
        B = 2 * (a / r ** 2 + c / rz ** 2)
        C = a * a / r ** 2 + c * c / rz ** 2 - 1
        disc = B * B - 4 * A * C
        sq = np.sqrt(np.maximum(disc, 0))
        t1, t2 = (-B - sq) / (2 * A), (-B + sq) / (2 * A)
        ok = disc >= 0
        tcap = hi - along
        tl = np.maximum(t1, lo - along)
        if zmin is not None:
            tl = np.maximum(tl, zmin)
        tu = np.minimum(t2, tcap)
        ok = ok & (tl <= tu)
        face = np.where(tu >= tcap - 1e-9, F_CAP, F_SIDE)
        pa, pz = (a + tu) / r ** 2, (c + tu) / rz ** 2
        rr = np.maximum(np.hypot(pa, pz), 1e-9)
        side = face == F_SIDE
        if axis == 'v':
            nx = np.where(side, pa / rr, 0.0)
            ny = np.where(side, 0.0, 1.0)
        else:
            nx = np.where(side, 0.0, 1.0)
            ny = np.where(side, pa / rr, 0.0)
        nz = np.where(side, pz / rr, 0.0)
        return np.where(ok, tu, -np.inf), face, nx, ny, nz


class Ell(Prim):
    """橢球（中心、三軸半徑），可切掉 z > zcut 的部分（切面＝F_CAP，例如鍋子裡的液面）。"""
    def __init__(self, cu, cv, cz, ru, rv, rz, mat, zcut=None, zmin=None, **kw):
        super().__init__(mat, **kw)
        self.e = (cu, cv, cz, ru, rv, rz, zcut, zmin)

    def hit(self, U, V):
        cu, cv, cz, ru, rv, rz, zcut, zmin = self.e
        a, b, c = (U - cu) / ru, (V - cv) / rv, (0 - cz) / rz
        da, db, dc = 1 / ru, 1 / rv, 1 / rz
        A = da * da + db * db + dc * dc
        B = 2 * (a * da + b * db + c * dc)
        C = a * a + b * b + c * c - 1
        disc = B * B - 4 * A * C
        sq = np.sqrt(np.maximum(disc, 0))
        t1, t2 = (-B - sq) / (2 * A), (-B + sq) / (2 * A)
        ok = disc >= 0
        tu = t2
        face = np.full(U.shape, F_SIDE)
        tl = t1
        if zcut is not None:
            cut = tu > zcut
            tu = np.where(cut, zcut, tu)
            face = np.where(cut, F_CAP, face)
        if zmin is not None:
            tl = np.maximum(tl, zmin)
        ok = ok & (tl <= tu)
        pu, pv, pz = U + tu - cu, V + tu - cv, tu - cz
        nx, ny, nz = pu / (ru * ru), pv / (rv * rv), pz / (rz * rz)
        nn = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1e-9)
        nx, ny, nz = nx / nn, ny / nn, nz / nn
        nx = np.where(face == F_CAP, 0.0, nx)
        ny = np.where(face == F_CAP, 0.0, ny)
        nz = np.where(face == F_CAP, 1.0, nz)
        return np.where(ok, tu, -np.inf), face, nx, ny, nz


class Scene:
    """一張圖（家具或房間殼）的邏輯像素場景。ox, oy ＝區域原點 (0,0,0) 在圖上的全解析度位置。"""
    def __init__(self, W, H, ox, oy, gx=0, gy=0):
        self.W, self.H, self.ox, self.oy, self.gx, self.gy = W, H, ox, oy, gx, gy
        self.LW = (W + gx + 1) // 2 + 1
        self.LH = (H + gy + 1) // 2 + 1
        self.I, self.J = np.meshgrid(np.arange(self.LW), np.arange(self.LH))
        cx = 2.0 * self.I - gx + 1.0
        cy = 2.0 * self.J - gy + 1.0
        dx, dy = cx - ox, cy - oy
        self.U0 = dx / 2 + dy
        self.V0 = dy - dx / 2
        self.t = np.full(self.U0.shape, -np.inf)
        self.ids = np.zeros(self.U0.shape, np.int32)
        self.rgb = np.zeros(self.U0.shape + (3,), np.uint8)
        self.edge_ok = [False]
        self.fine = []          # ×1 原生像素的小細節：(全解析度 x, y, rgb, 深度 t)
        self.shadow = np.zeros(self.U0.shape, bool)
        self.pos = np.zeros(self.U0.shape + (3,), np.float32)   # 每個像素打到的 (u,v,z)（夜晚打光用）

    # ── 座標 ──
    def lp(self, u, v, z=0.0):
        """區域 (u,v,z) → 邏輯像素座標（浮點，像素中心＝整數）。"""
        x = self.ox + u - v
        y = self.oy + (u + v) / 2 - z
        return (x + self.gx - 1.0) / 2.0, (y + self.gy - 1.0) / 2.0

    def t_at(self, u, v, z):
        """點 (u,v,z) 沿視線的深度。"""
        return z

    # ── 立體 ──
    def add(self, prim):
        t, face, nx, ny, nz = prim.hit(self.U0, self.V0)
        win = t > self.t + 1e-6
        if not win.any():
            return
        tt = t[win]
        c = Ctx(u=self.U0[win] + tt, v=self.V0[win] + tt, z=tt, face=face[win], nx=nx[win], ny=ny[win], nz=nz[win],
                I=self.I[win], J=self.J[win], prim=prim, sc=self)
        col = prim.mat(c)
        col = np.asarray(col, dtype=np.uint8)
        if col.ndim == 1:
            col = np.broadcast_to(col, (int(win.sum()), 3))
        self.rgb[win] = col
        self.t[win] = tt
        self.pos[win] = np.stack([c.u, c.v, c.z], -1)
        self.edge_ok.append(prim.edge)
        self.ids[win] = len(self.edge_ok) - 1

    def sprite(self, img, u, v, z, anchor=(0.5, 1.0), depth=None, edge=True, outline=None):
        """立牌：img 是邏輯像素 RGBA（numpy），anchor 那一點放在 (u,v,z)。深度用 u+v 平面（或給 depth＝(u,v) 底座）。"""
        h, w = img.shape[:2]
        fx, fy = self.lp(u, v, z)
        x0 = int(round(fx - anchor[0] * (w - 1)))
        y0 = int(round(fy - anchor[1] * (h - 1)))
        bu, bv = depth if depth is not None else (u, v)
        xa, ya = max(0, x0), max(0, y0)
        xb, yb = min(self.LW, x0 + w), min(self.LH, y0 + h)
        if xa >= xb or ya >= yb:
            return
        sub = img[ya - y0:yb - y0, xa - x0:xb - x0]
        tb = ((bu + bv) - (self.U0[ya:yb, xa:xb] + self.V0[ya:yb, xa:xb])) / 2.0
        win = (sub[..., 3] > 0) & (tb > self.t[ya:yb, xa:xb] - 0.01)
        self.edge_ok.append(edge)
        n = len(self.edge_ok) - 1
        for ch in range(3):
            self.rgb[ya:yb, xa:xb, ch] = np.where(win, sub[..., ch], self.rgb[ya:yb, xa:xb, ch])
        self.t[ya:yb, xa:xb] = np.where(win, tb, self.t[ya:yb, xa:xb])
        self.ids[ya:yb, xa:xb] = np.where(win, n, self.ids[ya:yb, xa:xb])

    def paint(self, mask, col):
        """直接塗在已經畫好的像素上（不改深度）。"""
        self.rgb[mask] = col

    def fine_px(self, u, v, z, rgb, dx=0, dy=0):
        x = self.ox + u - v + dx
        y = self.oy + (u + v) / 2 - z + dy
        self.fine.append((int(math.floor(x)), int(math.floor(y)), np.array(rgb, np.uint8)))

    def ground_shadow(self, mask_fn):
        """接地陰影（半透明，畫在物件外面）：mask_fn(u0, v0) 對 z=0 的地面點。"""
        self.shadow |= mask_fn(self.U0, self.V0)

    # ── 收尾 ──
    def finish(self, outline=True, inner=True, shadow_rgba=(30, 14, 30, 86)):
        solid = self.ids > 0
        rgb = self.rgb.copy()
        if inner:
            edge = np.zeros_like(solid)
            ok = np.array(self.edge_ok)[self.ids]
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nid = np.roll(np.roll(self.ids, dy, 0), dx, 1)
                nt = np.roll(np.roll(self.t, dy, 0), dx, 1)
                edge |= solid & ok & (nid != self.ids) & (nid > 0) & (nt < self.t - 3.0)
            rgb[edge] = (rgb[edge].astype(np.int32) * 50 + OUT.astype(np.int32) * 50) // 100
        alpha = np.where(solid, 255, 0).astype(np.uint8)
        if outline:
            big = solid.copy()
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                big |= np.roll(np.roll(solid, dy, 0), dx, 1)
            ring = big & ~solid
            rgb[ring] = OUT
            alpha[ring] = 255
            solid = solid | ring
        sh = self.shadow & ~solid
        out = np.zeros(self.U0.shape + (4,), np.uint8)
        out[..., :3] = rgb
        out[..., 3] = alpha
        out[sh] = shadow_rgba
        big = out.repeat(2, 0).repeat(2, 1)[self.gy:self.gy + self.H, self.gx:self.gx + self.W].copy()
        for x, y, c in self.fine:
            if 0 <= x < self.W and 0 <= y < self.H and big[y, x, 3] == 255:
                big[y, x, :3] = c
        return big


# ═══════════════════════════════ 小工具：材質 ═══════════════════════════════

def bevel(c, b, hi=1, lo=-1, w=1.6):
    """方塊的倒角：頂面靠前兩條邊、立面靠上緣 +hi；立面靠下緣 lo。b＝方塊範圍。"""
    u0, u1, v0, v1, z0, z1 = b
    d = np.zeros(c.u.shape)
    top = c.face == F_TOP
    d = np.where(top & ((u1 - c.u < w) | (v1 - c.v < w)), hi, d)
    vert = (c.face == F_U) | (c.face == F_V)
    d = np.where(vert & (z1 - c.z < w * 0.8), hi, d)
    d = np.where(vert & (c.z - z0 < w * 0.9), lo, d)
    # 兩個立面的交角（+u 與 +v 面相交的那條直線）亮一點
    d = np.where((c.face == F_V) & (u1 - c.u < w * 0.9), d + hi, d)
    # 高的立面：下面三分之一收暗一階（像女巫裙擺那樣的柔和多階）
    tall = (z1 - z0) > 16
    if tall:
        d = np.where(vert & (c.z - z0 > w * 0.9) & ((c.z - z0) / (z1 - z0) < 0.1), d + lo, d)
    return d


def face_a(c):
    """立面上的水平座標（+u 面沿 −v 走、+v 面沿 u 走、頂面沿 u−v），用來畫木紋、石塊。"""
    return np.where(c.face == F_U, -c.v, np.where(c.face == F_V, c.u, c.u - c.v))


def wood_mat(rmp=WOOD, base=5, grain_axis='auto', bevel_b=None, k=3.6, plank=0, seed=1):
    """木頭：受光＋木紋（順著長邊的深色細紋、偶爾節眼）＋倒角。"""
    def mat(c):
        idx = tone_idx(c, base, k)
        if bevel_b is not None:
            idx = idx + bevel(c, bevel_b).astype(int)
        a = face_a(c)
        ga = grain_axis
        if ga == 'auto' and bevel_b is not None:
            u0, u1, v0, v1, z0, z1 = bevel_b
            hz = z1 - z0
            vert_u = hz > (v1 - v0) * 1.2          # +u 面：寬 = dv
            vert_v = hz > (u1 - u0) * 1.2          # +v 面：寬 = du
            zg = ((c.face == F_U) & vert_u) | ((c.face == F_V) & vert_v)
        else:
            zg = np.full(c.u.shape, ga == 'z')
        zg = zg & (c.face != F_TOP)
        along = np.where(zg, c.z, a)
        across = np.where(zg, a, np.where(c.face == F_TOP, (c.u + c.v) * 0.5, c.z))
        g = h32(np.floor(across / 1.6), np.floor(along / 9.0 + h32(np.floor(across / 1.6), seed) * 5), seed)
        idx = np.where(g > 0.86, idx - 1, idx)
        idx = np.where((g < 0.05), idx + 1, idx)
        if plank:
            pk = np.floor(across / plank)
            fa = across - pk * plank
            idx = np.where(fa < 1.1, idx - 1, idx)
            idx = idx + np.where(h32(pk, seed + 4) > 0.75, 1, 0) - np.where(h32(pk, seed + 4) < 0.2, 1, 0)
        return pick(rmp, idx)
    return mat


def solid_mat(rmp, base, k=3.6, b=None, dither=0.0, extra=None):
    def mat(c):
        idx = tone_idx(c, base, k, dither=dither)
        if b is not None:
            idx = idx + bevel(c, b).astype(int)
        if extra is not None:
            idx = extra(c, idx)
        return pick(rmp, idx)
    return mat


def metal_mat(rmp=IRON, base=4, k=4.2, spec=True):
    def mat(c):
        lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
        idx = base + (lit - 0.5) * k
        idx = np.where(lit > 0.93, len(rmp) - 1, idx) if spec else idx
        # 背光側一點反光（環境光從地板反上來）
        idx = np.where((c.nz < -0.2) & (lit < 0.2), idx + 1, idx)
        return pick(rmp, np.round(idx))
    return mat


# ═══════════════════════════════ 小工具：2D 立牌 ═══════════════════════════════

def blank(w, h):
    return np.zeros((h, w, 4), np.uint8)


def put(img, x, y, rgb):
    h, w = img.shape[:2]
    x, y = int(x), int(y)
    if 0 <= x < w and 0 <= y < h:
        img[y, x, :3] = rgb
        img[y, x, 3] = 255


def rect(img, x0, y0, x1, y1, rgb):
    """含頭含尾的方塊。"""
    h, w = img.shape[:2]
    xa, xb = max(0, int(x0)), min(w, int(x1) + 1)
    ya, yb = max(0, int(y0)), min(h, int(y1) + 1)
    if xa < xb and ya < yb:
        img[ya:yb, xa:xb, :3] = rgb
        img[ya:yb, xa:xb, 3] = 255


def add_outline(img, color=OUT, diag=False):
    m = img[..., 3] > 0
    big = m.copy()
    dirs = ((0, 1), (0, -1), (1, 0), (-1, 0)) + (((1, 1), (1, -1), (-1, 1), (-1, -1)) if diag else ())
    for dy, dx in dirs:
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


def pad(img, n=1):
    h, w = img.shape[:2]
    o = blank(w + 2 * n, h + 2 * n)
    o[n:n + h, n:n + w] = img
    return o


def from_ascii(rows, cmap):
    """ASCII 小圖：每個字一個邏輯像素，'.' 透明。"""
    h, w = len(rows), max(len(r) for r in rows)
    img = blank(w, h)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != '.' and ch != ' ':
                img[y, x, :3] = cmap[ch]
                img[y, x, 3] = 255
    return img


def ball(img, cx, cy, rx, ry, rmp, base, spec=True, k=2.6, rim_dark=True):
    """受光的小球／橢圓（左上亮），畫在 img 上。"""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    dx = (xx - cx) / max(rx, 0.5)
    dy = (yy - cy) / max(ry, 0.5)
    d2 = dx * dx + dy * dy
    m = d2 <= 1.0
    lv = -(dx * -0.55 + dy * -0.8)
    t = base + np.round(lv * k * 0.6).astype(int)
    if rim_dark:
        t = np.where(d2 > 0.7, np.minimum(t, base), t)
    if spec:
        t = np.where(((dx + 0.4) ** 2 + (dy + 0.45) ** 2) < 0.05, len(rmp) - 1, t)
    t = np.clip(t, 0, len(rmp) - 1)
    img[m, :3] = rmp[t[m]]
    img[m, 3] = 255
    return m


def flame_img(h, w, frame, seed=0):
    """小火苗（蠟燭）：外橘、中黃、芯白。h 邏輯像素高。"""
    img = blank(w, h)
    cx = (w - 1) / 2.0
    sway = [0, 1, 0, -1][frame % 4] * 0.4
    for y in range(h):
        f = y / max(1, h - 1)                         # 0 頂 → 1 底
        half = (w / 2.0) * (math.sin(f * math.pi * 0.85 + 0.25)) * (0.55 + 0.45 * f)
        x0 = cx + sway * (1 - f) - half
        x1 = cx + sway * (1 - f) + half
        for x in range(w):
            if x0 - 0.2 <= x <= x1 + 0.2:
                core = abs(x - cx - sway * (1 - f)) < half * 0.45 and f > 0.35
                col = FIRE[8] if core and f > 0.55 else FIRE[6] if (abs(x - cx) < half * 0.7 and f > 0.2) else FIRE[4]
                put(img, x, y, col)
    return img


def candle_img(hgt, frame=0, wax=LINEN, wax_base=7, w=3, flame_h=4, drip=True):
    """一根蠟燭（邏輯像素）：w 寬、hgt 高（不含火）。"""
    W = w + 2
    img = blank(W, hgt + flame_h + 1)
    for y in range(hgt):
        for x in range(w):
            t = wax_base + (1 if x == 0 else -1 if x == w - 1 else 0) - (1 if y == hgt - 1 else 0)
            put(img, x + 1, flame_h + 1 + y, wax[min(len(wax) - 1, t)])
    if drip and hgt > 3:
        put(img, 1, flame_h + 3, wax[min(len(wax) - 1, wax_base + 2)])
        put(img, w, flame_h + 2, wax[wax_base - 1])
    put(img, 1 + w // 2, flame_h, IRON[2])            # 燭芯
    f = flame_img(flame_h, 3, frame)
    m = f[..., 3] > 0
    sub = img[0:flame_h, w // 2:w // 2 + 3]
    sub[m] = f[m]
    return img


# ═══════════════════════════════ 房間殼 ═══════════════════════════════

WIN_U0, WIN_U1, WIN_Z0, WIN_Z1 = 84, 168, 70, 152          # 窗（右後牆）：跟舊版同一個位置
LIGHT_PATCH = [(112, 56), (196, 56), (234, 150), (150, 150)]
WAINSCOT_Z = 54                                             # 護牆板高
BEAM_Z0, BEAM_Z1 = 150, 164                                 # 上方橫樑
POSTS_R = [(198, 208), (394, 402)]                          # 右後牆的木柱（u）
POSTS_L = [(116, 126), (206, 216), (318, 326)]              # 左後牆的木柱（v）
CHART = (246, 292, 92, 146)                                 # 左後牆的星圖（v0, v1, z0, z1）


def in_poly(pts, x, y):
    n = len(pts)
    inside = np.zeros(np.shape(x), bool)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cond = ((y1 > y) != (y2 > y))
        xint = (x2 - x1) * (y - y1) / ((y2 - y1) + 1e-12) + x1
        inside ^= cond & (x < xint)
    return inside


def plank_floor(u, v, I, J, base=5):
    """地板：沿 u 鋪的長木板（寬 25），錯縫、木紋、節眼、釘子、板縫。回傳色階（int）。"""
    W = 25.0
    row = np.floor(v / W)
    fv = v - row * W
    off = h32(row, 11) * 160
    L = 130 + np.floor(h32(row, 12) * 3) * 30
    bu = u + off
    bid = np.floor(bu / L)
    fu = bu - bid * L
    var = h32(bid, row, 13)
    idx = base + np.where(var > 0.78, 1, 0) - np.where(var < 0.22, 1, 0) - np.where(var < 0.06, 1, 0)
    # 木紋：順著 u 的細紋（拉長的雜訊）
    gn = fbm(u * 0.08 + row * 13.7, fv * 0.9 + bid * 5.1, 1.0, 21, 2)
    idx = np.where(gn > 0.66, idx - 1, idx)
    idx = np.where((gn < 0.24) & (fv > 3), idx + 1, idx)
    # 節眼（深色芯＋一圈年輪）
    kn = h32(bid, row, 17) > 0.55
    ku = (h32(bid, row, 18) * 0.6 + 0.2) * L
    kv = 6 + h32(bid, row, 19) * (W - 12)
    dk = np.hypot((fu - ku) * 0.35, (fv - kv) * 1.0)
    idx = np.where(kn & (dk < 1.3), base - 3, idx)
    idx = np.where(kn & (dk >= 1.3) & (dk < 2.6), idx - 1, idx)
    idx = np.where(kn & (np.abs(dk - 4.2) < 0.55), idx - 1, idx)
    # 板縫（v 方向的長縫最深）、板頭接縫、上緣受光
    idx = np.where(fv < 1.6, base - 3, idx)
    idx = np.where((fv >= 1.6) & (fv < 3.2), idx + 1, idx)
    idx = np.where(fu < 1.5, base - 3, idx)
    idx = np.where((fu >= 1.5) & (fu < 3.5), idx + 1, idx)
    # 釘子：板頭兩顆
    nail = (np.abs(fu - 6) < 1.4) & ((np.abs(fv - 7) < 1.2) | (np.abs(fv - 19) < 1.2))
    idx = np.where(nail, base - 3, idx)
    return idx


def wall_pattern(a, z, I, J, side):
    """牆面（a＝沿牆的座標、z＝高）：下段直條護牆板、上段暖奶油灰泥（局部露出石頭）。回傳 (色盤編號, 色階)。"""
    n = a.shape[0]
    rmp_id = np.zeros(n, int)        # 0 灰泥、1 木、2 石
    seed = 31 if side == 'R' else 57
    lift = 0 if side == 'R' else -1
    # ── 灰泥 ──
    mott = fbm(a * 0.6, z * 1.1, 9.0, seed, 3)
    idx = 6 + lift + np.where(mott > 0.62, 1, 0) - np.where(mott < 0.36, 1, 0)
    sp = h32(I, J, seed + 2)
    idx = np.where(sp > 0.965, idx - 1, idx)
    idx = np.where(sp < 0.02, idx + 1, idx)
    # 露出的石頭（幾塊不規則的區域）
    patch = fbm(a * 0.5 + 300, z * 0.9, 26.0, seed + 5, 2)
    band = (z > WAINSCOT_Z + 6) & (z < BEAM_Z0 - 4)
    stone = (patch > 0.7) & band
    rows = np.floor((z - WAINSCOT_Z) / 11.0)
    off = (rows % 2) * 9
    col = np.floor((a + off) / 18.0)
    fa = (a + off) - col * 18.0
    fz = (z - WAINSCOT_Z) - rows * 11.0
    sv = h32(col, rows, seed + 6)
    sidx = 5 + lift + np.where(sv > 0.7, 1, 0) - np.where(sv < 0.3, 1, 0)
    sidx = np.where(fz > 8.5, sidx + 1, sidx)            # 上緣亮
    sidx = np.where(fa > 15.8, sidx - 1, sidx)           # 右緣暗
    mortar = np.hypot(np.maximum(0, np.abs(fa - 9.4) - 6.0), np.maximum(0, np.abs(fz - 5.9) - 3.0)) > 1.9
    sidx = np.where(mortar, 3 + lift, sidx)
    edge = (patch > 0.7) & (patch < 0.72) & band
    idx = np.where(stone, sidx, idx)
    rmp_id = np.where(stone, 2, rmp_id)
    idx = np.where(edge, 4 + lift, idx)
    rmp_id = np.where(edge, 0, rmp_id)
    # 樑下的一點陰影
    idx = np.where((rmp_id == 0) & (z > BEAM_Z0 - 6), idx - 1, idx)
    # ── 護牆板 ──
    low = z < WAINSCOT_Z
    pw = 11.0
    pk = np.floor(a / pw)
    fp = a - pk * pw
    pv = h32(pk, seed + 9)
    widx = 4 + lift + np.where(pv > 0.7, 1, 0) - np.where(pv < 0.25, 1, 0)
    gr = h32(np.floor(a / 1.5), np.floor(z / 7 + h32(np.floor(a / 1.5), seed) * 4), seed + 10)
    widx = np.where(gr > 0.85, widx - 1, widx)
    widx = np.where(fp < 1.4, 2 + lift, widx)
    widx = np.where((fp >= 1.4) & (fp < 2.6), widx + 1, widx)
    widx = np.where(z < 12, widx - 1, widx)
    rail = (z >= WAINSCOT_Z - 5) & (z < WAINSCOT_Z)
    widx = np.where(rail, 5 + lift + np.where(z > WAINSCOT_Z - 2, 1, 0), widx)
    widx = np.where(rail & (z < WAINSCOT_Z - 4), 2 + lift, widx)
    idx = np.where(low, widx, idx)
    rmp_id = np.where(low, 1, rmp_id)
    return rmp_id, idx


def wall_colors(rmp_id, idx):
    out = np.zeros(rmp_id.shape + (3,), np.uint8)
    for k, rmp in ((0, PLASTER), (1, WOOD), (2, WSTONE)):
        m = rmp_id == k
        if m.any():
            out[m] = pick(rmp, idx[m])
    return out


def window_paint(a, z, night):
    """右後牆的窗（a＝u）：回傳 (mask, rgb)。窗框、窗櫺、天空（白天藍天白雲遠山／夜晚星空月亮）、兩側紫色窗簾、上方荷葉邊。"""
    n = a.shape[0]
    rgb = np.zeros((n, 3), np.uint8)
    m = np.zeros(n, bool)
    u0, u1, z0, z1 = WIN_U0, WIN_U1, WIN_Z0, WIN_Z1
    inw = (a >= u0) & (a < u1) & (z >= z0) & (z < z1)
    gu0, gu1, gz0, gz1 = u0 + 5, u1 - 1, z0 + 1, z1 - 6
    glass = inw & (a >= gu0) & (a < gu1) & (z >= gz0) & (z < gz1)
    reveal = inw & ~glass
    rgb[reveal] = pick(PLASTER, np.where(z[reveal] > gz1, 2, 3))
    m |= reveal
    bay = BAYER4[(np.floor(z).astype(int)) % 4, (np.floor(a).astype(int)) % 4]
    if not night:
        f = (z - gz0) / (gz1 - gz0)
        sidx = np.clip(np.floor(1.5 + f * 4.4), 0, 6).astype(int)
        col = SKY[sidx]
        cl = (((a - (gu0 + 22)) / 11) ** 2 + ((z - (gz1 - 16)) / 4.5) ** 2 < 1) | \
             (((a - (gu0 + 31)) / 8) ** 2 + ((z - (gz1 - 12)) / 4.5) ** 2 < 1) | \
             (((a - (gu1 - 18)) / 9) ** 2 + ((z - (gz0 + 40)) / 3.5) ** 2 < 1)
        col = np.where(cl[:, None], SKY[6], col)
        h1 = gz0 + 14 + 6 * np.sin((a - gu0) / 12.0) + 3 * np.sin(a / 4.3)
        h2 = gz0 + 7 + 4 * np.sin((a - gu0) / 8.0 + 1.3)
        col = np.where((z < h1)[:, None], pick(LEAF, 6 + (np.sin(a / 2.0) > 0.6)), col)
        col = np.where((z < h2)[:, None], pick(LEAF, 4 + (np.sin(a / 1.7) > 0.5)), col)
        sl = (np.abs((a - gu0) - (z - gz0) * 0.9 - 8) < 1.6) | (np.abs((a - gu0) - (z - gz0) * 0.9 - 50) < 1.2)
        col = np.where((sl & (z > gz0 + 18))[:, None], np.minimum(col.astype(int) + 40, 255).astype(np.uint8), col)
    else:
        f = (z - gz0) / (gz1 - gz0)
        sidx = np.clip(np.floor(4.9 - f * 4.2), 0, 5).astype(int)
        col = NSKY[sidx]
        st = (h32(np.floor(a / 2), np.floor(z / 2), 77) > 0.955) & (z > gz0 + 14)
        col = np.where(st[:, None], STAR, col)
        mu, mz = gu1 - 20, gz1 - 18
        moon = ((a - mu) ** 2 + (z - mz) ** 2 < 64) & ~((a - mu - 4) ** 2 + (z - mz - 3) ** 2 < 49)
        halo = ((a - mu) ** 2 + (z - mz) ** 2 < 150) & ~moon
        col = np.where(halo[:, None], NSKY[5], col)
        col = np.where(moon[:, None], STAR, col)
        h1 = gz0 + 14 + 6 * np.sin((a - gu0) / 12.0) + 3 * np.sin(a / 4.3)
        col = np.where((z < h1)[:, None], NSKY[0], col)
        lit = (z < h1) & (h32(np.floor(a / 3), np.floor(z / 3), 5) > 0.95) & (z > gz0 + 3)
        col = np.where(lit[:, None], FIRE[6], col)
    rgb[glass] = col[glass]
    m |= glass
    mid = (gu0 + gu1) / 2
    zm = gz0 + (gz1 - gz0) * 0.55
    bars = glass & ((a < gu0 + 3) | (a >= gu1 - 3) | (z < gz0 + 3) | (z >= gz1 - 3) |
                    (np.abs(a - mid) < 1.6) | (np.abs(z - zm) < 1.6))
    bidx = np.where((z >= gz1 - 3) | (np.abs(z - zm - 1) < 0.8), 6, 4)
    rgb[bars] = pick(WOOD, bidx[bars])
    # 窗簾：兩側紫布（褶子），中段用金色綁帶束起來
    tie = z0 + 30
    def curtain(a0, a1, inner_left):
        reg = (a >= a0) & (a < a1) & (z >= z0 - 6) & (z < z1 + 2)
        # 束起來的下半：往牆邊收
        if inner_left:
            reg &= (z >= tie) | (a < a1 - 2 - (tie - z) * 0.35)
        else:
            reg &= (z >= tie) | (a >= a0 + 2 + (tie - z) * 0.35)
        return reg
    cur = curtain(u0 - 10, u0 + 14, True) | curtain(u1 - 14, u1 + 10, False)
    fold = np.sin((a - u0) * 0.9) + 0.3 * np.sin((a - u0) * 2.3)
    cidx = 5 + np.round(fold * 1.2).astype(int) - np.where(z < tie, 1, 0)
    rgb[cur] = pick(PURPLE, cidx[cur])
    tieb = cur & (np.abs(z - tie) < 2.2)
    rgb[tieb] = pick(GOLD, np.where(z[tieb] > tie, 5, 4))
    m |= cur
    val = (a >= u0 - 12) & (a < u1 + 12) & (z >= z1 - 4) & (z < z1 + 10)
    scal = z1 - 4 + 3 * np.abs(np.sin((a - u0) * math.pi / 12.0))
    val &= z > scal
    vidx = 6 + np.where(z > z1 + 7, 1, 0) - np.where(z < scal + 2, 1, 0)
    rgb[val] = pick(PURPLE, vidx[val])
    dots = val & (np.abs(z - (z1 + 3)) < 1) & (np.mod(a - u0, 12) < 1.6)
    rgb[dots] = GOLD[6]
    m |= val
    rod = (a >= u0 - 16) & (a < u1 + 16) & (z >= z1 + 10) & (z < z1 + 13)
    rgb[rod] = pick(BRASS, np.where(z[rod] > z1 + 11.5, 6, 4))
    knob = ((np.abs(a - (u0 - 16)) < 2.5) | (np.abs(a - (u1 + 16)) < 2.5)) & (np.abs(z - (z1 + 11.5)) < 2.6)
    rgb[knob] = BRASS[6]
    m |= rod | knob
    return m, rgb


def chart_paint(a, z):
    """左後牆的星圖（a＝v）：木框＋深藍底＋金色星座。"""
    v0, v1, z0, z1 = CHART
    n = a.shape[0]
    rgb = np.zeros((n, 3), np.uint8)
    fr = (a >= v0) & (a < v1) & (z >= z0) & (z < z1)
    inner = fr & (a >= v0 + 4) & (a < v1 - 4) & (z >= z0 + 4) & (z < z1 - 4)
    rgb[fr] = pick(WOOD, np.where(z[fr] > z1 - 2, 6, 4))
    cz, ca = (z0 + z1) / 2, (v0 + v1) / 2
    bidx = 2 + (h32(np.floor(a / 2), np.floor(z / 2), 3) > 0.9).astype(int)
    col = pick(BLUE, bidx)
    r = np.hypot((a - ca), (z - cz))
    ring = (np.abs(r - 14) < 0.8) | (np.abs(r - 8) < 0.7)
    col = np.where(ring[:, None], GOLD[3], col)
    cross = ((np.abs(a - ca) < 0.6) | (np.abs(z - cz) < 0.6)) & (r < 18)
    col = np.where(cross[:, None], GOLD[2], col)
    for (da, dz, big) in ((-8, 10, 1), (9, 6, 0), (-12, -9, 0), (4, -13, 1), (12, -4, 0), (-3, 4, 0), (7, 15, 0)):
        st = (np.abs(a - ca - da) + np.abs(z - cz - dz) < (2.2 if big else 1.2))
        col = np.where(st[:, None], STAR, col)
    moon = (np.hypot(a - ca + 2, z - cz - 1) < 4.5) & ~(np.hypot(a - ca + 0.5, z - cz - 2) < 3.8)
    col = np.where(moon[:, None], GOLD[6], col)
    rgb[inner] = col[inner]
    return fr, rgb


def bunting_paint(a, z, side):
    """橫樑下的一串三角旗（a＝沿牆座標）。"""
    n = a.shape[0]
    rgb = np.zeros((n, 3), np.uint8)
    m = np.zeros(n, bool)
    spans = [(10, 110), (130, 204), (222, 314)] if side == 'L' else [(214, 300), (406, 466)]
    for s0, s1 in spans:
        L = s1 - s0
        sag = BEAM_Z0 - 2 - 7 * np.sin(np.clip((a - s0) / L, 0, 1) * math.pi)
        inr = (a >= s0) & (a < s1)
        string = inr & (np.abs(z - sag) < 0.8)
        rgb[string] = LINEN[3]
        m |= string
        k = np.floor((a - s0) / 9.0)
        fa = (a - s0) - k * 9.0
        tri = inr & (fa > 1) & (fa < 8) & (z < sag) & (z > sag - 8 + np.abs(fa - 4.5) * 1.6) & (k * 9 + 9 < L)
        ci = (k.astype(int) + (0 if side == 'L' else 2)) % len(BUNT)
        for q in range(len(BUNT)):
            mm = tri & (ci == q)
            rgb[mm] = BUNT[q][np.where(fa[mm] < 3.5, 2, 1)]
        m |= tri
    return m, rgb


def shell_scene(night):
    sc = Scene(CANVAS_W, CANVAS_H, OX, OY)

    def floor_mat(c):
        top = c.face == F_TOP
        idx = plank_floor(c.u, c.v, c.I, c.J)
        ao = np.minimum(c.u, c.v)
        idx = np.where(ao < 5, idx - 2, np.where(ao < 12, idx - 1, idx))
        mu = (LIGHT_PATCH[0][0] + LIGHT_PATCH[1][0]) / 2
        vv = c.v - 56
        cross = (np.abs(c.u - (mu + vv * 0.4)) < 2.6) | (np.abs(vv - (150 - 56) * 0.5) < 2.4)
        lp = in_poly(LIGHT_PATCH, c.u, c.v) & ~cross
        idx = np.where(lp, idx + (1 if night else 2), idx)
        col = pick(FLOOR, idx)
        # 出口門墊（條紋＋月亮）
        cu, cv = EXIT_UV
        du_, dv_ = c.u - cu, c.v - cv
        dm = top & (np.abs(du_) < 30) & (np.abs(dv_) < 21)
        if dm.any():
            inner = (np.abs(du_) < 26) & (np.abs(dv_) < 17)
            stripe = (np.floor((du_ + 40) / 5) % 2 == 0)
            midx = np.where(inner, np.where(stripe, 5, 4), 3)
            midx = np.where((np.abs(du_) >= 29) | (np.abs(dv_) >= 20), 2, midx)
            mcol = pick(TERRA, midx)
            moon = (np.hypot(du_ * 0.8, dv_) < 7) & ~(np.hypot(du_ * 0.8 - 2.5, dv_ + 2) < 6)
            mcol = np.where(moon[:, None], GOLD[5], mcol)
            col = np.where(dm[:, None], mcol, col)
        side = ~top
        sidx = np.where(c.z > -2, 5, np.where(c.z > -6, 3, 2)) - np.where(c.face == F_U, 1, 0)
        col = np.where(side[:, None], pick(TIMBER, sidx), col)
        return col

    def wall_mat(side):
        def mat(c):
            inner = (c.face == F_V) if side == 'R' else (c.face == F_U)
            a = c.u if side == 'R' else c.v
            rid, idx = wall_pattern(a, c.z, c.I, c.J, side)
            if side == 'L':
                idx = np.where(c.v < 10, idx - 1, idx)
            col = wall_colors(rid, idx)
            if side == 'R':
                wm, wrgb = window_paint(a, c.z, night)
                col = np.where((wm & inner)[:, None], wrgb, col)
            else:
                cm, crgb = chart_paint(a, c.z)
                col = np.where((cm & inner)[:, None], crgb, col)
            bm, brgb = bunting_paint(a, c.z, side)
            col = np.where((bm & inner)[:, None], brgb, col)
            top = c.face == F_TOP
            al = c.u if side == 'R' else c.v
            slab = np.floor(al / 22.0)
            fa = al - slab * 22
            tidx = 6 + np.where(h32(slab, 4) > 0.7, 1, 0) - np.where(h32(slab, 4) < 0.25, 1, 0)
            tidx = np.where(fa < 1.2, 3, tidx)
            col = np.where(top[:, None], pick(STONE, tidx), col)
            endf = ~top & ~inner
            eidx = 3 + np.where(np.mod(c.z, 22) < 1.5, -1, 0) + (1 if side == 'L' else 0)
            col = np.where(endf[:, None], pick(STONE, eidx), col)
            return col
        return mat

    sc.add(Box(0, ROOM_U, 0, ROOM_V, -RIM, 0, floor_mat, name='floor'))
    sc.add(Box(-WALL_T, ROOM_U, -WALL_T, 0, -RIM, WALL_H, wall_mat('R'), name='wallR'))
    sc.add(Box(-WALL_T, 0, -WALL_T, ROOM_V, -RIM, WALL_H, wall_mat('L'), name='wallL'))
    tim = wood_mat(TIMBER, 4, grain_axis='z', seed=3)
    sc.add(Box(0, 5, 0, 5, 0, WALL_H, tim, name='cornerpost'))
    for a0, a1 in POSTS_R:
        sc.add(Box(a0, a1, 0, 3, 0, BEAM_Z0, tim))
    for a0, a1 in POSTS_L:
        sc.add(Box(0, 3, a0, a1, 0, BEAM_Z0, tim))
    beam = wood_mat(TIMBER, 4, seed=5)
    sc.add(Box(0, ROOM_U, 0, 4, BEAM_Z0, BEAM_Z1, beam, name='beamR'))
    sc.add(Box(0, 4, 0, ROOM_V, BEAM_Z0, BEAM_Z1, beam, name='beamL'))
    base = wood_mat(TIMBER, 5, seed=8)
    sc.add(Box(0, ROOM_U, 0, 2, 0, 8, base))
    sc.add(Box(0, 2, 0, ROOM_V, 0, 8, base))
    sb = (WIN_U0 - 6, WIN_U1 + 6, 0, 9, WIN_Z0 - 5, WIN_Z0)
    sc.add(Box(*sb, wood_mat(WOOD, 6, bevel_b=sb, seed=9)))
    fb = (WIN_U0 + 8, WIN_U0 + 40, 2, 9, WIN_Z0, WIN_Z0 + 7)
    sc.add(Box(*fb, wood_mat(TERRA, 5, bevel_b=fb, seed=10)))
    flower_box(sc, WIN_U0 + 8, WIN_U0 + 40, 5.5, WIN_Z0 + 7)
    su0, su1, sz = 404, 452, 112
    sb = (su0, su1, 0, 10, sz - 4, sz)
    sc.add(Box(*sb, wood_mat(WOOD, 5, bevel_b=sb, seed=12)))
    for uu in (su0 + 6, su1 - 8):
        sc.add(Box(uu, uu + 2, 0, 7, sz - 12, sz - 4, wood_mat(WOOD, 4, seed=13)))
    shelf_items(sc, su0, su1, sz)
    herbs(sc)
    broom(sc)
    return sc


def flower_box(sc, u0, u1, v, z):
    """窗台花箱裡的小花（立牌）。"""
    for k in range(9):
        uu = u0 + 2 + (u1 - u0 - 4) * k / 8
        img = blank(3, 5)
        hgt = 3 + int(hs(k, 4) * 2)
        for y in range(hgt):
            put(img, 1, 4 - y, LEAF[4 + (y % 2)])
        put(img, 0, 4 - hgt + 2, LEAF[6])
        sc.sprite(img, uu, v, z, anchor=(0.5, 1.0))
    for f, rmp, b in ((0.15, PINK, 4), (0.4, GOLD, 5), (0.62, PINK, 5), (0.85, PURPLE, 6)):
        uu = u0 + (u1 - u0) * f
        img = blank(3, 3)
        for dx, dy in ((1, 0), (0, 1), (2, 1), (1, 2)):
            put(img, dx, dy, rmp[b])
        put(img, 1, 1, GOLD[6] if rmp is not GOLD else CREAM)
        sc.sprite(img, uu, v + 1, z + 5, anchor=(0.5, 0.5))


def bottle_img(w, h, liq, neck=2, cork=True, label=None, round_=False):
    """藥瓶（邏輯像素）。liq＝液體色盤。"""
    W, H = w + 2, h + 2
    img = blank(W, H)
    nk = max(1, w // 3)
    bx0 = 1
    body_top = 1 + neck + (1 if cork else 0)
    if round_:
        cy = body_top + (H - 1 - body_top) / 2.0
        ball(img, (W - 1) / 2.0, cy, w / 2.0, (H - 1 - body_top) / 2.0, liq, 5, spec=False)
        m = img[..., 3] > 0
        yy = np.arange(H)[:, None] * np.ones((1, W))
        img[m & (yy < cy - 0.5), :3] = GLASS[5]
    else:
        for y in range(body_top, H - 1):
            for x in range(bx0, bx0 + w):
                f = (y - body_top) / max(1, H - 1 - body_top)
                if f < 0.25:
                    c = GLASS[5] if x > bx0 else GLASS[6]
                else:
                    c = liq[6 if x == bx0 else 3 if x == bx0 + w - 1 else 5]
                    if y == H - 2:
                        c = liq[3]
                put(img, x, y, c)
    cx = (W - 1) // 2
    for y in range(1 + (1 if cork else 0), body_top):
        for x in range(cx - nk // 2, cx - nk // 2 + nk):
            put(img, x, y, GLASS[5])
    if cork:
        for x in range(cx - nk // 2, cx - nk // 2 + nk):
            put(img, x, 1, TERRA[6])
        put(img, cx - nk // 2, 0, TERRA[7])
    if label is not None and not round_ and h >= 6:
        ly = body_top + (H - 1 - body_top) // 2
        for x in range(bx0 + (1 if w > 3 else 0), bx0 + w - (1 if w > 3 else 0)):
            put(img, x, ly, label)
    put(img, bx0 + 1 if w > 2 else bx0, body_top + 1, GLASS[7])
    return add_outline(img)


def jar_img(w, h, fill):
    img = blank(w + 2, h + 3)
    for y in range(2, h + 2):
        for x in range(1, w + 1):
            put(img, x, y, fill[5 if (x + y) % 3 else 6] if y > 3 else GLASS[6])
    for x in range(1, w + 1):
        put(img, x, 1, TERRA[5])
    put(img, 1, 3, GLASS[7])
    return add_outline(img)


def shelf_items(sc, u0, u1, z):
    v = 5
    items = [(u0 + 8, bottle_img(3, 7, PINK, label=LINEN[8])), (u0 + 18, bottle_img(4, 6, TEAL, round_=True)),
             (u0 + 28, bottle_img(3, 9, GOLD, label=LINEN[7])), (u0 + 39, jar_img(5, 5, LEAF))]
    for uu, img in items:
        sc.sprite(img, uu, v, z, anchor=(0.5, 1.0), depth=(uu, v))


def herbs(sc):
    """右後牆、窗戶左邊：一根木桿掛幾束乾藥草（倒吊）。"""
    zr = 146
    sc.add(Box(14, 76, 3, 5, zr, zr + 2.5, wood_mat(WOOD, 5, seed=21)))
    for uu in (16, 72):
        sc.add(Box(uu, uu + 2, 0, 4, zr - 1, zr + 6, wood_mat(TIMBER, 4, seed=22)))
    kinds = [(22, LEAF, 5, 15), (34, PURPLE, 6, 12), (46, LEAF, 7, 17), (58, GOLD, 5, 11), (68, PINK, 5, 13)]
    for uu, rmp, b, ln in kinds:
        w = 7
        img = blank(w, ln + 2)
        cx = w // 2
        put(img, cx, 0, LINEN[4])
        put(img, cx, 1, LINEN[4])
        rect(img, cx - 1, 2, cx + 1, 3, LINEN[6])
        for y in range(4, ln + 2):
            f = (y - 4) / max(1, ln - 2)
            half = 0.8 + f * 2.4 * (1 - 0.6 * max(0, f - 0.75) / 0.25)
            for x in range(w):
                d = x - cx
                if abs(d) <= half:
                    k = b + (1 if d < -0.5 else -1 if d > 0.8 else 0) - (1 if (x * 3 + y * 5) % 7 == 0 else 0)
                    put(img, x, y, rmp[max(0, min(len(rmp) - 1, k))])
        img = add_outline(img)
        sc.sprite(img, uu, 4, zr, anchor=(0.5, 0.02), depth=(uu, 4))


def broom(sc):
    """右後牆角落：靠牆的掃帚（女巫的！）。"""
    img = blank(14, 62)
    for y in range(0, 46):
        x = 9 - y * 0.08
        put(img, int(round(x)), y, WOOD[6])
        put(img, int(round(x)) + 1, y, WOOD[4])
    for y in range(44, 62):
        f = (y - 44) / 17.0
        half = 2 + f * 4.2
        cx = 6.3
        for x in range(14):
            d = x - cx
            if abs(d) <= half:
                k = 6 if d < -1 else 4 if d > 1.5 else 5
                if (x + y) % 4 == 0:
                    k -= 1
                put(img, x, y, GOLD[k])
    rect(img, 4, 46, 9, 47, PURPLE[5])
    rect(img, 4, 48, 9, 48, PURPLE[3])
    img = add_outline(img)
    sc.sprite(img, 10, 14, 0, anchor=(0.45, 1.0), depth=(8, 12))


# ── 夜晚：暖光一圈一圈 ──

# 夜晚的光源（地板 uv、高 z、半徑、強度）：跟 gen_brew_room.py 的 PIECES glows 同一批（落地範圍左上角＋區域座標）。
NIGHT_LIGHTS = [
    (12, 302, 64, 46, 0.8),        # 書桌的蠟燭
    (90, 20, 50, 40, 0.8),         # 鍊金桌的酒精燈
    (278, 14, 66, 40, 0.65),       # 床頭櫃的水晶球
    (518, 24, 22, 96, 1.0),        # 壁爐
    (478, 14, 124, 30, 0.6),       # 壁爐台上的蠟燭（左）
    (556, 14, 120, 30, 0.6),       # 壁爐台上的蠟燭（右）
    (51, 123, 22, 40, 0.85),       # 衣櫃旁的蠟燭
    (413, 19, 22, 40, 0.85),       # 床邊的蠟燭
    (273, 373, 22, 40, 0.85),      # 藥水台旁的蠟燭
    (22, 382, 66, 52, 0.9),        # 左邊的燭台
    (582, 252, 66, 52, 0.9),       # 右邊的燭台
    (320, 242, 10, 60, 0.85),      # 鍋爐下的火
]


def night_grade(sc, rgb):
    """把白天畫好的房間殼調成夜晚：整體乘夜色，壁爐、蠟燭附近（照像素打到的 3D 位置算距離）一圈圈暖光（量化成色階＋交界抖動）。"""
    pos = sc.pos
    H, W = rgb.shape[:2]
    lv = np.zeros((H, W))
    # 光源：從 Glows 取（世界座標）。壁爐那顆最大。
    for (lu, lv_, lz, r, k) in NIGHT_LIGHTS:
        d = np.sqrt((pos[..., 0] - lu) ** 2 + (pos[..., 1] - lv_) ** 2 + ((pos[..., 2] - lz) * 1.2) ** 2)
        R = r * (2.9 if r >= 90 else 2.1)
        lv = lv + k * np.clip(1 - d / R, 0, 1) ** 1.4
    lv = np.clip(lv, 0, 1.2)
    bay = BAYER4[np.arange(H)[:, None] // 2 % 4, np.arange(W)[None, :] // 2 % 4]
    q = np.clip(np.floor(lv * 4 + bay * 0.45 + 0.3), 0, 4) / 4.0
    m0 = np.array(NIGHT_MUL)
    m1 = np.array([1.12, 0.88, 0.6])
    mul = m0[None, None, :] * (1 - q[..., None]) + m1[None, None, :] * q[..., None]
    out = np.clip(rgb.astype(np.float64) * mul, 0, 255)
    return out.astype(np.uint8), q


# ═══════════════════════════════ 家具登記 ═══════════════════════════════

def piece_scene(name):
    g = piece_geo(name)
    return Scene(g['W'], g['H'], g['ox'], g['oy'], g['gx'], g['gy']), g


DRAW = {}          # 圖名 → 函式(frame) → RGBA（全解析度，跟舊圖同尺寸）


def register(name, frames=1):
    def deco(fn):
        if frames == 1:
            DRAW[name] = lambda: fn(0)
        else:
            for i in range(frames):
                DRAW['%s-%d' % (name, i)] = (lambda k: (lambda: fn(k)))(i)
        return fn
    return deco




# ═══════════════════════════════ 家具共用 ═══════════════════════════════

def shadow_rect(sc, u0, u1, v0, v1, g=3.0):
    sc.ground_shadow(lambda U, V: (U > u0 - g + 2) & (U < u1 + g + 2) & (V > v0 - g + 1) & (V < v1 + g + 1))


def shadow_round(sc, cu, cv, r, rv=None):
    rv = rv or r
    sc.ground_shadow(lambda U, V: ((U - cu - 2) / r) ** 2 + ((V - cv - 1) / rv) ** 2 < 1)


def wbox(sc, u0, u1, v0, v1, z0, z1, rmp=WOOD, base=5, seed=1, grain='auto', plank=0, edge=True):
    b = (u0, u1, v0, v1, z0, z1)
    sc.add(Box(*b, wood_mat(rmp, base, grain_axis=grain, bevel_b=b, seed=seed, plank=plank), edge=edge))


def sbox(sc, u0, u1, v0, v1, z0, z1, rmp, base, k=3.6, extra=None, edge=True):
    b = (u0, u1, v0, v1, z0, z1)
    sc.add(Box(*b, solid_mat(rmp, base, k=k, b=b, extra=extra), edge=edge))


def cloth_mat(rmp, base, k=3.0, pattern=None, dither=0.0):
    def mat(c):
        idx = tone_idx(c, base, k, dither=dither)
        if pattern is not None:
            r = pattern(c, idx)
            if isinstance(r, tuple):
                return r[0]
            idx = r
        return pick(rmp, idx)
    return mat


def leg(sc, cu, cv, r, z0, z1, rmp=WOOD, base=4):
    sc.add(Cyl(cu, cv, r, z0, z1, solid_mat(rmp, base, k=3.2)))


def knob(sc, cu, cv, cz, r, rmp=BRASS, base=5):
    sc.add(Ell(cu, cv, cz, r, r, r, metal_mat(rmp, base, k=3.4)))


def star_mask(x, y, cx, cy, R, rot=-math.pi / 2):
    """五角星（2D）：x, y 陣列；R＝外半徑。"""
    dx, dy = x - cx, y - cy
    ang = np.arctan2(dy, dx) - rot
    r = np.hypot(dx, dy)
    k = np.abs(np.mod(ang + math.pi / 5, 2 * math.pi / 5) - math.pi / 5) / (math.pi / 5)   # 0＝尖角、1＝凹處
    return r < R * (1 - 0.55 * k)


def star_img(n=5, col=GOLD):
    """小星星立牌（n＝5 或 3）。"""
    if n >= 5:
        rows = ['..a..', '.aba.', 'abbba', '.aba.', 'a...a'] if False else ['..b..', '.bcb.', 'bcccb', '.bcb.', '.b.b.']
    else:
        rows = ['.b.', 'bcb', '.b.']
    return from_ascii(rows, {'b': col[4], 'c': col[6]})


# ═══════════════════════════════ 地毯 ═══════════════════════════════

@register('rug-circle')
def draw_rug_circle(f):
    """鍋爐下的圓形編織地毯：一圈圈辮子紋（梅紅／奶油／青綠／紫），中心一圈星星魔法陣。"""
    sc, g = piece_scene('rug-circle')
    R = 82.0
    cu, cv = g['du'] / 2, g['dv'] / 2

    def mat(c):
        r = np.hypot(c.u - cu, c.v - cv)
        ang = np.arctan2(c.v - cv, c.u - cu)
        band = np.floor((R - r) / 6.0)
        fr = (R - r) - band * 6.0
        cols = [PLUM, LINEN, TEAL, LINEN, PURPLE, GOLD, LINEN, PLUM]
        bases = [5, 6, 5, 7, 5, 5, 6, 6]
        out = np.zeros(c.u.shape + (3,), np.uint8)
        # 辮子紋：沿圓周的斜短紋（每段亮→暗）
        braid = np.mod(ang * r / 3.2 + fr * 0.9, 3.0)
        d = np.where(braid < 1.0, 1, np.where(braid > 2.2, -1, 0))
        d = d + np.where((fr < 0.9) | (fr > 5.1), -1, 0)
        inner = r < 30
        for k, (rmp, b) in enumerate(zip(cols, bases)):
            m = (band.astype(int) % len(cols)) == k
            out[m] = pick(rmp, b + d[m])
        # 中心：深藍底＋金色圓與五芒星點（大部分被鍋爐蓋住）
        mc = r < 36
        cidx = 3 + np.where(h32(np.floor(c.u / 2), np.floor(c.v / 2), 9) > 0.93, 2, 0)
        out[mc] = pick(BLUE, cidx[mc])
        ring = (np.abs(r - 33) < 1.2) | (np.abs(r - 28) < 0.8)
        out[ring & mc] = GOLD[5]
        for k in range(8):
            a0 = k * math.pi / 4 + math.pi / 8
            su, sv = cu + 31 * math.cos(a0), cv + 31 * math.sin(a0)
            st = np.abs(c.u - su) + np.abs(c.v - sv) < 2.4
            out[st] = GOLD[6]
        # 最外圈：深色收邊＋流蘇點
        edge = r > R - 2.5
        out[edge] = PLUM[3]
        return out
    sc.add(Cyl(cu, cv, R, -1, 0.5, mat, edge=False))
    return sc.finish()


@register('rug-star')
def draw_rug_star(f):
    """深藍星空長毯：金色雙邊框、一彎月亮、大小星星，兩頭流蘇。"""
    sc, g = piece_scene('rug-star')
    du, dv = g['du'], g['dv']

    def mat(c):
        u, v = c.u, c.v
        idx = 3 + np.where(fbm(u, v, 10, 41, 2) > 0.6, 1, 0)
        weave = (np.floor(u / 2) + np.floor(v / 2)) % 2 == 0
        idx = np.where(weave & (h32(np.floor(u / 2), np.floor(v / 2), 3) > 0.6), idx - 1, idx)
        col = pick(BLUE, idx)
        e = np.minimum(np.minimum(u, du - u), np.minimum(v - 5, dv - 5 - v))
        col = np.where(((e > 2) & (e < 4.5))[:, None], GOLD[4], col)
        col = np.where(((e > 6.5) & (e < 8))[:, None], GOLD[3], col)
        col = np.where((e <= 2)[:, None], BLUE[1], col)
        # 星星
        for (su, sv, R) in ((18, 26, 5.5), (46, 44, 3.2), (24, 64, 3.0), (44, 86, 5.0), (16, 92, 2.6), (52, 20, 2.4), (33, 102, 2.2)):
            st = star_mask(u, v, su, sv, R)
            col = np.where(st[:, None], GOLD[6], col)
            col = np.where((st & (np.hypot(u - su, v - sv) < R * 0.35))[:, None], GOLD[7], col)
        # 月亮
        moon = (np.hypot(u - 34, v - 56) < 9) & ~(np.hypot(u - 38, v - 52) < 8)
        col = np.where(moon[:, None], LINEN[8], col)
        col = np.where((moon & (np.hypot(u - 34, v - 56) > 7.5))[:, None], GOLD[5], col)
        # 小點點星
        dots = (h32(np.floor(u / 3), np.floor(v / 3), 77) > 0.96) & (e > 9)
        col = np.where(dots[:, None], BLUE[7], col)
        # 兩頭流蘇（v 的兩端）
        fr = (v < 5) | (v > dv - 5)
        fcol = np.where((np.mod(np.floor(u / 2), 2) == 0)[:, None], LINEN[7], LINEN[5])
        col = np.where(fr[:, None], fcol, col)
        return col
    sc.add(Box(0, du, 0, dv, -1, 0.5, mat, edge=False))
    # 流蘇的空隙（挖掉一點）
    img = sc.finish()
    return img


@register('rug-hearth')
def draw_rug_hearth(f):
    """壁爐前的橢圓辮子毯（暖橘紅）＋一個空的貓窩（圓圓的絨毛窩、奶油色軟墊、小腳印）。"""
    sc, g = piece_scene('rug-hearth')
    cu, cv = g['du'] / 2, g['dv'] / 2
    ru, rv = cu - 0.5, cv - 0.5

    def mat(c):
        e = np.hypot((c.u - cu) / ru, (c.v - cv) / rv)
        rr = (1 - e) * 34
        band = np.floor(rr / 5.0)
        fr = rr - band * 5
        ang = np.arctan2((c.v - cv) / rv, (c.u - cu) / ru)
        braid = np.mod(ang * 60 / 6.0 + fr * 0.9, 3.0)
        d = np.where(braid < 1.0, 1, np.where(braid > 2.2, -1, 0)) + np.where((fr < 0.8) | (fr > 4.2), -1, 0)
        cols = [ROSE, GOLD, TERRA, LINEN, ROSE, TERRA]
        bases = [4, 4, 5, 6, 5, 6]
        out = np.zeros(c.u.shape + (3,), np.uint8)
        for k, (rmp, b) in enumerate(zip(cols, bases)):
            m = (band.astype(int) % len(cols)) == k
            out[m] = pick(rmp, b + d[m])
        out[e > 0.965] = ROSE[2]
        return out
    sc.add(Cyl(cu, cv, ru, -1, 0.5, mat, rv=rv, edge=False))
    # 貓窩（區域座標）
    bu, bv = CAT_BED_UV[0] - g['piece']['U0'], CAT_BED_UV[1] - g['piece']['V0']
    sc.ground_shadow(lambda U, V: ((U - bu - 1.5) ** 2 + (V - bv - 1.5) ** 2) < (CAT_BED_R + 2) ** 2)

    def rim_mat(c):
        idx = tone_idx(c, 5, 3.2)
        fluff = h32(c.I, c.J, 31) > 0.7
        idx = np.where(fluff, idx + 1, idx)
        idx = np.where(c.face == F_CAP, idx - 1, idx)
        return pick(PLUM, idx + 1)

    def pad_mat(c):
        idx = tone_idx(c, 6, 2.0)
        du_, dv_ = c.u - bu, c.v - bv
        # 小腳印（一顆大肉球＋三顆小的）
        paw = (np.hypot(du_ - 1, dv_ - 1) < 2.2) | (np.hypot(du_ - 3.8, dv_ - 2.2) < 1.0) | \
              (np.hypot(du_ - 2.6, dv_ - 4.2) < 1.0) | (np.hypot(du_ + 0.2, dv_ - 4.4) < 1.0)
        col = pick(LINEN, idx + np.where(h32(c.I // 1, c.J, 5) > 0.8, -1, 0))
        col = np.where(paw[:, None], PINK[5], col)
        return col
    sc.add(Cyl(bu, bv, CAT_BED_R - 4.0, 0, 4.5, pad_mat))
    sc.add(Cyl(bu, bv, CAT_BED_R, 0, 8.0, rim_mat, r_in=CAT_BED_R - 4.4))
    return sc.finish(outline=True)


# ═══════════════════════════════ 床 ═══════════════════════════════

def quilt_pattern(u, v):
    """被子的拼布：12×12 的格子輪流紫／深藍／梅紅，有的格子繡金星；斜向絎縫線。回傳 (色盤編號, 色階差)。"""
    P = 15.0
    cu = np.floor((u - 3) / P)
    cvv = np.floor((v - 2) / P)
    pid = (cu + cvv).astype(int) % 2
    fu, fv = (u - 3) - cu * P, (v - 2) - cvv * P
    d = np.zeros(u.shape, int)
    seam = (fu < 1.0) | (fv < 1.0)
    d = np.where(seam, -1, d)
    puff = (np.abs(fu - P / 2) < 4.5) & (np.abs(fv - P / 2) < 4.5)
    d = np.where(puff, d + 1, d)
    stitch = (np.abs(fu - P / 2) < 0.6) & (np.mod(fv, 2.0) < 1.0) & ~seam
    d = np.where(stitch, d - 1, d)
    has_star = (pid == 1) & (h32(cu, cvv, 7) > 0.35)
    st = has_star & star_mask(fu, fv, P / 2, P / 2, 3.6)
    return pid, d, st


@register('bed')
def draw_bed(f):
    sc, g = piece_scene('bed')
    du, dv = g['du'], g['dv']            # 84 × 120：v=0 靠牆（床頭）
    shadow_rect(sc, 2, du - 2, 2, dv - 2, 3)
    # ── 床架 ──
    wbox(sc, 3, du - 3, 6, dv - 6, 10, 22, seed=3)               # 床箱
    # ── 床墊＋床單 ──
    def sheet_mat(c):
        idx = tone_idx(c, 7, 2.6)
        idx = np.where((c.face != F_TOP) & (c.z < 26), idx - 1, idx)
        return pick(LINEN, idx)
    sc.add(Box(5, du - 5, 8, dv - 8, 22, 32, sheet_mat))
    # ── 被子（垂到床箱兩側）──
    q0 = 46

    def quilt_mat(c):
        pid, d, st = quilt_pattern(c.u, c.v - q0)
        idx = tone_idx(c, 5, 3.0) + d
        top = c.face == F_TOP
        # 側面：垂下來的布邊有一點波浪＋金色滾邊
        side = ~top
        wav = np.where(c.face == F_U, np.sin(c.v * 0.6), np.sin(c.u * 0.6))
        idx = np.where(side & (wav > 0.4), idx - 1, idx)
        out = np.zeros(c.u.shape + (3,), np.uint8)
        for k, (rmp, sh) in enumerate(((PURPLE, 1), (BLUE, 0))):
            m = pid == k
            out[m] = pick(rmp, idx[m] + sh)
        out[st & top] = GOLD[6]
        hem = side & (c.z < 15.5)
        out[hem] = pick(GOLD, 4 + (c.face[hem] == F_V))
        return out
    sc.add(Box(2, du - 2, q0, dv - 5, 14, 35, quilt_mat))
    # 反折的床單（被子上緣一條白邊，帶一條淡紫線）
    def fold_mat(c):
        idx = tone_idx(c, 7, 2.6)
        line = np.abs(c.v - (q0 - 2.5)) < 0.9
        col = pick(LINEN, idx)
        col = np.where(line[:, None], PURPLE[7], col)
        return col
    sc.add(HCyl('u', q0 - 1, 35, 4.2, 3, du - 3, fold_mat, rz=3.2))
    # ── 枕頭（兩顆圓滾滾的＋一顆粉紅愛心小抱枕）──
    def pillow_mat(rmp, base):
        def m(c):
            idx = tone_idx(c, base, 3.4)
            stripe = (np.mod(c.u, 6) < 1) & (rmp is LINEN)
            idx = np.where(stripe, idx - 1, idx)
            return pick(rmp, idx)
        return m
    sc.add(Ell(24, 22, 36, 17, 10, 7.5, pillow_mat(LINEN, 7)))
    sc.add(Ell(60, 22, 36, 17, 10, 7.5, pillow_mat(LINEN, 7)))
    sc.add(Ell(44, 34, 38, 9, 5, 7, pillow_mat(PINK, 5)))
    # 被子上的星星小抱枕（立牌）
    star = from_ascii(['....a....', '...aba...', 'aaabcbaaa', '.abcccba.', '..abcba..', '.abbabba.', 'aba...aba'],
                      {'a': GOLD[2], 'b': GOLD[5], 'c': GOLD[7]})
    sc.sprite(add_outline(star), 30, 80, 35, anchor=(0.5, 0.9), depth=(30, 82))
    # ── 床頭板（拱形、紫絨鑲板、金色星月）──
    def head_mat(c):
        idx = tone_idx(c, 5, 3.6)
        # 拱頂是一層層薄板疊的：頂面跟正面同色，才不會變成一條條橫紋
        idx = np.where((c.face == F_TOP) & (c.z > 61), 5, idx)
        front = (c.face == F_V) | ((c.face == F_TOP) & (c.z > 61))
        a = c.u - du / 2
        panel = front & (np.abs(a) < 30) & (c.z > 30) & (c.z < 58 + 10 * np.sqrt(np.clip(1 - (a / 30) ** 2, 0, 1)))
        col = pick(WOOD, idx + np.where(c.z > 74, 1, 0))
        pidx = 4 + np.where(np.abs(a) < 26, 1, 0)
        btn = panel & (np.mod(a + 30, 10) < 1.6) & (np.abs(np.mod(c.z - 30, 10) - 5) < 1.2)
        pc = pick(PURPLE, pidx + np.where(np.mod(a + c.z, 10) < 5, 0, 0))
        col = np.where(panel[:, None], pc, col)
        col = np.where(btn[:, None], PURPLE[7], col)
        moon = front & (np.hypot(a, c.z - 62) < 6) & ~(np.hypot(a - 2.5, c.z - 64) < 5.2)
        col = np.where(moon[:, None], GOLD[6], col)
        for sa, sz in ((-14, 66), (13, 68), (-8, 74), (9, 59)):
            st = front & (np.abs(a - sa) + np.abs(c.z - sz) < 1.6)
            col = np.where(st[:, None], GOLD[7], col)
        rimp = front & panel & ~(np.abs(a) < 28.5)
        col = np.where(rimp[:, None], GOLD[4], col)
        return col
    sc.add(Box(0, du, 0, 6, 10, 62, head_mat))
    for k in range(8):
        z = 62 + k * 2
        w = (du / 2 - 4) * math.sqrt(max(0.0, 1 - ((k + 1) / 9.0) ** 2))
        sc.add(Box(du / 2 - w, du / 2 + w, 0, 6, z, z + 2, head_mat, edge=False))
    # ── 床尾板（低、中間一顆星）──
    def foot_mat(c):
        idx = tone_idx(c, 5, 3.6) + bevel(c, (0, du, dv - 7, dv, 8, 40)).astype(int)
        front = c.face == F_V
        a = c.u - du / 2
        inset = front & (np.abs(a) < 30) & (c.z > 15) & (c.z < 34)
        idx = np.where(inset, idx - 1, idx)
        idx = np.where(front & (np.abs(np.abs(a) - 30) < 0.8) & (c.z > 15) & (c.z < 34), idx + 2, idx)
        col = pick(WOOD, idx)
        st = front & star_mask(a, c.z, 0, 25, 6.5, rot=math.pi / 2)
        col = np.where(st[:, None], GOLD[5], col)
        col = np.where((st & star_mask(a, c.z, -0.6, 25.6, 3.2, rot=math.pi / 2))[:, None], GOLD[7], col)
        return col
    sc.add(Box(0, du, dv - 7, dv, 8, 40, foot_mat))
    # ── 四根柱子（床尾兩根短的，床頭兩根長的頂著半罩帳）＋金色圓頭 ──
    for (pu, pv, top) in ((4, 4, 120), (du - 4, 4, 120), (4, dv - 4, 46), (du - 4, dv - 4, 46)):
        sc.add(Cyl(pu, pv, 4.2, 0, top, wood_mat(WOOD, 5, grain_axis='z', seed=int(pu + pv))))
        sc.add(Cyl(pu, pv, 5.2, top - 4, top - 1, solid_mat(WOOD, 6, k=3.0)))
        knob(sc, pu, pv, top + 3, 4.6, GOLD, 5)
    # ── 半罩帳（貼牆的木冠＋兩側垂下的紫紗帳，金色綁帶）──
    def crown_mat(c):
        idx = tone_idx(c, 5, 3.6) + bevel(c, (-2, du + 2, 0, 16, 128, 138)).astype(int)
        col = pick(WOOD, idx)
        front = c.face == F_V
        trim = front & (np.abs(c.z - 131) < 1.0)
        col = np.where(trim[:, None], GOLD[5], col)
        return col
    sc.add(Box(-2, du + 2, 0, 16, 128, 138, crown_mat))

    def drape_mat(c):
        a = np.where(c.face == F_U, -c.v, c.u)
        fold = np.sin(a * 1.1 + c.z * 0.02)
        idx = tone_idx(c, 5, 3.0) + np.round(fold * 1.1).astype(int)
        col = pick(PURPLE, idx)
        sheer = h32(c.I, c.J, 11) > 0.85
        col = np.where(sheer[:, None], pick(PURPLE, idx + 1), col)
        return col
    # 垂帳頂端的荷葉邊（木冠前緣，沿 u）
    def valance_mat(c):
        sc_ = 128 - 2.5 * np.abs(np.sin(c.u * math.pi / 10.5))
        idx = tone_idx(c, 6, 3.0) - np.where(c.z < sc_ + 2, 1, 0)
        col = pick(PURPLE, idx)
        fringe = c.z < sc_ + 0.8
        col = np.where(fringe[:, None], GOLD[5], col)
        return col
    sc.add(Box(-2, du + 2, 15, 18, 121, 130, valance_mat, edge=False))
    for (ua, ub) in ((-1, 5), (du - 5, du + 1)):
        # 上半：從木冠垂下（寬）
        sc.add(Box(ua, ub, 1, 18, 70, 128, drape_mat))
        # 下半：被綁帶束起，往後收窄
        sc.add(Box(ua + 1, ub - 1, 1, 9, 24, 70, drape_mat))
        sc.add(Box(ua, ub, 1, 12, 64, 70, solid_mat(GOLD, 5, k=3.0)))
    return sc.finish()


# ═══════════════════════════════ 鍋爐（6 幀）═══════════════════════════════

def bubble_img(r, rmp=TEAL):
    s = 2 * r + 3
    img = blank(s, s)
    ball(img, r + 1, r + 1, r + 0.4, r + 0.4, rmp, 6, spec=True)
    add_outline(img, color=rmp[2])
    return img


@register('cauldron', frames=6)
def draw_cauldron(f):
    sc, g = piece_scene('cauldron')
    cu, cv = 32.0, 32.0
    shadow_round(sc, cu, cv, 30)
    ph = f / 6.0 * 2 * math.pi
    # ── 底下的柴火（交叉兩根）──
    sc.add(HCyl('v', cu - 4, 3.5, 3.2, cv - 16, cv + 14, wood_mat(WOOD, 4, seed=4)))
    sc.add(HCyl('u', cv + 3, 4.5, 3.2, cu - 16, cu + 15, wood_mat(WOOD, 5, seed=5)))
    # ── 三隻腳 ──
    for k in range(3):
        a = k * 2 * math.pi / 3 + math.pi / 6
        leg(sc, cu + 17 * math.cos(a), cv + 17 * math.sin(a), 2.6, 0, 18, IRON, 4)
    flick = [0, 1, 0, 1, 1, 0][f]

    def body_mat(c):
        lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
        idx = 4 + (lit - 0.45) * 4.6
        idx = np.where(lit > 0.9, 8.5, idx)
        col = pick(IRON, np.round(idx))
        # 火光：鍋身下緣反橘光（隨幀一明一暗）
        fire = c.z < 15 + flick * 2
        fidx = np.where(c.z < 11, 3, 2) + np.where((h32(c.I, c.J, 3) > 0.75), 1, 0)
        col = np.where(fire[:, None], pick(COPPER, fidx - (c.nx + c.ny < 0.2)), col)
        band = np.abs(c.z - 44) < 1.6
        col = np.where(band[:, None], pick(IRON, np.round(idx) + 2), col)
        ang = np.arctan2(c.v - cv, c.u - cu)
        rivet = band & (np.mod(ang * 26 / (2 * math.pi), 1.0) < 0.25)
        col = np.where(rivet[:, None], BRASS[6], col)
        fx = (c.u - c.v)
        front = (c.nx + c.ny) > 0.85
        moon = front & (np.hypot(fx, (c.z - 28) * 1.1) < 7.5) & ~(np.hypot(fx - 3.4, (c.z - 30.5) * 1.1) < 6.4)
        col = np.where(moon[:, None], pick(GOLD, np.where(fx < -2, 6, 5)), col)
        for (sx, sz) in ((9, 34), (-10, 22), (11, 20)):
            st = front & (np.abs(fx - sx) + np.abs(c.z - sz) < 1.7)
            col = np.where(st[:, None], GOLD[6], col)
        # 液面（切開的頂）
        cap = c.face == F_CAP
        r = np.hypot(c.u - cu, c.v - cv)
        ang2 = np.arctan2(c.v - cv, c.u - cu)
        swirl = np.sin(ang2 * 2 - r * 0.32 + ph) + 0.5 * np.sin(r * 0.7 - ph * 2)
        lidx = 5 + np.where(swirl > 0.7, 1, 0) + np.where(swirl > 1.25, 1, 0) - np.where(swirl < -0.9, 1, 0)
        # 中間偏後有一塊亮亮的反光（魔法在發光）
        glow_ = np.hypot(c.u - cu + 4, c.v - cv + 4) < 6
        lidx = np.where(glow_, lidx + 1, lidx)
        lidx = np.where(r > 17.0, 4, lidx)
        lidx = np.where(r > 18.4, 3, lidx)
        lcol = pick(TEAL, lidx)
        lcol = np.where((r > 19.6)[:, None], IRON[2], lcol)
        col = np.where(cap[:, None], lcol, col)
        return col
    sc.add(Ell(cu, cv, 34, 27, 27, 25, body_mat, zcut=53))

    def rim_mat(c):
        lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
        idx = np.where(c.face == F_TOP, 6, np.where(c.face == F_CAP, 2, 4 + (lit - 0.4) * 4))
        ang = np.arctan2(c.v - cv, c.u - cu)
        idx = np.where((c.face == F_TOP) & (np.abs(ang + 2.36) < 0.9), 8, idx)
        return pick(IRON, np.round(idx))
    sc.add(Cyl(cu, cv, 23.5, 50, 56, rim_mat, r_in=19.6))
    # 兩個把手（鐵環）
    for (hu, hv) in ((cu + 24, cv - 6), (cu - 6, cv + 24)):
        img = from_ascii(['.aaa.', 'ab.ba', 'a...a', '.aaa.'], {'a': IRON[5], 'b': IRON[7]})
        sc.sprite(add_outline(img), hu, hv, 46, anchor=(0.5, 0.5), depth=(hu + 6, hv + 6))
    # ── 液面上的泡泡：慢慢長大、破掉，每幀不一樣 ──
    spots = [(0.0, -6, 3), (0.34, 7, -6), (0.67, -2, 10), (0.17, 10, 5), (0.5, -10, -3), (0.84, 3, -1)]
    for k, (p0, du_, dv_) in enumerate(spots):
        t = (f / 6.0 + p0) % 1.0
        bu, bvv = cu + du_, cv + dv_
        if t < 0.5:
            r = 1 if t < 0.15 else 2 if (t < 0.35 or k % 2) else 3
            img = blank(2 * r + 1, 2 * r + 1)
            ball(img, r, r, r + 0.3, r + 0.3, TEAL, 7, spec=False)
            img[0, r, :3] = TEAL[9]
            add_outline(img, color=TEAL[3])
            sc.sprite(img, bu, bvv, 53.6, anchor=(0.5, 0.7), depth=(bu + 1, bvv + 1), edge=False)
        elif t < 0.67:
            ring = from_ascii(['.a.a.', 'a...a', '.a.a.'], {'a': TEAL[8]})
            sc.sprite(ring, bu, bvv, 53.5, anchor=(0.5, 0.5), depth=(bu + 1, bvv + 1), edge=False)
    # ── 往上飄的蒸氣（一小團一小團）＋星光 ──
    for k in range(3):
        t = (f / 6.0 + k / 3.0) % 1.0
        a = k * 2.1 + 0.6
        bu, bvv = cu + 6 * math.cos(a) - 3, cv + 6 * math.sin(a) - 3
        z = 58 + t * 24
        w = 3 if t < 0.5 else 2
        puff = blank(w * 2 + 1, w + 1)
        ball(puff, w, w / 2.0, w + 0.2, w / 2.0 + 0.3, TEAL, 8, spec=False, rim_dark=False)
        if t > 0.75:
            puff[..., 3] = np.where((np.arange(puff.shape[1])[None, :] + np.arange(puff.shape[0])[:, None]) % 2 == 0, puff[..., 3], 0)
        sc.sprite(puff, bu + math.sin(t * 5 + k) * 2, bvv, z, anchor=(0.5, 0.5), depth=(cu + 40, cv + 40), edge=False)
    for k in range(2):
        t = (f / 6.0 + k * 0.5 + 0.25) % 1.0
        bu, bvv = cu + (6 if k else -8), cv + (-6 if k else 4)
        img = from_ascii(['.a.', 'aba', '.a.'], {'a': PINK[6], 'b': LINEN[9]}) if t < 0.6 else from_ascii(['a'], {'a': PINK[7]})
        sc.sprite(img, bu, bvv, 60 + t * 22, anchor=(0.5, 0.5), depth=(cu + 40, cv + 40), edge=False)
    # ── 底下的火苗（從鍋底下冒出來，排在鍋身前面）──
    for k, (fu, fv) in enumerate(((cu - 2, cv + 16), (cu + 16, cv - 2), (cu + 9, cv + 9), (cu - 12, cv + 10), (cu + 10, cv - 12))):
        hgt = 6 + ((f + k * 2) % 3) * 2
        img = flame_img(hgt, 5, f + k)
        sc.sprite(img, fu, fv, 1, anchor=(0.5, 1.0), depth=(fu + 4, fv + 4), edge=False)
    return sc.finish()


# ═══════════════════════════════ 壁爐＋爐火 ═══════════════════════════════

FP_OPEN = (30, 72, 52)        # 火口：u 範圍與拱頂高（在 v=FP_D 的正面）
FP_D = 18                     # 爐身深度（v），前面再鋪一塊爐台石


@register('fireplace')
def draw_fireplace(f):
    sc, g = piece_scene('fireplace')
    du, dv = g['du'], g['dv']                # 96 × 36
    shadow_rect(sc, 0, du, 0, dv, 2)
    o0, o1, oh = FP_OPEN
    oc, ow = (o0 + o1) / 2, (o1 - o0) / 2

    def opening(u, z):
        top = oh - 10 + 10 * np.sqrt(np.clip(1 - ((u - oc) / ow) ** 2, 0, 1))
        return (u > o0) & (u < o1) & (z > 5) & (z < top), top

    def stone_mat(seed, rmp=WSTONE, base=5, front_open=False):
        def mat(c):
            a = face_a(c)
            h = np.where(c.face == F_TOP, (c.u + c.v) * 0.5, c.z)
            rows = np.floor(h / 9.0)
            off = (rows % 2) * 7
            col_ = np.floor((a + off) / 14.0)
            fa = (a + off) - col_ * 14.0
            fz = h - rows * 9.0
            sv = h32(col_, rows, seed)
            idx = tone_idx(c, base, 3.4) + np.where(sv > 0.72, 1, 0) - np.where(sv < 0.25, 1, 0)
            idx = np.where(fz > 6.8, idx + 1, idx)
            idx = np.where(fa > 12.2, idx - 1, idx)
            mort = np.hypot(np.maximum(0, np.abs(fa - 7.2) - 5.0), np.maximum(0, np.abs(fz - 4.6) - 2.6)) > 1.7
            idx = np.where(mort, base - 2, idx)
            hue = h32(col_, rows, seed + 1)
            out = np.where((hue > 0.66)[:, None], pick(STONE, idx + 1), pick(rmp, idx))
            if front_open:
                front = c.face == F_V
                op, top = opening(c.u, c.z)
                op &= front
                # 火口裡面：深色的爐膛，後壁磚被火照亮（越下面越亮）
                depth_lit = np.clip((top - c.z) / (top - 5), 0, 1)
                brick = (np.mod(np.floor(c.z / 4) * 3 + np.floor((c.u + np.mod(np.floor(c.z / 4), 2) * 3) / 6), 2) == 0)
                fidx = np.round(1 + depth_lit * 2.2).astype(int) + np.where(brick, 0, -1)
                inner = pick(ROSE, fidx)
                rimm = op & ((c.z > top - 2.2) | (np.abs(c.u - o0) < 2.2) | (np.abs(c.u - o1) < 2.2))
                inner = np.where(rimm[:, None], IRON[1], inner)
                out = np.where(op[:, None], inner, out)
                # 拱頂的楔石
                key = front & (np.abs(c.u - oc) < 4) & (c.z > oh - 1) & (c.z < oh + 7)
                out = np.where(key[:, None], pick(WSTONE, 7 - (np.abs(c.u - oc) > 2.5)), out)
                arch = front & ~op & (np.abs(np.hypot((c.u - oc) / (ow + 4), (c.z - (oh - 10)) / 14.0) - 1) < 0.08) & (c.z > oh - 10)
                out = np.where(arch[:, None], pick(WSTONE, 7 + 0 * c.z), out)
            return out
        return mat
    # 爐身（石）
    sc.add(Box(0, du, 0, FP_D, 0, 100, stone_mat(11, front_open=True)))
    # 爐台石（前面低低一塊）
    hb = (-2, du + 2, FP_D, dv, 0, 5)
    sc.add(Box(*hb, stone_mat(13, DSTONE, 6)))
    # 爐膛裡的柴架與木柴（火在另一張圖上，這裡是底下的炭）
    sc.add(HCyl('u', FP_D - 4, 5.5, 3, o0 + 6, o1 - 6, wood_mat(WOOD, 3, seed=6)))
    sc.add(HCyl('u', FP_D - 1, 8, 2.6, o0 + 10, o1 - 10, wood_mat(WOOD, 4, seed=7)))
    for uu in (o0 + 8, o1 - 8):
        sc.add(Box(uu - 1, uu + 1, FP_D - 8, FP_D + 1, 0, 11, solid_mat(IRON, 4, k=3.0)))
        knob(sc, uu, FP_D + 0.5, 12, 1.8, BRASS, 5)
    # 壁爐台（木）＋煙囪胸（灰泥＋木框）
    mb = (-4, du + 4, -2, FP_D + 8, 100, 107)
    wbox(sc, *mb, seed=8)
    sc.add(Box(-1, du + 1, 0, FP_D + 4, 95, 100, wood_mat(WOOD, 4, seed=9)))

    def chimney_mat(c):
        front = c.face == F_V
        col = stone_mat(17)(c)
        # 正面掛一面圓鏡（金框、粉紅蝴蝶結）
        a, z = c.u - du / 2, c.z
        r = np.hypot(a * 0.95, z - 128)
        frame = front & (r < 12) & (r >= 9.5)
        glass = front & (r < 9.5)
        gcol = pick(GLASS, np.where((a + (z - 128)) < -4, 6, 4))
        gl = glass & (np.abs((a - (z - 128)) + 3) < 1.6)
        col = np.where(glass[:, None], gcol, col)
        col = np.where(gl[:, None], GLASS[7], col)
        col = np.where(frame[:, None], pick(GOLD, np.where(z > 128, 5, 4)), col)
        bow = front & (np.abs(a) < 4) & (np.abs(z - 141) < 2.2) & ~(np.abs(a) < 1)
        col = np.where(bow[:, None], PINK[5], col)
        col = np.where((front & (np.abs(a) < 1) & (np.abs(z - 141) < 1.6))[:, None], PINK[3], col)
        return col
    sc.add(Box(14, du - 14, 0, 13, 107, 148, chimney_mat))
    wbox(sc, 12, du - 12, 0, 15, 148, 153, base=5, seed=10)
    # 壁爐台上的東西：兩根蠟燭（光暈在 (8,14,124)、(86,14,120)）、小時鐘、星星罐、小盆栽
    for (uu, hgt) in ((8, 9), (86, 7)):
        sc.add(Cyl(uu, 14, 3.4, 107, 109, metal_mat(BRASS, 5)))
        sc.sprite(add_outline(candle_img(hgt, 0, flame_h=4)), uu, 14, 109, anchor=(0.5, 1.0), depth=(uu, 14))
    clock = from_ascii(['..aaaaa..', '.abbbbba.', 'abbcccbba', 'abccdccba', 'abccdccba', 'abccddcba', 'abbcccbba',
                        '.abbbbba.', '.aaaaaaa.', 'aa.....aa'],
                       {'a': WOOD[2], 'b': WOOD[6], 'c': LINEN[8], 'd': IRON[2]})
    sc.sprite(add_outline(clock), 40, 12, 107, anchor=(0.5, 1.0), depth=(40, 12))
    sc.sprite(jar_img(5, 6, GOLD), 58, 12, 107, anchor=(0.5, 1.0), depth=(58, 12))
    sc.sprite(bottle_img(3, 7, PINK, label=LINEN[8]), 68, 12, 107, anchor=(0.5, 1.0), depth=(68, 12))
    pot = from_ascii(['.e.e.e.', 'eefefee', '.efeef.', '..eee..', '.ccccc.', '.cdddc.', '..ccc..'],
                     {'c': TERRA[5], 'd': TERRA[3], 'e': LEAF[5], 'f': LEAF[7]})
    sc.sprite(add_outline(pot), 24, 12, 107, anchor=(0.5, 1.0), depth=(24, 12))
    # 壁爐台前緣垂一串小葉子花環＋小金星
    gar = blank(56, 9)
    for x in range(56):
        y = int(round(2 + 3 * math.sin(math.pi * (x % 28) / 28.0)))
        put(gar, x, y, LEAF[4 + (x % 3 == 0)])
        put(gar, x, y + 1, LEAF[3])
        if x % 4 == 1:
            put(gar, x, y - 1, LEAF[6])
        if x % 9 == 4:
            put(gar, x, y + 2, GOLD[6])
            put(gar, x, y + 3, GOLD[4])
    sc.sprite(add_outline(gar, color=LEAF[0]), du / 2 + 4, FP_D + 8.5, 102, anchor=(0.5, 0.2), depth=(du / 2, FP_D + 9))
    return sc.finish()


@register('fireplace-fire', frames=2)
def draw_fireplace_fire(f):
    """爐火（不乘夜色、會疊在壁爐上）：兩幀交替的火舌，底下一排紅炭。"""
    g = piece_geo('fireplace-fire-0')
    W, H = g['W'], g['H']
    LW, LH = (W + g['gx'] + 1) // 2 + 1, (H + g['gy'] + 1) // 2 + 1
    img = blank(LW, LH)
    base_y = (H - 6 + g['gy']) // 2          # 炭在畫布底部往上一點
    cx = (W / 2 + g['gx']) / 2.0 - 0.5
    rng_ = [(-4.0, 9, 0.0), (-1.2, 14, 1.0), (1.6, 18, 2.0), (4.2, 12, 3.0), (6.4, 8, 4.0)]
    for (dx, hgt, ph) in rng_:
        hgt = hgt + (2 if (f + int(ph)) % 2 == 0 else -1)
        sway = (1 if f == 0 else -1) * (0.6 if int(ph) % 2 else -0.4)
        for y in range(hgt):
            fy = y / max(1, hgt - 1)             # 0 底 → 1 頂
            half = 2.6 * (1 - fy) ** 0.8 + 0.3
            xc = cx + dx + sway * fy * 2
            for x in range(LW):
                d = abs(x - xc)
                if d <= half:
                    t = 7 if (d < half * 0.35 and fy < 0.55) else 6 if d < half * 0.7 else 4
                    if fy > 0.75:
                        t -= 1
                    yy = base_y - y
                    if 0 <= yy < LH:
                        cur = img[yy, x]
                        if cur[3] == 0 or t > 0:
                            img[yy, x, :3] = FIRE[max(t, 3)]
                            img[yy, x, 3] = 255
    # 火星（往上飄）
    for k, (dx, dy) in enumerate(((-3, 20), (3, 23), (0, 22), (5, 17))):
        if (k + f) % 2 == 0:
            put(img, int(cx + dx), base_y - dy, FIRE[7])
    # 炭
    for x in range(int(cx - 7), int(cx + 9)):
        put(img, x, base_y + 1, FIRE[2] if (x + f) % 3 else FIRE[5])
        put(img, x, base_y + 2, IRON[2] if x % 2 else FIRE[1])
    big = img.repeat(2, 0).repeat(2, 1)[g['gy']:g['gy'] + H, g['gx']:g['gx'] + W].copy()
    return big


# ═══════════════════════════════ 衣櫃 ═══════════════════════════════

@register('wardrobe')
def draw_wardrobe(f):
    sc, g = piece_scene('wardrobe')
    du, dv = g['du'], g['dv']            # 36 × 80，正面朝 +u
    shadow_rect(sc, 0, du, 0, dv, 2)
    for (pu, pv) in ((du - 5, 5), (du - 5, dv - 5), (5, dv - 5)):
        sc.add(Ell(pu, pv, 3.5, 4.5, 4.5, 4.2, solid_mat(WOOD, 4, k=3.0)))

    def body_mat(c):
        idx = tone_idx(c, 5, 3.6) + bevel(c, (2, du - 2, 2, dv - 2, 6, 166)).astype(int)
        front = c.face == F_U
        a = c.v
        # 兩扇門（拱形鑲板、金色星月、銅把手）＋底下一個抽屜
        door = front & (c.z > 44) & (c.z < 158) & (a > 6) & (a < dv - 6)
        mid = np.abs(a - dv / 2) < 1.0
        idx = np.where(door & mid, 2, idx)
        da = np.where(a < dv / 2, a - (6 + 17), a - (dv / 2 + 17))
        ptop = 132 + 9 * np.sqrt(np.clip(1 - (da / 13.0) ** 2, 0, 1))
        panel = door & (np.abs(da) < 13) & (c.z > 54) & (c.z < ptop)
        pedge = door & (np.abs(da) < 14.2) & (c.z > 53) & (c.z < ptop + 1.2) & ~panel
        idx = np.where(panel, idx - 1, idx)
        idx = np.where(pedge & ((c.z > ptop - 0.5) | (da < 0)), idx + 2, idx)
        idx = np.where(pedge & ~((c.z > ptop - 0.5) | (da < 0)), idx - 2, idx)
        drawer = front & (c.z > 14) & (c.z < 40) & (a > 6) & (a < dv - 6)
        dedge = drawer & ((c.z < 15.5) | (c.z > 38.5) | (a < 7.5) | (a > dv - 7.5))
        idx = np.where(dedge, 3, idx)
        col = pick(WOOD, idx)
        # 門上的雕花：左門月亮、右門星星（金）
        moon = panel & (np.hypot(da, c.z - 112) < 6.5) & ~(np.hypot(da - 2.8, c.z - 114) < 5.6) & (a < dv / 2)
        col = np.where(moon[:, None], GOLD[5], col)
        st = panel & star_mask(da, c.z, 0, 112, 7.0, rot=math.pi / 2) & (a > dv / 2)
        col = np.where(st[:, None], GOLD[5], col)
        dia = panel & (np.abs(da) + np.abs(c.z - 76) * 0.8 < 5)
        col = np.where(dia[:, None], pick(GOLD, 4 - (np.abs(da) + np.abs(c.z - 76) * 0.8 > 3.5)), col)
        # 銅把手與鑰匙孔
        kn = front & (np.abs(c.z - 96) < 2.2) & ((np.abs(a - (dv / 2 - 4)) < 1.6) | (np.abs(a - (dv / 2 + 4)) < 1.6))
        col = np.where(kn[:, None], BRASS[6], col)
        dk = drawer & (np.abs(c.z - 27) < 2.0) & (np.abs(a - dv / 2) < 5)
        col = np.where(dk[:, None], BRASS[5], col)
        dk2 = drawer & (np.abs(c.z - 27.5) < 0.9) & (np.abs(a - dv / 2) < 4)
        col = np.where(dk2[:, None], BRASS[7], col)
        # 側面（+v 面）：直條木紋
        side = c.face == F_V
        pl = side & (np.mod(c.u, 8) < 1.0)
        col = np.where(pl[:, None], pick(WOOD, idx - 1), col)
        return col
    sc.add(Box(2, du - 2, 2, dv - 2, 6, 166, body_mat))
    # 冠頂（多一圈線腳）＋中間拱形的頂飾
    wbox(sc, 0, du, 0, dv, 166, 172, seed=21)
    wbox(sc, 1, du - 1, 1, dv - 1, 172, 175, base=4, seed=22)
    for k in range(6):
        z = 175 + k * 2
        w = 16 * math.sqrt(max(0.0, 1 - ((k + 1) / 7.0) ** 2))
        sc.add(Box(du - 6, du - 2, dv / 2 - w, dv / 2 + w, z, z + 2, wood_mat(WOOD, 6, seed=23), edge=False))
    crest = from_ascii(['..a..', '.aba.', 'abcba', '.aba.', '..a..'], {'a': GOLD[3], 'b': GOLD[5], 'c': GOLD[7]})
    sc.sprite(add_outline(crest), du - 2, dv / 2, 182, anchor=(0.5, 0.5), depth=(du, dv / 2))
    # 頂上：一頂女巫帽、一個帽盒
    hat = from_ascii(['........aa.....', '.......abba....', '......abbba....', '.....abbcba....', '.....abbbba....',
                      '....abbbbbba...', '....adddddda...', '..aabbbbbbbbaa.', 'abbbbbbbbbbbbba', '.aaaaaaaaaaaaa.'],
                     {'a': PURPLE[1], 'b': PURPLE[4], 'c': PURPLE[6], 'd': GOLD[5]})
    sc.sprite(add_outline(hat), du / 2 + 2, 24, 175, anchor=(0.5, 1.0), depth=(du / 2 + 2, 26))
    sc.add(Cyl(du / 2, 58, 9, 175, 185, cloth_mat(PINK, 5, k=3.0,
                                                     pattern=lambda c, i: np.where(np.abs(c.z - 181) < 1.2, 8, i))))
    return sc.finish()


# ═══════════════════════════════ 書櫃 ═══════════════════════════════

BOOK_COLS = [PURPLE, ROSE, TEAL, BLUE, GOLD, LEAF, PLUM, TERRA]


@register('bookshelf')
def draw_bookshelf(f):
    sc, g = piece_scene('bookshelf')
    du, dv = g['du'], g['dv']            # 26 × 70，開口朝 +u
    shadow_rect(sc, 0, du, 0, dv, 2)
    TOP = 138
    wbox(sc, 0, 4, 0, dv, 0, TOP, base=3, seed=31)                 # 背板
    wbox(sc, 0, du, 0, 4, 0, TOP, seed=32)                          # 側板（遠）
    wbox(sc, 0, du, dv - 4, dv, 0, TOP, seed=33)                    # 側板（近）
    wbox(sc, 0, du + 1, -1, dv + 1, TOP, TOP + 5, base=6, seed=34)  # 頂
    wbox(sc, 0, du, 4, dv - 4, 0, 6, base=4, seed=35)               # 底座
    shelves = [6, 40, 74, 108]
    for z in shelves[1:]:
        wbox(sc, 4, du, 4, dv - 4, z - 3, z, base=6, seed=int(z))
    rnd = lambda *a: hs(*a)  # noqa: E731
    # 書：一本本獨立的盒子，書背在 +u 面（有書名條、金線）
    for si, z in enumerate(shelves):
        v = 5.0
        k = 0
        while v < dv - 6:
            r1 = rnd(si, k, 1)
            if si == 1 and 30 < v < 44:            # 第二層中間放一個罐子
                sc.add(Cyl(14, v + 6, 5.5, z, z + 12, solid_mat(GLASS, 5, k=3.0)))
                sc.add(Cyl(14, v + 6, 5.0, z, z + 8, solid_mat(PINK, 5, k=3.0)))
                sc.add(Cyl(14, v + 6, 4.0, z + 12, z + 14, solid_mat(TERRA, 5, k=3.0)))
                v += 14
                k += 1
                continue
            if si == 3 and 40 < v < 54:            # 第四層：水晶簇
                for (cu_, cv_, h_) in ((12, v + 4, 12), (15, v + 8, 8), (10, v + 9, 6)):
                    sc.add(Cyl(cu_, cv_, 2.2, z, z + h_, solid_mat(PURPLE, 6, k=4.0)))
                    sc.add(Ell(cu_, cv_, z + h_, 2.2, 2.2, 2.4, solid_mat(PURPLE, 8, k=3.0)))
                v += 14
                k += 1
                continue
            th = 3 + int(r1 * 3)
            hgt = 18 + int(rnd(si, k, 2) * 10)
            if si == 0:
                hgt = min(hgt, 30)
            rmp = BOOK_COLS[int(rnd(si, k, 3) * len(BOOK_COLS))]
            dep = 16 + int(rnd(si, k, 4) * 4)
            lean = (si == 2 and k == 3)
            bb = (4, 4 + dep, v, v + th, z, z + hgt)

            def book_mat(c, rmp=rmp, bb=bb, hgt=hgt, z=z, seed=k * 7 + si):
                idx = tone_idx(c, 4, 3.4)
                spine = c.face == F_U
                rel = c.z - z
                band = spine & ((np.abs(rel - hgt * 0.2) < 1.0) | (np.abs(rel - hgt * 0.8) < 1.0))
                lab = spine & (np.abs(rel - hgt * 0.5) < 2.5)
                col = pick(rmp, idx + bevel(c, bb, hi=1, lo=0, w=1.0).astype(int))
                col = np.where(band[:, None], GOLD[5] if seed % 3 else LINEN[7], col)
                col = np.where(lab[:, None], LINEN[7] if seed % 2 else pick(rmp, idx + 3), col)
                pages = c.face == F_TOP
                col = np.where(pages[:, None], LINEN[6], col)
                return col
            if lean:
                v += 2
            sc.add(Box(*bb, book_mat))
            v += th + (0.0 if rnd(si, k, 5) > 0.2 else 1.0)
            k += 1
    # 頂上：垂下來的小藤蔓盆栽＋一疊書
    sc.add(Cyl(14, 14, 6, TOP + 5, TOP + 13, solid_mat(TERRA, 5, k=3.4)))
    vine = blank(14, 40)
    for strand, (x0, ln) in enumerate(((3, 34), (7, 24), (10, 30))):
        for y in range(ln):
            x = x0 + int(round(math.sin(y * 0.35 + strand) * 1.2))
            put(vine, x, y, LEAF[3])
            if y % 3 == 0:
                put(vine, x - 1, y, LEAF[5 + (y % 2)])
                put(vine, x + 1, y + 1, LEAF[4])
                put(vine, x - 1, y + 1, LEAF[6])
    for x in range(1, 13):
        put(vine, x, 0, LEAF[5 + (x % 2)])
        put(vine, x, 1, LEAF[4])
    sc.sprite(add_outline(vine, color=LEAF[0]), du - 2, 16, TOP + 12, anchor=(0.45, 0.04), depth=(du + 1, 16))
    for k, (hh, rmp) in enumerate(((4, ROSE), (3, BLUE), (4, GOLD))):
        z0 = TOP + 5 + sum(x[0] for x in ((4, ROSE), (3, BLUE), (4, GOLD))[:k])
        sbox(sc, 5 + k, 20 - k, 40 - k, 56 + k, z0, z0 + hh, rmp, 4, extra=lambda c, i: np.where(c.face == F_U, i, i))
    return sc.finish()


# ═══════════════════════════════ 書桌 ═══════════════════════════════

@register('desk')
def draw_desk(f):
    sc, g = piece_scene('desk')
    du, dv = g['du'], g['dv']            # 46 × 90，正面朝 +u
    shadow_rect(sc, 2, du - 2, 2, dv - 2, 2)
    TZ = 42
    for (pu, pv) in ((4, 4), (du - 4, 4), (4, dv - 4), (du - 4, dv - 4)):
        sc.add(Cyl(pu, pv, 2.8, 0, TZ - 6, wood_mat(WOOD, 4, grain_axis='z', seed=int(pu * 3 + pv))))
        sc.add(Ell(pu, pv, 1.6, 3.4, 3.4, 2.2, solid_mat(WOOD, 3, k=3.0)))

    def apron_mat(c):
        idx = tone_idx(c, 5, 3.6) + bevel(c, (2, du - 2, 2, dv - 2, TZ - 9, TZ - 1)).astype(int)
        front = c.face == F_U
        dr = front & (np.abs(c.v - dv / 2) < 18) & (c.z > TZ - 8) & (c.z < TZ - 2)
        idx = np.where(dr & ((np.abs(np.abs(c.v - dv / 2) - 18) < 1.0)), 3, idx)
        col = pick(WOOD, idx)
        kn = front & (np.abs(c.v - dv / 2) < 1.8) & (np.abs(c.z - (TZ - 5)) < 1.6)
        col = np.where(kn[:, None], BRASS[6], col)
        return col
    sc.add(Box(3, du - 3, 3, dv - 3, TZ - 9, TZ - 1, apron_mat))
    wbox(sc, 0, du, 0, dv, TZ - 1, TZ + 3, base=6, seed=41, plank=11)
    # 桌上的東西
    T = TZ + 3
    # 攤開的書（兩頁、中間一條摺痕、字是一行行小點）
    def book_mat(c):
        idx = tone_idx(c, 8, 2.0)
        top = c.face == F_TOP
        fold = np.abs(c.v - 44) < 0.8
        lines = top & (np.mod(c.u, 3) < 1) & (np.abs(c.v - 44) > 2.5) & (np.abs(c.v - 44) < 11) & (c.u > 12) & (c.u < 30)
        col = pick(LINEN, idx)
        col = np.where(lines[:, None], LINEN[4], col)
        col = np.where((fold & top)[:, None], LINEN[5], col)
        col = np.where((c.face != F_TOP)[:, None], pick(ROSE, idx - 4), col)
        return col
    sc.add(Box(10, 32, 31, 57, T, T + 2, book_mat))
    # 墨水瓶＋羽毛筆
    sc.add(Cyl(30, 66, 3.2, T, T + 5, solid_mat(BLUE, 3, k=3.0)))
    sc.add(Cyl(30, 66, 1.6, T + 5, T + 6.5, solid_mat(IRON, 4, k=3.0)))
    quill = from_ascii(['......a', '.....ab', '....abb', '...abb.', '..abb..', '.abb...', '.ab....', 'a......', 'c......'],
                       {'a': LINEN[6], 'b': LINEN[9], 'c': IRON[3]})
    sc.sprite(add_outline(quill), 30, 66, T + 6, anchor=(0.1, 1.0), depth=(30, 66))
    # 捲起來的地圖（橫躺的圓柱）
    sc.add(HCyl('v', 34, T + 2.6, 2.6, 12, 26, cloth_mat(LINEN, 6, k=2.6,
                                                         pattern=lambda c, i: np.where(c.face == F_CAP, i - 2, i))))
    # 小香菇盆栽（蘑菇長在小陶盆裡）
    sc.add(Cyl(14, 16, 5, T, T + 6, solid_mat(TERRA, 5, k=3.4)))
    sc.add(Cyl(14, 16, 4.2, T + 5.5, T + 6.2, solid_mat(WOOD, 2, k=1.0)))
    for (mu, mv, mh, r) in ((12, 15, 6, 4.4), (17, 18, 3, 3.2), (15, 12, 4, 2.6)):
        sc.add(Cyl(mu, mv, 0.9, T + 6, T + 6 + mh, solid_mat(LINEN, 7, k=2.0)))

        def cap_mat(c, mu=mu, mv=mv, mh=mh):
            idx = tone_idx(c, 5, 3.2)
            dot = (h32(np.floor((c.u - mu) * 1.2), np.floor((c.v - mv) * 1.2), np.floor(c.z * 1.2), 3) > 0.78) & (c.nz > 0.3)
            col = pick(ROSE, idx + 1)
            return np.where(dot[:, None], LINEN[9], col)
        sc.add(Ell(mu, mv, T + 6 + mh, r, r, r * 0.75, cap_mat, zmin=T + 6 + mh - 0.5))
    # 蠟燭（燭台）—— 光暈在 (12, 80, 64)
    sc.add(Cyl(12, 80, 4.5, T, T + 1.5, metal_mat(BRASS, 5)))
    sc.sprite(add_outline(candle_img(8, 0, wax=LINEN, flame_h=4)), 12, 80, T + 1.5, anchor=(0.5, 1.0), depth=(12, 80))
    # 一小疊信
    sbox(sc, 22, 34, 74, 84, T, T + 1.5, LINEN, 6)
    sbox(sc, 23, 33, 75, 83, T + 1.5, T + 3, PINK, 6)
    return sc.finish()


# ═══════════════════════════════ 小凳子 ═══════════════════════════════

@register('stool')
def draw_stool(f):
    sc, g = piece_scene('stool')
    c0 = g['du'] / 2
    shadow_round(sc, c0, c0, 10)
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.5
        sc.add(Cyl(c0 + 6.5 * math.cos(a), c0 + 6.5 * math.sin(a), 1.7, 0, 20, solid_mat(WOOD, 4, k=3.0)))
    sc.add(Cyl(c0, c0, 9.5, 18, 22, wood_mat(WOOD, 5, seed=51)))
    # 格紋小坐墊
    def cush(c):
        idx = tone_idx(c, 5, 3.0)
        chk = (np.mod(np.floor((c.u - c0) / 3) + np.floor((c.v - c0) / 3), 2) == 0)
        col = np.where(chk[:, None], pick(TEAL, idx), pick(LINEN, idx + 2))
        return col
    sc.add(Ell(c0, c0, 22.5, 9, 9, 4.0, cush, zmin=22))
    return sc.finish()


# ═══════════════════════════════ 木箱（倉庫）═══════════════════════════════

@register('chest')
def draw_chest(f):
    sc, g = piece_scene('chest')
    du, dv = g['du'], g['dv']            # 36 × 56，正面朝 +u
    shadow_rect(sc, 2, du - 2, 2, dv - 2, 2)
    BZ = 22
    bands = (10.0, dv / 2, dv - 10.0)

    def body_mat(c):
        idx = tone_idx(c, 5, 3.6) + bevel(c, (2, du - 2, 2, dv - 2, 1, BZ)).astype(int)
        pl = np.mod(c.z - 1, 7) < 1.0
        idx = np.where(pl & (c.face != F_TOP), idx - 2, idx)
        col = pick(WOOD, idx)
        a = c.v
        band = np.zeros(c.u.shape, bool)
        for b in bands:
            band |= np.abs(a - b) < 2.2
        band &= c.face == F_U
        side_band = (c.face == F_V) & ((np.abs(c.u - 6) < 2.2) | (np.abs(c.u - (du - 6)) < 2.2))
        bb = band | side_band
        col = np.where(bb[:, None], pick(IRON, tone_idx(c, 5, 3.0) + np.where(np.mod(c.z, 6) < 1.2, 2, 0)), col)
        lock = (c.face == F_U) & (np.abs(a - dv / 2) < 4.5) & (c.z > BZ - 9) & (c.z < BZ + 1)
        col = np.where(lock[:, None], pick(BRASS, 5 + (c.z > BZ - 3)), col)
        kh = lock & (np.abs(a - dv / 2) < 1.0) & (np.abs(c.z - (BZ - 5)) < 2.0)
        col = np.where(kh[:, None], IRON[1], col)
        return col
    sc.add(Box(2, du - 2, 2, dv - 2, 1, BZ, body_mat))

    def lid_mat(c):
        lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
        idx = np.round(5 + (lit - 0.5) * 3.8).astype(int)
        cap = c.face == F_CAP
        pl = (np.mod(np.arctan2(c.z - BZ, c.u - du / 2) * 5, 1.0) < 0.14) & ~cap
        idx = np.where(pl, idx - 2, idx)
        col = pick(WOOD, idx)
        band = np.zeros(c.u.shape, bool)
        for b in bands:
            band |= np.abs(c.v - b) < 2.2
        band &= ~cap
        ib = tone_idx(c, 5, 3.6)
        col = np.where(band[:, None], pick(IRON, ib + np.where(lit > 0.85, 3, 0)), col)
        rivet = band & (np.abs(c.v - np.round(c.v / 1.0)) < 2) & (np.mod(np.arctan2(c.z - BZ, c.u - du / 2) * 4, 1.0) < 0.12)
        col = np.where(rivet[:, None], BRASS[6], col)
        # 端面（+v）：一圈鐵框
        rim = cap & (np.hypot((c.u - du / 2) / 16, (c.z - BZ) / 9) > 0.82)
        col = np.where(rim[:, None], IRON[4], col)
        return col
    sc.add(HCyl('v', du / 2, BZ, 16, 2, dv - 2, lid_mat, rz=9, zmin=BZ))
    # 鎖扣在蓋子正面
    hasp = from_ascii(['aaa', 'aba', 'aba', 'aaa'], {'a': BRASS[4], 'b': BRASS[6]})
    sc.sprite(add_outline(hasp), du - 2, dv / 2, BZ + 6, anchor=(0.5, 0.5), depth=(du + 1, dv / 2))
    return sc.finish()


# ═══════════════════════════════ 鍊金桌 ═══════════════════════════════

def flask_img(kind, liq, h=10):
    if kind == 'round':
        img = blank(11, h + 2)
        ball(img, 5, h - 3.5, 4.6, 4.2, liq, 5, spec=True)
        m = img[..., 3] > 0
        yy = np.arange(img.shape[0])[:, None] * np.ones((1, 11))
        img[m & (yy < h - 4), :3] = GLASS[6]
        rect(img, 4, 0, 6, h - 7, GLASS[6])
        put(img, 4, 1, GLASS[7])
        rect(img, 3, 0, 7, 0, GLASS[5])
        return add_outline(img)
    if kind == 'cone':
        img = blank(11, h + 2)
        for y in range(h):
            f = y / (h - 1)
            half = 1 + f * 4
            for x in range(11):
                d = x - 5
                if abs(d) <= half:
                    c = (GLASS[6] if f < 0.45 else liq[6 if d < 0 else 4])
                    put(img, x, y + 1, c)
        rect(img, 4, 0, 6, 0, GLASS[5])
        put(img, 4, 3, GLASS[7])
        return add_outline(img)
    return bottle_img(3, h, liq, label=LINEN[8])


@register('alchemy-table')
def draw_alchemy(f):
    sc, g = piece_scene('alchemy-table')
    du, dv = g['du'], g['dv']            # 110 × 44，靠右後牆，正面朝 +v
    shadow_rect(sc, 2, du - 2, 2, dv - 4, 2)
    TZ = 44
    for (pu, pv) in ((4, 4), (du - 4, 4), (4, dv - 6), (du - 4, dv - 6)):
        sc.add(Box(pu - 2.5, pu + 2.5, pv - 2.5, pv + 2.5, 0, TZ - 2, wood_mat(WOOD, 4, grain_axis='z', seed=int(pu + pv))))
    wbox(sc, 3, du - 3, 3, dv - 6, 10, 13, base=5, seed=61, plank=10)        # 下層板
    # 下層：木條箱、幾個罐子、一籃藥草
    wbox(sc, 8, 28, 10, 34, 13, 25, base=4, seed=62, plank=4)
    for k, (uu, rmp) in enumerate(((38, GOLD), (46, TEAL), (54, PINK))):
        sc.add(Cyl(uu, 26, 3.4, 13, 22 - k, solid_mat(GLASS, 5, k=3.0)))
        sc.add(Cyl(uu, 26, 3.0, 13, 18 - k, solid_mat(rmp, 5, k=3.0)))
        sc.add(Cyl(uu, 26, 2.8, 22 - k, 24 - k, solid_mat(TERRA, 5, k=3.0)))

    def basket(c):
        idx = tone_idx(c, 6, 3.0) + np.where(np.mod(np.floor(c.z / 2) + np.floor(np.arctan2(c.v - 22, c.u - 86) * 4), 2) == 0, 1, -0)
        return pick(GOLD, idx - 1)
    sc.add(Cyl(86, 22, 10, 13, 21, basket, r_in=8.6))
    sc.add(Ell(86, 22, 20, 8.6, 8.6, 4.4, solid_mat(LEAF, 5, k=3.4)))
    # 抽屜帶＋桌面
    def apron(c):
        idx = tone_idx(c, 5, 3.6) + bevel(c, (2, du - 2, 2, dv - 4, TZ - 8, TZ - 1)).astype(int)
        front = c.face == F_V
        col = pick(WOOD, idx)
        for d0 in (12, 44, 76):
            dr = front & (c.u > d0) & (c.u < d0 + 26)
            ed = dr & ((c.u < d0 + 1.2) | (c.u > d0 + 24.8))
            col = np.where(ed[:, None], WOOD[3], col)
            kn = front & (np.abs(c.u - (d0 + 13)) < 2) & (np.abs(c.z - (TZ - 4.5)) < 1.6)
            col = np.where(kn[:, None], BRASS[6], col)
        return col
    sc.add(Box(2, du - 2, 2, dv - 4, TZ - 8, TZ - 1, apron))

    def top_mat(c):
        idx = tone_idx(c, 6, 3.6) + bevel(c, (0, du, 0, dv - 2, TZ - 1, TZ + 3)).astype(int)
        pk = np.mod(c.v, 11) < 1.0
        idx = np.where(pk & (c.face == F_TOP), idx - 1, idx)
        col = pick(WOOD, idx)
        # 桌面上一塊藥水漬
        st = (c.face == F_TOP) & (np.hypot(c.u - 70, (c.v - 30) * 1.4) < 4)
        col = np.where(st[:, None], pick(TEAL, idx - 2), col)
        return col
    sc.add(Box(0, du, 0, dv - 2, TZ - 1, TZ + 3, top_mat))
    T = TZ + 3
    # ── 蒸餾器：酒精燈（光暈 (22,20,50)）＋三腳架＋銅燒瓶＋彎管到收集瓶 ──
    sc.add(Cyl(22, 20, 4.5, T, T + 4, solid_mat(GLASS, 5, k=3.0)))
    sc.add(Cyl(22, 20, 1.2, T + 4, T + 6, solid_mat(LINEN, 6, k=2.0)))
    sc.sprite(flame_img(5, 3, 0), 22, 20, T + 6, anchor=(0.5, 1.0), depth=(22, 20), edge=False)
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.3
        sc.add(Cyl(22 + 7 * math.cos(a), 20 + 7 * math.sin(a), 0.9, T, T + 14, solid_mat(IRON, 5, k=3.0)))
    sc.add(Cyl(22, 20, 8, T + 13, T + 15, metal_mat(IRON, 4), r_in=6.5))
    sc.add(Ell(22, 20, T + 22, 8.5, 8.5, 8.5, metal_mat(COPPER, 5)))
    sc.add(Cyl(22, 20, 2.6, T + 29, T + 38, metal_mat(COPPER, 5)))
    tube = blank(16, 12)
    for x in range(16):
        y = int(round(1 + (x / 15.0) ** 1.6 * 10))
        put(tube, x, y, COPPER[6])
        put(tube, x, y + 1, COPPER[4])
    sc.sprite(add_outline(tube), 24, 20, T + 38, anchor=(0.0, 0.05), depth=(26, 22))
    sc.sprite(flask_img('round', PINK, 12), 40, 24, T, anchor=(0.5, 1.0), depth=(40, 24))
    # ── 天平（銅）──
    scale = from_ascii(['.......a.......', '......aba......', 'cccccccbccccccc', 'd......b......d', 'd......b......d',
                        'd......b......d', 'eee....b....eee', 'fff....b....fff', '.......b.......', '.....ggggg.....',
                        '....ggggggg....'],
                       {'a': BRASS[7], 'b': BRASS[5], 'c': BRASS[6], 'd': BRASS[3], 'e': BRASS[6], 'f': BRASS[4],
                        'g': WOOD[5]})
    scale[6, 0:3, :3] = BRASS[6]
    scale[5, 0:3, :3] = PINK[5]                   # 左盤上一顆粉紅結晶
    scale[5, 12:15, :3] = GOLD[6]                 # 右盤上金粉
    scale[5, 0:3, 3] = 255
    scale[5, 12:15, 3] = 255
    sc.sprite(add_outline(scale), 60, 16, T, anchor=(0.5, 1.0), depth=(60, 16))
    # ── 研缽＋研杵 ──
    sc.add(Cyl(78, 30, 5, T, T + 5, solid_mat(STONE, 6, k=3.4), r_in=3.6))
    sc.add(Cyl(78, 30, 3.6, T, T + 3, solid_mat(LEAF, 4, k=2.0)))
    pestle = from_ascii(['..ab', '.ab.', 'ab..', 'b...'], {'a': STONE[7], 'b': STONE[5]})
    sc.sprite(add_outline(pestle), 80, 30, T + 5, anchor=(0.2, 1.0), depth=(80, 30))
    # ── 食譜（攤開的羊皮紙卷）──
    def scroll(c):
        idx = tone_idx(c, 7, 2.2)
        lines = (c.face == F_TOP) & (np.mod(c.u, 3) < 1) & (np.abs(c.v - 28) < 6) & (c.u > 92) & (c.u < 104)
        col = pick(LINEN, idx - 1)
        return np.where(lines[:, None], PLUM[4], col)
    sc.add(Box(90, 106, 20, 37, T, T + 0.8, scroll))
    sc.add(HCyl('v', 90, T + 1.6, 1.6, 20, 37, cloth_mat(LINEN, 5, k=2.4)))
    # ── 試管架＋其他瓶子 ──
    wbox(sc, 96, 108, 4, 12, T, T + 4, base=5, seed=63)
    for k, rmp in enumerate((TEAL, PINK, GOLD)):
        img = from_ascii(['a', 'a', 'b', 'b', 'b'], {'a': GLASS[6], 'b': rmp[5]})
        sc.sprite(add_outline(img), 98 + k * 4, 8, T + 2, anchor=(0.5, 1.0), depth=(98 + k * 4, 9))
    sc.sprite(flask_img('cone', TEAL, 10), 50, 30, T, anchor=(0.5, 1.0), depth=(50, 30))
    sc.sprite(flask_img('bottle', PURPLE, 9), 70, 10, T, anchor=(0.5, 1.0), depth=(70, 10))
    return sc.finish()


# ═══════════════════════════════ 床頭櫃 ═══════════════════════════════

@register('nightstand')
def draw_nightstand(f):
    sc, g = piece_scene('nightstand')
    du, dv = g['du'], g['dv']            # 36 × 30，正面朝 +v
    shadow_rect(sc, 2, du - 2, 2, dv - 2, 2)
    TZ = 34
    for (pu, pv) in ((4, 4), (du - 4, 4), (4, dv - 4), (du - 4, dv - 4)):
        sc.add(Ell(pu, pv, 2.4, 3.2, 3.2, 2.6, solid_mat(WOOD, 4, k=3.0)))

    def body(c):
        idx = tone_idx(c, 5, 3.6) + bevel(c, (2, du - 2, 2, dv - 2, 3, TZ)).astype(int)
        front = c.face == F_V
        col = pick(WOOD, idx)
        for (z0, z1) in ((7, 18), (20, 31)):
            ed = front & (c.u > 5) & (c.u < du - 5) & ((np.abs(c.z - z0) < 0.8) | (np.abs(c.z - z1) < 0.8) |
                                                       (((np.abs(c.u - 5.6) < 0.8) | (np.abs(c.u - (du - 5.6)) < 0.8)) & (c.z > z0) & (c.z < z1)))
            col = np.where(ed[:, None], WOOD[3], col)
            kn = front & (np.abs(c.u - du / 2) < 2) & (np.abs(c.z - (z0 + z1) / 2) < 1.6)
            col = np.where(kn[:, None], BRASS[6], col)
            heart = front & (np.abs(c.u - du / 2 - 6) < 0)
        return col
    sc.add(Box(2, du - 2, 2, dv - 2, 3, TZ, body))
    wbox(sc, 0, du, 0, dv, TZ, TZ + 3, base=6, seed=71)
    T = TZ + 3
    # 蕾絲桌巾
    def doily(c):
        r = np.hypot(c.u - 16, c.v - 14)
        holes = (np.mod(np.arctan2(c.v - 14, c.u - 16) * 8 / math.pi, 1.0) < 0.3) & (r > 7) & (r < 9)
        col = pick(LINEN, 8 - (r > 9.5))
        return np.where(holes[:, None], LINEN[5], col)
    sc.add(Cyl(16, 14, 11, T, T + 0.6, doily, edge=False))
    # 水晶球（光暈 (16,14,66)）＋金色座
    sc.add(Cyl(16, 14, 5.5, T + 0.6, T + 4, metal_mat(GOLD, 5)))
    sc.add(Cyl(16, 14, 4.2, T + 4, T + 6, metal_mat(GOLD, 6)))

    def orb(c):
        lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
        sw = np.sin((c.u - c.v) * 0.5 + c.z * 0.45)
        idx = np.round(5 + (lit - 0.5) * 3 + sw * 0.9).astype(int)
        col = np.where((sw > 0.3)[:, None], pick(PINK, idx), pick(PURPLE, idx + 1))
        col = np.where((lit > 0.9)[:, None], LINEN[9], col)
        st = h32(c.I, c.J, 9) > 0.93
        col = np.where(st[:, None], STAR, col)
        return col
    sc.add(Ell(16, 14, T + 13, 7.5, 7.5, 7.5, orb))
    # 一本小書＋眼鏡
    sbox(sc, 26, 34, 18, 28, T, T + 2, BLUE, 4)
    sbox(sc, 26.5, 33.5, 18.5, 27.5, T + 2, T + 3.5, ROSE, 5)
    return sc.finish()


# ═══════════════════════════════ 扶手椅 ═══════════════════════════════

@register('armchair')
def draw_armchair(f):
    sc, g = piece_scene('armchair')
    du, dv = g['du'], g['dv']            # 52 × 50：椅背在 v 小的那邊，座位朝 +v
    shadow_rect(sc, 3, du - 3, 3, dv - 3, 2)
    for (pu, pv) in ((7, 6), (du - 7, 6), (7, dv - 6), (du - 7, dv - 6)):
        sc.add(Ell(pu, pv, 2.4, 3.0, 3.0, 2.6, solid_mat(WOOD, 4, k=3.0)))

    def velvet(base=5, tuft=False):
        def m(c):
            idx = tone_idx(c, base, 3.4)
            col = pick(ROSE, idx)
            if tuft:
                front = c.ny > 0.7
                bt = front & (np.mod(c.u - 6, 9) < 1.6) & (np.abs(np.mod(c.z - 30, 9) - 4.5) < 1.2) & (c.z > 30) & (c.z < 60)
                col = np.where(bt[:, None], ROSE[2], col)
                pl = front & ((np.abs(np.mod(c.u - 6 + (c.z - 30), 9) - 4.5) < 0.5) | (np.abs(np.mod(c.u - 6 - (c.z - 30), 9) - 4.5) < 0.5)) & (c.z > 30) & (c.z < 60)
                col = np.where(pl[:, None], ROSE[3], col)
            return col
        return m
    sc.add(Box(5, du - 5, 5, dv - 5, 4, 16, velvet(4)))                        # 底座
    sc.add(Box(6, du - 6, 4, 14, 14, 56, velvet(5, True)))                      # 椅背
    sc.add(HCyl('u', 9, 56, 5.5, 6, du - 6, velvet(5), rz=6.5))                 # 椅背圓頂
    for (ua, ub) in ((3, 12), (du - 12, du - 3)):                                # 兩邊扶手
        sc.add(Box(ua, ub, 6, dv - 4, 4, 28, velvet(5)))
        sc.add(HCyl('v', (ua + ub) / 2, 28, 5.0, 6, dv - 4, velvet(5), rz=4.2))
    sc.add(Box(12, du - 12, 14, dv - 5, 16, 24, velvet(6)))                     # 坐墊
    sc.add(HCyl('u', dv - 6, 22, 2.6, 12, du - 12, velvet(6), rz=3.0))
    # 一條奶油色針織毯掛在右扶手（條紋）＋一顆小圓抱枕
    def knit(c):
        idx = tone_idx(c, 7, 2.6) + np.where(np.mod(c.z + c.v * 0.2, 6) < 1.5, -2, 0)
        stripe = np.mod(np.floor(c.v / 8), 3) == 1
        col = np.where(stripe[:, None], pick(TEAL, idx - 1), pick(LINEN, idx))
        return col
    sc.add(Box(du - 13, du - 2, 20, 34, 6, 33, knit))
    sc.add(Ell(26, 20, 30, 8, 4.5, 7, cloth_mat(GOLD, 5, k=3.0,
                                                 pattern=lambda c, i: np.where(np.hypot(c.u - c.v - 6, c.z - 31) < 2.2, i + 2, i))))
    return sc.finish()


# ═══════════════════════════════ 柴堆 ═══════════════════════════════

def log_mat(seed):
    def m(c):
        cap = c.face == F_CAP
        lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
        idx = np.round(4 + (lit - 0.5) * 3.6).astype(int)
        bark = h32(np.floor(c.v / 3), np.floor(np.arctan2(c.nz, c.nx) * 6), seed) > 0.6
        idx = np.where(bark & ~cap, idx - 1, idx)
        col = pick(TIMBER, idx + 1)
        return col
    return m


@register('firewood')
def draw_firewood(f):
    sc, g = piece_scene('firewood')
    du, dv = g['du'], g['dv']            # 32 × 58：木柴沿 v 躺，切口朝 +v（左下）
    shadow_rect(sc, 1, du - 1, 3, dv - 3, 2)
    logs = [(7, 5.2), (16, 5.2), (25, 5.2), (11.5, 13.6), (20.5, 13.6), (16, 22)]
    for k, (lu, lz) in enumerate(logs):
        r = 4.8 + (k % 2) * 0.4
        v1 = dv - 3 - (k % 3) * 2
        cu_, cz_ = lu, lz

        def m(c, cu_=cu_, cz_=cz_, r=r, k=k):
            cap = c.face == F_CAP
            lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
            idx = np.round(4 + (lit - 0.5) * 3.6).astype(int)
            bark = h32(np.floor(c.v / 3), np.floor((c.u - c.z) * 1.0), k + 3) > 0.55
            idx = np.where(bark, idx - 1, idx)
            col = pick(TIMBER, idx + 1)
            rr = np.hypot(c.u - cu_, c.z - cz_) / r
            ring = (np.abs(np.mod(rr * 3.2, 1.0) - 0.5) < 0.16)
            ccol = pick(WOOD, np.where(rr > 0.84, 3, np.where(ring, 6, 8)))
            col = np.where(cap[:, None], ccol, col)
            return col
        sc.add(HCyl('v', cu_, cz_, r, 4 + (k % 2) * 2, v1, m))
    # 一把小斧頭靠在旁邊
    axe = from_ascii(['.aab', 'aaab', 'aa.b', '...b', '...b', '...b', '...b', '...b', '...b', '...b'],
                     {'a': IRON[6], 'b': WOOD[6]})
    axe[0:3, 0:3, :3] = np.where(axe[0:3, 0:3, 3:4] > 0, IRON[6], 0)
    sc.sprite(add_outline(axe), du - 1, dv - 2, 0, anchor=(0.7, 1.0), depth=(du, dv))
    return sc.finish()


# ═══════════════════════════════ 藥水台 ═══════════════════════════════

def heart_bottle(liq):
    rows = ['....aa....', '....bb....', '...cbbc...', '.cc....cc.', 'cdddcddddc', 'cdeddddddc', 'cdddddddfc',
            '.cddddddc.', '..cdddddc.', '...cdddc..', '....cdc...', '.....c....']
    return from_ascii(rows, {'a': TERRA[6], 'b': GLASS[5], 'c': GLASS[3], 'd': liq[5], 'e': LINEN[9], 'f': liq[3]})


@register('potion-bench')
def draw_potion_bench(f):
    sc, g = piece_scene('potion-bench')
    du, dv = g['du'], g['dv']            # 100 × 36，正面朝 +v
    shadow_rect(sc, 2, du - 2, 2, dv - 4, 2)
    TZ = 32
    for (pu, pv) in ((4, 4), (du - 4, 4), (4, dv - 6), (du - 4, dv - 6)):
        sc.add(Box(pu - 2.2, pu + 2.2, pv - 2.2, pv + 2.2, 0, TZ, wood_mat(WOOD, 4, grain_axis='z', seed=int(pu + pv))))
    wbox(sc, 2, du - 2, 2, dv - 4, 7, 10, base=5, seed=81, plank=9)
    # 下層：罐子、一捲布、一籃小蘑菇
    for k, (uu, rmp, h_) in enumerate(((12, LEAF, 10), (21, PLUM, 8), (30, GOLD, 9))):
        sc.add(Cyl(uu, 18, 3.6, 10, 10 + h_, solid_mat(GLASS, 5, k=3.0)))
        sc.add(Cyl(uu, 18, 3.2, 10, 8 + h_, solid_mat(rmp, 5, k=3.0)))
        sc.add(Cyl(uu, 18, 3.0, 10 + h_, 12 + h_, solid_mat(TERRA, 5, k=3.0)))
    sc.add(HCyl('u', 18, 14.5, 4.5, 44, 66, cloth_mat(TEAL, 5, k=3.0, pattern=lambda c, i: np.where(c.face == F_CAP, i + 1, i))))

    def basket(c):
        idx = tone_idx(c, 6, 3.0) + np.where(np.mod(np.floor(c.z / 2) + np.floor(np.arctan2(c.v - 18, c.u - 82) * 4), 2) == 0, 1, 0)
        return pick(GOLD, idx - 1)
    sc.add(Cyl(82, 18, 9, 10, 18, basket, r_in=7.6))
    for (mu, mv) in ((79, 16), (85, 19), (82, 22)):
        sc.add(Cyl(mu, mv, 0.9, 10, 20, solid_mat(LINEN, 7, k=2.0)))
        sc.add(Ell(mu, mv, 20, 3, 3, 2.4, solid_mat(ROSE, 6, k=3.0), zmin=19.5))
    # 桌面
    def top_mat(c):
        idx = tone_idx(c, 6, 3.6) + bevel(c, (0, du, 0, dv - 2, TZ, TZ + 4)).astype(int)
        pk = np.mod(c.v, 9) < 1.0
        idx = np.where(pk & (c.face == F_TOP), idx - 1, idx)
        col = pick(WOOD, idx)
        front = c.face == F_V
        carve = front & (np.abs(c.z - (TZ + 2)) < 0.8) & (np.mod(c.u, 6) < 3)
        col = np.where(carve[:, None], WOOD[7], col)
        return col
    sc.add(Box(0, du, 0, dv - 2, TZ, TZ + 4, top_mat))
    T = TZ + 4
    # 桌上：一排藥水（愛心瓶、圓瓶、高瓶）、試管架、一疊書＋小水晶球
    sc.sprite(add_outline(heart_bottle(PINK)), 14, 16, T, anchor=(0.5, 1.0), depth=(14, 16))
    sc.sprite(flask_img('round', TEAL, 12), 26, 12, T, anchor=(0.5, 1.0), depth=(26, 12))
    sc.sprite(bottle_img(3, 11, PURPLE, label=GOLD[6]), 34, 10, T, anchor=(0.5, 1.0), depth=(34, 10))
    sc.sprite(bottle_img(4, 7, GOLD, label=LINEN[8]), 41, 20, T, anchor=(0.5, 1.0), depth=(41, 20))
    sc.sprite(bottle_img(2, 6, LEAF), 47, 14, T, anchor=(0.5, 1.0), depth=(47, 14))
    wbox(sc, 52, 66, 6, 14, T, T + 5, base=5, seed=82)
    for k, rmp in enumerate((ROSE, TEAL, GOLD, PURPLE)):
        img = from_ascii(['a', 'a', 'a', 'b', 'b', 'b'], {'a': GLASS[6], 'b': rmp[5]})
        sc.sprite(add_outline(img), 54 + k * 3.6, 10, T + 3, anchor=(0.5, 1.0), depth=(54 + k * 3.6, 11))
    sbox(sc, 72, 92, 12, 26, T, T + 3, PURPLE, 4)
    sbox(sc, 73, 91, 13, 25, T + 3, T + 5.5, TEAL, 5)
    sbox(sc, 74, 90, 14, 24, T + 5.5, T + 7.5, ROSE, 5)
    sc.add(Cyl(82, 19, 3.2, T + 7.5, T + 9, metal_mat(GOLD, 5)))

    def orb(c):
        lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
        idx = np.round(5 + (lit - 0.5) * 3).astype(int)
        col = pick(TEAL, idx + 1)
        return np.where((lit > 0.9)[:, None], LINEN[9], col)
    sc.add(Ell(82, 19, T + 13, 4.4, 4.4, 4.4, orb))
    return sc.finish()


# ═══════════════════════════════ 蠟燭、燭台、盆栽 ═══════════════════════════════

@register('candles')
def draw_candles(f):
    """三根粗蠟燭（不乘夜色）：銅盤上，高矮不一，蠟淚。"""
    sc, g = piece_scene('candles')
    c0 = g['du'] / 2
    shadow_round(sc, c0, c0, 8)
    sc.add(Cyl(c0, c0, 8.5, 0, 2, metal_mat(BRASS, 5)))
    sc.add(Cyl(c0, c0, 7.0, 2, 2.6, metal_mat(BRASS, 4)))
    for (du_, dv_, h, rmp, b) in ((-3, -2, 20, LINEN, 7), (3, -1, 14, PINK, 6), (-1, 4, 10, LINEN, 8)):
        cu, cv = c0 + du_, c0 + dv_
        r = 2.6

        def wax(c, rmp=rmp, b=b, cu=cu, cv=cv, h=h):
            idx = tone_idx(c, b, 3.0)
            drip = (c.face == F_SIDE) & (c.z > h - 4 - 3 * h32(np.floor(np.arctan2(c.v - cv, c.u - cu) * 3), 2))
            idx = np.where(drip, idx + 1, idx)
            return pick(rmp, idx)
        sc.add(Cyl(cu, cv, r, 2, 2 + h, wax))
        sc.sprite(flame_img(5, 3, 0), cu, cv, 2 + h, anchor=(0.5, 1.0), depth=(cu, cv), edge=False)
        sc.fine_px(cu, cv, 2 + h + 3, FIRE[8])
    return sc.finish()


@register('candle-stand')
def draw_candle_stand(f):
    """高腳燭台（鐵，三腳）：一根長蠟燭（不乘夜色）。光暈在 z=66。"""
    sc, g = piece_scene('candle-stand')
    c0 = g['du'] / 2
    shadow_round(sc, c0, c0, 7)
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.4
        sc.add(Ell(c0 + 5.5 * math.cos(a), c0 + 5.5 * math.sin(a), 1.2, 2.6, 2.6, 1.8, metal_mat(IRON, 5)))
    sc.add(Cyl(c0, c0, 3.2, 0, 4, metal_mat(IRON, 5)))
    sc.add(Cyl(c0, c0, 1.2, 4, 50, metal_mat(IRON, 5)))
    for z in (14, 30):
        sc.add(Ell(c0, c0, z, 2.2, 2.2, 1.6, metal_mat(IRON, 6)))
    sc.add(Cyl(c0, c0, 5.5, 50, 52, metal_mat(BRASS, 5), r_in=4.0))
    sc.add(Cyl(c0, c0, 4.2, 50, 51.5, metal_mat(BRASS, 4)))

    def wax(c):
        idx = tone_idx(c, 7, 3.0)
        drip = (c.face == F_SIDE) & (c.z > 58) & (h32(np.floor(np.arctan2(c.v - c0, c.u - c0) * 4), 3) > 0.5)
        return pick(LINEN, idx + np.where(drip, 1, 0))
    sc.add(Cyl(c0, c0, 2.4, 51, 62, wax))
    sc.sprite(flame_img(6, 3, 0), c0, c0, 62, anchor=(0.5, 1.0), depth=(c0, c0), edge=False)
    sc.fine_px(c0, c0, 66, FIRE[8])
    return sc.finish()


@register('plant')
def draw_plant(f):
    """陶盆（畫了一顆小愛心）裡的圓葉植物。"""
    sc, g = piece_scene('plant')
    c0 = g['du'] / 2
    shadow_round(sc, c0, c0, 9)

    def pot(c):
        idx = tone_idx(c, 5, 3.4)
        front = (c.nx + c.ny) > 0.85
        fx = c.u - c.v
        ht = front & (np.abs(fx) * 1.0 + np.abs(c.z - 8) < 2.8) & ~((np.abs(fx) < 0.8) & (c.z > 9))
        col = pick(TERRA, idx)
        return np.where(ht[:, None], PINK[6], col)
    sc.add(Cyl(c0, c0, 7.5, 0, 14, pot))
    sc.add(Cyl(c0, c0, 8.8, 12, 16, solid_mat(TERRA, 6, k=3.4), r_in=7.0))
    sc.add(Cyl(c0, c0, 7.0, 0, 14.5, solid_mat(WOOD, 1, k=1.0)))
    # 葉子：一片片圓葉（受光、中肋），往外散開
    img = blank(26, 34)
    leaves = [(13, 30, 0, 4.4), (6, 22, -1, 4.6), (20, 21, 1, 4.6), (9, 13, -1, 4.8), (18, 11, 1, 4.6),
              (13, 6, 0, 4.6), (4, 29, -1, 3.8), (22, 29, 1, 3.8), (13, 18, 0, 4.8)]
    for (lx, ly, d, r) in leaves:
        # 莖
        for t in np.linspace(0, 1, 12):
            x = 13 + (lx - 13) * t
            y = 33 - (33 - ly) * t
            put(img, int(round(x)), int(round(y)), LEAF[3])
    for (lx, ly, d, r) in leaves:
        m = ball(img, lx, ly, r, r * 0.8, LEAF, 5, spec=False)
        yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
        rib = m & (np.abs((xx - lx) * 0.6 - (yy - ly) * d * 0.8) < 0.5)
        img[rib, :3] = LEAF[7]
        hi_ = m & ((xx - lx + 1.5) ** 2 + (yy - ly + 1.5) ** 2 < 2.0)
        img[hi_, :3] = LEAF[8]
    sc.sprite(add_outline(img, color=LEAF[0]), c0, c0, 14, anchor=(0.5, 0.97), depth=(c0 + 4, c0 + 4))
    return sc.finish()


# ═══════════════════════════════ 組裝 ═══════════════════════════════

def render_shell(night):
    sc = shell_scene(night)
    if night:
        p = sc.pos
        keep = (np.abs(p[..., 1]) < 0.6) & (p[..., 0] >= WIN_U0 + 5) & (p[..., 0] < WIN_U1 - 1) & \
               (p[..., 2] >= WIN_Z0 + 1) & (p[..., 2] < WIN_Z1 - 6)
        graded, q = night_grade(sc, sc.rgb)
        sc.rgb = np.where(keep[..., None], sc.rgb, graded)
    img = sc.finish(outline=False, inner=True)
    img[..., 3] = np.where(sc_alpha_full(sc), 255, img[..., 3])
    return img


def sc_alpha_full(sc):
    m = (sc.ids > 0).repeat(2, 0).repeat(2, 1)[sc.gy:sc.gy + sc.H, sc.gx:sc.gx + sc.W]
    return m


def build_all(only=None):
    arts = {}
    arts['shell-day'] = render_shell(False)
    arts['shell-night'] = render_shell(True)
    for nm, fn in DRAW.items():
        if only and nm not in only:
            continue
        arts[nm] = fn()
    return arts


def glow_image(size=128):
    r = (np.arange(size) - (size - 1) / 2) / (size / 2)
    X, Y = np.meshgrid(r, r)
    d = np.clip(np.hypot(X, Y), 0, 1)
    a = np.clip((1 - d) ** 2 * (1 - d * 0.15), 0, 1)
    img = np.zeros((size, size, 4), np.uint8)
    img[..., :3] = 255
    img[..., 3] = (a * 255).round().astype(np.uint8)
    return img


def check_sizes(arts):
    bad = []
    for nm, a in arts.items():
        p = os.path.join(OLD_DIR, nm + '.png')
        if not os.path.exists(p):
            bad.append('%s：舊資料夾沒有這張' % nm)
            continue
        w, h = Image.open(p).size
        if (a.shape[1], a.shape[0]) != (w, h):
            bad.append('%s：%dx%d ≠ 舊圖 %dx%d' % (nm, a.shape[1], a.shape[0], w, h))
    return bad


def write_arts(arts, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for nm, a in arts.items():
        Image.fromarray(a).save(os.path.join(out_dir, nm + '.png'))
    Image.fromarray(glow_image()).save(os.path.join(out_dir, 'glow.png'))


# ═══════════════════════════════ 預覽 ═══════════════════════════════

def load_set(src):
    """src：dict（新圖）或資料夾（舊圖）。回傳 圖名 → RGBA 陣列。"""
    if isinstance(src, dict):
        return src
    out = {}
    for fn in os.listdir(src):
        if fn.endswith('.png'):
            out[fn[:-4]] = np.asarray(Image.open(os.path.join(src, fn)).convert('RGBA'))
    return out


def witch_sprite():
    b = Image.open(os.path.join(RES, 'witch8', 'base.png')).convert('RGBA')
    cw, ch = b.width // 8, b.height // 25
    cell = b.crop((0, 0, cw, ch))
    return cell.resize((round(cw * 1.6), round(ch * 1.6)), Image.NEAREST)


def player_order(wx, wy, wsz):
    u, v = world_to_uv(wx, wy)
    w, h = wsz
    x0, x1, y0, y1 = wx - w * 0.35, wx + w * 0.35, wy, wy + h * 0.9
    lo, hi = None, None
    for p in LAYOUT['pieces']:
        if p['kind'] != 'Stand':
            continue
        r = p['rect']
        if x1 <= r[0] or r[2] <= x0 or y1 <= r[1] or r[3] <= y0:
            continue
        if u >= p['U1'] or v >= p['V1']:
            front = True
        elif u <= p['U0'] or v <= p['V0']:
            front = False
        else:
            front = u + v > (p['U0'] + p['U1'] + p['V0'] + p['V1']) / 2
        if front:
            lo = p['order'] if lo is None else max(lo, p['order'])
        else:
            hi = p['order'] if hi is None else min(hi, p['order'])
    if lo is None and hi is None:
        return round(-wy)
    if lo is None:
        return hi - 1
    return lo + 1


OLD_FALLBACK = None


def compose(src, night, witches=(), skip_cat=True, frame=0, fire_frame=0, glows=True):
    arts = load_set(src)
    img = Image.fromarray(arts['shell-night' if night else 'shell-day'])
    layers = []
    for p in LAYOUT['pieces']:
        if skip_cat and p['name'] == 'cat':
            continue
        fr = p['frames']
        k = frame if p['name'] == 'cauldron' else fire_frame if p['name'] == 'fireplace-fire' else 0
        nm = art_name(fr[min(k, len(fr) - 1)])
        a_ = arts.get(nm)
        if a_ is None:
            a_ = OLD_FALLBACK.get(nm) if OLD_FALLBACK is not None else None
            if a_ is None:
                continue
        layers.append((p['order'], 0, p, a_))
    wimg = witch_sprite()
    for (wx, wy) in witches:
        layers.append((player_order(wx, wy, wimg.size) + 0.5, 1, (wx, wy), None))
    for o, kind, p, a in sorted(layers, key=lambda t: t[0]):
        if kind == 1:
            wx, wy = p
            x, y = wx + CANVAS_W / 2, CANVAS_H / 2 - wy
            from PIL import ImageDraw
            sh = Image.new('RGBA', (40, 12), (0, 0, 0, 0))
            ImageDraw.Draw(sh).ellipse([0, 0, 39, 11], fill=(20, 10, 25, 90))
            img.alpha_composite(sh, (int(x - 20), int(y - 6)))
            img.alpha_composite(wimg, (int(round(x - wimg.width / 2)), int(round(y - wimg.height + 3 * 1.6))))
            continue
        im = a
        if night and p['tint']:
            f = im.astype(np.float32)
            f[..., :3] *= np.array(NIGHT_MUL, np.float32)
            im = f.clip(0, 255).astype(np.uint8)
        left = int(round(p['x'] - p['px'] + CANVAS_W / 2))
        top = int(round(CANVAS_H / 2 - (p['y'] - p['py']) - a.shape[0]))
        img.alpha_composite(Image.fromarray(im), (left, top))
    if night and glows:
        g = glow_image(128)
        for (gx, gy, r, k, fl) in LAYOUT['glows']:
            size = int(r * 2)
            gi = np.asarray(Image.fromarray(g).resize((size, size), Image.BILINEAR)).astype(np.float32)
            gi[..., 0], gi[..., 1], gi[..., 2] = GLOW_COLOR
            gi[..., 3] *= k * GLOW_ALPHA
            x, y = gx + CANVAS_W / 2, CANVAS_H / 2 - gy
            img.alpha_composite(Image.fromarray(gi.astype(np.uint8)), (int(x - size / 2), int(y - size / 2)))
    bg = Image.new('RGBA', img.size, (24, 20, 30, 255))
    bg.alpha_composite(img)
    return bg.convert('RGB')


def witch_spots():
    pts = LAYOUT['points']
    return [(pts['cauldron'][0][0] - 60, pts['cauldron'][0][1] - 10),     # 鍋爐左邊
            (pts['bed'][0][0] - 40, pts['bed'][0][1] - 70),               # 床尾前面
            (LAYOUT['spawn'][0] - 210, LAYOUT['spawn'][1] + 200)]        # 書櫃、書桌前


def debug_overlay(base):
    from PIL import ImageDraw
    a = np.asarray(base.convert('RGBA')).astype(np.float32)
    a[..., :3] = a[..., :3] * 0.7 + 20
    im = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(im)
    P = lambda x, y: (x + CANVAS_W / 2, CANVAS_H / 2 - y)  # noqa: E731
    d.polygon([P(*q) for q in LAYOUT['walk']], outline=(255, 230, 60, 255))
    for p in LAYOUT['pieces']:
        if p['shape'] == 'Poly':
            d.line([P(*q) for q in p['poly']] + [P(*p['poly'][0])], fill=(255, 40, 40, 255), width=2)
        elif p['shape'] == 'Ellipse':
            cx, cy, hx, hy = p['ell']
            a1, b1 = P(cx - hx, cy + hy)
            a2, b2 = P(cx + hx, cy - hy)
            d.ellipse([a1, b1, a2, b2], outline=(255, 40, 40, 255), width=2)
        # 落地範圍（uv 盒子）細線
        corners = [(p['U0'], p['V0']), (p['U1'], p['V0']), (p['U1'], p['V1']), (p['U0'], p['V1'])]
        d.line([room_px(u, v) for u, v in corners] + [room_px(*corners[0])], fill=(80, 220, 255, 255), width=1)
    for k, ((x, y), r) in LAYOUT['points'].items():
        X, Y = P(x, y)
        d.ellipse([X - r, Y - r, X + r, Y + r], outline=(140, 255, 160, 255), width=1)
        d.ellipse([X - 4, Y - 4, X + 4, Y + 4], fill=(140, 255, 160, 255))
    cx, cy = room_px(*CAT_BED_UV)
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], outline=(255, 120, 255, 255), width=2)
    return im.convert('RGB')


def preview(arts, outdir):
    os.makedirs(outdir, exist_ok=True)
    files = []
    W = witch_spots()

    def save(im, nm):
        p = os.path.join(outdir, nm)
        im.save(p)
        files.append(p)
        return p
    day = compose(arts, False, W)
    night = compose(arts, True, W)
    save(day, 'room8-day.png')
    save(night, 'room8-night.png')
    old_day = compose(OLD_DIR, False, W, skip_cat=False)
    sbs = Image.new('RGB', (CANVAS_W * 2 + 8, CANVAS_H), (0, 0, 0))
    sbs.paste(old_day, (0, 0))
    sbs.paste(day, (CANVAS_W + 8, 0))
    save(sbs, 'old-vs-new-day.png')
    old_night = compose(OLD_DIR, True, W, skip_cat=False)
    sbs = Image.new('RGB', (CANVAS_W * 2 + 8, CANVAS_H), (0, 0, 0))
    sbs.paste(old_night, (0, 0))
    sbs.paste(night, (CANVAS_W + 8, 0))
    save(sbs, 'old-vs-new-night.png')
    # 2 倍放大
    for nm, box_ in (('zoom-bed', (600, 140, 920, 470)), ('zoom-cauldron', (440, 360, 620, 520)),
                     ('zoom-fireplace', (800, 230, 1030, 560)), ('zoom-books', (120, 100, 460, 420)),
                     ('zoom-alchemy', (430, 120, 700, 330)), ('zoom-left', (40, 260, 400, 560))):
        save(day.crop(box_).resize(((box_[2] - box_[0]) * 2, (box_[3] - box_[1]) * 2), Image.NEAREST), nm + '.png')
        save(night.crop(box_).resize(((box_[2] - box_[0]) * 2, (box_[3] - box_[1]) * 2), Image.NEAREST), nm + '-night.png')
    save(debug_overlay(compose(arts, False, [])), 'debug-collision.png')
    # 動畫 GIF（鍋爐 6 幀、爐火 2 幀）
    for base_nm, n, box_, dur in (('cauldron', 6, (440, 360, 620, 520), 140), ('fireplace-fire', 2, (800, 230, 1030, 560), 250)):
        frames = []
        for k in range(n if n > 2 else 4):
            im = compose(arts, False, [], frame=k if base_nm == 'cauldron' else 0, fire_frame=k % 2)
            frames.append(im.crop(box_).resize(((box_[2] - box_[0]) * 2, (box_[3] - box_[1]) * 2), Image.NEAREST))
        p = os.path.join(outdir, base_nm + '.gif')
        frames[0].save(p, save_all=True, append_images=frames[1:], duration=dur, loop=0)
        files.append(p)
    # 單件放大
    names = [nm for nm in arts if not nm.startswith('shell')]
    tiles = [Image.fromarray(arts[nm]) for nm in names]
    Wt = 1500
    x = y = rowh = 0
    pos = []
    for t in tiles:
        if x + t.width * 2 > Wt:
            x, y, rowh = 0, y + rowh + 8, 0
        pos.append((x, y))
        x += t.width * 2 + 8
        rowh = max(rowh, t.height * 2)
    sheet = Image.new('RGBA', (Wt, y + rowh), (60, 70, 64, 255))
    for t, (x, y) in zip(tiles, pos):
        sheet.alpha_composite(t.resize((t.width * 2, t.height * 2), Image.NEAREST), (x, y))
    save(sheet.convert('RGB'), 'pieces8.png')
    return files


def main():
    args = sys.argv[1:]
    out_dir = OUT_DIR
    if '--out' in args:
        out_dir = args[args.index('--out') + 1]
    preview_dir = args[args.index('--preview') + 1] if '--preview' in args else None
    only = None
    if '--only' in args:
        only = set(args[args.index('--only') + 1].split(','))
    arts = build_all(only)
    bad = check_sizes(arts)
    if bad:
        print('⚠️ 尺寸不符：\n  ' + '\n  '.join(bad))
        sys.exit(1)
    missing = [art_name(f) for p in LAYOUT['pieces'] for f in p['frames']
               if art_name(f) not in arts and p['name'] != 'cat']
    if missing and not only:
        print('⚠️ 沒畫到：' + ', '.join(sorted(set(missing))))
    write_arts(arts, out_dir)
    print('寫出 %d 張圖到 %s' % (len(arts) + 1, out_dir))
    cx, cy = px_to_world(*room_px(*CAT_BED_UV))
    print('貓窩：地板 uv (%g, %g) → 世界 (%.1f, %.1f)' % (CAT_BED_UV[0], CAT_BED_UV[1], cx, cy))
    if preview_dir:
        for f in preview(arts, preview_dir):
            print('預覽：' + f)


if __name__ == '__main__':
    main()
