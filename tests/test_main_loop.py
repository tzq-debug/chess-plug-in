"""主循环端到端测试：假的 grab（合成画面序列）+ 假的引擎。

验证的是「程序能不能真的跑起来」，包括：
    * 启动链路：网格精修 → 90/90 识别 → 自动定向 → 建立可信盘面
    * 一整个回合：我方走子、对方走子、轮到我就算棋、写出标注图
    * main_log.txt 里记录的死锁场景（残影/无法解析的变化）能自愈
    * 截屏失败、引擎崩溃都不会打死主循环
"""

import json
import os

import cv2
import numpy as np
import pytest

import synth
from xiangqi import capture
from xiangqi.board import STARTING_BOARD
from xiangqi.calibrate import extract_templates, rectify, save_templates
from xiangqi.main import fen_is_sane, main, validate_config

FLIP = True                                  # 用户真机：屏幕红方在上
SCREEN0 = synth.std_to_screen(STARTING_BOARD, FLIP)


# ---------------------------------------------------------------- 假部件

class ScriptedGrab:
    """按脚本返回截图路径；脚本用完后一直重复最后一张（模拟静态画面）。"""

    def __init__(self, paths):
        self.paths = list(paths)
        self.calls = 0

    def __call__(self):
        path = self.paths[min(self.calls, len(self.paths) - 1)]
        self.calls += 1
        return path


class FakeEngine:
    """UCI 引擎替身。fail_times > 0 时前几次 search 抛异常（模拟崩溃）。"""

    def __init__(self, bestmove="b2e2", fail_times=0):
        self.bestmove = bestmove
        self.fail_times = fail_times
        self.started = 0
        self.quit_called = False
        self.restarted = 0
        self.fens = []

    def start(self):
        self.started += 1

    def set_position(self, fen):
        self.fens.append(fen)

    def search(self, movetime_ms):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("引擎进程已退出")
        return {"bestmove": self.bestmove, "score": 42, "depth": 10, "pv": []}

    def is_alive(self):
        return self.fail_times == 0

    def restart(self):
        self.restarted += 1

    def quit(self):
        self.quit_called = True


# ---------------------------------------------------------------- 脚手架

def _render(tmpdir, name, std_board, **kw):
    """把标准坐标盘面渲染成屏幕坐标图片并落盘，返回路径。"""
    img = synth.render_board(synth.std_to_screen(std_board, FLIP), **kw)
    path = str(tmpdir / name)
    assert cv2.imwrite(path, img), f"写图失败: {path}"
    return path


def _config(tmpdir, templates_root=None, **over):
    """写配置文件。故意用相对路径：正常使用就是 cd 到哪都能跑，
    路径要按配置文件所在目录解析（由 resolve_paths 负责）。"""
    cfg = {
        "hdc_path": "hdc",
        "remote_path": "/data/local/tmp/x.png",
        "local_path": "shot.png",
        "board_corners": synth.canonical_corners(),
        "templates_dir": "templates",
        "engine_path": "engine/pikafish.exe",
        "player_color": "red",
        "poll_interval": 0,
        "movetime_ms": 10,
        "flip_board": True,
    }
    cfg.update(over)
    path = tmpdir / "config.json"
    path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    return str(path)


@pytest.fixture
def templates_dir(tmp_path):
    img = synth.render_board(SCREEN0)
    rect, cell, margin = rectify(img, synth.canonical_corners())
    templates = extract_templates(rect, SCREEN0, cell, margin)
    assert len(templates) == 14
    target = tmp_path / "templates"
    save_templates(templates, str(target))
    return target


def _run(cfg_path, grab, engine, tmpdir, iterations):
    return main(
        cfg_path,
        max_iterations=iterations,
        grab=grab,
        sleep=lambda _s: None,
        engine_factory=lambda: engine,
        out_path=str(tmpdir / "bestmove.png"),
    )


# ---------------------------------------------------------------- 正常回合

