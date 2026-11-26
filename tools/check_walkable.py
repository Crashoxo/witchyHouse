# -*- coding: utf-8 -*-
"""
碰撞的離線可達性檢查 ＋ 障礙俯視預覽（不用開 Unity）。

    python tools/check_walkable.py [輸出資料夾]

對森林（main）、城鎮（town）、糖果鎮（candy）各做一次跟遊戲裡 Obstacles.SelfCheck 同樣的檢查：
  1. 依 Data/ForestLayout.cs、TownLayout.cs、Candy.cs 的座標，用 tools/gen_footprints.py 的規則
     （同一份 CATS／RULES／玩家半徑／邊緣內縮）算出每個物件的落地範圍；城鎮小屋的門口照
     Doorways.cs 的門座標挖開；
  2. 以 16px 的粗格從玩家出生點（場景產生器裡的位置）flood fill，得到可走區域；
  3. 逐一檢查互動點在它的互動距離內是否有可走到的格子：採集點（Range）、門（自動觸發距離
     ＋按 E 的距離）、NPC、商店、每個會換場景的邊界出口；城鎮另外檢查村民路點有沒有落在障礙裡。
藥水室（brew，SVG 重畫的房間）另外檢查：家具的落地範圍與地板可走多邊形都來自 tools/gen_brew_room.py
（room_data()），從出生點 flood fill、五個互動點（床／衣櫃／木箱／鍋爐／出口）各自的互動距離內有沒有走得到的位置，
並列出互動點兩兩之間「同時在兩個範圍內、走得到的位置」（一顆 E 會同時觸發兩件事的地方，要是「無」）。
輸出摘要，並在輸出資料夾存每張地圖的俯視預覽（整張縮半＋幾張 1:1 特寫）：
  紅框＝落地範圍、淡紅＝再長一個玩家半徑（腳底圓心進不去的範圍）、灰＝走不到、
  綠點＝走得到的互動點、紅叉＝走不到、黃框＝可走範圍（內縮後的邊界）、藍點＝村民路點。
城鎮另外把河的水域障礙（Data/TownWaterData.cs，tools/gen_town_water.py 產生、執行期由 Core/TownWater 登記）
算進去 —— 預覽裡是青色框（跟物件的紅框分開）；店門口的開店／關店招牌（Core/ShopSignPost，執行期在小屋
旁邊生成、柱腳登記一個小橢圓）也照 Doorways.CottageSign／ShopSignPost.BlockHalf 算進去；並先不算水跑一次，印出加水域前後的可走面積，
以及少掉的格子有多少是「水面本身（含玩家半徑）」、多少是被河切斷的（後者應該是 0）。

⚠️ 規則數值一律來自 gen_footprints.py —— 這支不自己寫任何碰撞常數。
"""
import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'ground'))

import gen_footprints as G   # noqa: E402
import gen_town_water as TW  # noqa: E402
import layouts               # noqa: E402

ROOT = G.ROOT
CORE = os.path.join(ROOT, 'Assets', 'Scripts', 'Core')
EDITOR = os.path.join(ROOT, 'Assets', 'Editor')
FLOOD = 16.0     # flood fill 的格子（像素）—— 跟 Obstacles.SelfCheck 一樣

SCENES = {
    # 場景名: (地圖, 場景產生器, 地面圖)
    'main': ('forest', 'ForestSceneBuilder.cs', 'art/ground/forest'),
    'town': ('town', 'TownSceneBuilder.cs', 'art/ground/town'),
    'candy': ('candy', 'CandySceneBuilder.cs', 'art/ground/candy'),
}


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def num(s):
    return float(s.rstrip('f'))


# ──────────── 從 C# 抽資料 ────────────

def spawn_of(builder):
    src = read(os.path.join(EDITOR, builder))
    m = re.search(r'player\.transform\.position\s*=\s*(Vector3\.zero|new Vector3\(([^)]*)\))', src)
    if m.group(1) == 'Vector3.zero':
        return 0.0, 0.0
    a = [num(v.strip()) for v in m.group(2).split(',')]
    return a[0], a[1]


