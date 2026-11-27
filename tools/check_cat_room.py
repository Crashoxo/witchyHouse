#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
藥水室的貓（Core/RoomCat.cs）離線檢查：不開 Unity，直接讀 C# 原始碼裡的數字。

    python tools/check_cat_room.py            # 檢查；有問題結束碼 1
    python tools/check_cat_room.py --png DIR  # 另外輸出俯視圖（可走格／走得到的格／貓窩／門口迎接點）

讀：
  * Assets/Scripts/Data/BrewRoomLayout.cs —— 可走範圍 Walk、出生點 Spawn、每件家具的碰撞形狀（Poly／Ellipse）
  * Assets/Scripts/Core/RoomCat.cs        —— DrawnBedAt、OwnBedAt、DoorGreet、Radius、PetRange、GridStep
驗：
  1. 貓窩站得住（兩個都驗：細畫房間畫好的 DrawnBedAt、自己擺坐墊的 OwnBedAt）（在地板多邊形內、半徑 Radius 的圓不碰到任何家具）—— 跟 Obstacles.InWalk／IsFree(p, r) 同一個算法
  2. 門口迎接點 DoorGreet 站得住，而且離女巫的出生點在 PetRange 內（一進門就摸得到）
  3. 從貓窩出發（8px 格、八向不切角，跟 RoomCat 的 BFS 一樣），走得到的格子佔地板的比例 ≥ MIN_REACH，迎接點也在裡面
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('WITCH_UNITY_ROOT') or os.path.dirname(HERE)
LAYOUT = os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'BrewRoomLayout.cs')
CAT = os.path.join(ROOT, 'Assets', 'Scripts', 'Core', 'RoomCat.cs')
MIN_REACH = 0.70

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

NUM = r'(-?\d+(?:\.\d+)?)f?'


def vec(src, name):
    m = re.search(name + r'\s*=\s*new(?:\s+Vector2)?\(\s*' + NUM + r'\s*,\s*' + NUM + r'\s*\)', src)
    if not m:
        raise SystemExit(f'找不到 {name}')
    return float(m.group(1)), float(m.group(2))


def const(src, name):
    m = re.search(r'const\s+float\s+' + name + r'\s*=\s*' + NUM, src)
    if not m:
        raise SystemExit(f'找不到 const {name}')
    return float(m.group(1))


def parse_layout(src):
    m = re.search(r'Walk\s*=\s*\{(.*?)\};', src, re.S)
    walk = [(float(a), float(b)) for a, b in re.findall(r'new\(\s*' + NUM + r'\s*,\s*' + NUM + r'\s*\)', m.group(1))]
    shapes = []
    for pm in re.finditer(r'new BrewPiece\("([^"]+)".*?BrewShape\.(\w+),\s*' + NUM + r',\s*' + NUM + r',\s*' + NUM + r',\s*' + NUM
                          + r',\s*(null|new Vector2\[\]\s*\{(.*?)\})\)', src, re.S):
        name, kind = pm.group(1), pm.group(2)
        cx, cy, hx_, hy = (float(pm.group(i)) for i in range(3, 7))
        if kind == 'Ellipse':
            shapes.append((name, 'e', (cx, cy, hx_, hy)))
        elif kind == 'Poly':
            pts = [(float(a), float(b)) for a, b in re.findall(r'new\(\s*' + NUM + r'\s*,\s*' + NUM + r'\s*\)', pm.group(8))]
            shapes.append((name, 'p', ccw(pts)))
    return walk, shapes


def ccw(pts):
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    return list(reversed(pts)) if area < 0 else list(pts)


def poly_dist(poly, x, y):
    """有號距離：外面正、裡面負（同 Obstacles.PolyDist）。"""
    inside = True
    best = 1e18
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        if l2 < 1e-8:
            continue
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / l2))
        qx, qy = ax + dx * t, ay + dy * t
        best = min(best, (x - qx) ** 2 + (y - qy) ** 2)
        if dx * (y - ay) - dy * (x - ax) < 0:
            inside = False
    best = math.sqrt(best)
    return -best if inside else best


def pen(shape, x, y, r):
    _, kind, s = shape
    if kind == 'p':
        return r - poly_dist(s, x, y)
    cx, cy, hx_, hy = s
    rx, ry = hx_ + r, hy + r
    d = math.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    return (1 - d) * min(rx, ry)


