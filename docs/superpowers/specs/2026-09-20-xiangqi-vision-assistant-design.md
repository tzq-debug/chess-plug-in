# 鸿蒙手机象棋实时识别 + 最佳走法 —— 设计文档

日期：2026-09-20
状态：待评审

## 1. 目标与范围

在电脑（Windows 11）上运行一个本地工具，通过 hdc 实时读取鸿蒙手机（HarmonyOS 7.0 / NEXT）上 JJ象棋 的对局画面，用纯 OpenCV 识别棋盘局面，调用免费开源引擎 Pikafish 计算最佳走法，并在电脑屏幕上展示。

**范围界定（v1）：**
- 读屏对象：鸿蒙手机上的 JJ象棋 联网对局（己方默认红方 / 棋盘下方）。
- 识别方式：纯 CV（OpenCV 模板匹配），不调用任何云端 API。
- 算棋引擎：Pikafish（UCI 协议，本地子进程）。
- 展示方式：tkinter 桌面窗口（截图 + 箭头 + 中文记谱 + 评估分）。

**不做（v1 之外）：** 摄像头拍实体棋盘、iOS、自动替你落子（只给建议不代下）。

## 2. 总体架构与数据流

```
鸿蒙手机(JJ象棋)
   │ USB
   ▼
[hdc]  snapshot_display 截屏 ──► file recv 拉回电脑
   │
   ▼
① capture  循环采集（约 1s/张）
   │
   ▼
② calibrate 一次性：检测棋盘四角 + 自动生成 14 张棋子模板
   │ (config.json + templates/)
   ▼
③ recognize 每帧识别：棋盘→90 交叉点→逐格棋子→FEN
   │
   ▼
④ turn_detect 判「轮到谁走」（头像计时器像素 diff）+ 己方颜色
   │
   ▼
⑤ engine   FEN → Pikafish → bestmove（坐标）
   │
   ▼
⑥ display  箭头 + 中文记谱（notation 转换）+ 评估分
```

主循环逻辑：
1. 每约 1 秒截屏一次 → 识别 → 得到 FEN。
2. 若 FEN 连续 N 帧（约 3 秒）不变，且「轮到己方」→ 调用引擎算最佳走法，缓存结果。
3. 对方走子后 FEN 变化 → 更新画面，待稳定后重新计算。

## 3. 模块详细设计

### 3.1 capture（画面采集）
- 依赖 `hdc.exe` + `libusb_shared`（无需 DevEco Studio）。
- 命令：
  - `hdc list targets` 检查设备连接。
  - `hdc shell snapshot_display -f /data/local/tmp/xq.png -t png` 截屏（若 `-t png` 不可用则回退默认 jpeg）。
  - `hdc file recv /data/local/tmp/xq.png <本地路径>` 拉回。
- 封装为 `grab()` → 返回本地 PNG 路径，超时/失败抛异常由主循环捕获。

### 3.2 calibrate（一次性校准，全自动）
流程（用户开一局**初始局面**后触发）：
1. 截屏，检测棋盘四角（优先霍夫直线求网格外框；失败则让用户手动点四角）。
2. 用四角计算透视变换矩阵，棋盘在标准视图下为 9×10 网格。
3. 计算 90 个交叉点的标准坐标；保存四角 + 变换矩阵到 `config.json`。
4. **生成模板**：初始局面每格棋子已知，按「棋盘格 → 棋子种类」映射，从每个交叉点裁剪圆形棋子图像，归一化后存入 `templates/`（14 张：红 帅仕相马车炮兵、黑 将士象马车炮卒）。
5. 记录两个头像计时器区域坐标到 `config.json`：上方对手头像、下方己方头像（计时器就在头像上）。

### 3.3 recognize（棋局识别，纯 OpenCV）
对每帧：
1. 用 `config.json` 的四角 + 变换矩阵，把 90 个交叉点映射回原始截图坐标。
2. 每交叉点：
   - **有无棋子**：该点附近圆形区域与棋盘底色做颜色/纹理对比，判定是否为空。
   - **红/黑**：棋子圆面色块主色调（红→HSV 红区间；黑→低亮度灰黑）。
   - **棋子种类**：裁剪棋子图，与 14 张模板做归一化模板匹配，取最高相似度（低于阈值判「不确定」，该帧放弃并重试）。
3. 组装 10×9 网格 → 生成 **象棋 FEN**。

FEN 约定（标准中国象棋 FEN）：
- 10 行，自上而下（黑方底线 rank0 → 红方底线 rank9），行内自左（file a）到右（file i），空格用数字压缩。
- 红方大写 / 黑方小写：`K`帅 `A`仕 `B`相 `N`马 `R`车 `C`炮 `P`兵；`k`将 `a`士 `b`象 `n`马 `r`车 `c`炮 `p`卒。
- 轮到谁：`w`（红）或 `b`（黑）。
- 初始局面：`rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1`

