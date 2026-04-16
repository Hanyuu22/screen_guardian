#!/usr/bin/env bash
# stop.sh — 停止 Screen Guardian

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/logs/guardian.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "[Screen Guardian] 未找到运行中的实例。"
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    rm -f "$PID_FILE"
    echo "[Screen Guardian] 已停止（PID $PID）。"
else
    rm -f "$PID_FILE"
    echo "[Screen Guardian] 进程已不存在，清理 PID 文件。"
fi
