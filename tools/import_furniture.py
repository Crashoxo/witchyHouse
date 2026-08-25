"""
把手繪／PixelLab 出的家具圖匯入成遊戲用的 `assets/resources/furniture/<id>.png`。

做兩件事：
  1. **量出佔地的前角**——家具圖的錨點約定是「圖的正下方中央＝佔地前角」，但生成器
     畫出來的東西是置中在畫布裡的，前角通常偏左也偏下（有腳的家具前角甚至沒畫到）。
     這裡用「**最貼合的 2:1 V 形**」求前角：底部輪廓不能低於這個 V，且 V 盡量高。
     等距投影下佔地菱形的兩條下緣斜率就是 ±1/2，所以這個 V 的頂點＝前角。
  2. **×2 NEAREST 放大**——美術是畫在來源解析度（一格 32×16），遊戲內一格是 64×32。
     `GameArt.furniture()` 拿到的圖是直接 1:1 用的（DecorRoom 的 k=1）。

用法：
    D:/python/python.exe tools/import_furniture.py            # 匯入 SOURCES 表裡的全部
    D:/python/python.exe tools/import_furniture.py shelf_arch # 只做其中一件
    D:/python/python.exe tools/import_furniture.py --contact  # 另外輸出一張對照圖

⚠️ 佔地格數（fw, fh）要跟 `assets/scripts/data/shopRoom.ts` 的 FURNITURE 一致。
"""
import os, sys, shutil
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageDraw
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'tools', 'art-src', 'furniture')
OUT = os.path.join(ROOT, 'assets', 'resources', 'furniture')
# 裝飾品走同一套流程（投影校正＋×2＋前角對位），只是換來源與輸出資料夾。
# 這些也是畫在同一個尺度上的，所以 data/decor.ts 那三筆要標 `scale: 1`
# （舊的十六款裝飾是大圖，DecorRoom 會用 decorScale 0.4 縮）。
SRC_DECOR = os.path.join(ROOT, 'tools', 'art-src', 'decor')
OUT_DECOR = os.path.join(ROOT, 'assets', 'resources', 'decor')

TW, TH = 32, 16          # 來源解析度的一格（遊戲內 64×32）
SCALE = 2                # 來源 → 遊戲
MARGIN_X = 2             # 左右各留幾 px（來源解析度）

# ── 投影校正 ──────────────────────────────────────────────────────────────
# ⚠️ **PixelLab 的 Objects 出的不是真 2:1 等距**：十六款貨架的兩個地面軸是**不對稱的**——
#        往左上 ≈ **1/2**（剛好對）　往右上 ≈ **1/3**（太平，26.6° 變成 18.4°）
#    而我們的地板兩邊都是嚴格 1/2 → 擺進房間就「角度很怪」。
#
# ⚠️⚠️ **量的時候一定要用「底座」的兩條下緣，不要用頂面的上緣**：
#    第一次我用上緣量，把兩個軸**對調**了（頂面上緣的「左半」對應的其實是「往右上」那個軸，
#    因為那條邊是從頂面後角往下走的 −B 方向），結果校正把本來正確的那個軸拉歪、
#    另一個也壓得更平，兩邊都變糟。底座是真正的地面矩形，量它不會錯。
#    驗證用 `verify()`：校正完再量一次輸出，兩軸都要落在 0.5 附近。
#
# 修法＝一個仿射校正：**x 不動、y' = SHEAR*x + STRETCH*y**，
# 解出來剛好讓兩個地面軸都變成 1/2，而且 **(0,1) → (0,STRETCH) 仍是垂直的**
# （垂直邊不歪，只是整體高 STRETCH 倍；佔地的水平寬度完全不變 → 佔地格數不受影響）。
SRC_SLOPE_L = 1 / 2      # 來源往左上的斜率（量出來的：本來就對）
SRC_SLOPE_R = 1 / 3      # 來源往右上的斜率（量出來的：太平，要拉陡）
DST_SLOPE = TH / TW      # 地板的 1/2
# ⚠️⚠️ **不是每張圖都需要校正** —— 實測（2026-08-25）：提示詞裡有沒有寫
#    `2:1 isometric view` 會直接決定投影對不對。
#        沒寫的（第一批十六款貨架、新出的 simple_box）→ 長軸 0.33~0.36 ✗
#        有寫的（三個展示架）                          → 長軸 0.500 ✅
#    所以預設改成 **'auto'**：先量來源的長軸，本來就 ≈0.5 就不要動它
#    （對已經正確的圖硬套校正會把它拉歪 —— 踩過）。
FIX_PROJECTION = 'auto'  # True / False / 'auto'
AUTO_TOL = 0.08          # 長軸離 0.5 這麼近就當成已經是 2:1

