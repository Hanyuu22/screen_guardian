# Screen Guardian

> 运行在 WSL2 后台的屏幕守护助手。定期截取 Windows 桌面，用 Vision LLM 判断你是否卡住，
> 自动弹窗提供帮助建议，点击后进入带屏幕上下文的多轮对话。

版本更新记录见 [CHANGELOG.md](CHANGELOG.md)

---

## 这是什么

Screen Guardian 是一个**主动式桌面助手**，解决的痛点是：

> 你对着报错发呆、反复重试同一个操作、安装包一直卡住——但你没有意识到自己已经卡住了，或者懒得开浏览器搜。

它在后台默默观察屏幕，发现异常时主动找你，而不是等你主动发问。

---

## 工作方式

```
每 20 秒截一次 Windows 屏幕
    │
    ├─ 画面无变化 → 跳过 VLM（节省费用）
    │
    └─ 有变化 → qwen-vl-plus 分析（应用名 / 任务 / 异常）
                    │
                每 5 轮聚合 → qwen-plus 判断是否卡住
                    │
                stuck=true 且置信度 > 0.6
                    │
                弹出通知窗（3 个建议选项）
                    │
                用户点击选项 → 注入屏幕上下文 → 多轮对话窗口
```

**两层 LLM 分工：**

| 层 | 模型 | 触发 | 作用 |
|----|------|------|------|
| 视觉层 | qwen-vl-plus | 每次截图 | 一句话描述屏幕状态 |
| 判断层 | qwen-plus | 每 5 轮 | 分析历史，输出是否卡住 |
| 对话层 | qwen-plus | 用户点击后 | 带屏幕上下文的多轮问答 |

---

## 存在形式

- **后台 daemon 线程**：负责截图 → VLM 分析 → stuck 检测，不阻塞 UI
- **Qt 主线程**：运行 PyQt5 事件循环，响应所有 UI 操作
- **持久对话窗**：启动即创建，最小化在任务栏，随时可点开聊天；检测到问题时自动弹出并注入上下文
- **进程管理**：`run.sh` 防重复启动，`stop.sh` 发 SIGINT 优雅退出

整个程序是**单进程、双线程**，通过 `pyqtSignal` 在后台线程和 Qt 主线程之间通信。

---

## 快速开始

### WSL2（推荐）

```bash
git clone git@github.com:Hanyuu22/screen_guardian.git
cd screen_guardian
bash setup.sh          # 安装依赖、字体、配置 API Key
source ~/.bashrc
bash run.sh            # 启动
```

### Windows 原生 Python

```bash
git clone git@github.com:Hanyuu22/screen_guardian.git
cd screen_guardian
pip install -r requirements.txt
set DASHSCOPE_API_KEY=sk-你的key
python v3_interact\guardian.py
```

> Windows 下中文输入完全无障碍，推荐在 Windows 原生运行。

---

## 日常操作

```bash
bash ~/screen_guardian/run.sh     # 启动
bash ~/screen_guardian/stop.sh    # 停止

# 查看运行日志
tail -f ~/screen_guardian/logs/*.log

# 手动 kill
pgrep -a python | grep guardian
kill -SIGINT <PID>
```

---

## 中文输入（WSL2）

WSLg 下已配置 ibus + libpinyin，开箱可用：

- 点击输入框后**直接打拼音**，候选词自动出现
- 在 libpinyin 内按 **Shift** 切换中英文模式
- **Ctrl+Space** 切换输入法（libpinyin <-> 英文键盘）

> 注：WSLg 下输入法体验与 Windows 微软拼音有差异，如需完全一致请改用 Windows 原生 Python 运行。

---

## 注意事项

**API 费用**
- 画面不变时自动跳过 VLM 调用
- 每 5 轮才触发一次 stuck 判断
- 实际费用极低，正常使用每天约几分钱

**冷却期**
- 触发弹窗后有 **5 分钟冷却**，防止反复打扰
- 从用户关闭对话窗时重新计时

**隐私**
- 截图只发送给 DashScope API（阿里云），不经过其他服务器
- 截图缓存在 `C:\temp\sg.png`，程序退出后不自动清理

**资源占用**
- 截图约 1.9s / 次，通过 PowerShell 调用，CPU 占用极低
- VLM 调用走网络，本机无 GPU 推理

---

## 依赖

```
requests >= 2.28
Pillow   >= 9.0
PyQt5    >= 5.15
mss      >= 9.0
```

系统依赖（Linux / WSL2）：
```bash
sudo apt-get install fonts-noto-cjk libxcb-xinerama0
```

---

## 架构

```
screen_guardian/
├── run.sh / stop.sh     进程管理
├── setup.sh             一键环境配置
├── requirements.txt
├── shared/
│   └── capture.py       跨平台截图（WSL2 / Linux / Windows 自动识别）
├── v0_probe/            可行性验证脚本（截图 / VLM / stuck 各自独立测试）
├── v1_loop/             核心监控循环 + 配置
├── v2_notify/           PyQt5 弹窗通知
└── v3_interact/         完整版（推荐使用）
    ├── guardian.py      入口：Qt 主线程 + 监控后台线程
    ├── chat_window.py   持久对话窗口
    └── context_builder.py  屏幕历史 -> LLM system prompt
```

---

## 平台支持

| 平台 | 状态 | 截图方式 |
|------|------|---------|
| WSL2 | 完整支持 | PowerShell 截取 Windows 屏幕 |
| 纯 Linux（X11） | 支持 | mss 库 |
| Windows 原生 Python | 支持（中文输入最佳） | mss 库 |
| macOS | 未测试 | mss 库（理论可用） |
