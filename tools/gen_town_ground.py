# -*- coding: utf-8 -*-
"""照 town-map.png 把城鎮地面鋪出來。

    D:/python/python.exe tools/gen_town_ground.py            # 只出預覽
    D:/python/python.exe tools/gen_town_ground.py --apply    # 覆蓋 assets/art/town-ground.png

輸入：
    tools/art-guide/town-map.png   50x32，一個像素 = 一格 64x64（使用者自己塗）
    tools/art-src/town/*.png       PixelLab 出的 32x32 地磚（程式 x2 放大）

沒有磚的地形先用純色頂著，之後補上磚再重跑即可。
"""
import sys, os, argparse, random

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image
import numpy as np

try:
    from scipy import ndimage
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, 'tools', 'art-guide', 'town-map.png')
SRC = os.path.join(ROOT, 'tools', 'art-src', 'town')
GUIDE = os.path.join(ROOT, 'tools', 'art-guide')
DESKTOP = os.path.join(os.path.expanduser('~'), 'Desktop')

TILE_SRC = 32          # 美術畫的大小
K = 2                  # 放大倍率 -> 遊戲內 64
TILE = TILE_SRC * K
SEED = 20260826

# 地形：調色盤顏色 -> (磚檔名與權重, 沒磚時的純色)
# 草地權重＝密度選項 C 茂密
TERRAIN = {
    'grass':  dict(rgb=(94, 155, 73),
                   tiles=[('grass-base', 20), ('grass-var1', 30),
                          ('grass-var2', 35), ('grass-accent', 15)],
                   flat=(94, 155, 73)),
    'dirt':   dict(rgb=(150, 111, 68),
                   tiles=[('dirt-1', 72), ('dirt-2', 12), ('dirt-3', 12), ('dirt-4', 4)],
                   flat=(150, 111, 68)),
    'cobble': dict(rgb=(150, 150, 158),
                   tiles=[('cobble-1', 70), ('cobble-2', 30)], flat=(150, 150, 158)),
    'paver':  dict(rgb=(176, 124, 104),
                   tiles=[('paver-1', 1)], flat=(176, 124, 104)),
    'water':  dict(rgb=(60, 120, 190), tiles=[('water-1', 55), ('water-2', 30), ('water-3', 15)], flat=(60, 120, 190)),
}
# 疊的順序：草地當底，其餘依序蓋上去
LAYERS = ['dirt', 'paver', 'cobble', 'water']
DECO_RATE = 0.20       # 幾成的草地格子上灑小草點/碎石（deco-tuft / deco-pebble）
FLOWER_RATE = 0.05     # 幾成的草地格子上灑野花叢（deco-flower，每片較大較搶眼）
EDGE_AMP = 9           # 交界處被雜訊推開幾 px（0 = 硬邊）
FRINGE = 8             # 石板/磚道外圍鑲多寬的土邊（px，0 = 不鑲）


def load_tiles(name):
    """回傳 [(Image, 權重)]，找不到檔案回 []。"""
    out = []
    for fn, w in TERRAIN[name]['tiles']:
        p = os.path.join(SRC, fn + '.png')
        if os.path.exists(p):
            t = Image.open(p).convert('RGBA')
            if t.size != (TILE_SRC, TILE_SRC):
                t = t.resize((TILE_SRC, TILE_SRC), Image.NEAREST)
            out.append((t.resize((TILE, TILE), Image.NEAREST), w))
    return out


def tile_fill(size, tiles, rng):
    """整片平鋪某一組磚（土邊那層要整張都有料，才切得出任意形狀）。"""
    out = Image.new('RGBA', size)
    pool = []
    for t, w in tiles:
        pool += [t] * w
    for y in range(0, size[1], TILE):
        for x in range(0, size[0], TILE):
            t = rng.choice(pool)
            if rng.random() < 0.5:
                t = t.transpose(Image.FLIP_LEFT_RIGHT)
            if rng.random() < 0.5:
                t = t.transpose(Image.FLIP_TOP_BOTTOM)
            out.paste(t, (x, y))
    return out


