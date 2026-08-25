# -*- coding: utf-8 -*-
"""
店內等距房間底圖 + 家具素材產生器（可重跑）。

    D:/python/python.exe tools/gen_shop_room.py

輸出：
    assets/resources/rooms/shop-room.png     房間底圖 960x640（14x10 等距長木板地板 + 兩面後牆）
    assets/resources/furniture/*.png         家具（程式生的 placeholder，之後可換手繪美術）

⚠️ 這裡的格子數學必須跟 assets/scripts/data/shopRoom.ts 一模一樣：
        tile(col,row) 中心 = (OX + (col-row)*TW/2 , OY - (col+row)*TH/2)
    家具圖的錨點約定：錨點 (0.5, 0)，且「佔地的前角」落在圖的正下方中央。

--------------------------------------------------------------------------
地板怎麼來的
--------------------------------------------------------------------------
**地板 ＝ 直接把 `tools/art-src/shop-room/floor-1.png` 平鋪上去，不做任何後製。**
使用者要的就是磚原本的樣子（2026-08-18 明確指示「用原本的地板就好，不要畫線」）。

⚠️ 磚要挑「板紋會跨格接起來」的那一格。同一張 sheet 的 16 格差很多：
   有些格子平鋪起來像編織紋，只有少數幾格的板紋會接成連續的斜向長條。
   現在用的是 `_pixellab-sheet-3-darkwood.png` 的來源格 **(0,0)**。
   換磚時先用 import_floor_tiles.py 切幾格出來平鋪比較過再定。

⚠️ 整間房間（含牆）都畫在 **半解析度 480x320** 再 x2 NEAREST 放大 ——
   480x320 才是這批美術真正的像素網格（磚原生 32x16、遊戲內 64x32）。
   直接在 960x640 畫會產生 1px 細節，跟角色的像素大小對不起來、看起來很糊。

（`DRAW_PLANKS = True` 是另一條路：磚只出顏色與木紋，長木板/接頭/板縫由程式在整片
  地板上畫，木板能跨好幾格延伸。做好了但**使用者選擇不用**，開關留著。）
"""
import os, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOMS = os.path.join(ROOT, 'assets', 'resources', 'rooms')
FURN = os.path.join(ROOT, 'assets', 'resources', 'furniture')
ARTSRC = os.path.join(ROOT, 'tools', 'art-src', 'shop-room')

W, H = 960, 640              # 最終輸出（＝data/shopRoom.ts 的 ROOM）
S = 2                        # 像素放大倍率
W2, H2 = W // S, H // S      # 半解析度畫布 480x320
GW, GH = 14, 10              # 格數：col 0..13, row 0..9
TW, TH = 64, 32              # 遊戲內一格（家具用）
TW2, TH2 = TW // S, TH // S  # 半解析度一格 32x16
OX, OY = -64, 108            # tile(0,0) 中心的世界座標
OX2, OY2 = OX // S, OY // S
WALL_H2, WAIN2 = 96, 32      # 牆高 / 護牆板高（半解析度）

# 地板：預設就是把磚原樣平鋪。
DRAW_PLANKS = False          # True ＝改走「程式畫長木板」那條路（見檔頭說明）
FLOOR_TINT = (1.0, 1.0, 1.0)  # 逐通道相乘微調磚的顏色；1.0 ＝原色不動
                              # ⚠️ 要調色用相乘，不要用亮度→色階，會把木紋暗點拉成黑點

# 以下只在 DRAW_PLANKS = True 時才用到
PLANKS_PER_TILE = 1.0        # 一格幾塊板（1.0 ＝ 遊戲內約 28px 寬的寬版木板）
PLANK_ALONG = 'gx'           # 木板沿哪條等距軸延伸（'gx' 往右下 / 'gy' 往左下）
JOINT_TILES = (3.5, 7.0)     # 每塊板每隔幾格一個接頭（隨機）

# 牆面。有 tools/art-src/shop-room/wall-panel.png 就用那張（正面平視、左右可無縫接），
# 由 paste_wall() 做 2:1 整數斜切貼上去；沒有就走下面這組程式畫的素面壁紙＋木裙板。
WALL_SHADE_L = 0.86          # 左牆壓暗（光源左上 → 右牆受光、左牆背光）
PLASTER_R, PLASTER_L = (214, 190, 162), (192, 168, 142)
WOOD_R, WOOD_L = (116, 74, 52), (98, 60, 42)

