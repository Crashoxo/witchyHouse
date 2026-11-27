#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
家裡（藥水室 brew）自己擺家具的離線檢查 —— 不開 Unity，直接讀 C# 原始碼裡的數字與規則常數。

    python tools/check_home_place.py            # 檢查；有問題結束碼 1
    python tools/check_home_place.py --png DIR  # 另外輸出合成預覽（白天／夜晚／除錯圖）

讀（一律讀原始碼，這裡不另寫規則數字）：
  * Data/BrewRoomLayout.cs  —— 可走範圍、出生點、互動點與範圍、每件家具的碰撞／uv 盒子／排序（經 gen_brew_room8.parse_layout）
  * Core/HomePlacement.cs   —— Snap、Inset、DoorClear、GreetClear、UseClear、CatBedHalf、Step、NearX/NearY、BaseA/BaseK、UseSpots
  * Core/RoomCat.cs         —— DrawnBedAt（貓窩）、DoorGreet、Radius
  * Data/ArtFootprints.cs   —— PlayerRadius
  * Data/Furniture.cs、Data/Decor.cs、Data/FurnitureArt8.cs —— 佔地 W×H、種類、燈、圖的尺寸／實心範圍／光點
驗：
  (0) 空房間：UseSpots 都站得住、從出生點走得到、在各自互動範圍內；可達性規則（ReachOk）成立
  (a) 空地面積；1×1（燈、龜背芋、邊几、貓跳台）與 2×1 沙發（兩個方向）各有幾個合法位置、列出例子
  (b) 一組範例擺設（3 盞燈、沙發、貓跳台、龜背芋、2 張地毯、幾個裝飾）逐件照規則擺進去 →
      出生點走得到每個互動點範圍、門的自動觸發範圍；貓（半徑 8）從貓窩走得到門口迎接點
  (c) 規則擋得住：沙發擺門口＝Door、邊几擺床前站位＝UseSpot、地毯蓋貓窩＝CatBed；
      再用一排會擋路的家具把床圍起來 —— 每件單獨看都不違反 ①～⑤，但最後一件會讓床走不到 → Check 回 CutOff
