from xiangqi.board import STARTING_BOARD, board_to_fen, fen_to_board, flip_board, side_to_move

START_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


def test_starting_board_to_fen():
    assert board_to_fen(STARTING_BOARD) == START_FEN


def test_fen_to_starting_board():
    assert fen_to_board(START_FEN) == STARTING_BOARD


def test_roundtrip():
    assert board_to_fen(fen_to_board(START_FEN)) == START_FEN


def test_side_to_move():
    assert side_to_move(START_FEN) == "w"
    assert side_to_move("9/9/9/9/9/9/9/9/9/9 b - - 0 1") == "b"


def test_empty_board_fen():
    empty = [" " * 9] * 10
    assert board_to_fen(empty) == "9/9/9/9/9/9/9/9/9/9 w - - 0 1"


def test_flip_board():
    flipped = flip_board(STARTING_BOARD)
    assert flipped == list(reversed(STARTING_BOARD))
    assert flip_board(flipped) == STARTING_BOARD


def test_board_problems_accepts_真实中局盘面():
    """真机中局（离开局 21 格不匹配）完全正确，不能判为可疑。"""
    from xiangqi.board import board_problems

    midgame = [
        "  baka cr", "       r ", "nc  b n  ", "p p p p p", "         ",
        "  P   P  ", "P   P   P", " CN B NC ", "        R", "R  AKAB  ",
    ]
    assert board_problems(midgame) == []


def test_board_problems_抓出棋子数量异常与非法字符():
    from xiangqi.board import STARTING_BOARD, board_problems

    assert board_problems(STARTING_BOARD) == []
    dup_king = ["KNBAKABNR"] + STARTING_BOARD[1:]          # 红方两个帅
    assert any("帅" in p for p in board_problems(dup_king))
    six_pawns = STARTING_BOARD[:6] + ["PPPPPP   "] + STARTING_BOARD[7:]
    assert any("兵" in p for p in board_problems(six_pawns))
    junk = ["?NBAKABNR"] + STARTING_BOARD[1:]
    assert any("非法字符" in p for p in board_problems(junk))


def test_sanitize_positions_清掉落点光点被读成的假士():
    """真机实测：上一步落点白点被读成黑「士」落在 (0,4)，让 FEN 非法。"""
    from xiangqi.board import sanitize_positions

    board = [
        "C.bRaa...",   # (0,4) 的 a 是白点幻觉，真士只在 (0,5)
        "..r.k....", "....b.n..", "....p...p", "......pr.",
        "P.P..NP..", "....P...P", "....B....", ".R..A....", "....KAB..",
    ]
    cleaned, removed = sanitize_positions(board)
    assert removed == [("a", 0, 4)]
    assert cleaned[0] == "C.bR a..."


def test_sanitize_positions_放过合法局面():
    from xiangqi.board import STARTING_BOARD, sanitize_positions

    cleaned, removed = sanitize_positions(STARTING_BOARD)
    assert removed == []
    assert cleaned == STARTING_BOARD


def test_sanitize_positions_兵不能后退():
    """红兵不会退回 r>6，黑卒不会跑到 r<3；越界即识别噪声。"""
    from xiangqi.board import sanitize_positions

    board = ["p" + " " * 8] + [" " * 9] * 8 + [" " * 8 + "P"]
    cleaned, removed = sanitize_positions(board, strict=True)
    assert sorted(removed) == [("P", 9, 8), ("p", 0, 0)]
    assert "".join(cleaned) == " " * 90


def test_sanitize_positions_帅不出九宫():
    from xiangqi.board import sanitize_positions

    board = [" " * 9] * 4 + ["K        "] + [" " * 9] * 5
    _, removed = sanitize_positions(board, strict=True)
    assert removed == [("K", 4, 0)]


def test_trust_guard_出问题后冻结若干帧再恢复():
    """真机教训：识别漂移时引擎会在假棋盘上给出「送车」的好评着法，必须闭嘴。"""
    from xiangqi.main import TrustGuard

    guard = TrustGuard(cooldown_frames=3)
    assert guard.ok, "初始应可信"
    assert guard.reason == ""

    guard.penalize("追踪失联")
    assert not guard.ok
    assert guard.reason == "追踪失联"

    for _ in range(2):
        guard.tick()
        assert not guard.ok, "冷却未到期前不能恢复"

    guard.tick()
    assert guard.ok, "冷却结束后应恢复"
    assert guard.reason == ""


def test_trust_guard_再次出错会重置冷却():
    from xiangqi.main import TrustGuard

    guard = TrustGuard(cooldown_frames=3)
    guard.penalize("盘面不自洽")
    guard.tick()
    guard.penalize("FEN 非法")     # 中途又坏：冷却重新开始
    guard.tick()
    guard.tick()
    assert not guard.ok
    guard.tick()
    assert guard.ok


def test_board_diff_标出追踪与重识别的差异格():
    """复核就靠它：少一个车在规则上合法，只有逐格比对才抓得到。"""
    from xiangqi.main import _board_diff

    tracked = [" " * 9] * 10
    recognized = [row for row in tracked]
    recognized[2] = " R       "
    recognized[9] = "    K    "
    diff = _board_diff(tracked, recognized)
    assert diff == [(2, 1, " ", "R"), (9, 4, " ", "K")]
    assert _board_diff(recognized, recognized) == []


def _pad(lines):
    return [line.ljust(9)[:9] for line in lines]


def test_material_jump_一步最多少一个子():
    """吃掉一个子合法；一次少两个、或凭空多子，都说明盘面不能信。"""
    from xiangqi.board import material_jump

    one_car = _pad(["r        "] + [" " * 9] * 9)
    no_car = _pad([" " * 9] * 10)
    assert material_jump(one_car, no_car) == [], "被吃一个车是正常走子"

    two_cars = _pad(["r        "] + [" " * 9] * 8 + ["r        "])
    assert material_jump(two_cars, no_car) == ["车一次少了 2 个"]

    fake_advisor = _pad(["    a    "] + [" " * 9] * 9)
    assert material_jump(no_car, fake_advisor) == ["士多出 1 个"]


def test_material_guard_连续三次一致才强制校准():
    """单帧跳变先守住；连着几次都这么认，才说明基准本身错了。"""
    from xiangqi.main import MaterialGuard

    guard = MaterialGuard(strikes=3)
    reasons = ["车一次少了 2 个"]
    assert guard.confirm(reasons) is False
    assert guard.confirm(reasons) is False
    assert guard.confirm(reasons) is True
    guard.clear()
    assert guard.confirm(reasons) is False, "clear 后重新计数"
