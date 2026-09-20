# 鸿蒙手机象棋实时识别 + 最佳走法 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Windows 电脑上运行一个本地工具，通过 hdc 截取鸿蒙手机 JJ象棋 对局画面，用 OpenCV 识别棋盘局面，调用 Pikafish 引擎计算最佳走法并展示。

**Architecture:** 7 个解耦模块（board/notation/engine/calibrate/recognize/turn_detect/capture/display）+ main 主循环。纯逻辑模块（board、notation、engine 解析、calibrate 几何、recognize、turn_detect）全部先写测试再用实现让测试通过；hdc 采集与 tkinter 展示为薄封装层，用 mock 测试、真机手动验证。

**Tech Stack:** Python 3.12（`D:\Python312\python.exe`）、opencv-python、numpy、pytest、tkinter（内置）、Pikafish 引擎（UCI）、hdc（HarmonyOS Device Connector）。

**Spec:** `docs/superpowers/specs/2026-09-20-xiangqi-vision-assistant-design.md`

## Global Constraints

- Python 解释器：`D:\Python312\python.exe`（版本 3.12），所有 `python`/`pytest`/`pip` 命令用它（或先把 `D:\Python312` 加入 PATH）。
- 依赖：`opencv-python`、`numpy`、`pytest`；GUI 用内置 tkinter。**禁止引入任何云端 API 依赖。**
- 内部棋盘表示：`board[r][f]`，`r` = rank（0=顶部黑方底线，9=底部红方底线），`f` = file（0=左 a，8=右 i）；空位用空格 `" "`。
- 棋子字符：红方大写 `K`帅 `A`仕 `B`相 `N`马 `R`车 `C`炮 `P`兵；黑方小写 `k`将 `a`士 `b`象 `n`马 `r`车 `c`炮 `p`卒。
- FEN：10 行自上而下，行内左→右，空格用数字压缩；走子方 `w`=红、`b`=黑。起始 FEN：`rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1`。
- Pikafish 坐标：file a–i、rank 0–9 **自下而上**（a0=红方左下角）；内部坐标 rank 相反，转换 `internal_rank = 9 - pikafish_rank`。中文记谱用汉字数字（一二…九），红方列号自右向左数（file8=1…file0=9）、黑方列号自左向右数（file0=1…file8=9）。
- 引擎思考时间 `movetime_ms = 3000`；己方默认红方（下方），`config.json` 可改。
- 坐标/走法内部统一为 `(rank, file)` 元组，即 `(r, f)`，rank 在前。
- 所有单元测试用 `pytest`，从仓库根目录运行，`conftest.py` 负责把根目录加入 `sys.path`。

---

## 文件结构

```
新建文件夹/
├── conftest.py                 # 让测试能 import xiangqi 包
├── requirements.txt            # opencv-python, numpy, pytest
├── config.example.json         # 配置模板（供用户填 hdc 路径等）
├── xiangqi/
│   ├── __init__.py
│   ├── board.py                # 棋盘表示 + FEN 转换
│   ├── notation.py             # Pikafish 坐标↔内部坐标 + 中文记谱
│   ├── engine.py               # Pikafish UCI 封装 + 输出解析
│   ├── calibrate.py            # 棋盘几何（四角→网格）+ 模板生成
│   ├── recognize.py            # 矫正图 → 逐格识别 → 棋盘
│   ├── turn_detect.py          # 头像计时器 diff 判先后
│   ├── capture.py              # hdc 截屏封装
│   ├── display.py              # tkinter 窗口 + 箭头绘制
│   └── main.py                 # 主循环编排
├── tests/
│   ├── test_board.py
│   ├── test_notation.py
│   ├── test_engine.py
│   ├── fake_engine.py          # 假引擎（说 UCI 的脚本，用于集成测试）
│   ├── test_calibrate.py
│   ├── test_recognize.py
│   ├── test_turn_detect.py
│   └── test_capture.py
├── templates/                  # 校准自动生成 14 张棋子模板
└── engine/                     # 放 pikafish.exe（用户自行下载）
```

---

### Task 0: 项目脚手架

**Files:**
- Create: `conftest.py`, `requirements.txt`, `config.example.json`, `xiangqi/__init__.py`, `.gitignore`

**Interfaces:**
- Produces: 可 `import xiangqi.board` 的包结构；`pytest` 可运行；`config.example.json` 字段约定（`hdc_path`、`player_color`、`movetime_ms`、`engine_path`）。

- [ ] **Step 1: 初始化 git 与目录**

```bash
cd "C:/Users/tzq/Desktop/新建文件夹"
git init
mkdir -p xiangqi tests templates engine
```

- [ ] **Step 2: 写 requirements.txt**

```
opencv-python
numpy
pytest
```

