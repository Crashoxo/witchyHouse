# -*- coding: utf-8 -*-
"""
NPC 尋路的離線檢查 ＋ 俯視預覽（不用開 Unity）—— 「路人走路不要穿牆」。

    python tools/check_npc_paths.py [輸出資料夾]

對城鎮（town）與糖果鎮（candy）做跟遊戲裡 Core/TownNav.cs **同一套規則**的尋路：
  ● 障礙：tools/check_walkable.py 的 build()（＝玩家碰撞的那一份：物件落地範圍、城鎮挖門、河、招牌柱腳）；
  ● 格距 CellSize、NPC 半徑 Radius、線段取樣 SampleStep、拉直最多看幾點 MaxPull、吸附圈數 SnapRings
    **直接從 TownNav.cs 讀**（這支不自己寫這些數字）；
  ● 格子中心「在可走範圍內 且 半徑 Radius 的腳底圓不碰障礙」才可站；直向邊多驗中點、斜向不切角＋驗 1/4、1/2、3/4；
  ● A*（八向、octile）→ 拉直（取樣驗直線，第一個走不到就停）；
  ● 城鎮偏好走路面：離路點 PreferRadius 內算路面、草地代價 × OffRoadCost，拉直不把路面上的一段拉成斜切草地。
後花園另外畫一張預覽（FenceWalk 折線 ＋ 橫向偏移極限；後花園沒有障礙資料，用眼睛看）。
輸出：
  1. 吸附過的路點（原座標 → 新座標）—— 路點本身站不住（落在建築裡）時換到最近的可站格中心；
  2. 路點兩兩求路：不連通的路點對（遊戲裡會換一個目的地，不會走）；
  3. 所有路徑（含隨機偏移後的停點，跟遊戲一樣先用 GoodStop 驗）每 2px 取樣，**落在障礙裡的次數**（半徑 0，要是 0），
     以及離障礙最近的距離；
  4. 預覽圖：地面 ＋ 障礙（紅框）＋ 不可站的格子（暗紅）＋ 路點（藍；吸附過的畫紅點→綠點）＋ 幾條範例路徑。
"""
import heapq
import math
import os
import random
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'ground'))

import check_walkable as CW   # noqa: E402
import gen_footprints as G    # noqa: E402

ROOT = G.ROOT
CORE = os.path.join(ROOT, 'Assets', 'Scripts', 'Core')


def nav_consts():
    src = CW.read(os.path.join(CORE, 'TownNav.cs'))

    def c(name):
        return float(re.search(r'const (?:float|int) %s\s*=\s*([\d.]+)f?;' % name, src).group(1))
    return dict(cell=c('CellSize'), radius=c('Radius'), step=c('SampleStep'),
                max_pull=int(c('MaxPull')), snap=int(c('SnapRings')),
                prefer_r=c('PreferRadius'), off_road=c('OffRoadCost'))


def candy_walk():
    src = CW.read(os.path.join(G.DATA, 'Candy.cs'))
    i = src.index('Vector2[] Walk')
    j = src.index('};', i)
    return [(float(a), float(b)) for a, b in re.findall(r'new\((-?[\d.]+)f?,\s*(-?[\d.]+)f?\)', src[i:j])]


def candy_jitter():
    src = CW.read(os.path.join(CORE, 'CandyTown.cs'))
    m = re.search(r'StopJitter\s*=\s*new\((-?[\d.]+)f,\s*(-?[\d.]+)f\)', src)
    return float(m.group(1)), float(m.group(2))


def town_jitter():
    src = CW.read(os.path.join(CORE, 'TownFolk.cs'))
    m = re.search(r'StopJitter\s*=\s*new\((-?[\d.]+)f,\s*(-?[\d.]+)f\)', src)
    return float(m.group(1)), float(m.group(2))


def pen(s, px, py, r):
    """gen_footprints.penetration 的純 math 版（同一個算法；numpy 純量太慢，兩兩求路要算上百萬次）。"""
    if s['shape'] == 'ellipse':
        rx, ry = s['hx'] + r, s['hy'] + r
        d = math.hypot((px - s['cx']) / rx, (py - s['cy']) / ry)
        return (1 - d) * min(rx, ry)
    qx = abs(px - s['cx']) - s['hx']
    qy = abs(py - s['cy']) - s['hy']
    return r - (math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0))


BUCKET = 128.0
REACH = 24.0     # 每個障礙登記到「外接框再長 REACH」涵蓋的桶 —— 要 ≥ NPC 半徑（查詢時只看所在那一桶）