def read_map():
    im = Image.open(MAP).convert('RGB')
    a = np.array(im)
    cols, rows = im.size
    lookup = {v['rgb']: k for k, v in TERRAIN.items()}
    grid = [[None] * cols for _ in range(rows)]
    unknown = {}
    for r in range(rows):
        for c in range(cols):
            rgb = tuple(int(x) for x in a[r, c])
            k = lookup.get(rgb)
            if k is None:
                unknown[rgb] = unknown.get(rgb, 0) + 1
                k = 'grass'
            grid[r][c] = k
    return grid, cols, rows, unknown


def paint(grid, cols, rows, name, tiles, flat, rng):
    """把某一種地形鋪成一整張圖 + 它的遮罩。"""
    W, H = cols * TILE, rows * TILE
    layer = Image.new('RGBA', (W, H), flat + (255,))
    mask = np.zeros((H, W), dtype=bool)
    if tiles:
        pool = []
        for t, w in tiles:
            pool += [t] * w
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != name:
                continue
            mask[r * TILE:(r + 1) * TILE, c * TILE:(c + 1) * TILE] = True
            if tiles:
                t = rng.choice(pool)
                if rng.random() < 0.5:
                    t = t.transpose(Image.FLIP_LEFT_RIGHT)
                if rng.random() < 0.5:
                    t = t.transpose(Image.FLIP_TOP_BOTTOM)
                layer.paste(t, (c * TILE, r * TILE))
    return layer, mask


def noise_field(W, H, cell, seed):
    """低解析度亂數 -> 雙三次放大 ＝ 連續的有機雜訊（不是逐像素雜點）。"""
    rng = np.random.default_rng(seed)
    small = rng.random((H // cell + 2, W // cell + 2))
    img = Image.fromarray((small * 255).astype(np.uint8), 'L').resize((W, H), Image.BICUBIC)
    return np.asarray(img, dtype=float) / 255.0


def warp_mask(mask, amp=EDGE_AMP, seed=SEED):
    """把方方正正的格子遮罩，用雜訊把邊界推來推去，變成有機的不規則邊。

    作法：算「有號距離場」（遮罩內為正、外為負），加上兩個尺度的雜訊再重新取門檻。
    ⚠️ 不是逐像素隨機丟棄（那會變成一圈雜點），而是整條邊界連續地擺動。
    """
    if not HAS_SCIPY or amp <= 0:
        return mask.astype(float)
    H, W = mask.shape
    inside = ndimage.distance_transform_edt(mask)
    outside = ndimage.distance_transform_edt(~mask)
    sdf = inside - outside
    n = (noise_field(W, H, 40, seed) - 0.5) * 2.0            # 大起伏：整段路的走向
    n += (noise_field(W, H, 11, seed + 1) - 0.5) * 0.9       # 小起伏：邊緣的碎屑感
    return (sdf + n * amp > 0).astype(float)


def scatter(layer, mask, tiles, rng, count, k=1):
    """在遮罩內隨機蓋幾塊點綴磚（破損地面、雜草石板之類）。"""
    if not tiles:
        return
    ys, xs = np.nonzero(mask[::TILE, ::TILE])
    if not len(ys):
        return
    pool = []
    for t, w in tiles:
        pool += [t] * w
    for _ in range(min(count, len(ys))):
        i = rng.randrange(len(ys))
        t = rng.choice(pool)
        if rng.random() < 0.5:
            t = t.transpose(Image.FLIP_LEFT_RIGHT)
        layer.paste(t, (int(xs[i]) * TILE, int(ys[i]) * TILE), t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='覆蓋 assets/art/town-ground.png')
    ap.add_argument('--no-dither', action='store_true')
    args = ap.parse_args()

    grid, cols, rows, unknown = read_map()
    W, H = cols * TILE, rows * TILE
    print('地圖 %dx%d 格  ->  %dx%d px' % (cols, rows, W, H))
    if unknown:
        print('⚠️ 有不在調色盤裡的顏色（已當成草地）：')
        for rgb, n in sorted(unknown.items(), key=lambda kv: -kv[1])[:6]:
            print('   %s  %d 格' % (str(rgb), n))

    counts = {}
    for r in range(rows):
        for c in range(cols):
            counts[grid[r][c]] = counts.get(grid[r][c], 0) + 1

    rng = random.Random(SEED)
    tiles = {k: load_tiles(k) for k in TERRAIN}
    for k in TERRAIN:
        have = '%d 種磚' % len(tiles[k]) if tiles[k] else '⚠️ 沒有磚，用純色'
        print('   %-7s %4d 格  %s' % (k, counts.get(k, 0), have))

    out, _ = paint(grid, cols, rows, 'grass', tiles['grass'], TERRAIN['grass']['flat'], rng)
    # 草地上灑小草叢／碎石（deco-*.png，已去背，直接疊上去）
    deco, flowers = [], []
    for fn in sorted(os.listdir(SRC)):
        if fn.startswith('deco-') and fn.endswith('.png'):
            d = Image.open(os.path.join(SRC, fn)).convert('RGBA')
            # 32px 的貼片放大 x2（跟地磚同尺度）；本來就畫得比較大的（野花 ~49px）用原尺寸
            k = 2 if d.width <= 32 else 1
            (flowers if fn.startswith('deco-flower') else deco).append(
                d.resize((d.width * k, d.height * k), Image.NEAREST))
    if deco or flowers:
        n = 0
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] != 'grass':
                    continue
                roll = rng.random()
                if roll < FLOWER_RATE and flowers:
                    t = rng.choice(flowers)
                elif roll < FLOWER_RATE + DECO_RATE and deco:
                    t = rng.choice(deco)
                else:
                    continue
                if rng.random() < 0.5:
                    t = t.transpose(Image.FLIP_LEFT_RIGHT)
                if rng.random() < 0.5:
                    t = t.transpose(Image.FLIP_TOP_BOTTOM)
                ox = c * TILE + (TILE - t.width) // 2
                oy = r * TILE + (TILE - t.height) // 2
                out.alpha_composite(t, (max(0, ox), max(0, oy)))
                n += 1
        print('   草地裝飾：小點 %d 種／野花 %d 種，共灑 %d 格' % (len(deco), len(flowers), n))
    dirt_layer, _ = paint(grid, cols, rows, 'dirt', tiles['dirt'], TERRAIN['dirt']['flat'], rng)
    dirt_layer = Image.new('RGBA', out.size, TERRAIN['dirt']['flat'] + (255,))         if not tiles['dirt'] else tile_fill(out.size, tiles['dirt'], rng)

    for name in LAYERS:
        if not counts.get(name):
            continue
        layer, mask = paint(grid, cols, rows, name, tiles[name], TERRAIN[name]['flat'], rng)
        warped = mask.astype(float) if args.no_dither else warp_mask(mask, seed=SEED + LAYERS.index(name))
        # 石板/磚道先鑲一圈土邊，再蓋路面 —— 硬邊被土帶吃掉，就不會是一條死線
        if FRINGE and name in ('cobble', 'paver') and not args.no_dither:
            # ⚠️ 土邊的外緣要「自己再擾動一次」，不然等寬的一圈看起來像描邊而不是踩出來的土
            grown = ndimage.binary_dilation(warped > 0.5, iterations=FRINGE)
            grown = warp_mask(grown, amp=FRINGE * 0.9, seed=SEED + 700 + LAYERS.index(name))
            out = Image.composite(dirt_layer, out,
                                  Image.fromarray((grown * 255).astype(np.uint8), 'L'))
        alpha = Image.fromarray((warped * 255).astype(np.uint8), 'L')
        out = Image.composite(layer, out, alpha)

    out = out.convert('RGB')
    prev = os.path.join(GUIDE, 'town-ground-preview.png')
    out.save(prev)
    out.resize((W // 3, H // 3), Image.NEAREST).save(
        os.path.join(DESKTOP, '城鎮地面_全圖預覽.png'))
    # 960x640 相機視角：玩家出生點附近（西門）
    cx, cy = W // 2 - 1500, H // 2 + 40
    box = (max(0, cx - 480), max(0, cy - 320), max(960, cx + 480), max(640, cy + 320))
    out.crop(box).save(os.path.join(DESKTOP, '城鎮地面_實際視角.png'))
    print('\n預覽：%s' % prev)
    print('桌面：城鎮地面_全圖預覽.png（1/3 縮圖）、城鎮地面_實際視角.png（960x640）')

    if args.apply:
        dst = os.path.join(ROOT, 'assets', 'art', 'town-ground.png')
        out.save(dst)
        print('\n已覆蓋 %s' % dst)
        print('⚠️ town-ground.png.meta 是手工 meta —— 尺寸若有變，'
              'width/height/rawWidth/rawHeight 與 vertices 都要同步改。')


if __name__ == '__main__':
    main()
