# -*- coding: utf-8 -*-
"""從現在的 town.scene + town-ground.png 生一張 50x32 的城鎮地圖底稿。

一個像素 = 遊戲裡一格 64x64。使用者拿它去小畫家/Aseprite 塗改路網，
再由 gen_town_ground.py 依這張圖鋪成 3200x2048 的地面。

    D:/python/python.exe tools/gen_town_map.py

輸出：
    tools/art-guide/town-map.png        50x32  ← 這張是拿去塗的
    tools/art-guide/town-map-guide.png  x12 預覽，疊格線與房子位置（只給人看）
"""
import sys, os, io, re, json, math

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENE = os.path.join(ROOT, 'assets', 'town.scene')
GROUND = os.path.join(ROOT, 'assets', 'art', 'town-ground.png')
TILES = os.path.join(ROOT, 'assets', 'art', 'town-tiles')
OUT = os.path.join(ROOT, 'tools', 'art-guide')

TILE = 64                      # 遊戲內一格
W, H = 3200, 2048              # 城鎮世界大小
COLS, ROWS = W // TILE, H // TILE   # 50 x 32

# 調色盤 —— 塗圖時就用這幾個顏色，一色一種地形
PALETTE = {
    'grass':  (94, 155, 73),
    'dirt':   (150, 111, 68),
    'cobble': (150, 150, 158),
    'paver':  (176, 124, 104),
    'water':  (60, 120, 190),
}
ORDER = ['grass', 'water', 'dirt', 'cobble', 'paver']

# 節點名字前綴 -> 地形
def road_class(name):
    n = name[5:] if name.startswith('road-') else name
    if n.startswith('dirt'):
        return 'dirt'
    if n.startswith('cobble'):
        return 'cobble'
    if n.startswith('paver') or n.startswith('arch'):
        return 'paver'
    if n.startswith('bridge'):
        return 'cobble'
    if n.startswith('puddle'):
        return None            # 水窪太小，不進地形圖
    return None


def load_scene():
    with io.open(SCENE, encoding='utf-8') as f:
        return json.load(f)


def find_node(d, name):
    for i, o in enumerate(d):
        if o.get('__type__') == 'cc.Node' and o.get('_name') == name:
            return i, o
    return None, None


def content_size(d, node):
    for c in node.get('_components', []):
        o = d[c['__id__']]
        if o.get('__type__') == 'cc.UITransform':
            s = o.get('_contentSize', {})
            return float(s.get('width', 0)), float(s.get('height', 0))
    return 0.0, 0.0


def world_to_px(x, y):
    """世界座標 -> town-ground.png 的像素座標（Ground 錨點置中）。"""
    return x + W / 2.0, H / 2.0 - y


