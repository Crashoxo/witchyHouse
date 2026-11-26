# -*- coding: utf-8 -*-
"""
量戶外地圖上每張物件圖「貼地那一段」的範圍，依物件類別決定碰撞形狀，
產生 Assets/Scripts/Data/ArtFootprints.cs（玩家碰撞用的落地範圍表）。

    python tools/gen_footprints.py            # 量圖 → 寫 ArtFootprints.cs，並印出分類表
    python tools/check_walkable.py            # 用同一份規則離線做可達性檢查＋輸出俯視預覽圖

仿 tools/gen_furniture_bounds.py 的做法：離線量 PNG 的不透明範圍 → 產生 C# 資料表。
固定結果、可重跑（只讀圖，不用亂數）。

── 這支是「碰撞規則的唯一來源」──────────────────────────────
  - 每類物件的形狀係數（CATS）、art 路徑 → 類別的對照（RULES）、玩家腳底圓半徑、
    地圖邊緣內縮、門口挖開的寬度，全部寫在這裡；
  - C# 那邊（Core/Obstacles.cs）只讀產生出來的 ArtFootprints.cs，不自己寫常數；
  - 離線檢查 tools/check_walkable.py 直接 import 這支的函式，所以兩邊的數值不會漂移。
  調某一類的範圍：改 CATS 裡那一類的係數 → 重跑這支 → 重跑 check_walkable.py 看預覽。

── 量什麼 ───────────────────────────────────────────────────
  對每張圖（alpha >= 40 才算畫到東西）：
  - 整體不透明範圍；
  - **貼地那一段**：不透明範圍最底下 BAND_FRAC（15%）高度的列。左右範圍只算「這一段裡
    至少 35% 的列都有畫到」的欄 —— 圖上偶爾有一兩條細細的雜線（花店右邊那條），
    單純取聯集會把寬度灌大；
  - 樹另外量「樹幹寬」：貼地那一段裡每一列寬度的中位數（樹根會往外張、樹冠會垂下來，
    中位數剛好落在樹幹上）。
  座標一律換成「相對圖片中心、y 朝上、原圖像素」，使用時再乘物件的 scale。

── 形狀 ─────────────────────────────────────────────────────
  ellipse：軸對齊橢圓（樹幹、圓灌木、小擺設）。
  box    ：軸對齊矩形，碰撞時再往外長一個玩家半徑 ＝ 圓角矩形（扁的時候就是膠囊）。
           建築、樹籬、圍籬、花台用它。
  none   ：不擋（橋、拱門、平貼地面的東西、可以走上去採的小採集點、NPC）。
"""
import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, 'Assets', 'Resources')
DATA = os.path.join(ROOT, 'Assets', 'Scripts', 'Data')
OUT = os.path.join(DATA, 'ArtFootprints.cs')

ALPHA = 40          # 低於這個 alpha 當成沒畫到
BAND_FRAC = 0.15    # 「貼地那一段」＝不透明範圍最底下多少比例的高度
COL_FRAC = 0.35     # 那一段裡某一欄至少要有多少比例的列畫到，才算進寬度（濾掉細雜線）

# ──────────── 玩家與地圖（C# 與離線檢查共用）────────────

PLAYER_RADIUS = 11.0     # 玩家腳底的碰撞圓半徑（像素）。女巫圖寬約 49、腳約 20 寬
# 地圖邊緣往內縮多少（像素）。女巫的樞紐在腳底、圖高約 66：
#   上緣縮一個身高，頭才不會畫到地面外；左右各縮半個身寬；下緣只要讓腳不踩出去。
EDGE_TOP = 64.0
EDGE_SIDE = 22.0
EDGE_BOTTOM = 6.0
DOOR_GAP_HALF = 24.0     # 門（SceneDoor）前方在建築範圍上挖開的半寬：玩家半徑 11 ＋ 留 13 的餘裕
CELL_SIZE = 128.0        # 執行期空間切格的格子大小
FLAT_ORDER = -8600       # 平貼地面的東西（橋、地上的糖果盤）的排序：地上光圈 -9000 之上、腳下影子 -8500 之下

