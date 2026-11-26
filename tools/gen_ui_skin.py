#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UI 外觀圖（8-bit 像素風的九宮格面板框、清單列、按鈕、分頁、格子、小圖示）產生器。

    python tools/gen_ui_skin.py                 # 輸出 Assets/Resources/ui/skin8/<名稱>.png
    python tools/gen_ui_skin.py --check         # 只比對 Skin8.uss 裡的九宮格數字跟這裡的常數一不一致
    python tools/gen_ui_skin.py --uss           # 印出每張九宮格圖該寫的 -unity-slice-* 片段（可直接貼進 uss）
    python tools/gen_ui_skin.py --sheet DIR     # 另外輸出一張所有 skin 圖的總覽（DIR/skin_sheet.png）

面板怎麼套這些圖：Assets/Resources/ui/Skin8.uss（由 UI/UiSkin.cs 的 UiSkin.Apply(root) 疊在各面板原本的
樣式表之後；UiSkin.Enabled = false 就整套退回舊的純色塊外觀）。離線預覽（mockup）見 tools/preview_ui_skin.py。

── 畫風：跟道具圖示 tools/gen_item_art.py 同一套 ─────────────────────────────────
  在低解析度的「邏輯格」上一格一格點出來（純色、alpha 只有 0／255、沒有抗鋸齒），1px 深棕紫外輪廓
  （PAL['outline']，不是純黑），光從左上來（左上亮、右下暗），最後 NEAREST 放大輸出。
  色盤直接 import gen_item_art 的 PAL（＝魔女房間 gen_brew_room.PAL ＋ 道具補色）：
  暖棕木頭（wd_*）做框、羊皮紙米黃（pa_*／li_*）做內裡、深紫布（pu_*）配金滾邊（go_*）做標題緞帶與 HUD 格子。
  這支只 import 色盤與基元，**不改**那兩支的任何輸出（items8／rooms 的 md5 不變）。

── ⚠️ 放大倍率為什麼是 ×3，以及「不是整數倍縮放」的取捨 ─────────────────────────────
  UIPanelSettings 是「依高度縮放、參考高度 640」：720p 時 1 個 UI 單位＝1.125 個螢幕像素，
  1080p＝1.6875 —— 都不是整數。所以一個邏輯格畫到螢幕上會是 3×1.125＝3.375 px，
  每隔幾格就有一格是 4 px、其他是 3 px（「粗細不均的像素列」）。
  * 邏輯格放得越大，這個 ±1 px 佔的比例越小：×1 會是 1～2 px（差 100%，很醜）、×2 是 2～3 px（50%）、
    ×3 是 3～4 px（33%）、×4 是 4～5 px（25%）。
  * 但邏輯格越大，框就越粗、能放的東西越少：×4 時一條 7 格的木框就 28 個 UI 單位，760 寬的面板會被框吃掉一圈。
  → 取 ×3：輸出圖的 1 px ＝ UI 的 1 單位（-unity-slice-scale: 1px，九宮格的邊照圖的原始像素畫），
    在參考解析度（高 640，例如 960×640 視窗）剛好 1:1 完全銳利；720p 時誤差 1 px／格，肉眼幾乎看不出來；
    1080p 時 5.06 px／格，幾乎是整數。
  * 所以 Skin8.uss 裡**所有跟這些圖對齊的尺寸都是 3 的倍數**（slice、按鈕高、圖示寬高）。
    小圖示（金幣、鎖頭…）一律照「邏輯格數 ×3」原尺寸顯示，不要叫 UI Toolkit 縮放它們 ——
    縮成非 3 倍數的大小，Point 取樣會隨機吃掉某幾列像素。

── 九宮格（9-slice）規則 ──────────────────────────────────────────────────
  * 下面 SLICES 的數字是**邏輯格**；Skin8.uss 裡寫的 -unity-slice-left/top/right/bottom 是**輸出圖的像素**＝邏輯格 ×3。
    （Unity 6 UI Toolkit：-unity-slice-* 是 <integer>，單位是圖的像素；-unity-slice-scale 是 <length>，
    預設 1px，乘在 slice 上決定邊在畫面上多寬 —— 我們圖已經放大過，所以寫 1px。）
    `python tools/gen_ui_skin.py --check` 會逐一比對，改了這裡的常數就要改 uss（或貼 --uss 的輸出）。
  * 九宮格的「邊」會被拉長、「中間」會被拉滿 —— 所以邊上的花樣必須沿著邊方向完全一致（只在粗細方向有變化），
    中間必須是單色（羊皮紙不要畫紋理，拉長會變成條紋）。所有裝飾（星星鉚釘、緞帶尾巴、× 叉）都只放在四個角裡。
  * 元素的實際尺寸至少要 ≥ 左右 slice 之和、上下 slice 之和，不然 UI Toolkit 會把邊壓扁。
  * 結果是確定的：沒有亂數，重跑 md5 相同。
