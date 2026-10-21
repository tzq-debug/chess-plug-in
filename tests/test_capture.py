"""capture 模块：hdc 截屏封装（成功路径 + 各类失败必须抛 CaptureError）。"""

import subprocess
from unittest import mock

import pytest

from xiangqi import capture


class _Ok:
    returncode = 0
    stdout = "ok\n"
    stderr = ""


class _Fail:
    returncode = 1
    stdout = ""
    stderr = "error: device not found"


@pytest.fixture
def fake_file(tmp_path):
    """让 grab() 的本地文件存在性检查指向一个真实临时文件。"""
    target = tmp_path / "out.png"
    target.write_bytes(b"png-bytes")
    with mock.patch.object(capture.os.path, "exists", side_effect=lambda p: str(p) == str(target)), \
         mock.patch.object(capture.os.path, "getsize", side_effect=lambda p: 9):
        yield str(target)


def test_grab_calls_commands(fake_file):
    calls = []

    def _run(args, **kw):
        calls.append(args)
        return _Ok()

    with mock.patch.object(capture, "run_hdc", side_effect=_run):
        path = capture.grab(
            hdc_path="hdc", remote="/data/local/tmp/x.png", local=fake_file
        )
    assert path == fake_file
    assert calls[0] == ["shell", "snapshot_display", "-f", "/data/local/tmp/x.png", "-t", "png"]
    assert calls[1] == ["file", "recv", "/data/local/tmp/x.png", fake_file]


def test_grab_raises_when_snapshot_fails(fake_file):
    with mock.patch.object(capture, "run_hdc", return_value=_Fail()):
        with pytest.raises(capture.CaptureError, match="snapshot_display"):
            capture.grab(local=fake_file)


def test_grab_raises_when_recv_fails(fake_file):
    with mock.patch.object(capture, "run_hdc", side_effect=[_Ok(), _Fail()]):
        with pytest.raises(capture.CaptureError, match="file recv"):
            capture.grab(local=fake_file)


def test_grab_raises_when_local_missing(tmp_path):
    """拉取命令成功但本地文件不存在 → 不能静默返回旧路径。"""
    missing = str(tmp_path / "nope.png")
    with mock.patch.object(capture, "run_hdc", return_value=_Ok()):
        with pytest.raises(capture.CaptureError, match="本地截图无效"):
            capture.grab(local=missing)


def test_grab_raises_on_timeout(tmp_path):
    with mock.patch.object(
        capture, "run_hdc", side_effect=subprocess.TimeoutExpired(cmd="hdc", timeout=10)
    ):
        with pytest.raises(capture.CaptureError, match="超时"):
            capture.grab(local=str(tmp_path / "x.png"))


def test_grab_raises_on_missing_hdc(tmp_path):
    with mock.patch.object(capture, "run_hdc", side_effect=OSError("no such file")):
        with pytest.raises(capture.CaptureError, match="无法执行 hdc"):
            capture.grab(local=str(tmp_path / "x.png"))


def test_device_connected_true():
    with mock.patch.object(capture, "run_hdc", return_value=_Ok()):
        assert capture.device_connected() is True


def test_device_connected_false_when_empty():
    class _Empty:
        stdout = "\n"

    with mock.patch.object(capture, "run_hdc", return_value=_Empty()):
        assert capture.device_connected() is False


def test_device_connected_false_on_empty_marker():
    """hdc 没有设备时打印 "[Empty]"，不能被当成有设备。"""

    class _EmptyMarker:
        stdout = "[Empty]\n"

    with mock.patch.object(capture, "run_hdc", return_value=_EmptyMarker()):
        assert capture.device_connected() is False


def test_device_connected_true_with_serial():
    class _Serial:
        stdout = "FMR0223B30000345\tdevice\n"

    with mock.patch.object(capture, "run_hdc", return_value=_Serial()):
        assert capture.device_connected() is True


def test_device_connected_false_on_oserror():
    """hdc 不存在时不能把异常抛给主循环。"""
    with mock.patch.object(capture, "run_hdc", side_effect=OSError("boom")):
        assert capture.device_connected() is False


def test_device_connected_false_on_timeout():
    with mock.patch.object(
        capture, "run_hdc", side_effect=subprocess.TimeoutExpired(cmd="hdc", timeout=5)
    ):
        assert capture.device_connected() is False


def test_grab_passes_scale_size(fake_file):
    """传 size 时让设备端按该尺寸生成（PNG 编码耗时随分辨率下降）。"""
    calls = []

    def _run(args, **kw):
        calls.append(args)
        return _Ok()

    with mock.patch.object(capture, "run_hdc", side_effect=_run):
        capture.grab(remote="/data/local/tmp/x.png", local=fake_file, size=(628, 1380))
    assert calls[0] == [
        "shell", "snapshot_display", "-f", "/data/local/tmp/x.png", "-t", "png",
        "-w", "628", "-h", "1380",
    ]
