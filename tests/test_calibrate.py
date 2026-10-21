import numpy as np
from xiangqi.calibrate import grid_intersections


def test_grid_intersections_rectangle():
    # 完美矩形 90 宽 100 高；9 文件 10 行
    corners = np.array([[0, 0], [90, 0], [90, 100], [0, 100]], dtype=np.float32)
    grid = grid_intersections(corners)
    assert grid.shape == (10, 9, 2)
    np.testing.assert_allclose(grid[0][0], [0, 0], atol=1e-4)
    np.testing.assert_allclose(grid[0][8], [90, 0], atol=1e-4)
    np.testing.assert_allclose(grid[9][8], [90, 100], atol=1e-4)
    np.testing.assert_allclose(grid[9][0], [0, 100], atol=1e-4)
    np.testing.assert_allclose(grid[0][4], [45, 0], atol=1e-4)
    np.testing.assert_allclose(grid[4][0], [0, 100 * 4 / 9], atol=1e-3)


def test_grid_intersections_trapezoid():
    # 轻微透视：右上角略抬高
    corners = np.array([[0, 0], [90, 10], [90, 100], [0, 100]], dtype=np.float32)
    grid = grid_intersections(corners)
    np.testing.assert_allclose(grid[0][0], [0, 0], atol=1e-4)
    np.testing.assert_allclose(grid[0][8], [90, 10], atol=1e-4)


def test_save_load_templates_roundtrip(tmp_path):
    import cv2
    from xiangqi.calibrate import save_templates, load_templates

    templates = {"R": np.full((80, 80, 3), 200, np.uint8), "r": np.full((80, 80, 3), 50, np.uint8)}
    save_templates(templates, str(tmp_path))
    loaded = load_templates(str(tmp_path))
    assert set(loaded.keys()) == {"R", "r"}
    assert loaded["R"].shape == (80, 80, 3)
    assert loaded["r"].shape == (80, 80, 3)


def _rectified_with_colored_backranks(top_ink, bottom_ink, cell=50, margin=50):
    import cv2

    W = 8 * cell + 2 * margin
    H = 9 * cell + 2 * margin
    img = np.full((H, W, 3), (150, 150, 150), np.uint8)
    for f in range(9):
        cv2.circle(img, (margin + f * cell, margin), int(cell * 0.4), top_ink, -1)
        cv2.circle(img, (margin + f * cell, margin + 9 * cell), int(cell * 0.4), bottom_ink, -1)
    return img


# JJ象棋 主题实测：红方墨迹 R-G≈+87，黑方墨迹 R-G≈+7
RED_INK = (36, 36, 190)     # BGR → R-G ≈ +154
BLACK_INK = (40, 40, 46)    # BGR → R-G ≈ +6


def test_detect_flip_red_on_top():
    from xiangqi.calibrate import detect_flip

    img = _rectified_with_colored_backranks(RED_INK, BLACK_INK)
    assert detect_flip(img, 50, 50) is True


def test_detect_flip_red_on_bottom():
    from xiangqi.calibrate import detect_flip

    img = _rectified_with_colored_backranks(BLACK_INK, RED_INK)
    assert detect_flip(img, 50, 50) is False


# ---------------------------------------------------------------- 网格精修

def test_refine_rectify_recovers_from_oversized_corners():
    """用户标定的四角常落在棋盘外框（比交叉点网格大约半格），
    精修必须把它拉回真实网格，否则占/空判定完全失效。"""
    import synth
    from xiangqi.board import STARTING_BOARD, flip_board
    from xiangqi.calibrate import refine_rectify
    from xiangqi.tracking import _center_luminance, _occupancy_threshold

    screen = flip_board(STARTING_BOARD)          # 红方在上（用户真实情形）
    img = synth.render_board(screen)
    c = synth.canonical_corners()
    pad = 70                                      # 外扩半格
    outer = [
        [c[0][0] - pad, c[0][1] - pad],
        [c[1][0] + pad, c[1][1] - pad],
        [c[2][0] + pad, c[2][1] + pad],
        [c[3][0] - pad, c[3][1] + pad],
    ]

    rect, cell, margin, corners, fit = refine_rectify(img, outer)
    assert fit is not None, "网格精修失败"
    assert not np.allclose(corners, np.asarray(outer, dtype=np.float32)), "四角没有被修正"

    # 网格是否真的对齐，最终要落到「占空判定能不能完全分开」上
    lum = [
        [_center_luminance(rect, cell, margin, r, f) for f in range(9)]
        for r in range(10)
    ]
    thr = _occupancy_threshold([v for row in lum for v in row])
    occ = [lum[r][f] for r in range(10) for f in range(9) if screen[r][f] != " "]
    empty = [lum[r][f] for r in range(10) for f in range(9) if screen[r][f] == " "]
    assert min(occ) > thr, f"有子格被判成空位，网格仍偏移: {min(occ):.1f} <= {thr:.1f}"
    assert max(empty) < thr, f"空位被判成有子，网格仍偏移: {max(empty):.1f} >= {thr:.1f}"


def test_refine_rectify_falls_back_when_no_pieces():
    """画面里没有棋子（非对局画面）时精修应返回 fit=None 而不是抛异常。"""
    from xiangqi.calibrate import refine_rectify

    blank = np.full((700, 700, 3), 130, np.uint8)
    corners = [[100, 100], [600, 100], [600, 600], [100, 600]]
    rect, cell, margin, out_corners, fit = refine_rectify(blank, corners)
    assert fit is None
    assert rect.shape[0] > 0
    np.testing.assert_allclose(out_corners, np.asarray(corners, dtype=np.float32))


def test_scale_corners_same_size_is_identity():
    """尺寸一致时不动四角（避免浮点误差把坐标改坏）。"""
    from xiangqi.calibrate import scale_corners

    corners = [[10, 20], [110, 22], [112, 220], [8, 218]]
    assert scale_corners(corners, (1256, 2760), (1256, 2760)) == corners


def test_scale_corners_halves_on_downsample():
    """设备端降采样一半时，四角必须等比缩一半，否则矫正裁到棋盘外。"""
    from xiangqi.calibrate import scale_corners

    corners = [[38, 697], [1214, 693], [1228, 2036], [21, 2032]]
    out = scale_corners(corners, (1256, 2760), (628, 1380))
    assert out == [[19.0, 348.5], [607.0, 346.5], [614.0, 1018.0], [10.5, 1016.0]]


def test_scale_corners_without_ref_size_is_identity():
    """没配 screen_size（老配置）时不能瞎换算。"""
    from xiangqi.calibrate import scale_corners

    corners = [[38, 697], [1214, 693], [1228, 2036], [21, 2032]]
    assert scale_corners(corners, None, (628, 1380)) == corners
