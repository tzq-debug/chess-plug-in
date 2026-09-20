"""判先后：对比相邻两帧头像计时器区域的像素差。"""

import numpy as np


def region_diff(img_a, img_b, region):
    """两帧在 region=(x,y,w,h) 内的平均绝对像素差。"""
    x, y, w, h = region
    a = img_a[y : y + h, x : x + w].astype(np.float32)
    b = img_b[y : y + h, x : x + w].astype(np.float32)
    return float(np.mean(np.abs(a - b)))


def active_side(diff_self, diff_opponent, threshold=5.0):
    """根据两个区域的 diff 判断谁在走。返回 'self' / 'opponent' / None。"""
    self_active = diff_self > threshold
    opp_active = diff_opponent > threshold
    if self_active and opp_active:
        return None  # 都在变，可能整体动画，判不出
    if self_active:
        return "self"
    if opp_active:
        return "opponent"
    return None