def test_full_round_runs_end_to_end(templates_dir, tmp_path):
    """启动 → 红走一步 → 黑走一步 → 轮到红方算棋 → 写出标注图。"""
    cfg = _config(tmp_path, templates_dir)
    std1 = synth.apply_move_std(STARTING_BOARD, ((6, 0), (5, 0)))   # 红兵进一
    std2 = synth.apply_move_std(std1, ((3, 0), (4, 0)))             # 黑卒进一
    frames = [
        _render(tmp_path, "f0.png", STARTING_BOARD),
        _render(tmp_path, "f1.png", STARTING_BOARD),
        _render(tmp_path, "f2.png", std1),
        _render(tmp_path, "f3.png", std1),
        _render(tmp_path, "f4.png", std1),
        _render(tmp_path, "f5.png", std2),
        _render(tmp_path, "f6.png", std2),
        _render(tmp_path, "f7.png", std2),
    ]
    engine = FakeEngine()
    summary = _run(cfg, ScriptedGrab(frames), engine, tmp_path, iterations=10)

    assert summary["quit_reason"] == "max_iterations"
    assert summary["flip"] is True, "屏幕红方在上应被自动识别出来"
    assert summary["grid_refined"] is True, "网格应精修成功"
    assert [m[0] for m in summary["moves"]] == ["P", "p"]
    assert summary["board"] == std2
    assert summary["side"] == "w"          # 黑方走完 → 轮到红方
    assert summary["searches"] >= 2        # 开局一次 + 黑方走子后一次
    assert (tmp_path / "bestmove.png").exists(), "没写出标注图"
    assert engine.quit_called, "退出时必须关掉引擎"


def test_screenshot_failure_does_not_kill_loop(templates_dir, tmp_path):
    """hdc 抽风时主循环要报错重试，而不是崩掉。"""
    cfg = _config(tmp_path, templates_dir)
    good = _render(tmp_path, "f0.png", STARTING_BOARD)
    calls = {"n": 0}

    def grab():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise capture.CaptureError("device offline")
        return good

    summary = _run(cfg, grab, FakeEngine(), tmp_path, iterations=6)
    assert summary["quit_reason"] == "max_iterations"
    assert summary["board"] is not None


def test_unreadable_screenshot_is_skipped(templates_dir, tmp_path):
    """截图文件损坏/为空时跳过该帧，不能拿旧图继续算。"""
    cfg = _config(tmp_path, templates_dir)
    good = _render(tmp_path, "f0.png", STARTING_BOARD)
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")
    paths = [good, str(broken), str(broken), good, good]
    summary = _run(cfg, ScriptedGrab(paths), FakeEngine(), tmp_path, iterations=6)
    assert summary["quit_reason"] == "max_iterations"
    assert summary["board"] == STARTING_BOARD


def test_engine_crash_is_retried(templates_dir, tmp_path):
    """引擎第一次要结果时崩溃 → 重启后重试，不放弃整个程序。"""
    cfg = _config(tmp_path, templates_dir)
    frames = [_render(tmp_path, "f0.png", STARTING_BOARD)] * 4
    engine = FakeEngine(fail_times=1)
    summary = _run(cfg, ScriptedGrab(frames), engine, tmp_path, iterations=5)
    assert engine.restarted >= 1
    assert summary["quit_reason"] == "max_iterations"


# ---------------------------------------------------------------- 死锁自愈

def test_residue_scene_resyncs_instead_of_hanging(templates_dir, tmp_path):
    """main_log.txt 的死锁：来源格残影 + 无法配成合法走子的变化。

    旧实现在这里会永远打印「等待稳定」。新实现必须（有限帧内）重新识别
    并采用识别结果，然后继续正常循环。
    """
    cfg = _config(tmp_path, templates_dir)
    screen = [list(r) for r in synth.std_to_screen(STARTING_BOARD, FLIP)]
    # 屏幕第 6 行 = 标准第 3 行（黑卒行）；抹掉三个卒，无法用任何合法走子解释
    for f in (0, 2, 4):
        screen[6][f] = " "
    broken = ["".join(r) for r in screen]
    good = _render(tmp_path, "f0.png", STARTING_BOARD)
    bad = str(tmp_path / "bad.png")
    assert cv2.imwrite(bad, synth.render_board(broken))

    frames = [good, good] + [bad] * 20
    summary = _run(cfg, ScriptedGrab(frames), FakeEngine(), tmp_path, iterations=25)

    assert summary["quit_reason"] == "max_iterations", "主循环卡住了"
    assert summary["resyncs"] >= 1, "没有触发重同步"
    # 采用识别结果后，盘面应与画面一致（三个黑卒消失）
    assert summary["board"][3][0] == " "
    assert summary["board"][3][2] == " "
    assert summary["board"][3][4] == " "


def test_tracking_survives_ghost_residue(templates_dir, tmp_path):
    """JJ象棋 在来源格留残影时仍能识别走子（旧实现死循环的根因）。"""
    cfg = _config(tmp_path, templates_dir)
    std1 = synth.apply_move_std(STARTING_BOARD, ((6, 0), (5, 0)))
    ghost_cell = (9 - 6, 0) if FLIP else (6, 0)        # 红兵原格在屏幕上的行
    frames = [
        _render(tmp_path, "f0.png", STARTING_BOARD),
        _render(tmp_path, "f1.png", STARTING_BOARD),
        _render(tmp_path, "f2.png", std1, ghosts=[ghost_cell]),
    ]
    frames += [frames[-1]] * 4
    summary = _run(cfg, ScriptedGrab(frames), FakeEngine(), tmp_path, iterations=8)
    assert [m[0] for m in summary["moves"]] == ["P"]
    assert summary["moves"][0][1] == (6, 0) and summary["moves"][0][2] == (5, 0)


