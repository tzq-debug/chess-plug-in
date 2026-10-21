"""诊断：截屏 → 矫正（含网格精修）→ 识别 → 保存矫正图，用于肉眼检查。

和主程序走完全相同的链路，方便对比「程序看到的」与「人看到的」是否一致：
    python -m xiangqi.diagnose [config.json]

输出：
    rectified.png   精修后的矫正图（网格交叉点用绿圈标出）
    diagnose.txt    识别盘面 + 每格匹配分数（分数低用 ^ 标出）
"""

import json
import sys

import cv2
import numpy as np

from . import capture
from .board import flip_board
from .calibrate import FILES, RANKS, load_templates, refine_rectify, scale_corners
from .recognize import recognize_board


def _read_image(path):
    """读图，兼容含中文的路径（cv2.imread 在 Windows 上会失败）。"""
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except (OSError, ValueError):
        data = None
    if data is not None and data.size:
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is not None:
            return img
    return cv2.imread(path)


def main(config_path="config.json"):
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    try:
        local = capture.grab(cfg["hdc_path"], cfg["remote_path"], cfg["local_path"])
    except capture.CaptureError as e:
        print(f"截屏失败: {e}")
        print("提示：请确认手机已连 USB、已授权调试，且 hdc 路径正确。")
        return 1
    img = _read_image(local)
    if img is None:
        print(f"读取截图失败: {local}")
        return 1

    corners = scale_corners(
        cfg["board_corners"], cfg.get("screen_size"), (img.shape[1], img.shape[0])
    )
    rect, cell, margin, corners, fit = refine_rectify(img, corners)
    if fit is None:
        print("警告：网格精修失败（四角外扩过多/画面里棋子太少），按标定四角继续。")
    else:
        print(f"网格已精修（修正四角: {[[round(x), round(y)] for x, y in corners]}）")

    vis = rect.copy()
    for r in range(RANKS):
        for fr in range(FILES):
            cv2.circle(vis, (int(margin + fr * cell), int(margin + r * cell)), 5, (0, 255, 0), 2)
    cv2.imwrite("rectified.png", vis)
    print(f"已保存 rectified.png {rect.shape}")

    templates = load_templates(cfg["templates_dir"])
    if not templates:
        print(f"模板目录 {cfg['templates_dir']} 为空，请先运行 python -m xiangqi.retemplate <截图>")
        return 1
    board, confs = recognize_board(rect, templates, cell, margin)
    flip = cfg.get("flip_board", False)
    std = flip_board(board) if flip else board

    lines = ["识别结果（标准坐标，红在下）："]
    lines += ["  " + row for row in std]
    lines.append("每格匹配分数（屏幕坐标，^ = 分数偏低，可能识别错误）：")
    for r in range(RANKS):
        cells = []
        for fr in range(FILES):
            score = confs[r * FILES + fr]
            mark = "^" if score < 0.55 else " "
            cells.append(f"{board[r][fr]}{mark}{score:.2f}")
        lines.append(f"  r{r} " + " ".join(cells))
    text = "\n".join(lines)
    print(text)
    with open("diagnose.txt", "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print("已保存 diagnose.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
