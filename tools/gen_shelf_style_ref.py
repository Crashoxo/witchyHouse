# -*- coding: utf-8 -*-
"""
產 PixelLab 用的 Style Reference：**把使用者自己那款貨架校正成正確 2:1 之後**縮到參考畫布。

為什麼不畫一張合成的積木圖：Style Reference 同時決定「風格」與「輸出尺寸」，
拿他自己的圖當參考，木色/描邊/打光才會跟已經在遊戲裡的那批一致；
而校正後的版本投影是對的（兩個地面軸都 1/2），生成器就會照著這個角度畫。

⚠️ 參考圖裡**不要放任何標記線**（做牆的時候把 wall-guide 的粉紅線當參考圖，
   結果粉紅線被當成圖案畫進去了）。
"""
import os, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import numpy as np
import import_furniture as I

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'art-guide')
BASE = 'shelf_box'        # 最素的一款，風格看得最清楚
CANVAS = 72               # 跟他原本那批的畫布一樣大 → 新的一批尺寸才對得上


def build():
    rel = I.SOURCES[BASE][0]
    src = Image.open(os.path.join(I.SRC, rel.replace('/', os.sep))).convert('RGBA')
    big = src.resize((src.width * 2, src.height * 2), Image.NEAREST)
    fixed = I.unskew(big)                       # 校正成 2:1
    fixed = fixed.crop(fixed.getbbox())
    # 等比縮回參考畫布（等比縮放不會破壞斜率）
    k = min(CANVAS / fixed.width, CANVAS / fixed.height)
    w, h = max(1, int(round(fixed.width * k))), max(1, int(round(fixed.height * k)))
    small = fixed.resize((w, h), Image.LANCZOS)
    # 縮完會有半透明的髒邊，把它硬化回像素畫該有的樣子
    a = np.array(small)
    alpha = a[:, :, 3]
    a[:, :, 3] = np.where(alpha >= 128, 255, 0)
    small = Image.fromarray(a).quantize(colors=32, method=Image.FASTOCTREE).convert('RGBA')
    a = np.array(small); a[:, :, 3] = np.where(alpha >= 128, 255, 0)
    small = Image.fromarray(a)

    ref = Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))
    ref.alpha_composite(small, ((CANVAS - w) // 2, CANVAS - h))
    p = os.path.join(OUT, 'shelf-style-ref.png')
    ref.save(p)
    print('shelf-style-ref.png', ref.size, '物件', (w, h), '->', p)
    return ref


if __name__ == '__main__':
    build()
