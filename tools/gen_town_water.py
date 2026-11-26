# -*- coding: utf-8 -*-
"""
城鎮（場景 town）的河 → 玩家碰撞用的水域障礙（一堆軸對齊矩形），
產生 Assets/Scripts/Data/TownWaterData.cs。執行期由 Core/TownWater.cs 登記進 Obstacles。

    python tools/gen_town_water.py              # 算遮罩 → 寫 TownWaterData.cs，印出矩形數與每座橋的可走寬度
    python tools/gen_town_water.py --preview DIR # 另外輸出遮罩／矩形的對照圖
    python tools/check_walkable.py [DIR]        # 再跑這支看可達性（會把水域矩形算進城鎮的檢查）

確定性、可重跑：遮罩來自 tools/ground/town.py 的 shape_masks()（固定 SEED），
跟烤進地面圖的水**逐像素是同一份**；之後的侵蝕／粗格／合併都沒有亂數。
⚠️ 改了 town.py 的路／河（townmask.py、round_mask 參數、SEED）→ 重烤地面之後**一定要重跑這支**，
   不然碰撞跟畫出來的河會對不上（走得進水裡、或岸上有隱形牆）。

── 做法 ──────────────────────────────────────────────────────
  1. 遮罩：town.shape_masks() 的 water（＝ water_r & ~stone & ~dirt：橋〔石頭〕已經扣掉，
     所以橋面天生就是空的）。美術解析度 1600×1024，1 美術像素 ＝ 2 世界像素（ART_PX）。
  2. 往內侵蝕 ERODE 世界像素（圓盤）。Obstacles 會把每個形狀往外長一個玩家半徑（11）、
     玩家當成點 → 侵蝕 11 的話腳底圓心剛好停在水邊。這裡只侵蝕 6：腳底圓心停在**離水邊約 5px 的岸上**，
     女巫的腳（約 20 寬）看起來踩在沙岸／橋欄杆上，而不是半隻腳泡在水裡（見下面 ERODE 的說明）。
     侵蝕後消失的細水（岸邊一兩像素的水花、河中間的小沙洲旁）就不擋。
  3. 粗格：16 世界像素一格（＝8×8 美術像素），格內侵蝕後的水超過一半才算擋。
  4. 貪婪合併成矩形：先直向、再橫向各試一次，取矩形數少的那個（河是直的一條，通常直向先併比較少）。
  5. 橋：每座橋（石頭蓋在 water_r 上的地方）量「腳底圓心可走的通道寬度」（已經扣掉兩側各 11），
     低於 MIN_BRIDGE 就把橋面範圍內有石頭的格子強制清掉，再量一次；還不夠就以錯誤結束。

── 座標 ─────────────────────────────────────────────────────
  地面 Ground 在世界原點、大小 3200×2048（BakedGround.cs 以 PPU 0.5 貼 1600×1024 的圖）。
  美術像素 (col, row)（row 0 ＝圖的最上緣）的中心在世界
      x = -1600 + (col + 0.5) × 2，   y = 1024 - (row + 0.5) × 2     ← ⚠️ y 軸方向相反
  粗格 (i, j)（j 從上往下數）的世界範圍：x ∈ [-1600 + 16i, -1600 + 16(i+1)]，
                                          y ∈ [1024 - 16(j+1), 1024 - 16j]。
"""
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'ground'))

import gen_footprints as G   # noqa: E402   玩家半徑（碰撞規則的唯一來源）
import layouts               # noqa: E402
import town                  # noqa: E402
from common import ART_PX    # noqa: E402

ROOT = G.ROOT
OUT = os.path.join(G.DATA, 'TownWaterData.cs')
GROUND_PNG = os.path.join(G.RES, 'art', 'ground', 'town.png')

R = G.PLAYER_RADIUS          # 11：Obstacles 碰撞時把形狀往外長的量
# 往內侵蝕多少（世界像素）。11 ＝腳底圓心剛好停在水邊；取 6 ＝停在離水約 5px 的岸上。
# 為什麼不是 11：女巫的樞紐在腳底中央、腳約 20 寬，圓心停在水邊時半隻腳畫在水上；
# 烤圖的岸邊是 2～10px 的沙岸（草地側）或橋欄杆（石頭側），停在水外 5px 剛好踩在沙岸／欄杆上。
# 為什麼不更小：粗格化本身有 ±8 的誤差，再小的話直的河岸會擋在離水 13px 以外，看起來像隱形牆。
ERODE = 6.0
CELL = 16.0                  # 粗格（世界像素）
FILL = 0.5                   # 格內水的比例「超過」這個才算擋
MIN_BRIDGE = 30.0            # 每座橋腳底圓心可走的通道至少要這麼寬（已扣掉兩側各 R）