# ──────────── 類別 → 形狀 ────────────
#
# 所有長度都是「原圖像素」（使用時乘物件的 scale）。用到的量：
#   fw  ＝ 貼地那一段的寬（樹用樹幹寬）     h ＝ 不透明範圍的高
# 欄位：
#   shape   ellipse / box / none
#   wk      寬度係數：半寬 ＝ fw/2 × wk（iso 建築例外：半寬 ＝ 圖寬 × wk）
#   depth   深度：>=1 當作像素、<1 當作 h 的比例。橢圓＝y 半徑×2，box＝整個高度
#   lift    範圍底緣比圖的底緣高多少（同上：>=1 像素、<1 比例）。正值＝腳可以稍微踩進圖裡
#   width   寬度量哪裡：'foot'（預設）＝貼地那一段、'full' ＝整體不透明寬（底部很零碎的小擺設）
#   min_hx / min_hy   最小半寬／半高（原圖像素；太小的圖不要小到變成一個點）
#   flat    平貼地面：排序壓到 FLAT_ORDER（不參與 YSort，人走上去一律畫在上面）
#   keep_order  不改排序（其餘的物件在執行期改成照「腳底 y」排，女巫才繞得到樹後面）。
#           城鎮建築要留著原本「圖片中心」的排序：門口的花台、灌木、路燈是貼在房子正面擺的，
#           改成看腳底會整個被房子蓋掉；而建築的範圍深到圖高一半＝剛好到圖片中心，
#           女巫站得到的地方不是在中心以下（前面）就是以上（後面），照中心排一樣對。
#   note    回報用的中文說明
CATS = {
    'tree':         dict(shape='ellipse', wk=0.85, depth=0.0, lift=0.0, min_hx=6, min_hy=4,
                         note='樹：只擋樹幹（小橢圓），能繞到樹冠後面'),
    'bush':         dict(shape='ellipse', wk=0.80, depth=0.30, lift=0.04, min_hx=8, min_hy=5,
                         note='灌木：底部寬的小橢圓'),
    'hedge':        dict(shape='box', wk=0.90, depth=0.26, lift=0.04, min_hx=8, min_hy=5,
                         note='樹籬／一排灌木：底部整排的扁長條'),
    'grove':        dict(shape='box', wk=0.85, depth=0.30, lift=0.04, min_hx=8, min_hy=5,
                         note='一叢樹林：底部寬的長條'),
    'building':     dict(shape='box', wk=0.95, depth=0.50, lift=0.0, min_hx=8, min_hy=8, keep_order=True,
                         note='建築：底部整個寬度、深到圖高一半（牆面走不進去），門口另外挖開'),
    'building_iso': dict(shape='box', wk=0.36, depth=0.42, lift=0.08, min_hx=8, min_hy=8,
                         note='斜角建築（糖果鎮）：底座是菱形，取中段的矩形'),
    'fence':        dict(shape='box', wk=0.95, depth=12, lift=2, min_hx=8, min_hy=4,
                         note='圍籬：整條、很薄'),
    'planter':      dict(shape='box', wk=0.95, depth=0.70, lift=0.0, min_hx=8, min_hy=4,
                         note='花台：整個底座'),
    'post':         dict(shape='ellipse', wk=1.0, depth=8, lift=1, min_hx=5, min_hy=3,
                         note='路燈：柱腳一小圈'),
    'fountain':     dict(shape='ellipse', wk=0.90, depth=0.50, lift=0.0, min_hx=8, min_hy=6,
                         note='噴泉：水池'),
    'prop':         dict(shape='ellipse', wk=0.60, depth=0.30, lift=0.04, min_hx=6, min_hy=4, width='full',
                         note='立著的小擺設（石頭、樹樁、寶箱、水晶）：底部小橢圓'),
    'bridge':       dict(shape='none', flat=True, note='橋：要走過去'),
    'arch':         dict(shape='none', note='拱門：要走過去'),
    'flat':         dict(shape='none', flat=True, note='平貼地面的東西'),
    'gather_small': dict(shape='none', note='小型採集點（藥草、落葉堆）：要走上去採'),
    'deco':         dict(shape='none', note='很小的地上裝飾'),
    'npc':          dict(shape='none', note='站著的 NPC（不擋，跟村民一致）'),
}

