"""
地面烘焙器：重新烤出森林／城鎮／糖果鎮三張戶外地圖的地面。

  python tools/bake_ground.py                 # 三張都烤
  python tools/bake_ground.py town candy      # 只烤指定的
  python tools/bake_ground.py --preview DIR   # 烤完順便輸出疊上物件與女巫的預覽圖
  python tools/bake_ground.py --restore       # 把 tools/ground/orig/ 的原圖蓋回去（並刪掉新圖）

輸出（詳見 tools/ground/README.md）：
  Assets/Resources/art/ground/{forest,town,candy}.png   低解析度（1 美術像素＝2 世界像素），
      由 Assets/Scripts/Core/BakedGround.cs 在執行期貼到場景的 Ground 上（PPU 0.5）。
  Assets/Resources/art/ground-grass.png / town-ground.png / candy/candy-town.png
      原檔名、原尺寸的「墊底版」（編輯器裡看到的、或執行期沒換成時的樣子）。
固定亂數種子：同樣的輸入每次烤出一模一樣的圖。
"""
import os
import shutil
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'ground'))

import common  # noqa: E402
import layouts  # noqa: E402

ROOT = layouts.ROOT
ART = os.path.join(ROOT, 'Assets', 'Resources', 'art')
ORIG = os.path.join(HERE, 'ground', 'orig')
OUT_DIR = os.path.join(ART, 'ground')

# 原檔（墊底版）位置
LEGACY = {
    'forest': os.path.join(ART, 'ground-grass.png'),
    'town': os.path.join(ART, 'town-ground.png'),
    'candy': os.path.join(ART, 'candy', 'candy-town.png'),
}


def backup():
    os.makedirs(ORIG, exist_ok=True)
    for p in LEGACY.values():
        dst = os.path.join(ORIG, os.path.basename(p))
        if not os.path.exists(dst):
            shutil.copy2(p, dst)
            print('備份', p, '→', dst)


def restore():
    for name, p in LEGACY.items():
        src = os.path.join(ORIG, os.path.basename(p))
        shutil.copy2(src, p)
        print('還原', p)
        new = os.path.join(OUT_DIR, name + '.png')
        for f in (new, new + '.meta'):
            if os.path.exists(f):
                os.remove(f)
                print('刪除', f)


def bake(name):
    if name == 'forest':
        import forest as m
    elif name == 'town':
        import town as m
    else:
        import candy as m
    rgb = m.bake()
    W, H = layouts.SIZES[name]
    assert rgb.shape[:2] == (H // common.ART_PX, W // common.ART_PX), rgb.shape
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, name + '.png')
    n = common.to_png(rgb, out)
    print(f'{name}: {out}  {rgb.shape[1]}×{rgb.shape[0]}  {n} 色  {os.path.getsize(out) // 1024} KB')

    # 墊底版：原檔名、原尺寸
    legacy = LEGACY[name]
    if name == 'forest':
        tile = common.upscale(m.bake_tile())
        common.to_png(tile, legacy)
    else:
        common.to_png(common.upscale(rgb), legacy)
    print(f'   墊底 {legacy}  {os.path.getsize(legacy) // 1024} KB')


def main(argv):
    if '--restore' in argv:
        restore()
        return
    backup()
    preview = None
    if '--preview' in argv:
        preview = argv[argv.index('--preview') + 1]
    names = [a for a in argv if a in ('forest', 'town', 'candy')] or ['forest', 'town', 'candy']
    for n in names:
        bake(n)
    if preview:
        import preview as pv
        pv.run(preview, False, names)
        print('預覽 →', preview)


if __name__ == '__main__':
    main(sys.argv[1:])
