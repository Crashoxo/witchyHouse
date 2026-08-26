# -*- coding: utf-8 -*-
"""直接讀 town.scene ＋ 地面圖，算出 960x640 的相機視角。

    D:/python/python.exe tools/render_town.py --at 0,0 --name 廣場
    D:/python/python.exe tools/render_town.py --at -1500,-40 --no-roads

--ground  用哪張地面圖（預設 tools/art-guide/town-ground-preview.png）
--no-roads  不畫 Roads 容器（＝路面已經烤進地面圖的情況）
"""
import sys, os, io, json, re, glob, argparse

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ART_DIRS = [os.path.join(ROOT, 'assets', 'art', d) for d in ('town-tiles', 'town', 'candy')]
WITCH = os.path.join(ROOT, 'assets', 'resources', 'witch8', 'base.png')
DESKTOP = os.path.join(os.path.expanduser('~'), 'Desktop')
VIEW = (960, 640)
WITCH_SCALE = 1.6


_UUID_MAP = None


def uuid_map():
    """掃 .meta 建 uuid -> png 對照，才能照場景「實際引用的圖」畫，而不是猜檔名。"""
    global _UUID_MAP
    if _UUID_MAP is None:
        _UUID_MAP = {}
        for d in ART_DIRS:
            for m in glob.glob(os.path.join(d, '*.png.meta')):
                try:
                    j = json.load(io.open(m, encoding='utf-8'))
                except Exception:
                    continue
                _UUID_MAP[j['uuid']] = m[:-5]
    return _UUID_MAP


def art_for(name):
    base = re.sub(r'-\d{3}$', '', name)
    if base.startswith('road-'):
        base = base[5:]
    elif base.startswith('town-'):
        base = base[5:]
    for d in ART_DIRS:
        p = os.path.join(d, base + '.png')
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--at', default='0,0')
    ap.add_argument('--name', default='視角')
    ap.add_argument('--ground', default=os.path.join(ROOT, 'tools', 'art-guide', 'town-ground-preview.png'))
    ap.add_argument('--no-roads', action='store_true')
    ap.add_argument('--scene', default='town')
    args = ap.parse_args()
    cx, cy = (float(v) for v in args.at.split(','))

    with io.open(os.path.join(ROOT, 'assets', args.scene + '.scene'), encoding='utf-8') as f:
        d = json.load(f)

    def node(i):
        return d[i]

    def size_of(n):
        for c in n.get('_components', []):
            o = d[c['__id__']]
            if o.get('__type__') == 'cc.UITransform':
                s = o.get('_contentSize', {})
                a = o.get('_anchorPoint', {})
                return (float(s.get('width', 0)), float(s.get('height', 0)),
                        float(a.get('x', .5)), float(a.get('y', .5)))
        return (0, 0, .5, .5)

    def find(name):
        for i, o in enumerate(d):
            if o.get('__type__') == 'cc.Node' and o.get('_name') == name:
                return o
        return None

    gimg = Image.open(args.ground).convert('RGBA')
    GW, GH = gimg.size
    # 世界座標 -> 地面圖像素
    def w2p(x, y):
        return x + GW / 2.0, GH / 2.0 - y

    px, py = w2p(cx, cy)
    left, top = px - VIEW[0] / 2, py - VIEW[1] / 2
    left = max(0, min(GW - VIEW[0], left))
    top = max(0, min(GH - VIEW[1], top))
    canvas = gimg.crop((int(left), int(top), int(left) + VIEW[0], int(top) + VIEW[1])).convert('RGBA')

    def sprite_png(n):
        """優先用 Sprite 引用的 uuid 找圖；找不到才退回檔名猜測。"""
        for c in n.get('_components', []):
            o = d[c['__id__']]
            if o.get('__type__') == 'cc.Sprite':
                sf = (o.get('_spriteFrame') or {}).get('__uuid__', '')
                base = sf.split('@')[0]
                p = uuid_map().get(base)
                if p:
                    return p
        return art_for(n.get('_name', ''))

    def draw(n, ysort_key):
        p = sprite_png(n)
        if not p:
            return None
        w, h, ax, ay = size_of(n)
        if w <= 0:
            return None
        im = Image.open(p).convert('RGBA').resize((int(round(w)), int(round(h))), Image.LANCZOS)
        ang = float(n.get('_euler', {}).get('z', 0) or 0)
        if abs(ang) > 0.5:
            im = im.rotate(ang, expand=True, resample=Image.BICUBIC)
        pos = n.get('_lpos', {})
        wx, wy = float(pos.get('x', 0)), float(pos.get('y', 0))
        ix, iy = w2p(wx, wy)
        x0 = ix - im.width * ax
        y0 = iy - im.height * (1 - ay)
        return (ysort_key, im, int(x0 - left), int(y0 - top))

    items = []
    if not args.no_roads:
        roads = find('Roads') or {'_children': []}
        for ch in (roads or {}).get('_children', []):
            r = draw(node(ch['__id__']), 10 ** 9)     # Roads 永遠畫在最下層
            if r:
                items.append(r)
    props = find('Props')
    player_pos = None
    for ch in props.get('_children', []):
        n = node(ch['__id__'])
        if n.get('_name') == 'Player':
            pos = n.get('_lpos', {})
            player_pos = (float(pos.get('x', 0)), float(pos.get('y', 0)))
            continue
        r = draw(n, -float(n.get('_lpos', {}).get('y', 0)))
        if r:
            items.append(r)
    items.sort(key=lambda t: (-t[0] if t[0] == 10 ** 9 else t[0]))
    items.sort(key=lambda t: t[0], reverse=True)
    for _, im, x, y in items:
        canvas.alpha_composite(im, (x, y))

    w8 = Image.open(WITCH).convert('RGBA')
    cw, chh = w8.width // 8, w8.height // 25
    witch = w8.crop((0, 0, cw, chh)).resize((int(cw * WITCH_SCALE), int(chh * WITCH_SCALE)), Image.NEAREST)
    canvas.alpha_composite(witch, (VIEW[0] // 2 - witch.width // 2, VIEW[1] // 2 - witch.height))

    out = os.path.join(DESKTOP, '城鎮_%s.png' % args.name)
    canvas.convert('RGB').save(out)
    print('%s   (世界座標 %.0f,%.0f，玩家出生點 %s)' % (out, cx, cy, player_pos))


if __name__ == '__main__':
    main()