# art 路徑（Resources 底下、不含副檔名）→ 類別。由上往下第一個符合的為準。
RULES = [
    (r'/tree-apple-[a-z]+$', 'tree'),
    (r'/candy/p-lollitree$', 'tree'),
    (r'/(herb-patch|leaf-pile)$', 'gather_small'),
    (r'/bush-hedge$', 'hedge'),
    (r'/bush-(berry|bramble)$', 'bush'),
    (r'/town-tiles/bush-', 'bush'),
    (r'/town/[a-z-]+$', 'building'),
    (r'/candy/b-', 'building_iso'),
    (r'/town-tiles/bridge-', 'bridge'),
    (r'/town-tiles/arch$', 'arch'),
    (r'/town-tiles/fence-', 'fence'),
    (r'/town-tiles/lamp-', 'post'),
    (r'/town-tiles/fountain$', 'fountain'),
    (r'/town-tiles/planter$', 'planter'),
    (r'/candy/p-(bush|cloud)$', 'bush'),
    (r'/candy/p-bushrow$', 'hedge'),
    (r'/candy/p-grove$', 'grove'),
    (r'/candy/p-(chest|rock|stump|mint|crystal|crystal2)$', 'prop'),
    (r'/candy/p-peppermint$', 'flat'),
    (r'/candy/p-(candycane|cherries)$', 'deco'),
    (r'/candy/(tamer|guard|sproutling)$', 'npc'),
]
DEFAULT_CAT = 'prop'     # 分不出來的：當成立著的小擺設（底部小橢圓），並在輸出列出來


# ──────────── 從 C# 收集實際會擺出來的圖 ────────────

def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def collect_arts():
    """森林、城鎮、糖果鎮實際引用的 art 路徑（排序、去重）。"""
    arts = set()
    for name in ('ForestLayout.cs', 'TownLayout.cs'):
        arts |= set(re.findall(r'\bArt\s*=\s*"(art/[^"]+)"', _read(os.path.join(DATA, name))))
    # 糖果鎮：Candy.cs 只寫檔名，資料夾在 CandyTown.cs 的 ArtDir
    candy_dir = re.search(r'const\s+string\s+ArtDir\s*=\s*"([^"]+)"',
                          _read(os.path.join(ROOT, 'Assets', 'Scripts', 'Core', 'CandyTown.cs'))).group(1)
    src = _read(os.path.join(DATA, 'Candy.cs'))
    for sec in ('CandyNpc[] Npcs', 'CandyProp[] Buildings', 'CandyProp[] Props'):
        i = src.index(sec)
        j = src.index('};', i)
        arts |= {candy_dir + a for a in re.findall(r'\bArt\s*=\s*"([^"]+)"', src[i:j])}
    return sorted(arts)


def category_of(art):
    """回傳 (類別, 是不是退回預設值)。"""
    for pat, cat in RULES:
        if re.search(pat, art):
            return cat, False
    return DEFAULT_CAT, True


# ──────────── 量圖 ────────────

_measure_cache = {}


