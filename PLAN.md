# Screen Guardian — 架构计划与实现路线

> 核心目标：一个运行在 WSL2 的后台守护程序，通过定期截屏 + Vision LLM 分析用户屏幕状态，
> 自动检测用户是否陷入困境（卡住/报错/重复操作），并主动弹窗提供帮助选项和交互式解答。

---

## 环境约束

- OS: WSL2 Ubuntu，监控的是 Windows 桌面
- GPU: RTX 3070 Ti Laptop 8GB（可用于本地 VLM，但优先用 API）
- conda 环境: `ppocr-vllm`（Pillow、requests 已有）
- API: DashScope `sk-765ab8c8b795499dba6bea8e5373646f`
- 代理: Clash `127.0.0.1:7897`
- 截图路径: PowerShell → `C:\temp\sg.png` → WSL 读 `/mnt/c/temp/sg.png`

---

## 整体架构

```
┌──────────────────────────────────────────────────────┐
│                  Screen Guardian Daemon               │
│                                                      │
│  Scheduler (while loop, sleep N秒)                   │
│      │                                               │
│      ▼                                               │
│  Capture  ──PowerShell──▶  C:\temp\sg.png            │
│      │                     /mnt/c/temp/sg.png        │
│      ▼                                               │
│  Diff Filter  ──64×36 MD5──▶  相同则跳过              │
│      │                                               │
│      ▼                                               │
│  Analyzer  ──qwen-vl-plus──▶  screen_state (str)     │
│      │                                               │
│      ▼                                               │
│  History Buffer  ──内存列表──▶  最近 10 条             │
│      │                                               │
│      ▼  (每5轮触发)                                   │
│  Stuck Detector  ──qwen-plus──▶  {stuck, reason,     │
│      │                            suggestions[3]}    │
│      │  stuck=True                                   │
│      ▼                                               │
│  Notifier  ──tkinter 独立线程──▶  弹窗               │
│      │  用户点击选项                                  │
│      ▼                                               │
│  Chat Window  ──qwen-plus 多轮──▶  交互式帮助         │
└──────────────────────────────────────────────────────┘
```

---

## 两层 LLM 分工

| 层 | 模型 | 触发时机 | Prompt 目标 | 预估耗时 |
|----|------|----------|-------------|---------|
| 视觉层 | qwen-vl-plus | 每次截图（画面有变化时） | 一句话描述屏幕：应用名+任务+异常标注 | 2-4s |
| 判断层 | qwen-plus | 每5轮聚合 | 分析 history，输出 stuck JSON | 1-2s |
| 对话层 | qwen-plus | 用户点击弹窗选项后 | 带屏幕上下文的多轮问答 | 1-3s |

---

## 版本路线图

### v0_probe — 可行性验证（独立脚本，无循环）

**目标**: 三件事各自跑通，确认延迟和准确性可接受

**文件**:
- `v0_probe/test_capture.py` — PowerShell 截图 → 验证文件存在、大小、耗时
- `v0_probe/test_analyze.py` — 读取截图 → 发 qwen-vl-plus → 打印描述 + 耗时
- `v0_probe/test_detect.py` — 构造 mock history → 发 qwen-plus → 打印 stuck JSON

**成功标准**:
- 截图延迟 < 3s，文件正常保存
- VLM 描述准确反映屏幕内容
- stuck 判断返回合法 JSON，reason 有意义

**状态**: [ ] 待实现

---

### v1_loop — 核心监控循环（单文件）

**目标**: 串联 while 循环，加入 diff 跳过 + history 管理，终端打印运行状态

**文件**:
- `v1_loop/guardian.py` — 主循环（截图→diff→分析→history→每5轮检测→终端输出）
- `v1_loop/config.py` — 所有常量（间隔、API key、路径、阈值）

**核心逻辑**:
```
每 CHECK_INTERVAL 秒:
  1. 截图 → /mnt/c/temp/sg.png
  2. 计算 64×36 MD5 hash
  3. 若 hash == last_hash: 记录重复次数，跳过 VLM
  4. 否则: VLM 分析 → 追加 history
  5. 每 DETECT_EVERY 轮: 规则检测 + LLM 检测 → 打印结果
```

**成功标准**:
- 稳定跑 10 分钟无崩溃
- 画面不变时正确跳过 VLM 调用（终端可见 "跳过"）
- 画面变化时正确更新描述
- 每5轮打印一次 stuck 判断

**状态**: [ ] 待实现

---

### v2_notify — 弹窗通知层

**目标**: stuck 触发时弹出 tkinter 窗口，含预生成选项，冷却期防骚扰

**新增文件**:
- `v2_notify/notifier.py` — tkinter 弹窗，独立线程，含 3 个选项按钮 + 忽略

**弹窗设计**:
```
┌─────────────────────────────────┐
│  Screen Guardian 发现可能的问题  │
├─────────────────────────────────┤
│  检测到：[reason]               │
│                                 │
│  [1. 建议选项1]                 │
│  [2. 建议选项2]                 │
│  [3. 建议选项3]                 │
│                                 │
│  [没问题，忽略]                  │
└─────────────────────────────────┘
```

**冷却期**: 触发一次后 300s 内不再弹窗