坐标系统（与屏幕一致）：屏幕上方=rank0（黑），下方=rank9（红）；左=file a，右=file i。识别出的网格行 r（0=上）即 rank r，列 c（0=左）即 file c。

### 3.4 turn_detect（判先后 + 己方颜色）
- 己方颜色：默认红方（下方），`config.json` 可改。
- 判先后：对比相邻两帧的**两个头像计时器区域**像素差；正在倒计时的那个区域变化量明显更大 → 该侧在走棋。无需 OCR。
- 若对局不显示计时器（变化量阈值不达标），退化为**手动触发**：主循环提供热键/按钮「分析当前局面」，用户按下即按己方颜色算棋。

### 3.5 engine（Pikafish 封装）
- `subprocess` 启动 `engine/pikafish.exe`（选本机最快的指令集版本，实测 `bench` 的 nodes/s）。
- 协议（UCI）：
  1. `uci` → `isready` → 等 `readyok`
  2. `position fen <FEN>`
  3. `go movetime 3000`
  4. 解析 `bestmove <move>`（如 `b7c7`）。
- 引擎常驻，重复利用；局面变化时重发 `position`。

### 3.6 notation（坐标走法 ↔ 中文记谱）
- 引擎输出坐标走法（from/to，file+rank）。
- 转中文记谱规则：结合棋子种类、颜色、方向，判定「平 / 进 / 退」及从哪侧数（车马炮兵/卒的纵向计数、马相象的进退），输出如「炮二平五」「马8进7」。
- 同时保留坐标形式，用于箭头绘制（坐标 → 逆变换回屏幕像素）。

### 3.7 display（展示）
- tkinter 单窗口：
  - 左侧/背景：最新截图；
  - 覆盖：绿箭头（起点圆 → 落点），红点标记；
  - 文字条：「红方最佳：炮二平五 ｜ 评估 +1.2」；
  - 无界面模式下改为控制台打印。

## 4. 关键数据结构

`config.json`：
```json
{
  "hdc_path": "D:/.../hdc.exe",
  "player_color": "red",
  "board_corners": [[x0,y0],[x1,y1],[x2,y2],[x3,y3]],
  "perspective_matrix": [[..],[..],[..]],
  "timer_regions": {"opponent": [x,y,w,h], "self": [x,y,w,h]},
  "engine_path": "engine/pikafish.exe",
  "movetime_ms": 3000
}
```

## 5. 错误处理与健壮性
- hdc 断连 / 截屏失败：主循环捕获，显示「设备未连接」并重试。
- 识别不确定（模板相似度低 / 红黑判不出）：丢弃该帧，用最近一次可靠 FEN。
- FEN 非法（棋子数量异常）：丢弃并告警。
- 引擎未就绪 / 崩溃：自动重启子进程并重发 `uci`。
- 手动热键始终可用，作为自动判先后的兜底。

## 6. 依赖与环境
- Python（D 盘，具体路径实现时用 `where python` 确认；建议 3.10+）。
- `pip install opencv-python numpy`（tkinter 为内置）。
- `hdc.exe` + `libusb_shared`（从 OpenHarmony SDK 的 toolchains 提取）。
- Pikafish 引擎（pikafish.com 或 GitHub releases，Windows 纯引擎版）。
- 手机：开发者选项 + USB 调试，首次 USB 授权。

## 7. 风险与缓解
| 风险 | 缓解 |
|------|------|
| hdc 在 HarmonyOS 7.0 上 `snapshot_display` 受限 | 实现时先做最小验证（单条截屏命令）；若受限改用 `wukong special -p` 或无线投屏 |
| JJ象棋 皮肤/特效/走子提示遮挡棋子 | 初始局面自动提取模板；仅在 FEN 稳定时识别；必要时扩大棋盘格裁剪范围 |
| 判先后不准确 | 计时器 diff + 手动热键双保险 |
| 引擎坐标方向与我们约定相反 | 实现时用一个已知局面（初始局面）验证 bestmove 方向，修正映射 |

## 8. 里程碑
- **M1（验证）**：hdc 截屏能跑通 + Pikafish 能正确算初始局面最佳走法。
- **M2（校准+识别）**：自动校准 + 模板生成 + 识别任意局面输出正确 FEN。
- **M3（闭环）**：主循环 + 判先后 + 中文记谱 + 窗口展示。
- **M4（打磨）**：稳定性、速度、手动兜底、美化。