# ──────────── 遮罩 ────────────

def masks():
    """town.py 的最終水遮罩（跟烤圖同一份）＋石頭（橋）＋ water_r（橋下也算水）。美術解析度。"""
    W, H = layouts.SIZES['town']
    w, h = W // ART_PX, H // ART_PX
    sm = town.shape_masks(np.random.default_rng(town.SEED), h, w)
    return sm, W, H


def disk(r):
    """半徑 r（美術像素）的圓盤位移清單。"""
    n = int(np.floor(r))
    return [(dy, dx) for dy in range(-n, n + 1) for dx in range(-n, n + 1) if dy * dy + dx * dx <= r * r + 1e-9]


def erode_disk(mask, r, outside=True):
    """圓盤侵蝕。outside＝地圖外當成什麼：True＝延伸邊緣（河流到地圖邊不會在邊上斷開一條縫）。"""
    if r <= 0:
        return mask.copy()
    n = int(np.floor(r))
    p = np.pad(mask, n, mode='edge') if outside else np.pad(mask, n, constant_values=False)
    h, w = mask.shape
    out = np.ones_like(mask)
    for dy, dx in disk(r):
        out &= p[n + dy:n + dy + h, n + dx:n + dx + w]
    return out


def dilate_disk(mask, r):
    if r <= 0:
        return mask.copy()
    n = int(np.floor(r))
    p = np.pad(mask, n, constant_values=False)
    h, w = mask.shape
    out = np.zeros_like(mask)
    for dy, dx in disk(r):
        out |= p[n + dy:n + dy + h, n + dx:n + dx + w]
    return out


