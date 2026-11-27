# -*- coding: utf-8 -*-
"""
8-bit 後花園（garden，GardenRoom.UsePixelGarden）的碰撞與擺位離線檢查（不用開 Unity）。

    python tools/check_garden_walk.py                 # 讀 Assets/Scripts/Data/GardenRoomData.cs
    python tools/check_garden_walk.py --cs PATH       # 讀別的（gen_garden_art.py --out 的輸出）
    python tools/check_garden_walk.py --preview PNG   # 另外輸出可走格／走不到的點的圖

照 GardenRoomData 的格盤、可走多邊形（Walk）、裝飾障礙（Decor 的橢圓），做跟 Obstacles 一樣的判定
（腳底圓半徑 ArtFootprints.PlayerRadius；橢圓往外長 R 之後的正規化距離，Obstacles.Pen 同一個算法），
從出生點 Spawn 4 向 flood fill（取樣 2px），檢查：
  1. 可走多邊形整個在草地（Floor）裡面，而且每條邊離草地邊緣 ≥ 腳底半徑（腳底圓不壓到牆）；
  2. 出生點站得住、門的觸發點（DoorAt）在自動觸發距離 DoorRange 內走得到；
  3. 每一格（裝飾那格除外）的中心 10px 內有走得到的點 —— 花圃擺到哪都碰得到（E 的範圍是 90px，這條更嚴）；
  4. 沒有「站得住但走不到」的口袋（可走取樣點全部連通）；
  5. 預設花圃 12 格：在格盤內、互不重疊、不在門口兩格與裝飾格上；
  6. 出生點離門 > DoorRange（一進來不會被彈回店裡）；
  7. 底圖（ImgW×ImgH，中心＝原點）比 960×640 的設計畫面大、草地整個在圖裡（鏡頭夾邊見 CameraFollow.ClampTo）；
  8. 路人路網（FolkNodes／FolkEdges／FolkExits，GardenFolk 用）：連通、每段都在圍牆與小屋的地面範圍外
     （草地菱形外擴 0.6 格、BackRects 外擴 0.25 格，含路人腳底的寬度）、在圖內（通往畫面外岔路盡頭的那段除外），
     並統計有多少比例是「在後牆／小屋後面」（GardenFolk 會排到後景層下面）。
⚠️ 常數一律從 C# 讀（GardenRoomData.cs / ArtFootprints.cs / Garden.cs），這支不自己寫常數。
"""
import os
import re
import sys
from collections import deque

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def src(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def num(text, pat):
    m = re.search(pat, text)
    if not m:
        raise SystemExit('讀不到：' + pat)
    return float(m.group(1))


FNUM = r'(-?[\d.]+)f'


def vec_list(text, name):
    m = re.search(name + r'\s*=\s*\{(.*?)\};', text, re.S)
    if not m:
        raise SystemExit('讀不到陣列：' + name)
    return [(float(a), float(b)) for a, b in re.findall(r'new\(' + FNUM + r',\s*' + FNUM + r'\)', m.group(1))]


def vec(text, name):
    m = re.search(name + r'\s*=\s*new\(' + FNUM + r',\s*' + FNUM + r'\)', text)
    if not m:
        raise SystemExit('讀不到座標：' + name)
    return float(m.group(1)), float(m.group(2))


def main():
    args = sys.argv[1:]
    cs = args[args.index('--cs') + 1] if '--cs' in args else os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'GardenRoomData.cs')
    T = src(cs)
    R = num(src(os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'ArtFootprints.cs')), r'PlayerRadius\s*=\s*([\d.]+)f')
    G = src(os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'Garden.cs'))
    plot_cols = int(num(G, r'PlotCols\s*=\s*(\d+)'))
    plot_rows = int(num(G, r'PlotRows\s*=\s*(\d+)'))

    HW = num(T, r'HalfW\s*=\s*' + FNUM)
    HH = num(T, r'HalfH\s*=\s*' + FNUM)
    COLS = int(num(T, r'Cols\s*=\s*(\d+)'))
    ROWS = int(num(T, r'Rows\s*=\s*(\d+)'))
    OX = num(T, r'OriginX\s*=\s*' + FNUM)
    OY = num(T, r'OriginY\s*=\s*' + FNUM)
    walk = vec_list(T, r'Vector2\[\] Walk')
    floor = vec_list(T, r'Vector2\[\] Floor')
    door = vec(T, 'DoorAt')
    spawn = vec(T, 'Spawn')
    door_range = num(T, r'DoorRange\s*=\s*' + FNUM)
    door_cell = (int(num(T, r'DoorGx\s*=\s*(\d+)')), int(num(T, r'DoorGy\s*=\s*(\d+)')))
    door_front = (int(num(T, r'DoorFrontGx\s*=\s*(\d+)')), int(num(T, r'DoorFrontGy\s*=\s*(\d+)')))
    block = (int(num(T, r'PlotBlockGx\s*=\s*(\d+)')), int(num(T, r'PlotBlockGy\s*=\s*(\d+)')))
    decor = []
    for m in re.finditer(r'new GardenDecor\("(\w+)",\s*"[^"]*",\s*(\d+),\s*(\d+),\s*' + FNUM + r',\s*' + FNUM +
                         r',\s*(-?\d+),\s*' + FNUM + r',\s*' + FNUM + r',\s*' + FNUM + r',\s*' + FNUM + r'\)', T):
        decor.append(dict(name=m.group(1), cell=(int(m.group(2)), int(m.group(3))),
                          c=(float(m.group(7)), float(m.group(8))), h=(float(m.group(9)), float(m.group(10)))))

    def cc(gx, gy):
        return OX + (gx - gy) * HW, OY - (gx + gy) * HH

    ok_all = True

    def report(ok, msg):
        nonlocal ok_all
        ok_all &= ok
        print(('  OK  ' if ok else '  ✗✗  ') + msg)

    print(f'格盤 {COLS}×{ROWS}、原點 ({OX:g},{OY:g})、腳底半徑 {R:g}、裝飾 {len(decor)} 件')

    # ── 1. 可走多邊形在草地裡、離邊 ≥ R ──
    def poly_dist(poly, p):
        """點到凸多邊形的有號距離（外正內負；頂點順時針或逆時針都行）。"""
        n = len(poly)
        area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
        inside = True
        best = 1e18
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy
            t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / l2))
            qx, qy = ax + dx * t, ay + dy * t
            best = min(best, (p[0] - qx) ** 2 + (p[1] - qy) ** 2)
            cross = dx * (p[1] - ay) - dy * (p[0] - ax)
            if (cross < 0) if area > 0 else (cross > 0):
                inside = False
        d = best ** 0.5
        return -d if inside else d

    clear = min(-poly_dist(floor, p) for p in walk)
    # 多邊形邊上的點離草地邊最近的距離（凸多邊形 → 只要看頂點）
    report(clear >= R - 0.01, f'可走範圍在草地裡，離草地邊最近 {clear:.1f}px（要 ≥ 腳底半徑 {R:g}）')

    # ── 取樣格 ──
    STEP = 2.0
    xs = [p[0] for p in walk]
    ys = [p[1] for p in walk]
    x0, x1, y0, y1 = min(xs) - 4, max(xs) + 4, min(ys) - 4, max(ys) + 4
    nx = int((x1 - x0) / STEP) + 1
    ny = int((y1 - y0) / STEP) + 1
    X = x0 + np.arange(nx) * STEP
    Y = y0 + np.arange(ny) * STEP
    XX, YY = np.meshgrid(X, Y)

    inside = np.ones(XX.shape, dtype=bool)
    n = len(walk)
    area = sum(walk[i][0] * walk[(i + 1) % n][1] - walk[(i + 1) % n][0] * walk[i][1] for i in range(n))
    for i in range(n):
        ax, ay = walk[i]
        bx, by = walk[(i + 1) % n]
        cross = (bx - ax) * (YY - ay) - (by - ay) * (XX - ax)
        inside &= (cross >= 0) if area > 0 else (cross <= 0)

    free = inside.copy()
    for d in decor:
        rx, ry = d['h'][0] + R, d['h'][1] + R
        e = ((XX - d['c'][0]) / rx) ** 2 + ((YY - d['c'][1]) / ry) ** 2
        free &= e >= 1.0

    def idx(p):
        return int(round((p[1] - y0) / STEP)), int(round((p[0] - x0) / STEP))

    # ── 2. 出生點 ──
    sj, si = idx(spawn)
    report(0 <= sj < ny and 0 <= si < nx and free[sj, si], f'出生點 ({spawn[0]:g},{spawn[1]:g}) 站得住')
    reach = np.zeros(free.shape, dtype=bool)
    if free[sj, si]:
        q = deque([(sj, si)])
        reach[sj, si] = True
        while q:
            j, i = q.popleft()
            for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a, b = j + dj, i + di
                if 0 <= a < ny and 0 <= b < nx and free[a, b] and not reach[a, b]:
                    reach[a, b] = True
                    q.append((a, b))

    def reach_within(p, r):
        d2 = (XX - p[0]) ** 2 + (YY - p[1]) ** 2
        m = reach & (d2 <= r * r)
        return bool(m.any()), (float(np.sqrt(d2[reach].min())) if reach.any() else 1e9)

    ok, dmin = reach_within(door, door_range)
    report(ok, f'門的觸發點 ({door[0]:g},{door[1]:g}) 走得到（最近 {dmin:.1f}px，自動觸發 {door_range:g}px）')
    ds = ((spawn[0] - door[0]) ** 2 + (spawn[1] - door[1]) ** 2) ** 0.5
    report(ds > door_range, f'出生點離門 {ds:.1f}px > 自動觸發 {door_range:g}px（一進來不會被彈回去）')

    # ── 3. 每一格中心附近走得到 ──
    decor_cells = {d['cell'] for d in decor}
    bad = []
    worst = 0.0
    for gx in range(COLS):
        for gy in range(ROWS):
            if (gx, gy) in decor_cells:
                continue
            ok, dmin = reach_within(cc(gx, gy), 10.0)
            worst = max(worst, dmin)
            if not ok:
                bad.append((gx, gy, round(dmin, 1)))
    report(not bad, f'{COLS * ROWS - len(decor_cells)} 格的中心 10px 內都走得到（最遠的一格差 {worst:.1f}px）' +
           ('' if not bad else f'；走不到：{bad}'))

    # ── 4. 口袋 ──
    pocket = int((free & ~reach).sum())
    report(pocket == 0, f'沒有站得住卻走不到的口袋（{pocket} 個取樣點；可走 {int(reach.sum())} 個）')

    # ── 5. 預設花圃 ──
    reserved = {door_cell, door_front} | decor_cells
    cells = [(block[0] + i % plot_cols, block[1] + i // plot_cols) for i in range(plot_cols * plot_rows)]
    in_grid = all(0 <= gx < COLS and 0 <= gy < ROWS for gx, gy in cells)
    report(in_grid and len(set(cells)) == len(cells) and not (set(cells) & reserved),
           f'預設花圃 {len(cells)} 格 {cells[0]}..{cells[-1]}：在格盤內、不重疊、不在門口／裝飾格')
    for d in decor:
        report(d['cell'] not in (door_cell, door_front), f'裝飾 {d["name"]} 在格 {d["cell"]}，不擋門口')

    if '--preview' in args:
        from PIL import Image
        out = args[args.index('--preview') + 1]
        img = np.zeros(free.shape + (3,), dtype=np.uint8)
        img[inside] = (60, 60, 60)
        img[free] = (90, 140, 90)
        img[reach] = (120, 220, 120)
        img[free & ~reach] = (240, 60, 60)
        Image.fromarray(img[::-1]).resize((nx * 2, ny * 2), Image.NEAREST).save(out)
        print('預覽 →', out)

    # ── 7. 底圖大小 ──
    img_w = num(T, r'ImgW\s*=\s*' + FNUM)
    img_h = num(T, r'ImgH\s*=\s*' + FNUM)
    inside_img = all(abs(x) <= img_w / 2 - 40 and abs(y) <= img_h / 2 - 40 for x, y in floor)
    report(img_w > 960 and img_h > 640 and inside_img,
           f'底圖 {img_w:g}×{img_h:g} 比設計畫面 960×640 大，草地四角離圖邊 ≥ 40px')

    # ── 8. 路人路網 ──
    if 'FolkNodes' in T:
        fnodes = vec_list(T, r'Vector2\[\] FolkNodes')
        m = re.search(r'int\[\] FolkEdges\s*=\s*\{(.*?)\};', T, re.S)
        ev = [int(x) for x in re.findall(r'-?\d+', m.group(1))]
        fedges = list(zip(ev[0::2], ev[1::2]))
        fexits = {int(x) for x in re.findall(r'-?\d+', re.search(r'FolkExits\s*=\s*\{(.*?)\}', T).group(1))}
        m = re.search(r'float\[\] BackRects\s*=\s*\{(.*?)\};', T, re.S)
        bv = [float(x) for x in re.findall(r'(-?[\d.]+)f', m.group(1))]
        rects = [tuple(bv[i:i + 4]) for i in range(0, len(bv) - 3, 4)]

        def tog(x, y):
            a = (x - OX) / HW
            b = (OY - y) / HH
            return (a + b) / 2, (b - a) / 2

        # 連通
        adj = {i: set() for i in range(len(fnodes))}
        for a, b in fedges:
            adj[a].add(b)
            adj[b].add(a)
        seen = {0}
        stack = [0]
        while stack:
            k = stack.pop()
            for j in adj[k]:
                if j not in seen:
                    seen.add(j)
                    stack.append(j)
        report(len(seen) == len(fnodes), f'路人路網連通：{len(fnodes)} 個節點、{len(fedges)} 段、{len(fexits)} 個畫面外出口')
        bad_in, bad_out, behind, total = [], [], 0, 0
        for a, b in fedges:
            pa, pb = fnodes[a], fnodes[b]
            L = ((pb[0] - pa[0]) ** 2 + (pb[1] - pa[1]) ** 2) ** 0.5
            n = max(2, int(L / 4))
            to_exit = a in fexits or b in fexits
            for k in range(n + 1):
                t = k / n
                x, y = pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t
                u, v = tog(x, y)
                total += 1
                if -0.5 - 0.6 < u < COLS - 0.5 + 0.6 and -0.5 - 0.6 < v < ROWS - 0.5 + 0.6:
                    bad_in.append((a, b, round(u, 2), round(v, 2)))
                for (u0, u1, v0, v1) in rects:
                    if u0 - 0.25 < u < u1 + 0.25 and v0 - 0.25 < v < v1 + 0.25:
                        bad_in.append((a, b, round(u, 2), round(v, 2)))
                if not to_exit and not (abs(x) <= img_w / 2 - 20 and abs(y) <= img_h / 2 - 20):
                    bad_out.append((a, b, round(x), round(y)))
                for (u0, u1, v0, v1) in rects:
                    lo = max(0.0, u0 - u, v0 - v)
                    hi = min(u1 - u, v1 - v)
                    if lo <= hi:
                        behind += 1
                        break
        report(not bad_in, '路網每段都在圍牆、小屋外（路人進不去花園、不會穿牆）' + ('' if not bad_in else f'；碰到：{bad_in[:6]}'))
        report(not bad_out, '路網（出口岔路以外）都在圖內' + ('' if not bad_out else f'；出圖：{bad_out[:6]}'))
        ex_out = all(not (abs(fnodes[e][0]) <= img_w / 2 and abs(fnodes[e][1]) <= img_h / 2) for e in fexits)
        report(ex_out, '每個出口節點都在畫面外（路人真的走出去）')
        print(f'  ..  路網取樣 {total} 點，其中 {100 * behind / max(1, total):.0f}% 在後牆／小屋後面（排在後景層下面）')

    print('全部通過' if ok_all else '有問題（見上面 ✗✗）')
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
