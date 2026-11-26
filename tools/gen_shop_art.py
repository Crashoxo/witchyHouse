# -*- coding: utf-8 -*-
"""
店裡的家具美術（16 款貨架＋販售桌）—— 用程式組 SVG 畫、轉像素風 PNG，
並產生「商品陳列位」表 Assets/Scripts/Data/ShopDisplaySlots.cs。

    python tools/gen_shop_art.py                    # 重畫 17 張、覆蓋 Assets/Resources/furniture/<id>.png、寫 C# 陳列位表、
                                                    # 重跑 gen_furniture_bounds.py、做「靠牆擺得下」驗算
    python tools/gen_shop_art.py --preview DIR      # 另外輸出總覽圖與「擺進店裡」的合成預覽
    python tools/gen_shop_art.py --check            # 只做驗算（量現有的 PNG，不畫圖、不寫檔）
    python tools/gen_shop_art.py --restore          # 把 tools/shop_art/orig/ 備份的原圖蓋回去（並重跑 bounds）

固定結果、可重跑（沒有用亂數）。渲染管線整個沿用 tools/gen_brew_room.py（**import 它，不是複製**）：
Svg／Iso／box 等等距畫法、色盤 PAL、render_sheet（無頭 Chrome 截圖）、postprocess（alpha 二值化、
貼齊色盤、補 1px 外輪廓）。畫法的約定也跟它一樣（見那支檔頭的「畫法的約定」）。

── 座標 ─────────────────────────────────────────────────────────
  每件家具在自己的區域座標裡畫：u 沿 gx（畫面右下）、v 沿 gy（畫面左下）、z 往上，
  **一格＝32 個 uv 單位**（店裡一格 64×32 世界像素，等距 2:1：Iso 的 1 個 u ＝ 畫面 (+1, +0.5)）。
  1 世界像素＝1 圖像素，跟魔女房間一樣不縮放。
  貨架（沒翻面）佔地 u∈[0,32]、v∈[0,32×深度]：背板貼著 u=0（左後牆）、開口朝 +u（畫面右下）。
  販售桌佔地 u∈[0,64]、v∈[0,32]。

── 錨點約定（C# 不改）─────────────────────────────────────────────
  **圖的正下方中央＝佔地的前角** P(du, dv, 0)（RoomLayout.AnchorPos / ShopRoomView.MakeGrounded）。
  產生器在渲染後**自己算好裁切**：前角那一點在畫布上的位置是整數 (fx, fy)，
  圖的底緣＝fy、左右以 fx 對稱補透明邊。不要事後手調偏移。
  ⚠️ 架子本體只有約半格厚（背板貼牆那側），前角在圖底下其實是一片透明 —— 那是故意的
     （前面半格是視覺上的空隙），錨點照樣是「佔地」的前角，不是架子本體的前角。

── 陳列位（給 ShopRoomView 擺商品）──────────────────────────────────
  每個位子＝商品「底部中心」相對於錨點的世界偏移 (x, y)（y 朝上）＋該位子塞得下的最大寬高。
  位子放在每層層板（或桌面）上、離開口 0.4 層深的地方；寬高算過「不會蓋到靠近玩家那側的側板」與
  「不會頂到上一層層板的前緣」—— 因為商品的 sortingOrder 一律比家具大 1，蓋到就會穿幫。
"""
import math
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np                      # noqa: E402
from PIL import Image                   # noqa: E402

import gen_brew_room as br              # noqa: E402  （它的 main 有 __name__ 保護，import 不會重畫房間）
from gen_brew_room import Svg, Iso, fu, fv, fz, box, hull, tiny_star, star_pts   # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, 'Assets', 'Resources')
FURN_DIR = os.path.join(RES, 'furniture')
WORK = os.path.join(HERE, 'shop_art')
SVG_DIR = os.path.join(WORK, 'svg')
ORIG_DIR = os.path.join(WORK, 'orig')
CS_OUT = os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'ShopDisplaySlots.cs')
SHOP_ROOM_PNG = os.path.join(RES, 'rooms', 'shop-room.png')


# ═══════════════════════════════ 格盤（從 C# 讀，不自己寫常數）═══════════════════════════════

