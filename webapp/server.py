"""本地 Web 界面：左边实时棋盘，右边最佳走法。

为什么是本地服务而不是网站：抓屏依赖 hdc（USB 连手机），算棋依赖本机的
Pikafish 引擎，浏览器和云端都碰不到这两样。所以后端跑在本机，前端只是个
网页——双击 start_web.bat 会自动起服务并打开浏览器，用起来和普通软件一样。

启动：python webapp/server.py   （或双击项目根目录的 start_web.bat）
"""

import os
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from xiangqi.main import main

STATIC = Path(__file__).resolve().parent / "static"
HOST = "127.0.0.1"
PORT = 8765

_state_lock = threading.Lock()
_resync_event = threading.Event()   # 界面点「重新识别」时置位，主循环据此重建盘面
STATE = {
    "status": "starting",
    "message": "正在连接手机，建立盘面…",
    "board": [],
    "side": None,
    "my_side": None,
    "flip": False,
    "move": None,
    "last_move": None,
}


def _on_state(snapshot):
    """主循环每帧推来的状态。只保存，不做耗时操作（它在抓帧线程里）。"""
    global STATE
    with _state_lock:
        STATE = snapshot


def _monitor():
    """后台跑监控主循环。它是个死循环，所以必须放线程里。"""
    os.chdir(ROOT)          # main() 用的都是相对项目根的路径
    try:
        main(on_state=_on_state, resync_event=_resync_event)
    except Exception as e:  # noqa: BLE001 - 异常要显示到界面上，不能静默
        global STATE
        with _state_lock:
            STATE = dict(STATE, status="error", message=f"监控异常：{e}", move=None)


app = FastAPI(title="象棋视觉助手")


@app.on_event("startup")
def _startup():
    threading.Thread(target=_monitor, daemon=True).start()


@app.get("/api/state")
def api_state():
    with _state_lock:
        return JSONResponse(STATE)


@app.post("/api/resync")
def api_resync():
    """界面上的「重新识别」按钮：让主循环抛掉当前盘面重新建一次。"""
    _resync_event.set()
    return {"ok": True}


@app.get("/api/bestmove.png")
def api_bestmove():
    """原始箭头图（叠在手机截图上的那张），供「截图模式」查看。"""
    p = ROOT / "bestmove.png"
    if not p.exists():
        return JSONResponse({"error": "还没有生成"}, status_code=404)
    return FileResponse(p, media_type="image/png",
                        headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/")
def index():
    # 页面与静态资源都别让浏览器缓存：改了界面却看到旧版，排查起来很费劲
    return FileResponse(
        STATIC / "index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


class _NoCacheStatic(StaticFiles):
    """静态文件禁缓存：前端一改就该立刻生效，避免「明明改了却没变」。"""

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return resp


app.mount("/static", _NoCacheStatic(directory=str(STATIC)), name="static")


def _open_browser_later():
    import time
    time.sleep(1.2)
    try:
        webbrowser.open(f"http://{HOST}:{PORT}/")
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    import uvicorn

    if "--no-browser" not in sys.argv:
        threading.Thread(target=_open_browser_later, daemon=True).start()
    print(f"界面地址：http://{HOST}:{PORT}/   （Ctrl+C 停止）")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
