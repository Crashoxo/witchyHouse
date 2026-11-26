# -*- coding: utf-8 -*-
"""
魔女的房間（藥水室 brew）—— 用程式組 SVG 畫出整間房與每一件家具，轉成像素風 PNG，
並產生遊戲讀的配置表 Assets/Scripts/Data/BrewRoomLayout.cs。

    python tools/gen_brew_room.py                    # 重畫全部、寫 PNG 與 C# 表、印互動點檢查
    python tools/gen_brew_room.py --preview DIR      # 另外輸出合成預覽（白天／夜晚／碰撞範圍）
    python tools/gen_brew_room.py --check            # 只做互動點與可走範圍的檢查（不畫圖、不寫檔）

固定結果、可重跑（亂數一律固定種子）。需要 Pillow、numpy，以及本機的 Chrome（或 Edge）當 SVG 轉檔器：
這台沒有 inkscape / cairosvg，所以把全部 SVG 排在一張 HTML 上，用無頭 Chrome 截一次圖再切開。
可用環境變數 CHROME 指定瀏覽器執行檔。

── 這支是「魔女房間」所有數字的唯一來源 ─────────────────────────────
  - 房間幾何（等距原點、地板長寬、牆高）、每件家具擺在哪（地板 uv 座標）、碰撞落地範圍、
    排序、夜晚發光的位置、五個互動點與互動距離、女巫出生點、地板可走多邊形 —— 全部在這裡；
  - C# 那邊（Core/BrewRoom.cs、Core/Obstacles.cs、PlayerController）只讀產生出來的
    Data/BrewRoomLayout.cs，不自己寫常數；
  - 離線檢查 tools/check_walkable.py 也 import 這支（room_data()），兩邊的數值不會漂移。

── 座標 ─────────────────────────────────────────────────────────
  地板 uv：u 沿「右後牆」往右下、v 沿「左後牆」往左下、z 往上。等距 2:1：
      畫面 x = OX + u − v，畫面 y = OY + (u + v)/2 − z      （房間圖的像素，y 朝下）
  世界座標（Unity，PPU 1）：房間圖的中心＝(0,0)，y 朝上：
      世界 x = 畫面 x − 541，世界 y = 358.5 − 畫面 y
  每件家具在自己的區域座標裡畫（落地範圍 u∈[0,du]、v∈[0,dv]），擺放時再平移到 (U,V)。

── 畫法的約定（改圖、加家具時請照著）───────────────────────────────
  - 光從右後牆的窗戶（畫面左上）來：頂面最亮、朝左下的面（+v 面）次亮、朝右下的面（+u 面）最暗。
  - 每種材質 4 階色（亮／本色／暗／最暗），內部線條用該材質的最暗色、1px；
    外輪廓由後處理自動補 1px 深棕紫（OUTLINE）。不要漸層、不要模糊（發光圖 glow 例外）。
  - 立著的物件腳下自帶一塊橢圓接地陰影（畫成 SHADOW 鍵色，後處理換成半透明深色）。
  - 後處理：alpha 二值化、顏色貼齊色盤（PAL）、裁到不透明範圍。
"""
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, 'Assets', 'Resources')
OUT_DIR = os.path.join(RES, 'rooms', 'brew')
SVG_DIR = os.path.join(HERE, 'brew_room', 'svg')
CS_OUT = os.path.join(ROOT, 'Assets', 'Scripts', 'Data', 'BrewRoomLayout.cs')
ART_PREFIX = 'rooms/brew/'

SQ2 = math.sqrt(2.0)

# ═══════════════════════════════ 房間幾何 ═══════════════════════════════

CANVAS_W, CANVAS_H = 1082, 717      # 跟舊的整張背景一樣（場景的 Ground 用它量尺寸）
OX, OY = 441, 196                   # 地板最裡面那個角（兩面後牆交會處，z=0）在房間圖上的位置
ROOM_U, ROOM_V = 600, 400           # 地板：右後牆長 600、左後牆長 400（uv 單位）
WALL_H = 176                        # 牆高（畫面像素）
WALL_T = 12                         # 牆厚（牆頂那條石蓋的寬）
RIM = 14                            # 前方兩條開放邊的地板厚度


def room_px(u, v, z=0.0):
    """地板 uv → 房間圖像素（y 朝下）。"""
    return OX + u - v, OY + (u + v) * 0.5 - z


def px_to_world(x, y):
    return x - CANVAS_W / 2, CANVAS_H / 2 - y


def uv_to_world(u, v):
    return px_to_world(*room_px(u, v))


def world_to_uv(wx, wy):
    x, y = wx + CANVAS_W / 2, CANVAS_H / 2 - wy
    dx, dy = x - OX, y - OY
    return dy + dx / 2, dy - dx / 2


# ═══════════════════════════════ 色盤 ═══════════════════════════════
# 從舊的整張房間圖取色：暖棕木頭（地板偏灰、家具偏紅）、灰米石牆、深紫布配金滾邊、深藍星星地毯、
# 藥水的青綠／桃紅／琥珀點綴、燭火橙黃。每種材質 3～4 階。全部物件共用這一張。

PAL = {
    'outline': '#2a1b24',   # 外描邊（深棕紫，不是純黑）
    # 地板木（灰棕）
    'fl_hi': '#9c8572', 'fl': '#84705f', 'fl_dk': '#6c5a4c', 'fl_dk2': '#4f4139', 'fl_lit': '#b59c82',
    # 家具木（紅棕）
    'wd_hi': '#b9784c', 'wd': '#955a38', 'wd_dk': '#703f29', 'wd_dk2': '#4b291c',
    # 石牆（灰米）
    'st_hi': '#cdbfa6', 'st': '#ad9f88', 'st_dk': '#8c806d', 'st_dk2': '#6c6254', 'mortar': '#585043',
    # 深石（壁爐）
    'sf_hi': '#a69a8b', 'sf': '#867a6c', 'sf_dk': '#665c51', 'sf_dk2': '#473f39',
    # 紫布
    'pu_hi': '#8b63a3', 'pu': '#684484', 'pu_dk': '#4b2f64', 'pu_dk2': '#331f46',
    # 金
    'go_hi': '#fbe08a', 'go': '#dcae4c', 'go_dk': '#a67a2f',
    # 深藍
    'bl_hi': '#5571b9', 'bl': '#3b5095', 'bl_dk': '#29386f', 'bl_dk2': '#1c2651',
    # 銅
    'cu_hi': '#f2ae70', 'cu': '#ca7a43', 'cu_dk': '#924f2b',
    # 鐵
    'ir_hi': '#7c8292', 'ir': '#565b69', 'ir_dk': '#3b3f4b', 'ir_dk2': '#262830',
    # 皮
    'le_hi': '#c08758', 'le': '#9a613b', 'le_dk': '#6d4026',
    # 米白（布、紙、蠟）
    'li_hi': '#f6eedb', 'li': '#e2d4b8', 'li_dk': '#bbac8e',
    # 綠草
    'gr_hi': '#a7cc73', 'gr': '#6f9e4b', 'gr_dk': '#476b31',
    # 藥水
    'teal_hi': '#9df0dc', 'teal': '#43c8b0', 'teal_dk': '#278a7e',
    'pink': '#ee70a3', 'pink_dk': '#ad4576',
    'amber': '#f1b23d', 'violet': '#a680df',
    # 火
    'fire_y': '#fff2a6', 'fire_o': '#ffb341', 'fire_r': '#e8652d',
    # 玻璃／天空
    'gl_hi': '#eef8ff', 'gl': '#b4d6e8', 'sky': '#9fcff3',
    # 夜空（夜晚版窗外，不壓暗）
    'n_sky': '#243270', 'n_sky_dk': '#161e4a', 'n_star': '#fff4c4',
    # 黑貓
    'cat': '#2c2634', 'cat_hi': '#4b435a',
}
SHADOW_KEY = '#ff00ff'                       # 接地陰影的鍵色（後處理換成下面的半透明色）
SHADOW_RGBA = (24, 12, 28, 92)
OUTLINE_RGB = tuple(int(PAL['outline'][i:i + 2], 16) for i in (1, 3, 5))

# 夜晚：房間殼另出一張壓暗偏藍紫的圖；家具在遊戲裡用 SpriteRenderer.color 乘同一組色（NIGHT_MUL）。
NIGHT_MUL = (0.56, 0.55, 0.76)
NIGHT_KEEP = ('n_', 'fire_', 'go_hi')       # 這些顏色夜晚不壓暗（夜空、火光）


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def rgb_hex(c):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, round(v)))) for v in c)


def night_palette():
    out = {}
    for k, v in PAL.items():
        if k.startswith(NIGHT_KEEP):
            out[k] = v
        else:
            r, g, b = hex_rgb(v)
            out[k] = rgb_hex((r * NIGHT_MUL[0], g * NIGHT_MUL[1], b * NIGHT_MUL[2]))
    return out


# ═══════════════════════════════ SVG 小工具 ═══════════════════════════════

class Svg:
    """一張物件畫布。座標是畫布像素（y 朝下）；顏色用色盤的名字。"""
    _uid = 0

    def __init__(self, w, h, pal=None, tag='x'):
        self.w, self.h = int(w), int(h)
        self.pal = pal or PAL
        self.el = []
        self.defs = []
        self.tag = tag

    def c(self, k):
        if k is None:
            return 'none'
        if k == 'SHADOW':
            return SHADOW_KEY
        if k.startswith('#'):
            return k
        return self.pal[k]

    @staticmethod
    def _pts(pts):
        return ' '.join('%.2f,%.2f' % (x, y) for x, y in pts)

    def _stroke(self, stroke, sw):
        if not stroke:
            return ''
        return ' stroke="%s" stroke-width="%g" stroke-linejoin="round"' % (self.c(stroke), sw)

    def poly(self, pts, fill, stroke=None, sw=1):
        self.el.append('<polygon points="%s" fill="%s"%s/>' % (self._pts(pts), self.c(fill), self._stroke(stroke, sw)))

    def path(self, d, fill, stroke=None, sw=1):
        self.el.append('<path d="%s" fill="%s"%s/>' % (d, self.c(fill), self._stroke(stroke, sw)))

    def line(self, a, b, col, sw=1):
        self.el.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%g" stroke-linecap="square"/>'
                       % (a[0], a[1], b[0], b[1], self.c(col), sw))

    def pline(self, pts, col, sw=1):
        self.el.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%g" stroke-linejoin="round" '
                       'stroke-linecap="round"/>' % (self._pts(pts), self.c(col), sw))

    def ell(self, cx, cy, rx, ry, fill, stroke=None, sw=1):
        self.el.append('<ellipse cx="%.2f" cy="%.2f" rx="%.2f" ry="%.2f" fill="%s"%s/>'
                       % (cx, cy, rx, ry, self.c(fill), self._stroke(stroke, sw)))

    def rect(self, x, y, w, h, fill):
        self.el.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s"/>' % (x, y, w, h, self.c(fill)))

    def px(self, x, y, col, w=1, h=1):
        """畫一個（或一小塊）像素：細節點綴用。"""
        self.rect(round(x), round(y), w, h, col)

    def clip(self, pts=None, d=None):
        Svg._uid += 1
        cid = 'c%s%d' % (self.tag, Svg._uid)
        shape = '<polygon points="%s"/>' % self._pts(pts) if pts is not None else '<path d="%s"/>' % d
        self.defs.append('<clipPath id="%s">%s</clipPath>' % (cid, shape))
        self.el.append('<g clip-path="url(#%s)">' % cid)

    def end(self):
        self.el.append('</g>')

    def markup(self, standalone=True):
        head = '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" ' \
               'shape-rendering="crispEdges"' % (self.w, self.h, self.w, self.h)
        if not standalone:
            head += ' style="position:absolute;left:%dpx;top:%dpx"' % self._at
        defs = '<defs>%s</defs>' % ''.join(self.defs) if self.defs else ''
        return head + '>' + defs + ''.join(self.el) + '</svg>'


class Iso:
    """區域 uvz → 畫布像素。"""

    def __init__(self, ox, oy):
        self.ox, self.oy = ox, oy

    def __call__(self, u, v, z=0.0):
        return (self.ox + u - v, self.oy + (u + v) * 0.5 - z)


# ── 等距形狀 ──

def fu(P, u, v0, v1, z0, z1):
    """u＝常數的面（朝右下的 +u 面）上的矩形。"""
    return [P(u, v0, z0), P(u, v1, z0), P(u, v1, z1), P(u, v0, z1)]


def fv(P, v, u0, u1, z0, z1):
    """v＝常數的面（朝左下的 +v 面）上的矩形。"""
    return [P(u0, v, z0), P(u1, v, z0), P(u1, v, z1), P(u0, v, z1)]


def fz(P, z, u0, u1, v0, v1):
    """水平面上的矩形。"""
    return [P(u0, v0, z), P(u1, v0, z), P(u1, v1, z), P(u0, v1, z)]


def mat(name):
    return (name + '_hi', name, name + '_dk', name + '_dk2')


WOOD = mat('wd')
STONE = mat('st')
FSTONE = mat('sf')
IRON = mat('ir')
PURP = mat('pu')


def box(s, P, u0, u1, v0, v1, z0, z1, m, top=None, left=None, right=None, line=None, sw=1):
    """實心盒子：頂面＝亮、+v 面（左下）＝本色、+u 面（右下）＝暗、線＝最暗。"""
    hi, base, dk, dk2 = m
    s.poly(fv(P, v1, u0, u1, z0, z1), left or base, line or dk2, sw)
    s.poly(fu(P, u1, v0, v1, z0, z1), right or dk, line or dk2, sw)
    s.poly(fz(P, z1, u0, u1, v0, v1), top or hi, line or dk2, sw)


def uv_ellipse(P, cu, cv, a, b, z=0.0, n=48):
    """uv 平面上的橢圓（a 沿 u、b 沿 v）→ 畫布上的多邊形。"""
    return [P(cu + a * math.cos(t), cv + b * math.sin(t), z) for t in (2 * math.pi * i / n for i in range(n))]


def shadow(s, P, cu, cv, a, b):
    s.poly(uv_ellipse(P, cu, cv, a, b), 'SHADOW')


def iso_circle(P, cu, cv, r, z):
    x, y = P(cu, cv, z)
    return x, y, r * SQ2, r * SQ2 / 2


def cyl(s, P, cu, cv, r, z0, z1, m, top=None, shade=True, line=None):
    """直立圓柱（等距）：身體左側亮帶、右側暗帶，最後蓋頂面橢圓。"""
    hi, base, dk, dk2 = m
    line = line or dk2
    x, yb, rx, ry = iso_circle(P, cu, cv, r, z0)
    _, yt, _, _ = iso_circle(P, cu, cv, r, z1)
    d = 'M%.2f,%.2f L%.2f,%.2f A%.2f,%.2f 0 0 0 %.2f,%.2f L%.2f,%.2f Z' % (
        x - rx, yt, x - rx, yb, rx, ry, x + rx, yb, x + rx, yt)
    s.path(d, base)
    if shade and rx >= 3:
        s.clip(d=d)
        s.rect(x + rx * 0.35, yt - ry - 2, rx, yb - yt + 2 * ry + 4, dk)
        s.rect(x - rx, yt - ry - 2, rx * 0.35, yb - yt + 2 * ry + 4, hi)
        s.end()
    s.path(d, None, line)
    s.ell(x, yt, rx, ry, top or hi, line)
    return x, yt, rx, ry