def _src(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def _num(text, pat):
    m = re.search(pat, text)
    if not m:
        raise SystemExit('讀不到常數：' + pat)
    return float(m.group(1))


_SHOP = _src('Assets/Scripts/Data/ShopRoom.cs')
TILE_W = _num(_SHOP, r'TileW\s*=\s*([\d.]+)f')
TILE_H = _num(_SHOP, r'TileH\s*=\s*([\d.]+)f')
GRID_W = int(_num(_SHOP, r'GridW\s*=\s*(\d+)'))
GRID_H = int(_num(_SHOP, r'GridH\s*=\s*(\d+)'))
ORIGIN_X = _num(_SHOP, r'OriginX\s*=\s*(-?[\d.]+)f')
ORIGIN_Y = _num(_SHOP, r'OriginY\s*=\s*(-?[\d.]+)f')
WALL_H = _num(_SHOP, r'WallH\s*=\s*([\d.]+)f')
ROOM_W = _num(_SHOP, r'RoomW\s*=\s*([\d.]+)f')
ROOM_H = _num(_SHOP, r'RoomH\s*=\s*([\d.]+)f')
if TILE_W != 2 * TILE_H:
    raise SystemExit('格子不是 2:1 等距 —— 這支的 Iso 投影要跟著改')
CELL = int(TILE_W / 2)                   # 一格＝幾個 uv 單位（32）

# 家具的佔地（從 Furniture.cs 讀：販售桌 2×1、貨架 1×深度）
_FURN = _src('Assets/Scripts/Data/Furniture.cs')
SHELF_DEPTH = {sid: int(d) for sid, d in
               re.findall(r'\("(shelf_\w+)",\s*"[^"]*",\s*\d+,\s*"[^"]*",\s*(\d+)\)', _FURN)}
SHELF_NAME = dict(re.findall(r'\("(shelf_\w+)",\s*"([^"]*)"', _FURN))
if len(SHELF_DEPTH) != 16:
    raise SystemExit('Furniture.cs 的貨架表讀不到 16 款（讀到 %d）' % len(SHELF_DEPTH))


# ═══════════════════════════════ 色盤（魔女房間的 PAL ＋ 店裡的木色）═══════════════════════════════
# 店裡的家具原圖是偏紅的深棕（取色 #8d4134 / #6b2b26 / #531b22 / #3b121a），比魔女房間的橘棕木（wd）紅、暗；
# 底圖地板也是紅棕，所以亮階拉得比原圖亮一點，擺在地板上才分得出來。
# 厚板木架是灰調舊木（原圖 #856a5c / #6e4b40 / #4a342e）。
# ⚠️ 只「加」顏色，不改 PAL 的任何一格（魔女房間的圖要逐 byte 不變）。

SHOP_EXTRA = {
    # 店木（暖紅棕）：lit＝頂面、hi＝靠玩家的側面／層板頂、本色＝正面、dk＝內部、dk2＝線
    'sw_lit': '#b96a4d', 'sw_hi': '#9a4a39', 'sw': '#7a342d', 'sw_dk': '#5a2228', 'sw_dk2': '#3d131b',
    # 紅木（更深更紅、帶一點紫，拱頂與抽屜架用）
    'sm_lit': '#ab5a55', 'sm_hi': '#88393b', 'sm': '#6a292f', 'sm_dk': '#4c1a26', 'sm_dk2': '#330f1b',
    # 灰調舊木（厚板木架）
    'gw_lit': '#aa9484', 'gw_hi': '#8c7667', 'gw': '#6d584c', 'gw_dk': '#4f3f38', 'gw_dk2': '#33262a',
}
for _k in SHOP_EXTRA:
    if _k in br.PAL:
        raise SystemExit('色名撞到 PAL：' + _k)
SHOP_PAL = dict(br.PAL)
SHOP_PAL.update(SHOP_EXTRA)


def wood(name):
    return {'lit': name + '_lit', 'hi': name + '_hi', 'b': name, 'dk': name + '_dk', 'dk2': name + '_dk2'}


# ═══════════════════════════════ 小工具 ═══════════════════════════════

def wbox(s, P, m, u0, u1, v0, v1, z0, z1, top='lit', left='hi', right='b', line='dk2'):
    """木頭盒子：頂面＝lit、+v 面（左下，受光）＝hi、+u 面（右下，正面）＝本色。"""
    box(s, P, u0, u1, v0, v1, z0, z1, (m['hi'], m['b'], m['dk'], m['dk2']),
        top=m[top], left=m[left], right=m[right], line=m[line])


def board(s, P, m, u0, u1, va, vb, z, T):
    """一片層板：頂面 hi、前緣（+u 面）dk，頂面靠前緣一條亮線（看得出是可以擺東西的平面）。"""
    wbox(s, P, m, u0, u1, va, vb, z, z + T, top='hi', left='b', right='dk')
    s.line(P(u1 - 1.5, va + 1, z + T), P(u1 - 1.5, vb - 1, z + T), m['lit'], 1)


def proj(P, u, pts):
    return [P(u, v, z) for v, z in pts]


def shape_pts(kind, v0, v1, z0, z1, r=0.0, rise=0.0, n=10):
    """正面（u＝常數平面）的外形，(v, z) 點列。"""
    vm = (v0 + v1) / 2.0
    if kind == 'rect':
        return [(v0, z0), (v1, z0), (v1, z1), (v0, z1)]
    if kind == 'round':
        pts = []
        for cv, cz, a0 in ((v1 - r, z0 + r, -90), (v1 - r, z1 - r, 0), (v0 + r, z1 - r, 90), (v0 + r, z0 + r, 180)):
            for i in range(n + 1):
                a = math.radians(a0 + 90.0 * i / n)
                pts.append((cv + r * math.cos(a), cz + r * math.sin(a)))
        return pts
    if kind == 'arch':
        hw = (v1 - v0) / 2.0
        pts = [(v0, z0), (v1, z0)]
        for i in range(2 * n + 1):
            t = math.pi * i / (2 * n)
            pts.append((vm + hw * math.cos(t), z1 + rise * math.sin(t)))
        return pts
    if kind == 'peak':
        return [(v0, z0), (v1, z0), (v1, z1), (vm, z1 + rise), (v0, z1)]
    raise ValueError(kind)


def plane_bar(P, u, a, b, w):
    """u＝常數平面上，從 (va,za) 到 (vb,zb) 的一根粗 w 的木條（交叉撐用）。"""
    (va, za), (vb, zb) = a, b
    dv, dz = vb - va, zb - za
    ln = math.hypot(dv, dz)
    nv, nz = -dz / ln * w / 2, dv / ln * w / 2
    return [P(u, va + nv, za + nz), P(u, vb + nv, zb + nz), P(u, vb - nv, zb - nz), P(u, va - nv, za - nz)]


def knob(s, x, y):
    s.px(x - 1, y - 1, 'go', 2, 2)
    s.px(x - 1, y - 1, 'go_hi')
    s.px(x, y, 'go_dk')


# ═══════════════════════════════ 貨架 ═══════════════════════════════
# 每款只寫「跟別款不一樣的地方」：參數化的架子產生函式 draw_shelf 依這些欄位組出來。
#   side   ：'panel' 實心側板 ／ 'posts' 四根立柱（開放）
#   back   ：'solid' 實心背板 ／ 'none' 無（看得到牆）／ 'slats' 木條 ／ 'cross' 交叉撐 ／ 'rails' 橫檔
#   shape  ：正面外形 'rect' ／ 'round' 圓角 ／ 'arch' 拱頂 ／ 'peak' 尖屋頂（rise＝頂飾多高）
#   top    ：'flat' 出簷頂板 ／ 'flush' 平頂不出簷 ／ 'crown' 兩段線腳 ／ 'none'
#   extra  ：'crest' 曲線頂飾 ／ 'scallop' 扇貝簷 ／ 'crate' 木箱板紋 ／ 'inset' 側板嵌框
#   seams  ：'v' 背板畫直拼的板縫（其餘實心背板是素的深色，層板才跳得出來）
#   lower  ：下段 'drawer1' 一個大抽屜 ／ 'drawers6' 六個小抽屜 ／ 'doors' 對開小櫃 ／ 'deep' 加深的最下層
#   levels ：每片層板的底 z（第一片＝最下層的地板）；Hs＝本體高（頂板的底）
#   D      ：架子本體的厚度（u），約 0.45～0.6 格；pt＝側板／立柱的厚度；T＝層板厚
#   plinth ：踢腳高度；feet ：'bun' 圓腳

SHELVES = {
    'shelf_narrow':  dict(side='posts', back='none', D=13, pt=3, T=3, levels=[8, 43, 78], Hs=112, top='flat',
                          rails=True),
    'shelf_tall':    dict(side='panel', back='solid', D=16, pt=4, levels=[5, 35, 65, 95], Hs=127, top='crown',
                          plinth=4),
    'shelf_cross':   dict(side='posts', back='cross', D=16, pt=4, levels=[6, 42, 78], Hs=114, top='flat'),
    'shelf_plank':   dict(side='posts', back='none', D=18, pt=6, T=6, levels=[6, 40, 74], Hs=114, top='plank',
                          wood='gw', overhang=5),
    'shelf_box':     dict(side='panel', back='solid', D=17, pt=7, levels=[7, 42, 77], Hs=114, top='flush',
                          extra='crate'),
    'shelf_slat':    dict(side='posts', back='slats', D=16, pt=4, levels=[6, 42, 78], Hs=114, top='flat'),
    'shelf_back':    dict(side='panel', back='solid', D=17, pt=4, levels=[8, 43, 78], Hs=112, top='crown',
                          plinth=6, extra='inset', seams='v'),
    'shelf_round':   dict(side='panel', back='solid', D=17, pt=6, levels=[8, 42, 76], Hs=116, top='none',
                          shape='round', r=16),
    'shelf_deep':    dict(side='panel', back='solid', D=15, pt=4, levels=[42, 78], Hs=112, top='flat',
                          lower='deep', lowD=27, lowH=42),
    'shelf_curve':   dict(side='posts', back='rails', D=15, pt=4, levels=[6, 41, 76], Hs=110, top='flat',
                          extra='crest', finials=True),
    'shelf_two':     dict(side='panel', back='solid', D=17, pt=4, levels=[34, 72], Hs=110, top='flat',
                          lower='drawer1', plinth=4),
    'shelf_scallop': dict(side='panel', back='solid', D=17, pt=4, levels=[6, 38, 70], Hs=112, top='flat',
                          extra='scallop'),
    'shelf_peak':    dict(side='panel', back='solid', D=17, pt=4, levels=[6, 37, 68], Hs=102, top='none',
                          shape='peak', rise=30, top_row=dict(vmax=60, hmax=20)),
    'shelf_arch':    dict(side='panel', back='solid', D=17, pt=6, levels=[6, 38, 70], Hs=98, top='none',
                          shape='arch', rise=30, wood='sm'),
    'shelf_cabinet': dict(side='panel', back='solid', D=17, pt=4, levels=[40, 76], Hs=110, top='crown',
                          lower='doors', plinth=4),
    'shelf_drawer':  dict(side='panel', back='solid', D=18, pt=5, levels=[42, 78], Hs=112, top='crown',
                          lower='drawers6', feet='bun', wood='sm'),
}

SLOT_W = 22.0          # 商品最寬（世界像素）；目標顯示高 22～26
SLOT_H_MAX = 26.0      # 商品最高（層間再高也不要畫得比這大，免得比女巫的頭還大）
SLOT_FRONT = 0.6       # 商品底部中心離背板多遠（佔層深的比例）——放前面一點，開口看得清楚
V0_PAD = 3             # 架子兩端離佔地邊緣留的空（uv）


def shelf_dims(sid):
    depth = SHELF_DEPTH[sid]
    DV = CELL * depth
    return CELL, DV, V0_PAD, DV - V0_PAD


def floor_shadow(s, P, u1, v0, v1):
    s.poly(fz(P, 0, 0, u1, v0, v1), 'SHADOW')


def interior(s, P, m, st, D, v0, v1, pt, levels, T, oz0, oz1, back, ztop_extra=0.0):
    """實心架子開口裡看得到的東西（呼叫端已經 clip 到開口）：背板、遠側板內面、層板。"""
    bu = 2.0
    zA, zB = oz0 - 2, oz1 + ztop_extra + 4
    s.poly(fu(P, bu, v0, v1, zA, zB), m['dk2'])
    if st.get('seams') == 'v':                                  # 封背貨架：直拼的背板
        v = v0 + pt + 10
        while v < v1 - pt - 3:
            s.line(P(bu, v, zA), P(bu, v, zB), m['dk'], 1)       # 背板的拼板縫（比底色亮一階：像受光的板緣）
            v += 11
    # 遠側板的內面（朝左下，受一點光）＋每片層板投在它上面的影子
    s.poly(fv(P, v0 + pt, bu, D, zA, zB), m['dk'], m['dk2'])
    ceil = list(levels[1:]) + [oz1]
    for zc in ceil:
        s.poly([P(bu, v0 + pt, zc), P(D, v0 + pt, zc), P(D, v0 + pt, zc - 3), P(bu, v0 + pt, zc - 8)], m['dk2'])
    for z in levels:
        board(s, P, m, bu, D, v0 + pt, v1 - pt, z, T)


def solid_body(s, P, m, st, D, v0, v1, z0, z1, levels, T=4, pt=4, shape='rect', r=0.0, rise=0.0,
               back='solid', top_t=4):
    """
    實心（有側板）的架身：先畫整塊實心的剪影（頂面）、靠玩家那面側板、正面，再把開口 clip 出來畫內部。
    回傳每一層的 (地板 z, 天花板 z, 該層深度)。
    ⚠️ 外形必須是凸的（矩形／圓角／拱／尖頂都是）：剪影＝前後兩個外形投影的凸包。
    """
    outer = shape_pts(shape, v0, v1, z0, z1, r, rise)
    s.poly(hull(proj(P, 0, outer) + proj(P, D, outer)), m['lit'], m['dk2'])
    zs0, zs1 = (z0 + r, z1 - r) if shape == 'round' else (z0, z1)
    s.poly(fv(P, v1, 0, D, zs0, zs1), m['hi'], m['dk2'])
    s.poly(proj(P, D, outer), m['b'], m['dk2'])

    oz0 = levels[0]
    if shape == 'arch':
        oz1 = z1
        inner = shape_pts('arch', v0 + pt, v1 - pt, oz0, oz1, rise=rise - top_t - 2)
        extra = rise
    elif shape == 'round':
        oz1 = z1 - pt
        inner = shape_pts('round', v0 + pt, v1 - pt, oz0, oz1, r=max(3.0, r - pt))
        extra = 0
    else:
        oz1 = z1 - top_t
        inner = shape_pts('rect', v0 + pt, v1 - pt, oz0, oz1)
        extra = 0
    op = proj(P, D, inner)
    s.clip(pts=op)
    interior(s, P, m, st, D, v0, v1, pt, levels, T, oz0, oz1, back, extra)
    s.end()
    s.poly(op, None, m['dk2'])
    comps = []
    for i, z in enumerate(levels):
        # 拱頂：最上層往上伸進拱裡。陳列位最遠只到拱寬的 ±76%，那裡拱還有 0.65 的高 → 取 0.6 保守
        zc = levels[i + 1] if i + 1 < len(levels) else oz1 + (0.6 * (rise - top_t - 2) if shape == 'arch' else 0)
        comps.append((z + T, zc, D))
    return comps


def posts_body(s, P, m, st, D, v0, v1, levels, Hs, T=4, pt=4, back='none'):
    """開放式（四根立柱）的架身。回傳每一層的 (地板 z, 天花板 z, 深度)。"""
    over = st.get('overhang', 0)
    tz = Hs - T                 # 頂板的底
    # 背面：牆上的影子／交叉撐／木條／橫檔
    if back in ('none', 'rails'):
        for z in levels[1:] + [tz]:
            s.poly(fu(P, 0, v0 + pt, v1 - pt, z - 7, z), 'SHADOW')        # 層板投在牆上的影子
    if back == 'slats':
        s.poly(fu(P, 0, v0 + pt, v1 - pt, levels[0], tz), 'SHADOW')
        v = v0 + pt + 1.5
        while v + 5 <= v1 - pt:
            s.poly(fu(P, 1, v, v + 5, levels[0], tz), m['b'], m['dk2'])
            s.line(P(1, v + 4, levels[0] + 1), P(1, v + 4, tz - 1), m['hi'], 1)
            v += 9
    if back == 'cross':
        z_lo, z_hi = levels[0] + T, tz
        vm = (v0 + v1) / 2.0
        for va, vb in ((v0 + pt, vm), (vm, v1 - pt)):
            s.poly(plane_bar(P, 1, (va + 2, z_lo + 2), (vb - 2, z_hi - 2), 5), m['dk'], m['dk2'])
            s.poly(plane_bar(P, 1.5, (va + 2, z_hi - 2), (vb - 2, z_lo + 2), 5), m['b'], m['dk2'])
            x, y = P(1.5, (va + vb) / 2.0, (z_lo + z_hi) / 2.0)
            s.px(x - 1, y - 1, m['dk2'], 2, 2)                                   # 交叉處的木釘
        for zr in (levels[0] + T, tz - 5):
            s.poly(fu(P, 2, v0 + pt, v1 - pt, zr, zr + 5), m['b'], m['dk2'])     # 上下兩條橫檔
    if back == 'rails':
        for i, z in enumerate(levels):
            zc = levels[i + 1] if i + 1 < len(levels) else tz
            zr = z + T + (zc - z - T) * 0.55
            wbox(s, P, m, 0, 2, v0 + pt, v1 - pt, zr, zr + 3, top='hi', left='b', right='b')

    def post(u, v):
        wbox(s, P, m, u, u + pt, v, v + pt, 0, Hs, top='lit', left='hi', right='b')

    post(0, v0)
    post(D - pt, v0)
    if not over:
        for z in levels:
            board(s, P, m, 0, D, v0 + pt, v1 - pt, z, T)
    if st.get('rails'):                     # 細架：兩側各兩根細橫檔，看起來比較穩
        for z in (levels[0] + 14, levels[-1] + 18):
            wbox(s, P, m, pt, D - pt, v1 - pt + 1, v1 - 1, z, z + 2, top='hi', left='hi', right='b')
    post(0, v1 - pt)
    post(D - pt, v1 - pt)
    if over:                                # 厚板：板子穿過立柱、兩頭露出來
        for z in levels + [tz]:
            board(s, P, m, -1, D + 1, v0 - over, v1 + over, z, T)
            for v in (v0 + pt / 2, v1 - pt / 2):
                x, y = P(D + 1, v, z + T / 2)
                s.px(x - 1, y - 1, 'ir_dk2', 2, 2)                              # 鐵釘
                s.px(x - 1, y - 1, 'ir_hi')
    comps = []
    for i, z in enumerate(levels):
        zc = levels[i + 1] if i + 1 < len(levels) else tz
        comps.append((z + T, zc, D))
    return comps


def top_grain(s, P, m, u0, u1, v0, v1, z):
    """頂面上兩三條短木紋（大片的亮面才不會一整塊平平的）。位置固定、不用亂數。"""
    L = v1 - v0
    for fu_, fa, fb in ((0.35, 0.12, 0.38), (0.62, 0.48, 0.8), (0.3, 0.7, 0.9)):
        u = u0 + (u1 - u0) * fu_
        s.line(P(u, v0 + L * fa, z), P(u, v0 + L * fb, z), m['hi'], 1)


def top_board(s, P, m, st, D, v0, v1, Hs, T=4):
    t = st.get('top', 'flat')
    if t in ('flat', 'crown', 'flush'):
        zt = Hs + (T if t == 'flat' else 7 if t == 'crown' else 0)
        top_grain_args = (-1, D + 2, v0, v1, zt)
    else:
        top_grain_args = None
    if t == 'flat':
        wbox(s, P, m, -1, D + 2, v0 - 2, v1 + 2, Hs, Hs + T)
        s.line(P(D + 2, v0 - 1, Hs + 1), P(D + 2, v1 + 1, Hs + 1), m['dk'], 1)
    elif t == 'crown':
        wbox(s, P, m, -1, D + 1, v0 - 1, v1 + 1, Hs, Hs + 3, right='dk')
        wbox(s, P, m, -2, D + 3, v0 - 3, v1 + 3, Hs + 3, Hs + 7)
        s.line(P(D + 3, v0 - 2, Hs + 5), P(D + 3, v1 + 2, Hs + 5), m['hi'], 1)
    elif t == 'plank':
        pass                                # 厚板木架的頂板就是最上面那片穿柱的板（posts_body 畫）
    if top_grain_args:
        top_grain(s, P, m, *top_grain_args)


def lower_front(s, P, m, st, D, v0, v1, pt, z0, z1):
    """下段（第一片層板以下）的正面：抽屜／小櫃門。畫在正面（u=D）上，稍微凸出 1。"""
    kind = st.get('lower')
    va, vb = v0 + pt, v1 - pt
    if kind == 'drawer1':
        wbox(s, P, m, D, D + 1.2, va + 1, vb - 1, z0 + 2, z1 - 2, top='lit', left='hi', right='hi')
        s.poly(fu(P, D + 1.2, va + 5, vb - 5, z0 + 6, z1 - 6), None, m['b'], 1)
        x, y = P(D + 1.2, (va + vb) / 2, (z0 + z1) / 2)
        s.rect(x - 4, y - 1, 8, 2, 'go_dk')                     # 長條把手
        s.rect(x - 4, y - 2, 8, 1, 'go')
        s.px(x - 3, y - 2, 'go_hi')
    elif kind == 'drawers6':
        n_c, n_r = 3, 2
        w = (vb - va) / n_c
        h = (z1 - z0) / n_r
        for r in range(n_r):
            for c in range(n_c):
                a, b = va + c * w + 0.8, va + (c + 1) * w - 0.8
                za, zb = z0 + r * h + 1.2, z0 + (r + 1) * h - 0.8
                wbox(s, P, m, D, D + 1.2, a, b, za, zb, top='lit', left='hi', right='hi')
                x, y = P(D + 1.2, (a + b) / 2, (za + zb) / 2)
                knob(s, x, y)
    elif kind == 'doors':
        vm = (va + vb) / 2
        for a, b in ((va + 1, vm - 0.5), (vm + 0.5, vb - 1)):
            wbox(s, P, m, D, D + 1.2, a, b, z0 + 2, z1 - 1, top='lit', left='hi', right='hi')
            s.poly(fu(P, D + 1.2, a + 4, b - 4, z0 + 6, z1 - 5), m['b'], m['dk2'], 1)      # 凹嵌板
            s.line(P(D + 1.2, a + 4, z1 - 6), P(D + 1.2, b - 4, z1 - 6), m['dk'], 1)
        for v in (vm - 3, vm + 3):
            x, y = P(D + 1.2, v, (z0 + z1) / 2 + 2)
            knob(s, x, y)


def draw_crest(s, P, m, v0, v1, zb):
    """曲線頂長架：頂板後緣立一片波浪曲線的頂飾（中間高、兩端捲下來）。"""
    L = v1 - v0
    vm = (v0 + v1) / 2

    def h(v):
        t = (v - v0) / L                                   # 0..1
        bell = math.cos(math.pi * (t - 0.5)) ** 2          # 中間 1、兩端 0
        wave = math.sin(math.pi * t * 3) ** 2              # 三個小波
        return 3 + 15 * bell ** 1.5 + 5 * wave * (1 - bell * 0.7)

    n = 48
    top = [(v0 + L * i / n, zb + h(v0 + L * i / n)) for i in range(n + 1)]
    back = [P(0, v, z) for v, z in top]
    front = [P(3, v, z) for v, z in top]
    s.poly([P(0, v1, zb)] + back[::-1] + [P(0, v0, zb)], m['lit'], m['dk2'])
    s.poly([P(3, v1, zb)] + front[::-1] + [P(3, v0, zb)], m['b'], m['dk2'])
    s.pline([P(3, v, z - 3) for v, z in top[3:-3]], m['hi'], 1)
    x, y = P(3, vm, zb + h(vm) - 7)                         # 中間一顆金色小太陽
    s.ell(x, y, 3, 3, 'go', 'go_dk', 1)
    s.px(x - 1, y - 1, 'go_hi')


def draw_scallop(s, P, m, D, v0, v1, zt):
    """波浪簷：頂板底下沿正面掛一排扇貝花邊（粉紅／米白相間，像店面的遮雨棚）。"""
    u = D + 1.5
    n = 9
    w = (v1 - v0) / n
    hang = 6
    for i in range(n):
        a, b = v0 + i * w, v0 + (i + 1) * w
        pts = [P(u, a, zt), P(u, b, zt)]
        for k in range(9):
            t = math.pi * k / 8
            pts.append(P(u, b - (b - a) * k / 8, zt - hang - 3 * math.sin(t)))
        col = 'pink' if i % 2 == 0 else 'li_hi'
        s.poly(pts, col, 'pink_dk', 1)
    s.poly(fu(P, u, v0, v1, zt - 2, zt), 'go', 'go_dk', 1)


def draw_roof(s, P, m, D, v0, v1, z1, rise):
    """尖頂小屋架：紫色魚鱗瓦的屋頂＋山牆上一扇亮著的小圓窗。"""
    vm = (v0 + v1) / 2
    ztop = z1 + rise + 2
    ua, ub = -2, D + 3
    # 山牆小圓窗（畫在正面 u=D 上）
    zc = z1 + rise * 0.36
    ring = [P(D, vm + 6 * math.cos(2 * math.pi * k / 24), zc + 6 * math.sin(2 * math.pi * k / 24)) for k in range(24)]
    s.poly(ring, 'amber', m['dk2'], 1)
    s.line(P(D, vm - 6, zc), P(D, vm + 6, zc), m['dk2'], 1)
    s.line(P(D, vm, zc - 6), P(D, vm, zc + 6), m['dk2'], 1)
    s.px(*P(D, vm + 3, zc + 3), 'fire_y', 2, 1)
    # 遠側的屋面（朝右後，背光）
    ve0 = v0 - 4
    s.poly([P(ua, ve0, z1 - 3), P(ub, ve0, z1 - 3), P(ub, vm, ztop), P(ua, vm, ztop)], 'pu_dk', 'pu_dk2', 1)
    s.poly([P(ub, ve0, z1 - 3), P(ub, vm, ztop), P(ub, vm, ztop - 3), P(ub, ve0, z1 - 6)], 'pu_dk2', 'pu_dk2', 1)
    # 近側的屋面（朝左下，受光）＋瓦片線
    ve1 = v1 + 4
    s.poly([P(ua, vm, ztop), P(ub, vm, ztop), P(ub, ve1, z1 - 3), P(ua, ve1, z1 - 3)], 'pu', 'pu_dk2', 1)
    for f in (0.25, 0.5, 0.75):
        v = vm + (ve1 - vm) * f
        z = ztop + (z1 - 3 - ztop) * f
        s.line(P(ua + 1, v, z), P(ub - 1, v, z), 'pu_dk', 1)
        for uu in range(int(ua) + 4, int(ub) - 1, 5):
            v2 = v - (ve1 - vm) * 0.125
            z2 = z - (z1 - 3 - ztop) * 0.125
            s.line(P(uu, v, z), P(uu, v2, z2), 'pu_dk', 1)
    s.poly([P(ub, vm, ztop), P(ub, ve1, z1 - 3), P(ub, ve1, z1 - 6), P(ub, vm, ztop - 3)], 'pu_dk2', 'pu_dk2', 1)
    s.line(P(ua, vm, ztop), P(ub, vm, ztop), 'pu_hi', 1)                          # 屋脊
    x, y = P(ub, vm, ztop)
    s.poly(star_pts(x, y - 4, 4, 1.8), 'go', 'go_dk', 1)                         # 屋脊上一顆小星星


def draw_arch_trim(s, P, m, D, v0, v1, z1, rise, pt):
    vm = (v0 + v1) / 2
    hw = (v1 - v0) / 2 - pt / 2
    arc = [P(D, vm + hw * math.cos(math.pi * i / 24), z1 + (rise - pt / 2) * math.sin(math.pi * i / 24))
           for i in range(25)]
    s.pline(arc, m['hi'], 1)                                                      # 拱上的一圈線腳
    x, y = P(D, vm, z1 + rise - 3)
    s.poly(star_pts(x, y, 5, 2.2), 'go', 'go_dk', 1)                             # 拱心石的金星
    s.px(x - 1, y - 2, 'go_hi')
    for v in (v0 + pt / 2, v1 - pt / 2):                                         # 拱腳兩顆小圓飾
        x, y = P(D, v, z1)
        s.ell(x, y, 2.5, 2.5, m['hi'], m['dk2'], 1)


def side_detail(s, P, m, st, D, v1, z0, z1):
    """靠玩家那面側板（+v 面）的細節。"""
    ex = st.get('extra')
    if ex == 'crate':                       # 木箱式：橫向拼板＋前後兩條直的壓條＋鐵釘
        z = z0 + 14
        while z < z1 - 6:
            s.line(P(1, v1, z), P(D - 1, v1, z), m['dk'], 1)
            z += 14
        for ua, ub in ((0, 3), (D - 3, D)):
            s.poly(fv(P, v1 + 0.6, ua, ub, z0, z1), m['lit'], m['dk2'], 1)
            z = z0 + 7
            while z < z1 - 3:
                s.px(*P((ua + ub) / 2, v1 + 0.6, z), m['dk2'])
                z += 14
    elif ex == 'inset':                     # 封背貨架：側板上一圈嵌框（像衣櫃那樣的面板）
        s.poly(fv(P, v1, 4, D - 4, z0 + 8, z1 - 8), None, m['b'], 1)
        s.line(P(5, v1, z1 - 9), P(D - 5, v1, z1 - 9), m['lit'], 1)
    else:                                   # 其他：兩條直木紋（圓角架從圓角以上才畫，免得畫到圓角外面）
        if st.get('shape') == 'round':
            z0, z1 = z0 + st['r'], z1 - st['r'] + 14
        for k, frac in enumerate((0.33, 0.7)):
            u = D * frac
            s.line(P(u, v1, z0 + 6 + k * 9), P(u, v1, z0 + 20 + k * 9), m['b'], 1)
            s.line(P(u + 1, v1, z1 - 30 - k * 12), P(u + 1, v1, z1 - 14 - k * 12), m['b'], 1)


def draw_shelf(s, P, sid):
    """依 SHELVES[sid] 組出一座貨架。回傳每一層的 (地板 z, 天花板 z, 深度)，給陳列位用。"""
    st = SHELVES[sid]
    m = wood(st.get('wood', 'sw'))
    DU, DV, v0, v1 = shelf_dims(sid)
    D, pt, T, Hs = st['D'], st['pt'], st.get('T', 4), st['Hs']
    levels = list(st['levels'])
    shape = st.get('shape', 'rect')
    comps = []

    floor_shadow(s, P, (st.get('lowD') or D) + 5, v0 - 1, v1 + 2)
    if st['side'] == 'posts':
        comps = posts_body(s, P, m, st, D, v0, v1, levels, Hs, T, pt, st['back'])
        top_board(s, P, m, st, D, v0, v1, Hs - T, T)
        if st.get('extra') == 'crest':
            draw_crest(s, P, m, v0 + 2, v1 - 2, Hs)
        # 立柱冒出頂板的部分（厚板木架的柱頭、曲線頂長架的圓球頂飾）—— 畫在頂板之後才不會被它蓋掉
        cap = 6 if st.get('top') == 'plank' else 4 if st.get('finials') else 0
        if cap:
            for v in (v0, v1 - pt):
                for u in (0, D - pt):
                    wbox(s, P, m, u, u + pt, v, v + pt, Hs, Hs + cap, top='lit', left='hi', right='b')
                    if st.get('finials'):
                        x, y = P(u + pt / 2, v + pt / 2, Hs + cap)
                        s.ell(x, y - 2.5, 3.2, 3.2, m['hi'], m['dk2'], 1)
                        s.px(x - 1, y - 4, m['lit'])
        return comps

    z0 = st.get('plinth', 0)
    if st.get('feet') == 'bun':
        z0 = 5
        for u, v in ((3, v0 + 3), (D - 3, v0 + 3), (3, v1 - 3), (D - 3, v1 - 3)):
            x, y = P(u, v, 0)
            s.ell(x, y - 2.5, 4, 3, m['b'], m['dk2'], 1)
            s.px(x - 2, y - 4, m['hi'], 2, 1)
    elif z0:
        wbox(s, P, m, 1, D - 1, v0 + 1, v1 - 1, 0, z0, top='dk', left='b', right='dk')

    if st.get('lower') == 'deep':
        # 深底：最下層是一個比上面深一截的箱子（前緣快到佔地的前緣），上段的架身坐在它後半
        lowD, lowH = st['lowD'], st['lowH']
        comps += solid_body(s, P, m, st, lowD, v0, v1, 0, lowH, [4], T, pt, 'rect', top_t=4)
        side_detail(s, P, m, st, lowD, v1, 0, lowH)
        s.line(P(lowD - 1.5, v0 + 1, lowH), P(lowD - 1.5, v1 - 1, lowH), m['hi'], 1)
        comps += solid_body(s, P, m, st, D, v0, v1, lowH, Hs, levels, T, pt, 'rect')
        side_detail(s, P, m, st, D, v1, lowH, Hs)
    else:
        comps += solid_body(s, P, m, st, D, v0, v1, z0, Hs, levels, T, pt, shape,
                            st.get('r', 0), st.get('rise', 0))
        side_detail(s, P, m, st, D, v1, z0, Hs)
        if st.get('lower'):
            lower_front(s, P, m, st, D, v0, v1, pt, z0, levels[0])
    if st.get('extra') == 'scallop':
        draw_scallop(s, P, m, D, v0, v1, Hs)
        # 最上層的天花板＝花邊的下緣（商品不能頂到花邊）：花邊最低 Hs-9，又比開口再往前 1.5 → 取 Hs-12
        f, c, d = comps[-1]
        comps[-1] = (f, Hs - 12, d)
    top_board(s, P, m, st, D, v0, v1, Hs, T)
    if shape == 'peak':
        draw_roof(s, P, m, D, v0, v1, Hs, st['rise'])
    if shape == 'arch':
        draw_arch_trim(s, P, m, D, v0, v1, Hs, st['rise'], pt)
    return comps


def shelf_slots(sid, comps):
    """每一層的陳列位（區域 uvz ＋ 最大寬高），由上而下、由左而右（左＝v 大）。"""
    DU, DV, v0, v1 = shelf_dims(sid)
    pt = SHELVES[sid]['pt']
    per_row = 3 if SHELF_DEPTH[sid] >= 3 else 2
    out = []
    tr = SHELVES[sid].get('top_row') or {}
    for row, (zf, zc, Dc) in enumerate(reversed(comps)):
        uc = round(Dc * SLOT_FRONT)
        # 最左（靠玩家那端）的商品左緣不能越過近側板的前緣 → 不然商品會畫在側板「前面」
        v_hi = (v1 - pt) - (Dc - uc) - SLOT_W / 2 - 1
        if row == 0 and 'vmax' in tr:
            v_hi = min(v_hi, tr['vmax'])        # 尖屋頂：最上層靠玩家那端被屋簷壓低，位子往裡收
        v_lo = v0 + pt + 9
        sp = (v_hi - v_lo) / (per_row - 1)
        mw = min(SLOT_W, sp - 1)
        # 頂端不能越過上一層層板的前緣（前緣比商品站的位置低 (Dc-uc)/2 個畫面像素）
        mh = min(SLOT_H_MAX, zc - zf - (Dc - uc) / 2.0 - 1)
        if row == 0 and 'hmax' in tr:
            mh = min(mh, tr['hmax'])
        for i in range(per_row):
            out.append((uc, v_hi - i * sp, zf, mw, mh, row))
    return out


# ═══════════════════════════════ 販售桌 ═══════════════════════════════

TABLE_H = 30


def draw_sale_table(s, P):
    m = wood('sw')
    du, dv, H = 2 * CELL, CELL, TABLE_H
    s.poly(br.uv_ellipse(P, du / 2, dv / 2, du / 2 - 1, dv / 2 - 1), 'SHADOW')
    legs = [(3, 3), (du - 8, 3), (3, dv - 8), (du - 8, dv - 8)]
    for u, v in sorted(legs, key=lambda q: q[0] + q[1]):
        if (u, v) == legs[3]:
            # 前腳之前先畫下層的橫檔（橫檔在兩隻前腳之間、被前腳蓋住兩端）
            wbox(s, P, m, 6, du - 6, 6, dv - 6, 7, 10, top='hi', left='b', right='dk')
        wbox(s, P, m, u, u + 5, v, v + 5, 0, H - 4, top='hi', left='hi', right='b')
    # 牙板＋桌面
    wbox(s, P, m, 2, du - 2, 2, dv - 2, H - 9, H - 4, top='dk', left='b', right='dk')
    wbox(s, P, m, 0.5, du - 0.5, 0.5, dv - 0.5, H - 4, H, top='lit', left='hi', right='b')
    for v in (11, 21):
        s.line(P(2, v, H), P(du - 2, v, H), m['hi'], 1)                    # 桌面拼板縫
    s.line(P(du - 2, 2, H), P(du - 2, dv - 2, H), m['lit'], 1)             # 前緣受光
    # 桌巾（紫底金邊的長條，沿長邊鋪、在 +u 那頭垂下來收成尖角、掛一顆金流蘇）
    va, vb = 10, 22
    s.poly(fz(P, H + 0.6, 2, du - 0.5, va, vb), 'pu', 'pu_dk2', 1)
    s.line(P(3, va + 1.5, H + 0.6), P(du - 1, va + 1.5, H + 0.6), 'go', 1)
    s.line(P(3, vb - 1.5, H + 0.6), P(du - 1, vb - 1.5, H + 0.6), 'go', 1)
    tip = [P(du - 0.5, va, H + 0.6), P(du - 0.5, vb, H + 0.6), P(du - 0.5, vb, H - 8),
           P(du - 0.5, (va + vb) / 2, H - 13), P(du - 0.5, va, H - 8)]
    s.poly(tip, 'pu_dk', 'pu_dk2', 1)
    s.pline([P(du - 0.5, va + 1.5, H - 1), P(du - 0.5, va + 1.5, H - 8), P(du - 0.5, (va + vb) / 2, H - 11.5),
             P(du - 0.5, vb - 1.5, H - 8), P(du - 0.5, vb - 1.5, H - 1)], 'go', 1)
    x, y = P(du - 0.5, (va + vb) / 2, H - 13)
    s.rect(x - 1, y, 3, 2, 'go')
    s.rect(x - 1.5, y + 2, 4, 4, 'go_dk')
    s.px(x - 1, y + 2, 'go_hi')
    # 桌巾中段的一顆小月亮刺繡
    x, y = P(du / 2, (va + vb) / 2, H + 0.6)
    s.ell(x, y, 3, 2.2, 'go')
    s.ell(x + 1.3, y - 0.6, 2.4, 1.8, 'pu')


def table_slots():
    """販售桌：三個位子沿長邊排在桌巾上（左→右＝u 小→大）。"""
    out = []
    for i, u in enumerate((9, 32, 55)):
        out.append((u, 16, TABLE_H + 1, SLOT_W, SLOT_H_MAX, 0))
    return out


# ═══════════════════════════════ 組裝 ═══════════════════════════════

MARGIN = 30
ZMAX = 170


def piece_list():
    out = [('sale_table', 2 * CELL, CELL)]
    for sid in SHELVES:
        out.append((sid, CELL, CELL * SHELF_DEPTH[sid]))
    return out


def build():
    """畫全部、轉 PNG。回傳 {id: (RGBA, svg, 陳列位（世界偏移）)}。"""
    jobs = []
    for pid, du, dv in piece_list():
        ox = dv + MARGIN
        oy = ZMAX + MARGIN
        s = Svg(du + dv + 2 * MARGIN, ZMAX + (du + dv) / 2 + 2 * MARGIN, SHOP_PAL, tag=pid.replace('_', ''))
        P = Iso(ox, oy)
        if pid == 'sale_table':
            draw_sale_table(s, P)
            slots_uvz = table_slots()
        else:
            comps = draw_shelf(s, P, pid)
            slots_uvz = shelf_slots(pid, comps)
        fx, fy = P(du, dv, 0)                       # 佔地前角在畫布上的位置（整數）
        assert fx == int(fx) and fy == int(fy), (pid, fx, fy)
        slots = []
        for (u, v, z, mw, mh, row) in slots_uvz:
            x, y = P(u, v, z)
            slots.append((round(x - fx, 1), round(fy - y, 1), round(mw, 1), round(mh, 1), row))
        jobs.append((pid, s, (int(fx), int(fy)), slots))
    imgs = br.render_sheet([j[1] for j in jobs])
    out = {}
    for (pid, s, (fx, fy), slots), a in zip(jobs, imgs):
        p = br.postprocess(a, SHOP_PAL)
        x0, y0, x1, y1 = br.crop_box(p)
        if y1 > fy:
            raise SystemExit('%s：圖畫到佔地前角底下了（%d > %d）—— 錨點會對不上' % (pid, y1, fy))
        half = max(fx - x0, x1 - fx)
        img = np.zeros((fy - y0, 2 * half, 4), np.uint8)
        sx0 = fx - half
        a0, a1 = max(0, sx0), min(p.shape[1], fx + half)
        img[:, a0 - sx0:a1 - sx0] = p[y0:fy, a0:a1]
        out[pid] = (img, s, slots)
    return out


# ═══════════════════════════════ C# 陳列位表 ═══════════════════════════════

def write_cs(arts):
    rows = []
    for pid, (img, s, slots) in arts.items():
        h, w = img.shape[:2]
        body = ',\n'.join('                new DisplaySlot(%sf, %sf, %sf, %sf, %d)' % (
            _f(x), _f(y), _f(mw), _f(mh), row) for (x, y, mw, mh, row) in slots)
        rows.append('            { "%s", (%d, %d, new[]\n            {\n%s,\n            }) },' % (pid, w, h, body))
    cs = '''// <auto-generated>
// ⚠️ 自動產生，不要手改。產生器：tools/gen_shop_art.py
//    重跑：python tools/gen_shop_art.py（加 --preview <資料夾> 輸出合成預覽）
//    要改陳列位的位置／大小：改產生器裡的 SHELVES／SLOT_* 常數，不是改這個檔。
// </auto-generated>
using System.Collections.Generic;

namespace WitchShop.Data
{
    /// <summary>
    /// 家具上的一個商品陳列位。座標是**相對於家具錨點（圖的正下方中央＝佔地前角）的世界偏移**，y 朝上；
    /// (X, Y) 是商品**底部中心**該落的位置（站在層板／桌面上）。家具翻面時 X 取負。
    /// MaxW／MaxH ＝這個位子塞得下的最大寬高（商品圖等比縮到塞得下）。Row ＝第幾層（0＝最上層）。
    /// </summary>
    public readonly struct DisplaySlot
    {
        public readonly float X, Y, MaxW, MaxH;
        public readonly int Row;

        public DisplaySlot(float x, float y, float maxW, float maxH, int row)
        { X = x; Y = y; MaxW = maxW; MaxH = maxH; Row = row; }
    }

    /// <summary>
    /// 每款家具的陳列位（由上而下、由左而右；販售桌是一排三個）。
    /// 跟 Resources/furniture/&lt;id&gt;.png 是**同一支產生器一起畫出來的** —— 換了圖要重跑，
    /// 否則商品會浮在半空中。圖的尺寸也記在這裡（ArtW/ArtH），對不上就不擺（例如用 --restore 換回舊圖時）。
    /// </summary>
    public static class ShopDisplaySlots
    {
        static readonly Dictionary<string, (int ArtW, int ArtH, DisplaySlot[] Slots)> Table = new()
        {
%BODY%
        };

        static readonly DisplaySlot[] None = new DisplaySlot[0];

        /// <summary>這款家具的陳列位；查不到、或圖的尺寸跟產生時不一樣（圖被換過）就回空陣列。</summary>
        public static DisplaySlot[] Get(string id, float artW, float artH)
        {
            if (!Table.TryGetValue(id, out var t)) return None;
            if (t.ArtW != (int)artW || t.ArtH != (int)artH) return None;
            return t.Slots;
        }
    }
}
'''.replace('%BODY%', '\n'.join(rows))
    with open(CS_OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(cs)


def _f(v):
    s = ('%.1f' % v).rstrip('0').rstrip('.')
    return s if s not in ('-0', '') else '0'


# ═══════════════════════════════ 擺放驗算（RoomLayout.ArtFits 的 Python 版）═══════════════════════════════

ALPHA = 40      # 跟 gen_furniture_bounds.py 一樣


def art_box(img):
    """同 gen_furniture_bounds.py：回傳 (ImgW, ImgH, X0, Y0, X1, Y1)，y 從圖底往上量。"""
    h, w = img.shape[:2]
    ys, xs = np.nonzero(img[..., 3] >= ALPHA)
    return w, h, int(xs.min()), h - 1 - int(ys.max()), int(xs.max()) + 1, h - int(ys.min())


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


SIL, FLOOR = _silhouette()


def inside_poly(poly, p, margin):
    """同 ShopRoom.InsidePoly（頂點順時針）。"""
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln < 1e-3:
            continue
        cross = (dx * (p[1] - a[1]) - dy * (p[0] - a[0])) / ln
        if -cross < margin:
            return False
    return True


def art_fits(box_, anchor, flipped):
    """同 RoomLayout.ArtFits ＋ ArtRect。"""
    w, h, x0, y0, x1, y1 = box_
    if flipped:
        x0, x1 = w - x1, w - x0
    left = anchor[0] - w / 2.0 + x0
    right = left + (x1 - x0)
    bottom = anchor[1] + y0
    top = bottom + (y1 - y0)
    on_floor = inside_poly(FLOOR, (left, bottom), 0) and inside_poly(FLOOR, (right, bottom), 0)
    in_room = all(inside_poly(SIL, c, 4.0) for c in ((left, bottom), (right, bottom), (left, top), (right, top)))
    return on_floor and in_room


def wall_fits(box_, depth):
    """靠左後牆（不翻面、左角基準）每個 gy、靠右後牆（翻面、右角基準）每個 gx 放不放得下。"""
    left_ok = []
    for gy in range(0, GRID_H - depth + 1):
        if art_fits(box_, tile_front(0, gy + depth - 1), False):
            left_ok.append(gy)
    right_ok = []
    for gx in range(0, GRID_W - depth + 1):
        if art_fits(box_, tile_front(gx + depth - 1, 0), True):
            right_ok.append(gx)
    return left_ok, right_ok


def check_fits(images, label):
    print('\n■ 擺放驗算（RoomLayout.ArtFits 規則）—— %s' % label)
    ok = True
    for pid in ['sale_table'] + list(SHELVES):
        if pid not in images:
            continue
        bx = art_box(images[pid])
        if pid == 'sale_table':
            from_cs = re.search(r'DefaultSaleCell\s*=\s*new\((\d+),\s*(\d+)\)', _SHOP)
            gx, gy = int(from_cs.group(1)), int(from_cs.group(2))
            good = art_fits(bx, tile_front(gx + 1, gy), False)
            print('  %-14s 圖 %3dx%-3d 預設位置 (%d,%d)：%s' % (pid, bx[0], bx[1], gx, gy, '合法' if good else '⚠️ 穿牆'))
            ok &= good
            continue
        dep = SHELF_DEPTH[pid]
        lo, ro = wall_fits(bx, dep)
        n_l, n_r = GRID_H - dep + 1, GRID_W - dep + 1
        print('  %-14s 圖 %3dx%-3d 高 %3d  靠左牆 gy∈%s（%d/%d）  翻面靠右牆 gx∈%s（%d/%d）' % (
            pid, bx[0], bx[1], bx[5] - bx[3], _ranges(lo), len(lo), n_l, _ranges(ro), len(ro), n_r))
        ok &= bool(lo) and bool(ro)
    return ok


def _ranges(xs):
    if not xs:
        return '無'
    out, a, b = [], xs[0], xs[0]
    for x in xs[1:]:
        if x == b + 1:
            b = x
            continue
        out.append('%d' % a if a == b else '%d..%d' % (a, b))
        a = b = x
    out.append('%d' % a if a == b else '%d..%d' % (a, b))
    return ','.join(out)


def load_pngs(d):
    out = {}
    for pid, _, _ in piece_list():
        p = os.path.join(d, pid + '.png')
        if os.path.exists(p):
            out[pid] = np.asarray(Image.open(p).convert('RGBA'))
    return out


# ═══════════════════════════════ 預覽 ═══════════════════════════════

def slots_needed(count):
    """同 ShopRoomView.SlotsFor：1 件→1 格、2～4→2、5 以上→3。"""
    return 1 if count <= 1 else 2 if count <= 4 else 3


def item_pool():
    """預覽用的商品圖：從 Resources 的道具資料夾隨便拿幾張（另一個代理正在重畫，有什麼用什麼）。"""
    pool = []
    for sub in ('items', 'potions', 'candy', 'garden'):
        d = os.path.join(RES, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.png'):
                pool.append(os.path.join(d, fn))
    return pool


def fit_item(path, mw, mh):
    im = Image.open(path).convert('RGBA')
    k = min(mw / im.size[0], mh / im.size[1])
    w, h = max(1, round(im.size[0] * k)), max(1, round(im.size[1] * k))
    return im.resize((w, h), Image.NEAREST)


def compose(arts_png, slots, layout, listings, pool):
    """把一組擺設疊在店的底圖上。layout: [(id, gx, gy, flip, anchor)]，anchor 0 前角／1 左角／2 右角。"""
    base = Image.open(SHOP_ROOM_PNG).convert('RGBA')
    W, H = base.size
    pieces = []
    for pid, gx, gy, flip, anc in layout:
        if pid == 'sale_table':
            w, h = (1, 2) if flip else (2, 1)
        else:
            d = SHELF_DEPTH[pid]
            w, h = (d, 1) if flip else (1, d)
        if anc == 1:
            a = tile_front(gx, gy + h - 1)
        elif anc == 2:
            a = tile_front(gx + w - 1, gy)
        else:
            a = tile_front(gx + w - 1, gy + h - 1)
        pieces.append((pid, flip, a))
    # 依 ShopRoomView 的分配：先販售桌、再依擺出來的順序
    order = [p for p in pieces if p[0] == 'sale_table'] + [p for p in pieces if p[0] != 'sale_table']
    goods = {i: [] for i in range(len(pieces))}
    queue = [(nm, slots_needed(c)) for nm, c in listings]
    qi = 0
    for p in order:
        idx = pieces.index(p)
        sl = slots[p[0]]
        k = 0
        rows = {}
        for s_ in sl:
            rows.setdefault(s_[4], []).append(s_)
        flat = []
        for r in sorted(rows):
            flat += rows[r][::-1] if p[1] else rows[r]
        while qi < len(queue) and k < len(flat):
            nm, n = queue[qi]
            take = min(n, len(flat) - k)
            for j in range(take):
                goods[idx].append((flat[k + j], nm))
            k += take
            qi += 1
    # 畫：依 sortingOrder（-錨點 y）由小到大，商品緊跟在它的家具後面
    canvas = base.copy()
    for idx in sorted(range(len(pieces)), key=lambda i: -pieces[i][2][1]):
        pid, flip, (ax, ay) = pieces[idx]
        im = Image.fromarray(arts_png[pid])
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        px = int(round(ax + W / 2 - im.size[0] / 2))
        py = int(round(H / 2 - ay - im.size[1]))
        canvas.alpha_composite(im, (px, py))
        for (x, y, mw, mh, row), nm in goods[idx]:
            it = fit_item(pool[nm % len(pool)], mw, mh) if pool else None
            if it is None:
                continue
            sx = -x if flip else x
            gx_ = int(round(ax + sx + W / 2 - it.size[0] / 2))
            gy_ = int(round(H / 2 - (ay + y) - it.size[1]))
            canvas.alpha_composite(it, (gx_, gy_))
    return canvas


def preview(arts_png, slots, outdir):
    os.makedirs(outdir, exist_ok=True)
    files = []
    bg = (54, 40, 46, 255)
    # 1) 總覽：17 張排一排（×2），每張下面標錨點、標出陳列位
    ids = ['sale_table'] + list(SHELVES)
    cols = 6
    cw, ch = 200, 220
    sheet = Image.new('RGBA', (cols * cw, ((len(ids) + cols - 1) // cols) * ch), bg)
    sheet_slots = sheet.copy()
    from PIL import ImageDraw
    dr = ImageDraw.Draw(sheet_slots)
    for i, pid in enumerate(ids):
        im = Image.fromarray(arts_png[pid])
        cx = (i % cols) * cw + cw // 2
        by = (i // cols) * ch + ch - 14
        for sh in (sheet, sheet_slots):
            sh.alpha_composite(im, (cx - im.size[0] // 2, by - im.size[1]))
        for (x, y, mw, mh, row) in slots.get(pid, []):
            bx, byy = cx + x, by - y
            dr.rectangle([bx - mw / 2, byy - mh, bx + mw / 2 - 1, byy - 1], outline=(120, 255, 160, 255))
            dr.point([(bx, byy)], fill=(255, 255, 0, 255))
        dr.line([(cx - 3, by), (cx + 3, by)], fill=(255, 80, 80, 255))
    p = os.path.join(outdir, 'overview.png')
    sheet.resize((sheet.size[0] * 2, sheet.size[1] * 2), Image.NEAREST).save(p)
    files.append(p)
    p = os.path.join(outdir, 'overview_slots.png')
    sheet_slots.resize((sheet_slots.size[0] * 2, sheet_slots.size[1] * 2), Image.NEAREST).save(p)
    files.append(p)
    # 2) 擺進店裡：四組擺設把 16 款都擺一次（左後牆不翻面、右後牆翻面），加販售桌與商品
    shelves = list(SHELVES)
    groups = [shelves[0:4], shelves[4:8], shelves[8:12], shelves[12:16]]
    pool = item_pool()
    listings = [(0, 5), (1, 1), (2, 3), (3, 2), (4, 7), (5, 1), (6, 4), (7, 2), (8, 6), (9, 1), (10, 3), (11, 2),
                (12, 5), (13, 1), (14, 2), (15, 3), (16, 9), (17, 1)]
    for gi, grp in enumerate(groups):
        layout = [('sale_table', 5, 3, False, 0)]
        # 左後牆：gy=0、3（第三座會壓到後花園門口的保留格，改擺 gy=6 前先看深度）
        lg = [grp[0], grp[1]]
        gy = 0
        for sid in lg:
            layout.append((sid, 0, gy, False, 1))
            gy += SHELF_DEPTH[sid]
        gx = 2
        for sid in grp[2:]:
            layout.append((sid, gx, 0, True, 2))
            gx += SHELF_DEPTH[sid]
        # 再擺一座靠右後牆的（同組第一款翻面），看同一款兩種朝向
        layout.append((grp[0], gx, 0, True, 2))
        img = compose(arts_png, slots, layout, listings[gi * 3:] + listings[:gi * 3], pool)
        crop = img.crop((0, 40, 960, 520))
        p = os.path.join(outdir, 'room_%d.png' % (gi + 1))
        crop.resize((crop.size[0] * 2, crop.size[1] * 2), Image.NEAREST).save(p)
        files.append(p)
    # 3) 沒有商品的對照（看家具本身）
    layout = [('sale_table', 5, 3, False, 0)]
    for k, sid in enumerate(shelves[:2]):
        layout.append((sid, 0, k * 3, False, 1))
    img = compose(arts_png, slots, layout, [], pool)
    p = os.path.join(outdir, 'room_empty.png')
    img.crop((0, 40, 960, 520)).save(p)
    files.append(p)
    return files


# ═══════════════════════════════ 備份／還原 ═══════════════════════════════

def backup_originals():
    os.makedirs(ORIG_DIR, exist_ok=True)
    n = 0
    for pid, _, _ in piece_list():
        src = os.path.join(FURN_DIR, pid + '.png')
        dst = os.path.join(ORIG_DIR, pid + '.png')
        if not os.path.exists(dst) and os.path.exists(src):          # ⚠️ 已經有備份就不要蓋（那才是原圖）
            shutil.copy2(src, dst)
            n += 1
    if n:
        print('備份了 %d 張原圖到 %s' % (n, ORIG_DIR))


def restore_originals():
    n = 0
    for pid, _, _ in piece_list():
        src = os.path.join(ORIG_DIR, pid + '.png')
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(FURN_DIR, pid + '.png'))   # 只蓋 PNG，.meta 不動
            n += 1
    print('還原了 %d 張原圖（ShopDisplaySlots.cs 的圖尺寸對不上，商品會自動不擺）' % n)


def run_bounds():
    subprocess.run([sys.executable, os.path.join(HERE, 'gen_furniture_bounds.py')], check=True)


def main():
    args = sys.argv[1:]
    if '--restore' in args:
        restore_originals()
        run_bounds()
        return 0
    if '--check' in args:
        ok = check_fits(load_pngs(FURN_DIR), '現有的圖')
        return 0 if ok else 1
    preview_dir = args[args.index('--preview') + 1] if '--preview' in args else None

    backup_originals()
    arts = build()
    os.makedirs(SVG_DIR, exist_ok=True)
    for pid, (img, s, slots) in arts.items():
        Image.fromarray(img).save(os.path.join(FURN_DIR, pid + '.png'))
        with open(os.path.join(SVG_DIR, pid + '.svg'), 'w', encoding='utf-8') as fh:
            fh.write(s.markup(standalone=True))
    write_cs(arts)
    run_bounds()
    print('寫出 %d 張圖到 %s、SVG 到 %s、陳列位表 %s' % (len(arts), FURN_DIR, SVG_DIR, CS_OUT))
    total = 0
    for pid, (img, s, slots) in arts.items():
        total += len(slots)
        rows = {}
        for sl in slots:
            rows.setdefault(sl[4], []).append(sl)
        print('  %-14s %3dx%-3d 陳列位 %2d（%s）' % (pid, img.shape[1], img.shape[0], len(slots), '、'.join(
            '第%d層 %d 個 %gx%g' % (r, len(v), v[0][2], v[0][3]) for r, v in sorted(rows.items()))))
    print('  共 %d 個陳列位' % total)
    pngs = {k: v[0] for k, v in arts.items()}
    ok = check_fits(pngs, '新圖')
    orig = load_pngs(ORIG_DIR)
    if orig:
        check_fits(orig, '原圖（對照）')
    if preview_dir:
        for f in preview(pngs, {k: v[2] for k, v in arts.items()}, preview_dir):
            print('預覽：' + f)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
