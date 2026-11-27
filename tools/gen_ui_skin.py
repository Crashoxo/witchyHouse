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
  * 例外：下排道具列「魔女腰包」7 張 belt-*（2026-11-27 細畫版）直接以 1 px 原生像素畫（_BeltPx，不放大），
    圖的尺寸與 slice 仍是 3 的倍數，排版規則不變。見檔尾「下排道具列」一段。
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
import math
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


# draw_keycap（鍵帽 24×27）：2026-11-27 改成 1 px 細畫版，移到檔尾「上方工具列」一段。


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


# draw_coin（金幣 21×21）：2026-11-27 改成 1 px 細畫版，移到檔尾「上方工具列」一段。


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


def draw_page(side, state):
    """
    翻頁小鈕（11×11 固定尺寸，2026-11-27 清單翻頁用，UI/Pager.cs）：跟 ± 小鈕同一顆木頭按鈕，
    符號換成實心三角（◀／▶，3 格寬 5 格高，尖端朝外）。state 多一個 'x'＝停用（第一頁的 ◀、最後一頁的 ▶）。
    """
    if state == 'x':
        px = button_face(11, 11, BTN_RAMPS['off'], 'n')
        ink, sh = 'st_off_hi', 'st_off_dk'
    else:
        px = button_face(11, 11, HOVER['wood'] if state == 'h' else BTN_RAMPS['wood'], state)
        ink, sh = 'li_hi', 'wd_dk2'
    oy = 1 if state == 'd' else 0
    # 往左：x=4 尖端（1 格）、x=5 三格、x=6 五格；往右左右對調
    cols = [(4, 1), (5, 3), (6, 5)] if side == 'prev' else [(6, 1), (5, 3), (4, 5)]
    pts = []
    for x, n in cols:
        y0 = 4 - n // 2
        pts += [(x, y0 + i + oy) for i in range(n)]
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


# draw_gear（齒輪 33×33）：2026-11-27 改成 1 px 細畫版，移到檔尾「上方工具列」一段。


# draw_star（名聲星 27×27）：2026-11-27 改成 1 px 細畫版，移到檔尾「上方工具列」一段。


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


# ═══════════════════════════════ 下排道具列：魔女腰包（第三輪；2026-11-27 細畫版）═══════════════════════════════
# 深紫布條＋上下金線針腳，每格是布上縫出來的口袋，兩端是金扣（左星、右月）＋垂下的金流蘇。
# ⚠️ 這 7 張**不走上面的 ×3 邏輯格**：直接在輸出解析度上一個 px 一個 px 畫（_BeltPx.image() 不放大），
#    細緻度對齊女巫走路圖（witch8：1 px 原生像素、約 40 色、多階色相偏移的陰影）。
#    色盤另開 BELT_PAL（布：暗部偏靛藍、亮部偏粉；金：暗部偏橘棕、亮部偏奶油），不動上面的 PAL。
#    允許半透明的只有：布條底下 3 列落地陰影、口袋／扣子投在布上的影子、亮光星的柔光。
# ⚠️ 全部是**固定尺寸**的圖、一格一張（金線針腳拉長會變實線，所以不用九宮格拉布條）：
#    InventoryHud 把 [左端][口袋]×N[右端] 一個接一個排起來。布條上下的針腳週期 3 px（亮、中、針孔），
#    口袋寬 51、左端寬 18 都是 3 的倍數，所以任何格數都接得上。
#   口袋 belt-pocket / -empty / -new  51×60：布條 0～56 列＋57～59 列落地陰影；縫上去的布片 x 4～49、y 9～51
#     （道具圖 48×48 疊在 (3, 6)，中心 26.5 ＝ 布片中心）。有東西：袋口張開、看得到沉穩的灰藕紫襯裡；
#     空：袋口闔成一條細縫、前片拉到上面、淡淡的刺繡小星；剛拿到：襯裡透出暖金粉色光、金線變亮。
#   兩端 belt-end-l（星星金扣）/ belt-end-r（月牙金扣） 18×78：布條外側圓角，底下垂一串金流蘇（到 y≈76）。
#   數量徽章 belt-badge 21×21、九宮格 slice 9（BELT_BADGE_SLICE＝3 是邏輯格，×3＝9 px；中間 3×3 每欄同色，橫向拉長不出條紋）；
#   新東西亮光 belt-spark 27×27（固定）。
# 跟 hud-bar／slot 是不同的圖：那兩張還有上方工具列、Toast、托盤、背包面板在用，一個像素都不動。

BELT_W, BELT_H = 51, 60              # 口袋（輸出 px）
BELT_END_W, BELT_END_H = 18, 78      # 兩端（輸出 px）
BELT_BADGE_N, BELT_BADGE_SLICE = 21, 3   # 徽章 21 px；slice 照 SLICES 慣例寫邏輯格（×3 ＝ 9 px）
BELT_SPARK_N = 27

BELT_PAL = {
    'ol': '#1d1024',    # 外輪廓（深紫黑）
    # 布：c1 最暗 → c8 最亮；c4 是底色，c4w 是織紋（只亮一點點）
    'c1': '#28163a', 'c2': '#35204c', 'c3': '#42295d', 'c4': '#4f316c', 'c4w': '#553674',
    'c5': '#5f3c7d', 'c6': '#73498f', 'c7': '#8c5ea2', 'c8': '#a979b4',
    # 金線／金扣：g0 針孔 → g5 奶油高光
    'g0': '#3e2016', 'g1': '#6e4220', 'g2': '#a06c2c', 'g3': '#d39f45', 'g4': '#f0cb6a', 'g5': '#fff0b4',
    # 口袋襯裡（有東西）：沉穩的中間調灰藕紫，比布條亮 —— 深色道具的外框也分得出來
    'i0': '#2a1c38', 'i1': '#3e2d4f', 'i2': '#52405f', 'i3': '#644f74', 'i4': '#735e83', 'i5': '#816b90',
    # 口袋襯裡（剛拿到）：暖暖的金粉色光
    'n0': '#3e2436', 'n1': '#5e3a4a', 'n2': '#80545c', 'n3': '#a06e66', 'n4': '#bf8c72', 'n5': '#d9ab82',
    # 徽章扣面（上淺下深的圓頂）
    'b1': '#fbe9ac', 'b2': '#f5da8a', 'b3': '#ecc96c', 'b4': '#dcb256',
    'wh': '#fffbef',
}
_BELT_SHADOW = ('#140a1c', (0.42, 0.24, 0.10))   # 布條底下 3 列落地陰影（顏色, 每列不透明度）
_BELT_BAND_H = 57                                  # 布條本體 0～56 列
_BELT_STITCH_TOP, _BELT_STITCH_BOT = 3, 53


