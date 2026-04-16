@echo off
chcp 65001 >nul
echo ========================================
echo  Screen Guardian - Windows 启动器
echo  中文输入支持版
echo ========================================
echo.

:: 检查 API Key
if "%DASHSCOPE_API_KEY%"=="" (
    echo [错误] 未设置 DASHSCOPE_API_KEY
    echo.
    echo 请先在 PowerShell 中运行：
    echo   $env:DASHSCOPE_API_KEY = "sk-你的key"
    echo.
    echo 或永久设置（系统环境变量）：
    echo   控制面板 ^> 系统 ^> 高级系统设置 ^> 环境变量
    echo.
    pause
    exit /b 1
)

:: 检查 Windows Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Windows Python
    echo 请从 https://python.org 安装 Python 3.10+
    pause
    exit /b 1
)

:: 检查并安装依赖
echo 检查依赖...
python -c "import PyQt5, requests, PIL" >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖（首次运行）...
    pip install PyQt5 requests Pillow
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请手动运行：
        echo   pip install PyQt5 requests Pillow
        pause
        exit /b 1
    )
)

:: 设置项目路径（UNC 路径访问 WSL）
set PROJECT=\\wsl.localhost\Ubuntu-22.04\home\hanyuu\screen_guardian

echo 启动 Screen Guardian...
echo （中文输入：使用系统输入法，正常切换即可）
echo.
python "%PROJECT%\v3_interact\guardian.py"

echo.
echo 程序已退出。
pause
