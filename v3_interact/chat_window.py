"""
v3_interact / chat_window.py — PyQt5 多轮对话窗口
必须在主线程（QApplication 所在线程）调用 show()
"""
import threading
import sys
import requests
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFrame, QApplication,
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QTextCursor

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "v1_loop"))
from context_builder import build_system_prompt
from config import API_KEY, API_BASE, PROXIES, TEXT_MODEL

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
FONT_FAMILY = "Microsoft YaHei"


class _Signals(QObject):
    append_msg   = pyqtSignal(str, str)  # (role, text)
    set_thinking = pyqtSignal(bool)
    enable_send  = pyqtSignal(bool)


class ChatWindow(QWidget):
    def __init__(self, history, stuck_reason, selected_option, suggestions, initial_message):
        super().__init__()
        self.system_prompt = build_system_prompt(history, stuck_reason, selected_option)
        self.initial_message = initial_message
        self.messages = []
        self._sending = False
        self._sig = _Signals()
        self._sig.append_msg.connect(self._on_append)
        self._sig.set_thinking.connect(self._on_thinking)
        self._sig.enable_send.connect(self._on_enable)
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("Screen Guardian")
        self.resize(580, 540)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Window)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        hdr = QFrame()
        hdr.setStyleSheet("background:#2c3e50;")
        hdr.setFixedHeight(44)
        hl = QHBoxLayout(hdr)
        title = QLabel("  Screen Guardian — 帮助对话")
        title.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        title.setStyleSheet("color:white; background:transparent;")
        hl.addWidget(title)
        layout.addWidget(hdr)

        # 对话区
        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        self.chat_box.setFont(QFont(FONT_FAMILY, 10))
        self.chat_box.setStyleSheet("QTextEdit{background:#f9f9f9; border:none; padding:8px;}")
        layout.addWidget(self.chat_box, stretch=1)

        # 思考中提示
        self.thinking_lbl = QLabel("  助手正在思考...")
        self.thinking_lbl.setFont(QFont(FONT_FAMILY, 9))
        self.thinking_lbl.setStyleSheet("color:#95a5a6; padding:4px 8px;")
        self.thinking_lbl.hide()
        layout.addWidget(self.thinking_lbl)

        # 输入区
        input_frame = QFrame()
        input_frame.setStyleSheet("background:white; border-top:1px solid #ddd;")
        il = QHBoxLayout(input_frame)
        il.setContentsMargins(8, 8, 8, 8)
        il.setSpacing(8)

        self.input_box = QTextEdit()
        self.input_box.setFont(QFont(FONT_FAMILY, 10))
        self.input_box.setFixedHeight(72)
        self.input_box.setPlaceholderText("输入问题，Enter 发送，Shift+Enter 换行...")
        self.input_box.setStyleSheet(
            "QTextEdit{border:1px solid #ccc; border-radius:4px; padding:6px;}")
        self.input_box.installEventFilter(self)
        il.addWidget(self.input_box, stretch=1)

        self.send_btn = QPushButton("发送\n(Enter)")
        self.send_btn.setFont(QFont(FONT_FAMILY, 9))
        self.send_btn.setFixedSize(72, 72)
        self.send_btn.setStyleSheet("""
            QPushButton{background:#3498db; color:white; border:none; border-radius:4px;}
            QPushButton:hover{background:#2980b9;}
            QPushButton:disabled{background:#bdc3c7;}
        """)
        self.send_btn.clicked.connect(self._send)
        il.addWidget(self.send_btn)
        layout.addWidget(input_frame)

        # 居中
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2,
                  (screen.height() - self.height()) // 2)

    def show_with_initial(self):
        self.show()
        self._append_bubble("assistant", self.initial_message)
        self.messages.append({"role": "assistant", "content": self.initial_message})

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if obj is self.input_box and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self._send()
                return True
        return super().eventFilter(obj, event)

    def _append_bubble(self, role, text):
        if role == "assistant":
            name, color = "助手", "#2980b9"
        else:
            name, color = "你", "#27ae60"
        self.chat_box.append(
            f'<span style="color:{color};font-weight:bold;">{name}</span>')
        self.chat_box.append(
            f'<span style="color:#2c3e50;">{text.replace(chr(10), "<br>")}</span><br>')
        self.chat_box.verticalScrollBar().setValue(
            self.chat_box.verticalScrollBar().maximum())

    def _on_append(self, role, text):
        self._append_bubble(role, text)

    def _on_thinking(self, visible):
        self.thinking_lbl.setVisible(visible)

    def _on_enable(self, enabled):
        self.send_btn.setEnabled(enabled)
        self._sending = not enabled

    def _send(self):
        if self._sending:
            return
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        self.input_box.clear()
        self._sig.append_msg.emit("user", text)
        self.messages.append({"role": "user", "content": text})
        self._sending = True
        self._sig.enable_send.emit(False)
        self._sig.set_thinking.emit(True)
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
        self._sig.set_thinking.emit(False)
        self._sig.append_msg.emit("assistant", reply)
        self._sig.enable_send.emit(True)