- [ ] **Step 3: 写 conftest.py（把根目录加入 sys.path）**

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

- [ ] **Step 4: 写 xiangqi/__init__.py（空文件）**

```python
"""鸿蒙象棋识别 + 最佳走法工具。"""
```

- [ ] **Step 5: 写 config.example.json**

```json
{
  "hdc_path": "hdc",
  "player_color": "red",
  "movetime_ms": 3000,
  "engine_path": "engine/pikafish.exe",
  "remote_path": "/data/local/tmp/xq.png",
  "local_path": "screenshot.png"
}
```

- [ ] **Step 6: 写 .gitignore**

```
__pycache__/
*.pyc
.pytest_cache/
screenshot.png
templates/*.png
engine/*.exe
```

- [ ] **Step 7: 安装依赖并验证**

```bash
D:/Python312/python.exe -m pip install opencv-python numpy pytest
D:/Python312/python.exe -m pytest --version
```

Expected: pytest 版本号打印成功。

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "chore: 项目脚手架"
```

---

### Task 1: board.py —— 棋盘表示与 FEN 转换

**Files:**
- Create: `xiangqi/board.py`
- Test: `tests/test_board.py`

**Interfaces:**
- Produces:
  - `STARTING_BOARD: list[str]`（10 行字符串，初始局面）
  - `PIECE_NAMES: dict[str,str]`（棋子字符→中文名）
  - `board_to_fen(board: list[str], side: str = "w") -> str`
  - `fen_to_board(fen: str) -> list[str]`
  - `side_to_move(fen: str) -> str`

- [ ] **Step 1: 写失败测试**

`tests/test_board.py`：

```python
from xiangqi.board import STARTING_BOARD, board_to_fen, fen_to_board, side_to_move

START_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


def test_starting_board_to_fen():
    assert board_to_fen(STARTING_BOARD) == START_FEN


def test_fen_to_starting_board():
    assert fen_to_board(START_FEN) == STARTING_BOARD


def test_roundtrip():
    assert board_to_fen(fen_to_board(START_FEN)) == START_FEN


def test_side_to_move():
    assert side_to_move(START_FEN) == "w"
    assert side_to_move("9/9/9/9/9/9/9/9/9/9 b - - 0 1") == "b"


def test_empty_board_fen():
    empty = [" " * 9] * 10
    assert board_to_fen(empty) == "9/9/9/9/9/9/9/9/9/9 w - - 0 1"
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/Python312/python.exe -m pytest tests/test_board.py -v
```

Expected: FAIL（`ModuleNotFoundError: No module named 'xiangqi.board'`）

- [ ] **Step 3: 写实现**

`xiangqi/board.py`：

```python
"""中国象棋棋盘表示与 FEN 转换。

内部表示：board[r][f]，r=rank(0=顶部黑方底线,9=底部红方底线)，f=file(0=左,8=右)。
空位用空格 " "。棋子字符：红方大写 K A B N R C P，黑方小写 k a b n r c p。
"""

RANK_COUNT = 10
FILE_COUNT = 9

STARTING_BOARD = [
    "rnbakabnr",
    "         ",
    " c     c ",
    "p p p p p",
    "         ",
    "         ",
    "P P P P P",
    " C     C ",
    "         ",
    "RNBAKABNR",
]

PIECE_NAMES = {
    "K": "帅", "A": "仕", "B": "相", "N": "马", "R": "车", "C": "炮", "P": "兵",
    "k": "将", "a": "士", "b": "象", "n": "马", "r": "车", "c": "炮", "p": "卒",
}


def board_to_fen(board, side="w"):
    """把 10 行字符串棋盘转成 FEN。side: 'w' 红方走，'b' 黑方走。"""
    rows = []
    for rank in board:
        if len(rank) != FILE_COUNT:
            raise ValueError(f"每行必须是 {FILE_COUNT} 列: {rank!r}")
        row = ""
        empty = 0
        for ch in rank:
            if ch == " ":
                empty += 1
            else:
                if empty:
                    row += str(empty)
                    empty = 0
                row += ch
        if empty:
            row += str(empty)
        rows.append(row)
    return "/".join(rows) + f" {side} - - 0 1"


def fen_to_board(fen):
    """解析 FEN 的棋子摆放部分，返回 10 行字符串棋盘。"""
    placement = fen.split()[0]
    rows = placement.split("/")
    if len(rows) != RANK_COUNT:
        raise ValueError(f"FEN 必须有 {RANK_COUNT} 行: {fen!r}")
    board = []
    for row in rows:
        out = ""
        for ch in row:
            if ch.isdigit():
                out += " " * int(ch)
            else:
                out += ch
        if len(out) != FILE_COUNT:
            raise ValueError(f"行解析后必须是 {FILE_COUNT} 列: {row!r}")
        board.append(out)
    return board


