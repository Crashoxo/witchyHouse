# -*- coding: utf-8 -*-
"""
程式合成的 8-bit 音效 —— 產出 `Assets/Resources/audio/*.wav`，給 `Core/Sfx.cs` 播。

為什麼用合成的：遊戲原本完全沒有聲音，也還沒有正式的音效素材。先用 sfxr 那一路的
復古合成（方波／三角波／雜訊、頻率滑動、ADSR 包絡、琶音）補一套「溫暖、可愛、cozy」
的佔位音效，讓每個動作都有回饋。之後有正式音檔，**直接用同名 .wav 蓋掉
`Assets/Resources/audio/` 裡的檔案**就好，程式一行都不用改（Sfx 是照檔名載入的）。

用法（在專案根目錄）：
    python tools/gen_sfx.py                          （全部）
    python tools/gen_sfx.py chime-open chime-close   （只產指定的名字，其他檔不碰）

⚠️ 會覆蓋 `Assets/Resources/audio/` 底下同名的 .wav —— 如果已經換成正式音檔，
   不要再跑這支（或先把那幾個名字從 SOUNDS 表裡拿掉）。

規格與約定：
- 只用 Python 3.9 標準函式庫（wave / math / random / struct），**不依賴 numpy**。
- 16-bit mono、22050 Hz。每個檔都很短，全部加起來幾百 KB（網頁版要小）。
- 亂數種子固定（每個音效各自以名字當種子），重跑結果逐 byte 一致。
- 方波一律過一道一階低通，把尖銳的高頻削掉 —— 要的是星露谷那種圓潤的 8-bit，不是刺耳的嗶嗶聲。
- 每個檔的峰值統一正規化到 PEAK × 該音效的 gain（留 headroom），頭尾各加幾毫秒淡入淡出，避免爆音。
- 變體（例如 step-1..3）由 Sfx 那邊輪播，這裡只負責把三個檔都產出來。
"""

import math
import os
import random
import struct
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'Assets', 'Resources', 'audio')

SR = 22050          # 取樣率
PEAK = 0.80         # 正規化後的峰值（再乘各音效的 gain）—— 留 headroom，多個音效疊在一起才不會破
FADE_IN = 0.002     # 頭：2ms 淡入
FADE_OUT = 0.008    # 尾：8ms 淡出

TAU = 2.0 * math.pi


# ──────────────── 音名 → 頻率 ────────────────

_NAMES = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6,
          'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}


def note(name):
    """'C5' → 523.25 Hz（A4 = 440）。"""
    pitch, octave = name[:-1], int(name[-1])
    semis = _NAMES[pitch] + (octave - 4) * 12 - 9
    return 440.0 * (2.0 ** (semis / 12.0))


# ──────────────── 基本合成 ────────────────

def envelope(n, a, d, s, r):
    """ADSR 包絡（單位：秒；s 是持續音量 0..1）。總長 n 個取樣，r 從尾端倒算。"""
    ai, di, ri = int(a * SR), int(d * SR), int(r * SR)
    out = []
    for i in range(n):
        if i < ai:
            v = i / max(1, ai)
        elif i < ai + di:
            v = 1.0 - (1.0 - s) * (i - ai) / max(1, di)
        else:
            v = s
        if i >= n - ri:
            v *= max(0.0, (n - i) / max(1, ri))
        out.append(v)
    return out


def tone(dur, f0, f1=None, wave_='square', duty=0.5, a=0.004, d=0.05, s=0.6, r=0.04,
         vol=1.0, vib_rate=0.0, vib_depth=0.0, rng=None):
    """
    一個音：頻率從 f0 指數滑到 f1（None＝不滑），套 ADSR。
    wave_：square（可調 duty）/ triangle / sine / noise（取樣保持式的 8-bit 雜訊，f 決定顆粒）。
    vib_rate/vib_depth：顫音（Hz / 半音）。
    """
    n = max(1, int(dur * SR))
    env = envelope(n, a, d, s, r)
    f1 = f0 if f1 is None else f1
    rng = rng or random.Random(0)
    out = []
    phase = 0.0
    held = 0.0
    for i in range(n):
        t = i / n
        f = f0 * ((f1 / f0) ** t)
        if vib_depth:
            f *= 2.0 ** (vib_depth * math.sin(TAU * vib_rate * i / SR) / 12.0)
        prev = phase
        phase = (phase + f / SR) % 1.0
        if wave_ == 'square':
            v = 1.0 if phase < duty else -1.0
        elif wave_ == 'triangle':
            v = 4.0 * abs(phase - 0.5) - 1.0
        elif wave_ == 'sine':
            v = math.sin(TAU * phase)
        else:   # noise：每過一個週期換一個亂數值（像紅白機的雜訊聲道）
            if phase < prev:
                held = rng.uniform(-1.0, 1.0)
            v = held
        out.append(v * env[i] * vol)
    return out


