"""
像素草地：大塊深淺斑塊 + 成簇草葉 + 小花 + 石子 + 三葉草。三張地圖共用，色盤與密度各自給。

做法是先算一張「色階索引」圖 idx（0＝最深 … N-1＝最亮），所有明暗變化（斑塊、樹蔭、
地圖邊緣變深）都是在 idx 上加減，最後一次查色盤 —— 這樣保證只用色盤裡的顏色、
不會出現平滑漸層。草葉/三葉草也是「相對色階」圖章（比腳下亮一階/暗一階），
所以在樹蔭裡的草自動是暗的草。花、石子則是固定顏色，另外疊。
"""
import numpy as np

from common import fnoise, fractal, parse_stamp, poisson_points

# 草葉圖章：數字＝相對色階（+1 亮一階、-1 暗一階…），'.'＝不畫
TUFTS = [parse_stamp(r) for r in [
    ["2.2",
     "121",
     "-1-"],
    ["2...2",
     "1.2.1",
     ".111.",
     "..-.."],
    [".2..",
     "21.2",
     "1121",
     "-11-"],
    ["2..",
     "1.2",
     "11-"],
    ["..2",
     "2.1",
     "-11"],
    ["2.2.2",
     "1.1.1",
     "-111-"],
]]
TALL_TUFTS = [parse_stamp(r) for r in [
    ["..3..",
     "2.2.2",
     "1.1.1",
     "11111",
     "-111-"],
    ["3...3.",
     "2.3.2.",
     "1.2.12",
     "111111",
     ".----."],
    [".3..3.",
     "32.32.",
     "21.21.",
     "111111",
     "-1111-"],
]]
CLOVER = [parse_stamp(r) for r in [
    [".1.",
     "1-1"],
    ["1.1",
     ".1.",
     ".-."],
]]


def rel(ch):
    return {'1': 1, '2': 2, '3': 3, '-': -1, '=': -2}[ch]


def stamp_rel(idx, pts, y, x, allow=None, hi=None):
    h, w = idx.shape
    for dy, dx, ch in pts:
        yy, xx = y + dy, x + dx
        if 0 <= yy < h and 0 <= xx < w and (allow is None or allow[yy, xx]):
            idx[yy, xx] = idx[yy, xx] + rel(ch) if hi is None else min(hi, idx[yy, xx] + rel(ch))


def base_levels(h, w, rng, style):
    """大塊斑塊：低頻雜訊量化成幾階，邊界加一點高頻讓它不規則（但仍是乾淨的像素邊）。"""
    big = fractal(h, w, style.get('patch_sigma', 38), rng, octaves=3, gain=0.45)
    rough = fnoise(h, w, style.get('rough_sigma', 2.2), rng)
    f = big + style.get('patch_rough', 0.22) * rough
    lev = np.full((h, w), float(style['base']))
    for t, d in style['patch_steps']:          # [(閾值, 加幾階), ...]
        if t >= 0:
            lev += d * (f > t)
        else:
            lev += d * (f < t)
    return lev


def shade_to_idx(lev, dark, rng, dither=0.25):
    """lev（整數斑塊）- dark（連續的變暗量）→ 整數色階。dark 的小數部分用雜訊抖動，
    在過渡帶上形成碎碎的像素邊而不是平滑漸層。"""
    n = rng.random(lev.shape)
    return np.floor(lev - dark + 0.5 + dither * (n - 0.5)).astype(int)


def add_tufts(idx, rng, density, count, tall_frac=0.15, allow=None, hi=None):
    """hi：草葉最亮只到第幾階（邊緣那種密草叢不要亮成一片碎點）。"""
    h, w = idx.shape
    for (y, x) in poisson_points(h, w, count, rng, density):
        pats = TALL_TUFTS if rng.random() < tall_frac else TUFTS
        stamp_rel(idx, pats[int(rng.integers(len(pats)))], y, x, allow, hi)


def add_clovers(idx, rng, density, clusters, allow=None):
    h, w = idx.shape
    for (cy, cx) in poisson_points(h, w, clusters, rng, density, min_d=20):
        for _ in range(int(rng.integers(3, 8))):
            y = int(cy + rng.normal(0, 3))
            x = int(cx + rng.normal(0, 4))
            stamp_rel(idx, CLOVER[int(rng.integers(len(CLOVER)))], y, x, allow)


FLOWER_BIG = parse_stamp([".p.", "pcp", ".p."])
FLOWER_SMALL = parse_stamp(["p", "s"])
FLOWER_DUO = parse_stamp(["p.", ".p"])


def add_flowers(ov, ovm, rng, density, clusters, colors, allow=None, per=(3, 9), spread=5.0,
                stem=None, min_d=40):
    """成群的小花：先撒群心，每群幾朵、同色系為主（偶爾混一朵別的顏色）。"""
    h, w = ovm.shape
    for (cy, cx) in poisson_points(h, w, clusters, rng, density, min_d=min_d):
        main = colors[int(rng.integers(len(colors)))]
        for _ in range(int(rng.integers(*per))):
            y = int(round(cy + rng.normal(0, spread * 0.7)))
            x = int(round(cx + rng.normal(0, spread)))
            c = main if rng.random() < 0.85 else colors[int(rng.integers(len(colors)))]
            r = rng.random()
            pat = FLOWER_BIG if r < 0.55 else (FLOWER_DUO if r < 0.7 else FLOWER_SMALL)
            cmap = {'p': c['petal'], 'c': c['center'], 's': stem}
            for dy, dx, ch in pat:
                yy, xx = y + dy, x + dx
                col = cmap.get(ch)
                if col is None or not (0 <= yy < h and 0 <= xx < w):
                    continue
                if allow is not None and not allow[yy, xx]:
                    continue
                ov[yy, xx] = col
                ovm[yy, xx] = True


PEBBLES = [parse_stamp(r) for r in [
    ["hl", "dd"],
    ["l", "d"],
    [".hl", "lld", ".dd"],
    ["hl.", "lld"],
]]


def add_pebbles(ov, ovm, rng, density, count, cols, allow=None):
    h, w = ovm.shape
    for (y, x) in poisson_points(h, w, count, rng, density):
        pat = PEBBLES[int(rng.integers(len(PEBBLES)))]
        for dy, dx, ch in pat:
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and (allow is None or allow[yy, xx]):
                ov[yy, xx] = cols[ch]
                ovm[yy, xx] = True


def edge_field(h, w, width, rng, portals=()):
    """地圖邊緣的變暗量（0 在內部，往邊界升到 1）。portals：[(cy, cx, 半徑)] 這些地方不壓暗，
    讓傳送出口看起來是「開口」。"""
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.minimum(np.minimum(yy, h - 1 - yy), np.minimum(xx, w - 1 - xx)).astype(float)
    d = d + 6 * fnoise(h, w, 10, rng)          # 不要一條直線
    f = np.clip(1 - d / width, 0, 1)
    for (py, px, r) in portals:
        g = np.sqrt((yy - py) ** 2 + (xx - px) ** 2) / r
        f *= np.clip(g - 0.3, 0, 1) ** 0.7
    return f
