# -*- coding: utf-8 -*-
"""
中文字型子集化 —— 把 11.4 MB 的 Noto Sans TC 砍成「這個遊戲真的會用到的字」。

為什麼要做：`Assets/Resources/ui/fonts/NotoSansTC.ttf` 的 meta 是
`includeFontData: 1` 的 **Dynamic** 字型 —— 整份 .ttf 會原封不動打進 build，
執行期才即時描繪。所以只要把 .ttf 本身變小，build 就跟著變小。

怎麼決定留哪些字：**掃過 Assets 底下所有原始碼與版面檔的每一個字元**
（.cs / .uxml / .uss / .json / .txt / .md），連註解一起收。註解裡的字當然不會被
畫出來，但那是刻意留的安全邊際 —— 遊戲裡的文字全部是程式裡的字串常值
（`Data/` 的任務台詞、道具名、UI 標題……），寧可多收幾百個字（成本是幾十 KB），
也不要漏一個字變成豆腐。

⚠️ **玩家自己打的字沒辦法預先收**（例如以後做存檔命名、或那個 AI NPC 對話的計畫）。
   真的做到那種功能時，這條路就走不通了，要改成「子集 ＋ 系統字型 fallback」。

用法（改了任何中文字串之後重跑一次就好）：
    python tools/subset_font.py

來源是 `tools/fonts/NotoSansTC-full.ttf`（完整字型，刻意放在 Assets 外面，
Unity 不會匯入、也不會進 build），輸出蓋回 `Assets/Resources/ui/fonts/NotoSansTC.ttf`。
.meta 不動 → guid 不變 → 所有參照都不用重接。

需要 fontTools：`python -m pip install fonttools brotli`
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'tools', 'fonts', 'NotoSansTC-full.ttf')
DST = os.path.join(ROOT, 'Assets', 'Resources', 'ui', 'fonts', 'NotoSansTC.ttf')
SCAN_ROOT = os.path.join(ROOT, 'Assets')
SCAN_EXT = ('.cs', '.uxml', '.uss', '.json', '.txt', '.md')

# ⚠️ 來源是**可變字型**（Windows 內建的 NotoSansTC-VF），wght 軸是 100~900、
#    而預設值落在 **100 ＝ Thin**。Unity 的 legacy Font 走 FreeType，載進去只會描
#    「預設實例」—— 也就是說不處理的話，整個遊戲的中文是用髮絲般的細體在畫。
#    所以子集化之前先把它定在下面這個字重（順便甩掉 fvar/gvar，檔案又更小）。
#    覺得太細/太粗就改這個數字：400 ＝ Regular、500 ＝ Medium、700 ＝ Bold。
WEIGHT = 400

# 執行期才組出來、原始碼裡不一定出現的符號。多收這些幾乎不花空間。
EXTRA = (
    ''.join(chr(c) for c in range(0x20, 0x7F))          # 可見的 ASCII
    + '　、。，．；：？！…‧·＿～－—–‥'
    + '「」『』（）〔〕【】《》〈〉'
    + '＋＝％＊／＼｜＜＞＄＃＆＠'
    + '０１２３４５６７８９'
    + '←↑→↓★☆♪♥■□●○◆◇▲△※°℃'
)


def collect_chars():
    chars = set(EXTRA)
    files = 0
    for dirpath, _, filenames in os.walk(SCAN_ROOT):
        for name in filenames:
            if not name.endswith(SCAN_EXT):
                continue
            path = os.path.join(dirpath, name)
            try:
                text = io.open(path, encoding='utf-8').read()
            except (UnicodeDecodeError, OSError):
                continue
            files += 1
            chars |= set(text)
    # 控制字元不用留
    return {c for c in chars if ord(c) >= 0x20}, files


def main():
    if not os.path.isfile(SRC):
        sys.exit('找不到完整字型：%s' % SRC)

    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer
    except ImportError:
        sys.exit('缺 fontTools，先跑：python -m pip install fonttools brotli')

    chars, files = collect_chars()
    print('掃了 %d 個檔，要保留 %d 個字元' % (files, len(chars)))

    options = subset.Options()
    options.layout_features = []      # UI 純文字，不需要連字/替代字那些
    options.hinting = False           # Unity 用 FreeType 自己描繪，hinting 用不到
    options.desubroutinize = True
    options.name_IDs = ['*']          # 字型名稱要留著，Unity 靠它認人
    options.notdef_outline = True     # 真的漏字時畫成方框，比整段消失好查
    options.drop_tables += ['DSIG']

    font = subset.load_font(SRC, options)

    # ① 先把可變字型定在指定字重（不做的話會拿到 Thin，見上面 WEIGHT 的說明）。
    #    刻意不開 updateFontNames —— 字型家族名要維持 "Noto Sans TC"，
    #    .meta 的 fontNames 是照那個名字寫的，改掉 Unity 就認不出來了。
    if 'fvar' in font:
        instancer.instantiateVariableFont(font, {'wght': WEIGHT}, inplace=True)
        font['OS/2'].usWeightClass = WEIGHT

    # ② 再砍掉用不到的字
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text=''.join(sorted(chars)))
    subsetter.subset(font)
    subset.save_font(font, DST, options)

    # 驗一遍：真的每個字都在 cmap 裡嗎
    out = TTFont(DST)
    cmap = set()
    for table in out['cmap'].tables:
        cmap |= set(table.cmap.keys())
    missing = sorted(c for c in chars if ord(c) not in cmap)
    before = os.path.getsize(SRC)
    after = os.path.getsize(DST)
    print('%.1f MB → %.1f KB（剩 %.1f%%）'
          % (before / 1024 / 1024, after / 1024, after * 100.0 / before))
    if missing:
        # 完整字型本來就沒有的字（罕用字、表情符號…）—— 提醒一下，不是錯誤。
        # 注意：Windows 的主控台是 cp950，印不出這些字會直接丟例外，所以印碼位就好。
        print('[note] %d chars are not in the full font either (emoji/rare):' % len(missing))
        print('       ' + ' '.join('U+%04X' % ord(c) for c in missing))


if __name__ == '__main__':
    main()
