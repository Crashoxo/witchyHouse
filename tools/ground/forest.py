"""
森林（場景 main）：整片草地，沒有路。

草地本體＝城鎮那一套（town.py 的色盤、斑塊參數、草葉、花），兩張地圖接起來是同一種草；
再加上森林感：
  - 所有樹、灌木、樹籬、藥草叢、落葉堆腳下的橢圓接地暗色（外圈暗一階、中心暗兩階，
    從城鎮草地色盤往下取，不另加色相）；
  - 果樹下零星落果、花樹下落瓣、落葉堆旁散葉；
  - 四周一圈較深、草叢較密的邊緣：寬度大幅不規則，內緣用草叢打散；東出口（y=0）與
    北出口（x=0）留開口。

花的數量是城鎮密度按面積換算再打八折（森林物件比較多）。

（歷程：第一版自己一套較暗的色盤＋兩階暗斑塊＋往出口的泥土小徑，像迷彩被退件；
  之後試過的極簡版太平。這一版是使用者選定的 D 版。）
"""
import numpy as np

import grass as G
import objects
import layouts
import town as T
from common import ART_PX, fnoise, poisson_points

SEED = 2611

GRASS, BASE, STYLE = T.GRASS, T.BASE, T.STYLE
TOWN_AREA = 1600 * 1024

APPLE = [(0xb8, 0x3a, 0x34), (0xd9, 0x5a, 0x48)]
GOLD = [(0xc9, 0x9a, 0x30), (0xf0, 0xd0, 0x6a)]
PETAL = [(0xf3, 0xc8, 0xd4), (0xfb, 0xe6, 0xec), (0xe7, 0x9a, 0xb0)]
LEAF = [(0xc4, 0x5a, 0x34), (0xd8, 0x84, 0x48), (0x9a, 0x3a, 0x2c)]


def edge_dark(h, w, rng):
    """四周一圈較深的草：寬度大幅不規則（有的地方深入、有的地方很薄），出口打開。
    回傳 (dark 連續值 0..2, 草叢密度 0..1)。"""
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.minimum(np.minimum(yy, h - 1 - yy), np.minimum(xx, w - 1 - xx)).astype(float)
    # 起伏：大尺度（深入/變薄）+ 中尺度（凹凸）。寬度約 6 ~ 60 美術像素之間變化
    width = 30 + 22 * fnoise(h, w, 45, rng) + 7 * fnoise(h, w, 9, rng)
    width = np.clip(width, 6, 70)
    t = 1 - d / width                         # 1 在地圖邊、0 在內緣
    # 出口（東側 y=0、北側 x=0）讓開
    op = np.minimum(np.hypot(yy - h / 2, (xx - w) * 0.7) / 75,
                    np.hypot(yy * 0.7, xx - w / 2) / 75)
    gate = np.clip(op - 0.35, 0, 1) ** 0.8
    t = t * gate
    dark = np.clip(t * 2.3 - 0.15, 0, 2.0)     # 內緣淡、外側兩階
    # 草叢從暗帶往內多溢出一截、越往內越稀 → 邊界是一叢一叢散開的，不是一條線
    tuft = np.clip((1 - d / (width * 1.45)) * 1.5, 0, 1) * gate
    return dark, tuft


