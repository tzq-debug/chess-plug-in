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
    eng.quit()
