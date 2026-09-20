"""诊断：截屏 → 矫正 → 识别 → 保存矫正图，用于肉眼检查高亮/走子。"""
import cv2
import json

from . import capture
from .board import flip_board
from .calibrate import FILES, RANKS, load_templates, rectify
from .recognize import recognize_board


def main():
    cfg = json.load(open("config.json", encoding="utf-8"))
    local = capture.grab(cfg["hdc_path"], cfg["remote_path"], cfg["local_path"])
    img = cv2.imread(local)
    if img is None:
        print("读取截图失败")
        return
    rect, cell, margin = rectify(img, cfg["board_corners"])
    cv2.imwrite("rectified.png", rect)
    print("已保存 rectified.png", rect.shape)

    templates = load_templates(cfg["templates_dir"])
    board, confs = recognize_board(rect, templates, cell, margin)
    flip = cfg.get("flip_board", False)
    std = flip_board(board) if flip else board
    print("识别结果（标准坐标，红在下）：")
    for row in std:
        print("  " + row)
    print("每格分数（RAW 红在上）：")
    for r in range(RANKS):
        line = []
        for f in range(FILES):
            line.append(f"{board[r][f]}:{confs[r * FILES + f]:.2f}")
        print("  " + " ".join(line))


if __name__ == "__main__":
    main()