def bake():
    rng = np.random.default_rng(SEED)
    Wd, Hd = layouts.SIZES['forest']
    w, h = Wd // ART_PX, Hd // ART_PX
    k = (w * h) / TOWN_AREA                     # 面積比，用來換算城鎮的數量參數

    lev = G.base_levels(h, w, rng, STYLE)      # ＝城鎮同一組斑塊參數
    dark = np.zeros((h, w))
    shade_core = np.zeros((h, w), bool)
    feet = objects.feet('forest')
    for f in feet:
        a = f.art
        if a.startswith('tree'):
            sap = 'sapling' in a
            rx = max(12, f.width * (0.32 if sap else 0.45))
            ry = rx * 0.42
            cy = f.cy - ry * 0.45
            outer, inner = (1.0, 1.0) if sap else (1.0, 2.0)
        elif a.startswith('bush-hedge'):
            rx, ry, cy = f.foot_w * 0.56, 6, f.cy - 2.5
            outer, inner = 1.0, 2.0
        else:                                   # 灌木、藥草叢、落葉堆
            rx = max(7, f.foot_w * 0.56)
            ry = max(3, rx * 0.34)
            cy = f.cy - ry * 0.45
            outer, inner = 1.0, 2.0
        r = objects.ellipse_local(h, w, f.cx, cy, rx, ry, pad=2)
        if r is None:
            continue
        sy, sx, e = r
        v = np.where(e > 0.45, inner, np.where(e > 0, outer, 0.0))
        dark[sy, sx] = np.maximum(dark[sy, sx], v)
        shade_core[sy, sx] |= e > 0

    edark, etuft = edge_dark(h, w, rng)
    dark = np.maximum(dark, edark)

    idx = G.shade_to_idx(lev, dark, rng).astype(int)
    # 草葉：城鎮同一套（密度場、數量按面積換算、tall_frac 0.12）
    dens = np.clip((fnoise(h, w, 14, rng) - 0.1) * 0.8, 0.02, 1)
    G.add_tufts(idx, rng, dens, int(w * h / 230), tall_frac=0.12)
    G.add_clovers(idx, rng, np.full((h, w), 0.6), int(140 * k))
    # 邊緣那圈的草叢（比內部密，最密在過渡帶，把內緣打散成一叢一叢）
    G.add_tufts(idx, rng, etuft, int(w * h / 160), tall_frac=0.45, hi=BASE + 1)
    idx = np.clip(idx, 0, len(GRASS) - 1)
    rgb = GRASS[idx]

    ov = np.zeros((h, w, 3), np.uint8)
    ovm = np.zeros((h, w), bool)
    # 花：城鎮同一組顏色與群大小，數量按面積換算再打八折（森林物件比較多）
    fl_dens = np.clip(0.3 + 0.6 * fnoise(h, w, 50, rng), 0, 1)
    fl_dens[shade_core] = 0
    fl_dens *= np.clip(1 - etuft * 2, 0, 1)
    G.add_flowers(ov, ovm, rng, fl_dens, int(150 * k * 0.8), T.FLOWERS, per=(5, 13), spread=6,
                  stem=tuple(GRASS[3]))
    G.add_pebbles(ov, ovm, rng, np.where(shade_core, 0, 0.4), int(140 * k), T.PEBBLE)

    # 落果、落瓣、散葉
    for f in feet:
        a = f.art
        if 'mature' in a or 'golden' in a or 'blossom' in a:
            cols = APPLE if 'mature' in a else GOLD if 'golden' in a else PETAL
            n = 4 if 'blossom' not in a else 12
            for _ in range(n):
                y = int(f.cy - 2 + rng.normal(0, 4))
                x = int(f.cx + rng.normal(0, f.width * 0.24))
                if 0 <= y < h - 1 and 0 <= x + 1 < w:
                    c = cols[int(rng.integers(len(cols)))]
                    ov[y, x] = c
                    ovm[y, x] = True
                    if 'blossom' not in a:     # 果子 2×2：上亮下暗
                        ov[y, x + 1] = cols[-1]
                        ov[y + 1, x] = ov[y + 1, x + 1] = cols[0]
                        ovm[y, x + 1] = ovm[y + 1, x] = ovm[y + 1, x + 1] = True
        elif a.startswith('leaf-pile'):
            for _ in range(12):
                y = int(f.cy - 1 + rng.normal(0, 3.5))
                x = int(f.cx + rng.normal(0, f.width * 0.4))
                if 0 <= y < h and 0 <= x + 1 < w:
                    c = LEAF[int(rng.integers(len(LEAF)))]
                    ov[y, x] = c
                    ovm[y, x] = True
                    if rng.random() < 0.5:
                        ov[y, x + 1] = c
                        ovm[y, x + 1] = True
    rgb[ovm] = ov[ovm]
    return rgb


def bake_tile(size=128, seed=SEED + 1):
    """原本那張 ground-grass.png 的替代品：城鎮草地風格、無縫平鋪的 128×128 美術像素草皮
    （放大成 256）。執行期 BakedGround 會把整張烤好的圖換上去；這張只是編輯器裡／
    萬一沒換成時的墊底。"""
    rng = np.random.default_rng(seed)
    h = w = size
    st = dict(STYLE, patch_sigma=14)
    lev = G.base_levels(h, w, rng, st)                  # fnoise 是週期性的 → 無縫
    idx = G.shade_to_idx(lev, np.zeros((h, w)), rng).astype(int)
    # 圖章在邊界要環繞，才能無縫：畫在 3×3 拼起來的大圖中間再切回來
    big = np.tile(idx, (3, 3))
    for (y, x) in poisson_points(h, w, int(w * h / 230), rng):
        pat = G.TUFTS[int(rng.integers(len(G.TUFTS)))]
        for oy in (0, h, 2 * h):
            for ox in (0, w, 2 * w):
                G.stamp_rel(big, pat, y + oy, x + ox)
    idx = big[h:2 * h, w:2 * w]
    return GRASS[np.clip(idx, 0, len(GRASS) - 1)]
