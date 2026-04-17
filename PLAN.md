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

---

## 后续开发方向

> 仅记录方向和思路，尚未实现。按优先级排列。

---

### P1 — 误判优化：区分"正在解决问题"和"真正卡住"

**问题**
当前 stuck 检测看到 ERROR 关键词就倾向于判断卡住，但程序员正常调试时屏幕上长期有报错是常态。
误报会打断用户思路，比不报更烦。

**方向**

1. **VLM prompt 改为输出状态变化向量**
   不只输出当前状态，同时输出"与上一帧相比是否有进展"：
   ```json
   {"app":"...", "task":"...", "status":"...", "anomaly":"...", "progress": "advancing/stalled/unknown"}
   ```

2. **stuck 判断层加入时间序列分析**
   - 连续 N 轮状态在变化（即使有报错）→ `advancing`，不触发
   - 连续 N 轮相同报错 + 无任何操作变化 → 才判定 `stuck`
   - 建议 N 取 3~4，对应约 1 分钟无进展

3. **加入"活跃度"指标**
   编辑器光标在动、终端有新输出、鼠标在移动 = 用户在工作，无论屏幕上有无报错

4. **提高触发阈值**
   当前 `STUCK_CONFIDENCE_THRESHOLD = 0.6`，考虑提高到 0.75，减少低置信度的误报

---

### P2 — 截图延迟优化

**问题**
PowerShell 每次冷启动约 1.9s，占完整一轮耗时的大头。

**方向**

1. **常驻 PowerShell 进程**
   启动时开一个 PowerShell 子进程保持运行，通过 stdin/stdout 管道发截图指令，
   避免每次冷启动开销，预期降到 0.3~0.5s。

2. **截图与 VLM 调用 overlap**
   当前流程是串行：截图完 → 分析。
   改为：分析上一张图的同时，异步截下一张，两步并行。

3. **粗分辨率预判**
   先用极低分辨率（如 32×18）做 MD5 diff，只在"可能有变化"时才截高清图发 VLM，
   比当前 64×36 还轻量。

4. **事件驱动替代轮询（长期）**
   监听鼠标键盘静止事件，只在用户停止操作超过 X 秒后才截图分析，
   完全消除用户活跃时的无效轮询。

---

### P3 — 安全与隐私

**问题**
截图可能含密码、API token、私人对话等敏感信息，直接上传第三方 API 存在泄露风险。

**方向**

1. **两阶段筛查**
   - 第一阶段：本地轻量模型（或规则）判断截图是否值得分析（有无明显变化/异常）
   - 第二阶段：只有通过第一阶段才上传云端 VLM
   - 目标：减少 60%+ 的截图上传量

2. **敏感区域遮挡**
   允许用户配置"不分析区域"（如密码管理器窗口、特定应用），截图时自动黑化这些区域。

3. **截图即用即删**
   分析完成后立即删除 `C:\temp\sg.png`，不留缓存。

4. **API Key 保护**
   当前明文存 `~/.bashrc`，改为系统 keyring（`keyring` 库）或加密文件存储。

5. **本地 VLM 选项**
   长期目标：支持本地部署的视觉模型（如 InternVL2-2B）作为替代，
   敏感环境下完全不走网络。

---

### P3.5 — 用户状态感知：离线检测 + 弹窗生命周期

**问题**

两个未处理场景：
1. 用户暂时离开，屏幕静止在有报错的画面，程序无法感知，持续截图分析并可能循环触发弹窗
2. stuck 弹窗出现后用户没有点击（正在忙或没注意），弹窗长期悬挂，冷却期空转，期间可能堆积新弹窗

**方向**

**一、系统级离线检测**

不依赖弹窗响应来判断用户是否在场，而是直接读取系统最后输入时间：
- Windows 侧通过 PowerShell 调用 `GetLastInputInfo` 获取鼠标/键盘最后活跃时间
- 超过阈值（建议默认 10 分钟）无输入 → 触发"您还在吗？"确认窗
- 确认窗使用 `Qt.WindowDoesNotAcceptFocus`，不抢焦点，不影响用户正在做的事
- 同时暂停截图循环，直到用户点击"我在"或系统检测到新的输入活动后自动恢复

