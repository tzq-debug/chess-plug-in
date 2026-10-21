"""展示：截图 + 箭头 + 中文记谱。"""

import cv2
import numpy as np

from .calibrate import grid_intersections

ARROW_HEAD_PX = 16.0   # 箭头头部长度上限（像素），避免长走法画出一个盖住邻子的大头


def draw_move(image, corners, move, color=(0, 255, 0)):
    """在截图 image 上画最佳走法箭头。move = ((fr, ff), (tr, tf))。

    箭头长度随棋盘尺寸走，但**箭头头部固定折算成像素上限**：cv2 的
    tipLength 是「占线长的比例」，一条 9 格长的炮箭会被画出 ~67px 的大头，
    直接盖住相邻棋子（实测 628px 宽的截图上横跨两列）。按线长反算比例，
    把头部钉在 16px 左右，长短走法的箭头看起来就一致了。
    """
    grid = grid_intersections(corners)
    (fr, ff), (tr, tf) = move
    p1 = tuple(int(v) for v in grid[fr][ff])
    p2 = tuple(int(v) for v in grid[tr][tf])
    cv2.circle(image, p1, 14, color, 3)
    dist = max(1.0, float(np.hypot(p2[0] - p1[0], p2[1] - p1[1])))
    tip = min(0.3, ARROW_HEAD_PX / dist)
    cv2.arrowedLine(image, p1, p2, color, 4, tipLength=tip)
    return image


def draw_void(image, label="WAIT"):
    """把画面打成「作废」样式：整体压暗 + 大红叉 + WAIT。

    盘面不稳时不能用删文件的方式表达。用户通常正开着预览面板看 bestmove.png，
    文件一消失面板就变成「暂无数据」，看着像程序挂了（真机实测踩过）。
    留一张明显作废的图：文件始终在，但没人会照着它走棋。
    """
    out = cv2.convertScaleAbs(image, alpha=0.35, beta=0)
    h, w = out.shape[:2]
    red = (0, 0, 255)
    cv2.line(out, (0, 0), (w, h), red, 8)
    cv2.line(out, (w, 0), (0, h), red, 8)
    cv2.putText(
        out, label, (int(w * 0.04), int(h * 0.55)),
        cv2.FONT_HERSHEY_SIMPLEX, 1.6, red, 4, cv2.LINE_AA,
    )
    return out


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


class LiveView:
    """可反复更新的 tkinter 实时窗口（主循环里每次算棋后刷新）。

    构造失败（无显示环境）会抛异常，由调用方退化为只写文件。"""

    def __init__(self, title="象棋最佳走法"):
        import tkinter as tk
        from PIL import Image, ImageTk

        self._tk = tk
        self._Image = __import__("PIL.Image", fromlist=["Image"])
        self._ImageTk = ImageTk
        self.root = tk.Tk()
        self.root.title(title)
        self.label = tk.Label(self.root)
        self.label.pack()
        self._photo = None

    def update(self, image_bgr):
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pil = self._Image.fromarray(rgb)
        self._photo = self._ImageTk.PhotoImage(pil)
        self.label.configure(image=self._photo)
        self.label.image = self._photo
        self.root.update_idletasks()
        self.root.update()

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass
