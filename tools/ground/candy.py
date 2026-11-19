"""
糖果鎮（場景 candy）：薄荷綠草地 + 十字巧克力磚路 + 中央廣場。

路的位置與寬度照原圖（tools/ground/orig/candy-town.png）抽出的遮罩，只把直角修圓。
糖果主題的處理：
  - 草是薄荷綠，小花以粉、白、淡藍為主，地上撒彩色糖粒。
  - 路是黑巧克力磚，外圍一圈奶油糖霜（下緣會往下滴）。
  - 廣場內圈換成牛奶巧克力磚，正中央一個粉白相間的薄荷糖漩渦地磚（原點＝地圖正中央）。
"""
import os

import numpy as np
from PIL import Image

import grass as G
import materials as M
import objects
from common import (ART_PX, pal, hexc, fnoise, dilate, erode, shift, edge_in, round_mask,
                    poisson_points, parse_stamp, dist_from, erode_big, dilate_big)
import layouts

SEED = 4242
HERE = os.path.dirname(os.path.abspath(__file__))

GRASS = pal('#2f5a50', '#386a5a', '#427b62', '#4e8d6a', '#5b9e72', '#6aae7a', '#80c085', '#a0d39a', '#c6e8b8')
BASE = 4
STYLE = dict(base=BASE, patch_sigma=36, patch_rough=0.18,
             patch_steps=[(-0.75, -1), (0.75, 1), (2.0, 1)])

DARK_CHOCO = dict(face=hexc('#5a3329'), hi=hexc('#774636'), lo=hexc('#43241c'),
                  groove=hexc('#2f1712'), shine=hexc('#94604b'))
MILK_CHOCO = dict(face=hexc('#80523f'), hi=hexc('#9c6a53'), lo=hexc('#633c2e'),
                  groove=hexc('#47281e'), shine=hexc('#bb8b6f'))
FROST = [hexc('#fbf1e4'), hexc('#efdccb'), hexc('#d9bba5')]   # 糖霜：亮、中、陰影
SPRINKLES = [(0xf2, 0x8f, 0xa8), (0x8f, 0xd3, 0xf0), (0xf7, 0xd7, 0x6a), (0xff, 0xff, 0xff),
             (0xb3, 0x9a, 0xe6), (0x8c, 0xd9, 0x9a)]
SWIRL = [hexc('#e9798f'), hexc('#fbf1e4')]
FLOWERS = [
    dict(petal=(0xf8, 0xb4, 0xc4), center=(0xff, 0xf2, 0xc8)),   # 粉
    dict(petal=(0xff, 0xf6, 0xee), center=(0xf2, 0x8f, 0xa8)),   # 白配粉心
    dict(petal=(0xb6, 0xe2, 0xf2), center=(0xff, 0xff, 0xff)),   # 淡藍
    dict(petal=(0xd8, 0xbf, 0xf2), center=(0xff, 0xf2, 0xc8)),   # 淡紫
    dict(petal=(0xf7, 0xd7, 0x6a), center=(0xf0, 0x9a, 0x6a)),   # 檸檬黃
]


def road_mask(h, w):
    """原圖裡的巧克力路（像素 r > g）→ 美術解析度。"""
    a = np.asarray(Image.open(os.path.join(HERE, 'orig', 'candy-town.png')).convert('RGB')).astype(int)
    br = a[..., 0] > a[..., 1] + 15
    # 以 32 格判讀（原圖每格都是整塊巧克力），去掉雜點
    H, W = br.shape
    g = br[:H // 32 * 32, :W // 32 * 32].reshape(H // 32, 32, W // 32, 32).mean((1, 3)) > 0.5
    k = 32 // ART_PX
    m = np.repeat(np.repeat(g, k, 0), k, 1)
    out = np.zeros((h, w), bool)
    out[:m.shape[0], :m.shape[1]] = m[:h, :w]
    return out


def bake():
    rng = np.random.default_rng(SEED)
    Wd, Hd = layouts.SIZES['candy']
    w, h = Wd // ART_PX, Hd // ART_PX
    raw = road_mask(h, w)
    road = round_mask(raw, 9.0, rng, jitter=0.03, jitter_sigma=6)
    # 廣場：原圖裡寬的那塊（把路寬 8 格以內的條狀去掉）→ 內圈牛奶巧克力
    plaza_raw = dilate_big(erode_big(raw, 80), 80) & raw
    plaza_in = round_mask(erode(plaza_raw, 16), 10.0, rng)
    frost_w = 4 + (fnoise(h, w, 2.5, rng) > 0.0).astype(int) + (fnoise(h, w, 6, rng) > 0.8)
    rd = dist_from(road, 7)
    frost = (rd >= 1) & (rd <= frost_w)
    # 下緣往下滴的糖霜
    drips = np.zeros((h, w), bool)
    bottom = frost & ~shift(frost | road, -1, 0, True)        # 糖霜帶的最下緣
    pts = np.argwhere(bottom & ~shift(road, -(4), 0))         # 只在「下面不是路」的地方
    for (y, x) in pts:
        if rng.random() < 0.12:
            L = int(rng.integers(2, 9))
            wdt = 2 if rng.random() < 0.6 else 3
            for i in range(L):
                for j in range(wdt - (1 if i == L - 1 and wdt > 1 else 0)):
                    yy, xx = y + 1 + i, x + j
                    if yy < h and xx < w:
                        drips[yy, xx] = True
    frost |= drips & ~road
    ground = ~(road | frost)

    # ── 草地 ──
    lev = G.base_levels(h, w, rng, STYLE)
    dark = np.zeros((h, w))
    near = dilate(frost, 1) & ground
    dark[near] = 1.0
    shade_core = np.zeros((h, w), bool)
    for f in objects.feet('candy'):
        a = f.art
        if f.obj.kind == 'building':
            rx, ry, cy, s = f.foot_w * 0.5, 8, f.cy - 3, 1.6
        elif a in ('p-cloud',):
            continue                                          # 雲是浮在空中的，不畫影
        else:
            rx, ry, cy, s = max(5, f.foot_w * 0.5), max(3, f.foot_w * 0.18), f.cy - 1.5, 1.3
        r = objects.ellipse_local(h, w, f.cx, cy, rx, ry, pad=3)
        if r is None:
            continue
        sy, sx, e = r
        dark[sy, sx] = np.maximum(dark[sy, sx], np.clip(e * 2.0 + 0.3, 0, 1) * s)
        shade_core[sy, sx] |= e > 0.2
    edge = G.edge_field(h, w, 36, rng, [(h - 1, w / 2, 80)])
    dark = np.maximum(dark, edge * 1.8)
    idx = G.shade_to_idx(lev, dark, rng).astype(int)
    dens = np.clip((fnoise(h, w, 14, rng) - 0.1) * 0.8, 0.02, 1)
    dens = np.clip(dens + edge * 0.6, 0, 1)
    G.add_tufts(idx, rng, dens, int(w * h / 240), tall_frac=0.12, allow=ground)
    G.add_clovers(idx, rng, np.full((h, w), 0.6), 120, allow=ground)
    idx = np.clip(idx, 0, len(GRASS) - 1)
    rgb = GRASS[idx]

    # ── 巧克力路 ──
    off = (1472 // ART_PX) % 16, (896 // ART_PX) % 16       # 磚縫對齊原本路的邊
    dark_t = M.choco_tiles(h, w, DARK_CHOCO, tile=16, off_x=off[0], off_y=off[1])
    milk_t = M.choco_tiles(h, w, MILK_CHOCO, tile=16, off_x=off[0], off_y=off[1])
    rgb[road] = dark_t[road]
    rgb[plaza_in] = milk_t[plaza_in]
    # 牛奶巧克力區外緣一圈深縫
    rgb[edge_in(plaza_in)] = MILK_CHOCO['groove']
    # 路的外緣：一圈最深色（糖霜下的陰影）
    rgb[edge_in(road)] = DARK_CHOCO['groove']

    # ── 中央的薄荷糖漩渦地磚 ──
    cy, cx = h / 2, w / 2
    yy, xx = np.mgrid[0:h, 0:w]
    rr = np.hypot((yy + 0.5 - cy), (xx + 0.5 - cx))
    ang = np.arctan2(yy + 0.5 - cy, xx + 0.5 - cx)
    R = 46
    disc = rr < R
    stripe = (np.floor((ang / (2 * np.pi) * 8 + rr / 34) % 2)).astype(int)
    rgb[disc] = np.array(SWIRL)[stripe[disc]]
    rgb[disc & (rr < 7)] = SWIRL[1]
    ring1 = (rr >= R) & (rr < R + 3)
    rgb[ring1] = FROST[0]
    rgb[(rr >= R + 3) & (rr < R + 5)] = MILK_CHOCO['groove']
    rgb[(rr >= R - 1) & (rr < R) ] = FROST[2]

    # ── 糖霜 ──
    fl = np.where(rd <= 1, 1, 0)
    frgb = np.array(FROST)[fl]
    rgb[frost] = frgb[frost]
    # 糖霜外緣（靠草那側）一點陰影，讓它有厚度
    fo = frost & dilate(ground, 1)
    rgb[fo & shift(ground, -1, 0, False)] = FROST[2]     # 下方是草 → 下緣陰影
    # 糖霜上的糖粒
    for (y, x) in np.argwhere(frost & (rng.random((h, w)) < 0.04)):
        rgb[y, x] = SPRINKLES[int(rng.integers(len(SPRINKLES)))]

    # ── 草地點綴：花、糖粒、小軟糖 ──
    ov = np.zeros((h, w, 3), np.uint8)
    ovm = np.zeros((h, w), bool)
    fl_dens = np.clip(0.3 + 0.6 * fnoise(h, w, 50, rng), 0, 1)
    fl_dens[shade_core | ~erode(ground, 3)] = 0
    G.add_flowers(ov, ovm, rng, fl_dens, 150, FLOWERS, allow=ground, per=(5, 13), spread=6,
                  stem=tuple(GRASS[3]))
    sp_dens = np.clip(fnoise(h, w, 20, rng) - 0.4, 0, 1)
    sp_dens[~erode(ground, 2)] = 0
    for (y, x) in poisson_points(h, w, 900, rng, sp_dens):
        c = SPRINKLES[int(rng.integers(len(SPRINKLES)))]
        if rng.random() < 0.5 and x + 1 < w:
            ov[y, x] = c; ov[y, x + 1] = c; ovm[y, x] = ovm[y, x + 1] = True
        elif y + 1 < h:
            ov[y, x] = c; ov[y + 1, x] = c; ovm[y, x] = ovm[y + 1, x] = True
    gum = parse_stamp([".ha.", "aaaa", "dddd"])
    for (y, x) in poisson_points(h, w, 70, rng, np.where(erode(ground, 4), 0.6, 0) * (1 - edge), min_d=30):
        base = np.array(SPRINKLES[int(rng.integers(len(SPRINKLES) - 1))])
        cols = {'h': (255, 255, 255), 'a': tuple(base), 'd': tuple((base * 0.72).astype(int))}
        for dy, dx, ch in gum:
            yy, xx2 = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx2 < w and ground[yy, xx2]:
                ov[yy, xx2] = cols[ch]
                ovm[yy, xx2] = True
    rgb[ovm] = ov[ovm]
    return rgb
