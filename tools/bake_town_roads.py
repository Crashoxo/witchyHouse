# -*- coding: utf-8 -*-
"""把路面烤進地面圖之後的收尾：

1. 從 town-map.png 產 `assets/scripts/data/townRoads.ts`（村民路點）
2. 從 town.scene 刪掉已經沒用的路面/水窪節點（橋留著），並重編 __id__

    D:/python/python.exe tools/bake_town_roads.py [--dry]
"""
import sys, os, io, json, re, argparse

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENE = os.path.join(ROOT, 'assets', 'town.scene')
MAP = os.path.join(ROOT, 'tools', 'art-guide', 'town-map.png')
DATA = os.path.join(ROOT, 'assets', 'scripts', 'data', 'townRoads.ts')
TILE = 64
ROAD_RGB = {(150, 111, 68), (150, 150, 158), (176, 124, 104)}   # dirt / cobble / paver
KEEP = ('road-bridge',)          # 橋留著，其餘 road-* 都刪


def gen_waypoints():
    im = Image.open(MAP).convert('RGB')
    cols, rows = im.size
    W, H = cols * TILE, rows * TILE
    road = [[im.getpixel((c, r)) in ROAD_RGB for c in range(cols)] for r in range(rows)]

    def deg(r, c):
        n = 0
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < rows and 0 <= cc < cols and road[rr][cc]:
                n += 1
        return n

    pts = []
    for r in range(rows):
        for c in range(cols):
            # 只取路的「內部」（四周至少 3 格也是路），村民才不會走在路邊緣
            if road[r][c] and deg(r, c) >= 3:
                pts.append((c, r))
    # 稀疏取樣：格點間隔至少 3 格，避免資料肥大又分佈不均
    picked = []
    for c, r in pts:
        if all(abs(c - pc) + abs(r - pr) >= 3 for pc, pr in picked):
            picked.append((c, r))
    out = []
    for c, r in picked:
        x = (c + 0.5) * TILE - W / 2
        y = H / 2 - (r + 0.5) * TILE
        out.append((int(round(x)), int(round(y))))
    return out, cols, rows


def write_data(pts):
    lines = ',\n'.join('    { x: %d, y: %d }' % p for p in pts)
    src = '''/**
 * 城鎮路點 —— 給 TownFolk 當村民的走動目標。
 *
 * 以前是讀 town.scene 的 `World/Roads` 子節點位置，但路面已經烤進 `town-ground.png`
 * （由 `tools/art-guide/town-map.png` 那張 50x32 的小地圖決定），場景裡不再有路面節點。
 * 這份清單由 `tools/gen_town_ground.py` 的同一張小地圖產生（`tools/bake_town_roads.py`），
 * **改地圖之後重跑那支腳本，村民動線就會自動跟著改**，跟以前一樣不用改程式。
 *
 * 取樣規則：只取「四周至少 3 格也是路」的格（＝路的內部，村民不會貼著路邊走），
 * 再以曼哈頓距離 >= 3 格稀疏化。
 */
export const TOWN_WALK: Array<{ x: number; y: number }> = [
%s,
];
''' % lines
    io.open(DATA, 'w', encoding='utf-8', newline='\n').write(src)
    meta = {
        "ver": "4.0.24", "importer": "typescript",
        "imported": True, "uuid": "5c0ab1de-0049-4900-8900-5c0ab1de0049",
        "files": [], "subMetas": {}, "userData": {}
    }
    io.open(DATA + '.meta', 'w', encoding='utf-8', newline='\n').write(
        json.dumps(meta, indent=2, ensure_ascii=False))


def strip_roads(dry):
    raw = io.open(SCENE, encoding='utf-8', newline='').read()
    crlf = raw.count('\r\n')
    d = json.loads(raw)
    assert json.dumps(d, ensure_ascii=False, indent=2).replace('\r\n', '\n') \
        == raw.replace('\r\n', '\n'), 'round-trip 不一致，不敢動'

    roads_i = next(i for i, o in enumerate(d)
                   if o.get('__type__') == 'cc.Node' and o.get('_name') == 'Roads')
    drop_nodes = []
    for ch in d[roads_i]['_children']:
        n = d[ch['__id__']]
        if not n['_name'].startswith(KEEP):
            drop_nodes.append(ch['__id__'])
    drop = set(drop_nodes)
    for i in drop_nodes:                       # 連同它們的元件一起刪
        for c in d[i].get('_components', []):
            drop.add(c['__id__'])
        pr = d[i].get('_prefab')
        if pr:
            drop.add(pr['__id__'])
    print('要刪 %d 個節點 + 元件，共 %d 個元素（原本 %d）' % (len(drop_nodes), len(drop), len(d)))
    if dry:
        return

    d[roads_i]['_children'] = [c for c in d[roads_i]['_children'] if c['__id__'] not in drop]
    keep = [i for i in range(len(d)) if i not in drop]
    remap = {old: new for new, old in enumerate(keep)}

    def fix(o):
        if isinstance(o, dict):
            if set(o.keys()) == {'__id__'}:
                assert o['__id__'] in remap, '指到被刪掉的元素 %d' % o['__id__']
                return {'__id__': remap[o['__id__']]}
            return {k: fix(v) for k, v in o.items()}
        if isinstance(o, list):
            return [fix(v) for v in o]
        return o

    out = [fix(d[i]) for i in keep]
    for o in out:                              # dangling 檢查
        for m in re.finditer(r'"__id__":\s*(\d+)', json.dumps(o)):
            assert int(m.group(1)) < len(out), 'dangling __id__'
    txt = json.dumps(out, ensure_ascii=False, indent=2)
    if crlf:                                   # 行尾跟著原檔走
        txt = txt.replace('\n', '\r\n')
    io.open(SCENE, 'w', encoding='utf-8', newline='').write(txt)
    print('town.scene 現在 %d 個元素（行尾 %s）' % (len(out), 'CRLF' if crlf else 'LF'))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    pts, cols, rows = gen_waypoints()
    print('村民路點 %d 個（地圖 %dx%d）' % (len(pts), cols, rows))
    if not a.dry:
        write_data(pts)
        print('已寫 %s' % DATA)
    strip_roads(a.dry)
