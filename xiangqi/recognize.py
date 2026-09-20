"""矫正后的棋盘图 → 逐格识别 → 棋盘。"""

import cv2
import numpy as np

from .calibrate import FILES, RANKS

TEMPLATE_SIZE = 40
MATCH_THRESHOLD = 0.41   # 彩色模板匹配高于此分即为棋子
WARM_MIN_SCORE = 0.32    # 兵/炮等暖色圆面在暗角仍可接受的最低分
WARM_RGB_GAP = 0.0       # 圆心 R-G 高于此判定为暖色（兵/炮圆面偏红，棋盘偏绿/中性）


def classify_cell(crop, templates):
    """识别单个交叉点：返回 (字符, 置信度)。

    用彩色模板匹配（保留颜色），能区分暖色兵/炮与中性木色棋盘，
    避免灰度匹配把暗角空位误判成棋子。空位 = 匹配分低且圆心非暖色；
    低分但圆心暖色只可能是兵/炮这类低对比圆面。
    """
    h, w = crop.shape[:2]
    cx, cy = w // 2, h // 2
    mask = np.zeros((h, w), np.uint8)
    cv2.circle(mask, (cx, cy), int(h * 0.30), 255, -1)
    b, g, r = cv2.mean(crop, mask=mask)[:3]
    warm = (r - g) > WARM_RGB_GAP

    small = cv2.resize(crop, (TEMPLATE_SIZE, TEMPLATE_SIZE))
    best, best_score = None, -1.0
    for ch, tmpl in templates.items():
        res = cv2.matchTemplate(small, tmpl, cv2.TM_CCOEFF_NORMED)
        score = float(res[0][0])
        if score > best_score:
            best_score, best = score, ch
    if best is None:
        return "?", 0.0
    if best_score >= MATCH_THRESHOLD:
        return best, best_score
    if warm and best_score >= WARM_MIN_SCORE:
        return best, best_score
    return " ", best_score


def recognize_board(rectified, templates, cell, margin):
    """识别整盘。返回 (board, confidences)。"""
    board_rows, confidences = [], []
    half = cell // 2
    for r in range(RANKS):
        row = ""
        for f in range(FILES):
            x = margin + f * cell
            y = margin + r * cell
            crop = rectified[y - half : y + half, x - half : x + half]
            ch, conf = classify_cell(crop, templates)
            row += ch
            confidences.append(conf)
        board_rows.append(row)
    return board_rows, confidences
