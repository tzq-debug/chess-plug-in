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