**成功标准**:
- 弹窗不阻塞主循环（独立线程）
- 点击任意按钮正常关闭
- 冷却期内不重复弹出
- 置信度 < 阈值时不触发

**状态**: [ ] 待实现

---

### v3_interact — 交互式对话帮助（完整版）

**目标**: 用户点击选项后，打开带屏幕上下文的多轮对话窗口

**新增文件**:
- `v3_interact/chat_window.py` — tkinter 多轮对话 UI
- `v3_interact/context_builder.py` — 将 history + 用户选项 → LLM system prompt

**对话窗口设计**:
```
┌──────────────────────────────────────┐
│  Screen Guardian — 帮助对话          │
├──────────────────────────────────────┤
│  [AI]: 我注意到你在 xxx 遇到了...    │
│        可能的原因是...               │
│        建议你...                     │
│                                      │
│  [用户选择的选项内容]                │
│                                      │
│  [AI]: 针对这个具体问题...           │
├──────────────────────────────────────┤
│  [输入框                    ] [发送] │
└──────────────────────────────────────┘
```

**context_builder 逻辑**:
```
system = f"""
你是一个桌面助手。用户屏幕最近状态如下：
{history_formatted}

用户表示遇到的问题可能是：{selected_option}

请基于上述上下文，给出具体可操作的帮助。
"""
```

**成功标准**:
- 对话窗口首条消息包含屏幕上下文
- 支持多轮追问
- 关闭对话窗不影响主循环继续运行

**状态**: [ ] 待实现

---

## 目录结构

```
screen_guardian/
├── PLAN.md              ← 本文件（核心参考）
├── requirements.txt
├── logs/                ← 运行日志（v1 开始写入）
├── shared/
│   ├── config.py        ← 统一配置（v1 开始使用）
│   └── capture.py       ← 截图工具（v1 开始抽离）
├── v0_probe/
│   ├── test_capture.py
│   ├── test_analyze.py
│   └── test_detect.py
├── v1_loop/
│   ├── guardian.py
│   └── config.py
├── v2_notify/
│   ├── guardian.py
│   ├── config.py
│   └── notifier.py
└── v3_interact/
    ├── guardian.py
    ├── config.py
    ├── notifier.py
    ├── chat_window.py
    └── context_builder.py
```

---

## 关键实现细节

### 截图（WSL2 → Windows 屏幕）
```python
PS_SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$s = [Windows.Forms.Screen]::PrimaryScreen.Bounds
$b = New-Object Drawing.Bitmap($s.Width, $s.Height)
$g = [Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen(0,0,0,0,$b.Size)
$b.Save('C:\temp\sg.png')
$g.Dispose(); $b.Dispose()
"""
subprocess.run(['powershell.exe', '-Command', PS_SCRIPT], timeout=10)
# WSL 读路径: /mnt/c/temp/sg.png
```

### 图像 Diff
```python
from PIL import Image
import hashlib
def img_hash(path):
    img = Image.open(path).resize((64, 36)).convert('L')
    return hashlib.md5(img.tobytes()).hexdigest()
```

### VLM Prompt（视觉层）
```
用一句话描述当前屏幕内容（应用名+用户正在做什么），
重点标注：错误信息、等待/加载状态、长时间无变化的迹象。
控制在20字以内。
```

### Stuck Detection Prompt（判断层）
```
以下是用户屏幕最近{N}次状态记录（时间顺序）：
{history}

请判断用户是否陷入困境（重复操作/长时间报错未解决/等待超时）。
返回 JSON：
{"stuck": bool, "confidence": 0-1, "reason": "简短原因", "suggestions": ["建议1","建议2","建议3"]}
只返回 JSON，不要其他文字。
```

### 代理配置
```python
PROXIES = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
```

---

## 进度追踪

| 阶段 | 状态 | 完成时间 | 备注 |
|------|------|---------|------|
| 目录结构 + PLAN.md | ✅ 完成 | 2026-04-16 | |
| v0: test_capture | ✅ 完成 | 2026-04-16 | 1.93s/帧，1920×1080，165KB PNG |
| v0: test_analyze | ✅ 完成 | 2026-04-16 | qwen-vl-plus 1.16s，结构化JSON准确 |
| v0: test_detect | ✅ 完成 | 2026-04-16 | 3场景100%正确，建议质量高 |
| v1: guardian loop | ✅ 完成 | 2026-04-16 | 稳定循环，diff跳过正常，检测准确 |
| v2: tkinter 弹窗 | ✅ 完成 | 2026-04-16 | 独立线程，WSLg渲染，3按钮+忽略 |
| v3: 对话窗口 | ✅ 完成 | 2026-04-16 | 多轮对话，屏幕上下文注入，不阻塞主循环 |

## 实测数据（2026-04-16）

| 组件 | 延迟 | 备注 |
|------|------|------|
| PowerShell 截图 | 平均 1.93s | C:\temp\sg.png → /mnt/c/temp/sg.png |
| VLM 分析 (qwen-vl-plus) | 1.15–1.7s | 1280px JPEG，~130KB base64 |
| Stuck 检测 (qwen-plus) | 2.6–3.7s | 每5轮触发一次 |
| 完整一轮总耗时 | 3–5s | 剩余时间 sleep |