def _bc(c):
    h = BELT_PAL.get(c, c)
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


class _BeltPx:
    """腰包用的 1 px 畫布（直接是輸出解析度；可以疊半透明）。介面跟 Px 一樣有 image()。"""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        self.px = self.im.load()

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = _bc(c) + (255,)

    def shade(self, x, y, c, a):
        """疊一層不透明度 a 的 c；底是透明的就直接放半透明像素（落地陰影）。"""
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        r, g, b, al = self.px[x, y]
        cr, cg, cb = _bc(c)
        if al == 0:
            self.px[x, y] = (cr, cg, cb, int(round(255 * a)))
        else:
            self.px[x, y] = (round(r + (cr - r) * a), round(g + (cg - g) * a), round(b + (cb - b) * a), al)

    def image(self):
        return self.im


def _belt_color(x, y):
    """
    布條第 y 列、整條腰帶座標 x 的顏色（由上往下）：外輪廓、捲邊高光兩列、金線（週期 3：亮／中／針孔）、
    線下小陰影、折邊、摺痕、摺痕受光、布身（上亮下暗＋斜紋織理）、下摺痕、下折邊、金線、線下陰影、暗邊、外輪廓。
    """
    if y in (0, _BELT_BAND_H - 1):
        return 'ol'
    if y == 1:
        return 'c8'
    if y == 2:
        return 'c7'
    ph = x % 3
    if y == _BELT_STITCH_TOP:
        return ('g5', 'g3', 'c2')[ph]
    if y == _BELT_STITCH_TOP + 1:
        return ('c3', 'c3', 'c5')[ph]
    if y == _BELT_STITCH_BOT:
        return ('g4', 'g2', 'c1')[ph]
    if y == _BELT_STITCH_BOT + 1:
        return ('c1', 'c1', 'c3')[ph]
    row = {5: 'c5', 6: 'c2', 7: 'c6', 51: 'c2', 52: 'c5', 55: 'c2'}
    if y in row:
        return row[y]
    t = (y - 8) / 42.0     # 布身 8～50
    base = 'c5' if t < 0.10 else ('c4' if t < 0.62 else ('c3' if t < 0.88 else 'c2'))
    if (x + 2 * y) % 5 == 0:
        return {'c5': 'c6', 'c4': 'c4w', 'c3': 'c4', 'c2': 'c3'}[base]
    if (x - y) % 7 == 0 and base == 'c4':
        return 'c3'
    return base


# 縫上去的布片（後片上緣直角縫在布條上，下緣圓角）
_BELT_PX0, _BELT_PX1, _BELT_PTOP, _BELT_PBOT = 4, 49, 9, 51


def _belt_pocket_mask():
    m = set()
    r = 5
    for y in range(_BELT_PTOP, _BELT_PBOT + 1):
        for x in range(_BELT_PX0, _BELT_PX1 + 1):
            dy = y - (_BELT_PBOT - r)
            if dy > 0:
                dx = max(_BELT_PX0 + r - x, x - (_BELT_PX1 - r), 0)
                if dx > 0 and dx * dx + dy * dy > r * r + 1:
                    continue
            m.add((x, y))
    return m


def _belt_lip(x, kind):
    """袋口（前片上緣）的 y：中間低、兩邊高的笑臉弧。空口袋闔起來：扁、而且在比較上面。"""
    cx = (_BELT_PX0 + _BELT_PX1) / 2.0
    u = (x - cx) / ((_BELT_PX1 - _BELT_PX0) / 2.0)
    if kind == 'empty':
        return int(round(15 + 3 * (1 - u * u)))
    return int(round(23 + 6 * (1 - u * u)))


def _belt_rivet(px, x, y, bright=True):
    """袋口兩端的 3×3 金鉚釘（外輪廓去掉四角＝圓的；左上受光）。(x, y)＝中心。"""
    for dx, dy in ((-2, -1), (-2, 0), (-2, 1), (2, -1), (2, 0), (2, 1),
                   (-1, -2), (0, -2), (1, -2), (-1, 2), (0, 2), (1, 2)):
        px.put(x + dx, y + dy, 'ol')
    hi, mid, dk = ('g5', 'g3', 'g1') if bright else ('g3', 'g2', 'g1')
    for dx, dy, c in ((-1, -1, hi), (0, -1, hi), (1, -1, mid), (-1, 0, hi), (0, 0, mid), (1, 0, dk),
                      (-1, 1, mid), (0, 1, dk), (1, 1, dk)):
        px.put(x + dx, y + dy, c)


