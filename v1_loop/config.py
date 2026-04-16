"""
v1_loop / config.py — 所有常量集中管理
API_KEY 从环境变量读取，在 ~/.bashrc 中设置：
  export DASHSCOPE_API_KEY="sk-..."
"""
import os

# ── API ──────────────────────────────────────────────
API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
if not API_KEY:
    raise EnvironmentError("请先设置环境变量 DASHSCOPE_API_KEY，例如在 ~/.bashrc 中添加：\nexport DASHSCOPE_API_KEY='sk-...'")
API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
PROXIES = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}

VLM_MODEL = "qwen-vl-plus"       # 视觉分析：每帧
TEXT_MODEL = "qwen-plus"          # 困境判断：每5轮

# ── 截图路径 ──────────────────────────────────────────
WIN_SAVE_PATH = r"C:\temp\sg.png"
WSL_READ_PATH = "/mnt/c/temp/sg.png"

# ── 调度参数 ──────────────────────────────────────────
CHECK_INTERVAL = 20       # 截图间隔（秒）
DETECT_EVERY   = 5        # 每 N 轮触发一次 stuck 检测
HISTORY_SIZE   = 10       # 保留最近 N 条历史
COOLDOWN       = 300      # 触发弹窗后的冷却期（秒）

# ── 判断阈值 ──────────────────────────────────────────
STUCK_CONFIDENCE_THRESHOLD = 0.6   # confidence 超过此值才触发弹窗

# ── 图像压缩 ──────────────────────────────────────────
IMG_MAX_WIDTH = 1280    # 发送给 VLM 前压缩到此宽度
IMG_QUALITY   = 85      # JPEG 压缩质量

# ── 日志 ──────────────────────────────────────────────
LOG_DIR = "/home/hanyuu/screen_guardian/logs"
