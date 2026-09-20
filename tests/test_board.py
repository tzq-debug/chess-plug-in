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
