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

    templates = {"R": np.full((40, 40, 3), 200, np.uint8), "r": np.full((40, 40, 3), 50, np.uint8)}
    save_templates(templates, str(tmp_path))
    loaded = load_templates(str(tmp_path))
    assert set(loaded.keys()) == {"R", "r"}
    assert loaded["R"].shape == (40, 40, 3)
    assert loaded["r"].shape == (40, 40, 3)


def _rectified_with_colored_backranks(top_bgr, bottom_bgr, cell=50, margin=50):
    import cv2

    W = 8 * cell + 2 * margin
    H = 9 * cell + 2 * margin
    img = np.full((H, W, 3), (150, 150, 150), np.uint8)
    for f in range(9):
        cv2.circle(img, (margin + f * cell, margin), int(cell * 0.4), top_bgr, -1)
        cv2.circle(img, (margin + f * cell, margin + 9 * cell), int(cell * 0.4), bottom_bgr, -1)
    return img


def test_detect_flip_red_on_top():
    from xiangqi.calibrate import detect_flip

    # 红方墨色偏绿(G>R)，黑方中性深色(R≈G)
    img = _rectified_with_colored_backranks((90, 150, 90), (70, 70, 70))
    assert detect_flip(img, 50, 50) is True


def test_detect_flip_red_on_bottom():
    from xiangqi.calibrate import detect_flip

    img = _rectified_with_colored_backranks((70, 70, 70), (90, 150, 90))
    assert detect_flip(img, 50, 50) is False
