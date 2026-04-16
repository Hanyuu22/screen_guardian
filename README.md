# Screen Guardian

定期截屏 + Vision LLM 分析，自动检测用户是否卡住，弹窗主动提供帮助。

## 平台支持

| 平台 | 支持状态 | 截图方式 |
|------|---------|---------|
| WSL2（当前开发环境） | ✅ 完整支持 | PowerShell 截取 Windows 屏幕 |
| 纯 Linux（X11/Wayland） | ✅ 支持 | mss 库 |
| Windows 原生 Python | ⚠️ 需小改（路径）| mss 库 |
| macOS | 🔲 未测试 | mss 库（理论可用） |

## 快速开始

### Linux / WSL2

```bash
git clone https://github.com/Hanyuu22/screen_guardian.git
cd screen_guardian
bash setup.sh          # 自动安装依赖、字体、配置 API Key
source ~/.bashrc
python v3_interact/guardian.py
```

### Windows 原生 Python

```bash
git clone https://github.com/Hanyuu22/screen_guardian.git
cd screen_guardian
pip install -r requirements.txt
# 设置环境变量
set DASHSCOPE_API_KEY=sk-你的key
python v3_interact/guardian.py
```

> Windows 用户需额外修改 `v1_loop/config.py`：
> 将 `WSL_READ_PATH` 改为 `C:\temp\sg_guardian.png`（与 shared/capture.py 保持一致）

## 依赖

### Python 包
```
requests >= 2.28
Pillow   >= 9.0
PyQt5    >= 5.15
mss      >= 9.0
```

### 系统包（Linux/WSL2）
```bash
sudo apt-get install fonts-noto-cjk libxcb-xinerama0
```

## 环境变量

```bash
export DASHSCOPE_API_KEY="sk-..."   # DashScope API Key（必须）
```

在 `~/.bashrc` 中添加后执行 `source ~/.bashrc`。

## 项目结构

```
screen_guardian/
├── v0_probe/       可行性验证脚本
├── v1_loop/        核心监控循环
├── v2_notify/      PyQt5 弹窗通知
├── v3_interact/    完整交互对话
├── shared/         跨平台工具（截图模块）
└── setup.sh        一键安装脚本
```
