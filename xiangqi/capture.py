"""hdc 截屏封装。"""

import os
import subprocess


class CaptureError(Exception):
    """截屏/拉取失败。"""


def run_hdc(args, hdc_path="hdc", timeout=10):
    return subprocess.run(
        [hdc_path] + list(args), capture_output=True, text=True, timeout=timeout
    )


def device_connected(hdc_path="hdc"):
    """是否有已连接的设备。

    hdc 本身不可用（找不到文件等）时返回 False 而不抛异常。
    注意：没有设备时 `hdc list targets` 会打印 "[Empty]"，不能当成有设备。
    """
    try:
        r = run_hdc(["list", "targets"], hdc_path=hdc_path, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    lines = [
        line.strip()
        for line in (r.stdout or "").splitlines()
        if line.strip() and line.strip() != "[Empty]"
    ]
    return bool(lines)


def grab(hdc_path="hdc", remote="/data/local/tmp/xq.png", local="screenshot.png", size=None):
    """截屏并拉回本地。任何一步失败都抛 CaptureError，避免主循环误用上一张旧图。

    size=(宽, 高) 时让设备端按该尺寸生成截图。实测 PNG 编码远慢于传输：
    1256x2760 要 ~3.0s，降到 628x1380 只要 ~1.6s（识别精度不受影响，因为
    rectify 会把棋盘归一化到固定 cell）。调用方需按同一比例换算 board_corners。
    """
    snap_args = ["shell", "snapshot_display", "-f", remote, "-t", "png"]
    if size:
        snap_args += ["-w", str(int(size[0])), "-h", str(int(size[1]))]
    try:
        r1 = run_hdc(snap_args, hdc_path=hdc_path)
        r2 = run_hdc(["file", "recv", remote, local], hdc_path=hdc_path)
    except subprocess.TimeoutExpired as e:
        raise CaptureError(f"hdc 命令超时: {e}") from e
    except OSError as e:
        raise CaptureError(f"无法执行 hdc（路径是否正确？）: {e}") from e
    if r1.returncode != 0:
        raise CaptureError(f"snapshot_display 失败: {(r1.stderr or r1.stdout).strip()[:200]}")
    if r2.returncode != 0:
        raise CaptureError(f"file recv 失败: {(r2.stderr or r2.stdout).strip()[:200]}")
    if not os.path.exists(local) or os.path.getsize(local) == 0:
        raise CaptureError(f"本地截图无效: {local}")
    return local