def measure(art):
    """量一張圖。回傳 dict（座標相對圖片中心、y 朝上、原圖像素）。"""
    if art in _measure_cache:
        return _measure_cache[art]
    path = os.path.join(RES, art.replace('/', os.sep) + '.png')
    a = np.asarray(Image.open(path).convert('RGBA'))[..., 3] >= ALPHA
    H, W = a.shape
    ys, xs = np.nonzero(a)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    oh = y1 - y0 + 1
    bh = max(3, int(round(BAND_FRAC * oh)))
    band = a[y1 - bh + 1:y1 + 1]
    cols = np.nonzero(band.mean(0) >= COL_FRAC)[0]
    if len(cols) == 0:                       # 底部太稀疏：退回聯集
        cols = np.nonzero(band.any(0))[0]
    fx0, fx1 = int(cols.min()), int(cols.max())
    widths = []
    for row in band:
        nz = np.nonzero(row)[0]
        if len(nz):
            widths.append(nz.max() - nz.min() + 1)
    trunk_w = float(np.median(widths)) if widths else float(fx1 - fx0 + 1)
    m = dict(
        w=W, h=H, oh=oh, band=bh,
        # 整體不透明範圍（相對中心、y 朝上）
        left=x0 - W / 2, right=x1 + 1 - W / 2,
        top=H / 2 - y0, bottom=H / 2 - (y1 + 1),
        # 貼地那一段
        foot_cx=(fx0 + fx1 + 1) / 2 - W / 2,
        foot_hw=(fx1 - fx0 + 1) / 2,
        trunk_hw=trunk_w / 2,
    )
    _measure_cache[art] = m
    return m


def _len(v, h):
    """>=1 當作像素、<1 當作高度比例。"""
    return float(v) if v >= 1 else float(v) * h


def footprint(art):
    """一張圖的碰撞形狀（相對圖片中心、y 朝上、原圖像素）。"""
    cat, fallback = category_of(art)
    c = CATS[cat]
    m = measure(art)
    fp = dict(art=art, key=art.split('/')[-1], cat=cat, fallback=fallback, shape=c['shape'],
              flat=bool(c.get('flat', False)), keep=bool(c.get('keep_order', False)),
              cx=0.0, cy=0.0, hx=0.0, hy=0.0, m=m)
    if c['shape'] == 'none':
        return fp
    h = m['oh']
    if cat == 'tree':
        hx = max(c['min_hx'], m['trunk_hw'] * c['wk'])
        hy = max(c['min_hy'], hx * 0.5)
        cy = m['bottom'] + hy * 0.5               # 橢圓中心略高於樹根底緣：腳可以稍微踩到樹根前面
    elif cat == 'building_iso':
        hx = max(c['min_hx'], m['w'] * c['wk'])
        d = _len(c['depth'], h)
        hy = max(c['min_hy'], d / 2)
        cy = m['bottom'] + _len(c['lift'], h) + hy
    else:
        full = c.get('width', 'foot') == 'full'
        hx = max(c['min_hx'], ((m['right'] - m['left']) / 2 if full else m['foot_hw']) * c['wk'])
        d = _len(c['depth'], h)
        hy = max(c['min_hy'], d / 2)
        cy = m['bottom'] + _len(c['lift'], h) + hy
    whole = cat == 'building_iso' or c.get('width', 'foot') == 'full'
    fp.update(cx=(m['left'] + m['right']) / 2 if whole else m['foot_cx'], cy=cy, hx=hx, hy=hy)
    return fp


def all_footprints():
    arts = collect_arts()
    keys = {}
    for a in arts:
        k = a.split('/')[-1]
        if k in keys and keys[k] != a:
            raise SystemExit(f'圖檔名撞名：{keys[k]} 與 {a}（執行期用 sprite 名稱查表，檔名必須唯一）')
        keys[k] = a
    return [footprint(a) for a in arts]


# ──────────── 世界座標（給離線檢查用；跟 Obstacles.cs 同一套換算）────────────

def world_shape(fp, x, y, scale, pivot):
    """物件擺在 (x, y)、縮放 scale 時的世界形狀。pivot='center'（森林/城鎮的場景物件）
    或 'foot'（糖果鎮：position 是腳底、圖往上推半個高）。回傳 None ＝ 不擋。"""
    m = fp['m']
    icx, icy = x, y if pivot == 'center' else y + m['h'] * scale / 2
    if fp['shape'] == 'none':
        return None
    return dict(name=fp['key'], cat=fp['cat'], shape=fp['shape'],
                cx=icx + fp['cx'] * scale, cy=icy + fp['cy'] * scale,
                hx=fp['hx'] * scale, hy=fp['hy'] * scale)


