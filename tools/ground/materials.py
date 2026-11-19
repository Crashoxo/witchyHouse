"""
路面材質（全圖大小的紋理，畫好後再用遮罩挖出要的部分）：石板、鋪石、泥土、水、巧克力磚。

全部在美術解析度、只用給定色盤作畫。
"""
import numpy as np

from common import fnoise


def _shade_pick(rng, n, weights):
    return rng.choice(len(weights), size=n, p=np.array(weights) / np.sum(weights))


def cobble(h, w, rng, P, row_h=(4, 5), stone_w=(4, 8), hi_frac=0.6):
    """不規則長短的石塊，一列一列錯縫排。
    P: dict(stones=[3~4 色], mortar, deep, hi)。回傳 (rgb, idmap)。"""
    rgb = np.zeros((h, w, 3), np.uint8)
    sid = np.zeros((h, w), np.int32)
    tone_n = fnoise(h, w, 20, rng)          # 大範圍的明暗（有些地方石頭整體偏亮/偏暗）
    y = 0
    k = 1
    stones = np.array(P['stones'])
    while y < h:
        rh = int(rng.integers(row_h[0], row_h[1] + 1))
        x = -int(rng.integers(0, stone_w[1]))
        while x < w:
            sw = int(rng.integers(stone_w[0], stone_w[1] + 1))
            y0, y1, x0, x1 = y, min(h, y + rh), max(0, x), min(w, x + sw)
            if x1 > x0 and y1 > y0:
                t = tone_n[min(h - 1, y0), min(w - 1, x0)]
                base = int(np.clip(round(rng.normal(1 + t * 0.6, 0.7)), 0, len(stones) - 1))
                rgb[y0:y1, x0:x1] = stones[base]
                sid[y0:y1, x0:x1] = k
                # 縫：右邊與下邊一格
                rgb[y0:y1, x1 - 1] = P['mortar']
                rgb[y1 - 1, x0:x1] = P['mortar']
                # 左上亮邊（不是每顆都有）
                if rng.random() < hi_frac and y1 - y0 > 2 and x1 - x0 > 2:
                    hc = stones[min(len(stones) - 1, base + 1)] if base + 1 < len(stones) else P['hi']
                    rgb[y0, x0:x1 - 1] = hc
                # 右下角的陰影點
                if rng.random() < 0.5 and y1 - y0 > 2:
                    rgb[y1 - 2, x1 - 2] = P['deep'] if rng.random() < 0.3 else P['mortar']
                k += 1
            x += sw
        y += rh
    return rgb, sid