# ---------------------------------------------------------------- 配置校验

def test_validate_config_reports_missing_keys():
    with pytest.raises(SystemExit) as e:
        validate_config({"hdc_path": "hdc"})
    assert "缺少字段" in str(e.value)


def test_validate_config_rejects_placeholder_corners():
    cfg = {
        "hdc_path": "hdc",
        "remote_path": "r",
        "local_path": "l",
        "board_corners": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "templates_dir": "t",
        "engine_path": "e",
    }
    with pytest.raises(SystemExit) as e:
        validate_config(cfg)
    assert "校准" in str(e.value)


def test_validate_config_rejects_bad_player_side():
    """player_side 拼错必须报错：否则会静默退回颜色判断，用户以为没生效。"""
    cfg = {
        "hdc_path": "hdc",
        "remote_path": "r",
        "local_path": "l",
        "board_corners": [[1, 1], [2, 1], [2, 2], [1, 2]],
        "templates_dir": "t",
        "engine_path": "e",
        "player_side": "down",
    }
    with pytest.raises(SystemExit) as e:
        validate_config(cfg)
    assert "player_side" in str(e.value)
    assert validate_config(dict(cfg, player_side="bottom"))["player_side"] == "bottom"


def test_fen_is_sane():
    from xiangqi.board import board_to_fen

    assert fen_is_sane(board_to_fen(STARTING_BOARD, "w"))
    assert not fen_is_sane("3k5/9/9/9/9/9/9/9/9/9 w - - 0 1")        # 缺帅
    too_many = "3k5/9/9/9/9/9/9/9/9/PPPPPPPPK w - - 0 1"             # 9 个兵
    assert not fen_is_sane(too_many)


def test_resolve_paths_relative_to_config_file(tmp_path):
    """相对路径按配置文件所在目录解析，从任何工作目录启动都能跑。"""
    from xiangqi.main import resolve_paths

    cfg = {
        "templates_dir": "templates",
        "engine_path": "engine/pikafish.exe",
        "local_path": "shot.png",
        "hdc_path": "hdc",              # 命令名，不能拼成路径
    }
    out = resolve_paths(dict(cfg), str(tmp_path / "config.json"))
    assert out["templates_dir"] == os.path.join(str(tmp_path), "templates")
    assert out["engine_path"] == os.path.join(str(tmp_path), "engine", "pikafish.exe")
    assert out["local_path"] == os.path.join(str(tmp_path), "shot.png")
    assert out["hdc_path"] == "hdc"


def test_missing_templates_dir_gives_friendly_error(templates_dir, tmp_path):
    """模板目录不存在时应提示怎么生成，而不是抛 FileNotFoundError。"""
    cfg = _config(tmp_path, templates_dir="no_such_dir")
    with pytest.raises(SystemExit) as e:
        _run(cfg, ScriptedGrab([_render(tmp_path, "f0.png", STARTING_BOARD)]), FakeEngine(), tmp_path, 2)
    assert "retemplate" in str(e.value)


# ---------------------------------------------------------------- 我方是谁

def test_resolve_my_side_by_screen_position():
    """「截屏下方是我方」与红黑无关，取决于屏幕方向。"""
    from xiangqi.main import resolve_my_side

    # 红方在上（flip=True）→ 下方是黑方
    assert resolve_my_side({"player_side": "bottom"}, True) == "b"
    assert resolve_my_side({"player_side": "top"}, True) == "w"
    # 红方在下（flip=False）→ 下方是红方
    assert resolve_my_side({"player_side": "bottom"}, False) == "w"
    assert resolve_my_side({"player_side": "top"}, False) == "b"


def test_resolve_my_side_position_wins_over_color():
    """player_side 与 player_color 冲突时以位置为准（位置是玩家感知到的事实）。"""
    from xiangqi.main import resolve_my_side

    assert resolve_my_side({"player_side": "bottom", "player_color": "red"}, True) == "b"


def test_resolve_my_side_falls_back_to_color_then_default():
    from xiangqi.main import resolve_my_side

    assert resolve_my_side({"player_color": "red"}, True) == "w"
    assert resolve_my_side({"player_color": "black"}, False) == "b"
    # 两者都没配：默认截屏下方是我方
    assert resolve_my_side({}, True) == "b"
    assert resolve_my_side({}, False) == "w"