def image_rect(fp, x, y, scale, pivot):
    """整張圖在世界上的矩形 (x0, y0, x1, y1)，y 朝上。預覽用。"""
    m = fp['m']
    icy = y if pivot == 'center' else y + m['h'] * scale / 2
    return (x - m['w'] * scale / 2, icy - m['h'] * scale / 2,
            x + m['w'] * scale / 2, icy + m['h'] * scale / 2)


def carve_doors(shapes, doors, auto_range):
    """門口挖開：門的觸發點落在範圍裡、或在範圍正後方（自動觸發距離內）的建築，拆成左右兩塊，
    中間留 2×DOOR_GAP_HALF。觸發點在範圍底緣以下（正面、本來就走得到）不挖。
    doors：[(x, y)]。跟 Obstacles.CarveDoors 同一個判準。"""
    out = []
    for s in shapes:
        cut = None
        if s['shape'] == 'box' and s['cat'] in ('building', 'building_iso'):
            for (dx, dy) in doors:
                if (abs(dx - s['cx']) < s['hx'] and abs(dy - s['cy']) <= s['hy'] + auto_range
                        and dy >= s['cy'] - s['hy']):
                    cut = dx
                    break
        if cut is None:
            out.append(s)
            continue
        l0, l1 = s['cx'] - s['hx'], cut - DOOR_GAP_HALF
        r0, r1 = cut + DOOR_GAP_HALF, s['cx'] + s['hx']
        for (a, b) in ((l0, l1), (r0, r1)):
            if b - a > 2:
                t = dict(s)
                t['cx'], t['hx'] = (a + b) / 2, (b - a) / 2
                t['name'] = s['name'] + '（門邊）'
                out.append(t)
    return out


def penetration(s, px, py, r=PLAYER_RADIUS):
    """玩家腳底在 (px, py) 時插進這個形狀多深（<=0 ＝ 沒碰到）。跟 Obstacles.Pen 同一個算法。"""
    if s['shape'] == 'ellipse':
        rx, ry = s['hx'] + r, s['hy'] + r
        d = np.hypot((px - s['cx']) / rx, (py - s['cy']) / ry)
        return (1 - d) * min(rx, ry)
    qx = abs(px - s['cx']) - s['hx']
    qy = abs(py - s['cy']) - s['hy']
    outside = np.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0)
    return r - outside


# ──────────── 產生 C# ────────────

def _f(v):
    s = ('%.1f' % v)
    return s + 'f'


