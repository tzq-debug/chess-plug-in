"""中国象棋棋盘表示与 FEN 转换。

内部表示：board[r][f]，r=rank(0=顶部黑方底线,9=底部红方底线)，f=file(0=左,8=右)。
空位用空格 " "。棋子字符：红方大写 K A B N R C P，黑方小写 k a b n r c p。
"""

from collections import Counter

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


def flip_board(board):
    """垂直翻转棋盘行。用于屏幕上红方在上时，转成标准 FEN（红方在下）。"""
    return list(reversed(board))


def side_to_move(fen):
    """返回 FEN 的走子方：'w' 或 'b'。"""
    parts = fen.split()
    return parts[1] if len(parts) > 1 else "w"


# 一副真棋里各类棋子的数量上限（帅/将各 1，其余各 2，兵/卒各 5）
MAX_PIECES = {"K": 1, "A": 2, "B": 2, "N": 2, "R": 2, "C": 2, "P": 5}

# 帅/士/象的合法落点（它们的活动范围是硬约束，越界一定是识别幻觉）。
# 兵/卒只受「不能后退」约束，单独在 sanitize_positions 里判。
_PALACE = {(r, f) for r in range(3) for f in range(3, 6)}
_A_SPOTS = {(0, 3), (0, 5), (1, 4), (2, 3), (2, 5)}
_B_SPOTS = {(0, 2), (0, 6), (2, 0), (2, 4), (2, 8), (4, 2), (4, 6)}
# strict=True：标准坐标（红方在下）。识别阶段还不知道屏幕朝向（手机可能
# 红方在上），只能用「红黑并集」，否则翻转前的红帅会被当成越界清掉——实测
# 这一个 bug 就把整副帅仕相抹平、9 个端到端测试全红。
LEGAL_SPOTS = {
    "k": _PALACE,
    "K": {(9 - r, f) for r, f in _PALACE},
    "a": _A_SPOTS,
    "A": {(9 - r, f) for r, f in _A_SPOTS},
    "b": _B_SPOTS,
    "B": {(9 - r, f) for r, f in _B_SPOTS},
}
LEGAL_SPOTS_ANY = {
    "k": _PALACE | {(9 - r, f) for r, f in _PALACE},
    "K": _PALACE | {(9 - r, f) for r, f in _PALACE},
    "a": _A_SPOTS | {(9 - r, f) for r, f in _A_SPOTS},
    "A": _A_SPOTS | {(9 - r, f) for r, f in _A_SPOTS},
    "b": _B_SPOTS | {(9 - r, f) for r, f in _B_SPOTS},
    "B": _B_SPOTS | {(9 - r, f) for r, f in _B_SPOTS},
}


def sanitize_positions(board, strict=False):
    """清掉落在非法位置的棋子，返回 (清理后的棋盘, [(字符, r, f), ...])。

    真机上「上一步落点」会留一个白色小光点（十字星标），亮度够高就能骗过
    占空图，模板又会把它匹配成字形最接近的棋子——实测 (0,4) 的空位被读成
    黑「士」，白得一个士让后续 FEN 直接非法。帅/士/象的活动范围是象棋的硬
    规则（士只走九宫对角、象不过河），落在范围外的一定是幻觉。

    strict=False 用「红黑位点并集」，与屏幕朝向无关（识别阶段用）；
    strict=True 用标准坐标（红方在下），并要求兵/卒不后退（主循环翻正后用）。
    """
    rows = [list(row) for row in board]
    removed = []
    table = LEGAL_SPOTS if strict else LEGAL_SPOTS_ANY
    for r in range(RANK_COUNT):
        for f in range(FILE_COUNT):
            ch = rows[r][f]
            if ch == " ":
                continue
            spots = table.get(ch)
            ok = True if spots is None else (r, f) in spots
            if strict:
                if ch == "p":
                    ok = r >= 3
                elif ch == "P":
                    ok = r <= 6
            if not ok:
                removed.append((ch, r, f))
                rows[r][f] = " "
    return ["".join(row) for row in rows], removed


def board_diff(tracked, recognized):
    """逐格比较两个盘面，返回 [(r, f, 追踪内容, 重识别内容), ...]。"""
    return [
        (r, f, tracked[r][f], recognized[r][f])
        for r in range(RANK_COUNT)
        for f in range(FILE_COUNT)
        if tracked[r][f] != recognized[r][f]
    ]


def material(board):
    """各类棋子数量（空格不计）。"""
    return Counter(ch for row in board for ch in row if ch != " ")


def material_jump(old_board, new_board, max_loss=1):
    """两个盘面的子力数量是否「跳变」了，返回不合理之处（空列表 = 合理）。

    一步棋最多吃掉对方一个子，所以任一方棋子只可能「不变或减少 1」，
    绝不可能凭空变多，也不会一步少两个。真机实测过两种翻车：
    重同步把红方两辆车一起读丢（16 秒内 -2），引擎随即在「无车」的假盘面上
    把一盘绝杀算成 -641；以及落点光点让某一格多出一个「士」。
    两头都要拦：多出棋子、一次少超过 1 个，都说明这盘面不能信。
    """
    old, new = material(old_board), material(new_board)
    reasons = []
    for ch in set(old) | set(new):
        delta = new[ch] - old[ch]
        name = PIECE_NAMES.get(ch, ch)
        if delta > 0:
            reasons.append(f"{name}多出 {delta} 个")
        elif delta < -max_loss:
            reasons.append(f"{name}一次少了 {-delta} 个")
    return reasons


def is_new_game_restart(old_board, new_board, opening_min=28):
    """盘面棋子「变多」且达到开局规模 → 用户打完一局又开了一局。

    这种跳变在子力校验看来是「凭空多出几个子」，会被一直拒绝采纳：程序卡在
    旧局的基准上，新局一步都看不懂、永远不给建议（真机实测：打完一局再开
    一局就哑了）。判据不能只看「旧盘是不是残局」——实测那局结束时还剩 26 子，
    比 20 子阈值高，于是没被识别成新局，白等了三轮重试。**正常对局子力只会
    减少（吃子），任何变多都只能是盘面重置**，所以直接比数量最可靠。
    """
    old_n = sum(1 for row in old_board for ch in row if ch != " ")
    new_n = sum(1 for row in new_board for ch in row if ch != " ")
    return new_n >= opening_min and new_n > old_n


def board_problems(board):
    """检查棋盘「像不像一副真棋」，返回问题列表（空列表 = 通过）。

    用于识别结果的 sanity 检查。用棋子清点而不是「和开局局面比对匹配数」：
    中局每走一步就会少 1~2 格匹配，开局匹配数既分不出「正常中局」也分不出
    「识别错乱」（实测真机中局 69/90 完全正确，却被判为可疑）。棋子数量是
    硬约束——多出一个车、少一个帅，一定是识别错了。
    """
    flat = "".join(board)
    if len(flat) != RANK_COUNT * FILE_COUNT:
        return [f"格子数不对（{len(flat)} 格）"]
    legal = set(" KABNCRPkabncrp")
    bad = sorted({ch for ch in flat if ch not in legal})
    if bad:
        return [f"含非法字符 {''.join(bad)!r}"]
    problems = []
    for ch, cap in MAX_PIECES.items():
        for c in (ch, ch.lower()):
            n = flat.count(c)
            if ch == "K":
                if n != cap:
                    problems.append(f"{PIECE_NAMES[c]} {n} 个（应为 {cap}）")
            elif n > cap:
                problems.append(f"{PIECE_NAMES[c]} {n} 个（上限 {cap}）")
    return problems