"""
import hashlib
import os
import re
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, 'Assets', 'Resources', 'ui', 'skin8')
USS_PATH = os.path.join(ROOT, 'Assets', 'Resources', 'ui', 'Skin8.uss')
ICONS8_DIR = os.path.join(ROOT, 'Assets', 'Resources', 'ui', 'icons8')

sys.path.insert(0, HERE)
from gen_item_art import PAL as ITEM_PAL   # noqa: E402  只拿色盤（含房間色盤），不跑它的管線

SCALE = 3          # 邏輯格 → 輸出像素（見檔頭「為什麼是 ×3」）

# ═══════════════════════════════ 色盤 ═══════════════════════════════
# 基底＝道具色盤（房間＋道具補色）。UI 另外補幾階「羊皮紙」：房間的 li_*／pa_* 是給布和紙道具的，
# 拿來當大面積底色太黃或太白，這裡補一組介於中間、可以久看的米色。
UI_EXTRA = {
    'pp_hi': '#fff8e6',    # 卡片高光
    'pp': '#fbefd4',       # 清單列卡片
    'pp_alt': '#f6e7c4',   # 交錯列
    'pp_bg': '#efdcb2',    # 面板內裡（比卡片深一階，卡片才浮得起來）
    'pp_dk': '#d7bb85',    # 內陰影
    'pp_ln': '#b48c58',    # 卡片外框（淡棕，不用深外輪廓 —— 一整排深框太吵）
    'pp_off': '#e4dccb',   # 不可用（材料不足）—— 去飽和的灰米
    'pp_offln': '#b2a48c',
    'gd_rim': '#e9c25c',   # 選取／滑過的金框（比 go 亮一點，在米色上才看得出來）
    'ink': '#4a2f25',      # 墨色（給圖示上的符號）
    'sh_ui': '#5a3f3a',    # 停用按鈕的暗面
    'st_off': '#b9ad9c', 'st_off_hi': '#d6ccbc', 'st_off_dk': '#8f8474',
}
PAL = dict(ITEM_PAL)
PAL.update(UI_EXTRA)
OL = 'outline'


def rgb(key):
    h = PAL[key]
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


# ═══════════════════════════════ 畫布 ═══════════════════════════════

class Px:
    """一張邏輯格畫布。p[(x, y)] = 色鍵；沒畫到的格子透明。"""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.p = {}

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.p[(x, y)] = c

    def fill(self, m, c):
        for x, y in m:
            self.put(x, y, c)

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, c)

    def image(self):
        im = Image.new('RGBA', (self.w, self.h), (0, 0, 0, 0))
        pix = im.load()
        for (x, y), c in self.p.items():
            pix[x, y] = rgb(c) + (255,)
        return im.resize((self.w * SCALE, self.h * SCALE), Image.NEAREST)


def rrect(x0, y0, x1, y1, r):
    """圓角矩形遮罩。r=0 直角、1 切掉角上 1 格、2 切掉角上 3 格（像素風的小圓角）。"""
    cut = {0: [], 1: [(0, 0)], 2: [(0, 0), (1, 0), (0, 1)], 3: [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (0, 2)]}[r]
    out = {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    for dx, dy in cut:
        out -= {(x0 + dx, y0 + dy), (x1 - dx, y0 + dy), (x0 + dx, y1 - dy), (x1 - dx, y1 - dy)}
    return out


def edge(m):
    """遮罩自己最外圈（4 鄰接有一邊在外面）。"""
    return {(x, y) for x, y in m if not {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} <= m}


def inset(m, n=1):
    out = set(m)
    for _ in range(n):
        out -= edge(out)
    return out


def lit_side(x, y, w, h):
    """bevel 用：這格比較靠近左上兩邊（受光）還是右下兩邊（背光）。角上的平手照對角線切。"""
    return min(x, y) <= min(w - 1 - x, h - 1 - y) if (x + y) != (w - 1 - x + h - 1 - y) else x < w - 1 - x


# ═══════════════════════════════ 小形狀 ═══════════════════════════════

def sparkle4(px, cx, cy, big=True):
    """四角星（金）：魔女房間星星地毯的那種。big：中心 3×3 菱形＋四角伸出 1 格。"""
    pts = {(cx, cy), (cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)}
    tips = {(cx + 2, cy), (cx - 2, cy), (cx, cy + 2), (cx, cy - 2)} if big else set()
    ring = set()
    for x, y in pts | tips:
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + d[0], y + d[1])
            if q not in pts and q not in tips:
                ring.add(q)
    px.fill(ring, OL)
    px.fill(tips, 'go_dk')
    px.fill(pts, 'go')
    px.put(cx, cy, 'go_hi')
    px.put(cx - 1, cy, 'go_hi')
    px.put(cx, cy - 1, 'go_hi')
    if big:
        px.put(cx - 2, cy, 'go')
        px.put(cx, cy - 2, 'go')


# ═══════════════════════════════ 面板框 ═══════════════════════════════
# 邏輯格 20×20、slice 9：外輪廓 1 ＋ 木框 4（外 bevel 1、木 2、內 bevel 1）＋ 金滾邊 1 ＋ 內陰影 1 ＝ 7 格，
# 第 8～9 格已經是羊皮紙（給角上星星留位置）。畫面上框寬 7×3＝21 UI 單位。

PANEL_SLICE = 9


def draw_panel():
    W = H = PANEL_SLICE * 2 + 2
    px = Px(W, H)
    m = rrect(0, 0, W - 1, H - 1, 2)
    for x, y in m:
        d = min(x, y, W - 1 - x, H - 1 - y)
        lit = lit_side(x, y, W, H)
        if d == 0:
            c = OL
        elif d == 1:
            c = 'wd_hi' if lit else 'wd_dk'
        elif d in (2, 3):
            c = 'wd'
        elif d == 4:
            c = 'wd_dk' if lit else 'wd_hi'       # 內 bevel 反過來 → 木框像凸起的一圈
        elif d == 5:
            c = 'go' if lit else 'go_dk'          # 金滾邊
        elif d == 6:
            c = 'wd_dk2'                          # 內陰影線
        elif d == 7:
            c = 'pp_dk' if lit else 'pp_bg'       # 紙的上緣與左緣落一點陰影 → 紙在框「裡面」
        else:
            c = 'pp_bg'
        px.put(x, y, c)
    # 圓角補外輪廓（rrect 切掉的角，最外圈那幾格要補成外框色）
    for x, y in edge(m):
        px.put(x, y, OL)
    for x, y in ((1, 1), (W - 2, 1), (1, H - 2), (W - 2, H - 2)):
        px.put(x, y, OL)
    # 四角的金色四角星，壓在木框上
    # 大四角星（中心 3×3＋四個尖角），中心壓在木框中段 (3,3)，尖角伸到金滾邊上
    for cx, cy in ((3, 3), (W - 4, 3), (3, H - 4), (W - 4, H - 4)):
        sparkle4(px, cx, cy, big=True)
    return px


# ═══════════════════════════════ 標題緞帶 ═══════════════════════════════
# 深紫布＋金滾邊，兩端是往下折、剪成燕尾的尾巴。邏輯 22×17、左右 slice 9（整條尾巴都在角裡）、上下 slice 5。
# 布面在第 1～13 列（金邊內的紫布 4～10 列，字落在這裡），尾巴在 6～16 列。

RIBBON_SLICE_X, RIBBON_H = 9, 17


def draw_ribbon():
    W, H = RIBBON_SLICE_X * 2 + 4, RIBBON_H
    px = Px(W, H)
    # 尾巴（後面）：左邊 x 0..6、右邊對稱，5..14 列，外側剪一個 V
    for side in (0, 1):
        tail = set()
        for y in range(6, 17):
            for x in range(0, 7):
                tail.add((x, y))
        # V 形缺口：最外側中間凹進去
        for y in range(6, 17):
            depth = 3 - abs(y - 12) if abs(y - 12) <= 3 else 0
            for x in range(0, depth):
                tail.discard((x, y))
        if side:
            tail = {(W - 1 - x, y) for x, y in tail}
        e = edge(tail)
        px.fill(tail, 'pu_dk')
        px.fill(e, OL)
        # 尾巴上的金邊（上緣下 1 列）
        for x, y in tail - e:
            if y == 7:
                px.put(x, y, 'go_dk')
            elif y == 15:
                px.put(x, y, 'pu_dk2')
        # 折痕：尾巴貼著布條的那一側落深色
        fx = 6 if not side else W - 7
        for y in range(13, 16):
            px.put(fx, y, 'pu_dk2')
    # 布條本體（前面）：x 4..W-5、y 1..13
    band = {(x, y) for x in range(4, W - 4) for y in range(1, 14)}
    e = edge(band)
    for x, y in band:
        if (x, y) in e:
            c = OL
        elif y == 2:
            c = 'go_hi'
        elif y == 3:
            c = 'go'
        elif y == 11:
            c = 'go'
        elif y == 12:
            c = 'go_dk'
        elif y == 4:
            c = 'pu_hi'
        elif y == 10:
            c = 'pu_dk'
        else:
            c = 'pu'
        px.put(x, y, c)
    # 布條兩端各一顆小金釘（在角裡）
    for x in (6, W - 7):
        px.put(x, 7, 'go_hi')
        px.put(x, 8, 'go_dk')
    return px


# ═══════════════════════════════ 按鈕（九宮格）═══════════════════════════════
# 邏輯 10×12：外輪廓、小圓角、上緣 1 列高光、底下 2 列「唇」（按鈕的厚度）。
# slice：左右 4、上 4、下 5（唇整條都在下緣的 slice 裡）。按下：唇剩 1 列、臉往下沉 1 格。

BTN_W, BTN_H = 10, 12
BTN_SLICE = (4, 4, 4, 5)     # 左、上、右、下

BTN_RAMPS = {
    #          亮         臉        暗（唇）   最暗（唇底／按下時的上緣陰影）
    'green': ('gr_hi', 'gr', 'gr_dk', 'gr_dk2'),
    'gold': ('go_hi', 'go', 'go_dk', 'go_dk2'),
    'wood': ('wd_hi', 'wd', 'wd_dk', 'wd_dk2'),
    'red': ('rd_hi', 'rd', 'rd_dk', 'rd_dk2'),
    'off': ('st_off_hi', 'st_off', 'st_off_dk', 'st_off_dk'),
}
HOVER = {   # 滑過：臉換亮一階、高光換成近白
    'green': ('#d4eba8', 'gr_hi', 'gr', 'gr_dk2'),
    'gold': ('wh', 'go_hi', 'go', 'go_dk2'),
    'wood': ('cu_hi', 'wd_hi', 'wd', 'wd_dk2'),
    'red': ('#ffb0a0', 'rd_hi', 'rd', 'rd_dk2'),
}


def _hex_key(c):
    if c.startswith('#'):
        PAL.setdefault(c, c)
    return c


def button_face(W, H, ramp, state, r=1):
    """state: 'n'（一般）／'h'（滑過）／'d'（按下）。回傳 Px。"""
    hi, face, dk, dk2 = (_hex_key(c) for c in ramp)
    px = Px(W, H)
    m = rrect(0, 0, W - 1, H - 1, r)
    e = edge(m)
    inner = m - e
    lip = 1 if state == 'd' else 2
    top = 2 if state == 'd' else 1          # 按下：上緣多一列陰影、臉往下沉
    for x, y in inner:
        if y >= H - 1 - lip:
            c = dk2 if y == H - 2 else dk
        elif state == 'd' and y == 1:
            c = dk                         # 按下時上緣是陰影
        elif y == top:
            c = hi
        elif x == 1 and y < H - 1 - lip:
            c = hi
        elif x == W - 2:
            c = dk
        else:
            c = face
        px.put(x, y, c)
    px.fill(e, OL)
    return px


# ═══════════════════════════════ 清單列卡片 ═══════════════════════════════
# 邏輯 10×11、slice 4（下 5）：淡棕細框＋上緣高光＋下緣內陰影，底下再墊 1 列「落影」讓卡片浮起來。

ROW_W, ROW_H = 10, 11
ROW_SLICE = (4, 4, 4, 5)

ROW_KINDS = {
    #          框         高光       底         內陰影      落影
    'row': ('pp_ln', 'pp_hi', 'pp', 'pp_alt', 'pp_dk'),
    'row-alt': ('pp_ln', 'pp', 'pp_alt', 'pp_dk', 'pp_dk'),
    'row-hover': ('go_dk', 'wh', 'pp_hi', 'pp', 'pp_dk'),
    'row-sel': ('gd_rim', 'wh', 'pp_hi', 'pp', 'go_dk'),
    'row-off': ('pp_offln', 'pp_off', 'pp_off', 'pp_offln', 'pp_dk'),
}


def draw_row(kind):
    ln, hi, base, sh, drop = ROW_KINDS[kind]
    W, H = ROW_W, ROW_H
    px = Px(W, H)
    card = rrect(0, 0, W - 1, H - 2, 1)
    e = edge(card)
    for x, y in card:
        if (x, y) in e:
            c = ln
        elif y == 1:
            c = hi
        elif y == H - 3:
            c = sh
        else:
            c = base
        px.put(x, y, c)
    if kind == 'row-sel':      # 選取：金框兩格粗（內圈再描一圈）
        for x, y in edge(card - e):
            px.put(x, y, 'go')
    for x in range(1, W - 1):
        px.put(x, H - 1, drop)
    return px


# ═══════════════════════════════ 分頁 ═══════════════════════════════
# 邏輯 10×10、slice 左右 4、上 4、下 3。上面兩角圓、底部開口（沒有下框）：
# 選中的分頁底色＝面板內裡色，往下壓住分頁列的底線 → 看起來跟內容是同一張紙。

TAB_W, TAB_H = 10, 10
TAB_SLICE = (4, 4, 4, 3)


def draw_tab(kind):
    W, H = TAB_W, TAB_H
    px = Px(W, H)
    m = {(x, y) for x in range(W) for y in range(H)}
    for d in ((0, 0), (1, 0), (0, 1)):
        m -= {(d[0], d[1]), (W - 1 - d[0], d[1])}
    if kind == 'tab-on':
        ln, hi, base = 'wd_dk', 'pp_hi', 'pp_bg'
    elif kind == 'tab-hover':
        ln, hi, base = 'wd_dk', 'pp_hi', 'pp_alt'
    else:
        ln, hi, base = 'wd_dk', 'pp_alt', 'pp_dk'
    for x, y in m:
        left = x == 0 or (x == 1 and y == 1)
        right = x == W - 1 or (x == W - 2 and y == 1)
        if y == 0 or left or right or (x, y) in ((1, 1), (W - 2, 1)):
            c = ln
        elif y == 1 or (y == 2 and x in (2, W - 3)):
            c = 'gd_rim' if kind == 'tab-on' else hi
        else:
            c = base
        if kind != 'tab-on' and y == H - 1:
            c = 'wd_dk'          # 沒選的分頁：最底一列＝分頁列底線的顏色（壓在線上，線看起來沒斷）
        px.put(x, y, c)
    return px


# ═══════════════════════════════ 格子 ═══════════════════════════════
# HUD 背包格（深紫布＋金框，壓在遊戲畫面上要看得清楚）：邏輯 14×14、slice 4。
#   框只有 3 格（外輪廓＋金 bevel 2）＋1 格內陰影 → 66 的格子內側剛好 48，道具圖（24 邏輯格 ×2）不會壓到金框。
# 列表裡的圖示凹槽（羊皮紙往下凹）：邏輯 10×10、slice 4。

SLOT_N, SLOT_SLICE = 14, 4
WELL_N, WELL_SLICE = 10, 4


def draw_slot(kind):
    N = SLOT_N
    px = Px(N, N)
    m = rrect(0, 0, N - 1, N - 1, 2)
    if kind == 'slot-sel':
        rim = ('wh', 'gd_rim', 'go_dk')
    elif kind == 'slot-empty':
        rim = ('wd_hi', 'wd', 'wd_dk')          # 空格：木框不鑲金 → 有東西的格子才「亮」起來
    else:
        rim = ('go_hi', 'go', 'go_dk')
    cloth = ('pu_dk2', 'pu_dk') if kind != 'slot-empty' else ('pu_dk2', 'pu_dk2')
    for x, y in m:
        d = min(x, y, N - 1 - x, N - 1 - y)
        lit = lit_side(x, y, N, N)
        if d == 0:
            c = OL
        elif d == 1:
            c = rim[0] if lit else rim[2]
        elif d == 2:
            if kind == 'slot-sel':
                c = rim[1]
            elif kind == 'slot-empty':
                c = 'wd_dk' if lit else 'wd'
            else:
                c = 'go_dk' if lit else 'go'
        elif d == 3:
            c = OL if lit else cloth[1]           # 內緣：上左落陰影
        else:
            c = cloth[1] if kind != 'slot-empty' else cloth[0]
        px.put(x, y, c)
    for x, y in edge(m):
        px.put(x, y, OL)
    for x, y in ((1, 1), (N - 2, 1), (1, N - 2), (N - 2, N - 2)):
        px.put(x, y, OL)
    return px


# 下排背包列的底座：木條＋金滾邊，裡面是深色木板（紫布格子擺上去才跳出來）。邏輯 16×16、slice 6。
BAR_N, BAR_SLICE = 16, 6


def draw_bar():
    N = BAR_N
    px = Px(N, N)
    m = rrect(0, 0, N - 1, N - 1, 2)
    for x, y in m:
        d = min(x, y, N - 1 - x, N - 1 - y)
        lit = lit_side(x, y, N, N)
        if d == 0:
            c = OL
        elif d == 1:
            c = 'wd_hi' if lit else 'wd_dk'
        elif d == 2:
            c = 'wd'
        elif d == 3:
            c = 'go' if lit else 'go_dk'
        elif d == 4:
            c = 'wd_dk2'
        else:
            c = 'wd_dk'
        px.put(x, y, c)
    for x, y in edge(m):
        px.put(x, y, OL)
    for x, y in ((1, 1), (N - 2, 1), (1, N - 2), (N - 2, N - 2)):
        px.put(x, y, OL)
    for cx, cy in ((2, 2), (N - 3, 2), (2, N - 3), (N - 3, N - 3)):
        sparkle4(px, cx, cy, big=False)
    return px


def draw_well():
    N = WELL_N
    px = Px(N, N)
    m = rrect(0, 0, N - 1, N - 1, 1)
    e = edge(m)
    for x, y in m:
        if (x, y) in e:
            c = 'pp_ln'
        elif x == 1 or y == 1:
            c = 'pp_dk'                           # 凹進去：上左是陰影
        elif x == N - 2 or y == N - 2:
            c = 'pp_hi'
        else:
            c = 'pp_alt'
        px.put(x, y, c)
    return px


# ═══════════════════════════════ 捲軸 ═══════════════════════════════
# 軌道：凹槽（深米），把手：小木條。都是邏輯 5×12、slice 左右 2、上下 4。

SCROLL_W, SCROLL_H = 5, 12
SCROLL_SLICE = (2, 4, 2, 4)


def draw_scroll(kind):
    W, H = SCROLL_W, SCROLL_H
    px = Px(W, H)
    m = rrect(0, 0, W - 1, H - 1, 1)
    e = edge(m)
    for x, y in m:
        if (x, y) in e:
            c = 'pp_ln' if kind == 'scroll-track' else OL
        elif kind == 'scroll-track':
            c = 'pp_dk' if x == 1 else 'pp_alt'
        else:
            hot = kind == 'scroll-thumb-hover'
            if x == 1:
                c = 'go_hi' if hot else 'wd_hi'
            elif x == W - 2:
                c = 'go_dk' if hot else 'wd_dk'
            else:
                c = 'go' if hot else 'wd'
            if y == H - 2:
                c = 'go_dk' if hot else 'wd_dk'
        px.put(x, y, c)
    if kind != 'scroll-track':     # 把手中間 3 道止滑紋（在 slice 外的中段會被拉長 → 只放在上下角裡各一道）
        px.put(2, 2, 'wd_dk2' if kind == 'scroll-thumb' else 'go_dk')
        px.put(2, H - 4, 'wd_dk2' if kind == 'scroll-thumb' else 'go_dk')
    return px


# ═══════════════════════════════ 徽章／標籤／材料小卡／鍵帽 ═══════════════════════════════
# 都是邏輯 7×7、slice 3 的小膠囊（圓角 1）。

PILL_N, PILL_SLICE = 7, 3

PILLS = {
    #           框      底        高光
    'badge': (OL, 'wd_dk2', 'wd_dk'),           # 數量徽章：深木底＋米色字
    'chip': ('pp_ln', 'pp_hi', 'wh'),           # 材料小卡（夠）
    'chip-short': ('rd_dk', '#fde0d6', 'wh'),   # 材料小卡（不夠）：淡紅底
    'tag-gold': ('go_dk2', 'go', 'go_hi'),      # 任務狀態：可回報
    'tag-green': ('gr_dk2', 'gr', 'gr_hi'),     # 進行中
    'tag-blue': ('bl_dk', 'bl_hi', '#8fa6e0'),  # 可接
    'tag-grey': ('st_off_dk', 'st_off', 'st_off_hi'),   # 已完成
}


def draw_pill(kind):
    ln, base, hi = (_hex_key(c) for c in PILLS[kind])
    N = PILL_N
    px = Px(N, N)
    m = rrect(0, 0, N - 1, N - 1, 1)
    e = edge(m)
    for x, y in m:
        px.put(x, y, ln if (x, y) in e else (hi if y == 1 else base))
    return px


KEY_W, KEY_H = 8, 9
KEY_SLICE = (3, 3, 3, 4)


def draw_keycap():
    """鍵帽（底部說明列的「Esc」）：米白鍵面＋2 列鍵身。"""
    W, H = KEY_W, KEY_H
    px = Px(W, H)
    m = rrect(0, 0, W - 1, H - 1, 1)
    e = edge(m)
    for x, y in m:
        if (x, y) in e:
            c = OL
        elif y >= H - 3:
            c = 'li_dk'
        elif y == 1:
            c = 'wh'
        else:
            c = 'li_hi'
        px.put(x, y, c)
    return px


DIV_W, DIV_H = 11, 5
DIV_SLICE = (5, 2, 5, 2)


def draw_divider():
    """分隔線：中間一條淡棕線（會拉長），兩端各一顆小金菱形（在角裡）。"""
    W, H = DIV_W, DIV_H
    px = Px(W, H)
    for x in range(2, W - 2):
        px.put(x, 2, 'pp_ln')
        px.put(x, 3, 'pp_hi')
    for cx in (2, W - 3):
        for d in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            px.put(cx + d[0], 2 + d[1], 'go_dk')
        px.put(cx, 2, 'go_hi')
    return px


# ═══════════════════════════════ 小圖示（固定尺寸，不切九宮格）═══════════════════════════════
# 一律照邏輯格 ×3 的原尺寸顯示（見檔頭）。
# ⚠️ 鎖頭／打勾／箭頭**不在這裡畫**：另一支產生器 tools/gen_ui_icons.py 的 Resources/ui/icons8/ 已經有
#    lock／st_ok／arrow（24 邏輯格 ×4 ＝ 96×96），Skin8.uss 直接用那幾張（顯示 24×24 ＝ 邏輯 1:1）。
#    draw_lock／draw_check／draw_arrow 留著只是備用，不在 SKINS 清單裡、不會輸出。

def from_rows(rows, keymap):
    """用字元畫：rows 是等長字串，keymap: 字元 → 色鍵（'.' 透明）。"""
    px = Px(len(rows[0]), len(rows))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != '.':
                px.put(x, y, keymap[ch])
    return px


def draw_coin():
    """金幣（7×7）：圓幣、左上打光、中間一道壓印。"""
    return from_rows([
        '..ooo..',
        '.ohhgo.',
        'ohHggdo',
        'ohgggdo',
        'ohggddo',
        '.oddko.',
        '..ooo..',
    ], {'o': OL, 'H': 'wh', 'h': 'go_hi', 'g': 'go', 'd': 'go_dk', 'k': 'go_dk2'})


def draw_lock():
    return from_rows([
        '..ooo..',
        '.oIoIo.',
        '.oi.io.',
        'ooooooo',
        'ohgggdo',
        'oggkgdo',
        'oggkgdo',
        'odddddo',
        'ooooooo',
    ], {'o': OL, 'I': 'ir_hi', 'i': 'ir', 'h': 'go_hi', 'g': 'go', 'd': 'go_dk', 'k': 'ink'})


def draw_check():
    return from_rows([
        '......oo',
        '.....oGo',
        'oo..oGgo',
        'oGooGgo.',
        'oggGgo..',
        '.oggo...',
        '..oo....',
    ], {'o': OL, 'G': 'gr_hi', 'g': 'gr'})


def draw_heart(on):
    k = {'o': OL, 'H': 'wh', 'h': 'pk_hi', 'p': 'pink', 'd': 'pink_dk'} if on else \
        {'o': 'pp_ln', 'H': 'pp_hi', 'h': 'pp_hi', 'p': 'pp_alt', 'd': 'pp_dk'}
    return from_rows([
        '.oo.oo.',
        'oHhoppo',
        'ohpppdo',
        'opppddo',
        '.opddo.',
        '..odo..',
        '...o...',
    ], k)


def draw_arrow():
    return from_rows([
        '...o...',
        '...oo..',
        'ooooGo.',
        'oHHGGGo',
        'ooooGo.',
        '...oo..',
        '...o...',
    ], {'o': OL, 'G': 'gr', 'H': 'gr_hi'})


def draw_close(state):
    """關閉鈕（12×12，固定尺寸）：紅色小方鈕＋米白 ×（字畫在圖裡，按鈕上的「×」文字在 uss 裡設成透明）。"""
    ramp = HOVER['red'] if state == 'h' else BTN_RAMPS['red']
    px = button_face(12, 12, ramp, state, r=2)
    oy = 1 if state == 'd' else 0
    # 2 格寬的斜線交叉（1 格寬在 ×3 下太細，而且兩條線交會處會變成棋盤格）
    xs = set()
    for i in range(5):
        y = 2 + i + oy
        xs |= {(3 + i, y), (4 + i, y), (8 - i, y), (7 - i, y)}
    for x, y in xs:
        if (x, y + 1) not in xs:
            px.put(x, y + 1, 'rd_dk2')          # 落影（只落在 × 本身沒蓋到的格子）
    for x, y in xs:
        px.put(x, y, 'li_hi')
    return px


def draw_step(sym, state):
    """± 小鈕（11×11 固定尺寸）：木頭按鈕＋符號畫在圖裡。state 多一個 'x'＝停用。"""
    if state == 'x':
        px = button_face(11, 11, BTN_RAMPS['off'], 'n')
        ink, sh = 'st_off_hi', 'st_off_dk'
    else:
        px = button_face(11, 11, HOVER['wood'] if state == 'h' else BTN_RAMPS['wood'], state)
        ink, sh = 'li_hi', 'wd_dk2'
    oy = 1 if state == 'd' else 0
    pts = [(x, 4 + oy) for x in range(3, 8)]
    if sym == 'plus':
        pts += [(5, y + oy) for y in range(2, 7)]
    for x, y in pts:
        px.put(x, y + 1, sh)
    for x, y in pts:
        px.put(x, y, ink)
    return px


# ═══════════════════════════════ 第二輪：任務簿／對話框／工具列／結算 ═══════════════════════════════
# 以下是第二輪加的圖（任務簿、對話框、上方工具列、每日結算、Toast 共用）。**只往清單尾巴加**，
# 前 53 張的畫法與輸出一個像素都沒動（md5 不變）。

# 任務簿的羊皮紙卷軸：上下各一根木軸（兩端金色軸頭，在角裡），中間米色紙。
# 邏輯 12×18、slice 左右 4、上下 7：軸 5 列＋紙捲進軸下的陰影 1 列＋紙 1 列都在上下 slice 裡；
# 紙的左右緣（淡棕線＋高光／陰影）沿垂直方向完全一致，中間單色 → 拉長不會出條紋。
SCROLL_PAPER_W, SCROLL_PAPER_H = 12, 18
SCROLL_PAPER_SLICE = (4, 7, 4, 7)


def draw_scroll_paper():
    W, H = SCROLL_PAPER_W, SCROLL_PAPER_H
    px = Px(W, H)
    # 紙（x 1..W-2）
    for y in range(4, H - 4):
        for x in range(1, W - 1):
            if x == 1 or x == W - 2:
                c = 'pp_ln'
            elif x == 2:
                c = 'pp_hi'
            elif x == W - 3:
                c = 'pp_dk'
            elif y in (5, H - 6):
                c = 'pp_dk'                         # 紙捲進木軸的那一列陰影
            else:
                c = 'pp_bg'
            px.put(x, y, c)
    # 木軸（上：0..4、下：H-5..H-1），整條寬；兩端 3 格是金色軸頭
    for y0 in (0, H - 5):
        for x in range(W):
            for k, c in enumerate((OL, 'wd_hi', 'wd', 'wd_dk', OL)):
                px.put(x, y0 + k, c)
        for xs, lit in ((0, True), (W - 3, False)):
            for k in range(5):
                for dx in range(3):
                    x = xs + dx
                    if k in (0, 4) or dx == (0 if lit else 2):
                        c = OL
                    elif k == 1:
                        c = 'go_hi'
                    elif k == 3:
                        c = 'go_dk'
                    else:
                        c = 'go'
                    px.put(x, y0 + k, c)
            # 軸頭跟木軸之間一道深色接縫
            sx = xs + 2 if lit else xs
            for k in range(1, 4):
                px.put(sx, y0 + k, 'go_dk2')
    return px


# 對話框的名字牌：深紫布＋金框的小牌子（緞帶的配色，沒有尾巴），底下 1 列落影。邏輯 9×11、slice 4／4／4／5。
PLATE_W, PLATE_H = 9, 11
PLATE_SLICE = (4, 4, 4, 5)


def draw_plate():
    W, H = PLATE_W, PLATE_H
    px = Px(W, H)
    m = rrect(0, 0, W - 1, H - 2, 1)
    e = edge(m)
    for x, y in m:
        d = min(x, y, W - 1 - x, H - 2 - y)
        lit = lit_side(x, y, W, H - 1)
        if (x, y) in e:
            c = OL
        elif d == 1:
            c = 'go_hi' if lit else 'go_dk'
        elif y == 2:
            c = 'pu_hi'
        elif y == H - 4:
            c = 'pu_dk'
        else:
            c = 'pu'
        px.put(x, y, c)
    for x in range(1, W - 1):
        px.put(x, H - 1, 'pu_dk2')                   # 落影
    return px


def draw_gear():
    """設定（齒輪，11×11 → 33 px）：金色、左上打光，中心一個十字形深色軸孔。
    程式算形狀：半徑 3.7 的圓盤＋8 個齒（上下左右 3×2、斜角 2×2）。9×9 試過，齒全被外輪廓吃掉、看起來像太陽。"""
    import math
    N = 11
    c0 = (N - 1) / 2
    body, hole = set(), set()
    for y in range(N):
        for x in range(N):
            r = math.hypot(x - c0, y - c0)
            if r <= 1.0:
                hole.add((x, y))
            elif r <= 3.7:
                body.add((x, y))
    teeth = [(4, 0, 6, 1), (4, 9, 6, 10), (0, 4, 1, 6), (9, 4, 10, 6),
             (1, 1, 2, 2), (8, 1, 9, 2), (1, 8, 2, 9), (8, 8, 9, 9)]
    for x0, y0, x1, y1 in teeth:
        body |= {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    px = Px(N, N)
    e = edge(body | hole)
    for x, y in body:
        if (x, y) in e:
            c = OL
        else:
            s_ = (x - c0) + (y - c0)
            c = 'go_hi' if s_ < -1.5 else ('go_dk' if s_ > 1.5 else 'go')
        px.put(x, y, c)
    for x, y in hole:
        px.put(x, y, OL)
    return px


def draw_star():
    """名聲（五角星，9×9，金）。"""
    return from_rows([
        '....o....',
        '...oHo...',
        'ooooHgooo',
        'oHHhhggdo',
        '.ohhggdo.',
        '..ohgdo..',
        '.ohgodgo.',
        '.ogo.odo.',
        '.oo...oo.',
    ], {'o': OL, 'H': 'wh', 'h': 'go_hi', 'g': 'go', 'd': 'go_dk'})


def draw_basket():
    """賣出件數（購物籃，9×9）。"""
    return from_rows([
        '..ooooo..',
        '.o.....o.',
        '.o.....o.',
        'ooooooooo',
        'ohhhhhhdo',
        '.owdwdwo.',
        '.odwdwdo.',
        '.owdwdwo.',
        '..ooooo..',
    ], {'o': OL, 'h': 'cu_hi', 'w': 'cu', 'd': 'cu_dk'})


def draw_sack():
    """材料收購（麻布袋，9×9）。"""
    return from_rows([
        '..o...o..',
        '...ooo...',
        '...oko...',
        '..oHhho..',
        '.oHhhhdo.',
        'oHhhhhddo',
        'ohhhhdddo',
        'ohhdddddo',
        '.ooooooo.',
    ], {'o': OL, 'k': 'go_dk', 'H': 'pa_hi', 'h': 'pa', 'd': 'pa_dk'})


def draw_leaf():
    """採集（葉子，9×9）。"""
    return from_rows([
        '......ooo',
        '....oohho',
        '...ohhggo',
        '..ohhgkgo',
        '.ohgkggdo',
        '.ohkggdo.',
        '.okggdo..',
        'okoodo...',
        'o..oo....',
    ], {'o': OL, 'h': 'gr_hi', 'g': 'gr', 'd': 'gr_dk', 'k': 'gr_dk2'})


def draw_flask():
    """煉製（藥水瓶，9×9）。"""
    return from_rows([
        '...ooo...',
        '...oco...',
        '...ogo...',
        '..ogggo..',
        '.ogwpppo.',
        'ogwpppppo',
        'ogppppPpo',
        '.opppPPo.',
        '..ooooo..',
    ], {'o': OL, 'c': 'cu', 'g': 'gl', 'w': 'wh', 'p': 'cy_p', 'P': 'cy_p2'})


def draw_bullet():
    """公告條目前面的小金菱形（5×5 → 15 px）。"""
    return from_rows([
        '..k..',
        '.khk.',
        'khgdk',
        '.kdk.',
        '..k..',
    ], {'k': 'go_dk2', 'h': 'go_hi', 'g': 'go', 'd': 'go_dk'})


def draw_qbox(on):
    """任務簿的勾選框（8×8）：羊皮紙上的凹框；可回報時打一個綠勾（勾的尾巴伸出框外一點）。"""
    px = from_rows([
        'oooooooo',
        'oddddddo',
        'odaaaaho',
        'odaaaaho',
        'odaaaaho',
        'odaaaaho',
        'ohhhhhho',
        'oooooooo',
    ], {'o': 'wd_dk', 'd': 'pp_dk', 'a': 'pp', 'h': 'pp_hi'})
    if on:
        # 綠勾：2 格粗的筆畫，底下落一格深綠；勾尾伸出框的右上角
        stroke = [(1, 3), (2, 4), (3, 5), (4, 4), (5, 3), (6, 2), (7, 1),
                  (1, 4), (2, 5), (3, 6), (4, 5), (5, 4), (6, 3), (7, 2)]
        for x, y in stroke:
            if (x, y + 1) not in stroke:
                px.put(x, y + 1, 'gr_dk2')
        for x, y in stroke:
            px.put(x, y, 'gr')
        for x, y in ((1, 3), (2, 4), (5, 3), (6, 2), (7, 1)):
            px.put(x, y, 'gr_hi')
    return px


def draw_cell(on):
    """設定面板音量條的一格：亮的是琥珀色小寶石、暗的是凹槽。邏輯 6×7。"""
    if on:
        return from_rows([
            'oooooo',
            'oHhhgo',
            'ohggdo',
            'ohggdo',
            'oggddo',
            'okkkko',
            'oooooo',
        ], {'o': OL, 'H': 'wh', 'h': 'hn_hi', 'g': 'hn', 'd': 'hn_dk', 'k': 'go_dk2'})
    return from_rows([
        'llllll',
        'lddddl',
        'ldaaal',
        'ldaaal',
        'ldaaal',
        'lhhhhl',
        'llllll',
    ], {'l': 'pp_ln', 'd': 'pp_dk', 'a': 'pp_alt', 'h': 'pp_hi'})


# ═══════════════════════════════ 下排道具列：魔女腰包（第三輪）═══════════════════════════════
# 深紫布條＋上下兩道金虛線，每格是布上縫出來的口袋（亮的薰衣草襯裡墊在道具後面，深色道具也看得清）。
# ⚠️ 全部是**固定尺寸**的圖、一格一張 —— 金虛線的針腳拉長會變成一條實線，所以不用九宮格拉布條：
#    InventoryHud 把 [左端][口袋]×N[右端] 一個接一個排起來，布條的虛線剛好接得上（每格 17 格寬，虛線週期 4）。
#   口袋 belt-pocket / -empty / -new  17×20（51×60 px）：道具圖 48×48 疊在 (3, 6) px ＝ 邏輯 (1, 2)。
#   兩端 belt-end-l（星星扣）/ belt-end-r（月亮扣） 6×26（18×78 px）：布條收圓角，底下垂一小串金流蘇。
#   數量徽章 belt-badge  7×7、slice 3（金扣子，墨色字）；新東西亮光 belt-spark 9×9（27 px，固定）。
# 跟 hud-bar／slot 是不同的圖：那兩張還有上方工具列、Toast、托盤、背包面板在用，一個像素都不動。

BELT_W, BELT_H = 17, 20
BELT_END_W, BELT_END_H = 6, 26
BELT_BADGE_N, BELT_BADGE_SLICE = 7, 3


def _belt_color(x, y):
    """布條在 (x, y) 的顏色：外輪廓、亮邊、金虛線、布……布、金虛線、暗邊、外輪廓。"""
    if y in (0, BELT_H - 1):
        return OL
    if y == 1:
        return 'pu'
    if y == BELT_H - 2:
        return 'pu_dk2'
    if y in (2, BELT_H - 3):
        return 'go' if (x % 4) in (1, 2) else 'pu_dk'
    return 'pu_dk'


# 口袋袋口的弧線：x → 袋口那一列的 y（中間低、兩邊高 —— 笑臉弧）
_BELT_LIP = {2: 11, 3: 11, 4: 12, 5: 12, 6: 13, 7: 13, 8: 13, 9: 13, 10: 13, 11: 13, 12: 12, 13: 12, 14: 11, 15: 11}
_BELT_PX0, _BELT_PX1, _BELT_PTOP, _BELT_PBOT = 2, 15, 4, 16


def draw_belt_pocket(kind):
    """
    kind：'full'（有東西：薰衣草襯裡）／'empty'（空：不畫襯裡，只剩袋口弧線＋前片＋一顆淡淡的小繡星）／
    'new'（剛拿到：奶油白襯裡＋亮金線）。
    """
    px = Px(BELT_W, BELT_H)
    for x in range(BELT_W):
        for y in range(BELT_H):
            px.put(x, y, _belt_color(x, y))
    if kind == 'empty':
        front, lip, stitch = 'pu_dk', 'pu', 'go_dk2'
    elif kind == 'new':
        lining = ('pp_hi', 'wh', 'pp')
        front, lip, stitch = 'pu', 'pu_hi', 'go_hi'
    else:
        lining = ('vi_hi', 'li_hi', 'lav_hi')
        front, lip, stitch = 'pu', 'pu_hi', 'go'
    x0, x1 = _BELT_PX0, _BELT_PX1
    if kind != 'empty':
        # 襯裡（袋子裡面）：圓角，上緣一列袋內陰影、左上一點高光
        m = rrect(x0, _BELT_PTOP, x1, _BELT_PBOT, 2)
        for x, y in m:
            px.put(x, y, lining[0])
        for x in range(x0 + 2, x1 - 1):
            px.put(x, _BELT_PTOP + 1, lining[2])
        px.put(x0 + 1, _BELT_PTOP + 2, lining[2])
        px.put(x1 - 1, _BELT_PTOP + 2, lining[2])
        px.put(x0 + 1, _BELT_PTOP + 3, lining[1])
        for x, y in edge(m):
            px.put(x, y, 'pu_dk2')
    # 袋子前片：袋口弧線以下；弧線下兩格縫一道金虛線
    for x in range(x0, x1 + 1):
        ly = _BELT_LIP[x]
        px.put(x, ly, lip)
        for y in range(ly + 1, _BELT_PBOT + 1):
            px.put(x, y, front)
        if x not in (x0, x1) and x % 2 == 1:
            px.put(x, ly + 2, stitch)
    for y in range(_BELT_LIP[x0] + 1, _BELT_PBOT + 1):
        px.put(x0, y, 'pu_dk2')
        px.put(x1, y, 'pu_dk2')
    if kind == 'empty':
        cx, cy = 8, 8
        for x, y in ((cx, cy), (cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            px.put(x, y, 'pu')
        px.put(cx, cy, 'pu_hi')
    return px


def _blob(px, fill, keep=()):
    """畫一塊形狀＋自動補 4 鄰接的外輪廓（keep 裡的格子不蓋）。fill: {(x, y): 色鍵}。"""
    for (x, y), c in fill.items():
        px.put(x, y, c)
    for x, y in fill:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in fill and q not in keep:
                px.put(q[0], q[1], OL)


def _belt_tassel(px, cx, y0, keep):
    """金流蘇：一格繩、三格寬的結、底下四列流蘇（最後一列參差）。y0 ＝ 繩頭（壓在布條下緣）。"""
    f = {(cx, y0): 'go_dk',
         (cx - 1, y0 + 1): 'go_hi', (cx, y0 + 1): 'go', (cx + 1, y0 + 1): 'go_dk'}
    for y in range(y0 + 2, y0 + 6):
        f[(cx - 1, y)] = 'go'
        f[(cx, y)] = 'go_dk' if y % 2 else 'go'
        f[(cx + 1, y)] = 'go_dk'
    f[(cx - 1, y0 + 2)] = 'go_hi'
    del f[(cx, y0 + 5)]
    _blob(px, f, keep)


def _belt_moon(px, x0, y0):
    """小弦月扣（金）：3×6 的 ( 形，左上受光。"""
    f = {(x0 + 1, y0): 'go', (x0 + 2, y0): 'go_dk',
         (x0, y0 + 1): 'go_hi', (x0 + 1, y0 + 1): 'go',
         (x0, y0 + 2): 'go_hi', (x0, y0 + 3): 'go',
         (x0, y0 + 4): 'go', (x0 + 1, y0 + 4): 'go_dk',
         (x0 + 1, y0 + 5): 'go_dk', (x0 + 2, y0 + 5): 'go_dk'}
    _blob(px, f)


def draw_belt_end(side):
    """布條的兩端：'l' ＝ 左端（星星扣），'r' ＝ 右端（月亮扣）。外側切圓角，底下垂一串金流蘇。"""
    W, H = BELT_END_W, BELT_END_H
    px = Px(W, H)
    band = {(x, y) for x in range(W) for y in range(BELT_H)}
    for dx, dy in ((0, 0), (1, 0), (0, 1), (0, BELT_H - 1), (1, BELT_H - 1), (0, BELT_H - 2)):
        band.discard((dx, dy) if side == 'l' else (W - 1 - dx, dy))
    for x, y in band:
        px.put(x, y, _belt_color(x + (BELT_W - W if side == 'l' else 0), y))
    for x, y in band:      # 外側收邊
        if ((x - 1, y) not in band) if side == 'l' else ((x + 1, y) not in band):
            px.put(x, y, OL)
    for x, y in edge(band):
        if y in (0, BELT_H - 1):
            px.put(x, y, OL)
    if side == 'l':
        for y in range(2, BELT_H - 2):
            px.put(1, y, 'pu')
        for x, y in ((1, 1), (1, BELT_H - 2)):
            px.put(x, y, OL)
        sparkle4(px, 3, 10, big=False)
        _belt_tassel(px, 2, BELT_H - 1, band)
    else:
        for y in range(2, BELT_H - 2):
            px.put(W - 2, y, 'pu_dk2')
        for x, y in ((W - 2, 1), (W - 2, BELT_H - 2)):
            px.put(x, y, OL)
        _belt_moon(px, 2, 7)
        _belt_tassel(px, 3, BELT_H - 1, band)
    return px


def draw_belt_badge():
    """數量徽章：金扣子（7×7，slice 3）—— 在深紫布上最跳，字是墨色。"""
    N = BELT_BADGE_N
    px = Px(N, N)
    m = rrect(0, 0, N - 1, N - 1, 1)
    for x, y in m:
        px.put(x, y, 'go')
    for x in range(1, N - 1):
        px.put(x, 1, 'go_hi')
        px.put(x, N - 2, 'go_dk')
    for x, y in edge(m):
        px.put(x, y, OL)
    for x, y in ((1, 1), (N - 2, 1), (1, N - 2), (N - 2, N - 2)):
        px.put(x, y, OL)
    return px


def draw_belt_spark():
    """剛拿到新東西：口袋右上角冒出一顆大四角星＋兩顆小亮點（9×9 固定）。"""
    px = Px(9, 9)
    sparkle4(px, 5, 3, big=True)
    for x, y in ((1, 6), (7, 8)):
        px.put(x, y, 'go_hi')
    px.put(1, 7, 'wh')
    return px


# ═══════════════════════════════ 清單 ═══════════════════════════════
# (檔名, 畫法, slice)：slice＝None 表示固定尺寸的小圖，否則是 (左, 上, 右, 下) 邏輯格。

def _skins():
    out = [
        ('panel', draw_panel, (PANEL_SLICE,) * 4),
        ('ribbon', draw_ribbon, (RIBBON_SLICE_X, 5, RIBBON_SLICE_X, 5)),
    ]
    for color in ('green', 'gold', 'wood'):
        out.append((f'btn-{color}', lambda c=color: button_face(BTN_W, BTN_H, BTN_RAMPS[c], 'n'), BTN_SLICE))
        out.append((f'btn-{color}-hover', lambda c=color: button_face(BTN_W, BTN_H, HOVER[c], 'n'), BTN_SLICE))
        out.append((f'btn-{color}-down', lambda c=color: button_face(BTN_W, BTN_H, BTN_RAMPS[c], 'd'), BTN_SLICE))
    out.append(('btn-off', lambda: button_face(BTN_W, BTN_H, BTN_RAMPS['off'], 'n'), BTN_SLICE))
    for st, suf in (('n', ''), ('h', '-hover'), ('d', '-down')):
        out.append((f'close{suf}', lambda s=st: draw_close(s), None))
    for sym in ('minus', 'plus'):
        for st, suf in (('n', ''), ('h', '-hover'), ('d', '-down'), ('x', '-off')):
            out.append((f'step-{sym}{suf}', lambda a=sym, s=st: draw_step(a, s), None))
    for k in ROW_KINDS:
        out.append((k, lambda k=k: draw_row(k), ROW_SLICE))
    for k in ('tab', 'tab-hover', 'tab-on'):
        out.append((k, lambda k=k: draw_tab(k), TAB_SLICE))
    for k in ('slot', 'slot-empty', 'slot-sel'):
        out.append((k, lambda k=k: draw_slot(k), (SLOT_SLICE,) * 4))
    out.append(('well', draw_well, (WELL_SLICE,) * 4))
    out.append(('hud-bar', draw_bar, (BAR_SLICE,) * 4))
    for k in ('scroll-track', 'scroll-thumb', 'scroll-thumb-hover'):
        out.append((k, lambda k=k: draw_scroll(k), SCROLL_SLICE))
    for k in PILLS:
        out.append((k, lambda k=k: draw_pill(k), (PILL_SLICE,) * 4))
    out.append(('keycap', draw_keycap, KEY_SLICE))
    out.append(('divider', draw_divider, DIV_SLICE))
    out += [
        ('coin', draw_coin, None),
        ('heart', lambda: draw_heart(True), None),
        ('heart-off', lambda: draw_heart(False), None),
        ('cell-on', lambda: draw_cell(True), None),
        ('cell-off', lambda: draw_cell(False), None),
    ]
    # ── 第二輪（只往尾巴加；上面 53 張不動）──
    out.append(('scroll-paper', draw_scroll_paper, SCROLL_PAPER_SLICE))
    out.append(('plate', draw_plate, PLATE_SLICE))
    for st, suf in (('n', ''), ('h', '-hover'), ('d', '-down')):
        out.append((f'btn-purple{suf}',
                    lambda s=st: button_face(BTN_W, BTN_H, HOVER2['purple'] if s == 'h' else BTN_RAMPS2['purple'],
                                             'd' if s == 'd' else 'n'), BTN_SLICE))
    out += [
        ('ico-gear', draw_gear, None),
        ('ico-star', draw_star, None),
        ('ico-basket', draw_basket, None),
        ('ico-sack', draw_sack, None),
        ('ico-leaf', draw_leaf, None),
        ('ico-flask', draw_flask, None),
        ('qbox', lambda: draw_qbox(False), None),
        ('qbox-on', lambda: draw_qbox(True), None),
        ('ico-bullet', draw_bullet, None),
    ]
    # ── 第三輪：下排道具列「魔女腰包」（只往尾巴加；上面 67 張不動）──
    out += [
        ('belt-pocket', lambda: draw_belt_pocket('full'), None),
        ('belt-pocket-empty', lambda: draw_belt_pocket('empty'), None),
        ('belt-pocket-new', lambda: draw_belt_pocket('new'), None),
        ('belt-end-l', lambda: draw_belt_end('l'), None),
        ('belt-end-r', lambda: draw_belt_end('r'), None),
        ('belt-badge', draw_belt_badge, (BELT_BADGE_SLICE,) * 4),
        ('belt-spark', draw_belt_spark, None),
    ]
    return out


# 紫色按鈕（上方工具列「關店中」的開關店鈕：夜色＝打烊）。另開一個字典，不動上面 BTN_RAMPS／HOVER。
BTN_RAMPS2 = {'purple': ('pu_hi', 'pu', 'pu_dk', 'pu_dk2')}
HOVER2 = {'purple': ('#c8aee0', 'pu_hi', 'pu', 'pu_dk2')}


SKINS = _skins()
SLICES = {name: sl for name, _, sl in SKINS if sl is not None}


def render_all():
    """回傳 [(名稱, PIL 圖, slice 或 None)]。"""
    return [(name, fn().image(), sl) for name, fn, sl in SKINS]


def md5(p):
    with open(p, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


# ═══════════════════════════════ uss 對照 ═══════════════════════════════

def uss_snippet():
    lines = []
    for name, sl in SLICES.items():
        l, t, r, b = (v * SCALE for v in sl)
        lines.append(f'/* {name} */ background-image: resource("ui/skin8/{name}"); '
                     f'-unity-slice-left: {l}; -unity-slice-top: {t}; -unity-slice-right: {r}; -unity-slice-bottom: {b}; '
                     f'-unity-slice-scale: 1px;')
    return '\n'.join(lines)


def check_uss():
    """
    掃 Skin8.uss：每一個 `{ … }` 區塊裡如果有 resource("ui/skin8/X") 而 X 是九宮格圖，
    同一個區塊裡有寫的 -unity-slice-* 必須等於 SLICES[X]×3；**完全沒寫**的話要在該選擇器的其他區塊裡寫過
    （例如 :hover 只換圖，slice 沿用一般狀態那條）—— 這裡只檢查「寫了但寫錯」與「整份檔都沒寫過」兩種。
    """
    if not os.path.exists(USS_PATH):
        print('找不到', USS_PATH)
        return 1
    src = open(USS_PATH, encoding='utf-8').read()
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    bad = 0
    seen_with_slice = set()
    for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', src):
        for name in re.findall(r'resource\("ui/skin8/([\w-]+)"\)', body):
            if not os.path.exists(os.path.join(OUT_DIR, name + '.png')):
                print(f'✗ {sel.strip()}：skin8/{name}.png 不存在')
                bad += 1
                continue
            if name not in SLICES:
                continue
            want = dict(zip(('left', 'top', 'right', 'bottom'), (v * SCALE for v in SLICES[name])))
            for side, v in re.findall(r'-unity-slice-(left|top|right|bottom)\s*:\s*(\d+)', body):
                seen_with_slice.add(name)
                if int(v) != want[side]:
                    print(f'✗ {sel.strip()}：{name} 的 slice-{side} 寫 {v}，應該是 {want[side]}')
                    bad += 1
    used = set(re.findall(r'resource\("ui/skin8/([\w-]+)"\)', src))
    covered = {SLICES[n] for n in seen_with_slice}
    for name in sorted(used & set(SLICES) - seen_with_slice):
        if SLICES[name] in covered:
            continue      # 狀態圖（:hover、--short…）跟一般狀態同尺寸同 slice，沿用那條規則寫的數字
        print(f'⚠ {name} 是九宮格圖，但整份 Skin8.uss 沒有一處寫它的 -unity-slice-*（確認是不是靠同一元素的別條規則帶過去）')
    print('Skin8.uss 九宮格數字檢查：', '全部一致' if bad == 0 else f'{bad} 處不一致')
    return 1 if bad else 0


# ═══════════════════════════════ 總覽圖 ═══════════════════════════════

def sheet(arts, outdir):
    """所有 skin 圖排成一張：每張放大 2 倍，九宮格圖畫出切線（紅），底下寫名稱與 slice。"""
    from PIL import ImageDraw, ImageFont
    os.makedirs(outdir, exist_ok=True)
    fpath = os.path.join(ROOT, 'Assets', 'Resources', 'ui', 'fonts', 'NotoSansTC.ttf')
    font = ImageFont.truetype(fpath, 13)
    cw, ch = 170, 150
    cols = 8
    rows = (len(arts) + cols - 1) // cols
    out = []
    for tag, bg in (('', (239, 220, 178)), ('_dark', (40, 32, 44))):
        im = Image.new('RGBA', (cols * cw, rows * ch), bg + (255,))
        d = ImageDraw.Draw(im)
        for i, (name, art, sl) in enumerate(arts):
            x0, y0 = (i % cols) * cw, (i // cols) * ch
            k = 2 if art.width <= 80 and art.height <= 60 else 1
            big = art.resize((art.width * k, art.height * k), Image.NEAREST)
            ox, oy = x0 + (cw - big.width) // 2, y0 + 8
            im.alpha_composite(big, (ox, oy))
            if sl:
                l, t, r, b = (v * SCALE * k for v in sl)
                red = (220, 40, 60, 255)
                d.line([(ox + l, oy), (ox + l, oy + big.height - 1)], fill=red)
                d.line([(ox + big.width - r, oy), (ox + big.width - r, oy + big.height - 1)], fill=red)
                d.line([(ox, oy + t), (ox + big.width - 1, oy + t)], fill=red)
                d.line([(ox, oy + big.height - b), (ox + big.width - 1, oy + big.height - b)], fill=red)
            fg = (60, 40, 30) if not tag else (236, 228, 214)
            lab = name
            sub = f'{art.width}×{art.height}' + (f'  slice {",".join(str(v * SCALE) for v in sl)}' if sl else '')
            d.text((x0 + 6, y0 + ch - 36), lab, fill=fg, font=font)
            d.text((x0 + 6, y0 + ch - 19), sub, fill=fg, font=font)
        p = os.path.join(outdir, f'skin_sheet{tag}.png')
        im.save(p)
        out.append(p)
    return out


def main():
    args = sys.argv[1:]
    if '--check' in args:
        sys.exit(check_uss())
    if '--uss' in args:
        print(uss_snippet())
        return
    if os.path.isdir(ICONS8_DIR):
        print(f'ℹ 發現 {ICONS8_DIR}（另一支產生器的圖示）—— 這裡只畫 UI 外框用的符號，重複的請在 uss 裡改指向 icons8')
    arts = render_all()
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, im, sl in arts:
        p = os.path.join(OUT_DIR, name + '.png')
        im.save(p, optimize=False)
        s = f'slice {",".join(str(v * SCALE) for v in sl)}' if sl else '固定尺寸'
        print(f'{name:<20} {im.width:>3}×{im.height:<3} {s:<22} {md5(p)[:8]}')
    print(f'共 {len(arts)} 張 → {OUT_DIR}')
    if '--sheet' in args:
        for p in sheet(arts, args[args.index('--sheet') + 1]):
            print('總覽', p)


if __name__ == '__main__':
    main()
