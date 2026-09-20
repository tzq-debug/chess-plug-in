import numpy as np
import cv2

from xiangqi.main import OCCUPIED_DARKNESS, _candidate_cells, _ink_darkness


def _synthetic_board(piece_cells, ink=50, bg=155, cell=140, margin=140):
    """合成 9x10 矫正图：木色底 + 指定格放墨迹圆盘。"""
    W = 8 * cell + 2 * margin
    H = 9 * cell + 2 * margin
    img = np.full((H, W, 3), bg, np.uint8)
    for r, f in piece_cells:
        x = margin + f * cell
        y = margin + r * cell
        cv2.circle(img, (x, y), int(cell * 0.38), (ink,) * 3, -1)
    return img


def test_move_detected_as_source_and_dest():
    prev = _synthetic_board([(6, 2)])
    cur = _synthetic_board([(5, 2)])
    assert sorted(_candidate_cells(prev, cur, 140, 140)) == [(5, 2), (6, 2)]
    # 来源格(6,2)变空，落点格(5,2)变有子
    assert not (_ink_darkness(cur, 140, 140, 6, 2) < OCCUPIED_DARKNESS)
    assert _ink_darkness(cur, 140, 140, 5, 2) < OCCUPIED_DARKNESS


def test_highlight_still_occupied_not_a_move():
    # 棋子被高亮（墨迹 50 → 110，变亮但仍暗于木色）不应判成离格
    prev = _synthetic_board([(6, 2)], ink=50)
    cur = _synthetic_board([(6, 2)], ink=110)
    assert (6, 2) in _candidate_cells(prev, cur, 140, 140)
    assert _ink_darkness(cur, 140, 140, 6, 2) < OCCUPIED_DARKNESS  # 仍判有子
