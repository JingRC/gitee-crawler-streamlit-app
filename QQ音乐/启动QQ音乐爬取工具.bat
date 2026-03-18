@echo off
chcp 65001 >nul
cd /d %~dp0

echo [1/3] 检查 Python...
where python >nul 2>nul
if errorlevel 1 (
    echo 未检测到 python，请先安装 Python 并加入 PATH。
    pause
    exit /b 1
)

echo [2/3] 安装依赖...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo 依赖安装失败，请检查网络或 Python 环境。
    pause
    exit /b 1
)

echo [3/3] 启动 Streamlit UI...
python -m streamlit run app.py
if errorlevel 1 (
    echo 启动失败，请查看报错信息。
    pause
)
