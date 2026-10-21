"""走子追踪：占空判定 + 走法合法性校验 + 失联自动重同步。

解决旧实现的死循环问题：旧逻辑只有在「恰好 1 对 1」或「恰好 2 对 2」的
占/空变化时才接受走子，其它一律「等待稳定」且永不刷新基准帧。JJ象棋 在
来源格留下的半透明走子残影、常驻高亮等会让画面变化永远不收敛，追踪就此卡死。

本模块的策略：
    1. 逐帧算「整盘占空图」：每格取中心区域（0.28*cell）的中位亮度，
       再用迭代两类中点对全盘 90 格自适应定分界。棋子是实心圆盘（中心亮），
       棋盘底色更深，两者天然双峰，因此不依赖皮肤配色、也没有写死的阈值。
       用中位数是为了抗格线——棋盘线正好穿过交叉点中心，会把均值拉高。
    2. 「离格」= 盘面说这格有子、画面上却没有了。只有离格才可能是走子：
       高亮、走子提示点、计时动画都不会让棋子消失，天然被排除，
       不需要任何像素差阈值。没有离格 → 吸收基准或直接 idle。
    3. 落点靠两条约束唯一确定：必须是该棋子的**合法**落点，且画面上
       那个格子**现在确实有子**。普通走子和吃子都满足（吃子落点本来就有子），
       而提示点所在格仍是空的，自动排除——吃子因此不需要识别像素差异。
    4. 离格模式稳定连续多帧后才尝试配对，支持同一间隔内的多步走子；
       每一对都做完整合法性校验（行棋规则 + 不送将 + 将帅照面）。
    5. 配不出唯一合法走子 → 累计到 RESYNC_POLLS 帧后发 need_resync，由
       调用方重新识别盘面后调 resync()——永不卡死。

坐标约定：
    rect（矫正图）是屏幕坐标（与手机画面一致）；
    board（可信盘面）是标准坐标（红方在下，rank 9）。
    flip=True 表示屏幕上红方在上，标准行号 = 9 - 屏幕行号。
"""

from collections import deque

import cv2
import numpy as np

from . import moves
from .calibrate import FILES, RANKS
from .occupancy import OCCUPANCY_FRAC, OCCUPANCY_TOL, occupancy_map
from .occupancy import center_luminance as _center_luminance
from .occupancy import occupancy_threshold as _occupancy_threshold

# ---- 占/空判定 ----
# 实现见 occupancy.py（识别也共用同一套判定）。要点：棋子是实心圆盘，
# 中心比棋盘底色亮，每帧对 90 格做迭代两类中点自适应分界，不写死阈值。

# ---- 吃子落点的「看得见」判定 ----
# 占空图只分得清空/有子、分不清颜色，于是「马从这里能吃到两处卒」这类局面
# 会同时给出两条合法解，只能判歧义去重同步（真机第 13 回合实际踩到：
# 马 (5,3) 吃 (3,2) 的卒，与「吃 (3,4) 的卒」都合法；前者换成了红马，
# 后者画面上什么都没变）。吃子必然把子换掉（字不同、多半颜色也不同），
# 所以「该格与基准帧相比有没有变化」是可靠判据。
# 度量用「格内平均颜色差」而不是逐像素差：每帧的网格精修有 1~2 像素抖动，
# 逐像素差在没变的格子上也能到 26~59，而平均颜色差对这种抖动不敏感。
# 实测（真机前后两帧，矫正图 140px 格）：
#   未变格 0.5~4.4   真吃子(卒→红马) 101   空位被占 209   离格 138~158
CAPTURE_FRAC = 0.30        # 采样半径 = 0.30 * cell
CAPTURE_MIN_CHANGE = 12.0  # 吃子格的最小平均颜色差（未变格实测 ≤4.4）

# ---- 稳定性与重同步 ----
STABLE_POLLS = 2           # 同一占/空模式连续这么多帧才采纳
RESYNC_POLLS = 6           # 连续这么多帧无法解析 → 请求重新识别
NOISE_ABSORB_POLLS = 20    # 长期只有噪声候选 → 直接吸收为新基准
MAX_INFER_NODES = 20000    # 走法配对搜索的节点上限（防止候选格多时指数爆炸）

