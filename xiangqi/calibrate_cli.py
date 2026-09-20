"""校准助手：交互式标定棋盘四角 + 计时器区域，自动生成棋子模板并写 config.json。

用法（开一局初始局面时）：
    python -m xiangqi.calibrate_cli screenshot.png [--config config.json]

流程：
    1. 打开截图，依次点击棋盘四角（左上、右上、右下、左下）。
    2. 框选上方（对手）、下方（自己）头像的计时器区域（各点两个角，ESC 跳过）。
    3. 按初始布局自动裁 14 张棋子模板到 templates/。
    4. 把四角与计时器区域写进 config.json。
"""

import argparse
import json
import os

import cv2

from .board import STARTING_BOARD
from .calibrate import extract_templates, rectify, save_templates

CORNER_LABELS = ["左上", "右上", "右下", "左下"]


def _display_scale(image, max_w=1200, max_h=800):
    """若图太大则缩小用于显示，返回 (显示图, 缩放系数)。点击坐标按系数换算回原图。"""
    h, w = image.shape[:2]
    scale = min(1.0, max_w / w, max_h / h)
    if scale >= 1.0:
        return image, 1.0
    return cv2.resize(image, (int(w * scale), int(h * scale))), scale


def _collect_points(image, n, window_name, labels):
    """在窗口里依次点击 n 个点，返回原图坐标 [[x, y], ...]。ESC 取消，Z 撤销。"""
    disp, scale = _display_scale(image)
    pts = []

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < n:
            pts.append((x, y))
            cv2.circle(disp, (x, y), 4, (0, 255, 0), -1)
            cv2.imshow(window_name, disp)

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, on_mouse)
    cv2.imshow(window_name, disp)
    idx = 0
    while len(pts) < n:
        if idx != len(pts):
            idx = len(pts)
            if idx < n:
                print(f"点击第 {idx + 1}/{n} 点：{labels[idx]}（Z 撤销 / ESC 取消）")
        key = cv2.waitKey(30) & 0xFF
        if key == 27:
            cv2.destroyAllWindows()
            raise SystemExit("校准已取消")
        if key in (ord("z"), ord("Z"), 8) and pts:
            pts.pop()
            disp, _ = _display_scale(image)
            for p in pts:
                cv2.circle(disp, p, 4, (0, 255, 0), -1)
            cv2.imshow(window_name, disp)
    cv2.destroyAllWindows()
    return [[round(x / scale), round(y / scale)] for x, y in pts]


def _collect_rect(image, window_name, prompt):
    """点左上、右下两个角返回 [x, y, w, h]；ESC 返回 [0, 0, 0, 0]。"""
    print(prompt)
    disp, scale = _display_scale(image)
    pts = []

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < 2:
            pts.append((x, y))
            cv2.circle(disp, (x, y), 4, (255, 0, 0), -1)
            cv2.imshow(window_name, disp)

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, on_mouse)
    cv2.imshow(window_name, disp)
    while len(pts) < 2:
        key = cv2.waitKey(30) & 0xFF
        if key == 27:
            cv2.destroyAllWindows()
            print("（已跳过）")
            return [0, 0, 0, 0]
    cv2.destroyAllWindows()
    (x1, y1), (x2, y2) = pts
    x = round(min(x1, x2) / scale)
    y = round(min(y1, y2) / scale)
    w = round(abs(x2 - x1) / scale)
    h = round(abs(y2 - y1) / scale)
    return [x, y, w, h]


def templates_from_screenshot(image, corners, board=None):
    """从一张初始局面截图 + 四角，提取 14 张棋子模板（{字符: 灰度图}）。"""
    board = board if board is not None else STARTING_BOARD
    rectified, cell, margin = rectify(image, corners)
    return extract_templates(rectified, board, cell, margin)


def make_config(base, corners, timer_regions):
    """返回合并了标定结果的配置 dict（保留 base 的其它字段）。"""
    cfg = dict(base)
    cfg["board_corners"] = corners
    cfg["timer_regions"] = timer_regions
    return cfg


def load_base_config(config_path):
    """优先读已有 config.json，否则读 config.example.json，都没有则空 dict。"""
    for path in (config_path, "config.example.json"):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    return {}


def write_config(cfg, config_path):
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def run(screenshot_path, config_path="config.json", templates_dir="templates"):
    img = cv2.imread(screenshot_path)
    if img is None:
        print(f"无法读取截图: {screenshot_path}")
        return 1

    print("请依次点击棋盘四角（左上 → 右上 → 右下 → 左下）：")
    corners = _collect_points(img, 4, "calibrate", CORNER_LABELS)
    print(f"四角坐标: {corners}")

    opp = _collect_rect(img, "calibrate-opponent", "框选上方（对手）头像计时器区域：点左上角与右下角，ESC 跳过")
    self_ = _collect_rect(img, "calibrate-self", "框选下方（自己）头像计时器区域：点左上角与右下角，ESC 跳过")
    timer_regions = {"opponent": opp, "self": self_}
    print(f"计时器区域: {timer_regions}")

    templates = templates_from_screenshot(img, corners)
    save_templates(templates, templates_dir)
    print(f"已生成 {len(templates)} 张棋子模板到 {templates_dir}/")

    cfg = make_config(load_base_config(config_path), corners, timer_regions)
    cfg["templates_dir"] = templates_dir
    write_config(cfg, config_path)
    print(f"已写入 {config_path}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="象棋识别校准助手")
    p.add_argument("screenshot", help="初始局面的截图路径（png）")
    p.add_argument("--config", default="config.json", help="输出配置路径（默认 config.json）")
    p.add_argument("--templates", default="templates", help="模板输出目录（默认 templates）")
    args = p.parse_args(argv)
    return run(args.screenshot, args.config, args.templates)


if __name__ == "__main__":
    raise SystemExit(main())
