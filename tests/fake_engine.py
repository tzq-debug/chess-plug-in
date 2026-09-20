"""一个说 UCI 协议的假引擎，用于测试 PikafishEngine。"""
import sys

for line in sys.stdin:
    cmd = line.strip()
    if cmd == "uci":
        print("id name fake")
        print("id author test")
        print("uciok")
        sys.stdout.flush()
    elif cmd == "isready":
        print("readyok")
        sys.stdout.flush()
    elif cmd.startswith("position"):
        pass
    elif cmd.startswith("go"):
        print("info depth 10 score cp 42")
        print("bestmove b7c7 ponder e2e2")
        sys.stdout.flush()
    elif cmd == "quit":
        break