def draw_belt_pocket(kind):
    """
    kind：'full'（有東西：袋口張開、灰藕紫襯裡、前片左上鼓起的高光）／
    'empty'（空：袋口闔成細縫、前片平、淡淡的刺繡小星、金線與鉚釘暗一階）／
    'new'（剛拿到：襯裡換暖金粉色光、金線最亮）。
    """
    px = _BeltPx(BELT_W, BELT_H)
    col, alphas = _BELT_SHADOW
    for x in range(BELT_W):
        for y in range(_BELT_BAND_H):
            px.put(x, y, _belt_color(x, y))
        for i, a in enumerate(alphas):
            px.shade(x, _BELT_BAND_H + i, col, a)
    m = _belt_pocket_mask()
    x0, x1 = _BELT_PX0, _BELT_PX1
    cx = (x0 + x1) / 2.0
    for x, y in m:                       # 布片投在布條上的影子（右下 1 px）
        q = (x + 1, y + 1)
        if q not in m and q[1] < _BELT_BAND_H - 1:
            px.shade(q[0], q[1], 'c1', 0.55)
    lips = {x: _belt_lip(x, kind) for x in range(x0, x1 + 1)}
    inner = ('n0', 'n1', 'n2', 'n3', 'n4', 'n5') if kind == 'new' else ('i0', 'i1', 'i2', 'i3', 'i4', 'i5')
    for x, y in m:
        ly = lips[x]
        if y < ly and kind != 'empty':
            # 襯裡：以 (cx, 16) 為中心的柔和橢圓漸層（道具就躺在最亮那圈），越靠袋口與上緣越暗
            ex, ey = (x - cx) / 25.0, (y - 16) / 15.0
            v = 5 - int((ex * ex + ey * ey) ** 0.5 * 4.2)
            d_lip = ly - y
            if d_lip <= 1:
                v = min(v, 0)
            elif d_lip == 2:
                v = min(v, 1)
            elif d_lip == 3:
                v -= 1
            if y <= _BELT_PTOP + 1:
                v = min(v, 1)
            elif y == _BELT_PTOP + 2:
                v -= 1
            px.put(x, y, inner[max(0, min(5, v))])
        else:
            # 前片（布）：比布條亮一階；有東西時左上一小團三階的鼓起高光
            if kind == 'empty':
                ex, ey = (x - (cx - 3)) / 20.0, (y - 30) / 14.0
                c = 'c5' if ex * ex + ey * ey < 0.6 else 'c4'
            else:
                ex, ey = (x - (cx - 6)) / 15.0, (y - (ly + 9)) / 8.0
                r2 = ex * ex + ey * ey
                c = 'c7' if r2 < 0.12 else ('c6' if r2 < 0.6 else 'c5')
            if (x + 2 * y) % 7 == 0 and c in ('c5', 'c4'):
                c = 'c6' if c == 'c5' else 'c4w'
            px.put(x, y, c)
    for x, y in m:                       # 前片下緣兩列暗（布片的厚度）
        if ((x, y + 1) not in m or (x, y + 2) not in m) and y >= lips[x]:
            px.put(x, y, 'c3' if (x, y + 1) in m else 'c2')
    for x, y in m:                       # 布片外框（上緣是後片縫在布條上，用暗紫不用外輪廓）
        if not {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} <= m:
            px.put(x, y, 'ol' if (y > _BELT_PTOP or kind == 'empty') else 'c1')
    for x in range(x0 + 1, x1):
        px.put(x, _BELT_PTOP, 'c1')
        if kind == 'empty':
            px.put(x, _BELT_PTOP + 1, 'c6')
    for y in range(_BELT_PTOP + 1, _BELT_PBOT - 4):   # 前片兩側：左亮右暗
        if y > lips[x0 + 1]:
            px.put(x0 + 1, y, 'c5' if kind == 'empty' else 'c7')
        if y > lips[x1 - 1]:
            px.put(x1 - 1, y, 'c3')
    for x in range(x0 + 1, x1):          # 袋口：前片上緣一條亮邊（布的厚度）＋上面一列最暗（袋內陰影／闔起來的細縫）
        ly = lips[x]
        if kind == 'empty':
            px.put(x, ly - 1, 'c1')
            px.put(x, ly, 'c7')
        else:
            px.put(x, ly - 1, inner[0])
            px.put(x, ly, 'c8')
        px.put(x, ly + 1, 'c6')
    # 前片上的金線：沿袋口弧線往下 4 列一道（線下有一點陰影），再一圈 U 形沿兩側與底邊（週期 3：亮、中、空）
    st_hi, st_lo = {'new': ('g5', 'g3'), 'empty': ('g3', 'g2')}.get(kind, ('g4', 'g2'))
    for x in range(x0 + 4, x1 - 3):
        y = lips[x] + 4
        ph = (x - x0) % 3
        if ph == 2:
            px.put(x, y, 'c3')
        else:
            px.put(x, y, st_hi if ph == 0 else st_lo)
            px.shade(x, y + 1, 'c1', 0.35)
    lx, rx, by = x0 + 3, x1 - 3, _BELT_PBOT - 3
    pts = [(lx, y) for y in range(lips[lx] + 4, by - 2)]
    pts += [(x, by) for x in range(lx + 3, rx - 2)]
    pts += [(rx, y) for y in range(lips[rx] + 4, by - 2)]
    pts += [(lx + 1, by - 2), (lx + 2, by - 1), (rx - 1, by - 2), (rx - 2, by - 1)]   # 底角斜接
    for x, y in pts:
        ph = (x + y) % 3
        if ph != 2:
            px.put(x, y, st_hi if ph == 0 else st_lo)
    _belt_rivet(px, x0 + 3, lips[x0 + 3] + 1, bright=(kind != 'empty'))
    _belt_rivet(px, x1 - 3, lips[x1 - 3] + 1, bright=(kind != 'empty'))
    if kind == 'empty':                  # 淡淡的刺繡小星（布色的線，不搶眼）
        sx, sy = 26, 33
        for (dx, dy), c in {(0, -4): 'c7', (0, -3): 'c7', (0, -2): 'c7', (-1, -1): 'c7', (0, -1): 'c8', (1, -1): 'c6',
                            (-4, 0): 'c7', (-3, 0): 'c7', (-2, 0): 'c7', (-1, 0): 'c8', (0, 0): 'c8', (1, 0): 'c7',
                            (2, 0): 'c6', (3, 0): 'c6', (4, 0): 'c6', (-1, 1): 'c7', (0, 1): 'c7', (1, 1): 'c6',
                            (0, 2): 'c6', (0, 3): 'c6', (0, 4): 'c6', (5, -4): 'c6', (-5, 4): 'c6'}.items():
            px.put(sx + dx, sy + dy, c)
    return px


def _belt_end_mask(side):
    """布條端點：外側上下圓角 r=6（接口袋那側直的）。"""
    m = set()
    r = 6
    for y in range(_BELT_BAND_H):
        for x in range(BELT_END_W):
            xo = x if side == 'l' else BELT_END_W - 1 - x
            dx = max(r - xo, 0)
            dy = max(r - y, y - (_BELT_BAND_H - 1 - r), 0)
            if dx and dy and (dx - 0.5) ** 2 + (dy - 0.5) ** 2 > r * r:
                continue
            m.add((x, y))
    return m


def _belt_disc(px, cx, cy, R):
    """金圓扣：外輪廓、外斜面（左上亮右下暗）、內斜面（反過來）、扣面，右下投影在布上。"""
    for y in range(cy - R - 1, cy + R + 2):
        for x in range(cx - R - 1, cx + R + 2):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if d > R + 0.5:
                continue
            lt = (x - cx) + (y - cy) < 0
            if d > R - 0.6:
                px.put(x, y, 'ol')
            elif d > R - 1.7:
                px.put(x, y, 'g4' if lt else 'g1')
            elif d > R - 2.8:
                px.put(x, y, 'g2' if lt else 'g3')
            else:
                px.put(x, y, 'g3')
    for y in range(cy - R, cy + R + 3):
        for x in range(cx - R, cx + R + 3):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            d2 = ((x - cx - 1.5) ** 2 + (y - cy - 1.5) ** 2) ** 0.5
            if d > R + 0.5 and d2 <= R + 0.5 and y < _BELT_BAND_H - 1:
                px.shade(x, y, 'c1', 0.6)


