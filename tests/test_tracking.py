"""BoardTracker：画面差分追踪的鲁棒性测试（合成画面，无需真机）。

覆盖真实使用中会遇到的全部情形：
    * 单步走子 / 吃子 / 同一间隔内多步走子
    * JJ象棋 在来源格留下的半透明残影（旧实现在这里死循环）
    * 常驻高亮、走子提示点等「不是走子」的画面变化
    * 无法用合法走子解释的变化 → 有限帧内请求重同步（绝不卡死）
    * 红方在上（flip=True）时的坐标换算
"""

import synth
from xiangqi import tracking
from xiangqi.board import STARTING_BOARD
from xiangqi.tracking import BoardTracker, _center_luminance, _occupancy_threshold

CELL = 140
MARGIN = 140


def _img(screen_board, **kw):
    return synth.render_board(screen_board, cell=CELL, margin=MARGIN, **kw)


def _tracker(board=None, flip=False, side="w"):
    """建好追踪器并喂入基准帧，返回 (tracker, 屏幕坐标盘面)。"""
    board = [row[:] for row in (board or STARTING_BOARD)]
    t = BoardTracker(board, flip, CELL, MARGIN, side_to_move=side)
    screen = synth.std_to_screen(board, flip)
    assert t.update(_img(screen)).kind == "idle"
    return t, screen


def _feed(t, screen_board, frames=3, **kw):
    img = _img(screen_board, **kw)
    return [t.update(img) for _ in range(frames)]


def _moved(events):
    return [e for e in events if e.kind == "moved"]


# ---------------------------------------------------------------- 占/空判定

def test_occupancy_separates_occupied_from_empty():
    """中心亮度 + 自适应分界必须把有子/空位完全分开，否则追踪无从谈起。

    这条取代了旧的「最暗墨迹」判据：旧判据假设棋盘比棋子亮，遇到深色
    棋盘（真机白圆盘 + 深蓝底）会整个反过来，是真机死锁的根因。
    """
    screen = STARTING_BOARD
    img = _img(screen)
    lum = [
        [_center_luminance(img, CELL, MARGIN, r, f) for f in range(9)]
        for r in range(10)
    ]
    thr = _occupancy_threshold([v for row in lum for v in row])
    occ = [lum[r][f] for r in range(10) for f in range(9) if screen[r][f] != " "]
    empty = [lum[r][f] for r in range(10) for f in range(9) if screen[r][f] == " "]
    assert occ and empty
    assert max(empty) < thr < min(occ), (
        f"分界 {thr:.0f} 未落在空位({max(empty):.0f})与有子({min(occ):.0f})之间"
    )


def test_no_change_is_idle():
    t, screen = _tracker()
    events = _feed(t, screen, frames=5)
    assert all(e.kind == "idle" for e in events)
    assert t.side_to_move == "w"


# ---------------------------------------------------------------- 走子识别

def test_single_move_detected():
    t, screen0 = _tracker()
    screen1 = synth.move_screen(screen0, (6, 0), (5, 0))
    events = _feed(t, screen1, frames=3)
    moved = _moved(events)
    assert len(moved) == 1
    assert moved[0].moves == [("P", (6, 0), (5, 0))]
    assert moved[0].board_before[6][0] == "P"
    assert t.board[5][0] == "P" and t.board[6][0] == " "
    assert t.side_to_move == "b"


def test_move_accepted_only_after_stable_polls():
    """第一帧就采纳会误判滑行动画，必须等占/空模式稳定。"""
    t, screen0 = _tracker()
    screen1 = synth.move_screen(screen0, (6, 0), (5, 0))
    img = _img(screen1)
    first = t.update(img)
    assert first.kind == "unstable"  # 第 1 帧只在计数，不采纳
    assert t.board[6][0] == "P"      # 盘面尚未改变
    assert t.update(img).kind == "moved"


def test_ghost_residue_at_source_still_detected():
    """JJ象棋 在来源格留下的半透明残影，是旧实现死循环的直接原因。"""
    t, screen0 = _tracker()
    screen1 = synth.move_screen(screen0, (6, 0), (5, 0))
    events = _feed(t, screen1, frames=3, ghosts=[(6, 0)])
    moved = _moved(events)
    assert len(moved) == 1, f"残影导致无法识别走子：{events}"
    assert moved[0].moves == [("P", (6, 0), (5, 0))]