# 盘面里允许出现的字符（识别失败会产生 "?" 等，重同步时一律拒绝）
LEGAL_CELL_CHARS = set(" KABNCRPkabncrp")
RECENT_FRAMES = 4          # 保留最近几帧矫正图，供重新识别时多帧投票


class TrackEvent:
    """一次 update 的结果。

    kind:
        'idle'        画面与基准一致，无事发生
        'moved'       采纳了走子，moves = [(棋子, 来源std, 落点std), ...]
        'settled'     纯噪声变化已吸收为新基准帧
        'unstable'    有候选格但暂无法解析（动画中/噪声/待稳定）
        'need_resync' 长时间无法解析，调用方应重新识别盘面并调 resync()
    detail: 调试信息（候选格、来源/落点、亮度等）。
    """

    __slots__ = ("kind", "moves", "board_before", "detail")

    def __init__(self, kind, moves=(), board_before=None, detail=None):
        self.kind = kind
        self.moves = list(moves)
        self.board_before = board_before
        self.detail = detail or {}

    def __repr__(self):
        return f"<TrackEvent {self.kind} moves={self.moves}>"


class BoardTracker:
    """基于画面差分的可信盘面追踪器（抗高亮/抗走子残影/失联自愈）。"""

    def __init__(self, board, flip, cell, margin, side_to_move="w"):
        self.board = [row[:] for row in board]   # 标准坐标可信盘面
        self.flip = bool(flip)                    # 屏幕红方在上？
        self.cell = cell
        self.margin = margin
        self.side_to_move = side_to_move
        self.stable_rect = None                   # 基准帧（屏幕坐标）
        self._mask = None                         # 残影位（屏幕坐标）
        self._last_threshold = 0.0                # 最近一帧的自适应占空分界（调试用）
        self._recent = deque(maxlen=RECENT_FRAMES)
        self._last_sig = None
        self._sig_count = 0
        self._unstable = 0
        self._noise = 0
        self.frames = 0

    # ---- 坐标换算 ----
    def to_std(self, r, f):
        """屏幕坐标 → 标准坐标。"""
        return (RANKS - 1 - r, f) if self.flip else (r, f)

    def to_screen(self, sr, sf):
        """标准坐标 → 屏幕坐标。"""
        return (RANKS - 1 - sr, sf) if self.flip else (sr, sf)

    # ---- 对外接口 ----
    def _occupancy_map(self, rect):
        """整盘「每格是否真有棋子」的布尔表（屏幕坐标）。

        实现在 occupancy 模块（识别也共用同一套判定），这里只记下本帧分界
        供 --debug 打印。
        """
        lum = np.empty((RANKS, FILES), dtype=np.float64)
        for r in range(RANKS):
            for f in range(FILES):
                lum[r, f] = _center_luminance(rect, self.cell, self.margin, r, f)
        self._last_threshold = _occupancy_threshold(lum)
        return occupancy_map(rect, self.cell, self.margin)

    def _change_map(self, rect):
        """每格「与基准帧相比的平均绝对差」（屏幕坐标），基准无效时返回 None。

        只用于判「这格上的子有没有被换掉」。没有发生走子的格子像素完全相同，
        所以不需要精细阈值——真吃子的差值比未变格大两个数量级。
        """
        if self.stable_rect is None or self.stable_rect.shape != rect.shape:
            return None
        k = 2 * max(2, int(round(CAPTURE_FRAC * self.cell))) + 1
        now = cv2.blur(rect.astype(np.float32), (k, k))
        old = cv2.blur(self.stable_rect.astype(np.float32), (k, k))
        out = np.zeros((RANKS, FILES), dtype=np.float32)
        for r in range(RANKS):
            for f in range(FILES):
                x = int(round(self.margin + f * self.cell))
                y = int(round(self.margin + r * self.cell))
                out[r, f] = float(np.linalg.norm(now[y, x] - old[y, x]))
        return out

    def update(self, rect):
        """喂入一帧矫正图（屏幕坐标），返回 TrackEvent。"""
        self.frames += 1
        self._recent.append(rect.copy())
        if self.stable_rect is None:
            self.stable_rect = rect.copy()
            return TrackEvent("idle")

        # 整盘占空一次算完：90 格中心亮度 + 自适应分界（与皮肤配色无关）
        occ = self._occupancy_map(rect)

        # 「离格」= 盘面说这格有子、画面上却没有了。只有离格才可能是走子：
        # 高亮/提示点/计时动画都不会让棋子消失，天然被排除，无需像素差阈值。
        srcs = []
        gone, arrived = [], []
        for r in range(RANKS):
            for f in range(FILES):
                sr, sf = self.to_std(r, f)
                was_occ = self.board[sr][sf] != " "
                now_occ = occ[r][f]
                if was_occ and not now_occ:
                    srcs.append((sr, sf))
                elif not was_occ and now_occ:
                    arrived.append((sr, sf))
                elif was_occ and now_occ:
                    gone.append((sr, sf))
        srcs.sort()
        detail = {
            "srcs": srcs,
            "arrived": arrived,     # 盘面说空、画面有子（走子落点或误判）
            "threshold": round(self._last_threshold, 1),
        }

        sig = (tuple(srcs), tuple(arrived))
        if sig == self._last_sig:
            self._sig_count += 1
        else:
            self._last_sig = sig
            self._sig_count = 1

        if not srcs:
            if not arrived:
                # 盘面与画面完全一致：没有棋子离开原位，也没有凭空多出的子
                self._reset_polls()
                return TrackEvent("idle", detail=detail)
            # 只有「多出」没有「少掉」：真实走子必然一少一多，只多不少说明
            # 识别出了问题——典型是上一手落点的白色光点压在原位，让「帅离开
            # 原位」这一半看不出来（真机实测：帅横移一步，程序只看到新位置多了
            # 一个子，当成噪声吸收掉，之后这颗子再动也检不出来）。
            # 不要再吸收：吸收会把基准帧和盘面永久错开。累积到阈值走整体重同步。
            self._unstable += 1
            detail["reason"] = "只多不少（疑似落点光点压住原位）"
            if self._unstable >= RESYNC_POLLS:
                self._unstable = 0
                return TrackEvent("need_resync", detail=detail)
            return TrackEvent("unstable", detail=detail)

        if self._sig_count < STABLE_POLLS:
            return TrackEvent("unstable", detail=detail)

        seq = self._infer_moves(srcs, occ, arrived, self._change_map(rect))
        if seq is None:
            self._unstable += 1
            detail["reason"] = "无法解析为合法走子"
            if self._unstable >= RESYNC_POLLS:
                self._unstable = 0
                return TrackEvent("need_resync", detail=detail)
            return TrackEvent("unstable", detail=detail)

        # 采纳走子
        board_before = [row[:] for row in self.board]
        board = [list(row) for row in self.board]   # 可变副本（字符串不可改）
        accepted = []
        for piece, (sr, sf), (dr, df) in seq:
            board[sr][sf] = " "
            board[dr][df] = piece
            accepted.append((piece, (sr, sf), (dr, df)))
        self.board = ["".join(row) for row in board]
        # 走子方由「实际移动的棋子颜色」决定：万一先后跟踪漂移，自我纠正
        self.side_to_move = moves.enemy_of(moves.side_of(accepted[-1][0]))
        # 残影位 = 最后一次走子的来源格（屏幕坐标）
        self._mask = self.to_screen(*accepted[-1][1])
        self.stable_rect = rect.copy()
        self._reset_polls()
        return TrackEvent("moved", accepted, board_before, detail)

    def set_board(self, board, rect):
        """硬重置：直接采用新盘面并刷新基准帧（失联后的整体重同步）。"""
        self.board = [row[:] for row in board]
        self.stable_rect = rect.copy()
        self._mask = None
        self._reset_polls()

    def resync(self, recognized, rect):
        """用重新识别的盘面（标准坐标）修复追踪状态。

        返回 TrackEvent：
            差异为空            → 只刷新基准帧（'settled'）
            差异恰为一步合法走子 → 按走子采纳（'moved'，差分漏检的补救）
            其它                → 整体采用识别结果（'resynced'，需调用方告警）

        残影位特判：识别可能把走子残留的淡影认成棋子，此时用占空图纠正
        ——该格画面上并不亮（没有实心圆盘），就按空位处理。
        """
        recognized = [row[:] for row in recognized]
        occ = self._occupancy_map(rect)
        diff_src, diff_dst = [], []
        for r in range(RANKS):
            for f in range(FILES):
                a, b = self.board[r][f], recognized[r][f]
                if a == b:
                    continue
                if self._mask is not None and self.to_screen(r, f) == self._mask:
                    if a == " " and b != " ":
                        # 残影位由空变有：画面上该格并没有实心棋子 → 不信识别
                        mr, mf = self._mask
                        if not occ[mr][mf]:
                            recognized[r] = recognized[r][:f] + " " + recognized[r][f + 1 :]
                            continue
                if a != " " and b == " ":
                    diff_src.append((r, f))
                elif a == " " and b != " ":
                    diff_dst.append((r, f))
                else:
                    # 棋子种类都变了（极罕见）：无法按走子解释，整体采用
                    diff_src.append((r, f))
                    diff_dst.append((r, f))

        if not diff_src and not diff_dst:
            self.stable_rect = rect.copy()
            self._mask = None
            self._reset_polls()
            return TrackEvent("settled", detail={"resync": "无差异，仅刷新基准"})

        if len(diff_src) == 1 and len(diff_dst) == 1:
            piece = self.board[diff_src[0][0]][diff_src[0][1]]
            move = (diff_src[0], diff_dst[0])
            if piece != " " and moves.is_legal(self.board, moves.side_of(piece), move):
                board_before = [row[:] for row in self.board]
                self.board = moves.apply_move(self.board, move)
                self.side_to_move = moves.enemy_of(moves.side_of(piece))
                self._mask = self.to_screen(*diff_src[0])
                self.stable_rect = rect.copy()
                self._reset_polls()
                return TrackEvent(
                    "moved", [(piece, diff_src[0], diff_dst[0])], board_before,
                    detail={"resync": "差分漏检的走子，由识别补救"},
                )

        # 整体采用识别结果（带基本 sanity 检查）
        flat = "".join(recognized)
        if any(ch not in LEGAL_CELL_CHARS for ch in flat):
            return TrackEvent(
                "unstable",
                detail={"resync": "识别结果含非法字符（识别失败），放弃采用，保留原盘面"},
            )
        if flat.count("K") != 1 or flat.count("k") != 1:
            return TrackEvent(
                "unstable",
                detail={"resync": "识别结果将/帅数量异常，放弃采用，保留原盘面"},
            )
        board_before = [row[:] for row in self.board]
        self.set_board(recognized, rect)
        return TrackEvent("resynced", detail={"resync": "整体采用识别结果", "board_before": board_before})

    # ---- 内部 ----
    def _reset_polls(self):
        self._last_sig = None
        self._sig_count = 0
        self._unstable = 0
        self._noise = 0

    def _infer_moves(self, srcs, occ, arrived=None, changes=None):
        """把「离格」配成合法走子序列；无法唯一确定时返回 None。

        判据：落点必须是该棋子**合法**的落点，且画面上那个格子**现在确实
        有一颗子**（occ=True）。这两条一起把候选压到唯一：
          * 普通走子：目标格走之前是空的，走完有子 → occ=True；
          * 吃子：目标格本来就有子，走完仍是子 → 也是 occ=True
            （所以吃子不需要任何像素差异，像素差极小也不影响）；
          * 走子提示点/高亮：格子依然是空的 → occ=False，自动排除。
        落点**允许重复**：兑子时「先吃过去、再被吃回来」两手的落点是同一格
        （真机实测：红炮隔黑车打黑炮，黑车立刻吃回，离格两个、落点只有一个，
        禁止复用就会被误判成无法解析，只能靠重同步补救并丢掉走子记录）。
        合法性校验天然保证第二次落上去的是敌方棋子（即吃子），不会出现
        「自己的两子叠在一格」。
        「凭空多出的子」必须有人落上去：占空图只分得清空/有子，分不清颜色，
        于是「黑车沿 4 路直下吃掉还摆在那里的红仕」也能凑出一套合法解（真机实测
        第 10 回合：黑车 (1,3) 退回 (1,1)，另有 (1,3)->(9,3) 吃仕这条假解，
        结果判成歧义）。要求 arrived 中每一格都是某个落点，假解就没有落点去
        解释 (1,1) 上多出来的车，自动被排除。
        吃子落点必须「看得见变化」：占空图分不清颜色，同一只马往往能合法地
        吃到相邻两处的兵，两条解都满足「落点有子」，只能判歧义。而吃子必然把
        子换掉，画面上那格一定变了；没被吃的格子像素完全相同（实测 ≤0.45）。
        因此对「落点原本有子」的走法要求 changes[dst] 不低于 CAPTURE_MIN_CHANGE，
        假解（吃一个根本没动过的兵）自动出局。
        若仍有多种解释并存 → 判歧义返回 None，交给重同步，绝不猜。
        """
        results = []
        need = set(arrived or ())     # 画面上凭空多出子的格子，必须被用上
        seen = set()          # 同一套走法的不同先后顺序算同一种解释
        budget = [MAX_INFER_NODES]

        def backtrack(remaining, board, acc):
            if len(results) > 1 or budget[0] <= 0:
                return  # 已确定歧义 / 预算耗尽：都判「无法确定」，不做猜测
            budget[0] -= 1
            if not remaining:
                if need - {dst for _, _, dst in acc}:
                    return          # 有格子凭空多了子却没人落上去 → 不是这套走子
                key = tuple(sorted(acc))
                if key not in seen:
                    seen.add(key)
                    results.append(list(acc))
                return
            # 逐个「谁先走」地试，而不是按格子顺序硬排：兑子时先后是唯一
            # 可行顺序（先吃的走不了、被吃的才动得起来），硬排会漏解。
            for idx, src in enumerate(remaining):
                piece = board[src[0]][src[1]]
                if piece == " ":
                    continue
                side = moves.side_of(piece)
                for s, dst in moves.generate_pseudo_moves(board, side):
                    if s != src:
                        continue
                    dr, df = self.to_screen(*dst)
                    if not occ[dr][df]:
                        continue      # 该格画面上没有子 → 不是这一步的落点
                    if not moves.is_legal(board, side, (src, dst)):
                        continue
                    acc.append((piece, src, dst))
                    backtrack(
                        remaining[:idx] + remaining[idx + 1:],
                        moves.apply_move(board, (src, dst)),
                        acc,
                    )
                    acc.pop()

        backtrack(list(srcs), [row[:] for row in self.board], [])
        if len(results) == 1:
            return self._order_moves(results[0])
        if results:
            # 多解：用「吃子必须看得见变化」筛（占空图分不清颜色，同一只马常能
            # 合法地吃到相邻两处兵，而只有真被吃的那个格子换了子）。这只是
            # 优先级而非硬条件——筛不出来就按原来的判歧义处理，绝不错杀。
            kept = [sol for sol in results if self._captures_visible(sol, changes)]
            if len(kept) == 1:
                return self._order_moves(kept[0])
        return None  # 无解或多种解释 → 无法确定

    def _captures_visible(self, seq, changes):
        """这套走子里的每处吃子，落点格子是否真的看得出换了子。"""
        if changes is None:
            return False
        for _, _, dst in seq:
            if self.board[dst[0]][dst[1]] == " ":
                continue          # 走到原本空着的格子，不算吃子
            dr, df = self.to_screen(*dst)
            if changes[dr][df] < CAPTURE_MIN_CHANGE:
                return False
        return True

    def _order_moves(self, seq):
        """多步走子按先行方交替排序（单步原样返回）。

        合法对局走子交替进行；同一采集间隔内可能漏看到多步。以追踪器当前
        的 side_to_move 为第一步，交替排列，最后一步的颜色决定新的走子方。
        """
        if len(seq) <= 1:
            return seq
        first_side = self.side_to_move
        by_side = {"w": [m for m in seq if moves.side_of(m[0]) == "w"],
                   "b": [m for m in seq if moves.side_of(m[0]) == "b"]}
        if len(by_side[first_side]) != (len(seq) + 1) // 2:
            return seq  # 颜色分布不符合交替，原样返回
        ordered = []
        side = first_side
        for _ in range(len(seq)):
            if not by_side[side]:
                return seq
            ordered.append(by_side[side].pop(0))
            side = moves.enemy_of(side)
        return ordered

    def recent_frames(self):
        return list(self._recent)