def silence(dur):
    return [0.0] * int(dur * SR)


def mix(*parts):
    """疊音軌：parts 是 (開始秒數, 取樣陣列)。長度取最長的那段。"""
    total = 0
    for start, buf in parts:
        total = max(total, int(start * SR) + len(buf))
    out = [0.0] * total
    for start, buf in parts:
        o = int(start * SR)
        for i, v in enumerate(buf):
            out[o + i] += v
    return out


def seq(notes, step, gap=0.0, **kw):
    """依序排一串音（琶音／小旋律）。notes 裡放音名或 Hz；None 是休止。"""
    parts = []
    t = 0.0
    for nm in notes:
        if nm is not None:
            f = note(nm) if isinstance(nm, str) else nm
            parts.append((t, tone(step, f, **kw)))
        t += step + gap
    return mix(*parts) if parts else silence(t)


def lowpass(buf, cutoff):
    """一階低通：把方波的稜角磨圓（cozy 的關鍵）。"""
    k = 1.0 - math.exp(-TAU * cutoff / SR)
    y = 0.0
    out = []
    for v in buf:
        y += k * (v - y)
        out.append(y)
    return out


def tremolo(buf, rate, depth):
    """音量快速起伏（樹葉沙沙、冒泡用）。"""
    return [v * (1.0 - depth * 0.5 * (1.0 + math.sin(TAU * rate * i / SR))) for i, v in enumerate(buf)]


# ──────────────── 收尾：正規化＋淡入淡出＋寫檔 ────────────────

def finish(buf, gain):
    peak = max(1e-9, max(abs(v) for v in buf))
    k = PEAK * gain / peak
    out = [v * k for v in buf]
    n = len(out)
    fi, fo = int(FADE_IN * SR), int(FADE_OUT * SR)
    for i in range(min(fi, n)):
        out[i] *= i / fi
    for i in range(min(fo, n)):
        out[n - 1 - i] *= i / fo
    return out


def write_wav(path, buf):
    frames = b''.join(struct.pack('<h', max(-32767, min(32767, int(round(v * 32767))))) for v in buf)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(frames)


# ──────────────── 各個音效 ────────────────
# 每支函式拿到一個以檔名為種子的 rng，回傳 (取樣, gain)。
# gain 是相對音量：UI 與腳步這種高頻率的小聲、旋律類的大聲。


def make_step(rng, variant):
    """腳步：一小撮低通過的雜訊（鞋底）＋很輕的三角波悶響。三個變體音高、長度各差一點。"""
    base = (150, 132, 168)[variant]
    cut = (1500, 1250, 1750)[variant]
    dur = (0.050, 0.058, 0.046)[variant]
    scuff = tone(dur, 1800 + 400 * variant, wave_='noise', a=0.002, d=dur * 0.6, s=0.15, r=0.01, rng=rng)
    thump = tone(dur, base, base * 0.6, wave_='triangle', a=0.002, d=dur * 0.5, s=0.2, r=0.01, vol=0.8)
    return lowpass(mix((0, scuff), (0, thump)), cut), 0.32


def make_gather(rng):
    """採集搖樹：樹葉沙沙（雜訊＋快速起伏）＋一聲木頭輕響。"""
    rustle = tone(0.24, 3200, 2200, wave_='noise', a=0.01, d=0.12, s=0.35, r=0.08, rng=rng)
    rustle = tremolo(lowpass(rustle, 2600), 26, 0.7)
    knock = tone(0.06, 260, 180, wave_='triangle', a=0.002, d=0.04, s=0.2, r=0.02, vol=0.7)
    return mix((0, rustle), (0.0, knock)), 0.55


def make_pickup(rng):
    """得到物品：兩個往上跳的小音（叮咚↑）。"""
    a = tone(0.055, note('E6'), wave_='square', duty=0.25, a=0.002, d=0.03, s=0.6, r=0.02)
    b = tone(0.14, note('B6'), wave_='square', duty=0.25, a=0.002, d=0.06, s=0.45, r=0.07)
    return lowpass(mix((0, a), (0.055, b)), 4200), 0.48


