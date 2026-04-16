"""
v2_notify / notifier.py — PyQt5 弹窗通知
在独立线程弹出，不阻塞主循环
回调：用户选择 → on_select(choice_index, choice_text)
      用户忽略 → on_dismiss()
"""
import threading
import sys
from typing import Callable

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

FONT_FAMILY = "Microsoft YaHei"
_qt_app = None
_qt_lock = threading.Lock()


def _get_app():
    global _qt_app
    with _qt_lock:
        if _qt_app is None:
            _qt_app = QApplication.instance() or QApplication(sys.argv)
    return _qt_app


class PopupWindow(QWidget):
    def __init__(self, reason, suggestions, on_select, on_dismiss):
        app = _get_app()
        super().__init__()
        self._on_select = on_select
        self._on_dismiss = on_dismiss
        self._build_ui(reason, suggestions)

    def _build_ui(self, reason, suggestions):
        self.setWindowTitle("Screen Guardian")
        self.setFixedWidth(500)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        title_bar = QFrame()
        title_bar.setStyleSheet("background-color: #2c3e50;")
        title_bar.setFixedHeight(44)
        title_layout = QHBoxLayout(title_bar)
        title_label = QLabel("  Screen Guardian  —  发现可能的问题")
        title_label.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        title_label.setStyleSheet("color: white; background: transparent;")
        title_layout.addWidget(title_label)
        layout.addWidget(title_bar)

        # 原因
        inner = QFrame()
        inner.setStyleSheet("background: white;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 12, 16, 8)
        inner_layout.setSpacing(8)

        reason_label = QLabel(f"检测到：{reason}")
        reason_label.setFont(QFont(FONT_FAMILY, 10))
        reason_label.setStyleSheet(
            "background: #ecf0f1; color: #2c3e50; padding: 8px; border-radius: 4px;"
        )
        reason_label.setWordWrap(True)
        inner_layout.addWidget(reason_label)

        # 建议按钮
        colors = ["#3498db", "#27ae60", "#8e44ad"]
        for i, suggestion in enumerate(suggestions[:3]):
            btn = QPushButton(f"  {i+1}.  {suggestion}")
            btn.setFont(QFont(FONT_FAMILY, 9))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {colors[i % len(colors)]};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 12px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    opacity: 0.85;
                    background: {colors[i % len(colors)]};
                }}
            """)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i, text=suggestion: self._select(idx, text))
            inner_layout.addWidget(btn)

        # 忽略按钮
        dismiss_btn = QPushButton("没问题，忽略")
        dismiss_btn.setFont(QFont(FONT_FAMILY, 9))
        dismiss_btn.setStyleSheet("""
            QPushButton {
                background: #bdc3c7; color: #7f8c8d;
                border: none; border-radius: 4px;
                padding: 6px 14px;
            }
        """)
        dismiss_btn.setCursor(Qt.PointingHandCursor)
        dismiss_btn.clicked.connect(self._dismiss)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(dismiss_btn)
        inner_layout.addLayout(btn_row)
        inner_layout.addSpacing(6)

        layout.addWidget(inner)
        self.adjustSize()

        # 窗口定位：屏幕右下角
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 20, screen.height() - self.height() - 60)

    def _select(self, idx, text):
        self.close()
        if self._on_select:
            self._on_select(idx, text)

    def _dismiss(self):
        self.close()
        if self._on_dismiss:
            self._on_dismiss()


def show_popup(
    reason: str,
    suggestions: list,
    on_select: Callable | None = None,
    on_dismiss: Callable | None = None,
) -> None:
    def _run():
        app = _get_app()
        win = PopupWindow(reason, suggestions, on_select, on_dismiss)
        win.show()
        app.exec_()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


# ── 独立测试 ──────────────────────────────────────────
if __name__ == "__main__":
    import time

    def on_select(idx, text):
        print(f"[回调] 选项{idx+1}: {text}")

    def on_dismiss():
        print("[回调] 忽略")

    show_popup(
        reason="pip install torch 进度条卡在47%超过3分钟",
        suggestions=[
            "改用国内镜像：pip install torch -i https://pypi.tuna.tsinghua.edu.cn/simple/",
            "检查代理设置，尝试切换/关闭 VPN",
            "用 conda install pytorch -c pytorch 替代",
        ],
        on_select=on_select,
        on_dismiss=on_dismiss,
    )
    print("主线程继续运行...")
    time.sleep(20)