# 找不到手繪磚時的後路（不開天窗）
FALLBACK_RAMP = [(40, 21, 21), (53, 29, 30), (63, 35, 31), (74, 42, 36), (83, 46, 39),
                 (91, 52, 43), (99, 58, 47), (106, 65, 55), (115, 75, 64), (128, 84, 70)]


# ---------------------------------------------------------------- 等距格座標
# 每個半解析度像素落在哪一格（連續值）。tile 在 (gx,gy) 空間剛好是一個單位正方形，
# 所以整片地板 ＝ gx∈[-0.5, GW-0.5)、gy∈[-0.5, GH-0.5)。
_j, _i = np.mgrid[0:H2, 0:W2]
_x = _i - W2 / 2.0
_y = H2 / 2.0 - _j
_u = (_x - OX2) / (TW2 / 2.0)
_v = (OY2 - _y) / (TH2 / 2.0)
GX = (_u + _v) / 2.0
GY = (_v - _u) / 2.0
FLOOR = (GX >= -0.5) & (GX < GW - 0.5) & (GY >= -0.5) & (GY < GH - 0.5)

PX_PER_AXIS = float(np.hypot(TW2 / 2.0, TH2 / 2.0))   # 沿板走 1 格 ＝ 幾 px
PX_PER_WIDTH = 14.31                                   # 跨板 1 格 ＝ 幾 px（垂直板向）


def lerp(a, b, t):
    return tuple(int(round(a[k] + (b[k] - a[k]) * t)) for k in range(3))


# ---------------------------------------------------------------- 磚 → 色盤 / 木紋
def load_tile():
    p = os.path.join(ARTSRC, 'floor-1.png')
    return Image.open(p).convert('RGBA') if os.path.exists(p) else None


def load_wall_panel():
    """正面平視的牆面貼圖（高度必須 ＝ WALL_H2，左右可無縫接）。沒有就回 None。"""
    p = os.path.join(ARTSRC, 'wall-panel.png')
    if not os.path.exists(p):
        return None
    im = Image.open(p).convert('RGBA')
    if im.height != WALL_H2:
        raise SystemExit('wall-panel.png 高度是 %d，必須是 %d —— 用 tools/import_wall.py 匯入'
                         % (im.height, WALL_H2))
    return im


def paste_wall(base, a, b, panel, shade=1.0):
    """
    把「正面平視」的牆面貼圖斜切貼到 a→b 這面牆上。
    a、b 是牆腳（跟地板交界）那條線的兩端世界座標，牆往上長 WALL_H2。

    ⚠️ 作法是**逐欄整數位移**（每往牆的方向 1px，牆腳往下 0.5px）而不是用 affine 變形：
       等距斜率剛好 2:1，逐欄位移出來是乾淨的像素階梯；用 transform 會做插值，糊掉。
    貼圖的第 0 欄對齊 a 端 → 兩面牆都從轉角開始鋪，轉角處接得起來。
    """
    W_, H_ = base.size
    arr = np.array(base).astype(np.uint8)
    pan = np.array(panel).astype(float)
    if shade != 1.0:
        pan[:, :, :3] = np.clip(pan[:, :, :3] * shade, 0, 255)
    pan = pan.astype(np.uint8)
    ph, pw = pan.shape[0], pan.shape[1]

    ax, ay = W_ / 2 + a[0], H_ / 2 - a[1]
    bx = W_ / 2 + b[0]
    step = 1 if bx > ax else -1
    for i in range(int(round(abs(bx - ax)))):
        x = int(round(ax)) + step * i
        if x < 0 or x >= W_:
            continue
        y_bot = int(round(ay + i * 0.5))          # 2:1：每 2px 往下 1px
        y_top = y_bot - ph
        y0, y1 = max(0, y_top), min(H_, y_bot)
        if y1 <= y0:
            continue
        col = pan[y0 - y_top:y1 - y_top, i % pw]
        al = col[:, 3:4].astype(float) / 255.0
        arr[y0:y1, x, :3] = (col[:, :3] * al + arr[y0:y1, x, :3] * (1 - al)).astype(np.uint8)
        arr[y0:y1, x, 3] = 255
    return Image.fromarray(arr)


