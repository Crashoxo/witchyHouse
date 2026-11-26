# -*- coding: utf-8 -*-
"""
程式合成的 8-bit 背景音樂 —— 產出 `Assets/Resources/audio/bgm/*.wav`，給 `Core/Bgm.cs` 播。

為什麼用合成的：跟 gen_sfx.py 同一個理由 —— 還沒有正式的音樂素材，先用同一套
復古合成（柔和的低通方波／三角波、ADSR、琶音、很輕的雜訊打點）寫四首短短的
循環曲，讓每個地方都有氣氛。之後有正式音樂，**直接用同名檔蓋掉
`Assets/Resources/audio/bgm/` 裡的檔案**就好，程式一行都不用改（Bgm 是照檔名載入的）。

用法（在專案根目錄）：
    python tools/gen_bgm.py          # 四首全部
    python tools/gen_bgm.py day      # 只產一首（day / night / shop / candy）

⚠️ 會覆蓋 `Assets/Resources/audio/bgm/` 底下同名的 .wav —— 如果已經換成正式音樂，
   不要再跑這支（或只產還沒換掉的那幾首）。

規格與約定：
- 只用 Python 3.9 標準函式庫，合成函式直接沿用 gen_sfx.py（tone / note / lowpass / write_wav）。
- 16-bit mono、22050 Hz（跟音效同規格）。匯入 Unity 時由 Editor/BgmImporter.cs 壓成 Vorbis。
- 旋律與和弦進行是**手寫的資料表**（音名＋拍數），不是隨機生的；亂數只用在打點的雜訊顆粒，
  種子固定（以曲名當種子），重跑結果逐 byte 一致。
- ⚠️ **無縫循環**：總長固定是整數小節；音符的尾巴（release、回音、低通的餘韻）超出結尾的部分
  **繞回開頭疊進去**（環狀緩衝），所以頭尾**不加淡入淡出**，循環點不會有爆音或停頓。
  低通、去直流、回音也都是「環狀」做的（先拿結尾那段暖機再處理），接點兩邊的濾波狀態一致。
- 峰值正規化到 PEAK（0.5）—— 音樂要比音效小聲、墊在底下不搶戲。夜晚曲另設 peak 0.40，再安靜一點。
- 每首不超過 40 秒（網頁版要小；Vorbis 壓過之後每首幾百 KB）。
"""

import os
import random
import sys

from gen_sfx import SR, lowpass, note, tone, write_wav

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'Assets', 'Resources', 'audio', 'bgm')

PEAK = 0.50          # 正規化後的峰值（音效是 0.8 × gain，音樂刻意更小聲）
MAX_SECONDS = 40.0   # 每首的長度上限
WARMUP = 4096        # 環狀濾波的暖機長度（取樣數）：一階濾波器的狀態早就收斂了


# ──────────────── 音名、和弦 ────────────────

_PC = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6,
       'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}


def midi_of(name):
    """'C4' → 60。"""
    return _PC[name[:-1]] + (int(name[-1]) + 1) * 12


def hz(m):
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


# 和弦：根音 ＋ 組成音（音名不帶八度；降記號一律寫成升記號，例如 Bb＝A#）
CHORDS = {
    'C': ('C', 'C E G'), 'Dm': ('D', 'D F A'), 'Em': ('E', 'E G B'), 'F': ('F', 'F A C'),
    'G': ('G', 'G B D'), 'Am': ('A', 'A C E'), 'Bm': ('B', 'B D F#'), 'D': ('D', 'D F# A'),
    'E': ('E', 'E G# B'), 'Gm': ('G', 'G A# D'), 'A#': ('A#', 'A# D F'),
    # 七和弦（day 用的西式色彩）：組成音照「根 三 五 七」排，第三個仍是五度音，fifth_midi() 照樣能用
    'Gmaj7': ('G', 'G B D F#'), 'Cmaj7': ('C', 'C E G B'), 'Em7': ('E', 'E G B D'),
    'Am7': ('A', 'A C E G'), 'Bm7': ('B', 'B D F# A'), 'D7': ('D', 'D F# A C'),
    # night 用的 F 大調柔和色彩（A#＝Bb）：maj7／m7／屬七，外加借自 F 小調的 Bbm（iv）—— 夜晚的那一點點暗
    'Fmaj7': ('F', 'F A C E'), 'Dm7': ('D', 'D F A C'), 'A#maj7': ('A#', 'A# D F A'),
    'C7': ('C', 'C E G A#'), 'Gm7': ('G', 'G A# D F'), 'A#m': ('A#', 'A# C# F'),
}


