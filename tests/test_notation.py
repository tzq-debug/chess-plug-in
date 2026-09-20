from xiangqi.board import STARTING_BOARD
from xiangqi.notation import pikafish_coord_to_internal, parse_move, move_to_chinese


def test_coord_convert():
    # Pikafish rank 自下而上：b7 = 内部 rank 2（= 9-7），file b = 1
    assert pikafish_coord_to_internal("b7") == (2, 1)
    assert pikafish_coord_to_internal("a0") == (9, 0)
    assert pikafish_coord_to_internal("i9") == (0, 8)


def test_parse_move():
    assert parse_move("b7c7") == ((2, 1), (2, 2))


def test_red_cannon_ping():
    # 炮二平五：红炮 file7 rank7 → file4 rank7
    assert move_to_chinese(STARTING_BOARD, 7, 7, 7, 4) == "炮二平五"


def test_red_horse_jin():
    # 马八进七：红马 file1 rank9 → file2 rank7
    assert move_to_chinese(STARTING_BOARD, 9, 1, 7, 2) == "马八进七"


def test_black_cannon_ping():
    # 黑炮 file7 rank2 → file4 rank2，黑方列号自左向右：file7=八，file4=五
    assert move_to_chinese(STARTING_BOARD, 2, 7, 2, 4) == "炮八平五"


def test_pawn_advance():
    # 红兵三进一：file6 rank6 → file6 rank5
    assert move_to_chinese(STARTING_BOARD, 6, 6, 5, 6) == "兵三进一"
