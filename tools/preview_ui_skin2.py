#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UI 外觀（skin8）第二輪的離線預覽：任務簿、每日結算、對話框、公告板、Toast、佈置托盤、上方工具列、時鐘周圍。

    python tools/preview_ui_skin2.py OUTDIR

共用 tools/preview_ui_skin.py 的零件（九宮格、字、按鈕、鍵帽…）。⚠️ 這裡的版面數字**必須跟
Assets/Resources/ui/Skin8.uss 第二輪那幾段一致**（每個常數旁邊註明對應哪一條）；改 uss 就要改這裡。
不是排版引擎：只照 flex 橫排／直排手算座標，夠用來看比例、配色與節奏。

輸出（參考解析度 1:1，高 640、16:9 時寬 1138）：
  mock2_quest.png     任務簿（靠右的卷軸）
  mock2_day.png       每日結算
  mock2_dialogue.png  對話框（名字牌＋一句話＋選項）
  mock2_update.png    開場公告板
  mock2_hud.png       上方工具列（開店／關店／店裡上鎖／佈置中）＋時鐘周圍＋Toast（文字版、圖示版）
  mock2_tray.png      佈置托盤
  mock2_compare.png   跟第一輪的製作清單擺在一起（看是不是同一個人做的）
"""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import preview_ui_skin as P      # noqa: E402
from preview_ui_skin import (Canvas, SKIN, INK, INK_SOFT, INK_DIM, GOLD_INK, GREEN_INK, RED_INK,  # noqa: E402
                             CREAM, GOLD_CREAM, OUTLINE, SCREEN_W, SCREEN_H, RES)

ICONS8 = os.path.join(RES, 'ui', 'icons8')
CREAM_SOFT = (236, 224, 200)      # 深木底上的次要字（.sk .hud-rep、時鐘日期）


def i8(name, h):
    """icons8 的圖（24 邏輯格高），照 UiIcons.Element：高 h、寬照比例。"""
    im = Image.open(os.path.join(ICONS8, name + '.png')).convert('RGBA')
    w = round(h * im.width / im.height)
    return im.resize((w, h), Image.NEAREST)


def art(path, w, h):
    im = Image.open(os.path.join(RES, path)).convert('RGBA')
    return im.resize((int(w), int(h)), Image.NEAREST)


def fit_art(path, box):
    """等比塞進 box×box（UI Toolkit 的 background 預設 scale-to-fit）。"""
    im = Image.open(os.path.join(RES, path)).convert('RGBA')
    k = min(box / im.width, box / im.height)
    return im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.NEAREST)


def room_bg(name='shop-room.png'):
    bg = Image.new('RGBA', (SCREEN_W, SCREEN_H), (60, 50, 44, 255))
    p = os.path.join(RES, 'rooms', name)
    if os.path.exists(p):
        room = Image.open(p).convert('RGBA')
        k = SCREEN_H / room.height
        room = room.resize((int(room.width * k), SCREEN_H), Image.NEAREST)
        bg.alpha_composite(room, ((SCREEN_W - room.width) // 2, 0))
    return bg


def wrap(c, s, size, w, bold=False):
    lines, cur = [], ''
    for ch in s:
        if ch == '\n':
            lines.append(cur)
            cur = ''
            continue
        if c.tw(cur + ch, size, bold) > w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    lines.append(cur)
    return lines


def keycap(c, x, y, k, minw=36, h=27):
    """.sk .sk-key：min-width 36、高 27、padding 0 6 3 6、字 12 粗。回傳寬。"""
    kw = max(minw, 6 + c.tw(k, 12, True) + 6)
    c.nine('keycap', x, y, kw, h)
    c.text(x, y, k, 12, INK, bold=True, w=kw, h=h - 3, align='c')
    return kw


def ribbon(c, cx, top, title):
    """.sk .title：高 51、padding 0 36 6 36、字 21 粗、min-width 150，水平置中於 cx。"""
    rw = max(150, 36 + c.tw(title, 21, True) + 36)
    c.nine('ribbon', cx - rw / 2, top, rw, 51)
    c.text(cx - rw / 2, top, title, 21, CREAM, bold=True, shadow=(2, OUTLINE), w=rw, h=45, align='c')


def coin_num(c, x, y, h, s, size, color):
    c.img('coin', x, y + (h - 21) / 2)
    return 24 + c.text(x + 24, y, s, size, color, bold=True, h=h)


# ═══════════════════════════════ 任務簿 ═══════════════════════════════
# .sk .quest-scroll：寬 312、高 576、max-height 96%、margin-right 15；scroll-paper 九宮格（slice 12/21/12/21）；
#   padding 51 21 27 21。標題緞帶（.sk .quest-title）絕對定位 top -6、置中；關閉鈕 .sk .quest-close 36×36 top 3 right 0。
# 一條任務 .sk .quest-entry：row 卡片（可回報＝row-sel），padding 6 9 9 9、margin-bottom 6。
#   第 1 行 [qbox 24][標題 16 粗]；第 2 行（margin-top 3）[動詞 13][道具 24][進度條 flex 高 12][2/5 14 粗]；
#   第 3 行（margin-top 3）[發任務的人 13][…][金幣＋獎勵]

QUESTS = [  # (標題, 動詞, 道具或 None(=金幣), 進度, 目標, 找誰, 金, 道具獎勵)
    ('收集木材', '採集', '木材', 5, 5, '地精老闆', 30, None),
    ('第一瓶藥水', '調配', '清涼藥水', 1, 3, '狐狸小姐', 50, ('金蘋果', 1)),
    ('小有名氣', '賣出', None, 4, 10, '熊大叔', 80, None),
    ('存點旅費', '存到', 'coin', 320, 500, '刺蝟奶奶', 0, ('薰衣草種子', 2)),
]


def quest_entry(c, x, y, w, q):
    title, verb, itm, prog, goal, giver, gold, ritem = q
    ready = prog >= goal
    h = 6 + 24 + 3 + 24 + 3 + 21 + 9
    c.nine('row-sel' if ready else 'row', x, y, w, h)
    ix, iw = x + 9, w - 18
    ly = y + 6
    c.img('qbox-on' if ready else 'qbox', ix, ly)
    c.text(ix + 30, ly, title, 16, INK, bold=True, h=24)
    ly += 27
    tw = c.text(ix, ly, verb, 13, INK_SOFT, h=24) + 3
    if itm == 'coin':
        c.img('coin', ix + tw, ly + 1.5)
        tw += 24
    elif itm:
        c.img(P.item(itm), ix + tw, ly, 24, 24)
        tw += 27
    else:
        c.img('ico-basket', ix + tw, ly - 1.5)
        tw += 30
    num = f'{prog}/{goal}'
    nw = c.tw(num, 14, True)
    bx, bw = ix + tw + 3, iw - tw - 3 - 6 - nw
    by = ly + 6
    # .sk .sk-q-bar：高 12、底 pp_dk、框 3 pp_ln；.sk .sk-q-fill：底 gr、上緣 3 gr_hi（可回報＝金）
    c.d.rectangle([bx, by, bx + bw - 1, by + 11], fill=(180, 140, 88))
    c.d.rectangle([bx + 3, by + 3, bx + bw - 4, by + 8], fill=(215, 187, 133))
    fw = int((bw - 6) * min(1, prog / goal))
    if fw > 0:
        fill, hi = ((220, 174, 76), (251, 224, 138)) if ready else ((111, 158, 75), (167, 204, 115))
        c.d.rectangle([bx + 3, by + 3, bx + 3 + fw - 1, by + 8], fill=fill)
        c.d.rectangle([bx + 3, by + 3, bx + 3 + fw - 1, by + 5], fill=hi)
    c.text(ix + iw - nw, ly, num, 14, GREEN_INK if ready else INK, bold=True, h=24)
    ly += 27
    # 第 3 行：[→ 發任務的人] …… [金幣 30][+ 道具 ×1]
    c.img('i8-arrow', ix, ly - 1.5)
    c.text(ix + 27, ly, giver, 13, GOLD_INK if ready else INK_SOFT, bold=ready, h=21)
    rx = ix + iw
    if ritem:
        s = f'×{ritem[1]}'
        rx -= c.tw(s, 14, True)
        c.text(rx, ly, s, 14, INK, bold=True, h=21)
        rx -= 24 + 2
        c.img(P.item(ritem[0]), rx, ly - 1.5, 24, 24)
        rx -= 9
    if gold:
        s = str(gold)
        rx -= c.tw(s, 14, True)
        c.text(rx, ly, s, 14, GOLD_INK, bold=True, h=21)
        rx -= 24
        c.img('coin', rx, ly)
    return h


def mock_quest(outdir):
    c = Canvas(bg=room_bg('brew-room-day.png'))
    W, H = 312, min(576, int(SCREEN_H * 0.96))
    x, y = SCREEN_W - 15 - W, (SCREEN_H - H) // 2
    c.nine('scroll-paper', x, y, W, H)
    ribbon(c, x + W / 2, y - 6, '任務簿')
    c.img('close', x + W - 36 - 0, y + 3)
    cx, cy, cw = x + 21, y + 51, W - 42
    for q in QUESTS:
        cy += quest_entry(c, cx, cy, cw, q) + 6
    # 底列：UiSkin.Footer → 分隔線＋[Q][Esc] 關閉 …… 1/2
    fy = y + H - 27 - 48
    P.footer(c, cx, fy, cw, ['Q', 'Esc'], '關閉', '‹ 1/2 ›')
    p = os.path.join(outdir, 'mock2_quest.png')
    c.im.save(p)
    return p


# ═══════════════════════════════ 每日結算 ═══════════════════════════════
# .sk .day-card：panel 九宮格、寬 480（max 90%）、padding 30 30 24 30；標題列＝.header＋.title（同其他面板）。
# .sk .day-date 14 次要墨、置中；.sk-day-stats：橫排換行，一格 .sk-day-tile 寬 136、高 57、margin 0 6 6 0（每列第 3 格 margin-right 0）。
#   格子：row 卡片、padding 0 9 3 9；[圖 27][6][數字 18 粗 / 小字 12]
# 明細 .sk .day-item：高 39、row／row-alt 卡片、padding 0 9 3 6、margin-bottom 3；[道具 24][名稱 14][×n 徽章][金幣 數字]
# 淨收入 .sk-day-net：row-sel 卡片、高 48、padding 0 12 3 12；[淨收入 15 粗][…][金幣 數字 21 粗]
# 持有 .sk-day-wallet：靠右、14 次要墨。

DAY = dict(day=7, revenue=286, sales=9, trade=42, spent=80, gathered=14, brewed=5, rep=6,
           items=[('清涼藥水', 3, 105), ('戀愛藥水', 2, 80), ('薰衣草', 3, 66), ('金蘋果', 1, 35)])


def mock_day(outdir):
    c = Canvas(bg=Image.new('RGBA', (SCREEN_W, SCREEN_H), (10, 8, 16, 255)))
    W = 480
    d = DAY
    tiles = [('coin', f'+{d["revenue"]}', '營收', GREEN_INK), ('ico-basket', str(d['sales']), '賣出', INK),
             ('ico-sack', f'+{d["trade"]}', '收購', GREEN_INK), ('coin', f'-{d["spent"]}', '支出', RED_INK),
             ('ico-leaf', str(d['gathered']), '採集', INK), ('ico-flask', str(d['brewed']), '煉製', INK),
             ('ico-star', f'+{d["rep"]}', '名聲', GREEN_INK)]
    rows_t = (len(tiles) + 2) // 3
    list_h = len(d['items']) * 42
    H = 30 - 40 + 36 + 9 + 21 + 9 + rows_t * 63 + 18 + list_h + 3 + 48 + 6 + 21 + 48 + 24
    x, y = (SCREEN_W - W) // 2, (SCREEN_H - H) // 2
    c.nine('panel', x, y, W, H)
    cx, cw = x + 30, W - 60
    ribbon(c, x + W / 2, y + 30 - 40 - 9, '今日結算')
    cy = y + 30 - 40 + 36 + 9
    c.text(cx, cy, '第 7 天　3 月 7 日', 14, INK_SOFT, w=cw, h=21, align='c')
    cy += 21 + 9
    for i, (ico, num, cap, col) in enumerate(tiles):
        tx = cx + (i % 3) * (136 + 6)
        ty = cy + (i // 3) * 63
        c.nine('row', tx, ty, 136, 57)
        if ico == 'coin':
            c.img('coin', tx + 9 + 3, ty + (54 - 21) / 2)
        else:
            c.img(ico, tx + 9, ty + (54 - 27) / 2)
        c.text(tx + 9 + 33, ty + 6, num, 18, col, bold=True, h=27)
        c.text(tx + 9 + 33, ty + 30, cap, 12, INK_SOFT, h=18)
    cy += rows_t * 63
    c.nine('divider', cx, cy, cw, 15)
    cy += 18
    for i, (name, q, g) in enumerate(d['items']):
        c.nine('row-alt' if i % 2 else 'row', cx, cy, cw, 39)
        mid = cy + 18
        c.img(P.item(name), cx + 6, mid - 12, 24, 24)
        c.text(cx + 36, mid - 12, name, 14, INK, bold=True, h=24)
        s = str(g)
        gx = cx + cw - 9 - c.tw(s, 15, True) - 24          # .sk-day-gold：寬 72、靠右
        coin_num(c, gx, mid - 12, 24, s, 15, GOLD_INK)
        bx = cx + cw - 9 - 72 - 45                           # .sk-day-qty：寬 45、徽章置中
        bw = max(27, 14 + c.tw(f'×{q}', 14, True))
        P.badge(c, bx + (45 - bw) / 2, mid, f'×{q}')
        cy += 42
    cy += 3
    c.nine('row-sel', cx, cy, cw, 48)
    c.text(cx + 12, cy, '淨收入', 15, INK, bold=True, h=45)
    net = d['revenue'] + d['trade'] - d['spent']
    s = f'+{net}'
    coin_num(c, cx + cw - 12 - 24 - c.tw(s, 21, True), cy, 45, s, 21, GREEN_INK)
    cy += 48 + 6
    s = '1280'
    wx = cx + cw - c.tw(s, 14, True) - 24
    coin_num(c, wx, cy, 21, s, 14, GOLD_INK)
    c.text(wx - 6 - c.tw('持有', 13), cy, '持有', 13, INK_SOFT, h=21)
    cy += 21
    P.footer(c, cx, cy, cw, ['Enter', 'Space'], '繼續')
    p = os.path.join(outdir, 'mock2_day.png')
    c.im.save(p)
    return p


# ═══════════════════════════════ 對話框 ═══════════════════════════════
# .sk .dlg-box：panel 九宮格、寬 84%（max 760）、margin-bottom 33、padding 33 30 24 30。
# 頭像框 .sk-dlg-frame：slot 九宮格 102×102、padding 9、margin-right 15；頭像 84×84。
# 名字牌 .sk .dlg-name：絕對定位 top -48、left 0（相對 .dlg-body）、高 33、padding 0 15 3 15、plate 九宮格、字 17 粗米白＋落影。
# 台詞 .sk .dlg-text：19、墨色、min-height 57。選項：.btn（第一個 .btn-list 綠、其他木）高 36、padding 0 18 3 18、字 16、margin-right 9。
# 繼續 .sk-dlg-next-row：靠右 [E][Space] 繼續（14 次要墨）。

def mock_dialogue(outdir):
    c = Canvas(bg=room_bg('shop-room.png'))
    for variant, oy in (('next', 0), ('choice', 1)):
        pass
    W = min(760, int(SCREEN_W * 0.84))
    H = 33 + 102 + 24 + 6
    x, y = (SCREEN_W - W) // 2, SCREEN_H - 33 - H
    # 上面再放一個「有選項」的版本（同尺寸，示意用）
    for k, (yy, choice) in enumerate(((y - H - 54, True), (y, False))):
        c.nine('panel', x, yy, W, H)
        fx, fy = x + 30, yy + 33
        c.nine('slot', fx, fy, 102, 102)
        c.img(fit_art('portraits/fox.png', 84), fx + 9, fy + 9)
        bx = fx + 102 + 15
        bw = x + W - 30 - bx
        name = '狐狸小姐'
        nw = 15 + c.tw(name, 17, True) + 15
        c.nine('plate', bx, fy - 48 + 0, nw, 33)
        c.text(bx, fy - 48, name, 17, CREAM, bold=True, shadow=(2, OUTLINE), w=nw, h=30, align='c')
        txt = '你就是新來的魔女嗎？聽說你的藥水很有效，可以幫我調一瓶清涼藥水嗎？' if choice else \
              '這座城鎮的河不能直接踩過去喔，記得走橋。'
        for i, ln in enumerate(wrap(c, txt, 19, bw)):
            c.text(bx, fy + i * 28, ln, 19, INK, h=28)
        if choice:
            cy = fy + 57 + 9
            cx2 = bx
            for j, lab in enumerate(('接受', '再想想')):
                w = 18 + c.tw(lab, 16, True) + 18
                P.button(c, cx2, cy, w, '', 'green' if j == 0 else 'wood')
                c.text(cx2, cy, lab, 16, CREAM, bold=True, shadow=(1, OUTLINE), w=w, h=33, align='c')
                cx2 += w + 9
        else:
            ry = fy + 57 + 9 + 6
            lab = '繼續'
            rx = bx + bw - c.tw(lab, 14)
            c.text(rx, ry, lab, 14, INK_SOFT, h=27)
            rx -= 3
            for kk in ('Space', 'E'):
                kw = max(36, 12 + c.tw(kk, 12, True))
                rx -= kw + 3
                keycap(c, rx, ry, kk)
    p = os.path.join(outdir, 'mock2_dialogue.png')
    c.im.save(p)
    return p


# ═══════════════════════════════ 公告板 ═══════════════════════════════
# .sk .update-panel：panel 九宮格、寬 600（max 88%）、padding 30 30 24 30；標題列＝.header＋.title「更新」。
# 日期 .sk-upd-date：14 次要墨、置中、margin-bottom 9。條目 .sk-upd-line：橫排、margin-bottom 6；
#   [ico-bullet 15，margin 3 9 0 0][字 15 墨色、可換行]。
# 底：分隔線＋置中的 OK 鈕（.btn.btn-list，寬 120）。

NOTES = [
    '上方工具列可以開店、關店，關店才能佈置',
    '道具圖示全部重畫成像素風',
    '店裡的貨架與販售桌重新畫過',
    '上架的商品會擺在架上，佈置模式可以拖去別的位子',
    '客人會三三兩兩上門，進門打招呼、邊逛邊聊天',
    '店裡的家具會擋路，客人也會繞著貨架走',
    '城鎮的河不能直接踩過去，要走橋',
    '魔女的房間重新畫過，家具會擋路、也能繞到後面',
]


def mock_update(outdir):
    c = Canvas(bg=room_bg('brew-room-day.png'))
    c.im.alpha_composite(Image.new('RGBA', c.im.size, (20, 14, 26, 171)))     # .update-layer 背板
    W = 600
    cw = W - 60
    lines = [wrap(c, s, 15, cw - 24) for s in NOTES]
    body_h = sum(len(l) * 22 + 6 for l in lines)
    H = 30 - 40 + 36 + 9 + 21 + 9 + body_h + 18 + 6 + 36 + 24
    x, y = (SCREEN_W - W) // 2, (SCREEN_H - H) // 2
    c.nine('panel', x, y, W, H)
    ribbon(c, x + W / 2, y + 30 - 40 - 9, '更新')
    cx = x + 30
    cy = y + 30 - 40 + 36 + 9
    c.text(cx, cy, '2026 / 11 / 26', 14, INK_SOFT, w=cw, h=21, align='c')
    cy += 21 + 9
    for ls in lines:
        c.img('ico-bullet', cx, cy + 3.5)
        for i, ln in enumerate(ls):
            c.text(cx + 24, cy + i * 22, ln, 15, INK, h=22)
        cy += len(ls) * 22 + 6
    c.nine('divider', cx, cy + 3, cw, 15)
    cy += 18 + 6
    P.button(c, x + (W - 120) / 2, cy, 120, 'OK', 'green')
    p = os.path.join(outdir, 'mock2_update.png')
    c.im.save(p)
    return p


# ═══════════════════════════════ 上方工具列＋時鐘＋Toast ═══════════════════════════════
# .sk .hud-corner：top 9、left 9、hud-bar 九宮格（slice 18）、padding 9 12；.sk .hud-tb 高 36。
# 一格 .sk .hud-seg padding 0 9。分隔 .sk .hud-sep 寬 6 高 30（暗 3 wd_dk2＋亮 3 wd）。
# 金幣：[coin 21][3][數字 20 粗 金米色]，min-width 84。
# 名聲：[ico-star 27][6][直排：上（Lv＋稱號 13 米白｜點數 12 淡）、下 進度條 高 12（框 3 outline、底 wd_dk2、填 go＋上緣 3 go_hi）]，min-width 186。
# 開關店：.btn 九宮格（開＝btn-gold、關＝btn-purple、停用＝btn-off）高 36、padding 0 9 3 9；[招牌 24][3][P 24]。
# R 提示：高 36、padding 0 6 3 6（tag-gold 可按／badge 上鎖）、margin-left 6；[R 24(+鎖 18)][3][木槌 24]。
# 設定：btn-wood 高 36、padding 0 9 3 3；[齒輪 33][O 鍵帽 24×24]。
# 時鐘：盤面 152×151（top 12 right 12）不動；下方 .sk-clock-info 靠右直排：時刻膠囊（badge、高 27、padding 0 9、字 16 粗米白）
#   ＋日期膠囊（高 24、padding 0 9、字 13 淡米白），間隔 3。
# Toast：.sk .toast hud-bar 九宮格、padding 9 21 12 21、字 18 米白＋落影；圖示版 padding 9 15 9 15。

def toolbar(c, x, y, state, in_shop, editing=False):
    """state：'open'／'closed'。回傳 (寬, 高)。"""
    segs = []
    gold = '1280'
    gw = max(84, 24 + c.tw(gold, 20, True))
    rep_w = 186
    sw = 9 + 24 + 3 + 24 + 9
    ew = 6 + 24 + 3 + 24 + 6 if in_shop else 0
    setw = 3 + 33 + 24 + 9                  # .sk .hud-btn.hud-settings padding 0 9 3 3；齒輪 33、O 鍵帽 24
    W = 12 + (9 + gw + 9) + 6 + (9 + rep_w + 9) + 6 + (9 + sw + (6 + ew if in_shop else 0) + 9) + 6 + (9 + setw + 9) + 12
    H = 9 + 36 + 9
    c.nine('hud-bar', x, y, W, H)
    cx, cy = x + 12, y + 9
    # 金幣
    sx = cx + 9
    coin_num(c, sx, cy, 36, gold, 20, GOLD_CREAM)
    cx += 9 + gw + 9

    def sep(px_):
        c.d.rectangle([px_, cy + 3, px_ + 2, cy + 32], fill=(75, 41, 28))
        c.d.rectangle([px_ + 3, cy + 3, px_ + 5, cy + 32], fill=(149, 90, 56))
    sep(cx)
    cx += 6
    # 名聲
    sx = cx + 9
    c.img('ico-star', sx, cy + 4.5)
    tx = sx + 33
    tw_ = rep_w - 33
    c.text(tx, cy, 'Lv.2 略有耳聞', 13, CREAM_SOFT, h=19)
    pts = '86/120'
    c.text(tx + tw_ - c.tw(pts, 12), cy, pts, 12, (214, 186, 140), h=19)
    by = cy + 21
    c.d.rectangle([tx, by, tx + tw_ - 1, by + 11], fill=OUTLINE)
    c.d.rectangle([tx + 3, by + 3, tx + tw_ - 4, by + 8], fill=(75, 41, 28))
    fw = int((tw_ - 6) * 86 / 120)
    c.d.rectangle([tx + 3, by + 3, tx + 3 + fw - 1, by + 8], fill=(220, 174, 76))
    c.d.rectangle([tx + 3, by + 3, tx + 3 + fw - 1, by + 5], fill=(251, 224, 138))
    cx += 9 + rep_w + 9
    sep(cx)
    cx += 6
    # 開關店鈕
    sx = cx + 9
    kind = 'x' if editing else 'n'
    name = {'open': 'btn-gold', 'closed': 'btn-purple'}[state] if not editing else 'btn-off'
    c.nine(name, sx, cy, sw, 36)
    al = 0.55 if editing else 1.0
    c.img(i8('shop_open' if state == 'open' else 'shop_closed', 24), sx + 9, cy + 4.5, alpha=al)
    c.img(i8('key_p', 24), sx + 9 + 27, cy + 4.5, alpha=al)
    ex = sx + sw + 6
    if in_shop and not editing:
        locked = state == 'open'
        c.nine('badge' if locked else 'tag-gold', ex, cy, ew, 36)
        dim_a = 0.45 if locked else 1.0
        c.img(i8('key_r', 24), ex + 6, cy + 4.5, alpha=dim_a)
        if locked:
            c.img(i8('lock', 18), ex + 6 + 24 - 13, cy + 4.5 + 24 - 14)
        c.img(i8('act_edit', 24), ex + 6 + 27, cy + 4.5, alpha=dim_a)
    cx += 9 + sw + (6 + ew if in_shop else 0) + 9
    sep(cx)
    cx += 6
    sx = cx + 9
    c.nine('btn-wood', sx, cy, setw, 36)
    c.img('ico-gear', sx + 3, cy)
    c.nine('keycap', sx + 3 + 33, cy + 4.5, 24, 24)
    c.text(sx + 3 + 33, cy + 4.5, 'O', 12, INK, bold=True, w=24, h=21, align='c')
    return W, H


def clock(c):
    face = art('ui/clock/face.png', 152, 151)
    X, Y = SCREEN_W - 12 - 152, 12
    c.img(face, X, Y)
    for nm, w, h, fy in (('sun', 22, 22, 0.39),):
        c.img(art('ui/clock/' + nm + '.png', w, h), X + 76 - w / 2, Y + 151 / 2 - fy * 151 - h / 2)
    c.img(art('ui/season/spring.png', 26, 26), X + 76 - 13, Y + 151 / 2 - 0.284 * 151 - 13)
    for fx, s in ((-0.135, '3'), (0.145, '7')):
        w, h = 0.2 * 152, 0.16 * 151
        c.text(X + 76 + fx * 152 - w / 2, Y + 151 / 2 + 0.05 * 151 - h / 2, s, 23, (244, 228, 176), bold=True, w=w, h=h, align='c')
    # .sk-clock-info：top 151+3、靠右
    ty = Y + 151 + 3
    s = '8:30'
    w = 9 + c.tw(s, 16, True) + 9
    c.nine('badge', X + 152 - w, ty, w, 27)
    c.text(X + 152 - w, ty, s, 16, CREAM, bold=True, w=w, h=27, align='c')
    ty += 27 + 3
    s = '第 1 年 3 月 7 日（春）'
    w = 9 + c.tw(s, 13) + 9
    c.nine('badge', X + 152 - w, ty, w, 24)
    c.text(X + 152 - w, ty, s, 13, CREAM_SOFT, w=w, h=24, align='c')


def toast_text(c, s, y):
    w = 21 + c.tw(s, 18) + 21
    h = 9 + 27 + 12
    x = (SCREEN_W - w) / 2
    c.nine('hud-bar', x, y, w, h)
    c.text(x, y + 9, s, 18, CREAM, shadow=(2, OUTLINE), w=w, h=27, align='c')


def toast_icons(c, icons, s, y):
    ims = [i8(n, 34) for n in icons]
    w = 15 + sum(im.width + 6 for im in ims) + (6 + c.tw(s, 18) if s else 0) + 15
    h = 9 + 34 + 9
    x = (SCREEN_W - w) / 2
    c.nine('hud-bar', x, y, w, h)
    ix = x + 15
    for im in ims:
        c.img(im, ix + 3, y + 9)
        ix += im.width + 6
    if s:
        c.text(ix + 6, y + 9, s, 18, CREAM, shadow=(2, OUTLINE), h=34)


def mock_hud(outdir):
    c = Canvas(bg=room_bg('shop-room.png'))
    toolbar(c, 9, 9, 'open', True)
    clock(c)
    toast_text(c, '材料已收進倉庫', 76)
    toast_icons(c, ['key_r', 'lock', 'shop_open'], '先關店', 140)
    # 其他狀態排在下面
    y = 220
    for st, ins, ed, lab in (('closed', True, False, '店內・關店（R 可按）'), ('open', False, False, '店外・開店'),
                             ('closed', False, False, '店外・關店'), ('closed', True, True, '佈置中（停用）')):
        c.d.rectangle([0, y - 4, 520, y + 66], fill=(30, 24, 30, 160))
        c.text(14, y - 2, lab, 12, (230, 220, 200), h=14)
        toolbar(c, 9, y + 12, st, ins, ed)
        y += 92
    p = os.path.join(outdir, 'mock2_hud.png')
    c.im.save(p)
    c.im.crop((0, 0, 620, 140)).resize((1240, 280), Image.NEAREST).save(os.path.join(outdir, 'mock2_hud_zoom.png'))
    c.im.crop((SCREEN_W - 260, 0, SCREEN_W, 230)).resize((520, 460), Image.NEAREST).save(
        os.path.join(outdir, 'mock2_clock_zoom.png'))
    return p


# ═══════════════════════════════ 佈置托盤 ═══════════════════════════════
# .sk .tray：hud-bar 九宮格、寬 92%（max 880）、margin-bottom 12、padding 12 15 12 15。
# 標題列 .tray-head：[木槌 34][提示列 flex]；.sk .tray-hints：badge 九宮格＋左邊 3 金條、padding 3 6 3 9。
# 托盤格 .sk .tray-item：slot 九宮格 66×66、margin 3、padding 9；圖 48；數量 .sk-badge 壓右下（right/bottom -6）；名稱改浮動說明。

TRAY = [('furniture/shelf_arch.png', 1), ('furniture/shelf_cabinet.png', 2), ('decor/bonsai.png', 1),
        ('decor/birdcage_small.png', 3), ('decor/blue_urn.png', 1), ('furniture/shelf_round.png', 1)]


def mock_tray(outdir):
    c = Canvas(bg=room_bg('shop-room.png'))
    W = min(880, int(SCREEN_W * 0.92))
    H = 12 + 40 + 9 + 72 + 12
    x, y = (SCREEN_W - W) // 2, SCREEN_H - 12 - H
    c.nine('hud-bar', x, y, W, H)
    cx, cy = x + 15, y + 12
    c.img(i8('act_edit', 34), cx, cy + 3)
    hx = cx + 34 + 9
    hw = x + W - 15 - hx
    c.nine('chip', hx, cy, hw, 40)
    c.d.rectangle([hx, cy, hx + 2, cy + 39], fill=(220, 174, 76))
    gx = hx + 9
    groups = [['mouse_drag', 'act_move'], ['key_f', 'act_rotate'], ['key_t', 'anchor_0'], ['mouse_right', 'act_stash'],
              '|', ['tile_green', 'st_ok'], ['tile_red', 'st_no'], ['tile_blue', 'act_walk'], '|',
              ['key_r', 'act_done'], ['key_esc', 'act_cancel']]
    for i, g in enumerate(groups):
        if g == '|':
            c.d.rectangle([gx + 2, cy + 7, gx + 4, cy + 32], fill=(180, 140, 88))
            gx += 13
            continue
        hot = i == 5
        ims = [i8(n, 30) for n in g]
        gw = sum(im.width + 2 for im in ims) + 6
        if hot:
            c.im.alpha_composite(Image.new('RGBA', (gw, 34), (233, 194, 92, 115)), (int(gx), int(cy + 3)))
        ix = gx + 3
        for im in ims:
            c.img(im, ix + 1, cy + 5)
            ix += im.width + 2
        gx += gw + 6
    iy = cy + 40 + 9
    ix = cx
    for i, (pth, n) in enumerate(TRAY):
        c.nine('slot-sel' if i == 1 else 'slot', ix + 3, iy + 3, 66, 66)
        im = fit_art(pth, 48)
        c.img(im, ix + 3 + 9 + (48 - im.width) / 2, iy + 3 + 9 + (48 - im.height) / 2)
        if n > 1:
            P.badge(c, ix + 3 + 66 + 6 - 27, iy + 3 + 66 + 6 - 12, f'×{n}', size=13, minw=27)
        ix += 72
    # 滑過第 2 格：浮動說明（在格子上方）
    s = '櫥櫃貨架'
    tw = 10 + c.tw(s, 14) + 10
    tx = cx + 72 + 3 + 33 - tw / 2
    c.nine('badge', tx, iy + 3 - 3 - 31, tw, 31)
    c.text(tx, iy + 3 - 3 - 31 + 4, s, 14, CREAM, w=tw, h=21, align='c')
    p = os.path.join(outdir, 'mock2_tray.png')
    c.im.save(p)
    return p


def compare(paths, outdir):
    ref = os.path.join(outdir, 'mock_brew.png')
    ims = [Image.open(p) for p in ([ref] if os.path.exists(ref) else []) + paths]
    tw, th = SCREEN_W // 2, SCREEN_H // 2
    rows = (len(ims) + 1) // 2
    sheet = Image.new('RGBA', (2 * tw, rows * th), (20, 16, 20, 255))
    for i, im in enumerate(ims):
        sheet.alpha_composite(im.convert('RGBA').resize((tw, th), Image.LANCZOS), ((i % 2) * tw, (i // 2) * th))
    p = os.path.join(outdir, 'mock2_compare.png')
    sheet.save(p)
    return p


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    P.mock_brew(outdir)
    paths = [mock_quest(outdir), mock_day(outdir), mock_dialogue(outdir), mock_update(outdir), mock_hud(outdir),
             mock_tray(outdir)]
    paths.append(compare(paths, outdir))
    for p in paths:
        print(p)


if __name__ == '__main__':
    main()