def _belt_clasp_star(px, cx, cy):
    """左端：金圓扣，扣面浮雕一顆五角星（星面亮、右下一格壓痕）。"""
    _belt_disc(px, cx, cy, 7)
    rows = ['...x...', '...x...', 'xxxxxxx', '.xxxxx.', '..xxx..', '.xx.xx.', 'x.....x']
    pts = {(cx - 3 + i, cy - 3 + j) for j, r in enumerate(rows) for i, ch in enumerate(r) if ch == 'x'}
    for x, y in pts:
        if (x + 1, y + 1) not in pts:
            px.put(x + 1, y + 1, 'g2')
    for x, y in pts:
        px.put(x, y, 'g5' if (x - cx) + (y - cy) <= 0 else 'g4')
    px.put(cx - 4, cy - 5, 'wh')


def _belt_clasp_moon(px, cx, cy):
    """右端：金月牙扣（往右開口的弦月），多階金色由左上亮到右下暗。"""
    R = 8
    pts = set()
    for y in range(cy - R, cy + R + 1):
        for x in range(cx - R, cx + R + 1):
            d1 = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            d2 = ((x - cx - 4) ** 2 + (y - cy + 1) ** 2) ** 0.5
            if d1 <= R - 0.3 and d2 > R - 2.2:
                pts.add((x, y))
    for x, y in pts:
        if (x + 1, y + 1) not in pts:
            px.shade(x + 2, y + 1, 'c1', 0.55)
    for x, y in pts:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in pts:
                px.put(x + dx, y + dy, 'ol')
    for x, y in pts:
        if not all((x + dx, y + dy) in pts for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            c = 'g4' if (x - cx) + (y - cy) < 0 else 'g1'
        else:
            t = (x - cx) * 0.6 + (y - cy)
            c = 'g5' if t < -4 else ('g4' if t < 0 else ('g3' if t < 4 else 'g2'))
        px.put(x, y, c)
    px.put(cx - 5, cy - 3, 'wh')


def _belt_tassel(px, cx):
    """布條下緣垂下的金流蘇：繩、結、圓帽、一圈紫色纏線、往下散開的七條細流蘇（左亮右暗、末端參差）。"""
    y0 = _BELT_BAND_H - 2
    shape = {}
    for y in range(y0, y0 + 3):
        shape[(cx, y)] = 'g3' if y % 2 else 'g2'
    k = y0 + 3
    for j, row in enumerate((((-1, 'g4'), (0, 'g3'), (1, 'g2')),
                             ((-1, 'g5'), (0, 'g4'), (1, 'g2')),
                             ((-2, 'g4'), (-1, 'g5'), (0, 'g4'), (1, 'g3'), (2, 'g1')),
                             ((-2, 'g3'), (-1, 'g4'), (0, 'g3'), (1, 'g2'), (2, 'g1')),
                             ((-2, 'c7'), (-1, 'c8'), (0, 'c6'), (1, 'c5'), (2, 'c3')))):
        for dx, c in row:
            shape[(cx + dx, k + j)] = c
    fr = k + 5
    darker = {'g5': 'g4', 'g4': 'g3', 'g3': 'g2', 'g2': 'g1', 'g1': 'g1'}
    for dx, (c, start, end) in {-3: ('g4', 2, 7), -2: ('g5', 0, 9), -1: ('g3', 0, 9), 0: ('g4', 0, 11),
                                1: ('g2', 0, 10), 2: ('g3', 0, 8), 3: ('g1', 2, 6)}.items():
        for j in range(start, end):
            shape[(cx + dx, fr + j)] = darker[c] if j == end - 1 else c
    for (x, y), c in shape.items():
        px.put(x, y, c)
    for x, y in shape:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in shape and q[1] >= _BELT_BAND_H - 1:
                px.put(q[0], q[1], 'ol')


def draw_belt_end(side):
    """布條的兩端：'l' ＝ 左端（星星金扣），'r' ＝ 右端（月牙金扣）。外側圓角、底下落地陰影、垂一串金流蘇。"""
    W = BELT_END_W
    px = _BeltPx(W, BELT_END_H)
    m = _belt_end_mask(side)
    x0w = -W if side == 'l' else 0       # 整條腰帶座標：寬度都是 3 的倍數，針腳週期照樣接得上
    for x, y in m:
        px.put(x, y, _belt_color(x + x0w, y))
    col, alphas = _BELT_SHADOW
    for x in range(W):
        ys = [y for (xx, y) in m if xx == x]
        for i, a in enumerate(alphas):
            px.shade(x, max(ys) + 1 + i, col, a)
    for x, y in m:                       # 外輪廓（接口袋那一側不畫）
        if not {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} <= m:
            if ((side == 'l' and x == W - 1) or (side == 'r' and x == 0)) and y not in (0, _BELT_BAND_H - 1):
                continue
            px.put(x, y, 'ol')
    if side == 'l':
        _belt_clasp_star(px, 9, 28)
        _belt_tassel(px, 9)
    else:
        _belt_clasp_moon(px, 8, 28)
        _belt_tassel(px, 8)
    return px


def draw_belt_badge():
    """數量徽章：金扣子（21×21，slice 9）—— 外輪廓、金邊（上亮下暗）、上淺下深的圓頂扣面、左上亮點，字是墨色。"""
    N = BELT_BADGE_N
    px = _BeltPx(N, N)
    c = (N - 1) / 2.0

    def inside(x, y, rr):
        # 角是 1/4 圓、中間 3 欄 3 列是直的（九宮格拉長的部分每欄同色）
        dx = max(abs(x - c) - 1.0, 0)
        dy = max(abs(y - c) - 1.0, 0)
        return dx * dx + dy * dy <= rr * rr

    R = 9.6
    for y in range(N):
        for x in range(N):
            if not inside(x, y, R):
                continue
            if not inside(x, y, R - 1.2):
                px.put(x, y, 'ol')
            elif not inside(x, y, R - 2.3):
                px.put(x, y, 'g3' if y < c - 2 else ('g1' if y > c + 2 else 'g2'))
            else:
                px.put(x, y, 'b1' if y < c - 4 else ('b2' if y <= c + 2 else ('b3' if y <= c + 5 else 'b4')))
    for x, y, cc in ((5, 4, 'wh'), (4, 5, 'wh'), (6, 4, 'g5'), (4, 6, 'g5')):
        px.put(x, y, cc)
    return px


def draw_belt_spark():
    """剛拿到新東西：口袋右上角一顆細長尖的大四角星（帶半透明柔光）＋兩顆小亮點（27×27 固定）。"""
    N = BELT_SPARK_N
    px = _BeltPx(N, N)
    cx, cy = 15, 10
    for y in range(N):
        for x in range(N):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if d < 7.5:
                px.shade(x, y, 'g5', 0.22 * (1 - d / 7.5))
    pts = {(cx + dx, cy + dy) for dx in range(-2, 3) for dy in range(-2, 3) if abs(dx) + abs(dy) <= 2}
    for i in range(1, 9):
        for s in (-1, 1):
            pts.add((cx + s * i, cy))
            pts.add((cx, cy + s * i))
            if i <= 2:
                pts.add((cx + s * i, cy + s))
    for x, y in pts:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in pts:
                px.put(x + dx, y + dy, 'ol')
    for x, y in pts:
        d = abs(x - cx) + abs(y - cy)
        c = 'g5' if d <= 1 else ('g4' if d <= 4 else 'g3')
        px.put(x, y, 'g3' if (x > cx and y > cy) else c)
    px.put(cx, cy, 'wh')
    px.put(cx - 1, cy - 1, 'wh')
    for (x, y), big in (((5, 19), True), ((22, 22), False)):
        dot = {(x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)} if big else {(x, y)}
        for p in dot:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (p[0] + dx, p[1] + dy) not in dot:
                    px.put(p[0] + dx, p[1] + dy, 'ol')
        for p in dot:
            px.put(p[0], p[1], 'g4')
        px.put(x, y, 'wh')
    return px


# ═══════════════════════════════ 上方工具列（2026-11-27 細畫版）═══════════════════════════════
# 使用者：「上方的狀態列也要精緻化」—— 跟下排腰包同一套：深紫布＋金滾邊／金釘，1 px 原生像素直接畫（_TbPx，不放大）。
# 新圖一律 tb- 開頭、只給 CornerHud（.hud-corner／.hud-sep／.hud-shop／.hud-edit／.hud-settings／名聲量表）與
# 時鐘下的兩顆牌（.sk-clock-time／-date）用；舊的 hud-bar／btn-*／badge／tag-gold 一個像素都不動（別的面板還在用）。
#   tb-bar        48×48  slice 18（＝hud-bar）：布底座、捲邊高光、一圈實線金滾邊、四角金菱形釘、下方 3 列落地陰影。
#   tb-sep         6×30  固定：縫線分隔（凹槽＋一排金針腳＋上下小金釘），底色＝tb-bar 中間的 c4。
#   tb-open／-hover／-down、tb-closed／-hover／-down、tb-off、tb-set／-hover／-down  30×36  slice 12/12/12/15（＝btn-*）：
#                  開店＝暖蜂蜜金牌、關店＝夜色靛藍牌（月白邊）、停用＝灰藕、設定＝紫布牌金邊；按下＝面板往下 3、厚邊收掉。
#   tb-tag／tb-tag-off  21×21 slice 9：R 佈置提示（可按＝亮紫浮起＋亮金邊；上鎖＝暗紫凹槽＋暗金邊）。
#   tb-plate      21×21  slice 9：時鐘的時刻／日期牌（深紫面＋金邊＋2 列落地陰影）。
#   tb-gauge      18×12  slice 6：名聲量表的槽（金邊＋深紫槽）；填充是 uss 的色塊，padding 3 塞在槽裡。
# ⚠️ 九宮格會拉長的邊只能是「沿拉長方向一致」的實線：金滾邊不畫針腳（拉長會糊成一團），針腳只放在固定尺寸的 tb-sep。
# ⚠️ 尺寸與 slice 都是 3 的倍數，SLICES 仍照慣例寫邏輯格（×3 才是 px）。
# 同一輪也把工具列用到的共用小圖重畫成 1 px 細畫（尺寸不變）：coin 21、ico-star 27、ico-gear 33、keycap 24×27（slice 9/9/9/12）。
#   這四張別的面板也在用（價格、每日結算、任務獎勵、各面板底部的鍵帽說明），外觀概念不變，只是更細。

TB_PAL = {
    # 開店：暖蜂蜜金面板
    'o_hi2': '#fff3c4', 'o_hi': '#fbe39a', 'o': '#f3cf74', 'o_md': '#e8b95a', 'o_dk': '#d39d43',
    'o_e1': '#b07632', 'o_e2': '#8a5424', 'o_e3': '#5e3519',
    # 關店：夜色靛藍（邊是月白）
    'n_hi2': '#7d76b4', 'n_hi': '#5f589a', 'n': '#4a4483', 'n_md': '#3f3974', 'n_dk': '#353064',
    'n_e1': '#28234d', 'n_e2': '#1e1a3c', 'n_e3': '#15112a', 'n_rim': '#b9b2dc', 'n_rim2': '#8a83b8',
    'n_rim_h': '#d8d2f2', 'n_hi3': '#9690c8',
    # 停用：灰藕
    'x_hi2': '#d4cedb', 'x_hi': '#b9b2c2', 'x': '#a39cae', 'x_md': '#968fa2', 'x_dk': '#888196',
    'x_e1': '#6c6579', 'x_e2': '#554f61', 'x_e3': '#3e3948',
    # 設定鈕滑過時最亮的布
    'c9': '#c493c8',
    # 鍵帽（象牙白）
    'k_hi': '#fffdf4', 'k': '#f8efda', 'k_md': '#efe2c4', 'k_dk': '#dccaa4',
    'k_s1': '#c2ab84', 'k_s2': '#a08766', 'k_s3': '#7a6350',
    'gem_hi': '#e8c8f0',
}
_TB_SHADOW = '#140a1c'


class _TbPx(_BeltPx):
    """工具列用的 1 px 畫布：色鍵先查 TB_PAL、再查 BELT_PAL（_BeltPx 也認直接寫的 #hex）。"""

    def put(self, x, y, c):
        super().put(x, y, TB_PAL.get(c, c))

    def shade(self, x, y, c, a):
        super().shade(x, y, TB_PAL.get(c, c), a)


def _tb_rounded(w, h, r, x0=0, y0=0):
    """圓角矩形遮罩（像素中心落在圓角內才算）。"""
    m = set()
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            cx = min(max(x + 0.5, x0 + r), x0 + w - r)
            cy = min(max(y + 0.5, y0 + r), y0 + h - r)
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r + 0.3:
                m.add((x, y))
    return m


def _tb_layers(m, n):
    """由外往內剝 n 圈（每圈＝目前遮罩的 4 鄰接外緣），回傳 (各圈, 剩下的內部)。"""
    inner, out = set(m), []
    for _ in range(n):
        e = edge(inner)
        out.append(e)
        inner -= e
    return out, inner


def _tb_drop_shadow(px, m, alphas):
    for x in range(px.w):
        ys = [y for (xx, y) in m if xx == x]
        if ys:
            for i, a in enumerate(alphas):
                px.shade(x, max(ys) + 1 + i, _TB_SHADOW, a)


def _tb_stud(px, cx, cy):
    """5×5 金菱形釘：外輪廓、依「左上→右下」五階金、中心偏左上一點白。"""
    for dx, dy in ((0, -3), (-1, -2), (1, -2), (-2, -1), (2, -1), (-3, 0), (3, 0),
                   (-2, 1), (2, 1), (-1, 2), (1, 2), (0, 3)):
        px.put(cx + dx, cy + dy, 'ol')
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if abs(dx) + abs(dy) <= 2:
                s = dx + dy
                px.put(cx + dx, cy + dy, ('g5', 'g4', 'g3', 'g2', 'g1')[max(0, min(4, s + 2))])
    px.put(cx - 1, cy - 1, 'wh')


def draw_tb_bar():
    """工具列底座（48×48，slice 18）：外輪廓→捲邊亮兩圈→金滾邊兩圈（亮／暗）→滾邊陰影→中間純色 c4。"""
    N = 48
    H = N - 3                       # 本體 0～44，45～47 是落地陰影
    px = _TbPx(N, N)
    m = _tb_rounded(N, H, 5)
    for x, y in m:
        px.put(x, y, 'c4')
    L, _ = _tb_layers(m, 6)

    def lit(x, y, d):               # 上緣或左緣（離右下角遠）＝受光
        return (y <= d and x < N - 1 - d) or (x <= d and y < H - 1 - d)
    for x, y in L[0]:
        px.put(x, y, 'ol')
    for x, y in L[1]:
        px.put(x, y, 'c8' if (y <= 2 and x < N - 3) else ('c7' if (x <= 2 and y < H - 3) else ('c2' if y >= H - 3 else 'c3')))
    for x, y in L[2]:
        px.put(x, y, 'c6' if (y <= 3 and x < N - 4) else ('c5' if (x <= 3 and y < H - 4) else 'c3'))
    for x, y in L[3]:
        px.put(x, y, 'g4' if lit(x, y, 4) else 'g3')
    for x, y in L[4]:
        px.put(x, y, 'g2' if lit(x, y, 5) else 'g1')
    for x, y in L[5]:
        px.put(x, y, 'c3' if lit(x, y, 6) else 'c5')
    for cx, cy in ((5, 5), (N - 6, 5), (5, H - 6), (N - 6, H - 6)):
        _tb_stud(px, cx, cy)
    _tb_drop_shadow(px, m, (0.42, 0.24, 0.10))
    return px


def draw_tb_sep():
    """分隔（6×30 固定）：布色底、中間一道凹槽（暗＋亮）、槽上縫一排金針腳（週期 3）、上下各一顆小金釘。"""
    W, H = 6, 30
    px = _TbPx(W, H)
    for y in range(H):
        for x, c in enumerate(('c4', 'c3', 'c1', 'c6', 'c5', 'c4')):
            px.put(x, y, c)
    for y in range(4, H - 4):
        ph = y % 3
        if ph == 0:
            px.put(2, y, 'g4'); px.put(3, y, 'g3')
        elif ph == 1:
            px.put(2, y, 'g3'); px.put(3, y, 'g2')
    for cy in (1, H - 2):
        for x, y in ((2, cy - 1), (3, cy - 1), (1, cy), (4, cy), (2, cy + 1), (3, cy + 1)):
            px.put(x, y, 'ol')
        px.put(2, cy, 'g5'); px.put(3, cy, 'g3')
    return px


TB_BTN_W, TB_BTN_H = 30, 36
#            邊亮      邊        邊暗     面最亮   面亮     面      面中    面暗     厚邊 1  厚邊 2  厚邊 3
TB_BTN = {
    'open':     ('g5', 'g4', 'g2', 'o_hi2', 'o_hi', 'o', 'o_md', 'o_dk', 'o_e1', 'o_e2', 'o_e3'),
    'open-h':   ('wh', 'g5', 'g3', 'wh', 'o_hi2', 'o_hi', 'o', 'o_md', 'o_e1', 'o_e2', 'o_e3'),
    'closed':   ('n_rim', 'n_rim2', 'n_e1', 'n_hi2', 'n_hi', 'n', 'n_md', 'n_dk', 'n_e1', 'n_e2', 'n_e3'),
    'closed-h': ('n_rim_h', 'n_rim', 'n_e1', 'n_hi3', 'n_hi2', 'n_hi', 'n', 'n_md', 'n_e1', 'n_e2', 'n_e3'),
    'set':      ('g4', 'g3', 'g1', 'c8', 'c7', 'c6', 'c5', 'c4', 'c3', 'c2', 'c1'),
    'set-h':    ('g5', 'g4', 'g2', 'c9', 'c8', 'c7', 'c6', 'c5', 'c3', 'c2', 'c1'),
    'off':      ('x_hi2', 'x_hi', 'x_e1', 'x_hi2', 'x_hi', 'x', 'x_md', 'x_dk', 'x_e1', 'x_e2', 'x_e3'),
}


def draw_tb_btn(kind, down=False):
    """
    工具列的立體小牌（30×36，slice 12/12/12/15）：外輪廓、兩圈邊（左上亮右下暗）、面板上淺下深
    （每一欄都一樣，橫向拉長不出條紋）、底下 3 px 厚邊；四個角裡各一顆 2×2 小釘。
    down：面板往下 3、厚邊收成 1 列（跟 btn-*-down 一樣，uss 那邊把圖示往下推 3）。
    """
    rim_hi, rim, rim_dk, fh2, fh, f, fm, fd, e1, e2, e3 = TB_BTN[kind]
    W, H = TB_BTN_W, TB_BTN_H
    px = _TbPx(W, H)
    top = 3 if down else 0
    body = _tb_rounded(W, H - top, 4, 0, top)
    face_bot = H - 1 - (1 if down else 4)
    for x, y in body:
        px.put(x, y, e1 if y == face_bot + 1 else (e2 if y < H - 2 else e3))
    face = {(x, y) for x, y in body if y <= face_bot}
    L, inner = _tb_layers(face, 3)
    n = face_bot - top
    for x, y in inner | L[2]:
        r = y - top
        px.put(x, y, fh2 if r <= 2 else (fh if r <= 6 else (f if r <= n - 8 else (fm if r <= n - 4 else fd))))
    for x, y in L[2]:
        if x <= 2:
            px.put(x, y, fh)
        elif x >= W - 3:
            px.put(x, y, fm if y < face_bot - 3 else fd)
    for x, y in L[0]:
        if (y >= face_bot - 1) or x >= W - 2:
            px.put(x, y, rim_dk)
        else:
            px.put(x, y, rim_hi if (y <= top + 1 or x <= 1) else rim)
    for x, y in L[1]:
        px.put(x, y, rim_hi if (y <= top + 2 and x < W - 3) else (rim if (x <= 2 and y < face_bot - 2) else rim_dk))
    for x, y in edge(body):
        px.put(x, y, 'ol')
    for cx, cy in ((4, top + 4), (W - 5, top + 4), (4, face_bot - 4), (W - 5, face_bot - 4)):
        px.put(cx, cy, rim_hi); px.put(cx + 1, cy, rim)
        px.put(cx, cy + 1, rim); px.put(cx + 1, cy + 1, rim_dk)
    return px


def draw_tb_tag(kind):
    """
    21×21 膠囊（slice 9）。'tag'：R 可按（亮紫浮起、亮金邊）；'tag-off'：上鎖（暗紫凹槽：上左暗下右亮、暗金邊）；
    'plate'：時鐘的時刻／日期牌（深紫面、金邊、下方 2 列落地陰影）。中間 3×3 是單色。
    """
    N = 21
    px = _TbPx(N, N)
    H = N - 2 if kind == 'plate' else N
    m = _tb_rounded(N, H, 5)
    rim_hi, rim, rim_dk, f_hi, f = {'tag': ('g5', 'g4', 'g2', 'c7', 'c6'),
                                     'tag-off': ('g2', 'g1', 'g0', 'c1', 'c2'),
                                     'plate': ('g4', 'g3', 'g1', 'c4', 'c3')}[kind]
    for x, y in m:
        px.put(x, y, f)
    L, _ = _tb_layers(m, 3)
    for x, y in L[0]:
        px.put(x, y, 'ol')
    for x, y in L[1]:
        lt = (y <= 2 and x < N - 3) or (x <= 2 and y < H - 3)
        px.put(x, y, rim_hi if (lt and y <= 2) else (rim if lt else rim_dk))
    for x, y in L[2]:
        if kind == 'tag-off':
            px.put(x, y, 'c1' if (y <= 3 or x <= 3) else 'c3')
        else:
            px.put(x, y, f_hi if ((y <= 3 and x < N - 4) or (x <= 3 and y < H - 4)) else f)
    if kind == 'plate':
        _tb_drop_shadow(px, m, (0.40, 0.16))
    return px


def draw_tb_gauge():
    """名聲量表的槽（18×12，slice 6）：外輪廓、金邊（上亮下暗）、內陰影一圈（上左暗）、深紫槽。"""
    W, H = 18, 12
    px = _TbPx(W, H)
    m = _tb_rounded(W, H, 3)
    for x, y in m:
        px.put(x, y, 'c2')
    L, _ = _tb_layers(m, 3)
    for x, y in L[0]:
        px.put(x, y, 'ol')
    for x, y in L[1]:
        px.put(x, y, 'g4' if y <= 1 else ('g1' if y >= H - 2 else ('g3' if x <= 1 else 'g2')))
    for x, y in L[2]:
        px.put(x, y, 'c1' if (y <= 2 or x <= 2) else 'c3')
    return px


# ── 共用小圖（工具列也在用）：細畫版，尺寸不變 ──

def draw_coin():
    """金幣（21×21）：外輪廓、幣緣五階（左上亮）、壓下去的內環（反光）、幣面浮雕小星、左上高光。"""
    N = 21
    px = _TbPx(N, N)
    for y in range(N):
        for x in range(N):
            dx, dy = x - 10.0, y - 10.0
            d = math.hypot(dx, dy)
            if d > 9.9:
                continue
            ang = (dx + dy) / max(d, 0.01)
            if d > 8.9:
                col = 'ol'
            elif d > 7.7:
                col = 'g5' if ang < -0.9 else ('g4' if ang < -0.2 else ('g3' if ang < 0.5 else ('g2' if ang < 1.1 else 'g1')))
            elif d > 6.6:
                col = 'g2' if ang < 0 else 'g4'
            else:
                col = 'g4' if ang < -0.5 else ('g3' if ang < 0.6 else 'g2')
            px.put(x, y, col)
    star = [(10, 5), (10, 6), (9, 7), (10, 7), (11, 7), (6, 9), (7, 9), (8, 8), (9, 8), (10, 8), (11, 8), (12, 8),
            (13, 9), (14, 9), (8, 9), (9, 9), (10, 9), (11, 9), (12, 9), (9, 10), (10, 10), (11, 10), (8, 11), (12, 11),
            (7, 12), (13, 12)]
    for x, y in star:
        if (x + 1, y + 1) not in star:
            px.put(x + 1, y + 1, 'g1')
    for x, y in star:
        px.put(x, y, 'g5' if x + y <= 19 else 'g4')
    for x, y, c in ((5, 4, 'wh'), (4, 5, 'wh'), (6, 4, 'g5'), (4, 6, 'g5'), (5, 5, 'g5')):
        px.put(x, y, c)
    return px


def draw_star():
    """名聲星（27×27）：五角星，每個尖角左右兩半各自朝一個方向受光（多面切光、四階金），1 px 外輪廓，中心兩點白。"""
    N = 27
    px = _TbPx(N, N)
    cx, cy, R, r = 13.5, 14.5, 12.4, 5.2
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = R if i % 2 == 0 else r
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))

    def inside(x, y):
        ins, j = False, len(pts) - 1
        for i in range(len(pts)):
            (xi, yi), (xj, yj) = pts[i], pts[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                ins = not ins
            j = i
        return ins

    m = {(x, y) for y in range(N) for x in range(N) if inside(x + 0.5, y + 0.5)}
    for x, y in m:
        dx, dy = x + 0.5 - cx, y + 0.5 - cy
        a = math.atan2(dy, dx)
        ta = -math.pi / 2 + round((a + math.pi / 2) / (2 * math.pi / 5)) * 2 * math.pi / 5   # 最近的尖角方向
        na = ta + (0.6 if math.sin(a - ta) > 0 else -0.6)                                   # 這半邊的「面」朝向
        lum = 0.6 * math.cos(na) + 0.8 * math.sin(na)
        lum = -lum + (0.3 if math.hypot(dx, dy) < 2.2 else 0.0)
        px.put(x, y, 'g5' if lum > 0.55 else ('g4' if lum > 0.05 else ('g3' if lum > -0.45 else 'g2')))
    for x, y in m:
        for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + ddx, y + ddy) not in m:
                px.put(x + ddx, y + ddy, 'ol')
    px.put(12, 12, 'wh'); px.put(13, 11, 'wh')
    return px