def voicing(chord, low):
    """和弦組成音排在 low（MIDI）以上最近的位置，由低到高。"""
    _, tones = CHORDS[chord]
    out = []
    for t in tones.split():
        pc = _PC[t]
        m = low + ((pc - low) % 12)
        out.append(m)
    return sorted(out)


def bass_midi(chord, low=40):
    """根音放在 E2（40）以上最近的位置。"""
    pc = _PC[CHORDS[chord][0]]
    return low + ((pc - low) % 12)


def fifth_midi(chord, low=40):
    """和弦第三個組成音（五度音）放在根音之上。"""
    root = bass_midi(chord, low)
    _, tones = CHORDS[chord]
    pc = _PC[tones.split()[2]]
    return root + ((pc - root) % 12)


def parse_bar(text):
    """'E5:1 G5:.5 -:1' → [('E5', 1.0), ('G5', 0.5), (None, 1.0)]。'-' 是休止。"""
    out = []
    for tok in text.split():
        nm, beats = tok.split(':')
        out.append((None if nm == '-' else nm, float(beats)))
    return out


# ──────────────── 環狀緩衝：超出結尾的尾巴繞回開頭 ────────────────

_tone_cache = {}


def cached_tone(dur, f, **kw):
    """同一個音（長度、音高、音色都一樣）只合成一次 —— 琶音與 bass 重複得很兇，省很多時間。"""
    key = (int(dur * SR), round(f, 4), tuple(sorted(kw.items())))
    buf = _tone_cache.get(key)
    if buf is None:
        buf = tone(dur, f, **kw)
        _tone_cache[key] = buf
    return buf


def add_wrapped(bus, start, part, gain=1.0):
    """把 part 疊進環狀的 bus，從第 start 個取樣開始；超過結尾的部分繞回開頭。"""
    n = len(bus)
    o = start % n
    i = 0
    m = len(part)
    while i < m:
        run = min(m - i, n - o)
        for j in range(run):
            bus[o + j] += part[i + j] * gain
        i += run
        o = 0


def lowpass_loop(buf, cutoff):
    """環狀的一階低通：先拿結尾那一段暖機，接點兩邊的濾波狀態才一致。"""
    w = min(WARMUP, len(buf))
    return lowpass(buf[-w:] + buf, cutoff)[w:]


def dc_block_loop(buf, r=0.995):
    """環狀的去直流（duty 0.25 的方波有直流偏移，不去掉會吃掉 headroom）。"""
    w = min(WARMUP, len(buf))
    x = buf[-w:] + buf
    out = []
    px = py = 0.0
    for v in x:
        py = v - px + r * py
        px = v
        out.append(py)
    return out[w:]


def echo_loop(buf, delay, taps):
    """環狀回音：taps 是每一階的音量（例如 (0.25, 0.1)），延遲 delay 個取樣。"""
    n = len(buf)
    out = list(buf)
    for k, g in enumerate(taps, start=1):
        d = (delay * k) % n
        for i in range(n):
            out[i] += buf[i - d] * g      # i - d 是負數時 Python 自己從尾巴取 → 天然環狀
    return out


# ──────────────── 四首曲子（手寫的資料表）────────────────
# 每首：
#   bpm / meter（一小節幾拍）
#   chords：一小節一個；寫 'Dm G' ＝ 前後各半小節
#   melody：一小節一串「音名:拍數」，每小節的拍數加起來要剛好等於 meter（下面會檢查）
#   lead：主旋律的音色    bass：一個和弦段落裡的 (起拍, 拍數, 'R'根音/'5'五度/'O'高八度)
#   arp：(每格拍數, 組成音索引的循環, 最低音, 音量, 音色)；可省略。索引超過組成音個數就往上一個八度
#        （例如四音和弦的 4＝根音高八度），琶音才能一路往上走；-1＝這格空著
#   pad：和弦墊底（慢慢浮起來的三角波長音）；可省略 —— 目前沒有曲子用（夜晚曲改成音樂盒後拿掉了）
#   stab：和弦刺點（整個和弦短短敲一下）—— full/half 是段落裡的起拍、low 最低音、len 拍數、vol、音色；可省略
#   lead 可另加 bell：高八度的正弦泛音（音量），短短一下就消失，像音樂盒／木琴的「叮」；省略＝0
#   perc：每小節的打點 (第幾拍, 種類, 音量)
#   peak：這首正規化的峰值；省略＝PEAK（0.5）