# id -> (來源檔, 佔地寬, 佔地深)
SHELF_SRC = 'shelf'
# 裝飾品：id -> (來源檔, 佔地寬, 佔地深)。都是一格大的擺飾。
SOURCES_DECOR = {
    'crystal_shelf': ('crystal_shelf.png', 1, 1),
    'herb_shelf':    ('herb_shelf.png',    1, 1),
    'potion_shelf':  ('potion_shelf.png',  1, 1),
}

SOURCES = {
    'shelf_box':     (f'{SHELF_SRC}/simple_box_shelf_with_visible.png',  1, 2),
    'shelf_arch':    (f'{SHELF_SRC}/shelf_with_arched_top_and_two.png',  1, 2),
    'shelf_peak':    (f'{SHELF_SRC}/shelf_with_a_peaked_top_like_a.png', 1, 2),
    'shelf_scallop': (f'{SHELF_SRC}/shelf_with_a_scalloped_top_edg.png', 1, 2),
    'shelf_curve':   (f'{SHELF_SRC}/shelf_with_curved_top_and_open.png', 1, 2),
    'shelf_round':   (f'{SHELF_SRC}/shelf_with_rounded_corners_and.png', 1, 2),
    'shelf_back':    (f'{SHELF_SRC}/shelf_with_closed_back_panel_a.png', 1, 2),
    'shelf_slat':    (f'{SHELF_SRC}/shelf_with_slatted_back_panel.png',  1, 2),
    'shelf_cross':   (f'{SHELF_SRC}/shelf_with_cross-braced_back.png',   1, 2),
    'shelf_drawer':  (f'{SHELF_SRC}/shelf_with_small_drawers_on_th.png', 1, 2),
    'shelf_two':     (f'{SHELF_SRC}/shelf_with_two_shelves_and_a_d.png', 1, 2),
    'shelf_cabinet': (f'{SHELF_SRC}/shelf_with_a_small_cabinet_at.png',  1, 2),
    'shelf_deep':    (f'{SHELF_SRC}/shelf_with_a_deep_bottom_shelf.png', 1, 2),
    'shelf_plank':   (f'{SHELF_SRC}/plain_plank_shelf_with_thick_s.png', 1, 2),
    'shelf_narrow':  (f'{SHELF_SRC}/narrow_shelf_with_three_open_s.png', 1, 2),
    'shelf_tall':    (f'{SHELF_SRC}/tall_narrow_shelf_with_four_th.png', 1, 2),
}


def correction():
    """回傳 (shear, stretch)：y' = shear*x + stretch*y。x 不變、垂直線保持垂直。"""
    sl, sr, d = SRC_SLOPE_L, SRC_SLOPE_R, DST_SLOPE
    # 解 { shear + stretch*sl = d ; shear - stretch*sr = -d }
    stretch = 2 * d / (sl + sr)
    shear = d - stretch * sl
    return shear, stretch


def unskew(im):
    """把來源的非對稱投影校正成 2:1。NEAREST，保持像素銳利。"""
    shear, stretch = correction()
    w, h = im.size
    ys = [shear * x + stretch * y for x in (0, w) for y in (0, h)]
    top, bot = min(ys), max(ys)
    out_h = int(round(bot - top))
    # PIL 的 AFFINE 是「輸出座標 → 輸入座標」，所以要餵反矩陣
    #   x_in = x_out
    #   y_in = (y_out + top - shear * x_out) / stretch
    data = (1, 0, 0,
            -shear / stretch, 1 / stretch, top / stretch)
    return im.transform((w, out_h), Image.AFFINE, data, resample=Image.NEAREST)


def base_slopes(mask):
    """量底座兩條下緣的斜率 (往左上, 往右上)。校正後兩個都應該 ≈ 0.5。"""
    import random
    rnd = random.Random(1)
    H, W = mask.shape
    bot = {}
    for x in range(W):
        ys = np.where(mask[:, x])[0]
        if len(ys):
            bot[x] = float(ys[-1])
    if not bot:
        return None, None
    low = max(bot, key=lambda x: bot[x])

    def fit(pts):
        if len(pts) < 8:
            return None
        best = (None, 0)
        for _ in range(4000):
            (x1, y1), (x2, y2) = rnd.sample(pts, 2)
            if x1 == x2:
                continue
            m = (y2 - y1) / (x2 - x1)
            if not (0.15 <= abs(m) <= 1.5):
                continue
            b = y1 - m * x1
            n = sum(1 for x, y in pts if abs(y - (m * x + b)) <= 1.0)
            if n > best[1]:
                best = (abs(m), n)
        return best[0] if best[1] >= 8 else None

    return (fit([(x, bot[x]) for x in bot if x < low]),
            fit([(x, bot[x]) for x in bot if x > low]))


