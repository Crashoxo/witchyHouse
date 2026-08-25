# -*- coding: utf-8 -*-
"""
把 PixelLab **Objects** 出的牆面素材，組成可以無縫平鋪的 wall-panel.png。

    D:/python/python.exe tools/compose_wall.py

輸出：
    tools/art-src/shop-room/wall-panel.png    gen_shop_room.py 會自動撿去用
    tools/art-guide/wall-preview.png          平鋪 6 次的接縫檢查圖

--------------------------------------------------------------------------
為什麼需要這支（不是直接用 import_wall.py）
--------------------------------------------------------------------------
⚠️ **Objects 出的是「物件」不是「材質」** —— 主體浮在透明背景中間，而且 2026-08-18
   這批四張的結果是：

     faded_floral  玫瑰圖案實心、**壁紙底色是透明的**；下方裙板實心    ← 壁紙來源
     dark_blue     壁紙整片沒生出來（全透明），但**裙板是最乾淨的一條**  ← 裙板來源
     aged_cream    裙板可用；灰泥是破破爛爛的一坨                      （備料）
     deep_green    只有三個空框                                        （失敗）

   所以不能整張拿來用，要**拆成「壁紙」與「裙板」兩段各自取用、再疊起來**，
   壁紙的透明底色由我們自己指定（GROUND）。

⚠️ 量出來的關鍵數字（autocorrelation + alpha 覆蓋率，見 measure()）：
     裙板在 y=80..127（高 48），三張位置一致
     水平重複週期 = **32**（128 剛好 4 個嵌板），壁紙也是 32
   週期 32 表示 **32 寬的一片就能完美無縫平鋪** —— 不需要 mirror/blend。

⚠️ 全程 1:1 不縮放。牆高 96 ＝ 壁紙 48 + 裙板 48。
"""
import os, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'tools', 'art-src', 'shop-room', 'wall-src')
OUT = os.path.join(ROOT, 'tools', 'art-src', 'shop-room')
GUIDE = os.path.join(ROOT, 'tools', 'art-guide')

PAPER_SRC = 'faded_floral_wallpaper_above_d'    # 取上半的玫瑰圖案
WAINS_SRC = 'dark_blue_wallpaper_with_tiny'     # 取下半的裙板（這張的最乾淨）

WALL_H = 96          # ⚠️ 必須跟 gen_shop_room.py 的 WALL_H2 一致
XOFF = 0             # 從來源的哪一欄開始取（週期是 32，所以任何位置都接得起來）

# 壁紙底色。玫瑰是實心的、底色透明 → 這個顏色就是整片牆的主色。
# 使用者 2026-08-18 選的「灰藍」：跟暖色深紅棕地板分得開，房間有層次，玫瑰也最跳。
GROUND = (92, 100, 112)


def load(name):
    p = os.path.join(SRC, name + '.png')
    if not os.path.exists(p):
        raise SystemExit('找不到來源：%s\n（PixelLab Objects 下載後放到 %s）' % (p, SRC))
    return np.array(Image.open(p).convert('RGBA'))


def wainscot_top(a):
    """從底部往上找「整列都不透明」的連續區段 ＝ 裙板。"""
    cov = (a[:, :, 3] > 8).mean(axis=1)
    top = a.shape[0]
    for y in range(a.shape[0] - 1, -1, -1):
        if cov[y] > 0.97:
            top = y
        else:
            break
    return top


def period(block, lo=8, hi=80):
    """水平重複週期（自相關取最大）。"""
    if block.size == 0 or block.shape[0] == 0:
        return 0                      # 那張沒有裙板（生失敗的圖），不用算
    m = block.astype(float)
    m = m - m.mean(axis=(0, 1))
    w = m.shape[1]
    best, bp = -1e18, w
    for p in range(lo, min(hi, w)):
        s = (m[:, :w - p] * m[:, p:]).mean()
        if s > best:
            best, bp = s, p
    return bp


def measure():
    for n in sorted(os.listdir(SRC)):
        if not n.endswith('.png'):
            continue
        a = load(n[:-4])
        top = wainscot_top(a)
        al = a[:, :, 3] > 8
        print('  %-32s 裙板 y=%d..%d(高%d)  上半覆蓋 %2.0f%%  裙板週期 %d'
              % (n[:-4], top, a.shape[0] - 1, a.shape[0] - top,
                 100 * al[:top].mean() if top else 0,
                 period(a[top:, :, :3])))


def build():
    paper_src, wains_src = load(PAPER_SRC), load(WAINS_SRC)
    ptop, wtop = wainscot_top(paper_src), wainscot_top(wains_src)
    wain_h = wains_src.shape[0] - wtop
    paper_h = WALL_H - wain_h
    if paper_h <= 0:
        raise SystemExit('裙板高 %d 已經超過牆高 %d' % (wain_h, WALL_H))

    per = period(paper_src[ptop - paper_h:ptop, :, 3:4])
    print('壁紙週期 %d、裙板高 %d、壁紙高 %d' % (per, wain_h, paper_h))

    # 壁紙：取裙板正上方那 paper_h 列（保住圖案與裙板壓條的垂直關係）
    paper = paper_src[ptop - paper_h:ptop, XOFF:XOFF + per].astype(float)
    wains = wains_src[wtop:, XOFF:XOFF + per].astype(float)

    out = np.zeros((WALL_H, per, 4), float)
    a = paper[:, :, 3:4] / 255.0                      # 玫瑰實心、底色透明
    out[:paper_h, :, :3] = paper[:, :, :3] * a + np.array(GROUND, float) * (1 - a)
    out[paper_h:, :, :3] = wains[:, :, :3]
    out[:, :, 3] = 255                                # 牆一定要不透明
    im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

    im.save(os.path.join(OUT, 'wall-panel.png'))
    print('wall-panel.png ->', im.size)

    os.makedirs(GUIDE, exist_ok=True)
    prev = Image.new('RGB', (im.width * 6, im.height))
    for i in range(6):
        prev.paste(im, (i * im.width, 0))
    prev.resize((prev.width * 3, prev.height * 3), Image.NEAREST).save(
        os.path.join(GUIDE, 'wall-preview.png'))
    print('接縫檢查圖 -> tools/art-guide/wall-preview.png')
    print('接著跑：D:/python/python.exe tools/gen_shop_room.py')


if __name__ == '__main__':
    print('來源量測：')
    measure()
    print()
    build()
