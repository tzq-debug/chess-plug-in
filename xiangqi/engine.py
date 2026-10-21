"""Pikafish 引擎封装（UCI 协议）。"""

import os
import subprocess
import threading


class EngineError(Exception):
    pass


NNUE_NAME = "pikafish.nnue"


def _engine_cwd(exe_path):
    """返回 NNUE 权重所在目录（作为引擎进程的工作目录）；找不到返回 None。

    Pikafish 默认 `EvalFile = pikafish.nnue`，按工作目录解析。工程里权重
    常放在可执行文件旁边或上一级（engine/ 与项目根），因此依次尝试：
    可执行文件目录 → 其上一级 → 当前工作目录。
    """
    exe_dir = os.path.dirname(exe_path)
    for cand in (exe_dir, os.path.dirname(exe_dir), os.getcwd()):
        if cand and os.path.isfile(os.path.join(cand, NNUE_NAME)):
            return cand
    return None


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
    def __init__(self, engine_path, threads=1, hash_mb=16):
        # 允许传单个可执行文件路径或 [可执行文件, 参数...]
        if isinstance(engine_path, str):
            engine_path = [engine_path]
        self.engine_path = list(engine_path)
        # 搜得越深，同分/近分走法的抖动越小。Pikafish 单线程 5 秒常只能到
        # 20 层左右，实测同一局面会在一对「差 20 分」的近等价走法间来回跳；
        # 多线程把同样 5 秒推到更深，结论明显稳定（24 核机器上 3/3 一致）。
        self.threads = int(threads or 1)
        self.hash_mb = int(hash_mb or 16)
        self.proc = None
        self.lock = threading.Lock()

    def start(self):
        # 用绝对路径启动：项目目录含中文时，相对路径会让 Windows 的
        # CreateProcess 找不到可执行文件（WinError 2）。
        cmd = [os.path.abspath(str(p)) for p in self.engine_path]
        # Pikafish 的 NNUE 权重（pikafish.nnue）是相对工作目录解析的，
        # 从别的目录启动就加载不到网络。这里向上找到权重所在目录作为 cwd。
        self.proc = subprocess.Popen(
            cmd,
            cwd=_engine_cwd(cmd[0]),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._send("uci")
        self._read_until("uciok")
        if self.threads > 1:
            self._send(f"setoption name Threads value {self.threads}")
        if self.hash_mb:
            self._send(f"setoption name Hash value {self.hash_mb}")
        self._send("isready")
        self._read_until("readyok")

    def is_alive(self):
        return self.proc is not None and self.proc.poll() is None

    def restart(self):
        """引擎崩溃后重启（先尽力退出旧进程）。"""
        if self.proc is not None:
            try:
                self.proc.kill()
            except Exception:
                pass
            self.proc = None
        self.start()

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
            if bestmove is None:
                # 输出流提前结束 = 引擎进程死了。必须抛异常，让调用方重启，
                # 否则会一直「没有最佳走法」而永远不恢复。
                raise EngineError("引擎未返回 bestmove（进程可能已崩溃）")
            return {"bestmove": bestmove, "score": score}

    def quit(self):
        if self.proc:
            try:
                self._send("quit")
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()
            self.proc = None
