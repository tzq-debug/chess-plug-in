"""展示：截图 + 箭头 + 中文记谱。"""

import cv2
import numpy as np

from .calibrate import grid_intersections


def draw_move(image, corners, move, color=(0, 255, 0)):
    """在截图 image 上画最佳走法箭头。move = ((fr, ff), (tr, tf))。"""
    grid = grid_intersections(corners)
    (fr, ff), (tr, tf) = move
    p1 = tuple(int(v) for v in grid[fr][ff])
    p2 = tuple(int(v) for v in grid[tr][tf])
    cv2.circle(image, p1, 14, color, 3)
    cv2.arrowedLine(image, p1, p2, color, 4, tipLength=0.3)
    return image


def show_window(image_bgr):
    """在 tkinter 窗口显示一张 BGR 图。返回后需 mainloop。"""
    import tkinter as tk
    from PIL import Image, ImageTk

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    root = tk.Tk()
    root.title("象棋最佳走法")
    photo = ImageTk.PhotoImage(pil)
    label = tk.Label(root, image=photo)
    label.image = photo
    label.pack()
    return root, photo
