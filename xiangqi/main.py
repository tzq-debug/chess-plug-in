"""主循环：采集 → 追踪走子 → 判先后 → 算棋 → 展示。

走子检测策略：
    开局直接以标准初始局面建立「可信盘面」（识别对高亮棋子不可靠，但开局位置是确定的），
    此后不再靠逐格识别判断走子，而是对相邻两帧的矫正图做逐格画面差分，找出发生变化的格子——
    来源格（可信盘面里有子、现在变空）+ 落点格（可信盘面里空、现在有了子），
    落点的棋子类型直接继承来源格。这样河界上因光照/底色认不出的走子也能正确追踪。
"""

import json
import time

import cv2
import numpy as np

from . import capture
from .board import STARTING_BOARD, board_to_fen, flip_board
from .calibrate import rectify, load_templates, FILES, RANKS
from .display import draw_move
from .engine import PikafishEngine
from .notation import parse_move, move_to_chinese
from .recognize import recognize_board


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


DIFF_THRESHOLD = 12.0  # 每像素平均绝对差，超过即认为该格画面发生了变化
SLEEP = 0.4            # 轮询间隔（秒），快一点能减少「两步挤进同一间隔」


def _cell_diff(prev, cur, cell, margin, r, f):
    """两帧矫正图同一格的平均绝对差。"""
    half = cell // 2
    x = margin + f * cell
    y = margin + r * cell
    a = prev[y - half : y + half, x - half : x + half].astype(np.int16)
    b = cur[y - half : y + half, x - half : x + half].astype(np.int16)
    return float(np.abs(a - b).mean())


def _changed_cells(prev, cur, cell, margin):
    """返回画面发生变化的格子 (r, f) 列表。"""
    out = []
    for r in range(RANKS):
        for f in range(FILES):
            if _cell_diff(prev, cur, cell, margin, r, f) > DIFF_THRESHOLD:
                out.append((r, f))
    return out