SONGS = {
    # 戶外白天（森林／城鎮）：西式 cozy 小鎮風，G 大調、108 BPM。
    # 原本是 C 大調、幾乎只用 C D E G A 的五聲音階＋抖音長音，被說「像武俠遊戲」，整首重寫：
    #   - 旋律用完整的自然大調，Do 之外刻意讓 Fa（C）與 Ti（F#）落在強拍與樂句轉折，多級進與鄰音，
    #     兩個半音經過音（第 8 小節 D–D#–E、第 11 小節 D–C#–D）
    #   - 節奏用附點、切分、八分短句加休止；主奏是短促的撥弦／音樂盒音色，沒有抖音、回音很輕
    #   - 和弦是七和弦，ii–V–I 終止；bass 咚–恰（根音／五度在 1、3 拍），和弦刺點在 2、4 拍
    # 段落：A(1–4)–A'(5–8 回主音)–B(9–12 下屬方向，上行模進)–C(13–16 ii–V–I，最後一拍的 A4 往上接回開頭的 B4)
    'day': dict(
        bpm=108, meter=4,
        chords=['Gmaj7', 'Em7', 'Am7', 'D7',
                'Gmaj7', 'Em7', 'Am7 D7', 'G',
                'Cmaj7', 'D', 'Bm7', 'Em7',
                'Cmaj7', 'Bm7 Em7', 'Am7 D7', 'G'],
        melody=[
            'B4:.5 C5:.5 D5:.75 B4:.25 F#5:1 -:.5 G5:.5',
            'E5:.5 D5:.5 E5:.75 F#5:.25 G5:1 -:1',
            'C5:.75 B4:.25 C5:.5 E5:.5 D5:.5 C5:.5 B4:.5 A4:.5',
            'F#4:.5 A4:.5 C5:1 B4:.5 A4:.5 -:.5 A4:.5',
            'B4:.5 C5:.5 D5:.75 B4:.25 F#5:1 -:.5 A5:.5',
            'G5:.75 F#5:.25 E5:.5 D5:.5 E5:1 -:.5 B4:.5',
            'C5:.5 D5:.5 E5:.5 C5:.5 A4:.75 B4:.25 C5:.5 F#4:.5',
            'G4:.75 A4:.25 B4:.5 G4:.5 -:1 D5:.5 D#5:.5',
            'E5:.75 D5:.25 C5:.5 B4:.5 C5:1 -:.5 E5:.5',
            'F#5:.75 E5:.25 D5:.5 C5:.5 D5:1 -:.5 F#5:.5',
            'G5:.5 F#5:.5 E5:.5 D5:.5 C#5:.5 D5:.5 B4:1',
            'E5:.5 -:.25 E5:.25 G5:.5 F#5:.5 E5:.5 D5:.5 B4:1',
            'C5:.5 E5:.5 D5:.5 C5:.5 B4:.75 C5:.25 D5:.5 E5:.5',
            'F#5:.75 G5:.25 A5:.5 F#5:.5 G5:.75 F#5:.25 E5:.5 D5:.5',
            'C5:.75 B4:.25 A4:.5 E5:.5 D5:.5 C5:.5 A4:.5 F#5:.5',
            'G5:.75 D5:.25 B4:.5 A4:.5 G4:1 -:.5 A4:.5',
        ],
        lead=dict(wave_='square', duty=0.5, a=0.003, d=0.09, s=0.22, rel=0.07, gate=0.58,
                  vib_rate=0.0, vib_depth=0.0, cutoff=2500, vol=1.0,
                  double=0.0, bell=0.22, echo=(0.75, (0.10,))),
        bass=dict(full=[(0, 0.55, 'R'), (2, 0.55, '5')],
                  half=[(0, 0.55, 'R')], vol=0.70),
        stab=dict(full=[1, 3], half=[1], low='B3', len=0.3, vol=0.075,
                  kw=dict(wave_='square', duty=0.25)),
        perc=dict(hits=[(0, 'kick', 0.28), (0.5, 'hat', 0.08), (1.5, 'hat', 0.12),
                        (2, 'kick', 0.20), (2.5, 'hat', 0.08), (3.5, 'hat', 0.12)]),
    ),

    # 戶外夜晚：西式的音樂盒搖籃曲，F 大調、76 BPM、3/4（動森深夜／星露谷夜晚那種安靜溫柔）。
    # 原本是 A 小調＋三角波抖音長音＋pad 墊底，小調五聲味加長音像簫／二胡，被說「像武俠遊戲」，整首重寫：
    #   - 和弦用 maj7／m7／屬七的柔和色彩，第 14 小節借 F 小調的 Bbm（iv）給一點夜晚的暗；結尾 C7 → 開頭 Fmaj7 是 V–I
    #   - 旋律用完整的自然大調、多級進，Fa（Bb）與 Ti（E）刻意常出現（合計約三成）；音符少、留白多，沒有長音
    #   - 主奏是音樂盒／鐘琴：三角波＋高八度的「叮」，起音極快、低 sustain、短 gate，讓聲音自己衰減掉；沒有抖音、回音很輕
    #   - 伴奏只有很輕的八分音符琶音一路往上走（根 三 五 七 再到高八度根音），低音每小節一個根音；沒有 pad、沒有打點
    # 段落：A(1–4)–A'(5–8 停在屬和弦)–B(9–12)–C(13–16 Bbmaj7–Bbm–Fmaj7–C7，最後的 E5–G5 往上接回開頭的 A5)
    'night': dict(
        bpm=76, meter=3,
        chords=['Fmaj7', 'Dm7', 'A#maj7', 'C7',
                'Fmaj7', 'Am7', 'Gm7', 'C7',
                'A#maj7', 'Am7', 'Dm7', 'Gm7',
                'A#maj7', 'A#m', 'Fmaj7', 'C7'],
        melody=[
            'A5:1 G5:.5 F5:.5 E5:1',
            'F5:1 D5:.5 E5:.5 F5:1',
            'A5:1 A#5:.5 A5:.5 F5:1',
            'G5:1 -:1 E5:.5 G5:.5',
            'A5:1 G5:.5 F5:.5 E5:1',
            'E5:1 D5:.5 C5:.5 E5:1',
            'A#4:.5 C5:.5 D5:1 F5:1',
            'E5:1 -:1 F5:.5 G5:.5',
            'A5:1 A#5:.5 A5:.5 F5:1',
            'G5:1 F5:.5 E5:.5 C5:1',
            'D5:1 E5:.5 F5:.5 A5:1',
            'A#5:1 -:.5 A5:.5 G5:1',
            'F5:1 D5:.5 E5:.5 F5:1',
            'C#5:1 -:.5 C5:.5 A#4:1',
            'A4:1 A#4:.5 C5:.5 E5:1',
            'D5:.5 C5:.5 -:.5 E5:.5 G5:1',
        ],
        lead=dict(wave_='triangle', duty=0.5, a=0.002, d=0.28, s=0.08, rel=0.3, gate=0.5,
                  vib_rate=0.0, vib_depth=0.0, cutoff=3200, vol=0.9,
                  double=0.0, bell=0.32, echo=(1.5, (0.12,))),
        bass=dict(full=[(0, 2.2, 'R')], half=[(0, 1.2, 'R')], vol=0.38),
        arp=(0.5, [-1, 0, 1, 2, 3, 4], 'F3', 0.075, dict(wave_='triangle')),   # 第一格讓給 bass
        perc=None,
        peak=0.40,      # 正規化峰值比其他曲（PEAK 0.5）低約 2 dB：整體 RMS 才會比白天曲安靜
    ),

    # 室內（店裡／藥水室／後花園）：輕快的小品，F 大調。bass 走 oom-pah，琶音往上跳。
    'shop': dict(
        bpm=104, meter=4,
        chords=['F', 'Dm', 'Gm', 'C',
                'F', 'Dm', 'Gm C', 'F',
                'A#', 'C', 'Am', 'Dm',
                'Gm', 'C', 'Gm C', 'F'],
        melody=[
            'C5:.5 A4:.5 C5:.5 F5:.5 A5:1 F5:1',  'D5:.5 F5:.5 A5:1 G5:1 F5:1',
            'G5:1 A#5:.5 A5:.5 G5:1 D5:1',        'E5:1.5 F5:.5 G5:2',
            'C5:.5 A4:.5 C5:.5 F5:.5 A5:1 C6:1',  'D6:1 C6:.5 A#5:.5 A5:1 F5:1',
            'G5:1 A#5:1 A5:.5 G5:.5 E5:1',        'F5:2 -:1 A4:.5 A#4:.5',
            'D5:1 F5:1 A#5:1.5 A5:.5',            'G5:1 E5:1 C5:2',
            'C5:.5 E5:.5 A5:1 G5:1 E5:1',         'F5:1 E5:.5 D5:.5 A4:2',
            'A#4:1 D5:1 G5:1 F5:1',               'E5:1 G5:1 C6:1 A#5:1',
            'A5:1 A#5:.5 A5:.5 G5:1 E5:1',        'F5:2.5 -:1.5',
        ],
        lead=dict(wave_='square', duty=0.25, a=0.006, d=0.08, s=0.55, rel=0.09, gate=0.72,
                  vib_rate=6.0, vib_depth=0.05, cutoff=2700, vol=1.0,
                  double=0.22, echo=(0.5, (0.18, 0.06))),
        bass=dict(full=[(0, 0.45, 'R'), (1, 0.45, '5'), (2, 0.45, 'R'), (3, 0.45, '5')],
                  half=[(0, 0.45, 'R'), (1, 0.45, '5')], vol=0.66),
        arp=(0.5, [-1, 0, 1, 2], 'A3', 0.15, dict(wave_='square', duty=0.125)),
        perc=dict(hits=[(0, 'kick', 0.30), (0.5, 'hat', 0.14), (1, 'snare', 0.16), (1.5, 'hat', 0.14),
                        (2, 'kick', 0.24), (2.5, 'hat', 0.14), (3, 'snare', 0.16), (3.5, 'hat', 0.14)]),
    ),

    # 糖果鎮：活潑跳躍，G 大調，八分音符跳來跳去的斷奏。最後一小節 B4–C5 往上接回開頭的 D5。
    'candy': dict(
        bpm=120, meter=4,
        chords=['G', 'Em', 'C', 'D',
                'G', 'Em', 'C D', 'G',
                'C', 'D', 'Bm', 'Em',
                'C', 'D', 'Am D', 'G'],
        melody=[
            'D5:.5 G5:.5 B5:.5 G5:.5 D5:.5 G5:.5 B5:1',  'E5:.5 G5:.5 B5:1 A5:.5 G5:.5 E5:1',
            'C5:.5 E5:.5 G5:.5 E5:.5 C6:1 B5:.5 A5:.5',  'F#5:1 A5:1 D5:2',
            'D5:.5 G5:.5 B5:.5 G5:.5 D6:1 B5:1',         'C6:.5 B5:.5 A5:.5 G5:.5 E5:1 G5:1',
            'E5:.5 G5:.5 C6:1 F#5:.5 A5:.5 D6:1',        'B5:.5 A5:.5 G5:2 -:1',
            'E5:1 E5:.5 G5:.5 C6:1 G5:1',                'F#5:1 F#5:.5 A5:.5 D6:1 A5:1',
            'B5:.5 A5:.5 F#5:.5 D5:.5 B4:1 D5:1',        'E5:1.5 F#5:.5 G5:1 B5:1',
            'C6:.5 B5:.5 A5:.5 G5:.5 E5:1 C5:1',         'D5:.5 F#5:.5 A5:.5 F#5:.5 D6:2',
            'C6:1 A5:1 F#5:1 A5:.5 F#5:.5',              'G5:2 -:1 B4:.5 C5:.5',
        ],
        lead=dict(wave_='square', duty=0.25, a=0.004, d=0.06, s=0.5, rel=0.07, gate=0.62,
                  vib_rate=0.0, vib_depth=0.0, cutoff=3000, vol=1.0,
                  double=0.20, echo=(0.75, (0.20, 0.07))),
        bass=dict(full=[(0, 0.4, 'R'), (0.5, 0.3, 'O'), (1, 0.4, '5'), (1.5, 0.3, 'O'),
                        (2, 0.4, 'R'), (2.5, 0.3, 'O'), (3, 0.4, '5'), (3.5, 0.3, 'O')],
                  half=[(0, 0.4, 'R'), (0.5, 0.3, 'O'), (1, 0.4, '5'), (1.5, 0.3, 'O')], vol=0.55),
        arp=(0.25, [0, 1, 2, 1], 'G4', 0.09, dict(wave_='square', duty=0.125)),
        perc=dict(hits=[(0, 'kick', 0.34), (0.5, 'hat', 0.16), (1, 'snare', 0.20), (1.5, 'hat', 0.16),
                        (2, 'kick', 0.30), (2.5, 'hat', 0.16), (3, 'snare', 0.20), (3.5, 'hat', 0.12),
                        (3.75, 'hat', 0.10)]),
    ),
}


