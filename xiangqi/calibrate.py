"""棋盘几何：四角 → 网格交叉点；以及棋子模板生成。"""

import cv2
import numpy as np

FILES = 9
RANKS = 10


def grid_intersections(corners, ranks=RANKS, files=FILES):
    """给定四角（左上、右上、右下、左下），返回 (ranks, files, 2) 交叉点坐标。

    在原图坐标里做双线性插值；[r][f] = (x, y)，r=0 为顶部，f=0 为左侧。
    """
    corners = np.asarray(corners, dtype=np.float32)
    tl, tr, br, bl = corners[0], corners[1], corners[2], corners[3]
    pts = []
    for r in range(ranks):
        t = r / (ranks - 1)
        left = (1 - t) * tl + t * bl
        right = (1 - t) * tr + t * br
        row = []
        for f in range(files):
            s = f / (files - 1)
            row.append((1 - s) * left + s * right)
        pts.append(row)
    return np.array(pts, dtype=np.float32)


def rectify(image, corners, cell=50):
    """把棋盘四角区域矫正成正面图。

    返回 (矫正图, cell, margin)。交叉点 (r, f) 在矫正图中位于
    (margin + f*cell, margin + r*cell)，四周留 margin 空白便于裁剪。
    """
    margin = cell
    W = (FILES - 1) * cell + 2 * margin
    H = (RANKS - 1) * cell + 2 * margin
    dst = np.array(
        [
            [margin, margin],
            [margin + (FILES - 1) * cell, margin],
            [margin + (FILES - 1) * cell, margin + (RANKS - 1) * cell],
            [margin, margin + (RANKS - 1) * cell],
        ],
        dtype=np.float32,
    )
    src = np.asarray(corners, dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    rectified = cv2.warpPerspective(image, M, (W, H))
    return rectified, cell, margin


def extract_templates(rectified, board, cell, margin, size=40):
    """从矫正后的初始局面图，按已知 board 提取每类棋子的模板。

    board: 10 行字符串（初始局面）。返回 {棋子字符: size x size 灰度图}。
    """
    templates = {}
    half = cell // 2
    for r in range(RANKS):
        for f in range(FILES):
            ch = board[r][f]
            if ch == " ":
                continue
            x = margin + f * cell
            y = margin + r * cell
            crop = rectified[y - half : y + half, x - half : x + half]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            templates[ch] = cv2.resize(gray, (size, size))
    return templates


def load_templates(templates_dir, size=40):
    """从目录加载棋子模板。返回 {棋子字符: size x size 灰度图}。

    模板文件名用棋子字符命名，如 R.png（红车）、c.png（黑炮）。
    """
    import os

    templates = {}
    for fname in os.listdir(templates_dir):
        if not fname.endswith(".png"):
            continue
        ch = os.path.splitext(fname)[0]
        img = cv2.imread(os.path.join(templates_dir, fname), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        templates[ch] = cv2.resize(img, (size, size))
    return templates
