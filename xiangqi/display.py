"""展示：截图 + 箭头 + 中文记谱。"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

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


_FONT_PATHS = (
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
)
_font_cache = {}


def _load_font(size):
    """找一个能显示中文的字体（Windows 上基本都能命中微软雅黑）。"""
    if size in _font_cache:
        return _font_cache[size]
    font = None
    for path in _FONT_PATHS:
        try:
            font = ImageFont.truetype(path, size)
            break
        except OSError:
            continue
    _font_cache[size] = font
    return font


def draw_void(image, title="暂不给出建议", subtitle="画面稳定后自动恢复"):
    """盘面存疑时覆盖一张「暂停」提示卡。

    盘面不稳时不能用删文件的方式表达：用户通常正开着预览面板看 bestmove.png，
    文件一消失面板就变成「暂无数据」，看着像程序挂了。之前画的是贯穿全屏的
    大红叉 + WAIT，太刺眼也不好看——改成整体压暗 + 居中一张深色圆角卡，
    标题说状态、副标题说会自动恢复，既明显又不喧宾夺主。
    """
    dimmed = cv2.convertScaleAbs(image, alpha=0.45, beta=0)
    pil = Image.fromarray(cv2.cvtColor(dimmed, cv2.COLOR_BGR2RGB)).convert("RGBA")
    w, h = pil.size

    card = Image.new("RGBA", pil.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    pad = int(w * 0.055)
    box_h = int(h * 0.135)
    top = (h - box_h) // 2
    draw.rounded_rectangle(
        (pad, top, w - pad, top + box_h),
        radius=int(box_h * 0.22),
        fill=(16, 20, 28, 208),
        outline=(240, 186, 78, 235),
        width=max(2, int(w * 0.006)),
    )

    title_font = _load_font(int(h * 0.032))
    sub_font = _load_font(int(h * 0.019))
    cx = w // 2
    if title_font is None:      # 没有中文字体就退回英文，别画出一堆方块
        title, subtitle = "PAUSED", "waiting for a stable frame"
        title_font = sub_font = None

    if title_font is not None:
        draw.text((cx, top + box_h * 0.37), title, font=title_font,
                  fill=(255, 214, 128, 255), anchor="mm")
        draw.text((cx, top + box_h * 0.71), subtitle, font=sub_font,
                  fill=(196, 204, 218, 255), anchor="mm")
    else:
        draw.text((cx, top + box_h * 0.44), title, fill=(255, 214, 128, 255), anchor="mm")
        draw.text((cx, top + box_h * 0.72), subtitle, fill=(196, 204, 218, 255), anchor="mm")

    merged = Image.alpha_composite(pil, card)
    return cv2.cvtColor(np.array(merged.convert("RGB")), cv2.COLOR_RGB2BGR)


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
