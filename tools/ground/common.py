"""
地面烘焙器的共用工具：雜訊、遮罩運算、像素小圖章、存檔。

所有圖都在「美術解析度」作畫：1 個美術像素 ＝ ART_PX 個世界像素（Unity 單位）。
最後輸出的低解析度圖由 BakedGround.cs 在執行期以 PPU = 1/ART_PX 貼回 Ground，
所以世界大小不變、像素格子銳利（不會被 Unity 的 Max Size 2048 縮糊）。
"""
import numpy as np
from PIL import Image, ImageFilter

ART_PX = 2   # 一個美術像素佔幾個世界像素（女巫 ×1.6、城鎮建築 ×1，取 2 讓地面略粗、退成背景）


def hexc(s):
    s = s.lstrip('#')
    return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.uint8)


def pal(*hexes):
    return np.stack([hexc(h) for h in hexes])


# ───────────── 雜訊 ─────────────

def fnoise(h, w, sigma, rng, aniso=1.0):
    """低頻雜訊：白雜訊經頻域高斯濾波，sigma 是特徵尺寸（美術像素）。回傳均值 0、標準差 1。
    aniso > 1 會把紋理沿 x 方向拉長（適合有方向的地面，如泥土路的車轍）。
    結果是週期性的（左右/上下可以無縫接），平鋪磚也能直接用。"""
    white = rng.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    g = np.exp(-2 * (np.pi * sigma) ** 2 * ((fx * aniso) ** 2 + fy ** 2))
    n = np.real(np.fft.ifft2(np.fft.fft2(white) * g))
    n -= n.mean()
    sd = n.std()
    return n / sd if sd > 0 else n


def fractal(h, w, sigma, rng, octaves=3, gain=0.5):
    out = np.zeros((h, w))
    amp, s, tot = 1.0, sigma, 0
    for _ in range(octaves):
        out += amp * fnoise(h, w, s, rng)
        tot += amp
        amp *= gain
        s /= 2
    return out / tot


# ───────────── 遮罩 ─────────────

def blur(mask, r):
    """高斯模糊（0..1 浮點遮罩）。邊界用延伸、不會從另一側滲過來。"""
    if r <= 0:
        return mask.astype(float)
    im = Image.fromarray(np.clip(mask * 255, 0, 255).astype(np.uint8), 'L')
    im = im.filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im).astype(float) / 255.0


def dilate(mask, n):
    if n <= 0:
        return mask.copy()
    im = Image.fromarray((mask > 0).astype(np.uint8) * 255, 'L')
    im = im.filter(ImageFilter.MaxFilter(2 * n + 1))
    return np.asarray(im) > 0


def erode(mask, n):
    if n <= 0:
        return mask.copy()
    im = Image.fromarray((mask > 0).astype(np.uint8) * 255, 'L')
    im = im.filter(ImageFilter.MinFilter(2 * n + 1))
    return np.asarray(im) > 0


def shift(m, dy, dx, fill=False):
    """平移遮罩（不環繞）。"""
    out = np.full_like(m, fill)
    h, w = m.shape
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = m[ys, xs]
    return out


def edge_in(m):
    """m 內部、但 4 鄰居有一格不在 m 裡的像素（＝內側描邊）。"""
    nb = shift(m, 1, 0, True) & shift(m, -1, 0, True) & shift(m, 0, 1, True) & shift(m, 0, -1, True)
    return m & ~nb


def round_mask(mask, r, rng, jitter=0.0, jitter_sigma=6.0, thresh=0.5):
    """把方塊遮罩的直角修圓：模糊後取 0.5 等高線（直邊位置不變、凸角變圓、凹角填滿），
    再加一點低頻雜訊抖動讓邊緣不是完美幾何。"""
    f = blur(mask.astype(float), r)
    if jitter:
        f = f + jitter * fnoise(*mask.shape, jitter_sigma, rng)
    return f > thresh


def dist_from(mask, maxd):
    """到 mask 的近似街區距離（0 ＝在 mask 裡），最多算到 maxd。"""
    d = np.full(mask.shape, maxd, dtype=np.int32)
    cur = mask.copy()
    d[cur] = 0
    for i in range(1, maxd):
        cur = dilate(cur, 1)
        d[(d == maxd) & cur] = i
    return d


# ───────────── 小圖章 ─────────────

def parse_stamp(rows):
    """把字元圖案轉成 (dy, dx, 字元) 清單。'.' 或空白＝透明。"""
    out = []
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch not in '. ':
                out.append((y, x, ch))
    return out


def stamp(img, pts, y, x, colors, allow=None):
    """在 (y, x) 蓋一個圖章；colors: 字元→RGB。allow（布林遮罩）可限制只能畫在哪裡。"""
    h, w = img.shape[:2]
    for dy, dx, ch in pts:
        yy, xx = y + dy, x + dx
        if 0 <= yy < h and 0 <= xx < w and (allow is None or allow[yy, xx]):
            c = colors.get(ch)
            if c is not None:
                img[yy, xx] = c


def poisson_points(h, w, n, rng, density=None, min_d=0):
    """撒 n 個點；density（0..1 陣列）控制哪裡比較密（拒絕取樣）。min_d>0 時做簡單的最小距離剔除。"""
    pts = []
    tries = 0
    grid = {}
    cell = max(1, min_d)
    while len(pts) < n and tries < n * 30:
        tries += 1
        y, x = int(rng.integers(0, h)), int(rng.integers(0, w))
        if density is not None and rng.random() > density[y, x]:
            continue
        if min_d:
            gy, gx = y // cell, x // cell
            ok = True
            for yy in range(gy - 1, gy + 2):
                for xx in range(gx - 1, gx + 2):
                    for (py, px) in grid.get((yy, xx), ()):
                        if (py - y) ** 2 + (px - x) ** 2 < min_d * min_d:
                            ok = False
                            break
            if not ok:
                continue
            grid.setdefault((gy, gx), []).append((y, x))
        pts.append((y, x))
    return pts


# ───────────── 輸出 ─────────────

def to_png(rgb, path):
    """存成索引色 PNG（顏色數 ≤256 時無損；地面用有限色盤，一定夠）。"""
    flat = rgb.reshape(-1, 3)
    cols, inv = np.unique(flat, axis=0, return_inverse=True)
    if len(cols) > 256:
        raise RuntimeError(f'{path}: 用了 {len(cols)} 色，超過 256 色盤')
    im = Image.fromarray(inv.reshape(rgb.shape[:2]).astype(np.uint8), 'P')
    p = cols.astype(np.uint8).ravel().tolist()
    im.putpalette(p + [0] * (768 - len(p)))
    im.save(path, optimize=True)
    return len(cols)


def upscale(rgb, k=ART_PX):
    return np.repeat(np.repeat(rgb, k, axis=0), k, axis=1)


def _run_count(m, r, axis):
    """沿 axis 方向，[i-r, i+r] 視窗內有幾格為真（cumsum 版，O(n)；地圖外算假）。"""
    m = m.astype(np.int32)
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(m, pad), axis=axis)
    n = m.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return hi - lo


def erode_big(mask, r):
    """方形大半徑侵蝕（MinFilter 在大半徑時太慢）。地圖外視為假。"""
    a = _run_count(mask, r, 0) == 2 * r + 1
    return _run_count(a, r, 1) == 2 * r + 1


def dilate_big(mask, r):
    a = _run_count(mask, r, 0) > 0
    return _run_count(a, r, 1) > 0