def wood_ramp(tile):
    """磚自己的色盤（由暗到亮）＝地板只會用到這幾個顏色，色感完全照美術。"""
    if tile is None:
        return FALLBACK_RAMP
    a = np.array(tile)
    rgb = a[:, :, :3][a[:, :, 3] > 0]
    cols, cnt = np.unique(rgb.reshape(-1, 3), axis=0, return_counts=True)
    keep = cols[cnt >= max(3, int(cnt.sum() * 0.01))]      # 濾掉抗鋸齒的零星色
    if len(keep) < 4:
        keep = cols
    order = np.argsort(keep[:, 0] * .3 + keep[:, 1] * .59 + keep[:, 2] * .11)
    return [tuple(int(v) for v in c) for c in keep[order]]


def tile_grain(tile):
    """
    磚的高頻木紋，鋪在等距格上。
    ⚠️ 先用高斯模糊取低頻再相減 —— 只留雜訊、丟掉「這塊磚中間亮邊緣暗」的形狀，
       不然棉被格會原封不動跟著回來。
    """
    n = np.zeros((H2, W2))
    if tile is None:
        return n
    a = np.array(tile).astype(float)
    al = a[:, :, 3] > 0
    if not al.any():
        return n
    lum = a[:, :, 0] * .3 + a[:, :, 1] * .59 + a[:, :, 2] * .11
    lum[~al] = lum[al].mean()
    low = np.array(Image.fromarray(lum.astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))).astype(float)
    hi = (lum - low) / 255.0
    th, tw = hi.shape
    for c in range(GW):
        for r in range(GH):
            cx = OX2 + (c - r) * TW2 / 2.0
            cy = OY2 - (c + r) * TH2 / 2.0
            L = int(W2 / 2 + cx - TW2 / 2)
            T = int(H2 / 2 - cy - TH2 / 2)
            if T < 0 or T + th > H2 or L < 0 or L + tw > W2:
                continue
            sub = n[T:T + th, L:L + tw]
            sub[al] = hi[al]
    return n


# ---------------------------------------------------------------- 木板
def wood_value(grain_tile, ppt=PLANKS_PER_TILE, along=PLANK_ALONG, seed=5):
    """每個地板像素「有多亮」。木板沿 run 軸延伸、沿 cross 軸一塊一塊排。"""
    run, cross = (GX, GY) if along == 'gx' else (GY, GX)
    rs = np.random.RandomState(seed)

    def field(su, sv, off=0):
        """沿板方向取樣稀疏、跨板方向取樣密集 → 拉長成木紋條紋。"""
        F = rs.uniform(-1, 1, (512, 512))
        return F[(np.floor((cross + .5) * sv).astype(int)) % 512,
                 (np.floor((run + .5) * su + off).astype(int)) % 512]

    grain = .050 * field(1.6, 9.0) + .030 * field(.55, 24.0, 7) + .55 * grain_tile

    bb = np.floor((cross + .5) * ppt)                  # 板號
    f = (cross + .5) * ppt - bb                        # 板內位置 0..1
    bi = bb.astype(int) % 4096
    board = rs.uniform(.92, 1.08, 4096)[bi]            # 每塊板的深淺
    jlen = rs.uniform(JOINT_TILES[0], JOINT_TILES[1], 4096)[bi]
    joff = rs.uniform(0, 5, 4096)[bi]                  # 接頭錯開

    jj = (run + .5 - joff) / jlen
    seg = np.floor(jj).astype(int)
    key = (bi * 7919 + (seg % 4096) * 104729) % 8192
    val = board * rs.uniform(.965, 1.035, 8192)[key] * (1.0 + grain)

    bw = PX_PER_WIDTH / ppt                            # 一塊板幾 px 寬
    seam = (f * bw < 1.0) | ((1 - f) * bw < 1.0)       # 板縫
    hilite = (f * bw >= 1.0) & (f * bw < 2.0)          # 板縫旁的受光邊
    joint = np.abs(jj - np.round(jj)) * jlen * PX_PER_AXIS < 1.0   # 接頭

    val = np.where(seam, val * .60, val)
    val = np.where(hilite, val * 1.10, val)
    val = np.where(joint, val * .64, val)

    # 靠兩面後牆的環境遮蔽
    return val * (.80 + .20 * np.clip(np.minimum(GX + .5, GY + .5) / 2.4, 0, 1))


def tint(im, mul):
    """逐通道相乘（壓深／偏暖）。不動對比，所以木紋不會被拉成黑點。"""
    if mul == (1.0, 1.0, 1.0):
        return im
    a = np.array(im).astype(float)
    for i in range(3):
        a[:, :, i] *= mul[i]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def to_palette(val, ramp):
    """亮度 → 磚的色盤。量化成有限階＝像素畫該有的樣子（不要平滑漸層）。"""
    inside = val[FLOOR]
    lo, hi = np.percentile(inside, 1.5), np.percentile(inside, 99)
    t = np.clip((val - lo) / max(hi - lo, 1e-6), 0, 1)
    idx = np.clip(np.round(t * (len(ramp) - 1)).astype(int), 0, len(ramp) - 1)
    return np.array(ramp, np.uint8)[idx]


