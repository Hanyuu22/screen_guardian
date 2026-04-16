#!/usr/bin/env bash
# run.sh — 启动 Screen Guardian（防重复 + 自动配输入法）
# 作用：
#   1. 检查是否已有实例，防止重复启动
#   2. 自动启动 ibus-daemon（中文输入法）
#   3. 启动 guardian.py：Qt 助手界面 + 后台监控检测循环

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/logs/guardian.pid"
PYTHON="$HOME/miniconda3/envs/ppocr-vllm/bin/python"

# ── 检查 Python 环境 ──────────────────────────────────
if [ ! -f "$PYTHON" ]; then
    echo "[错误] 找不到 conda 环境：$PYTHON"
    echo "  请确认 ppocr-vllm 环境已创建，或修改 run.sh 中的 PYTHON 路径"
    exit 1
fi

# ── 检查是否已有实例在运行 ────────────────────────────
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[Screen Guardian] 已有实例在运行（PID $OLD_PID），不重复启动。"
        echo "  停止现有实例：bash $SCRIPT_DIR/stop.sh"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# ── 输入法环境变量 ────────────────────────────────────
export GTK_IM_MODULE=ibus
export QT_IM_MODULE=ibus
export XMODIFIERS=@im=ibus

# ── 启动 ibus-daemon（若未运行） ─────────────────────
if ! pgrep -x ibus-daemon > /dev/null; then
    echo "[Screen Guardian] 启动 ibus-daemon..."
    ibus-daemon -drx
    sleep 1
fi

# ── 确保日志目录存在 ──────────────────────────────────
mkdir -p "$SCRIPT_DIR/logs"

# ── 启动主程序（后台运行，拿到真实 Python PID） ───────
echo "[Screen Guardian] 启动中..."
"$PYTHON" "$SCRIPT_DIR/v3_interact/guardian.py" &
GUARDIAN_PID=$!
echo $GUARDIAN_PID > "$PID_FILE"

echo "[Screen Guardian] 已启动（PID $GUARDIAN_PID）"
echo "  监控循环和 Qt 助手均已在同一进程内运行"
echo "  停止：bash $SCRIPT_DIR/stop.sh"