**二、弹窗倒计时与生命周期管理**

弹窗出现后启动倒计时（建议默认 60s），超时自动消失，期间暂停截图：

```
stuck 弹窗弹出 → 暂停截图
    ├─ 用户点选项    → 进入对话窗，对话关闭后恢复监控（冷却重置）
    ├─ 用户点"没问题" → 消失，恢复截图，冷却 180s
    └─ 60s 超时无响应 → 自动消失，恢复截图，冷却 60s（没看到，快速恢复）
```

**三、冷却时长按场景区分**

当前统一 300s 过于保守，建议改为：

| 消失原因 | 冷却时长 | 理由 |
|----------|----------|------|
| 用户主动点"没问题" | 180s | 用户明确说没事，短期内不再打扰 |
| 用户点选项进入对话 | 对话关闭后重置，不计冷却 | 已处理，应立即恢复正常检测 |
| 60s 超时自动消失 | 60s | 用户没看到，尽快恢复检测 |
| 离线检测触发暂停 | 恢复活跃后直接重置 | 用户回来就重新开始，不惩罚离开 |

**四、统一暂停机制**

离线暂停和弹窗期间暂停共用同一个 `_pause_event`，避免两套状态逻辑并行导致混乱：
```python
_pause_event = threading.Event()   # set = 暂停，clear = 恢复
# 监控循环改为：
while not _stop_event.is_set():
    _pause_event.wait()            # 暂停时阻塞在这里
    ...
```

---

### P4 — 用户设置面板

**问题**
所有参数（冷却时长、截图间隔、检测阈值等）目前硬编码在 `config.py`，修改需要重启程序，不够灵活。

**方向**

**一、settings.json 持久化配置（前提）**

设置面板的基础：启动时读取 `~/.screen_guardian/settings.json` 覆盖默认值，
修改后实时写入，下次启动自动生效。无此机制则设置面板无意义。

```json
{
  "check_interval": 20,
  "detect_every": 5,
  "stuck_confidence_threshold": 0.6,
  "popup_timeout": 60,
  "cooldown_dismissed": 180,
  "cooldown_timeout": 60,
  "idle_detect_minutes": 10,
  "idle_detect_enabled": true,
  "popup_enabled": true
}
```

**二、设置面板 UI**

在对话窗口加一个设置入口（齿轮图标或菜单），打开独立设置窗口，分两组：

- **行为参数**（数字输入/滑块）
  - 截图间隔（秒）
  - 弹窗倒计时（秒）
  - 各场景冷却时长（秒）
  - 离线判定等待时间（分钟）
  - stuck 置信度阈值（0~1）

- **功能开关**（复选框）
  - 启用 stuck 检测弹窗
  - 启用离线检测
  - 截图分析完立即删除缓存文件

**三、参数修改实时生效**

部分参数（如冷却时长、置信度阈值）可以在监控线程下次循环时直接读新值，无需重启。
截图间隔等影响循环节奏的参数，修改后在当前轮结束时生效。

---

### P5 — Windows 原生输入法支持

**问题**
WSLg 下 ibus libpinyin 与 Windows 微软拼音体验有差距，属于平台架构限制，难以从 Linux 侧彻底解决。

**方向**

1. **Windows 原生 Python 运行模式（推荐）**
   `config.py` 已有平台自动检测，主要需要：
   - 验证 Windows 下截图、VLM 调用、PyQt5 全流程可用
   - 补充 Windows 一键启动脚本（`run.bat` 或 PowerShell 脚本）
   - 打包为单文件 `.exe`（用 PyInstaller）方便分发

2. **WSLg Wayland 输入协议（备选，复杂度高）**
   研究能否让 Qt 应用走 Wayland 协议而非 X11，
   理论上 Wayland 下 Windows IME 透传更完整，但目前 WSLg + Qt5 + Wayland 组合不成熟。
