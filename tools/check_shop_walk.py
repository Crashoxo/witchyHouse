# -*- coding: utf-8 -*-
"""
店裡（shop，等距房間）的碰撞離線檢查（不用開 Unity）。

    python tools/check_shop_walk.py

照 Data/ShopRoom.cs 的格盤數學與家具碰撞內縮（FurnitureInset）、地板邊界（FloorMargin），
對幾種擺設做跟 Obstacles.SelfCheck 同樣的 flood fill：
  1. 可走範圍 ＝ 地板菱形內縮 FloorMargin 格（＝ShopRoom.WalkFloor()，也＝舊的 ClampToFloor）；
  2. 每件家具 ＝ 佔地 w×h 格、每邊內縮 FurnitureInset 格的平行四邊形，再往外長玩家半徑 PlayerRadius
     （腳底圓心進不去的範圍；跟 Obstacles.Pen 一樣：到凸多邊形的有號距離 < R 就擋）；
  3. 從出生點 PlayerSpawn 4 向 flood fill，檢查：
       - 三扇門（DoorTown／DoorBrew／DoorGarden，格子中心）在自動觸發距離 autoRange 內走得到；
       - 販售桌前（RoomLayout.SaleFront）在 SaleCounter.InteractRange 內走得到；
       - 每個貨架前方走道的每一格（RoomLayout.FrontClearance）都站得到（格子中心 10px 內有走得到的點）；
     取樣格 2px（精確）與 8px（＝編輯器 SelfCheck 在房間用的 FloodRoom）各跑一次，兩者結論要一樣；
     再用 2px＋「寬裕」（障礙多長 SLACK px，走道淨空至少 2×SLACK）跑一次 —— 幾何上剛好擠得過不算數。
另外印出：一格走道的淨寬（解析算式）、斜對角相鄰的角縫寬、WalkFloor 跟 ClampToFloor 是否同一塊區域、
腳底最多能踩進家具佔地格多深（ShopRoomView.PlayerOrder 尖角放寬的依據）。

擺設都先照 RoomLayout.Check 的格子規則（地板內、不重疊、門口保留格、貨架走道）驗過是合法的
（「圖會不會穿牆」要量圖，這裡不檢查）。

⚠️ 常數一律從 C# 原始檔讀（ShopRoom.cs / ArtFootprints.cs / SaleCounter.cs / SceneDoor.cs / RoomLayout.cs /
   Furniture.cs），這支不自己寫任何碰撞或格盤常數 —— 改了 C# 重跑就好。
"""
import os
import re
import sys
from collections import deque

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def src(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def num(text, pattern):
    m = re.search(pattern, text)
    if not m:
        raise SystemExit(f'讀不到常數：{pattern}')
    return float(m.group(1))


def cell(text, name):
    m = re.search(name + r'\s*=\s*new\((\d+),\s*(\d+)\)', text)
    if not m:
        raise SystemExit(f'讀不到格子：{name}')
    return int(m.group(1)), int(m.group(2))


SHOP = src('Assets/Scripts/Data/ShopRoom.cs')
TILE_W = num(SHOP, r'TileW\s*=\s*([\d.]+)f')
TILE_H = num(SHOP, r'TileH\s*=\s*([\d.]+)f')
GRID_W = int(num(SHOP, r'GridW\s*=\s*(\d+)'))
GRID_H = int(num(SHOP, r'GridH\s*=\s*(\d+)'))
ORIGIN_X = num(SHOP, r'OriginX\s*=\s*(-?[\d.]+)f')
ORIGIN_Y = num(SHOP, r'OriginY\s*=\s*(-?[\d.]+)f')
FLOOR_MARGIN = num(SHOP, r'FloorMargin\s*=\s*([\d.]+)f')
INSET = num(SHOP, r'FurnitureInset\s*=\s*([\d.]+)f')
SPAWN = cell(SHOP, 'PlayerSpawn')
DOORS = {'DoorTown': cell(SHOP, 'DoorTown'), 'DoorBrew': cell(SHOP, 'DoorBrew'),
         'DoorGarden': cell(SHOP, 'DoorGarden')}
SALE_CELL = cell(SHOP, 'DefaultSaleCell')

R = num(src('Assets/Scripts/Data/ArtFootprints.cs'), r'PlayerRadius\s*=\s*([\d.]+)f')
SALE_RANGE = num(src('Assets/Scripts/Core/SaleCounter.cs'), r'InteractRange\s*=\s*([\d.]+)f')
DOOR_AUTO = num(src('Assets/Scripts/Core/SceneDoor.cs'), r'autoRange\s*=\s*([\d.]+)f')
SALE_GAP = num(src('Assets/Scripts/Core/RoomLayout.cs'), r'SaleStandGap\s*=\s*([\d.]+)f')
# 開店／關店招牌（ShopSignPost）搬到城鎮的店門口了（tools/check_walkable.py 檢查它）——
# 店裡不再有招牌，以前它站的 (7,9) 也不再是保留格（見下面「前排地板邊」那組擺設）。

# 家具定義：販售桌 2×1；貨架 1×depth（Furniture.cs 的 ShelfStyles 最後一欄）
FURN = src('Assets/Scripts/Data/Furniture.cs')
DEFS = {'sale_table': (2, 1, False)}
for sid, depth in re.findall(r'\("(shelf_\w+)",\s*"[^"]*",\s*\d+,\s*"[^"]*",\s*(\d+)\)', FURN):
    DEFS[sid] = (1, int(depth), True)
if 'shelf_box' not in DEFS or 'shelf_tall' not in DEFS:
    raise SystemExit('Furniture.cs 的貨架表讀不到')


# ──────────── 格盤數學（跟 ShopRoom.cs 同一套）────────────

def g2w(gx, gy):
    return (ORIGIN_X + (gx - gy) * TILE_W / 2.0, ORIGIN_Y - (gx + gy) * TILE_H / 2.0)


def to_grid(x, y):
    a = (x - ORIGIN_X) / (TILE_W / 2.0)
    b = (ORIGIN_Y - y) / (TILE_H / 2.0)
    return ((a + b) / 2.0, (b - a) / 2.0)


def tile_center(c):
    return g2w(c[0], c[1])


def walk_floor(margin=FLOOR_MARGIN):
    lo = -0.5 + margin
    hx, hy = GRID_W - 0.5 - margin, GRID_H - 0.5 - margin
    return [g2w(lo, lo), g2w(hx, lo), g2w(hx, hy), g2w(lo, hy)]


def footprint_poly(gx, gy, w, h, inset=INSET):
    x0, x1 = gx - 0.5 + inset, gx + w - 0.5 - inset
    y0, y1 = gy - 0.5 + inset, gy + h - 0.5 - inset
    return [g2w(x0, y0), g2w(x1, y0), g2w(x1, y1), g2w(x0, y1)]


def ccw(poly):
    area = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly)))
    return poly[::-1] if area < 0 else poly