def test_capture_detected_through_ambiguous_cell():
    """吃子时落点「有子→有子」，只能靠 amb 解释，不能被忽略。"""
    rows = [list(r) for r in STARTING_BOARD]
    rows[5][0] = "p"          # 在红兵正前方放一个黑卒（将帅未照面，局面合法）
    board = ["".join(r) for r in rows]
    t, screen0 = _tracker(board)
    screen1 = synth.move_screen(screen0, (6, 0), (5, 0))
    events = _feed(t, screen1, frames=3)
    moved = _moved(events)
    assert len(moved) == 1
    assert moved[0].moves == [("P", (6, 0), (5, 0))]
    assert t.board[5][0] == "P"
    assert t.board[6][0] == " "


def test_two_moves_in_one_interval():
    """轮询间隔较大时（如引擎思考期间）可能一次漏看两步。"""
    t, screen0 = _tracker()
    screen1 = synth.move_screen(screen0, (6, 0), (5, 0))
    screen1 = synth.move_screen(screen1, (3, 0), (4, 0))
    events = _feed(t, screen1, frames=3)
    moved = _moved(events)
    assert len(moved) == 1
    assert moved[0].moves == [("P", (6, 0), (5, 0)), ("p", (3, 0), (4, 0))]
    assert t.side_to_move == "w"  # 红先、黑后 → 又轮到红


def test_side_to_move_self_corrects():
    """若侧别跟踪漂移，按实际移动的棋子颜色纠正，而不是继续错下去。"""
    t, screen0 = _tracker(side="b")  # 故意给错的先行方
    screen1 = synth.move_screen(screen0, (6, 0), (5, 0))  # 走的是红兵
    events = _feed(t, screen1, frames=3)
    assert len(_moved(events)) == 1
    assert t.side_to_move == "b"  # 红方走完 → 该黑方


def test_flip_board_maps_screen_to_standard():
    """屏幕红方在上：屏幕 rank 3 的红兵对应标准 rank 6。"""
    t = BoardTracker([row[:] for row in STARTING_BOARD], True, CELL, MARGIN, "w")
    screen0 = synth.std_to_screen(STARTING_BOARD, True)
    t.update(_img(screen0))
    assert t.to_screen(6, 0) == (3, 0)
    screen1 = synth.move_screen(screen0, (3, 0), (4, 0))
    events = _feed(t, screen1, frames=3)
    moved = _moved(events)
    assert len(moved) == 1
    # 事件里的坐标必须是标准坐标
    assert moved[0].moves == [("P", (6, 0), (5, 0))]
    assert t.board[5][0] == "P"


# ---------------------------------------------------------------- 非走子变化

def test_highlight_only_change_settles_without_resync():
    """高亮只改圆面亮度、不改墨迹 → 不能当成走子。"""
    t, screen0 = _tracker()
    img = _img(screen0, highlights=[(6, 0)])
    events = [t.update(img) for _ in range(tracking.STABLE_POLLS + 2)]
    kinds = [e.kind for e in events]
    assert not any(k in ("moved", "need_resync") for k in kinds)
    # 高亮只让圆面更亮，占空不变 → 判「画面与盘面一致」或「已吸收」，都不是走子
    assert all(k in ("idle", "settled") for k in kinds)
    assert t.side_to_move == "w"


def test_hint_dots_do_not_trigger_move():
    """走子提示点面积小、变化幅度低，应被 BIG diff 过滤。"""
    t, screen0 = _tracker()
    events = _feed(t, screen0, frames=3, hints=[(5, 4), (4, 4)])
    assert not any(e.kind in ("moved", "need_resync") for e in events)