def make_cast(rng):
    """施法：往上滑的三角波（帶顫音）＋尾巴兩顆閃亮的小琶音。"""
    sweep = tone(0.20, 330, 1180, wave_='triangle', a=0.005, d=0.1, s=0.7, r=0.05,
                 vib_rate=18, vib_depth=0.4)
    shimmer = seq(['E6', 'G#6', 'B6'], 0.04, wave_='square', duty=0.125, a=0.002, d=0.03, s=0.4, r=0.015, vol=0.35)
    return lowpass(mix((0, sweep), (0.14, shimmer)), 3800), 0.50


def make_spell_hit(rng):
    """魔法彈消失：一小團「噗」（雜訊）＋往下掉的三角波。"""
    puff = lowpass(tone(0.12, 2600, 900, wave_='noise', a=0.002, d=0.08, s=0.1, r=0.03, rng=rng), 2000)
    drop = tone(0.13, 880, 220, wave_='triangle', a=0.002, d=0.08, s=0.3, r=0.04, vol=0.8)
    return mix((0, puff), (0, drop)), 0.38


def make_water(rng):
    """澆水：低通的水流聲＋幾顆往上冒的小泡泡（bloop）。"""
    flow = tremolo(lowpass(tone(0.34, 4000, wave_='noise', a=0.03, d=0.1, s=0.5, r=0.12, rng=rng), 1400), 11, 0.5)
    parts = [(0, flow)]
    t = 0.02
    for _ in range(5):
        f = rng.uniform(380, 720)
        parts.append((t, tone(0.05, f, f * 1.9, wave_='sine', a=0.003, d=0.03, s=0.3, r=0.015, vol=0.55)))
        t += rng.uniform(0.045, 0.07)
    return mix(*parts), 0.50


def make_plant(rng):
    """種下：土「撲」一聲（低沉）＋一顆小小的芽冒出來的叮。"""
    soil = lowpass(tone(0.09, 900, wave_='noise', a=0.002, d=0.06, s=0.15, r=0.02, rng=rng), 900)
    thud = tone(0.10, 210, 110, wave_='triangle', a=0.002, d=0.06, s=0.25, r=0.03)
    sprout = tone(0.10, note('G5'), note('C6'), wave_='square', duty=0.25, a=0.003, d=0.05, s=0.4, r=0.04, vol=0.4)
    return lowpass(mix((0, soil), (0, thud), (0.09, sprout)), 3500), 0.52


def make_harvest(rng):
    """收成：開心的大三和弦往上琶（C E G C）。"""
    arp = seq(['C5', 'E5', 'G5', 'C6'], 0.055, wave_='square', duty=0.25, a=0.002, d=0.04, s=0.55, r=0.02)
    ring = tone(0.22, note('C6'), wave_='triangle', a=0.003, d=0.1, s=0.4, r=0.1, vol=0.6)
    return lowpass(mix((0, arp), (0.22, ring)), 4000), 0.55


def make_coin(rng):
    """收錢：經典的「叮—鈴」（B5 → E6），尾音長一點比較有「賺到了」的感覺。"""
    a = tone(0.06, note('B5'), wave_='square', duty=0.5, a=0.002, d=0.02, s=0.8, r=0.01)
    b = tone(0.28, note('E6'), wave_='square', duty=0.5, a=0.002, d=0.12, s=0.35, r=0.14)
    return lowpass(mix((0, a), (0.06, b)), 4500), 0.50


def make_buy(rng):
    """花錢：往下的兩個音＋收銀機那種一小撮「喀」。比 coin 低、短，聽得出是付出去。"""
    a = tone(0.05, note('E6'), wave_='square', duty=0.25, a=0.002, d=0.02, s=0.7, r=0.01)
    b = tone(0.13, note('A5'), wave_='square', duty=0.25, a=0.002, d=0.06, s=0.4, r=0.06)
    click = lowpass(tone(0.03, 5000, wave_='noise', a=0.001, d=0.02, s=0.1, r=0.008, rng=rng), 3000)
    return lowpass(mix((0, click), (0.01, a), (0.06, b)), 4200), 0.46


