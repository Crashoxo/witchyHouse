"""
預覽合成：把地面圖 + 實際物件（照資料檔的座標）+ 女巫疊成一張，方便肉眼檢查。

  python tools/ground/preview.py OUTDIR            # 用目前 Assets 裡的地面（＝烤好的新圖）
  python tools/ground/preview.py OUTDIR --before   # 用 tools/ground/orig/ 的原圖

輸出 OUTDIR/<map>-full.png（整張縮圖）與 OUTDIR/<map>-view<N>.png（960×640 1:1 實際視野）。
物件縮放用 NEAREST，跟 Unity 的 Point 濾鏡一樣。
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import layouts  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = layouts.RES

# 女巫出生點（各 SceneBuilder 寫死的位置）
SPAWN = {'forest': (0, 0), 'town': (-1200, -40), 'candy': (0, -820)}
WITCH_SCALE = 1.6

# 960×640 檢查視野的中心點（世界座標）
VIEWS = {
    'forest': [(0, 0), (-700, -450), (950, 0), (0, 600)],
    'town': [(-1200, -40), (600, 300), (1250, 400), (-300, -500)],
    'candy': [(0, -820), (0, 0), (-900, 450), (1100, -500)],
}

_cache = {}


def _img(path):
    if path not in _cache:
        _cache[path] = Image.open(path).convert('RGBA')
    return _cache[path]


def witch():
    im = _img(os.path.join(RES, 'witch8', 'base.png'))
    cw, ch = im.width // 8, im.height // 25
    cell = im.crop((0, 0, cw, ch))
    return cell.resize((round(cw * WITCH_SCALE), round(ch * WITCH_SCALE)), Image.NEAREST)


def ground_image(name, before=False):
    """回傳世界大小（1 像素＝1 單位）的地面圖。"""
    W, H = layouts.SIZES[name]
    if before:
        src = {'forest': 'ground-grass.png', 'town': 'town-ground.png', 'candy': 'candy-town.png'}[name]
        im = Image.open(os.path.join(HERE, 'orig', src)).convert('RGB')
        if name != 'forest' and im.width > 2048:
            # 遊戲裡實際看到的樣子：原圖 .meta 的 Max Size 是 2048，Unity 匯入時會先縮到
            # 2048 寬（預設 Mitchell 濾鏡），畫的時候再用 Point 拉回 3200 —— 這裡照樣模擬
            s = 2048 / im.width
            im = im.resize((2048, round(im.height * s)), Image.BICUBIC).resize((W, H), Image.NEAREST)
            return im
        if name == 'forest':          # 原本是 256 平鋪
            out = Image.new('RGB', (W, H))
            for y in range(0, H, im.height):
                for x in range(0, W, im.width):
                    out.paste(im, (x, y))
            return out
        return im
    path = os.path.join(RES, 'art', 'ground', name + '.png')
    im = Image.open(path).convert('RGB')
    return im.resize((W, H), Image.NEAREST)


def compose(name, ground):
    W, H = layouts.SIZES[name]
    canvas = ground.convert('RGBA').copy()
    objs = layouts.OBJECTS[name]()
    items = []
    for o in objs:
        items.append((o.y, o))
    sx, sy = SPAWN[name]
    items.append((sy, 'witch'))
    items.sort(key=lambda t: -t[0])          # sortingOrder = -y：y 大的先畫
    wimg = witch()
    for y, o in items:
        if o == 'witch':
            im = wimg
            px = sx + W / 2 - im.width / 2
            py = H / 2 - sy - im.height
        else:
            src = _img(o.path())
            w, h = max(1, round(src.width * o.scale)), max(1, round(src.height * o.scale))
            im = src.resize((w, h), Image.NEAREST) if (w, h) != src.size else src
            px = o.x + W / 2 - w / 2
            if o.pivot == 'center':
                py = H / 2 - o.y - h / 2
            else:
                py = H / 2 - o.y - h
        canvas.alpha_composite(im, (int(round(px)), int(round(py)))) if 0 <= px and 0 <= py and px + im.width <= W and py + im.height <= H \
            else _paste_clip(canvas, im, int(round(px)), int(round(py)))
    return canvas.convert('RGB')


def _paste_clip(canvas, im, px, py):
    canvas.paste(im, (px, py), im)


def views(name, comp):
    W, H = layouts.SIZES[name]
    out = []
    for cx, cy in VIEWS[name]:
        x0 = int(min(max(cx + W / 2 - 480, 0), W - 960))
        y0 = int(min(max(H / 2 - cy - 320, 0), H - 640))
        out.append(comp.crop((x0, y0, x0 + 960, y0 + 640)))
    return out


def run(outdir, before=False, names=('forest', 'town', 'candy')):
    os.makedirs(outdir, exist_ok=True)
    tag = 'before' if before else 'after'
    res = {}
    for n in names:
        comp = compose(n, ground_image(n, before))
        comp.resize((comp.width // 2, comp.height // 2), Image.LANCZOS).save(os.path.join(outdir, f'{n}-{tag}-full.png'))
        vs = views(n, comp)
        for i, v in enumerate(vs):
            v.save(os.path.join(outdir, f'{n}-{tag}-view{i}.png'))
        res[n] = (comp, vs)
    return res


def side_by_side(a, b, label_a='BEFORE', label_b='AFTER', vertical=False):
    from PIL import ImageDraw
    gap = 12
    if vertical:
        out = Image.new('RGB', (max(a.width, b.width), a.height + b.height + gap), (20, 20, 20))
        out.paste(a, (0, 0)); out.paste(b, (0, a.height + gap))
        pos = [(8, 8), (8, a.height + gap + 8)]
    else:
        out = Image.new('RGB', (a.width + b.width + gap, max(a.height, b.height)), (20, 20, 20))
        out.paste(a, (0, 0)); out.paste(b, (a.width + gap, 0))
        pos = [(8, 8), (a.width + gap + 8, 8)]
    d = ImageDraw.Draw(out)
    for (x, y), t in zip(pos, (label_a, label_b)):
        d.rectangle((x - 4, y - 2, x + 8 * len(t) + 4, y + 14), fill=(0, 0, 0))
        d.text((x, y), t, fill=(255, 255, 255))
    return out


if __name__ == '__main__':
    od = sys.argv[1]
    before = '--before' in sys.argv
    names = [a for a in sys.argv[2:] if not a.startswith('--')] or ['forest', 'town', 'candy']
    run(od, before, names)
