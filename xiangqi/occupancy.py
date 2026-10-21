"""逐格「有没有棋子」的判定（皮肤无关）。

棋子是实心圆盘（中心亮），棋盘底色更深且随山水背景渐变——所以「有子」
就是「格中心比棋盘底色亮」。不写死亮度阈值：每帧对全盘 90 格做迭代
两类中点自适应分界，皮肤/配色换了也不用调参。

实测（当前皮肤，精修网格）：有子 202~237，空位 36~114，余量 +88，零误判。

这个判定被两处共用：
    * tracking：走子检测（哪格空了、哪格多了子）
    * recognize：先定「有没有子」，再让模板只负责「是哪颗子」
      ——模板匹配对网格偏移很敏感，空位容易被邻格棋子蹭出高分，
      用占空图做硬约束就不会无中生有。

反面教材：早先用「中心最暗 20% 像素」判「墨迹深=有子」，在深色棋盘上
完全反了（空位比白圆盘还暗），这正是真机走子检测死锁的根因。
"""

import cv2
import numpy as np

from .calibrate import FILES, RANKS

OCCUPANCY_FRAC = 0.28      # 采样区半径 = 0.28 * cell（避开格线与相邻棋子）
OCCUPANCY_TOL = 0.0        # 自适应阈值再向「有子」侧收紧的量（0 = 取两类中点）


def center_luminance(rect, cell, margin, r, f, frac=OCCUPANCY_FRAC):
    """格中心区域的中位亮度。

    用中位数而不是均值：棋盘格线正好穿过交叉点中心，线比底色/棋子都亮，
    均值会被线条拉高（实测某空位因此从 60 跳到 116），中位数不受影响。
    """
    k = max(3, int(cell * frac))
    x = margin + f * cell
    y = margin + r * cell
    patch = rect[int(y) - k : int(y) + k, int(x) - k : int(x) + k]
    if patch.size == 0:
        return 0.0
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    return float(np.median(gray))


def occupancy_threshold(values, tol=OCCUPANCY_TOL):
    """对全盘格中心亮度做「迭代两类中点」，得到有子/空位的自适应分界。

    Otsu 会被离群值拉偏（实测被一个背景偏亮的空位从 145 拉到 116），
    迭代取两类均值的中点更稳：只要有子/空位两簇存在，分界就落在谷底。
    全盘都空或都有子时两簇退化，函数会收敛到原值附近，不影响判断。
    """
    flat = np.asarray(values, dtype=np.float64).ravel()
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return 0.0
    t = float(np.median(flat))
    for _ in range(20):
        lo = flat[flat <= t]
        hi = flat[flat > t]
        if lo.size == 0 or hi.size == 0:
            break
        nt = (lo.mean() + hi.mean()) / 2.0
        if abs(nt - t) < 0.2:
            t = nt
            break
        t = nt
    return t + tol


def occupancy_map(rect, cell, margin):
    """整盘「每格是否真有棋子」的布尔表（屏幕坐标）。"""
    lum = np.empty((RANKS, FILES), dtype=np.float64)
    for r in range(RANKS):
        for f in range(FILES):
            lum[r, f] = center_luminance(rect, cell, margin, r, f)
    return lum > occupancy_threshold(lum)