def make_upgrade(rng):
    """升級：快速往上的五音琶音＋最後閃一下。"""
    arp = seq(['C5', 'E5', 'G5', 'C6', 'E6'], 0.045, wave_='square', duty=0.25, a=0.002, d=0.03, s=0.6, r=0.015)
    top = tone(0.28, note('G6'), wave_='triangle', a=0.003, d=0.1, s=0.5, r=0.14, vib_rate=7, vib_depth=0.25, vol=0.6)
    return lowpass(mix((0, arp), (0.225, top)), 4200), 0.55


def make_deny(rng):
    """不行／錢不夠：兩個往下的低音「嗯—嗯」。圓潤的低通方波，提醒但不刺耳。"""
    a = tone(0.08, note('A3'), wave_='square', duty=0.5, a=0.003, d=0.03, s=0.7, r=0.02)
    b = tone(0.13, note('F3'), wave_='square', duty=0.5, a=0.003, d=0.05, s=0.6, r=0.06)
    return lowpass(mix((0, a), (0.095, b)), 1300), 0.44


def make_ui_open(rng):
    """面板打開：短短往上滑。"""
    s = tone(0.075, 520, 980, wave_='triangle', a=0.003, d=0.04, s=0.6, r=0.025)
    p = tone(0.04, note('A6'), wave_='square', duty=0.125, a=0.002, d=0.02, s=0.3, r=0.015, vol=0.3)
    return lowpass(mix((0, s), (0.05, p)), 3500), 0.38


def make_ui_close(rng):
    """面板關閉：短短往下滑（比打開輕一點）。"""
    s = tone(0.075, 900, 480, wave_='triangle', a=0.003, d=0.04, s=0.55, r=0.025)
    return lowpass(s, 3000), 0.32


def make_ui_click(rng):
    """一般按鈕：很短很輕的「得」。"""
    c = tone(0.028, 1250, 1100, wave_='square', duty=0.25, a=0.001, d=0.015, s=0.3, r=0.01)
    return lowpass(c, 3000), 0.28


def make_ui_tab(rng):
    """切分頁：兩個連續的小音（翻頁感）。"""
    t = seq([880, 1175], 0.03, wave_='triangle', a=0.002, d=0.015, s=0.5, r=0.01)
    return lowpass(t, 3500), 0.30


def make_page(rng):
    """翻書頁（調配藥水的配方書）：短促的紙張「唰」—— 往下滑的濾過雜訊、快速衰減，
    尾巴一下很輕的「啪」（紙落下）。比 ui-tab 安靜、沒有音高，連翻幾頁也不吵。"""
    swish = tone(0.13, 5200, 2400, wave_='noise', a=0.012, d=0.07, s=0.25, r=0.05, rng=rng)
    swish = lowpass(swish, 3200)
    flap = lowpass(tone(0.03, 1800, wave_='noise', a=0.001, d=0.02, s=0.1, r=0.008, rng=rng), 1400)
    return mix((0, swish), (0.11, flap)), 0.40


def make_talk(rng):
    """對話 blip：像動森那種很短的「哺」。音高的變化交給 Sfx 的隨機 pitch。"""
    b = tone(0.045, 620, 560, wave_='square', duty=0.5, a=0.003, d=0.02, s=0.5, r=0.015)
    return lowpass(b, 1800), 0.26


def make_door(rng):
    """換場景／進門：木門「喀」＋一陣柔和的風聲往下收。"""
    latch = tone(0.05, 300, 160, wave_='triangle', a=0.002, d=0.03, s=0.2, r=0.015)
    knock = lowpass(tone(0.03, 3000, wave_='noise', a=0.001, d=0.02, s=0.1, r=0.008, rng=rng), 2200)
    swish = tone(0.36, 2400, 700, wave_='noise', a=0.08, d=0.12, s=0.5, r=0.14, rng=rng)
    swish = lowpass(swish, 1100)
    return mix((0, knock), (0, latch), (0.04, swish)), 0.45


def make_brew(rng):
    """煉藥成功：咕嘟咕嘟的泡泡＋往上的魔法琶音＋閃亮的尾巴。"""
    parts = []
    t = 0.0
    for _ in range(6):
        f = rng.uniform(260, 520)
        parts.append((t, tone(0.05, f, f * 2.0, wave_='sine', a=0.003, d=0.03, s=0.3, r=0.015, vol=0.5)))
        t += rng.uniform(0.04, 0.06)
    arp = seq(['G4', 'B4', 'D5', 'G5', 'B5'], 0.06, wave_='square', duty=0.25, a=0.002, d=0.04, s=0.55, r=0.02)
    parts.append((0.20, arp))
    tail = tone(0.32, note('D6'), wave_='triangle', a=0.004, d=0.12, s=0.4, r=0.16, vib_rate=6, vib_depth=0.3, vol=0.55)
    parts.append((0.50, tail))
    return lowpass(mix(*parts), 3800), 0.58


