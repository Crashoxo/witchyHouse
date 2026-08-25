# -*- coding: utf-8 -*-
"""
把 PixelLab 出的「正面平視牆面」修成可以斜切上牆的貼圖。

    D:/python/python.exe tools/import_wall.py <來源png> [選項]

PixelLab 的 **Objects** 一次出 16 張（4x4 grid、正方形），所以流程是兩步：

    1. D:/python/python.exe tools/import_wall.py <sheet.png> --sheet
       → 切格、編號，輸出 tools/art-guide/wall-cells.png 給你挑
    2. D:/python/python.exe tools/import_wall.py <sheet.png> --cell 1,2
       → 拿那一格做成 wall-panel.png

選項：
    --sheet          只切格編號、輸出挑選用的接觸表（不產出 wall-panel）
    --cell r,c       從 4x4 grid 挑一格
    --crop x,y,w,h   先裁一塊（來源有多餘的畫面時用）
    --seam mirror    左右接縫處理：mirror（預設）＝再接一張左右翻轉的，接縫必定完美
    --seam blend[:N] 把左邊 N px 交叉淡入右邊（預設 N=8）＝不會有對稱感，但花紋要夠雜
    --seam none      原圖直接用（只有本來就無縫才選這個）
    --shade s        整體亮度相乘（例如 0.9 壓暗）

輸出：
    tools/art-src/shop-room/wall-panel.png    高度固定 WALL_H2，gen_shop_room.py 會自動撿去用
    tools/art-guide/wall-preview.png          鋪 4 次的接縫檢查圖（看左右接得起來沒）

⚠️ 牆是斜的但**來源要畫正面平視的**，斜切由 gen_shop_room.paste_wall() 做
   （等距斜率剛好 2:1 ＝ 逐欄整數位移，乾淨的像素階梯；用 affine 變形會插值糊掉）。
⚠️ 高度會被 NEAREST 縮到 WALL_H2。畫的時候直接照 WALL_H2 最保險，
   不然非整數倍縮放會讓像素大小不均勻。
"""
import os, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'art-src', 'shop-room')
GUIDE = os.path.join(ROOT, 'tools', 'art-guide')

WALL_H = 96          # ⚠️ 必須跟 gen_shop_room.py 的 WALL_H2 一致


def parse_args(argv):
    src, opts = None, {'seam': 'mirror', 'crop': None, 'shade': 1.0,
                       'sheet': False, 'cell': None}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--sheet':
            opts['sheet'] = True
        elif a == '--cell':
            i += 1
            r, c = argv[i].split(',')
            opts['cell'] = (int(r), int(c))
        elif a == '--crop':
            i += 1
            opts['crop'] = tuple(int(v) for v in argv[i].split(','))
        elif a == '--seam':
            i += 1
            opts['seam'] = argv[i]
        elif a == '--shade':
            i += 1
            opts['shade'] = float(argv[i])
        elif src is None:
            src = a
        i += 1
    return src, opts


def grid_geometry(im, n=4):
    """
    推算 4x4 grid 的格子大小與間隔。PixelLab 的圖有時每格中間夾 1px 縫、有時沒有。
    回傳 (cell_w, cell_h, gap)。
    """
    for gap in (1, 0, 2):
        if (im.width - (n - 1) * gap) % n == 0 and (im.height - (n - 1) * gap) % n == 0:
            return ((im.width - (n - 1) * gap) // n,
                    (im.height - (n - 1) * gap) // n, gap)
    return im.width // n, im.height // n, 0


def cut_cell(im, r, c, n=4):
    cw, ch, gap = grid_geometry(im, n)
    x, y = c * (cw + gap), r * (ch + gap)
    return im.crop((x, y, x + cw, y + ch))


def trim_alpha(im):
    """
    去掉四周的透明邊。
    ⚠️ Objects 出的是「物件」＝主體浮在透明背景中間，直接拿去平鋪會有透明縫。
    """
    a = np.array(im)
    if a.shape[2] < 4 or (a[:, :, 3] > 8).all():
        return im
    solid = a[:, :, 3] > 8
    if not solid.any():
        return im
    ys, xs = np.where(solid)
    return im.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))


def contact_sheet(im, n=4, zoom=3):
    """把 16 格切開、編號，讓使用者挑哪一格當牆。"""
    from PIL import ImageDraw, ImageFont
    cw, ch, gap = grid_geometry(im, n)
    f = ImageFont.load_default()
    pad, lbl = 10, 12
    W = n * (cw * zoom + pad) + pad
    H = n * (ch * zoom + pad + lbl) + pad
    out = Image.new('RGB', (W, H), (18, 18, 22))
    d = ImageDraw.Draw(out)
    for r in range(n):
        for c in range(n):
            cell = trim_alpha(cut_cell(im, r, c, n))
            big = cell.resize((cell.width * zoom, cell.height * zoom), Image.NEAREST)
            x = pad + c * (cw * zoom + pad)
            y = pad + r * (ch * zoom + pad + lbl)
            out.paste(Image.new('RGB', (cw * zoom, ch * zoom), (44, 44, 50)), (x, y))
            out.paste(big, (x, y), big)
            d.rectangle([x, y, x + cw * zoom - 1, y + ch * zoom - 1], outline=(90, 90, 100))
            d.text((x, y + ch * zoom + 1), '%d,%d  %dx%d' % (r, c, cell.width, cell.height),
                   fill=(232, 224, 208), font=f)
    return out