def portals_of(scene):
    src = read(os.path.join(G.DATA, 'TownRoads.cs'))
    out = []
    for m in re.finditer(r'Scene\s*=\s*"(\w+)",\s*Side\s*=\s*"(\w+)",\s*To\s*=\s*"(\w+)",\s*At\s*=\s*(-?[\d.]+)f?,'
                         r'\s*Span\s*=\s*([\d.]+)f?', src):
        if m.group(1) == scene:
            out.append(dict(side=m.group(2), to=m.group(3), at=float(m.group(4)), span=float(m.group(5))))
    return out


def roads():
    src = read(os.path.join(G.DATA, 'TownRoads.cs'))
    i = src.index('Vector2[] Walk')
    j = src.index('};', i)
    return [(float(a), float(b)) for a, b in re.findall(r'new\((-?[\d.]+)f,\s*(-?[\d.]+)f\)', src[i:j])]


def door_defaults():
    src = read(os.path.join(CORE, 'SceneDoor.cs'))
    auto = float(re.search(r'autoRange\s*=\s*([\d.]+)f', src).group(1))
    inter = float(re.search(r'interactRange\s*=\s*([\d.]+)f', src).group(1))
    return auto, inter


def town_interacts(objs):
    """城鎮：小屋的門、三位 NPC、兩間商店（Doorways.cs 掛上去的，位置＝那個物件的位置）。"""
    src = read(os.path.join(CORE, 'Doorways.cs'))
    by = {}
    for o in objs:
        by.setdefault(o.art.split('/')[-1], o)
    auto, inter = door_defaults()
    m = re.search(r'CottageDoor\s*=\s*new\((-?[\d.]+)f,\s*(-?[\d.]+)f\)', src)
    cot = by['cottage-home']
    doors = [dict(name='門：cottage-home → shop', x=cot.x + float(m.group(1)), y=cot.y + float(m.group(2)),
                  auto=auto, range=inter)]
    pts = []
    npc_r = float(re.search(r't\.interactRange\s*=\s*([\d.]+)f', src).group(1))
    shop_r = float(re.search(r'a\.interactRange\s*=\s*([\d.]+)f', src).group(1))
    for node in re.findall(r'AddNpc\("([^"]+)"', src):
        o = by[node]
        pts.append(dict(name='NPC：' + node, x=o.x, y=o.y, range=npc_r))
    for node in re.findall(r'AddShop\("([^"]+)"', src):
        o = by[node]
        pts.append(dict(name='商店：' + node, x=o.x, y=o.y, range=shop_r))
    return doors, pts


def forest_interacts():
    src = read(os.path.join(G.DATA, 'ForestLayout.cs'))
    pts = []
    for m in re.finditer(r'Art\s*=\s*"art/([^"]+)",\s*X\s*=\s*(-?[\d.]+)f,\s*Y\s*=\s*(-?[\d.]+)f,.*?Range\s*=\s*([\d.]+)f',
                         src):
        pts.append(dict(name='採集：' + m.group(1), x=float(m.group(2)), y=float(m.group(3)),
                        range=float(m.group(4))))
    return pts


def candy_interacts(objs):
    src = read(os.path.join(CORE, 'CandyTown.cs'))
    r = float(re.search(r'talk\.interactRange\s*=\s*([\d.]+)f', src).group(1))
    return [dict(name='NPC：' + o.art.split('/')[-1], x=o.x, y=o.y, range=r) for o in objs if o.kind == 'npc']


# ──────────── 障礙 ────────────

