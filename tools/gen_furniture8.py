# -*- coding: utf-8 -*-
"""
店裡與家裡共用的家具／裝飾 —— 細畫像素版（標竿：女巫走路圖 witch8、魔女房間 brew8）。程式畫、固定結果、可重跑。

    python tools/gen_furniture8.py                   # 畫全部 → Assets/Resources/furniture8/、decor8/，寫 Data/FurnitureArt8.cs
    python tools/gen_furniture8.py --preview DIR     # 另外輸出預覽：新舊對照、陳列桌擺商品、燈（夜晚／店裡）、整間店、家裡日夜
    python tools/gen_furniture8.py --out DIR         # 圖寫到 DIR/furniture8、DIR/decor8（不碰專案、不寫 C#；調圖用）
    python tools/gen_furniture8.py --only a,b        # 只畫這幾張（只寫圖，不寫 C#）
    python tools/gen_furniture8.py --restore         # 刪掉 furniture8/、decor8/，FurnitureArt8.cs 清空 → 遊戲退回舊圖

── 跟其他產生器的關係 ─────────────────────────────────────────
  · 畫法整套 import tools/gen_brew_room8.py（Scene 光線求交、Box／Cyl／HCyl／Ell、材質、色盤、外輪廓 #2a1b24），
    家裡跟店裡的家具才會是同一套。這支另外加了 SDF 立體（拱頂、尖頂、圓角、花瓶旋轉體）與幾組新色盤（只加不改）。
  · 舊圖（furniture/ 的 ×3 粗像素、decor/ 的厚塗）一張都沒動；tools/gen_shop_art.py 與它的 ShopDisplaySlots.cs 照舊是舊圖的資料。
  · 開關 GameArt.UsePixelFurniture：開著先讀 furniture8/、decor8/，缺哪張就退回舊資料夾那張（逐張）。
    陳列位／實心範圍／光暈點在 Data/FurnitureArt8.cs，靠「圖的尺寸」認是不是細畫版 —— 對不上就自動用舊表。

── 座標 ─────────────────────────────────────────────────────────
  吃格子的家具：一格＝32 uv（＝店裡 64×32 的等距菱形）；u 沿 gx（畫面右下）、v 沿 gy（畫面左下）、z 往上；
  佔地 u∈[0,32W]、v∈[0,32H]；貨架／書櫃／鐘背板貼 u=0（左後牆）、開口朝 +u。
  錨點＝圖的正下方中央＝佔地前角（RoomLayout.AnchorPos 照舊）；前角在偶數像素上，邏輯像素 ×2 的格線跟世界對齊。
  裝飾：在一塊小地面上畫，錨點＝中心的 x、圖的最底（自由座標的落腳點）。地毯平貼（排序 -9000）。
  ⚠️ 半透明的接地影子不算實心：穿牆判斷用的實心範圍只量 alpha 255。
"""
import math
import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import numpy as np                       # noqa: E402
from PIL import Image                    # noqa: E402

import gen_brew_room8 as b8              # noqa: E402
from gen_brew_room8 import (             # noqa: E402,F401
    Scene, Prim, Box, Cyl, HCyl, Ell, Ctx,
    wood_mat, solid_mat, metal_mat, cloth_mat, tone_idx, pick, bevel, face_a, shade,
    h32, hs, fbm, vnoise, blank, put, rect, add_outline, pad, from_ascii, ball, flame_img, candle_img,
    bottle_img, jar_img, flask_img, heart_bottle, star_img, star_mask,
    F_TOP, F_U, F_V, F_SIDE, F_CAP, F_BB, LIGHT, OUT, ramp, hexrgb,
    WOOD, TIMBER, FLOOR, PLASTER, STONE, WSTONE, DSTONE, PURPLE, PLUM, GOLD, BLUE, TEAL, PINK, ROSE, IRON,
    COPPER, BRASS, LINEN, LEAF, TERRA, FIRE, GLASS, CREAM, STAR,
)

CELL = 32
SHADOW = (30, 14, 30, 86)

# 店裡追加的材質（只加，不改 brew8 的任何色盤）
GWOOD = ramp('#231d24', '#342a2f', '#473a3c', '#5c4c4a', '#716058', '#867468', '#9a897a', '#ae9e8d', '#c2b4a2', '#d6cbbb')
MAHOG = ramp('#220c18', '#33121f', '#481a27', '#5f2430', '#773038', '#8f3f40', '#a6524a', '#bb6958', '#cf8670', '#e2aa90')
SAGE = ramp('#1c2b2a', '#243a35', '#2f4b42', '#3c5e50', '#4b725f', '#5e8770', '#769b83', '#91b199', '#afc8b2', '#d0e1cd')
CREAMW = ramp('#5a4652', '#75606a', '#917c80', '#ab9792', '#c3b1a2', '#d7c7b4', '#e7dbc8', '#f3ecdc', '#fbf7ee', '#ffffff')
PUMPKIN = ramp('#4a1a10', '#6e2a12', '#963c14', '#bc5418', '#d86e1e', '#ec8c2c', '#f6ac48', '#fcca74', '#ffe4a8')
MOSS = ramp('#1a2a1e', '#223826', '#2b4a2e', '#365e36', '#43733e', '#548a46', '#6aa052', '#86b664', '#a6cc7c')
LILAC = ramp('#2a1e3a', '#3a2a50', '#4e3a68', '#644c82', '#7a609a', '#9278b2', '#ab94c8', '#c4b2dc', '#ddd0ee', '#f2ecfa')
SKYB = ramp('#1a2a44', '#22385a', '#2c4a72', '#385e8a', '#4874a2', '#5c8cb8', '#78a6cc', '#98c0de', '#bcd8ec', '#e2f0fa')
CHERRY = ramp('#3a0e18', '#5a1422', '#7c1c2c', '#9c2636', '#ba3442', '#d24a52', '#e46a6a', '#f29088', '#fab8ac')
SUN = ramp('#5a3a08', '#7c520c', '#a06c12', '#c48a1a', '#e0a826', '#f2c43a', '#fcdc5c', '#fff08e', '#fffac8')


# ═══════════════════════════════ SDF 立體（拱頂、尖頂、圓角等等）═══════════════════════════════

SQ3 = math.sqrt(3.0)


class SDF(Prim):
    """任意形狀：f(u,v,z) 是有號距離（裡面負、Lipschitz ≤ 1），bounds＝包住它的盒子。
    視線 (U+t, V+t, t) 從最靠鏡頭那端往回做 sphere tracing，法線用中央差分。"""
    def __init__(self, f, bounds, mat, steps=160, safety=0.5, **kw):
        super().__init__(mat, **kw)
        self.f, self.bb, self.steps, self.safety = f, bounds, steps, safety

    def hit(self, U, V):
        u0, u1, v0, v1, z0, z1 = self.bb
        thi = np.minimum(np.minimum(u1 - U, v1 - V), np.full(U.shape, float(z1)))
        tlo = np.maximum(np.maximum(u0 - U, v0 - V), np.full(U.shape, float(z0)))
        active = thi >= tlo
        t = thi.copy()
        hit = np.zeros(U.shape, bool)
        for _ in range(self.steps):
            if not active.any():
                break
            d = self.f(U + t, V + t, t)
            nh = active & (d <= 0.02)
            hit |= nh
            active &= ~nh
            t = np.where(active, t - np.maximum(d / SQ3 * self.safety, 0.04), t)
            active &= t >= tlo
        uu, vv, zz = U + t, V + t, t
        e = 0.35
        f = self.f
        gx = f(uu + e, vv, zz) - f(uu - e, vv, zz)
        gy = f(uu, vv + e, zz) - f(uu, vv - e, zz)
        gz = f(uu, vv, zz + e) - f(uu, vv, zz - e)
        n = np.sqrt(gx * gx + gy * gy + gz * gz) + 1e-9
        nx, ny, nz = gx / n, gy / n, gz / n
        face = np.where(nz > 0.8, F_TOP, np.where((nx > 0.8), F_U, np.where(ny > 0.8, F_V, F_SIDE)))
        return np.where(hit, t, -np.inf), face, nx, ny, nz


# 2D／3D 距離小工具（numpy）
def sd_box2(a, b, ca, cb, ha, hb, r=0.0):
    qa, qb = np.abs(a - ca) - (ha - r), np.abs(b - cb) - (hb - r)
    return np.hypot(np.maximum(qa, 0), np.maximum(qb, 0)) + np.minimum(np.maximum(qa, qb), 0) - r


def sd_circle2(a, b, ca, cb, r):
    return np.hypot(a - ca, b - cb) - r


def sd_slab(x, lo, hi):
    return np.maximum(lo - x, x - hi)


def sd_arch2(v, z, v0, v1, z0, z1, rise):
    """拱形：矩形 [v0,v1]×[z0,z1] ＋上面一個半橢圓（高 rise）。"""
    hw = (v1 - v0) / 2.0
    vm = (v0 + v1) / 2.0
    rect_ = sd_box2(v, z, vm, (z0 + z1) / 2, hw, (z1 - z0) / 2)
    ell = (np.hypot((v - vm) / hw, (z - z1) / max(rise, 0.1)) - 1.0) * min(hw, rise)
    ell = np.maximum(ell, z1 - z)
    return np.minimum(rect_, ell)


def sd_peak2(v, z, v0, v1, z0, z1, rise):
    """尖頂：矩形＋上面一個三角形。"""
    vm = (v0 + v1) / 2.0
    hw = (v1 - v0) / 2.0
    rect_ = sd_box2(v, z, vm, (z0 + z1) / 2, hw, (z1 - z0) / 2)
    L = math.hypot(hw, rise)
    tri = np.maximum(((z - z1) * hw + np.abs(v - vm) * rise - hw * rise) / L, z1 - z)
    return np.minimum(rect_, tri)


# ═══════════════════════════════ 場景與裁切 ═══════════════════════════════

class Art:
    def __init__(self, pid, img, slots=(), lights=(), kind='furniture'):
        self.id, self.img, self.slots, self.lights, self.kind = pid, img, list(slots), list(lights), kind

    def bounds(self):
        """(ImgW, ImgH, X0, Y0, X1, Y1)：實心（alpha 255，不含半透明影子）範圍，y 從圖底往上量。"""
        a = self.img[..., 3] == 255
        h, w = a.shape
        ys, xs = np.nonzero(a)
        return w, h, int(xs.min()), h - 1 - int(ys.max()), int(xs.max()) + 1, h - int(ys.min())