def stones(h, w, rng, P, spacing=6.0, jitter=0.8, squash=1.0, hi_frac=1.0):
    """圓潤的石塊（Voronoi）：每個像素歸給最近的種子點 → 一顆顆不規則的石頭。
    縫＝相鄰像素屬於不同石頭；石頭左上緣亮一階、右下緣暗一階（光從左上來）。
    P: dict(stones=[深→亮 3~4 色], mortar, deep, hi)。squash>1 讓石頭橫向扁一點。"""
    gy, gx = int(h / spacing) + 3, int(w / (spacing * squash)) + 3
    py = (np.arange(gy)[:, None] - 1 + 0.5 + (rng.random((gy, gx)) - 0.5) * jitter) * spacing
    px = (np.arange(gx)[None, :] - 1 + 0.5 + (rng.random((gy, gx)) - 0.5) * jitter) * spacing * squash
    yy, xx = np.mgrid[0:h, 0:w]
    cy = (yy / spacing).astype(int) + 1
    cx = (xx / (spacing * squash)).astype(int) + 1
    best = np.full((h, w), 1e9)
    sid = np.zeros((h, w), np.int32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ny = np.clip(cy + dy, 0, gy - 1)
            nx = np.clip(cx + dx, 0, gx - 1)
            d = ((yy + 0.5 - py[ny, nx]) ** 2 + ((xx + 0.5 - px[ny, nx]) / squash) ** 2)
            m = d < best
            best[m] = d[m]
            sid[m] = (ny * gx + nx)[m]
    S = np.array(P['stones'])
    tone_n = fnoise(h, w, 22, rng)
    n_ids = gy * gx
    base = np.clip(np.round(rng.normal(1.2, 0.75, n_ids)), 0, len(S) - 1).astype(int)
    # 區域明暗：在種子點取大範圍雜訊
    sy = np.clip(py.ravel().astype(int), 0, h - 1)
    sx = np.clip(px.ravel().astype(int), 0, w - 1)
    base = np.clip(base + np.round(tone_n[sy, sx] * 0.6).astype(int), 0, len(S) - 1)
    lv = base[sid]
    up = np.roll(sid, 1, 0) != sid
    left = np.roll(sid, 1, 1) != sid
    down = np.roll(sid, -1, 0) != sid
    right = np.roll(sid, -1, 1) != sid
    rgb = S[lv].copy()
    hl = (up | left) & ~(down | right)
    if hi_frac < 1:
        hl &= (rng.random(n_ids) < hi_frac)[sid]
    lit = np.clip(lv + 1, 0, len(S) - 1)
    rgb[hl] = np.where((lv[hl] + 1 >= len(S))[:, None], P['hi'], S[lit[hl]])
    sh = (down | right) & ~(up | left)
    rgb[sh] = S[np.clip(lv[sh] - 1, 0, None)]
    mortar = down | right
    rgb[mortar] = P['mortar']
    corner = mortar & (np.roll(mortar, -1, 0) & np.roll(mortar, -1, 1))
    rgb[corner] = P['deep']
    return rgb, sid


def pavers(h, w, rng, P, slab=(10, 7)):
    """廣場大方石：整齊錯縫，每塊有自己的色調，偶爾裂紋。"""
    rgb = np.zeros((h, w, 3), np.uint8)
    sw, sh = slab
    stones = np.array(P['stones'])
    tone_n = fnoise(h, w, 30, rng)
    for r, y in enumerate(range(0, h, sh)):
        off = (sw // 2) * (r % 2)
        for x in range(-off, w, sw):
            y0, y1, x0, x1 = y, min(h, y + sh), max(0, x), min(w, x + sw)
            if x1 <= x0:
                continue
            t = tone_n[min(h - 1, y0), min(w - 1, x0)]
            base = int(np.clip(round(rng.normal(1 + t * 0.5, 0.6)), 0, len(stones) - 1))
            rgb[y0:y1, x0:x1] = stones[base]
            rgb[y0:y1, x1 - 1] = P['mortar']
            rgb[y1 - 1, x0:x1] = P['mortar']
            if y1 - y0 > 2:
                rgb[y0, x0:x1 - 1] = stones[min(len(stones) - 1, base + 1)] if base + 1 < len(stones) else P['hi']
            if rng.random() < 0.12 and x1 - x0 > 4 and y1 - y0 > 4:     # 裂紋
                cx = int(rng.integers(x0 + 1, x1 - 2))
                for yy in range(y0 + 1, y1 - 1):
                    rgb[yy, min(x1 - 2, max(x0, cx))] = P['mortar']
                    cx += int(rng.integers(-1, 2))
    return rgb


def dirt(h, w, rng, P, aniso=1.0):
    """泥土：色階斑塊 + 細碎深點/亮點。P: dict(levels=[深→亮 4~5 色], speck_dark, speck_light)。"""
    L = np.array(P['levels'])
    n = 0.75 * fnoise(h, w, 9, rng, aniso) + 0.35 * fnoise(h, w, 2.5, rng, aniso)
    idx = np.full((h, w), len(L) // 2)
    idx = idx + (n > 0.6) - (n < -0.7) - (n < -1.6)
    idx = np.clip(idx, 0, len(L) - 1)
    rgb = L[idx].copy()
    r = rng.random((h, w))
    rgb[r < 0.012] = P['speck_dark']
    rgb[(r > 0.990)] = P['speck_light']
    return rgb


def water(h, w, rng, mask, P, shore_dist):
    """水：依離岸距離分深淺，加短橫向的高光波紋。shore_dist：水內每格離岸幾格（美術像素）。"""
    rgb = np.zeros((h, w, 3), np.uint8)
    n = fnoise(h, w, 6, rng, aniso=2.5)
    d = shore_dist + 1.2 * n
    rgb[:] = P['deep']
    rgb[d < 9] = P['mid']
    rgb[d < 3.5] = P['shallow']
    # 波紋：在 mid/deep 區撒短橫線
    cnt = int(mask.sum() / 70)
    ys = rng.integers(0, h, cnt * 3)
    xs = rng.integers(0, w, cnt * 3)
    placed = 0
    for y, x in zip(ys, xs):
        if placed >= cnt:
            break
        if not mask[y, x] or shore_dist[y, x] < 4:
            continue
        L = int(rng.integers(2, 5))
        c = P['hi'] if rng.random() < 0.55 else P['light']
        for i in range(L):
            if x + i < w and mask[y, x + i] and shore_dist[y, x + i] >= 3:
                rgb[y, x + i] = c
        if rng.random() < 0.5 and y + 1 < h and x + L + 1 < w and mask[y + 1, x + L]:
            rgb[y + 1, x + L] = P['light']
        placed += 1
    return rgb


def choco_tiles(h, w, P, tile=12, off_x=0, off_y=0):
    """巧克力磚（像一片片巧克力）：每塊有亮的左上斜邊、暗的右下斜邊、中間平面。
    P: dict(face, hi, lo, groove, shine)。"""
    rgb = np.zeros((h, w, 3), np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    ly = (yy - off_y) % tile
    lx = (xx - off_x) % tile
    rgb[:] = P['face']
    bev = 2
    top = (ly < bev) & (lx >= ly) & (lx < tile - 1 - ly)
    left = (lx < bev) & (ly >= lx) & (ly < tile - 1 - lx)
    bot = (ly >= tile - 1 - bev) & ~top & ~left
    right = (lx >= tile - 1 - bev) & ~top & ~left & ~bot
    rgb[top | left] = P['hi']
    rgb[bot | right] = P['lo']
    groove = (ly == tile - 1) | (lx == tile - 1)
    rgb[groove] = P['groove']
    # 每塊左上一點高光
    rgb[(ly == bev) & (lx == bev)] = P['shine']
    rgb[(ly == bev) & (lx == bev + 1)] = P['shine']
    return rgb