def shop_sign_shape(objs):
    """城鎮店門口的招牌柱腳（Core/ShopSignPost 在 Start 用 Obstacles.AddEllipse 登記的那一個）。
    落地點＝小屋位置＋Doorways.CottageSign，對齊到偶數像素（跟 ShopSignPost.Ensure 一樣）。"""
    door_src = read(os.path.join(CORE, 'Doorways.cs'))
    sign_src = read(os.path.join(CORE, 'ShopSignPost.cs'))
    m = re.search(r'CottageSign\s*=\s*new\((-?[\d.]+)f,\s*(-?[\d.]+)f\)', door_src)
    b = re.search(r'BlockHalf\s*=\s*new\((-?[\d.]+)f,\s*(-?[\d.]+)f\)', sign_src)
    cot = next(o for o in objs if o.art.split('/')[-1] == 'cottage-home')
    # C# 的 Mathf.Round 是銀行家捨入；這裡的值不會剛好落在 .5，用一般 round 一樣
    fx = round((cot.x + float(m.group(1))) / 2) * 2
    fy = round((cot.y + float(m.group(2))) / 2) * 2
    return dict(name='shop-sign', cat='prop', shape='ellipse', cx=fx, cy=fy,
                hx=float(b.group(1)), hy=float(b.group(2)))


def water_shapes():
    """城鎮河的水域矩形（讀遊戲實際用的 TownWaterData.cs），換成跟 world_shape 一樣的 box 形狀。"""
    return [dict(name='water', cat='water', shape='box', cx=(x0 + x1) / 2, cy=(y0 + y1) / 2,
                 hx=(x1 - x0) / 2, hy=(y1 - y0) / 2) for x0, y0, x1, y1 in TW.load_cs()]


def build(scene, water=True):
    mapname, builder, ground = SCENES[scene]
    W, H = layouts.SIZES[mapname]
    objs = layouts.OBJECTS[mapname]()
    shapes, placed = [], []
    for o in objs:
        fp = G.footprint(o.art)
        placed.append((o, fp))
        s = G.world_shape(fp, o.x, o.y, o.scale, o.pivot)
        if s is not None:
            shapes.append(s)
    doors, pts = [], []
    if scene == 'town':
        doors, pts = town_interacts(objs)
    elif scene == 'main':
        pts = forest_interacts()
    else:
        pts = candy_interacts(objs)
    if doors:
        shapes = G.carve_doors(shapes, [(d['x'], d['y']) for d in doors], doors[0]['auto'])
    # 河：執行期是 Begin 之後登記（CarveDoors 只挖 building 類，不會動到它們），這裡接在挖門之後
    if scene == 'town' and water:
        shapes = shapes + water_shapes()
    if scene == 'town':
        shapes = shapes + [shop_sign_shape(objs)]     # 招牌也是 Begin 之後才登記（ShopSignPost.Start）
    bounds = (-W / 2 + G.EDGE_SIDE, -H / 2 + G.EDGE_BOTTOM, W / 2 - G.EDGE_SIDE, H / 2 - G.EDGE_TOP)
    return dict(scene=scene, map=mapname, W=W, H=H, objs=placed, shapes=shapes, doors=doors, pts=pts,
                bounds=bounds, spawn=spawn_of(builder), portals=portals_of(scene), ground=ground)


def pen_grid(s, X, Y, r=G.PLAYER_RADIUS):
    """整張格子的穿入深度（跟 gen_footprints.penetration 同一個算法，向量化）。"""
    if s['shape'] == 'ellipse':
        rx, ry = s['hx'] + r, s['hy'] + r
        d = np.hypot((X - s['cx']) / rx, (Y - s['cy']) / ry)
        return (1 - d) * min(rx, ry)
    qx = np.abs(X - s['cx']) - s['hx']
    qy = np.abs(Y - s['cy']) - s['hy']
    outside = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)
    return r - outside