def main():
    d = load_scene()

    # ---- 1. 草地 / 溪流：直接看底圖顏色 ----
    g = Image.open(GROUND).convert('RGB').resize((COLS, ROWS), Image.BOX)
    grid = [[None] * COLS for _ in range(ROWS)]
    for r in range(ROWS):
        for c in range(COLS):
            R, G, B = g.getpixel((c, r))
            grid[r][c] = 'water' if (B > R + 18 and B > G + 6) else 'grass'

    # ---- 2. 路面：把 Roads 底下每個節點的實際 alpha 蓋上去 ----
    cover = {}                                   # (r,c) -> {class: 像素數}
    _, roads = find_node(d, 'Roads')
    missing = []
    for ch in roads.get('_children', []):
        node = d[ch['__id__']]
        cls = road_class(node.get('_name', ''))
        if cls is None:
            continue
        base = node['_name'][5:]
        src = os.path.join(TILES, base + '.png')
        if not os.path.exists(src):
            # Cocos 會給同名節點加 -001 之類的尾巴
            src = os.path.join(TILES, re.sub(r'-\d{3}$', '', base) + '.png')
        if not os.path.exists(src):
            missing.append(node['_name'])
            continue
        w, h = content_size(d, node)
        if w <= 0 or h <= 0:
            continue
        im = Image.open(src).convert('RGBA').resize((int(round(w)), int(round(h))), Image.NEAREST)
        ang = float(node.get('_euler', {}).get('z', 0) or 0)
        if abs(ang) > 0.5:
            im = im.rotate(ang, expand=True, resample=Image.NEAREST)
        pos = node.get('_lpos', {})
        cx, cy = world_to_px(float(pos.get('x', 0)), float(pos.get('y', 0)))
        ox, oy = cx - im.width / 2.0, cy - im.height / 2.0
        a = im.split()[3]
        # 逐格數 alpha
        for r in range(max(0, int(oy // TILE)), min(ROWS, int((oy + im.height) // TILE) + 1)):
            for c in range(max(0, int(ox // TILE)), min(COLS, int((ox + im.width) // TILE) + 1)):
                bx, by = c * TILE - ox, r * TILE - oy
                box = (int(bx), int(by), int(bx) + TILE, int(by) + TILE)
                if box[0] >= im.width or box[1] >= im.height or box[2] <= 0 or box[3] <= 0:
                    continue
                crop = a.crop(box)
                n = sum(1 for v in crop.getdata() if v > 96)
                if n:
                    cover.setdefault((r, c), {})
                    cover[(r, c)][cls] = cover[(r, c)].get(cls, 0) + n

    covered = 0
    for (r, c), by_cls in cover.items():
        cls, n = max(by_cls.items(), key=lambda kv: kv[1])
        if n >= TILE * TILE * 0.22:              # 蓋掉超過 22% 才算這一格是路
            grid[r][c] = cls
            covered += 1

    # ---- 3. 存 50x32 ----
    out = Image.new('RGB', (COLS, ROWS))
    for r in range(ROWS):
        for c in range(COLS):
            out.putpixel((c, r), PALETTE[grid[r][c]])
    os.makedirs(OUT, exist_ok=True)
    p1 = os.path.join(OUT, 'town-map.png')
    out.save(p1)

    # ---- 4. 給人看的預覽：放大 + 格線 + 房子框 ----
    K = 12
    pv = out.resize((COLS * K, ROWS * K), Image.NEAREST)
    dr = ImageDraw.Draw(pv)
    for c in range(COLS + 1):
        dr.line([(c * K, 0), (c * K, ROWS * K)], fill=(0, 0, 0, 60), width=1)
    for r in range(ROWS + 1):
        dr.line([(0, r * K), (COLS * K, r * K)], fill=(0, 0, 0, 60), width=1)
    _, props = find_node(d, 'Props')
    marks = []
    for ch in props.get('_children', []):
        node = d[ch['__id__']]
        nm = node.get('_name', '')
        pos = node.get('_lpos', {})
        px, py = world_to_px(float(pos.get('x', 0)), float(pos.get('y', 0)))
        w, h = content_size(d, node)
        if nm == 'Player':
            dr.ellipse([px / TILE * K - 5, py / TILE * K - 5, px / TILE * K + 5, py / TILE * K + 5],
                       outline=(255, 60, 60), width=2)
            marks.append(('Player', px, py))
            continue
        if nm.startswith('town-'):
            continue                              # 小景物不標
        x0 = (px - w / 2) / TILE * K
        x1 = (px + w / 2) / TILE * K
        y1 = py / TILE * K                        # 錨點 (0.5,0)
        y0 = y1 - h / TILE * K
        dr.rectangle([x0, y0, x1, y1], outline=(230, 60, 200), width=2)
        marks.append((nm, px, py))
    p2 = os.path.join(OUT, 'town-map-guide.png')
    pv.save(p2)

    counts = {k: 0 for k in ORDER}
    for r in range(ROWS):
        for c in range(COLS):
            counts[grid[r][c]] += 1
    print('格數 %dx%d = %d 格（一格 %dpx）' % (COLS, ROWS, COLS * ROWS, TILE))
    for k in ORDER:
        print('   %-7s %-16s %4d 格  %4.1f%%' % (k, str(PALETTE[k]), counts[k], counts[k] / (COLS * ROWS) * 100))
    print('路面節點蓋到 %d 格' % covered)
    if missing:
        print('找不到來源圖：', ', '.join(sorted(set(missing))))
    print('建築 %d 棟：' % (len(marks) - 1), ', '.join(m[0] for m in marks if m[0] != 'Player'))
    print('\n輸出：\n   %s\n   %s' % (p1, p2))


if __name__ == '__main__':
    main()
