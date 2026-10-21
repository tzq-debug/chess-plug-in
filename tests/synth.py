"""合成手机棋盘画面（矫正图坐标系），供测试用。

按真实截图实测标定 JJ象棋 主题的关键视觉特征：
  * 空位：灰绿棋盘，中心亮度 ~130
  * 棋子：米黄暖色圆盘（R-G>15、中心亮度高，半径 ~0.45 格）+ 深色字迹
    （红方字迹偏红 R-G≈+70，黑方近中性）
  * 高亮：圆面整体提亮、字迹不变 → 占/空判定不受影响
  * 残影：来源格半透明圆盘（比实体棋子暗，应被判成「空」）
  * 提示点：格心小圆点（格子仍是空的 → 占空图自动排除，不会当成落点）
  * 滑移动画：slide=(from, to, t) 把棋子画在插值位置

占/空判定（xiangqi.tracking）用的是「格中心中位亮度 + 每帧自适应分界」，
因此本合成器的配色只是其中一种取值；render_board 的 bg_bgr / disc_bgr
可渲染相反的明暗关系（深色棋盘 + 白圆盘）来做皮肤无关性回归测试。

所有图案按棋子字符确定性生成：同型棋子渲染完全一致（模板匹配可分辨），
不同型棋子图案不同。坐标约定与 xiangqi.calibrate 一致：
交叉点 (r, f) 位于 (margin + f*cell, margin + r*cell)，r=0 为屏幕顶行。
"""

import cv2
import numpy as np

from xiangqi.calibrate import FILES, RANKS

EMPTY_BG = 132        # 空位棋盘亮度
DISC_BGR = (168, 198, 218)   # 米黄圆盘（BGR），R-G=+20、亮度高
DISC_HIGHLIGHT_BGR = (208, 235, 250)  # 高亮圆面（更亮）
RED_INK_BGR = (36, 36, 108)    # 红方字迹（R-G=+72）
BLACK_INK_BGR = (38, 38, 44)   # 黑方字迹（近中性）
GHOST_VALUE = 68       # 残影亮度：比实体棋子暗、接近空位 → 应判为「无子」
HINT_VALUE = 30        # 提示点亮度（够暗、但面积小）


def canonical_corners(cell=140):
    """合成图自身的标准四角（传入 rectify 等于恒等变换）。"""
    margin = cell
    return [
        [margin, margin],
        [margin + (FILES - 1) * cell, margin],
        [margin + (FILES - 1) * cell, margin + (RANKS - 1) * cell],
        [margin, margin + (RANKS - 1) * cell],
    ]


def _glyph_strokes(ch):
    """每个棋子字符一组确定性笔画（在单位圆内），保证同型一致、异型可辨。"""
    rng = np.random.default_rng(ord(ch) * 2654435761 % (2**32))
    n = 5 + (ord(ch) % 4)
    strokes = []
    for _ in range(n):
        x1, y1 = rng.uniform(-0.55, 0.55, 2)
        x2, y2 = rng.uniform(-0.55, 0.55, 2)
        strokes.append((float(x1), float(y1), float(x2), float(y2)))
    # 中心十字，保证所有字迹都覆盖圆盘中心（ darkest 20% 采样区内有墨）
    strokes.append((-0.30, 0.0, 0.30, 0.0))
    strokes.append((0.0, -0.30, 0.0, 0.30))
    return strokes


def _draw_piece(img, cx, cy, rad, ch, disc_bgr, ink_bgr):
    cv2.circle(img, (int(cx), int(cy)), int(rad), disc_bgr, -1)
    cv2.circle(img, (int(cx), int(cy)), int(rad), tuple(max(0, v - 40) for v in disc_bgr), 2)
    ink_r = rad * 0.62
    for x1, y1, x2, y2 in _glyph_strokes(ch):
        cv2.line(
            img,
            (int(cx + x1 * ink_r), int(cy + y1 * ink_r)),
            (int(cx + x2 * ink_r), int(cy + y2 * ink_r)),
            ink_bgr,
            max(2, int(rad * 0.16)),
            cv2.LINE_AA,
        )


