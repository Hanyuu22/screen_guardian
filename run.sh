#!/usr/bin/env bash
# run.sh — 启动 Screen Guardian（防重复 + 自动配输入法）

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/logs/guardian.pid"

# ── 检查是否已有实例在运行 ────────────────────────────
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[Screen Guardian] 已有实例在运行（PID $OLD_PID），请勿重复启动。"
        echo "  如需强制重启，先执行：kill $OLD_PID"
        exit 1
    else
        # PID 文件残留但进程已不存在
        rm -f "$PID_FILE"
    fi
fi

# ── 环境变量（输入法） ────────────────────────────────
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

# ── 启动主程序 ────────────────────────────────────────
echo "[Screen Guardian] 启动中..."
conda run -n ppocr-vllm python "$SCRIPT_DIR/v3_interact/guardian.py" &
GUARDIAN_PID=$!
echo $GUARDIAN_PID > "$PID_FILE"
echo "[Screen Guardian] 已启动（PID $GUARDIAN_PID）"
echo "  停止：bash $SCRIPT_DIR/stop.sh"
