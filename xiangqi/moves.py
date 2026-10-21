"""中国象棋走法规则：伪合法走法生成与合法性校验。

坐标约定与 board.py 一致：board[r][f]，r=0 为顶部黑方底线，r=9 为底部红方底线，
f=0 为左侧。红方大写（走向 r 减小），黑方小写（走向 r 增大）。

「合法」= 符合该棋子的行棋规则 + 落点没有己方棋子 + 走完本方将/帅不被将军
（含「将帅照面」直接判负规则）。视觉追踪只接受合法走子，可防止把
JJ象棋 的高亮/走子提示等画面噪声收进可信盘面。
"""

RANKS = 10
FILES = 9

_ORTHO = ((-1, 0), (1, 0), (0, -1), (0, 1))
_DIAG = ((-1, -1), (-1, 1), (1, -1), (1, 1))
_HORSE = ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1))
_ELEPH = ((-2, -2), (-2, 2), (2, -2), (2, 2))


def side_of(piece):
    """棋子字符 → 所属方：'w' 红 / 'b' 黑。"""
    return "w" if piece.isupper() else "b"


def enemy_of(side):
    return "b" if side == "w" else "w"


def in_board(r, f):
    return 0 <= r < RANKS and 0 <= f < FILES


def in_palace(r, f, side):
    """是否在指定方的九宫内。"""
    if not 3 <= f <= 5:
        return False
    return 7 <= r <= 9 if side == "w" else 0 <= r <= 2


def crossed_river(r, side):
    """该格子的棋子是否已过河。红方过河 = rank <= 4，黑方 = rank >= 5。"""
    return r <= 4 if side == "w" else r >= 5


def find_king(board, side):
    king = "K" if side == "w" else "k"
    for r in range(RANKS):
        row = board[r]
        f = row.find(king)
        if f >= 0:
            return (r, f)
    return None


def _can_land(board, r, f, side):
    ch = board[r][f]
    return ch == " " or side_of(ch) != side


def generate_pseudo_moves(board, side):
    """生成 side 方所有「行棋规则合法」的走法（不检查自杀/将军）。

    返回 [((fr, ff), (tr, tf)), ...]，标准坐标。
    """
    out = []
    for r in range(RANKS):
        for f in range(FILES):
            ch = board[r][f]
            if ch == " " or side_of(ch) != side:
                continue
            kind = ch.upper()
            if kind == "K":  # 帅/将：九宫内一步直行
                for dr, df in _ORTHO:
                    nr, nf = r + dr, f + df
                    if in_palace(nr, nf, side) and _can_land(board, nr, nf, side):
                        out.append(((r, f), (nr, nf)))
            elif kind == "A":  # 仕/士：九宫内一步斜行
                for dr, df in _DIAG:
                    nr, nf = r + dr, f + df
                    if in_palace(nr, nf, side) and _can_land(board, nr, nf, side):
                        out.append(((r, f), (nr, nf)))
            elif kind == "B":  # 相/象：田字，不过河，田心不能有子
                for dr, df in _ELEPH:
                    nr, nf = r + dr, f + df
                    if not in_board(nr, nf):
                        continue
                    if crossed_river(nr, side):
                        continue
                    if board[r + dr // 2][f + df // 2] != " ":
                        continue
                    if _can_land(board, nr, nf, side):
                        out.append(((r, f), (nr, nf)))
            elif kind == "N":  # 马：日字，蹄下（马腿）不能有子
                for dr, df in _HORSE:
                    nr, nf = r + dr, f + df
                    if not in_board(nr, nf):
                        continue
                    # 马腿在「日」字长边的相邻格：(±2,±1) 看 (±1,0)，(±1,±2) 看 (0,±1)
                    if abs(dr) == 2:
                        leg = (r + dr // 2, f)
                    else:
                        leg = (r, f + df // 2)
                    if board[leg[0]][leg[1]] != " ":
                        continue
                    if _can_land(board, nr, nf, side):
                        out.append(((r, f), (nr, nf)))
            elif kind == "R":  # 车：直线，路径无子
                for dr, df in _ORTHO:
                    nr, nf = r + dr, f + df
                    while in_board(nr, nf):
                        cell = board[nr][nf]
                        if cell == " ":
                            out.append(((r, f), (nr, nf)))
                        else:
                            if side_of(cell) != side:
                                out.append(((r, f), (nr, nf)))
                            break
                        nr += dr
                        nf += df
            elif kind == "C":  # 炮：直线；不吃子时路径无子，吃子时中间恰隔一子
                for dr, df in _ORTHO:
                    nr, nf = r + dr, f + df
                    jumped = False
                    while in_board(nr, nf):
                        cell = board[nr][nf]
                        if not jumped:
                            if cell == " ":
                                out.append(((r, f), (nr, nf)))
                            else:
                                jumped = True
                        else:
                            if cell != " ":
                                if side_of(cell) != side:
                                    out.append(((r, f), (nr, nf)))
                                break
                        nr += dr
                        nf += df
            elif kind == "P":  # 兵/卒：向前一步；过河后可平移；永不后退
                dr = -1 if side == "w" else 1
                nr, nf = r + dr, f
                if in_board(nr, nf) and _can_land(board, nr, nf, side):
                    out.append(((r, f), (nr, nf)))
                if crossed_river(r, side):
                    for df in (-1, 1):
                        nr, nf = r, f + df
                        if in_board(nr, nf) and _can_land(board, nr, nf, side):
                            out.append(((r, f), (nr, nf)))
    return out


def apply_move(board, move):
    """返回走完一步后的新盘面（不改原盘面）。"""
    (sr, sf), (dr, df) = move
    rows = [list(row) for row in board]
    rows[sr][sf] = " "
    rows[dr][df] = board[sr][sf]
    return ["".join(row) for row in rows]


def kings_facing(board):
    """将帅是否照面（同列且中间无子）。照面貌似合法实则输棋，判为非法。"""
    wk = find_king(board, "w")
    bk = find_king(board, "b")
    if wk is None or bk is None or wk[1] != bk[1]:
        return False
    lo, hi = sorted((wk[0], bk[0]))
    for r in range(lo + 1, hi):
        if board[r][wk[1]] != " ":
            return False
    return True


def is_in_check(board, side):
    """side 方是否被将军（含将帅照面）。"""
    king = find_king(board, side)
    if king is None:
        return False
    if kings_facing(board):
        return True
    for _, dst in generate_pseudo_moves(board, enemy_of(side)):
        if dst == king:
            return True
    return False


def is_legal(board, side, move):
    """move = ((fr, ff), (tr, tf)) 是否为 side 方的合法走法。"""
    (sr, sf), (dr, df) = move
    if not (in_board(sr, sf) and in_board(dr, df)):
        return False
    piece = board[sr][sf]
    if piece == " " or side_of(piece) != side:
        return False
    if move not in generate_pseudo_moves(board, side):
        return False
    after = apply_move(board, move)
    if kings_facing(after) or is_in_check(after, side):
        return False
    return True
