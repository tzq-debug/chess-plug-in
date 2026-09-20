"""hdc 截屏封装。"""

import subprocess


def run_hdc(args, hdc_path="hdc", timeout=10):
    return subprocess.run(
        [hdc_path] + list(args), capture_output=True, text=True, timeout=timeout
    )


def device_connected(hdc_path="hdc"):
    r = run_hdc(["list", "targets"], hdc_path=hdc_path)
    return bool(r.stdout.strip())


def grab(hdc_path="hdc", remote="/data/local/tmp/xq.png", local="screenshot.png"):
    run_hdc(["shell", "snapshot_display", "-f", remote, "-t", "png"], hdc_path=hdc_path)
    run_hdc(["file", "recv", remote, local], hdc_path=hdc_path)
    return local