# ---------------------------------------------------------------- 房間底圖
def build_room():
    def px(x, y):
        return (W2 / 2 + x, H2 / 2 - y)

    def center(c, r):
        return (OX2 + (c - r) * TW2 / 2.0, OY2 - (c + r) * TH2 / 2.0)

    # ⚠️ 底色要填滿：房間是菱形，四個角若留透明，遊戲裡會露出相機底色。
    #    （DecorRoom.applyRoomArt 也會把相機 clearColor 設成同一個深褐。）
    img = Image.new('RGBA', (W2, H2), (26, 21, 19, 255))
    d = ImageDraw.Draw(img)

    top_v = (OX2, OY2 + TH2 / 2)
    left_v = (center(0, GH - 1)[0] - TW2 / 2, center(0, GH - 1)[1])
    right_v = (center(GW - 1, 0)[0] + TW2 / 2, center(GW - 1, 0)[1])

    def wall(a, b, base, wd):
        d.polygon([px(*a), px(*b), px(b[0], b[1] + WALL_H2), px(a[0], a[1] + WALL_H2)], fill=base)
        d.polygon([px(*a), px(*b), px(b[0], b[1] + WAIN2), px(a[0], a[1] + WAIN2)], fill=wd)
        d.line([px(a[0], a[1] + WAIN2), px(b[0], b[1] + WAIN2)],
               fill=lerp(wd, (255, 255, 255), .35), width=2)
        for k in range(1, 18):
            t = k / 18.0
            sx = a[0] + (b[0] - a[0]) * t
            sy = a[1] + (b[1] - a[1]) * t
            d.line([px(sx, sy + WAIN2), px(sx, sy + WALL_H2)],
                   fill=lerp(base, (255, 255, 255), .26), width=1)
        d.line([px(a[0], a[1] + WALL_H2), px(b[0], b[1] + WALL_H2)],
               fill=lerp(base, (60, 46, 36), .45), width=2)
        d.line([px(*a), px(*b)], fill=lerp(wd, (30, 20, 14), .5), width=2)

    panel = load_wall_panel()
    if panel is not None:
        img = paste_wall(img, top_v, right_v, panel)
        img = paste_wall(img, top_v, left_v, panel, WALL_SHADE_L)
        d = ImageDraw.Draw(img)
    else:
        wall(top_v, right_v, PLASTER_R, WOOD_R)
        wall(top_v, left_v, PLASTER_L, WOOD_L)

    tile = load_tile()
    ramp = wood_ramp(tile)
    if DRAW_PLANKS or tile is None:
        rgb = to_palette(wood_value(tile_grain(tile)), ramp)
        floor = np.zeros((H2, W2, 4), np.uint8)
        floor[:, :, :3] = rgb
        floor[:, :, 3] = np.where(FLOOR, 255, 0)
        floor = Image.fromarray(floor)
    else:
        # 磚原樣平鋪（不隨機、不鏡射 —— 這批磚的板紋是跨格接起來的，一亂鋪就斷掉）
        floor = Image.new('RGBA', (W2, H2), (0, 0, 0, 0))
        for c in range(GW):
            for r in range(GH):
                cx, cy = center(c, r)
                floor.alpha_composite(tile, (int(W2 / 2 + cx - TW2 / 2), int(H2 / 2 - cy - TH2 / 2)))
        floor = tint(floor, FLOOR_TINT)
    img.alpha_composite(floor)

    # 牆腳投影
    sh = Image.new('RGBA', (W2, H2), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    for a, b in ((top_v, right_v), (top_v, left_v)):
        sd.polygon([px(*a), px(*b), px(b[0], b[1] - 14), px(a[0], a[1] - 14)], fill=(30, 18, 14, 105))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(4)))

    bottom_v = (center(GW - 1, GH - 1)[0], center(GW - 1, GH - 1)[1] - TH2 / 2)
    ol = [px(*top_v), px(*right_v), px(*bottom_v), px(*left_v)]
    ImageDraw.Draw(img).line(ol + [ol[0]], fill=lerp(ramp[0], (0, 0, 0), .25), width=1)

    img = img.resize((W, H), Image.NEAREST)            # 半解析度 → 遊戲尺寸
    os.makedirs(ROOMS, exist_ok=True)
    out = os.path.join(ROOMS, 'shop-room.png')
    img.convert('RGB').save(out)
    print('room ->', out, img.size, '（木板色盤 %d 階，來源磚：%s）'
          % (len(ramp), '有' if tile else '無，走後路'))


