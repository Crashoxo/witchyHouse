# -*- coding: utf-8 -*-
"""把 PixelLab Objects 出的城鎮景物匯入 assets/art/town-tiles/ 並換進 town.scene。

    D:/python/python.exe tools/import_town_props.py "<objects 資料夾>" [--dry]

* 灌木/柵欄 -> town-tiles/ + 手工 meta（sprite-frame、nearest、trimType none），
  再把 town.scene 裡對應的節點改成引用新圖（同時更新 UITransform 的 contentSize）。
* 野花草叢 -> tools/art-src/town/deco-flower-NN.png，由 gen_town_ground.py 灑進地面。

⚠️ 這批素材是 1:1 使用（不放大）。舊的 town-tiles 是 31px 原圖顯示成 62px（x2），
   新的原圖本來就 ~52px，所以 x1 就跟舊的一樣大。
"""
import sys, os, io, re, json, glob, random, argparse, shutil
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(ROOT, 'assets', 'art', 'town-tiles')
ARTSRC = os.path.join(ROOT, 'tools', 'art-src', 'town')
SCENE = os.path.join(ROOT, 'assets', 'town.scene')
TEMPLATE = os.path.join(TILES, 'bush-green.png.meta')
UUID_BASE = 'a3000000-%04d-4a00-8b00-a30000000%03d'
SEED = 20260826


def load(p):
    im = Image.open(p).convert('RGBA')
    b = im.getbbox()
    return im.crop(b) if b else im


def flower_kind(im):
    """依非綠色的點綴顏色分類：warm(粉/紅/橘) / white / plain。"""
    a = np.array(im).astype(int)
    m = a[..., 3] > 128
    r, g, b = a[..., 0][m], a[..., 1][m], a[..., 2][m]
    warm = ((r > g + 25) & (r > 110)).mean()
    white = ((r > 190) & (g > 190) & (b > 175)).mean()
    if warm > 0.02:
        return 'warm'
    if white > 0.02:
        return 'white'
    return 'plain'


def write_meta(png, uuid, name):
    tpl = json.load(io.open(TEMPLATE, encoding='utf-8'))
    w, h = Image.open(png).size
    tpl['uuid'] = uuid
    for sid, sub in tpl['subMetas'].items():
        sub['uuid'] = '%s@%s' % (uuid, sid)
        sub['displayName'] = name
        ud = sub['userData']
        if 'imageUuidOrDatabaseUri' in ud:
            ud['imageUuidOrDatabaseUri'] = uuid
        if 'width' in ud:
            ud.update(width=w, height=h, rawWidth=w, rawHeight=h,
                      trimX=0, trimY=0, offsetX=0, offsetY=0)
            hw, hh = w / 2.0, h / 2.0
            ud['vertices'] = {
                'rawPosition': [-hw, -hh, 0, hw, -hh, 0, -hw, hh, 0, hw, hh, 0],
                'indexes': [0, 1, 2, 2, 1, 3],
                'uv': [0, h, w, h, 0, 0, w, 0],
                'nuv': [0, 0, 1, 0, 0, 1, 1, 1],
                'minPos': [-hw, -hh, 0], 'maxPos': [hw, hh, 0],
            }
    io.open(png + '.meta', 'w', encoding='utf-8', newline='\n').write(
        json.dumps(tpl, indent=2, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    rng = random.Random(SEED)

    def group(pat):
        return sorted(glob.glob(os.path.join(a.src, '*%s*' % pat, 'rotations', '*.png')))

    bushes = [load(p) for p in group('round_g')]
    fences = [load(p) for p in group('wooden')]
    flowers = [load(p) for p in group('cute_ti')]
    print('灌木 %d ／ 柵欄 %d ／ 野花 %d' % (len(bushes), len(fences), len(flowers)))

    kinds = [flower_kind(im) for im in bushes]
    print('灌木分類：', Counter(kinds))

    if a.dry:
        return

    # --- 1. 灌木與柵欄進 town-tiles ---
    assets = {}          # name -> (uuid, w, h)
    idx = 1
    for i, im in enumerate(bushes, 1):
        name = 'bush-n%02d' % i
        p = os.path.join(TILES, name + '.png')
        im.save(p)
        u = UUID_BASE % (idx, idx)
        write_meta(p, u, name)
        assets[name] = (u, im.width, im.height)
        idx += 1
    for i, im in enumerate(fences, 1):
        name = 'fence-n%02d' % i
        p = os.path.join(TILES, name + '.png')
        im.save(p)
        u = UUID_BASE % (idx, idx)
        write_meta(p, u, name)
        assets[name] = (u, im.width, im.height)
        idx += 1
    print('寫進 town-tiles：%d 個 png + meta' % len(assets))

    # --- 2. 野花進 art-src 給地面灑 ---
    for f in glob.glob(os.path.join(ARTSRC, 'deco-flower-*.png')):
        os.remove(f)
    for i, im in enumerate(flowers, 1):
        im.save(os.path.join(ARTSRC, 'deco-flower-%02d.png' % i))
    print('野花 %d 張 -> tools/art-src/town/deco-flower-*.png' % len(flowers))

    # --- 3. 換 town.scene ---
    raw = io.open(SCENE, encoding='utf-8', newline='').read()
    crlf = '\r\n' in raw
    d = json.loads(raw)
    by_kind = {k: [n for n, kk in zip(sorted(assets)[:len(bushes)], kinds) if kk == k]
               for k in ('warm', 'white', 'plain')}
    bush_names = sorted(n for n in assets if n.startswith('bush-n'))
    fence_names = sorted(n for n in assets if n.startswith('fence-n'))
    want = {'town-bush-pink': 'warm', 'town-bush-white': 'white', 'town-bush-green': 'plain'}

    props = next(o for o in d if o.get('__type__') == 'cc.Node' and o.get('_name') == 'Props')
    changed = 0
    for ch in props['_children']:
        n = d[ch['__id__']]
        base = re.sub(r'-\d{3}$', '', n['_name'])
        if base in want:
            pool = by_kind.get(want[base]) or bush_names
        elif base == 'town-fence-white':
            pool = fence_names
        else:
            continue
        name = rng.choice(pool)
        uuid, w, h = assets[name]
        for c in n['_components']:
            o = d[c['__id__']]
            if o['__type__'] == 'cc.UITransform':
                o['_contentSize'].update(width=w, height=h)
            elif o['__type__'] == 'cc.Sprite':
                o['_spriteFrame']['__uuid__'] = uuid + '@f9941'
        changed += 1
    txt = json.dumps(d, ensure_ascii=False, indent=2)
    if crlf:
        txt = txt.replace('\n', '\r\n')
    io.open(SCENE, 'w', encoding='utf-8', newline='').write(txt)
    print('town.scene 換掉 %d 個節點（行尾 %s）' % (changed, 'CRLF' if crlf else 'LF'))


if __name__ == '__main__':
    main()
