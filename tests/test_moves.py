from xiangqi.board import STARTING_BOARD, fen_to_board
from xiangqi.moves import (
    apply_move,
    find_king,
    generate_pseudo_moves,
    is_in_check,
    is_legal,
    kings_facing,
)


def _board(fen):
    return fen_to_board(fen)


def test_opening_move_count():
    # 初始局面双方各 44 步（象棋公认值），可发现马腿/炮架等规则错误
    assert len(generate_pseudo_moves(STARTING_BOARD, "w")) == 44
    assert len(generate_pseudo_moves(STARTING_BOARD, "b")) == 44


def test_rook_blocked_by_pawn():
    # 车(9,0)向上被兵(6,0)挡住，只能到 (8,0)、(7,0)
    moves = [m for m in generate_pseudo_moves(STARTING_BOARD, "w") if m[0] == (9, 0)]
    assert sorted(m[1] for m in moves) == [(7, 0), (8, 0)]


def test_horse_leg_blocked():
    # 马(9,1)想去 (8,3) 被象(9,2)别住马腿，非法
    assert not is_legal(STARTING_BOARD, "w", ((9, 1), (8, 3)))
    assert is_legal(STARTING_BOARD, "w", ((9, 1), (7, 2)))


def test_cannon_needs_screen_to_capture():
    # 初始局面中路 f=1 上，(3,1)~(6,1) 全空（兵在偶数路）→ 炮(7,1)没有炮架，吃不到(2,1)
    assert not is_legal(STARTING_BOARD, "w", ((7, 1), (2, 1)))
    # 炮不能借炮架跳到空位（目标必须有子）
    assert not is_legal(STARTING_BOARD, "w", ((7, 1), (1, 1)))
    # 炮平五：(7,1)→(7,4) 路径无子、目标是空位 → 合法
    assert is_legal(STARTING_BOARD, "w", ((7, 1), (7, 4)))
    # 恰好一个炮架 → 可吃；没有炮架 → 不能吃
    with_screen = _board("3k5/9/2n6/9/9/2P6/9/2C6/9/4K4")
    assert is_legal(with_screen, "w", ((7, 2), (2, 2)))
    no_screen = _board("3k5/9/2n6/9/9/9/9/2C6/9/4K4")
    assert not is_legal(no_screen, "w", ((7, 2), (2, 2)))


def test_pawn_cannot_move_backward_or_sideways_before_river():
    assert is_legal(STARTING_BOARD, "w", ((6, 2), (5, 2)))      # 兵七进一
    assert not is_legal(STARTING_BOARD, "w", ((6, 2), (7, 2)))  # 后退
    assert not is_legal(STARTING_BOARD, "w", ((6, 2), (6, 3)))  # 未过河横走


def test_pawn_sideways_after_crossing_river():
    # 红兵已推进到 (3,2)（过了河）
    board = _board("rnbakabnr/9/1c5c1/p1P1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1")
    assert is_legal(board, "w", ((3, 2), (3, 3)))      # 过河可横走
    assert not is_legal(board, "w", ((3, 2), (4, 2)))  # 仍不能后退


def test_elephant_stays_own_side_and_needs_clear_midpoint():
    assert is_legal(STARTING_BOARD, "w", ((9, 2), (7, 4)))
    assert not is_legal(STARTING_BOARD, "w", ((9, 2), (5, 6)))  # 过河
    # 相(9,2)→(7,0) 的田心是 (8,1)，被自己的马占住 → 非法
    board = _board("rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/1N7/R1BAKABNR w - - 0 1")
    assert not is_legal(board, "w", ((9, 2), (7, 0)))


def test_king_and_advisor_confined_to_palace():
    assert is_legal(STARTING_BOARD, "w", ((9, 4), (8, 4)))
    assert not is_legal(STARTING_BOARD, "w", ((9, 4), (7, 4)))  # 帅不能走两格
    assert is_legal(STARTING_BOARD, "w", ((9, 3), (8, 4)))
    assert not is_legal(STARTING_BOARD, "w", ((9, 3), (8, 5)))  # 仕不能斜出九宫


def test_cannot_capture_own_piece():
    assert not is_legal(STARTING_BOARD, "w", ((7, 1), (7, 7)))  # 炮打自己另一门炮
    assert not is_legal(STARTING_BOARD, "w", ((9, 0), (9, 1)))  # 车吃自己的马


def test_kings_facing_is_illegal():
    # 帅(9,4)与将(0,4)同列，中间有红炮(7,4)挡着 → 不照面
    board = _board("4k4/9/9/9/9/9/9/4C4/9/4K4 w - - 0 1")
    assert not kings_facing(board)
    # 炮移开中路 → 将帅照面，非法
    assert not is_legal(board, "w", ((7, 4), (7, 3)))
    # 中路无子的盘面直接照面
    face = _board("4k4/9/9/9/9/9/9/9/9/4K4 w - - 0 1")
    assert kings_facing(face)


def test_cannot_leave_king_in_check():
    # 黑车(9,5) 沿底线将军红帅(9,3)
    board = _board("4k4/9/4c4/9/9/9/9/4C4/9/3K1r3 w - - 0 1")
    assert is_in_check(board, "w")
    # 帅往将线上躲（仍在车攻击线上）→ 非法
    assert not is_legal(board, "w", ((9, 3), (9, 4)))
    # 帅平移躲开 → 合法
    assert is_legal(board, "w", ((9, 3), (8, 3)))
    # 炮(7,4)→(9,4) 垫将 → 合法
    assert is_legal(board, "w", ((7, 4), (9, 4)))
    # 不应将的走法 → 非法
    assert not is_legal(board, "w", ((7, 4), (7, 5)))


def test_apply_move_and_find_king():
    board = apply_move(STARTING_BOARD, ((7, 1), (7, 4)))
    assert board[7][1] == " " and board[7][4] == "C"
    assert find_king(board, "w") == (9, 4)
    assert find_king(board, "b") == (0, 4)
    assert STARTING_BOARD[7][1] == "C"  # 原盘面不被修改
