const PIECE_CHAR = {
  K: "帥", A: "仕", B: "相", N: "馬", R: "車", C: "炮", P: "兵",
  k: "將", a: "士", b: "象", n: "馬", r: "車", c: "砲", p: "卒",
};
const SIDE_NAME = { w: "红方", b: "黑方" };

const svg = document.getElementById("board");
const el = (id) => document.getElementById(id);

function esc(s) { return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }

/* ---------- 棋盘绘制（viewBox 单位 = 一格） ---------- */
function boardSVG(board, move) {
  const parts = [];
  // 底板
  parts.push(`<rect x="-0.55" y="-0.55" width="9.1" height="10.1" rx="0.35" fill="#c9a267"/>`);
  parts.push(`<rect x="-0.42" y="-0.42" width="8.84" height="9.84" rx="0.22" fill="none" stroke="#7a5a2c" stroke-width="0.05"/>`);

  const L = "rgba(70,48,20,.62)", W = 0.028;
  // 横线 10 条
  for (let r = 0; r < 10; r++) {
    parts.push(`<line x1="0" y1="${r}" x2="8" y2="${r}" stroke="${L}" stroke-width="${W}"/>`);
  }
  // 竖线 9 条（河界处断开，两条边线贯通）
  for (let f = 0; f < 9; f++) {
    if (f === 0 || f === 8) {
      parts.push(`<line x1="${f}" y1="0" x2="${f}" y2="9" stroke="${L}" stroke-width="${W}"/>`);
    } else {
      parts.push(`<line x1="${f}" y1="0" x2="${f}" y2="4" stroke="${L}" stroke-width="${W}"/>`);
      parts.push(`<line x1="${f}" y1="5" x2="${f}" y2="9" stroke="${L}" stroke-width="${W}"/>`);
    }
  }
  // 九宫斜线
  const diag = [["3,0", "5,2"], ["5,0", "3,2"], ["3,7", "5,9"], ["5,7", "3,9"]];
  diag.forEach(([a, b]) => {
    const [x1, y1] = a.split(","), [x2, y2] = b.split(",");
    parts.push(`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${L}" stroke-width="${W}"/>`);
  });
  // 楚河汉界
  parts.push(`<text x="2" y="4.62" font-size="0.52" fill="rgba(70,48,20,.55)" text-anchor="middle" font-family="KaiTi,STKaiti,serif">楚 河</text>`);
  parts.push(`<text x="6" y="4.62" font-size="0.52" fill="rgba(70,48,20,.55)" text-anchor="middle" font-family="KaiTi,STKaiti,serif">汉 界</text>`);

  // 建议箭头
  if (move && move.from && move.to) {
    const [fr, ff] = move.from, [tr, tf] = move.to;
    parts.push(`<line x1="${ff}" y1="${fr}" x2="${tf}" y2="${tr}" stroke="#1f9d63" stroke-width="0.09" stroke-linecap="round" opacity="0.95"/>`);
    parts.push(`<circle cx="${ff}" cy="${fr}" r="0.46" fill="none" stroke="#1f9d63" stroke-width="0.08"/>`);
    parts.push(`<circle cx="${tf}" cy="${tr}" r="0.46" fill="none" stroke="#1f9d63" stroke-width="0.08" stroke-dasharray="0.16 0.12"/>`);
  }

  // 棋子
  if (board && board.length === 10) {
    for (let r = 0; r < 10; r++) {
      for (let f = 0; f < 9; f++) {
        const ch = board[r][f];
        if (!ch || ch === " ") continue;
        const red = ch === ch.toUpperCase();
        const cx = f, cy = r;
        parts.push(`<circle cx="${cx}" cy="${cy}" r="0.43" fill="#f3e7cf" stroke="${red ? "#b23a2c" : "#2a2a2a"}" stroke-width="0.045"/>`);
        parts.push(`<circle cx="${cx}" cy="${cy}" r="0.36" fill="none" stroke="${red ? "rgba(178,58,44,.55)" : "rgba(42,42,42,.5)"}" stroke-width="0.022"/>`);
        parts.push(`<text x="${cx}" y="${cy + 0.145}" font-size="0.55" text-anchor="middle" font-family="KaiTi,STKaiti,serif"
          fill="${red ? "#b23a2c" : "#232323"}" font-weight="700">${PIECE_CHAR[ch] || "?"}</text>`);
      }
    }
  } else {
    parts.push(`<text x="4" y="5" font-size="0.55" text-anchor="middle" fill="rgba(70,48,20,.6)">盘面建立中…</text>`);
  }
  return parts.join("");
}

/* ---------- 面板 ---------- */
function setStatus(st) {
  const pill = el("statusPill");
  const map = {
    starting: ["启动中", ""],
    waiting: ["等待对方", "waiting"],
    ready: ["轮到我方", "ready"],
    frozen: ["暂缓建议", "frozen"],
    error: ["异常", "error"],
  };
  const [text, cls] = map[st.status] || ["运行中", ""];
  pill.textContent = text;
  pill.className = "status-pill " + cls;
  // 带上「多久前更新」，卡住时一眼能看出来后端是停了还是只是没新数据
  const age = st.updated_at ? Math.max(0, Math.round(Date.now() / 1000 - st.updated_at)) : null;
  el("subtitle").textContent = (st.message || "") + (age === null ? "" : `　·　${age}s 前`);
  if (age !== null && age > 15) {
    pill.textContent = "后端无响应";
    pill.className = "status-pill error";
  }
  el("hintText").textContent = st.message || "";
}

