"""
v1_loop / config.py — 所有常量集中管理
API_KEY 优先读环境变量 DASHSCOPE_API_KEY，Windows 下也可在系统环境变量里设置。
"""
import os
import sys
import platform

# ── 平台检测 ──────────────────────────────────────────
IS_WINDOWS = platform.system() == "Windows"

# ── API ──────────────────────────────────────────────
API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
if not API_KEY:
    raise EnvironmentError(
        "请先设置环境变量 DASHSCOPE_API_KEY\n"
        "  Linux/WSL:  export DASHSCOPE_API_KEY='sk-...'\n"
        "  Windows:    $env:DASHSCOPE_API_KEY='sk-...'  (PowerShell)"
    )
API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
PROXIES = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}

VLM_MODEL = "qwen-vl-plus"
TEXT_MODEL = "qwen-plus"

# ── 截图路径（自动适配平台） ──────────────────────────
WIN_SAVE_PATH = r"C:\temp\sg.png"
WSL_READ_PATH = r"C:\temp\sg.png" if IS_WINDOWS else "/mnt/c/temp/sg.png"

# ── 调度参数 ──────────────────────────────────────────
CHECK_INTERVAL = 20
DETECT_EVERY   = 5
HISTORY_SIZE   = 10
COOLDOWN       = 300

# ── 判断阈值 ──────────────────────────────────────────
STUCK_CONFIDENCE_THRESHOLD = 0.6

# ── 图像压缩 ──────────────────────────────────────────
IMG_MAX_WIDTH = 1280
IMG_QUALITY   = 85

# ── 日志目录（自动适配平台） ──────────────────────────
if IS_WINDOWS:
    LOG_DIR = os.path.join(os.environ.get("APPDATA", "C:\\"), "ScreenGuardian", "logs")
else:
    LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
