"""
從原本的 town-ground.png（tools/ground/orig/ 的備份）抽出路面／河的格子地圖。

原圖是用一張 50×32 的小地圖（每格 64 世界像素）烤出來的，路面都是整格；河與橋在
半格（32 像素）上有錯位，所以這裡以 32×32 為一格判讀（100×64 格）。

每格判成：G 草地、C 石板路（冷灰、主要街道）、P 鋪石廣場（暖灰、有橫向深縫）、
D 泥土路、W 水。判法是格內每個像素先按顏色分類，再看哪一類佔多數。
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CELL = 32
CODES = 'GCPDW'


def _classify_pixels(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(-1)
    mn = a.min(-1)
    sat = (mx - mn)
    out = np.zeros(a.shape[:2], np.uint8)            # 0 草
    water = (b > r + 40) & (b > g + 10)
    green = (g > r + 15) & (g > b + 15)
    brown = (r > g + 25) & (g > b + 15)
    grey = (sat < 40) & ~water & ~green
    out[grey] = 1                                    # 石（之後再分冷暖）
    out[brown] = 3
    out[water] = 4
    out[green] = 0
    return out, grey


def grid():
    """回傳 (64, 100) 的字元陣列。"""
    a = np.asarray(Image.open(os.path.join(HERE, 'orig', 'town-ground.png')).convert('RGB')).astype(int)
    H, W = a.shape[:2]
    gh, gw = H // CELL, W // CELL
    cls, grey = _classify_pixels(a)
    warm = (a[..., 0] - a[..., 2])                   # 暖灰（廣場鋪石）R 明顯大於 B
    res = np.empty((gh, gw), dtype='<U1')
    for y in range(gh):
        for x in range(gw):
            c = cls[y * CELL:(y + 1) * CELL, x * CELL:(x + 1) * CELL]
            cnt = np.bincount(c.ravel(), minlength=5)
            k = int(cnt.argmax())
            if k == 1:
                gm = grey[y * CELL:(y + 1) * CELL, x * CELL:(x + 1) * CELL]
                wv = warm[y * CELL:(y + 1) * CELL, x * CELL:(x + 1) * CELL][gm]
                k = 2 if wv.mean() > 9 else 1
            res[y, x] = CODES[k]
    return res


if __name__ == '__main__':
    g = grid()
    for row in g:
        print(''.join(row))