function fmtScore(move) {
  if (!move || move.score === null || move.score === undefined) return "—";
  const s = Number(move.score);
  if (s >= 99000) return "绝杀";
  if (s <= -99000) return "被绝杀";
  const v = s / 100;
  return (v > 0 ? "+" : "") + v.toFixed(2);
}

function renderEval(move) {
  const value = el("evalValue"), fill = el("evalFill");
  const txt = fmtScore(move);
  value.textContent = txt;
  value.className = "eval-value";

  if (!move || move.score === null || move.score === undefined) {
    fill.style.marginLeft = "50%"; fill.style.width = "0%";
    return;
  }
  const s = Number(move.score);
  if (s >= 99000) {
    value.className = "eval-value good";
    fill.style.marginLeft = "50%"; fill.style.width = "48%"; fill.style.background = "var(--good)";
    return;
  }
  if (s <= -99000) {
    value.className = "eval-value bad";
    fill.style.marginLeft = "2%"; fill.style.width = "48%"; fill.style.background = "var(--bad)";
    return;
  }
  const pct = Math.min(48, Math.abs(s) / 1000 * 48);
  if (s >= 0) {
    value.classList.add("good");
    fill.style.marginLeft = "50%"; fill.style.width = pct + "%"; fill.style.background = "var(--good)";
  } else {
    value.classList.add("bad");
    fill.style.marginLeft = (50 - pct) + "%"; fill.style.width = pct + "%"; fill.style.background = "var(--bad)";
  }
}

let lastShotKey = null;

function renderShot(st) {
  const img = el("shot"), empty = el("shotEmpty"), link = el("shotLink");
  const m = st.move;
  if (!m || !m.uci) return;           // 没新建议就不动图，避免反复拉 600KB
  const key = m.uci + "|" + m.score;
  if (key === lastShotKey) return;
  lastShotKey = key;
  const url = "/api/bestmove.png?t=" + Date.now();
  img.src = url;
  img.classList.add("ready");
  empty.classList.add("hide");
  link.href = url;
}

/* 执黑时把棋盘上下翻转，让「我方」永远在下方——和后端给的是标准坐标
   （红在下）无关，纯粹是显示视角问题。转盘面、也转建议箭头。 */
function orientForViewer(board, move, mySide) {
  if (mySide !== "b" || !board || board.length !== 10) return { board, move };
  const flipPoint = (p) => (Array.isArray(p) && p.length === 2 ? [9 - p[0], p[1]] : p);
  return {
    board: [...board].reverse(),
    move: move ? { ...move, from: flipPoint(move.from), to: flipPoint(move.to) } : move,
  };
}

function render(st) {
  setStatus(st);
  const view = orientForViewer(st.board, st.move, st.my_side);
  svg.innerHTML = boardSVG(view.board, view.move);

  const hasMove = st.move && st.move.chinese;
  el("moveMain").textContent = hasMove ? st.move.chinese : "—";
  el("moveSub").textContent = hasMove
    ? `${st.move.uci}　评估 ${fmtScore(st.move)}`
    : (st.status === "waiting" ? "等对方走子" : st.status === "frozen" ? "盘面待确认" : "等待建议");

  renderEval(st.move);
  renderShot(st);

  if (st.last_move && st.last_move.chinese) {
    el("lastMove").textContent = st.last_move.chinese;
    const p = st.last_move;
    el("lastMoveMeta").textContent = `${p.piece || ""} ${(p.from || []).join(",")} → ${(p.to || []).join(",")}`;
  }

  el("sideInfo").textContent = st.my_side
    ? `我方 ${SIDE_NAME[st.my_side]}　轮 ${SIDE_NAME[st.side] || "—"}`
    : "—";
}

/* ---------- 轮询 ---------- */
async function tick() {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    const st = await res.json();
    render(st);
  } catch (e) {
    el("statusPill").textContent = "连接断开";
    el("statusPill").className = "status-pill error";
    el("subtitle").textContent = "后端可能已停止，请重新运行 start_web.bat";
  }
}

// 「重新识别」：程序自己判断不出的偏差，由人点一下兜底
el("resyncBtn").addEventListener("click", async () => {
  const btn = el("resyncBtn");
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = "识别中…";
  try {
    await fetch("/api/resync", { method: "POST" });
    await new Promise((r) => setTimeout(r, 1500));
    await tick();
  } catch (e) {
    /* 忽略：下一轮轮询会显示真实状态 */
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
});

tick();
setInterval(tick, 800);

// 标签页/预览面板切到后台时浏览器会把定时器节流（可能降到一分钟一次），
// 切回来立刻补一次，避免看起来像「卡住了」。
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) tick();
});
window.addEventListener("focus", tick);
