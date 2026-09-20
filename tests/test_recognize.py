import numpy as np
import cv2

from xiangqi.board import STARTING_BOARD
from xiangqi.calibrate import extract_templates
from xiangqi.recognize import recognize_board

CELL = 50
MARGIN = 50


def make_synthetic_board(board, cell=CELL, margin=MARGIN):
    files, ranks = 9, 10
    W = (files - 1) * cell + 2 * margin
    H = (ranks - 1) * cell + 2 * margin
    img = np.full((H, W, 3), (150, 120, 80), np.uint8)  # 木色背景
    for f in range(files):
        x = margin + f * cell
        cv2.line(img, (x, margin), (x, margin + (ranks - 1) * cell), (60, 40, 20), 1)
    for r in range(ranks):
        y = margin + r * cell
        cv2.line(img, (margin, y), (margin + (files - 1) * cell, y), (60, 40, 20), 1)
    for r in range(ranks):
        for f in range(files):
            ch = board[r][f]
            if ch == " ":
                continue
            x = margin + f * cell
            y = margin + r * cell
            color = (40, 40, 200) if ch.isupper() else (30, 30, 30)
            cv2.circle(img, (x, y), int(cell * 0.4), color, -1)
            cv2.circle(img, (x, y), int(cell * 0.4), (0, 0, 0), 1)
            cv2.putText(img, ch, (x - 10, y + 10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (255, 255, 255), 2)
    return img


def test_recognize_starting_board():
    img = make_synthetic_board(STARTING_BOARD)
    templates = extract_templates(img, STARTING_BOARD, CELL, MARGIN)
    board, _ = recognize_board(img, templates, CELL, MARGIN)
    assert board == STARTING_BOARD
