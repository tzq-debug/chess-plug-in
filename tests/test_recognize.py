import numpy as np
import cv2

from xiangqi.board import STARTING_BOARD
from xiangqi.calibrate import extract_templates
from xiangqi.recognize import recognize_board

CELL = 50
MARGIN = 50


def make_synthetic_board(board, cell=CELL, margin=MARGIN):
    """合成一张「深色棋盘 + 浅色圆盘」的图（与真机皮肤一致）。

    圆盘必须比棋盘亮——占空判定就是靠这一点（见 xiangqi/occupancy.py）。
    红黑棋子用字迹颜色区分：红方红字、黑方黑字。
    """
    files, ranks = 9, 10
    W = (files - 1) * cell + 2 * margin
    H = (ranks - 1) * cell + 2 * margin
    img = np.full((H, W, 3), (82, 84, 88), np.uint8)  # 深灰蓝棋盘
    for f in range(files):
        x = margin + f * cell
        cv2.line(img, (x, margin), (x, margin + (ranks - 1) * cell), (150, 150, 150), 1)
    for r in range(ranks):
        y = margin + r * cell
        cv2.line(img, (margin, y), (margin + (files - 1) * cell, y), (150, 150, 150), 1)
    for r in range(ranks):
        for f in range(files):
            ch = board[r][f]
            if ch == " ":
                continue
            x = margin + f * cell
            y = margin + r * cell
            cv2.circle(img, (x, y), int(cell * 0.4), (228, 232, 238), -1)
            cv2.circle(img, (x, y), int(cell * 0.4), (40, 40, 40), 1)
            ink = (30, 30, 210) if ch.isupper() else (25, 25, 25)
            cv2.putText(img, ch, (x - 10, y + 10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, ink, 2)
    return img


def test_recognize_starting_board():
    img = make_synthetic_board(STARTING_BOARD)
    templates = extract_templates(img, STARTING_BOARD, CELL, MARGIN)
    board, _ = recognize_board(img, templates, CELL, MARGIN)
    assert board == STARTING_BOARD


# ---------- 数量纠错（repair_counts）：落子高亮导致误认时的兜底 ----------

def _maps_from(board, base=0.95):
    """每格给自己字符一个高分，其它留 0，得到 score_maps。"""
    return [{board[r][f]: base} if board[r][f] != " " else {} for r in range(10) for f in range(9)]


def test_repair_counts_把高亮误认的黑车救回来():
    """真机实测：黑车被落子光晕洗白，灰度匹配把「象」认到 0.568、车只有 0.525。

    单格改判不了（试过模糊/边缘/局部亮度归一化都不行），但棋子数量是硬约束：
    黑象出现了 3 个 → 必有一个是错的。把「最没把握」的那格改成次选（车）。
    """
    from xiangqi.recognize import repair_counts

    board = [
        "  b ka   ", " r  a    ", "nc  b n  ", "p p p p p", "       b ",
        "  PN  P  ", "P   P   P", "C   B N  ", " R  A    ", "R   KAB  ",
    ]
    maps = _maps_from([row for row in board])
    maps[4 * 9 + 7] = {"b": 0.568, "r": 0.525}   # 误认的那一格：次选才是对的
    fixed = repair_counts(board, maps)
    assert fixed[4][7] == "r"
    assert sum(row.count("b") for row in fixed) == 2      # 象回到 2 个
    assert sum(row.count("r") for row in fixed) == 2      # 车补齐到 2 个


def test_repair_counts_不动有把握的格子():
    """首选分都很高时不改判：不能为了凑数量把真象（0.95）改掉。"""
    from xiangqi.recognize import repair_counts

    board = [
        "  b ka   ", " r  a    ", "nc  b n  ", "p p p p p", "       b ",
        "  PN  P  ", "P   P   P", "C   B N  ", " R  A    ", "R   KAB  ",
    ]
    maps = _maps_from(board)          # 全部 0.95
    assert repair_counts(board, maps) == board


def test_repair_counts_次选差太多时不动():
    """次选分比首选低 0.3 以上：宁可不改，留给调用方告警。"""
    from xiangqi.recognize import repair_counts

    board = [
        "  b ka   ", " r  a    ", "nc  b n  ", "p p p p p", "       b ",
        "  PN  P  ", "P   P   P", "C   B N  ", " R  A    ", "R   KAB  ",
    ]
    maps = _maps_from(board)
    maps[4 * 9 + 7] = {"b": 0.78, "r": 0.30}
    assert repair_counts(board, maps) == board


def test_repair_counts_不跨色改判():
    """红子多出来时不能靠改成黑子来凑数。"""
    from xiangqi.recognize import repair_counts

    board = [
        "  b ka   ", " r  a    ", "nc  b n  ", "p p p p p", "         ",
        "  PN  P  ", "P   P   P", "C   B N  ", " R  A    ", "R   KABB ",
    ]
    maps = _maps_from(board)
    maps[9 * 9 + 7] = {"B": 0.60, "b": 0.55}     # 次选是黑象，不能改
    assert repair_counts(board, maps)[9][7] == "B"


def test_recognize_tolerates_grid_offset():
    """网格偏几像素也要认对（真机每帧的圆盘拟合会抖 1~4 像素）。

    旧实现按格硬切、1:1 比对，偏 2 像素匹配分就从 0.95 掉到 0.55，
    整盘塌掉（真机第 13 回合把「将」认丢、把「车」认成 4 个）。
    """
    img = make_synthetic_board(STARTING_BOARD)
    templates = extract_templates(img, STARTING_BOARD, CELL, MARGIN)
    M = np.float32([[1, 0, 4], [0, 1, 3]])
    shifted = cv2.warpAffine(
        img, M, (img.shape[1] + 8, img.shape[0] + 8),
        borderValue=(82, 84, 88),
    )
    board, _ = recognize_board(shifted, templates, CELL, MARGIN)
    assert board == STARTING_BOARD


def test_recognize_does_not_invent_pieces_on_empty_cells():
    """空位不许被邻格棋子「蹭」出高分而凭空造子（占空图做硬约束）。"""
    board = [
        "  b ka   ", "    a    ", "nc  b n  ", "p N p p p", "       r ",
        "  P   P  ", "P   P   P", "C   B N  ", " R  A    ", "R   KAB  ",
    ]
    img = make_synthetic_board(board)
    templates = extract_templates(img, STARTING_BOARD, CELL, MARGIN)
    got, _ = recognize_board(img, templates, CELL, MARGIN)
    empty_truth = [(r, f) for r in range(10) for f in range(9) if board[r][f] == " "]
    invented = [(r, f, got[r][f]) for r, f in empty_truth if got[r][f] != " "]
    assert invented == []


def test_enforce_counts_清掉落点光点读出的第二个将():
    """真机：白点让 (1,4) 也被判成黑将，盘面出现 2 个将 → FEN 非法、算棋被跳过。"""
    from xiangqi.recognize import _enforce_counts

    board = ["    k    ", "    k    "] + [" " * 9] * 7 + ["    K    "]
    weight = {(0, 4): 0.93, (1, 4): 0.35, (9, 4): 0.95}
    out = _enforce_counts(board, lambda r, f: weight.get((r, f), 0.0))
    assert out[1] == "         ", "低分的假将应被清掉"
    assert out[0] == "    k    " and out[9] == "    K    ", "真将帅必须保留"


def test_enforce_counts_不动数量正常的局面():
    from xiangqi.board import STARTING_BOARD
    from xiangqi.recognize import _enforce_counts

    assert _enforce_counts(STARTING_BOARD, lambda r, f: 0.9) == STARTING_BOARD
