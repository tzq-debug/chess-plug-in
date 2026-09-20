from unittest import mock

from xiangqi import capture


class _Ok:
    stdout = "ok\n"


def test_grab_calls_commands():
    calls = []
    with mock.patch.object(capture, "run_hdc", side_effect=lambda args, **kw: calls.append(args) or _Ok()):
        path = capture.grab(hdc_path="hdc", remote="/data/local/tmp/x.png", local="out.png")
    assert path == "out.png"
    assert calls[0] == ["shell", "snapshot_display", "-f", "/data/local/tmp/x.png", "-t", "png"]
    assert calls[1] == ["file", "recv", "/data/local/tmp/x.png", "out.png"]


def test_device_connected_true():
    with mock.patch.object(capture, "run_hdc", return_value=_Ok()):
        assert capture.device_connected() is True