def poly_sd(poly, px, py):
    """點（numpy 陣列）到凸多邊形的有號距離：外正內負。同 Obstacles.PolyDist。"""
    poly = ccw(poly)
    best = np.full(px.shape, np.inf)
    inside = np.ones(px.shape, bool)
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = np.clip(((px - ax) * dx + (py - ay) * dy) / l2, 0.0, 1.0)
        qx, qy = ax + dx * t, ay + dy * t
        best = np.minimum(best, (px - qx) ** 2 + (py - qy) ** 2)
        inside &= (dx * (py - ay) - dy * (px - ax)) >= 0.0
    d = np.sqrt(best)
    return np.where(inside, -d, d)


# ──────────── 擺放規則（RoomLayout.Check 的格子部分）────────────

def size(p):
    w, h, _ = DEFS[p['id']]
    return (h, w) if p.get('flip') else (w, h)


def cells_of(p):
    w, h = size(p)
    return {(p['gx'] + c, p['gy'] + r) for c in range(w) for r in range(h)}


def in_grid(c):
    return 0 <= c[0] < GRID_W and 0 <= c[1] < GRID_H


def front_clearance(p):
    if not DEFS[p['id']][2]:
        return []
    w, h = size(p)
    if not p.get('flip'):
        return [(p['gx'] + w, p['gy'] + r) for r in range(h)]
    return [(p['gx'] + c, p['gy'] + h) for c in range(w)]


