@echo off
chcp 65001 >nul
setlocal

set "APP_DIR=%~dp0"
set "PY_EXE=%APP_DIR%.venv\Scripts\python.exe"
set "UI_FILE=%APP_DIR%crawler_ui.py"
set "PORT=8501"

if not exist "%PY_EXE%" (
  echo [ERROR] 未找到虚拟环境解释器：%PY_EXE%
  echo 请先在项目目录创建并激活 .venv，安装依赖后再运行。
  echo.
  pause
  exit /b 1
)

if not exist "%UI_FILE%" (
  echo [ERROR] 未找到 UI 文件：%UI_FILE%
  echo.
  pause
  exit /b 1
)

echo [INFO] 正在启动 Streamlit UI...
echo [INFO] 地址: http://localhost:%PORT%

timeout /t 2 >nul
start "" "http://localhost:%PORT%"

"%PY_EXE%" -m streamlit run "%UI_FILE%" --server.address 127.0.0.1 --server.port %PORT%

echo.
echo [INFO] UI 已退出。
pause
endlocal
