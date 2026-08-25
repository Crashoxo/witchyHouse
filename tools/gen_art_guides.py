# -*- coding: utf-8 -*-
"""
手繪美術用的「參考框」產生器（可重跑）。

    D:/python/python.exe tools/gen_art_guides.py

輸出到 tools/art-guide/：
    floor-tile.png        地板磚的菱形遮罩（56x28）＝你要畫的那塊磚的形狀
    <id>-guide.png        每件家具的佔地框（底部中央＝佔地前角）
    wall-guide.png        牆面貼圖的畫布框（給你看的，有標記線）
    wall-init.png         同尺寸的乾淨底圖（構圖用）
    wall-style-ref.png    給 PixelLab 當 Style Reference 的地板材質片（128x128）
    overview-wall.png     牆面貼圖的尺寸說明＋平鋪接縫檢查
    palette.png           主角＋現有房間的色票（給 PixelLab 鎖色用）
    overview-room.png     店內底圖疊上格線與格號
    overview-furniture.png 五件家具的框並排（放大 2 倍看）

⚠️ 這裡的數字是「半解析度」：遊戲裡一格是 64x32，但手繪圖一律畫 32x16，
   由 compose 腳本 x2 NEAREST 放大。理由見 tools/art-guide/README.md。
"""
import os, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from collections import Counter
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'art-guide')
ROOM_PNG = os.path.join(ROOT, 'assets', 'resources', 'rooms', 'shop-room.png')
WITCH_PNG = os.path.join(ROOT, 'assets', 'resources', 'witch8', 'base.png')

TW, TH = 32, 16          # 來源解析度的一格（遊戲內 64x32，由程式 x2 NEAREST 放大）
GW, GH = 14, 10
PAD = 3

# id -> (佔地寬, 佔地深, 建議畫布高)
PIECES = {
    'sale_table':   (2, 1, 48),
    'long_table':   (3, 1, 56),
    'round_stand':  (1, 1, 40),
    'flower_bench': (2, 1, 44),
}

NAMES = {
    'sale_table': '販售桌 2x1',
    'long_table': '長木桌 3x1',
    'round_stand': '展示台 1x1',
    'flower_bench': '花草長凳 2x1',
}


def font(size):
    for p in ('C:/Windows/Fonts/msjh.ttc', 'C:/Windows/Fonts/mingliu.ttc', 'C:/Windows/Fonts/arial.ttf'):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ---------------------------------------------------------------- 地板磚

def diamond_rows(w=TW, h=TH):
    """2:1 菱形每一列的 (x0, 寬)。每往下一列左右各多 2px＝正確的 2:1 斜率。"""
    half = h // 2
    for y in range(h):
        d = y if y < half else h - 1 - y
        wid = 4 * (d + 1)
        yield y, (w - wid) // 2, wid


def build_floor_tile():
    im = Image.new('RGBA', (TW, TH), (0, 0, 0, 0))
    px = im.load()
    for y, x0, wid in diamond_rows():
        for x in range(x0, x0 + wid):
            edge = (x < x0 + 2) or (x >= x0 + wid - 2)
            px[x, y] = (150, 128, 104, 255) if edge else (222, 206, 182, 255)
    im.save(os.path.join(OUT, 'floor-tile.png'))
    print('floor-tile.png', im.size)


# ---------------------------------------------------------------- 家具佔地框

