"""Pikafish 坐标 ↔ 内部坐标转换，以及中文记谱。"""

from .board import PIECE_NAMES

CHINESE_DIGITS = "零一二三四五六七八九"


def pikafish_coord_to_internal(sq):
    """把 Pikafish 坐标 'b7' 转成内部 (rank, file)。

    Pikafish: file a–i（a=左），rank 0–9 自下而上（0=红方底线）。
    内部: rank 0=顶部（黑方），所以 rank 要翻转。
    """
    f = ord(sq[0]) - ord("a")
    r = 9 - int(sq[1])
    return (r, f)


def parse_move(move):
    """把 'b7c7' 转成 ((fr, ff), (tr, tf)) 内部坐标。"""
    if len(move) != 4:
        raise ValueError(f"非法走法: {move!r}")
    return pikafish_coord_to_internal(move[0:2]), pikafish_coord_to_internal(move[2:4])


def _col_num(color, f):
    """某文件在该方视角下的列号（1-9）。红方自右向左，黑方自左向右。"""
    return (9 - f) if color == "red" else (f + 1)


def _is_forward(color, fr, tr):
    """该方视角下 tr 是否在 fr 前方。红方前方=rank 减小，黑方前方=rank 增大。"""
    return (tr < fr) if color == "red" else (tr > fr)


def move_to_chinese(board, fr, ff, tr, tf):
    """把一步内部坐标走法转成中文记谱，如 '炮二平五'。

    board: 走子前的棋盘（10 行字符串）。坐标顺序为 (rank, file)。
    """
    piece = board[fr][ff]
    if piece == " ":
        raise ValueError(f"({fr},{ff}) 处无棋子")
    color = "red" if piece.isupper() else "black"
    kind = piece.upper()

    name = PIECE_NAMES[piece]
    from_col = _col_num(color, ff)

    # 同类同色同列的其它棋子（用于 前/后 消歧）
    same_file = [r for r in range(10) if r != fr and board[r][ff] == piece]

    if fr == tr:
        move_word = "平"
        num = _col_num(color, tf)
    else:
        move_word = "进" if _is_forward(color, fr, tr) else "退"
        if kind in ("N", "B", "A"):
            num = _col_num(color, tf)  # 马/相/象/仕/士 用落点列
        else:
            num = abs(tr - fr)  # 车/炮/兵/帅 用步数

    if same_file:
        front_rank = min(fr, *same_file) if color == "red" else max(fr, *same_file)
        prefix = "前" if fr == front_rank else "后"
    else:
        prefix = CHINESE_DIGITS[from_col]

    return f"{name}{prefix}{move_word}{CHINESE_DIGITS[num]}"