"""
import math
import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_brew_room8 as B8  # noqa: E402  （只讀 LAYOUT 與合成小工具；import 時不會重畫）

ROOT = B8.ROOT
SCRIPTS = os.path.join(ROOT, 'Assets', 'Scripts')
RES = os.path.join(ROOT, 'Assets', 'Resources')
NUM = r'(-?\d+(?:\.\d+)?)f?'


def read(*p):
    with open(os.path.join(SCRIPTS, *p), encoding='utf-8') as f:
        return f.read()


def cconst(src, name):
    m = re.search(r'const float [^;]*?\b' + name + r'\s*=\s*' + NUM, src)
    if not m:
        raise SystemExit('找不到常數 ' + name)
    return float(m.group(1))


def cvec(src, name):
    m = re.search(name + r'\s*=\s*new(?:\s+Vector2)?\(\s*' + NUM + r'\s*,\s*' + NUM + r'\s*\)', src)
    if not m:
        raise SystemExit('找不到 ' + name)
    return float(m.group(1)), float(m.group(2))


# ──────────── 讀 C# ────────────

HP = read('Core', 'HomePlacement.cs')
SNAP = cconst(HP, 'Snap')
INSET = cconst(HP, 'Inset')
DOOR_CLEAR = cconst(HP, 'DoorClear')
GREET_CLEAR = cconst(HP, 'GreetClear')
USE_CLEAR = cconst(HP, 'UseClear')
STEP = cconst(HP, 'Step')
NEAR_X = cconst(HP, 'NearX')
NEAR_Y = cconst(HP, 'NearY')
BASE_A = cconst(HP, 'BaseA')
BASE_K = cconst(HP, 'BaseK')
CAT_BED_HALF = cvec(HP, 'CatBedHalf')
USE_SPOTS = [(float(a), float(b)) for a, b in
             re.findall(r'new\(\s*' + NUM + r'\s*,\s*' + NUM + r'\s*\)', re.search(r'UseSpots\s*=\s*\{(.*?)\};', HP, re.S).group(1))]
CAT = read('Core', 'RoomCat.cs')
CAT_BED = cvec(CAT, 'DrawnBedAt')
DOOR_GREET = cvec(CAT, 'DoorGreet')
CAT_R = cconst(CAT, 'Radius')
PLAYER_R = cconst(read('Data', 'ArtFootprints.cs'), 'PlayerRadius')
LAY = read('Data', 'BrewRoomLayout.cs')
ISO_X, ISO_Y = cconst(LAY, 'IsoX'), cconst(LAY, 'IsoY')
EXIT_AUTO = cconst(LAY, 'ExitAuto')
SPAWN = cvec(LAY, 'Spawn')
L = B8.LAYOUT
POINTS = L['points']             # name → ((x, y), range)
EXIT_AT = POINTS['exit'][0]
WALK = L['walk']

FURN = {}
for m in re.finditer(r'\("(\w+)",\s*"[^"]*",\s*\d+,\s*"[^"]*",\s*(\d+),\s*(\d+),\s*FurnKind\.(\w+),\s*(true|false)\)', read('Data', 'Furniture.cs')):
    FURN[m.group(1)] = dict(w=int(m.group(2)), h=int(m.group(3)), kind=m.group(4))
LIGHTS = {}
for m in re.finditer(r'\["(\w+)"\]\s*=\s*new LightSpec\(' + NUM + r',\s*new Color32\((\d+), (\d+), (\d+), \d+\),\s*' + NUM, read('Data', 'Furniture.cs')):
    LIGHTS[m.group(1)] = (float(m.group(2)), (int(m.group(3)), int(m.group(4)), int(m.group(5))), float(m.group(6)))
DEC_SRC = read('Data', 'Decor.cs')
DECOR = {}
for m in re.finditer(r'new\(\)\s*\{\s*Id\s*=\s*"(\w+)"(.*?)\}', DEC_SRC, re.S):
    DECOR[m.group(1)] = dict(rug='FurnKind.Rug' in m.group(2))
    lm = re.search(r'Light = new LightSpec\(' + NUM + r',\s*new UnityEngine\.Color32\((\d+), (\d+), (\d+), \d+\),\s*' + NUM, m.group(2))
    if lm:
        LIGHTS[m.group(1)] = (float(lm.group(1)), (int(lm.group(2)), int(lm.group(3)), int(lm.group(4))), float(lm.group(5)))
ART8 = {}
for m in re.finditer(r'\["(\w+)"\] = new Entry\((\d+), (\d+), new ArtBox\(\d+, \d+, ([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+)\),\s*(?:NoSlots|new\[\].*?\}\)),?\s*(NoLights|new\[\] \{(.*?)\})\)',
                     read('Data', 'FurnitureArt8.cs'), re.S):
    lights = [(float(a), float(b)) for a, b in re.findall(r'new Vector2\(' + NUM + r', ' + NUM + r'\)', m.group(9) or '')]
    ART8[m.group(1)] = dict(W=int(m.group(2)), H=int(m.group(3)), box=tuple(float(m.group(i)) for i in range(4, 8)), lights=lights)


# ──────────── 幾何（同 HomePlacement.cs）────────────

def to_uv(x, y):
    dx, dy = x - ISO_X, ISO_Y - y
    return dy + dx * 0.5, dy - dx * 0.5


def from_uv(u, v):
    return ISO_X + u - v, ISO_Y - (u + v) * 0.5


def snap(x, y):
    u, v = to_uv(x, y)
    return from_uv(round(u / SNAP) * SNAP, round(v / SNAP) * SNAP)


def ccw(pts):
    a = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    return list(reversed(pts)) if a < 0 else list(pts)


def poly_dist(poly, x, y):
    """有號距離（外正內負）；x, y 可以是 numpy 陣列。poly 要逆時針。"""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    best = np.full(x.shape, np.inf)
    inside = np.ones(x.shape, bool)
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        if l2 < 1e-8:
            continue
        t = np.clip(((x - ax) * dx + (y - ay) * dy) / l2, 0, 1)
        best = np.minimum(best, (x - ax - dx * t) ** 2 + (y - ay - dy * t) ** 2)
        inside &= ~(dx * (y - ay) - dy * (x - ax) < 0)
    d = np.sqrt(best)
    return np.where(inside, -d, d)


def ellipse_poly(cx, cy, rx, ry, n=16):
    return [(cx + math.cos(i * 2 * math.pi / n) * rx, cy + math.sin(i * 2 * math.pi / n) * ry) for i in range(n)]


def footprint(front, w, h, inset):
    ex, ey = (32.0, -16.0), (-32.0, -16.0)

    def G(a, b):
        return (front[0] + (a - w) * ex[0] + (b - h) * ey[0], front[1] + (a - w) * ex[1] + (b - h) * ey[1])
    return [G(inset, inset), G(w - inset, inset), G(w - inset, h - inset), G(inset, h - inset)]


def is_grid(i):
    return i in FURN


def is_flat(i):
    return i in DECOR and DECOR[i]['rug']


def art_size(i):
    a = ART8.get(i)
    return (a['W'], a['H']) if a else (48.0, 64.0)


def shape(i, pos, flip=False):
    s = dict(id=i, pos=pos, flip=flip, grid=is_grid(i), flat=is_flat(i), blocks=is_grid(i))
    iw, ih = art_size(i)
    if s['grid']:
        f = FURN[i]
        w, h = (f['h'], f['w']) if flip else (f['w'], f['h'])
        s['foot'] = footprint(pos, w, h, 0.0)
        s['solid'] = footprint(pos, w, h, INSET)
        u, v = to_uv(*pos)
        s['U0'], s['U1'], s['V0'], s['V1'] = u - 32 * w, u, v - 32 * h, v
        x0, y0, x1, y1 = ART8[i]['box'] if i in ART8 else (0, 0, iw, ih)
        if flip:
            x0, x1 = iw - x1, iw - x0
        s['art'] = (pos[0] - iw / 2 + x0, pos[1] + y0, pos[0] - iw / 2 + x1, pos[1] + y1)
    else:
        if s['flat']:
            c, rx, ry = (pos[0], pos[1] + iw * 0.25), iw * 0.5, iw * 0.25
        else:
            rx = max(6.0, iw * 0.32)
            c, ry = (pos[0], pos[1] + rx * 0.5), rx * 0.5
        s['foot'] = ellipse_poly(c[0], c[1], rx, ry)
        s['solid'] = None
        u, v = to_uv(*c)
        r = rx / math.sqrt(2)
        s['U0'], s['U1'], s['V0'], s['V1'] = u - r, u + r, v - r, v + r
        s['art'] = (pos[0] - iw / 2, pos[1], pos[0] + iw / 2, pos[1] + ih)
    s['depth'] = (s['U0'] + s['U1'] + s['V0'] + s['V1']) / 2
    return s


def overlaps(a, b):
    def sep(p, q):
        for i in range(len(p)):
            ex, ey = p[(i + 1) % len(p)][0] - p[i][0], p[(i + 1) % len(p)][1] - p[i][1]
            nx, ny = -ey, ex
            if nx * nx + ny * ny < 1e-10:
                continue
            pp = [v[0] * nx + v[1] * ny for v in p]
            qq = [v[0] * nx + v[1] * ny for v in q]
            if max(pp) <= min(qq) + 1e-3 or max(qq) <= min(pp) + 1e-3:
                return True
        return False
    return not sep(a, b) and not sep(b, a)


def seg_point(a, b, p):
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = 0 if l2 < 1e-8 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return math.hypot(p[0] - a[0] - dx * t, p[1] - a[1] - dy * t)


def cross_seg(a, b, c, d):
    def cr(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1, d2, d3, d4 = cr(c, d, a), cr(c, d, b), cr(a, b, c), cr(a, b, d)
    return ((d1 > 0 > d2) or (d1 < 0 < d2)) and ((d3 > 0 > d4) or (d3 < 0 < d4))


def poly_near_seg(poly, a, b, r):
    pc = ccw(poly)
    if float(poly_dist(pc, a[0], a[1])) <= r or float(poly_dist(pc, b[0], b[1])) <= r:
        return True
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        if cross_seg(a, b, p, q) or min(seg_point(a, b, p), seg_point(a, b, q), seg_point(p, q, a), seg_point(p, q, b)) <= r:
            return True
    return False


# 房間原本的東西
FIXED = []
for p in L['pieces']:
    if p['shape'] == 'Poly':
        FIXED.append(dict(name=p['name'], poly=ccw(p['poly']), ell=None))
    elif p['shape'] == 'Ellipse':
        cx, cy, hx, hy = p['ell']
        FIXED.append(dict(name=p['name'], poly=ellipse_poly(cx, cy, hx, hy), ell=(cx, cy, hx, hy)))
FIXED_SORT = [p for p in L['pieces'] if p['kind'] == 'Stand' and p['name'] != 'cat']
WALK_CCW = ccw(WALK)
CAT_BED_POLY = ellipse_poly(CAT_BED[0], CAT_BED[1], CAT_BED_HALF[0], CAT_BED_HALF[1])

XS = [q[0] for q in WALK]
YS = [q[1] for q in WALK]
GX0, GY0 = min(XS), min(YS)
GW = int((max(XS) - GX0) // STEP) + 1
GH = int((max(YS) - GY0) // STEP) + 1
GXX, GYY = np.meshgrid(GX0 + np.arange(GW) * STEP, GY0 + np.arange(GH) * STEP)   # [j, i]
IN_WALK = poly_dist(WALK_CCW, GXX, GYY) <= 0


def fixed_pen(r):
    worst = np.full(GXX.shape, -np.inf)
    for f in FIXED:
        if f['ell']:
            cx, cy, hx, hy = f['ell']
            rx, ry = hx + r, hy + r
            v = (1 - np.sqrt(((GXX - cx) / rx) ** 2 + ((GYY - cy) / ry) ** 2)) * min(rx, ry)
        else:
            v = r - poly_dist(f['poly'], GXX, GYY)
        worst = np.maximum(worst, v)
    return worst


BASE_PLAYER = IN_WALK & (fixed_pen(PLAYER_R) <= 0)
BASE_CAT = IN_WALK & (fixed_pen(CAT_R) <= 0)


def free_grid(solids, r, base):
    free = base.copy()
    for s in solids:
        pc = ccw(s)
        free &= ~(r - poly_dist(pc, GXX, GYY) > 0)
    return free


def nearest_idx(mask, p, maxr=8):
    ci, cj = round((p[0] - GX0) / STEP), round((p[1] - GY0) / STEP)
    best = None
    for rr in range(maxr + 1):
        for j in range(cj - rr, cj + rr + 1):
            for i in range(ci - rr, ci + rr + 1):
                if 0 <= i < GW and 0 <= j < GH and mask[j, i]:
                    d = (GXX[j, i] - p[0]) ** 2 + (GYY[j, i] - p[1]) ** 2
                    if best is None or d < best[0]:
                        best = (d, j, i)
        if best:
            return best[1], best[2]
    return None


def flood(free, start):
    s = nearest_idx(free, start)
    if s is None:
        return np.zeros_like(free)
    lab, _ = ndimage.label(free)      # 預設 4 連通（同 Obstacles.SelfCheck）
    return lab == lab[s]


def any_within(reach, at, rng):
    return bool(np.any(reach & ((GXX - at[0]) ** 2 + (GYY - at[1]) ** 2 <= rng * rng)))


def reach_report(solids):
    """回傳 (全部 OK?, 細項 dict, 女巫可達格, 貓可達格)。"""
    reach = flood(free_grid(solids, PLAYER_R, BASE_PLAYER), SPAWN)
    out = {}
    for k in ('bed', 'wardrobe', 'chest', 'cauldron'):
        at, rng = POINTS[k]
        out[k] = any_within(reach, at, rng)
    out['exit(自動觸發 %g)' % EXIT_AUTO] = any_within(reach, EXIT_AT, EXIT_AUTO)
    cfree = free_grid(solids, CAT_R, BASE_CAT)
    creach = flood(cfree, CAT_BED)
    g = nearest_idx(cfree, DOOR_GREET, 6)
    out['貓：貓窩→迎接點'] = g is not None and bool(creach[g])
    return all(out.values()), out, reach, creach


def check(me, others, reach=True):
    inner = me['solid'] or me['foot']
    if any(float(poly_dist(WALK_CCW, q[0], q[1])) > 0 for q in inner):
        return 'OffFloor'
    if me['flat']:
        return 'CatBed' if overlaps(me['foot'], CAT_BED_POLY) else 'Ok'
    for f in FIXED:
        if overlaps(me['foot'], f['poly']):
            return 'Overlap'
    for o in others:
        if not o['flat'] and overlaps(me['foot'], o['foot']):
            return 'Overlap'
    if poly_near_seg(me['foot'], EXIT_AT, SPAWN, DOOR_CLEAR) or poly_near_seg(me['foot'], DOOR_GREET, DOOR_GREET, GREET_CLEAR):
        return 'Door'
    for u in USE_SPOTS:
        if poly_near_seg(me['foot'], u, u, USE_CLEAR):
            return 'UseSpot'
    if overlaps(me['foot'], CAT_BED_POLY):
        return 'CatBed'
    if reach and me['blocks']:
        solids = [o['solid'] for o in others if o['blocks'] and o['solid']] + [me['solid']]
        if not reach_report(solids)[0]:
            return 'CutOff'
    return 'Ok'


# ──────────── 排序（同 HomePlacement.AssignOrders）────────────

def front(a, b):
    su = 1 if a[0] >= b[1] else -1 if b[0] >= a[1] else 0
    sv = 1 if a[2] >= b[3] else -1 if b[2] >= a[3] else 0
    if su and sv and su != sv:
        su = sv = 0
    if su:
        return su > 0
    if sv:
        return sv > 0
    return sum(a) > sum(b)


def near(a, b):
    return a[0] - NEAR_X < b[2] and b[0] < a[2] + NEAR_X and a[1] - NEAR_Y < b[3] and b[1] < a[3] + NEAR_Y


def pick(base, lo, hi):
    want = base
    if lo is not None and hi is not None and hi - lo < 8:
        want = (lo + hi) / 2
    else:
        if lo is not None:
            want = max(want, lo + 4)
        if hi is not None:
            want = min(want, hi - 4)
    c = int(round(want / 4)) * 4
    if lo is not None and c <= lo:
        c += 4
    if hi is not None and c >= hi and (lo is None or c - 4 > lo):
        c -= 4
    return c


def assign_orders(items):
    orders = [0] * len(items)
    flat = 0
    idx = []
    for i, s in enumerate(items):
        if s['flat']:
            orders[i] = -9000 + flat
            flat += 1
        else:
            idx.append(i)
    idx.sort(key=lambda i: (items[i]['depth'], i))
    done = []
    for i in idx:
        me = items[i]
        box = (me['U0'], me['U1'], me['V0'], me['V1'])
        lo = hi = None
        for f in FIXED_SORT:
            r = f['rect']
            if not near(me['art'], r):
                continue
            if front(box, (f['U0'], f['U1'], f['V0'], f['V1'])):
                lo = f['order'] if lo is None else max(lo, f['order'])
            else:
                hi = f['order'] if hi is None else min(hi, f['order'])
        for j in done:
            o = items[j]
            if not near(me['art'], o['art']):
                continue
            if front(box, (o['U0'], o['U1'], o['V0'], o['V1'])):
                lo = orders[j] if lo is None else max(lo, orders[j])
            else:
                hi = orders[j] if hi is None else min(hi, orders[j])
        orders[i] = pick(BASE_A + BASE_K * me['depth'], lo, hi)
        done.append(i)
    return orders


def player_order(wx, wy, w, h, items, orders):
    """同 BrewRoom.PlayerOrder（房間家具＋家裡擺的）。"""
    u, v = to_uv(wx, wy)
    x0, x1, y0, y1 = wx - w * 0.35, wx + w * 0.35, wy, wy + h * 0.9
    lo = hi = None
    boxes = [((p['U0'], p['U1'], p['V0'], p['V1']), p['rect'], p['order']) for p in FIXED_SORT]
    boxes += [((s['U0'], s['U1'], s['V0'], s['V1']), s['art'], orders[k]) for k, s in enumerate(items) if not s['flat']]
    for (U0, U1, V0, V1), r, o in boxes:
        if x1 <= r[0] or r[2] <= x0 or y1 <= r[1] or r[3] <= y0:
            continue
        if u >= U1 or v >= V1:
            f = True
        elif u <= U0 or v <= V0:
            f = False
        else:
            f = u + v > (U0 + U1 + V0 + V1) / 2
        if f:
            lo = o if lo is None else max(lo, o)
        else:
            hi = o if hi is None else min(hi, o)
    if lo is None and hi is None:
        return round(-wy)
    if lo is None:
        return hi - 1
    return lo + 1


# ──────────── 擺設的小工具 ────────────

LATTICE = []
for _u in np.arange(0, 640, SNAP):
    for _v in np.arange(0, 440, SNAP):
        _x, _y = from_uv(float(_u), float(_v))
        if float(poly_dist(WALK_CCW, _x, _y)) <= 0:
            LATTICE.append((_x, _y))


def place_near(item, target, placed, flip=False, reach=True):
    for p in sorted(LATTICE, key=lambda q: (q[0] - target[0]) ** 2 + (q[1] - target[1]) ** 2):
        s = shape(item, p, flip)
        if check(s, placed, reach) == 'Ok':
            return s
    return None


def fmt(p):
    return '(%.0f, %.0f)' % p


SAMPLE = [  # (id, 想擺的地方附近, 翻面)
    ('rug_round', (-215, -70), False),
    ('rug_star', (170, -130), False),
    ('sofa_small', (-150, -200), False),
    ('lamp_lantern', (-235, -215), False),
    ('lamp_moon', (-55, 35), False),
    ('lamp_mushroom', (150, -205), False),
    ('cat_tree', (240, -160), False),
    ('plant_monstera', (-45, 115), False),
    ('side_table', (-80, -230), False),
    ('roses_vase', (-205, -30), False),
    ('succulent', (110, -60), False),
    ('blue_urn', (-330, -175), False),
]


def main():
    args = sys.argv[1:]
    png = args[args.index('--png') + 1] if '--png' in args else None
    bad = []
    print('規則常數（HomePlacement.cs）：Snap %g、Inset %g、DoorClear %g、GreetClear %g、UseClear %g、貓窩 %s、Step %g、女巫半徑 %g、貓半徑 %g'
          % (SNAP, INSET, DOOR_CLEAR, GREET_CLEAR, USE_CLEAR, CAT_BED_HALF, STEP, PLAYER_R, CAT_R))

    # (0) 空房間
    print('\n(0) 空房間')
    ok0, det0, reach0, creach0 = reach_report([])
    print('  可達性：' + '、'.join('%s %s' % (k, '✓' if v else '✗') for k, v in det0.items()))
    if not ok0:
        bad.append('空房間就不滿足可達性')
    names = ['bed', 'wardrobe', 'chest', 'cauldron']
    for (x, y), nm in zip(USE_SPOTS, names):
        at, rng = POINTS[nm]
        ij = nearest_idx(reach0, (x, y), 1)
        stand = bool(IN_WALK[round((y - GY0) / STEP), round((x - GX0) / STEP)]) and float(fixed_pen(PLAYER_R)[round((y - GY0) / STEP), round((x - GX0) / STEP)]) <= 0
        d = math.dist((x, y), at)
        good = stand and ij is not None and d <= rng
        print('  站位 %-8s %s：%s、離互動點 %.1f（範圍 %g）、%s' % (nm, fmt((x, y)), '站得住' if stand else '✗站不住', d, rng,
                                                       '走得到' if ij is not None else '✗走不到'))
        if not good:
            bad.append('站位 %s 不合格' % nm)

    # (a) 空地
    print('\n(a) 空地與合法位置')
    cell_area = STEP * STEP
    floor_px = IN_WALK.sum() * cell_area
    free_px = (IN_WALK & (fixed_pen(0) <= 0)).sum() * cell_area
    zone = np.zeros_like(IN_WALK)
    for u in USE_SPOTS:
        zone |= (GXX - u[0]) ** 2 + (GYY - u[1]) ** 2 <= USE_CLEAR ** 2
    t = np.clip(((GXX - EXIT_AT[0]) * (SPAWN[0] - EXIT_AT[0]) + (GYY - EXIT_AT[1]) * (SPAWN[1] - EXIT_AT[1]))
                / ((SPAWN[0] - EXIT_AT[0]) ** 2 + (SPAWN[1] - EXIT_AT[1]) ** 2), 0, 1)
    zone |= np.hypot(GXX - EXIT_AT[0] - t * (SPAWN[0] - EXIT_AT[0]), GYY - EXIT_AT[1] - t * (SPAWN[1] - EXIT_AT[1])) <= DOOR_CLEAR
    zone |= (GXX - DOOR_GREET[0]) ** 2 + (GYY - DOOR_GREET[1]) ** 2 <= GREET_CLEAR ** 2
    zone |= ((GXX - CAT_BED[0]) / CAT_BED_HALF[0]) ** 2 + ((GYY - CAT_BED[1]) / CAT_BED_HALF[1]) ** 2 <= 1
    usable_px = (IN_WALK & (fixed_pen(0) <= 0) & ~zone).sum() * cell_area
    print('  地板（可走範圍）≈ %d px²；扣掉房間家具 ≈ %d px²；再扣掉門口／站位／貓窩禁區 ≈ %d px²（%.0f%%）；吸附點 %d 個'
          % (floor_px, free_px, usable_px, 100 * usable_px / floor_px, len(LATTICE)))
    for item, flip in (('lamp_moon', False), ('plant_monstera', False), ('side_table', False), ('cat_tree', False),
                       ('sofa_small', False), ('sofa_small', True), ('rug_round', False)):
        valid = [p for p in LATTICE if check(shape(item, p, flip), [], reach=False) == 'Ok']
        # 抽幾個分散的例子，再補跑可達性
        ex = []
        for p in sorted(valid, key=lambda q: (round(q[0] / 120), q[1])):
            if all(math.dist(p, e) > 110 for e in ex):
                ex.append(p)
        ex = [p for p in ex if check(shape(item, p, flip), [], reach=True) == 'Ok'][:6]
        print('  %-15s%s 合法位置 %4d 個；例：%s' % (item, '（翻面）' if flip else '', len(valid), '  '.join(fmt(p) for p in ex)))
        if len(valid) < 6:
            bad.append('%s 合法位置太少' % item)

    # (b) 範例擺設
    print('\n(b) 範例擺設（逐件照規則擺，含可達性）')
    placed = []
    for item, target, flip in SAMPLE:
        s = place_near(item, target, placed, flip)
        if s is None:
            print('  %-15s 想擺 %s：✗ 找不到合法位置' % (item, fmt(target)))
            bad.append('範例 %s 擺不下' % item)
            continue
        placed.append(s)
        print('  %-15s 想擺 %s → %s（離目標 %.0f）' % (item, fmt(target), fmt(s['pos']), math.dist(s['pos'], target)))
    solids = [s['solid'] for s in placed if s['blocks']]
    okb, detb, reachb, creachb = reach_report(solids)
    print('  擺完的可達性：' + '、'.join('%s %s' % (k, '✓' if v else '✗') for k, v in detb.items()))
    print('  女巫可走格 %d → %d（少 %.1f%%）；貓可走格 %d → %d' % (reach0.sum(), reachb.sum(), 100 * (1 - reachb.sum() / reach0.sum()),
                                                        creach0.sum(), creachb.sum()))
    if not okb:
        bad.append('範例擺設擋到路')
    orders = assign_orders(placed)
    print('  排序：' + '、'.join('%s %d' % (s['id'], o) for s, o in zip(placed, orders)))
    if any(o % 4 for s, o in zip(placed, orders) if not s['flat']):
        bad.append('排序不是 4 的倍數')

    # (c) 規則擋得住
    print('\n(c) 規則擋得住')
    cases = [('sofa_small', SPAWN, 'Door', '沙發擺在出生點'),
             ('rug_round', (CAT_BED[0], CAT_BED[1] - 12), 'CatBed', '地毯蓋貓窩'),
             ('cat_tree', (CAT_BED[0] + 6, CAT_BED[1] - 6), 'CatBed', '貓跳台壓貓窩'),
             ('lamp_lantern', (430, -260), 'OffFloor', '燈擺到牆外'),
             ('side_table', (-22, -125), 'Overlap', '邊几壓到鍋爐')]
    for item, at, want, label in cases:
        got = check(shape(item, snap(*at)), [], True)
        print('  %-14s → %-8s %s' % (label, got, '✓' if got == want else '✗ 應該是 ' + want))
        if got != want:
            bad.append('擋不住：' + label)
    # 站位與門口：所有「佔地蓋到站位／門口走道（含女巫半徑）」的位置都要被擋（原因不一定是 UseSpot —— 也可能先疊到家具）
    for label, a_, b_, r_ in [('床前站位', USE_SPOTS[0], USE_SPOTS[0], PLAYER_R), ('衣櫃前站位', USE_SPOTS[1], USE_SPOTS[1], PLAYER_R),
                              ('木箱前站位', USE_SPOTS[2], USE_SPOTS[2], PLAYER_R), ('鍋爐前站位', USE_SPOTS[3], USE_SPOTS[3], PLAYER_R),
                              ('門→出生點', EXIT_AT, SPAWN, PLAYER_R), ('貓迎接點', DOOR_GREET, DOOR_GREET, CAT_R)]:
        hits, leaks, why = 0, [], {}
        for item in ('side_table', 'sofa_small', 'roses_vase'):
            for p in LATTICE:
                if math.dist(p, a_) > 140 and math.dist(p, b_) > 140:
                    continue
                sh = shape(item, p)
                if not poly_near_seg(sh['foot'], a_, b_, r_):
                    continue
                hits += 1
                got = check(sh, [], reach=False)
                why[got] = why.get(got, 0) + 1
                if got == 'Ok':
                    leaks.append((item, p))
        print('  蓋到%-6s的位置 %3d 個 → %s%s' % (label, hits, '、'.join('%s %d' % kv for kv in sorted(why.items())),
                                            '' if not leaks else '  ✗ 漏掉 %s' % leaks[:3]))
        if leaks:
            bad.append('擋不住：蓋到' + label)

    # 把床／門口圍起來：一件一件加（每件只看 ①～⑤，而且單獨加不會壞可達性），直到某一件會讓目標走不到 —— 那一件 Check 要回 CutOff
    def seal(center, rmin, rmax, keys):
        wall = []
        for p in sorted(LATTICE, key=lambda q: math.dist(q, center)):
            if not rmin <= math.dist(p, center) <= rmax:
                continue
            for item in ('sofa_small', 'bookshelf', 'side_table'):
                done = False
                for flip in (False, True):
                    sh = shape(item, p, flip)
                    if check(sh, wall, reach=False) != 'Ok':
                        continue
                    ok, det, _, _ = reach_report([w['solid'] for w in wall] + [sh['solid']])
                    if ok:
                        wall.append(sh)
                        done = True
                        break
                    if any((keys is None or k in keys) and not v for k, v in det.items()):
                        return wall, sh, det
                if done:
                    break
        return wall, None, None

    wall_png = []
    # 堵門口：門口一圈封起來時，貓（貓窩→門口迎接點）通常最先斷 —— 哪一項先斷都算
    for label, center, rmin, rmax, keys in (('圍床', POINTS['bed'][0], 70, 230, ('bed',)), ('堵門口', SPAWN, 40, 190, None)):
        wall, cut, det = seal(center, rmin, rmax, keys)
        if cut is None:
            print('  %s：✗ 找不到會擋路的組合（規則沒被考到）' % label)
            bad.append('沒考到 CutOff：' + label)
            continue
        got = check(cut, wall, True)
        lost = [k for k, v in det.items() if not v]
        print('  %s：先擺 %d 件（各自合法、擺完都還走得到），第 %d 件 %s 擺在 %s 會讓「%s」走不到 → Check＝%s %s'
              % (label, len(wall), len(wall) + 1, cut['id'], fmt(cut['pos']), '、'.join(lost), got, '✓' if got == 'CutOff' else '✗'))
        if got != 'CutOff':
            bad.append(label + '沒被擋')
        wall_png.append((label, wall, cut))

    if png:
        os.makedirs(png, exist_ok=True)
        files = previews(png, placed, orders, reachb, creachb, wall_png)
        print('\n預覽：')
        for f in files:
            print('  ' + f)

    print('\n結果：' + ('全部通過' if not bad else '✗ ' + '；'.join(bad)))
    sys.exit(1 if bad else 0)


# ──────────── 預覽 ────────────

LIGHT_PTS_FLIP = True
HOME_RADIUS_K = HOME_STRENGTH_K = HOME_MAX_ALPHA = POOL_RADIUS_K = POOL_ALPHA_K = None


def light_consts():
    src = read('Core', 'FurnitureLight.cs')
    return (cconst(src, 'HomeRadiusK'), cconst(src, 'HomeStrengthK'), cconst(src, 'HomeMaxAlpha'),
            cconst(src, 'PoolRadiusK'), cconst(src, 'PoolAlphaK'))


LAMP_LIFT = cconst(read('Core', 'HomeFurnishings.cs'), 'LampNightLift')


def item_img(i, flip):
    sub = 'furniture8' if is_grid(i) else 'decor8'
    im = Image.open(os.path.join(RES, sub, i + '.png')).convert('RGBA')
    return im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im


def cat_img(row, col):
    sheet = Image.open(os.path.join(RES, 'cat8', 'cat.png')).convert('RGBA')
    c = sheet.crop((col * 40, row * 36, col * 40 + 40, row * 36 + 36))
    return c.resize((64, round(36 * 1.6)), Image.NEAREST)


def to_px(x, y):
    return x + B8.CANVAS_W / 2, B8.CANVAS_H / 2 - y


def glow_layer(img, x, y, rx, ry, rgb, alpha):
    g = Image.fromarray(B8.glow_image(128)).resize((max(2, int(rx * 2)), max(2, int(ry * 2))), Image.BILINEAR)
    a = np.asarray(g).astype(np.float32)
    a[..., 0], a[..., 1], a[..., 2] = rgb
    a[..., 3] *= alpha
    X, Y = to_px(x, y)
    img.alpha_composite(Image.fromarray(a.clip(0, 255).astype(np.uint8)), (int(X - rx), int(Y - ry)))


def compose(night, items, orders, witches, cats):
    HR, HS, HM, PR, PA = light_consts()
    arts = B8.load_set(os.path.join(RES, 'rooms', 'brew8'))
    img = Image.fromarray(arts['shell-night' if night else 'shell-day']).convert('RGBA')
    layers = []
    for p in L['pieces']:
        if p['name'] == 'cat':
            continue
        a = arts.get(B8.art_name(p['frames'][0]))
        if a is None:
            continue
        layers.append((p['order'], 'fixed', p, a))
    for s, o in zip(items, orders):
        layers.append((o, 'item', s, None))
        if night and s['id'] in LIGHTS:
            layers.append((-8900, 'pool', s, None))
    wimg = B8.witch_sprite()
    for (wx, wy) in witches:
        layers.append((player_order(wx, wy, wimg.width, wimg.height, items, orders) + 0.5, 'witch', (wx, wy), wimg))
    for (cx, cy, row, col) in cats:
        ci = cat_img(row, col)
        layers.append((player_order(cx, cy, ci.width, ci.height, items, orders) + 0.4, 'cat', (cx, cy), ci))
    for o, kind, p, a in sorted(layers, key=lambda t: t[0]):
        if kind == 'fixed':
            im = a
            if night and p['tint']:
                f = im.astype(np.float32)
                f[..., :3] *= np.array(B8.NIGHT_MUL, np.float32)
                im = f.clip(0, 255).astype(np.uint8)
            left = int(round(p['x'] - p['px'] + B8.CANVAS_W / 2))
            top = int(round(B8.CANVAS_H / 2 - (p['y'] - p['py']) - a.shape[0]))
            img.alpha_composite(Image.fromarray(im), (left, top))
        elif kind == 'item':
            im = item_img(p['id'], p['flip'])
            if night:
                mul = np.array(B8.NIGHT_MUL, np.float32)
                if p['id'] in LIGHTS:
                    mul = mul + (1 - mul) * LAMP_LIFT
                f = np.asarray(im).astype(np.float32)
                f[..., :3] *= mul
                im = Image.fromarray(f.clip(0, 255).astype(np.uint8))
            X, Y = to_px(*p['pos'])
            img.alpha_composite(im, (int(round(X - im.width / 2)), int(round(Y - im.height))))
        elif kind == 'pool':
            r, rgb, st = LIGHTS[p['id']]
            glow_layer(img, p['pos'][0], p['pos'][1] + 2, r * PR, r * PR / 2, rgb, st * PA)
        else:
            X, Y = to_px(*p)
            sh = Image.new('RGBA', (40, 12), (0, 0, 0, 0))
            ImageDraw.Draw(sh).ellipse([0, 0, 39, 11], fill=(20, 10, 25, 90))
            if kind == 'witch':
                img.alpha_composite(sh, (int(X - 20), int(Y - 6)))
                img.alpha_composite(a, (int(round(X - a.width / 2)), int(round(Y - a.height + 3 * 1.6))))
            else:
                img.alpha_composite(sh.resize((30, 9)), (int(X - 15), int(Y - 4)))
                img.alpha_composite(a, (int(round(X - a.width / 2)), int(round(Y - a.height + 3 * 1.6))))
    if night:
        for (gx, gy, r, k, fl) in L['glows']:
            glow_layer(img, gx, gy, r, r, B8.GLOW_COLOR, k * B8.GLOW_ALPHA)
        for s in items:
            if s['id'] not in LIGHTS:
                continue
            r, rgb, st = LIGHTS[s['id']]
            pts = ART8.get(s['id'], {}).get('lights') or [(0.0, 40.0)]
            for (lx, ly) in pts:
                glow_layer(img, s['pos'][0] + (-lx if s['flip'] else lx), s['pos'][1] + ly, r * HR, r * HR, rgb, min(HM, st * HS))
    bg = Image.new('RGBA', img.size, (24, 20, 30, 255))
    bg.alpha_composite(img)
    return bg.convert('RGB')


def debug(base, items, reach, creach, wall=None):
    a = np.asarray(base.convert('RGBA')).astype(np.float32)
    a[..., :3] = a[..., :3] * 0.55 + 18
    im = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(im, 'RGBA')
    P = to_px
    # 可達格（綠＝女巫走得到、藍點＝貓走得到）
    for j in range(GH):
        for i in range(GW):
            x, y = P(GXX[j, i], GYY[j, i])
            if reach[j, i]:
                d.rectangle([x - 1, y - 1, x + 1, y + 1], fill=(90, 230, 120, 200))
            elif creach[j, i]:
                d.point((x, y), fill=(120, 170, 255, 255))
    # 禁區
    zone = Image.new('RGBA', im.size, (0, 0, 0, 0))
    zd = ImageDraw.Draw(zone)
    for k in range(0, 11):
        x, y = P(EXIT_AT[0] + (SPAWN[0] - EXIT_AT[0]) * k / 10, EXIT_AT[1] + (SPAWN[1] - EXIT_AT[1]) * k / 10)
        zd.ellipse([x - DOOR_CLEAR, y - DOOR_CLEAR, x + DOOR_CLEAR, y + DOOR_CLEAR], fill=(255, 60, 60, 90))
    for (cx, cy), r in [(u, USE_CLEAR) for u in USE_SPOTS] + [(DOOR_GREET, GREET_CLEAR)]:
        x, y = P(cx, cy)
        zd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 60, 60, 90))
    x, y = P(*CAT_BED)
    zd.ellipse([x - CAT_BED_HALF[0], y - CAT_BED_HALF[1], x + CAT_BED_HALF[0], y + CAT_BED_HALF[1]], fill=(255, 120, 255, 110))
    im.alpha_composite(zone)
    d = ImageDraw.Draw(im, 'RGBA')
    d.polygon([P(*q) for q in WALK], outline=(255, 230, 60, 255))
    for f in FIXED:
        d.line([P(*q) for q in f['poly']] + [P(*f['poly'][0])], fill=(255, 50, 50, 255), width=2)
    for s in items:
        col = (255, 170, 255, 255) if s['flat'] else (80, 220, 255, 255)
        d.line([P(*q) for q in s['foot']] + [P(*s['foot'][0])], fill=col, width=2)
        if s['solid']:
            d.line([P(*q) for q in s['solid']] + [P(*s['solid'][0])], fill=(40, 120, 255, 255), width=1)
        X, Y = P(*s['pos'])
        d.ellipse([X - 2, Y - 2, X + 2, Y + 2], fill=(255, 255, 255, 255))
    if wall:
        ws, cut = wall
        for s in ws:
            d.polygon([P(*q) for q in s['foot']], fill=(255, 200, 60, 120), outline=(255, 200, 60, 255))
        d.polygon([P(*q) for q in cut['foot']], fill=(255, 30, 30, 170), outline=(255, 255, 255, 255))
    for nm in ('bed', 'wardrobe', 'chest', 'cauldron', 'exit'):
        (x, y), r = POINTS[nm]
        X, Y = P(x, y)
        d.ellipse([X - r, Y - r, X + r, Y + r], outline=(140, 255, 160, 200), width=1)
        d.ellipse([X - 3, Y - 3, X + 3, Y + 3], fill=(140, 255, 160, 255))
    X, Y = P(*SPAWN)
    d.ellipse([X - 5, Y - 5, X + 5, Y + 5], outline=(255, 255, 255, 255), width=2)
    return im.convert('RGB')


def previews(out, items, orders, reach, creach, wall):
    files = []
    witches = [(-110, -95), (40, -60), (-180, -255)]
    cats_day = [(-40, -205, 3, 0)]           # 坐在鍋爐前面的地板上
    cats_night = [(CAT_BED[0], CAT_BED[1] - 2 * 1.6, 5, 0)]   # 晚上在貓窩睡
    day = compose(False, items, orders, witches, cats_day)
    night = compose(True, items, orders, witches, cats_night)
    empty_night = compose(True, [], [], witches[:1], cats_night)
    for nm, im in (('home_day.png', day), ('home_night.png', night), ('home_night_empty.png', empty_night)):
        p = os.path.join(out, nm)
        im.save(p)
        files.append(p)
    for nm, im, box in (('home_day_x2_left.png', day, (60, 300, 560, 640)), ('home_night_x2_left.png', night, (60, 300, 560, 640)),
                        ('home_night_x2_right.png', night, (520, 260, 1020, 600))):
        p = os.path.join(out, nm)
        c = im.crop(box)
        c.resize((c.width * 2, c.height * 2), Image.NEAREST).save(p)
        files.append(p)
    p = os.path.join(out, 'home_debug.png')
    debug(day, items, reach, creach).save(p)
    files.append(p)
    for k, (label, ws, cut) in enumerate(wall):
        _, _, r2, c2 = reach_report([w['solid'] for w in ws + [cut]])
        p = os.path.join(out, 'home_debug_cutoff%d.png' % (k + 1))
        debug(compose(False, ws, assign_orders(ws), [], []), ws, r2, c2, (ws, cut)).save(p)
        files.append(p)
    return files


if __name__ == '__main__':
    main()
