# -*- coding: utf-8 -*-
"""挑 PixelLab Tiles 出的地磚：切格、評接縫、鋪一片比一比、放進遊戲比例看。

    D:/python/python.exe tools/pick_tile.py <下載的sheet.png> [--name 草地]

輸出到桌面：
    <name>_16格比較.png     每格鋪 3x3 放大，附接縫分數
    <name>_遊戲比例試鋪.png  前四名鋪成 480x320 並放上主角（真實 px）
"""
import sys, os, argparse

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image, ImageDraw, ImageFont
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESKTOP = os.path.join(os.path.expanduser('~'), 'Desktop')
WITCH = os.path.join(ROOT, 'assets', 'resources', 'witch8', 'base.png')
WITCH_COLS, WITCH_ROWS, WITCH_SCALE = 8, 25, 1.6
GAME_K = 2                      # 來源 32px -> 遊戲內 64px


def font(size=14):
    for p in (r'C:\Windows\Fonts\msjh.ttc', r'C:\Windows\Fonts\msyh.ttc'):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def detect_grid(im):
    """找 1px 分隔線 -> 回傳 (格邊長, 間距, 欄數, 列數)。"""
    a = np.array(im.convert('RGBA'))
    seps = [i for i in range(a.shape[0]) if a[i, :, 3].max() == 0]
    if seps:
        step = seps[0] + 1
        t = seps[0]
    else:                                   # 沒有透明縫，猜正方等分
        for t in (32, 48, 64, 16):
            if im.width % t == 0:
                break
        step = t
    return t, step, im.width // step + (1 if im.width % step >= t else 0), \
           im.height // step + (1 if im.height % step >= t else 0)


def seam(tile):
    a = np.array(tile.convert('RGB')).astype(float)
    ih = np.abs(a[:, 1:] - a[:, :-1]).mean()
    iv = np.abs(a[1:] - a[:-1]).mean()
    wh = np.abs(a[:, 0] - a[:, -1]).mean()
    wv = np.abs(a[0] - a[-1]).mean()
    return wh / max(ih, 1e-6), wv / max(iv, 1e-6)


def banding(tile, n=6):
    """鋪 n x n 後看有沒有週期性明暗帶（格紋）。回傳 (欄std, 列std)。"""
    T = tile.width
    big = Image.new('RGBA', (T * n, T * n))
    for y in range(n):
        for x in range(n):
            big.paste(tile, (x * T, y * T))
    a = np.array(big.convert('RGB')).astype(float).mean(axis=2)
    return a.mean(axis=0).std(), a.mean(axis=1).std()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sheet')
    ap.add_argument('--name', default='地磚')
    args = ap.parse_args()

    im = Image.open(args.sheet).convert('RGBA')
    T, STEP, COLS, ROWS = detect_grid(im)
    print('sheet %dx%d  ->  %dx%d 格，每格 %dpx，間距 %dpx' % (im.size + (COLS, ROWS, T, STEP)))

    cells = []
    for r in range(ROWS):
        for c in range(COLS):
            x, y = c * STEP, r * STEP
            if x + T > im.width or y + T > im.height:
                continue
            t = im.crop((x, y, x + T, y + T))
            sh, sv = seam(t)
            bh, bv = banding(t)
            a = np.array(t.convert('RGB')).astype(float)
            ncol = len(np.unique(a.reshape(-1, 3), axis=0))
            cells.append(dict(r=r, c=c, tile=t, seam=(sh + sv) / 2,
                              band=max(bh, bv), colors=ncol,
                              bright=a.mean(), contrast=a.std()))

    # 排序：接縫要小、格紋要小、顏色多一點比較有質感
    for d in cells:
        d['score'] = d['seam'] * 3 + d['band'] * 1.5 - min(d['colors'], 12) * 0.25
    ranked = sorted(cells, key=lambda d: d['score'])

    print('\n格      接縫   格紋   色數  亮度  對比   分數（越小越好）')
    for d in ranked:
        print('(%d,%d)  %6.2f %6.2f %5d %5.1f %5.1f  %6.2f'
              % (d['r'], d['c'], d['seam'], d['band'], d['colors'],
                 d['bright'], d['contrast'], d['score']))

    f = font(14)
    # --- 對照圖：每格鋪 3x3 ---
    N, K, pad, lab = 3, 2, 14, 20
    cw = T * N * K
    W = COLS * (cw + pad) + pad
    H = ROWS * (cw + pad + lab) + pad
    sheet = Image.new('RGB', (W, H), (26, 26, 30))
    dr = ImageDraw.Draw(sheet)
    for d in cells:
        big = Image.new('RGBA', (T * N, T * N))
        for y in range(N):
            for x in range(N):
                big.paste(d['tile'], (x * T, y * T))
        big = big.resize((cw, cw), Image.NEAREST)
        x0 = pad + d['c'] * (cw + pad)
        y0 = pad + d['r'] * (cw + pad + lab)
        sheet.paste(big.convert('RGB'), (x0, y0))
        rank = ranked.index(d) + 1
        col = (255, 210, 120) if rank <= 4 else (200, 200, 200)
        dr.text((x0, y0 + cw + 3),
                '(%d,%d) #%d 縫%.2f 紋%.2f %d色' % (d['r'], d['c'], rank, d['seam'], d['band'], d['colors']),
                fill=col, font=f)
    p1 = os.path.join(DESKTOP, '%s_16格比較.png' % args.name)
    sheet.save(p1)

    # --- 遊戲比例試鋪 ---
    w8 = Image.open(WITCH).convert('RGBA')
    cw8, ch8 = w8.width // WITCH_COLS, w8.height // WITCH_ROWS
    witch = w8.crop((0, 0, cw8, ch8)).resize(
        (int(cw8 * WITCH_SCALE), int(ch8 * WITCH_SCALE)), Image.NEAREST)
    PW, PH = 480, 320
    top = ranked[:4]
    W2 = 2 * PW + 3 * pad
    H2 = 2 * (PH + lab) + 3 * pad
    sh2 = Image.new('RGB', (W2, H2), (24, 24, 28))
    dr2 = ImageDraw.Draw(sh2)
    for i, d in enumerate(top):
        t = d['tile'].resize((T * GAME_K, T * GAME_K), Image.NEAREST)
        p = Image.new('RGBA', (PW, PH))
        for y in range(0, PH, t.height):
            for x in range(0, PW, t.width):
                p.paste(t, (x, y))
        p.alpha_composite(witch, (PW // 2 - witch.width // 2, PH // 2 - witch.height // 2))
        gx, gy = i % 2, i // 2
        x0 = pad + gx * (PW + pad)
        y0 = pad + gy * (PH + lab + pad)
        sh2.paste(p.convert('RGB'), (x0, y0))
        dr2.rectangle([x0 - 1, y0 - 1, x0 + PW, y0 + PH], outline=(90, 90, 100))
        dr2.text((x0, y0 + PH + 3), '#%d  (%d,%d)   %d 色   亮度 %.0f'
                 % (i + 1, d['r'], d['c'], d['colors'], d['bright']), fill=(230, 230, 230), font=f)
    p2 = os.path.join(DESKTOP, '%s_遊戲比例試鋪.png' % args.name)
    sh2.save(p2)
    print('\n%s\n%s' % (p1, p2))


if __name__ == '__main__':
    main()
