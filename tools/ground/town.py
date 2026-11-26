"""
城鎮（場景 town）：草地 + 石板街 + 鋪石廣場 + 泥土路 + 河與橋。

路與河的位置一律從原圖（tools/ground/orig/town-ground.png）抽出來（見 townmask.py），
再把方塊邊修圓、加材質。路的「中心線」與寬度都不變（村民走的路點 Data/TownRoads.cs
全在路的內部），只是直角變成圓角、邊緣多一圈描邊與壓在路邊的草葉。
"""
import numpy as np

import grass as G
import materials as M
import objects
import townmask
from common import (ART_PX, pal, hexc, fnoise, blur, dilate, erode, shift, edge_in,
                    round_mask, dist_from)
import layouts

SEED = 7310

# ── 草：比森林亮、偏暖一點（城鎮是開闊的地方）──
GRASS = pal('#24402a', '#2f5030', '#3b6034', '#497238', '#56823c', '#649043', '#76a04c', '#8fb45a', '#abc972')
BASE = 4
STYLE = dict(base=BASE, patch_sigma=34, patch_rough=0.14,
             patch_steps=[(-0.9, -1), (0.8, 1), (2.0, 1)])

# ── 石板街（主要街道）：帶一點暖的灰，跟木造建築搭 ──
COBBLE = dict(stones=[hexc('#6f6966'), hexc('#7f7873'), hexc('#8e8780'), hexc('#9d968d')],
              mortar=hexc('#4a4341'), deep=hexc('#3a3433'), hi=hexc('#b0a89c'))
COBBLE_EDGE = hexc('#3e3836')
# ── 廣場鋪石：較亮的米灰大方石 ──
PAVER = dict(stones=[hexc('#8f8475'), hexc('#9d9282'), hexc('#aa9f8d'), hexc('#b6ab98')],
             mortar=hexc('#6a6055'), deep=hexc('#564d44'), hi=hexc('#c6bca8'))
PAVER_CURB = (hexc('#d8cfbd'), hexc('#5c534a'))      # 路緣石：亮邊 + 暗邊
# ── 泥土路 ──
DIRT = dict(levels=[hexc('#6f5236'), hexc('#82613f'), hexc('#957149'), hexc('#a68053'), hexc('#b68f60')],
            speck_dark=hexc('#5c4330'), speck_light=hexc('#c9a575'))
DIRT_EDGE = hexc('#644a31')
# ── 水 ──
WATER = dict(deep=hexc('#3a6fa6'), mid=hexc('#4687bd'), shallow=hexc('#5ea2cf'),
             light=hexc('#86c0e0'), hi=hexc('#c4e6f2'))
WATER_SHADOW = hexc('#2f5c8c')
BANK = [hexc('#6b5a3e'), hexc('#8f7a55'), hexc('#a8936a')]     # 濕泥 → 乾沙

FLOWERS = [
    dict(petal=(0xf4, 0xf0, 0xe2), center=(0xf2, 0xc8, 0x4f)),
    dict(petal=(0xf2, 0xc8, 0x4f), center=(0xc4, 0x80, 0x2a)),
    dict(petal=(0xe8, 0x8f, 0xa8), center=(0xfb, 0xe8, 0xe8)),
    dict(petal=(0xe4, 0x6a, 0x58), center=(0xf6, 0xd6, 0x7a)),   # 紅（城鎮花多一點）
    dict(petal=(0x9d, 0xa8, 0xe6), center=(0xf5, 0xf0, 0xff)),
]
PEBBLE = {'h': (0xcf, 0xc8, 0xb4), 'l': (0x9c, 0x96, 0x86), 'd': (0x5f, 0x5b, 0x4e)}


