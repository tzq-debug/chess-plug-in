import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xiangqi.engine import parse_bestmove, parse_score, PikafishEngine


def test_parse_bestmove():
    assert parse_bestmove("bestmove b7c7 ponder e2e2") == "b7c7"


def test_parse_score_cp():
    assert parse_score("info depth 18 score cp 120 nodes 1000") == 120


def test_parse_score_mate():
    assert parse_score("info depth 5 score mate 2") == 100000
    assert parse_score("info depth 5 score mate -1") == -100000


def test_engine_integration():
    fake = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_engine.py")
    eng = PikafishEngine([sys.executable, fake])
    eng.start()
    eng.set_position("rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1")
    result = eng.search(100)
    assert result["bestmove"] == "b7c7"
    assert result["score"] == 42
    assert eng.is_alive()
    eng.quit()


def test_engine_accepts_plain_string_path():
    """只传一个可执行文件路径也要能启动（旧实现会把字符串按字符拆开）。"""
    fake = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_engine.py")
    eng = PikafishEngine(sys.executable)
    assert eng.engine_path == [sys.executable]
    eng2 = PikafishEngine([sys.executable, fake])
    assert eng2.engine_path == [sys.executable, fake]


def test_search_raises_when_engine_dies():
    """引擎中途崩溃（输出流 EOF）必须抛 EngineError，让主循环能重启它。"""
    fake = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_engine.py")
    eng = PikafishEngine([sys.executable, fake])
    eng.start()
    eng.proc.kill()
    eng.proc.wait(timeout=5)
    try:
        eng.search(50)
    except Exception as e:  # noqa: BLE001
        assert type(e).__name__ in ("EngineError", "BrokenPipeError", "OSError", "ValueError")
    else:
        raise AssertionError("引擎已崩溃但 search() 没有报错")
    eng.quit()


def test_engine_cwd_finds_nnue(tmp_path, monkeypatch):
    """Pikafish 的 NNUE 权重按工作目录解析，要从可执行文件往上找。"""
    from xiangqi.engine import NNUE_NAME, _engine_cwd

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setattr(os, "getcwd", lambda: str(elsewhere))
    eng_dir = tmp_path / "engine"
    eng_dir.mkdir()
    exe = eng_dir / "pikafish.exe"
    exe.write_bytes(b"")

    assert _engine_cwd(str(exe)) is None          # 到处都没有权重

    (eng_dir / NNUE_NAME).write_bytes(b"")        # 权重就在 exe 旁边
    assert os.path.normcase(_engine_cwd(str(exe))) == os.path.normcase(str(eng_dir))

    (eng_dir / NNUE_NAME).unlink()
    (tmp_path / NNUE_NAME).write_bytes(b"")       # 权重在上一级（本工程的实际布局）
    assert os.path.normcase(_engine_cwd(str(exe))) == os.path.normcase(str(tmp_path))