def make_quest_done(rng):
    """任務完成：短短一句小旋律（主旋律方波＋三角波低八度和聲）。"""
    melody = [('C5', 0.10), ('E5', 0.10), ('G5', 0.10), ('C6', 0.20),
              (None, 0.04), ('A5', 0.10), ('C6', 0.36)]
    lead, bass = [], []
    t = 0.0
    for nm, d in melody:
        if nm:
            lead.append((t, tone(d, note(nm), wave_='square', duty=0.25, a=0.003, d=0.05, s=0.6, r=0.04)))
        t += d
    for nm, st, d in [('C4', 0.0, 0.30), ('G3', 0.30, 0.24), ('F3', 0.54, 0.14), ('C4', 0.68, 0.36)]:
        bass.append((st, tone(d, note(nm), wave_='triangle', a=0.004, d=0.06, s=0.7, r=0.05, vol=0.7)))
    return lowpass(mix(*lead, *bass), 4000), 0.60


def make_new_day(rng):
    """新的一天：慢一點、像晨光的五音小旋律（三角波主奏＋淡淡的方波回音）。"""
    melody = [('G4', 0.16), ('C5', 0.16), ('E5', 0.16), ('D5', 0.16), ('G5', 0.50)]
    parts = []
    t = 0.0
    for nm, d in melody:
        f = note(nm)
        parts.append((t, tone(d + 0.06, f, wave_='triangle', a=0.01, d=0.08, s=0.6, r=0.08,
                              vib_rate=5, vib_depth=0.15)))
        # 回音：晚 0.12 秒、小聲的細方波
        parts.append((t + 0.12, tone(d, f * 2, wave_='square', duty=0.125, a=0.005, d=0.05, s=0.3, r=0.06, vol=0.18)))
        t += d
    pad = tone(1.1, note('C4'), wave_='triangle', a=0.15, d=0.3, s=0.5, r=0.4, vol=0.45)
    parts.append((0.0, pad))
    return lowpass(mix(*parts), 3200), 0.55


def make_place(rng):
    """佈置模式放下家具：木頭「叩」一聲。"""
    knock = tone(0.08, 170, 95, wave_='triangle', a=0.002, d=0.05, s=0.2, r=0.025)
    tap = lowpass(tone(0.025, 3500, wave_='noise', a=0.001, d=0.015, s=0.1, r=0.008, rng=rng), 2400)
    return mix((0, tap), (0, knock)), 0.48


# ──────────────── 風鈴（門口招牌開店／關店，ShopSign.SetOpen 播）────────────────
# 風鈴＝幾根金屬管被風一碰、各自「叮」一聲然後慢慢消失。要的是**清亮、透明、尾巴長**，
# 不是電子嗶聲 —— 所以完全不用方波：正弦為主＋高八度（2×）泛音＋一點點金屬感的不協和泛音（2.76×，
# 管鐘／鐵琴第二泛音的比例），高的泛音消得比基音快（真的金屬就是這樣：一開始亮、尾巴變圓）。
# ⚠️ tone() 的 ADSR 是線性衰減，敲擊類聽起來像「被剪掉」；這裡另外乘一條指數衰減（ring 的 decay），
#    s 給 1、只靠指數收尾，r 只負責最後幾十毫秒歸零。

def ring(dur, f, decay, vol=1.0, rng=None):
    """
    一根風鈴管被碰一下：正弦基音 ＋ 2× 泛音（高八度）＋ 2.76× 金屬泛音，各自指數衰減。
    decay：基音音量掉到 1/e 的秒數；泛音依序 ×0.55、×0.3（高的先消）。
    rng 有給的話每根管子音準偏個 ±6 cents（風鈴本來就不是調得很準的樂器，太準反而像電子琴）。
    """
    if rng is not None:
        f *= 2.0 ** (rng.uniform(-6.0, 6.0) / 1200.0)
    out = None
    for ratio, amp, dk in ((1.0, 1.0, 1.0), (2.0, 0.42, 0.55), (2.76, 0.16, 0.30)):
        t = tone(dur, f * ratio, wave_='sine', a=0.0015, d=0.0, s=1.0, r=0.03, vol=amp * vol)
        tau = decay * dk
        t = [v * math.exp(-(i / SR) / tau) for i, v in enumerate(t)]
        out = t if out is None else [x + y for x, y in zip(out, t)]
    # 敲擊瞬間那一下「叮」的金屬顆粒：很短、很輕的高頻雜訊
    tick = lowpass(tone(0.012, 7000, wave_='noise', a=0.0005, d=0.008, s=0.1, r=0.003,
                        rng=rng or random.Random(0)), 5200)
    return mix((0, out), (0, [v * 0.10 * vol for v in tick]))