# ──────────────── 合成一首 ────────────────

def segments(chords, meter):
    """把每小節的和弦字串攤開成 (起拍, 拍數, 和弦)。"""
    out = []
    for bar, text in enumerate(chords):
        names = text.split()
        span = meter / len(names)
        for k, c in enumerate(names):
            out.append((bar * meter + k * span, span, c))
    return out


def perc_hit(kind, rng):
    """打點：都很輕、很短，過一道低通，只是給節奏一點顆粒。"""
    if kind == 'kick':
        return tone(0.11, 120, 48, wave_='triangle', a=0.002, d=0.07, s=0.15, r=0.03)
    if kind == 'snare':
        n = lowpass(tone(0.09, 3200, wave_='noise', a=0.002, d=0.05, s=0.12, r=0.03, rng=rng), 2600)
        b = tone(0.06, 210, 160, wave_='triangle', a=0.002, d=0.04, s=0.1, r=0.02, vol=0.5)
        return [x + (b[i] if i < len(b) else 0.0) for i, x in enumerate(n)]
    # hat
    return tone(0.03, 7000, wave_='noise', a=0.001, d=0.015, s=0.1, r=0.01, rng=rng)


def render(name, song):
    bpm, meter = song['bpm'], song['meter']
    spb = 60.0 / bpm
    bars = len(song['chords'])
    total_beats = bars * meter
    n = int(round(total_beats * spb * SR))
    if n / SR > MAX_SECONDS + 1e-9:
        raise SystemExit(f'{name}: {n / SR:.2f}s 超過 {MAX_SECONDS}s 上限')

    def at(beat):
        return int(round(beat * spb * SR))

    rng = random.Random('witch-bgm:' + name)      # 只有打點的雜訊顆粒會用到

    # ── 檢查旋律的拍數（寫錯一拍整首就歪掉，在這裡擋下來）
    if len(song['melody']) != bars:
        raise SystemExit(f'{name}: 旋律 {len(song["melody"])} 小節，和弦 {bars} 小節，對不起來')
    for i, text in enumerate(song['melody']):
        s = sum(b for _, b in parse_bar(text))
        if abs(s - meter) > 1e-9:
            raise SystemExit(f'{name}: 第 {i + 1} 小節旋律是 {s} 拍，應該是 {meter} 拍')

    # ── 主旋律
    L = song['lead']
    lead = [0.0] * n
    beat = 0.0
    for text in song['melody']:
        for nm, beats in parse_bar(text):
            if nm is not None:
                f = note(nm)
                held = beats * spb * L['gate']
                dur = held + L['rel']
                kw = dict(wave_=L['wave_'], duty=L['duty'], a=L['a'], d=L['d'], s=L['s'], r=L['rel'],
                          vib_rate=L['vib_rate'], vib_depth=L['vib_depth'])
                add_wrapped(lead, at(beat), cached_tone(dur, f, **kw), L['vol'])
                if L['double']:      # 低八度的三角波陪著，聲音比較圓、比較暖
                    add_wrapped(lead, at(beat), cached_tone(dur, f / 2, wave_='triangle', a=L['a'] + 0.01,
                                                            d=L['d'], s=0.6, r=L['rel']), L['double'])
                if L.get('bell', 0.0):     # 高八度的正弦泛音，一下就消失 —— 撥弦／音樂盒的「叮」
                    add_wrapped(lead, at(beat), cached_tone(min(dur, 0.18), f * 2, wave_='sine', a=0.002,
                                                            d=0.06, s=0.0, r=0.03), L['bell'])
            beat += beats
    lead = lowpass_loop(lead, L['cutoff'])
    if L['echo']:
        dbeats, taps = L['echo']
        lead = echo_loop(lead, at(dbeats), taps)

    # ── bass（三角波）
    B = song['bass']
    bass = [0.0] * n
    segs = segments(song['chords'], meter)
    for start, span, ch in segs:
        pattern = B['full'] if span >= meter else B['half']
        for off, length, deg in pattern:
            if off >= span:
                continue
            m = bass_midi(ch)
            if deg == '5':
                m = fifth_midi(ch)
            elif deg == 'O':
                m += 12
            dur = length * spb + 0.06
            add_wrapped(bass, at(start + off),
                        cached_tone(dur, hz(m), wave_='triangle', a=0.006, d=0.12, s=0.7, r=0.06), B['vol'])
    bass = lowpass_loop(bass, 1400)

    # ── 琶音（很輕的細方波／三角波，墊在旋律底下）
    arp = [0.0] * n
    if song.get('arp'):
        step, idx, low, avol, akw = song['arp']
        low_m = midi_of(low)
        for start, span, ch in segs:
            tones = voicing(ch, low_m)
            k = 0
            t = 0.0
            while t < span - 1e-9:
                i = idx[k % len(idx)]
                if i >= 0:
                    # 索引 < 組成音個數時跟原本一模一樣；超過的部分往上疊八度
                    f = hz(tones[i % len(tones)] + 12 * (i // len(tones)))
                    dur = step * spb * 0.8 + 0.05
                    add_wrapped(arp, at(start + t),
                                cached_tone(dur, f, a=0.004, d=0.05, s=0.45, r=0.05, **akw), avol)
                k += 1
                t += step
        arp = lowpass_loop(arp, 2200)

    # ── 和弦刺點（白天：咚–恰的「恰」，整個和弦短短敲一下；跟 bass 錯開拍子）
    stab = [0.0] * n
    if song.get('stab'):
        S = song['stab']
        low_m = midi_of(S['low'])
        for start, span, ch in segs:
            for off in (S['full'] if span >= meter else S['half']):
                if off >= span:
                    continue
                dur = S['len'] * spb + 0.04
                for m in voicing(ch, low_m):
                    add_wrapped(stab, at(start + off),
                                cached_tone(dur, hz(m), a=0.003, d=0.06, s=0.3, r=0.04, **S['kw']), S['vol'])
        stab = lowpass_loop(stab, 2000)

    # ── 和弦墊底（每小節一個慢慢浮起來的三角波和弦，跟著尾巴疊進下一小節；目前沒有曲子用）
    pad = [0.0] * n
    if song.get('pad'):
        P = song['pad']
        for start, span, ch in segs:
            dur = span * spb + 0.6
            for m in voicing(ch, midi_of(P['low'])):
                add_wrapped(pad, at(start),
                            cached_tone(dur, hz(m), wave_='triangle', a=0.5, d=0.3, s=0.8, r=0.7), P['vol'])
        pad = lowpass_loop(pad, 1200)

    # ── 打點
    perc = [0.0] * n
    if song.get('perc'):
        for bar in range(bars):
            for b, kind, vol in song['perc']['hits']:
                add_wrapped(perc, at(bar * meter + b), perc_hit(kind, rng), vol)
        perc = lowpass_loop(perc, 5200)

    # ── 混音、去直流、正規化（頭尾不淡入淡出：循環點靠環狀緩衝接起來）
    out = [lead[i] + bass[i] + arp[i] + stab[i] + pad[i] + perc[i] for i in range(n)]
    out = dc_block_loop(out)
    peak = max(1e-9, max(abs(v) for v in out))
    k = song.get('peak', PEAK) / peak       # 曲子可自訂峰值（夜晚曲要更安靜）；省略＝PEAK
    return [v * k for v in out]


def main(argv):
    names = argv or list(SONGS)
    bad = [x for x in names if x not in SONGS]
    if bad:
        raise SystemExit(f'不認得的曲名：{", ".join(bad)}（可用：{", ".join(SONGS)}）')
    os.makedirs(OUT_DIR, exist_ok=True)
    total = 0
    for name in names:
        buf = render(name, SONGS[name])
        path = os.path.join(OUT_DIR, name + '.wav')
        write_wav(path, buf)
        size = os.path.getsize(path)
        total += size
        print(f'  {name:<6} {len(buf) / SR:5.2f}s  {size / 1024:7.1f} KB')
    print(f'共 {len(names)} 首，{total / 1024:.0f} KB → {os.path.relpath(OUT_DIR, ROOT)}')


if __name__ == '__main__':
    main(sys.argv[1:])
