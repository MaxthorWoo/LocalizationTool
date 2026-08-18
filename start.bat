@echo off
chcp 65001 >nul
title 本地化翻译平台 - Reflex
cd /d "%~dp0"

echo ============================================
echo   本地化可视化翻译平台 - 一键启动
echo ============================================
echo.

REM ---- 1. 激活虚拟环境 ----
if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 未找到虚拟环境 .venv，请先执行:
    echo        python -m venv .venv
    echo        .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"
echo [OK] 虚拟环境已激活: %VIRTUAL_ENV%

REM ---- 2. 校验 Reflex 是否安装 ----
if not exist ".venv\Scripts\reflex.exe" (
    echo [错误] 未检测到 reflex，请先安装依赖:
    echo        .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM ---- 3. 打开浏览器（稍等几秒让服务启动） ----
start "" cmd /c "timeout /t 8 >nul & start http://localhost:3100"

echo.
echo [启动中] Reflex 正在启动，请稍候...
echo          前端: http://localhost:3100
echo          后端: http://localhost:8100
echo.
echo [提示] 关闭本窗口即可停止服务。
echo ============================================

REM ---- 4. 启动 Reflex ----
reflex run

echo.
echo Reflex 已停止。
pause