def draw_gear():
    """設定齒輪（33×33）：黃銅 8 齒（圓頭）、輪緣、一道溝、輪面四個小孔、正中一顆紫寶石；光從左上。"""
    N = 33
    px = _TbPx(N, N)
    m = {}
    for y in range(N):
        for x in range(N):
            dx, dy = x - 16.0, y - 16.0
            d = math.hypot(dx, dy)
            tooth = (math.cos(8 * math.atan2(dy, dx)) + 1) / 2
            if d <= 11.2 + 3.6 * min(1.0, tooth * 1.6):
                m[(x, y)] = (d, (dx + dy) / max(d, 0.01))
    for (x, y), (d, ang) in m.items():
        if d > 11.4:
            col = 'g4' if ang < -0.5 else ('g3' if ang < 0.5 else 'g2')
        elif d > 10.2:
            col = 'g5' if ang < -0.6 else ('g4' if ang < 0.2 else ('g3' if ang < 0.9 else 'g2'))
        elif d > 8.8:
            col = 'g1' if ang < 0 else 'g3'
        elif d > 5.6:
            col = 'g4' if ang < -0.4 else ('g3' if ang < 0.6 else 'g2')
        elif d > 4.5:
            col = 'g1'
        else:
            col = 'c8' if ang < -0.6 else ('c7' if ang < 0.2 else ('c5' if ang < 0.9 else 'c4'))
        px.put(x, y, col)
    for x, y in m:
        for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + ddx, y + ddy) not in m:
                px.put(x + ddx, y + ddy, 'ol')
    px.put(14, 14, 'wh'); px.put(15, 14, 'gem_hi')
    for ax, ay in ((16, 9), (23, 16), (16, 23), (9, 16)):
        px.put(ax, ay, 'g1'); px.put(ax + 1, ay, 'g2'); px.put(ax, ay + 1, 'g2'); px.put(ax + 1, ay + 1, 'g3')
    return px