def front_corner(mask):
    """最貼合的 2:1 V 形頂點＝佔地前角。回傳 (fx, fy)，可能落在畫布外（腳沒畫到前角時）。"""
    H, W = mask.shape
    bot = {}
    for x in range(W):
        ys = np.where(mask[:, x])[0]
        if len(ys):
            bot[x] = float(ys[-1])
    if not bot:
        raise ValueError('整張圖都是透明的')
    xs = sorted(bot)
    best = None
    # 半格精度：×2 放大後剛好落在整數像素上
    lo, hi = xs[0] - 4, xs[-1] + 4
    fx = lo
    while fx <= hi:
        B = max(bot[x] + 0.5 * abs(x - fx) for x in xs)
        if best is None or B < best[0] - 1e-9:
            best = (B, fx)
        fx += 0.5
    return best[1], best[0]


def convert(pid, rel, fw, fh, verbose=True, src_dir=None, out_dir=None):
    path = os.path.join(src_dir or SRC, rel.replace('/', os.sep))
    im = Image.open(path).convert('RGBA')
    fx, fy = front_corner(np.array(im)[:, :, 3] > 8)

    big = im.resize((im.width * SCALE, im.height * SCALE), Image.NEAREST)
    fix = FIX_PROJECTION
    if fix == 'auto':
        _, long_axis = base_slopes(np.array(big)[:, :, 3] > 8)
        fix = not (long_axis is not None and abs(long_axis - 0.5) <= AUTO_TOL)
    if fix:
        # 校正後底部輪廓才真的是 2:1，前角要重量一次（量出來會更準）
        big = unskew(big)
        m2 = np.array(big)[:, :, 3] > 8
        fx, fy = front_corner(m2)
        fx2, fy2 = int(round(fx)), int(round(fy))
    else:
        fx2, fy2 = int(round(fx * SCALE)), int(round(fy * SCALE))
    bb = big.getbbox()                                   # (l, t, r, b)
    m = MARGIN_X * SCALE
    half = max(fx2 - bb[0], bb[2] - fx2) + m
    w = half * 2
    h = fy2 - bb[1] + 1 + m                              # 上方留一點，底部就是前角

    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    out.alpha_composite(big, (half - fx2, (h - 1) - fy2))
    dst = os.path.join(out_dir or OUT, pid + '.png')
    out.save(dst, optimize=True)
    if verbose:
        # ⚠️ 只嚴格檢查**長邊那個軸**（往右上，佔 fh 格）。往左上那條只有半格多、
        #    通常還被腳擋住，樣本點常常不到 10 個，量出來 ±0.15 都算正常，不要拿它當判準。
        sa, sb = base_slopes(np.array(out)[:, :, 3] > 8)
        chk = ('  ✔ 長軸 %.2f' % sb) if (sb and abs(sb - .5) < .08)               else ('  ⚠ 長軸 %s（應該 ~0.50）' % (f'{sb:.2f}' if sb else '點太少量不出來'))
        chk += ('（短軸 %.2f，僅供參考）' % sa) if sa else ''
        chk = ('[校正]' if fix else '[原圖已是 2:1]') + chk
        span = (fw + fh) * TW // 2
        print(f'{pid:14s} <- {os.path.basename(rel):34s} 前角=({fx:6.1f},{fy:6.1f}) '
              f'佔地 {fw}x{fh} -> {w}x{h}{chk}')
    return out


def contact_sheet(items):
    """把匯入結果排一張對照圖，底下畫出佔地菱形，確認前角對得上。"""
    cols = 4
    cw = max(i[1].width for i in items) + 16
    ch = max(i[1].height for i in items) + 40
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new('RGBA', (cols * cw, rows * ch), (34, 30, 34, 255))
    d = ImageDraw.Draw(sheet)
    for i, (pid, im, fw, fh) in enumerate(items):
        x = (i % cols) * cw + cw // 2
        y = (i // cols) * ch + ch - 28
        sheet.alpha_composite(im, (x - im.width // 2, y - im.height + 1))
        F = (x, y)
        L = (x - fw * TW * SCALE / 2, y - fw * TH * SCALE / 2)
        R = (x + fh * TW * SCALE / 2, y - fh * TH * SCALE / 2)
        B = (L[0] + R[0] - F[0], L[1] + R[1] - F[1])
        d.polygon([F, R, B, L], outline=(0, 235, 180, 255))
        d.text((x - cw // 2 + 6, y + 8), pid, fill=(230, 226, 232))
    p = os.path.join(ROOT, 'tools', 'art-guide', 'furniture-contact.png')
    sheet.save(p)
    print('對照圖 ->', p, sheet.size)


if __name__ == '__main__':
    decor = '--decor' in sys.argv
    table = SOURCES_DECOR if decor else SOURCES
    src_dir, out_dir = (SRC_DECOR, OUT_DECOR) if decor else (SRC, OUT)
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    want = args or list(table)
    os.makedirs(out_dir, exist_ok=True)
    done = []
    for pid in want:
        rel, fw, fh = table[pid]
        done.append((pid, convert(pid, rel, fw, fh, src_dir=src_dir, out_dir=out_dir), fw, fh))
    if '--contact' in sys.argv:
        contact_sheet(done)