def write_cs(fps):
    rows = []
    for fp in fps:
        m = fp['m']
        kind = {'ellipse': 'FootShape.Ellipse', 'box': 'FootShape.Box', 'none': 'FootShape.None'}[fp['shape']]
        rows.append('            { "%s", new ArtFootprint("%s", %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) },' % (
            fp['key'], fp['cat'], kind, _f(fp['cx']), _f(fp['cy']), _f(fp['hx']), _f(fp['hy']),
            'true' if fp['flat'] else 'false', 'true' if fp['keep'] else 'false',
            _f(m['foot_cx']), _f(m['foot_hw']), _f(m['bottom'])))
    body = '\n'.join(rows)
    cs = '''// <auto-generated>
// ⚠️ 自動產生，不要手改。產生器：tools/gen_footprints.py
//    重跑：python tools/gen_footprints.py（再跑 python tools/check_walkable.py 看可達性與預覽）
//    要調某一類物件的範圍：改產生器裡的 CATS 係數，不是改這個檔。
// </auto-generated>
using System.Collections.Generic;

namespace WitchShop.Data
{
    /// <summary>碰撞形狀：不擋／軸對齊橢圓／軸對齊矩形（碰撞時再長一個玩家半徑＝圓角矩形）。</summary>
    public enum FootShape { None, Ellipse, Box }

    /// <summary>
    /// 一張物件圖的落地範圍。座標**相對圖片中心、y 朝上、單位是原圖像素**，
    /// 使用時乘上物件的 scale（翻面時 x 取負）。
    /// </summary>
    public readonly struct ArtFootprint
    {
        public readonly string Category;     // 類別（tree / building / bush …，見產生器的 CATS）
        public readonly FootShape Shape;
        public readonly float Cx, Cy;        // 形狀中心
        public readonly float Hx, Hy;        // 橢圓＝半徑、矩形＝半寬半高
        public readonly bool Flat;           // 平貼地面：排序壓到最底，不參與 YSort
        public readonly bool KeepOrder;      // 不改排序（城鎮建築：門口的擺設是貼著正面放的，見產生器的 CATS）
        public readonly float FootX, FootHalfW, BottomY;   // 量到的貼地那一段（中心、半寬）與不透明範圍的底緣

        public ArtFootprint(string category, FootShape shape, float cx, float cy, float hx, float hy,
                            bool flat, bool keepOrder, float footX, float footHalfW, float bottomY)
        {
            Category = category; Shape = shape; Cx = cx; Cy = cy; Hx = hx; Hy = hy; Flat = flat; KeepOrder = keepOrder;
            FootX = footX; FootHalfW = footHalfW; BottomY = bottomY;
        }

        public bool Blocks => Shape != FootShape.None;
    }

    /// <summary>
    /// 戶外物件的落地範圍表（玩家碰撞用）—— **自動產生，不要手改**。
    /// key 是圖檔名（＝執行期 Sprite 的名字）。查不到的圖一律不擋。
    /// </summary>
    public static class ArtFootprints
    {
        /// <summary>玩家腳底的碰撞圓半徑（像素）。</summary>
        public const float PlayerRadius = %PR%;
        /// <summary>戶外地圖邊緣往內縮（像素）：上緣一個身高、左右半個身寬、下緣一點點。</summary>
        public const float EdgeTop = %ET%, EdgeSide = %ES%, EdgeBottom = %EB%;
        /// <summary>門前在建築範圍上挖開的半寬（像素）。</summary>
        public const float DoorGapHalf = %DG%;
        /// <summary>執行期空間切格的格子大小（像素）。</summary>
        public const float CellSize = %CS%;
        /// <summary>平貼地面的東西（橋…）的排序。</summary>
        public const int FlatOrder = %FO%;

        static readonly Dictionary<string, ArtFootprint> Table = new()
        {
%BODY%
        };

        public static bool TryGet(string spriteName, out ArtFootprint fp) => Table.TryGetValue(spriteName, out fp);
    }
}
'''
    cs = (cs.replace('%BODY%', body)
            .replace('%PR%', _f(PLAYER_RADIUS)).replace('%ET%', _f(EDGE_TOP))
            .replace('%ES%', _f(EDGE_SIDE)).replace('%EB%', _f(EDGE_BOTTOM))
            .replace('%DG%', _f(DOOR_GAP_HALF)).replace('%CS%', _f(CELL_SIZE))
            .replace('%FO%', str(FLAT_ORDER)))
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(cs)


def main():
    fps = all_footprints()
    print('掃到 %d 張圖（森林／城鎮／糖果鎮實際擺出來的）：' % len(fps))
    print('  %-26s %-13s %-7s %8s %8s %7s %7s   %s' % ('圖', '類別', '形狀', '中心x', '中心y', '半寬', '半高', '量到的（圖寬×高／貼地寬／樹幹寬）'))
    for fp in fps:
        m = fp['m']
        print('  %-26s %-13s %-7s %8.1f %8.1f %7.1f %7.1f   %dx%d / %.0f / %.0f%s' % (
            fp['art'].replace('art/', ''), fp['cat'], fp['shape'], fp['cx'], fp['cy'], fp['hx'], fp['hy'],
            m['w'], m['h'], m['foot_hw'] * 2, m['trunk_hw'] * 2, '   ← 退回預設類別' if fp['fallback'] else ''))
    fb = [fp['art'] for fp in fps if fp['fallback']]
    print('退回預設類別（%s）的圖：%s' % (DEFAULT_CAT, '、'.join(fb) if fb else '無'))
    write_cs(fps)
    print('寫出', OUT, '共', len(fps), '筆')


if __name__ == '__main__':
    main()
