# -*- coding: utf-8 -*-
"""
把 PixelLab「Tiles → Isometric」產出的 tile group 修成標準等距地磚。

    D:/python/python.exe tools/import_floor_tiles.py <來源png> [挑選 r,c ...]

PixelLab 的 tile group 是一張 131x131 的圖＝4x4 個 32x32 的變化（中間 1px 縫），
裡面混著邊角、半塊等自動接圖用的形狀，而且菱形不是精確的 2:1（它是 28 度、約 32x20）。

這支腳本做三件事：
    1. 依 33px 間距切出指定的那幾格
    2. 用「數學上精確的 32x16 菱形」當遮罩去取樣（不縮放，像素保持銳利）
    3. 遮罩內若有破洞（來源那格邊緣不規則），用最近的不透明像素補起來

輸出 tools/art-src/shop-room/floor-N.png（32x16，正好可以無縫鋪）。
"""
import os, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'art-src', 'shop-room')

TW, TH = 32, 16          # 來源磚的目標尺寸（遊戲內會 x2 = 64x32）
CELL, GAP = 32, 1


def diamond_rows(w=TW, h=TH):
    """精確 2:1 菱形每列的 (x0, 寬)：每往下一列左右各多 2px。"""
    half = h // 2
    for y in range(h):
        d = y if y < half else h - 1 - y
        wid = 4 * (d + 1)
        yield y, (w - wid) // 2, wid


def deseam(tile):
    """
    抹掉菱形最外圈 —— PixelLab 的磚在**下緣兩條邊**畫了立體暗邊（實測比內部暗 30 階），
    鋪滿之後每塊磚下面都多一條深線、跟隔壁磚的正常亮度一比就成了明顯的格線。
    作法：外圈每個像素改用最近的內部像素顏色（材質是雜訊，看不出重複）。
    """
    a = np.array(tile).astype(np.uint8)
    solid = a[:, :, 3] > 0
    inner = ndimage.binary_erosion(solid, np.ones((3, 3)))
    if not inner.any():
        return tile
    _, idx = ndimage.distance_transform_edt(~inner, return_indices=True)
    ring = solid & ~inner
    a[ring] = a[idx[0][ring], idx[1][ring]]
    a[:, :, 3] = np.where(solid, 255, 0)
    return Image.fromarray(a)


def fit_tile(src):
    """把一格 32x32 的來源修成 32x16 的精確菱形。"""
    a = np.array(src.convert('RGBA'))
    alpha = a[:, :, 3]
    ys = np.where(alpha.any(axis=1))[0]
    if len(ys) == 0:
        return None
    top = int(round((ys[0] + ys[-1]) / 2)) - TH // 2   # 內容的垂直中心對齊菱形中心
    top = max(0, min(src.height - TH, top))

    # 破洞用最近的不透明像素補
    _, idx = ndimage.distance_transform_edt(alpha == 0, return_indices=True)
    filled = a[idx[0], idx[1]]

    out = np.zeros((TH, TW, 4), np.uint8)
    for y, x0, wid in diamond_rows():
        sy = top + y
        for x in range(x0, x0 + wid):
            out[y, x] = filled[sy, x]
    out[:, :, 3] = 0
    for y, x0, wid in diamond_rows():
        out[y, x0:x0 + wid, 3] = 255
    return Image.fromarray(out, 'RGBA')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    sheet = Image.open(sys.argv[1]).convert('RGBA')
    picks = []
    for arg in sys.argv[2:]:
        r, c = arg.split(',')
        picks.append((int(r), int(c)))
    if not picks:
        picks = [(3, 1), (3, 2), (0, 1)]

    os.makedirs(OUT, exist_ok=True)
    n = 0
    for (r, c) in picks:
        x, y = c * (CELL + GAP), r * (CELL + GAP)
        cell = sheet.crop((x, y, x + CELL, y + CELL))
        tile = fit_tile(cell)
        if tile is not None:
            tile = deseam(tile)
        if tile is None:
            print('  (%d,%d) 是空的，跳過' % (r, c))
            continue
        n += 1
        path = os.path.join(OUT, 'floor-%d.png' % n)
        tile.save(path)
        print('floor-%d.png  <- 來源格 (%d,%d)' % (n, r, c))
    print('\n輸出：', OUT)


if __name__ == '__main__':
    main()