def test_ghost_fade_after_accepted_move_is_noise():
    """已采纳走子的来源格残影逐渐变淡，不能反复触发新走子。"""
    t, screen0 = _tracker()
    screen1 = synth.move_screen(screen0, (6, 0), (5, 0))
    assert len(_moved(_feed(t, screen1, frames=3, ghosts=[(6, 0)]))) == 1
    # 残影消失（回到纯空位）
    events = _feed(t, screen1, frames=tracking.STABLE_POLLS + 2)
    assert not any(e.kind in ("moved", "need_resync") for e in events)


# ---------------------------------------------------------------- 死锁自愈

def test_unresolvable_change_requests_resync_then_recovers():
    """main_log.txt 的死锁场景：变化无法配成合法走子时必须有限帧内重同步。"""
    t, screen0 = _tracker()
    rows = [list(r) for r in screen0]
    for f in (0, 2, 4):          # 3 个兵凭空消失（3 src / 0 dst）
        rows[6][f] = " "
    screen1 = ["".join(r) for r in rows]

    kinds = []
    for _ in range(tracking.STABLE_POLLS + tracking.RESYNC_POLLS + 4):
        kinds.append(t.update(_img(screen1)).kind)
    assert "need_resync" in kinds, f"永不请求重同步（死循环）: {kinds}"
    assert "moved" not in kinds

    # 调用方多帧识别后重同步 → 采用新盘面并恢复
    res = t.resync(screen1, _img(screen1))
    assert res.kind == "resynced"
    assert t.board == screen1
    assert all(t.update(_img(screen1)).kind in ("idle", "settled") for _ in range(3))


def test_illegal_teleport_never_accepted():
    """棋子瞬移多格（非法走法）不能被采纳，只能走重同步。"""
    t, screen0 = _tracker()
    screen1 = synth.move_screen(screen0, (6, 0), (3, 0))  # 兵一次冲三格
    frames = tracking.STABLE_POLLS + tracking.RESYNC_POLLS + 2
    kinds = [e.kind for e in _feed(t, screen1, frames=frames)]
    assert "moved" not in kinds
    assert "need_resync" in kinds


def test_resync_adopts_recognized_board_without_crash():
    t, screen0 = _tracker()
    screen1 = synth.move_screen(screen0, (6, 0), (5, 0))
    res = t.resync(screen1, _img(screen1))
    assert res.kind in ("resynced", "moved")
    assert t.board[5][0] == "P"


def test_resync_rejects_board_missing_king():
    """识别出错（丢将/帅）时必须拒绝采用，保留原盘面。"""
    t, screen0 = _tracker()
    broken = [row.replace("K", " ") for row in screen0]
    res = t.resync(broken, _img(screen0))
    assert res.kind == "unstable"
    assert "K" in "".join(t.board)


def test_resync_rejects_garbage_characters():
    """识别彻底失败会产出 '?'，重同步不能把这种盘面吃进来。"""
    t, screen0 = _tracker()
    garbage = ["?" * 9 for _ in range(10)]
    res = t.resync(garbage, _img(screen0))
    assert res.kind == "unstable"
    assert t.board == STARTING_BOARD


def test_resync_single_legal_move_is_treated_as_move():
    """差分漏检（如截屏时机错过动画）但识别发现一步合法走子 → 记为走子。"""
    t, screen0 = _tracker()
    # 先把基准帧推到「走子之后」，再重同步一个「又走了一步」的盘面
    screen1 = synth.move_screen(screen0, (6, 0), (5, 0))
    t.set_board(screen1, _img(screen0))  # 基准帧仍是旧的 → 差分视角看像漏检
    screen2 = synth.move_screen(screen1, (5, 0), (4, 0))
    res = t.resync(screen2, _img(screen2))
    assert res.kind == "moved"
    assert res.moves == [("P", (5, 0), (4, 0))]
    assert t.side_to_move == "b"


# ---------------------------------------------------------------- 状态维护

def test_recent_frames_bounded():
    t, screen = _tracker()
    for _ in range(10):
        t.update(_img(screen))
    frames = t.recent_frames()
    assert len(frames) == tracking.RECENT_FRAMES


def test_set_board_resets_baseline():
    t, screen0 = _tracker()
    other = [row[:] for row in screen0]
    t.set_board(other, _img(other))
    assert all(e.kind == "idle" for e in _feed(t, other, frames=3))