def fit_height(im, h):
    """NEAREST 縮到指定高度（等比）。已經是那個高度就不動。"""
    if im.height == h:
        return im
    k = h / float(im.height)
    if abs(k - round(k)) > 0.02:
        print('   [注意] 高度 %d -> %d 是 %.2f 倍，非整數倍縮放會讓像素大小不均勻。'
              % (im.height, h, k))
        print('          下次在 PixelLab 直接把 Size 拉到 %d 就不用縮。' % h)
    w = max(1, int(round(im.width * k)))
    return im.resize((w, h), Image.NEAREST)


def seam_mirror(im):
    """接一張左右翻轉的 → 週期變兩倍，接縫必定完美（代價：看得出對稱）。"""
    out = Image.new('RGBA', (im.width * 2, im.height))
    out.paste(im, (0, 0))
    out.paste(im.transpose(Image.FLIP_LEFT_RIGHT), (im.width, 0))
    return out


def seam_blend(im, n=8):
    """
    環繞交叉淡化：丟掉最右邊 n 欄、把它們淡入最左邊 n 欄。
    輸出寬度 W-n，左右接得起來且沒有 mirror 的對稱感（前提：花紋夠雜）。
    """
    a = np.array(im).astype(float)
    h, w = a.shape[0], a.shape[1]
    n = min(n, w // 3)
    if n < 2:
        return im
    m = w - n                                   # 輸出寬度
    out = a[:, :m].copy()
    tail = a[:, m:]                             # 被丟掉的那 n 欄
    t = (np.arange(n) / float(n - 1)).reshape(1, n, 1)   # 0→1
    # 平鋪後 out[0] 接在 out[m-1] 之後，而原圖裡接在 img[m-1] 之後的就是 tail[0]
    out[:, :n] = tail * (1 - t) + a[:, :n] * t
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def tile_preview(im, times=4):
    prev = Image.new('RGBA', (im.width * times, im.height))
    for i in range(times):
        prev.paste(im, (i * im.width, 0))
    return prev.resize((prev.width * 2, prev.height * 2), Image.NEAREST)


def main():
    src, opts = parse_args(sys.argv[1:])
    if not src:
        print(__doc__)
        return
    im = Image.open(src).convert('RGBA')
    print('來源', im.size)

    if opts['sheet']:
        cw, ch, gap = grid_geometry(im)
        os.makedirs(GUIDE, exist_ok=True)
        dst = os.path.join(GUIDE, 'wall-cells.png')
        contact_sheet(im).save(dst)
        print('4x4 grid：每格 %dx%d、間隔 %dpx' % (cw, ch, gap))
        print('挑選圖 ->', dst)
        print('挑好之後：D:/python/python.exe tools/import_wall.py %s --cell r,c' % src)
        return

    if opts['cell']:
        im = cut_cell(im, *opts['cell'])
        print('取格 %d,%d ->' % opts['cell'], im.size)

    if opts['crop']:
        x, y, w, h = opts['crop']
        im = im.crop((x, y, x + w, y + h))
        print('裁切 ->', im.size)

    im = trim_alpha(im)
    print('去透明邊 ->', im.size)

    # 來源比牆高 → 直接裁，不要縮（1:1 像素最乾淨）。
    # ⚠️ 裁**底部**：裙板／踢腳板一定要留在最下面，裁上面等於把牆腳切掉。
    if im.height > WALL_H:
        im = im.crop((0, im.height - WALL_H, im.width, im.height))
        print('裁下緣 %d 列 ->' % WALL_H, im.size, '（保留裙板，不縮放）')
    else:
        im = fit_height(im, WALL_H)
        print('校高度 ->', im.size)

    seam = opts['seam']
    if seam.startswith('blend'):
        n = int(seam.split(':')[1]) if ':' in seam else 8
        im = seam_blend(im, n)
        print('接縫 blend %d ->' % n, im.size)
    elif seam == 'mirror':
        im = seam_mirror(im)
        print('接縫 mirror ->', im.size)
    else:
        print('接縫 none（原圖直接用）')

    if opts['shade'] != 1.0:
        a = np.array(im).astype(float)
        a[:, :, :3] = np.clip(a[:, :, :3] * opts['shade'], 0, 255)
        im = Image.fromarray(a.astype(np.uint8))
        print('壓暗 x%.2f' % opts['shade'])

    # 牆面必須不透明（透明處會露出相機底色）
    a = np.array(im)
    if (a[:, :, 3] < 250).any():
        print('⚠️ 有半透明像素，已補成不透明')
        a[:, :, 3] = 255
        im = Image.fromarray(a)

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(GUIDE, exist_ok=True)
    dst = os.path.join(OUT, 'wall-panel.png')
    im.save(dst)
    tile_preview(im).save(os.path.join(GUIDE, 'wall-preview.png'))
    print('\nwall-panel.png ->', dst, im.size)
    print('接縫檢查圖 ->', os.path.join(GUIDE, 'wall-preview.png'))
    print('接著跑：D:/python/python.exe tools/gen_shop_room.py')


if __name__ == '__main__':
    main()
