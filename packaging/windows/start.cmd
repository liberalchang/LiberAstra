@echo off
rem 启动已安装的 LiberAstra。数据在当前用户目录，不写进安装目录。
setlocal
set "ROOT=%~dp0"
set "LIBERASTRA_DATA_DIR=%LOCALAPPDATA%\LiberAstra\data"
set "LIBERASTRA_HOST=0.0.0.0"
set "LIBERASTRA_PORT=8000"
set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%ms-playwright"
set "PYTHONPATH=%ROOT%backend"
cd /d "%ROOT%"

if not exist "%LIBERASTRA_DATA_DIR%" mkdir "%LIBERASTRA_DATA_DIR%"

rem 等服务起来再打开浏览器
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:%LIBERASTRA_PORT%"

"%ROOT%runtime\python.exe" -m uvicorn liberastra.main:app --host %LIBERASTRA_HOST% --port %LIBERASTRA_PORT%
if errorlevel 1 (
  echo.
  echo 启动失败。若端口被占用，先关掉旧的 LiberAstra 窗口再试。
  pause
)