def star_pts(cx, cy, ro, ri, n=5, rot=-90.0):
    pts = []
    for i in range(n * 2):
        r = ro if i % 2 == 0 else ri
        a = math.radians(rot + i * 180.0 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def tiny_star(s, x, y, col='go', big=False):
    """像素小星星（十字＋中心）。"""
    s.px(x, y, col)
    s.px(x - 1, y, col)
    s.px(x + 1, y, col)
    s.px(x, y - 1, col)
    s.px(x, y + 1, col)
    if big:
        s.px(x - 2, y, col)
        s.px(x + 2, y, col)
        s.px(x, y - 2, col)
        s.px(x, y + 2, col)


def flame(s, x, y, h, w, frame=0):
    """燭火：外橙內黃的水滴，(x, y) 是燭芯頂。"""
    lean = (-1, 1, 0)[frame % 3] * 0.8
    tip = (x + lean, y - h)
    outer = [(x - w, y - h * 0.32), (x - w * 0.6, y + 0.5), (x + w * 0.6, y + 0.5), (x + w, y - h * 0.32), tip]
    s.poly(outer, 'fire_o', 'fire_r', 1)
    s.poly([(x - w * 0.45, y - h * 0.3), (x, y), (x + w * 0.45, y - h * 0.3), (x + lean * 0.6, y - h * 0.72)], 'fire_y')


def candle(s, P, cu, cv, r, z0, h, frame=0, drips=True):
    x, yt, rx, ry = cyl(s, P, cu, cv, r, z0, z0 + h, ('li_hi', 'li', 'li_dk', 'li_dk'), top='li_hi')
    if drips and rx >= 3:
        s.line((x - rx * 0.3, yt + 1), (x - rx * 0.3, yt + 4), 'li_hi', 1)
        s.line((x + rx * 0.5, yt + 1), (x + rx * 0.5, yt + 3), 'li_dk', 1)
    s.line((x, yt), (x, yt - 2), 'ir_dk2', 1)
    flame(s, x, yt - 2, 7 + r * 0.6, 2.6 + r * 0.25, frame)


def hull(pts):
    pts = sorted(set((round(a, 2), round(b, 2)) for a, b in pts))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


# ═══════════════════════════════ 瓶瓶罐罐（畫布座標）═══════════════════════════════

def flask_round(s, x, y, r, liquid, neck=8, nw=3, level=0.45):
    """圓底燒瓶：(x, y) 是瓶底接觸點。"""
    cy = y - r
    s.rect(x - nw / 2, cy - r - neck + 1, nw, neck + 2, 'gl')
    s.ell(x, cy, r, r, 'gl', 'ir_dk', 1)
    s.clip(d='M%.2f,%.2f A%.2f,%.2f 0 1 0 %.2f,%.2f A%.2f,%.2f 0 1 0 %.2f,%.2f Z' % (
        x - r + 1, cy, r - 1, r - 1, x + r - 1, cy, r - 1, r - 1, x - r + 1, cy))
    lv = cy + r - 2 * r * level
    s.rect(x - r, lv, 2 * r, 2 * r, liquid[0])
    s.rect(x + r * 0.35, lv, r, 2 * r, liquid[1])
    s.line((x - r, lv), (x + r, lv), 'gl_hi', 1)
    s.end()
    s.line((x - nw / 2, cy - r - neck + 1), (x - nw / 2, cy - r + 1), 'ir_dk', 1)
    s.line((x + nw / 2, cy - r - neck + 1), (x + nw / 2, cy - r + 1), 'ir_dk', 1)
    s.rect(x - nw / 2 - 1, cy - r - neck - 1, nw + 2, 2, 'le')     # 軟木塞
    s.px(x - r * 0.45, cy - r * 0.45, 'gl_hi', 2, 2)


def flask_cone(s, x, y, w, h, liquid):
    """錐形瓶。"""
    neck = h * 0.38
    pts = [(x - w / 2, y), (x + w / 2, y), (x + 2, y - h + neck), (x + 2, y - h), (x - 2, y - h), (x - 2, y - h + neck)]
    s.poly(pts, 'gl', 'ir_dk', 1)
    lv = y - (h - neck) * 0.5
    s.clip(pts=pts)
    s.rect(x - w, lv, w * 2, h, liquid[0])
    s.rect(x + w * 0.18, lv, w, h, liquid[1])
    s.line((x - w, lv), (x + w, lv), 'gl_hi', 1)
    s.end()
    s.poly(pts, None, 'ir_dk', 1)
    s.line((x - 1, y - h + neck + 2), (x - w * 0.3, y - 3), 'gl_hi', 1)


def bottle(s, x, y, w, h, liquid, neck=5, cork='le', label=None):
    """直身瓶：(x, y) 底部中央。"""
    s.rect(x - w / 2, y - h, w, h, 'gl')
    s.rect(x - w / 2, y - h * 0.62, w, h * 0.62, liquid[0])
    s.rect(x + w * 0.15, y - h * 0.62, w * 0.35, h * 0.62, liquid[1])
    if label:
        s.rect(x - w / 2 + 1, y - h * 0.5, w - 2, h * 0.24, label)
    s.poly([(x - w / 2, y), (x + w / 2, y), (x + w / 2, y - h), (x - w / 2, y - h)], None, 'ir_dk', 1)
    s.rect(x - 1.5, y - h - neck, 3, neck, 'gl')
    s.line((x - 1.5, y - h - neck), (x - 1.5, y - h), 'ir_dk', 1)
    s.line((x + 1.5, y - h - neck), (x + 1.5, y - h), 'ir_dk', 1)
    s.rect(x - 2, y - h - neck - 2, 4, 3, cork)
    s.line((x - w / 2 + 1.5, y - h + 2), (x - w / 2 + 1.5, y - h * 0.68), 'gl_hi', 1)


def test_tube(s, x, y, h, liquid):
    s.rect(x - 1.5, y - h, 3, h, 'gl')
    s.rect(x - 1.5, y - h * 0.5, 3, h * 0.5, liquid)
    s.poly([(x - 1.5, y), (x + 1.5, y), (x + 1.5, y - h), (x - 1.5, y - h)], None, 'ir_dk', 1)


LIQ_TEAL = ('teal', 'teal_dk')
LIQ_PINK = ('pink', 'pink_dk')
LIQ_AMBER = ('amber', 'cu')
LIQ_VIOLET = ('violet', 'pu')
LIQ_GREEN = ('gr_hi', 'gr')


# ═══════════════════════════════ 房間殼（牆＋地板＋窗＋牆上的東西）═══════════════════════════════

def stone_wall(s, F, length, height, rng, tones, mortar='mortar', z0=10,
               widths=(26, 30, 34, 38, 42, 48, 52), heights=(19, 21, 23, 25)):
    """一面石牆：F(s, z) 把牆面座標換成畫布座標。不規則的石塊、錯縫、少數幾塊顏色略深。"""
    corner = [F(0, z0), F(length, z0), F(length, height), F(0, height)]
    s.poly(corner, mortar)
    hi, base, dk, dk2 = tones
    z = z0
    row = 0
    while z < height - 2:
        hgt = rng.choice(heights)
        z1 = min(height, z + hgt)
        if height - z1 < 10:
            z1 = height
        x = -rng.uniform(4, 30) if row % 2 else -rng.uniform(18, 40)
        while x < length:
            w = rng.choice(widths)
            a, b = max(0.0, x), min(length, x + w)
            if b - a > 6:
                c = 2.2
                ia, ib, iz0, iz1 = a + 1.2, b - 1.2, z + 1.2, z1 - 1.2
                pts = [F(ia + c, iz0), F(ib - c, iz0), F(ib, iz0 + c), F(ib, iz1 - c),
                       F(ib - c, iz1), F(ia + c, iz1), F(ia, iz1 - c), F(ia, iz0 + c)]
                r = rng.random()
                tone = base if r < 0.66 else hi if r < 0.78 else dk if r < 0.95 else dk2
                s.poly(pts, tone)
                # 斜角小倒角：上緣一條亮線、下緣一條暗線（受光在上）
                if tone != hi:
                    s.line(F(ia + c, iz1 - 0.8), F(ib - c, iz1 - 0.8), hi, 1)
                s.line(F(ia + c, iz0 + 0.6), F(ib - c, iz0 + 0.6), dk2 if tone != dk2 else mortar, 1)
                # 少數石塊有一兩個小坑
                if rng.random() < 0.25:
                    px_, pz = F(rng.uniform(ia + 4, ib - 4), rng.uniform(iz0 + 4, iz1 - 4))
                    s.px(px_, pz, dk, 2, 1)
            x += w
        z = z1
        row += 1


def floor_planks(s, P, rng, colmap=None, clip=None):
    """木地板：沿 u 方向鋪的長木板，錯縫，木紋短線，偶爾一個節眼。"""
    cm = colmap or {}
    def c(k):
        return cm.get(k, k)
    W = 25
    rows = ROOM_V // W
    if clip is not None:
        s.clip(pts=clip)
    boards = []
    for r in range(rows):
        v0, v1 = r * W, (r + 1) * W
        u = -rng.uniform(0, 120)
        while u < ROOM_U:
            ln = rng.choice((96, 120, 140, 160, 180, 210))
            a, b = max(0.0, u), min(float(ROOM_U), u + ln)
            if b - a > 2:
                t = rng.random()
                tone = 'fl' if t < 0.62 else 'fl_hi' if t < 0.8 else 'fl_dk'
                boards.append((a, b, v0, v1, tone, rng.random(), rng.random()))
            u += ln
    for a, b, v0, v1, tone, r1, r2 in boards:
        s.poly(fz(P, 0, a, b, v0, v1), c(tone))
    rr = random.Random(77)
    for a, b, v0, v1, tone, r1, r2 in boards:
        # 木紋短線
        grain = c('fl_dk') if tone != 'fl_dk' else c('fl_dk2')
        for _ in range(int((b - a) / 40) + 1):
            gu = rr.uniform(a + 6, max(a + 7, b - 26))
            gv = rr.uniform(v0 + 5, v1 - 5)
            gl = rr.uniform(10, 24)
            s.line(P(gu, gv), P(gu + gl, gv), grain, 1)
        if r1 < 0.12:
            ku, kv = rr.uniform(a + 10, max(a + 11, b - 10)), rr.uniform(v0 + 7, v1 - 7)
            x, y = P(ku, kv)
            s.ell(x, y, 3, 1.5, grain)
        # 上緣受光的一條亮線（木板之間的縫上方）
        s.line(P(a + 2, v0 + 1.6), P(b - 2, v0 + 1.6), c('fl_hi') if tone != 'fl_hi' else c('fl_lit'), 1)
    for r in range(1, rows):
        s.line(P(0, r * W), P(ROOM_U, r * W), c('fl_dk2'), 1)
    for a, b, v0, v1, tone, r1, r2 in boards:
        if b < ROOM_U:
            s.line(P(b, v0), P(b, v1), c('fl_dk2'), 1)
        if r2 < 0.5 and b - a > 60:     # 釘子
            s.px(*P(b - 4, (v0 + v1) / 2), c('fl_dk2'))
    if clip is not None:
        s.end()


# 窗（右後牆上，u 範圍、z 範圍）
WIN_U0, WIN_U1, WIN_Z0, WIN_Z1 = 84, 168, 70, 152
# 窗光在地板上的那塊（色塊、不是漸層）
LIGHT_PATCH = [(112, 56), (196, 56), (234, 150), (150, 150)]


def draw_window(s, P, night):
    F = lambda u, z, v=0: P(u, v, z)  # noqa: E731
    u0, u1, z0, z1 = WIN_U0, WIN_U1, WIN_Z0, WIN_Z1
    # 窗台下的石托
    box(s, P, u0 - 8, u1 + 8, 0, 9, z0 - 8, z0 - 2, STONE, top='st_hi', left='st', right='st_dk')
    # 牆洞（深）＋側面
    s.poly([F(u0, z0), F(u1, z0), F(u1, z1), F(u0, z1)], 'st_dk2', 'mortar')
    s.poly([P(u0, 0, z0), P(u0, -8, z0), P(u0, -8, z1), P(u0, 0, z1)], 'st_dk', 'mortar')   # 左側的牆厚（朝右下）
    s.poly([P(u0, -8, z1), P(u1, -8, z1), P(u1, 0, z1), P(u0, 0, z1)], 'st_dk2')            # 上緣
    # 玻璃（凹進牆 8）
    g = lambda u, z: P(u, -8, z)  # noqa: E731
    gu0, gu1, gz0, gz1 = u0 + 4, u1, z0, z1 - 4
    if not night:
        s.poly([g(gu0, gz0), g(gu1, gz0), g(gu1, gz1), g(gu0, gz1)], 'sky')
        s.poly([g(gu0, gz0 + 24), g(gu1, gz0 + 24), g(gu1, gz1), g(gu0, gz1)], 'gl')
        s.poly([g(gu0, gz1 - 18), g(gu1, gz1 - 18), g(gu1, gz1), g(gu0, gz1)], 'sky')
        # 遠山與樹
        hill = [g(gu0, gz0)] + [g(u, gz0 + 10 + 7 * math.sin((u - gu0) / 14.0) + 4 * math.sin(u / 5.0)) for u in range(int(gu0), int(gu1) + 1, 3)] + [g(gu1, gz0)]
        s.poly(hill, 'gr')
        hill2 = [g(gu0, gz0)] + [g(u, gz0 + 5 + 4 * math.sin((u - gu0) / 9.0 + 1.3)) for u in range(int(gu0), int(gu1) + 1, 3)] + [g(gu1, gz0)]
        s.poly(hill2, 'gr_dk')
        # 一朵雲
        cx, cy = g(gu0 + 22, gz1 - 18)
        s.ell(cx, cy, 8, 3, 'gl_hi')
        s.ell(cx + 6, cy - 2, 6, 3, 'gl_hi')
        # 反光斜線
        for k in (0, 1):
            a = g(gu0 + 12 + k * 40, gz1 - 6)
            b = g(gu0 + 2 + k * 40, gz0 + 30)
            s.line(a, b, 'gl_hi', 2)
    else:
        s.poly([g(gu0, gz0), g(gu1, gz0), g(gu1, gz1), g(gu0, gz1)], 'n_sky_dk')
        s.poly([g(gu0, gz0), g(gu1, gz0), g(gu1, gz0 + 34), g(gu0, gz0 + 34)], 'n_sky')
        hill = [g(gu0, gz0)] + [g(u, gz0 + 10 + 7 * math.sin((u - gu0) / 14.0) + 4 * math.sin(u / 5.0)) for u in range(int(gu0), int(gu1) + 1, 3)] + [g(gu1, gz0)]
        s.poly(hill, 'n_sky_dk')
        rr = random.Random(5)
        for _ in range(14):
            x, y = g(rr.uniform(gu0 + 3, gu1 - 3), rr.uniform(gz0 + 22, gz1 - 3))
            s.px(x, y, 'n_star')
        x, y = g(gu0 + 20, gz1 - 20)
        tiny_star(s, x, y, 'n_star')
        # 月亮（彎月）
        mx, my = g(gu1 - 22, gz1 - 18)
        s.ell(mx, my, 7, 7, 'n_star')
        s.ell(mx + 3.5, my - 2, 6, 6, 'n_sky_dk')
    # 窗框（木）＋十字窗櫺
    fr = 'wd'
    def bar_u(ua, ub, za, zb, col):
        s.poly([g(ua, za), g(ub, za), g(ub, zb), g(ua, zb)], col, 'wd_dk2', 1)
    bar_u(gu0, gu1, gz0, gz0 + 4, fr)
    bar_u(gu0, gu1, gz1 - 4, gz1, fr)
    bar_u(gu0, gu0 + 4, gz0, gz1, fr)
    bar_u(gu1 - 4, gu1, gz0, gz1, fr)
    mid = (gu0 + gu1) / 2
    bar_u(mid - 2, mid + 2, gz0, gz1, fr)
    zm = gz0 + (gz1 - gz0) * 0.52
    bar_u(gu0, gu1, zm - 2, zm + 2, fr)
    # 石楣（窗上方一塊大石）
    s.poly([F(u0 - 6, z1), F(u1 + 6, z1), F(u1 + 6, z1 + 12), F(u0 - 6, z1 + 12)], 'st_hi', 'mortar')
    s.line(F(u0 - 4, z1 + 1), F(u1 + 4, z1 + 1), 'st_dk', 1)
    # 窗台上的小盆栽
    pu_, pv_ = u1 - 14, 4
    cyl(s, P, pu_, pv_, 4, z0 - 2, z0 + 5, ('cu_hi', 'cu', 'cu_dk', 'wd_dk2'), top='wd_dk2')
    x, y = P(pu_, pv_, z0 + 5)
    for dx, dy, col in ((-3, -6, 'gr'), (3, -7, 'gr_hi'), (0, -10, 'gr'), (-5, -3, 'gr_dk'), (5, -3, 'gr_dk')):
        s.ell(x + dx, y + dy, 2.6, 2.2, col)


def draw_herbs(s, P):
    """右後牆、窗戶左邊：一根橫桿掛四束藥草。"""
    zr = 150
    a, b = P(12, 1, zr), P(74, 1, zr)
    s.line(a, b, 'wd_dk2', 3)
    s.line((a[0], a[1] - 1), (b[0], b[1] - 1), 'wd', 1)
    for u in (14, 72):
        x, y = P(u, 1, zr)
        s.rect(x - 1, y - 1, 3, 5, 'ir_dk')
    bundles = [(22, 'gr', 'gr_dk', 'gr_hi', 26), (36, 'violet', 'pu', 'pink', 22), (50, 'gr_hi', 'gr', 'li_hi', 28),
               (63, 'amber', 'cu', 'go_hi', 20)]
    for u, c1, c2, c3, ln in bundles:
        x, y = P(u, 2, zr)
        s.line((x, y), (x, y + 5), 'li_dk', 1)
        top = y + 5
        # 綁起來的莖
        s.rect(x - 1, top, 3, 5, 'gr_dk' if c1 != 'amber' else 'cu_dk')
        s.rect(x - 2, top + 2, 5, 2, 'li_dk')
        # 往下散開的葉子（倒三角＋鋸齒）
        pts = [(x - 2, top + 5), (x + 2, top + 5), (x + 8, top + ln * 0.6), (x + 5, top + ln * 0.8),
               (x + 2, top + ln), (x - 1, top + ln * 0.85), (x - 5, top + ln * 0.95), (x - 7, top + ln * 0.6)]
        s.poly(pts, c1, c2, 1)
        s.line((x, top + 6), (x + 1, top + ln - 3), c2, 1)
        s.line((x - 3, top + ln * 0.45), (x - 5, top + ln * 0.7), c2, 1)
        s.px(x - 3, top + ln * 0.3, c3, 2, 2)
        s.px(x + 3, top + ln * 0.5, c3)


def draw_starchart(s, P):
    """左後牆、書桌上方：裱框的星圖。"""
    F = lambda v, z: P(1, v, z)  # noqa: E731
    v0, v1, z0, z1 = 246, 292, 92, 146
    s.poly([F(v0, z0), F(v1, z0), F(v1, z1), F(v0, z1)], 'wd', 'wd_dk2', 1)
    s.poly([F(v0 + 4, z0 + 4), F(v1 - 4, z0 + 4), F(v1 - 4, z1 - 4), F(v0 + 4, z1 - 4)], 'bl_dk2', 'wd_dk2', 1)
    s.line(F(v0 + 1, z1 - 1), F(v1 - 1, z1 - 1), 'wd_hi', 1)
    cx, cy = F((v0 + v1) / 2, (z0 + z1) / 2)
    s.ell(cx, cy, 13, 13, None, 'go_dk', 1)
    s.ell(cx, cy, 8, 8, None, 'go_dk', 1)
    s.line((cx - 14, cy), (cx + 14, cy), 'go_dk', 1)
    s.line((cx, cy - 16), (cx, cy + 16), 'go_dk', 1)
    s.ell(cx - 6, cy - 4, 4, 4, 'go_hi')
    s.ell(cx - 4.5, cy - 5, 3.2, 3.2, 'bl_dk2')
    for dx, dy in ((7, -9), (9, 5), (-8, 8), (2, 11), (-11, -10), (11, -14)):
        s.px(cx + dx, cy + dy, 'go_hi')
    tiny_star(s, cx + 5, cy - 2, 'go_hi')


def draw_wallshelf(s, P):
    """右後牆、床與壁爐之間：小掛架，放藥瓶與骷髏蠟燭。"""
    u0, u1, z = 404, 452, 112
    box(s, P, u0, u1, 0, 10, z - 4, z, WOOD, top='wd_hi')
    for u in (u0 + 6, u1 - 6):
        a = P(u, 1, z - 4)
        s.poly([a, (a[0], a[1] + 8), (a[0] - 6, a[1] + 3)], 'wd_dk', 'wd_dk2', 1)
    x, y = P(u0 + 9, 5, z)
    bottle(s, x, y, 6, 10, LIQ_PINK)
    x, y = P(u0 + 22, 5, z)
    flask_round(s, x, y, 5, LIQ_TEAL, neck=4, nw=2)
    x, y = P(u0 + 34, 5, z)
    bottle(s, x, y, 5, 13, LIQ_AMBER, label='li')
    x, y = P(u0 + 44, 6, z)
    s.rect(x - 3, y - 7, 7, 7, 'gl')
    s.rect(x - 3, y - 4, 7, 4, 'gr')
    s.poly([(x - 3, y), (x + 4, y), (x + 4, y - 7), (x - 3, y - 7)], None, 'ir_dk', 1)
    s.rect(x - 4, y - 9, 9, 2, 'wd_dk')


def draw_broom(s, P):
    """右後牆、窗戶與床之間：靠牆的掃帚（女巫的！）。"""
    base = P(8, 12, 0)
    top = P(1, 24, 118)
    s.line(base, top, 'wd_dk2', 4)
    s.line((base[0], base[1]), (top[0], top[1]), 'wd', 2)
    x, y = base
    pts = [(x - 9, y + 2), (x + 9, y), (x + 6, y - 22), (x + 2, y - 26), (x - 2, y - 25), (x - 6, y - 20)]
    s.poly(pts, 'amber', 'cu_dk', 1)
    for dx in (-5, -2, 1, 4):
        s.line((x + dx, y), (x + dx * 0.4 + 1.5, y - 21), 'cu', 1)
    s.rect(x - 4, y - 24, 9, 3, 'pu')
    s.line((x - 4, y - 22), (x + 5, y - 23), 'pu_dk2', 1)


def draw_doormat(s, P):
    """出口：前方開放邊中間的門墊（玩家知道這裡是門）。"""
    cu, cv = EXIT_UV
    u0, u1, v0, v1 = cu - 30, cu + 30, cv - 20, cv + 22
    s.poly(fz(P, 0, u0, u1, v0, v1), 'le', 'le_dk', 1)
    s.poly(fz(P, 0, u0 + 5, u1 - 5, v0 + 5, v1 - 5), 'le_hi', 'le_dk', 1)
    for k in range(int(u0) + 9, int(u1) - 6, 6):
        s.line(P(k, v0 + 6), P(k, v1 - 6), 'le', 1)
    # 中間一枚月亮
    x, y = P(cu, cv)
    s.ell(x, y, 9, 5, 'go')
    s.ell(x + 3, y - 1, 7.5, 4.2, 'le_hi')
    # 流蘇
    for k in range(int(u0) + 2, int(u1), 4):
        a = P(k, v1)
        s.line(a, (a[0] - 2, a[1] + 1), 'li_dk', 1)
    # 往外的小箭頭（地板上的出口標示）
    ax, ay = P(cu + 46, cv + 44)
    s.poly([(ax - 6, ay - 3), (ax + 4, ay + 2), (ax - 2, ay + 5)], 'go', 'go_dk', 1)


def draw_shell(night=False):
    pal = night_palette() if night else PAL
    s = Svg(CANVAS_W, CANVAS_H, pal, tag='shell%d' % night)
    P = room_px
    rng = random.Random(20261125)
    # ── 牆的外側厚度（前端斷面）與牆頂 ──
    # 左後牆的斷面（v=400 那一端，朝左下）
    s.poly([P(-WALL_T, ROOM_V, -RIM), P(0, ROOM_V, -RIM), P(0, ROOM_V, WALL_H), P(-WALL_T, ROOM_V, WALL_H)], 'st_dk', 'mortar')
    for z in range(-RIM + 20, WALL_H, 22):
        s.line(P(-WALL_T, ROOM_V, z), P(0, ROOM_V, z), 'st_dk2', 1)
    # 右後牆的斷面（u=600 那一端，朝右下）
    s.poly([P(ROOM_U, -WALL_T, -RIM), P(ROOM_U, 0, -RIM), P(ROOM_U, 0, WALL_H), P(ROOM_U, -WALL_T, WALL_H)], 'st_dk2', 'mortar')
    for z in range(-RIM + 14, WALL_H, 22):
        s.line(P(ROOM_U, -WALL_T, z), P(ROOM_U, 0, z), 'mortar', 1)
    # ── 牆面 ──
    stone_wall(s, lambda a, z: P(a, 0, z), ROOM_U, WALL_H, rng, ('st_hi', 'st', 'st_dk', 'st_dk2'))
    stone_wall(s, lambda a, z: P(0, a, z), ROOM_V, WALL_H, rng, ('st', 'st_dk', 'st_dk2', 'mortar'), mortar='st_dk2')
    # 牆角的陰影（左後牆靠角落那一條比較暗）
    s.poly([P(0, 0, 10), P(0, 14, 10), P(0, 14, WALL_H), P(0, 0, WALL_H)], 'st_dk2')
    # 踢腳板
    s.poly([P(0, 0, 0), P(ROOM_U, 0, 0), P(ROOM_U, 0, 10), P(0, 0, 10)], 'wd_dk', 'wd_dk2', 1)
    s.line(P(0, 0, 9), P(ROOM_U, 0, 9), 'wd', 1)
    s.poly([P(0, 0, 0), P(0, ROOM_V, 0), P(0, ROOM_V, 10), P(0, 0, 10)], 'wd_dk2', 'wd_dk2', 1)
    s.line(P(0, 0, 9), P(0, ROOM_V, 9), 'wd_dk', 1)
    # 牆頂石蓋（L 形）
    cap = [P(-WALL_T, -WALL_T, WALL_H), P(ROOM_U, -WALL_T, WALL_H), P(ROOM_U, 0, WALL_H), P(0, 0, WALL_H),
           P(0, ROOM_V, WALL_H), P(-WALL_T, ROOM_V, WALL_H)]
    s.poly(cap, 'st_hi', 'st_dk2', 1)
    for u in range(36, ROOM_U, 44):
        s.line(P(u, -WALL_T, WALL_H), P(u, 0, WALL_H), 'st_dk', 1)
    for v in range(30, ROOM_V, 44):
        s.line(P(-WALL_T, v, WALL_H), P(0, v, WALL_H), 'st_dk', 1)
    s.line(P(0, 0, WALL_H - 1), P(ROOM_U, 0, WALL_H - 1), 'st_dk2', 1)
    s.line(P(0, 0, WALL_H - 1), P(0, ROOM_V, WALL_H - 1), 'mortar', 1)
    # ── 地板 ──
    s.poly(fz(P, 0, 0, ROOM_U, 0, ROOM_V), 'fl')
    floor_planks(s, P, random.Random(31))
    # 窗光：同一組木板、換亮一階的顏色，裁在窗光那塊平行四邊形裡
    if not night:
        patch = [P(u, v) for u, v in LIGHT_PATCH]
        floor_planks(s, P, random.Random(31), colmap={'fl': 'fl_hi', 'fl_hi': 'fl_lit', 'fl_dk': 'fl', 'fl_dk2': 'fl_dk'},
                     clip=patch)
        # 窗櫺的影子（十字）
        mu = (LIGHT_PATCH[0][0] + LIGHT_PATCH[1][0]) / 2
        s.poly([P(mu - 3, 56), P(mu + 3, 56), P(mu + 3 + 38, 150), P(mu - 3 + 38, 150)], 'fl')
        zv = 56 + (150 - 56) * 0.48
        s.poly([P(112 + 0.4 * (zv - 56) - 2, zv - 2), P(196 + 0.4 * (zv - 56), zv - 2),
                P(196 + 0.4 * (zv - 56) + 2, zv + 3), P(112 + 0.4 * (zv - 56), zv + 3)], 'fl')
    # 牆腳的接地暗線
    s.line(P(0, 0, 0), P(ROOM_U, 0, 0), 'fl_dk2', 2)
    s.line(P(0, 0, 0), P(0, ROOM_V, 0), 'fl_dk2', 2)
    # ── 地板前緣的厚度（開放的兩條邊）──
    s.poly([P(0, ROOM_V, 0), P(ROOM_U, ROOM_V, 0), P(ROOM_U, ROOM_V, -RIM), P(0, ROOM_V, -RIM)], 'wd_dk', 'wd_dk2', 1)
    s.line(P(0, ROOM_V, -6), P(ROOM_U, ROOM_V, -6), 'wd_dk2', 1)
    s.line(P(0, ROOM_V, -1), P(ROOM_U, ROOM_V, -1), 'fl_hi', 1)
    s.poly([P(ROOM_U, 0, 0), P(ROOM_U, ROOM_V, 0), P(ROOM_U, ROOM_V, -RIM), P(ROOM_U, 0, -RIM)], 'wd_dk2', 'outline', 1)
    for v in range(25, ROOM_V, 25):
        s.line(P(ROOM_U, v, 0), P(ROOM_U, v, -5), 'outline', 1)
    s.line(P(ROOM_U, 0, -1), P(ROOM_U, ROOM_V, -1), 'fl_dk', 1)
    # 散落的乾藥草屑（魔法陣與煉金台附近）
    rr = random.Random(66)
    for (cu, cv, n_) in ((250, 190, 7), (390, 330, 6), (120, 90, 5), (300, 120, 4)):
        for _ in range(n_):
            x, y = P(cu + rr.uniform(-34, 34), cv + rr.uniform(-26, 26))
            col = rr.choice(('gr_dk', 'amber', 'le_hi', 'gr'))
            s.px(x, y, col, 2, 1)
            if rr.random() < 0.5:
                s.px(x + 1, y - 1, col)
    # ── 牆上的東西 ──
    draw_window(s, P, night)
    draw_window_curtains(s, P)
    draw_herbs(s, P)
    draw_wallshelf_left(s, P)
    draw_starchart(s, P)
    draw_wallshelf(s, P)
    draw_broom(s, P)
    draw_doormat(s, P)
    return s


# ═══════════════════════════════ 平貼地面 ═══════════════════════════════

def draw_rug_circle(s, P, f):
    """魔法陣圓毯：兩圈同心圓、五芒星、一圈符文短線。石灰白配淡金。"""
    c, R = 84, 82
    s.poly(uv_ellipse(P, c, c, R, R, n=72), 'li', 'li_dk', 1)
    s.poly(uv_ellipse(P, c, c, R - 4, R - 4, n=72), None, 'li_dk', 1)
    s.poly(uv_ellipse(P, c, c, R - 16, R - 16, n=72), None, 'go', 2)
    s.poly(uv_ellipse(P, c, c, R - 6, R - 6, n=72), None, 'go', 2)
    # 符文帶：短線與小記號
    rr = random.Random(9)
    n = 30
    for i in range(n):
        t = 2 * math.pi * (i + 0.5) / n
        r0, r1 = R - 13, R - 9
        a = P(c + r0 * math.cos(t), c + r0 * math.sin(t))
        b = P(c + r1 * math.cos(t), c + r1 * math.sin(t))
        kind = rr.randrange(4)
        if kind == 0:
            s.line(a, b, 'st_dk2', 1)
        elif kind == 1:
            s.line(a, b, 'st_dk2', 1)
            s.px((a[0] + b[0]) / 2 + 2, (a[1] + b[1]) / 2, 'st_dk2', 2, 1)
        elif kind == 2:
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            s.px(m[0] - 1, m[1] - 1, 'st_dk2', 3, 1)
            s.px(m[0], m[1] - 1, 'st_dk2', 1, 3)
        else:
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            s.px(m[0] - 1, m[1], 'go_dk', 3, 1)
    # 五芒星
    rs = R - 18
    pts = [P(c + rs * math.cos(math.radians(-90 + 72 * k * 2) + 0.4), c + rs * math.sin(math.radians(-90 + 72 * k * 2) + 0.4)) for k in range(5)]
    for k in range(5):
        s.line(pts[k], pts[(k + 1) % 5], 'go', 2)
    s.poly(uv_ellipse(P, c, c, rs * 0.38, rs * 0.38, n=40), None, 'go_dk', 1)
    # 星角上的小點
    for k in range(5):
        t = math.radians(-90 + 72 * k * 2) + 0.4
        x, y = P(c + (R - 11) * math.cos(t), c + (R - 11) * math.sin(t))
        s.ell(x, y, 2.5, 1.5, 'go_hi', 'go_dk', 1)
    # 磨損的幾塊（顏色深一點）
    for u, v in ((30, 120), (140, 60), (110, 150)):
        x, y = P(u, v)
        s.ell(x, y, 5, 2, 'li_dk')


def draw_rug_star(s, P, f):
    """深藍星星地毯（床邊），兩端有金色流蘇。"""
    du, dv = 66, 112
    s.poly(fz(P, 0, 0, du, 0, dv), 'bl', 'bl_dk2', 1)
    s.poly(fz(P, 0, 4, du - 4, 5, dv - 5), None, 'go', 1)
    s.poly(fz(P, 0, 7, du - 7, 9, dv - 9), 'bl_dk', None)
    s.poly(fz(P, 0, 9, du - 9, 11, dv - 11), 'bl', 'bl_hi', 1)
    rr = random.Random(12)
    for _ in range(11):
        x, y = P(rr.uniform(14, du - 14), rr.uniform(16, dv - 16))
        if rr.random() < 0.45:
            s.poly(star_pts(x, y, 4.2, 1.8), 'go_hi', 'go_dk', 1)
        else:
            tiny_star(s, x, y, 'go')
    # 流蘇（v 的兩端）
    for v in (0, dv):
        for u in range(2, du - 1, 4):
            a = P(u, v)
            d = 3 if v == dv else -3
            s.line(a, (a[0] - d * 0.8, a[1] + d * 0.6), 'go_dk', 1)


# ═══════════════════════════════ 家具 ═══════════════════════════════

def draw_bed(s, P, f):
    du, dv = 84, 120
    shadow(s, P, du / 2 + 2, dv / 2 + 2, du / 2 + 8, dv / 2 + 8)
    # 牆上的背幔（床頭後面）
    top_z = 150
    pts = [P(4, -1, 30), P(80, -1, 30), P(80, -1, top_z), P(4, -1, top_z)]
    s.poly(pts, 'pu_dk', 'pu_dk2', 1)
    for u in range(10, 80, 9):
        s.line(P(u, -1, 32), P(u, -1, top_z - 2), 'pu_dk2', 1)
        s.line(P(u + 3, -1, 34), P(u + 3, -1, top_z - 6), 'pu', 1)
    # 柱子
    def post(u0, v0, ztop=162):
        box(s, P, u0, u0 + 6, v0, v0 + 6, 0, ztop, WOOD, top='wd_hi', left='wd', right='wd_dk')
        for z in (40, 96, 140):
            s.line(P(u0, v0 + 6, z), P(u0 + 6, v0 + 6, z), 'wd_hi', 1)
            s.line(P(u0 + 6, v0, z), P(u0 + 6, v0 + 6, z), 'wd', 1)
    post(0, 0)
    # 床頭板（拱頂）
    n = 18
    arch = [(6 + 72 * i / n, 74 + 16 * math.sin(math.pi * i / n)) for i in range(n + 1)]
    front = [P(6, 6, 22)] + [P(u, 6, z) for u, z in arch] + [P(78, 6, 22)]
    topband = [P(u, 6, z) for u, z in arch] + [P(u, 1, z) for u, z in reversed(arch)]
    s.poly(topband, 'wd_hi', 'wd_dk2', 1)
    s.poly(front, 'wd', 'wd_dk2', 1)
    inner = [P(14, 6, 40)] + [P(14 + 56 * i / n, 70 + 10 * math.sin(math.pi * i / n)) if False else
                              P(14 + 56 * i / n, 6, 66 + 11 * math.sin(math.pi * i / n)) for i in range(n + 1)] + [P(70, 6, 40)]
    s.poly(inner, 'wd_dk', 'wd_dk2', 1)
    s.pline([P(15 + 54 * i / n, 6, 66.5 + 10 * math.sin(math.pi * i / n) - 1.5) for i in range(n + 1)], 'wd_dk2', 1)
    s.line(P(70, 6, 41), P(70, 6, 65), 'wd_hi', 1)
    s.line(P(15, 6, 41), P(69, 6, 41), 'wd_hi', 1)
    # 床頭的金色月亮浮雕
    mx, my = P(42, 6, 60)
    s.ell(mx, my, 8, 8, 'go', 'go_dk', 1)
    s.ell(mx + 4, my - 2.5, 6.5, 6.5, 'wd_dk')
    tiny_star(s, mx + 9, my - 8, 'go_hi')
    post(78, 0)
    # 側邊床框（+u 面）
    box(s, P, 78, 84, 6, 114, 10, 26, WOOD, top='wd_hi', left='wd', right='wd_dk')
    # 床墊
    box(s, P, 6, 78, 5, 114, 24, 38, ('li_hi', 'li', 'li_dk', 'li_dk'), line='li_dk')
    # 枕頭
    def pillow(cu, cv, w, h, z, cols, ztop):
        x, y = P(cu, cv, z)
        s.ell(x, y - ztop * 0.5, w, h, cols[1], cols[3], 1)
        s.ell(x - w * 0.25, y - ztop * 0.5 - h * 0.3, w * 0.55, h * 0.45, cols[0])
        s.line((x - w * 0.6, y - ztop * 0.5 + h * 0.45), (x + w * 0.5, y - ztop * 0.5 + h * 0.55), cols[2], 1)
    pillow(26, 16, 17, 8, 38, ('li_hi', 'li_hi', 'li', 'li_dk'), 8)
    pillow(58, 16, 17, 8, 38, ('li_hi', 'li_hi', 'li', 'li_dk'), 8)
    # 抱枕（方形、四角捏起來）：紫、桃紅、綠
    def cushion(cu, cv, z, w, h, cols, tassel):
        x, y = P(cu, cv, z)
        y -= h
        d = ('M%.2f,%.2f Q%.2f,%.2f %.2f,%.2f Q%.2f,%.2f %.2f,%.2f Q%.2f,%.2f %.2f,%.2f Q%.2f,%.2f %.2f,%.2f Z' % (
            x - w, y - h, x, y - h + 3, x + w, y - h + 1, x + w - 3, y, x + w, y + h, x, y + h - 3, x - w, y + h - 1,
            x - w + 3, y, x - w, y - h))
        s.path(d, cols[1], cols[3], 1)
        s.clip(d=d)
        s.ell(x + w * 0.7, y + h * 0.6, w * 0.9, h * 0.8, cols[2])
        s.ell(x - w * 0.45, y - h * 0.45, w * 0.5, h * 0.35, cols[0])
        s.end()
        s.path(d, None, cols[3], 1)
        s.line((x - 2, y - 2), (x + 1, y + 1), cols[2], 1)
        s.px(x, y, tassel)
        for (dx, dy) in ((-w, -h), (w, -h + 1), (w, h), (-w, h - 1)):
            s.px(x + dx - 1, y + dy - 1, tassel, 2, 2)
    cushion(20, 30, 38, 11, 9, ('pu_hi', 'pu', 'pu_dk', 'pu_dk2'), 'go')
    cushion(63, 30, 38, 11, 9, ('gr_hi', 'gr', 'gr_dk', 'outline'), 'go')
    cushion(42, 33, 37, 10, 8, ('pink', 'pink', 'pink_dk', 'pu_dk2'), 'go_hi')
    # 被子（蓋過床尾與右側往下垂）
    bu0, bu1, bv0, bv1 = 4, 81, 44, 117
    s.poly(fv(P, bv1, bu0, bu1, 14, 42), 'pu_dk', 'pu_dk2', 1)
    s.poly(fu(P, bu1, bv0, bv1, 14, 42), 'pu_dk2', 'outline', 1)
    s.poly(fz(P, 42, bu0, bu1, bv0, bv1), 'pu', 'pu_dk2', 1)
    # 反折的白被單
    s.poly(fz(P, 42.5, bu0, bu1, bv0, bv0 + 8), 'li_hi', 'li_dk', 1)
    s.poly(fu(P, bu1, bv0, bv0 + 8, 34, 42.5), 'li', 'li_dk', 1)
    # 被子上的金邊與摺痕
    s.poly(fz(P, 42, bu0 + 4, bu1 - 4, bv0 + 12, bv1 - 4), None, 'go', 1)
    s.line(P(bu0, bv1, 20), P(bu1, bv1, 20), 'go', 1)
    s.line(P(bu1, bv0, 20), P(bu1, bv1, 20), 'go_dk', 1)
    for (u, v) in ((20, 70), (50, 60), (36, 92), (66, 86), (18, 106), (60, 108), (32, 74)):
        x, y = P(u, v, 42)
        if (u + v) % 3 == 0:
            s.poly(star_pts(x, y, 4, 1.7), 'go_hi', 'go_dk', 1)
        else:
            tiny_star(s, x, y, 'go')
    for (u, v, l) in ((12, 60, 20), (40, 100, 16), (70, 64, 14)):
        s.line(P(u, v, 42), P(u + l * 0.3, v + l, 42), 'pu_hi', 1)
    for u in range(14, 80, 13):
        s.line(P(u, bv1, 18), P(u - 2, bv1, 38), 'pu_dk2', 1)
    for v in range(56, 117, 14):
        s.line(P(bu1, v, 17), P(bu1, v + 2, 38), 'outline', 1)
    # 床尾板
    post(0, 114)
    box(s, P, 6, 78, 114, 119, 10, 54, WOOD, top='wd_hi', left='wd', right='wd_dk')
    s.poly(fv(P, 119, 12, 72, 20, 48), 'wd_dk', 'wd_dk2', 1)
    s.line(P(12, 119, 47), P(72, 119, 47), 'wd_dk2', 1)
    s.line(P(12, 119, 21), P(72, 119, 21), 'wd_hi', 1)
    x, y = P(42, 119, 34)
    s.poly(star_pts(x, y, 5, 2.2), 'go', 'go_dk', 1)
    post(78, 114)
    # 帷幔（綁在柱子上）
    def drape(px_, py_, side, ztop=150, h=124):
        x0, y0 = px_, py_
        tie = 0.48
        w0, wm, w1 = 15, 6, 13
        sgn = side
        pts = [(x0, y0), (x0 + sgn * w0, y0 + 2), (x0 + sgn * wm, y0 + h * tie), (x0 + sgn * w1, y0 + h),
               (x0 + sgn * (w1 - 7), y0 + h + 2), (x0, y0 + h)]
        s.poly(pts, 'pu', 'pu_dk2', 1)
        s.line((x0 + sgn * 4, y0 + 4), (x0 + sgn * 3, y0 + h * tie - 2), 'pu_hi', 1)
        s.line((x0 + sgn * 9, y0 + 4), (x0 + sgn * 5, y0 + h * tie - 2), 'pu_dk', 1)
        s.line((x0 + sgn * 4, y0 + h * tie + 4), (x0 + sgn * 7, y0 + h - 2), 'pu_dk', 1)
        s.line((x0 + sgn * 2, y0 + h * tie + 6), (x0 + sgn * 3, y0 + h - 3), 'pu_hi', 1)
        ty = y0 + h * tie
        s.poly([(x0 - sgn * 1, ty - 2), (x0 + sgn * (wm + 2), ty - 2), (x0 + sgn * (wm + 2), ty + 2), (x0 - sgn * 1, ty + 2)],
               'go', 'go_dk', 1)
        s.px(x0 + sgn * (wm + 3), ty + 2, 'go', 1, 5)
    a = P(0, 120, 148)
    drape(a[0], a[1], -1)
    a = P(84, 120, 148)
    drape(a[0] + 1, a[1] - 1, +1)
    a = P(84, 0, 148)
    drape(a[0] + 1, a[1], +1, h=110)
    # 頂篷
    zc = 164
    box(s, P, -2, 86, -2, 122, zc - 4, zc, WOOD, top='wd_hi', left='wd', right='wd_dk')
    s.poly(fz(P, zc + 1, 0, 84, 0, 120), 'pu_dk', 'pu_dk2', 1)
    for v in range(14, 120, 18):
        s.line(P(2, v, zc + 1), P(82, v + 4, zc + 1), 'pu_dk2', 1)
        s.line(P(4, v + 3, zc + 1), P(80, v + 7, zc + 1), 'pu', 1)
    # 垂飾（波浪下緣＋金邊＋流蘇）
    def valance_v():
        top = [P(-2, 122, zc), P(86, 122, zc)]
        pts = [P(86, 122, zc), P(-2, 122, zc)]
        k = 8
        scal = []
        for i in range(k + 1):
            u = -2 + 88 * i / k
            scal.append(P(u, 122, zc - 20))
            if i < k:
                scal.append(P(u + 88 / k / 2, 122, zc - 14))
        s.poly([P(-2, 122, zc)] + scal + [P(86, 122, zc)], 'pu', 'pu_dk2', 1)
        s.line(P(-2, 122, zc - 4), P(86, 122, zc - 4), 'go', 1)
        for i in range(k + 1):
            x, y = P(-2 + 88 * i / k, 122, zc - 20)
            s.rect(x - 1, y, 2, 3, 'go')
    def valance_u():
        k = 11
        scal = []
        for i in range(k + 1):
            v = -2 + 124 * i / k
            scal.append(P(86, v, zc - 20))
            if i < k:
                scal.append(P(86, v + 124 / k / 2, zc - 14))
        s.poly([P(86, -2, zc)] + scal + [P(86, 122, zc)], 'pu_dk', 'pu_dk2', 1)
        s.line(P(86, -2, zc - 4), P(86, 122, zc - 4), 'go_dk', 1)
        for i in range(k + 1):
            x, y = P(86, -2 + 124 * i / k, zc - 20)
            s.rect(x - 1, y, 2, 3, 'go_dk')
    valance_u()
    valance_v()
    for (u, v) in ((-2, -2), (86, -2), (-2, 122), (86, 122)):
        x, y = P(u, v, zc + 1)
        s.ell(x, y - 3, 3, 3, 'go', 'go_dk', 1)
        s.px(x - 1, y - 5, 'go_hi')


def draw_wardrobe(s, P, f):
    du, dv, H = 36, 80, 146
    shadow(s, P, du / 2 + 2, dv / 2, du / 2 + 8, dv / 2 + 8)
    # 底座與腳
    box(s, P, -2, du + 2, -2, dv + 2, 4, 12, WOOD, top='wd', left='wd_dk', right='wd_dk2', line='outline')
    for v in (2, dv - 4):
        box(s, P, du - 4, du + 2, v, v + 4, 0, 4, WOOD, left='wd_dk', right='wd_dk2', line='outline')
    # 本體：側面（+v，受光）較亮、正面（+u）本色
    s.poly(fv(P, dv, 0, du, 12, H), 'wd_hi', 'wd_dk2', 1)
    s.poly(fu(P, du, 0, dv, 12, H), 'wd', 'wd_dk2', 1)
    for z in range(22, H, 16):
        s.line(P(4, dv, z), P(du - 3, dv, z), 'wd', 1)          # 側板木紋
    s.poly(fv(P, dv, 6, du - 6, 24, H - 12), None, 'wd', 1)
    # 頂飾（簷口）
    box(s, P, -2, du + 3, -3, dv + 3, H, H + 8, WOOD, top='wd_hi', left='wd', right='wd_dk')
    s.line(P(du + 3, -3, H + 2), P(du + 3, dv + 3, H + 2), 'wd_dk2', 1)
    s.line(P(-2, dv + 3, H + 2), P(du + 3, dv + 3, H + 2), 'wd_dk', 1)
    # 弧形雕飾（正面上方）
    n = 20
    cv0, cv1, zb = 8, dv - 8, H + 8
    arc = [P(du + 2, cv0 + (cv1 - cv0) * i / n, zb + 20 * math.sin(math.pi * i / n)) for i in range(n + 1)]
    s.poly([P(du + 2, cv0 - 4, zb)] + arc + [P(du + 2, cv1 + 4, zb)], 'wd', 'wd_dk2', 1)
    arc2 = [P(du + 2, cv0 + 8 + (cv1 - cv0 - 16) * i / n, zb + 2 + 12 * math.sin(math.pi * i / n)) for i in range(n + 1)]
    s.poly(arc2, 'wd_dk', 'wd_dk2', 1)
    # 捲渦兩端
    for v in (cv0 - 2, cv1 + 2):
        x, y = P(du + 2, v, zb + 3)
        s.ell(x, y, 3.5, 3.5, 'wd', 'wd_dk2', 1)
        s.px(x - 1, y - 1, 'wd_hi', 2, 1)
    # 金色月亮＋星的徽記
    mx, my = P(du + 2, dv / 2, zb + 9)
    s.ell(mx, my, 5.5, 5.5, 'go', 'go_dk', 1)
    s.ell(mx + 2.6, my - 1.6, 4.4, 4.4, 'wd_dk')
    tiny_star(s, mx - 7, my - 5, 'go_hi')
    tiny_star(s, mx + 8, my + 1, 'go')
    # 兩扇門
    for (v0, v1) in ((4, dv / 2 - 1), (dv / 2 + 1, dv - 4)):
        s.poly(fu(P, du, v0, v1, 16, H - 6), 'wd', 'wd_dk2', 1)
        # 上嵌板（拱頂）
        m = 14
        a0, a1 = v0 + 5, v1 - 5
        top = [P(du, a0 + (a1 - a0) * i / m, H - 30 + 9 * math.sin(math.pi * i / m)) for i in range(m + 1)]
        s.poly([P(du, a0, 84)] + top + [P(du, a1, 84)], 'wd_dk', 'wd_dk2', 1)
        s.pline([P(du, a0 + 1 + (a1 - a0 - 2) * i / m, H - 31 + 8 * math.sin(math.pi * i / m)) for i in range(m + 1)], 'wd_dk2', 1)
        s.line(P(du, a0 + 1, 85), P(du, a1 - 1, 85), 'wd_hi', 1)
        s.line(P(du, a0, 86), P(du, a0, H - 31), 'wd_hi', 1)
        # 下嵌板
        s.poly(fu(P, du, a0, a1, 24, 74), 'wd_dk', 'wd_dk2', 1)
        s.line(P(du, a0 + 1, 25), P(du, a1 - 1, 25), 'wd_hi', 1)
        s.line(P(du, a0, 25), P(du, a0, 73), 'wd_hi', 1)
        # 嵌板裡的菱形雕花
        x, y = P(du, (a0 + a1) / 2, 49)
        s.poly([(x, y - 7), (x + 4, y), (x, y + 7), (x - 4, y)], 'wd', 'wd_dk2', 1)
        s.px(x - 1, y - 3, 'wd_hi', 1, 3)
        x, y = P(du, (a0 + a1) / 2, H - 50)
        s.poly(star_pts(x, y, 5, 2.2), 'go_dk', 'wd_dk2', 1)
    # 門縫、把手
    s.line(P(du, dv / 2, 16), P(du, dv / 2, H - 6), 'wd_dk2', 1)
    for v in (dv / 2 - 4, dv / 2 + 4):
        x, y = P(du, v, 80)
        s.rect(x - 1, y - 6, 2, 9, 'go')
        s.px(x - 1, y - 6, 'go_hi')
        s.px(x, y + 2, 'go_dk')
    # 門縫露出的一角圍巾（衣櫃！）
    x, y = P(du, dv / 2, 60)
    s.poly([(x - 1, y - 3), (x + 2, y - 2), (x + 5, y + 10), (x + 2, y + 13), (x, y + 6)], 'pink', 'pink_dk', 1)
    s.px(x + 2, y + 2, 'li_hi')
    # 櫃頂的魔女帽
    hx, hy = P(du / 2 - 2, dv / 2 + 10, H + 8)
    s.ell(hx, hy, 16, 6, 'pu_dk', 'pu_dk2', 1)
    s.ell(hx - 2, hy - 1, 12, 4, 'pu_dk2')
    cone = [(hx - 9, hy - 1), (hx + 8, hy - 1), (hx + 6, hy - 14), (hx + 4, hy - 22), (hx + 10, hy - 27), (hx + 12, hy - 25),
            (hx + 7, hy - 21), (hx + 1, hy - 21), (hx - 4, hy - 12)]
    s.poly(cone, 'pu', 'pu_dk2', 1)
    s.line((hx - 5, hy - 4), (hx - 1, hy - 18), 'pu_hi', 1)
    s.poly([(hx - 9, hy - 2), (hx + 8, hy - 2), (hx + 7.5, hy - 6), (hx - 8, hy - 6)], 'go', 'go_dk', 1)
    s.px(hx - 1, hy - 5, 'go_hi', 3, 2)


def draw_bookshelf(s, P, f):
    du, dv, H = 26, 70, 126
    rng = random.Random(4)
    shadow(s, P, du / 2 + 2, dv / 2, du / 2 + 7, dv / 2 + 7)
    # 背板與內部（暗）
    s.poly(fu(P, 2, 4, dv - 4, 4, H - 4), 'wd_dk2', 'outline', 1)
    s.poly(fv(P, 4, 2, du, 4, H - 4), 'wd_dk', 'wd_dk2', 1)        # 右邊側板的內面（朝左下，受一點光）
    shelves = [4, 34, 64, 94]
    spines = [('pink', 'pink_dk'), ('bl', 'bl_dk'), ('gr', 'gr_dk'), ('pu', 'pu_dk'), ('amber', 'cu'), ('wd_hi', 'wd'),
              ('teal_dk', 'bl_dk'), ('li', 'li_dk'), ('le', 'le_dk'), ('bl_hi', 'bl'), ('cu', 'cu_dk'), ('pu_hi', 'pu')]
    for k, zb in enumerate(shelves):
        zt = (shelves[k + 1] if k + 1 < len(shelves) else H - 4) - 4
        gap = zt - zb - 4
        # 層板先畫（書站在它上面；後畫會把書的下半蓋掉）
        box(s, P, 2, du, 2, dv - 2, zb, zb + 4, WOOD, top='wd_hi', left='wd', right='wd_dk')
        v = 6.0
        while v < dv - 7:
            r = rng.random()
            if r < 0.1 and v < dv - 24:
                # 平放的一疊書
                w = 16
                zz = zb + 4
                for j in range(rng.randint(2, 3)):
                    c = spines[rng.randrange(len(spines))]
                    box(s, P, 6, 22, v, v + w, zz, zz + 4, (c[0], c[0], c[1], 'outline'), top='li')
                    zz += 4
                v += w + 2
                continue
            if r < 0.18 and v < dv - 14:
                # 小瓶子
                x, y = P(14, v + 5, zb + 4)
                bottle(s, x, y, 5, 8, (LIQ_TEAL, LIQ_PINK, LIQ_AMBER, LIQ_VIOLET)[rng.randrange(4)], neck=3)
                v += 10
                continue
            if r < 0.24 and v < dv - 14:
                # 卷軸
                for j in range(2):
                    x, y = P(12, v + 4, zb + 8 + j * 6)
                    s.ell(x, y, 3, 3, 'li', 'li_dk', 1)
                    s.line((x + 2, y - 1), (x + 12, y - 6), 'li', 3)
                    s.line((x + 2, y + 1.5), (x + 12, y - 3.5), 'li_dk', 1)
                v += 9
                continue
            w = rng.choice((3, 4, 4, 5, 5, 6, 7))
            h = rng.uniform(gap * 0.62, gap * 0.95)
            c = spines[rng.randrange(len(spines))]
            lean = rng.random() < 0.1
            z0 = zb + 4
            if lean:
                pts = [P(22, v, z0), P(22, v + w, z0), P(22, v + w + 6, z0 + h), P(22, v + 6, z0 + h)]
                s.poly(pts, c[0], 'outline', 1)
                v += w + 7
                continue
            box(s, P, 6, 22, v, v + w, z0, z0 + h, (c[0], c[0], c[1], 'outline'), top='li_dk', left=c[1], right=c[0])
            if rng.random() < 0.55:
                s.line(P(22, v + 0.5, z0 + h - 3), P(22, v + w - 0.5, z0 + h - 3), 'go', 1)
                s.line(P(22, v + 0.5, z0 + 4), P(22, v + w - 0.5, z0 + 4), 'go_dk', 1)
            v += w
    # 頂板
    box(s, P, 0, du + 2, -1, dv + 1, H - 4, H + 2, WOOD, top='wd_hi', left='wd', right='wd_dk')
    s.line(P(du + 2, -1, H - 2), P(du + 2, dv + 1, H - 2), 'wd_dk2', 1)
    # 兩側立板（左＝靠 v 大那邊，看得到它的側面）
    box(s, P, 0, du, dv - 4, dv, 0, H - 4, WOOD, top='wd_hi', left='wd_hi', right='wd')
    box(s, P, 0, du, 0, 4, 0, H - 4, WOOD, top='wd_hi', left='wd', right='wd')
    s.poly(fv(P, dv, 4, du - 4, 8, H - 10), None, 'wd', 1)
    # 頂上：盆栽與卷軸
    x, y = P(12, 14, H + 2)
    cyl(s, P, 12, 14, 5, H + 2, H + 10, ('cu_hi', 'cu', 'cu_dk', 'wd_dk2'), top='wd_dk2')
    x, y = P(12, 14, H + 10)
    for dx, dy, col in ((-4, -4, 'gr'), (4, -5, 'gr_hi'), (0, -9, 'gr'), (-7, 0, 'gr_dk'), (7, 1, 'gr_dk'), (2, -13, 'gr_hi')):
        s.ell(x + dx, y + dy, 3, 2.5, col, 'gr_dk' if col != 'gr_dk' else None, 1)
    for j in range(2):
        x, y = P(10, 44 + j * 7, H + 5)
        s.line((x, y), (x + 14, y + 7), 'li', 5)
        s.line((x, y + 2), (x + 14, y + 9), 'li_dk', 1)
        s.ell(x + 14, y + 7, 2.5, 2.5, 'li_hi', 'li_dk', 1)


def draw_desk(s, P, f):
    du, dv, H = 46, 90, 46
    shadow(s, P, du / 2 + 2, dv / 2, du / 2 + 6, dv / 2 + 6)
    for (u, v) in ((2, 2), (39, 2), (2, 83), (39, 83)):
        box(s, P, u, u + 5, v, v + 5, 0, H - 6, WOOD, top='wd', left='wd', right='wd_dk')
    # 橫撐
    box(s, P, 4, 6, 6, 84, 8, 11, WOOD, left='wd_dk', right='wd_dk2')
    # 牙板＋抽屜
    box(s, P, 2, 44, 2, 88, H - 14, H - 5, WOOD, top='wd', left='wd', right='wd_dk')
    s.poly(fu(P, 44, 30, 60, H - 13, H - 6), 'wd', 'wd_dk2', 1)
    x, y = P(44, 45, H - 9.5)
    s.rect(x - 1, y - 1, 3, 2, 'go')
    # 桌面
    box(s, P, 0, du, 0, dv, H - 5, H, WOOD, top='wd_hi', left='wd', right='wd_dk')
    s.line(P(2, 30, H), P(du - 2, 30, H), 'wd', 1)
    s.line(P(2, 62, H), P(du - 2, 62, H), 'wd', 1)
    # 攤開的書
    bu, bv = 16, 48
    pa = [P(bu, bv, H + 1), P(bu + 22, bv, H + 1), P(bu + 22, bv + 15, H + 3), P(bu, bv + 15, H + 3)]
    pb = [P(bu, bv + 15, H + 3), P(bu + 22, bv + 15, H + 3), P(bu + 22, bv + 30, H + 1), P(bu, bv + 30, H + 1)]
    s.poly([P(bu - 1, bv - 1, H + 0.5), P(bu + 23, bv - 1, H + 0.5), P(bu + 23, bv + 31, H + 0.5), P(bu - 1, bv + 31, H + 0.5)], 'pink_dk', 'outline', 1)
    s.poly(pa, 'li_hi', 'li_dk', 1)
    s.poly(pb, 'li', 'li_dk', 1)
    for k in range(4):
        s.line(P(bu + 4 + k * 4, bv + 3, H + 1.5), P(bu + 4 + k * 4, bv + 12, H + 2.5), 'li_dk', 1)
        s.line(P(bu + 4 + k * 4, bv + 18, H + 2.5), P(bu + 4 + k * 4, bv + 27, H + 1.5), 'li_dk', 1)
    # 墨水瓶＋羽毛筆
    cyl(s, P, 12, 18, 4, H, H + 6, ('bl_hi', 'bl_dk', 'bl_dk2', 'outline'), top='bl_dk2')
    x, y = P(12, 18, H + 6)
    feather = [(x, y), (x + 3, y - 10), (x + 9, y - 22), (x + 12, y - 24), (x + 10, y - 16), (x + 4, y - 6)]
    s.poly(feather, 'li_hi', 'li_dk', 1)
    s.line((x, y), (x + 11, y - 23), 'li_dk', 1)
    # 一疊紙與卷軸
    box(s, P, 26, 40, 8, 26, H, H + 3, ('li_hi', 'li', 'li_dk', 'li_dk'), line='li_dk')
    box(s, P, 27, 41, 9, 27, H + 3, H + 5, ('li_hi', 'li', 'li_dk', 'li_dk'), line='li_dk')
    x, y = P(31, 30, H + 4)
    s.line((x - 9, y - 4), (x + 4, y + 2), 'li', 5)
    s.line((x - 9, y - 2), (x + 4, y + 4), 'li_dk', 1)
    s.ell(x + 4, y + 2, 2.5, 2.5, 'li_hi', 'li_dk', 1)
    # 蠟燭（燭台）
    cyl(s, P, 12, 80, 5, H, H + 2, ('go_hi', 'go', 'go_dk', 'go_dk'), top='go')
    candle(s, P, 12, 80, 2.4, H + 2, 12, f)


def draw_stool(s, P, f):
    shadow(s, P, 12, 12, 13, 13)
    x, y = P(12, 12, 0)
    for (dx, dy, ex, ey) in ((-9, 0, -7, -26), (9, 0, 7, -26), (0, 6, 0, -24)):
        s.line((x + dx, y + dy), (x + ex, y + ey), 'wd_dk2', 3)
        s.line((x + dx, y + dy - 1), (x + ex, y + ey), 'wd_dk', 1)
    cyl(s, P, 12, 12, 10, 26, 30, WOOD, top='wd_hi')
    x, y = P(12, 12, 30)
    s.ell(x - 3, y - 1, 5, 2, 'li_dk')
    s.ell(x - 3, y - 1.5, 4, 1.4, 'wd_hi')


def draw_chest(s, P, f):
    du, dv = 36, 56
    shadow(s, P, du / 2 + 2, dv / 2, du / 2 + 6, dv / 2 + 6)
    # 腳
    for v in (2, dv - 6):
        box(s, P, du - 6, du, v, v + 4, 0, 3, IRON)
    # 箱身：正面（+u）、側面（+v）
    zb, zt = 3, 26
    s.poly(fv(P, dv, 0, du, zb, zt), 'wd', 'wd_dk2', 1)
    s.poly(fu(P, du, 0, dv, zb, zt), 'wd_dk', 'wd_dk2', 1)
    for z in (10, 18):
        s.line(P(1, dv, z), P(du - 1, dv, z), 'wd_dk', 1)
        s.line(P(du, 1, z), P(du, dv - 1, z), 'wd_dk2', 1)
    # 弧形蓋子（沿 v 的半圓柱）
    n = 10
    prof = [(du / 2 - du / 2 * math.cos(math.pi * i / n), zt + 12 * math.sin(math.pi * i / n)) for i in range(n + 1)]
    s.poly([P(u, dv, z) for u, z in prof], 'wd_hi', 'wd_dk2', 1)
    for i in range(n):
        (u0, z0), (u1, z1) = prof[i], prof[i + 1]
        if u1 < u0 + 0.01:
            continue
        nz = (z1 - z0)
        tone = 'wd_hi' if nz > 2 else 'wd' if nz > -2 else 'wd_dk'
        if i < n // 2:
            continue
        s.poly([P(u0, 0, z0), P(u1, 0, z1), P(u1, dv, z1), P(u0, dv, z0)], tone, 'wd_dk2', 1)
    top = [P(u, 0, z) for u, z in prof[:n // 2 + 1]] + [P(u, dv, z) for u, z in reversed(prof[:n // 2 + 1])]
    s.poly(top, 'wd_hi', 'wd_dk2', 1)
    s.pline([P(u, dv, z) for u, z in prof], 'wd_dk2', 1)
    # 鐵條
    for (v0, v1) in ((7, 12), (dv - 12, dv - 7)):
        s.poly(fu(P, du, v0, v1, zb, zt), 'ir', 'ir_dk2', 1)
        for i in range(n // 2, n):
            (u0, z0), (u1, z1) = prof[i], prof[i + 1]
            s.poly([P(u0, v0, z0), P(u1, v0, z1), P(u1, v1, z1), P(u0, v1, z0)], 'ir_hi' if i < n - 2 else 'ir', 'ir_dk2', 1)
        x, y = P(du, (v0 + v1) / 2, zb + 5)
        s.px(x, y, 'ir_hi')
        x, y = P(du, (v0 + v1) / 2, zt - 4)
        s.px(x, y, 'ir_hi')
    s.poly(fv(P, dv, 0, du, zb, zb + 4), 'ir', 'ir_dk2', 1)
    s.poly(fv(P, dv, 0, 4, zb, zt), 'ir', 'ir_dk2', 1)
    s.poly(fv(P, dv, du - 4, du, zb, zt), 'ir_dk', 'ir_dk2', 1)
    # 鎖
    x, y = P(du, dv / 2, zt - 1)
    s.poly([(x - 4, y - 4), (x + 4, y - 0), (x + 4, y + 8), (x - 4, y + 4)], 'go', 'go_dk', 1)
    s.px(x - 1, y + 1, 'outline', 2, 3)
    s.px(x - 3, y - 3, 'go_hi', 2, 1)


def draw_alchemy(s, P, f):
    du, dv, H = 110, 44, 44
    shadow(s, P, du / 2, dv / 2 + 2, du / 2 + 8, dv / 2 + 7)
    for (u, v) in ((3, 3), (101, 3), (3, 36), (101, 36)):
        box(s, P, u, u + 5, v, v + 5, 0, H - 4, WOOD, top='wd', left='wd', right='wd_dk')
    # 下層板與雜物
    box(s, P, 5, 105, 6, 40, 8, 11, WOOD, top='wd', left='wd_dk', right='wd_dk2')
    box(s, P, 14, 40, 12, 36, 11, 27, WOOD, top='wd_hi', left='wd', right='wd_dk')          # 木箱
    s.line(P(14, 36, 19), P(40, 36, 19), 'wd_dk', 1)
    s.line(P(40, 12, 19), P(40, 36, 19), 'wd_dk2', 1)
    x, y = P(60, 30, 11)
    bottle(s, x, y, 8, 12, LIQ_GREEN, label='li')
    x, y = P(74, 28, 11)
    s.ell(x, y - 7, 7, 7, 'cu', 'cu_dk', 1)
    s.ell(x - 2, y - 9, 3, 3, 'cu_hi')
    s.rect(x - 4, y - 16, 8, 3, 'li_dk')
    x, y = P(90, 26, 11)
    bottle(s, x, y, 6, 10, LIQ_VIOLET)
    # 桌面
    box(s, P, 0, du, 0, dv, H - 5, H, WOOD, top='wd_hi', left='wd', right='wd_dk')
    s.line(P(2, 16, H), P(du - 2, 16, H), 'wd', 1)
    s.line(P(2, 30, H), P(du - 2, 30, H), 'wd', 1)
    z = H
    # 小火爐（三腳鐵架＋火）
    bu, bv = 22, 20
    x, y = P(bu, bv, z)
    for dx in (-9, 9):
        s.line((x + dx, y + 2), (x + dx * 0.7, y - 10), 'ir_dk2', 2)
    s.line((x, y + 5), (x, y - 9), 'ir_dk2', 2)
    s.ell(x, y - 10, 10, 4, 'ir', 'ir_dk2', 1)
    flame(s, x, y - 9, 7, 3.5, f)
    # 銅蒸餾器：大銅壺＋壺頸＋頭＋鵝頸管
    px_, py_ = x, y - 26
    s.ell(px_, py_, 14, 12, 'cu', 'cu_dk', 1)
    s.clip(d='M%.2f,%.2f A14,12 0 1 0 %.2f,%.2f A14,12 0 1 0 %.2f,%.2f Z' % (px_ - 14, py_, px_ + 14, py_, px_ - 14, py_))
    s.ell(px_ + 7, py_ + 4, 10, 10, 'cu_dk')
    s.ell(px_ - 5, py_ - 4, 6, 5, 'cu_hi')
    s.end()
    s.ell(px_, py_, 14, 12, None, 'cu_dk', 1)
    s.px(px_ - 7, py_ - 6, 'li_hi', 2, 2)
    s.rect(px_ - 3, py_ - 22, 6, 11, 'cu')
    s.rect(px_ + 1, py_ - 22, 2, 11, 'cu_dk')
    s.rect(px_ - 3, py_ - 22, 1, 11, 'cu_hi')
    s.ell(px_, py_ - 27, 8, 7, 'cu', 'cu_dk', 1)
    s.ell(px_ - 2, py_ - 29, 3, 2.5, 'cu_hi')
    s.ell(px_, py_ - 34, 3, 2, 'cu_dk')
    # 鵝頸管通到接收瓶
    rx_, ry_ = P(64, 24, z)
    tube = [(px_ + 6, py_ - 30), (px_ + 20, py_ - 32), (px_ + 34, py_ - 26), (rx_ - 2, ry_ - 30)]
    s.pline(tube, 'outline', 5)
    s.pline(tube, 'cu', 3)
    s.pline([(a + 0, b - 1) for a, b in tube[:3]], 'cu_hi', 1)
    # 接收瓶（圓底）＋支架
    s.ell(rx_, ry_ - 2, 6, 2.5, 'ir_dk', 'ir_dk2', 1)
    flask_round(s, rx_, ry_ - 3, 9, LIQ_TEAL, neck=9, nw=4, level=0.5)
    # 錐形瓶（桃紅）
    x, y = P(80, 32, z)
    flask_cone(s, x, y, 14, 22, LIQ_PINK)
    # 試管架
    tu, tv = 92, 8
    box(s, P, tu, tu + 14, tv, tv + 8, z, z + 3, WOOD, top='wd', left='wd_dk', right='wd_dk2')
    for k, liq in enumerate(('amber', 'violet', 'teal')):
        x, y = P(tu + 3 + k * 4.5, tv + 4, z + 3)
        test_tube(s, x, y, 14, liq)
    box(s, P, tu, tu + 14, tv, tv + 8, z + 9, z + 11, WOOD, top='wd', left='wd_dk', right='wd_dk2')
    # 研缽
    x, y = P(102, 34, z)
    s.ell(x, y - 4, 6, 4, 'st', 'st_dk2', 1)
    s.ell(x, y - 6, 5, 2, 'st_dk2')
    s.line((x + 1, y - 6), (x + 6, y - 14), 'st_hi', 2)
    # 一張配方紙
    s.poly(fz(P, z + 0.5, 44, 60, 30, 42), 'li_hi', 'li_dk', 1)
    for k in range(3):
        s.line(P(47, 33 + k * 3, z + 1), P(57, 33 + k * 3, z + 1), 'li_dk', 1)


def draw_nightstand(s, P, f):
    du, dv, H = 36, 30, 40
    shadow(s, P, du / 2, dv / 2 + 2, du / 2 + 6, dv / 2 + 6)
    for (u, v) in ((2, 24), (30, 24), (30, 2)):
        box(s, P, u, u + 4, v, v + 4, 0, 6, WOOD, left='wd_dk', right='wd_dk2')
    box(s, P, 0, du, 0, dv, 6, H, WOOD, top='wd_hi', left='wd', right='wd_dk')
    for (z0, z1) in ((10, 22), (24, 36)):
        s.poly(fv(P, dv, 4, du - 4, z0, z1), 'wd_hi', 'wd_dk2', 1)
        s.line(P(5, dv, z1 - 1), P(du - 5, dv, z1 - 1), 'wd', 1)
        x, y = P(du / 2, dv, (z0 + z1) / 2)
        s.ell(x, y, 2, 1.6, 'go', 'go_dk', 1)
    s.poly(fz(P, H, -2, du + 2, -2, dv + 2), 'wd_hi', 'wd_dk2', 1)
    s.poly(fv(P, dv + 2, -2, du + 2, H - 3, H), 'wd', 'wd_dk2', 1)
    s.poly(fu(P, du + 2, -2, dv + 2, H - 3, H), 'wd_dk', 'wd_dk2', 1)
    # 水晶球＋金座
    cu, cv = du / 2 - 2, dv / 2 - 1
    cyl(s, P, cu, cv, 6, H, H + 5, ('go_hi', 'go', 'go_dk', 'go_dk'), top='go')
    x, y = P(cu, cv, H + 5)
    for dx in (-6, 0, 6):
        s.line((x + dx * 0.9, y + 1), (x + dx * 0.55, y - 3), 'go_dk', 2)
    r = 11
    cy = y - r + 2
    s.ell(x, cy, r, r, 'gl', 'bl_dk', 1)
    s.clip(d='M%.2f,%.2f A%.2f,%.2f 0 1 0 %.2f,%.2f A%.2f,%.2f 0 1 0 %.2f,%.2f Z' % (x - r, cy, r, r, x + r, cy, r, r, x - r, cy))
    s.ell(x + 5, cy + 5, 10, 9, 'violet')
    s.ell(x + 7, cy + 7, 7, 6, 'bl_hi')
    s.ell(x - 1, cy + 1, 4, 3, 'pink')
    s.end()
    s.ell(x, cy, r, r, None, 'bl_dk', 1)
    s.px(x - 6, cy - 6, 'gl_hi', 3, 2)
    s.px(x - 7, cy - 4, 'gl_hi', 1, 2)
    tiny_star(s, x + 2, cy - 1, 'gl_hi')
    # 一本小書
    box(s, P, 22, 32, 18, 28, H, H + 3, ('bl', 'bl', 'bl_dk', 'outline'), top='bl')
    s.line(P(22, 28, H + 1.5), P(32, 28, H + 1.5), 'li', 1)


def draw_armchair(s, P, f):
    du, dv = 52, 50
    L = ('le_hi', 'le', 'le_dk', 'outline')
    shadow(s, P, du / 2, dv / 2 + 2, du / 2 + 6, dv / 2 + 6)
    for (u, v) in ((4, 44), (44, 44), (44, 4)):
        box(s, P, u, u + 4, v, v + 4, 0, 5, WOOD, left='wd_dk', right='wd_dk2')
    # 椅背（拱頂）
    n = 16
    arch = [(2 + 48 * i / n, 56 + 10 * math.sin(math.pi * i / n)) for i in range(n + 1)]
    s.poly([P(u, 12, z) for u, z in arch] + [P(u, 2, z) for u, z in reversed(arch)], 'le_hi', 'outline', 1)
    s.poly([P(2, 12, 18)] + [P(u, 12, z) for u, z in arch] + [P(50, 12, 18)], 'le', 'outline', 1)
    s.poly([P(50, 2, 18), P(50, 12, 18)] + [P(50, 12, arch[-1][1]), P(50, 2, arch[-1][1])], 'le_dk', 'outline', 1)
    # 拉扣
    for (u, z) in ((14, 50), (26, 54), (38, 50), (20, 38), (32, 38)):
        x, y = P(u, 12, z)
        s.px(x, y, 'le_dk', 2, 2)
        s.line((x - 3, y - 2), (x, y), 'le_dk', 1)
        s.line((x + 2, y + 2), (x + 5, y + 4), 'le_hi', 1)
    s.line(P(4, 12, 28), P(48, 12, 28), 'le_dk', 1)
    # 左扶手
    def arm(u0):
        box(s, P, u0, u0 + 10, 8, dv, 6, 34, L, top='le_hi')
        x, y = P(u0 + 5, dv, 36)
        s.ell(x, y, 7.5, 6, 'le_hi', 'outline', 1)
        s.ell(x, y, 4, 3, 'le', 'le_dk', 1)
        s.line(P(u0 + 1, dv, 28), P(u0 + 9, dv, 28), 'le_dk', 1)
    arm(0)
    # 座墊
    box(s, P, 8, 44, 12, dv, 6, 20, L, top='le', left='le', right='le_dk')
    box(s, P, 10, 42, 14, dv - 1, 20, 26, L, top='le_hi', left='le', right='le_dk')
    s.line(P(12, dv - 1, 23), P(40, dv - 1, 23), 'le_hi', 1)
    s.line(P(14, 30, 26), P(38, 30, 26), 'le', 1)
    arm(42)
    # 搭在右扶手上的小毯子（紫＋金條紋）
    pts = [P(42, 18, 35), P(52, 18, 35), P(52, 40, 35), P(52, 40, 10), P(52, 30, 8), P(52, 20, 12), P(52, 18, 35)]
    s.poly([P(42, 18, 35), P(52, 18, 35), P(52, 40, 35), P(42, 40, 35)], 'pu', 'pu_dk2', 1)
    s.poly([P(52, 18, 35), P(52, 40, 35), P(52, 40, 9), P(52, 32, 7), P(52, 20, 11)], 'pu_dk', 'pu_dk2', 1)
    for v in (24, 33):
        s.line(P(52, v, 34), P(52, v, 10), 'go_dk', 1)
    for v in range(21, 40, 3):
        a = P(52, v, 9 if v > 30 else 11)
        s.line(a, (a[0], a[1] + 3), 'go', 1)


def draw_fireplace(s, P, f):
    du, dv = 96, 22
    shadow(s, P, du / 2, 24, du / 2 + 6, 18)
    # 煙囪（貼牆往上到天花）
    rr = random.Random(3)
    zh = 138                                   # 爐罩收窄到這個高度，之後直上天花板
    front = [P(6, 14, 106), P(90, 14, 106), P(70, 14, zh), P(70, 14, WALL_H), P(26, 14, WALL_H), P(26, 14, zh)]
    s.poly([P(90, 0, 106), P(90, 14, 106), P(70, 14, zh), P(70, 0, zh)], 'sf_dk', 'sf_dk2', 1)
    s.poly(fu(P, 70, 0, 14, zh, WALL_H), 'sf_dk2', 'outline', 1)
    s.poly(front, 'sf_dk2')
    s.clip(pts=front)
    stone_wall(s, lambda a, z: P(6 + a, 14, z), 84, WALL_H, random.Random(41), FSTONE, mortar='sf_dk2', z0=106,
               widths=(14, 16, 18, 20, 24), heights=(10, 11, 12, 13))
    s.end()
    s.poly(front, None, 'sf_dk2', 1)
    for z in range(zh + 8, WALL_H, 12):
        s.line(P(70, 1, z), P(70, 13, z), 'outline', 1)
    # 爐罩上的黃銅月亮牌
    mx, my = P(48, 14, 150)
    s.ell(mx, my, 8, 8, 'go_dk', 'outline', 1)
    s.ell(mx, my, 6, 6, 'go')
    s.ell(mx + 2.5, my - 1.5, 4.5, 4.5, 'go_dk')
    s.px(mx - 4, my - 3, 'go_hi', 2, 1)
    # 本體
    s.poly(fv(P, dv, 0, du, 0, 100), 'sf', 'sf_dk2', 1)
    s.poly(fu(P, du, 0, dv, 0, 100), 'sf_dk', 'sf_dk2', 1)
    # 石塊紋
    for z in range(6, 100, 14):
        off = 10 if (z // 14) % 2 else 0
        for u in range(off, du, 20):
            pts = [P(u + 1.5, dv, z + 1.5), P(min(du, u + 19) - 1.5, dv, z + 1.5),
                   P(min(du, u + 19) - 1.5, dv, z + 12.5), P(u + 1.5, dv, z + 12.5)]
            tone = rr.choice(('sf', 'sf', 'sf', 'sf_hi', 'sf_dk'))
            s.poly(pts, tone, 'sf_dk2', 1)
            s.line(P(u + 2, dv, z + 11.5), P(min(du, u + 19) - 2, dv, z + 11.5), 'sf_hi' if tone != 'sf_hi' else 'st_hi', 1)
        s.line(P(du, 1, z), P(du, dv - 1, z), 'sf_dk2', 1)
    # 爐口（拱）
    a0, a1, zt = 22, 74, 52
    n = 16
    rad = (a1 - a0) / 2
    arch = [(a0 + rad - rad * math.cos(math.pi * i / n), zt + rad * 0.62 * math.sin(math.pi * i / n)) for i in range(n + 1)]
    outer = [P(a0 - 4, dv, 4)] + [P(a0 + rad - (rad + 4) * math.cos(math.pi * i / n), dv, zt + (rad + 4) * 0.62 * math.sin(math.pi * i / n)) for i in range(n + 1)] + [P(a1 + 4, dv, 4)]
    s.poly(outer, 'sf_hi', 'sf_dk2', 1)
    for i in range(0, n + 1, 2):
        t = math.pi * i / n
        s.line(P(a0 + rad - rad * math.cos(t), dv, zt + rad * 0.62 * math.sin(t)),
               P(a0 + rad - (rad + 4) * math.cos(t), dv, zt + (rad + 4) * 0.62 * math.sin(t)), 'sf_dk', 1)
    hole = [P(a0, dv, 4)] + [P(u, dv, z) for u, z in arch] + [P(a1, dv, 4)]
    s.poly(hole, 'ir_dk2', 'outline', 1)
    s.clip(pts=hole)
    # 內壁（左側的厚度看得到）＋煙燻
    s.poly([P(a0, dv, 4), P(a0, 4, 4), P(a0, 4, 70), P(a0, dv, 70)], 'sf_dk2')
    s.poly([P(a0, 4, 4), P(a1, 4, 4), P(a1, 4, 70), P(a0, 4, 70)], 'ir_dk')
    s.poly([P(a0, 4, 4), P(a1, 4, 4), P(a1, dv, 4), P(a0, dv, 4)], 'sf_dk')
    # 火光映在內壁
    x, y = P((a0 + a1) / 2, 6, 16)
    s.ell(x, y, 22, 10, 'cu_dk')
    s.ell(x, y + 2, 14, 6, 'fire_r')
    s.end()
    # 柴與火
    x, y = P((a0 + a1) / 2, 14, 6)
    s.poly([(x - 18, y + 2), (x + 12, y - 4), (x + 14, y + 1), (x - 16, y + 6)], 'wd_dk', 'outline', 1)
    s.poly([(x - 12, y - 5), (x + 18, y + 2), (x + 16, y + 6), (x - 14, y - 1)], 'wd', 'outline', 1)
    s.ell(x + 16, y + 4, 2.5, 2, 'cu', 'outline', 1)
    s.ell(x - 16, y + 3, 2.5, 2, 'cu', 'outline', 1)
    # 壁爐架（木）
    box(s, P, -4, du + 4, -1, 28, 98, 106, WOOD, top='wd_hi', left='wd', right='wd_dk')
    s.line(P(-4, 28, 101), P(du + 4, 28, 101), 'wd_dk', 1)
    for u in (6, du - 10):
        a = P(u, 28, 98)
        s.poly([a, (a[0] + 4, a[1] + 2), (a[0] + 4, a[1] + 8), (a[0], a[1] + 4)], 'wd_dk', 'wd_dk2', 1)
    # 架上的東西：兩支蠟燭、一瓶藥、一個小時鐘
    candle(s, P, 8, 14, 2.6, 106, 14, f)
    candle(s, P, 86, 14, 2.6, 106, 10, f + 1)
    x, y = P(24, 14, 106)
    bottle(s, x, y, 7, 12, LIQ_TEAL, label='li')
    x, y = P(56, 12, 106)
    s.rect(x - 7, y - 18, 14, 18, 'wd')
    s.poly([(x - 7, y - 18), (x + 7, y - 18), (x + 7, y), (x - 7, y)], None, 'wd_dk2', 1)
    s.ell(x, y - 18, 7, 4, 'wd_hi', 'wd_dk2', 1)
    s.ell(x, y - 10, 5, 5, 'li_hi', 'go_dk', 1)
    s.line((x, y - 10), (x, y - 13), 'outline', 1)
    s.line((x, y - 10), (x + 2, y - 9), 'outline', 1)
    x, y = P(70, 16, 106)
    s.ell(x, y - 5, 5, 5, 'li', 'li_dk', 1)          # 小頭骨（可愛版）
    s.rect(x - 3, y - 2, 6, 3, 'li')
    s.px(x - 3, y - 6, 'outline', 2, 2)
    s.px(x + 1, y - 6, 'outline', 2, 2)
    # 爐前石板
    box(s, P, -6, du + 6, dv, dv + 14, 0, 4, FSTONE, top='sf_hi', left='sf', right='sf_dk')
    for u in range(10, du, 22):
        s.line(P(u, dv, 4), P(u, dv + 14, 4), 'sf', 1)


def fireplace_fire_base(P):
    """壁爐火的落點（跟 draw_fireplace 的柴堆同一處）。"""
    return P((22 + 74) / 2, 14, 6)


def draw_fireplace_fire(s, P, f):
    """壁爐的火（獨立一張、夜晚不壓暗、兩幀）。疊在壁爐那張上面。"""
    x, y = fireplace_fire_base(P)
    sway = (0, 3)[f % 2]
    def tongue(cx, h, w, col, lean):
        s.poly([(cx - w, y), (cx + w, y), (cx + w * 0.4 + lean, y - h * 0.6), (cx + lean * 1.4, y - h),
                (cx - w * 0.5 + lean, y - h * 0.55)], col)
    tongue(x - 8, 22 + sway, 6, 'fire_r', -2)
    tongue(x + 7, 26 - sway, 7, 'fire_r', 2)
    tongue(x - 1, 32 - sway, 8, 'fire_r', 1 - sway)
    tongue(x - 6, 16 + sway, 4.5, 'fire_o', -1)
    tongue(x + 5, 19 - sway, 5, 'fire_o', 1)
    tongue(x, 24 - sway * 1.5, 5.5, 'fire_o', sway - 1)
    tongue(x - 1, 13 + sway, 3.5, 'fire_y', 0)
    tongue(x + 4, 10, 2.5, 'fire_y', 1)
    for (dx, dy) in ((-4, -36), (6, -30), (1, -42)):
        s.px(x + dx + sway, y + dy - sway, 'fire_o')
    s.ell(x, y + 3, 13, 2, 'fire_y')


def draw_firewood(s, P, f):
    du, dv = 32, 58
    shadow(s, P, du / 2, dv / 2, du / 2 + 5, dv / 2 + 5)
    logs = [(6, 6, 6), (16, 6, 6), (26, 6, 6), (11, 6, 16.5), (21, 6, 16.5), (16, 6, 27)]
    rr = random.Random(8)
    for (cu, r, cz) in logs:
        near = [P(cu + r * math.cos(t), dv - 2, cz + r * math.sin(t)) for t in (2 * math.pi * i / 16 for i in range(16))]
        far = [P(cu + r * math.cos(t), 2, cz + r * math.sin(t)) for t in (2 * math.pi * i / 16 for i in range(16))]
        s.poly(hull(near + far), 'wd_dk', 'outline', 1)
        a, b = P(cu - r * 0.3, 4, cz + r * 0.7), P(cu - r * 0.3, dv - 4, cz + r * 0.7)
        s.line(a, b, 'wd', 1)
        a, b = P(cu + r * 0.5, 6, cz - r * 0.2), P(cu + r * 0.5, dv - 10, cz - r * 0.2)
        s.line(a, b, 'wd_dk2', 1)
        s.poly(near, 'li_dk', 'outline', 1)
        x, y = P(cu, dv - 2, cz)
        s.ell(x, y, r * 0.75, r * 0.75, 'li', None)
        s.ell(x, y, r * 0.35, r * 0.35, None, 'le', 1)
        s.px(x - 2, y - 2, 'li_hi')
    # 一把斧頭靠在柴堆旁
    x, y = P(du + 2, dv - 10, 0)
    s.line((x, y), (x + 10, y - 30), 'wd_dk2', 3)
    s.line((x, y - 1), (x + 10, y - 30), 'wd', 1)
    s.poly([(x + 7, y - 30), (x + 15, y - 34), (x + 17, y - 26), (x + 11, y - 24)], 'ir_hi', 'ir_dk2', 1)


def draw_potion_bench(s, P, f):
    du, dv, H = 100, 36, 34
    shadow(s, P, du / 2, dv / 2, du / 2 + 7, dv / 2 + 6)
    for (u, v) in ((3, 3), (92, 3), (3, 28), (92, 28)):
        box(s, P, u, u + 5, v, v + 5, 0, H - 4, WOOD, top='wd', left='wd', right='wd_dk')
    box(s, P, 5, 95, 6, 31, 6, 9, WOOD, top='wd', left='wd_dk', right='wd_dk2')
    # 下層：籃子＋罐子
    x, y = P(30, 20, 9)
    s.poly([(x - 14, y - 12), (x + 14, y - 12), (x + 11, y), (x - 11, y)], 'amber', 'cu_dk', 1)
    for k in range(-10, 12, 4):
        s.line((x + k, y - 11), (x + k * 0.8, y - 1), 'cu', 1)
    s.line((x - 13, y - 7), (x + 13, y - 7), 'cu', 1)
    s.ell(x - 4, y - 14, 4, 2.5, 'gr', 'gr_dk', 1)
    s.ell(x + 4, y - 15, 4, 2.5, 'pink', 'pink_dk', 1)
    x, y = P(66, 22, 9)
    s.ell(x, y - 6, 7, 6, 'li_dk', 'le_dk', 1)
    s.rect(x - 4, y - 14, 8, 3, 'wd')
    box(s, P, 0, du, 0, dv, H - 4, H, WOOD, top='wd_hi', left='wd', right='wd_dk')
    s.line(P(2, 18, H), P(du - 2, 18, H), 'wd', 1)
    z = H
    # 瓶瓶罐罐
    x, y = P(10, 14, z)
    bottle(s, x, y, 8, 20, LIQ_TEAL, neck=6, label='li')
    x, y = P(22, 22, z)
    flask_round(s, x, y, 8, LIQ_PINK, neck=7, nw=3)
    for k, liq in enumerate((LIQ_AMBER, LIQ_VIOLET, LIQ_GREEN)):
        x, y = P(36 + k * 6, 26 - k * 2, z)
        bottle(s, x, y, 5, 9, liq, neck=3)
    box(s, P, 56, 74, 10, 24, z, z + 4, ('bl', 'bl', 'bl_dk', 'outline'), top='li')
    box(s, P, 57, 73, 11, 23, z + 4, z + 8, ('pink_dk', 'pink', 'pink_dk', 'outline'), top='li')
    x, y = P(66, 18, z + 8)
    s.ell(x, y - 6, 5, 5, 'gl', 'ir_dk', 1)
    s.ell(x, y - 4, 4, 3, 'teal')
    s.px(x - 2, y - 9, 'gl_hi', 2, 2)
    x, y = P(84, 26, z)
    flask_cone(s, x, y, 11, 16, LIQ_AMBER)
    x, y = P(90, 10, z)
    s.ell(x, y - 3, 6, 4, 'st', 'st_dk2', 1)
    s.ell(x, y - 5, 5, 2, 'st_dk2')
    s.line((x + 1, y - 5), (x + 7, y - 12), 'wd', 2)
    # 散落的草葉
    for (u, v) in ((46, 10), (50, 14), (78, 30)):
        x, y = P(u, v, z)
        s.px(x, y, 'gr', 3, 1)
        s.px(x + 1, y - 1, 'gr_hi')


def draw_candles(s, P, f):
    shadow(s, P, 11, 11, 12, 12)
    cyl(s, P, 11, 11, 10, 0, 2, ('go_hi', 'go', 'go_dk', 'go_dk'), top='go_dk')
    candle(s, P, 8, 8, 3.2, 2, 26, f)
    candle(s, P, 15, 12, 3.2, 2, 17, f + 1)
    candle(s, P, 7, 16, 2.6, 2, 10, f + 2)
    x, y = P(15, 17, 2)
    s.ell(x, y, 3, 1.5, 'li')


def draw_candle_stand(s, P, f):
    shadow(s, P, 10, 10, 10, 10)
    x, y = P(10, 10, 0)
    for dx in (-7, 7):
        s.line((x, y - 6), (x + dx, y + 1), 'ir_dk2', 2)
    s.line((x, y + 3), (x, y - 6), 'ir_dk2', 2)
    s.rect(x - 1, y - 58, 3, 54, 'ir_dk2')
    s.rect(x - 1, y - 58, 1, 54, 'ir')
    for (dx, h, zz) in ((-11, 10, 50), (11, 12, 50), (0, 14, 60)):
        top = y - zz
        if dx:
            s.pline([(x, y - 44), (x + dx * 0.6, y - 45), (x + dx, top + 3)], 'ir_dk2', 2)
        s.ell(x + dx, top + 3, 4, 1.6, 'ir', 'ir_dk2', 1)
        s.rect(x + dx - 2, top - h + 3, 4, h, 'li')
        s.rect(x + dx + 1, top - h + 3, 1, h, 'li_dk')
        s.rect(x + dx - 2, top - h + 3, 4, 1, 'li_hi')
        s.line((x + dx, top - h + 3), (x + dx, top - h + 1), 'ir_dk2', 1)
        flame(s, x + dx, top - h + 1, 8, 3, f + (dx > 0))
    s.ell(x, y - 44, 3, 1.3, 'ir', 'ir_dk2', 1)


def draw_cauldron(s, P, f):
    c = 32
    shadow(s, P, c, c, 34, 34)
    x, y = P(c, c, 0)
    # 柴與火（鍋底）
    s.poly([(x - 30, y + 1), (x + 18, y - 9), (x + 21, y - 4), (x - 27, y + 6)], 'wd_dk', 'outline', 1)
    s.poly([(x - 20, y - 9), (x + 28, y + 2), (x + 25, y + 7), (x - 23, y - 4)], 'wd', 'outline', 1)
    s.ell(x + 26, y + 5, 2.6, 2, 'cu', 'outline', 1)
    s.ell(x - 28, y + 4, 2.6, 2, 'cu', 'outline', 1)
    rr = random.Random(100 + f)
    ph = f * math.pi / 3
    for k, (dx, base_h, w) in enumerate(((-16, 15, 7), (14, 17, 7), (-4, 22, 9), (6, 19, 7), (-22, 9, 5), (22, 10, 5))):
        h = base_h + 5 * math.sin(ph + k * 1.7)
        lean = 2.5 * math.sin(ph * 1.3 + k)
        s.poly([(x + dx - w, y - 2), (x + dx + w, y - 2), (x + dx + w * 0.5 + lean, y - 2 - h * 0.6),
                (x + dx + lean * 1.5, y - 2 - h), (x + dx - w * 0.55 + lean, y - 2 - h * 0.55)], 'fire_r')
    for k, (dx, base_h, w) in enumerate(((-12, 10, 5), (10, 12, 5), (-1, 15, 6))):
        h = base_h + 4 * math.sin(ph + k * 2.1 + 1)
        lean = 2 * math.sin(ph + k)
        s.poly([(x + dx - w, y - 2), (x + dx + w, y - 2), (x + dx + lean, y - 2 - h)], 'fire_o')
        s.poly([(x + dx - w * 0.5, y - 2), (x + dx + w * 0.5, y - 2), (x + dx + lean * 0.7, y - 2 - h * 0.55)], 'fire_y')
    # 三支腳
    for (dx, dy) in ((-24, -2), (24, -2), (0, 6)):
        s.poly([(x + dx * 0.7 - 2, y - 14), (x + dx * 0.7 + 3, y - 14), (x + dx + 2, y + dy), (x + dx - 3, y + dy)], 'ir_dk', 'outline', 1)
    # 鍋身（扁球）
    bx, by, brx, bry = x, y - 36, 40, 27
    body = 'M%.2f,%.2f A%.2f,%.2f 0 1 0 %.2f,%.2f A%.2f,%.2f 0 1 0 %.2f,%.2f Z' % (
        bx - brx, by, brx, bry, bx + brx, by, brx, bry, bx - brx, by)
    s.path(body, 'ir')
    s.clip(d=body)
    s.ell(bx + 14, by + 10, 36, 26, 'ir_dk')
    s.ell(bx + 24, by + 18, 30, 20, 'ir_dk2')
    s.ell(bx - 18, by - 6, 18, 14, 'ir_hi')
    s.ell(bx - 12, by - 2, 16, 13, 'ir')
    s.end()
    s.path(body, None, 'outline', 1)
    s.line((bx - 30, by - 4), (bx - 27, by + 6), 'gl_hi', 2)
    s.px(bx - 24, by - 12, 'gl_hi', 2, 2)
    # 鍋耳
    for side in (-1, 1):
        hx = bx + side * 38
        s.ell(hx, by - 12, 5, 6, None, 'outline', 3)
        s.ell(hx, by - 12, 5, 6, None, 'ir' if side < 0 else 'ir_dk', 1)
    # 鍋口與藥水
    rx_, ry_ = 34, 12
    ty = by - 21
    s.ell(bx, ty, rx_, ry_, 'ir_hi', 'outline', 1)
    s.ell(bx, ty + 1, rx_ - 4, ry_ - 3, 'ir_dk2')
    s.ell(bx, ty + 2, rx_ - 5, ry_ - 4.5, 'teal_dk')
    liq = 'M%.2f,%.2f A%.2f,%.2f 0 1 0 %.2f,%.2f A%.2f,%.2f 0 1 0 %.2f,%.2f Z' % (
        bx - rx_ + 5, ty + 2, rx_ - 5, ry_ - 4.5, bx + rx_ - 5, ty + 2, rx_ - 5, ry_ - 4.5, bx - rx_ + 5, ty + 2)
    s.clip(d=liq)
    s.ell(bx - 4, ty + 1, rx_ - 10, ry_ - 6, 'teal')
    # 漩渦
    sw = f * 0.6
    s.pline([(bx - 14 + 3 * math.cos(sw), ty + 2), (bx - 4, ty - 1 + math.sin(sw)), (bx + 8, ty + 1), (bx + 16, ty + 3)], 'teal_hi', 1)
    # 泡泡（每幀位置不同）
    bubbles = [(-14, 1, 3), (6, 3, 2.5), (16, 0, 2), (-4, -2, 2), (10, -3, 3)]
    for k, (dx, dy, r) in enumerate(bubbles):
        t = (f + k * 2) % 6
        if t < 4:
            rr_ = r * (0.6 + 0.2 * t)
            s.ell(bx + dx, ty + dy - t * 0.3, rr_, rr_ * 0.7, 'teal_hi', 'teal_dk', 1)
            s.px(bx + dx - rr_ * 0.4, ty + dy - t * 0.3 - rr_ * 0.4, 'gl_hi')
    s.end()
    s.ell(bx, ty, rx_, ry_, None, 'outline', 1)
    s.ell(bx, ty, rx_ - 1.5, ry_ - 1.5, None, 'ir_hi', 1)
    # 冒出的大泡泡與閃光
    t = f % 6
    s.ell(bx + 8 - t, ty - 6 - t * 3, 3 + t * 0.3, 3 + t * 0.3, 'teal', 'teal_dk', 1)
    s.px(bx + 7 - t, ty - 7 - t * 3, 'teal_hi')
    for k in range(3):
        tt = (f + k * 2) % 6
        sx = bx - 16 + k * 16 + 3 * math.sin(tt + k)
        sy = ty - 8 - tt * 4
        if tt < 5:
            tiny_star(s, sx, sy, 'teal_hi' if k % 2 else 'go_hi')


def draw_cat(s, P, f):
    shadow(s, P, 15, 15, 17, 15)
    # 小坐墊
    cyl(s, P, 15, 15, 15, 0, 5, PURP, top='pu')
    x, y = P(15, 15, 5)
    s.ell(x, y, 15 * SQ2 - 3, 15 * SQ2 / 2 - 2, None, 'go', 1)
    for a in range(0, 360, 90):
        t = math.radians(a + 45)
        s.px(x + math.cos(t) * 21, y + math.sin(t) * 10.5 + 1, 'go_hi', 2, 2)
    # 身體（蜷成一團）
    cx, cy = x + 2, y - 7
    s.ell(cx, cy, 15, 8.5, 'cat', 'outline', 1)
    s.ell(cx + 2, cy - 4, 10, 4, 'cat_hi')
    s.ell(cx + 4, cy - 2, 10, 4, 'cat')
    # 尾巴（繞到前面，尾尖每幀擺一點）
    tip = (0, -2, 1)[f % 3]
    s.pline([(cx + 13, cy + 2), (cx + 10, cy + 7), (cx - 2, cy + 8.5), (cx - 12, cy + 6), (cx - 16 + tip, cy + 2 + tip)], 'outline', 5)
    s.pline([(cx + 13, cy + 2), (cx + 10, cy + 7), (cx - 2, cy + 8.5), (cx - 12, cy + 6), (cx - 16 + tip, cy + 2 + tip)], 'cat', 3)
    # 頭（朝左下）
    hx, hy = cx - 11, cy - 3
    s.ell(hx, hy, 7, 6, 'cat', 'outline', 1)
    ear = (0, 0, -2)[f % 3]
    s.poly([(hx - 6, hy - 3), (hx - 6 + ear, hy - 11), (hx - 1, hy - 5)], 'cat', 'outline', 1)
    s.poly([(hx + 1, hy - 5), (hx + 5, hy - 10), (hx + 6, hy - 2)], 'cat', 'outline', 1)
    s.px(hx - 5 + ear * 0.5, hy - 7, 'pink_dk')
    s.px(hx + 4, hy - 7, 'pink_dk')
    # 閉著的眼睛（彎線）與鼻子
    s.px(hx - 4, hy, 'cat_hi', 2, 1)
    s.px(hx + 1, hy, 'cat_hi', 2, 1)
    s.px(hx - 1.5, hy + 2, 'pink')
    s.px(hx - 3, hy - 3, 'cat_hi', 2, 1)
    # 睡覺的 z
    if f == 1:
        s.px(hx + 8, hy - 13, 'li_hi', 3, 1)
        s.px(hx + 10, hy - 14, 'li_hi', 1, 1)
        s.px(hx + 8, hy - 11, 'li_hi', 3, 1)
        s.px(hx + 9, hy - 12, 'li_hi')


def draw_rug_hearth(s, P, f):
    """壁爐前的橢圓編織地毯（貓的地盤）：米色底、辮子邊、中間一圈紫色菱形。"""
    cu, cv, a, b = 60, 40, 58, 38
    s.poly(uv_ellipse(P, cu, cv, a, b, n=64), 'le', 'le_dk', 1)
    for k, col in ((4, 'li_dk'), (8, 'le_hi'), (12, 'li_dk')):
        s.poly(uv_ellipse(P, cu, cv, a - k, b - k, n=64), col)
    s.poly(uv_ellipse(P, cu, cv, a - 2, b - 2, n=64), None, 'le_dk', 1)
    s.poly(uv_ellipse(P, cu, cv, a - 15, b - 15, n=64), 'li', 'li_dk', 1)
    # 辮子紋：外圈上的短斜線
    for i in range(40):
        t = 2 * math.pi * i / 40
        x, y = P(cu + (a - 6) * math.cos(t), cv + (b - 6) * math.sin(t))
        s.line((x - 1, y - 1), (x + 1, y + 1), 'le', 1)
    # 中間的菱形圈
    for i in range(8):
        t = 2 * math.pi * i / 8
        x, y = P(cu + (a - 26) * math.cos(t), cv + (b - 26) * math.sin(t))
        s.poly([(x, y - 3), (x + 5, y), (x, y + 3), (x - 5, y)], 'pu', 'pu_dk2', 1)
    x, y = P(cu, cv)
    s.poly([(x, y - 5), (x + 9, y), (x, y + 5), (x - 9, y)], 'pu_dk', 'pu_dk2', 1)
    s.px(x - 1, y - 1, 'go', 3, 2)
    for (u, v) in ((22, 30), (90, 56)):       # 磨舊的地方
        x, y = P(u, v)
        s.ell(x, y, 5, 2, 'li_dk')


def draw_plant(s, P, f):
    """牆角的大盆栽（龜背芋）。"""
    shadow(s, P, 12, 12, 14, 14)
    cyl(s, P, 12, 12, 9, 0, 16, ('cu_hi', 'cu', 'cu_dk', 'outline'), top='cu')
    x, y = P(12, 12, 16)
    s.ell(x, y, 9 * SQ2 - 2, 9 * SQ2 / 2 - 1, 'wd_dk2')
    leaves = [(-14, -18, 11, 7, -25), (12, -22, 11, 7, 25), (-6, -36, 10, 8, -10), (10, -42, 9, 7, 30), (-16, -44, 8, 6, -40),
              (2, -52, 8, 7, 5), (-2, -24, 9, 6, 0)]
    for (dx, dy, rx, ry, rot) in leaves:
        s.line((x, y - 2), (x + dx * 0.8, y + dy * 0.8), 'gr_dk', 2)
    for k, (dx, dy, rx, ry, rot) in enumerate(leaves):
        cx, cy = x + dx, y + dy
        s.el.append('<g transform="rotate(%g %.2f %.2f)">' % (rot, cx, cy))
        s.ell(cx, cy, rx, ry, 'gr' if k % 2 else 'gr_hi', 'gr_dk', 1)
        s.line((cx - rx + 2, cy), (cx + rx - 2, cy), 'gr_dk', 1)
        s.line((cx - 2, cy - 1), (cx - 4, cy - ry + 2), 'gr_dk', 1)
        s.line((cx + 3, cy + 1), (cx + 5, cy + ry - 2), 'gr_dk', 1)
        s.end()


def draw_wallshelf_left(s, P):
    """左後牆、木箱上方：小掛架，放罐子、頭骨和一本書。"""
    v0, v1, z = 330, 392, 104
    s.poly([P(0, v0, z), P(0, v1, z), P(10, v1, z), P(10, v0, z)], 'wd_hi', 'wd_dk2', 1)
    s.poly(fv(P, v1, 0, 10, z - 4, z), 'wd', 'wd_dk2', 1)
    s.poly(fu(P, 10, v0, v1, z - 4, z), 'wd_dk', 'wd_dk2', 1)
    for v in (v0 + 8, v1 - 8):
        a = P(10, v, z - 4)
        s.poly([a, (a[0] - 5, a[1] - 2), (a[0] - 5, a[1] + 5)], 'wd_dk', 'wd_dk2', 1)
    x, y = P(5, v0 + 8, z)
    s.rect(x - 4, y - 9, 8, 9, 'gl')
    s.rect(x - 4, y - 6, 8, 6, 'amber')
    s.poly([(x - 4, y), (x + 4, y), (x + 4, y - 9), (x - 4, y - 9)], None, 'ir_dk', 1)
    s.rect(x - 5, y - 11, 10, 2, 'le')
    x, y = P(5, v0 + 22, z)
    s.ell(x, y - 5, 5, 5, 'li', 'li_dk', 1)
    s.rect(x - 3, y - 2, 6, 3, 'li')
    s.px(x - 3, y - 6, 'outline', 2, 2)
    s.px(x + 1, y - 6, 'outline', 2, 2)
    x, y = P(5, v0 + 36, z)
    bottle(s, x, y, 6, 12, LIQ_VIOLET, label='li')
    x, y = P(4, v0 + 50, z)
    s.poly([(x - 2, y), (x + 6, y - 4), (x + 6, y - 17), (x - 2, y - 13)], 'gr_dk', 'outline', 1)
    s.poly([(x - 5, y + 1), (x - 2, y), (x - 2, y - 13), (x - 5, y - 12)], 'li', 'outline', 1)
    s.line((x + 1, y - 3), (x + 5, y - 5), 'go', 1)


def draw_window_curtains(s, P):
    """窗戶兩邊的紫色窗簾（綁起來）＋窗簾桿。"""
    zr, tz, zb = 160, 108, WIN_Z0 - 6
    a, b = P(WIN_U0 - 14, 3, zr), P(WIN_U1 + 14, 3, zr)
    s.line(a, b, 'outline', 4)
    s.line(a, b, 'wd_dk', 2)
    for p_ in (a, b):
        s.ell(p_[0], p_[1], 2.5, 2.5, 'go', 'go_dk', 1)
    for side in (-1, 1):
        # 外側那條邊（貼著牆、直直垂下來）、上緣蓋過窗框一點
        if side < 0:
            o, i_ = WIN_U0 - 12, WIN_U0 + 8
        else:
            o, i_ = WIN_U1 + 12, WIN_U1 - 8
        pts = [P(o, 3, zr - 1), P(i_, 3, zr - 1),
               P(i_ - side * 2, 3, zr - 14),
               P(o - side * 7, 3, tz + 4),                 # 往外收到綁帶
               P(o - side * 5, 3, tz),
               P(o - side * 9, 3, zb + 4), P(o - side * 8, 3, zb),
               P(o + side * 1, 3, zb), P(o, 3, tz)]
        s.poly(pts, 'pu', 'pu_dk2', 1)
        # 布摺
        s.line(P(o - side * 3, 3, zr - 3), P(o - side * 3, 3, tz + 6), 'pu_dk', 1)
        s.line(P(o - side * 9, 3, zr - 3), P(o - side * 5, 3, tz + 8), 'pu_hi', 1)
        s.line(P(o - side * 4, 3, tz - 4), P(o - side * 5, 3, zb + 2), 'pu_dk', 1)
        s.line(P(o - side * 1, 3, tz - 6), P(o - side * 1, 3, zb + 2), 'pu_hi', 1)
        # 綁帶
        t0 = P(o + side * 1, 3, tz + 2)
        t1 = P(o - side * 8, 3, tz + 2)
        s.line(t0, t1, 'go_dk', 3)
        s.line(t0, t1, 'go', 1)
        # 上緣的布摺小亮點
        lo, hi = min(o, i_), max(o, i_)
        for k in range(int(lo) + 2, int(hi) - 1, 4):
            s.px(*P(k, 3, zr - 2), 'pu_hi')


# ═══════════════════════════════ 擺設表（位置只在這裡定義）═══════════════════════════════
#
# 每件：名字、畫法、落地範圍在房間 uv 的左上角 (U, V)、大小 (du, dv)、高 h（畫布用）、
#   kind   'stand' 立著（照腳底排序、可遮住女巫）／'flat' 平貼地面（壓在最底）
#   frames 動畫幀數（>1 就輸出 名字-0..N-1）、fps
#   coll   碰撞：'box'（落地範圍內縮 inset 的平行四邊形）、('ellipse', 半徑)（等距圓）、None 不擋
#   tint   夜晚要不要乘夜色（會發光的東西不乘）
#   glows  夜晚的光暈：[(區域 u, v, z, 半徑, 強度)]
# 互動物（Bed / Wardrobe / StorageCabinet / BrewCauldron）的觸發點另外寫在 INTERACT。

EXIT_UV = (548, 368)                  # 出口（回店裡的門）：前方開放邊的中間偏下
SPAWN_UV = (EXIT_UV[0] - 80, EXIT_UV[1] - 80)     # 出生點：出口往房間裡 80px（畫面正上方）

PIECES = [
    dict(name='rug-circle', draw=draw_rug_circle, U=236, V=158, du=168, dv=168, h=4, kind='flat'),
    dict(name='rug-star', draw=draw_rug_star, U=232, V=46, du=66, dv=112, h=4, kind='flat'),
    dict(name='rug-hearth', draw=draw_rug_hearth, U=474, V=42, du=120, dv=80, h=4, kind='flat'),
    dict(name='plant', draw=draw_plant, U=184, V=6, du=24, dv=24, h=80, coll=('ellipse', 9)),
    dict(name='wardrobe', draw=draw_wardrobe, U=0, V=30, du=36, dv=80, h=190, coll='box'),
    dict(name='bookshelf', draw=draw_bookshelf, U=0, V=128, du=26, dv=70, h=150, coll='box'),
    dict(name='desk', draw=draw_desk, U=0, V=222, du=46, dv=90, h=80, coll='box', glows=[(12, 80, 64, 46, 0.8)]),
    dict(name='stool', draw=draw_stool, U=58, V=256, du=24, dv=24, h=36, coll=('ellipse', 10)),
    dict(name='chest', draw=draw_chest, U=26, V=330, du=36, dv=56, h=44, coll='box'),
    dict(name='alchemy-table', draw=draw_alchemy, U=68, V=0, du=110, dv=44, h=120, coll='box',
         glows=[(22, 20, 50, 40, 0.8)]),
    dict(name='nightstand', draw=draw_nightstand, U=262, V=0, du=36, dv=30, h=76, coll='box',
         glows=[(16, 14, 66, 40, 0.65)]),
    dict(name='bed', draw=draw_bed, U=306, V=0, du=84, dv=120, h=180, coll='box'),
    dict(name='fireplace', draw=draw_fireplace, U=470, V=0, du=96, dv=36, h=180, coll='box',
         glows=[(48, 24, 22, 96, 1.0), (8, 14, 124, 30, 0.6), (86, 14, 120, 30, 0.6)]),
    dict(name='fireplace-fire', draw=draw_fireplace_fire, U=470, V=0, du=96, dv=36, h=180, frames=2, fps=4,
         tint=False, outline=False, overlay='fireplace'),
    dict(name='armchair', draw=draw_armchair, U=540, V=60, du=52, dv=50, h=80, coll='box'),
    dict(name='cat', draw=draw_cat, U=490, V=50, du=30, dv=30, h=30, frames=3, fps=1.5, seq=(0, 0, 0, 1, 1, 0, 0, 2, 0)),
    dict(name='firewood', draw=draw_firewood, U=566, V=166, du=32, dv=58, h=44, coll='box'),
    dict(name='potion-bench', draw=draw_potion_bench, U=150, V=352, du=100, dv=36, h=70, coll='box'),
    dict(name='candles', draw=draw_candles, U=40, V=112, du=22, dv=22, h=40, coll=('ellipse', 6), tint=False,
         glows=[(11, 11, 22, 40, 0.85)]),
    dict(name='candles', draw=draw_candles, U=402, V=8, du=22, dv=22, h=40, coll=('ellipse', 6), tint=False,
         glows=[(11, 11, 22, 40, 0.85)], inst='candles-bed'),
    dict(name='candles', draw=draw_candles, U=262, V=362, du=22, dv=22, h=40, coll=('ellipse', 6), tint=False,
         glows=[(11, 11, 22, 40, 0.85)], inst='candles-bench'),
    dict(name='candle-stand', draw=draw_candle_stand, U=12, V=372, du=20, dv=20, h=80, coll=('ellipse', 6), tint=False,
         glows=[(10, 10, 66, 52, 0.9)]),
    dict(name='candle-stand', draw=draw_candle_stand, U=572, V=242, du=20, dv=20, h=80, coll=('ellipse', 6), tint=False,
         glows=[(10, 10, 66, 52, 0.9)], inst='candle-stand-right'),
    dict(name='cauldron', draw=draw_cauldron, U=288, V=210, du=64, dv=64, h=110, frames=6, fps=0, coll=('ellipse', 30),
         glows=[(32, 32, 10, 60, 0.85)]),
]

# 互動點：名字、uv、互動距離（像素，世界座標的直線距離 —— 跟 InteractPoint 的判定一樣）
INTERACT = {
    'bed': dict(uv=(348, 64), range=118.0, label='床（按 E 睡覺）'),
    'wardrobe': dict(uv=(56, 64), range=100.0, label='衣櫃（按 E 換衣服）'),
    'chest': dict(uv=(84, 358), range=110.0, label='倉庫木箱（按 E 開倉庫）'),
    'cauldron': dict(uv=(320, 242), range=100.0, label='鍋爐（按 E 調配藥水）'),
}
DOOR_AUTO = 70.0          # SceneDoor：走進這個距離就回店裡
DOOR_RANGE = 90.0         # SceneDoor：這個距離內顯示提示、可以按 E

# 地板可走範圍：地板菱形往內縮（後牆那兩邊縮一點點讓腳貼得到牆、前方開放邊縮多一點腳才不會踩出去）
WALK_INSET_BACK = 8.0
WALK_INSET_FRONT = 14.0
PLAYER_RADIUS = 11.0      # 跟戶外一樣（gen_footprints.PLAYER_RADIUS）
BOX_INSET = 2.0           # 家具落地範圍往內縮一點（腳可以稍微踩到家具的腳邊）

NIGHT_TINT = NIGHT_MUL    # 家具夜晚乘的顏色（跟房間殼夜晚版同一組）
GLOW_COLOR = (255, 196, 120)
GLOW_ALPHA = 0.6          # 光暈最亮處的不透明度（再乘每個光暈自己的強度）


# ═══════════════════════════════ 渲染（SVG → 無頭 Chrome → 後處理）═══════════════════════════════

def find_chrome():
    cands = [os.environ.get('CHROME', ''),
             r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
             r'C:\Program Files\Google\Chrome\Application\chrome.exe',
             r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
             r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise SystemExit('找不到 Chrome／Edge（可用環境變數 CHROME 指定）')


def render_sheet(svgs):
    """把一串 Svg 排在一張 HTML 上，無頭 Chrome 截一次圖，切回每一張的 RGBA 陣列。"""
    W = 2600
    x = y = rowh = 0
    for s in svgs:
        if x + s.w > W:
            x, y, rowh = 0, y + rowh + 6, 0
        s._at = (x, y)
        x += s.w + 6
        rowh = max(rowh, s.h)
    H = y + rowh
    html = ('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;'
            'background:transparent;overflow:hidden}</style></head><body>' +
            ''.join(s.markup(standalone=False) for s in svgs) + '</body></html>')
    tmp = tempfile.mkdtemp(prefix='brewroom-')
    try:
        hp = os.path.join(tmp, 'sheet.html')
        pp = os.path.join(tmp, 'sheet.png')
        with open(hp, 'w', encoding='utf-8') as fh:
            fh.write(html)
        cmd = [find_chrome(), '--headless=new', '--screenshot=' + pp, '--window-size=%d,%d' % (W, H),
               '--default-background-color=00000000', '--force-device-scale-factor=1', '--hide-scrollbars',
               '--disable-gpu', 'file:///' + hp.replace('\\', '/')]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=170)
        sheet = np.asarray(Image.open(pp).convert('RGBA'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if sheet.shape[0] < H or sheet.shape[1] < W:
        raise SystemExit('截圖尺寸不對：%s（預期 %dx%d）' % (sheet.shape, W, H))
    return [sheet[s._at[1]:s._at[1] + s.h, s._at[0]:s._at[0] + s.w].copy() for s in svgs]


def palette_array(pal):
    keys = sorted(pal)
    return np.array([hex_rgb(pal[k]) for k in keys], dtype=np.int32)


def postprocess(a, pal, outline=True):
    """alpha 二值化、陰影鍵色換成半透明、顏色貼齊色盤、補 1px 外輪廓。"""
    rgb = a[..., :3].astype(np.int32)
    solid = a[..., 3] >= 128
    sk = np.array(hex_rgb(SHADOW_KEY))
    is_sh = solid & (np.abs(rgb - sk).sum(-1) < 60)
    obj = solid & ~is_sh
    parr = palette_array(pal)
    flat = rgb[obj]
    if len(flat):
        d = ((flat[:, None, :] - parr[None, :, :]) ** 2).sum(-1)
        rgb[obj] = parr[d.argmin(1)]
    out = np.zeros(a.shape, dtype=np.uint8)
    out[obj, :3] = rgb[obj]
    out[obj, 3] = 255
    out[is_sh] = SHADOW_RGBA
    if outline:
        nb = np.zeros_like(obj)
        nb[1:, :] |= obj[:-1, :]
        nb[:-1, :] |= obj[1:, :]
        nb[:, 1:] |= obj[:, :-1]
        nb[:, :-1] |= obj[:, 1:]
        ring = nb & ~obj
        out[ring, :3] = OUTLINE_RGB
        out[ring, 3] = 255
    return out


def crop_box(a):
    ys, xs = np.nonzero(a[..., 3] > 0)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


GLOW_PX = 128


def glow_image(size=GLOW_PX):
    """柔和的暖色光暈（唯一允許漸層的一張）。白色＋alpha，顏色由遊戲裡的 SpriteRenderer.color 給。"""
    r = (np.arange(size) - (size - 1) / 2) / (size / 2)
    X, Y = np.meshgrid(r, r)
    d = np.clip(np.hypot(X, Y), 0, 1)
    a = (1 - d) ** 2 * (1 - d * 0.15)
    a = np.clip(a, 0, 1)
    img = np.zeros((size, size, 4), np.uint8)
    img[..., :3] = 255
    img[..., 3] = (a * 255).round().astype(np.uint8)
    return img


# ═══════════════════════════════ 組裝 ═══════════════════════════════

MARGIN = 26


def piece_canvas(pc, frame):
    du, dv, h = pc['du'], pc['dv'], pc['h']
    ox = dv + MARGIN
    oy = h + MARGIN
    w = du + dv + 2 * MARGIN
    hh = h + (du + dv) / 2 + 2 * MARGIN
    s = Svg(w, hh, PAL, tag=pc['name'].replace('-', '') + str(frame))
    pc['draw'](s, Iso(ox, oy), frame)
    return s, (ox, oy)


def art_names(pc):
    n = pc.get('frames', 1)
    return [pc['name']] if n == 1 else ['%s-%d' % (pc['name'], i) for i in range(n)]


def build_art():
    """畫全部、轉 PNG。回傳 {圖名: (RGBA 陣列, 原點在裁切後圖上的位置)}。"""
    jobs = []
    shell_day = draw_shell(False)
    shell_night = draw_shell(True)
    jobs.append(('shell-day', shell_day, None, PAL, True))
    jobs.append(('shell-night', shell_night, None, night_palette(), True))
    seen = set()
    for pc in PIECES:
        for i, nm in enumerate(art_names(pc)):
            if nm in seen:
                continue
            seen.add(nm)
            s, origin = piece_canvas(pc, i)
            jobs.append((nm, s, origin, PAL, pc.get('outline', True)))
    imgs = render_sheet([j[1] for j in jobs])
    arts = {}
    for (nm, s, origin, pal, ol), a in zip(jobs, imgs):
        p = postprocess(a, pal, outline=ol)
        if origin is None:                 # 房間殼：保持 1082×717 不裁
            arts[nm] = (p, (0, 0), s)
            continue
        x0, y0, x1, y1 = crop_box(p)
        arts[nm] = (p[y0:y1, x0:x1], (origin[0] - x0, origin[1] - y0), s)
    # 動畫：同一組幀裁成一樣大（取聯集），樞紐才不會跳
    for pc in PIECES:
        names = art_names(pc)
        if len(names) < 2 or names[0] not in arts:
            continue
        boxes = []
        for nm in names:
            p, (ox, oy), s = arts[nm]
            boxes.append((-ox, -oy, p.shape[1] - ox, p.shape[0] - oy))
        X0 = min(b[0] for b in boxes)
        Y0 = min(b[1] for b in boxes)
        X1 = max(b[2] for b in boxes)
        Y1 = max(b[3] for b in boxes)
        for nm in names:
            p, (ox, oy), s = arts[nm]
            q = np.zeros((Y1 - Y0, X1 - X0, 4), np.uint8)
            q[-oy - Y0:-oy - Y0 + p.shape[0], -ox - X0:-ox - X0 + p.shape[1]] = p
            arts[nm] = (q, (-X0, -Y0), s)
    return arts


# ═══════════════════════════════ 配置資料（C# 與離線檢查共用）═══════════════════════════════

def floor_poly_uv():
    return [(0, 0), (ROOM_U, 0), (ROOM_U, ROOM_V), (0, ROOM_V)]


def walk_poly_world():
    """可走多邊形（世界座標、順時針）：地板菱形各邊往內縮。"""
    # 在畫面上縮：uv 的菱形 → 世界座標的菱形，每條邊往內平移 inset（法線方向）
    T = uv_to_world(0, 0)
    R = uv_to_world(ROOM_U, 0)
    B = uv_to_world(ROOM_U, ROOM_V)
    L = uv_to_world(0, ROOM_V)
    poly = [T, R, B, L]                       # 世界座標（y 朝上）：上→右→下→左 ＝ 順時針
    insets = [WALK_INSET_BACK, WALK_INSET_FRONT, WALK_INSET_FRONT, WALK_INSET_BACK]   # 邊 TR、RB、BL、LT
    lines = []
    n = len(poly)
    for i in range(n):
        a, b = np.array(poly[i]), np.array(poly[(i + 1) % n])
        d = b - a
        nrm = np.array([d[1], -d[0]]) / np.hypot(*d)   # 順時針（y 朝上）→ 內側在右手邊：(dy, -dx)
        # 內側法線要指向中心
        c = np.mean(np.array(poly), axis=0)
        if np.dot(c - a, nrm) < 0:
            nrm = -nrm
        lines.append((a + nrm * insets[i], d))
    out = []
    for i in range(n):
        p1, d1 = lines[i - 1]
        p2, d2 = lines[i]
        A = np.array([d1, -d2]).T
        t = np.linalg.solve(A, p2 - p1)
        out.append(tuple(p1 + d1 * t[0]))
    return [(round(float(x), 2), round(float(y), 2)) for x, y in out]


def piece_world(pc, art):
    """一件家具的世界資料：落腳點（落地範圍中心）、樞紐、圖的世界矩形。"""
    U, V, du, dv = pc['U'], pc['V'], pc['du'], pc['dv']
    p, (ox, oy) = art[0], art[1]
    h, w = p.shape[0], p.shape[1]
    # 區域原點 (0,0,0) 在房間圖上的像素（取整，跟殼的像素格對齊）
    rx, ry = room_px(U, V)
    rx, ry = round(rx), round(ry)
    left, top = rx - ox, ry - oy                     # 圖的左上角在房間圖上的位置
    cu, cv = U + du / 2, V + dv / 2
    ax, ay = room_px(cu, cv)
    ax, ay = rx + (ax - room_px(U, V)[0]), ry + (ay - room_px(U, V)[1])
    wx, wy = px_to_world(ax, ay)
    pivot = (ax - left, top + h - ay)                # 樞紐（像素，從圖的左下角量；Unity 的 Sprite 座標）
    x0, y1 = px_to_world(left, top)
    x1, y0 = px_to_world(left + w, top + h)
    return dict(x=wx, y=wy, pivot=pivot, left=left, top=top, w=w, h=h, rect=(x0, y0, x1, y1))


def piece_shape(pc):
    """碰撞形狀（世界座標）。"""
    c = pc.get('coll')
    if c is None:
        return None
    U, V, du, dv = pc['U'], pc['V'], pc['du'], pc['dv']
    if c == 'box':
        i = BOX_INSET
        pts = [uv_to_world(U + i, V + i), uv_to_world(U + du - i, V + i),
               uv_to_world(U + du - i, V + dv - i), uv_to_world(U + i, V + dv - i)]
        return dict(shape='poly', pts=[(round(x, 2), round(y, 2)) for x, y in pts], name=pc.get('inst', pc['name']))
    kind, r = c
    cx, cy = uv_to_world(U + du / 2, V + dv / 2)
    return dict(shape='ellipse', cx=round(cx, 2), cy=round(cy, 2), hx=round(r * SQ2, 2), hy=round(r * SQ2 / 2, 2),
                name=pc.get('inst', pc['name']))


def iso_front(a, b):
    """a 是否在 b 前面（兩個 uv 盒子，畫面上重疊時才有意義）。"""
    if a['U'] >= b['U'] + b['du'] - 0.01 or a['V'] >= b['V'] + b['dv'] - 0.01:
        return True
    if b['U'] >= a['U'] + a['du'] - 0.01 or b['V'] >= a['V'] + a['dv'] - 0.01:
        return False
    return (a['U'] + a['du'] / 2 + a['V'] + a['dv'] / 2) > (b['U'] + b['du'] / 2 + b['V'] + b['dv'] / 2)


def rect_overlap(r1, r2):
    return r1[0] < r2[2] and r2[0] < r1[2] and r1[1] < r2[3] and r2[1] < r1[3]


ORDER_BASE = -3000
ORDER_STEP = 20
FLAT_ORDER = -9500


def assign_orders(pieces):
    """立著的物件：畫面上重疊的兩件用等距盒子的前後關係排（拓樸排序），其餘照落地範圍前角的 y。"""
    st = [p for p in pieces if p['kind'] == 'stand' and not p.get('overlay')]
    n = len(st)
    after = {i: set() for i in range(n)}          # i 要畫在 after[i] 這些之後
    for i in range(n):
        for j in range(n):
            if i != j and rect_overlap(st[i]['world']['rect'], st[j]['world']['rect']) and iso_front(st[i], st[j]):
                after[i].add(j)
    key = lambda i: (st[i]['U'] + st[i]['du'] + st[i]['V'] + st[i]['dv'], st[i]['U'] + st[i]['du'])  # noqa: E731
    done, order = set(), []
    while len(order) < n:
        ready = [i for i in range(n) if i not in done and after[i] <= done]
        if not ready:      # 有環（不該發生）：退回前角排序
            ready = [min((i for i in range(n) if i not in done), key=key)]
        i = min(ready, key=key)
        done.add(i)
        order.append(i)
    for rank, i in enumerate(order):
        st[i]['order'] = ORDER_BASE + rank * ORDER_STEP
    flats = [p for p in pieces if p['kind'] == 'flat']
    for k, p in enumerate(flats):
        p['order'] = FLAT_ORDER + k
    for p in pieces:
        if p.get('overlay'):          # 疊在某件家具上的（壁爐的火）：排在它正上方一格
            p['order'] = next(q['order'] for q in pieces if q['name'] == p['overlay']) + 1


def interact_world():
    pts = []
    for k, d in INTERACT.items():
        x, y = uv_to_world(*d['uv'])
        pts.append(dict(name=k, label=d['label'], x=round(x, 2), y=round(y, 2), range=d['range']))
    x, y = uv_to_world(*EXIT_UV)
    pts.append(dict(name='exit', label='出口（回店裡）', x=round(x, 2), y=round(y, 2), range=DOOR_RANGE, auto=DOOR_AUTO))
    return pts


def room_data(arts=None):
    """房間的全部配置（世界座標）。arts＝None 時只算碰撞與互動點（給離線檢查用，不畫圖）。"""
    pieces = []
    for pc in PIECES:
        q = dict(pc)
        q.setdefault('kind', 'stand')
        q.setdefault('frames', 1)
        q.setdefault('fps', 0)
        q.setdefault('tint', True)
        q.setdefault('glows', [])
        q.setdefault('seq', ())
        q['art'] = art_names(pc)
        q['shape'] = piece_shape(pc)
        if arts is not None:
            q['world'] = piece_world(pc, arts[q['art'][0]])
        pieces.append(q)
    if arts is not None:
        assign_orders(pieces)
    glows = []
    for q in pieces:
        for (u, v, z, r, k) in q['glows']:
            x, y = room_px(q['U'] + u, q['V'] + v, z)
            wx, wy = px_to_world(x, y)
            glows.append(dict(x=round(wx, 2), y=round(wy, 2), r=r, k=k, flicker=q['name'] != 'nightstand'))
    sx, sy = uv_to_world(*SPAWN_UV)
    tx, ty = uv_to_world(0, 0)
    return dict(pieces=pieces, glows=glows, walk=walk_poly_world(), spawn=(round(sx, 2), round(sy, 2)),
                points=interact_world(), shapes=[q['shape'] for q in pieces if q['shape']],
                iso=(round(tx, 2), round(ty, 2)), radius=PLAYER_RADIUS)


# ═══════════════════════════════ 幾何（跟 Obstacles.cs 同一套算法）═══════════════════════════════

def poly_signed_dist(pts, px, py):
    """點到凸多邊形的有號距離（外面為正、裡面為負）。numpy 陣列也可以。"""
    n = len(pts)
    px = np.asarray(px, dtype=float)
    py = np.asarray(py, dtype=float)
    inside = np.ones(px.shape, bool)
    best = np.full(px.shape, np.inf)
    # 方向：計算面積符號
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0          # >0：逆時針
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0, 1)
        qx, qy = ax + t * dx - px, ay + t * dy - py
        best = np.minimum(best, np.hypot(qx, qy))
        cross = dx * (py - ay) - dy * (px - ax)
        inside &= (cross * sgn) >= 0
    return np.where(inside, -best, best)


def penetration(s, px, py, r=PLAYER_RADIUS):
    """腳底圓心在 p 時插進形狀多深（<=0 沒碰到）。跟 Obstacles.Pen 同一個算法。"""
    if s['shape'] == 'ellipse':
        rx, ry = s['hx'] + r, s['hy'] + r
        d = np.hypot((np.asarray(px) - s['cx']) / rx, (np.asarray(py) - s['cy']) / ry)
        return (1 - d) * min(rx, ry)
    return r - poly_signed_dist(s['pts'], px, py)


def in_walk(walk, px, py):
    return poly_signed_dist(walk, px, py) <= 0


def flood(data, step=16.0):
    walk = data['walk']
    xs_ = [p[0] for p in walk]
    ys_ = [p[1] for p in walk]
    x0, x1, y0, y1 = min(xs_), max(xs_), min(ys_), max(ys_)
    nx = int((x1 - x0) // step) + 1
    ny = int((y1 - y0) // step) + 1
    X, Y = np.meshgrid(x0 + np.arange(nx) * step, y0 + np.arange(ny) * step)
    free = in_walk(walk, X, Y)
    for s in data['shapes']:
        free &= penetration(s, X, Y) <= 0
    sx, sy = data['spawn']
    d = np.hypot(X - sx, Y - sy) + np.where(free, 0, 1e9)
    start = np.unravel_index(np.argmin(d), d.shape)
    reach = np.zeros_like(free)
    stack = [start]
    reach[start] = True
    while stack:
        j, i = stack.pop()
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = j + dj, i + di
            if 0 <= a < ny and 0 <= b < nx and free[a, b] and not reach[a, b]:
                reach[a, b] = True
                stack.append((a, b))
    spawn_bad = (not in_walk(walk, sx, sy)) or any(penetration(s, sx, sy) > 0 for s in data['shapes'])
    return dict(X=X, Y=Y, free=free, reach=reach, bounds=(x0, y0, x1, y1), spawn_bad=bool(spawn_bad))


def check_room(data, verbose=True):
    """可達性（16px，跟 Obstacles.SelfCheck 一樣）＋互動點兩兩之間的距離與「同時在兩個範圍內」的可走位置（4px）。"""
    fl = flood(data, 16.0)
    lines = []
    bad = []
    for p in data['points']:
        d = np.hypot(fl['X'] - p['x'], fl['Y'] - p['y'])
        ok = bool(np.any(fl['reach'] & (d <= p['range'])))
        p['ok'] = ok
        if not ok:
            bad.append('%s (%.0f, %.0f) 範圍 %.0f' % (p['label'], p['x'], p['y'], p['range']))
        if 'auto' in p:
            ok2 = bool(np.any(fl['reach'] & (d <= p['auto'])))
            p['ok_auto'] = ok2
            if ok and not ok2:
                bad.append('%s 只能按 E，走不到自動觸發的 %.0f 內' % (p['label'], p['auto']))
    walkable = fl['reach'].sum() / max(1, in_walk(data['walk'], fl['X'], fl['Y']).sum())
    lines.append('[Obstacles] brew：障礙 %d 個；可走面積 %.1f%%（地板多邊形內、從出生點走得到的格子）；出生點 (%.0f, %.0f)%s' % (
        len(data['shapes']), walkable * 100, data['spawn'][0], data['spawn'][1], '（⚠️ 在障礙裡或地板外）' if fl['spawn_bad'] else ''))
    lines.append('    走不到的互動點：' + ('無' if not bad else ''))
    lines += ['      - ' + b for b in bad]
    # 兩兩檢查（4px 細格，只算走得到的位置）
    fine = flood(data, 4.0)
    pts = data['points']
    lines.append('    互動點兩兩距離（同時在兩個範圍內、走得到的位置）：')
    pair_bad = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            a, b = pts[i], pts[j]
            dist = math.hypot(a['x'] - b['x'], a['y'] - b['y'])
            both = fine['reach'] & (np.hypot(fine['X'] - a['x'], fine['Y'] - a['y']) <= a['range']) & \
                   (np.hypot(fine['X'] - b['x'], fine['Y'] - b['y']) <= b['range'])
            nboth = int(both.sum())
            lines.append('      %-8s ↔ %-8s 距離 %5.0f  範圍和 %5.0f（%.2f 倍）  重疊可走格 %s' % (
                a['name'], b['name'], dist, a['range'] + b['range'], dist / (a['range'] + b['range']),
                '無' if nboth == 0 else '%d 格（約 %d px²）' % (nboth, nboth * 16)))
            if nboth:
                pair_bad.append((a['name'], b['name']))
    data['flood'] = fl
    data['fine'] = fine
    data['bad'] = bad
    data['pair_bad'] = pair_bad
    if verbose:
        print('\n'.join(lines))
    return lines


# ═══════════════════════════════ 輸出 C# ═══════════════════════════════

def _f(v):
    s = '%.2f' % v
    s = s.rstrip('0').rstrip('.') if '.' in s else s
    return s + 'f'


def write_cs(data):
    rows = []
    for q in data['pieces']:
        wd = q['world']
        sh = q['shape']
        if sh is None:
            coll = 'BrewShape.None, 0f, 0f, 0f, 0f, null'
        elif sh['shape'] == 'ellipse':
            coll = 'BrewShape.Ellipse, %s, %s, %s, %s, null' % (_f(sh['cx']), _f(sh['cy']), _f(sh['hx']), _f(sh['hy']))
        else:
            coll = 'BrewShape.Poly, 0f, 0f, 0f, 0f, new Vector2[] { %s }' % ', '.join(
                'new(%s, %s)' % (_f(x), _f(y)) for x, y in sh['pts'])
        frames = ', '.join('"%s%s"' % (ART_PREFIX, a) for a in q['art'])
        seq = 'null' if not q['seq'] else 'new[] { %s }' % ', '.join(str(i) for i in q['seq'])
        r = wd['rect']
        rows.append(
            '            new BrewPiece("%s", new[] { %s }, %s, %s, %s,\n'
            '                %s, %s, %s, %s, %d,\n'
            '                %s, %s, %s, %s,\n'
            '                %s, %s, %s, %s,\n'
            '                %s,\n'
            '                %s),' % (
                q.get('inst', q['name']), frames, _f(q['fps']), seq, 'BrewKind.Flat' if q['kind'] == 'flat' else 'BrewKind.Stand',
                _f(wd['x']), _f(wd['y']), _f(wd['pivot'][0]), _f(wd['pivot'][1]), q['order'],
                _f(q['U']), _f(q['U'] + q['du']), _f(q['V']), _f(q['V'] + q['dv']),
                _f(r[0]), _f(r[1]), _f(r[2]), _f(r[3]),
                'true' if q['tint'] else 'false', coll))
    glows = ['            new BrewGlow(%s, %s, %s, %s, %s),' % (_f(g['x']), _f(g['y']), _f(g['r']), _f(g['k']),
                                                              'true' if g['flicker'] else 'false') for g in data['glows']]
    pts = {p['name']: p for p in data['points']}
    walk = ', '.join('new(%s, %s)' % (_f(x), _f(y)) for x, y in data['walk'])
    def pt(n):
        p = pts[n]
        return 'new(%s, %s)' % (_f(p['x']), _f(p['y']))
    cs = '''// <auto-generated>
// ⚠️ 自動產生，不要手改。產生器：tools/gen_brew_room.py
//    重跑：python tools/gen_brew_room.py（加 --preview <資料夾> 輸出合成預覽）
//    要搬家具、改互動距離、改碰撞：改產生器裡的 PIECES／INTERACT／DOOR_* 等常數，不是改這個檔。
// </auto-generated>
using UnityEngine;

namespace WitchShop.Data
{
    /// <summary>藥水室物件的種類：平貼地面（壓在最底、不擋）／立著（照前後關係排序）。</summary>
    public enum BrewKind { Flat, Stand }

    /// <summary>碰撞形狀：不擋／軸對齊橢圓（等距的圓）／凸多邊形（等距的落地範圍＝平行四邊形）。</summary>
    public enum BrewShape { None, Ellipse, Poly }

    /// <summary>
    /// 藥水室裡的一件東西。座標全是**世界座標**（PPU 1、房間圖中心＝原點）。
    /// X/Y ＝落腳點（落地範圍中心），圖的樞紐 PivotX/PivotY（像素）就對在這一點。
    /// U0..V1 ＝落地範圍在地板 uv 座標的盒子（女巫排序用，見 BrewRoom.PlayerOrder）。
    /// Rect* ＝整張圖在世界上的矩形（判斷跟女巫的圖有沒有重疊）。
    /// </summary>
    public readonly struct BrewPiece
    {
        public readonly string Name;
        public readonly string[] Frames;     // Resources 路徑（單張＝一個元素）
        public readonly float Fps;           // 動畫速度（0 ＝由別的元件控制，例如鍋爐只在熬煮時播）
        public readonly int[] Seq;           // 幀的播放順序（null ＝ 0,1,2… 依序）
        public readonly BrewKind Kind;
        public readonly float X, Y;          // 落腳點（世界座標）
        public readonly float PivotX, PivotY;   // 樞紐（像素，從圖的左下角量）：Sprite 的樞紐放這裡，position 就是落腳點
        public readonly int Order;           // 靜態排序（立著的物件彼此之間已排好；女巫插在中間）
        public readonly float U0, U1, V0, V1;
        public readonly float RectXMin, RectYMin, RectXMax, RectYMax;
        public readonly bool Tint;           // 夜晚乘 NightTint（會發光的東西 false）
        public readonly BrewShape Shape;
        public readonly float Cx, Cy, Hx, Hy;   // 橢圓
        public readonly Vector2[] Poly;          // 凸多邊形（世界座標）

        public BrewPiece(string name, string[] frames, float fps, int[] seq, BrewKind kind,
                         float x, float y, float pivotX, float pivotY, int order,
                         float u0, float u1, float v0, float v1,
                         float rx0, float ry0, float rx1, float ry1,
                         bool tint,
                         BrewShape shape, float cx, float cy, float hx, float hy, Vector2[] poly)
        {
            Name = name; Frames = frames; Fps = fps; Seq = seq; Kind = kind;
            X = x; Y = y; PivotX = pivotX; PivotY = pivotY; Order = order;
            U0 = u0; U1 = u1; V0 = v0; V1 = v1;
            RectXMin = rx0; RectYMin = ry0; RectXMax = rx1; RectYMax = ry1;
            Tint = tint; Shape = shape; Cx = cx; Cy = cy; Hx = hx; Hy = hy; Poly = poly;
        }
    }

    /// <summary>夜晚的光暈：位置、半徑（像素）、強度（0..1）、要不要閃爍（燭火、爐火）。</summary>
    public readonly struct BrewGlow
    {
        public readonly float X, Y, Radius, Strength;
        public readonly bool Flicker;
        public BrewGlow(float x, float y, float radius, float strength, bool flicker)
        { X = x; Y = y; Radius = radius; Strength = strength; Flicker = flicker; }
    }

    /// <summary>
    /// 魔女的房間（藥水室）的配置表 —— **自動產生，不要手改**。
    /// 美術在 Resources/rooms/brew/，所有位置數字來自 tools/gen_brew_room.py。
    /// </summary>
    public static class BrewRoomLayout
    {
        public const string ShellDay = "%PFX%shell-day";
        public const string ShellNight = "%PFX%shell-night";
        public const string Glow = "%PFX%glow";

        /// <summary>地板 uv 原點（兩面後牆交會的牆角）的世界座標。uv → 世界：x = IsoX + u − v、y = IsoY − (u + v)/2。</summary>
        public const float IsoX = %ISOX%, IsoY = %ISOY%;

        /// <summary>家具夜晚乘的顏色（跟 shell-night 壓暗的那一組一樣）。</summary>
        public static readonly Color NightTint = new(%NT0%, %NT1%, %NT2%, 1f);
        public static readonly Color GlowColor = new Color32(%GC0%, %GC1%, %GC2%, 255);
        /// <summary>光暈最亮處的不透明度（再乘每個光暈的 Strength）。</summary>
        public const float GlowAlpha = %GA%;
        /// <summary>光暈貼圖的邊長（像素）：縮放 ＝ 半徑 × 2 ÷ 這個值。</summary>
        public const float GlowSize = %GS%;

        /// <summary>女巫的可走範圍：地板菱形往內縮（世界座標、順時針、凸多邊形）。</summary>
        public static readonly Vector2[] Walk = { %WALK% };

        /// <summary>女巫出生點（離出口 80px —— SceneDoor 的 armed 機制另外擋「一進來就被彈回去」）。</summary>
        public static readonly Vector2 Spawn = new(%SPX%, %SPY%);

        // 互動點（世界座標）與互動距離（像素）
        public static readonly Vector2 BedAt = %BED%;
        public const float BedRange = %BEDR%;
        public static readonly Vector2 WardrobeAt = %WAR%;
        public const float WardrobeRange = %WARR%;
        public static readonly Vector2 ChestAt = %CHE%;
        public const float ChestRange = %CHER%;
        public static readonly Vector2 CauldronAt = %CAU%;
        public const float CauldronRange = %CAUR%;
        public static readonly Vector2 ExitAt = %EXI%;
        public const float ExitRange = %EXIR%;
        public const float ExitAuto = %EXIA%;

        public static readonly BrewPiece[] Pieces =
        {
%PIECES%
        };

        public static readonly BrewGlow[] Glows =
        {
%GLOWS%
        };

        /// <summary>世界座標 → 地板 uv。</summary>
        public static Vector2 ToUV(float x, float y)
        {
            float dx = x - IsoX, dy = IsoY - y;
            return new Vector2(dy + dx * 0.5f, dy - dx * 0.5f);
        }
    }
}
'''
    rep = {
        '%PFX%': ART_PREFIX, '%ISOX%': _f(data['iso'][0]), '%ISOY%': _f(data['iso'][1]),
        '%NT0%': _f(NIGHT_TINT[0]), '%NT1%': _f(NIGHT_TINT[1]), '%NT2%': _f(NIGHT_TINT[2]),
        '%GA%': _f(GLOW_ALPHA), '%GS%': _f(GLOW_PX),
        '%GC0%': str(GLOW_COLOR[0]), '%GC1%': str(GLOW_COLOR[1]), '%GC2%': str(GLOW_COLOR[2]),
        '%WALK%': walk, '%SPX%': _f(data['spawn'][0]), '%SPY%': _f(data['spawn'][1]),
        '%BED%': pt('bed'), '%BEDR%': _f(pts['bed']['range']),
        '%WAR%': pt('wardrobe'), '%WARR%': _f(pts['wardrobe']['range']),
        '%CHE%': pt('chest'), '%CHER%': _f(pts['chest']['range']),
        '%CAU%': pt('cauldron'), '%CAUR%': _f(pts['cauldron']['range']),
        '%EXI%': pt('exit'), '%EXIR%': _f(pts['exit']['range']), '%EXIA%': _f(pts['exit']['auto']),
        '%PIECES%': '\n'.join(rows), '%GLOWS%': '\n'.join(glows),
    }
    for k, v in rep.items():
        cs = cs.replace(k, v)
    with open(CS_OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(cs)


# ═══════════════════════════════ 預覽 ═══════════════════════════════

def witch_sprite():
    """女巫站姿（朝南那一格）× WitchScale 1.6 —— 遊戲裡實際的大小。"""
    b = Image.open(os.path.join(RES, 'witch8', 'base.png')).convert('RGBA')
    cw, ch = b.width // 8, b.height // 25
    cell = b.crop((0, 0, cw, ch))
    return cell.resize((round(cw * 1.6), round(ch * 1.6)), Image.NEAREST)


def player_order(data, wx, wy, wsz):
    """女巫的排序（跟 BrewRoom.PlayerOrder 同一個算法）。"""
    u, v = world_to_uv(wx, wy)
    w, h = wsz
    rect = (wx - w * 0.35, wy, wx + w * 0.35, wy + h * 0.9)
    lo, hi = -10 ** 9, 10 ** 9
    for q in data['pieces']:
        if q['kind'] != 'stand' or not rect_overlap(rect, q['world']['rect']):
            continue
        U0, U1, V0, V1 = q['U'], q['U'] + q['du'], q['V'], q['V'] + q['dv']
        if u >= U1 or v >= V1:
            front = True
        elif u <= U0 or v <= V0:
            front = False
        else:
            front = (u + v) > (U0 + U1 + V0 + V1) / 2
        if front:
            lo = max(lo, q['order'])
        else:
            hi = min(hi, q['order'])
    if lo == -10 ** 9 and hi == 10 ** 9:
        return round(-wy)
    if lo == -10 ** 9:
        return hi - 1
    return lo + 1


def compose(data, arts, night, witches=()):
    shell = arts['shell-night' if night else 'shell-day'][0]
    img = Image.fromarray(shell.copy())
    layers = []
    for q in data['pieces']:
        p = arts[q['art'][0]][0]
        layers.append((q['order'], 'piece', q, p))
    wimg = witch_sprite()
    for (wx, wy) in witches:
        o = player_order(data, wx, wy, wimg.size)
        layers.append((o + 0.5, 'witch', (wx, wy), None))
    for o, kind, q, p in sorted(layers, key=lambda t: t[0]):
        if kind == 'witch':
            wx, wy = q
            x, y = wx + CANVAS_W / 2, CANVAS_H / 2 - wy
            sh = Image.new('RGBA', (40, 12), (0, 0, 0, 0))
            from PIL import ImageDraw
            ImageDraw.Draw(sh).ellipse([0, 0, 39, 11], fill=(20, 10, 25, 90))
            img.alpha_composite(sh, (int(x - 20), int(y - 6)))
            img.alpha_composite(wimg, (int(round(x - wimg.width / 2)), int(round(y - wimg.height + 3 * 1.6))))
            continue
        im = Image.fromarray(p)
        if night and q['tint']:
            a = np.asarray(im).astype(np.float32)
            a[..., 0] *= NIGHT_TINT[0]
            a[..., 1] *= NIGHT_TINT[1]
            a[..., 2] *= NIGHT_TINT[2]
            im = Image.fromarray(a.clip(0, 255).astype(np.uint8))
        img.alpha_composite(im, (int(q['world']['left']), int(q['world']['top'])))
    if night:
        g = glow_image(128)
        for gl in data['glows']:
            size = int(gl['r'] * 2)
            gi = Image.fromarray(g).resize((size, size), Image.BILINEAR)
            a = np.asarray(gi).astype(np.float32)
            a[..., 0] = GLOW_COLOR[0]
            a[..., 1] = GLOW_COLOR[1]
            a[..., 2] = GLOW_COLOR[2]
            a[..., 3] *= gl['k'] * GLOW_ALPHA
            gi = Image.fromarray(a.astype(np.uint8))
            x, y = gl['x'] + CANVAS_W / 2, CANVAS_H / 2 - gl['y']
            img.alpha_composite(gi, (int(x - size / 2), int(y - size / 2)))
    return img


def collision_image(data, base):
    """碰撞俯視圖：紅＝落地範圍、黃＝可走多邊形、淡綠＝走得到、紅點＝同時在兩個互動範圍內、圓＝互動距離、白方塊＝出生點。
    data 要先跑過 check_room()。"""
    from PIL import ImageDraw
    a = np.asarray(base.convert('RGBA')).astype(np.float32)
    a[..., :3] = a[..., :3] * 0.55 + 40
    im = Image.fromarray(a.astype(np.uint8))
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    P = lambda x, y: (x + CANVAS_W / 2, CANVAS_H / 2 - y)  # noqa: E731
    fine = data['fine']
    pl = data['points']
    over = np.zeros_like(fine['reach'])
    for i in range(len(pl)):
        for j in range(i + 1, len(pl)):
            a_, b_ = pl[i], pl[j]
            over |= fine['reach'] & (np.hypot(fine['X'] - a_['x'], fine['Y'] - a_['y']) <= a_['range']) & \
                (np.hypot(fine['X'] - b_['x'], fine['Y'] - b_['y']) <= b_['range'])
    for jj, ii in zip(*np.nonzero(fine['reach'])):
        x, y = P(fine['X'][jj, ii], fine['Y'][jj, ii])
        d.rectangle([x - 2, y - 2, x + 1, y + 1], fill=(255, 40, 40, 170) if over[jj, ii] else (90, 230, 120, 60))
    d.polygon([P(*q) for q in data['walk']], outline=(255, 220, 60, 255))
    for s_ in data['shapes']:
        if s_['shape'] == 'ellipse':
            a1, b1 = P(s_['cx'] - s_['hx'], s_['cy'] + s_['hy'])
            a2, b2 = P(s_['cx'] + s_['hx'], s_['cy'] - s_['hy'])
            d.ellipse([a1, b1, a2, b2], outline=(230, 20, 20, 255), width=2)
        else:
            d.line([P(*q) for q in s_['pts']] + [P(*s_['pts'][0])], fill=(230, 20, 20, 255), width=2)
    cols = {'bed': (120, 160, 255), 'wardrobe': (255, 150, 220), 'chest': (255, 190, 80), 'cauldron': (80, 230, 210),
            'exit': (150, 220, 255)}
    for p in pl:
        x, y = P(p['x'], p['y'])
        c = cols.get(p['name'], (255, 255, 255)) + (255,)
        d.ellipse([x - p['range'], y - p['range'], x + p['range'], y + p['range']], outline=c, width=2)
        if 'auto' in p:
            d.ellipse([x - p['auto'], y - p['auto'], x + p['auto'], y + p['auto']], outline=c, width=1)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=c, outline=(0, 0, 0, 255))
    x, y = P(*data['spawn'])
    d.rectangle([x - 6, y - 6, x + 6, y + 6], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    im.alpha_composite(ov)
    return im.convert('RGB')


def preview(data, arts, outdir):
    os.makedirs(outdir, exist_ok=True)
    pts = {p['name']: p for p in data['points']}
    # 女巫站的幾個位置：出生點、鍋爐左前、床的左邊（床後面被遮）、衣櫃前、木箱前、扶手椅後面、藥水台後面
    W = []
    for nm, (du_, dv_) in (('cauldron', (-50, 30)), ('wardrobe', (14, 0)), ('chest', (8, 0))):
        u, v = INTERACT[nm]['uv']
        W.append(uv_to_world(u + du_, v + dv_))
    W.append(data['spawn'])
    W.append(uv_to_world(296, 70))     # 床的左邊（應該在床後面一點、被床柱與帷幔遮住一部分）
    W.append(uv_to_world(350, 140))    # 床尾前面（應該蓋住床尾）
    W.append(uv_to_world(200, 340))    # 藥水台後面（被台子遮住腳）
    W.append(uv_to_world(530, 40))     # 扶手椅與壁爐之間（椅背後）
    day = compose(data, arts, False, W)
    night = compose(data, arts, True, W[:4])
    files = []
    p = os.path.join(outdir, 'brew-empty.png')
    bg = Image.new('RGBA', day.size, (24, 20, 30, 255))
    bg.alpha_composite(compose(data, arts, False, []))
    bg.convert('RGB').save(p)
    files.append(p)
    for nm, im in (('brew-day.png', day), ('brew-night.png', night)):
        p = os.path.join(outdir, nm)
        bg = Image.new('RGBA', im.size, (24, 20, 30, 255))
        bg.alpha_composite(im)
        bg.convert('RGB').save(p)
        files.append(p)
        bg.crop((300, 120, 860, 520)).resize((1120, 800), Image.NEAREST).convert('RGB').save(p.replace('.png', '-zoom.png'))
        files.append(p.replace('.png', '-zoom.png'))
    # 碰撞範圍
    p = os.path.join(outdir, 'brew-collision.png')
    collision_image(data, compose(data, arts, False, [])).save(p)
    files.append(p)
    # 單件放大（檢查描邊與硬邊）
    sheet_items = [nm for nm in arts if not nm.startswith('shell')]
    tiles = [Image.fromarray(arts[nm][0]) for nm in sheet_items]
    Wt = 1500
    x = y = rowh = 0
    pos = []
    for t in tiles:
        if x + t.width * 2 > Wt:
            x, y, rowh = 0, y + rowh + 8, 0
        pos.append((x, y))
        x += t.width * 2 + 8
        rowh = max(rowh, t.height * 2)
    sheet = Image.new('RGBA', (Wt, y + rowh), (60, 70, 64, 255))
    for t, (x, y) in zip(tiles, pos):
        sheet.alpha_composite(t.resize((t.width * 2, t.height * 2), Image.NEAREST), (x, y))
    p = os.path.join(outdir, 'brew-pieces.png')
    sheet.convert('RGB').save(p)
    files.append(p)
    return files


# ═══════════════════════════════ 主程式 ═══════════════════════════════

def main():
    args = sys.argv[1:]
    if '--check' in args:
        data = room_data(None)
        check_room(data)
        sys.exit(1 if data['bad'] else 0)
    preview_dir = None
    if '--preview' in args:
        preview_dir = args[args.index('--preview') + 1]
    arts = build_art()
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SVG_DIR, exist_ok=True)
    keep = set(arts) | {'glow'}
    for d, ext in ((OUT_DIR, '.png'), (SVG_DIR, '.svg')):
        for fn in os.listdir(d):
            base = fn[:-len(ext)] if fn.endswith(ext) else fn[:-len(ext + '.meta')] if fn.endswith(ext + '.meta') else None
            if base is not None and base not in keep:
                os.remove(os.path.join(d, fn))          # 拿掉或改名的圖（連同 Unity 產生的 .meta）
    for nm, (p, origin, s) in arts.items():
        Image.fromarray(p).save(os.path.join(OUT_DIR, nm + '.png'))
        with open(os.path.join(SVG_DIR, nm + '.svg'), 'w', encoding='utf-8') as fh:
            fh.write(s.markup(standalone=True))
    Image.fromarray(glow_image(128)).save(os.path.join(OUT_DIR, 'glow.png'))
    data = room_data({k: (v[0], v[1]) for k, v in arts.items()})
    check_room(data)
    write_cs(data)
    print('寫出 %d 張圖到 %s、SVG 原始檔到 %s、配置表 %s' % (len(arts) + 1, OUT_DIR, SVG_DIR, CS_OUT))
    print('物件：')
    for q in data['pieces']:
        p = arts[q['art'][0]][0]
        sh = q['shape']
        print('  %-20s %3dx%-3d 落腳 (%7.1f, %7.1f)  排序 %6d  碰撞 %s' % (
            q.get('inst', q['name']), p.shape[1], p.shape[0], q['world']['x'], q['world']['y'], q['order'],
            '無' if sh is None else ('橢圓 %.0fx%.0f' % (sh['hx'] * 2, sh['hy'] * 2) if sh['shape'] == 'ellipse' else '平行四邊形')))
    if preview_dir:
        for f in preview(data, arts, preview_dir):
            print('預覽：' + f)
    if data['bad']:
        sys.exit(1)


if __name__ == '__main__':
    main()
