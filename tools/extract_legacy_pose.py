# -*- coding: utf-8 -*-
"""
把「前一位（紫袍）女巫」的施法 6 幀＋蹲下 5 幀從舊圖集裡抽出來存成 tools/legacy_pose.png。

為什麼要存：2026-08-07 換上新的哥德女巫時，她只有走路與跑步，施法/蹲下的新圖還沒做；
而舊圖的**來源資料夾（桌面 Idle／新增資料夾 …）已經被刪掉了**，唯一還留著這兩段動畫的
地方就是舊的 resources/witch8/base.png。先抽成獨立檔，export_witch8.py 才能重跑
（不然重跑一次就會拿「已經被自己寫過的 base.png」當來源，愈跑愈糊）。

新圖集的施法/蹲下換好之後，這個檔跟 export_witch8.py 裡讀它的那段就可以一起刪掉。

輸出 tools/legacy_pose.png：8 欄 × 2 列、格子 38×53（舊圖集的格子大小）
                            列 0 ＝施法（欄 0..5 有效）／列 1 ＝蹲下（欄 0..4 有效）
"""
import os, sys
from PIL import Image
sys.stdout.reconfigure(encoding='utf-8')

SRC = r"D:\Crash\witch-shop\assets\resources\witch8\base.png"
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "legacy_pose.png")

OLD_COLS, OLD_ROWS = 8, 11        # 舊排法：列 0 站姿／1..8 走路／9 施法／10 蹲下
ROW_CAST, ROW_CROUCH = 9, 10

sheet = Image.open(SRC).convert("RGBA")
cw, ch = sheet.width // OLD_COLS, sheet.height // OLD_ROWS
print(f"來源 {SRC}  {sheet.width}x{sheet.height}  格子 {cw}x{ch}")
if (cw, ch) != (38, 53):
    print("⚠️ 格子大小不是舊圖集的 38x53 —— base.png 可能已經被新版蓋掉了，先確認再跑！")

out = Image.new("RGBA", (OLD_COLS * cw, 2 * ch), (0, 0, 0, 0))
for r_out, r_in in enumerate((ROW_CAST, ROW_CROUCH)):
    band = sheet.crop((0, r_in * ch, OLD_COLS * cw, (r_in + 1) * ch))
    out.paste(band, (0, r_out * ch))
out.save(DST)
print(f"寫出 {DST}  {out.size[0]}x{out.size[1]}  {os.path.getsize(DST)/1024:.0f}KB")
