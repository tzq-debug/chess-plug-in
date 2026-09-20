"""矫正后的棋盘图 → 逐格识别 → 棋盘。"""

import cv2
import numpy as np

from .calibrate import FILES, RANKS

TEMPLATE_SIZE = 80
MATCH_THRESHOLD = 0.41   # 彩色模板匹配高于此分即为棋子
WARM_MIN_SCORE = 0.25    # 兵/炮等暖色圆面在暗角仍可接受的最低分
WARM_RGB_GAP = 0.0       # 圆心 R-G 高于此判定为暖色（兵/炮圆面偏红，棋盘偏绿/中性）
WARM_PIECES = {"P", "p", "C", "c"}  # 暖色规则只对兵/炮生效，避免暖色色带误判士相马车
OFFICERS = set("KABNkabn")          # 士相马车将帅：复杂字形，匹配分更高才可信
OFFICER_MIN_SCORE = 0.55            # 车炮兵卒圆面简单，沿用 MATCH_THRESHOLD


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
    # 只匹配棋子圆面（中心区域），忽略四周底色：圆盘不透明，
    # 落到河界/不同底色上圆面本身几乎不变，四周底色才会变。
    m = TEMPLATE_SIZE // 8
    disc = small[m:-m, m:-m]
    best, best_score = None, -1.0
    for ch, tmpl in templates.items():
        res = cv2.matchTemplate(disc, tmpl[m:-m, m:-m], cv2.TM_CCOEFF_NORMED)
        score = float(res[0][0])
        if score > best_score:
            best_score, best = score, ch
    if best is None:
        return "?", 0.0
    # 士相马车将帅字形复杂，模板匹配分可靠（实测 0.63~1.00），
    # 空位偶尔会以 0.45 左右误配成此类，故单独提高阈值；
    # 车炮兵卒圆面简单、匹配分散，沿用较低的 MATCH_THRESHOLD。
    threshold = OFFICER_MIN_SCORE if best in OFFICERS else MATCH_THRESHOLD
    if best_score >= threshold:
        return best, best_score
    if warm and best in WARM_PIECES and best_score >= WARM_MIN_SCORE:
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
