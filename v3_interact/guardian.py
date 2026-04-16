"""
v3_interact / guardian.py — 完整版
架构：QApplication 在主线程 → 监控循环在后台线程 → Signal 触发 UI
"""
import subprocess, time, json, re, io, base64, hashlib, os, sys, logging, threading, signal
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image

# ── sys.path ─────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "v1_loop"))

from config import (
    API_KEY, API_BASE, PROXIES, VLM_MODEL, TEXT_MODEL,
    WSL_READ_PATH, CHECK_INTERVAL, DETECT_EVERY,
    HISTORY_SIZE, COOLDOWN, STUCK_CONFIDENCE_THRESHOLD,
    IMG_MAX_WIDTH, IMG_QUALITY, LOG_DIR,
)
from context_builder import build_first_message

# importlib 加载 v2_notify/notifier.py（避免同名冲突）
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "v2_notifier",
    str(Path(__file__).parent.parent / "v2_notify" / "notifier.py"),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
PopupWindow = _mod.PopupWindow

from chat_window import ChatWindow

# ── PyQt5 ─────────────────────────────────────────────
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

# ── 日志 ─────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"v3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

PS_SCREENSHOT = r"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$s = [Windows.Forms.Screen]::PrimaryScreen.Bounds
$b = New-Object Drawing.Bitmap($s.Width, $s.Height)
$g = [Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen(0, 0, 0, 0, $b.Size)
New-Item -ItemType Directory -Force -Path C:\temp | Out-Null
$b.Save('C:\temp\sg.png')
$g.Dispose(); $b.Dispose()
"""

VLM_PROMPT = (
    "分析屏幕，以 JSON 格式返回（只返回 JSON，不要其他文字）：\n"
    '{"app":"当前应用名","task":"用户正在做什么（15字内）",'
    '"status":"normal/loading/error/idle","anomaly":"异常描述或null"}'
)

DETECT_PROMPT = """\
以下是用户屏幕最近 {n} 次状态记录（时间顺序，每条间隔约{interval}秒）：
{history}
请判断用户是否陷入困境（重复操作无进展、长时间报错、安装卡住、等待超时等）。
只返回 JSON：
{{"stuck":true或false,"confidence":0到1,"reason":"简短原因或null","suggestions":["建议1","建议2","建议3"]}}
"""


# ════════════════════════════════════════════════════
# Qt Signal 桥：后台线程 → 主线程 UI
# Signal 只传基本类型（str/int），复杂对象通过共享变量传递
# ════════════════════════════════════════════════════
class _Bridge(QObject):
    trigger_popup = pyqtSignal(str)   # token，对应 _pending 里的一条记录

_bridge = _Bridge()
_pending: dict[str, dict] = {}        # token → {reason, suggestions, history}
_open_windows: list = []              # 持有窗口引用，防止被 GC 回收

# ── 暂停标志：对话窗打开时暂停截图 ─────────────────────
_chat_open = threading.Event()        # set = 对话窗打开中，监控暂停
_last_alert_reset = threading.Event() # set = 对话窗关闭，要求重置冷却计时器

# ── 持久化上下文 ──────────────────────────────────────
CONTEXT_FILE = os.path.join(LOG_DIR, "context.json")


def load_context() -> list:
    """启动时从文件加载上一次保留的 history 摘要"""
    try:
        with open(CONTEXT_FILE, encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("history", [])[-HISTORY_SIZE:]
        log.info(f"[上下文] 加载 {len(entries)} 条历史记录（上次保存于 {data.get('saved_at','')}）")
        return entries
    except FileNotFoundError:
        return []
    except Exception as e:
        log.warning(f"[上下文] 加载失败: {e}")
        return []


def save_context(history: list) -> None:
    """对话窗关闭时保存当前 history 到文件"""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "saved_at": datetime.now().isoformat(),
                "history": history,
            }, f, ensure_ascii=False, indent=2)
        log.info(f"[上下文] 已保存 {len(history)} 条记录")
    except Exception as e:
        log.warning(f"[上下文] 保存失败: {e}")


def _make_token() -> str:
    import uuid
    return uuid.uuid4().hex


def _on_trigger_popup(token: str):
    ctx = _pending.pop(token, None)
    if not ctx:
        return

    reason      = ctx["reason"]
    suggestions = ctx["suggestions"]
    history     = ctx["history"]

    def on_select(idx, text):
        log.info(f"[弹窗] 用户选择选项{idx+1}: {text}")
        first_msg = build_first_message(reason, text, suggestions)
        win = ChatWindow(
            history=history,
            stuck_reason=reason,
            selected_option=text,
            suggestions=suggestions,
            initial_message=first_msg,
        )
        win.show_with_initial()
        _open_windows.append(win)
        _chat_open.set()                              # 暂停监控
        log.info("[监控] 对话窗已打开，暂停截图")

        def on_chat_closed():
            if win in _open_windows:
                _open_windows.remove(win)
            save_context(history)                     # 保存上下文
            _last_alert_reset.set()                   # 通知监控循环重置冷却计时器
            _chat_open.clear()                        # 恢复监控
            log.info("[监控] 对话窗已关闭，恢复截图，冷却计时器将重置")

        win.window_closed.connect(on_chat_closed)     # closeEvent 触发，不依赖 C++ 销毁

    def on_dismiss():
        log.info("[弹窗] 用户忽略")

    win = PopupWindow(reason, suggestions, on_select=on_select, on_dismiss=on_dismiss)
    win.show()
    _open_windows.append(win)
    win.destroyed.connect(lambda: _open_windows.remove(win) if win in _open_windows else None)


_bridge.trigger_popup.connect(_on_trigger_popup)


# ════════════════════════════════════════════════════
# 监控逻辑（后台线程）
# ════════════════════════════════════════════════════
def take_screenshot() -> bool:
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", PS_SCREENSHOT],
            capture_output=True, timeout=12,
        )
        return r.returncode == 0 and os.path.exists(WSL_READ_PATH)
    except Exception as e:
        log.warning(f"截图失败: {e}")
        return False


def img_hash(path):
    img = Image.open(path).resize((64, 36)).convert("L")
    return hashlib.md5(img.tobytes()).hexdigest()


def img_to_b64(path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if w > IMG_MAX_WIDTH:
        img = img.resize((IMG_MAX_WIDTH, int(h * IMG_MAX_WIDTH / w)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=IMG_QUALITY)
    return base64.b64encode(buf.getvalue()).decode()


def call_llm(messages, model, max_tokens=200):
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    resp = requests.post(API_BASE, headers=HEADERS, json=payload,
                         proxies=PROXIES, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def analyze_screen(b64):
    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        {"type": "text", "text": VLM_PROMPT},
    ]}]
    raw = call_llm(messages, VLM_MODEL, max_tokens=150)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return {"app": "unknown", "task": raw[:50], "status": "unknown", "anomaly": None}


def detect_stuck(history):
    lines = []
    for i, h in enumerate(history, 1):
        a = f"  ⚠ {h['anomaly']}" if h.get("anomaly") else ""
        lines.append(f"{i}. [{h['app']}] {h['task']} (状态:{h['status']}){a}")
    prompt = DETECT_PROMPT.format(
        n=len(history), interval=CHECK_INTERVAL, history="\n".join(lines))
    try:
        raw = call_llm([{"role": "user", "content": prompt}], TEXT_MODEL, max_tokens=300)
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        log.warning(f"stuck 检测失败: {e}")
    return None


def monitor_loop():
    log.info("=" * 55)
    log.info("Screen Guardian v3 启动（监控线程）")
    log.info(f"截图间隔: {CHECK_INTERVAL}s  检测周期: 每{DETECT_EVERY}轮")
    log.info("=" * 55)

    history  = load_context()           # 加载上次保留的上下文
    last_hash, last_alert, cycle = None, 0.0, 0

    while True:
        # ── 对话窗打开时暂停，每5秒检查一次是否恢复 ──
        if _chat_open.is_set():
            log.info("[监控] 暂停中（对话窗开着）...")
            time.sleep(5)
            continue

        # ── 对话窗刚关闭：重置冷却计时器，从现在起重新计算 ──
        if _last_alert_reset.is_set():
            _last_alert_reset.clear()
            last_alert = 0.0
            log.info("[监控] 冷却计时器已重置（对话窗已关闭）")

        cycle += 1
        t0 = time.time()
        log.info(f"── 第 {cycle} 轮 ──────────────────────────")

        if not take_screenshot():
            time.sleep(CHECK_INTERVAL)
            continue

        cur_hash = img_hash(WSL_READ_PATH)
        if cur_hash == last_hash:
            log.info("画面无变化 → 跳过 VLM")
            if history:
                e = dict(history[-1]); e["repeated"] = True; history.append(e)
            else:
                history.append({"app":"unknown","task":"静止","status":"idle","anomaly":None})
        else:
            last_hash = cur_hash
            t_v = time.time()
            state = analyze_screen(img_to_b64(WSL_READ_PATH))
            log.info(f"VLM ({round(time.time()-t_v,2)}s) → [{state['app']}] {state['task']}  状态:{state['status']}")
            if state.get("anomaly"):
                log.info(f"  ⚠ {state['anomaly']}")
            history.append(state)

        if len(history) > HISTORY_SIZE:
            history.pop(0)

        if cycle % DETECT_EVERY == 0 and len(history) >= 3:
            now = time.time()
            if now - last_alert < COOLDOWN:
                log.info(f"[检测] 冷却中，剩余 {int(COOLDOWN-(now-last_alert))}s")
            else:
                log.info("[检测] 分析历史...")
                result = detect_stuck(history)
                if result:
                    stuck = result.get("stuck", False)
                    conf  = result.get("confidence", 0)
                    log.info(f"[检测] stuck={stuck}  conf={conf}  reason={result.get('reason','')}")
                    if stuck and conf >= STUCK_CONFIDENCE_THRESHOLD:
                        log.info("[!] 触发弹窗")
                        last_alert = now
                        token = _make_token()
                        _pending[token] = {
                            "reason":      result.get("reason", "检测到异常"),
                            "suggestions": result.get("suggestions", []),
                            "history":     list(history),
                        }
                        _bridge.trigger_popup.emit(token)

        time.sleep(max(0, CHECK_INTERVAL - (time.time() - t0)))


# ════════════════════════════════════════════════════
# 入口：Qt 主线程 + 监控后台线程
# ════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # 关闭弹窗不退出程序

    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()

    # 让 Python 信号处理器能被触发：每 500ms 交还控制权一次
    _sigint_timer = QTimer()
    _sigint_timer.start(500)
    _sigint_timer.timeout.connect(lambda: None)

    # Ctrl+C → app.quit() → exec_() 返回
    signal.signal(signal.SIGINT, lambda *_: app.quit())

    log.info("Qt 主线程就绪，按 Ctrl+C 退出")
    sys.exit(app.exec_())
    log.info("退出")