def test_player_side_bottom_waits_for_opponent_then_searches(templates_dir, tmp_path):
    """我方是截屏下方（红方在上 → 我方黑方）：开局轮到红方时不算棋，
    红方走完才轮到我方、这时才该算棋。"""
    cfg = _config(tmp_path, player_side="bottom")   # 同时留着 player_color=red 验证优先级
    std1 = synth.apply_move_std(STARTING_BOARD, ((6, 0), (5, 0)))   # 红兵进一（对方）
    frames = [
        _render(tmp_path, "f0.png", STARTING_BOARD),
        _render(tmp_path, "f1.png", std1),
        _render(tmp_path, "f2.png", std1),
        _render(tmp_path, "f3.png", std1),
    ]
    summary = _run(cfg, ScriptedGrab(frames), FakeEngine(bestmove="b7c7"), tmp_path, iterations=6)
    assert summary["flip"] is True, "屏幕红方在上"
    assert summary["my_side"] == "b", "截屏下方是黑方，不能被 player_color=red 覆盖"
    assert [m[0] for m in summary["moves"]] == ["P"]
    assert summary["side"] == "b"
    assert summary["searches"] == 1, "只该在轮到我方（黑方）时算一次"


def test_engine_move_for_wrong_side_is_not_drawn(templates_dir, tmp_path):
    """引擎返回不属于走子方的走法（比如把对方的炮走出来）时不能画箭头。

    这条防线能挡住「FEN 拼错 / 引擎状态残留」导致的自信错箭头。
    """
    cfg = _config(tmp_path)
    frames = [_render(tmp_path, "f0.png", STARTING_BOARD)] * 3
    engine = FakeEngine(bestmove="b7c7")     # 黑炮；但此刻轮到红方
    summary = _run(cfg, ScriptedGrab(frames), engine, tmp_path, iterations=3)
    assert summary["searches"] == 1          # 确实算了
    assert not (tmp_path / "bestmove.png").exists(), "不该画出错误走法"


def test_engine_illegal_move_is_not_drawn(templates_dir, tmp_path):
    """走子方自己的棋子但走法违规（兵一次冲三格）同样不画。"""
    cfg = _config(tmp_path)
    frames = [_render(tmp_path, "f0.png", STARTING_BOARD)] * 3
    # a3a6：红兵 (6,0) 一次冲三格 —— 起点是走子方的子，但走法违规
    engine = FakeEngine(bestmove="a3a6")
    summary = _run(cfg, ScriptedGrab(frames), engine, tmp_path, iterations=3)
    assert summary["searches"] == 1
    assert not (tmp_path / "bestmove.png").exists()


def test_check_engine_move_accepts_legal_move():
    from xiangqi.main import check_engine_move

    assert check_engine_move(STARTING_BOARD, "w", "b2e2") is None      # 炮八平五
    assert check_engine_move(STARTING_BOARD, "w", "b7c7") is not None  # 黑炮，不是红方走子
    assert check_engine_move(STARTING_BOARD, "w", "a3a6") is not None  # 红兵冲三格
    assert check_engine_move(STARTING_BOARD, "w", "zzzz") is not None  # 越界/无法解析


def test_capture_size_from_config():
    """按标定尺寸 * capture_scale 算设备端抓图尺寸；不配则走原生分辨率。"""
    from xiangqi.main import capture_size

    assert capture_size({"screen_size": [1256, 2760], "capture_scale": 0.5}) == (628, 1380)
    assert capture_size({"screen_size": [1256, 2760], "capture_scale": 1.0}) is None
    assert capture_size({"screen_size": [1256, 2760]}) is None
    assert capture_size({"capture_scale": 0.5}) is None


def test_orientation_midgame_uses_king_rows(templates_dir):
    """中局（匹配不足 85）时按帅位定向，而不是靠与开局比对。"""
    from xiangqi.board import flip_board
    from xiangqi.calibrate import load_templates
    from xiangqi.main import detect_orientation

    # 中局残局：红帅跑到屏幕上方的「错误」位置也不能被当成开局
    mid = [
        "r        ",
        "         ",
        "         ",
        "         ",
        "         ",
        "         ",
        "         ",
        "         ",
        "         ",
        "    K    ",
    ]
    screen = flip_board(mid)            # 红方在上：屏幕上第 0 行是红帅
    img = synth.render_board(screen)
    rect, cell, margin = rectify(img, synth.canonical_corners())
    std, flip, matches = detect_orientation(
        rect, load_templates(str(templates_dir)), cell, margin
    )
    assert matches < 85, "中局不该被判成开局"
    assert flip is True, "屏幕上第 0 行是红帅 → 红方在上"
    assert "K" in std[9], "换算成标准坐标后，红帅应在最后一行（红方底线）"
