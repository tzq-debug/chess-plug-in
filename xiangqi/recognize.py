"""矫正后的棋盘图 → 逐格识别 → 棋盘。"""

import cv2
import numpy as np

from .calibrate import FILES, RANKS

TEMPLATE_SIZE = 40
MATCH_THRESHOLD = 0.5


def classify_color(bgr):
    """根据棋子圆面平均色判断颜色。返回 'red' / 'black' / 'unknown'。"""
    b, g, r = bgr
    if r > 90 and r > g + 40 and r > b + 40:
        return "red"
    if r + g + b < 240:
        return "black"
    return "unknown"


def _color_dist(a, b):
    return float(np.linalg.norm(np.array(a, dtype=np.float32) - np.array(b, dtype=np.float32)))


def classify_cell(crop, templates, background):
    """识别单个交叉点的棋子。crop 为 BGR 图，background 为棋盘底色 BGR。"""
    h, w = crop.shape[:2]
    cx, cy = w // 2, h // 2
    mask = np.zeros((h, w), np.uint8)
    cv2.circle(mask, (cx, cy), int(h * 0.35), 255, -1)
    mean = cv2.mean(crop, mask=mask)[:3]  # BGR

    if _color_dist(mean, background) < 30:
        return " ", 1.0

    color = classify_color(mean)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (TEMPLATE_SIZE, TEMPLATE_SIZE))

    best, best_score = None, -1.0
    for ch, tmpl in templates.items():
        if (color == "red") != ch.isupper():
            continue  # 颜色不符，跳过
        res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
        score = float(res[0][0])
        if score > best_score:
            best_score, best = score, ch
    if best is None or best_score < MATCH_THRESHOLD:
        return "?", best_score
    return best, best_score


def recognize_board(rectified, templates, cell, margin):
    """识别整盘。返回 (board, confidences)。background 取四周留白均值。"""
    h, w = rectified.shape[:2]
    # 每条留白分别摊平成 (N, 1, 3) 的像素列再堆叠，这样 cv2.mean 才按 3 通道统计
    border = np.vstack(
        [
            rectified[0:margin, :].reshape(-1, 1, 3),
            rectified[h - margin : h, :].reshape(-1, 1, 3),
            rectified[:, 0:margin].reshape(-1, 1, 3),
            rectified[:, w - margin : w].reshape(-1, 1, 3),
        ]
    )
    background = tuple(float(v) for v in cv2.mean(border)[:3])

    board_rows, confidences = [], []
    half = cell // 2
    for r in range(RANKS):
        row = ""
        for f in range(FILES):
            x = margin + f * cell
            y = margin + r * cell
            crop = rectified[y - half : y + half, x - half : x + half]
            ch, conf = classify_cell(crop, templates, background)
            row += ch
            confidences.append(conf)
        board_rows.append(row)
    return board_rows, confidences