def draw_keycap():
    """
    鍵帽（24×27，slice 9/9/9/12）：象牙白頂面（上左亮兩圈、右下暗一階、最下一列暗）、前緣厚邊 5 列三階、圓角外輪廓。
    中間 6 欄 × 6 列每欄／每列都一樣，橫向直向拉長都不出條紋。字由 uss（墨色 12）疊上去。
    """
    W, H = KEY_W * SCALE, KEY_H * SCALE
    px = _TbPx(W, H)
    body = _tb_rounded(W, H, 4)
    face_bot = H - 7
    for x, y in body:
        if y > face_bot:
            px.put(x, y, 'k_s1' if y == face_bot + 1 else ('k_s2' if y < H - 2 else 'k_s3'))
        else:
            px.put(x, y, 'k')
    face = {(x, y) for x, y in body if y <= face_bot}
    L, _ = _tb_layers(face, 2)
    for x, y in L[0]:
        px.put(x, y, 'k_hi' if ((y <= 1 or x <= 1) and x < W - 2) else ('k_dk' if y >= face_bot else 'k_md'))
    for x, y in L[1]:
        px.put(x, y, 'k_hi' if (y <= 2 and x < W - 3) else ('k' if x <= 2 else 'k_md'))
    for x in range(2, W - 2):
        px.put(x, face_bot, 'k_dk')
    for x, y in edge(body):
        px.put(x, y, 'ol')
    for y in range(face_bot + 1, H - 1):
        px.put(1, y, 'k_s1')
        px.put(W - 2, y, 'k_s3' if y > face_bot + 1 else 'k_s2')
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
    # ── 第四輪：上方工具列細畫版（只往尾巴加；上面的圖除了 coin／ico-star／ico-gear／keycap 重畫之外都不動）──
    out.append(('tb-bar', draw_tb_bar, (6,) * 4))
    out.append(('tb-sep', draw_tb_sep, None))
    for k in ('open', 'closed', 'set'):
        out.append((f'tb-{k}', lambda k=k: draw_tb_btn(k), BTN_SLICE))
        out.append((f'tb-{k}-hover', lambda k=k: draw_tb_btn(k + '-h'), BTN_SLICE))
        out.append((f'tb-{k}-down', lambda k=k: draw_tb_btn(k, down=True), BTN_SLICE))
    out.append(('tb-off', lambda: draw_tb_btn('off'), BTN_SLICE))
    for k in ('tag', 'tag-off', 'plate'):
        out.append((f'tb-{k}', lambda k=k: draw_tb_tag(k), (3,) * 4))
    out.append(('tb-gauge', draw_tb_gauge, (2,) * 4))
    # ── 第五輪：清單翻頁鈕（2026-11-27，UI/Pager.cs；只往尾巴加，上面的圖一張都不動）──
    for side in ('prev', 'next'):
        for st, suf in (('n', ''), ('h', '-hover'), ('d', '-down'), ('x', '-off')):
            out.append((f'page-{side}{suf}', lambda a=side, s=st: draw_page(a, s), None))
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