def main(config_path="config.json"):
    cfg = load_config(config_path)
    engine = None
    try:
        engine = PikafishEngine([cfg["engine_path"]])
        engine.start()
        templates = load_templates(cfg["templates_dir"])
    except Exception as e:
        print(f"初始化失败: {e}")
        if engine is not None:
            try:
                engine.quit()
            except Exception:
                pass
        return

    player = cfg.get("player_color", "red")
    my_side = "w" if player == "red" else "b"
    flip = bool(cfg.get("flip_board", False))

    side_to_move = "w"
    board = None          # 可信盘面：10 行字符串
    stable_rect = None    # 上一稳定帧的矫正图，用于画面差分
    last_fen = None       # 上次已算棋的局面，避免每帧重复算
    try:
        while True:
            try:
                local = capture.grab(cfg["hdc_path"], cfg["remote_path"], cfg["local_path"])
                img = cv2.imread(local)
                if img is None:
                    print("读取截图失败")
                    time.sleep(SLEEP)
                    continue
                rect, cell, margin = rectify(img, cfg["board_corners"])

                # ---- 开局：以标准初始局面作为可信盘面 ----
                # 逐格识别对「高亮/反光」的个别棋子不可靠（实测有 3 个棋子会漏判），
                # 但开局必然是标准初始局面，所以直接采用它，再用识别做一次校验。
                if board is None:
                    raw, _ = recognize_board(rect, templates, cell, margin)
                    raw = flip_board(raw) if flip else raw
                    matches = sum(
                        1
                        for r in range(RANKS)
                        for f in range(FILES)
                        if raw[r][f] == STARTING_BOARD[r][f]
                    )
                    print(f"初始局面校验：识别匹配 {matches}/90")
                    if matches < 85:
                        print("警告：识别结果与初始局面差异较大，可能不是开局或截图异常。")
                    board = [row[:] for row in STARTING_BOARD]
                    stable_rect = rect.copy()
                    print("初始局面已建立：")
                    for row in board:
                        print("  " + row)
                    time.sleep(SLEEP)
                    continue

                # ---- 画面差分，检测走子 ----
                # stable_rect / rect 是矫正图（红在上），board 是标准盘面（红在下），
                # 两者行序相反，diff 坐标需先转成标准坐标再索引 board。
                changed = _changed_cells(stable_rect, rect, cell, margin)
                if changed:
                    # 调试：打印每个变化格子的差分幅度，便于区分「真走子」与「高亮漂移」
                    _mags = sorted(
                        ((_cell_diff(stable_rect, rect, cell, margin, r, f), (r, f))
                         for r, f in changed),
                        reverse=True,
                    )
                    print("变化格子（幅度降序）：",
                          [(c, round(d, 1)) for d, c in _mags])
                    if flip:
                        changed = [(RANKS - 1 - r, f) for (r, f) in changed]
                    srcs = [c for c in changed if board[c[0]][c[1]] != " "]
                    dsts = [c for c in changed if board[c[0]][c[1]] == " "]

                    if len(srcs) == 1 and len(dsts) == 1:
                        # 单步走子
                        (sr, sf), (dr, df) = srcs[0], dsts[0]
                        piece = board[sr][sf]
                        rows = [list(row) for row in board]
                        rows[sr][sf] = " "
                        rows[dr][df] = piece
                        board = ["".join(row) for row in rows]
                        side_to_move = "b" if side_to_move == "w" else "w"
                        stable_rect = rect.copy()
                        print(f"检测到走子：{piece} {srcs[0]} -> {dsts[0]}，"
                              f"轮到{'红' if side_to_move == 'w' else '黑'}")
                        for row in board:
                            print("  " + row)
                    elif len(srcs) == 2 and len(dsts) == 2:
                        # 两步（红+黑）挤进同一间隔：按最近邻配对，各走一步，轮次翻转两次不变
                        rows = [list(row) for row in board]
                        dsts = list(dsts)
                        for (sr, sf) in srcs:
                            piece = board[sr][sf]
                            nearest = min(dsts, key=lambda d: abs(d[0] - sr) + abs(d[1] - sf))
                            rows[sr][sf] = " "
                            rows[nearest[0]][nearest[1]] = piece
                            dsts.remove(nearest)
                        board = ["".join(row) for row in rows]
                        stable_rect = rect.copy()
                        print("检测到两步连续走子（红+黑），轮次不变")
                        for row in board:
                            print("  " + row)
                    else:
                        # 动画中或噪声，等待稳定
                        print(f"画面变化 {len(changed)} 格（src={len(srcs)} dst={len(dsts)}），"
                              f"srcs={srcs} dsts={dsts}，等待稳定")
                        time.sleep(SLEEP)
                        continue

                # ---- 轮到我方且局面未算过：算棋 ----
                if side_to_move == my_side:
                    fen = board_to_fen(board, side_to_move)
                    if fen != last_fen:
                        last_fen = fen
                        engine.set_position(fen)
                        result = engine.search(cfg["movetime_ms"])
                        move = result["bestmove"]
                        if move is None or move in ("(none)", "0000"):
                            print("引擎未给出合法走法")
                        else:
                            (fr, ff), (tr, tf) = parse_move(move)
                            chinese = move_to_chinese(board, fr, ff, tr, tf)
                            print(f"最佳走法: {chinese}  ({move})  评估: {result['score']}")
                            # draw_move 用的是屏幕坐标（红在上），标准坐标需先翻转行号
                            dfr, dtr = (RANKS - 1 - fr, RANKS - 1 - tr) if flip else (fr, tr)
                            annotated = draw_move(img, cfg["board_corners"], ((dfr, ff), (dtr, tf)))
                            cv2.imwrite("bestmove.png", annotated)

                time.sleep(SLEEP)
            except Exception as e:
                print(f"采集/追踪/算棋失败，重试: {e}")
                time.sleep(SLEEP)
    except KeyboardInterrupt:
        pass
    finally:
        if engine is not None:
            engine.quit()


if __name__ == "__main__":
    main()
