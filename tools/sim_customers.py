# -*- coding: utf-8 -*-
"""
來客節奏離線模擬 —— 驗證 CustomerManager 11/26 改版後「每遊戲小時成交件數」跟舊版同一個量級。

    python tools/sim_customers.py

模擬的是 CustomerManager.Update 的排程邏輯（不是畫面）：
  舊版：每 I 秒檢查一次，店裡人數 < 上限就生一位，每位都買。
  新版：間隔 I × f（f = 0.35 + 1.4·u^1.5），25% 是 2～3 人結伴（錯開 0.6～1.8 / 0.6～2.5 秒進門），
        每位以 BuyChance 的機率要買；同時上限 ceil(舊上限×1.5)+2，滿了就在門外等（不丟掉）。

停留時間用估的（離線看不到真的路徑）：
  走一趟（門 ↔ 商品）150～320px ÷ 120px/s，BFS 繞路再 ×1.15。
  舊版：走進 + 1.2 + 1.0 + 走出。
  新版買的人：走進 + 1.6（想要）+ 1.4（+金額）+ 0.6（道謝）+ 走出。
  新版只逛的人：走進 + 每樣 2.4～3.2 秒、兩樣之間再走 0.6～1.6 秒 + 55% 留一句話 0.8 秒 + 走出。

⚠️ 假設架上一直有貨（沒貨是「玩家沒補貨」，新舊版一樣都會空手而歸，不影響比較）。
⚠️ 改了 CustomerManager 的常數要跟著改這裡上面那幾個值。
"""

import math
import random

SEC_PER_GAME_HOUR = 43.8          # TimeSystem：10 遊戲分鐘 = 7.3 真實秒
WALK = 120.0

GAP_MIN, GAP_SPAN, GAP_POW = 0.35, 1.4, 1.5
MEAN_GAP = GAP_MIN + GAP_SPAN / (GAP_POW + 1)
GROUP_CHANCE, GROUP3_SHARE = 0.25, 0.35
MEAN_VISITORS = 1 + GROUP_CHANCE * (1 + GROUP3_SHARE)
BUY_CHANCE = MEAN_GAP / MEAN_VISITORS

INTERVAL_AT = [6, 5, 4, 3, 2.5]
MAX_AT = [2, 3, 3, 4, 5]
REP = [(0, 1.00), (0, 0.92), (1, 0.85), (1, 0.78), (2, 0.70)]   # (Extra, Scale)


def walk_time(rng):
    return rng.uniform(150, 320) * 1.15 / WALK


def stay_old(rng):
    return walk_time(rng) + 1.2 + 1.0 + walk_time(rng)


def stay_new(rng, buyer):
    t = walk_time(rng) + walk_time(rng)
    if buyer:
        return t + 1.6 + 1.4 + 0.6
    n = 2 if rng.random() < 0.5 else 1
    for k in range(n):
        t += rng.uniform(2.4, 3.2)
        if k > 0:
            t += rng.uniform(0.6, 1.6)
    if rng.random() < 0.55:
        t += 0.8
    return t


def sim_old(I, cap, hours, rng, dt=0.05):
    t, timer, sales, inside = 0.0, 0.0, 0, []
    end = hours * SEC_PER_GAME_HOUR
    while t < end:
        t += dt
        inside = [x for x in inside if x > t]
        timer += dt
        if timer >= I:
            timer = 0.0
            if len(inside) < cap:
                inside.append(t + stay_old(rng))
                sales += 1
    return sales


def sim_new(I, old_cap, hours, rng, dt=0.05):
    cap = math.ceil(old_cap * 1.5) + 2
    t, sales, visitors = 0.0, 0, 0
    inside, pending = [], []          # inside: 離開時刻；pending: 進門時刻
    timer = I * (GAP_MIN + GAP_SPAN * rng.random() ** GAP_POW)
    end = hours * SEC_PER_GAME_HOUR
    full_time, peak, conc_sum, n = 0.0, 0, 0.0, 0

    def enter():
        nonlocal sales, visitors
        buyer = rng.random() < BUY_CHANCE
        visitors += 1
        if buyer:
            sales += 1
        inside.append(t + stay_new(rng, buyer))

    while t < end:
        t += dt
        inside = [x for x in inside if x > t]
        still = []
        for p in pending:
            if p <= t:
                enter()
            else:
                still.append(p)
        pending = still

        if timer > 0:
            timer -= dt
        used = len(inside) + len(pending)
        if used >= cap:
            full_time += dt
        if timer <= 0 and used < cap:
            size = 1
            if rng.random() < GROUP_CHANCE:
                size = 3 if rng.random() < GROUP3_SHARE else 2
            size = min(size, cap - used)
            enter()
            d = 0.0
            for k in range(1, size):
                d += rng.uniform(0.6, 1.8) if k == 1 else rng.uniform(0.6, 2.5)
                pending.append(t + d)
            timer = I * (GAP_MIN + GAP_SPAN * rng.random() ** GAP_POW)

        peak = max(peak, len(inside))
        conc_sum += len(inside)
        n += 1
    return sales, visitors, full_time / end, peak, conc_sum / n, cap


def main():
    rng = random.Random(20261126)
    hours = 400          # 每個設定模擬 400 遊戲小時（≈ 33 個營業日）
    print("E[f] = %.4f  E[每組人數] = %.4f  BuyChance = %.4f  來客倍數 = %.3f"
          % (MEAN_GAP, MEAN_VISITORS, BUY_CHANCE, MEAN_VISITORS / MEAN_GAP))
    # 間隔分布
    fs = [GAP_MIN + GAP_SPAN * rng.random() ** GAP_POW for _ in range(200000)]
    print("間隔係數 f：<0.6 佔 %.1f%%，>1.4 佔 %.1f%%"
          % (100 * sum(f < 0.6 for f in fs) / len(fs), 100 * sum(f > 1.4 for f in fs) / len(fs)))
    print()
    print("%-26s %6s %8s %8s %8s %8s %7s %6s %6s %5s" %
          ("設定", "I(秒)", "理論/時", "舊/時", "新/時", "新/舊", "來客/時", "滿座%", "平均人", "峰值"))
    cases = [
        ("招牌0 名聲1", 0, 0, False),
        ("招牌0 名聲1 節日", 0, 0, True),
        ("招牌2 名聲3", 2, 2, False),
        ("招牌4 名聲5", 4, 4, False),
        ("招牌4 名聲5 節日（最快）", 4, 4, True),
    ]
    for name, lv, rp, fest in cases:
        I = INTERVAL_AT[lv] * REP[rp][1] * (0.6 if fest else 1.0)
        old_cap = MAX_AT[lv] + REP[rp][0] + (1 if fest else 0)
        theo = SEC_PER_GAME_HOUR / I
        so = sim_old(I, old_cap, hours, rng) / hours
        sn, vis, full, peak, avg, cap = sim_new(I, old_cap, hours, rng)
        sn /= hours
        print("%-26s %6.2f %8.2f %8.2f %8.2f %7.1f%% %7.2f %5.1f%% %6.2f %3d/%d" %
              (name, I, theo, so, sn, 100 * sn / so, vis / hours, 100 * full, avg, peak, cap))
    print()
    print("AwayShop（離店）＝ 0.7 / I，跟舊版在店的比例一樣是 70%；新版在店的比例見上面「新/舊」。")


if __name__ == "__main__":
    main()