def make_chime_open(rng):
    """開店：四根管子由低往高被風一路碰過去（E6 G#6 B6 E7，亮的大三和弦），間隔與音量帶一點隨機錯位。"""
    parts = []
    t = 0.0
    for i, nm in enumerate(['E6', 'G#6', 'B6', 'E7']):
        vol = rng.uniform(0.75, 1.0) * (1.0 - 0.08 * i)       # 越高的越輕一點，不刺耳
        parts.append((t, ring(1.25, note(nm), rng.uniform(0.32, 0.42), vol, rng)))
        t += rng.uniform(0.065, 0.10)
    # 最後再輕輕回碰一下中間那根（風鈴不會規規矩矩只響一輪）
    parts.append((t + 0.05, ring(1.0, note('B6'), 0.30, 0.35, rng)))
    return lowpass(mix(*parts), 6500), 0.55


def make_chime_close(rng):
    """關店：同一組管子由高往低（E7 B6 G#6 E6），間隔慢一點、音量收小、低通多削一點 —— 像風停了。"""
    parts = []
    t = 0.0
    for i, nm in enumerate(['E7', 'B6', 'G#6', 'E6']):
        vol = rng.uniform(0.7, 0.9) * (0.8 + 0.07 * i)        # 越往下越穩，最後一聲最飽滿
        parts.append((t, ring(1.35, note(nm), rng.uniform(0.38, 0.48), vol, rng)))
        t += rng.uniform(0.10, 0.14)
    return lowpass(mix(*parts), 4200), 0.45


SOUNDS = {
    'step-1': lambda r: make_step(r, 0),
    'step-2': lambda r: make_step(r, 1),
    'step-3': lambda r: make_step(r, 2),
    'gather': make_gather,
    'pickup': make_pickup,
    'cast': make_cast,
    'spell-hit': make_spell_hit,
    'water': make_water,
    'plant': make_plant,
    'harvest': make_harvest,
    'coin': make_coin,
    'buy': make_buy,
    'upgrade': make_upgrade,
    'deny': make_deny,
    'ui-open': make_ui_open,
    'ui-close': make_ui_close,
    'ui-click': make_ui_click,
    'ui-tab': make_ui_tab,
    'page': make_page,
    'talk': make_talk,
    'door': make_door,
    'brew': make_brew,
    'quest-done': make_quest_done,
    'new-day': make_new_day,
    'place': make_place,
    'chime-open': make_chime_open,
    'chime-close': make_chime_close,
}


def main():
    """
    python tools/gen_sfx.py                          # 全部重產（覆蓋同名檔）
    python tools/gen_sfx.py chime-open chime-close   # 只產指定的名字（其他檔完全不碰）
    python tools/gen_sfx.py --out DIR                # 輸出到別的資料夾（驗證「重跑 md5 不變」用）
    """
    import sys
    args = sys.argv[1:]
    out_dir = OUT_DIR
    if '--out' in args:
        i = args.index('--out')
        out_dir = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    unknown = [a for a in args if a not in SOUNDS]
    if unknown:
        raise SystemExit(f'沒有這些音效：{unknown}（可用：{", ".join(SOUNDS)}）')
    names = args or list(SOUNDS)

    os.makedirs(out_dir, exist_ok=True)
    total = 0
    for name in names:
        fn = SOUNDS[name]
        rng = random.Random('witch-sfx:' + name)     # 以名字當種子：單獨改一個音效不會牽動其他檔
        buf, gain = fn(rng)
        buf = finish(buf, gain)
        path = os.path.join(out_dir, name + '.wav')
        write_wav(path, buf)
        size = os.path.getsize(path)
        total += size
        print(f'  {name:<11} {len(buf) / SR:5.2f}s  {size / 1024:6.1f} KB')
    print(f'共 {len(names)} 個，{total / 1024:.0f} KB → {out_dir}')


if __name__ == '__main__':
    main()
