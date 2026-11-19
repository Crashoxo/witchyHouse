"""
從 Unity 專案的資料檔（Assets/Scripts/Data/*.cs）讀出三張戶外地圖上的物件座標。

只讀不寫 —— ForestLayout.cs / TownLayout.cs 是自動產生的，Candy.cs 是手寫的，
這裡用正規表示式把 `Art = "...", X = .., Y = .., Scale = ..` 抓出來即可。

座標系：Unity 世界座標（PPU=1，1 單位＝1 像素），原點在地圖正中央，y 朝上。
"""
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA = os.path.join(ROOT, 'Assets', 'Scripts', 'Data')
RES = os.path.join(ROOT, 'Assets', 'Resources')

_PAT = re.compile(r'Art\s*=\s*"([^"]+)"\s*,\s*X\s*=\s*(-?[\d.]+)f?\s*,\s*Y\s*=\s*(-?[\d.]+)f?\s*,'
                  r'\s*Scale\s*=\s*([\d.]+)f?')


def _read(name):
    with open(os.path.join(DATA, name), encoding='utf-8') as f:
        return f.read()


def _section(src, start, end_marker='};'):
    i = src.index(start)
    j = src.index(end_marker, i)
    return src[i:j]


class Obj:
    """地圖上的一個物件。pivot='center'（森林/城鎮）或 'foot'（糖果鎮，錨點在腳底）。"""

    def __init__(self, art, x, y, scale, pivot, kind):
        self.art, self.x, self.y, self.scale, self.pivot, self.kind = art, x, y, scale, pivot, kind

    def path(self):
        return os.path.join(RES, self.art.replace('/', os.sep) + '.png')

    def __repr__(self):
        return f'Obj({self.art},{self.x},{self.y},{self.scale},{self.pivot})'


def _parse(text, pivot, kind, prefix=''):
    return [Obj(prefix + m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4)), pivot, kind)
            for m in _PAT.finditer(text)]


def forest():
    src = _read('ForestLayout.cs')
    return _parse(src, 'center', 'forest')


def town():
    src = _read('TownLayout.cs')
    return _parse(src, 'center', 'town')


def candy():
    src = _read('Candy.cs')
    out = []
    out += _parse(_section(src, 'CandyProp[] Buildings'), 'foot', 'building', 'art/candy/')
    out += _parse(_section(src, 'CandyProp[] Props'), 'foot', 'prop', 'art/candy/')
    out += _parse(_section(src, 'CandyNpc[] Npcs'), 'foot', 'npc', 'art/candy/')
    return out


# 每張地圖的世界大小（＝Ground 的 bounds，不能改）
SIZES = {'forest': (2816, 1792), 'town': (3200, 2048), 'candy': (3200, 2048)}
OBJECTS = {'forest': forest, 'town': town, 'candy': candy}

if __name__ == '__main__':
    for k, f in OBJECTS.items():
        objs = f()
        print(k, len(objs), objs[:2])
