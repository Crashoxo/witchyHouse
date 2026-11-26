#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
路人（村民／顧客）走路圖（8-bit 像素風）產生器：11 位居民全部用程式點陣畫。

    python tools/gen_villager_art.py                    # 輸出 Assets/Resources/villagers8/<名字>.png
    python tools/gen_villager_art.py --preview DIR      # 另外輸出總覽圖、GIF、實景合成到 DIR
    python tools/gen_villager_art.py --out DIR          # 走路表改寫到 DIR（迭代時用，不碰 Assets）
    python tools/gen_villager_art.py --restore          # 刪掉 villagers8/（GameArt 會自動退回舊圖）

── 為什麼重畫 ────────────────────────────────────────────────────────
  舊的 Resources/villagers/*.png 是 AI 生成的厚塗風走路表：每張尺寸、格子、角色比例都不一樣，
  有的格子切到隔壁幀的殘影，走路幀不連貫，跟場景／女巫／道具圖示的 8-bit 點陣也不搭。
  這裡照 gen_item_art.py 的做法：在低解析度邏輯格上用幾何基元畫、3 階打光、自動補 1px 深色外輪廓、
  NEAREST 放大 —— 成品每一格都是純色、alpha 只有 0 或 255。

── 規格（⚠️ GameArt.cs／VillagerAnim.cs 依賴這個，改之前先看那邊的 UsePixelVillagers 說明）────
  * 每格邏輯 28×36、放大 3 倍 → 84×108；一張 4 欄 × 3 列 ＝ 336×324。**11 位全部同一個格子**。
  * 列 0 朝下、列 1 側面（朝左）、列 2 朝上；欄 0～3 ＝ 站—左腳前—站—右腳前（第 0 欄兼站姿）。
  * 角色水平置中（以第 13／14 欄之間為中線）；**腳底最後一列像素在第 33 列，外輪廓落在第 34 列，
    第 35 列（最底下那一列）留空** → 鞋底外輪廓的下緣＝格子底邊往上 1 個邏輯格（輸出 3px），
    所有角色、所有幀都一樣（走路不會上下跳、YSort 準）。四周至少留 1 格透明。
  * 走路循環：跨步那兩幀身體（腿以上）往上提 1 格，後腳抬起 2 格（正背面）或往後擺（側面），
    手跟腳反向擺。騎掃帚的魔女腳不著地：整個人＋掃帚上下浮 1 格、掃帚尾擺動。
  * 大人（法師、旅人）可見高約 32～33 格（×3＝96～99px，比女巫的 93px 略高）；
    小魔女、兔子、鹿約 29～31 格；青蛙、刺蝟、狐狸、妖精約 25～29 格。
  * 結果是確定的：沒有亂數，重跑 md5 相同。

── 組件式 ──────────────────────────────────────────────────────────
  共用的 Q 版骨架（Pose：腳、腿、身體、手、頭的位置，依方向與幀算好），角色只是一串「組件」：
  膚／毛色、衣服（上衣、長袍、斗篷）、耳朵、吻部、尾巴、帽子、翅膀、手上或背上的道具。
  畫的順序依方向不同（側面：遠側的手 → 尾巴 → 腳 → 身體 → 頭 → 帽子 → 近側的手與道具；
  背面：背上的東西〔尾巴、翅膀、背包〕在身體之後畫，蓋在背上）。

⚠️ 陷阱
  * 外輪廓一樣用 4 鄰接（理由同 gen_item_art.py）。部件之間要分開的地方（手臂壓在身體上、
    頭壓在衣領上）用 part(..., ol=True) 先描一圈再填色。
  * 不要在 finish() 裡自動置中／貼底 —— 道具圖示可以，走路圖不行：每一幀內容寬高不同，
    自動置中會讓角色每幀左右抖。這裡所有座標都是格子絕對座標，finish() 只檢查有沒有超框。
  * 側面一律畫「朝左」，往右走由 VillagerAnim 把 scale.x 取負 —— 所以側面的東西不要畫字或不對稱的標記。
"""
import hashlib
import math
import os
import shutil
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, 'Assets', 'Resources')
OUT_DIR = os.path.join(RES, 'villagers8')

sys.path.insert(0, HERE)
# 只 import 道具圖示那支的繪圖基元與色盤（它自己的輸出不受影響）
from gen_item_art import (Icon, ell, rect, poly, line, leaf, dilate,   # noqa: E402
                          find_font, PAL as ITEM_PAL)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

W, H = 28, 36       # 邏輯格
SCALE = 3           # 輸出放大倍數 → 84×108
FB = 33             # 腳底最後一列像素（外輪廓在 34、35 留空）
COLS, ROWS = 4, 3
DOWN, SIDE, UP = 0, 1, 2

# ═══════════════════════════════ 色盤 ═══════════════════════════════
# 基底沿用道具圖示的色盤（裡面已含魔女房間的 PAL），外輪廓同一個深棕紫。下面補路人專用的色。
VPAL = {
    'eye': '#2a1b24',                                                   # 眼睛＝外輪廓色（不多算一色）
    'blush': '#f28b8b',
    'sk_hi': '#ffe2c6', 'sk': '#f6c49c', 'sk_dk': '#d6946e',            # 人的皮膚
    'hr_hi': '#a8643a', 'hr': '#7c4528', 'hr_dk': '#55301f',            # 棕髮
    'gn_hi': '#f0a050', 'gn': '#d0682c', 'gn_dk': '#963e1e',            # 薑紅髮
    'bd_hi': '#fff0a8', 'bd': '#f0cc62', 'bd_dk': '#c09038',            # 金髮
    'fg_hi': '#b4e884', 'fg': '#72c25c', 'fg_dk': '#3f8a48',            # 青蛙綠
    'ry_hi': '#fff08a', 'ry': '#f6cc3a', 'ry_dk': '#c4901f',            # 雨衣黃
    'fx_hi': '#ffae5c', 'fx': '#ec7a30', 'fx_dk': '#b04e22',            # 狐狸橘
    'cr_hi': '#fffaf0', 'cr': '#f3e4cc', 'cr_dk': '#cfb99a',            # 奶油白（兔毛、狐狸胸口）
    'nv_hi': '#5266b4', 'nv': '#36448a', 'nv_dk': '#232c5e',            # 星空藍
    'hg_hi': '#b98a62', 'hg': '#8e6342', 'hg_dk': '#64432c',            # 刺蝟刺
    'mr_hi': '#d85a66', 'mr': '#a8384a', 'mr_dk': '#6e2236',            # 酒紅
    'sc_hi': '#8cc8f4', 'sc': '#5fa0e0', 'sc_dk': '#3a6cb0',            # 圍巾藍
    'dr_hi': '#dca068', 'dr': '#b87848', 'dr_dk': '#86522e',            # 鹿毛
    'lf_hi': '#a6d870', 'lf': '#64a446', 'lf_dk': '#3c6c30',            # 葉子
    'mu_hi': '#f2665a', 'mu': '#d23a3c', 'mu_dk': '#962431',            # 蘑菇紅
    'wg_hi': '#f0fdff', 'wg': '#bfeaf4', 'wg_dk': '#7ec0d8',            # 妖精翅膀
    'tr_hi': '#b48a64', 'tr': '#8c6244', 'tr_dk': '#60412c',            # 旅人斗篷
    'wp_hi': '#a07ed0', 'wp': '#7452a8', 'wp_dk': '#4c3478',            # 魔女紫
    'lv_hi': '#d4c0f4', 'lv': '#a68ad8', 'lv_dk': '#7660ae',            # 兔魔女淡紫
    'bk_hi': '#5c5078', 'bk': '#3c3454', 'bk_dk': '#262036',            # 魔女黑（帶紫）
    'pm_hi': '#ffb04a', 'pm': '#f07c22', 'pm_dk': '#b0501a',            # 南瓜
    'ov_hi': '#80b4ec', 'ov': '#4a7ec8', 'ov_dk': '#2e5590',            # 吊帶褲藍
    'pink_in': '#f4a6b8',                                               # 耳朵內側
    'ft': '#ffd76a',                                                    # 燈火
}
PAL = dict(ITEM_PAL)
PAL.update(VPAL)
OL = 'outline'


def rgb(key):
    h = PAL[key]
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def mir(m):
    """左右鏡射（以第 13／14 欄之間為中線）。"""
    return {(W - 1 - x, y) for x, y in m}


def sym(m):
    return m | mir(m)


def thick(pts, w=2):
    """把一條線加粗成 w 格寬（往右長）。"""
    return {(x + i, y) for x, y in pts for i in range(w)}


# ═══════════════════════════════ 畫布 ═══════════════════════════════

class Spr(Icon):
    """一格走路圖。沿用道具圖示的 Icon（put／sphere／cyl／flat／glow），只換掉 finish（不自動置中）。"""

    def part(self, m, ramp, ol=False, shade='flat', cuts=(0.9, 0.12)):
        """畫一個部件：ol＝先在四周描一圈外輪廓（壓在已畫的部件上，部件之間才分得開）。"""
        m = set(m)
        if ol:
            for p in dilate(m) - m:
                self.px[p] = OL
        if isinstance(ramp, str):
            ramp = (ramp,)
        if shade == 'solid' or len(ramp) == 1:
            self.put(m, ramp[0])
        elif shade == 'flat' and len(ramp) == 3:
            self.flat(m, ramp)
        elif shade == 'flat':                          # 兩階：右下邊暗
            for x, y in m:
                edge = (x + 1, y) not in m or (x, y + 1) not in m
                self.px[(x, y)] = ramp[1] if edge else ramp[0]
        elif shade == 'cyl':
            self.cyl(m, ramp)
        elif shade == 'ball':
            xs = [p[0] for p in m]
            ys = [p[1] for p in m]
            cx, cy = (min(xs) + max(xs) + 1) / 2, (min(ys) + max(ys) + 1) / 2
            rx, ry = (max(xs) - min(xs) + 1) / 2, (max(ys) - min(ys) + 1) / 2
            self.sphere(m, ramp, cx, cy, rx, ry, cuts=cuts)
        return m

    def shifted(self, dx, dy):
        self.px = {(x + dx, y + dy): c for (x, y), c in self.px.items()}
        self.glow = {(x + dx, y + dy): c for (x, y), c in self.glow.items()}

    def finish(self, name):
        body = dict(self.px)
        for (x, y), c in list(self.px.items()):
            if c == OL:                  # part(ol=True) 描的那圈本身就是外輪廓，不要再往外長一圈
                continue
            for p in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if p not in self.px:
                    body[p] = OL
        for p, c in self.glow.items():
            if p not in body or body[p] == OL:
                body[p] = c
        for x, y in body:
            assert 1 <= x <= W - 2 and 1 <= y <= FB + 1, f'{name}: ({x},{y}) 超出格子'
        grid = [[None] * W for _ in range(H)]
        for (x, y), c in body.items():
            grid[y][x] = c
        return grid


# ═══════════════════════════════ 骨架 ═══════════════════════════════

class Pose:
    """
    依方向 d、幀 f、體型 B 算出各部位位置（格子座標，y 往下）。
      step：0＝站、1／-1＝兩邊跨步；bob：跨步時身體往上提 1 格。
      ty0..ty1：身體（上衣）上下緣；hy0..hy1：頭；hx0..hx1：頭的左右；tx0..tx1：身體左右。
      B：leg 腿長（含被身體蓋住的一列）、th／tw 身體高寬、hw／hh 頭寬高、arm 手長（含手掌 2 列）。
    """

    def __init__(self, d, f, B):
        self.d, self.f, self.B = d, f, B
        self.step = (0, 1, 0, -1)[f]
        self.bob = -1 if self.step else 0
        self.ft = FB - 1                           # 腳（2 列）的上面那一列
        self.leg, self.th, self.tw = B['leg'], B['th'], B['tw']
        self.hw, self.hh, self.arm = B['hw'], B['hh'], B['arm']
        self.ty1 = self.ft - self.leg + self.bob
        self.ty0 = self.ty1 - self.th + 1
        self.hy1 = self.ty0 + B.get('neck', 0)
        self.hy0 = self.hy1 - self.hh + 1
        self.hx0, self.hx1 = 14 - self.hw // 2, 13 + self.hw // 2
        tw = self.tw - (2 if d == SIDE else 0)
        self.tx0, self.tx1 = 14 - tw // 2, 13 + tw // 2
        self.hcy = (self.hy0 + self.hy1 + 1) / 2
        self.ey = self.hy0 + int(round(self.hh * B.get('eye', 0.56)))

    @property
    def near_off(self):
        """側面：近側的腳往前（左）擺 -2*step，遠側反向。"""
        return -2 * self.step

    @property
    def far_off(self):
        return 2 * self.step


# ─────────── 共用部件 ───────────

def legs(s, P, pant, shoe, foot_w=3):
    """
    腿＋鞋。正背面：抬起的那隻腳離地 2 格；側面：近側腳畫亮、遠側腳畫暗、往後那隻腳跟抬 1 格。
    ⚠️ 鞋的 ramp 想要深到跟外輪廓同色時用 'eye'，不要用 'outline' —— finish() 不會在 'outline'
       外面再補一圈，鞋底就少一列、腳底基準線變成第 33 列（那位角色整個浮 1 格）。
    """
    if P.d != SIDE:
        for side in (-1, 1):
            lifted = (P.step == side) if P.d == DOWN else (P.step == -side)
            ftop = P.ft - (2 if lifted else 0)
            lx = 11 if side < 0 else 15
            s.part(rect(lx, P.ty1, lx + 1, ftop - 1), pant)
            fx = (lx - foot_w + 2) if side < 0 else lx
            s.part(rect(fx, ftop, fx + foot_w - 1, ftop + 1), shoe)
        return
    for off, near in ((P.far_off, False), (P.near_off, True)):
        ftop = P.ft - (1 if off > 0 else 0)
        lm = thick(line(13, P.ty1, 13 + off, ftop - 1))
        fm = rect(13 + off - 1, ftop, 13 + off + foot_w - 2, ftop + 1)
        if near:
            s.part(lm, pant, ol=bool(P.step))
            s.part(fm, shoe, ol=bool(P.step))
        else:
            s.part(lm, pant[-1])
            s.part(fm, shoe[-1])


def torso(s, P, ramp, flare=0, hem=0, ol=False, top_w=None):
    """身體：正背面是梯形（flare＝下襬往外擴幾格、hem＝下襬比腰多垂幾列）；側面窄 2 格。"""
    y1 = P.ty1 + hem
    x0, x1 = P.tx0, P.tx1
    if top_w is not None:
        x0, x1 = 14 - top_w // 2, 13 + top_w // 2
    if flare == 0 and top_w is None:
        m = rect(x0, P.ty0, x1, y1)
    else:
        m = poly([(x0 + 0.0, P.ty0), (x1 + 1.0, P.ty0),
                  (P.tx1 + 1.0 + flare, y1 + 1.0), (P.tx0 - flare + 0.0, y1 + 1.0)])
    return s.part(m, ramp, ol=ol)


def hem_wave(s, P, m, col):
    """長袍下襬隨走路擺動：最底一列每隔 4 格缺一格、缺口位置跟著幀走。"""
    y1 = max(p[1] for p in m)
    for x, y in list(m):
        if y == y1 and (x + P.f * 2) % 4 == 0:
            s.px.pop((x, y), None)
            if (x, y - 1) in s.px:
                s.px[(x, y - 1)] = col


def arms(s, P, sleeve, skin, which='both', hand=True, ol=True, fixed=None):
    """
    手：正背面兩邊垂下、跨步時一隻提高 1 格；側面近側手前後擺 2 格（跟近側腳反向）。
    fixed：側面時把近側手固定伸到前面（拿法杖、提燈），值＝往前幾格。
    回傳：正背面 {-1: 左手, 1: 右手}、側面 {True: 近側手, False: 遠側手}，值＝(手的左邊 x, 手的最下列 y)。
    """
    out = {}
    if P.d != SIDE:
        for side in (-1, 1):
            short = 1 if P.step == side else 0
            n = P.arm - short
            x0 = P.tx0 - 2 if side < 0 else P.tx1 + 1
            sl = rect(x0, P.ty0 + 1, x0 + 1, P.ty0 + n - (2 if hand else 0))
            s.part(sl, sleeve, ol=ol)
            if hand:
                s.part(rect(x0, P.ty0 + n - 1, x0 + 1, P.ty0 + n), skin)
            out[side] = (x0, P.ty0 + n)
        return out
    sel = {'both': (False, True), 'near': (True,), 'far': (False,)}[which]
    for near in sel:
        sw = (-P.near_off if near else -P.far_off) // 2   # 手跟腳反向：+1 往後、-1 往前
        if near and fixed is not None:
            end = (13 - fixed, P.ty0 + P.arm - 3)
        else:
            end = (13 + sw * 2, P.ty0 + P.arm - 2)
        pts = line(13, P.ty0 + 1, end[0], end[1] - (1 if hand else 0))
        sl = thick(pts)
        if near:
            s.part(sl, sleeve, ol=ol)
        else:
            s.part(sl, sleeve[-1])
        if hand:
            hm = rect(end[0], end[1], end[0] + 1, end[1] + 1)
            s.part(hm, skin if near else skin[-1])
        out[near] = (end[0], end[1] + 1)
    return out


def head(s, P, ramp, w=None, h=None, dx=0.0, dy=0.0, ol=True):
    w = w or P.hw
    h = h or P.hh
    m = ell(14.0 + dx, P.hcy + dy, w / 2, h / 2)
    s.part(m, ramp, ol=ol, shade='ball', cuts=(0.9, -0.02))
    return m


def face(s, P, blush=True, eye_dx=3, side_x=None, nose=None, dy=0):
    """正面：兩顆 1×2 的眼睛＋腮紅；側面：一顆眼睛靠左。背面不畫。"""
    ey = P.ey + dy
    if P.d == DOWN:
        for x in (14 - eye_dx, 13 + eye_dx):
            s.px[(x, ey)] = 'eye'
            s.px[(x, ey + 1)] = 'eye'
        if blush:
            for x in (14 - eye_dx - 2, 14 - eye_dx - 1, 13 + eye_dx + 1, 13 + eye_dx + 2):
                s.px[(x, ey + 2)] = 'blush'
        if nose:
            s.px[(13, ey + 2)] = nose
            s.px[(14, ey + 2)] = nose
    elif P.d == SIDE:
        x = P.hx0 + 2 if side_x is None else side_x
        s.px[(x, ey)] = 'eye'
        s.px[(x, ey + 1)] = 'eye'
        if blush:
            s.px[(x, ey + 2)] = 'blush'
            s.px[(x + 1, ey + 2)] = 'blush'


def hair(s, P, ramp, hm, bangs=True, locks=2, long_back=0, top_frac=0.42):
    """人類頭髮：頭頂一片、正面瀏海鋸齒、兩側鬢髮；背面整顆頭都是頭髮；側面後半是頭髮。"""
    top = P.hy0 + int(P.hh * top_frac)
    if P.d == UP:
        m = set(hm)
        if long_back:
            m |= rect(P.hx0 + 1, P.hy1 - 2, P.hx1 - 1, P.hy1 + long_back)
        s.part(m, ramp)
        return
    if P.d == DOWN:
        m = {p for p in hm if p[1] <= top}
        if bangs:
            for x in range(P.hx0, P.hx1 + 1):
                if (x - P.hx0) % 3 == 1:
                    m.add((x, top + 1))
        for x in list(range(P.hx0, P.hx0 + locks)) + list(range(P.hx1 - locks + 1, P.hx1 + 1)):
            for y in range(top, P.ey + 2 + long_back):
                if (x, y) in hm or long_back:
                    m.add((x, y))
        s.part(m, ramp)
        return
    m = {p for p in hm if p[1] <= top or p[0] >= 15}
    if bangs:
        m.add((P.hx0 + 1, top + 1))
    if long_back:
        m |= rect(15, P.hy1 - 2, P.hx1, P.hy1 + long_back)
    s.part(m, ramp)


def witch_hat(s, P, ramp, band, tall=9, brim_w=None, by=None, tip=1, gem=None, base=4.5):
    """魔女尖帽：帽簷（扁橢圓）＋往一邊倒的尖帽身＋帽帶。tip＝帽尖往哪邊倒（背面自動反過來）。"""
    by = P.hy0 + 3 if by is None else by
    bw = brim_w or (P.hw + 5)
    if P.d == SIDE:
        brim = ell(13.5, by + 0.5, bw / 2 + 0.5, 1.6)
        cone = poly([(14.0 - base, by + 0.5), (14.0 + base, by + 0.5), (17.5, by - tall + 4.0),
                     (21.0, by - tall + 1.5), (15.0, by - tall + 3.5)])
    else:
        t = tip if P.d == DOWN else -tip
        brim = ell(14.0, by + 0.5, bw / 2, 1.6)
        cone = poly([(14.0 - base, by + 0.5), (14.0 + base, by + 0.5), (14.0 + t * 2.0, by - tall + 4.0),
                     (14.0 + t * 5.0, by - tall + 1.5), (14.0 - t * 0.5, by - tall + 4.5)])
    s.part(cone, ramp, ol=True)
    s.part(brim, ramp, ol=True)
    s.put({p for p in cone if by - 2 <= p[1] <= by - 1}, band)
    if gem and P.d != UP:
        x = 12 if P.d == DOWN else 11
        s.px[(x, by - 2)] = gem
        s.px[(x, by - 1)] = gem
    return brim | cone


def side_snout(s, P, ramp, length=3, nose='eye', dy=2):
    """側面的吻部：從臉往左伸出的小橢圓，最左邊一格是鼻頭。"""
    y = P.ey + dy
    m = ell(P.hx0 + 1.5 - length / 2, y + 0.5, length / 2 + 1.0, 1.5)
    s.part(m, ramp, ol=True)
    nx = min(p[0] for p in m)
    s.px[(nx, y)] = nose
    return m


def sparkle(s, x, y, col='go_hi', core='wh'):
    s.glow[(x, y)] = core
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        s.glow[(x + dx, y + dy)] = col


# ═══════════════════════════════ 角色 ═══════════════════════════════
# 每位角色＝ draw(s, P)，在裡面依方向決定畫的順序。

SKIN = ('sk', 'sk', 'sk_dk')
HAIR = ('hr_hi', 'hr', 'hr_dk')
HAIR2 = ('hr', 'hr', 'hr_dk')
SHOE = ('hr', 'hr', 'hr_dk')          # 鞋子沿用棕髮的色（不另開色）

KID = dict(leg=2, th=8, tw=8, hw=12, hh=12, arm=6)
ADULT = dict(leg=5, th=10, tw=10, hw=12, hh=12, arm=8)


# ─── 小魔女（witch）────────────────────────────────

def draw_witch(s, P):
    """提南瓜桶的小魔女：紫尖帽、星空藍洋裝、棕髮兩條小辮、手提南瓜桶。"""
    dress = ('nv_hi', 'nv', 'nv_dk')
    hat = ('wp_hi', 'wp', 'wp_dk')

    def pumpkin(hx, hy):
        pm = ell(hx + 1.0, hy + 2.5, 2.6, 2.1)
        s.part(pm, ('pm', 'pm', 'pm_dk'), ol=True, shade='ball', cuts=(0.85, 0.3))
        s.px[(hx, hy + 2)] = 'eye'
        s.px[(hx + 2, hy + 2)] = 'eye'
        s.px[(hx + 1, hy + 3)] = 'eye'
        s.px[(hx + 1, hy)] = 'hr_dk'

    if P.d == SIDE:
        arms(s, P, dress, SKIN, which='far')
    legs(s, P, ('nv_dk', 'nv_dk'), SHOE)
    m = torso(s, P, dress, flare=2, hem=0)
    hem_wave(s, P, m, 'nv_dk')
    if P.d == DOWN:
        s.put({(13, P.ty0 + 1), (14, P.ty0 + 1)}, 'go')          # 領口金扣
    hm = head(s, P, SKIN)
    hair(s, P, HAIR2, hm)
    # 兩條小辮（在帽簷下面、耳朵兩側）
    if P.d != SIDE:
        for x in (P.hx0 - 1, P.hx1):
            s.part(rect(x, P.ey, x + 1, P.ey + 3), HAIR2, ol=True)
            s.px[(x, P.ey + 3)] = 'pm'
            s.px[(x + 1, P.ey + 3)] = 'pm'
    else:
        s.part(rect(P.hx1 - 1, P.ey, P.hx1, P.ey + 3), HAIR2, ol=True)
        s.px[(P.hx1 - 1, P.ey + 3)] = 'pm'
        s.px[(P.hx1, P.ey + 3)] = 'pm'
    face(s, P)
    witch_hat(s, P, hat, 'go', tall=10)
    if P.d == SIDE:
        hx, hy = arms(s, P, dress, SKIN, which='near')[True]
        pumpkin(hx - 1, hy)
    else:
        hd = arms(s, P, dress, SKIN)
        hx, hy = hd[1]
        if P.d == DOWN:
            pumpkin(hx, hy - 2)
        else:
            pumpkin(P.tx0 - 3, hd[-1][1])


# ─── 騎掃帚的魔女（broomwitch）────────────────────────

def draw_broomwitch(s, P):
    """
    騎掃帚低空飄的魔女：黑紫尖帽＋金帽帶、酒紅洋裝、薑紅髮。腳不著地，整個人跟掃帚一起上下浮、
    掃帚尾擺動（走路的四幀拿來當飄浮循環：0、-1、0、+1）。
    """
    dress = ('mr_hi', 'mr', 'mr_dk')
    hat = ('bk_hi', 'bk', 'bk_dk')
    ghair = ('gn_hi', 'gn', 'gn_dk')
    f = P.f
    P = Pose(P.d, 0, P.B)                       # 不走路：骨架用站姿，浮動最後整張平移
    lift = 5                                    # 平常離地幾格（最低的那幀也不碰地）
    float_y = (0, -1, 0, 1)[f]
    sway = (0, 1, 0, -1)[f]
    seat = P.ty1 + 1                            # 掃帚柄那一列（坐在上面）

    def fan(x0, x1, cy, h0, h1):
        """掃帚尾：從綁帶（x0，高 h0）往後張開成扇形（x1，高 h1），末端跟著 sway 上下擺。"""
        m = poly([(x0, cy - h0 / 2), (x1 + 1.0, cy - h1 / 2 + sway), (x1 + 1.0, cy + h1 / 2 + sway),
                  (x0, cy + h0 / 2)])
        return m

    def paint_fan(m, x0):
        s.part(m, ('go', 'go', 'go_dk'), ol=True)
        for x, y in m:                                   # 一根根的草：隔列畫深色條紋
            if (y + (x > x0 + 3)) % 2 == 0 and x >= x0 + 1 and (x, y - 1) in m and (x, y + 1) in m:
                s.px[(x, y)] = 'go_dk'

    def broom(mirror):
        """柄在前（左）、掃帚尾在後（右）；正面／側面同一個構圖，背面左右鏡射。"""
        hm = rect(2, seat, 19, seat + 1)
        tail = fan(19.5, 25, seat + 1.0, 3.0, 7.0)
        band = rect(18, seat - 1, 19, seat + 2)
        if mirror:
            hm, tail, band = mir(hm), mir(tail), mir(band)
        s.part(hm, ('gn_dk', 'mr_dk'), ol=True)
        paint_fan(tail, 20 if not mirror else 7)
        s.part(band, 'mr_hi', ol=True)

    if P.d == SIDE:
        arms(s, P, dress, SKIN, which='far', fixed=None)
        m = torso(s, P, dress, flare=1, hem=0)
        broom(False)
        # 坐姿：裙襬蓋在掃帚上，小腿從掃帚前面垂下來、腳尖朝前（左）
        s.part(rect(10, seat - 1, 17, seat - 1), dress, ol=True)
        s.part(rect(10, seat + 1, 11, seat + 2), 'bk_dk', ol=True)
        s.part(rect(8, seat + 3, 11, seat + 4), ('bk', 'bk', 'bk_dk'), ol=True)
    else:
        # 腿垂在掃帚下面，兩腳併攏微微晃
        broom(P.d == UP)
        for lx in (11, 15):
            s.part(rect(lx, P.ty1, lx + 1, seat + 3), 'bk_dk')
            s.part(rect(lx - (1 if lx == 11 else 0), seat + 4, lx + (1 if lx == 11 else 2), seat + 5), ('bk', 'bk', 'bk_dk'))
        m = torso(s, P, dress, flare=2, hem=0)
    hm = head(s, P, SKIN)
    hair(s, P, ghair, hm, long_back=1, locks=2)
    face(s, P)
    witch_hat(s, P, hat, 'go', tall=9, tip=-1, gem='mr_hi')
    if P.d == SIDE:
        hx, hy = arms(s, P, dress, SKIN, which='near', fixed=4)[True]
    else:
        arms(s, P, dress, SKIN)
    s.shifted(0, -lift + float_y)


# ─── 星空法師（mage）────────────────────────────────

def draw_mage(s, P):
    """星空斗篷的法師：深藍兜帽與長袍（金色小星星）、金髮、手持星星法杖。大人身材。"""
    robe = ('nv_hi', 'nv', 'nv_dk')

    def staff(x, ytop, ybot):
        s.part(rect(x, ytop + 1, x, ybot), ('bd_dk',), ol=True)
        s.part({(x, ytop - 1), (x - 1, ytop), (x, ytop), (x + 1, ytop), (x, ytop + 1)}, 'go_hi', ol=True)
        s.px[(x, ytop)] = 'wh'

    if P.d == UP:
        staff(P.tx1 + 2, P.hy0 + 1, FB - 2 + P.bob)
    if P.d == SIDE:
        arms(s, P, robe, SKIN, which='far')
    legs(s, P, ('nv_dk', 'nv_dk'), ('nv_dk', 'nv_dk', 'eye'))   # 鞋底用 'eye'，見 legs()
    m = torso(s, P, robe, flare=2, hem=P.leg - 2)
    hem_wave(s, P, m, 'nv_dk')
    stars = [(P.tx0 + 1, P.ty0 + 5), (P.tx1 - 1, P.ty0 + 8), (P.tx0 + 2, P.ty1 + 2),
             (P.tx1 - 2, P.ty0 + 3), (P.tx1 + 1, P.ty1 + 2)]
    for p in stars:
        if p in m:
            s.px[p] = 'go_hi'
    # 兜帽：比頭大一圈，頭頂微尖
    hood = ell(14.0, P.hcy - 0.5, P.hw / 2 + 1.5, P.hh / 2 + 1.0)
    hood |= {(13, P.hy0 - 2), (14, P.hy0 - 2)} if P.d != SIDE else {(16, P.hy0 - 2), (17, P.hy0 - 2)}
    s.part(hood, robe, ol=True, shade='ball', cuts=(0.85, 0.2))
    if P.d != UP:
        cx = 13.0 if P.d == SIDE else 14.0
        hm = ell(cx, P.hcy + 1.0, P.hw / 2 - 1, P.hh / 2 - 1)
        s.part(hm, SKIN, ol=True, shade='ball')
        # 瀏海：臉的上緣兩三列
        top = min(p[1] for p in hm)
        bang = {p for p in hm if p[1] <= top + 1}
        bang |= {(x, top + 2) for x in range(P.hx0, P.hx1 + 1) if x % 3 == 0 and (x, top + 2) in hm}
        if P.d == SIDE:
            bang |= {p for p in hm if p[0] >= 16}
        s.part(bang, ('bd_hi', 'bd', 'bd_dk'))
        face(s, P, dy=1, side_x=P.hx0 + 2)
        s.px[(14 if P.d == DOWN else 18, P.hy0 + 1)] = 'go_hi'
    else:
        for p in ((14, P.hy0 + 3), (11, P.hy0 + 7), (16, P.hy0 + 9)):
            s.px[p] = 'go_hi'
        s.put({(x, P.hy1 - 1) for x in range(11, 17)}, 'nv_dk')     # 兜帽下緣的摺痕
    if P.d == SIDE:
        hx, hy = arms(s, P, robe, SKIN, which='near', fixed=4)[True]
        staff(hx, P.hy0 + 1, FB - 2 + P.bob)
        s.part(rect(hx - 1, hy - 1, hx + 1, hy), SKIN)
    elif P.d == DOWN:
        hd = arms(s, P, robe, SKIN)
        hx, hy = hd[-1]
        staff(hx, P.hy0 + 1, FB - 2 + P.bob)
        s.part(rect(hx - 1, hy - 1, hx + 1, hy), SKIN)
    else:
        arms(s, P, robe, SKIN)


# ─── 旅人（traveler）────────────────────────────────

def draw_traveler(s, P):
    """提燈的旅人：棕色連帽長斗篷（兜帽放下堆在頸後）、棕髮圓眼鏡、背著捆了睡袋的背包、手提油燈。"""
    cloak = ('tr_hi', 'tr', 'tr_dk')

    def pack(x0, y0, w, h):
        pm = rect(x0, y0, x0 + w - 1, y0 + h - 1)
        s.part(pm, ('le', 'le', 'le_dk'), ol=True)
        s.put({(x, y0 + 2) for x in range(x0, x0 + w)}, 'le_dk')          # 袋蓋
        roll = rect(x0 - 1, y0 - 3, x0 + w, y0 - 1)
        s.part(roll, ('sc', 'sc', 'sc_dk'), ol=True)
        s.put({(x0 + 1, y) for y in range(y0 - 3, y0)} | {(x0 + w - 2, y) for y in range(y0 - 3, y0)}, 'le_dk')

    def lantern(x, y):
        # x,y＝手的左下角；燈掛在手下
        s.part({(x + 1, y + 1)}, 'hr_dk')
        body = rect(x, y + 2, x + 2, y + 5)
        s.part(body, ('hr_dk',), ol=True)
        s.px[(x + 1, y + 3)] = 'ft'
        s.px[(x + 1, y + 4)] = 'go'
        s.px[(x, y + 2)] = 'go'
        s.px[(x + 2, y + 2)] = 'go'

    if P.d == SIDE:
        arms(s, P, cloak, SKIN, which='far')
    legs(s, P, ('tr_dk', 'tr_dk'), SHOE)
    m = torso(s, P, cloak, flare=2, hem=P.leg - 2)
    hem_wave(s, P, m, 'tr_dk')
    if P.d == SIDE:
        pack(P.tx1, P.ty0 + 2, 4, 7)
    if P.d == DOWN:
        # 前襟一條深色、腰帶
        s.put({(14, y) for y in range(P.ty0 + 1, max(p[1] for p in m))}, 'tr_dk')
        s.put({(x, P.ty0 + 5) for x in range(P.tx0, P.tx1 + 1)}, 'le_dk')
        s.px[(13, P.ty0 + 5)] = 'go'
        s.put({(P.tx0 + 1, y) for y in range(P.ty0 + 1, P.ty0 + 5)}, 'le_dk')   # 背帶
        s.put({(P.tx1 - 1, y) for y in range(P.ty0 + 1, P.ty0 + 5)}, 'le_dk')
    if P.d == UP:
        pack(10, P.ty0 + 2, 8, 7)
    hm = head(s, P, SKIN)
    hair(s, P, HAIR2, hm, locks=1, top_frac=0.45)
    # 兜帽放下，堆在頸後（正面看是一圈領子）
    collar = rect(P.tx0 - 1, P.ty0 - 1, P.tx1 + 1, P.ty0 + 1) - ell(14.0, P.ty0 - 1.0, 3.0, 2.0)
    if P.d == UP:
        collar = rect(P.tx0, P.ty0 - 1, P.tx1, P.ty0 + 1)
    s.part(collar, cloak, ol=True)
    face(s, P, blush=False)
    if P.d == DOWN:
        # 圓眼鏡：只畫上框＋鼻樑＋鏡片反光（整圈框在這個解析度會把臉蓋掉）
        for ex in (11, 16):
            s.put({(ex - 1, P.ey - 1), (ex, P.ey - 1), (ex + 1, P.ey - 1)}, 'hr_dk')
            s.px[(ex + 1, P.ey)] = 'wh'
        s.put({(13, P.ey), (14, P.ey)}, 'hr_dk')
    elif P.d == SIDE:
        ex = P.hx0 + 2
        s.put({(ex - 1, P.ey - 1), (ex, P.ey - 1), (ex + 1, P.ey - 1), (ex + 2, P.ey), (ex + 3, P.ey)}, 'hr_dk')
        s.px[(ex - 1, P.ey)] = 'wh'
    if P.d == SIDE:
        hx, hy = arms(s, P, cloak, SKIN, which='near', fixed=3)[True]
        lantern(hx - 1, hy - 1)
    else:
        hd = arms(s, P, cloak, SKIN)
        if P.d == DOWN:
            lantern(hd[1][0], hd[1][1] - 1)
        else:
            lantern(hd[-1][0] - 1, hd[-1][1] - 1)


# ─── 青蛙（frog）────────────────────────────────

def draw_frog(s, P):
    """穿黃雨衣、背釣竿的青蛙：寬寬的綠臉、頭頂兩顆凸眼、一條笑線。"""
    green = ('fg_hi', 'fg', 'fg_dk')
    coat = ('ry_hi', 'ry', 'ry_dk')

    def rod(front):
        # 釣竿斜插在背上：正面從左肩後面伸出來，背面在背上（鏡射），側面往後上方
        # 正面／背面：拿在手上（手的外側往上斜）；側面：斜背在背上（往後上方伸出去）
        if P.d == DOWN:
            pts, out = line(8, P.ty0 + 6, 4, P.hy0 - 1), -1
        elif P.d == UP:
            pts, out = mir(line(8, P.ty0 + 6, 4, P.hy0 - 1)), 1
        else:
            pts, out = line(15, P.ty0 + 4, 24, P.hy0 - 1), 1
        s.part(pts, ('wd', 'wd_dk'), ol=True)
        tip = min(pts, key=lambda p: p[1])
        lx = tip[0] + out
        sway = (0, 1, 0, -1)[P.f] if P.step else 0
        s.put({(lx, tip[1] + k) for k in range(0, 4)}, 'li')
        s.part({(lx + (sway if P.d != SIDE else 0), tip[1] + 4), (lx + (sway if P.d != SIDE else 0), tip[1] + 5)}, 'mu', ol=True)
        s.px[(lx + (sway if P.d != SIDE else 0), tip[1] + 5)] = 'wh'

    if P.d == SIDE:
        rod(False)
        arms(s, P, coat, green, which='far')
    legs(s, P, green, ('fg', 'fg', 'fg_dk'), foot_w=3)
    m = torso(s, P, coat, flare=2, hem=1)
    hem_wave(s, P, m, 'ry_dk')
    if P.d == DOWN:
        s.put({(14, y) for y in range(P.ty0 + 1, P.ty1 + 2)}, 'ry_dk')
        for y in (P.ty0 + 2, P.ty0 + 5):
            s.px[(13, y)] = 'wd_dk'
    if P.d == UP:
        s.put({(14, y) for y in range(P.ty0 + 1, P.ty1 + 2)} & m, 'ry_dk')
    # 頭：寬扁
    hm = head(s, P, green, dy=0.5)
    if P.d == SIDE:
        bulges = [(11.5, P.hy0 + 1.0)]
    else:
        bulges = [(10.0, P.hy0 + 1.0), (18.0, P.hy0 + 1.0)]
    for bx, by in bulges:
        s.part(ell(bx, by, 2.6, 2.6), green, ol=True, shade='ball')
        if P.d != UP:
            bx0 = int(bx) - 1
            s.put(rect(bx0, int(by) - 1, bx0 + 1, int(by)), 'wh')
            s.px[(bx0 + (1 if P.d == DOWN and bx < 14 else 0) if P.d == DOWN else bx0, int(by) - 1)] = 'eye'
            s.px[(bx0 + (1 if P.d == DOWN and bx < 14 else 0) if P.d == DOWN else bx0, int(by))] = 'eye'
    if P.d == DOWN:
        my = P.hy1 - 2
        s.put({(x, my) for x in range(11, 17)}, 'fg_dk')
        s.px[(10, my - 1)] = 'fg_dk'
        s.px[(17, my - 1)] = 'fg_dk'
        for x in (8, 9, 18, 19):
            s.px[(x, my - 1)] = 'blush'
        # 雨衣領子
        s.part({(10, P.ty0), (11, P.ty0), (16, P.ty0), (17, P.ty0)}, 'ry_hi')
    elif P.d == SIDE:
        my = P.hy1 - 2
        s.put({(x, my) for x in range(P.hx0 + 1, P.hx0 + 5)}, 'fg_dk')
        s.px[(P.hx0 + 4, my - 1)] = 'fg_dk'
        s.px[(P.hx0 + 3, my - 2)] = 'blush'
        s.px[(P.hx0 + 4, my - 2)] = 'blush'
    if P.d == SIDE:
        arms(s, P, coat, green, which='near')
    else:
        arms(s, P, coat, green)
        rod(True)


FROG = dict(leg=2, th=8, tw=10, hw=16, hh=10, arm=5)


# ─── 狐狸（fox）────────────────────────────────

def fox_tail(s, P):
    fur = ('fx_hi', 'fx', 'fx_dk')
    wag = (0, 1, 0, -1)[P.f]
    if P.d == DOWN:
        m = leaf(P.tx1 - 1, P.ty1 + 1, P.tx1 + 6, P.ty0 - 1 + wag, 6, sharp=0.6)
        tipz = lambda p: p[1] <= P.ty0 + 1 + wag
    elif P.d == SIDE:
        m = leaf(16, P.ty1, 25, P.ty0 + 1 + wag, 7, sharp=0.6)
        tipz = lambda p: p[0] >= 23
    else:
        m = leaf(14, P.ty0 + 4, 18 + wag, P.ty1 + 3, 7, sharp=0.6)
        tipz = lambda p: p[1] >= P.ty1 + 1
    s.part(m, fur, ol=True)
    s.put({p for p in m if tipz(p)}, 'cr')


def fox_ears(s, P, inner='fx_dk'):
    if P.d == SIDE:
        e = poly([(14.5, P.hy0 + 2.5), (17.0, P.hy0 - 3.0), (19.5, P.hy0 + 2.5)])
        s.part(e, ('fx_hi', 'fx', 'fx_dk'), ol=True)
        return
    e = poly([(P.hx0 + 0.5, P.hy0 + 3.5), (P.hx0 + 1.5, P.hy0 - 3.0), (P.hx0 + 5.5, P.hy0 + 1.0)])
    for m in (e, mir(e)):
        s.part(m, ('fx_hi', 'fx', 'fx_dk'), ol=True)
        if P.d == DOWN:
            xs = sorted({p[0] for p in m})
            s.put({p for p in m if p[0] in xs[1:3] and p[1] >= P.hy0 - 1} & m, 'cr_dk')


def draw_fox(s, P):
    """披星星斗篷、提籃子的狐狸：尖耳、白腮、大尾巴（白尾尖）。"""
    fur = ('fx_hi', 'fx', 'fx_dk')
    cape = ('nv_hi', 'nv', 'nv_dk')

    def basket(x, y):
        # x,y＝手的左下角，籃子掛在手下面
        hd = {(x - 1, y), (x - 1, y + 1), (x + 2, y), (x + 2, y + 1), (x, y - 1), (x + 1, y - 1)}
        s.part(hd, 'le_dk')
        b = rect(x - 2, y + 2, x + 3, y + 4)
        s.part(b, ('le', 'le', 'le_dk'), ol=True)
        for bx in range(x - 2, x + 4):
            if (bx + y) % 2 == 0:
                s.px[(bx, y + 3)] = 'le_dk'
        s.put({(x - 1, y + 1), (x, y + 1), (x + 1, y + 1)}, 'mu')         # 籃子裡的紅果子
        s.px[(x + 2, y + 1)] = 'mu'

    if P.d != UP:
        fox_tail(s, P)
    if P.d == SIDE:
        arms(s, P, cape, fur, which='far')
    legs(s, P, ('fx_dk', 'fx_dk'), ('nv_dk', 'nv_dk', 'eye'))   # 鞋底用 'eye'，見 legs()
    m = torso(s, P, cape, flare=2, hem=1)
    hem_wave(s, P, m, 'nv_dk')
    for p in ((P.tx0, P.ty0 + 4), (P.tx1, P.ty0 + 6), (P.tx0 + 2, P.ty1 + 1), (P.tx1 - 1, P.ty0 + 2)):
        if p in m:
            s.px[p] = 'go_hi'
    if P.d == DOWN:
        chest = ell(14.0, P.ty0 + 2.0, 2.0, 2.5) & m
        s.part(chest, ('cr', 'cr', 'cr_dk'))
        s.px[(13, P.ty0)] = 'go'
        s.px[(14, P.ty0)] = 'go'
    if P.d == UP:
        fox_tail(s, P)
    fox_ears(s, P)
    hm = head(s, P, fur)
    if P.d == DOWN:
        cheeks = (ell(10.5, P.hy1 - 1.5, 3.0, 2.2) | ell(17.5, P.hy1 - 1.5, 3.0, 2.2) |
                  ell(14.0, P.hy1 - 0.5, 3.0, 2.0)) & hm
        s.part(cheeks, ('cr', 'cr', 'cr_dk'))
        face(s, P, nose='eye', blush=False)
        s.px[(9, P.ey + 2)] = 'blush'
        s.px[(18, P.ey + 2)] = 'blush'
    elif P.d == SIDE:
        s.part((ell(P.hx0 + 3.5, P.hy1 - 1.5, 3.0, 2.0) & hm), ('cr', 'cr', 'cr_dk'))
        side_snout(s, P, ('cr', 'cr', 'cr_dk'), length=3)
        face(s, P, side_x=P.hx0 + 3, blush=False)
        s.px[(P.hx0 + 5, P.ey + 2)] = 'blush'
    if P.d == SIDE:
        hx, hy = arms(s, P, cape, fur, which='near')[True]
        basket(hx, hy)
    else:
        hd = arms(s, P, cape, fur)
        if P.d == DOWN:
            basket(hd[-1][0], hd[-1][1])


FOX = dict(leg=2, th=8, tw=10, hw=14, hh=11, arm=5)


# ─── 兔子（rabbit）────────────────────────────────

def rabbit_ears(s, P, fur, inner=True, base=None):
    by = P.hy0 + 2 if base is None else base
    if P.d == SIDE:
        for dx, col in ((2, fur[-1]), (0, None)):
            e = leaf(15 + dx, by + 1, 19 + dx, by - 9, 4.2, sharp=0.5)
            if col:
                s.part(e, col, ol=True)
            else:
                s.part(e, fur, ol=True)
                if inner:
                    s.put({p for p in e if p[0] == min(q[0] for q in e if q[1] == p[1]) + 1 and p[1] < by - 1}, 'pink_in')
        return
    e = ell(11.0, by - 4.5, 1.8, 5.5)
    for m in (e, mir(e)):
        s.part(m, fur, ol=True)
        if inner and P.d == DOWN:
            cx = sorted({p[0] for p in m})
            s.put({p for p in m if p[0] == cx[len(cx) // 2] and by - 8 <= p[1] <= by - 2}, 'pink_in')


def draw_rabbit(s, P):
    """背郵差包的兔子：奶油色毛、長耳朵（粉紅內側）、白襯衫＋藍吊帶褲、圓尾巴。"""
    fur = ('cr', 'cr', 'cr_dk')
    over = ('ov_hi', 'ov', 'ov_dk')
    shirt = ('wh', 'wh', 'li_dk')

    def satchel(x, y):
        b = rect(x, y, x + 3, y + 3)
        s.part(b, ('le', 'le', 'le_dk'), ol=True)
        s.put({(x, y), (x + 1, y), (x + 2, y), (x + 3, y)}, 'le_dk')
        s.px[(x + 1, y + 1)] = 'le_dk'

    if P.d == SIDE:
        arms(s, P, shirt, fur, which='far')
    legs(s, P, over, ('le', 'le', 'le_dk'))
    m = torso(s, P, shirt)
    lower = {p for p in m if p[1] >= P.ty0 + 4}
    s.part(lower, over)
    if P.d != SIDE:
        for x in (P.tx0 + 1, P.tx1 - 1):
            s.put({(x, y) for y in range(P.ty0, P.ty0 + 4)}, 'ov')
        if P.d == DOWN:
            s.px[(P.tx0 + 1, P.ty0 + 4)] = 'ov_hi'
            s.px[(P.tx1 - 1, P.ty0 + 4)] = 'ov_hi'
            s.put({(14, P.ty0 + 6), (13, P.ty0 + 6)}, 'ov_dk')     # 口袋
    else:
        s.put({(15, y) for y in range(P.ty0, P.ty0 + 4)}, 'ov')
    # 郵差包背帶：從左肩斜到右腰
    if P.d == DOWN:
        s.put(line(P.tx0, P.ty0 + 1, P.tx1, P.ty0 + 6), 'le_dk')
    elif P.d == UP:
        s.put(line(P.tx1, P.ty0 + 1, P.tx0, P.ty0 + 6), 'le_dk')
        s.part(ell(14.0, P.ty1 - 0.5, 1.8, 1.8), fur, ol=True)          # 圓尾巴
    rabbit_ears(s, P, fur)
    hm = head(s, P, fur)
    if P.d == DOWN:
        face(s, P, nose='pink_in')
        s.px[(13, P.ey + 3)] = 'cr_dk'
        s.px[(14, P.ey + 3)] = 'cr_dk'
    elif P.d == SIDE:
        face(s, P, side_x=P.hx0 + 2)
        s.px[(min(p[0] for p in hm if p[1] == P.ey + 2), P.ey + 2)] = 'pink_in'
    if P.d == SIDE:
        satchel(P.tx1 - 2, P.ty0 + 4)
        arms(s, P, shirt, fur, which='near')
    else:
        hd = arms(s, P, shirt, fur)
        if P.d == DOWN:
            satchel(P.tx1 + 1, P.ty0 + 5)
        else:
            satchel(P.tx0 - 4, P.ty0 + 5)


RABBIT = dict(leg=3, th=8, tw=10, hw=14, hh=11, arm=6)


# ─── 刺蝟（hedgehog）────────────────────────────────

def spiky(cx, cy, rx, ry, a0, a1, n, out=2.6):
    """鋸齒刺：沿橢圓從角度 a0 到 a1，交錯放外圈（刺尖）與內圈的點。"""
    pts = [(cx, cy)]
    for i in range(n * 2 + 1):
        a = math.radians(a0 + (a1 - a0) * i / (n * 2))
        r = 1.0 + (out / min(rx, ry) if i % 2 == 1 else 0.0)
        pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    return poly(pts)


def draw_hedgehog(s, P):
    """
    戴酒紅貝雷帽、繫藍圍巾的刺蝟：頭跟身體是一整顆圓滾滾的棕色刺球（外緣一圈刺尖），
    正面中間露出奶油色的臉（上緣是往下戳的瀏海刺）、小圓耳、黑鼻頭；側面是尖尖的吻部。
    """
    sp = ('hg_hi', 'hg', 'hg_dk')
    skin = ('cr', 'cr', 'cr_dk')
    beret = ('mr_hi', 'mr', 'mr_dk')
    cy = (P.hy0 + P.ty1) / 2 + 1.0              # 刺球中心（頭跟身體合成一顆）

    def ticks(m):
        # 刺的紋路：斜斜的短深色點，只畫在內部
        for x, y in m:
            if (x + 2 * y) % 4 == 0 and {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} <= m:
                s.px[(x, y)] = 'hg_dk'

    def hands(xs, y):
        for x in xs:
            s.part(rect(x, y, x + 1, y + 1), skin, ol=True)

    legs(s, P, ('hg', 'hg_dk'), ('hg_dk', 'hg_dk', 'eye'))   # 鞋底用 'eye'，見 legs()
    if P.d == DOWN:
        ball = spiky(14.0, cy, 8.5, 9.0, 150, 390, 8, out=2.2) | ell(14.0, cy, 8.0, 8.5)
        s.part(ball, sp, ol=True, shade='ball', cuts=(0.85, 0.2))
        ticks(ball)
        s.part(ell(14.0, P.ty1 - 1.5, 4.0, 3.0), skin, ol=True)          # 肚子
        # 臉：橢圓，上緣鋸齒（往下戳的瀏海刺）
        fc = ell(14.0, P.hcy + 2.0, 5.5, 4.2)
        top = min(p[1] for p in fc)
        fc -= {(x, y) for x, y in fc if y == top or (y == top + 1 and x % 3 == 1)}
        s.part(fc, skin)
        for ex in (9.0, 19.0):                                           # 小圓耳
            s.part(ell(ex, P.hy0 + 3.5, 1.6, 1.6), skin, ol=True)
        ey = P.hy0 + 6
        for x in (11, 16):
            s.px[(x, ey)] = 'eye'
            s.px[(x, ey + 1)] = 'eye'
        s.put({(9, ey + 2), (10, ey + 2), (17, ey + 2), (18, ey + 2)}, 'blush')
        s.put({(13, ey + 2), (14, ey + 2)}, 'eye')                     # 黑鼻頭
        hands((P.tx0 - 1, P.tx1), P.ty0 + 3)
    elif P.d == SIDE:
        ball = spiky(15.0, cy, 8.0, 9.0, -125, 55, 7, out=2.2) | ell(15.0, cy, 7.5, 8.5)
        s.part(ball, sp, ol=True, shade='ball', cuts=(0.85, 0.2))
        ticks(ball)
        s.part(ell(11.5, P.ty1 - 1.5, 3.0, 3.0), skin, ol=True)          # 肚子
        fc = ell(11.0, P.hcy + 2.0, 4.0, 4.0) | leaf(10, P.hy0 + 8, 4, P.hy0 + 8, 3.6, sharp=0.5)
        s.part(fc, skin, ol=True)
        nx = min(p[0] for p in fc)
        s.px[(nx, P.hy0 + 7)] = 'eye'
        s.px[(nx, P.hy0 + 8)] = 'eye'
        s.part(ell(14.0, P.hy0 + 3.5, 1.6, 1.6), skin, ol=True)
        s.px[(9, P.hy0 + 5)] = 'eye'
        s.px[(9, P.hy0 + 6)] = 'eye'
        s.px[(10, P.hy0 + 8)] = 'blush'
        s.px[(11, P.hy0 + 8)] = 'blush'
        hands((11 - P.near_off // 2,), P.ty0 + 3)
    else:
        ball = spiky(14.0, cy, 8.5, 9.0, 150, 390, 8, out=2.2) | ell(14.0, cy, 8.0, 8.5)
        s.part(ball, sp, ol=True, shade='ball', cuts=(0.85, 0.2))
        ticks(ball)
    # 圍巾（正面打結垂一段，背面看得到結尾巴）
    s.part(rect(P.tx0, P.ty0, P.tx1, P.ty0 + 1), ('sc_hi', 'sc', 'sc_dk'), ol=True)
    if P.d == DOWN:
        s.part(rect(15, P.ty0 + 2, 16, P.ty0 + 3), ('sc', 'sc_dk'), ol=True)
    elif P.d == UP:
        s.part(rect(12, P.ty0 + 2, 13, P.ty0 + 4), ('sc', 'sc_dk'), ol=True)
    else:
        s.part(rect(P.tx1, P.ty0 + 2, P.tx1 + 1, P.ty0 + 3 + (P.f % 2)), ('sc', 'sc_dk'), ol=True)
    # 貝雷帽（往一邊歪，頂上一根小梗）
    bx = {DOWN: 13.0, SIDE: 15.0, UP: 15.0}[P.d]
    s.part(ell(bx, P.hy0 - 0.5, 6.0, 2.2), beret, ol=True)
    s.part({(int(bx), P.hy0 - 3), (int(bx), P.hy0 - 2)}, 'mr_dk', ol=True)


HEDGEHOG = dict(leg=2, th=6, tw=10, hw=14, hh=11, arm=4)


# ─── 鹿（deer）────────────────────────────────

def draw_deer(s, P):
    """戴花冠、披葉子斗篷的小鹿：小鹿角、橫的大耳朵、奶油色吻部、背上白斑。"""
    fur = ('dr_hi', 'dr', 'dr_dk')
    lf = ('lf_hi', 'lf', 'lf_dk')

    def antlers():
        if P.d == SIDE:
            a = line(15, P.hy0 + 1, 17, P.hy0 - 3) | line(16, P.hy0 - 1, 19, P.hy0 - 2) | {(18, P.hy0 - 4)}
            s.part(a, ('cr', 'cr_dk'), ol=True)
            return
        a = line(11, P.hy0 + 1, 9, P.hy0 - 3) | line(10, P.hy0 - 1, 7, P.hy0 - 2) | {(10, P.hy0 - 4)}
        s.part(sym(a), ('cr', 'cr_dk'), ol=True)

    def ears():
        # 鹿耳：大片、往兩側斜下垂的葉片形（圓耳會變熊）
        if P.d == SIDE:
            e = leaf(16, P.hy0 + 4, 22, P.hy0 + 6, 4.0, sharp=0.6)
            s.part(e, fur, ol=True)
            return
        e = leaf(P.hx0 + 2, P.hy0 + 4, P.hx0 - 4, P.hy0 + 6, 4.0, sharp=0.6)
        for m in (e, mir(e)):
            s.part(m, fur, ol=True)
            if P.d == DOWN:
                cy = P.hy0 + 5
                s.put({p for p in m if p[1] == cy and (P.hx0 - 3 <= p[0] <= P.hx0 - 1 or
                                                       P.hx1 + 1 <= p[0] <= P.hx1 + 3)}, 'pink')

    def crown():
        cols = ('pink', 'wh', 'go_hi', 'pink', 'wh', 'go_hi', 'pink')
        y = P.hy0 + 1
        if P.d == SIDE:
            xs = range(11, 19)
        else:
            xs = range(P.hx0 + 1, P.hx1)
        for i, x in enumerate(xs):
            if (x, y) in hm or (x, y + 1) in hm:
                s.px[(x, y)] = 'lf' if i % 2 else cols[(i // 2) % len(cols)]
                if i % 2 == 0:
                    s.px[(x, y - 1)] = cols[(i // 2) % len(cols)]

    def mantle():
        # 葉子披肩：肩上一圈，下緣是一片片葉尖
        y0, y1 = P.ty0, P.ty0 + 3
        m = rect(P.tx0 - 2, y0, P.tx1 + 2, y1)
        for x in range(P.tx0 - 2, P.tx1 + 3):
            if (x - P.tx0) % 3 == 1:
                m.add((x, y1 + 1))
        s.part(m, lf, ol=True)
        for x in range(P.tx0 - 2, P.tx1 + 3, 3):
            s.px[(x, y0 + 1)] = 'lf_dk'
            s.px[(x + 1, y0 + 2)] = 'lf_dk'

    if P.d == SIDE:
        arms(s, P, fur, fur, which='far', hand=False)
    legs(s, P, ('dr', 'dr_dk'), ('dr_dk', 'dr_dk', 'eye'))   # 鞋底用 'eye'，見 legs()
    m = torso(s, P, fur)
    if P.d == DOWN:
        s.part(ell(14.0, P.ty1 - 1.0, 2.5, 2.5) & m, ('cr',))
    if P.d == UP:
        for p in ((11, P.ty0 + 5), (16, P.ty0 + 6), (13, P.ty1 - 1)):
            s.px[p] = 'wh'
        s.part({(13, P.ty1 - 1), (14, P.ty1 - 1), (13, P.ty1), (14, P.ty1)}, 'wh', ol=True)   # 白尾巴
    elif P.d == SIDE:
        for p in ((15, P.ty0 + 5), (13, P.ty1 - 1)):
            s.px[p] = 'wh'
        s.part({(P.tx1 + 1, P.ty0 + 4), (P.tx1 + 1, P.ty0 + 5)}, 'wh', ol=True)
    antlers()
    ears()
    hm = head(s, P, fur)
    if P.d == DOWN:
        mz = ell(14.0, P.hy1 - 1.0, 3.0, 2.4) & hm
        s.part(mz, ('cr', 'cr', 'cr_dk'))
        face(s, P, blush=True, dy=-1)
        s.px[(13, P.hy1 - 2)] = 'eye'
        s.px[(14, P.hy1 - 2)] = 'eye'
    elif P.d == SIDE:
        side_snout(s, P, ('cr',), length=3, nose='eye')
        face(s, P, side_x=P.hx0 + 3)
    crown()
    mantle()
    if P.d == SIDE:
        arms(s, P, fur, fur, which='near', hand=False)
    else:
        arms(s, P, fur, fur, hand=False)
        if P.d == DOWN:
            # 胸前的葉子別針
            s.part({(13, P.ty0 + 3), (14, P.ty0 + 3)}, 'pink')


DEER = dict(leg=3, th=8, tw=10, hw=12, hh=12, arm=5)


# ─── 妖精（fairy）────────────────────────────────

def draw_fairy(s, P):
    """蘑菇帽的妖精：紅底白點的大蘑菇帽、葉子裙、背上兩對透明翅膀（會拍）、拿一根發光小樹枝。"""
    cap = ('mu_hi', 'mu', 'mu_dk')
    dress = ('lf', 'lf', 'lf_dk')
    flap = (0, 1, 0, 1)[P.f]

    def wings():
        if P.d == SIDE:
            up = leaf(16, P.ty0 + 1, 25, P.ty0 - 5 + flap, 6, sharp=0.7)
            lo = leaf(16, P.ty0 + 3, 23, P.ty0 + 6 + flap, 4, sharp=0.7)
            for m in (lo, up):
                s.part(m, ('wh', 'wg', 'wg_dk'), ol=True)
            return
        up = leaf(12, P.ty0 + 1, 2, P.ty0 - 5 + flap, 6, sharp=0.7)
        lo = leaf(12, P.ty0 + 3, 4, P.ty0 + 6 + flap, 4, sharp=0.7)
        for m in (lo, mir(lo), up, mir(up)):
            s.part(m, ('wh', 'wg', 'wg_dk'), ol=True)

    def wand(x, y, out=1):
        pts = line(x, y, x + 2 * out, y - 5)
        s.part(pts, ('hr', 'hr_dk'), ol=True)
        tip = min(pts, key=lambda p: p[1])
        sparkle(s, tip[0], tip[1] - 2)

    if P.d == DOWN or P.d == SIDE:
        wings()
    if P.d == SIDE:
        arms(s, P, SKIN, SKIN, which='far', hand=False)
    legs(s, P, SKIN, SHOE)
    m = torso(s, P, dress, flare=2, hem=1)
    # 葉子裙的鋸齒下襬
    y1 = max(p[1] for p in m)
    for x, y in list(m):
        if y == y1 and (x + P.f) % 3 == 0:
            s.px.pop((x, y), None)
    s.put({(14, y) for y in range(P.ty0 + 2, y1)} & m, 'lf_dk')
    hm = head(s, P, SKIN)
    hair(s, P, HAIR2, hm, locks=2, long_back=1)
    face(s, P)
    if P.d == UP:
        wings()
    # 蘑菇帽：半圓頂＋奶油色菇褶
    ctop = P.hy0 - 2
    dome = {p for p in ell(14.0, P.hy0 + 3.0, 9.0, 6.0) if p[1] <= P.hy0 + 3}
    s.part(dome, cap, ol=True, shade='ball', cuts=(0.85, 0.25))
    gill = rect(6, P.hy0 + 4, 21, P.hy0 + 4) - {(6, P.hy0 + 4), (21, P.hy0 + 4)}
    s.part(gill, ('sk', 'sk_dk'), ol=True)
    dots = [(10, P.hy0 + 1), (14, P.hy0 - 1), (17, P.hy0 + 2), (7, P.hy0 + 3), (19, P.hy0)]
    if P.d == SIDE:
        dots = [(9, P.hy0 + 1), (13, P.hy0 - 1), (17, P.hy0 + 1), (20, P.hy0 + 3)]
    elif P.d == UP:
        dots = [(11, P.hy0 + 2), (15, P.hy0), (18, P.hy0 + 2), (8, P.hy0 + 1)]
    for x, y in dots:
        for p in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)):
            if p in dome:
                s.px[p] = 'wh'
    _ = ctop
    if P.d == SIDE:
        hx, hy = arms(s, P, SKIN, SKIN, which='near', hand=False, fixed=3)[True]
        wand(hx, hy - 1, out=-1)
    else:
        hd = arms(s, P, SKIN, SKIN, hand=False)
        if P.d == DOWN:
            wand(hd[1][0] + 1, hd[1][1] - 1)


FAIRY = dict(leg=2, th=7, tw=8, hw=12, hh=11, arm=5)


# ─── 兔子魔女（rabbitwitch）────────────────────────────

def draw_rabbitwitch(s, P):
    """戴淡紫尖帽（耳朵從帽子穿出來）、穿紫袍的白兔魔女，側背小包、手捧一本魔法書。"""
    fur = ('cr', 'cr', 'cr_dk')
    robe = ('wp_hi', 'wp', 'wp_dk')
    hat = ('lv_hi', 'lv', 'lv_dk')

    def book(x, y):
        b = rect(x, y, x + 3, y + 2)
        s.part(b, ('mr', 'mr', 'mr_dk'), ol=True)
        s.px[(x + 1, y + 1)] = 'go'

    if P.d == SIDE:
        arms(s, P, robe, fur, which='far')
    legs(s, P, fur, fur)
    m = torso(s, P, robe, flare=2, hem=0)
    hem_wave(s, P, m, 'wp_dk')
    if P.d == DOWN:
        s.put({(13, P.ty0 + 1), (14, P.ty0 + 1), (13, P.ty0 + 2), (14, P.ty0 + 2)}, 'go')
    hm = head(s, P, fur)
    if P.d == DOWN:
        face(s, P, nose='pink_in')
    elif P.d == SIDE:
        face(s, P)
        s.px[(min(p[0] for p in hm if p[1] == P.ey + 2), P.ey + 2)] = 'pink_in'
    witch_hat(s, P, hat, 'wp', tall=9, brim_w=P.hw + 4, tip=1, by=P.hy0 + 2, base=3.5)
    by = P.hy0 + 1
    if P.d == SIDE:
        rabbit_ears(s, P, fur, base=by)
    else:
        e = leaf(10, by, 7, by - 9, 4.0, sharp=0.5)
        for m in (e, mir(e)):
            s.part(m, fur, ol=True)
            if P.d == DOWN:
                for y in range(by - 7, by - 1):
                    xs = sorted(p[0] for p in m if p[1] == y)
                    if len(xs) >= 3:
                        s.px[(xs[len(xs) // 2], y)] = 'pink_in'
    if P.d == SIDE:
        hx, hy = arms(s, P, robe, fur, which='near', fixed=3)[True]
        book(hx - 2, hy - 2)
    else:
        hd = arms(s, P, robe, fur)
        if P.d == DOWN:
            book(hd[1][0] - 1, hd[1][1] - 1)


RWITCH = dict(leg=2, th=8, tw=10, hw=14, hh=11, arm=6, eye=0.6)


CHARS = [
    ('frog', FROG, draw_frog),
    ('fox', FOX, draw_fox),
    ('rabbit', RABBIT, draw_rabbit),
    ('hedgehog', HEDGEHOG, draw_hedgehog),
    ('witch', KID, draw_witch),
    ('deer', DEER, draw_deer),
    ('broomwitch', KID, draw_broomwitch),
    ('fairy', FAIRY, draw_fairy),
    ('traveler', ADULT, draw_traveler),
    ('mage', ADULT, draw_mage),
    ('rabbitwitch', RWITCH, draw_rabbitwitch),
]


# ═══════════════════════════════ 輸出 ═══════════════════════════════

def to_image(grid):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    pix = im.load()
    for y in range(H):
        for x in range(W):
            c = grid[y][x]
            if c is not None:
                pix[x, y] = rgb(c) + (255,)
    return im


def render(name, B, fn):
    sheet = Image.new('RGBA', (W * COLS, H * ROWS), (0, 0, 0, 0))
    colors = set()
    cells = {}
    for d in (DOWN, SIDE, UP):
        for f in range(COLS):
            s = Spr()
            fn(s, Pose(d, f, B))
            grid = s.finish(f'{name}[{d},{f}]')
            colors |= {PAL[c] for row in grid for c in row if c is not None}
            im = to_image(grid)
            cells[(d, f)] = im
            sheet.alpha_composite(im, (f * W, d * H))
    big = sheet.resize((W * COLS * SCALE, H * ROWS * SCALE), Image.NEAREST)
    return big, cells, len(colors)


def render_all():
    out = []
    errs = []
    for name, B, fn in CHARS:
        try:
            big, cells, nc = render(name, B, fn)
        except AssertionError as e:
            errs.append(str(e))
            continue
        out.append((name, big, cells, nc))
    if errs:
        sys.exit('\n'.join(errs))
    return out


def md5(p):
    with open(p, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


# ─────────── 預覽 ───────────

DARK = (38, 30, 44)
GRASS = (112, 158, 82)


def preview(arts, outdir):
    """
    sheets_dark.png / sheets_grass.png —— 11 張走路表（輸出尺寸 ×1）排在一起；
    gif_<名字>_<方向>.gif —— 8fps、輸出 ×4；frames_<名字>.png —— 同內容的 4 幀並排（看不到動態時用）；
    all_down.gif ／ all_down_frames.png —— 全部角色朝下走；
    scene_town.png ／ scene_shop.png —— 照遊戲內縮放跟女巫站在一起（整張再 ×2 方便看）。
    """
    os.makedirs(outdir, exist_ok=True)
    font = find_font(16)
    files = []
    cw, ch = W * COLS * SCALE, H * ROWS * SCALE
    per_row = 4
    for tag, bg, fg in (('dark', DARK, (236, 228, 214)), ('grass', GRASS, (30, 30, 30))):
        rows = (len(arts) + per_row - 1) // per_row
        sheet = Image.new('RGBA', (per_row * (cw + 16) + 16, rows * (ch + 30) + 10), bg + (255,))
        d = ImageDraw.Draw(sheet)
        for i, (name, big, cells, nc) in enumerate(arts):
            x0, y0 = 16 + (i % per_row) * (cw + 16), 10 + (i // per_row) * (ch + 30)
            sheet.alpha_composite(big, (x0, y0))
            d.text((x0, y0 + ch + 4), f'{name}  {nc}色', fill=fg, font=font)
        p = os.path.join(outdir, f'sheets_{tag}.png')
        sheet.save(p)
        files.append(p)

    gz = SCALE * 4
    for name, big, cells, nc in arts:
        strip = Image.new('RGBA', (W * gz * COLS + 10 * 3, H * gz * ROWS + 10 * 2), GRASS + (255,))
        for di, dn in ((DOWN, 'down'), (SIDE, 'side'), (UP, 'up')):
            frames = []
            for f in range(COLS):
                fr = Image.new('RGBA', (W * gz, H * gz), GRASS + (255,))
                fr.alpha_composite(cells[(di, f)].resize((W * gz, H * gz), Image.NEAREST))
                frames.append(fr.convert('RGB'))
                strip.paste(fr, (f * (W * gz + 10), di * (H * gz + 10)))
            p = os.path.join(outdir, f'gif_{name}_{dn}.gif')
            frames[0].save(p, save_all=True, append_images=frames[1:], duration=125, loop=0)
            files.append(p)
        p = os.path.join(outdir, f'frames_{name}.png')
        strip.save(p)
        files.append(p)

    gz2 = SCALE * 2
    n = len(arts)
    frames = []
    for f in range(COLS):
        fr = Image.new('RGBA', (n * W * gz2, H * gz2), GRASS + (255,))
        for i, (name, big, cells, nc) in enumerate(arts):
            fr.alpha_composite(cells[(DOWN, f)].resize((W * gz2, H * gz2), Image.NEAREST), (i * W * gz2, 0))
        frames.append(fr.convert('RGB'))
    p = os.path.join(outdir, 'all_down.gif')
    frames[0].save(p, save_all=True, append_images=frames[1:], duration=125, loop=0)
    files.append(p)
    strip = Image.new('RGB', (n * W * gz2, COLS * H * gz2), GRASS)
    for f, fr in enumerate(frames):
        strip.paste(fr, (0, f * H * gz2))
    p = os.path.join(outdir, 'all_down_frames.png')
    strip.save(p)
    files.append(p)

    files += scene_preview(arts, outdir)
    return files


def witch_idle():
    """主角女巫朝下站立格（witch8/base.png 第 0 列第 0 欄，49×66），×1.6、樞紐在格子底邊。"""
    w = Image.open(os.path.join(RES, 'witch8', 'base.png')).convert('RGBA')
    cw, chh = w.width // 8, w.height // 25
    c = w.crop((0, 0, cw, chh))
    return c.resize((round(cw * 1.6), round(chh * 1.6)), Image.NEAREST)


# 遊戲裡這批圖再乘的倍數（＝ GameArt.PixelVillagerScale，兩邊要一起改）
GAME_SCALE = 1.1


def scene_preview(arts, outdir):
    """實景合成：照遊戲內縮放（村民 ×GAME_SCALE、女巫 ×1.6），擺在城鎮地面與店內，最後整張 ×2。"""
    files = []
    wi = witch_idle()
    lookup = {a[0]: a for a in arts}

    def cell(name, d=DOWN, f=0):
        k = SCALE * GAME_SCALE
        return lookup[name][2][(d, f)].resize((round(W * k), round(H * k)), Image.NEAREST)

    def place(bg, im, fx, fy, flip=False):
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        bg.alpha_composite(im, (int(fx - im.width / 2), int(fy - im.height)))

    names = [a[0] for a in arts]
    for tag, path, box in (('town', os.path.join(RES, 'art', 'ground', 'town.png'), (520, 330, 1120, 730)),
                           ('shop', os.path.join(RES, 'rooms', 'shop-room.png'), (120, 200, 840, 640))):
        bg = Image.open(path).convert('RGBA').crop(box)
        bw = bg.width
        base1 = bg.height - 20
        base0 = base1 - 150
        place(bg, wi, 50, base1)
        for i, nm in enumerate(names):
            if i < 6:
                x, y, d = 120 + i * 80, base1, DOWN
            else:
                x, y, d = 60 + (i - 6) * 100, base0, (SIDE, UP, SIDE, DOWN, UP)[i - 6]
            place(bg, cell(nm, d, (i % 2) * 1), x, y, flip=(d == SIDE and i % 2 == 0))
        bg = bg.resize((bw * 2, bg.height * 2), Image.NEAREST)
        p = os.path.join(outdir, f'scene_{tag}.png')
        bg.save(p)
        files.append(p)
    return files


def main():
    args = sys.argv[1:]
    if '--restore' in args:
        if os.path.isdir(OUT_DIR):
            shutil.rmtree(OUT_DIR)
        meta = OUT_DIR + '.meta'
        if os.path.exists(meta):
            os.remove(meta)
        print(f'已刪除 {OUT_DIR}（GameArt 找不到 villagers8 的圖時會自動退回舊圖；要完全關掉請把 GameArt.UsePixelVillagers 設 false）')
        return
    out_dir = args[args.index('--out') + 1] if '--out' in args else OUT_DIR
    preview_dir = args[args.index('--preview') + 1] if '--preview' in args else None
    arts = render_all()
    os.makedirs(out_dir, exist_ok=True)
    for name, big, cells, nc in arts:
        p = os.path.join(out_dir, name + '.png')
        big.save(p, optimize=False)
        print(f'{name:<12} → {name}.png  {nc} 色  {md5(p)[:8]}')
    print(f'共 {len(arts)} 張')
    if preview_dir:
        for f in preview(arts, preview_dir):
            print('預覽', f)


if __name__ == '__main__':
    main()