def grid_scene(fw, fh, zmax=200, margin=20):
    du, dv = fw * CELL, fh * CELL
    W = du + dv + 2 * margin
    H = zmax + (du + dv) // 2 + 2 * margin
    ox, oy = dv + margin, zmax + margin
    sc = Scene(W, H, ox, oy, 0, 0)
    sc.du, sc.dv = du, dv
    sc.anchor = (ox + du - dv, oy + (du + dv) // 2)
    sc.slots, sc.lights = [], []
    return sc


def free_scene(r, zmax=160, margin=16):
    """裝飾（自由座標）：在一塊 2r×2r 的小地面上畫，中心 (r, r)。錨點＝中心的 x、圖的最底。"""
    d = int(2 * r)
    W = 2 * d + 2 * margin
    H = zmax + d + 2 * margin
    sc = Scene(W, H, d + margin, zmax + margin, 0, 0)
    sc.du = sc.dv = d
    sc.c = r
    sc.anchor = None
    sc.slots, sc.lights = [], []
    return sc


def to_px(sc, u, v, z):
    return sc.ox + u - v, sc.oy + (u + v) / 2.0 - z


def crop(sc, img, pid, kind='furniture'):
    a = img[..., 3]
    ys, xs = np.nonzero(a > 0)
    if sc.anchor is not None:
        fx, fy = sc.anchor
        solid_below = (img[fy:, :, 3] == 255).any()
        if solid_below:
            n = int((img[fy:, :, 3] == 255).sum())
            print('  ⚠️ %s：有 %d 個實心像素畫到佔地前角底下（裁掉）' % (pid, n))
    else:
        fx = int(round(sc.ox + 0))      # 中心 (c,c) 的 x ＝ ox
        fy = int(ys.max()) + 1
        fy += fy % 2
    half = max(fx - int(xs.min()), int(xs.max()) + 1 - fx)
    half += half % 2
    y0 = int(ys.min())
    y0 -= y0 % 2
    out = np.zeros((fy - y0, 2 * half, 4), np.uint8)
    sx0 = fx - half
    a0, a1 = max(0, sx0), min(img.shape[1], fx + half)
    out[:, a0 - sx0:a1 - sx0] = img[y0:fy, a0:a1]
    slots = []
    for (u, v, z, mw, mh, row) in sc.slots:
        x, y = to_px(sc, u, v, z)
        slots.append((round(x - fx, 1), round(fy - y, 1), round(mw, 1), round(mh, 1), row))
    lights = []
    for (u, v, z) in sc.lights:
        x, y = to_px(sc, u, v, z)
        lights.append((round(x - fx, 1), round(fy - y, 1)))
    return Art(pid, out, slots, lights, kind)


def render(sc, pid, kind='furniture', shadow=SHADOW):
    img = sc.finish(shadow_rgba=shadow)
    return crop(sc, img, pid, kind)


# ═══════════════════════════════ 材質小工具 ═══════════════════════════════

def wbox(sc, u0, u1, v0, v1, z0, z1, rmp=WOOD, base=5, seed=1, grain='auto', plank=0, edge=True, ao=None):
    b = (u0, u1, v0, v1, z0, z1)
    m = wood_mat(rmp, base, grain_axis=grain, bevel_b=b, seed=seed, plank=plank)
    if ao is not None:
        inner = m

        def m(c, inner=inner):
            col = inner(c)
            k = ao(c)
            if k is None:
                return col
            return np.where((k > 0)[:, None], (col.astype(np.int32) * (100 - 22) // 100).astype(np.uint8), col)
    sc.add(Box(*b, m, edge=edge))


def sbox(sc, u0, u1, v0, v1, z0, z1, rmp, base, k=3.6, extra=None, edge=True):
    b = (u0, u1, v0, v1, z0, z1)
    sc.add(Box(*b, solid_mat(rmp, base, k=k, b=b, extra=extra), edge=edge))


def shadow_rect(sc, u0, u1, v0, v1, g=2.0):
    sc.ground_shadow(lambda U, V: (U > u0 - g + 2) & (U < u1 + g + 1) & (V > v0 - g + 1) & (V < v1 + g + 1))


def shadow_round(sc, cu, cv, r, rv=None):
    rv = rv or r
    sc.ground_shadow(lambda U, V: ((U - cu - 2) / r) ** 2 + ((V - cv - 1) / rv) ** 2 < 1)


def darker(col, k=0.78):
    return (col.astype(np.int32) * int(k * 100) // 100).astype(np.uint8)


def glow_px(sc, u, v, z, rmp=FIRE):
    sc.fine_px(u, v, z, rmp[-1])


def sprite(sc, img, u, v, z, anchor=(0.5, 1.0), depth=None, edge=True, outline=True, ocol=None):
    if outline:
        img = add_outline(pad(img, 1), color=OUT if ocol is None else ocol)
    sc.sprite(img, u, v, z, anchor=anchor, depth=depth, edge=edge)



def wmat(rmp=WOOD, base=5, b=None, seed=1, grain='auto', plank=0, k=3.6, ao=None, deco=None):
    """木頭材質（同 brew8 的 wood_mat，多兩個鉤子：ao(c)→色階位移、deco(c, idx, col)→最後改色）。"""
    def mat(c):
        idx = tone_idx(c, base, k)
        if b is not None:
            idx = idx + bevel(c, b).astype(int)
        a = face_a(c)
        if grain == 'auto' and b is not None:
            u0, u1, v0, v1, z0, z1 = b
            hz = z1 - z0
            zg = (((c.face == F_U) & (hz > (v1 - v0) * 1.2)) | ((c.face == F_V) & (hz > (u1 - u0) * 1.2)))
        else:
            zg = np.full(c.u.shape, grain == 'z')
        zg = zg & (c.face != F_TOP)
        along = np.where(zg, c.z, a)
        across = np.where(zg, a, np.where(c.face == F_TOP, (c.u + c.v) * 0.5, c.z))
        g = h32(np.floor(across / 1.6), np.floor(along / 9.0 + h32(np.floor(across / 1.6), seed) * 5), seed)
        idx = np.where(g > 0.86, idx - 1, idx)
        idx = np.where(g < 0.05, idx + 1, idx)
        if plank:
            pk = np.floor(across / plank)
            fa = across - pk * plank
            idx = np.where(fa < 1.1, idx - 1, idx)
        if ao is not None:
            idx = idx + ao(c)
        col = pick(rmp, idx)
        if deco is not None:
            col = deco(c, idx, col)
        return col
    return mat


def box(sc, b, rmp=WOOD, base=5, seed=1, edge=True, **kw):
    sc.add(Box(*b, wmat(rmp, base, b=b, seed=seed, **kw), edge=edge))


def sdf_mat(rmp, base, k=3.4, ao=None, deco=None, seed=3, grain=True):
    def mat(c):
        idx = tone_idx(c, base, k)
        if grain:
            g = h32(np.floor((c.u + c.v) / 1.6), np.floor(c.z / 9.0), seed)
            idx = np.where(g > 0.88, idx - 1, idx)
        if ao is not None:
            idx = idx + ao(c)
        col = pick(rmp, idx)
        if deco is not None:
            col = deco(c, idx, col)
        return col
    return mat


# ═══════════════════════════════ 貨架參數 ═══════════════════════════════
#   dep    ：佔地深度（格，跟 Furniture.cs 一致）
#   side   ：'panel' 實心側板 ／ 'posts' 四根立柱
#   back   ：'solid' ／ 'none' ／ 'slats' ／ 'cross' ／ 'rails'
#   shape  ：'rect' ／ 'round' ／ 'arch' ／ 'peak'（rise＝頂上多高）
#   top    ：'flat' ／ 'flush' ／ 'crown' ／ 'plank' ／ 'none'
#   extra  ：'crest' ／ 'scallop' ／ 'crate' ／ 'inset'
#   lower  ：'drawer1' ／ 'drawers6' ／ 'doors' ／ 'deep'
#   levels ：每片層板的底 z；Hs＝本體高；D＝本體厚（u）；pt＝側板厚；T＝層板厚
#   orn    ：頂上的小裝飾 'star' ／ 'moon' ／ 'heart' ／ 'shroom' ／ 'candle' ／ 'plant' ／ 'books' ／ 'cat'

SHELVES = {
    'shelf_narrow':  dict(dep=3, side='posts', back='none', D=15, pt=3, T=3, levels=[8, 44, 80], Hs=114, top='flat',
                          rails=True, orn='plant'),
    'shelf_tall':    dict(dep=2, side='panel', back='solid', D=17, pt=4, levels=[6, 38, 70, 102], Hs=132, top='crown',
                          plinth=5, orn='candle'),
    'shelf_cross':   dict(dep=3, side='posts', back='cross', D=17, pt=4, levels=[7, 43, 79], Hs=114, top='flat',
                          orn='shroom'),
    'shelf_plank':   dict(dep=3, side='posts', back='none', D=19, pt=5, T=5, levels=[6, 42, 78], Hs=114, top='plank',
                          wood=GWOOD, overhang=5, orn='books'),
    'shelf_box':     dict(dep=3, side='panel', back='solid', D=18, pt=6, levels=[7, 43, 79], Hs=116, top='flush',
                          extra='crate', orn=None),
    'shelf_slat':    dict(dep=3, side='posts', back='slats', D=17, pt=4, levels=[7, 43, 79], Hs=114, top='flat',
                          orn='plant2'),
    'shelf_back':    dict(dep=3, side='panel', back='solid', D=18, pt=4, levels=[9, 45, 81], Hs=116, top='crown',
                          plinth=6, extra='inset', seams=True, orn='moon'),
    'shelf_round':   dict(dep=3, side='panel', back='solid', D=18, pt=5, levels=[9, 44, 79], Hs=118, top='none',
                          shape='round', r=14, orn='cat'),
    'shelf_deep':    dict(dep=3, side='panel', back='solid', D=16, pt=4, levels=[40, 77], Hs=114, top='flat',
                          lower='deep', lowD=27, lowH=40, orn='heart'),
    'shelf_curve':   dict(dep=3, side='posts', back='rails', D=16, pt=4, levels=[7, 42, 77], Hs=112, top='flat',
                          extra='crest', finials=True, orn=None),
    'shelf_two':     dict(dep=3, side='panel', back='solid', D=18, pt=4, levels=[36, 74], Hs=112, top='flat',
                          lower='drawer1', plinth=4, orn='candle'),
    'shelf_scallop': dict(dep=3, side='panel', back='solid', D=18, pt=4, levels=[7, 40, 73], Hs=114, top='flat',
                          extra='scallop', orn='star'),
    'shelf_peak':    dict(dep=3, side='panel', back='solid', D=18, pt=4, levels=[7, 38, 69], Hs=100, top='none',
                          shape='peak', rise=28, orn=None, wood=WOOD),
    'shelf_arch':    dict(dep=3, side='panel', back='solid', D=18, pt=6, levels=[7, 39, 71], Hs=100, top='none',
                          shape='arch', rise=28, wood=MAHOG, orn=None),
    'shelf_cabinet': dict(dep=3, side='panel', back='solid', D=18, pt=4, levels=[42, 78], Hs=112, top='crown',
                          lower='doors', plinth=4, orn='shroom'),
    'shelf_drawer':  dict(dep=3, side='panel', back='solid', D=19, pt=5, levels=[44, 80], Hs=114, top='crown',
                          lower='drawers6', feet='bun', wood=MAHOG, orn='books'),
}

SLOT_W = 22.0
SLOT_H_MAX = 26.0
SLOT_FRONT = 0.6
BT = 3                      # 背板厚


def capsule2(a, b, a0, b0, a1, b1, r):
    da, db = a1 - a0, b1 - b0
    L2 = da * da + db * db
    t = np.clip(((a - a0) * da + (b - b0) * db) / L2, 0, 1)
    return np.hypot(a - (a0 + da * t), b - (b0 + db * t)) - r


def ornament(sc, kind, u, v, z, seed=0):
    """頂上的小擺飾（女巫店的可愛小東西）。"""
    if kind is None:
        return
    if kind == 'star':
        img = from_ascii(['...a...', '..aba..', 'aabbbaa', '.abbba.', '.ab.ba.', 'a.....a'],
                         {'a': GOLD[4], 'b': GOLD[6]})
        img[2, 3, :3] = GOLD[7]
        sc.add(Cyl(u, v, 2.6, z, z + 2, metal_mat(GOLD, 4)))
        sprite(sc, img, u, v, z + 2, depth=(u + 1, v + 1))
    elif kind == 'moon':
        img = from_ascii(['..aab.', '.ab...', 'ab....', 'ab....', 'ab....', '.ab...', '..aabb'],
                         {'a': GOLD[5], 'b': GOLD[6]})
        sc.add(Cyl(u, v, 3, z, z + 2, metal_mat(BRASS, 4)))
        sprite(sc, img, u, v, z + 2, depth=(u + 1, v + 1))
    elif kind == 'heart':
        img = from_ascii(['.aa.aa.', 'abbabba', 'abbbbba', '.abbba.', '..aba..', '...a...'],
                         {'a': PINK[4], 'b': PINK[6]})
        img[1, 1, :3] = PINK[8]
        sc.add(Cyl(u, v, 3.2, z, z + 3, solid_mat(TERRA, 5, k=3)))
        sprite(sc, img, u, v, z + 3, depth=(u + 1, v + 1))
    elif kind == 'shroom':
        for (du_, dv_, h, r, rmp) in ((0, 0, 6, 4.6, ROSE), (3, 5, 3.5, 3.0, PUMPKIN), (-2, 6, 2.5, 2.2, ROSE)):
            sc.add(Cyl(u + du_, v + dv_, 1.1, z, z + h, solid_mat(LINEN, 7, k=2.0)))

            def cap(c, cu=u + du_, cv=v + dv_, rmp=rmp):
                idx = tone_idx(c, 5, 3.2)
                dot = (h32(np.floor((c.u - cu) * 1.1), np.floor((c.v - cv) * 1.1), np.floor(c.z * 1.1), 5) > 0.74) & (c.nz > 0.35)
                return np.where(dot[:, None], LINEN[9], pick(rmp, idx + 1))
            sc.add(Ell(u + du_, v + dv_, z + h, r, r, r * 0.7, cap, zmin=z + h - 0.4))
    elif kind == 'candle':
        sc.add(Cyl(u, v, 4.0, z, z + 1.5, metal_mat(BRASS, 5)))
        sprite(sc, candle_img(7, 0, wax=LINEN, flame_h=4), u, v, z + 1.5, depth=(u, v), outline=False)
        sc.lights.append((u, v, z + 12))
    elif kind in ('plant', 'plant2'):
        sc.add(Cyl(u, v, 4.5, z, z + 7, solid_mat(TERRA, 5, k=3.4)))
        sc.add(Cyl(u, v, 5.2, z + 6, z + 8, solid_mat(TERRA, 6, k=3.4), r_in=4.2))
        sc.add(Cyl(u, v, 4.2, z, z + 7.6, solid_mat(WOOD, 1, k=1.0)))
        img = blank(15, 14) if kind == 'plant' else blank(13, 22)
        if kind == 'plant':
            # 垂藤：一顆圓葉叢＋兩條往下垂的藤
            img = blank(17, 22)
            for (lx, ly, r) in ((8, 5, 3.2), (5, 6, 2.6), (11, 6, 2.6), (8, 3, 2.4)):
                ball(img, lx, ly, r, r * 0.8, LEAF, 5, spec=False)
            for (x0, ln, ph) in ((3, 14, 0.0), (13, 18, 1.3)):
                for y in range(7, 7 + ln):
                    x = int(round(x0 + math.sin(y * 0.5 + ph) * 1.0))
                    put(img, x, y, LEAF[3])
                    if y % 3 == 0:
                        put(img, x - 1, y, LEAF[6])
                        put(img, x + 1, y + 1, LEAF[5])
        else:
            for k_ in range(5):
                x0 = 6 + (k_ - 2) * 1.6
                for y in range(4, 22):
                    t = (21 - y) / 17.0
                    x = int(round(x0 + (k_ - 2) * t * 2.2))
                    put(img, x, y, LEAF[4 + (y % 3 == 0)])
                put(img, int(round(x0 + (k_ - 2) * 2.2)), 3, LEAF[7])
        sprite(sc, img, u, v, z + 7, anchor=(0.5, 0.42 if kind == 'plant' else 0.92), depth=(u + 6, v + 6), ocol=LEAF[0])
    elif kind == 'books':
        for k_, (hh, rmp) in enumerate(((3, ROSE), (3, TEAL), (2.5, GOLD))):
            z0 = z + k_ * 3
            sbox(sc, u - 6 + k_, u + 6 - k_, v - 7 + k_, v + 7 - k_, z0, z0 + hh, rmp, 5)
        sc.add(Cyl(u, v - 1, 2.4, z + 8.5, z + 11, solid_mat(GLASS, 5, k=3)))
        sc.add(Ell(u, v - 1, z + 13, 2.8, 2.8, 2.6, solid_mat(PURPLE, 6, k=3)))
    elif kind == 'cat':
        # 睡著的黑貓（立牌）
        img = from_ascii(['.a....a.......', 'aba..aba......', 'abbbbbba......', 'abcbbcbbaaaa..',
                          'abbbbbbbbbbbaa', '.abbbbbbbbbbba', '..aaaabbbbbbba', '......aaaaaaa.'],
                         {'a': IRON[1], 'b': IRON[4], 'c': GOLD[6]})
        img[3, 2, :3] = GOLD[6]
        img[3, 5, :3] = GOLD[6]
        img[1, 1, :3] = PINK[5]
        img[1, 6, :3] = PINK[5]
        sprite(sc, img, u, v, z, depth=(u + 2, v + 2))


def draw_shelf(sid):
    st = SHELVES[sid]
    dep = st['dep']
    sc = grid_scene(1, dep, zmax=190)
    DV = CELL * dep
    v0, v1 = 3, DV - 3
    D, pt = st['D'], st['pt']
    T = st.get('T', 3)
    rmp = st.get('wood', WOOD)
    Hs, levels = st['Hs'], st['levels']
    shape = st.get('shape', 'rect')
    side, back = st['side'], st['back']
    vi0, vi1 = (v0 + pt, v1 - pt) if side == 'panel' else (v0, v1)
    lowD = st.get('lowD', D)
    shadow_rect(sc, 0, max(D, lowD), v0, v1, 2)

    # 架子裡面的陰影：越往裡（u 小）越暗、層板下緣一條陰影
    lv_tops = [z + T for z in levels]

    lowH = st.get('lowH', 0)
    deep_lower = st.get('lower') == 'deep'
    floor_z = 2 if deep_lower else levels[0]

    def ao(c):
        Dl = np.where(c.z < lowH, lowD, D) if deep_lower else D
        inside = (c.u < Dl - 0.6) & (c.v > vi0 - 0.6) & (c.v < vi1 + 0.6) & (c.z > floor_z + T - 0.5) & (c.z < Hs + 0.1)
        deep = np.clip((Dl - c.u) / Dl, 0, 1)
        d = -np.round(0.6 + deep * 2.4).astype(int)
        under = np.zeros(c.u.shape, bool)
        for zt in levels[1:] + ([Hs] if shape == 'rect' else []) + ([lowH - 3, levels[0]] if deep_lower else []):
            under |= (c.z < zt) & (c.z > zt - 5) & ((c.face == F_U) | (c.face == F_V))
        d = d - under.astype(int)
        return np.where(inside, d, 0)

    plinth = st.get('plinth', 0)
    zbase = plinth

    # ── 本體 ──
    if shape == 'rect':
        if back == 'solid':
            seam = st.get('seams')

            def back_deco(c, idx, col):
                if seam:
                    s_ = (np.mod(c.v - v0, 8) < 0.9) & (c.face == F_U)
                    col = np.where(s_[:, None], pick(rmp, idx - 1), col)
                return col
            box(sc, (0, BT, v0, v1, zbase, Hs), rmp, 4, seed=11, ao=ao, deco=back_deco, grain='z')
        elif back == 'slats':
            for k in range(int((v1 - v0 - 2) // 7) + 1):
                vv = v0 + 2 + k * 7
                if vv + 4 > v1:
                    break
                box(sc, (0, BT, vv, vv + 4, zbase + 2, Hs), rmp, 4, seed=20 + k, ao=ao, grain='z')
        elif back == 'rails':
            for z in (levels[0] + 18, levels[1] + 18, levels[-1] + 20):
                if z + 3 < Hs:
                    box(sc, (0, BT, v0, v1, z, z + 3), rmp, 4, seed=int(z), ao=ao)
        elif back == 'cross':
            for (za, zb) in zip(levels, levels[1:] + [Hs]):
                zt = za + T
                f = (lambda zt=zt, zb=zb: lambda u, v, z: np.maximum(
                    sd_slab(u, 0, BT),
                    np.minimum(capsule2(v, z, v0 + 3, zt + 2, v1 - 3, zb - 2, 1.8),
                               capsule2(v, z, v0 + 3, zb - 2, v1 - 3, zt + 2, 1.8))))()
                sc.add(SDF(f, (0, BT, v0, v1, zt, zb), sdf_mat(rmp, 4, ao=ao)))
        # 側板／立柱
        if side == 'panel':
            ext = st.get('extra')

            def side_deco(c, idx, col):
                outer = c.face == F_V
                if ext == 'crate':
                    pl = (np.mod(c.z - zbase, 12) < 1.0) & (c.face != F_TOP)
                    col = np.where(pl[:, None], pick(rmp, idx - 1), col)
                    nail = outer & (np.abs(np.mod(c.z - zbase - 6, 12) - 0) < 1.0) & (np.abs(c.u - 3) < 1.0)
                    col = np.where(nail[:, None], IRON[6], col)
                if ext == 'inset':
                    fr = outer & (c.u > 3.5) & (c.u < D - 3.5) & (c.z > zbase + 5) & (c.z < Hs - 5)
                    ed = fr & ((c.u < 5) | (c.u > D - 5) | (c.z < zbase + 6.5) | (c.z > Hs - 6.5))
                    col = np.where(fr[:, None], pick(rmp, idx - 1), col)
                    col = np.where(ed[:, None], pick(rmp, idx + 1), col)
                return col
            box(sc, (0, D, v0, v0 + pt, zbase, Hs), rmp, 5, seed=12, deco=side_deco, ao=ao)
            box(sc, (0, D, v1 - pt, v1, zbase, Hs), rmp, 5, seed=13, deco=side_deco)
        else:
            for (uu, vv) in ((0, v0), (D - pt, v0), (0, v1 - pt), (D - pt, v1 - pt)):
                box(sc, (uu, uu + pt, vv, vv + pt, 0, Hs), rmp, 5, seed=int(uu * 7 + vv), grain='z')
            if st.get('rails'):
                for z in (levels[0] + T + 1,):
                    pass
    else:
        # 拱頂／尖頂／圓角：外形是一個 v–z 剖面沿 u 擠出來的，挖掉開口
        r = st.get('r', 12)
        rise = st.get('rise', 0)
        zt = Hs

        def outer2(v, z):
            if shape == 'round':
                return sd_box2(v, z, (v0 + v1) / 2, (zbase + zt) / 2, (v1 - v0) / 2, (zt - zbase) / 2, r)
            if shape == 'arch':
                return sd_arch2(v, z, v0, v1, zbase, zt, rise)
            return sd_peak2(v, z, v0, v1, zbase, zt, rise)

        def inner2(v, z):
            q = pt
            if shape == 'round':
                return sd_box2(v, z, (v0 + v1) / 2, (levels[0] + T + zt - q) / 2 - 0.0, (v1 - v0) / 2 - q,
                               (zt - q - levels[0] - T) / 2 + 0.01, max(1.0, r - q))
            if shape == 'arch':
                return sd_arch2(v, z, v0 + q, v1 - q, levels[0], zt, rise - q)
            return sd_peak2(v, z, v0 + q, v1 - q, levels[0], zt - 1, rise - q - 2)

        def carcass(u, v, z):
            o = np.maximum(outer2(v, z), sd_slab(u, 0, D))
            hole = np.maximum(inner2(v, z), sd_slab(u, BT, D + 4))
            return np.maximum(o, -hole)

        def deco(c, idx, col):
            # 正面外框（+u 面）一圈亮邊
            front = (c.face == F_U) | (c.nx > 0.7)
            col = np.where((front & (c.u > D - 0.8))[:, None], pick(rmp, idx + 1), col)
            return col
        top_extra = rise + 2
        # 背板（同外形、u∈[0,BT+0.5]）單獨一個立體 —— 只靠 carcass 挖洞的話，拱頂裡的背板在視線擦過時會打出梳子狀的縫
        sc.add(SDF(lambda u, v, z: np.maximum(outer2(v, z) + 0.5, sd_slab(u, 0, BT + 0.5)),
                   (0, BT + 0.5, v0, v1, 0, zt + top_extra), sdf_mat(rmp, 4, ao=ao, grain=False), edge=False))
        def deco2(c, idx, col):
            # 拱頂／屋頂的內側天花（法線朝下）：一律畫成架子裡面的暗色，不然視線擦過時會一條亮一條暗
            ceil = (c.nz < -0.3) | ((c.u < D - 0.7) & (c.u > BT + 0.6) & (np.abs(inner2(c.v, c.z)) < 2.0)
                                    & (c.nz < 0.5))
            col = np.where(ceil[:, None], pick(rmp, 2 + (c.u > D * 0.6).astype(int)), col)
            return deco(c, idx, col)
        sc.add(SDF(carcass, (0, D, v0, v1, 0, zt + top_extra), sdf_mat(rmp, 5, ao=ao, deco=deco2, grain=True), edge=False))
        if shape == 'arch':
            ornament(sc, 'star', D * 0.45, (v0 + v1) / 2, zt + rise - 1)
            sc.add(Ell(D - 0.4, (v0 + v1) / 2, zt + rise - 6, 2.2, 2.2, 2.2, metal_mat(GOLD, 5, k=3.4)))
        if shape == 'peak':
            # 紫色瓦片屋頂（比本體大一圈、前後出簷）＋圓窗＋星星
            hw = (v1 - v0) / 2 + 3
            vm = (v0 + v1) / 2
            L = math.hypot(hw, rise)

            def roof(u, v, z):
                outer_ = ((z - zt) * hw + np.abs(v - vm) * rise - hw * rise) / L
                inner_ = -(outer_ + 3.5)
                return np.maximum(np.maximum(outer_, inner_), np.maximum(sd_slab(u, -0.5, D + 3), zt - 2 - z))

            def shingle(c):
                idx = tone_idx(c, 5, 3.0)
                row = np.floor((c.z - zt) / 4.0)
                sh = np.mod(c.u + row * 3, 6) < 1.0
                idx = np.where(np.mod(c.z - zt, 4) < 1.0, idx - 1, idx)
                idx = np.where(sh, idx - 1, idx)
                return pick(PURPLE, idx)
            sc.add(SDF(roof, (-0.5, D + 3, v0 - 4, v1 + 4, zt - 2, zt + rise + 1), shingle))
            # 屋頂下的山牆圓窗（亮著）
            win = blank(7, 7)
            ball(win, 3, 3, 3.2, 3.2, SUN, 6, spec=False, rim_dark=False)
            win[3, :, :3] = WOOD[3]
            win[:, 3, :3] = WOOD[3]
            sprite(sc, win, D + 0.5, vm, zt + 4, anchor=(0.5, 0.5), depth=(D + 2, vm + 2))
            sc.add(Cyl(D * 0.3, vm, 1.0, zt + rise - 2, zt + rise + 4, metal_mat(IRON, 5)))
            ornament(sc, 'star', D * 0.3, vm, zt + rise + 3)
            sc.lights.append((D + 1, vm, zt + 4))

    # ── 層板 ──
    def board_ao(c):
        # 層板頂面：靠背板那一半暗一階（上一層壓下來的陰影）
        return np.where((c.face == F_TOP) & (c.u < D * 0.45), -1, 0)

    for z in levels:
        bu = BT if back != 'none' else 0
        box(sc, (bu, D, vi0, vi1, z, z + T), rmp, 6, seed=int(z) + 3, ao=board_ao)
    if side == 'posts' and st.get('rails'):
        # 細架：層板底下的小撐條
        for z in levels[1:]:
            box(sc, (D - 3, D - 1, v0, v1, z - 3, z), rmp, 4, seed=int(z))

    # ── 頂板 ──
    top = st.get('top', 'none')
    ztop = Hs
    if shape == 'rect':
        if top == 'flat':
            box(sc, (0, D + 2, v0 - 1.5, v1 + 1.5, Hs, Hs + 4), rmp, 6, seed=31)
            ztop = Hs + 4
        elif top == 'flush':
            box(sc, (0, D, v0, v1, Hs, Hs + T), rmp, 6, seed=31)
            ztop = Hs + T
        elif top == 'crown':
            box(sc, (0, D + 1, v0 - 1, v1 + 1, Hs, Hs + 3), rmp, 5, seed=31)
            box(sc, (0, D + 3, v0 - 2.5, v1 + 2.5, Hs + 3, Hs + 7), rmp, 6, seed=32)
            ztop = Hs + 7
        elif top == 'plank':
            oh = st.get('overhang', 5)
            box(sc, (0, D + 1, v0 - oh, v1 + oh, Hs, Hs + 6), rmp, 6, seed=31)
            ztop = Hs + 6
    if st.get('finials'):
        for vv in (v0 + pt / 2, v1 - pt / 2):
            sc.add(Ell(D - pt / 2 - 0.5, vv, ztop + 3, 2.8, 2.8, 3.0, solid_mat(GOLD, 5, k=3.2)))
            sc.add(Ell(pt / 2, vv, ztop + 3, 2.8, 2.8, 3.0, solid_mat(GOLD, 5, k=3.2)))

    # ── 頂飾 ──
    ext = st.get('extra')
    if ext == 'crest':
        vm = (v0 + v1) / 2
        hw = (v1 - v0) / 2 - 4

        def crest(u, v, z):
            t = np.clip(np.abs(v - vm) / hw, 0, 1)
            hz = 4 + 11 * (1 - t) ** 1.6
            prof = np.maximum(z - (ztop + hz), ztop - 0.5 - z)
            prof = np.maximum(prof, np.abs(v - vm) - hw)
            return np.maximum(prof, sd_slab(u, 1, 4))
        sc.add(SDF(crest, (1, 4, v0, v1, ztop - 1, ztop + 16), sdf_mat(rmp, 6, k=3.0)))
        # 金色月亮徽章
        img = from_ascii(['.aaa.', 'abb..', 'ab...', 'abb..', '.aaa.'], {'a': GOLD[4], 'b': GOLD[6]})
        sprite(sc, img, 4.2, vm, ztop + 6, anchor=(0.5, 0.5), depth=(5, vm + 1))
    if ext == 'scallop':
        zb = Hs - 7

        def val(u, v, z):
            s_ = np.mod(v - v0, 8.0) - 4.0
            edge = zb + 3 - np.sqrt(np.maximum(0, 16 - s_ * s_)) * 0.9
            prof = np.maximum(edge - z, z - Hs)
            return np.maximum(np.maximum(prof, sd_slab(u, D - 1.2, D + 0.8)), sd_slab(v, v0, v1))

        def stripes(c):
            idx = tone_idx(c, 6, 2.4)
            k = np.mod(np.floor((c.v - v0) / 8.0), 2) == 0
            return np.where(k[:, None], pick(PINK, idx), pick(CREAMW, idx + 1))
        sc.add(SDF(val, (D - 1.2, D + 0.8, v0, v1, zb - 2, Hs), stripes))

    # ── 下段 ──
    lower = st.get('lower')
    lz1 = levels[0]
    if lower in ('drawer1', 'drawers6', 'doors'):
        cols, rows_ = {'drawer1': (1, 1), 'drawers6': (3, 2), 'doors': (2, 1)}[lower]
        zz0 = zbase + (0 if not st.get('feet') else 0)

        def front_deco(c, idx, col):
            f_ = c.face == F_U
            wv = (vi1 - vi0) / cols
            hz = (lz1 - zz0) / rows_
            iv = np.floor((c.v - vi0) / wv)
            iz = np.floor((c.z - zz0) / hz)
            lv = c.v - vi0 - iv * wv
            lz = c.z - zz0 - iz * hz
            gap = f_ & ((lv < 1.2) | (lz < 1.2))
            panel = f_ & (lv > 3.0) & (lv < wv - 2.0) & (lz > 3.0) & (lz < hz - 2.0)
            rim = f_ & (lv > 2.0) & (lv < wv - 1.0) & (lz > 2.0) & (lz < hz - 1.0) & ~panel
            col = np.where(panel[:, None], pick(rmp, idx + 1), col)
            col = np.where(rim[:, None], pick(rmp, idx - 1), col)
            col = np.where(gap[:, None], pick(rmp, idx - 3), col)
            return col
        box(sc, (BT, D, vi0, vi1, zz0, lz1), rmp, 5, seed=41, deco=front_deco)
        wv = (vi1 - vi0) / cols
        hz = (lz1 - zz0) / rows_
        for i in range(cols):
            for j in range(rows_):
                if lower == 'doors':
                    vv = vi0 + wv * (i + (0.15 if i == 0 else 0.85))
                    vv = vi0 + wv * (1 - 0.12) if i == 0 else vi0 + wv * (1 + 0.12)
                    zz = zz0 + hz * 0.55
                else:
                    vv = vi0 + wv * (i + 0.5)
                    zz = zz0 + hz * (j + 0.55)
                sc.add(Ell(D + 0.8, vv, zz, 2.0, 2.0, 2.0, metal_mat(BRASS, 5, k=3.4)))
        if lower == 'doors':
            # 門上的小星星挖孔
            for i in range(2):
                vv = vi0 + wv * (i + 0.5)
                sc.fine_px(D, vv, zz0 + hz * 0.75, GOLD[6])
    if lower == 'deep':
        # 下段是一個比較深的開放格（底板＋兩側加深），上面一片出簷的檯面
        for (va, vb) in ((v0, v0 + pt), (v1 - pt, v1)):
            box(sc, (0, lowD, va, vb, 0, lowH - 3), rmp, 5, seed=int(va) + 51, ao=ao if va == v0 else None)
        box(sc, (BT, lowD, vi0, vi1, 0, 2 + T), rmp, 6, seed=53, ao=board_ao)
        box(sc, (0, lowD + 1.5, v0 - 1, v1 + 1, lowH - 3, lowH), rmp, 6, seed=52)
    if plinth:
        box(sc, (0, D + (lowD - D if lower == 'deep' else 0) + 1, v0 - 0.5, v1 + 0.5, 0, plinth), rmp, 3, seed=61)
    if st.get('feet') == 'bun':
        for (uu, vv) in ((3, v0 + 3), (D - 2.5, v0 + 3), (3, v1 - 3), (D - 2.5, v1 - 3)):
            sc.add(Ell(uu, vv, 1.6, 2.8, 2.8, 2.6, solid_mat(rmp, 4, k=3.2)))

    # ── 頂上小擺飾 ──
    orn = st.get('orn')
    if orn:
        zo = ztop if shape == 'rect' else Hs
        ornament(sc, orn, D * 0.5, v0 + (v1 - v0) * 0.72, zo)

    # ── 陳列位 ──
    per_row = 3 if dep >= 3 else 2
    comps = []                       # (層板頂, 上一層的底, 這一層的深度)
    all_lv = list(levels)
    if lower == 'deep':
        comps.append((2 + T, lowH - 3, lowD))
    tops_ = all_lv[1:] + [Hs - (7 if ext == 'scallop' else 0)]
    for z, zc in zip(all_lv, tops_):
        if lower in ('drawer1', 'drawers6', 'doors') or lower == 'deep':
            pass
        comps.append((z + T, zc, D))
    if lower == 'deep':
        comps = comps          # 最下層＝下櫃的頂
    for row, (zf, zc, Dc) in enumerate(sorted(comps, key=lambda q: -q[0])):
        uc = round(Dc * SLOT_FRONT)
        v_hi = (v1 - (pt if side == 'panel' else 0)) - (Dc - uc) - SLOT_W / 2 - 1
        if shape == 'peak' and row == 0:
            v_hi = min(v_hi, 60)
        v_lo = v0 + (pt if side == 'panel' else 0) + 9
        sp = (v_hi - v_lo) / (per_row - 1)
        mw = min(SLOT_W, sp - 1)
        mh = min(SLOT_H_MAX, zc - zf - (Dc - uc) / 2.0 - 1)
        if shape == 'peak' and row == 0:
            mh = min(mh, 22)
        for i in range(per_row):
            sc.slots.append((uc, v_hi - i * sp, zf, mw, mh, row))
    return render(sc, sid)


# ═══════════════════════════════ 販售桌 ═══════════════════════════════

TABLE_H = 30


def draw_sale_table():
    sc = grid_scene(2, 1, zmax=90)
    du, dv = 2 * CELL, CELL
    H = TABLE_H
    shadow_rect(sc, 2, du - 3, 2, dv - 3, 2)
    for (pu, pv) in ((5, 5), (du - 6, 5), (5, dv - 6), (du - 6, dv - 6)):
        sc.add(Cyl(pu, pv, 2.4, 0, H - 4, wmat(WOOD, 4, grain='z', seed=int(pu + pv))))
        for zz in (8, 18):
            sc.add(Ell(pu, pv, zz, 3.0, 3.0, 1.6, solid_mat(WOOD, 5, k=3.0)))
        sc.add(Ell(pu, pv, 1.5, 3.2, 3.2, 1.8, solid_mat(WOOD, 3, k=3.0)))
    box(sc, (6, du - 6, 6, dv - 6, 6, 8.5), WOOD, 4, seed=7)          # 下層橫撐

    def apron(c, idx, col):
        front = (c.face == F_V) | (c.face == F_U)
        carve = front & (np.abs(c.z - (H - 6.5)) < 0.9) & (np.mod(face_a(c), 6) < 3)
        return np.where(carve[:, None], pick(WOOD, idx + 2), col)
    box(sc, (3, du - 3, 3, dv - 3, H - 9, H - 3), WOOD, 5, seed=8, deco=apron)
    box(sc, (0.5, du - 0.5, 0.5, dv - 0.5, H - 3, H), WOOD, 6, seed=9, plank=10)
    # 桌巾：紫絨金邊，沿長邊鋪，在 +u 那頭垂下收成尖角＋金流蘇
    va, vb = 9, 23

    def runner(c):
        idx = tone_idx(c, 5, 2.6)
        edge = (np.abs(c.v - va - 1.2) < 0.9) | (np.abs(c.v - vb + 1.2) < 0.9)
        col = pick(PURPLE, idx)
        col = np.where(edge[:, None], GOLD[5], col)
        mx, my = du / 2, (va + vb) / 2
        moon = (np.hypot(c.u - mx, c.v - my) < 3.6) & (np.hypot(c.u - mx - 1.6, c.v - my + 1.0) > 3.0) & (c.face == F_TOP)
        col = np.where(moon[:, None], GOLD[6], col)
        dots = (c.face == F_TOP) & (h32(np.floor(c.u / 2), np.floor(c.v / 2), 13) > 0.94) & ~edge
        col = np.where(dots[:, None], LILAC[8], col)
        return col
    sc.add(Box(2, du - 0.5, va, vb, H, H + 1, runner, edge=False))
    tip = blank(9, 9)
    rows = ['aaaaaaaaa', 'abbbbbbba', 'abbbcbbba', '.abbbbba.', '..abbba..', '...aba...', '....d....', '...ded...', '...ddd...']
    tip = from_ascii(rows, {'a': GOLD[4], 'b': PURPLE[4], 'c': GOLD[6], 'd': GOLD[5], 'e': GOLD[7]})
    sprite(sc, tip, du, (va + vb) / 2, H + 1, anchor=(0.5, 0.0), depth=(du + 1, (va + vb) / 2 + 1))
    for i, u in enumerate((9, 32, 55)):
        sc.slots.append((u, 16, H + 1, SLOT_W, SLOT_H_MAX, 0))
    return render(sc, 'sale_table')



def lace_mat(rmp=CREAMW, base=7, cu=16, cv=16):
    """蕾絲桌巾：一圈圈小洞＋扇形邊。"""
    def m(c):
        idx = tone_idx(c, base, 2.6)
        r = np.hypot(c.u - cu, c.v - cv)
        ang = np.arctan2(c.v - cv, c.u - cu)
        holes = (np.mod(ang * 12 / math.pi + np.floor(r / 3) * 0.5, 1.0) < 0.28) & (np.mod(r, 3.0) < 1.0) & (c.face == F_TOP)
        idx = np.where(holes, idx - 2, idx)
        side = c.face != F_TOP
        drop = side & (np.mod(ang * 16 / math.pi, 2.0) < 1.0)
        idx = np.where(drop, idx - 1, idx)
        return pick(rmp, idx)
    return m


def legs4(sc, pts, z1, rmp=WOOD, r=2.2, turned=True):
    for (pu, pv) in pts:
        sc.add(Cyl(pu, pv, r, 0, z1, wmat(rmp, 4, grain='z', seed=int(pu * 3 + pv))))
        if turned:
            sc.add(Ell(pu, pv, z1 * 0.35, r + 0.9, r + 0.9, 1.5, solid_mat(rmp, 5, k=3.0)))
        sc.add(Ell(pu, pv, 1.2, r + 0.8, r + 0.8, 1.6, solid_mat(rmp, 3, k=3.0)))


# ═══════════════════════════════ 陳列桌 ═══════════════════════════════

def table_round():
    """蕾絲小圓桌（1×1）：單柱三腳、桌面鋪奶油色蕾絲、桌邊垂一圈扇形。2 個位子。"""
    sc = grid_scene(1, 1, zmax=80)
    c0, H = 16, 28
    shadow_round(sc, c0, c0, 11)
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.6
        sc.add(Ell(c0 + 7 * math.cos(a), c0 + 7 * math.sin(a), 1.5, 3.0, 3.0, 1.8, solid_mat(WOOD, 4, k=3.0)))
    sc.add(Cyl(c0, c0, 4.0, 0, 3, solid_mat(WOOD, 4, k=3.0)))
    sc.add(Cyl(c0, c0, 1.9, 0, H - 2, wmat(WOOD, 4, grain='z', seed=3)))
    sc.add(Ell(c0, c0, 10, 3.0, 3.0, 2.0, solid_mat(WOOD, 5, k=3.0)))
    sc.add(Cyl(c0, c0, 12.5, H - 3, H, solid_mat(WOOD, 6, k=3.4)))

    def skirt(u, v, z):
        r = np.hypot(u - c0, v - c0)
        ang = np.arctan2(v - c0, u - c0)
        bottom = H - 13 + np.abs(np.sin(ang * 6)) * 3.0
        return np.maximum(np.maximum(r - 12.6, 11.4 - r), np.maximum(bottom - z, z - H - 0.8))
    sc.add(SDF(skirt, (c0 - 13, c0 + 13, c0 - 13, c0 + 13, H - 14, H + 0.8), lace_mat(cu=c0, cv=c0), edge=False))
    sc.add(Cyl(c0, c0, 12.4, H, H + 0.8, lace_mat(cu=c0, cv=c0), edge=False))
    # 中間一小瓶花
    sc.slots += [(c0 + 5.5, c0 - 5.5, H + 0.8, SLOT_W, SLOT_H_MAX, 0), (c0 - 5.5, c0 + 5.5, H + 0.8, SLOT_W, SLOT_H_MAX, 0)]
    return render(sc, 'table_round')


def table_long():
    """長木展示桌（2×1）：方腳長桌、格紋桌巾。3 個位子。"""
    sc = grid_scene(2, 1, zmax=80)
    du, dv, H = 64, 32, 26
    shadow_rect(sc, 3, du - 3, 3, dv - 3)
    legs4(sc, ((5, 5), (du - 5, 5), (5, dv - 5), (du - 5, dv - 5)), H - 3, r=2.0)
    box(sc, (4, du - 4, 4, dv - 4, H - 8, H - 3), WOOD, 5, seed=4)
    box(sc, (1, du - 1, 2, dv - 2, H - 3, H), WOOD, 6, seed=5, plank=10)

    def gingham(c):
        idx = tone_idx(c, 6, 2.4)
        a = np.mod(np.floor(c.u / 3), 2) + np.mod(np.floor((c.v + c.z) / 3), 2)
        col = np.where((a == 0)[:, None], pick(SKYB, idx - 1), np.where((a == 1)[:, None], pick(SKYB, idx + 1), pick(CREAMW, idx + 1)))
        return col
    sc.add(Box(14, 50, 2.5, dv - 2.5, H, H + 0.8, gingham, edge=False))
    sc.add(Box(14, 50, dv - 2.5, dv - 1.6, H - 8, H + 0.8, gingham, edge=False))     # 垂下來的那一片（左下）
    for u in (11, 32, 53):
        sc.slots.append((u, 16, H + 0.8, SLOT_W, SLOT_H_MAX, 0))
    return render(sc, 'table_long')


def table_tier():
    """雙層階梯架（2×1）：後排高、前排低的兩階木台，前緣有月亮雕花。6 個位子。"""
    sc = grid_scene(2, 1, zmax=90)
    du, dv = 64, 32
    shadow_rect(sc, 2, du - 2, 2, dv - 2)

    def carve(c, idx, col):
        f_ = c.face == F_V
        k = f_ & (np.abs(np.mod(c.u, 10) - 5) < 1.2) & (np.abs(c.z - (c.z // 1)) < 2)
        return col
    zf, zb = 20, 38
    box(sc, (2, du - 2, 16, dv - 2, 0, zf - 3), WOOD, 5, seed=7, ao=None)
    box(sc, (1, du - 1, 15.5, dv - 1, zf - 3, zf), WOOD, 6, seed=8)
    box(sc, (2, du - 2, 2, 16, 0, zb - 3), WOOD, 4, seed=9)
    box(sc, (1, du - 1, 1, 16.5, zb - 3, zb), WOOD, 6, seed=10)
    # 前緣的小月亮與星星（金）
    for k, u in enumerate((12, 32, 52)):
        img = from_ascii(['.aa.', 'a...', 'a...', '.aa.'], {'a': GOLD[5]}) if k % 2 == 0 else \
            from_ascii(['.a.', 'aba', '.a.'], {'a': GOLD[5], 'b': GOLD[7]})
        sc.sprite(img, u, dv - 1.6, 9, anchor=(0.5, 0.5), depth=(u + 1, dv))
    # 階面鋪紫色毛氈
    sc.add(Box(3, du - 3, 18, dv - 3, zf, zf + 0.7, cloth_mat(LILAC, 5, k=2.0), edge=False))
    sc.add(Box(3, du - 3, 3, 15, zb, zb + 0.7, cloth_mat(LILAC, 5, k=2.0), edge=False))
    for u in (11, 32, 53):
        sc.slots.append((u, 8.5, zb + 0.7, SLOT_W, SLOT_H_MAX, 0))
    for u in (11, 32, 53):
        sc.slots.append((u, 24, zf + 0.7, SLOT_W, 22.0, 1))
    return render(sc, 'table_tier')


def table_barrel():
    """木桶小桌（1×1）：橡木桶＋鐵箍，桶頂一塊圓木板。2 個位子。"""
    sc = grid_scene(1, 1, zmax=80)
    c0, H = 16, 30
    shadow_round(sc, c0, c0, 12)

    def staves(c):
        lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
        idx = np.round(5 + (lit - 0.5) * 3.4).astype(int)
        ang = np.arctan2(c.v - c0, c.u - c0)
        seam = np.mod(ang * 14 / math.pi, 1.0) < 0.16
        idx = np.where(seam & (c.face == F_SIDE), idx - 2, idx)
        band = (np.abs(c.z - 6) < 1.6) | (np.abs(c.z - (H - 7)) < 1.6)
        col = pick(WOOD, idx)
        col = np.where((band & (c.face == F_SIDE))[:, None], pick(IRON, idx + 1), col)
        rivet = band & (c.face == F_SIDE) & (np.mod(ang * 14 / math.pi + 0.5, 2.0) < 0.25)
        col = np.where(rivet[:, None], IRON[8], col)
        return col

    def bulge(u, v, z):
        r = 11.0 + 1.6 * np.sin(np.clip(z / (H - 2), 0, 1) * math.pi)
        return np.maximum(np.hypot(u - c0, v - c0) - r, sd_slab(z, 0, H - 2))
    sc.add(SDF(bulge, (c0 - 13, c0 + 13, c0 - 13, c0 + 13, 0, H - 2), staves))
    sc.add(Cyl(c0, c0, 13.5, H - 2, H, wmat(WOOD, 6, seed=12, plank=6)))
    sc.slots += [(c0 + 5, c0 - 5, H, SLOT_W, SLOT_H_MAX, 0), (c0 - 5, c0 + 5, H, SLOT_W, SLOT_H_MAX, 0)]
    return render(sc, 'table_barrel')


def table_crate():
    """木箱堆疊架（2×1）：三個木箱，中間高、兩邊矮；箱子側面有標籤、旁邊一點稻草。3 個位子。"""
    sc = grid_scene(2, 1, zmax=90)
    du, dv = 64, 32
    shadow_rect(sc, 2, du - 2, 3, dv - 3)
    spans = ((2, 21, 16, TIMBER), (22, 42, 30, WOOD), (43, 62, 16, TIMBER))
    for k, (ua, ub, h, rmp) in enumerate(spans):
        def slats(c, idx, col, h=h, rmp=rmp, k=k):
            side = c.face != F_TOP
            gap = side & (np.mod(c.z, h / 3.0) < 1.0)
            col = np.where(gap[:, None], pick(rmp, idx - 2), col)
            lab = (c.face == F_V) & (np.abs(c.z - h * 0.5) < 2.5) & (np.abs(c.u - (ua + ub) / 2) < 3.5) & (k == 1)
            col = np.where(lab[:, None], pick(CREAMW, 6), col)
            return col
        box(sc, (ua, ub, 3, dv - 3, 0, h), rmp, 5, seed=20 + k, deco=slats)
        sc.slots.append(((ua + ub) / 2, 16, h, SLOT_W - 2, SLOT_H_MAX, 0))
    # 稻草
    straw = blank(12, 4)
    for x in range(12):
        put(straw, x, 3 - (x * 7 % 3), SUN[5 + x % 3])
        put(straw, x, 3, SUN[4])
    sc.sprite(add_outline(straw, color=SUN[2]), 12, dv - 2, 16, anchor=(0.5, 1.0), depth=(14, dv))
    # 讓中間那格排第一（最高的先看到）
    sc.slots = [sc.slots[1], sc.slots[0], sc.slots[2]]
    sc.slots = [(u, v, z, mw, mh, i) for i, (u, v, z, mw, mh, _) in enumerate(sc.slots)]
    sc.slots = [(u, v, z, mw, mh, 0 if z > 20 else 1) for (u, v, z, mw, mh, _) in sc.slots]
    return render(sc, 'table_crate')


def table_pedestal():
    """絲絨展示台（1×1）：白石柱台、金邊、紅絲絨坐墊。1 個大位子。"""
    sc = grid_scene(1, 1, zmax=90)
    c0, H = 16, 34
    shadow_round(sc, c0, c0, 11)
    sc.add(Cyl(c0, c0, 10, 0, 4, solid_mat(CREAMW, 5, k=3.0)))
    sc.add(Cyl(c0, c0, 8.5, 4, 6, metal_mat(GOLD, 5)))

    def column(c):
        idx = tone_idx(c, 6, 3.4)
        ang = np.arctan2(c.v - c0, c.u - c0)
        flute = np.mod(ang * 8 / math.pi, 1.0) < 0.3
        return pick(CREAMW, np.where(flute & (c.face == F_SIDE), idx - 1, idx))
    sc.add(Cyl(c0, c0, 6, 6, H - 6, column))
    sc.add(Cyl(c0, c0, 9, H - 6, H - 3, metal_mat(GOLD, 5)))
    sc.add(Cyl(c0, c0, 10, H - 3, H, solid_mat(CREAMW, 6, k=3.0)))

    def velvet(c):
        idx = tone_idx(c, 5, 3.2)
        return pick(CHERRY, idx)
    sc.add(Ell(c0, c0, H, 9, 9, 3.2, velvet, zmin=H))
    for a in range(4):
        aa = a * math.pi / 2 + math.pi / 4
        sc.add(Ell(c0 + 8.2 * math.cos(aa), c0 + 8.2 * math.sin(aa), H + 0.5, 1.4, 1.4, 1.8, metal_mat(GOLD, 6)))
    sc.slots.append((c0, c0, H + 2.2, 28.0, 30.0, 0))
    return render(sc, 'table_pedestal')


def table_cart():
    """條紋小攤車（2×1）：木頭推車＋兩個大輪子＋後面撐一片粉白條紋遮陽棚。3 個位子。"""
    sc = grid_scene(2, 1, zmax=120)
    du, dv, H = 64, 32, 28
    shadow_rect(sc, 3, du - 3, 3, dv - 3)
    # 車身
    box(sc, (4, du - 4, 4, dv - 4, 10, H - 3), WOOD, 5, seed=31,
        deco=lambda c, idx, col: np.where(((c.face != F_TOP) & (np.mod(c.z - 10, 5) < 0.9))[:, None], pick(WOOD, idx - 2), col))
    box(sc, (2, du - 2, 2, dv - 2, H - 3, H), WOOD, 6, seed=32)
    # 兩個大輪子（在 +v 那側，看得到）＋後側的輪子
    for vv in (dv - 3.0, 3.0):
        def wheel(c, vv=vv):
            r = np.hypot(c.u - 32, c.z - 11)
            spoke = (np.mod(np.arctan2(c.z - 11, c.u - 32) * 4 / math.pi, 1.0) < 0.22) & (r < 8)
            hub = r < 2.2
            idx = tone_idx(c, 5, 3.0)
            col = pick(WOOD, idx)
            col = np.where((r < 8.6)[:, None] & ~spoke[:, None] & ~hub[:, None], pick(WOOD, idx - 3), col)
            col = np.where(hub[:, None], BRASS[6], col)
            col = np.where((r > 9.0)[:, None], pick(IRON, idx), col)
            return col

        def wf(u, v, z, vv=vv):
            return np.maximum(np.hypot(u - 32, z - 11) - 10.5, sd_slab(v, vv - 1.6, vv + 1.6))
        sc.add(SDF(wf, (21, 43, vv - 1.6, vv + 1.6, 0, 22), wheel))
    # 把手（+u 那頭）
    sc.add(HCyl('v', du + 0.5, H + 2, 1.1, 5, dv - 5, solid_mat(WOOD, 6, k=3)))
    for vv in (6, dv - 6):
        box(sc, (du - 4, du + 1, vv - 1, vv + 1, H - 2, H + 2.5), WOOD, 5, seed=int(vv))
    # 後側兩根柱子＋條紋遮陽棚（往前斜）
    for uu in (5, du - 5):
        sc.add(Cyl(uu, 5, 1.2, H, H + 44, solid_mat(WOOD, 5, k=3)))

    def canopy(u, v, z):
        zc = H + 46 - (v - 2) * 0.55
        return np.maximum(np.maximum(np.abs(z - zc) - 0.9, sd_slab(u, 1, du - 1)), sd_slab(v, 1, 20))

    def stripes(c):
        idx = tone_idx(c, 6, 2.4)
        k = np.mod(np.floor(c.u / 6), 2) == 0
        return np.where(k[:, None], pick(PINK, idx), pick(CREAMW, idx + 1))
    sc.add(SDF(canopy, (1, du - 1, 1, 20, H + 30, H + 48), stripes))

    def valance(u, v, z):
        s_ = np.mod(u, 6.0) - 3.0
        edge = H + 35.5 - np.sqrt(np.maximum(0, 9 - s_ * s_)) * 0.9
        prof = np.maximum(edge - z, z - (H + 36.6))
        return np.maximum(np.maximum(prof, sd_slab(v, 19.2, 20.8)), sd_slab(u, 1, du - 1))
    sc.add(SDF(valance, (1, du - 1, 19.2, 20.8, H + 31, H + 37), stripes))
    for u in (12, 32, 52):
        sc.slots.append((u, 21, H, SLOT_W, 24.0, 0))
    return render(sc, 'table_cart')


# ═══════════════════════════════ 燈 ═══════════════════════════════

def lamp_lantern():
    """提燈立燈（1×1）：鐵柱、捲曲的吊臂、掛一盞玻璃提燈（裡面一根蠟燭）。"""
    sc = grid_scene(1, 1, zmax=150)
    c0 = 16
    shadow_round(sc, c0, c0, 8)
    sc.add(Cyl(c0, c0, 6, 0, 3, metal_mat(IRON, 4)))
    sc.add(Cyl(c0, c0, 3.5, 3, 5, metal_mat(IRON, 5)))
    sc.add(Cyl(c0 - 4, c0 - 4, 1.4, 0, 96, metal_mat(IRON, 5)))
    for z in (30, 60):
        sc.add(Ell(c0 - 4, c0 - 4, z, 2.4, 2.4, 1.6, metal_mat(IRON, 6)))
    sc.add(Ell(c0 - 4, c0 - 4, 98, 2.6, 2.6, 2.6, metal_mat(BRASS, 5)))
    # 吊臂：往 +u+v 伸出去的一段＋捲花
    sc.add(HCyl('u', c0 - 4, 92, 1.1, c0 - 4, c0 + 8, metal_mat(IRON, 5)))
    curl = from_ascii(['.aaa.', 'a...a', 'a.a.a', 'a..a.', '.a...'], {'a': IRON[5]})
    sc.sprite(add_outline(pad(curl, 1)), c0 + 1, c0 - 4, 89, anchor=(0.5, 0.0), depth=(c0 + 1, c0 - 3))
    sc.add(Cyl(c0 + 7, c0 - 4, 0.6, 82, 92, metal_mat(IRON, 4)))
    # 提燈：頂蓋＋四根框＋玻璃＋蠟燭
    lu, lv = c0 + 7, c0 - 4
    sc.add(Ell(lu, lv, 82, 5, 5, 3, metal_mat(IRON, 5), zmin=79))
    sc.add(Cyl(lu, lv, 1.2, 82, 85, metal_mat(BRASS, 6)))

    def glass(c):
        idx = tone_idx(c, 6, 2.0)
        frame = (np.abs(np.mod(np.arctan2(c.v - lv, c.u - lu) * 2 / math.pi + 0.5, 1.0) - 0.5) < 0.12)
        col = pick(SUN, idx + 1)
        col = np.where(((c.z > 75) & (c.z < 76.5))[:, None], pick(SUN, idx + 2), col)
        return np.where(frame[:, None], pick(IRON, 5), col)
    sc.add(Cyl(lu, lv, 4.4, 66, 79, glass))
    sc.add(Cyl(lu, lv, 5, 64, 66.5, metal_mat(IRON, 5)))
    sc.fine_px(lu, lv, 73, FIRE[8])
    sc.fine_px(lu, lv, 74, FIRE[7])
    sc.lights.append((lu, lv, 72))
    return render(sc, 'lamp_lantern')


def lamp_mushroom():
    """蘑菇燈（1×1）：一朵大蘑菇，傘蓋底下發光；腳邊兩朵小的。"""
    sc = grid_scene(1, 1, zmax=110)
    c0 = 16
    shadow_round(sc, c0, c0, 10)
    sc.add(Ell(c0, c0, 0, 9, 9, 3, cloth_mat(MOSS, 5, k=3.0), zmin=0))

    def stem(c):
        idx = tone_idx(c, 7, 3.0)
        return pick(CREAMW, idx)
    sc.add(SDF(lambda u, v, z: np.hypot(u - c0, v - c0) - (4.8 - z * 0.035), (c0 - 6, c0 + 6, c0 - 6, c0 + 6, 0, 44), stem))

    def cap(c):
        idx = tone_idx(c, 5, 3.2)
        under = c.nz < -0.1
        dot = (h32(np.floor((c.u - c0) / 2.6), np.floor((c.v - c0) / 2.6), np.floor(c.z / 2.6), 7) > 0.72) & (c.nz > 0.25)
        col = pick(CHERRY, idx + 1)
        col = np.where(dot[:, None], CREAMW[8], col)
        col = np.where(under[:, None], pick(SUN, 6), col)
        return col
    sc.add(Ell(c0, c0, 44, 14, 14, 13, cap, zmin=42))
    # 傘緣下的發光圈（看得到的那一圈）
    sc.add(Cyl(c0, c0, 13.4, 41.2, 42.2, solid_mat(SUN, 7, k=1.0), edge=False))
    for (du_, dv_, h, r) in ((8, 3, 9, 4.5), (3, 9, 6, 3.4)):
        sc.add(Cyl(c0 + du_, c0 + dv_, 1.3, 0, h, stem))
        sc.add(Ell(c0 + du_, c0 + dv_, h, r, r, r * 0.8, cap, zmin=h - 0.5))
    sc.lights.append((c0, c0, 38))
    return render(sc, 'lamp_mushroom')


def lamp_moon():
    """星月燈（1×1）：木座、黃銅彎臂，掛著一彎發光的月亮，下面垂兩顆小星星。"""
    sc = grid_scene(1, 1, zmax=150)
    c0 = 16
    shadow_round(sc, c0, c0, 8)
    sc.add(Cyl(c0, c0, 7, 0, 4, wmat(WOOD, 5, seed=3)))
    sc.add(Cyl(c0, c0, 5.5, 4, 5.5, metal_mat(BRASS, 5)))
    sc.add(Cyl(c0 - 3, c0 - 3, 1.2, 5, 86, metal_mat(BRASS, 5)))
    sc.add(HCyl('u', c0 - 3, 87, 1.1, c0 - 3, c0 + 9, metal_mat(BRASS, 5)))
    sc.add(Ell(c0 - 3, c0 - 3, 87, 1.8, 1.8, 1.8, metal_mat(BRASS, 6)))
    sc.add(Cyl(c0 + 9, c0 - 3, 0.5, 80, 87, metal_mat(BRASS, 5)))
    moon = blank(20, 22)
    yy, xx = np.mgrid[0:22, 0:20]
    m = ((xx - 10) ** 2 / 81.0 + (yy - 11) ** 2 / 100.0 < 1) & ~((xx - 14) ** 2 / 64.0 + (yy - 9) ** 2 / 81.0 < 1)
    moon[m, :3] = SUN[6]
    moon[m, 3] = 255
    lit = m & ((xx - 5) ** 2 + (yy - 8) ** 2 < 12)
    moon[lit, :3] = SUN[8]
    shadow_ = m & (yy > 16)
    moon[shadow_, :3] = SUN[5]
    moon[13, 5, :3] = PINK[6]                       # 腮紅
    moon[12, 7, :3] = IRON[2]                       # 閉著的眼睛
    moon[12, 6, :3] = IRON[2]
    sc.sprite(add_outline(pad(moon, 1), color=SUN[2]), c0 + 9, c0 - 3, 78, anchor=(0.5, 0.5), depth=(c0 + 12, c0 + 2), edge=False)
    for (dz, du_) in ((14, 5), (20, 11)):
        sc.add(Cyl(c0 + du_, c0 - 6, 0.3, 66 - dz + 4, 70, metal_mat(GOLD, 6)))
        st = from_ascii(['.a.', 'aba', '.a.'], {'a': SUN[6], 'b': SUN[8]})
        sc.sprite(add_outline(st, color=SUN[2]), c0 + du_, c0 - 6, 66 - dz, anchor=(0.5, 0.5), depth=(c0 + du_ + 2, c0 - 4), edge=False)
    sc.lights.append((c0 + 9, c0 - 3, 78))
    return render(sc, 'lamp_moon')


def lamp_crystal():
    """水晶燈（1×1）：石座上一叢發光的紫水晶。"""
    sc = grid_scene(1, 1, zmax=110)
    c0 = 16
    shadow_round(sc, c0, c0, 10)

    def rock(c):
        idx = tone_idx(c, 4, 3.4)
        n = h32(np.floor(c.u / 3), np.floor(c.v / 3), np.floor(c.z / 3), 5) > 0.7
        return pick(DSTONE, np.where(n, idx - 1, idx))
    sc.add(Ell(c0, c0, 2, 11, 10, 9, rock, zmin=0))
    sc.add(Ell(c0 + 4, c0 + 5, 1, 6, 5, 6, rock, zmin=0))

    def cryst(c):
        lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
        idx = np.round(6 + (lit - 0.5) * 3.0).astype(int)
        edge = np.mod(np.arctan2(c.v - c0, c.u - c0) * 3 / math.pi, 1.0) < 0.2
        idx = np.where(edge, idx + 1, idx)
        return pick(LILAC, idx)
    for (du_, dv_, h, r, lean) in ((0, 0, 40, 4.0, 0), (-5, 3, 26, 3.0, 0), (4, -3, 30, 3.0, 0), (3, 6, 20, 2.5, 0), (-3, -5, 18, 2.4, 0)):
        cu, cv = c0 + du_, c0 + dv_
        sc.add(Cyl(cu, cv, r, 6, 6 + h - r * 1.5, cryst))
        sc.add(SDF((lambda cu=cu, cv=cv, r=r, zt=6 + h - r * 1.5: lambda u, v, z:
                    np.maximum(np.hypot(u - cu, v - cv) - r * np.clip((zt + r * 1.8 - z) / (r * 1.8), 0, 1), sd_slab(z, zt, zt + r * 1.8)))(),
                   (cu - r, cu + r, cv - r, cv + r, 6 + h - r * 1.5, 6 + h + r * 0.4), cryst))
    sc.fine_px(c0, c0, 38, LILAC[9])
    sc.fine_px(c0 - 1, c0, 30, CREAMW[9])
    sc.lights.append((c0, c0, 30))
    return render(sc, 'lamp_crystal')


def lamp_candelabra():
    """三叉燭台（1×1）：鐵製落地燭台，三根蠟燭。"""
    sc = grid_scene(1, 1, zmax=130)
    c0 = 16
    shadow_round(sc, c0, c0, 8)
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.4
        sc.add(Ell(c0 + 6 * math.cos(a), c0 + 6 * math.sin(a), 1.2, 2.8, 2.8, 1.8, metal_mat(IRON, 5)))
    sc.add(Cyl(c0, c0, 3.4, 0, 4, metal_mat(IRON, 5)))
    sc.add(Cyl(c0, c0, 1.3, 4, 70, metal_mat(IRON, 5)))
    for z in (20, 44):
        sc.add(Ell(c0, c0, z, 2.4, 2.4, 1.8, metal_mat(IRON, 6)))
    sc.add(HCyl('u', c0 + 0.0, 70, 1.0, c0 - 10, c0 + 10, metal_mat(IRON, 5)) if False else
           HCyl('v', c0, 70, 1.0, c0 - 11, c0 + 11, metal_mat(IRON, 5)))
    for dv_ in (-10, 0, 10):
        zb = 74 if dv_ == 0 else 70
        if dv_ == 0:
            sc.add(Cyl(c0, c0, 1.0, 70, 74, metal_mat(IRON, 5)))
        sc.add(Cyl(c0, c0 + dv_, 3.6, zb, zb + 1.6, metal_mat(BRASS, 5), r_in=2.6))
        sc.add(Cyl(c0, c0 + dv_, 2.6, zb, zb + 1.2, metal_mat(BRASS, 4)))
        hgt = 12 if dv_ == 0 else 9

        def wax(c, cv=c0 + dv_, zt=zb + hgt):
            idx = tone_idx(c, 7, 3.0)
            drip = (c.face == F_SIDE) & (c.z > zt - 3) & (h32(np.floor(np.arctan2(c.v - cv, c.u - c0) * 4), 3) > 0.5)
            return pick(CREAMW, idx + np.where(drip, 1, 0))
        sc.add(Cyl(c0, c0 + dv_, 1.9, zb + 1, zb + hgt, wax))
        sc.sprite(flame_img(6, 3, 0), c0, c0 + dv_, zb + hgt, anchor=(0.5, 1.0), depth=(c0, c0 + dv_), edge=False)
        sc.fine_px(c0, c0 + dv_, zb + hgt + 4, FIRE[8])
    sc.lights.append((c0, c0, 88))
    return render(sc, 'lamp_candelabra')


def lamp_pumpkin():
    """南瓜燈（1×1）：一顆刻了笑臉的大南瓜，上面疊一顆小的，裡面亮著。"""
    sc = grid_scene(1, 1, zmax=90)
    c0 = 16
    shadow_round(sc, c0, c0, 11)

    def pumpkin(cu, cv, cz, R, face):
        def m(c):
            lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
            idx = np.round(5 + (lit - 0.5) * 3.4).astype(int)
            ang = np.arctan2(c.v - cv, c.u - cu)
            rib = np.mod(ang * 8 / math.pi, 1.0) < 0.2
            idx = np.where(rib & (np.abs(c.nz) < 0.85), idx - 1, idx)
            col = pick(PUMPKIN, idx)
            if face:
                # 臉在 +u+v 方向（正對鏡頭）：用面上的 (s, z) 座標
                s_ = (c.u - c.v) - (cu - cv)
                zz = c.z - cz
                front = (c.nx + c.ny) > 0.9
                eye = front & ((((s_ - 5) ** 2 + (zz - 3) ** 2) < 5) | (((s_ + 5) ** 2 + (zz - 3) ** 2) < 5)) & (zz < 4.5)
                mouth = front & (np.abs(zz + 3.5) < 1.6 + 0.0) & (np.abs(s_) < 7) & ~((np.mod(s_ + 7, 4.6) < 1.3) & (zz > -3.5))
                col = np.where((eye | mouth)[:, None], SUN[7], col)
            return col
        return m
    sc.add(Ell(c0, c0, 11, 12, 12, 10, pumpkin(c0, c0, 11, 12, True), zmin=0))
    sc.add(Ell(c0 - 1, c0 - 1, 25, 7, 7, 5.5, pumpkin(c0 - 1, c0 - 1, 25, 7, False), zmin=20))
    sc.add(Cyl(c0 - 1, c0 - 1, 1.2, 29, 33, solid_mat(MOSS, 4, k=3)))
    leaf = from_ascii(['.aa..', 'abba.', '.abba', '..aa.'], {'a': MOSS[3], 'b': MOSS[6]})
    sc.sprite(add_outline(leaf, color=MOSS[0]), c0 + 1, c0 - 1, 31, anchor=(0.0, 1.0), depth=(c0 + 2, c0))
    sc.lights.append((c0 + 6, c0 + 6, 12))
    return render(sc, 'lamp_pumpkin')


# ═══════════════════════════════ 家具 ═══════════════════════════════

def velvet_mat(rmp, base=5, tuft=None):
    def m(c):
        idx = tone_idx(c, base, 3.2)
        col = pick(rmp, idx)
        if tuft is not None:
            bt = tuft(c)
            col = np.where(bt[:, None], pick(rmp, idx - 2), col)
        return col
    return m


def sofa_small():
    """小雙人沙發（2×1）：薰衣草紫絨布、拉扣椅背、兩顆抱枕。椅背在 v 小那側、座位朝 +v。"""
    sc = grid_scene(2, 1, zmax=100)
    du, dv = 64, 32
    shadow_rect(sc, 3, du - 3, 3, dv - 3)
    for (pu, pv) in ((6, 6), (du - 6, 6), (6, dv - 5), (du - 6, dv - 5)):
        sc.add(Ell(pu, pv, 2.0, 2.4, 2.4, 2.4, solid_mat(WOOD, 4, k=3.0)))
    sc.add(Box(4, du - 4, 4, dv - 3, 3, 13, velvet_mat(LILAC, 4)))
    tuft = lambda c: (c.ny > 0.7) & (np.mod(c.u - 4, 8) < 1.4) & (np.abs(np.mod(c.z - 20, 8) - 4) < 1.0) & (c.z > 20) & (c.z < 40)  # noqa: E731
    sc.add(Box(5, du - 5, 3, 11, 12, 40, velvet_mat(LILAC, 5, tuft)))
    sc.add(HCyl('u', 7, 40, 4.0, 5, du - 5, velvet_mat(LILAC, 5), rz=4.5))
    for (ua, ub) in ((3, 11), (du - 11, du - 3)):
        sc.add(Box(ua, ub, 4, dv - 3, 3, 23, velvet_mat(LILAC, 5)))
        sc.add(HCyl('v', (ua + ub) / 2, 23, 4.0, 4, dv - 3, velvet_mat(LILAC, 6), rz=3.4))
    for (ua, ub) in ((11, 32), (32, du - 11)):
        sc.add(Box(ua + 0.4, ub - 0.4, 11, dv - 4, 13, 20, velvet_mat(LILAC, 6)))
        sc.add(HCyl('u', dv - 5, 18.5, 2.2, ua + 0.4, ub - 0.4, velvet_mat(LILAC, 6), rz=2.0))
    # 抱枕：粉色愛心、黃色星星
    sc.add(Ell(17, 15, 28, 6.5, 3.4, 6, cloth_mat(PINK, 5, k=3.0), zmin=19))
    sc.add(Ell(48, 15, 28, 6.5, 3.4, 6, cloth_mat(SUN, 5, k=3.0), zmin=19))
    ht = from_ascii(['a.a', 'aaa', '.a.'], {'a': CHERRY[5]})
    sc.sprite(ht, 17, 18.6, 29, anchor=(0.5, 0.5), depth=(19, 20), edge=False)
    stt = from_ascii(['.a.', 'aaa', '.a.'], {'a': CREAMW[8]})
    sc.sprite(stt, 48, 18.6, 29, anchor=(0.5, 0.5), depth=(50, 20), edge=False)
    return render(sc, 'sofa_small')


def armchair_teal():
    """絨布扶手椅（1×1）：青綠絨布、圓背、針織毯。"""
    sc = grid_scene(1, 1, zmax=90)
    du = dv = 32
    shadow_rect(sc, 3, du - 3, 3, dv - 3)
    for (pu, pv) in ((6, 6), (du - 6, 6), (6, dv - 5), (du - 6, dv - 5)):
        sc.add(Ell(pu, pv, 2.0, 2.2, 2.2, 2.4, solid_mat(WOOD, 4, k=3.0)))
    sc.add(Box(4, du - 4, 4, dv - 3, 3, 12, velvet_mat(TEAL, 4)))
    tuft = lambda c: (c.ny > 0.7) & (np.mod(c.u - 8, 8) < 1.4) & (np.abs(np.mod(c.z - 20, 8) - 4) < 1.0) & (c.z > 20) & (c.z < 38)  # noqa: E731
    sc.add(Box(5, du - 5, 3, 11, 11, 38, velvet_mat(TEAL, 5, tuft)))
    sc.add(HCyl('u', 7, 38, 4.0, 5, du - 5, velvet_mat(TEAL, 5), rz=5.5))
    for (ua, ub) in ((3, 10), (du - 10, du - 3)):
        sc.add(Box(ua, ub, 4, dv - 3, 3, 22, velvet_mat(TEAL, 5)))
        sc.add(HCyl('v', (ua + ub) / 2, 22, 3.5, 4, dv - 3, velvet_mat(TEAL, 6), rz=3.2))
    sc.add(Box(10.4, du - 10.4, 11, dv - 4, 12, 19, velvet_mat(TEAL, 6)))

    def knit(c):
        idx = tone_idx(c, 7, 2.6) + np.where(np.mod(c.z + c.v * 0.2, 5) < 1.4, -2, 0)
        return np.where((np.mod(np.floor(c.v / 6), 2) == 1)[:, None], pick(PINK, idx - 1), pick(CREAMW, idx))
    sc.add(Box(du - 11, du - 2, 12, 24, 5, 26, knit))
    return render(sc, 'armchair')


def side_table():
    """圓邊几（1×1）：小圓桌上一組茶壺茶杯。"""
    sc = grid_scene(1, 1, zmax=80)
    c0, H = 16, 24
    shadow_round(sc, c0, c0, 10)
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.4
        sc.add(Cyl(c0 + 6 * math.cos(a), c0 + 6 * math.sin(a), 1.4, 0, H - 2, wmat(WOOD, 4, grain='z', seed=k)))
    sc.add(Cyl(c0, c0, 7, 9, 11, solid_mat(WOOD, 5, k=3.0)))
    sc.add(Cyl(c0, c0, 11, H - 3, H, wmat(WOOD, 6, seed=5)))

    def china(c):
        idx = tone_idx(c, 7, 3.0)
        band = np.abs(c.z - (H + 5)) < 1.0
        col = pick(CREAMW, idx)
        return np.where((band & (c.face == F_SIDE))[:, None], pick(SKYB, idx - 2), col)
    sc.add(Ell(c0 - 2, c0 - 2, H + 5, 5.5, 5.5, 5.0, china, zmin=H))
    sc.add(Ell(c0 - 2, c0 - 2, H + 10, 1.6, 1.6, 1.6, solid_mat(SKYB, 5, k=3)))
    spout = from_ascii(['...a', '..a.', '.a..', 'a...'], {'a': CREAMW[7]})
    sc.sprite(add_outline(spout), c0 + 3, c0 - 2, H + 3, anchor=(0.0, 1.0), depth=(c0 + 2, c0 - 1))
    sc.add(Cyl(c0 + 5, c0 + 5, 2.6, H, H + 3.5, china, r_in=2.0))
    sc.add(Cyl(c0 + 5, c0 + 5, 2.0, H, H + 3.0, solid_mat(PUMPKIN, 3, k=1)))
    sc.add(Cyl(c0 + 5, c0 + 5, 3.6, H, H + 0.6, china))
    return render(sc, 'side_table')


BOOK_COLS = [PURPLE, ROSE, TEAL, BLUE, GOLD, LEAF, PLUM, TERRA]


def bookshelf():
    """小書櫃（1×2、靠牆）：一格格書、罐子、小水晶。開口朝 +u。"""
    sc = grid_scene(1, 2, zmax=180)
    dv = 64
    v0, v1, D = 3, dv - 3, 17
    shadow_rect(sc, 0, D, v0, v1)
    TOP = 120
    box(sc, (0, 3, v0, v1, 0, TOP), WOOD, 3, seed=31, grain='z')
    box(sc, (0, D, v0, v0 + 4, 0, TOP), WOOD, 5, seed=32)
    box(sc, (0, D, v1 - 4, v1, 0, TOP), WOOD, 5, seed=33)
    box(sc, (0, D + 2, v0 - 1.5, v1 + 1.5, TOP, TOP + 5), WOOD, 6, seed=34)
    box(sc, (0, D, v0 + 4, v1 - 4, 0, 5), WOOD, 4, seed=35)
    shelves = [5, 33, 61, 89]
    for z in shelves[1:]:
        box(sc, (3, D, v0 + 4, v1 - 4, z - 3, z), WOOD, 6, seed=int(z))
    for si, z in enumerate(shelves):
        v = v0 + 5.0
        k = 0
        while v < v1 - 6:
            r1 = hs(si, k, 1)
            if (si, k) in ((1, 3), (3, 1)):
                sc.add(Cyl(10, v + 5, 4.5, z, z + 10, solid_mat(GLASS, 5, k=3.0)))
                sc.add(Cyl(10, v + 5, 4.0, z, z + 7, solid_mat(PINK if si == 1 else TEAL, 5, k=3.0)))
                sc.add(Cyl(10, v + 5, 3.4, z + 10, z + 12, solid_mat(TERRA, 5, k=3.0)))
                v += 11
                k += 1
                continue
            th = 3 + int(r1 * 2.5)
            hgt = 15 + int(hs(si, k, 2) * 8)
            rmp = BOOK_COLS[int(hs(si, k, 3) * len(BOOK_COLS))]
            bb = (3, 3 + 12 + int(hs(si, k, 4) * 2), v, v + th, z, z + hgt)

            def book_mat(c, rmp=rmp, bb=bb, hgt=hgt, z=z, seed=k * 7 + si):
                idx = tone_idx(c, 4, 3.4)
                spine = c.face == F_U
                rel = c.z - z
                band = spine & ((np.abs(rel - hgt * 0.2) < 1.0) | (np.abs(rel - hgt * 0.8) < 1.0))
                col = pick(rmp, idx + bevel(c, bb, hi=1, lo=0, w=1.0).astype(int))
                col = np.where(band[:, None], GOLD[5] if seed % 3 else CREAMW[7], col)
                return np.where((c.face == F_TOP)[:, None], CREAMW[6], col)
            sc.add(Box(*bb, book_mat))
            v += th + (0.0 if hs(si, k, 5) > 0.25 else 1.0)
            k += 1
    ornament(sc, 'plant', D * 0.5, 40, TOP + 5)
    return render(sc, 'bookshelf')


def clock_tall():
    """老爺鐘（1×1、靠牆）：深木鐘身、圓鐘面、鐘擺小窗、頂上月亮。正面朝 +u。"""
    sc = grid_scene(1, 1, zmax=170)
    v0, v1, D = 5, 27, 15
    shadow_rect(sc, 0, D, v0, v1)
    box(sc, (0, D + 1, v0 - 1, v1 + 1, 0, 8), MAHOG, 4, seed=1)
    box(sc, (1, D - 1, v0 + 1, v1 - 1, 8, 70), MAHOG, 5, seed=2)
    box(sc, (0, D + 1, v0 - 1, v1 + 1, 70, 74), MAHOG, 5, seed=3)
    box(sc, (0, D, v0, v1, 74, 104), MAHOG, 5, seed=4)
    box(sc, (0, D + 1.5, v0 - 1.5, v1 + 1.5, 104, 108), MAHOG, 6, seed=5)
    vm = (v0 + v1) / 2
    # 鐘擺窗（玻璃＋金擺）
    sc.add(Box(D - 1.3, D - 0.6, vm - 5, vm + 5, 22, 60, solid_mat(GLASS, 3, k=1.0), edge=True))
    sc.add(Cyl(D - 1.0, vm, 0.4, 36, 56, metal_mat(GOLD, 5)) if False else Box(D - 0.9, D - 0.4, vm - 0.5, vm + 0.5, 34, 56, solid_mat(GOLD, 5, k=1.0)))
    sc.add(Ell(D - 0.4, vm, 32, 0.8, 3.2, 3.2, metal_mat(GOLD, 6)))
    # 鐘面
    face = blank(15, 15)
    yy, xx = np.mgrid[0:15, 0:15]
    r = np.hypot(xx - 7, yy - 7)
    face[r < 7.4, :3] = GOLD[4]
    face[r < 7.4, 3] = 255
    face[r < 6.2, :3] = CREAMW[8]
    for k in range(12):
        a = k * math.pi / 6
        put(face, 7 + round(5 * math.cos(a)), 7 + round(5 * math.sin(a)), IRON[3])
    for y in range(3, 8):
        put(face, 7, y, IRON[2])
    for x in range(7, 11):
        put(face, x, 7, IRON[2])
    put(face, 4, 4, CREAMW[9])
    sc.sprite(face, D + 0.2, vm, 89, anchor=(0.5, 0.5), depth=(D + 1, vm + 1))
    # 頂上：拱飾＋月亮
    sc.add(SDF(lambda u, v, z: np.maximum(np.hypot(v - vm, (z - 108) * 1.2) - 9, np.maximum(sd_slab(u, 2, 6), 108 - z)),
               (2, 6, vm - 9, vm + 9, 108, 117), sdf_mat(MAHOG, 6)))
    ornament(sc, 'moon', 4, vm, 116)
    return render(sc, 'clock_tall')


def cat_tree():
    """貓跳台（1×1）：麻繩柱、兩層有坐墊的平台、吊一顆毛線球。"""
    sc = grid_scene(1, 1, zmax=140)
    c0 = 16
    shadow_rect(sc, 2, 30, 2, 30)
    box(sc, (2, 30, 2, 30, 0, 5), WOOD, 5, seed=1)
    sc.add(Box(3, 29, 3, 29, 5, 6, cloth_mat(CREAMW, 6, k=2.0), edge=False))

    def rope(c):
        idx = tone_idx(c, 6, 3.0)
        wrap = np.mod(c.z + np.arctan2(c.v - c0, c.u - c0) * 0.6, 2.0) < 0.9
        return pick(CREAMW, np.where(wrap, idx - 3, idx - 1))
    sc.add(Cyl(c0 - 3, c0 - 3, 3.4, 6, 74, rope))
    sc.add(Cyl(c0 + 6, c0 + 6, 2.6, 6, 38, rope))
    box(sc, (1, 26, 6, 31, 38, 42), WOOD, 6, seed=2)
    sc.add(Ell(14, 19, 42.5, 10, 10, 2.6, cloth_mat(PINK, 6, k=2.6), zmin=42))
    box(sc, (2, 24, 1, 22, 74, 78), WOOD, 6, seed=3)

    def bed(c):
        idx = tone_idx(c, 5, 3.0)
        return pick(LILAC, idx)
    sc.add(Cyl(13, 11, 9, 78, 84, bed, r_in=6.0))
    sc.add(Cyl(13, 11, 7, 78, 80.5, cloth_mat(CREAMW, 7, k=2.0)))
    # 毛線球垂在上層平台邊
    sc.add(Cyl(22, 18, 0.3, 58, 74, solid_mat(CHERRY, 5, k=1)))

    def yarn(c):
        idx = tone_idx(c, 5, 3.0)
        s_ = np.mod((c.u - c.z) * 0.9, 2.0) < 0.8
        return pick(CHERRY, np.where(s_, idx - 1, idx + 1))
    sc.add(Ell(22, 18, 55, 3.6, 3.6, 3.6, yarn))
    # 小魚抱枕
    fish = from_ascii(['.aa..a', 'abbbaa', 'abcbba', '.aa..a'], {'a': SKYB[3], 'b': SKYB[6], 'c': IRON[2]})
    sc.sprite(add_outline(fish), 18, 24, 43, depth=(20, 26))
    return render(sc, 'cat_tree')


def plant_monstera():
    """龜背芋盆栽（1×1）：大陶盆＋幾片有裂口的大葉子。"""
    sc = grid_scene(1, 1, zmax=130)
    c0 = 16

    shadow_round(sc, c0, c0, 10)

    def pot(c):
        idx = tone_idx(c, 6, 3.4)
        band = (c.z > 14) & (c.z < 17)
        col = pick(CREAMW, idx)
        return np.where((band & (c.face == F_SIDE))[:, None], pick(SAGE, idx - 1), col)
    sc.add(SDF(lambda u, v, z: np.maximum(np.hypot(u - c0, v - c0) - (8 + z * 0.12), sd_slab(z, 0, 20)),
               (c0 - 11, c0 + 11, c0 - 11, c0 + 11, 0, 20), pot))
    sc.add(Cyl(c0, c0, 10.0, 18, 20.5, solid_mat(WOOD, 1, k=1.0)))
    img = blank(44, 58)
    yy, xx = np.mgrid[0:58, 0:44]
    leaves = [(22, 12, 9, 7, 0.0), (10, 24, 8, 6, -0.5), (34, 23, 8, 6, 0.5), (16, 38, 7, 5.5, -0.3), (30, 40, 7, 5, 0.4),
              (22, 28, 8, 6.5, 0.0)]
    for (lx, ly, rx, ry, rot) in leaves:
        for t in np.linspace(0, 1, 30):
            x = 22 + (lx - 22) * t
            y = 57 - (57 - ly) * t
            put(img, int(round(x)), int(round(y)), LEAF[3])
    for (lx, ly, rx, ry, rot) in leaves:
        dx, dy = xx - lx, yy - ly
        a = dx * math.cos(rot) + dy * math.sin(rot)
        b = -dx * math.sin(rot) + dy * math.cos(rot)
        m = (a / rx) ** 2 + (b / ry) ** 2 < 1
        ang = np.arctan2(b, a)
        slit = (np.abs(np.mod(ang * 5 / math.pi, 1.0) - 0.5) < 0.08) & ((a / rx) ** 2 + (b / ry) ** 2 > 0.35)
        m &= ~slit
        lv = np.clip(5 - (a * 0.5 + b * 0.6) / rx * 1.6, 2, 8).round().astype(int)
        img[m, :3] = LEAF[lv[m]]
        img[m, 3] = 255
        rib = m & (np.abs(b) < 0.6) & (a > -rx * 0.8)
        img[rib, :3] = LEAF[7]
    sc.sprite(add_outline(img, color=LEAF[0]), c0, c0, 19, anchor=(0.5, 0.98), depth=(c0 + 5, c0 + 5))
    return render(sc, 'plant_monstera')


TABLES = {'table_round': table_round, 'table_long': table_long, 'table_tier': table_tier, 'table_barrel': table_barrel,
          'table_crate': table_crate, 'table_pedestal': table_pedestal, 'table_cart': table_cart}
LAMPS = {'lamp_lantern': lamp_lantern, 'lamp_mushroom': lamp_mushroom, 'lamp_moon': lamp_moon,
         'lamp_crystal': lamp_crystal, 'lamp_candelabra': lamp_candelabra, 'lamp_pumpkin': lamp_pumpkin}
FURN = {'sofa_small': sofa_small, 'armchair': armchair_teal, 'side_table': side_table, 'bookshelf': bookshelf,
        'clock_tall': clock_tall, 'cat_tree': cat_tree, 'plant_monstera': plant_monstera}



# ═══════════════════════════════ 花朵立牌 ═══════════════════════════════

def _px(img, x, y, col):
    put(img, int(round(x)), int(round(y)), col)


def blossom(img, x, y, kind, k=0):
    if kind == 'rose':
        rmp = (CHERRY, PINK, CHERRY)[k % 3]
        ball(img, x, y, 2.6, 2.4, rmp, 5, spec=False)
        _px(img, x, y, rmp[3]); _px(img, x + 1, y - 1, rmp[7]); _px(img, x - 1, y + 1, rmp[3])
    elif kind == 'daisy':
        for a in range(6):
            t = a * math.pi / 3 + 0.3
            _px(img, x + 2 * math.cos(t), y + 1.6 * math.sin(t), CREAMW[8 if a < 3 else 7])
        _px(img, x, y, SUN[6]); _px(img, x + 1, y, SUN[5])
    elif kind == 'lily':
        rmp = (CREAMW, PINK)[k % 2]
        for a in range(5):
            t = a * 2 * math.pi / 5 - math.pi / 2 + 0.2
            for d in (1, 2, 3):
                _px(img, x + d * math.cos(t), y + d * math.sin(t) * 0.8, rmp[8 - d] if rmp is CREAMW else rmp[7 - d // 2])
        _px(img, x, y, SUN[6])
    elif kind == 'sun':
        for a in range(12):
            t = a * math.pi / 6
            _px(img, x + 4 * math.cos(t), y + 3.4 * math.sin(t), SUN[6 if a % 2 else 5])
            _px(img, x + 3 * math.cos(t), y + 2.6 * math.sin(t), SUN[7])
        ball(img, x, y, 2.2, 2.0, TIMBER, 4, spec=False)
        _px(img, x - 1, y - 1, TIMBER[6])
    elif kind == 'violet':
        rmp = (PURPLE, LILAC)[k % 2]
        for (dx, dy) in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            _px(img, x + dx, y + dy, rmp[6])
        _px(img, x - 1, y - 1, rmp[8])
        _px(img, x, y, SUN[7])
    elif kind == 'lav':
        for d in range(6):
            _px(img, x + (d % 2) * 0.6, y + d, LILAC[5 + (d % 3)])
            if d % 2 == 0:
                _px(img, x - 1, y + d, LILAC[4])
    elif kind == 'leaf':
        rmp = (PUMPKIN, CHERRY, SUN)[k % 3]
        ball(img, x, y, 2.2, 1.6, rmp, 5, spec=False)
        _px(img, x - 1, y, rmp[7])
    elif kind == 'blue':
        rmp = (SKYB, BLUE, LILAC)[k % 3]
        ball(img, x, y, 2.0, 1.8, rmp, 6, spec=False)
        _px(img, x, y, CREAMW[8])
    elif kind == 'pink':
        ball(img, x, y, 1.8, 1.6, PINK, 6, spec=False)
        _px(img, x, y, SUN[7])
    elif kind == 'dot':
        _px(img, x, y, CREAMW[8])


def bouquet(w, h, kinds, n, seed, top=0.12, depth=0.55, spread=0.85, leaves=True, stem_y=None):
    """一束花（邏輯像素立牌）：莖從底部中央散開、花朵分布在上半部。"""
    img = blank(w, h)
    bx, by = (w - 1) / 2.0, h - 1 if stem_y is None else stem_y
    pts = []
    for i in range(n):
        r1, r2 = hs(seed, i, 1), hs(seed, i, 2)
        x = bx + (r1 - 0.5) * (w - 6) * spread
        y = h * top + r2 * h * depth + abs(r1 - 0.5) * h * 0.15
        pts.append((x, y, kinds[i % len(kinds)], i))
    for (x, y, kd, i) in pts:
        steps = int(max(abs(by - y), abs(bx - x)) * 1.5) + 2
        for t in np.linspace(0, 1, steps):
            sx = bx + (x - bx) * t + math.sin(t * 3 + i) * 0.4
            sy = by + (y - by) * t
            _px(img, sx, sy, LEAF[3 + (i % 2)])
        if leaves and kd not in ('leaf',):
            t = 0.45 + hs(seed, i, 3) * 0.2
            lx, ly = bx + (x - bx) * t, by + (y - by) * t
            d = 1 if x > bx else -1
            _px(img, lx + d, ly, LEAF[6]); _px(img, lx + 2 * d, ly - 1, LEAF[5]); _px(img, lx + d, ly - 1, LEAF[7])
    for (x, y, kd, i) in sorted(pts, key=lambda p: p[1]):
        blossom(img, x, y, kd, i)
    return img


def leaf_out(img):
    return add_outline(pad(img, 1), color=LEAF[0])


# ═══════════════════════════════ 盆、瓶 ═══════════════════════════════

def pot(sc, cu, cv, r, h, rmp=TERRA, base=5, rim=True, heart=False, soil=True, band=None):
    def m(c):
        idx = tone_idx(c, base, 3.4)
        col = pick(rmp, idx)
        if band is not None:
            bd = (np.abs(c.z - h * 0.45) < 1.2) & (c.face == F_SIDE)
            col = np.where(bd[:, None], pick(band, idx), col)
        if heart:
            fx = c.u - c.v - (cu - cv)
            front = (c.nx + c.ny) > 0.85
            ht = front & (np.abs(fx) + np.abs(c.z - h * 0.45) < 2.4)
            col = np.where(ht[:, None], PINK[6], col)
        return col
    sc.add(SDF(lambda u, v, z: np.maximum(np.hypot(u - cu, v - cv) - (r * 0.82 + r * 0.18 * z / h), sd_slab(z, 0, h)),
               (cu - r - 1, cu + r + 1, cv - r - 1, cv + r + 1, 0, h), m))
    if rim:
        sc.add(Cyl(cu, cv, r + 0.8, h - 2, h + 0.5, solid_mat(rmp, base + 1, k=3.4), r_in=r - 0.8))
    if soil:
        sc.add(Cyl(cu, cv, r - 0.6, h - 2.5, h - 0.4, solid_mat(TIMBER, 2, k=1.0)))


def vase(sc, cu, cv, prof, h, mat):
    """旋轉體花瓶：prof(z)→半徑。"""
    R = max(prof(z) for z in np.linspace(0, h, 40)) + 1
    sc.add(SDF(lambda u, v, z: np.maximum((np.hypot(u - cu, v - cv) - prof(np.clip(z, 0, h))) * 0.8, sd_slab(z, 0, h)),
               (cu - R, cu + R, cv - R, cv + R, 0, h), mat))


def glaze(rmp, base=5, spec=True, pattern=None):
    def m(c):
        lit = c.nx * LIGHT[0] + c.ny * LIGHT[1] + c.nz * LIGHT[2]
        idx = np.round(base + (lit - 0.5) * 3.4).astype(int)
        if pattern is not None:
            idx = pattern(c, idx)
        col = pick(rmp, idx)
        if spec:
            col = np.where((lit > 0.92)[:, None], CREAMW[9], col)
        return col
    return m


def put_flowers(sc, img, cu, cv, z, anchor=(0.5, 0.96)):
    sc.sprite(leaf_out(img), cu, cv, z, anchor=anchor, depth=(cu + 3, cv + 3))


# ═══════════════════════════════ 各款 ═══════════════════════════════

def d_succulent():
    sc = free_scene(10, zmax=70)
    c = 10
    shadow_round(sc, c, c, 8)
    pot(sc, c, c, 7.0, 11, TERRA, heart=True)
    img = blank(19, 12)
    for (x, y, r, b) in ((9, 7, 4.4, 4), (4, 8, 3.2, 5), (14, 8, 3.2, 5), (6, 4, 3.0, 6), (12, 4, 3.0, 6), (9, 3, 2.6, 7)):
        ball(img, x, y, r, r * 0.75, SAGE, b, spec=False)
    _px(img, 7, 1, PINK[6]); _px(img, 3, 5, PINK[5]); _px(img, 11, 5, PINK[5])
    put_flowers(sc, img, c, c, 11, anchor=(0.5, 0.93))
    return render(sc, 'succulent', 'decor')


def d_daisypot():
    sc = free_scene(8, zmax=80)
    c = 8
    shadow_round(sc, c, c, 6)
    pot(sc, c, c, 5.6, 10, SKYB, base=5)
    put_flowers(sc, bouquet(16, 24, ['daisy'], 7, 3, top=0.1, depth=0.35), c, c, 10)
    return render(sc, 'daisypot', 'decor')


def d_violetpot():
    sc = free_scene(10, zmax=70)
    c = 10
    shadow_round(sc, c, c, 8)
    pot(sc, c, c, 7.0, 10, CREAMW, base=6, band=LILAC)
    img = blank(18, 10)
    for (x, y) in ((4, 6), (9, 7), (14, 6), (6, 4), (12, 4), (9, 3)):
        ball(img, x, y, 2.6, 1.8, LEAF, 4, spec=False)
    for i, (x, y) in enumerate(((5, 3), (9, 2), (13, 3), (3, 6), (15, 6), (8, 5), (11, 6))):
        blossom(img, x, y, 'violet', i)
    put_flowers(sc, img, c, c, 10, anchor=(0.5, 0.92))
    return render(sc, 'violetpot', 'decor')


def cage_img(w, h, birds=1):
    img = blank(w, h)
    cx = (w - 1) / 2.0
    dome = h * 0.35
    for x in range(w):
        dx = (x - cx) / (w / 2.0)
        top = dome * (1 - math.sqrt(max(0.0, 1 - dx * dx))) + 2
        if x % 2 == 0 or x in (0, w - 1):
            for y in range(int(top), h - 3):
                put(img, x, y, BRASS[5] if x < cx else BRASS[4])
        put(img, x, int(top), BRASS[6])
    for y in (int(h * 0.55), h - 4):
        for x in range(w):
            put(img, x, y, BRASS[5])
    for x in range(1, w - 1):
        put(img, x, h - 3, BRASS[4]); put(img, x, h - 2, BRASS[3])
    put(img, int(cx), 0, BRASS[6]); put(img, int(cx), 1, BRASS[5])
    # 棲木＋小鳥
    py = int(h * 0.68)
    for x in range(2, w - 2):
        put(img, x, py, WOOD[5])
    for b in range(birds):
        bx = int(cx - 2 + b * 4 - (birds - 1) * 2)
        rmp = (SUN, SKYB)[b % 2]
        for (dx, dy, k) in ((0, -1, 6), (1, -1, 6), (-1, -2, 7), (0, -2, 7), (1, -2, 6), (0, -3, 7), (-1, -1, 5), (2, -1, 5)):
            put(img, bx + dx, py + dy, rmp[k])
        put(img, bx, py - 3, rmp[7]); put(img, bx - 1, py - 3, IRON[2]); put(img, bx - 2, py - 2, PUMPKIN[6])
    # 纏在籠上的小花
    for (x, y) in ((1, int(h * 0.5)), (w - 2, int(h * 0.4)), (2, h - 5)):
        put(img, x, y, PINK[6]); put(img, x + 1, y + 1, LEAF[5])
    return img


def d_birdcage_small():
    sc = free_scene(7, zmax=70)
    c = 7
    shadow_round(sc, c, c, 5)
    sc.add(Cyl(c, c, 5.5, 0, 2.5, metal_mat(BRASS, 4)))
    sc.sprite(add_outline(pad(cage_img(13, 20, 1), 1)), c, c, 2, depth=(c + 2, c + 2))
    return render(sc, 'birdcage_small', 'decor')


def d_birdcage_large():
    sc = free_scene(8, zmax=110)
    c = 8
    shadow_round(sc, c, c, 6)
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.4
        sc.add(Ell(c + 5 * math.cos(a), c + 5 * math.sin(a), 1, 2.2, 2.2, 1.6, metal_mat(BRASS, 5)))
    sc.add(Cyl(c, c, 1.0, 0, 34, metal_mat(BRASS, 5)))
    sc.add(Cyl(c, c, 6.5, 34, 36, metal_mat(BRASS, 4)))
    sc.sprite(add_outline(pad(cage_img(17, 26, 2), 1)), c, c, 36, depth=(c + 3, c + 3))
    return render(sc, 'birdcage_large', 'decor')


def d_bonsai():
    sc = free_scene(12, zmax=60)
    c = 12
    shadow_rect(sc, c - 10, c + 10, c - 7, c + 7)
    sbox(sc, c - 9, c + 9, c - 6, c + 6, 0, 5, TERRA, 4)
    sc.add(Box(c - 8, c + 8, c - 5, c + 5, 5, 5.6, solid_mat(MOSS, 5, k=1.0)))
    img = blank(26, 20)
    # 樹幹
    for y in range(8, 20):
        x = 13 + int(round(math.sin(y * 0.45) * 2.0))
        put(img, x, y, TIMBER[4]); put(img, x + 1, y, TIMBER[6]); put(img, x - 1, y, TIMBER[3])
    for (x0, y0, x1, y1) in ((13, 11, 5, 7), (14, 9, 21, 6)):
        for t in np.linspace(0, 1, 10):
            put(img, round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t), TIMBER[5])
    for (x, y, rx, ry) in ((5, 6, 4.4, 2.8), (21, 5, 4.4, 2.8), (13, 3, 5.0, 3.0), (9, 9, 3.0, 2.0)):
        ball(img, x, y, rx, ry, MOSS, 5, spec=False)
        _px(img, x - 1, y - 1, MOSS[8])
    put_flowers(sc, img, c, c, 5.6, anchor=(0.5, 0.97))
    return render(sc, 'bonsai', 'decor')


def d_ivy_hanging():
    sc = free_scene(9, zmax=120)
    c = 9
    shadow_round(sc, c, c, 6)
    sc.add(Cyl(c, c, 5, 0, 2, metal_mat(IRON, 4)))
    sc.add(Cyl(c - 3, c - 3, 1.0, 2, 78, metal_mat(IRON, 5)))
    sc.add(HCyl('u', c - 3, 77, 0.9, c - 3, c + 8, metal_mat(IRON, 5)))
    sc.add(Ell(c - 3, c - 3, 80, 1.8, 1.8, 1.8, metal_mat(IRON, 6)))
    for dv_ in (-3, 3):
        sc.add(Cyl(c + 8, c - 3 + dv_ * 0.3, 0.25, 58, 77, metal_mat(IRON, 6)))

    def basket(cc):
        idx = tone_idx(cc, 6, 3.0) + np.where(np.mod(np.floor(cc.z / 2) + np.floor(np.arctan2(cc.v - c + 3, cc.u - c - 8) * 4), 2) == 0, 1, 0)
        return pick(SUN, idx - 2)
    sc.add(Ell(c + 8, c - 3, 58, 7, 7, 6, basket, zcut=58))
    img = blank(22, 36)
    for (x0, ln, ph) in ((3, 30, 0.0), (8, 22, 1.0), (13, 34, 2.0), (18, 26, 0.5)):
        for y in range(4, ln):
            x = int(round(x0 + math.sin(y * 0.4 + ph) * 1.2))
            put(img, x, y, LEAF[3])
            if y % 3 == 0:
                put(img, x - 1, y, LEAF[6]); put(img, x + 1, y + 1, LEAF[5]); put(img, x - 1, y + 1, LEAF[7])
    for x in range(1, 21):
        put(img, x, 3 + (x % 2), LEAF[5 + (x % 3)])
        put(img, x, 4, LEAF[4])
    sc.sprite(leaf_out(img), c + 8, c - 3, 59, anchor=(0.5, 0.12), depth=(c + 14, c + 3))
    return render(sc, 'ivy_hanging', 'decor')


def d_roses_vase():
    sc = free_scene(7, zmax=90)
    c = 7
    shadow_round(sc, c, c, 5)

    def glassv(cc):
        lit = cc.nx * LIGHT[0] + cc.ny * LIGHT[1] + cc.nz * LIGHT[2]
        idx = np.round(4 + (lit - 0.5) * 3).astype(int)
        col = pick(GLASS, idx)
        water = cc.z < 10
        col = np.where(water[:, None], pick(TEAL, idx + 1), col)
        return np.where((lit > 0.9)[:, None], CREAMW[9], col)
    vase(sc, c, c, lambda z: 3.2 + 1.4 * np.sin(np.clip(z / 16, 0, 1) * math.pi * 0.8) - 0.6 * (z > 14), 18, glassv)
    put_flowers(sc, bouquet(18, 22, ['rose'], 7, 11, top=0.08, depth=0.35), c, c, 17)
    return render(sc, 'roses_vase', 'decor')


def d_lily_vase():
    sc = free_scene(8, zmax=100)
    c = 8
    shadow_round(sc, c, c, 6)
    vase(sc, c, c, lambda z: 3.0 + 3.0 * np.sin(np.clip(z / 20, 0, 1) * math.pi) ** 1.5, 20, glaze(BLUE, 5))
    sc.add(Cyl(c, c, 2.8, 19.5, 21, glaze(BLUE, 6), r_in=2.0))
    put_flowers(sc, bouquet(22, 26, ['lily', 'lily', 'lav'], 8, 12, top=0.06, depth=0.4), c, c, 20)
    return render(sc, 'lily_vase', 'decor')


def d_sunflower_vase():
    sc = free_scene(7, zmax=110)
    c = 7
    shadow_round(sc, c, c, 5)
    vase(sc, c, c, lambda z: 3.6 - z * 0.03 + 0.6 * np.sin(np.clip(z / 22, 0, 1) * math.pi * 2), 22,
         glaze(CREAMW, 6, pattern=lambda cc, i: np.where(np.abs(cc.z - 15) < 1.2, i - 3, i)))
    put_flowers(sc, bouquet(18, 30, ['sun'], 3, 4, top=0.12, depth=0.25, spread=0.75), c, c, 22)
    return render(sc, 'sunflower_vase', 'decor')


def d_autumn_vase():
    sc = free_scene(8, zmax=100)
    c = 8
    shadow_round(sc, c, c, 6)
    vase(sc, c, c, lambda z: 2.6 + 3.4 * np.sin(np.clip((z + 2) / 22, 0, 1) * math.pi) ** 2, 20, metal_mat(COPPER, 5))
    put_flowers(sc, bouquet(24, 28, ['leaf'], 14, 21, top=0.05, depth=0.5, spread=0.95, leaves=False), c, c, 19)
    return render(sc, 'autumn_vase', 'decor')


def d_potted_fern():
    sc = free_scene(10, zmax=110)
    c = 10
    shadow_round(sc, c, c, 8)
    pot(sc, c, c, 7.5, 12, TERRA, band=TERRA[2:] if False else None)
    img = blank(32, 30)
    for k in range(7):
        ang = math.pi * (0.12 + 0.76 * k / 6)
        L = 15 + (3 if k in (2, 3, 4) else 0)
        x0, y0 = 15.5, 29
        for s in range(L):
            t = s / L
            a = ang + (t * 0.5 if k < 3 else -t * 0.5 if k > 3 else 0)
            x = x0 - math.cos(ang) * s * 1.0 - (math.cos(ang) * t * t * 3)
            y = y0 - math.sin(ang) * s * 1.0 + t * t * 6
            _px(img, x, y, LEAF[4])
            if s > 2 and s % 2 == 0:
                w_ = int(3 * (1 - t)) + 1
                for d in range(1, w_ + 1):
                    _px(img, x - math.sin(ang) * d, y - math.cos(ang) * d * 0.6 - 0.5, LEAF[6])
                    _px(img, x + math.sin(ang) * d, y + math.cos(ang) * d * 0.6 - 0.5, LEAF[5])
    put_flowers(sc, img, c, c, 11, anchor=(0.5, 0.97))
    return render(sc, 'potted_fern', 'decor')


def d_window_box():
    sc = free_scene(16, zmax=60)
    c = 16
    shadow_rect(sc, c - 14, c + 14, c - 5, c + 5)

    def planks(cc, idx, col):
        return np.where(((cc.face != F_TOP) & (np.mod(cc.z, 4) < 0.9))[:, None], pick(WOOD, idx - 2), col)
    box(sc, (c - 14, c + 14, c - 5, c + 5, 0, 9), WOOD, 5, seed=3, deco=planks)
    sc.add(Box(c - 13, c + 13, c - 4, c + 4, 0, 8.6, solid_mat(TIMBER, 2, k=1.0)))
    sc.add(Box(c - 13, c + 13, c - 4, c + 4, 0, 8.4, solid_mat(MOSS, 4, k=1.0)))
    img = bouquet(36, 14, ['violet', 'pink', 'violet', 'dot'], 18, 31, top=0.1, depth=0.4, spread=1.0)
    put_flowers(sc, img, c, c, 8.4, anchor=(0.5, 0.85))
    return render(sc, 'window_box', 'decor')


def d_blue_urn():
    sc = free_scene(12, zmax=140)
    c = 12
    shadow_round(sc, c, c, 10)

    def stone(cc):
        lit = cc.nx * LIGHT[0] + cc.ny * LIGHT[1] + cc.nz * LIGHT[2]
        idx = np.round(5 + (lit - 0.5) * 3.4).astype(int)
        n = h32(np.floor(cc.u / 2), np.floor(cc.v / 2), np.floor(cc.z / 2), 3) > 0.8
        return pick(STONE, np.where(n, idx - 1, idx))
    sbox(sc, c - 8, c + 8, c - 8, c + 8, 0, 4, STONE, 5)

    def prof(z):
        return np.where(z < 8, 3.0 + 0.0 * z, np.where(z < 12, 3 + (z - 8) * 1.2, 7.8 + 1.6 * np.sin(np.clip((z - 12) / 16, 0, 1) * math.pi * 0.9)))
    sc.add(SDF(lambda u, v, z: np.maximum((np.hypot(u - c, v - c) - prof(np.clip(z - 4, 0, 30))) * 0.7, sd_slab(z, 4, 32)),
               (c - 11, c + 11, c - 11, c + 11, 4, 32), stone))
    sc.add(Cyl(c, c, 10.2, 30, 33, solid_mat(STONE, 6, k=3), r_in=8.6))
    sc.add(Cyl(c, c, 8.8, 30, 32.5, solid_mat(TIMBER, 2, k=1)))
    put_flowers(sc, bouquet(34, 34, ['blue', 'blue', 'dot', 'lav'], 20, 41, top=0.08, depth=0.55, spread=1.0), c, c, 31,
                anchor=(0.5, 0.88))
    return render(sc, 'blue_urn', 'decor')


def d_wildflower_basket():
    sc = free_scene(14, zmax=100)
    c = 14
    shadow_round(sc, c, c, 12)

    def wicker(cc):
        idx = tone_idx(cc, 6, 3.0)
        w_ = np.mod(np.floor(cc.z / 2) + np.floor(np.arctan2(cc.v - c, cc.u - c) * 7), 2) == 0
        return pick(SUN, np.where(w_, idx - 1, idx - 3))
    sc.add(SDF(lambda u, v, z: np.maximum(np.hypot(u - c, v - c) - (9 + z * 0.18), sd_slab(z, 0, 12)),
               (c - 12, c + 12, c - 12, c + 12, 0, 12), wicker))
    sc.add(Cyl(c, c, 11.6, 10.5, 12.8, solid_mat(SUN, 3, k=3), r_in=10.2))
    img = bouquet(40, 30, ['daisy', 'violet', 'pink', 'lav', 'sun', 'blue'], 22, 51, top=0.12, depth=0.55, spread=1.0)
    put_flowers(sc, img, c, c, 12, anchor=(0.5, 0.86))
    # 提把
    sc.add(SDF(lambda u, v, z: np.maximum(np.abs(np.hypot(u - v, (z - 12) * 1.15) - 13.5) - 0.9, np.abs(u + v - 2 * c) - 1.2),
               (0, 2 * c, 0, 2 * c, 12, 30), wicker))
    return render(sc, 'wildflower_basket', 'decor')


def d_flower_case():
    """星光花櫃：長腳木花槽，滿滿的花，上面一道黃銅拱、掛一串小星星燈。"""
    sc = free_scene(16, zmax=110)
    c = 16
    u0, u1, v0, v1 = c - 15, c + 15, c - 6, c + 6
    shadow_rect(sc, u0, u1, v0, v1)
    for (uu, vv) in ((u0 + 2, v0 + 2), (u1 - 2, v0 + 2), (u0 + 2, v1 - 2), (u1 - 2, v1 - 2)):
        sc.add(Cyl(uu, vv, 1.4, 0, 10, solid_mat(WOOD, 4, k=3)))

    def planks(cc, idx, col):
        return np.where(((cc.face != F_TOP) & (np.mod(cc.z - 10, 4) < 0.9))[:, None], pick(WOOD, idx - 2), col)
    box(sc, (u0, u1, v0, v1, 9, 20), WOOD, 5, seed=4, deco=planks)
    sc.add(Box(u0 + 1, u1 - 1, v0 + 1, v1 - 1, 9, 19.6, solid_mat(MOSS, 4, k=1.0)))
    img = bouquet(40, 18, ['pink', 'violet', 'blue', 'daisy', 'rose', 'lav'], 26, 61, top=0.1, depth=0.55, spread=1.0)
    put_flowers(sc, img, c, c, 19.6, anchor=(0.5, 0.86))
    # 黃銅拱＋星星燈串
    def arch(u, v, z):
        return np.maximum(np.abs(np.hypot((u - c) * 1.0, (z - 20) * 0.75) - 15.5) - 0.8, np.abs(v - c) - 0.8)
    sc.add(SDF(arch, (u0 - 1, u1 + 1, c - 1, c + 1, 20, 44), metal_mat(BRASS, 5)))
    for k in range(9):
        a = math.pi * (k + 0.5) / 9
        uu = c - 15.5 * math.cos(a)
        zz = 20 + 15.5 / 0.75 * math.sin(a) - 2.5
        st = from_ascii(['.a.', 'aba', '.a.'], {'a': SUN[6], 'b': SUN[8]})
        sc.sprite(add_outline(st, color=SUN[2]), uu, c + 1, zz, anchor=(0.5, 0.2), depth=(uu + 1, c + 2), edge=False)
    sc.lights.append((c, c, 34))
    return render(sc, 'flower_case', 'decor')


def mini_rack(pid, stuff):
    """桌上的小擺架（兩層小木架），stuff(sc, z, u_mid) 擺東西。"""
    sc = free_scene(13, zmax=60)
    c = 13
    u0, u1, v0, v1 = c - 5, c + 5, c - 12, c + 12
    shadow_rect(sc, u0, u1, v0, v1)
    box(sc, (u0, u0 + 2, v0, v1, 0, 24), WOOD, 4, seed=1, grain='z')
    for vv in (v0, v1 - 2):
        box(sc, (u0, u1, vv, vv + 2, 0, 24), WOOD, 5, seed=int(vv))
    for z in (0, 11):
        box(sc, (u0 + 2, u1, v0 + 2, v1 - 2, z, z + 2), WOOD, 6, seed=int(z) + 4)
    box(sc, (u0, u1 + 1, v0 - 1, v1 + 1, 24, 26), WOOD, 6, seed=9)
    stuff(sc, 2, 13, (v0 + 4, v1 - 4))
    stuff(sc, 13, 26, (v0 + 4, v1 - 4))
    return render(sc, pid, 'decor')


def herbs(sc, z, z2, vr):
    vs = np.linspace(vr[0] + 1, vr[1] - 1, 4)
    for i, vv in enumerate(vs):
        if z < 10:
            sc.sprite(jar_img(4, 6, (SUN, LEAF, CHERRY, LILAC)[i]), 13, vv, z, depth=(14, vv))
        else:
            img = blank(5, 9)
            for y in range(9):
                for x in range(5):
                    if abs(x - 2) <= (y // 3):
                        put(img, x, y, (LEAF, MOSS, LILAC, SAGE)[i][4 + (x + y) % 3])
            for x in range(5):
                put(img, x, 1, WOOD[5])
            sc.sprite(add_outline(img), 13, vv, z, depth=(14, vv))


def crystals(sc, z, z2, vr):
    vs = np.linspace(vr[0] + 1, vr[1] - 1, 4)
    for i, vv in enumerate(vs):
        rmp = (LILAC, TEAL, PINK, SKYB)[i]
        img = blank(7, 9)
        for (x0, h) in ((3, 9), (1, 6), (5, 5)):
            for y in range(9 - h, 9):
                put(img, x0, y, rmp[6]); put(img, x0 + (1 if x0 < 6 else 0), y, rmp[4])
            put(img, x0, 9 - h, rmp[8])
        sc.sprite(add_outline(img), 13, vv, z, depth=(14, vv))
        sc.fine_px(13, vv, z + 6, CREAMW[9])


def potions(sc, z, z2, vr):
    vs = np.linspace(vr[0] + 1, vr[1] - 1, 4)
    for i, vv in enumerate(vs):
        rmp = (PINK, TEAL, SUN, LILAC)[(i + (z > 10)) % 4]
        if i % 2 == 0:
            img = heart_bottle(rmp) if z < 10 else flask_img('round', rmp, 9)
        else:
            img = bottle_img(3, 8, rmp, label=GOLD[6])
        if img.shape[2] == 4 and z < 10 and i % 2 == 0:
            img = add_outline(img)
        sc.sprite(img, 13, vv, z, depth=(14, vv))


def d_rug_round():
    sc = free_scene(34, zmax=10, margin=8)
    c = 34

    def mat(cc):
        r = np.hypot(cc.u - c, cc.v - c)
        ring = np.floor(r / 3.4).astype(int)
        cols = [PINK, CREAMW, TEAL, CREAMW, LILAC, CREAMW, PINK, SUN, LILAC, CREAMW]
        col = np.zeros(cc.u.shape + (3,), np.uint8)
        braid = np.mod(np.arctan2(cc.v - c, cc.u - c) * r / 2.2 + ring, 2.0) < 1.0
        for k, rm in enumerate(cols):
            m = ring == k
            if m.any():
                col[m] = pick(rm, np.where(braid[m], 6, 5))
        star = star_mask(cc.u - cc.v, (cc.u + cc.v) * 0.5, 0, c, 7)
        col[star] = SUN[7]
        return col
    sc.add(Cyl(c, c, 33, 0, 0.8, mat, edge=False))
    return render(sc, 'rug_round', 'decor', shadow=(0, 0, 0, 0))


def d_rug_star():
    sc = free_scene(32, zmax=10, margin=8)
    c = 32
    u0, u1, v0, v1 = c - 30, c + 30, c - 18, c + 18

    def mat(cc):
        idx = np.full(cc.u.shape, 3)
        border = (cc.u < u0 + 4) | (cc.u > u1 - 4) | (cc.v < v0 + 4) | (cc.v > v1 - 4)
        col = pick(BLUE, idx)
        col = np.where(border[:, None], pick(LILAC, 4 + (np.mod(np.floor((cc.u + cc.v) / 3), 2)).astype(int)), col)
        gold = (np.abs(cc.u - (u0 + 4)) < 0.8) | (np.abs(cc.u - (u1 - 4)) < 0.8) | (np.abs(cc.v - (v0 + 4)) < 0.8) | (np.abs(cc.v - (v1 - 4)) < 0.8)
        col = np.where((gold & ~((cc.u < u0 + 3) | (cc.u > u1 - 3) | (cc.v < v0 + 3) | (cc.v > v1 - 3)))[:, None], GOLD[5], col)
        st = h32(np.floor(cc.u / 2.5), np.floor(cc.v / 2.5), 77) > 0.93
        col = np.where((st & ~border)[:, None], SUN[7], col)
        moon = (np.hypot(cc.u - c, cc.v - c) < 7) & (np.hypot(cc.u - c - 3, cc.v - c + 2) > 6)
        col = np.where(moon[:, None], SUN[6], col)
        return col
    sc.add(Box(u0, u1, v0, v1, 0, 0.8, mat, edge=False))
    for k in range(int((v1 - v0) / 2.4)):
        vv = v0 + 1 + k * 2.4
        sc.add(Box(u1, u1 + 2.4, vv, vv + 0.8, 0, 0.5, solid_mat(CREAMW, 7, k=1), edge=False))
        sc.add(Box(u0 - 2.4, u0, vv, vv + 0.8, 0, 0.5, solid_mat(CREAMW, 7, k=1), edge=False))
    return render(sc, 'rug_star', 'decor', shadow=(0, 0, 0, 0))


DECOR = {
    'succulent': d_succulent, 'daisypot': d_daisypot, 'violetpot': d_violetpot, 'birdcage_small': d_birdcage_small,
    'bonsai': d_bonsai, 'ivy_hanging': d_ivy_hanging, 'roses_vase': d_roses_vase, 'lily_vase': d_lily_vase,
    'sunflower_vase': d_sunflower_vase, 'autumn_vase': d_autumn_vase, 'potted_fern': d_potted_fern,
    'window_box': d_window_box, 'birdcage_large': d_birdcage_large, 'blue_urn': d_blue_urn,
    'wildflower_basket': d_wildflower_basket, 'flower_case': d_flower_case,
    'herb_shelf': lambda: mini_rack('herb_shelf', herbs),
    'crystal_shelf': lambda: mini_rack('crystal_shelf', crystals),
    'potion_shelf': lambda: mini_rack('potion_shelf', potions),
    'rug_round': d_rug_round, 'rug_star': d_rug_star,
}

# ═══════════════════════════════ 目錄（跟 C# 對）═══════════════════════════════

ROOT = os.environ.get('WITCH_ROOT') or os.path.dirname(TOOLS)
RES = os.path.join(ROOT, 'Assets', 'Resources')
FURN8 = os.path.join(RES, 'furniture8')
DECOR8 = os.path.join(RES, 'decor8')
CS_OUT = os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'FurnitureArt8.cs')


def _src(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def _num(text, pat):
    m = re.search(pat, text)
    if not m:
        raise SystemExit('讀不到常數：' + pat)
    return float(m.group(1))


_FURN_CS = _src('Assets/Scripts/Data/Furniture.cs')
FOOT = {'sale_table': (2, 1)}
for sid, d in re.findall(r'\("(shelf_\w+)",\s*"[^"]*",\s*\d+,\s*"[^"]*",\s*(\d+)\)', _FURN_CS):
    FOOT[sid] = (1, int(d))
for tid, w, h in re.findall(r'\("(\w+)",\s*"[^"]*",\s*\d+,\s*"[^"]*",\s*(\d+),\s*(\d+)\)', _FURN_CS):
    FOOT[tid] = (int(w), int(h))
for tid, w, h, kind, wall in re.findall(r'\("(\w+)",\s*"[^"]*",\s*\d+,\s*"[^"]*",\s*(\d+),\s*(\d+),\s*FurnKind\.(\w+),\s*(true|false)\)', _FURN_CS):
    FOOT[tid] = (int(w), int(h))
WALLS = {tid for tid, wall in re.findall(r'\("(\w+)",\s*"[^"]*",\s*\d+,\s*"[^"]*",\s*\d+,\s*\d+,\s*FurnKind\.\w+,\s*(true)\)', _FURN_CS)}
_DECOR_CS = _src('Assets/Scripts/Data/Decor.cs')
DECOR_IDS = re.findall(r'Id = "(\w+)"', _DECOR_CS)

FURN_FUNCS = {'sale_table': draw_sale_table}
FURN_FUNCS.update({sid: (lambda s=sid: draw_shelf(s)) for sid in SHELVES})
FURN_FUNCS.update(TABLES)
FURN_FUNCS.update(LAMPS)
FURN_FUNCS.update(FURN)


def check_catalog():
    bad = []
    for pid in FURN_FUNCS:
        if pid not in FOOT:
            bad.append('%s：Furniture.cs 沒有這一款' % pid)
    for pid in FOOT:
        if pid not in FURN_FUNCS:
            bad.append('%s：產生器沒有畫' % pid)
    for pid in DECOR_IDS:
        if pid not in DECOR:
            bad.append('%s（裝飾）：產生器沒有畫' % pid)
    for pid, sd in SHELVES.items():
        if FOOT.get(pid) != (1, sd['dep']):
            bad.append('%s：佔地 %s ≠ 圖的 1×%d' % (pid, FOOT.get(pid), sd['dep']))
    if bad:
        raise SystemExit('⚠️ 目錄對不上：\n  ' + '\n  '.join(bad))


def build(only=None):
    out = {}
    for pid, fn in FURN_FUNCS.items():
        if only and pid not in only:
            continue
        a = fn()
        a.kind = 'furniture'
        out[pid] = a
    for pid, fn in DECOR.items():
        if only and pid not in only:
            continue
        out[pid] = fn()
    return out


# ═══════════════════════════════ C#（陳列位、實心範圍、光暈點）═══════════════════════════════

def _f(v):
    s = ('%.1f' % v).rstrip('0').rstrip('.')
    return s if s not in ('-0', '') else '0'


def write_cs(arts):
    rows = []
    for pid in sorted(arts):
        a = arts[pid]
        h, w = a.img.shape[:2]
        bw, bh, x0, y0, x1, y1 = a.bounds()
        slots = ('new[]\n                {\n' + ''.join('                    new DisplaySlot(%sf, %sf, %sf, %sf, %d),\n' % (
            _f(x), _f(y), _f(mw), _f(mh), row) for (x, y, mw, mh, row) in a.slots) + '                }') if a.slots else 'NoSlots'
        lights = ('new[] { ' + ', '.join('new Vector2(%sf, %sf)' % (_f(x), _f(y)) for (x, y) in a.lights) + ' }') if a.lights else 'NoLights'
        rows.append('            ["%s"] = new Entry(%d, %d, new ArtBox(%d, %d, %d, %d, %d, %d),\n                %s,\n                %s),'
                    % (pid, w, h, w, h, x0, y0, x1, y1, slots, lights))
    cs = '''// <auto-generated>
// ⚠️ 自動產生，不要手改。產生器：tools/gen_furniture8.py（細畫版家具／裝飾 Resources/furniture8、decor8）
//    重跑：python tools/gen_furniture8.py（加 --preview <資料夾> 輸出預覽；--restore 刪掉細畫版、這張表清空）
// </auto-generated>
using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Data
{
    /// <summary>
    /// 細畫版家具／裝飾圖（tools/gen_furniture8.py）跟圖一起量出來的資料：
    ///   · 圖的尺寸（W×H）—— 載到的圖尺寸對不上（例如退回舊圖）就一律當沒有，呼叫端退回舊表；
    ///   · 實心範圍（不含半透明的接地影子；穿牆判斷用，同 FurnitureBounds）；
    ///   · 陳列位（同 ShopDisplaySlots：相對錨點、y 朝上、翻面 X 取負）；
    ///   · 光暈的中心（相對錨點、y 朝上、沒翻面；燈的半徑顏色在 Furniture／Decor 的 Light）。
    /// 錨點＝圖的正下方中央（吃格子的＝佔地前角；裝飾＝落腳點）。
    /// </summary>
    public static class FurnitureArt8
    {
        sealed class Entry
        {
            public readonly int W, H;
            public readonly ArtBox Box;
            public readonly DisplaySlot[] Slots;
            public readonly Vector2[] Lights;

            public Entry(int w, int h, ArtBox box, DisplaySlot[] slots, Vector2[] lights)
            { W = w; H = h; Box = box; Slots = slots; Lights = lights; }
        }

        static readonly DisplaySlot[] NoSlots = new DisplaySlot[0];
        static readonly Vector2[] NoLights = new Vector2[0];

        static readonly Dictionary<string, Entry> Table = new()
        {
%BODY%
        };

        static Entry Match(string id, float w, float h) =>
            id != null && Table.TryGetValue(id, out var e) && e.W == (int)w && e.H == (int)h ? e : null;

        /// <summary>這張圖是不是細畫版（尺寸對得上表）。</summary>
        public static bool Matches(string id, float w, float h) => Match(id, w, h) != null;

        public static bool TryGetSlots(string id, float w, float h, out DisplaySlot[] slots)
        {
            var e = Match(id, w, h);
            slots = e?.Slots;
            return e != null;
        }

        public static bool TryGetBounds(string id, float w, float h, out ArtBox box)
        {
            var e = Match(id, w, h);
            box = e != null ? e.Box : default;
            return e != null;
        }

        /// <summary>光暈中心（相對錨點、沒翻面）；圖對不上或不發光回空陣列。</summary>
        public static Vector2[] LightPoints(string id, float w, float h) => Match(id, w, h)?.Lights ?? NoLights;
    }
}
'''.replace('%BODY%', '\n'.join(rows))
    with open(CS_OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(cs)


# ═══════════════════════════════ 擺放驗算（RoomLayout.ArtFits 的 Python 版）═══════════════════════════════

_SHOP = _src('Assets/Scripts/Data/ShopRoom.cs')
TILE_W = _num(_SHOP, r'TileW\s*=\s*([\d.]+)f')
TILE_H = _num(_SHOP, r'TileH\s*=\s*([\d.]+)f')
GRID_W = int(_num(_SHOP, r'GridW\s*=\s*(\d+)'))
GRID_H = int(_num(_SHOP, r'GridH\s*=\s*(\d+)'))
ORIGIN_X = _num(_SHOP, r'OriginX\s*=\s*(-?[\d.]+)f')
ORIGIN_Y = _num(_SHOP, r'OriginY\s*=\s*(-?[\d.]+)f')
WALL_H = _num(_SHOP, r'WallH\s*=\s*([\d.]+)f')


def g2w(gx, gy):
    return (ORIGIN_X + (gx - gy) * TILE_W / 2.0, ORIGIN_Y - (gx + gy) * TILE_H / 2.0)


def tile_front(gx, gy):
    x, y = g2w(gx, gy)
    return x, y - TILE_H / 2.0


def _silhouette():
    top = (ORIGIN_X, ORIGIN_Y + TILE_H / 2)
    cx, cy = g2w(GRID_W - 1, 0)
    right = (cx + TILE_W / 2, cy)
    cx, cy = g2w(0, GRID_H - 1)
    left = (cx - TILE_W / 2, cy)
    cx, cy = g2w(GRID_W - 1, GRID_H - 1)
    bottom = (cx, cy - TILE_H / 2)
    up = lambda p: (p[0], p[1] + WALL_H)          # noqa: E731
    return [up(left), up(top), up(right), right, bottom, left], [top, right, bottom, left]


SIL, FLOORP = _silhouette()


def inside_poly(poly, p, margin):
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln < 1e-3:
            continue
        if -(dx * (p[1] - a[1]) - dy * (p[0] - a[0])) / ln < margin:
            return False
    return True


def art_fits(bx, anchor, flipped):
    w, h, x0, y0, x1, y1 = bx
    if flipped:
        x0, x1 = w - x1, w - x0
    left = anchor[0] - w / 2.0 + x0
    right = left + (x1 - x0)
    bottom = anchor[1] + y0
    top = bottom + (y1 - y0)
    on_floor = inside_poly(FLOORP, (left, bottom), 0) and inside_poly(FLOORP, (right, bottom), 0)
    in_room = all(inside_poly(SIL, c, 4.0) for c in ((left, bottom), (right, bottom), (left, top), (right, top)))
    return on_floor and in_room


def check_fits(arts):
    """靠牆的（貨架、書櫃、鐘）：左後牆（不翻面、左角）每個 gy、右後牆（翻面、右角）每個 gx 放不放得下；
    其餘：房間正中間放得下。"""
    print('\n■ 擺放驗算（RoomLayout.ArtFits 規則）')
    ok = True
    for pid, a in arts.items():
        if a.kind != 'furniture':
            continue
        bx = a.bounds()
        w, d = FOOT[pid]
        if pid.startswith('shelf_') or pid in WALLS:
            lo = [gy for gy in range(0, GRID_H - d + 1) if art_fits(bx, tile_front(0, gy + d - 1), False)]
            ro = [gx for gx in range(0, GRID_W - d + 1) if art_fits(bx, tile_front(gx + d - 1, 0), True)]
            print('  %-16s %3dx%-3d 靠左牆 %d/%d 格、翻面靠右牆 %d/%d 格' % (pid, bx[0], bx[1], len(lo), GRID_H - d + 1,
                                                                           len(ro), GRID_W - d + 1))
            ok &= bool(lo) and bool(ro)
        else:
            good = art_fits(bx, tile_front(6 + w - 1, 4 + d - 1), False)
            if not good:
                print('  ⚠️ %s 放在房間中央會穿牆？' % pid)
            ok &= good
    return ok


# ═══════════════════════════════ 輸出 ═══════════════════════════════

def write_pngs(arts, root=None):
    fd = FURN8 if root is None else os.path.join(root, 'furniture8')
    dd = DECOR8 if root is None else os.path.join(root, 'decor8')
    os.makedirs(fd, exist_ok=True)
    os.makedirs(dd, exist_ok=True)
    for pid, a in arts.items():
        Image.fromarray(a.img).save(os.path.join(fd if a.kind == 'furniture' else dd, pid + '.png'))
    return fd, dd


def restore():
    n = 0
    for d in (FURN8, DECOR8):
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            os.remove(os.path.join(d, fn))
            n += 1
        os.rmdir(d)
        if os.path.exists(d + '.meta'):
            os.remove(d + '.meta')
    write_cs({})
    print('刪掉細畫版 %d 個檔、FurnitureArt8.cs 清空（遊戲會退回 furniture/、decor/ 的舊圖；新款家具沒有舊圖，花店不會列）' % n)

# ═══════════════════════════════ 預覽 ═══════════════════════════════

from PIL import ImageDraw  # noqa: E402

LIGHT_SPEC = {}
for _id, _r, _cr, _cg, _cb, _s, _fl in re.findall(
        r'\["(\w+)"\] = new LightSpec\(([\d.]+)f, new Color32\((\d+), (\d+), (\d+), 255\), ([\d.]+)f, ([\d.]+)f\)', _FURN_CS):
    LIGHT_SPEC[_id] = (float(_r), (int(_cr), int(_cg), int(_cb)), float(_s))
for _id, _r, _cr, _cg, _cb, _s, _fl in re.findall(
        r'Id = "(\w+)"[^}]*?LightSpec\(([\d.]+)f, new UnityEngine\.Color32\((\d+), (\d+), (\d+), 255\), ([\d.]+)f, ([\d.]+)f\)',
        _DECOR_CS, re.S):
    LIGHT_SPEC[_id] = (float(_r), (int(_cr), int(_cg), int(_cb)), float(_s))
SHOP_GLOW_DAY = 0.45          # 同 FurnitureLight：店裡白天也有一點暖光，傍晚到晚上全亮
OLD_SCALE = {'herb_shelf': 0.45, 'crystal_shelf': 0.45, 'potion_shelf': 0.45}


def _glow(radius, rgb, alpha):
    size = max(2, int(radius * 2))
    r = (np.arange(size) - (size - 1) / 2) / (size / 2)
    X, Y = np.meshgrid(r, r)
    d = np.clip(np.hypot(X, Y), 0, 1)
    a = np.clip((1 - d) ** 2, 0, 1) * alpha
    img = np.zeros((size, size, 4), np.uint8)
    img[..., :3] = rgb
    img[..., 3] = (a * 255).round().astype(np.uint8)
    return Image.fromarray(img)


def item_pool():
    d = os.path.join(RES, 'items8')
    return [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith('.png')]


def good_img(path, mw, mh):
    """同 ShopRoomView.MakeGood：整張 96×96 等比縮到塞得進 MaxW×MaxH，底部中心對在位子上。"""
    im = Image.open(path).convert('RGBA')
    k = min(mw / im.width, mh / im.height)
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.NEAREST)


def witch_img():
    b = Image.open(os.path.join(RES, 'witch8', 'base.png')).convert('RGBA')
    cw, ch = b.width // 8, b.height // 25
    return b.crop((0, 0, cw, ch)).resize((round(cw * 1.6), round(ch * 1.6)), Image.NEAREST), round(3 * 1.6)


def villager_img(name, col=0, row=0):
    b = Image.open(os.path.join(RES, 'villagers8', name + '.png')).convert('RGBA')
    cw, ch = b.width // 4, b.height // 3
    return b.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch)).resize((round(cw * 1.6), round(ch * 1.6)), Image.NEAREST), round(3 * 1.6)


def slot_seq(slots, flip):
    rows = {}
    for s_ in slots:
        rows.setdefault(s_[4], []).append(s_)
    out = []
    for r in sorted(rows):
        out += rows[r][::-1] if flip else rows[r]
    return out


def compose_shop(arts, furn, decor=(), listings=(), chars=(), glow=1.0, base=None, show_glow=True):
    """店的合成：furn [(id, gx, gy, flip, anchor)]、decor [(id, x, y, flip)]、listings [(itemIndex, count)]、
    chars [(img, footpad, x, y)]。排序照遊戲：家具 -錨點y、商品 +1、裝飾 -y、地毯最底、人 -腳y。"""
    base = Image.open(os.path.join(RES, 'rooms', 'shop-room.png')).convert('RGBA') if base is None else base.copy()
    W, H = base.size
    layers = []
    pool = item_pool()
    pieces = []
    for (pid, gx, gy, flip, anc) in furn:
        w, h = FOOT[pid]
        if flip:
            w, h = h, w
        a = tile_front(gx, gy + h - 1) if anc == 1 else tile_front(gx + w - 1, gy) if anc == 2 else tile_front(gx + w - 1, gy + h - 1)
        pieces.append((pid, flip, a, gx, gy, w, h))
    order = [p for p in pieces if p[0] == 'sale_table'] + [p for p in pieces if p[0] != 'sale_table']
    q = [(nm, 1 if c <= 1 else 2 if c <= 4 else 3) for nm, c in listings]
    qi = 0
    goods = {}
    for p in order:
        seq = slot_seq(arts[p[0]].slots, p[1])
        k = 0
        while qi < len(q) and k < len(seq):
            nm, n = q[qi]
            take = min(n, len(seq) - k)
            for j in range(take):
                goods.setdefault(id(p), []).append((seq[k + j], nm))
            k += take
            qi += 1
    lights = []
    for p in pieces:
        pid, flip, (ax, ay), *_ = p
        im = Image.fromarray(arts[pid].img)
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        o = round(-ay)
        layers.append((o, 0, im, (round(ax + W / 2 - im.width / 2), round(H / 2 - ay - im.height))))
        for (x, y, mw, mh, row), nm in goods.get(id(p), []):
            it = good_img(pool[nm % len(pool)], mw, mh)
            sx = -x if flip else x
            layers.append((o + 1, 1, it, (round(ax + sx + W / 2 - it.width / 2), round(H / 2 - (ay + y) - it.height))))
        if pid in LIGHT_SPEC:
            for (lx, ly) in arts[pid].lights:
                lights.append((ax + (-lx if flip else lx), ay + ly, LIGHT_SPEC[pid]))
    for (pid, x, y, flip) in decor:
        a = arts[pid]
        im = Image.fromarray(a.img)
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        o = -9000 if pid.startswith('rug_') else round(-y)
        layers.append((o, 0, im, (round(x + W / 2 - im.width / 2), round(H / 2 - y - im.height))))
        if pid in LIGHT_SPEC:
            for (lx, ly) in a.lights:
                lights.append((x + (-lx if flip else lx), y + ly, LIGHT_SPEC[pid]))
    for (im, pad_, x, y) in chars:
        sh = Image.new('RGBA', (34, 10), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([0, 0, 33, 9], fill=(20, 10, 25, 90))
        layers.append((round(-y) - 0.5, 2, sh, (round(x + W / 2 - 17), round(H / 2 - y - 5))))
        layers.append((round(-y), 2, im, (round(x + W / 2 - im.width / 2), round(H / 2 - y - im.height + pad_))))
    for o, _, im, pos in sorted(layers, key=lambda t: (t[0], t[1])):
        base.alpha_composite(im, pos)
    if show_glow:
        for (x, y, (rad, rgb, s_)) in lights:
            g = _glow(rad, rgb, s_ * glow)
            base.alpha_composite(g, (round(x + W / 2 - g.width / 2), round(H / 2 - y - g.height / 2)))
    return base


def save_x(im, path, k=2):
    if k != 1:
        im = im.resize((im.width * k, im.height * k), Image.NEAREST)
    im.save(path)
    return path


def preview(arts, outdir):
    os.makedirs(outdir, exist_ok=True)
    files = []
    bg = (54, 40, 46, 255)
    # (a) 新舊對照（每件：舊圖｜新圖，2×）
    ids = list(arts)
    cw, ch, cols = 210, 210, 6
    rows = (len(ids) + cols - 1) // cols
    sheet = Image.new('RGBA', (cols * cw, rows * ch), bg)
    dr = ImageDraw.Draw(sheet)
    for i, pid in enumerate(ids):
        a = arts[pid]
        x0, by = (i % cols) * cw, (i // cols) * ch + ch - 14
        old = os.path.join(RES, 'furniture' if a.kind == 'furniture' else 'decor', pid + '.png')
        new = Image.fromarray(a.img)
        if os.path.exists(old):
            o = Image.open(old).convert('RGBA')
            if a.kind != 'furniture':
                k = OLD_SCALE.get(pid, 0.4)
                o = o.resize((max(1, round(o.width * k)), max(1, round(o.height * k))), Image.LANCZOS)
            sheet.alpha_composite(o, (x0 + cw // 4 - o.width // 2, by - o.height))
            sheet.alpha_composite(new, (x0 + 3 * cw // 4 - new.width // 2, by - new.height))
        else:
            sheet.alpha_composite(new, (x0 + cw // 2 - new.width // 2, by - new.height))
        dr.text((x0 + 4, by + 1), pid + ('' if os.path.exists(old) else ' (new)'), fill=(230, 220, 220, 255))
    files.append(save_x(sheet, os.path.join(outdir, 'a_old_vs_new.png')))
    # (b) 陳列桌＋真的商品
    tabs = [k for k in TABLES] + ['sale_table']
    pool = item_pool()
    sheet = Image.new('RGBA', (len(tabs) * 150, 170), bg)
    n = 0
    for i, pid in enumerate(tabs):
        a = arts[pid]
        cx, by = i * 150 + 75, 150
        sheet.alpha_composite(Image.fromarray(a.img), (cx - a.img.shape[1] // 2, by - a.img.shape[0]))
        for (x, y, mw, mh, row) in slot_seq(a.slots, False):
            it = good_img(pool[(n * 7) % len(pool)], mw, mh)
            n += 1
            sheet.alpha_composite(it, (round(cx + x - it.width / 2), round(by - y - it.height)))
    files.append(save_x(sheet, os.path.join(outdir, 'b_tables_goods.png'), 3))
    # (c) 燈：暗背景＋光暈；店地板上（白天的淡光／傍晚全亮）
    lamps = list(LAMPS) + ['flower_case']
    dark = Image.new('RGBA', (len(lamps) * 110, 170), (16, 14, 26, 255))
    for i, pid in enumerate(lamps):
        a = arts[pid]
        cx, by = i * 110 + 55, 160
        im = Image.fromarray(a.img)
        f = np.asarray(im).astype(np.float32)
        f[..., :3] *= np.array((0.56, 0.55, 0.76), np.float32)            # 家裡的夜色（BrewRoomLayout.NightTint）
        dark.alpha_composite(Image.fromarray(f.clip(0, 255).astype(np.uint8)), (cx - im.width // 2, by - im.height))
        rad, rgb, s_ = LIGHT_SPEC[pid]
        for (lx, ly) in a.lights:
            g = _glow(rad, rgb, s_)
            dark.alpha_composite(g, (round(cx + lx - g.width / 2), round(by - ly - g.height / 2)))
    files.append(save_x(dark, os.path.join(outdir, 'c_lamps_night.png')))
    furn = [(pid, 2 + 2 * i, 4, False, 0) for i, pid in enumerate(LAMPS)]
    for gl, nm in ((SHOP_GLOW_DAY, 'c_lamps_shop_day.png'), (1.0, 'c_lamps_shop_evening.png')):
        im = compose_shop(arts, furn, decor=[('flower_case', 60, -120, False)], glow=gl)
        files.append(save_x(im.crop((80, 140, 900, 470)), os.path.join(outdir, nm)))
    # (d) 整間店
    W, H = 960, 640
    furn = [('sale_table', 5, 3, False, 0),
            ('shelf_arch', 0, 0, False, 1), ('shelf_scallop', 0, 3, False, 1),
            ('shelf_peak', 2, 0, True, 2), ('shelf_drawer', 5, 0, True, 2), ('bookshelf', 8, 0, True, 2),
            ('table_tier', 4, 6, False, 0), ('table_round', 8, 4, False, 0), ('table_barrel', 2, 7, False, 0),
            ('table_cart', 9, 6, False, 0), ('table_pedestal', 11, 3, False, 0),
            ('lamp_lantern', 12, 1, False, 0), ('lamp_mushroom', 7, 6, False, 0), ('lamp_moon', 2, 5, False, 0),
            ('armchair', 10, 0, False, 0), ('plant_monstera', 11, 0, False, 0)]
    dec = [('rug_round', 190, -150, False), ('blue_urn', 330, 10, False), ('roses_vase', 150, -40, False),
           ('succulent', -40, 0, False), ('potion_shelf', 245, -60, False)]
    wi, wp = witch_img()
    v1, p1 = villager_img('rabbit')
    v2, p2 = villager_img('fox', 0, 0)
    chars = [(wi, wp, 30, -100), (v1, p1, 140, -170), (v2, p2, -130, -10)]
    listings = [(i * 3, (1, 3, 5, 2, 7, 1, 4, 2, 6, 1, 3, 2, 5, 1, 2, 3, 9, 1, 2, 4)[i % 20]) for i in range(24)]
    shop = compose_shop(arts, furn, dec, listings, chars, glow=SHOP_GLOW_DAY)
    files.append(save_x(shop, os.path.join(outdir, 'd_shop_full.png'), 1))
    for nm, box_ in (('d_crop_left.png', (60, 60, 460, 400)), ('d_crop_right.png', (440, 60, 900, 400)),
                     ('d_crop_front.png', (250, 260, 700, 600))):
        files.append(save_x(shop.crop(box_), os.path.join(outdir, nm)))
    # (e) 家裡（brew8 白天／夜晚）
    import gen_brew_room8 as b8m
    for night in (False, True):
        room = b8m.compose(os.path.join(RES, 'rooms', 'brew8'), night, [(-120, -40)]).convert('RGBA')
        CW, CH = room.size
        put_ = [('lamp_lantern', -330, -60), ('armchair', -250, -20), ('side_table', -195, -55), ('lamp_mushroom', 120, -230),
                ('cat_tree', -330, -175), ('rug_star', 60, -250), ('lamp_moon', 210, -200)]
        layers = []
        for (pid, x, y) in put_:
            a = arts[pid]
            im = np.asarray(Image.fromarray(a.img)).astype(np.float32)
            if night:
                im[..., :3] *= np.array((0.56, 0.55, 0.76), np.float32)
            im = Image.fromarray(im.clip(0, 255).astype(np.uint8))
            o = -9000 if pid.startswith('rug') else -y
            layers.append((o, im, (round(x + CW / 2 - im.width / 2), round(CH / 2 - y - im.height)), pid, x, y))
        for o, im, pos, pid, x, y in sorted(layers, key=lambda t: t[0]):
            room.alpha_composite(im, pos)
        if night:
            for o, im, pos, pid, x, y in layers:
                if pid in LIGHT_SPEC:
                    rad, rgb, s_ = LIGHT_SPEC[pid]
                    for (lx, ly) in arts[pid].lights:
                        g = _glow(rad, rgb, s_)
                        room.alpha_composite(g, (round(x + lx + CW / 2 - g.width / 2), round(CH / 2 - (y + ly) - g.height / 2)))
        nm = 'e_home_night.png' if night else 'e_home_day.png'
        files.append(save_x(room.convert('RGB'), os.path.join(outdir, nm), 1))
        files.append(save_x(room.crop((80, 250, 620, 640)).convert('RGB'), os.path.join(outdir, nm.replace('.png', '_crop.png'))))
    return files


# ═══════════════════════════════ main ═══════════════════════════════

def main():
    args = sys.argv[1:]
    if '--restore' in args:
        restore()
        return 0
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    out_root = args[args.index('--out') + 1] if '--out' in args else None
    preview_dir = args[args.index('--preview') + 1] if '--preview' in args else None
    check_catalog()
    arts = build(only)
    fd, dd = write_pngs(arts, out_root)
    print('寫出 %d 張圖 → %s、%s' % (len(arts), fd, dd))
    if out_root is None and not only:
        write_cs(arts)
        print('寫出 ' + CS_OUT)
    nslots = 0
    for pid, a in arts.items():
        nslots += len(a.slots)
        print('  %-18s %3dx%-3d 陳列位 %2d  光暈 %d' % (pid, a.img.shape[1], a.img.shape[0], len(a.slots), len(a.lights)))
    print('  共 %d 個陳列位' % nslots)
    ok = check_fits(arts)
    if preview_dir and not only:
        for f in preview(arts, preview_dir):
            print('預覽：' + f)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
