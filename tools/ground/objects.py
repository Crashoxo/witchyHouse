"""
物件的「落腳處」：從圖的 alpha 量出實際不透明範圍，算出它站在地上的位置與寬度，
給烘焙器畫樹蔭／踩實的泥土用。座標全部換成美術像素（左上原點、y 朝下）。
"""
import numpy as np
from PIL import Image

from common import ART_PX
import layouts

_cache = {}


def _alpha_box(path):
    if path not in _cache:
        a = np.asarray(Image.open(path).convert('RGBA'))[..., 3] > 40
        ys, xs = np.nonzero(a)
        h, w = a.shape
        if len(ys) == 0:
            _cache[path] = None
        else:
            bottom = ys.max()
            low = a[max(0, bottom - h // 6):bottom + 1]      # 底部 1/6 的不透明寬度＝腳的寬度
            lx = np.nonzero(low.any(0))[0]
            _cache[path] = dict(w=w, h=h, x0=xs.min(), x1=xs.max(), y0=ys.min(), y1=bottom,
                                fx0=lx.min(), fx1=lx.max())
    return _cache[path]


class Foot:
    def __init__(self, obj, cx, cy, width, foot_w, height, top):
        self.obj, self.cx, self.cy, self.width, self.foot_w, self.height, self.top = \
            obj, cx, cy, width, foot_w, height, top

    @property
    def art(self):
        return self.obj.art.split('/')[-1]


def feet(name):
    W, H = layouts.SIZES[name]
    out = []
    for o in layouts.OBJECTS[name]():
        b = _alpha_box(o.path())
        if b is None:
            continue
        s = o.scale
        # 圖左上角的世界像素座標（y 朝下）
        if o.pivot == 'center':
            left = o.x + W / 2 - b['w'] * s / 2
            top = H / 2 - o.y - b['h'] * s / 2
        else:
            left = o.x + W / 2 - b['w'] * s / 2
            top = H / 2 - o.y - b['h'] * s
        cx = left + (b['fx0'] + b['fx1'] + 1) / 2 * s
        cy = top + (b['y1'] + 1) * s
        out.append(Foot(o, cx / ART_PX, cy / ART_PX,
                        (b['x1'] - b['x0'] + 1) * s / ART_PX,
                        (b['fx1'] - b['fx0'] + 1) * s / ART_PX,
                        (b['y1'] - b['y0'] + 1) * s / ART_PX,
                        (top + b['y0'] * s) / ART_PX))
    return out


def ellipse(h, w, cx, cy, rx, ry):
    """回傳 0..1 的橢圓距離場（中心 1、邊緣 0、外面負）。"""
    yy, xx = np.mgrid[0:h, 0:w]
    d = ((xx + 0.5 - cx) / max(rx, 0.5)) ** 2 + ((yy + 0.5 - cy) / max(ry, 0.5)) ** 2
    return 1 - np.sqrt(d)


def ellipse_local(h, w, cx, cy, rx, ry, pad=2):
    """只在 bbox 內算的橢圓距離場：回傳 (slice_y, slice_x, field)。"""
    y0, y1 = max(0, int(cy - ry - pad)), min(h, int(cy + ry + pad) + 1)
    x0, x1 = max(0, int(cx - rx - pad)), min(w, int(cx + rx + pad) + 1)
    if y0 >= y1 or x0 >= x1:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d = ((xx + 0.5 - cx) / max(rx, 0.5)) ** 2 + ((yy + 0.5 - cy) / max(ry, 0.5)) ** 2
    return slice(y0, y1), slice(x0, x1), 1 - np.sqrt(d)
