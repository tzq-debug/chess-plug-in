"""仅重新提取棋子模板（不重新标定四角）。

用法（开一局初始局面时，截图已存到 screenshot.png）：
    python -m xiangqi.retemplate screenshot.png [--config config.json]

复用 config.json 里已有的 board_corners，先自动精修网格（用户标定的四角
往往含棋盘外框，比真实交叉点网格大约半格，直接按四角矫正会让模板整体
偏心），再按初始布局裁模板，覆盖 templates/ 下的旧模板。
"""

import argparse

import cv2
import numpy as np

from .board import STARTING_BOARD, flip_board
from .calibrate import (
    detect_flip,
    extract_templates,
    refine_rectify,
    save_templates,
    scale_corners,
)
from .calibrate_cli import load_base_config, write_config


def _imread(path):
    """读图，兼容含中文/特殊字符的路径（cv2.imread 在 Windows 上会失败）。"""
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except (OSError, ValueError):
        data = None
    if data is not None and data.size:
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is not None:
            return img
    return cv2.imread(path)


def run(screenshot_path, config_path="config.json", templates_dir="templates"):
    img = _imread(screenshot_path)
    if img is None:
        print(f"无法读取截图: {screenshot_path}")
        return 1
    cfg = load_base_config(config_path)
    corners = cfg.get("board_corners")
    if not corners:
        print("config.json 里没有 board_corners，请先运行 calibrate_cli 标定。")
        return 1

    # 截图尺寸与标定 board_corners 时不同（例如设备端降采样抓图）则等比换算
    corners = scale_corners(corners, cfg.get("screen_size"), (img.shape[1], img.shape[0]))
    rectified, cell, margin, _, fit = refine_rectify(img, corners)
    if fit is None:
        print("警告：网格自动精修失败（未检测到足够的棋子圆盘），按原四角矫正提取。")
    flip = detect_flip(rectified, cell, margin)
    board = flip_board(STARTING_BOARD) if flip else STARTING_BOARD
    print(f"棋盘方向：{'红方在上（翻转）' if flip else '红方在下（标准）'}"
          f"（网格精修{'成功' if fit else '失败'}）")

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
