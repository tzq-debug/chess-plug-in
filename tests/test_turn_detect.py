import numpy as np
from xiangqi.turn_detect import region_diff, active_side, to_fen_side


def _img(value):
    return np.full((100, 100, 3), value, np.uint8)


def test_region_diff_zero_and_changed():
    a = _img(100)
    assert region_diff(a, a, (0, 0, 50, 50)) == 0.0
    b = _img(100)
    b[0:50, 0:50] = 200
    assert region_diff(a, b, (0, 0, 50, 50)) > 50.0


def test_active_side():
    assert active_side(10.0, 1.0) == "self"
    assert active_side(1.0, 10.0) == "opponent"
    assert active_side(1.0, 1.0) is None
    assert active_side(10.0, 10.0) is None


def test_to_fen_side():
    assert to_fen_side("self", "red") == "w"
    assert to_fen_side("opponent", "red") == "b"
    assert to_fen_side("self", "black") == "b"
    assert to_fen_side("opponent", "black") == "w"
    assert to_fen_side(None, "red") is None
