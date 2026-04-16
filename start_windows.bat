@echo off
chcp 65001 >nul

echo ========================================
echo  Screen Guardian - Windows Launcher
echo ========================================
echo.

:: Check API Key
if "%DASHSCOPE_API_KEY%"=="" (
    echo [ERROR] DASHSCOPE_API_KEY is not set.
    echo.
    echo Please set it first in PowerShell:
    echo   $env:DASHSCOPE_API_KEY = "sk-your-key"
    echo.
    echo Or set it permanently in:
    echo   Control Panel - System - Advanced - Environment Variables
    echo.
    pause
    exit /b 1
)

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: Install dependencies if missing
python -c "import PyQt5, requests, PIL" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install PyQt5 requests Pillow
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        echo Please run manually: pip install PyQt5 requests Pillow
        pause
        exit /b 1
    )
)

:: Get script directory and launch
set PROJECT=%~dp0
echo Starting Screen Guardian...
echo Chinese input: use Windows IME normally (Win+Space or Shift)
echo.
python "%PROJECT%v3_interact\guardian.py"

echo.
echo Exited.
pause
