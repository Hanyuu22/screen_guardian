"""
v3_interact / chat_window.py — PyQt5 多轮对话窗口
带屏幕上下文，支持追问，关闭后主循环继续运行
"""
import threading
import sys
import requests
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFrame, QScrollArea,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor, QPalette, QTextCursor

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "v1_loop"))
from context_builder import build_system_prompt
from config import API_KEY, API_BASE, PROXIES, TEXT_MODEL

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
FONT_FAMILY = "Microsoft YaHei"

_qt_app = None
_qt_lock = threading.Lock()


def _get_app():
    global _qt_app
    with _qt_lock:
        if _qt_app is None:
            _qt_app = QApplication.instance() or QApplication(sys.argv)
    return _qt_app


class _Signals(QObject):
    append_msg = pyqtSignal(str, str)   # (role, text)
    set_thinking = pyqtSignal(bool)
    enable_send = pyqtSignal(bool)


class ChatWindow(QWidget):
    def __init__(self, history, stuck_reason, selected_option, suggestions, initial_message):
        app = _get_app()
        super().__init__()
        self.system_prompt = build_system_prompt(history, stuck_reason, selected_option)
        self.initial_message = initial_message
        self.messages = []
        self._sending = False
        self._signals = _Signals()
        self._signals.append_msg.connect(self._on_append_msg)
        self._signals.set_thinking.connect(self._on_set_thinking)
        self._signals.enable_send.connect(self._on_enable_send)
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("Screen Guardian — 帮助对话")
        self.resize(580, 540)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        title_bar = QFrame()
        title_bar.setStyleSheet("background-color: #2c3e50;")
        title_bar.setFixedHeight(44)
        title_layout = QHBoxLayout(title_bar)
        title_label = QLabel("  Screen Guardian — 帮助对话")
        title_label.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        title_label.setStyleSheet("color: white; background: transparent;")
        title_layout.addWidget(title_label)
        layout.addWidget(title_bar)

        # 对话区
        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        self.chat_box.setFont(QFont(FONT_FAMILY, 10))
        self.chat_box.setStyleSheet("""
            QTextEdit {
                background: #f9f9f9;
                border: none;
                padding: 8px;
            }
        """)
        layout.addWidget(self.chat_box, stretch=1)

        # 思考中提示
        self.thinking_label = QLabel("  助手正在思考...")
        self.thinking_label.setFont(QFont(FONT_FAMILY, 9))
        self.thinking_label.setStyleSheet("color: #95a5a6; padding: 4px 8px;")
        self.thinking_label.hide()
        layout.addWidget(self.thinking_label)

        # 输入区
        input_frame = QFrame()
        input_frame.setStyleSheet("background: white; border-top: 1px solid #ddd;")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(8)

        self.input_box = QTextEdit()
        self.input_box.setFont(QFont(FONT_FAMILY, 10))
        self.input_box.setFixedHeight(72)
        self.input_box.setPlaceholderText("输入问题，Enter 发送，Shift+Enter 换行...")
        self.input_box.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        self.input_box.installEventFilter(self)
        input_layout.addWidget(self.input_box, stretch=1)

        self.send_btn = QPushButton("发送\n(Enter)")
        self.send_btn.setFont(QFont(FONT_FAMILY, 9))
        self.send_btn.setFixedSize(72, 72)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #3498db; color: white;
                border: none; border-radius: 4px;
            }
            QPushButton:hover { background: #2980b9; }
            QPushButton:disabled { background: #bdc3c7; }
        """)
        self.send_btn.clicked.connect(self._send)
        input_layout.addWidget(self.send_btn)

        layout.addWidget(input_frame)

        # 居中显示
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        from PyQt5.QtGui import QKeyEvent
        if obj is self.input_box and event.type() == QEvent.KeyPress:
            key_event = QKeyEvent(event)
            if key_event.key() == Qt.Key_Return and not (key_event.modifiers() & Qt.ShiftModifier):
                self._send()
                return True
        return super().eventFilter(obj, event)

    def _append_bubble(self, role: str, text: str):
        cursor = self.chat_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_box.setTextCursor(cursor)

        if role == "assistant":
            name_color = "#2980b9"
            name = "助手"
        else:
            name_color = "#27ae60"
            name = "你"

        self.chat_box.append(f'<span style="color:{name_color};font-weight:bold;">{name}</span>')
        self.chat_box.append(f'<span style="color:#2c3e50;">{text.replace(chr(10), "<br>")}</span>')
        self.chat_box.append("")
        self.chat_box.verticalScrollBar().setValue(self.chat_box.verticalScrollBar().maximum())

    def _on_append_msg(self, role: str, text: str):
        self._append_bubble(role, text)

    def _on_set_thinking(self, visible: bool):
        if visible:
            self.thinking_label.show()
        else:
            self.thinking_label.hide()

    def _on_enable_send(self, enabled: bool):
        self.send_btn.setEnabled(enabled)
        self._sending = not enabled

    def _send(self):
        if self._sending:
            return
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        self.input_box.clear()
        self._signals.append_msg.emit("user", text)
        self.messages.append({"role": "user", "content": text})
        self._sending = True
        self._signals.enable_send.emit(False)
        self._signals.set_thinking.emit(True)
        threading.Thread(target=self._call_llm, daemon=True).start()

    def _call_llm(self):
        try:
            payload = {
                "model": TEXT_MODEL,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    *self.messages,
                ],
                "max_tokens": 600,
            }
            resp = requests.post(API_BASE, headers=HEADERS, json=payload,
                                 proxies=PROXIES, timeout=30)
            resp.raise_for_status()
            reply = resp.json()["choices"][0]["message"]["content"].strip()
            self.messages.append({"role": "assistant", "content": reply})
        except Exception as e:
            reply = f"请求失败：{e}"

        self._signals.set_thinking.emit(False)
        self._signals.append_msg.emit("assistant", reply)
        self._signals.enable_send.emit(True)

    def show_with_initial(self):
        self.show()
        self._append_bubble("assistant", self.initial_message)
        self.messages.append({"role": "assistant", "content": self.initial_message})


def open_chat(history, stuck_reason, selected_option, suggestions, initial_message) -> "ChatWindow":
    def _run():
        app = _get_app()
        win = ChatWindow(history, stuck_reason, selected_option, suggestions, initial_message)
        win.show_with_initial()
        app.exec_()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


# ── 独立测试 ──────────────────────────────────────────
if __name__ == "__main__":
    import time

    mock_history = [
        {"app": "Terminal", "task": "pip install torch", "status": "loading", "anomaly": None},
        {"app": "Terminal", "task": "pip 卡在47%", "status": "loading", "anomaly": "进度条长时间无变化"},
    ]
    open_chat(
        history=mock_history,
        stuck_reason="pip install 卡住",
        selected_option="改用国内镜像",
        suggestions=["pip install torch -i https://pypi.tuna.tsinghua.edu.cn/simple/", "检查代理", "用conda替代"],
        initial_message="我注意到 pip 安装卡住了。\n\n先按 Ctrl+C 取消，然后运行：\npip install torch -i https://pypi.tuna.tsinghua.edu.cn/simple/",
    )
    print("主线程继续...")
    time.sleep(30)
