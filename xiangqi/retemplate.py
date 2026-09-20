"""仅重新提取棋子模板（不重新标定四角）。

用法（开一局初始局面时，截图已存到 screenshot.png）：
    python -m xiangqi.retemplate screenshot.png [--config config.json]

复用 config.json 里已有的 board_corners，按初始布局重新裁模板，
覆盖 templates/ 下的旧模板。用于更换识别分辨率后重做模板。
"""

import argparse

import cv2

from .board import STARTING_BOARD, flip_board
from .calibrate import detect_flip, extract_templates, rectify, save_templates
from .calibrate_cli import load_base_config, write_config


def run(screenshot_path, config_path="config.json", templates_dir="templates"):
    img = cv2.imread(screenshot_path)
    if img is None:
        print(f"无法读取截图: {screenshot_path}")
        return 1
    cfg = load_base_config(config_path)
    corners = cfg.get("board_corners")
    if not corners:
        print("config.json 里没有 board_corners，请先运行 calibrate_cli 标定。")
        return 1

    rectified, cell, margin = rectify(img, corners)
    flip = detect_flip(rectified, cell, margin)
    board = flip_board(STARTING_BOARD) if flip else STARTING_BOARD
    print(f"棋盘方向：{'红方在上（翻转）' if flip else '红方在下（标准）'}")

    templates = extract_templates(rectified, board, cell, margin)
    save_templates(templates, templates_dir)
    print(f"已生成 {len(templates)} 张棋子模板到 {templates_dir}/")

    cfg["templates_dir"] = templates_dir
    cfg["flip_board"] = flip
    write_config(cfg, config_path)
    print(f"已更新 {config_path} 的 flip_board")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="仅重新提取棋子模板")
    p.add_argument("screenshot", help="初始局面的截图路径（png）")
    p.add_argument("--config", default="config.json")
    p.add_argument("--templates", default="templates")
    args = p.parse_args(argv)
    return run(args.screenshot, args.config, args.templates)


if __name__ == "__main__":
    raise SystemExit(main())
