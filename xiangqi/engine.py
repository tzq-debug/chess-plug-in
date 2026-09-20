"""Pikafish 引擎封装（UCI 协议）。"""

import os
import subprocess
import threading


class EngineError(Exception):
    pass


def parse_bestmove(line):
    """从 'bestmove b7c7 ponder e2e2' 解析最佳走法字符串。"""
    parts = line.strip().split()
    if len(parts) < 2 or parts[0] != "bestmove":
        raise ValueError(f"不是 bestmove 行: {line!r}")
    return parts[1]


def parse_score(line):
    """从 'info ... score cp 120 ...' 解析评估分（cp 为厘分，1 = 1 分）。"""
    parts = line.strip().split()
    if "score" not in parts:
        return None
    idx = parts.index("score")
    if idx + 2 >= len(parts):
        return None
    kind, val = parts[idx + 1], parts[idx + 2]
    if kind == "cp":
        return int(val)
    if kind == "mate":
        return 100000 if int(val) > 0 else -100000
    return None


class PikafishEngine:
    def __init__(self, engine_path):
        self.engine_path = engine_path
        self.proc = None
        self.lock = threading.Lock()

    def start(self):
        # 用绝对路径启动：项目目录含中文时，相对路径会让 Windows 的
        # CreateProcess 找不到可执行文件（WinError 2）。
        cmd = [os.path.abspath(str(p)) for p in self.engine_path]
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._send("uci")
        self._read_until("uciok")
        self._send("isready")
        self._read_until("readyok")

    def _send(self, cmd):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def _read_until(self, token):
        for line in self.proc.stdout:
            if line.strip() == token:
                return
        raise EngineError(f"引擎未返回 {token}")

    def set_position(self, fen):
        self._send(f"position fen {fen}")

    def search(self, movetime_ms=3000):
        with self.lock:
            self._send(f"go movetime {movetime_ms}")
            bestmove = None
            score = None
            for line in self.proc.stdout:
                s = line.strip()
                if s.startswith("bestmove"):
                    bestmove = parse_bestmove(s)
                    break
                sc = parse_score(s)
                if sc is not None:
                    score = sc
            return {"bestmove": bestmove, "score": score}

    def quit(self):
        if self.proc:
            try:
                self._send("quit")
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()
            self.proc = None