def test_infer_moves_node_budget_terminates(monkeypatch):
    """候选格异常多时配对搜索必须快速返回，不能指数爆炸卡住主循环。"""
    t, screen0 = _tracker()
    rows = [list(r) for r in screen0]
    for f in (0, 2, 4, 6, 8):
        rows[6][f] = " "          # 5 个兵消失
        rows[5][f] = "P"          # 5 个兵前移（看似可解释，实则混杂）
    scrambled = ["".join(r) for r in rows]
    monkeypatch.setattr(tracking, "MAX_INFER_NODES", 50)
    kinds = [e.kind for e in _feed(t, scrambled, frames=4)]
    assert kinds  # 只要不抛异常、能返回即可


# ------------------------------------------------- 皮肤无关性（真机回归）

DARK_SKIN = dict(bg_bgr=(70, 78, 88), disc_bgr=(228, 234, 240))


def test_occupancy_correct_on_dark_board_skin():
    """深蓝棋盘 + 白圆盘（真机实际皮肤）：占空判据必须仍然正确。

    旧实现用「中心最暗 20% 像素 = 墨迹深 = 有子」，在深色棋盘上整个反过来
    （空位 47 比白圆盘 97 更暗），真机上表现为「走子后一直 unstable、
    永远检测不到走子」——这正是用户遇到的死锁。
    """
    screen = STARTING_BOARD
    img = _img(screen, **DARK_SKIN)
    lum = [
        [_center_luminance(img, CELL, MARGIN, r, f) for f in range(9)]
        for r in range(10)
    ]
    thr = _occupancy_threshold([v for row in lum for v in row])
    occ = [lum[r][f] for r in range(10) for f in range(9) if screen[r][f] != " "]
    empty = [lum[r][f] for r in range(10) for f in range(9) if screen[r][f] == " "]
    assert min(occ) > thr, f"白圆盘被判成空位（阈值 {thr:.0f}）"
    assert max(empty) < thr, f"深色空位被判成有子（阈值 {thr:.0f}）"


def test_move_detected_on_dark_board_skin():
    """深色皮肤上走子也要能检测出来（端到端，不只是判据）。"""
    rows = [list(r) for r in STARTING_BOARD]
    board = ["".join(r) for r in rows]
    t = BoardTracker([row[:] for row in board], False, CELL, MARGIN, side_to_move="w")
    assert t.update(_img(board, **DARK_SKIN)).kind == "idle"
    after = synth.move_screen(board, (6, 0), (5, 0))
    events = [_feed(t, after, frames=1, **DARK_SKIN)[0] for _ in range(3)]
    moved = _moved(events)
    assert len(moved) == 1, [e.kind for e in events]
    assert moved[0].moves == [("P", (6, 0), (5, 0))]


def test_trade_in_one_interval_reuses_same_landing_cell():
    """兑子：先吃过去、立刻被吃回来，两手的落点是同一格。

    真机实测（第 7 回合）：红炮 (7,7) 隔黑车 (1,7) 打黑炮 (0,7)，黑车 (0,8)
    随即吃回。此时离格是 (7,7) 与 (0,8) 两个，落点却只有 (0,7) 一个——
    旧实现禁止落点复用，直接判「无法解析」，只能靠重同步补救（丢走子记录）。
    """
    board = [
        "  baka cr", "       r ", "nc  b n  ", "p p p p p", "         ",
        "  P   P  ", "P   P   P", " CN B NC ", "        R", "R  AKAB  ",
    ]
    t, screen0 = _tracker(board)
    screen1 = synth.move_screen(screen0, (7, 7), (0, 7))   # 炮吃炮
    screen1 = synth.move_screen(screen1, (0, 8), (0, 7))   # 车吃回
    events = _feed(t, screen1, frames=3)
    moved = _moved(events)
    assert len(moved) == 1, [e.kind for e in events]
    assert moved[0].moves == [("C", (7, 7), (0, 7)), ("r", (0, 8), (0, 7))]
    assert t.board[0][7] == "r"      # 该格最终是黑车
    assert t.board[0][8] == " "      # 两个来源格都空了
    assert t.board[7][7] == " "
    assert t.side_to_move == "w"     # 红先黑后 → 又轮到红