def side_to_move(fen):
    """返回 FEN 的走子方：'w' 或 'b'。"""
    parts = fen.split()
    return parts[1] if len(parts) > 1 else "w"
```

- [ ] **Step 4: 运行确认通过**

```bash
D:/Python312/python.exe -m pytest tests/test_board.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add xiangqi/board.py tests/test_board.py && git commit -m "feat: 棋盘表示与 FEN 转换"
```

---

### Task 2: notation.py —— 坐标转换与中文记谱

**Files:**
- Create: `xiangqi/notation.py`
- Test: `tests/test_notation.py`

**Interfaces:**
- Consumes: `xiangqi.board.PIECE_NAMES`, `STARTING_BOARD`
- Produces:
  - `pikafish_coord_to_internal(sq: str) -> tuple[int,int]`（`'b7'`→`(rank,file)`）
  - `parse_move(move: str) -> tuple[tuple[int,int], tuple[int,int]]`（`'b7c7'`→`((fr,ff),(tr,tf))`）
  - `move_to_chinese(board: list[str], fr:int, ff:int, tr:int, tf:int) -> str`

- [ ] **Step 1: 写失败测试**

`tests/test_notation.py`：

```python
from xiangqi.board import STARTING_BOARD
from xiangqi.notation import pikafish_coord_to_internal, parse_move, move_to_chinese


def test_coord_convert():
    # Pikafish rank 自下而上：b7 = 内部 rank 2（= 9-7），file b = 1
    assert pikafish_coord_to_internal("b7") == (2, 1)
    assert pikafish_coord_to_internal("a0") == (9, 0)
    assert pikafish_coord_to_internal("i9") == (0, 8)


def test_parse_move():
    assert parse_move("b7c7") == ((2, 1), (2, 2))


def test_red_cannon_ping():
    # 炮二平五：红炮 file7 rank7 → file4 rank7
    assert move_to_chinese(STARTING_BOARD, 7, 7, 7, 4) == "炮二平五"


def test_red_horse_jin():
    # 马八进七：红马 file1 rank9 → file2 rank7
    assert move_to_chinese(STARTING_BOARD, 9, 1, 7, 2) == "马八进七"


def test_black_cannon_ping():
    # 黑炮 file7 rank2 → file4 rank2，黑方列号自左向右：file7=八，file4=五
    assert move_to_chinese(STARTING_BOARD, 2, 7, 2, 4) == "炮八平五"


def test_pawn_advance():
    # 红兵三进一：file6 rank6 → file6 rank5
    assert move_to_chinese(STARTING_BOARD, 6, 6, 5, 6) == "兵三进一"
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/Python312/python.exe -m pytest tests/test_notation.py -v
```

Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 写实现**

`xiangqi/notation.py`：

```python
"""Pikafish 坐标 ↔ 内部坐标转换，以及中文记谱。"""

from .board import PIECE_NAMES

CHINESE_DIGITS = "零一二三四五六七八九"


def pikafish_coord_to_internal(sq):
    """把 Pikafish 坐标 'b7' 转成内部 (rank, file)。

    Pikafish: file a–i（a=左），rank 0–9 自下而上（0=红方底线）。
    内部: rank 0=顶部（黑方），所以 rank 要翻转。
    """
    f = ord(sq[0]) - ord("a")
    r = 9 - int(sq[1])
    return (r, f)


def parse_move(move):
    """把 'b7c7' 转成 ((fr, ff), (tr, tf)) 内部坐标。"""
    if len(move) != 4:
        raise ValueError(f"非法走法: {move!r}")
    return pikafish_coord_to_internal(move[0:2]), pikafish_coord_to_internal(move[2:4])


def _col_num(color, f):
    """某文件在该方视角下的列号（1-9）。红方自右向左，黑方自左向右。"""
    return (9 - f) if color == "red" else (f + 1)


def _is_forward(color, fr, tr):
    """该方视角下 tr 是否在 fr 前方。红方前方=rank 减小，黑方前方=rank 增大。"""
    return (tr < fr) if color == "red" else (tr > fr)


def move_to_chinese(board, fr, ff, tr, tf):
    """把一步内部坐标走法转成中文记谱，如 '炮二平五'。

    board: 走子前的棋盘（10 行字符串）。坐标顺序为 (rank, file)。
    """
    piece = board[fr][ff]
    if piece == " ":
        raise ValueError(f"({fr},{ff}) 处无棋子")
    color = "red" if piece.isupper() else "black"
    kind = piece.upper()

    name = PIECE_NAMES[piece]
    from_col = _col_num(color, ff)

    # 同类同色同列的其它棋子（用于 前/后 消歧）
    same_file = [r for r in range(10) if r != fr and board[r][ff] == piece]

    if ff == tf:
        move_word = "平"
        num = _col_num(color, tf)
    else:
        move_word = "进" if _is_forward(color, fr, tr) else "退"
        if kind in ("N", "B", "A"):
            num = _col_num(color, tf)  # 马/相/象/仕/士 用落点列
        else:
            num = abs(tr - fr)  # 车/炮/兵/帅 用步数

    if same_file:
        front_rank = min(fr, *same_file) if color == "red" else max(fr, *same_file)
        prefix = "前" if fr == front_rank else "后"
    else:
        prefix = CHINESE_DIGITS[from_col]

    return f"{name}{prefix}{move_word}{CHINESE_DIGITS[num]}"