def _clean_grid(g):
    """格子地圖小修：分出廣場鋪石、去掉原圖描邊造成的零星泥土格。"""
    g = g.copy()
    H, W = g.shape
    stone = (g == 'C') | (g == 'P')
    isP = g == 'P'
    for y in range(H):
        for x in range(W):
            if stone[y, x]:
                y0, y1, x0, x1 = max(0, y - 3), min(H, y + 4), max(0, x - 3), min(W, x + 4)
                s = stone[y0:y1, x0:x1].sum()
                p = isP[y0:y1, x0:x1].sum()
                g[y, x] = 'P' if p / max(1, s) > 0.2 else 'C'
    # 小塊（≤3 格）泥土、旁邊是石頭 → 併進石頭
    seen = np.zeros((H, W), bool)
    for y in range(H):
        for x in range(W):
            if g[y, x] != 'D' or seen[y, x]:
                continue
            comp, stack = [], [(y, x)]
            seen[y, x] = True
            while stack:
                cy, cx = stack.pop()
                comp.append((cy, cx))
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < H and 0 <= nx < W and not seen[ny, nx] and g[ny, nx] == 'D':
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(comp) <= 4:
                nb = []
                for cy, cx in comp:
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < H and 0 <= nx < W and g[ny, nx] != 'D':
                            nb.append(g[ny, nx])
                stones = [c for c in nb if c in 'CP']
                if stones:
                    fill = max(set(stones), key=stones.count)
                    for cy, cx in comp:
                        g[cy, cx] = fill
    return g


def masks(h, w):
    g = _clean_grid(townmask.grid())
    k = h // g.shape[0]                       # 每格幾個美術像素（32 世界像素 → 16）
    up = lambda c: np.repeat(np.repeat(g == c, k, 0), k, 1)
    return {c: up(c) for c in 'GCPDW'}


def shape_masks(rng, h, w):
    """修圓後的路／河遮罩（美術解析度，row 0 ＝地圖最上緣）。

    bake() 與 tools/gen_town_water.py（河的碰撞）共用 —— 碰撞跟畫出來的水是同一份遮罩。
    ⚠️ 會從 rng 取亂數，而且**順序固定**：bake() 必須最先呼叫它、再做其他用到 rng 的事，
       不然後面草地／材質的亂數全部錯位、烤圖就變了。gen_town_water.py 用同一個 SEED
       新開 rng、只呼叫這一段，得到的遮罩跟 bake() 裡的逐像素相同。
    ⚠️ 回傳的 stone 是 bake() 之後會就地 |= 噴泉鋪石的那個陣列；water 在那之前就算好了，不受影響。
    回傳 dict：m（格子遮罩）、stone_raw、stone、dirt、water_r（橋下也算水）、water（最後畫成水的）。
    """
    m = masks(h, w)
    # ── 修圓 ──
    stone_raw = m['C'] | m['P']
    stone = round_mask(stone_raw, 6.0, rng, jitter=0.05, jitter_sigma=5)
    dirt = round_mask(m['D'], 7.0, rng, jitter=0.14, jitter_sigma=4) & ~stone
    water_r = round_mask(m['W'] | (stone_raw & dilate(m['W'], 16)), 13.0, rng, jitter=0.06, jitter_sigma=12)
    # ↑ 先把橋下也當水一起修圓（河才是連續的一條），再讓石頭蓋在上面
    water = water_r & ~stone & ~dirt
    return dict(m=m, stone_raw=stone_raw, stone=stone, dirt=dirt, water_r=water_r, water=water)