def reserved():
    out = set()
    for d in DOORS.values():
        for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
            c = (d[0] + dx, d[1] + dy)
            if in_grid(c):
                out.add(c)
    return out


def check_layout(items):
    errs = []
    res = reserved()
    for i, p in enumerate(items):
        mine = cells_of(p)
        name = f"{p['id']}@({p['gx']},{p['gy']}){'翻' if p.get('flip') else ''}"
        if not all(in_grid(c) for c in mine):
            errs.append(f'{name} 超出地板')
        for j, o in enumerate(items):
            if i == j:
                continue
            if mine & cells_of(o):
                errs.append(f'{name} 跟別件重疊')
            if mine & set(front_clearance(o)):
                errs.append(f'{name} 壓到別的貨架走道')
            if set(front_clearance(p)) & cells_of(o):
                errs.append(f'{name} 自己的走道被擋')
        if mine & res:
            errs.append(f'{name} 壓到門口保留格')
        if any(not in_grid(c) for c in front_clearance(p)):
            errs.append(f'{name} 走道不在地板上')
    return sorted(set(errs))


def sale_front(items):
    for p in items:
        if p['id'] == 'sale_table':
            w, h = size(p)
            fx, fy = g2w(p['gx'] + w - 1 + 0.0, p['gy'] + h - 1 + 0.0)   # TileCenter
            return (fx, fy - TILE_H / 2.0 - SALE_GAP)                      # TileFront 再往下 SaleStandGap
    return None


# ──────────── flood fill ────────────

# 「寬裕」檢查：障礙再多長 SLACK px（＝走道淨空至少要 2×SLACK）。只用 2px 取樣的話，
# 淨空 6.6px 的走道（家具不內縮）在幾何上也「過得去」，但實際斜著走、點地自動走一定卡 ——
# 這一趟就是要抓這種情況（把 FurnitureInset 改成 0 重跑，一格走道會在這一趟失敗）。
SLACK = 4.0

WALK = walk_floor()
XS = [q[0] for q in WALK]
YS = [q[1] for q in WALK]
X0, X1, Y0, Y1 = min(XS), max(XS), min(YS), max(YS)