# ---------------------------------------------------------------- 家具
# 錨點約定：圖的「正下方中央」＝佔地的前角（tile(fw-1,fh-1) 的下角）。
# 節點用錨點 (0.5, 0) 擺在該格前角的世界座標上，YSort 就會正確遮擋。

def furniture(fw, fh, height, top_col, side_col, leg_col, legs=True, back=0):
    pad = 6                                  # 只留在上方與左右，底部不留（底＝前角）
    sprite_w = int(max(fw, fh) * TW) + pad * 2
    sprite_h = int((fw + fh) * TH / 2 + height + back + pad) + 1
    im = Image.new('RGBA', (sprite_w, sprite_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fx, fy = sprite_w / 2, sprite_h - 1

    def p(wx, wy):
        return (fx + wx, fy - wy)

    front = (0, 0)
    right = (fh * TW / 2, fh * TH / 2)
    left = (-fw * TW / 2, fw * TH / 2)
    back_c = (right[0] + left[0], right[1] + left[1])
    base = [front, right, back_c, left]
    top = [(x, y + height) for x, y in base]

    d.polygon([p(*base[0]), p(*base[1]), p(*top[1]), p(*top[0])], fill=side_col)
    d.polygon([p(*base[3]), p(*base[0]), p(*top[0]), p(*top[3])],
              fill=tuple(int(v * .84) for v in side_col))
    d.polygon([p(*q) for q in top], fill=top_col)
    d.line([p(*q) for q in top] + [p(*top[0])], fill=lerp(top_col, (60, 40, 26), .35), width=2)
    for i in range(1, 6):
        t = i / 6
        a = (top[0][0] + (top[1][0] - top[0][0]) * t, top[0][1] + (top[1][1] - top[0][1]) * t)
        b = (top[3][0] + (top[2][0] - top[3][0]) * t, top[3][1] + (top[2][1] - top[3][1]) * t)
        d.line([p(*a), p(*b)], fill=lerp(top_col, (120, 82, 50), .22), width=1)
    if back:
        bl, br = top[3], top[2]
        d.polygon([p(*bl), p(*br), p(br[0], br[1] + back), p(bl[0], bl[1] + back)],
                  fill=lerp(top_col, (90, 62, 40), .30))
        for i in range(1, 3):
            y = back * i / 3
            d.line([p(bl[0], bl[1] + y), p(br[0], br[1] + y)], fill=lerp(top_col, (60, 40, 26), .45), width=3)
    if legs:
        for a, b in ((base[3], base[0]), (base[0], base[1])):
            d.line([p(*a), p(*b)], fill=leg_col, width=4)
    return im


# ⚠️ sale_table 的「高」要跟 RoomLayout.ts 的 SALE_TOP_H 一致（商品陳列在檯面上）。
# ⚠️ **貨架不在這裡** —— 十六款貨架是手繪的，由 tools/import_furniture.py 匯入。
#    誰的圖已經換成手繪，就要從這張表拿掉，否則重跑這支會把美術蓋回木頭方塊。
# 色調配深紅棕地板：比地板亮一階（家具才浮得出來），但別用原本那種亮黃橡木。
PIECES = {
    # id            fw fh  高  檯面色          側面色         腳色        背板
    'sale_table':   (2, 1, 20, (162, 118, 84), (120, 84, 58), (86, 56, 38), 0),
    'long_table':   (3, 1, 20, (154, 112, 80), (114, 80, 55), (82, 54, 36), 0),
    'round_stand':  (1, 1, 25, (172, 128, 92), (128, 90, 62), (92, 60, 40), 0),
    'flower_bench': (2, 1, 15, (140, 154, 118), (100, 114, 84), (72, 84, 60), 0),
}


def build_furniture():
    os.makedirs(FURN, exist_ok=True)
    for pid, (fw, fh, hgt, top, side, leg, back) in PIECES.items():
        im = furniture(fw, fh, hgt, top, side, leg, back=back)
        out = os.path.join(FURN, pid + '.png')
        im.save(out)
        print('furniture ->', pid, im.size)


if __name__ == '__main__':
    build_room()
    build_furniture()
