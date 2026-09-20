import numpy as np
from xiangqi.display import draw_move


def test_draw_move_draws_arrow():
    img = np.zeros((200, 200, 3), np.uint8)
    corners = np.array([[0, 0], [180, 0], [180, 180], [0, 180]], dtype=np.float32)
    move = ((0, 0), (0, 8))  # 从左上角交叉点到右上角交叉点
    out = draw_move(img, corners, move)
    assert out.shape == img.shape
    # 起点与终点附近应出现绿色像素（0,255,0）
    assert (out[0, 0] == [0, 255, 0]).all()
    assert (out[0, 180] == [0, 255, 0]).all()