def build_piece(pid, fw, fh, canvas_h):
    w = max(fw, fh) * TW + PAD * 2
    im = Image.new('RGBA', (w, canvas_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fx, fy = w / 2, canvas_h - 1              # 前角＝圖的正下方中央

    def p(wx, wy):
        return (fx + wx, fy - wy)

    front = (0, 0)
    right = (fh * TW / 2, fh * TH / 2)
    left = (-fw * TW / 2, fw * TH / 2)
    back = (right[0] + left[0], right[1] + left[1])
    poly = [p(*front), p(*right), p(*back), p(*left)]

    d.polygon(poly, fill=(255, 90, 160, 60))
    d.line(poly + [poly[0]], fill=(255, 60, 140, 220), width=1)
    # 內部的格線（看得出佔了幾格）
    for i in range(1, fw):
        a = (left[0] * i / fw, left[1] * i / fw)
        d.line([p(*a), p(a[0] + right[0], a[1] + right[1])], fill=(255, 60, 140, 110), width=1)
    for i in range(1, fh):
        a = (right[0] * i / fh, right[1] * i / fh)
        d.line([p(*a), p(a[0] + left[0], a[1] + left[1])], fill=(255, 60, 140, 110), width=1)
    # 前角十字標
    d.line([(fx - 4, fy), (fx + 4, fy)], fill=(40, 220, 255, 255))
    d.line([(fx, fy - 5), (fx, fy)], fill=(40, 220, 255, 255))

    im.save(os.path.join(OUT, pid + '-guide.png'))
    print(pid + '-guide.png', im.size)
    return im


# ---------------------------------------------------------------- 牆面

WALL_W, WALL_H = 96, 96      # ⚠️ WALL_H 必須跟 gen_shop_room.py 的 WALL_H2 一致


def build_wall_init():
    """
    **給 PixelLab 當 init image 用的乾淨底圖**（沒有標記線 —— wall-guide.png 上的粉紅
    會被生成器當成圖案吃進去）。只放構圖與目標色調：下方裙板、上方牆面、交界的壓條。
    """
    WAIN = 32                                  # 裙板高度（從底部算）
    plaster, cap, wains = (176, 156, 132), (150, 112, 82), (104, 66, 48)
    im = Image.new('RGBA', (WALL_W, WALL_H), plaster + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([0, WALL_H - WAIN, WALL_W - 1, WALL_H - 1], fill=wains)
    d.rectangle([0, WALL_H - WAIN - 2, WALL_W - 1, WALL_H - WAIN - 1], fill=cap)
    im.save(os.path.join(OUT, 'wall-init.png'))
    print('wall-init.png', im.size)


def build_wall_style_ref():
    """
    給 PixelLab 的 **Style Reference Image**（風格參考，不是構圖底圖）。
    ⚠️ 不要傳 wall-init.png 那種純色塊 —— 當風格參考沒有資訊。
    這裡用真的地板磚鋪一片：色盤、像素大小、明暗處理一次到位，牆才會跟地板同一個調。
    """
    src = os.path.join(ROOT, 'tools', 'art-src', 'shop-room', 'floor-1.png')
    if not os.path.exists(src):
        return
    t = Image.open(src).convert('RGBA')
    n = 128
    im = Image.new('RGBA', (n, n), (26, 21, 19, 255))
    span = n // min(t.width, t.height) + 4      # 菱形鋪法要蓋過整個方形，範圍抓寬一點
    for r in range(-span, span + 1):
        for c in range(-span, span + 1):
            x = (c - r) * (t.width // 2) - t.width // 2
            y = (c + r) * (t.height // 2) - t.height // 2
            im.alpha_composite(t, (x, y))
    im.convert('RGB').save(os.path.join(OUT, 'wall-style-ref.png'))
    print('wall-style-ref.png', im.size)


def build_wall_guide():
    """
    牆面貼圖的參考框。**畫正面平視就好** —— 等距斜切由 gen_shop_room.paste_wall() 做。
    左右邊要接得起來（接不起來也沒關係，import_wall.py 可以用 mirror/blend 幫忙）。
    """
    im = Image.new('RGBA', (WALL_W, WALL_H), (228, 214, 196, 255))
    d = ImageDraw.Draw(im)
    # 左右接縫邊
    d.rectangle([0, 0, 1, WALL_H - 1], fill=(255, 60, 140, 255))
    d.rectangle([WALL_W - 2, 0, WALL_W - 1, WALL_H - 1], fill=(255, 60, 140, 255))
    # 建議的裙板高度（不是規定，畫在圖裡由你決定）
    for x in range(0, WALL_W, 4):
        d.line([(x, 63), (x + 1, 63)], fill=(40, 220, 255, 255))
    im.save(os.path.join(OUT, 'wall-guide.png'))
    print('wall-guide.png', im.size)
    build_wall_init()
    build_wall_style_ref()

    # 說明圖：放大 4 倍 + 平鋪 3 次看接縫
    z = 4
    big = im.resize((WALL_W * z, WALL_H * z), Image.NEAREST)
    tiled = Image.new('RGBA', (WALL_W * z * 3, WALL_H * z))
    for i in range(3):
        tiled.paste(big, (i * WALL_W * z, 0))
    W = max(big.width + tiled.width + 60, 720)
    info = Image.new('RGB', (W, big.height + 96), (30, 28, 34))
    di = ImageDraw.Draw(info)
    f, fs = font(17), font(13)
    info.paste(big, (20, 56), big)
    info.paste(tiled, (40 + big.width, 56), tiled)
    di.text((20, 14), '牆面貼圖　畫布 %dx%d（遊戲內 x2）　正面平視、不要自己畫斜的'
            % (WALL_W, WALL_H), font=f, fill=(235, 230, 224))
    di.text((20, 34), '粉紅＝左右接縫邊，要接得起來　　青色虛線＝建議的裙板高度（可自行決定）',
            font=fs, fill=(180, 200, 255))
    di.text((20, big.height + 62), '單張', font=fs, fill=(200, 196, 190))
    di.text((40 + big.width, big.height + 62), '平鋪 3 次（檢查接縫）', font=fs, fill=(200, 196, 190))
    info.save(os.path.join(OUT, 'overview-wall.png'))
    print('overview-wall.png', info.size)


# ---------------------------------------------------------------- 色票

def top_colors(path, n, alpha_min=200):
    if not os.path.exists(path):
        return []
    im = Image.open(path).convert('RGBA')
    c = Counter()
    for r, g, b, a in im.getdata():
        if a >= alpha_min:
            c[(r, g, b)] += 1
    return [col for col, _ in c.most_common(n)]


def build_palette():
    rows = [('主角 witch8', top_colors(WITCH_PNG, 18)),
            ('店內底圖', top_colors(ROOM_PNG, 12))]
    sw, gap, pad = 44, 4, 12
    cols = max(len(r[1]) for r in rows) or 1
    W = pad * 2 + cols * (sw + gap)
    H = pad * 2 + len(rows) * (sw + 30)
    im = Image.new('RGB', (W, H), (28, 26, 32))
    d = ImageDraw.Draw(im)
    f = font(15)
    fs = font(11)
    y = pad
    for label, cols_ in rows:
        d.text((pad, y), label, font=f, fill=(230, 226, 220))
        y += 20
        for i, c in enumerate(cols_):
            x = pad + i * (sw + gap)
            d.rectangle([x, y, x + sw - 1, y + sw - 1], fill=c)
            d.text((x + 2, y + sw - 14), '%02X%02X%02X' % c, font=fs, fill=(0, 0, 0) if sum(c) > 380 else (255, 255, 255))
        y += sw + 10
    im.save(os.path.join(OUT, 'palette.png'))
    print('palette.png', im.size)


# ---------------------------------------------------------------- 總覽

def build_overview_room():
    if not os.path.exists(ROOM_PNG):
        return
    im = Image.open(ROOM_PNG).convert('RGBA')
    W, H = im.size
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f = font(13)
    OX, OY, FW, FH = -64, 108, 64, 32        # 遊戲內（＝來源 x2）

    def px(x, y):
        return (W / 2 + x, H / 2 - y)

    def center(c, r):
        return (OX + (c - r) * FW / 2, OY - (c + r) * FH / 2)

    doors = {(11, 9): '往城鎮', (13, 0): '往房間', (0, 9): '往花園', (5, 2): '販售桌', (6, 5): '出生點'}
    for r in range(GH):
        for c in range(GW):
            cx, cy = center(c, r)
            poly = [px(cx, cy + FH / 2), px(cx + FW / 2, cy), px(cx, cy - FH / 2), px(cx - FW / 2, cy)]
            d.line(poly + [poly[0]], fill=(255, 60, 140, 170), width=1)
            tag = doors.get((c, r))
            d.text(px(cx - 22, cy + 4), '%d,%d' % (c, r), font=f, fill=(255, 255, 255, 210))
            if tag:
                d.text(px(cx - 24, cy - 6), tag, font=f, fill=(120, 255, 200, 255))
    out = Image.alpha_composite(im, ov)
    out.convert('RGB').save(os.path.join(OUT, 'overview-room.png'))
    print('overview-room.png', out.size)


def build_overview_furniture(guides):
    f = font(16)
    fs = font(13)
    scale = 2
    pad = 24
    W = pad + sum(g.width * scale + pad for g in guides.values())
    H = pad + 30 + max(g.height for g in guides.values()) * scale + 40
    im = Image.new('RGB', (W, H), (30, 28, 34))
    d = ImageDraw.Draw(im)
    x = pad
    for pid, g in guides.items():
        big = g.resize((g.width * scale, g.height * scale), Image.NEAREST)
        y = H - 40 - big.height
        im.paste(big, (x, y), big)
        d.rectangle([x, y, x + big.width - 1, y + big.height - 1], outline=(90, 86, 96))
        d.text((x, 12), NAMES[pid], font=f, fill=(235, 230, 224))
        d.text((x, H - 32), '畫布 %dx%d px' % (g.width, g.height), font=fs, fill=(180, 200, 255))
        d.line([(x + big.width / 2, y), (x + big.width / 2, H - 40)], fill=(40, 160, 190))
        x += big.width + pad
    im.save(os.path.join(OUT, 'overview-furniture.png'))
    print('overview-furniture.png', im.size)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    build_floor_tile()
    guides = {pid: build_piece(pid, *spec) for pid, spec in PIECES.items()}
    build_wall_guide()
    build_palette()
    build_overview_room()
    build_overview_furniture(guides)
    print('\n輸出目錄：', OUT)
