import numpy as np
import cv2

from xiangqi.board import STARTING_BOARD
from xiangqi.calibrate_cli import make_config, templates_from_screenshot


def _synthetic_board_image(cell=50, margin=50):
    """画一张「已矫正」的初始局面图，棋子画在 (margin + f*cell, margin + r*cell)。"""
    W = 8 * cell + 2 * margin
    H = 9 * cell + 2 * margin
    img = np.full((H, W, 3), 255, np.uint8)
    for r in range(10):
        for f in range(9):
            if STARTING_BOARD[r][f] != " ":
                cv2.circle(img, (margin + f * cell, margin + r * cell), cell // 2 - 2, (0, 0, 0), -1)
    return img, W, H


def test_templates_from_screenshot_has_all_14_pieces():
    img, W, H = _synthetic_board_image()
    # 四角即矫正图自身边框 → 变换为恒等，棋子中心与裁剪中心重合
    corners = [[50, 50], [W - 50, 50], [W - 50, H - 50], [50, H - 50]]
    templates = templates_from_screenshot(img, corners)
    assert set(templates) == set("KABNRCPkabnrcp")
    assert len(templates) == 14


def test_make_config_preserves_keys_and_updates_calibration():
    base = {
        "hdc_path": "hdc",
        "engine_path": "engine/pikafish.exe",
        "templates_dir": "templates",
        "board_corners": [[0, 0]] * 4,
        "timer_regions": {"opponent": [0, 0, 0, 0], "self": [0, 0, 0, 0]},
    }
    corners = [[10, 20], [30, 40], [50, 60], [70, 80]]
    timer = {"opponent": [1, 2, 3, 4], "self": [5, 6, 7, 8]}
    out = make_config(base, corners, timer)
    assert out["hdc_path"] == "hdc"
    assert out["engine_path"] == "engine/pikafish.exe"
    assert out["board_corners"] == corners
    assert out["timer_regions"] == timer
