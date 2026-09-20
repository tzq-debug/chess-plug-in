"""中国象棋棋盘表示与 FEN 转换。

内部表示：board[r][f]，r=rank(0=顶部黑方底线,9=底部红方底线)，f=file(0=左,8=右)。
空位用空格 " "。棋子字符：红方大写 K A B N R C P，黑方小写 k a b n r c p。
"""

RANK_COUNT = 10
FILE_COUNT = 9

STARTING_BOARD = [
    "rnbakabnr",
    "         ",
    " c     c ",
    "p p p p p",
    "         ",
    "         ",
    "P P P P P",
    " C     C ",
    "         ",
    "RNBAKABNR",
]

PIECE_NAMES = {
    "K": "帅", "A": "仕", "B": "相", "N": "马", "R": "车", "C": "炮", "P": "兵",
    "k": "将", "a": "士", "b": "象", "n": "马", "r": "车", "c": "炮", "p": "卒",
}


def board_to_fen(board, side="w"):
    """把 10 行字符串棋盘转成 FEN。side: 'w' 红方走，'b' 黑方走。"""
    rows = []
    for rank in board:
        if len(rank) != FILE_COUNT:
            raise ValueError(f"每行必须是 {FILE_COUNT} 列: {rank!r}")
        row = ""
        empty = 0
        for ch in rank:
            if ch == " ":
                empty += 1
            else:
                if empty:
                    row += str(empty)
                    empty = 0
                row += ch
        if empty:
            row += str(empty)
        rows.append(row)
    return "/".join(rows) + f" {side} - - 0 1"


def fen_to_board(fen):
    """解析 FEN 的棋子摆放部分，返回 10 行字符串棋盘。"""
    placement = fen.split()[0]
    rows = placement.split("/")
    if len(rows) != RANK_COUNT:
        raise ValueError(f"FEN 必须有 {RANK_COUNT} 行: {fen!r}")
    board = []
    for row in rows:
        out = ""
        for ch in row:
            if ch.isdigit():
                out += " " * int(ch)
            else:
                out += ch
        if len(out) != FILE_COUNT:
            raise ValueError(f"行解析后必须是 {FILE_COUNT} 列: {row!r}")
        board.append(out)
    return board


def side_to_move(fen):
    """返回 FEN 的走子方：'w' 或 'b'。"""
    parts = fen.split()
    return parts[1] if len(parts) > 1 else "w"