def free_mask(items, step, extra=0.0):
    nx = int((X1 - X0) // step) + 1
    ny = int((Y1 - Y0) // step) + 1
    gx, gy = np.meshgrid(X0 + np.arange(nx) * step, Y0 + np.arange(ny) * step)
    free = poly_sd(WALK, gx, gy) <= 0.0
    for p in items:
        w, h = size(p)
        free &= poly_sd(footprint_poly(p['gx'], p['gy'], w, h), gx, gy) >= R + extra
    return gx, gy, free


def flood(gx, gy, free, start):
    ny, nx = free.shape
    d = (gx - start[0]) ** 2 + (gy - start[1]) ** 2
    d = np.where(free, d, np.inf)
    k = int(np.argmin(d))
    reach = np.zeros_like(free)
    if not np.isfinite(d.flat[k]):
        return reach
    j0, i0 = divmod(k, nx)
    q = deque([(j0, i0)])
    reach[j0, i0] = True
    while q:
        j, i = q.popleft()
        for a, b in ((j + 1, i), (j - 1, i), (j, i + 1), (j, i - 1)):
            if 0 <= a < ny and 0 <= b < nx and free[a, b] and not reach[a, b]:
                reach[a, b] = True
                q.append((a, b))
    return reach


def reachable_within(gx, gy, reach, at, rng):
    m = reach & (((gx - at[0]) ** 2 + (gy - at[1]) ** 2) <= rng * rng)
    return bool(m.any())


def run(name, items, note=''):
    print(f'\n■ {name}' + (f' —— {note}' if note else ''))
    print('  家具：' + '、'.join(f"{p['id']}({p['gx']},{p['gy']}){'翻' if p.get('flip') else ''} "
                                 f"{size(p)[0]}×{size(p)[1]}" for p in items))
    errs = check_layout(items)
    print('  擺放規則：' + ('合法' if not errs else '⚠️ ' + '；'.join(errs)))
    all_ok = not errs
    results = {}
    for step, extra in ((2.0, 0.0), (8.0, 0.0), (2.0, SLACK)):
        gx, gy, free = free_mask(items, step, extra)
        sp = tile_center(SPAWN)
        reach = flood(gx, gy, free, sp)
        bad = []
        for dn, dc in DOORS.items():
            if not reachable_within(gx, gy, reach, tile_center(dc), DOOR_AUTO):
                bad.append(f'{dn}{dc}')
        sf = sale_front(items)
        if sf is not None and not reachable_within(gx, gy, reach, sf, SALE_RANGE):
            bad.append('販售桌前')
        aisle_n = 0
        for p in items:
            for c in front_clearance(p):
                aisle_n += 1
                if not reachable_within(gx, gy, reach, tile_center(c), 10.0):
                    bad.append(f"走道{c}（{p['id']}）")
        spawn_free = bool(free_mask_point(items, sp))
        results[step] = bad
        label = f'取樣 {step:.0f}px' + (f'＋寬裕 {extra:.0f}px' if extra else '')
        print(f'  {label}：可走 {100.0 * reach.sum() / max(1, free.sum()):.1f}% 的空地；'
              f'出生點{"可站" if spawn_free else "⚠️ 在障礙裡"}；檢查 3 扇門＋販售桌前＋{aisle_n} 格走道 → '
              + ('全部走得到' if not bad else '⚠️ 走不到：' + '、'.join(bad)))
        all_ok &= not bad and spawn_free
    return all_ok


def free_mask_point(items, p):
    px, py = np.array([p[0]]), np.array([p[1]])
    ok = poly_sd(WALK, px, py)[0] <= 0.0
    for it in items:
        w, h = size(it)
        ok &= poly_sd(footprint_poly(it['gx'], it['gy'], w, h), px, py)[0] >= R
    return ok


# ──────────── 解析數字 ────────────

def analytics():
    print(f'常數：一格 {TILE_W:.0f}×{TILE_H:.0f}、格盤 {GRID_W}×{GRID_H}、玩家半徑 {R:.0f}、'
          f'地板邊界內縮 {FLOOR_MARGIN} 格、家具碰撞內縮 {INSET} 格（每邊）')
    # 兩條平行磚緣（gx = c 與 gx = c+1）之間的垂直距離
    ex = np.array([TILE_W / 2.0, -TILE_H / 2.0])          # gx +1 的世界位移
    ey = np.array([-TILE_W / 2.0, -TILE_H / 2.0])         # gy +1 的世界位移
    nrm = np.array([-ey[1], ey[0]]) / np.linalg.norm(ey)  # 磚緣（沿 gy）的法線
    per = abs(float(ex @ nrm))
    raw = per - 2 * R
    inset = per * (1 + 2 * INSET) - 2 * R
    edge = per * (1 + INSET - FLOOR_MARGIN) - 2 * R + R   # 一側家具、一側地板邊（地板邊不用再扣半徑）
    print(f'一格的垂直寬 {per:.2f}px；一格走道（兩側都是家具）扣掉身寬後的淨空：'
          f'不內縮 {raw:.2f}px → 內縮後 {inset:.2f}px')
    print(f'一格走道（一側家具、一側地板邊）淨空：{edge:.2f}px')
    gap = float(np.linalg.norm(2 * INSET * (ex + ey)))
    print(f'斜對角相鄰（只碰一個角）的角縫：{gap:.2f}px（要 > {2 * R:.0f}px 才鑽得過 → '
          f'{"過得去" if gap > 2 * R else "過不去，要從旁邊繞（跟畫面一致：兩件家具在那裡頂著）"}）')

    # WalkFloor 與 ClampToFloor 同一塊區域？
    rng = np.random.default_rng(1)
    px = rng.uniform(X0 - 40, X1 + 40, 20000)
    py = rng.uniform(Y0 - 40, Y1 + 40, 20000)
    in_poly = poly_sd(WALK, px, py) <= 1e-6
    a = (px - ORIGIN_X) / (TILE_W / 2.0)
    b = (ORIGIN_Y - py) / (TILE_H / 2.0)
    fx, fy = (a + b) / 2.0, (b - a) / 2.0
    lo = -0.5 + FLOOR_MARGIN
    in_clamp = (fx >= lo - 1e-6) & (fx <= GRID_W - 0.5 - FLOOR_MARGIN + 1e-6) & \
               (fy >= lo - 1e-6) & (fy <= GRID_H - 0.5 - FLOOR_MARGIN + 1e-6)
    print(f'WalkFloor（多邊形）與 ClampToFloor（格座標夾）的區域比對：20000 個隨機點，不一致 '
          f'{int((in_poly != in_clamp).sum())} 個')

    # 腳底最多踩進佔地格多深（在格子裡、但不在「內縮多邊形＋半徑」裡的點）
    gxs, gys = np.meshgrid(np.linspace(-0.5, 0.5, 801), np.linspace(-0.5, 0.5, 801))
    wx, wy = g2w(5 + gxs, 5 + gys)
    sd = poly_sd(footprint_poly(5, 5, 1, 1), wx, wy)
    ok = sd >= R
    if ok.any():
        depth_x = np.minimum(gxs + 0.5, 0.5 - gxs)
        depth_y = np.minimum(gys + 0.5, 0.5 - gys)
        depth = np.minimum(depth_x, depth_y)[ok].max()
        near_front = (np.maximum(gxs, gys) >= 0.5 - INSET)[ok].all()
        print(f'腳底最多踩進佔地格 {depth:.3f} 格（≈{depth * per:.1f}px），而且都在離 +gx／+gy 面 {INSET} 格以內：'
              f'{"是" if near_front else "⚠️ 否"}（PlayerOrder 的尖角放寬只在這裡用得到）')
    else:
        print('腳底踩不進佔地格')


def main():
    analytics()
    sale = {'id': 'sale_table', 'gx': SALE_CELL[0], 'gy': SALE_CELL[1]}
    layouts = [
        ('預設擺設', [sale], '只有販售桌在 DefaultSaleCell'),
        ('一格走道（gx 方向，6 格長的死巷）', [
            {'id': 'shelf_box', 'gx': 0, 'gy': 0}, {'id': 'shelf_box', 'gx': 0, 'gy': 3},
            {'id': 'shelf_box', 'gx': 2, 'gy': 0}, {'id': 'shelf_box', 'gx': 2, 'gy': 3},
            sale,
        ], '左後牆兩座 1×3 貨架＋對面兩座，中間只留 gx=1 那一格，盡頭是後牆；(1,0) 走得到＝一格走道過得去'),
        ('一格走道（gy 方向，盡頭被堵）', [
            {'id': 'shelf_box', 'gx': 4, 'gy': 0, 'flip': True},
            {'id': 'shelf_box', 'gx': 4, 'gy': 2, 'flip': True},
            {'id': 'shelf_tall', 'gx': 7, 'gy': 0},
            {'id': 'sale_table', 'gx': 8, 'gy': 5},
        ], '右後牆翻面的 3×1 貨架前只留 gy=1 一排，另一頭被 1×2 高架堵住'),
        ('斜對角相鄰', [
            {'id': 'shelf_box', 'gx': 0, 'gy': 0}, {'id': 'shelf_box', 'gx': 1, 'gy': 3},
            sale, {'id': 'shelf_box', 'gx': 7, 'gy': 3},
        ], '兩座貨架角碰角、販售桌 (6,2) 跟貨架 (7,3) 角碰角'),
        ('販售桌貼著出生點', [
            {'id': 'sale_table', 'gx': 6, 'gy': 4},
            {'id': 'shelf_box', 'gx': 0, 'gy': 4}, {'id': 'shelf_tall', 'gx': 2, 'gy': 6},
        ], '桌子就在出生點正後方一格；左側貨架走道前再擺一座高架'),
        ('前排地板邊（以前的招牌格）', [
            sale, {'id': 'shelf_box', 'gx': 7, 'gy': 7},
        ], '招牌搬到城鎮後 (7,9) 不再是保留格：1×3 貨架一路壓到前排地板邊（佔 (7,7)~(7,9)、離城鎮門 4 格），擺法合法、門與走道都走得到'),
    ]
    ok = True
    for name, items, note in layouts:
        ok &= run(name, items, note)
    print('\n結論：' + ('全部通過' if ok else '⚠️ 有擺設沒通過（見上面）'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