def flood(m):
    x0, y0, x1, y1 = m['bounds']
    nx = int((x1 - x0) // FLOOD) + 1
    ny = int((y1 - y0) // FLOOD) + 1
    xs = x0 + np.arange(nx) * FLOOD
    ys = y0 + np.arange(ny) * FLOOD
    X, Y = np.meshgrid(xs, ys)
    free = np.ones(X.shape, bool)
    for s in m['shapes']:
        free &= pen_grid(s, X, Y) <= 0
    # 出生點：最近的可走格（遊戲裡也是這樣，出生在障礙裡仍走得出來）
    sx, sy = m['spawn']
    d = np.hypot(X - sx, Y - sy) + np.where(free, 0, 1e9)
    start = np.unravel_index(np.argmin(d), d.shape)
    spawn_blocked = any(G.penetration(s, sx, sy) > 0 for s in m['shapes'])
    reach = np.zeros_like(free)
    stack = [start]
    reach[start] = True
    while stack:
        j, i = stack.pop()
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = j + dj, i + di
            if 0 <= a < ny and 0 <= b < nx and free[a, b] and not reach[a, b]:
                reach[a, b] = True
                stack.append((a, b))
    m.update(X=X, Y=Y, free=free, reach=reach, spawn_blocked=spawn_blocked)
    return m


def reachable_within(m, x, y, r):
    d = np.hypot(m['X'] - x, m['Y'] - y)
    return bool(np.any(m['reach'] & (d <= r)))


def check(m):
    out = []
    x0, y0, x1, y1 = m['bounds']
    bad = []
    for p in m['pts']:
        ok = reachable_within(m, p['x'], p['y'], p['range'])
        p['ok'] = ok
        if not ok:
            bad.append('%s (%.0f, %.0f) 範圍 %.0f' % (p['name'], p['x'], p['y'], p['range']))
    for d in m['doors']:
        d['ok_auto'] = reachable_within(m, d['x'], d['y'], d['auto'])
        d['ok'] = reachable_within(m, d['x'], d['y'], d['range'])
        if not d['ok']:
            bad.append('%s (%.0f, %.0f) 按 E 範圍 %.0f' % (d['name'], d['x'], d['y'], d['range']))
        elif not d['ok_auto']:
            bad.append('%s (%.0f, %.0f) 只能按 E，走不到自動觸發的 %.0f 內' % (d['name'], d['x'], d['y'], d['auto']))
    for g in m['portals']:
        X, Y, R = m['X'], m['Y'], m['reach']
        if g['side'] == 'right':
            zone = (X >= x1 - FLOOD) & (np.abs(Y - g['at']) <= g['span'])
        elif g['side'] == 'left':
            zone = (X <= x0 + FLOOD) & (np.abs(Y - g['at']) <= g['span'])
        elif g['side'] == 'top':
            zone = (Y >= y1 - FLOOD) & (np.abs(X - g['at']) <= g['span'])
        else:
            zone = (Y <= y0 + FLOOD) & (np.abs(X - g['at']) <= g['span'])
        g['ok'] = bool(np.any(R & zone))
        if not g['ok']:
            bad.append('邊界出口 %s → %s（At %.0f ±%.0f）' % (g['side'], g['to'], g['at'], g['span']))
    road_bad = []
    if m['scene'] == 'town':
        for (x, y) in roads():
            hit = [s['name'] for s in m['shapes'] if G.penetration(s, x, y, 0.0) > 0]
            if hit:
                road_bad.append('(%.0f, %.0f) 在 %s 裡' % (x, y, '、'.join(hit)))
    cats = {}
    for s in m['shapes']:
        cats[s['cat']] = cats.get(s['cat'], 0) + 1
    walkable = m['reach'].sum() / m['free'].size
    out.append('[Obstacles] %s：障礙 %d 個（%s）；可走面積 %.1f%%（可走範圍內、從出生點走得到的格子）；'
               '出生點 (%.0f, %.0f)%s' % (
                   m['scene'], len(m['shapes']), '、'.join('%s %d' % kv for kv in sorted(cats.items())),
                   walkable * 100, m['spawn'][0], m['spawn'][1], '（⚠️ 在障礙裡）' if m['spawn_blocked'] else ''))
    out.append('    可走範圍 x %.0f..%.0f、y %.0f..%.0f；互動點 %d 個、門 %d 個、邊界出口 %d 個' % (
        x0, x1, y0, y1, len(m['pts']), len(m['doors']), len(m['portals'])))
    out.append('    走不到的互動點：' + ('無' if not bad else ''))
    out += ['      - ' + b for b in bad]
    if m['scene'] == 'town':
        out.append('    落在障礙裡的村民路點：' + ('無' if not road_bad else ''))
        out += ['      - ' + b for b in road_bad]
    m['bad'], m['road_bad'] = bad, road_bad
    return out


# ──────────── 預覽 ────────────

def preview(m, outdir):
    W, H = m['W'], m['H']
    gp = os.path.join(G.RES, m['ground'].replace('/', os.sep) + '.png')
    img = Image.open(gp).convert('RGBA').resize((W, H), Image.NEAREST)

    def P(x, y):                      # 世界 → 圖（左上原點、y 朝下）
        return x + W / 2, H / 2 - y

    # 物件圖（照腳底 y 由上往下畫）
    items = []
    for o, fp in m['objs']:
        x0, y0, x1, y1 = G.image_rect(fp, o.x, o.y, o.scale, o.pivot)
        items.append((y0, o, fp, (x0, y0, x1, y1)))
    for _, o, fp, (x0, y0, x1, y1) in sorted(items, key=lambda t: -t[0]):
        sp = Image.open(os.path.join(G.RES, o.art.replace('/', os.sep) + '.png')).convert('RGBA')
        sw, sh = max(1, round(sp.width * o.scale)), max(1, round(sp.height * o.scale))
        sp = sp.resize((sw, sh), Image.NEAREST)
        a = np.asarray(sp).copy()
        a[..., 3] = (a[..., 3] * 0.55).astype(np.uint8)          # 半透明，才看得到底下的範圍
        px, py = P(x0, y1)
        img.alpha_composite(Image.fromarray(a), (int(round(px)), int(round(py))))

    ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    # 走不到（但在可走範圍內）的格子：灰
    X, Y, R, F = m['X'], m['Y'], m['reach'], m['free']
    hf = FLOOD / 2
    for j, i in zip(*np.nonzero(~R)):
        x, y = X[j, i], Y[j, i]
        a, b = P(x - hf, y + hf)
        c, e = P(x + hf, y - hf)
        d.rectangle([a, b, c, e], fill=(40, 40, 40, 110) if F[j, i] else (200, 40, 40, 60))
    # 可走範圍
    x0, y0, x1, y1 = m['bounds']
    a, b = P(x0, y1)
    c, e = P(x1, y0)
    d.rectangle([a, b, c, e], outline=(255, 220, 60, 255), width=3)
    # 落地範圍
    r = G.PLAYER_RADIUS
    for s in m['shapes']:
        cols = ((r, (120, 230, 255, 200), 1), (0, (0, 170, 230, 255), 2)) if s['cat'] == 'water' else                ((r, (255, 120, 120, 200), 1), (0, (230, 20, 20, 255), 2))
        for grow, col, w in cols:
            a, b = P(s['cx'] - s['hx'] - grow, s['cy'] + s['hy'] + grow)
            c, e = P(s['cx'] + s['hx'] + grow, s['cy'] - s['hy'] - grow)
            if s['shape'] == 'ellipse':
                d.ellipse([a, b, c, e], outline=col, width=w)
            else:
                d.rounded_rectangle([a, b, c, e], radius=grow, outline=col, width=w)
    # 村民路點
    if m['scene'] == 'town':
        for (x, y) in roads():
            a, b = P(x, y)
            hit = any(G.penetration(s, x, y, 0.0) > 0 for s in m['shapes'])
            col = (255, 0, 0, 255) if hit else (60, 140, 255, 255)
            d.ellipse([a - 4, b - 4, a + 4, b + 4], fill=col)
    # 互動點
    for p in m['pts'] + m['doors']:
        a, b = P(p['x'], p['y'])
        if p.get('ok', True) and p.get('ok_auto', True):
            d.ellipse([a - 6, b - 6, a + 6, b + 6], fill=(40, 230, 90, 255), outline=(0, 0, 0, 255))
        else:
            d.line([a - 9, b - 9, a + 9, b + 9], fill=(255, 0, 0, 255), width=4)
            d.line([a - 9, b + 9, a + 9, b - 9], fill=(255, 0, 0, 255), width=4)
    for dd in m['doors']:
        a, b = P(dd['x'], dd['y'])
        d.ellipse([a - dd['auto'], b - dd['auto'], a + dd['auto'], b + dd['auto']], outline=(80, 200, 255, 255), width=2)
    # 出生點
    a, b = P(*m['spawn'])
    d.rectangle([a - 7, b - 7, a + 7, b + 7], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    img.alpha_composite(ov)

    os.makedirs(outdir, exist_ok=True)
    full = os.path.join(outdir, '%s-full.png' % m['scene'])
    img.resize((W // 2, H // 2), Image.LANCZOS).convert('RGB').save(full)
    saved = [full]
    # 1:1 特寫
    crops = {
        'main': [('spawn', 0, 0), ('trees', -900, -400), ('top-exit', 0, 700), ('east-exit', 1250, 0)],
        'town': [('cottage', -538, 330), ('plaza', 400, 300), ('shops-north', 0, 700), ('west-exit', -1350, -40),
                 ('river-north', 1180, 220), ('river-mid', 1180, -40), ('river-south', 1180, -580)],
        'candy': [('plaza', 0, 0), ('south-exit', 0, -800), ('north', 0, 650)],
    }[m['scene']]
    for name, cx, cy in crops:
        a, b = P(cx, cy)
        box = (int(a - 480), int(b - 320), int(a + 480), int(b + 320))
        p = os.path.join(outdir, '%s-%s.png' % (m['scene'], name))
        img.crop(box).convert('RGB').save(p)
        saved.append(p)
    return saved


def water_diff(m):
    """城鎮：不算水再跑一次 flood fill，比較加水域前後的可走面積，並把少掉的格子分成
    「水面本身（腳底圓心進不去的水域範圍內）」與「被河切斷、走不過去的岸」兩種。"""
    m0 = flood(build('town', water=False))
    ws = [s for s in m['shapes'] if s['cat'] == 'water']
    inwater = np.zeros(m['X'].shape, bool)
    for s in ws:
        inwater |= pen_grid(s, m['X'], m['Y']) > 0
    lost = m0['reach'] & ~m['reach']
    gained = m['reach'] & ~m0['reach']
    n = m['free'].size
    out = ['[水域] 城鎮河的矩形 %d 個（Data/TownWaterData.cs）' % len(ws),
           '    可走面積：不算水 %.2f%% → 算水 %.2f%%（差 %.2f 個百分點、%d 格）' % (
               100 * m0['reach'].sum() / n, 100 * m['reach'].sum() / n,
               100 * (m0['reach'].sum() - m['reach'].sum()) / n, lost.sum()),
           '    少掉的格子：水面本身（含玩家半徑）%d 格、被河切斷的岸 %d 格；多出來的 %d 格' % (
               (lost & inwater).sum(), (lost & ~inwater).sum(), gained.sum())]
    m['water_cut'] = int((lost & ~inwater).sum())
    return out


def brew(outdir):
    """藥水室：規則與座標全部來自 gen_brew_room.py（這裡不寫任何數字）。"""
    import gen_brew_room as B
    data = B.room_data(None)
    lines = B.check_room(data, verbose=False)
    base = Image.open(os.path.join(G.RES, 'rooms', 'brew', 'shell-day.png'))
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, 'brew-full.png')
    B.collision_image(data, base).save(p)
    return lines, bool(data['bad']) or bool(data['pair_bad']), [p]


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'Temp', 'collide')
    lines = ['玩家半徑 %.0f；邊緣內縮 上 %.0f／左右 %.0f／下 %.0f；門口挖開半寬 %.0f' % (
        G.PLAYER_RADIUS, G.EDGE_TOP, G.EDGE_SIDE, G.EDGE_BOTTOM, G.DOOR_GAP_HALF)]
    files = []
    any_bad = False
    for scene in ('main', 'town', 'candy'):
        m = flood(build(scene))
        if scene == 'town':
            lines += water_diff(m)
        lines += check(m)
        any_bad |= bool(m['bad'])
        files += preview(m, outdir)
    bl, bbad, bfiles = brew(outdir)
    lines += bl
    any_bad |= bbad
    files += bfiles
    print('\n'.join(lines))
    print('預覽圖：')
    for f in files:
        print('  ' + f)
    sys.exit(1 if any_bad else 0)


if __name__ == '__main__':
    main()