def test_rook_retreat_is_not_mistaken_for_capturing_adviser():
    """真机第 10 回合：黑车退回 (1,1)，同时我方车平到 (8,1)。

    占空图只分得清「空 / 有子」，分不清颜色。于是除正确解之外，还有一条同样
    合法的假解：黑车 (1,3) 沿 4 路直下吃掉 (9,3) 的红仕——因为红仕确实还摆
    在那里（该格 was_occ & now_occ）。两条解释并存，旧实现判「无法确定」，
    连续 6 帧后 need_resync。修复后要求「凭空多出的子必须由某步落上去」，
    假解没人去解释 (1,1) 上多出来的车，被自动排除。
    """
    board = [
        "  baka r ", "   r     ", "nc  b n  ", "p p p p p", "         ",
        "  P   P  ", "P   P   P", "C N B N  ", "        R", "R  AKAB  ",
    ]
    t, screen0 = _tracker(board)
    screen1 = synth.move_screen(screen0, (8, 8), (8, 1))    # 我方：车一平八
    screen1 = synth.move_screen(screen1, (1, 3), (1, 1))    # 对方：车退回底线
    events = _feed(t, screen1, frames=3)
    moved = _moved(events)
    assert len(moved) == 1, [e.kind for e in events]
    assert moved[0].moves == [("R", (8, 8), (8, 1)), ("r", (1, 3), (1, 1))]
    assert t.board[8][1] == "R" and t.board[8][8] == " "
    assert t.board[1][1] == "r" and t.board[1][3] == " "
    assert t.board[9][3] == "A"          # 红仕没被吃掉
    assert t.side_to_move == "w"


def test_capture_uses_the_pawn_that_actually_changed():
    """真机第 13 回合：马在 (5,3)，能合法吃掉 (3,2) 与 (3,4) 两处卒。

    占空图只分得清空/有子，两条解都满足「落点有子」，旧实现判歧义 → 连续
    6 帧「无法解析」→ need_resync。真实走法是吃 (3,2)（那格换成了红马），
    (3,4) 的卒一动不动。修复后要求「吃子落点必须与基准帧相比看得出变化」，
    假解自动出局。
    """
    board = [
        "  b ka   ", " r  a    ", "nc  b n  ", "p p p p p", "       r ",
        "  PN  P  ", "P   P   P", "C   B N  ", " R  A    ", "R   KAB  ",
    ]
    t, screen0 = _tracker(board)
    screen1 = synth.move_screen(screen0, (5, 3), (3, 2))    # 我方马吃卒
    screen1 = synth.move_screen(screen1, (1, 1), (0, 1))    # 对方车退到死路
    moved = _moved(_feed(t, screen1, frames=3))
    assert len(moved) == 1, [e.kind for e in _feed(_tracker(board)[0], screen1)]
    assert moved[0].moves == [("N", (5, 3), (3, 2)), ("r", (1, 1), (0, 1))]
    assert t.board[3][2] == "N" and t.board[5][3] == " "
    assert t.board[3][4] == "p"          # 另一只卒没被吃
    assert t.side_to_move == "w"


def test_capture_picks_whichever_pawn_really_moved():
    """对偶：同一局面改吃 (3,4)，也必须认对（不能是硬编码某一侧）。"""
    board = [
        "  b ka   ", " r  a    ", "nc  b n  ", "p p p p p", "       r ",
        "  PN  P  ", "P   P   P", "C   B N  ", " R  A    ", "R   KAB  ",
    ]
    t, screen0 = _tracker(board)
    screen1 = synth.move_screen(screen0, (5, 3), (3, 4))
    screen1 = synth.move_screen(screen1, (1, 1), (0, 1))
    moved = _moved(_feed(t, screen1, frames=3))
    assert len(moved) == 1
    assert moved[0].moves == [("N", (5, 3), (3, 4)), ("r", (1, 1), (0, 1))]
    assert t.board[3][4] == "N" and t.board[3][2] == "p"