class Nav:
    """TownNav.cs 的 Python 版（同一套規則）。"""

    def __init__(self, m, k, prefer=None):
        self.m, self.k = m, k
        self.shapes = m['shapes']
        assert REACH >= k['radius']
        self.buckets = {}
        for s in self.shapes:
            for bx in range(int(math.floor((s['cx'] - s['hx'] - REACH) / BUCKET)),
                            int(math.floor((s['cx'] + s['hx'] + REACH) / BUCKET)) + 1):
                for by in range(int(math.floor((s['cy'] - s['hy'] - REACH) / BUCKET)),
                                int(math.floor((s['cy'] + s['hy'] + REACH) / BUCKET)) + 1):
                    self.buckets.setdefault((bx, by), []).append(s)
        x0, y0, x1, y1 = m['bounds']
        self.bounds = m['bounds']
        cs = k['cell']
        self.nx = max(1, int(math.floor((x1 - x0) / cs)))
        self.ny = max(1, int(math.floor((y1 - y0) / cs)))
        self.ox, self.oy = x0 + cs / 2, y0 + cs / 2
        nx, ny = self.nx, self.ny
        self.free = np.zeros(nx * ny, bool)
        self.mult = np.ones(nx * ny)
        pr2 = k['prefer_r'] ** 2
        for j in range(ny):
            for i in range(nx):
                cx, cy = self.center(j * nx + i)
                self.free[j * nx + i] = self.standable(cx, cy)
                if prefer:
                    if not any((qx - cx) ** 2 + (qy - cy) ** 2 <= pr2 for qx, qy in prefer):
                        self.mult[j * nx + i] = k['off_road']
        # 連線（E, N, NE, NW）
        self.link = np.zeros(nx * ny, np.uint8)
        h = cs / 2
        F = self.free
        for j in range(ny):
            for i in range(nx):
                kk = j * nx + i
                if not F[kk]:
                    continue
                cx, cy = self.center(kk)
                b = 0
                if i + 1 < nx and F[kk + 1] and self.standable(cx + h, cy):
                    b |= 1
                if j + 1 < ny and F[kk + nx] and self.standable(cx, cy + h):
                    b |= 2
                if i + 1 < nx and j + 1 < ny and F[kk + nx + 1] and F[kk + 1] and F[kk + nx] \
                        and self.diag(cx, cy, cs, cs):
                    b |= 4
                if i - 1 >= 0 and j + 1 < ny and F[kk + nx - 1] and F[kk - 1] and F[kk + nx] \
                        and self.diag(cx, cy, -cs, cs):
                    b |= 8
                self.link[kk] = b
        # 連通區塊
        self.comp = np.full(nx * ny, -1, int)
        lab = 0
        for s in range(nx * ny):
            if not F[s] or self.comp[s] >= 0:
                continue
            self.comp[s] = lab
            st = [s]
            while st:
                cur = st.pop()
                for nb, _ in self.neighbors(cur):
                    if self.comp[nb] < 0:
                        self.comp[nb] = lab
                        st.append(nb)
            lab += 1
        self.ncomp = lab

    # ── 基本查詢 ──
    def in_walk(self, x, y):
        x0, y0, x1, y1 = self.bounds
        return x0 <= x < x1 and y0 <= y < y1      # Rect.Contains：xMin 含、xMax 不含

    def standable(self, x, y, r=None):
        r = self.k['radius'] if r is None else r
        if not self.in_walk(x, y):
            return False
        for s in self.near(x, y):
            if pen(s, x, y, r) > 0:
                return False
        return True

    def near(self, x, y):
        return self.buckets.get((int(math.floor(x / BUCKET)), int(math.floor(y / BUCKET))), ())

    def diag(self, cx, cy, dx, dy):
        return all(self.standable(cx + dx * t, cy + dy * t) for t in (0.25, 0.5, 0.75))

    def center(self, kk):
        cs = self.k['cell']
        return self.ox + (kk % self.nx) * cs, self.oy + (kk // self.nx) * cs

    def neighbors(self, kk):
        nx = self.nx
        i, j = kk % nx, kk // nx
        L = self.link
        cs = self.k['cell']
        d = cs * 1.41421356
        if L[kk] & 1:
            yield kk + 1, cs
        if i > 0 and L[kk - 1] & 1:
            yield kk - 1, cs
        if L[kk] & 2:
            yield kk + nx, cs
        if j > 0 and L[kk - nx] & 2:
            yield kk - nx, cs
        if L[kk] & 4:
            yield kk + nx + 1, d
        if i > 0 and j > 0 and L[kk - nx - 1] & 4:
            yield kk - nx - 1, d
        if L[kk] & 8:
            yield kk + nx - 1, d
        if i + 1 < self.nx and j > 0 and L[kk - nx + 1] & 8:
            yield kk - nx + 1, d

    def cell_of(self, x, y):
        cs = self.k['cell']
        i = min(max(int(round((x - self.ox) / cs)), 0), self.nx - 1)
        j = min(max(int(round((y - self.oy) / cs)), 0), self.ny - 1)
        return j * self.nx + i

    def nearest_free(self, x, y):
        k0 = self.cell_of(x, y)
        if self.free[k0]:
            return k0
        i0, j0 = k0 % self.nx, k0 // self.nx
        for r in range(1, self.k['snap'] + 1):
            best, bd = -1, float('inf')
            for j in range(j0 - r, j0 + r + 1):
                for i in range(i0 - r, i0 + r + 1):
                    if max(abs(i - i0), abs(j - j0)) != r or i < 0 or j < 0 or i >= self.nx or j >= self.ny:
                        continue
                    kk = j * self.nx + i
                    if not self.free[kk]:
                        continue
                    cx, cy = self.center(kk)
                    dd = (cx - x) ** 2 + (cy - y) ** 2
                    if dd < bd:
                        bd, best = dd, kk
            if best >= 0:
                return best
        return -1

    def seg_clear(self, a, b):
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        n = int(math.ceil(ln / self.k['step']))
        for s in range(1, n):
            t = s / n
            if not self.standable(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t):
                return False
        return True

    def stays_cheap(self, a, b):
        cap = max(self.mult[self.cell_of(*a)], self.mult[self.cell_of(*b)])
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        n = int(math.ceil(ln / self.k['step']))
        for s in range(1, n):
            t = s / n
            if self.mult[self.cell_of(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)] > cap:
                return False
        return True

    def snap(self, p):
        kk = self.cell_of(*p)
        if self.standable(*p) and self.comp[kk] >= 0 and self.seg_clear(self.center(kk), p):
            return p
        kk = self.nearest_free(*p)
        return self.center(kk) if kk >= 0 else p

    def good_stop(self, p):
        if not self.standable(*p):
            return False
        kk = self.cell_of(*p)
        return bool(self.free[kk]) and self.seg_clear(self.center(kk), p)

    def comp_at(self, p):
        kk = self.nearest_free(*p)
        return self.comp[kk] if kk >= 0 else -1

    # ── 尋路 ──
    def astar(self, s, g):
        if s == g:
            return [s]
        gx, gy = self.center(g)

        def H(kk):
            cx, cy = self.center(kk)
            dx, dy = abs(cx - gx), abs(cy - gy)
            return max(dx, dy) + 0.41421356 * min(dx, dy)
        gs = {s: 0.0}
        par = {s: -1}
        closed = set()
        q = [(H(s), s)]
        while q:
            _, cur = heapq.heappop(q)
            if cur in closed:
                continue
            closed.add(cur)
            if cur == g:
                out = []
                while cur >= 0:
                    out.append(cur)
                    cur = par[cur]
                return out[::-1]
            for nb, c in self.neighbors(cur):
                ng = gs[cur] + c * 0.5 * (self.mult[cur] + self.mult[nb])
                if nb in closed or ng >= gs.get(nb, float('inf')):
                    continue
                gs[nb] = ng
                par[nb] = cur
                heapq.heappush(q, (ng + H(nb), nb))
        return None

    def find(self, a, b):
        s, g = self.nearest_free(*a), self.nearest_free(*b)
        if s < 0 or g < 0 or self.comp[s] != self.comp[g]:
            return None
        cells = self.astar(s, g)
        if cells is None:
            return None
        pts = [a] + [self.center(c) for c in cells]
        end = b
        if not self.standable(*end) or not self.seg_clear(self.center(g), end):
            end = self.center(g)
        if (end[0] - pts[-1][0]) ** 2 + (end[1] - pts[-1][1]) ** 2 > 0.01:
            pts.append(end)
        out = []
        at = 0
        while at < len(pts) - 1:
            nxt = at + 1
            for j in range(at + 2, min(len(pts) - 1, at + self.k['max_pull']) + 1):
                if not self.seg_clear(pts[at], pts[j]) or not self.stays_cheap(pts[at], pts[j]):
                    break
                nxt = j
            out.append(pts[nxt])
            at = nxt
        return [a] + out


def path_hits(nav, path, step=2.0):
    """沿整條路徑每 step px 取樣：落在障礙裡（半徑 0）的次數、離障礙最近的距離。"""
    hits, minclr, n = 0, float('inf'), 0
    for a, b in zip(path, path[1:]):
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        k = max(1, int(math.ceil(ln / step)))
        for s in range(k + 1):
            t = s / k
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            n += 1
            # penetration(r=0) > 0 ＝ 點在形狀裡；-penetration ＝ 到形狀的距離（附近沒有障礙 → 至少 REACH）
            p = max([pen(sh, x, y, 0.0) for sh in nav.near(x, y)] + [-REACH])
            if p > 0:
                hits += 1
            minclr = min(minclr, -p)
    return hits, minclr, n


def candy_avoid(m):
    """糖果鎮只擋 NPC 的圓（CandyTown.RegisterNpcAvoid → TownNav.Avoid）：中央噴泉 ＋ 三位 NPC 的腳底。
    換成跟落地範圍一樣的 ellipse（hx＝hy＝半徑）—— 穿入算法對圓剛好等於「離中心 < 半徑＋NPC 半徑」。"""
    src = CW.read(os.path.join(CORE, 'CandyTown.cs'))
    f = re.search(r'Fountain\s*=\s*new\((-?[\d.]+)f,\s*(-?[\d.]+)f\)', src)
    fr = float(re.search(r'FountainR\s*=\s*([\d.]+)f', src).group(1))
    nr = float(re.search(r'NpcAvoidR\s*=\s*([\d.]+)f', src).group(1))
    out = [dict(name='fountain', cat='npc_avoid', shape='ellipse', cx=float(f.group(1)), cy=float(f.group(2)),
                hx=fr, hy=fr)]
    for o, _ in m['objs']:
        if o.kind == 'npc':
            out.append(dict(name='npc:' + o.art.split('/')[-1], cat='npc_avoid', shape='ellipse',
                            cx=o.x, cy=o.y, hx=nr, hy=nr))
    return out


def run_scene(scene, waypoints, jitter, k, outdir, rng, prefer):
    m = CW.build(scene)
    if scene == 'candy':
        m['shapes'] = m['shapes'] + candy_avoid(m)
    nav = Nav(m, k, waypoints if prefer else None)
    lines = ['[NPC 尋路] %s：格子 %d×%d（%.0fpx）、可站 %d 格、連通區塊 %d 塊；NPC 半徑 %.0f、取樣 %.0fpx' % (
        scene, nav.nx, nav.ny, k['cell'], int(nav.free.sum()), nav.ncomp, k['radius'], k['step'])]
    # 1. 吸附
    snapped = []
    for p in waypoints:
        q = nav.snap(p)
        snapped.append(q)
    moved = [(p, q) for p, q in zip(waypoints, snapped) if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > 0.01]
    lines.append('    路點 %d 個；吸附過的 %d 個%s' % (len(waypoints), len(moved), '' if moved else '（無）'))
    for p, q in moved:
        hit = [s['name'] for s in m['shapes'] if G.penetration(s, p[0], p[1], 0.0) > 0]
        lines.append('      - (%.0f, %.0f) → (%.0f, %.0f)%s' % (
            p[0], p[1], q[0], q[1], '（原本在 %s 裡）' % '、'.join(hit) if hit else '（貼太近，站不住）'))
    comps = [nav.comp_at(q) for q in snapped]
    main = max(set(comps), key=comps.count) if comps else -1
    off = [(p, c) for p, c in zip(waypoints, comps) if c != main]
    lines.append('    不在主要區塊的路點：%s' % ('無' if not off else '、'.join(
        '(%.0f, %.0f)[區塊 %d]' % (p[0], p[1], c) for p, c in off)))
    # 2. 兩兩求路
    disc, total_hits, total_samples, minclr, npaths = [], 0, 0, float('inf'), 0
    paths = {}
    for i in range(len(snapped)):
        for j in range(i + 1, len(snapped)):
            path = nav.find(snapped[i], snapped[j])
            if path is None:
                disc.append((i, j))
                continue
            paths[(i, j)] = path
            h, c, n = path_hits(nav, path)
            total_hits += h
            total_samples += n
            minclr = min(minclr, c)
            npaths += 1
    lines.append('    路點兩兩求路 %d 對：走得到 %d 對、不連通 %d 對' % (
        len(snapped) * (len(snapped) - 1) // 2, npaths, len(disc)))
    for i, j in disc[:20]:
        lines.append('      - (%.0f, %.0f) ↔ (%.0f, %.0f)' % (waypoints[i] + waypoints[j]))
    if len(disc) > 20:
        lines.append('      …（共 %d 對）' % len(disc))
    # 3. 隨機偏移後的停點（跟遊戲一樣：偏移 → GoodStop 驗 → 不行就重抽 → 都不行用吸附後的路點）
    rnd_hits, rnd_n, rnd_paths, rnd_fail = 0, 0, 0, 0
    for _ in range(300):
        a = snapped[rng.randrange(len(snapped))]
        b = snapped[rng.randrange(len(snapped))]

        def jit(p):
            for _t in range(6):
                q = (p[0] + (rng.random() - 0.5) * jitter[0], p[1] + (rng.random() - 0.5) * jitter[1])
                if nav.good_stop(q) and nav.comp_at(q) == nav.comp_at(p):
                    return q
            return p
        a, b = jit(a), jit(b)
        path = nav.find(a, b)
        if path is None:
            rnd_fail += 1
            continue
        h, c, n = path_hits(nav, path)
        rnd_hits += h
        rnd_n += n
        minclr = min(minclr, c)
        rnd_paths += 1
    lines.append('    隨機偏移停點 300 趟：走得到 %d 趟、走不到 %d 趟（遊戲裡會換目的地）' % (rnd_paths, rnd_fail))
    lines.append('    路徑取樣（每 2px）落在障礙裡的次數：路點對 %d / %d 點、隨機停點 %d / %d 點；離障礙最近 %.1fpx' % (
        total_hits, total_samples, rnd_hits, rnd_n, minclr))
    bad = total_hits + rnd_hits
    # 4. 預覽
    files = preview(m, nav, waypoints, snapped, paths, outdir, rng)
    return lines, bad, len(disc), files


def preview(m, nav, waypoints, snapped, paths, outdir, rng):
    W, H = m['W'], m['H']
    gp = os.path.join(G.RES, m['ground'].replace('/', os.sep) + '.png')
    img = Image.open(gp).convert('RGBA').resize((W, H), Image.NEAREST)

    def P(x, y):
        return x + W / 2, H / 2 - y

    items = []
    for o, fp in m['objs']:
        x0, y0, x1, y1 = G.image_rect(fp, o.x, o.y, o.scale, o.pivot)
        items.append((y0, o, (x0, y0, x1, y1)))
    for _, o, (x0, y0, x1, y1) in sorted(items, key=lambda t: -t[0]):
        sp = Image.open(os.path.join(G.RES, o.art.replace('/', os.sep) + '.png')).convert('RGBA')
        sw, sh = max(1, round(sp.width * o.scale)), max(1, round(sp.height * o.scale))
        sp = sp.resize((sw, sh), Image.NEAREST)
        a = np.asarray(sp).copy()
        a[..., 3] = (a[..., 3] * 0.45).astype(np.uint8)
        px, py = P(x0, y1)
        img.alpha_composite(Image.fromarray(a), (int(round(px)), int(round(py))))

    ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    h = nav.k['cell'] / 2
    for kk in range(nav.nx * nav.ny):
        if nav.free[kk]:
            continue
        cx, cy = nav.center(kk)
        a, b = P(cx - h, cy + h)
        c, e = P(cx + h, cy - h)
        d.rectangle([a, b, c, e], fill=(150, 20, 20, 70))
    if nav.mult.max() > 1:                       # 草地（偏好路面時比較貴的格子）：淡淡一層
        for kk in range(nav.nx * nav.ny):
            if nav.free[kk] and nav.mult[kk] > 1:
                cx, cy = nav.center(kk)
                a, b = P(cx - h, cy + h)
                c, e = P(cx + h, cy - h)
                d.rectangle([a, b, c, e], fill=(0, 0, 0, 40))
    for s in m['shapes']:
        col = (0, 170, 230, 255) if s['cat'] == 'water' else (230, 20, 20, 255)
        a, b = P(s['cx'] - s['hx'], s['cy'] + s['hy'])
        c, e = P(s['cx'] + s['hx'], s['cy'] - s['hy'])
        if s['shape'] == 'ellipse':
            d.ellipse([a, b, c, e], outline=col, width=2)
        else:
            d.rectangle([a, b, c, e], outline=col, width=2)
    # 範例路徑：挑幾條長的
    keys = sorted(paths, key=lambda kv: -len(paths[kv]))
    pick = keys[:4] + (rng.sample(keys[4:], min(8, max(0, len(keys) - 4))) if len(keys) > 4 else [])
    cols = [(255, 230, 0), (255, 120, 0), (255, 0, 200), (0, 255, 120), (120, 160, 255), (255, 255, 255),
            (0, 255, 255), (200, 255, 0), (255, 80, 80), (160, 80, 255), (80, 255, 200), (255, 180, 120)]
    for n, key in enumerate(pick):
        pts = [P(*p) for p in paths[key]]
        d.line(pts, fill=cols[n % len(cols)] + (255,), width=4)
        for q in pts[1:-1]:
            d.ellipse([q[0] - 3, q[1] - 3, q[0] + 3, q[1] + 3], fill=cols[n % len(cols)] + (255,))
    for p, q in zip(waypoints, snapped):
        a, b = P(*p)
        moved = (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > 0.01
        if moved:
            c, e = P(*q)
            d.line([a, b, c, e], fill=(255, 255, 255, 255), width=2)
            d.ellipse([a - 6, b - 6, a + 6, b + 6], fill=(255, 0, 0, 255))
            d.ellipse([c - 6, e - 6, c + 6, e + 6], fill=(40, 230, 90, 255), outline=(0, 0, 0, 255))
        else:
            d.ellipse([a - 5, b - 5, a + 5, b + 5], fill=(60, 140, 255, 255), outline=(0, 0, 0, 255))
    img.alpha_composite(ov)
    os.makedirs(outdir, exist_ok=True)
    full = os.path.join(outdir, '%s-npc-paths.png' % m['scene'])
    img.resize((W // 2, H // 2), Image.LANCZOS).convert('RGB').save(full)
    return [full]


def garden(outdir):
    """後花園：沒開 Obstacles，村民以 polyline 模式只沿 GardenData.FenceWalk 相鄰兩點走（TownFolk 加 ±LaneMax 的橫向偏移）。
    這裡只畫預覽：底圖 ＋ 折線 ＋ 兩條偏移極限，眼睛看它是不是整條都在柵欄外的石板路上。"""
    src = CW.read(os.path.join(G.DATA, 'Garden.cs'))
    i = src.index('Vector2[] FenceWalk')
    j = src.index('};', i)
    pts = [(float(a), float(b)) for a, b in re.findall(r'new\((-?[\d.]+)f,\s*(-?[\d.]+)f\)', src[i:j])]
    lane = float(re.search(r'LaneMax\s*=\s*([\d.]+)f', CW.read(os.path.join(CORE, 'TownFolk.cs'))).group(1))
    img = Image.open(os.path.join(G.RES, 'rooms', 'garden.png')).convert('RGBA')
    W, H = img.size
    d = ImageDraw.Draw(img)

    def P(x, y):
        return x + W / 2, H / 2 - y
    for off, col in ((-lane, (255, 150, 0)), (lane, (255, 150, 0)), (0, (255, 0, 0))):
        d.line([P(x, y + off) for x, y in pts], fill=col + (255,), width=2 if off else 3)
    for n, (x, y) in enumerate(pts):
        a, b = P(x, y)
        d.ellipse([a - 5, b - 5, a + 5, b + 5], fill=(60, 140, 255, 255))
        d.text((a + 7, b - 6), str(n), fill=(255, 255, 0, 255))
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, 'garden-npc-paths.png')
    img.convert('RGB').save(p)
    return ['[NPC 尋路] garden：FenceWalk 折線 %d 點、橫向偏移 ±%.0f（polyline 模式，不用 TownNav）' % (len(pts), lane)], [p]


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'Temp', 'npc_paths')
    k = nav_consts()
    rng = random.Random(1)
    lines, files, bad, disc = [], [], 0, 0
    # 城鎮偏好走路面（TownFolk 呼叫 TownNav.Prefer(TownRoads.Walk)）；糖果鎮不分（CandyTown 呼叫 Prefer(null)）
    for scene, wps, jit, pref in (('town', CW.roads(), town_jitter(), True),
                                  ('candy', candy_walk(), candy_jitter(), False)):
        l, b, dc, f = run_scene(scene, wps, jit, k, outdir, rng, pref)
        lines += l
        files += f
        bad += b
        disc += dc
    gl, gf = garden(outdir)
    lines += gl
    files += gf
    print('\n'.join(lines))
    print('預覽圖：')
    for f in files:
        print('  ' + f)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
