import numpy as np
from xiangqi.display import ARROW_HEAD_PX, draw_move


def test_draw_move_draws_arrow():
    img = np.zeros((200, 200, 3), np.uint8)
    corners = np.array([[0, 0], [180, 0], [180, 180], [0, 180]], dtype=np.float32)
    move = ((0, 0), (0, 8))  # 从左上角交叉点到右上角交叉点
    out = draw_move(img, corners, move)
    assert out.shape == img.shape
    # 起点与终点附近应出现绿色像素（0,255,0）
    assert (out[0, 0] == [0, 255, 0]).all()
    assert (out[0, 180] == [0, 255, 0]).all()


def test_长距离走法的箭头头部不会盖住邻子():
    """头部长度必须钉在像素上限：否则 9 格长的炮箭会画出 0.3*线长 的大头，
    横跨两列盖住相邻棋子（真机截图 628px 宽时实测头宽 ~113px）。"""
    img = np.zeros((400, 400, 3), np.uint8)
    corners = np.array([[10, 10], [390, 10], [390, 390], [10, 390]], dtype=np.float32)
    out = draw_move(img, corners, ((9, 4), (0, 4)))  # 竖贯全盘的长走法
    xs = np.nonzero(out[:, :, 1] > 150)[1]
    assert len(xs) > 0
    assert xs.max() - xs.min() <= 2 * ARROW_HEAD_PX + 4


def test_draw_void_压暗并画出作废标记():
    """盘面不稳时覆盖一张「作废」图，而不是删文件（删了预览面板会变空白）。"""
    import numpy as np

    from xiangqi.display import draw_void

    img = np.full((966, 440, 3), 200, np.uint8)
    out = draw_void(img)
    assert out.shape == img.shape and out.dtype == img.dtype
    assert out.mean() < img.mean(), "整图应压暗"
    assert (out[:, :, 2] > 150).sum() > 2000, "应出现红色叉与文字"