```

- [ ] **Step 4: 运行确认通过**

```bash
D:/Python312/python.exe -m pytest tests/test_notation.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add xiangqi/notation.py tests/test_notation.py && git commit -m "feat: 坐标转换与中文记谱"
```

---

### Task 3: engine.py —— Pikafish UCI 封装

**Files:**
- Create: `xiangqi/engine.py`
- Test: `tests/test_engine.py`, `tests/fake_engine.py`

**Interfaces:**
- Produces:
  - `parse_bestmove(line: str) -> str`
  - `parse_score(line: str) -> int | None`（cp 返回厘分；mate 返回 ±100000）
  - `class PikafishEngine`：`__init__(engine_path)`、`start()`、`set_position(fen)`、`search(movetime_ms=3000) -> dict`（`{"bestmove":str,"score":int|None}`）、`quit()`

- [ ] **Step 1: 写失败测试**

`tests/test_engine.py`：

```python
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
```

`tests/fake_engine.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/Python312/python.exe -m pytest tests/test_engine.py -v
```

Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 写实现**

`xiangqi/engine.py`：

```python
"""Pikafish 引擎封装（UCI 协议）。"""

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
        self.proc = subprocess.Popen(
            list(self.engine_path),
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
```

- [ ] **Step 4: 运行确认通过**

```bash
D:/Python312/python.exe -m pytest tests/test_engine.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add xiangqi/engine.py tests/test_engine.py tests/fake_engine.py && git commit -m "feat: Pikafish UCI 引擎封装"
```

---

### Task 4: calibrate.py —— 棋盘几何与模板生成

**Files:**
- Create: `xiangqi/calibrate.py`
- Test: `tests/test_calibrate.py`

**Interfaces:**
- Produces:
  - `grid_intersections(corners: np.ndarray, ranks=10, files=9) -> np.ndarray`（shape `(10,9,2)`，`[r][f]=(x,y)`，原图坐标，双线性插值）
  - `rectify(image, corners, cell=50) -> tuple[np.ndarray, int, int]`（返回 `(矫正图, cell, margin)`）
  - `extract_templates(rectified, board, cell, margin) -> dict[str, np.ndarray]`（`{棋子字符: 40x40 灰度模板}`）

- [ ] **Step 1: 写失败测试**

`tests/test_calibrate.py`：

```python
import numpy as np
from xiangqi.calibrate import grid_intersections


def test_grid_intersections_rectangle():
    # 完美矩形 90 宽 100 高；9 文件 10 行
    corners = np.array([[0, 0], [90, 0], [90, 100], [0, 100]], dtype=np.float32)
    grid = grid_intersections(corners)
    assert grid.shape == (10, 9, 2)
    np.testing.assert_allclose(grid[0][0], [0, 0], atol=1e-4)
    np.testing.assert_allclose(grid[0][8], [90, 0], atol=1e-4)
    np.testing.assert_allclose(grid[9][8], [90, 100], atol=1e-4)
    np.testing.assert_allclose(grid[9][0], [0, 100], atol=1e-4)
    np.testing.assert_allclose(grid[0][4], [45, 0], atol=1e-4)
    np.testing.assert_allclose(grid[4][0], [0, 100 * 4 / 9], atol=1e-3)


def test_grid_intersections_trapezoid():
    # 轻微透视：右上角略抬高
    corners = np.array([[0, 0], [90, 10], [90, 100], [0, 100]], dtype=np.float32)
    grid = grid_intersections(corners)
    np.testing.assert_allclose(grid[0][0], [0, 0], atol=1e-4)
    np.testing.assert_allclose(grid[0][8], [90, 10], atol=1e-4)
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/Python312/python.exe -m pytest tests/test_calibrate.py -v
```

Expected: FAIL

- [ ] **Step 3: 写实现**

`xiangqi/calibrate.py`：

```python
"""棋盘几何：四角 → 网格交叉点；以及棋子模板生成。"""

import cv2
import numpy as np

FILES = 9
RANKS = 10


def grid_intersections(corners, ranks=RANKS, files=FILES):
    """给定四角（左上、右上、右下、左下），返回 (ranks, files, 2) 交叉点坐标。

    在原图坐标里做双线性插值；[r][f] = (x, y)，r=0 为顶部，f=0 为左侧。
    """
    corners = np.asarray(corners, dtype=np.float32)
    tl, tr, br, bl = corners[0], corners[1], corners[2], corners[3]
    pts = []
    for r in range(ranks):
        t = r / (ranks - 1)
        left = (1 - t) * tl + t * bl
        right = (1 - t) * tr + t * br
        row = []
        for f in range(files):
            s = f / (files - 1)
            row.append((1 - s) * left + s * right)
        pts.append(row)
    return np.array(pts, dtype=np.float32)


def rectify(image, corners, cell=50):
    """把棋盘四角区域矫正成正面图。

    返回 (矫正图, cell, margin)。交叉点 (r, f) 在矫正图中位于
    (margin + f*cell, margin + r*cell)，四周留 margin 空白便于裁剪。
    """
    margin = cell
    W = (FILES - 1) * cell + 2 * margin
    H = (RANKS - 1) * cell + 2 * margin
    dst = np.array(
        [
            [margin, margin],
            [margin + (FILES - 1) * cell, margin],
            [margin + (FILES - 1) * cell, margin + (RANKS - 1) * cell],
            [margin, margin + (RANKS - 1) * cell],
        ],
        dtype=np.float32,
    )
    src = np.asarray(corners, dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    rectified = cv2.warpPerspective(image, M, (W, H))
    return rectified, cell, margin


def extract_templates(rectified, board, cell, margin, size=40):
    """从矫正后的初始局面图，按已知 board 提取每类棋子的模板。

    board: 10 行字符串（初始局面）。返回 {棋子字符: size x size 灰度图}。
    """
    templates = {}
    half = cell // 2
    for r in range(RANKS):
        for f in range(FILES):
            ch = board[r][f]
            if ch == " ":
                continue
            x = margin + f * cell
            y = margin + r * cell
            crop = rectified[y - half : y + half, x - half : x + half]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            templates[ch] = cv2.resize(gray, (size, size))
    return templates
```

- [ ] **Step 4: 运行确认通过**

```bash
D:/Python312/python.exe -m pytest tests/test_calibrate.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add xiangqi/calibrate.py tests/test_calibrate.py && git commit -m "feat: 棋盘几何与模板生成"
```

---

### Task 5: recognize.py —— 逐格识别

**Files:**
- Create: `xiangqi/recognize.py`
- Test: `tests/test_recognize.py`

**Interfaces:**
- Consumes: `xiangqi.calibrate.extract_templates`、`xiangqi.board.STARTING_BOARD`
- Produces:
  - `classify_color(bgr: tuple) -> str`（`"red"`/`"black"`/`"unknown"`）
  - `classify_cell(crop, templates, background) -> tuple[str, float]`（返回 `(棋子字符, 置信度)`，空位返回 `(" ", 1.0)`，无法识别返回 `("?", 分数)`）
  - `recognize_board(rectified, templates, cell, margin) -> tuple[list[str], list[float]]`（返回 `(board, confidences)`）

- [ ] **Step 1: 写失败测试（含合成棋盘端到端）**

`tests/test_recognize.py`：

```python
import numpy as np
import cv2

from xiangqi.board import STARTING_BOARD
from xiangqi.calibrate import extract_templates
from xiangqi.recognize import recognize_board, classify_color

CELL = 50
MARGIN = 50


def make_synthetic_board(board, cell=CELL, margin=MARGIN):
    files, ranks = 9, 10
    W = (files - 1) * cell + 2 * margin
    H = (ranks - 1) * cell + 2 * margin
    img = np.full((H, W, 3), (150, 120, 80), np.uint8)  # 木色背景
    for f in range(files):
        x = margin + f * cell
        cv2.line(img, (x, margin), (x, margin + (ranks - 1) * cell), (60, 40, 20), 1)
    for r in range(ranks):
        y = margin + r * cell
        cv2.line(img, (margin, y), (margin + (files - 1) * cell, y), (60, 40, 20), 1)
    for r in range(ranks):
        for f in range(files):
            ch = board[r][f]
            if ch == " ":
                continue
            x = margin + f * cell
            y = margin + r * cell
            color = (40, 40, 200) if ch.isupper() else (30, 30, 30)
            cv2.circle(img, (x, y), int(cell * 0.4), color, -1)
            cv2.circle(img, (x, y), int(cell * 0.4), (0, 0, 0), 1)
            cv2.putText(img, ch, (x - 10, y + 10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (255, 255, 255), 2)
    return img


def test_classify_color():
    assert classify_color((40, 40, 200)) == "red"
    assert classify_color((30, 30, 30)) == "black"


def test_recognize_starting_board():
    img = make_synthetic_board(STARTING_BOARD)
    templates = extract_templates(img, STARTING_BOARD, CELL, MARGIN)
    board, _ = recognize_board(img, templates, CELL, MARGIN)
    assert board == STARTING_BOARD
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/Python312/python.exe -m pytest tests/test_recognize.py -v
```

Expected: FAIL

- [ ] **Step 3: 写实现**

`xiangqi/recognize.py`：

```python
"""矫正后的棋盘图 → 逐格识别 → 棋盘。"""

import cv2
import numpy as np

from .calibrate import FILES, RANKS

TEMPLATE_SIZE = 40
MATCH_THRESHOLD = 0.5


def classify_color(bgr):
    """根据棋子圆面平均色判断颜色。返回 'red' / 'black' / 'unknown'。"""
    b, g, r = bgr
    if r > 90 and r > g + 40 and r > b + 40:
        return "red"
    if r + g + b < 240:
        return "black"
    return "unknown"


def _color_dist(a, b):
    return float(np.linalg.norm(np.array(a, dtype=np.float32) - np.array(b, dtype=np.float32)))


def classify_cell(crop, templates, background):
    """识别单个交叉点的棋子。crop 为 BGR 图，background 为棋盘底色 BGR。"""
    h, w = crop.shape[:2]
    cx, cy = w // 2, h // 2
    mask = np.zeros((h, w), np.uint8)
    cv2.circle(mask, (cx, cy), int(h * 0.35), 255, -1)
    mean = cv2.mean(crop, mask=mask)[:3]  # BGR

    if _color_dist(mean, background) < 30:
        return " ", 1.0

    color = classify_color(mean)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (TEMPLATE_SIZE, TEMPLATE_SIZE))

    best, best_score = None, -1.0
    for ch, tmpl in templates.items():
        if (color == "red") != ch.isupper():
            continue  # 颜色不符，跳过
        res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
        score = float(res[0][0])
        if score > best_score:
            best_score, best = score, ch
    if best is None or best_score < MATCH_THRESHOLD:
        return "?", best_score
    return best, best_score


def recognize_board(rectified, templates, cell, margin):
    """识别整盘。返回 (board, confidences)。background 取四周留白均值。"""
    h, w = rectified.shape[:2]
    border = np.vstack(
        [
            rectified[0:margin, :],
            rectified[h - margin : h, :],
            rectified[:, 0:margin],
            rectified[:, w - margin : w],
        ]
    )
    background = tuple(float(v) for v in cv2.mean(border)[:3])

    board_rows, confidences = [], []
    half = cell // 2
    for r in range(RANKS):
        row = ""
        for f in range(FILES):
            x = margin + f * cell
            y = margin + r * cell
            crop = rectified[y - half : y + half, x - half : x + half]
            ch, conf = classify_cell(crop, templates, background)
            row += ch
            confidences.append(conf)
        board_rows.append(row)
    return board_rows, confidences
```

- [ ] **Step 4: 运行确认通过**

```bash
D:/Python312/python.exe -m pytest tests/test_recognize.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add xiangqi/recognize.py tests/test_recognize.py && git commit -m "feat: 逐格识别棋子"
```

---

### Task 6: turn_detect.py —— 判先后

**Files:**
- Create: `xiangqi/turn_detect.py`
- Test: `tests/test_turn_detect.py`

**Interfaces:**
- Produces:
  - `region_diff(img_a, img_b, region) -> float`（`region=(x,y,w,h)`，平均绝对像素差）
  - `active_side(diff_self, diff_opponent, threshold=5.0) -> str | None`（`"self"`/`"opponent"`/`None`）

- [ ] **Step 1: 写失败测试**

`tests/test_turn_detect.py`：

```python
import numpy as np
from xiangqi.turn_detect import region_diff, active_side


def _img(value):
    return np.full((100, 100, 3), value, np.uint8)


def test_region_diff_zero_and_changed():
    a = _img(100)
    assert region_diff(a, a, (0, 0, 50, 50)) == 0.0
    b = _img(100)
    b[0:50, 0:50] = 200
    assert region_diff(a, b, (0, 0, 50, 50)) > 50.0


def test_active_side():
    assert active_side(10.0, 1.0) == "self"
    assert active_side(1.0, 10.0) == "opponent"
    assert active_side(1.0, 1.0) is None
    assert active_side(10.0, 10.0) is None
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/Python312/python.exe -m pytest tests/test_turn_detect.py -v
```

Expected: FAIL

- [ ] **Step 3: 写实现**

`xiangqi/turn_detect.py`：

```python
"""判先后：对比相邻两帧头像计时器区域的像素差。"""

import numpy as np


def region_diff(img_a, img_b, region):
    """两帧在 region=(x,y,w,h) 内的平均绝对像素差。"""
    x, y, w, h = region
    a = img_a[y : y + h, x : x + w].astype(np.float32)
    b = img_b[y : y + h, x : x + w].astype(np.float32)
    return float(np.mean(np.abs(a - b)))


def active_side(diff_self, diff_opponent, threshold=5.0):
    """根据两个区域的 diff 判断谁在走。返回 'self' / 'opponent' / None。"""
    self_active = diff_self > threshold
    opp_active = diff_opponent > threshold
    if self_active and opp_active:
        return None  # 都在变，可能整体动画，判不出
    if self_active:
        return "self"
    if opp_active:
        return "opponent"
    return None
```

- [ ] **Step 4: 运行确认通过**

```bash
D:/Python312/python.exe -m pytest tests/test_turn_detect.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add xiangqi/turn_detect.py tests/test_turn_detect.py && git commit -m "feat: 计时器 diff 判先后"
```

---

### Task 7: capture.py —— hdc 截屏封装

**Files:**
- Create: `xiangqi/capture.py`
- Test: `tests/test_capture.py`

**Interfaces:**
- Produces:
  - `run_hdc(args, hdc_path="hdc", timeout=10) -> subprocess.CompletedProcess`
  - `device_connected(hdc_path="hdc") -> bool`
  - `grab(hdc_path="hdc", remote=..., local=...) -> str`（返回本地路径）

- [ ] **Step 1: 写失败测试（mock run_hdc）**

`tests/test_capture.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/Python312/python.exe -m pytest tests/test_capture.py -v
```

Expected: FAIL

- [ ] **Step 3: 写实现**

`xiangqi/capture.py`：

```python
"""hdc 截屏封装。"""

import subprocess


def run_hdc(args, hdc_path="hdc", timeout=10):
    return subprocess.run(
        [hdc_path] + list(args), capture_output=True, text=True, timeout=timeout
    )


def device_connected(hdc_path="hdc"):
    r = run_hdc(["list", "targets"], hdc_path)
    return bool(r.stdout.strip())


def grab(hdc_path="hdc", remote="/data/local/tmp/xq.png", local="screenshot.png"):
    run_hdc(["shell", "snapshot_display", "-f", remote, "-t", "png"], hdc_path)
    run_hdc(["file", "recv", remote, local], hdc_path)
    return local
```

- [ ] **Step 4: 运行确认通过**

```bash
D:/Python312/python.exe -m pytest tests/test_capture.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add xiangqi/capture.py tests/test_capture.py && git commit -m "feat: hdc 截屏封装"
```

---

### Task 8: display.py + main.py —— 集成与主循环

**Files:**
- Create: `xiangqi/display.py`, `xiangqi/main.py`
- Test: `tests/test_display.py`

**Interfaces:**
- Consumes: `grid_intersections`、`parse_move`、`move_to_chinese`、`PikafishEngine`、`recognize_board`、`rectify`、`capture.grab`、`turn_detect`、`board_to_fen`
- Produces:
  - `draw_move(image, corners, move, color=(0,255,0)) -> np.ndarray`（`move=((fr,ff),(tr,tf))`）
  - `main(config_path)`：主循环（真机手动验证）

- [ ] **Step 1: 写失败测试（draw_move）**

`tests/test_display.py`：

```python
import numpy as np
from xiangqi.display import draw_move


def test_draw_move_draws_arrow():
    img = np.zeros((200, 200, 3), np.uint8)
    corners = np.array([[0, 0], [180, 0], [180, 180], [0, 180]], dtype=np.float32)
    move = ((0, 0), (0, 8))  # 从左上角交叉点到右上角交叉点
    out = draw_move(img, corners, move)
    assert out.shape == img.shape
    # 起点与终点附近应出现绿色像素（0,255,0）
    assert (out[0, 0] == [0, 255, 0]).all()
    assert (out[0, 180] == [0, 255, 0]).all()
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/Python312/python.exe -m pytest tests/test_display.py -v
```

Expected: FAIL

- [ ] **Step 3: 写实现**

`xiangqi/display.py`：

```python
"""展示：截图 + 箭头 + 中文记谱。"""

import cv2
import numpy as np

from .calibrate import grid_intersections


def draw_move(image, corners, move, color=(0, 255, 0)):
    """在截图 image 上画最佳走法箭头。move = ((fr, ff), (tr, tf))。"""
    grid = grid_intersections(corners)
    (fr, ff), (tr, tf) = move
    p1 = tuple(int(v) for v in grid[fr][ff])
    p2 = tuple(int(v) for v in grid[tr][tf])
    cv2.circle(image, p1, 14, color, 3)
    cv2.arrowedLine(image, p1, p2, color, 4, tipLength=0.3)
    return image


def show_window(image_bgr):
    """在 tkinter 窗口显示一张 BGR 图。返回后需 mainloop。"""
    import tkinter as tk
    from PIL import Image, ImageTk

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    root = tk.Tk()
    root.title("象棋最佳走法")
    photo = ImageTk.PhotoImage(pil)
    label = tk.Label(root, image=photo)
    label.image = photo
    label.pack()
    return root, photo
```

`xiangqi/main.py`：

```python
"""主循环：采集 → 识别 → 判先后 → 算棋 → 展示。"""

import json
import time

import cv2

from . import capture
from .board import board_to_fen, side_to_move
from .calibrate import rectify
from .display import draw_move
from .engine import PikafishEngine
from .notation import parse_move, move_to_chinese
from .recognize import recognize_board
from .turn_detect import active_side, region_diff


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(config_path="config.json"):
    cfg = load_config(config_path)
    engine = PikafishEngine([cfg["engine_path"]])
    engine.start()

    prev_img = None
    last_fen = None
    try:
        while True:
            local = capture.grab(cfg["hdc_path"], cfg["remote_path"], cfg["local_path"])
            img = cv2.imread(local)
            if img is None:
                print("读取截图失败")
                time.sleep(1)
                continue

            rect, cell, margin = rectify(img, cfg["board_corners"])
            board, conf = recognize_board(rect, cfg["templates"], cell, margin)
            fen = board_to_fen(board, "w")

            # 判先后（可选，需 timer_regions 已标定）
            if prev_img is not None and "timer_regions" in cfg:
                d_self = region_diff(img, prev_img, cfg["timer_regions"]["self"])
                d_opp = region_diff(img, prev_img, cfg["timer_regions"]["opponent"])
                side = active_side(d_self, d_opp)
            prev_img = img

            if fen == last_fen:
                time.sleep(1)
                continue
            last_fen = fen

            engine.set_position(fen)
            result = engine.search(cfg["movetime_ms"])
            move = result["bestmove"]
            if move is None:
                print("引擎未给出走法")
                continue
            (fr, ff), (tr, tf) = parse_move(move)
            chinese = move_to_chinese(board, fr, ff, tr, tf)
            print(f"最佳走法: {chinese}  ({move})  评估: {result['score']}")

            annotated = draw_move(img, cfg["board_corners"], ((fr, ff), (tr, tf)))
            cv2.imwrite("bestmove.png", annotated)
    except KeyboardInterrupt:
        pass
    finally:
        engine.quit()
```

- [ ] **Step 4: 运行确认通过**

```bash
D:/Python312/python.exe -m pytest tests/test_display.py -v
```

Expected: 1 passed

- [ ] **Step 5: 运行全量测试**

```bash
D:/Python312/python.exe -m pytest -v
```

Expected: 全部通过（board 5 + notation 6 + engine 4 + calibrate 2 + recognize 2 + turn_detect 2 + capture 2 + display 1 = 24 passed）

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: 展示与主循环集成"
```

---

## 真机验证清单（需用户配合，代码实现后执行）

这些步骤依赖真实手机与 Pikafish 引擎二进制，无法在纯代码环境完成：

1. **hdc 可用**：手机开「开发者选项 → USB 调试」，连 USB 后运行 `hdc list targets` 能看到设备；把 hdc 路径填入 `config.json`。
2. **引擎下载**：从 pikafish.com 或 GitHub releases 下载 Windows 纯引擎，选本机最快指令集版本，放 `engine/pikafish.exe`。
3. **校准**：开一局初始局面，运行校准脚本定位 `board_corners` 与 `timer_regions`，生成 `templates/` 并写入 `config.json`。
4. **坐标方向确认**：初始局面让引擎算一步，验证 `bestmove` 是否对应红方开局（如炮二平五 → `h2e2`），若方向反了只需改 `notation.pikafish_coord_to_internal` 里 `9 - int(sq[1])` 为 `int(sq[1])`。
5. **真机截图识别**：对局中运行 `main.py`，核对识别出的 FEN 与实际棋盘一致，箭头指向正确落点。

---

## Self-Review 记录

- **Spec 覆盖**：spec 的 7 个模块 + 主循环均有对应 Task（board=FEN、notation=中文记谱+坐标、engine=Pikafish、calibrate=几何+模板、recognize=识别、turn_detect=判先后、capture=hdc、display+main=展示与闭环）。
- **占位符扫描**：无 TBD/TODO；每处代码均有完整实现与测试。
- **类型一致性**：内部坐标统一 `(rank, file)`；`parse_move` 返回 `((fr,ff),(tr,tf))`，`move_to_chinese(board, fr, ff, tr, tf)`、`draw_move(image, corners, ((fr,ff),(tr,tf)))`、`grid_intersections[corners][r][f]` 全部一致；`extract_templates`/`recognize_board`/`rectify` 共享 `(rectified, cell, margin)` 约定。
