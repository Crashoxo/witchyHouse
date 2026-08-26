# -*- coding: utf-8 -*-
"""把 PixelLab Objects 出的房子換進 assets/art/town/ 與 town.scene。

    D:/python/python.exe tools/import_town_buildings.py

* 來源畫在 Size 192 的畫布上（主體約 145~173px）→ **×2 NEAREST 存成 1:1 的圖**
  （town/ 這批本來就是 1:1，node 的 sizeMode 是 TRIMMED，畫多大就多大）。
* 沿用原本的 uuid，所以 town.scene 的引用不用動；只要同步改 meta 的尺寸與
  node 的 contentSize。
"""
import sys, os, io, json, glob, shutil

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DL = os.path.join(os.path.expanduser('~'), 'Downloads')
TOWN = os.path.join(ROOT, 'assets', 'art', 'town')
SRCKEEP = os.path.join(ROOT, 'tools', 'art-src', 'town', 'buildings')
SCENE = os.path.join(ROOT, 'assets', 'town.scene')
K = 2

# 來源資料夾前綴 -> 要取代的建築
MAP = {
    'Top-down_pixel_art_RPG_cute_co': 'cottage-home',
    'Top-down_pixel_art_RPG_cute_al': 'potion-shop',
    'Top-down_pixel_art_RPG_magic_s': 'scroll-shop',
}


def main():
    os.makedirs(SRCKEEP, exist_ok=True)
    sizes = {}
    for folder, slot in MAP.items():
        fs = glob.glob(os.path.join(DL, folder, 'rotations', '*.png'))
        if not fs:
            print('⚠️ 找不到 %s' % folder)
            continue
        shutil.copy(fs[0], os.path.join(SRCKEEP, slot + '-src.png'))
        im = Image.open(fs[0]).convert('RGBA')
        im = im.crop(im.getbbox())
        big = im.resize((im.width * K, im.height * K), Image.NEAREST)
        dst = os.path.join(TOWN, slot + '.png')
        old = Image.open(dst).size
        big.save(dst)
        sizes[slot] = big.size
        print('%-14s %s -> %s   (舊的是 %s)' % (slot, im.size, big.size, old))

        # meta：只改尺寸相關欄位，uuid 一律不動
        mp = dst + '.meta'
        m = json.load(io.open(mp, encoding='utf-8'))
        w, h = big.size
        for sid, sub in m['subMetas'].items():
            ud = sub['userData']
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
        io.open(mp, 'w', encoding='utf-8', newline='\n').write(
            json.dumps(m, indent=2, ensure_ascii=False))

    # scene：同步 contentSize（sizeMode 是 TRIMMED，執行期會自己算，但編輯器看得到才不會困惑）
    raw = io.open(SCENE, encoding='utf-8', newline='').read()
    crlf = '\r\n' in raw
    d = json.loads(raw)
    props = next(o for o in d if o.get('__type__') == 'cc.Node' and o.get('_name') == 'Props')
    n_done = 0
    for ch in props['_children']:
        n = d[ch['__id__']]
        if n['_name'] in sizes:
            w, h = sizes[n['_name']]
            for c in n['_components']:
                o = d[c['__id__']]
                if o['__type__'] == 'cc.UITransform':
                    o['_contentSize'].update(width=w, height=h)
                    n_done += 1
    txt = json.dumps(d, ensure_ascii=False, indent=2)
    if crlf:
        txt = txt.replace('\n', '\r\n')
    io.open(SCENE, 'w', encoding='utf-8', newline='').write(txt)
    print('town.scene 更新 %d 個 contentSize（行尾 %s）' % (n_done, 'CRLF' if crlf else 'LF'))


if __name__ == '__main__':
    main()