def coarse(mask, k):
    """k×k 美術像素一格，回傳每格的覆蓋比例。"""
    h, w = mask.shape
    return mask.reshape(h // k, k, w // k, k).mean(axis=(1, 3))


def components(mask):
    """8 連通的連通塊，回傳 [(y0, x0, y1, x1), ...]（含端點、美術像素），由上往下排。"""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        ys, xs = [], []
        while stack:
            y, x = stack.pop()
            ys.append(y)
            xs.append(x)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    a, b = y + dy, x + dx
                    if 0 <= a < h and 0 <= b < w and mask[a, b] and not seen[a, b]:
                        seen[a, b] = True
                        stack.append((a, b))
        out.append((min(ys), min(xs), max(ys), max(xs)))
    return sorted(out)


# ──────────── 合併成矩形 ────────────

def greedy(cells, vertical):
    """貪婪合併：每個還沒蓋到的格子，先往一個方向延伸到底，再往另一個方向整排延伸。
    回傳 [(j0, i0, j1, i1)]（含端點，格子座標，j 從上往下）。"""
    g = cells if not vertical else cells.T
    ny, nx = g.shape
    used = np.zeros_like(g)
    out = []
    for j in range(ny):
        for i in range(nx):
            if not g[j, i] or used[j, i]:
                continue
            i1 = i
            while i1 + 1 < nx and g[j, i1 + 1] and not used[j, i1 + 1]:
                i1 += 1
            j1 = j
            while j1 + 1 < ny and np.all(g[j1 + 1, i:i1 + 1]) and not np.any(used[j1 + 1, i:i1 + 1]):
                j1 += 1
            used[j:j1 + 1, i:i1 + 1] = True
            out.append((j, i, j1, i1) if not vertical else (i, j, i1, j1))
    return out


def to_world(rects, W, H):
    """格子矩形 → 世界座標 (xMin, yMin, xMax, yMax)。"""
    out = []
    for j0, i0, j1, i1 in rects:
        out.append((-W / 2 + CELL * i0, H / 2 - CELL * (j1 + 1), -W / 2 + CELL * (i1 + 1), H / 2 - CELL * j0))
    return out


# ──────────── 橋的通道寬度 ────────────

def bridges(sm):
    """每座橋的範圍（美術像素 bbox）：河流經的那幾欄（有水的最左欄～最右欄）裡，石頭的連通塊。
    ⚠️ 不能用「石頭 & water_r」：water_r 只把離水 16 美術像素內的石頭當成橋下的水，
       北邊那座大石橋（90 美術像素高）中間不在裡面，會被拆成上下兩條欄杆、量出來的寬度沒有意義。
    太小的塊（< 200 美術像素，路角零星的石頭）不算橋。"""
    water = sm['water']
    cols = np.nonzero(water.any(axis=0))[0]
    band = np.zeros_like(water)
    band[:, cols.min():cols.max() + 1] = True
    deck = sm['stone'] & band
    boxes = [b for b in components(deck) if deck[b[0]:b[2] + 1, b[1]:b[3] + 1].sum() >= 200]
    return boxes, deck


def passage(cells, box, k):
    """橋 box（美術像素）上，腳底圓心從西岸走到東岸的通道最寬能多寬（世界像素，已扣掉兩側各 R）。
    做法：擋住的格子長一個 R ＝圓心進不去；再把進不去的範圍逐步長 t，看西→東還通不通，
    最大的 t ×2 就是通道寬度。窗口左右各多 20 美術像素（伸到岸上），上下各多 4。"""
    y0, x0, y1, x1 = box
    y0, y1 = max(0, y0 - 4), y1 + 4
    x0, x1 = max(0, x0 - 20), x1 + 20
    full = np.repeat(np.repeat(cells, k, 0), k, 1)
    # 窗口外再多抓 R 的邊，窗口邊上的格子才算得到附近的障礙
    pad = int(np.ceil(R / ART_PX)) + 2
    ya, yb = max(0, y0 - pad), min(full.shape[0], y1 + 1 + pad)
    xa, xb = max(0, x0 - pad), min(full.shape[1], x1 + 1 + pad)
    sub = full[ya:yb, xa:xb]
    blocked = dilate_disk(sub, R / ART_PX)
    wy0, wx0 = y0 - ya, x0 - xa
    wy1, wx1 = wy0 + (y1 - y0), wx0 + (x1 - x0)

    def crosses(t):
        free = ~dilate_disk(blocked, t / ART_PX)[wy0:wy1 + 1, wx0:wx1 + 1]
        h, w = free.shape
        reach = np.zeros_like(free)
        stack = [(y, 0) for y in range(h) if free[y, 0]]
        for p in stack:
            reach[p] = True
        while stack:
            y, x = stack.pop()
            for a, b in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= a < h and 0 <= b < w and free[a, b] and not reach[a, b]:
                    reach[a, b] = True
                    stack.append((a, b))
        return bool(reach[:, -1].any())

    if not crosses(0.0):
        return 0.0
    best = 0.0
    t = ART_PX
    while t <= 200 and crosses(t):
        best = t
        t += ART_PX
    # 圓心離進不去的範圍 ≥ t 的路徑存在 → 通道寬 ≈ 2t（＋一格量化誤差）
    return 2 * best + ART_PX


# ──────────── 主程式 ────────────

def compute(verbose=True):
    sm, W, H = masks()
    water = sm['water']
    k = int(CELL // ART_PX)                                   # 8 美術像素一格
    eroded = erode_disk(water, ERODE / ART_PX, outside=True)
    cov = coarse(eroded, k)
    cells = cov > FILL

    boxes, deck = bridges(sm)
    deck_cov = coarse(deck, k)
    widths, forced = [], 0
    for b in boxes:
        wdt = passage(cells, b, k)
        if wdt < MIN_BRIDGE:
            # 橋口被粗格吃窄了：橋的範圍內、有石頭的格子一律清掉（石頭本來就是可以走的）
            y0, x0, y1, x1 = b
            j0, j1, i0, i1 = y0 // k, y1 // k, x0 // k, x1 // k
            sel = np.zeros_like(cells)
            sel[j0:j1 + 1, i0:i1 + 1] = deck_cov[j0:j1 + 1, i0:i1 + 1] > 0
            forced += int((cells & sel).sum())
            cells &= ~sel
            wdt = passage(cells, b, k)
        widths.append((b, wdt))

    rv = greedy(cells, True)
    rh = greedy(cells, False)
    rects = rv if len(rv) <= len(rh) else rh
    world = to_world(rects, W, H)

    if verbose:
        print('水遮罩：%d 美術像素（%.0f 世界像素²）；侵蝕 %.0f 後剩 %d；粗格 %.0f、格內 >%.0f%% 才擋 → %d 格' % (
            water.sum(), water.sum() * ART_PX * ART_PX, ERODE, eroded.sum(), CELL, FILL * 100, cells.sum()))
        print('合併：直向先併 %d 個、橫向先併 %d 個 → 用 %s，共 %d 個矩形' % (
            len(rv), len(rh), '直向' if rects is rv else '橫向', len(world)))
        for n, (b, wdt) in enumerate(widths, 1):
            y0, x0, y1, x1 = b
            print('橋 %d：世界 x %.0f..%.0f、y %.0f..%.0f；腳底圓心可走寬度 %.0f px（已扣兩側各 %.0f）%s' % (
                n, -W / 2 + x0 * ART_PX, -W / 2 + (x1 + 1) * ART_PX, H / 2 - (y1 + 1) * ART_PX, H / 2 - y0 * ART_PX,
                wdt, R, '' if wdt >= MIN_BRIDGE else '  ⚠️ 不夠寬'))
        print('橋面強制清掉的格子：%d' % forced)
    bad = [w for _, w in widths if w < MIN_BRIDGE]
    return dict(sm=sm, W=W, H=H, eroded=eroded, cells=cells, rects=world, widths=widths, forced=forced, bad=bad)


def _f(v):
    s = ('%.1f' % v).rstrip('0').rstrip('.')
    return (s if s not in ('', '-0') else '0') + 'f'


def write_cs(res):
    rows = '\n'.join('            new(%s, %s, %s, %s),' % tuple(_f(v) for v in r) for r in res['rects'])
    cs = '''// <auto-generated>
// ⚠️ 自動產生，不要手改。產生器：tools/gen_town_water.py
//    重跑：python tools/gen_town_water.py（再跑 python tools/check_walkable.py 看可達性與預覽）
//    要調侵蝕量／粗格大小／橋的最小寬度：改產生器最上面的 ERODE／CELL／FILL／MIN_BRIDGE，不是改這個檔。
//    ⚠️ 改了城鎮地面的河（tools/ground/town.py、townmask.py）重烤之後，也要重跑產生器。
// </auto-generated>
namespace WitchShop.Data
{
    /// <summary>一塊水域障礙：軸對齊矩形，世界座標。</summary>
    public readonly struct WaterRect
    {
        public readonly float XMin, YMin, XMax, YMax;

        public WaterRect(float xMin, float yMin, float xMax, float yMax)
        {
            XMin = xMin; YMin = yMin; XMax = xMax; YMax = yMax;
        }
    }

    /// <summary>
    /// 城鎮（town）的河：玩家不能直接走過去、要走橋。由 Core/TownWater.Register 登記進 Obstacles。
    /// 來源是烤進地面圖的同一份水遮罩（tools/ground/town.py 的 shape_masks；橋〔石頭〕已經扣掉），
    /// 往內侵蝕 %(erode)s 世界像素（Obstacles 會再往外長玩家半徑 %(r)s → 腳底圓心停在離水約 %(gap)s px 的岸上）、
    /// 以 %(cell)s px 的粗格（格內水超過一半才算）貪婪合併成矩形。
    /// 每座橋的通道（腳底圓心可走寬度）：%(widths)s。
    /// </summary>
    public static class TownWaterData
    {
        public static readonly WaterRect[] Rects =
        {
%(rows)s
        };
    }
}
''' % dict(erode=_g(ERODE), r=_g(R), gap=_g(R - ERODE), cell=_g(CELL), rows=rows,
           widths='、'.join('%.0f px' % w for _, w in res['widths']))
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(cs)


def _g(v):
    return ('%.1f' % v).rstrip('0').rstrip('.')


def load_cs():
    """讀回產生出來的 TownWaterData.cs（check_walkable.py 用：檢查的是遊戲實際用的那份資料）。
    回傳 [(xMin, yMin, xMax, yMax)]；檔案不存在回傳 []。"""
    import re
    if not os.path.exists(OUT):
        return []
    with open(OUT, encoding='utf-8') as f:
        src = f.read()
    num = r'(-?[\d.]+)f'
    return [tuple(float(v) for v in m.groups())
            for m in re.finditer(r'new\(%s,\s*%s,\s*%s,\s*%s\)' % (num, num, num, num), src)]


def preview(res, outdir):
    """地面圖（世界解析度）＋水遮罩外框＋矩形。"""
    W, H = res['W'], res['H']
    img = Image.open(GROUND_PNG).convert('RGB').resize((W, H), Image.NEAREST)
    a = np.asarray(img).copy()
    water = np.repeat(np.repeat(res['sm']['water'], ART_PX, 0), ART_PX, 1)
    eroded = np.repeat(np.repeat(res['eroded'], ART_PX, 0), ART_PX, 1)
    a[water & ~eroded] = (a[water & ~eroded] * 0.5 + np.array([255, 255, 0]) * 0.5).astype(np.uint8)
    img = Image.fromarray(a)
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for x0, y0, x1, y1 in res['rects']:
        d.rectangle([x0 + W / 2, H / 2 - y1, x1 + W / 2 - 1, H / 2 - y0 - 1], outline=(0, 255, 255))
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, 'town-water-rects.png')
    xs = [r[0] for r in res['rects']] + [r[2] for r in res['rects']]
    box = (int(min(xs) + W / 2 - 120), 0, int(max(xs) + W / 2 + 120), H)
    img.crop(box).save(p)
    return p


def main():
    res = compute()
    write_cs(res)
    print('寫出', OUT, '共', len(res['rects']), '個矩形')
    if '--preview' in sys.argv:
        print('預覽 →', preview(res, sys.argv[sys.argv.index('--preview') + 1]))
    if res['bad']:
        print('⚠️ 有橋的通道不到 %.0f px' % MIN_BRIDGE)
        sys.exit(1)


if __name__ == '__main__':
    main()
