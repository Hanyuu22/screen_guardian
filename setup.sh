#!/bin/bash
# Screen Guardian — 一键环境配置
# 支持：纯 Linux / WSL2 / (macOS 未测试)

set -e

echo "======================================"
echo "  Screen Guardian 环境配置"
echo "======================================"

# ── 1. 检测运行环境 ────────────────────────
IS_WSL=false
IS_LINUX=false

if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=true
    echo "检测到：WSL2"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    IS_LINUX=true
    echo "检测到：Linux"
fi

# ── 2. 系统依赖（中文字体 + Qt 依赖） ──────
echo ""
echo "[1/3] 安装系统依赖..."

sudo apt-get update -qq
sudo apt-get install -y -qq \
    fonts-noto-cjk \
    libxcb-xinerama0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-render-util0 \
    python3-dev

# WSL2：额外链接 Windows 微软雅黑（备用）
if [ "$IS_WSL" = true ]; then
    if [ -f "/mnt/c/Windows/Fonts/msyh.ttc" ]; then
        echo "  → 链接 Windows 微软雅黑字体"
        sudo mkdir -p /usr/local/share/fonts/windows
        sudo cp /mnt/c/Windows/Fonts/msyh.ttc /usr/local/share/fonts/windows/ 2>/dev/null || true
    fi
fi

sudo fc-cache -fv -q
echo "  ✓ 系统依赖完成"

# ── 3. Python 依赖 ──────────────────────────
echo ""
echo "[2/3] 安装 Python 依赖..."
pip install -r requirements.txt -q
echo "  ✓ Python 依赖完成"

# ── 4. 环境变量 ─────────────────────────────
echo ""
echo "[3/3] 配置环境变量..."

BASHRC="$HOME/.bashrc"
if ! grep -q "DASHSCOPE_API_KEY" "$BASHRC"; then
    echo ""
    read -p "请输入你的 DashScope API Key (sk-...): " API_KEY
    if [ -n "$API_KEY" ]; then
        echo "export DASHSCOPE_API_KEY=\"$API_KEY\"" >> "$BASHRC"
        echo "  ✓ API Key 已写入 ~/.bashrc"
    else
        echo "  ⚠ 跳过，请手动在 ~/.bashrc 添加："
        echo "    export DASHSCOPE_API_KEY='sk-...'"
    fi
else
    echo "  ✓ DASHSCOPE_API_KEY 已存在"
fi

# ── 5. 验证 ─────────────────────────────────
echo ""
echo "======================================"
echo "  验证安装..."
echo "======================================"

python3 -c "
import sys
errors = []

try:
    import requests; print('  ✓ requests', requests.__version__)
except: errors.append('requests')

try:
    from PIL import Image; print('  ✓ Pillow')
except: errors.append('Pillow')

try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QFontDatabase
    app = QApplication(sys.argv)
    db = QFontDatabase()
    chinese = [f for f in db.families() if any(k in f for k in ['Noto','CJK','YaHei'])]
    if chinese:
        print(f'  ✓ PyQt5 + 中文字体: {chinese[0]}')
    else:
        print('  ⚠ PyQt5 已安装，但未找到中文字体')
    app.quit()
except Exception as e: errors.append(f'PyQt5: {e}')

try:
    import mss; print('  ✓ mss')
except: errors.append('mss')

if errors:
    print()
    print('  ✗ 以下依赖安装失败:', errors)
    sys.exit(1)
else:
    print()
    print('  全部依赖验证通过！')
"

echo ""
echo "======================================"
echo "启动方式："
echo "  source ~/.bashrc"
if [ "$IS_WSL" = true ]; then
echo "  python v3_interact/guardian.py   # WSL2 完整版"
else
echo "  python v3_interact/guardian_linux.py  # Linux 版（截图方式不同）"
fi
echo "======================================"
