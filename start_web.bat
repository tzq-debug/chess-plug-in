@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   象棋视觉助手  -  正在启动本地服务
echo   界面会自动在浏览器打开；关闭本窗口即停止
echo ============================================
D:/Python312/python.exe webapp\server.py
echo.
echo 服务已停止，按任意键关闭。
pause >nul
