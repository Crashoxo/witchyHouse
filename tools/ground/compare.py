"""
產生前後對照圖（給人看的）：

  python tools/ground/compare.py OUTDIR

輸出 OUTDIR/<map>-before-after.png（整張縮圖，左前右後）與
OUTDIR/<map>-view-before-after.png（960×640 實際遊戲視野 1:1，上前下後，每張地圖兩個視野）。
「前」用 tools/ground/orig/ 的原圖，「後」用 Assets/Resources/art/ground/ 的烤好的圖；
兩邊都疊上真實物件與女巫。
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import preview as pv  # noqa: E402

# 每張地圖挑兩個視野放進對照圖（VIEWS 的索引）
PICK = {'forest': [0, 2], 'town': [0, 1, 2], 'candy': [0, 2]}
NAMES = {'forest': 'forest', 'town': 'town', 'candy': 'candy'}


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    for n in ('forest', 'town', 'candy'):
        LB = 'BEFORE' if n == 'forest' else 'BEFORE (as shown in game: 3200px squeezed to 2048 by import)'
        b = pv.compose(n, pv.ground_image(n, True))
        a = pv.compose(n, pv.ground_image(n, False))
        half = lambda im: im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
        pv.side_by_side(half(b), half(a), LB, 'AFTER').save(os.path.join(outdir, f'{n}-before-after.png'))
        vb, va = pv.views(n, b), pv.views(n, a)
        for k, i in enumerate(PICK[n]):
            suffix = '' if k == 0 else str(k + 1)
            pv.side_by_side(vb[i], va[i], LB, 'AFTER').save(
                os.path.join(outdir, f'{n}-view-before-after{suffix}.png'))
        print(n, 'ok')


if __name__ == '__main__':
    main(sys.argv[1])