def main():
    args = sys.argv[1:]
    png = None
    if '--png' in args:
        png = args[args.index('--png') + 1]
    lsrc = open(LAYOUT, encoding='utf-8').read()
    csrc = open(CAT, encoding='utf-8').read()
    walk, shapes = parse_layout(lsrc)
    walk_ccw = ccw(walk)
    spawn = vec(lsrc, 'Spawn')
    beds = [('細畫房間的貓窩 DrawnBedAt', vec(csrc, 'DrawnBedAt')), ('自己擺坐墊的貓窩 OwnBedAt', vec(csrc, 'OwnBedAt'))]
    bed = beds[0][1]
    greet = vec(csrc, 'DoorGreet')
    R = const(csrc, 'Radius')
    pet = const(csrc, 'PetRange')
    step = const(csrc, 'GridStep')

    def in_walk(x, y):
        return poly_dist(walk_ccw, x, y) <= 0

    def blocker(x, y):
        for s in shapes:
            if pen(s, x, y, R) > 0:
                return s[0]
        return None

    def free(x, y):
        return in_walk(x, y) and blocker(x, y) is None

    bad = []
    print(f'碰撞形狀 {len(shapes)} 個；可走範圍 {len(walk)} 邊；貓半徑 {R:g}、摸得到 {pet:g}px、格子 {step:g}px')
    for name, (x, y) in beds + [('門口迎接 DoorGreet', greet)]:
        ok = free(x, y)
        clear = min([-poly_dist(walk_ccw, x, y)] + [-(pen(s, x, y, 0)) for s in shapes])
        print(f'  {name} ({x:g}, {y:g})：{"站得住" if ok else "✗ 站不住"}（離最近的家具／牆 {clear:.1f}px）'
              + ('' if ok else f'  ← {blocker(x, y) or "地板外"}'))
        if not ok:
            bad.append(name + ' 站不住')
    dg = math.dist(greet, spawn)
    print(f'  迎接點離出生點 {dg:.1f}px（要 ≤ {pet:g}）')
    if dg > pet:
        bad.append('迎接點離出生點太遠，一進門摸不到')

    xs = [p[0] for p in walk]
    ys = [p[1] for p in walk]
    x0, y0 = min(xs), min(ys)
    gw = int((max(xs) - x0) // step) + 1
    gh = int((max(ys) - y0) // step) + 1
    cell = lambda i, j: (x0 + i * step, y0 + j * step)
    fr = [[free(*cell(i, j)) for i in range(gw)] for j in range(gh)]
    floor = sum(1 for j in range(gh) for i in range(gw) if in_walk(*cell(i, j)))

    def nearest(p):
        ci, cj = round((p[0] - x0) / step), round((p[1] - y0) / step)
        best = None
        for rr in range(7):
            for j in range(cj - rr, cj + rr + 1):
                for i in range(ci - rr, ci + rr + 1):
                    if 0 <= i < gw and 0 <= j < gh and fr[j][i]:
                        d = math.dist(cell(i, j), p)
                        if best is None or d < best[0]:
                            best = (d, i, j)
            if best:
                return best[1], best[2]
        return None

    freec = sum(1 for j in range(gh) for i in range(gw) if fr[j][i])
    reach = set()
    for bname, bpos in beds:
        s = nearest(bpos)
        r = set()
        if s:
            stack = [s]
            r.add(s)
            while stack:
                i, j = stack.pop()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    a, b = i + dx, j + dy
                    if not (0 <= a < gw and 0 <= b < gh) or not fr[b][a] or (a, b) in r:
                        continue
                    if dx and dy and (not fr[j][i + dx] or not fr[j + dy][i]):
                        continue
                    r.add((a, b))
                    stack.append((a, b))
        if bpos == bed:
            reach = r
        frac = len(r) / max(1, floor)
        print(f'  從{bname}走得到 {len(r)} 格 ＝ 地板 {floor} 格的 {frac * 100:.1f}%（可站的 {freec} 格裡 {len(r) / max(1, freec) * 100:.1f}%；要 ≥ {MIN_REACH * 100:.0f}%）')
        if frac < MIN_REACH:
            bad.append(f'從{bname}走得到的地板太少')
        if nearest(greet) not in r:
            bad.append(f'從{bname}走不到門口迎接點')
        else:
            print(f'  門口迎接點從{bname}走得到')

    if png:
        from PIL import Image, ImageDraw
        k = 2
        im = Image.new('RGB', (gw * k * 4, gh * k * 4), (30, 26, 36))
        d = ImageDraw.Draw(im)
        for j in range(gh):
            for i in range(gw):
                c = (60, 52, 70)
                if fr[j][i]:
                    c = (70, 120, 90) if (i, j) in reach else (150, 90, 60)
                elif in_walk(*cell(i, j)):
                    c = (110, 50, 60)
                X, Y = i * k * 4, (gh - 1 - j) * k * 4
                d.rectangle([X, Y, X + k * 4 - 2, Y + k * 4 - 2], fill=c)
        for (px, py), col in ((bed, (255, 210, 80)), (greet, (120, 200, 255)), (spawn, (255, 255, 255))):
            X = (px - x0) / step * k * 4
            Y = (gh - 1 - (py - y0) / step) * k * 4
            d.ellipse([X - 6, Y - 6, X + 6, Y + 6], outline=col, width=3)
        os.makedirs(png, exist_ok=True)
        im.save(os.path.join(png, 'cat_reach.png'))
        print(f'  俯視圖 → {os.path.join(png, "cat_reach.png")}（綠＝走得到、橘＝可站但走不到、紅＝地板上被家具佔、黃圈細畫房間的貓窩、藍圈迎接點、白圈出生點）')

    print('結果：' + ('全部通過' if not bad else '✗ ' + '；'.join(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