def bake():
    rng = np.random.default_rng(SEED)
    Wd, Hd = layouts.SIZES['town']
    w, h = Wd // ART_PX, Hd // ART_PX
    sm = shape_masks(rng, h, w)
    m, stone, dirt, water = sm['m'], sm['stone'], sm['dirt'], sm['water']
    paver = stone & blur(m['P'].astype(float), 1.0).__gt__(0.5)
    # 噴泉（擺在草地上）腳下鋪一圈圓形鋪石，不然像是直接插在草裡
    for f in objects.feet('town'):
        if f.art == 'fountain':
            e = objects.ellipse(h, w, f.cx, f.cy - f.height * 0.32, f.width * 0.78, f.width * 0.52)
            disc = e > 0
            stone |= disc
            paver |= disc
    cobble = stone & ~paver
    road = stone | dirt
    ground = ~(road | water)                   # 草地

    # ── 草地：斑塊 + 陰影 ──
    lev = G.base_levels(h, w, rng, STYLE)
    dark = np.zeros((h, w))
    # 路邊與水邊的草暗一階（接縫的陰影）
    near_road = dilate(road, 1) & ground
    dark[near_road] = np.maximum(dark[near_road], 1.0)
    # 物件腳下
    shade_core = np.zeros((h, w), bool)
    for f in objects.feet('town'):
        a = f.art
        if not (0 <= f.cx < w and 0 <= f.cy < h + 10):
            continue
        if f.obj.art.startswith('art/town/'):            # 建築：沿著牆腳一條深色帶
            rx, ry, cy, s = f.foot_w * 0.55, 7, f.cy - 2, 1.7
        elif a.startswith('lamp'):
            rx, ry, cy, s = 4, 2, f.cy - 0.5, 1.2
        elif a.startswith('fence'):
            rx, ry, cy, s = f.foot_w * 0.5, 3, f.cy - 1, 1.1
        elif a.startswith('bridge'):
            continue
        else:                                              # 灌木、花盆、噴泉、拱門
            rx, ry, cy, s = max(5, f.foot_w * 0.55), max(3, f.foot_w * 0.2), f.cy - 1.5, 1.3
        r = objects.ellipse_local(h, w, f.cx, cy, rx, ry, pad=3)
        if r is None:
            continue
        sy, sx, e = r
        val = np.clip(e * 2.0 + 0.3, 0, 1) * s
        dark[sy, sx] = np.maximum(dark[sy, sx], val)
        shade_core[sy, sx] |= e > 0.2
    edge = G.edge_field(h, w, 30, rng, [(h / 2 + 40 / ART_PX, 0, 70)])
    dark = np.maximum(dark, edge * 1.6)

    idx = G.shade_to_idx(lev, dark, rng).astype(int)
    dens = np.clip((fnoise(h, w, 14, rng) - 0.1) * 0.8, 0.02, 1)
    dens = np.clip(dens + edge * 0.6, 0, 1)
    G.add_tufts(idx, rng, dens, int(w * h / 230), tall_frac=0.12, allow=ground)
    G.add_clovers(idx, rng, np.full((h, w), 0.6), 140, allow=ground)
    # 路邊的草葉：壓在路緣上（允許畫進路緣 1~2 格）
    road_edge_band = (dilate(ground, 2) & road) | (dilate(road, 2) & ground)
    edge_pts = np.argwhere(dilate(road, 2) & ground & ~dilate(road, 0))
    rng.shuffle(edge_pts)
    for (y, x) in edge_pts[: len(edge_pts) // 9]:
        pat = G.TUFTS[int(rng.integers(len(G.TUFTS)))]
        G.stamp_rel(idx, pat, int(y) - 1, int(x) - 1, allow=ground)
    idx = np.clip(idx, 0, len(GRASS) - 1)
    rgb = GRASS[idx]

    # ── 河岸（只畫在草地上）──
    wd = dist_from(water, 7)
    bn = fnoise(h, w, 4, rng)
    bank = (wd >= 1) & ground & (wd <= np.where(bn > 0.4, 5, np.where(bn > -0.5, 4, 3)))
    bank_lv = np.clip(np.where(wd <= 1, 0, np.where(wd <= 2, 1, 2)), 0, 2)
    rgb[bank] = np.array(BANK)[bank_lv[bank]]
    # 沙岸上零星的小石子
    sand_peb = bank & (wd >= 3) & (rng.random((h, w)) < 0.025)
    rgb[sand_peb] = PEBBLE['l']
    ring = dilate(bank, 1) & ground & ~bank & ~dilate(water, 1)
    rgb[ring] = GRASS[np.clip(idx[ring] - 1, 0, None)]
    # 草葉壓在沙岸外緣
    bpts = np.argwhere(ring)
    rng.shuffle(bpts)
    bank_allow = (ground & ~bank) | (bank & dilate(ring, 1))
    for (y, x) in bpts[: len(bpts) // 6]:
        pat = G.TUFTS[int(rng.integers(len(G.TUFTS)))]
        for dy, dx, ch in pat:
            yy, xx = int(y) + dy - 1, int(x) + dx - 1
            if 0 <= yy < h and 0 <= xx < w and bank_allow[yy, xx]:
                rgb[yy, xx] = GRASS[np.clip(BASE + G.rel(ch) - 1, 0, len(GRASS) - 1)]

    # ── 水 ──
    inside = dist_from(~water, 14)              # 水內離岸距離
    wrgb = M.water(h, w, rng, water, WATER, inside)
    rgb[water] = wrgb[water]
    # 上岸邊（岸在水的上方）一條陰影；橋（石頭）下方的水也有陰影
    above_land = water & ~shift(water, 1, 0, True)
    rgb[above_land] = WATER_SHADOW
    under_bridge = water & (shift(stone, 1, 0) | shift(stone, 2, 0) | shift(stone, 3, 0))
    rgb[under_bridge] = WATER_SHADOW
    # 其他岸邊一圈淺色（水拍岸）
    foam = edge_in(water) & ~above_land & ~under_bridge
    rgb[foam] = WATER['light']

    # ── 泥土路 ──
    drgb = M.dirt(h, w, rng, DIRT)
    rgb[dirt] = drgb[dirt]
    dedge = edge_in(dirt) & ~dilate(stone, 0)
    rgb[dedge & ~shift(dirt, 1, 0, True)] = DIRT_EDGE      # 上緣（草壓過來的陰影）較明顯
    rgb[dedge & (rng.random((h, w)) < 0.5)] = DIRT_EDGE
    # 泥土裡的小石子
    ov = np.zeros((h, w, 3), np.uint8)
    ovm = np.zeros((h, w), bool)
    G.add_pebbles(ov, ovm, rng, erode(dirt, 3).astype(float), int(dirt.sum() / 900), PEBBLE, allow=dirt)

    # ── 石板街 ──
    crgb, _ = M.stones(h, w, rng, COBBLE, spacing=5.5, squash=1.25)
    rgb[cobble] = crgb[cobble]
    prgb, _ = M.stones(h, w, rng, PAVER, spacing=9.0, jitter=0.55, squash=1.1)
    rgb[paver] = prgb[paver]
    # 描邊：石板街外緣一圈深色；廣場外緣是亮/暗兩條路緣石
    se = edge_in(stone)
    rgb[se & cobble] = COBBLE_EDGE
    pe1 = se & paver
    pe2 = edge_in(stone & ~se) & paver
    rgb[pe2] = PAVER_CURB[0]
    rgb[pe1] = PAVER_CURB[1]
    # 橋：石頭上下貼著水的地方畫欄杆邊（亮石 + 內側暗線）
    wv = shift(water, 1, 0) | shift(water, 2, 0) | shift(water, -1, 0) | shift(water, -2, 0)
    rail = stone & wv
    rail_in = stone & ~rail & (shift(rail, 1, 0) | shift(rail, -1, 0))
    rgb[rail] = COBBLE['hi']
    rgb[rail_in] = COBBLE['mortar']

    # ── 草葉壓在路緣（最後畫，蓋在路上）──
    edge_pts = np.argwhere(edge_in(road) & dilate(ground, 1))
    rng.shuffle(edge_pts)
    for (y, x) in edge_pts[: len(edge_pts) // 7]:
        pat = G.TUFTS[int(rng.integers(len(G.TUFTS)))]
        for dy, dx, ch in pat:
            yy, xx = int(y) + dy - 2, int(x) + dx - 1
            if 0 <= yy < h and 0 <= xx < w and (ground[yy, xx] or road_edge_band[yy, xx]):
                rgb[yy, xx] = GRASS[np.clip(BASE + G.rel(ch) - 1, 0, len(GRASS) - 1)]

    # ── 草地上的點綴 ──
    fl_dens = np.clip(0.3 + 0.6 * fnoise(h, w, 50, rng), 0, 1)
    fl_dens[shade_core | ~erode(ground, 3)] = 0
    G.add_flowers(ov, ovm, rng, fl_dens, 150, FLOWERS, allow=ground, per=(5, 13), spread=6,
                  stem=tuple(GRASS[3]))
    G.add_pebbles(ov, ovm, rng, np.where(erode(ground, 2), 0.4, 0), 140, PEBBLE, allow=ground)
    rgb[ovm] = ov[ovm]
    return rgb
