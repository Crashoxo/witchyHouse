# -*- coding: utf-8 -*-
"""
量每張家具圖「真正畫到東西」的範圍，產生 Assets/Scripts/Data/FurnitureBounds.cs。

    python tools/gen_furniture_bounds.py

為什麼需要：家具的 PNG 有很大一塊透明邊，而且**不是置中**的
（例：shelf_box 圖寬 176，實際畫到的只有 x=62..171）。判斷「貨架會不會穿牆」時
如果拿整張圖的矩形去比，左邊會被那 62px 的空白誤判成超出去、右邊又會少算。

⚠️ 換了家具美術要重跑這支。跑完 Unity 會自己重編。
"""
import os, sys, glob
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'Assets', 'Resources', 'furniture')
OUT = os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'FurnitureBounds.cs')
ALPHA = 40          # 低於這個 alpha 當成沒畫到（JPEG/縮放的殘影不算）

rows = []
for path in sorted(glob.glob(os.path.join(SRC, '*.png'))):
    ident = os.path.splitext(os.path.basename(path))[0]
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    px = im.load()
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if px[x, y][3] >= ALPHA:
                if x < x0: x0 = x
                if x > x1: x1 = x
                if y < y0: y0 = y
                if y > y1: y1 = y
    if x1 < 0:
        print('  略過（整張透明）：', ident)
        continue
    # PNG 的 y 由上往下，Unity 的圖由下往上 → 換算成「離圖底部幾 px」
    bottom = h - 1 - y1
    top = h - y0
    rows.append((ident, w, h, x0, bottom, x1 + 1, top))
    print('  %-14s 圖 %3dx%3d  不透明 x %3d..%-3d  y(離底) %3d..%-3d' %
          (ident, w, h, x0, x1 + 1, bottom, top))

body = '\n'.join(
    '            { "%s", new ArtBox(%d, %d, %d, %d, %d, %d) },' % r for r in rows)

cs = '''using System.Collections.Generic;

namespace WitchShop.Data
{
    /// <summary>一張家具圖裡「真正畫到東西」的範圍（座標原點在圖的左下角）。</summary>
    public readonly struct ArtBox
    {
        public readonly float ImgW, ImgH;      // 整張圖的尺寸
        public readonly float X0, Y0, X1, Y1;  // 不透明範圍

        public ArtBox(float imgW, float imgH, float x0, float y0, float x1, float y1)
        { ImgW = imgW; ImgH = imgH; X0 = x0; Y0 = y0; X1 = x1; Y1 = y1; }
    }

    /// <summary>
    /// 家具圖的不透明範圍表 —— **自動產生，不要手改**。
    /// 產生器：`tools/gen_furniture_bounds.py`（換了家具美術要重跑）。
    ///
    /// 為什麼要這張表：家具的 PNG 有很大一塊透明邊，而且不是置中的
    /// （shelf_box 圖寬 176，實際畫到的只有 x=62..171）。判「貨架會不會穿牆」時
    /// 拿整張圖的矩形去比，左邊會被空白誤判成超出去、右邊又會少算。
    /// </summary>
    public static class FurnitureBounds
    {
        static readonly Dictionary<string, ArtBox> Table = new()
        {
%BODY%
        };

        /// <summary>查不到就回 false（呼叫端退回用整張圖的矩形）。</summary>
        public static bool TryGet(string id, out ArtBox box) => Table.TryGetValue(id, out box);

        /// <summary>
        /// 依「實際載到的圖尺寸」查：細畫版（FurnitureArt8，尺寸對得上）優先，再查舊圖這張表（也要尺寸對得上）。
        /// </summary>
        public static bool TryGet(string id, float imgW, float imgH, out ArtBox box)
        {
            if (FurnitureArt8.TryGetBounds(id, imgW, imgH, out box)) return true;
            return Table.TryGetValue(id, out box) && (int)box.ImgW == (int)imgW && (int)box.ImgH == (int)imgH;
        }
    }
}
'''.replace('%BODY%', body)

with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write(cs)
print('寫出', OUT, '共', len(rows), '筆')
