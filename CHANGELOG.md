# Changelog

## [v0.4.1] - 2026-04-16 22:00
### 修复
- WSLg 中文输入法三项根因修复：
  1. `enable-by-default: true` — ibus 在每个窗口自动激活，无需手动按快捷键
  2. 触发快捷键改为 `Ctrl+Space`（原 `Super+Space` 在 WSLg 被 Windows 语言切换拦截）
  3. `run.sh` 与 `guardian.py` 启动时均调用 `ibus engine libpinyin`，防止 daemon 重启后引擎重置为英文键盘
- `.gitignore` 加入 `NOTES.md`（开发私人笔记）

### 技术备注
- dconf 在 WSLg 下无法通过 `gsettings` 直接写入（无 dconf-service），
  改用系统 `python3 + gi.repository.Gio` 绕过限制完成配置持久化

---

## [v0.4.0] - 2026-04-16
### 修复
- QApplication 移至主线程，解决子线程创建 Qt 导致的 Segmentation fault
- Signal 改用 token 机制传递复杂对象（list[dict]），避免 PyQt5 序列化问题
- 弹窗点击选项后直接在主线程创建对话窗，无需二次 Signal
- 窗口销毁时自动从引用列表移除，防止内存持续积累
- 弹窗 `Qt.Tool` 改为 `Qt.Window`，支持拖动

### 变更
- 架构调整：监控循环移至后台 daemon 线程，主线程专属 Qt 事件循环
- README.md 补充架构说明、PyQt5 注意事项、CHANGELOG 引用

---

## [v0.3.0] - 2026-04-16
### 新增
- 跨平台截图模块 `shared/capture.py`，自动识别 WSL2 / Linux / Windows
- `setup.sh` 一键安装脚本（系统字体 + Python 依赖 + API Key 配置）
- `README.md` 平台支持说明和快速开始指引

### 修复
- UI 框架从 tkinter 改为 PyQt5，解决 WSLg 中文乱码（\u52a9 等 Unicode 转义）问题
- 弹窗窗口标志改为 `Qt.Window`，支持拖动

### 变更
- `requirements.txt` 补充 PyQt5 >= 5.15 和 mss >= 9.0

---

## [v0.2.0] - 2026-04-16
### 新增
- `v3_interact/`: 带屏幕上下文的 PyQt5 多轮对话窗口
- `v3_interact/context_builder.py`: history → LLM system prompt 构建器
- 弹窗点击选项后自动打开对话窗，预注入屏幕历史上下文

### 修复
- 修复 `v3_interact/guardian.py` 中 sys.path 优先级导致的循环 import 问题
- 修复同名 `notifier.py` 引起的 partially initialized module 错误（改用 importlib 按路径加载）
- `config.py` API Key 从硬编码改为读取 `DASHSCOPE_API_KEY` 环境变量

---

## [v0.1.0] - 2026-04-16
### 新增
- `v0_probe/`: 三项独立可行性验证脚本
  - `test_capture.py`: PowerShell 截图验证（WSL2 → Windows 屏幕）
  - `test_analyze.py`: qwen-vl-plus 视觉分析验证（三种 Prompt 对比）
  - `test_detect.py`: qwen-plus stuck 判断验证（三场景 100% 正确）
- `v1_loop/guardian.py`: 核心监控循环（截图 → diff 跳过 → VLM → history → stuck 检测）
- `v2_notify/notifier.py`: PyQt5 弹窗，独立线程，冷却期防重复
- 实测数据：截图 ~1.9s，VLM 分析 ~1.2s，stuck 判断 ~3s
