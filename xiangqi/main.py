"""主循环：采集 → 识别 → 判先后 → 算棋 → 展示。"""

import json
import time

import cv2

from . import capture
from .board import board_to_fen, flip_board
from .calibrate import rectify, load_templates
from .display import draw_move
from .engine import PikafishEngine
from .notation import parse_move, move_to_chinese
from .recognize import recognize_board
from .turn_detect import active_side, region_diff, to_fen_side


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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
    has_timer = "timer_regions" in cfg

    prev_img = None
    last_board = None
    try:
        while True:
            try:
                local = capture.grab(cfg["hdc_path"], cfg["remote_path"], cfg["local_path"])
                img = cv2.imread(local)
                if img is None:
                    print("读取截图失败")
                    time.sleep(1)
                    continue

                rect, cell, margin = rectify(img, cfg["board_corners"])
                board, conf = recognize_board(rect, templates, cell, margin)
                if "?" in "".join(board):
                    # 识别不确定，丢弃该帧（spec §5）
                    time.sleep(1)
                    continue
                if cfg.get("flip_board"):
                    board = flip_board(board)

                # 判先后：对比相邻两帧头像计时器区域，谁在走谁的行棋方
                side = None
                if has_timer and prev_img is not None:
                    d_self = region_diff(img, prev_img, cfg["timer_regions"]["self"])
                    d_opp = region_diff(img, prev_img, cfg["timer_regions"]["opponent"])
                    side = active_side(d_self, d_opp)
                prev_img = img

                if board == last_board:
                    time.sleep(1)
                    continue

                # 映射成 FEN 走子方；判不出先后则保留 last_board，下一帧再试
                fen_side = to_fen_side(side, player) if has_timer else my_side
                if fen_side is None:
                    time.sleep(1)
                    continue
                last_board = board

                if fen_side != my_side:
                    # 轮到对手，等待即可
                    time.sleep(1)
                    continue

                fen = board_to_fen(board, fen_side)
                engine.set_position(fen)
                result = engine.search(cfg["movetime_ms"])
                move = result["bestmove"]
                if move is None or move in ("(none)", "0000"):
                    print("引擎未给出合法走法")
                    continue
                (fr, ff), (tr, tf) = parse_move(move)
                chinese = move_to_chinese(board, fr, ff, tr, tf)
                print(f"最佳走法: {chinese}  ({move})  评估: {result['score']}")

                annotated = draw_move(img, cfg["board_corners"], ((fr, ff), (tr, tf)))
                cv2.imwrite("bestmove.png", annotated)
            except Exception as e:
                print(f"采集/识别/算棋失败，重试: {e}")
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if engine is not None:
            engine.quit()


if __name__ == "__main__":
    main()