def render_board(
    screen_board,
    cell=140,
    margin=140,
    *,
    highlights=(),
    ghosts=(),
    hints=(),
    slide=None,
    bg_bgr=None,
    disc_bgr=None,
):
    """渲染一帧合成棋盘图（BGR，屏幕坐标）。

    screen_board: 10 行字符串（屏幕坐标，空格为空位）。
    highlights:   高亮格 (r, f) 列表——圆面提亮、字迹不变。
    ghosts:       残影格 (r, f) 列表——半透明暗圆盘（无字迹）。
    hints:        提示点格 (r, f) 列表——格心小暗点。
    slide:        ((fr, ff), (tr, tf), t)——把 from 格棋子画在向 to 格
                  插值的位置（t∈[0,1]，t=1 时回到 to 格中心）。
    bg_bgr / disc_bgr: 覆盖棋盘底色与棋子圆盘色，用于模拟不同皮肤。
                  真机曾出现「深蓝棋盘 + 白色圆盘」，与默认的
                  「灰绿棋盘 + 米黄圆盘」明暗关系相反，必须都能判对。
    """
    W = (FILES - 1) * cell + 2 * margin
    H = (RANKS - 1) * cell + 2 * margin
    bg = EMPTY_BG if bg_bgr is None else bg_bgr
    disc_normal = DISC_BGR if disc_bgr is None else disc_bgr
    disc_lit = tuple(min(255, c + 30) for c in disc_normal) if disc_bgr else DISC_HIGHLIGHT_BGR
    img = np.full((H, W, 3), bg, np.uint8)
    # 棋盘底色略带噪声/纹理，避免差分恒零的退化
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 1.5, (H, W, 1))
    img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    rad = cell * 0.45

    def center(r, f):
        return margin + f * cell, margin + r * cell

    # 残影（画在棋子下面）
    for (r, f) in ghosts:
        cx, cy = center(r, f)
        cv2.circle(img, (int(cx), int(cy)), int(rad * 0.92), (GHOST_VALUE,) * 3, -1)

    # 提示点
    for (r, f) in hints:
        cx, cy = center(r, f)
        cv2.circle(img, (int(cx), int(cy)), int(cell * 0.10), (HINT_VALUE,) * 3, -1)

    # 棋子
    slide_from = slide[0] if slide else None
    for r in range(RANKS):
        for f in range(FILES):
            ch = screen_board[r][f]
            if ch == " ":
                continue
            if slide is not None and (r, f) == slide[1]:
                continue  # 滑行中的棋子在循环外按插值位置画
            if slide is not None and (r, f) == slide_from:
                continue  # 已离格
            cx, cy = center(r, f)
            disc = disc_lit if (r, f) in highlights else disc_normal
            ink = RED_INK_BGR if ch.isupper() else BLACK_INK_BGR
            _draw_piece(img, cx, cy, rad, ch, disc, ink)

    if slide is not None:
        (fr, ff), (tr, tf), t = slide
        ch = screen_board[tr][tf]
        if ch != " ":
            x0, y0 = center(fr, ff)
            x1, y1 = center(tr, tf)
            cx, cy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            disc = disc_lit if (tr, tf) in highlights else disc_normal
            ink = RED_INK_BGR if ch.isupper() else BLACK_INK_BGR
            _draw_piece(img, cx, cy, rad, ch, disc, ink)
    return img


def screen_to_std(board, flip):
    """屏幕坐标盘面 → 标准坐标盘面。"""
    return list(reversed(board)) if flip else list(board)


def std_to_screen(board, flip):
    """标准坐标盘面 → 屏幕坐标盘面。"""
    return list(reversed(board)) if flip else list(board)


def move_screen(board, src, dst):
    """在屏幕坐标盘面上走一步，返回新盘面（字符串列表）。"""
    rows = [list(row) for row in board]
    sr, sf = src
    dr, df = dst
    rows[dr][df] = rows[sr][sf]
    rows[sr][sf] = " "
    return ["".join(row) for row in rows]


def apply_move_std(board, move):
    """标准坐标走子（薄封装，方便测试按标准思考、屏幕渲染）。"""
    from xiangqi.moves import apply_move

    return apply_move(board, move)
