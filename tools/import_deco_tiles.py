# -*- coding: utf-8 -*-
"""把 PixelLab 出的「草地裝飾」sheet 去背成可疊在自己草地上的貼片。

    D:/python/python.exe tools/import_deco_tiles.py <sheet.png>

sheet 的背景是單一純色（PixelLab 給裝飾塊配的底色），出圖沒有 AA，
所以精確比對那個顏色就能完美去背。輸出 tools/art-src/town/deco-*.png。
"""
import sys, os, argparse
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'art-src', 'town')
T, STEP = 32, 33

# (列,欄) -> 檔名。scatter=可以隨機灑在草地上的細節；prop=有份量、之後當節點擺
PICKS = {
    (0, 2): ('deco-tuft-1', 'scatter'), (0, 3): ('deco-tuft-2', 'scatter'),
    (1, 0): ('deco-tuft-3', 'scatter'), (2, 2): ('deco-tuft-4', 'scatter'),
    (3, 2): ('deco-tuft-5', 'scatter'), (0, 1): ('deco-pebble-1', 'scatter'),
    (1, 1): ('deco-pebble-2', 'scatter'), (1, 3): ('deco-pebble-3', 'scatter'),
    (2, 0): ('deco-pebble-4', 'scatter'),
    (0, 0): ('prop-tallgrass-1', 'prop'), (3, 3): ('prop-tallgrass-2', 'prop'),
    (1, 2): ('prop-boulder', 'prop'), (2, 1): ('prop-rocks', 'prop'),
    (2, 3): ('prop-stump-1', 'prop'), (3, 1): ('prop-stump-2', 'prop'),
    (3, 0): ('prop-pond', 'prop'),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sheet')
    a = ap.parse_args()
    im = Image.open(a.sheet).convert('RGBA')
    arr = np.array(im)
    bg = Counter(map(tuple, arr[..., :3].reshape(-1, 3))).most_common(1)[0][0]
    print('背景色 %s（佔 %.0f%%）' % (str(bg), 100 * (arr[..., :3] == bg).all(-1).mean()))

    os.makedirs(OUT, exist_ok=True)
    for (r, c), (name, kind) in sorted(PICKS.items()):
        t = np.array(im.crop((c * STEP, r * STEP, c * STEP + T, r * STEP + T)))
        m = (t[..., :3] == bg).all(-1)
        t[m] = (0, 0, 0, 0)
        cover = 100 * (~m).mean()
        Image.fromarray(t).save(os.path.join(OUT, name + '.png'))
        print('  %-18s <- (%d,%d)  %-7s 覆蓋 %4.1f%%' % (name, r, c, kind, cover))


if __name__ == '__main__':
    main()
