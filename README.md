# Screen Guardian

定期截屏 + Vision LLM 分析，自动检测用户是否卡住，弹窗主动提供帮助。

> 版本更新记录见 [CHANGELOG.md](CHANGELOG.md)

# TO DO
  正在解决WSL GUI无法正确键入中文
  
## 功能

- 每 20 秒截取屏幕，用 `qwen-vl-plus` 分析当前状态
- 画面无变化时自动跳过 VLM 调用（节省费用）
- 每 5 轮聚合分析历史，用 `qwen-plus` 判断是否卡住
- 检测到困境时弹出通知窗，提供 3 个建议选项
- 点击选项后打开带屏幕上下文的多轮对话窗口
- 5 分钟冷却期，防止重复打扰

## 架构说明

```
主线程: QApplication 事件循环（PyQt5）
后台线程: 监控循环（截图 → 分析 → 检测）
通信: pyqtSignal token 机制（后台 → 主线程触发 UI）

弹窗点击选项 → 回调在主线程执行 → 直接创建对话窗
```

## 平台支持

| 平台 | 状态 | 截图方式 |
|------|------|---------|
| WSL2 | ✅ 完整支持 | PowerShell 截取 Windows 屏幕 |
| 纯 Linux（X11/Wayland） | ✅ 支持 | mss 库 |
| Windows 原生 Python | ⚠️ 需修改路径 | mss 库 |
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
set DASHSCOPE_API_KEY=sk-你的key
python v3_interact/guardian.py
```

> Windows 用户需修改 `v1_loop/config.py`：
> 将 `WSL_READ_PATH` 改为 `C:\temp\sg_guardian.png`

## 依赖

### Python 包
```
requests >= 2.28
Pillow   >= 9.0
PyQt5    >= 5.15    # UI 框架，需在主线程创建 QApplication
mss      >= 9.0     # 跨平台截图（Linux/Windows 使用）
```

### 系统包（Linux / WSL2）
```bash
sudo apt-get install fonts-noto-cjk libxcb-xinerama0
```

> WSL2 用户：`setup.sh` 会自动从 `C:\Windows\Fonts\` 链接微软雅黑作为备用字体

## 环境变量

```bash
export DASHSCOPE_API_KEY="sk-..."   # DashScope API Key（必须）
```

写入 `~/.bashrc` 后执行 `source ~/.bashrc`，之后每次开终端自动生效。

## 项目结构

```
screen_guardian/
├── PLAN.md          架构设计文档
├── CHANGELOG.md     版本更新记录
├── setup.sh         一键安装脚本（Linux/WSL2）
├── requirements.txt Python 依赖
├── shared/
│   └── capture.py   跨平台截图模块（自动识别 WSL2/Linux/Windows）
├── v0_probe/        可行性验证脚本（截图/VLM/stuck 检测）
├── v1_loop/         核心监控循环 + 配置
├── v2_notify/       PyQt5 弹窗通知
└── v3_interact/     完整版（弹窗 + 多轮对话，推荐使用）
```
