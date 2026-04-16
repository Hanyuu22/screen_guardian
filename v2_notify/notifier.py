"""
v2_notify / notifier.py — PyQt5 弹窗
注意：必须在主线程（QApplication 所在线程）调用 show()
通过 GuardianSignals 从后台线程触发
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QApplication,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from typing import Callable

FONT_FAMILY = "Microsoft YaHei"


class PopupWindow(QWidget):
    def __init__(self, reason: str, suggestions: list,
                 on_select: Callable | None = None,
                 on_dismiss: Callable | None = None):
        super().__init__()
        self._on_select = on_select
        self._on_dismiss = on_dismiss
        self._build_ui(reason, suggestions)

    def _build_ui(self, reason, suggestions):
        self.setWindowTitle("Screen Guardian - Alert")
        self.setFixedWidth(500)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        title_bar = QFrame()
        title_bar.setStyleSheet("background-color: #2c3e50;")
        title_bar.setFixedHeight(44)
        tl = QHBoxLayout(title_bar)
        lbl = QLabel("  Screen Guardian  —  发现可能的问题")
        lbl.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        lbl.setStyleSheet("color: white; background: transparent;")
        tl.addWidget(lbl)
        layout.addWidget(title_bar)

        # 内容区
        inner = QFrame()
        inner.setStyleSheet("background: white;")
        il = QVBoxLayout(inner)
        il.setContentsMargins(16, 12, 16, 8)
        il.setSpacing(8)

        reason_lbl = QLabel(f"检测到：{reason}")
        reason_lbl.setFont(QFont(FONT_FAMILY, 10))
        reason_lbl.setStyleSheet(
            "background:#ecf0f1; color:#2c3e50; padding:8px; border-radius:4px;")
        reason_lbl.setWordWrap(True)
        il.addWidget(reason_lbl)

        colors = ["#3498db", "#27ae60", "#8e44ad"]
        for i, s in enumerate(suggestions[:3]):
            btn = QPushButton(f"  {i+1}.  {s}")
            btn.setFont(QFont(FONT_FAMILY, 9))
            c = colors[i % len(colors)]
            btn.setStyleSheet(f"""
                QPushButton {{background:{c}; color:white; border:none;
                              border-radius:4px; padding:8px 12px; text-align:left;}}
                QPushButton:hover {{background:{c}; opacity:0.85;}}
            """)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i, text=s: self._select(idx, text))
            il.addWidget(btn)

        dismiss_btn = QPushButton("没问题，忽略")
        dismiss_btn.setFont(QFont(FONT_FAMILY, 9))
        dismiss_btn.setStyleSheet("""
            QPushButton {background:#bdc3c7; color:#7f8c8d; border:none;
                         border-radius:4px; padding:6px 14px;}
        """)
        dismiss_btn.setCursor(Qt.PointingHandCursor)
        dismiss_btn.clicked.connect(self._dismiss)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(dismiss_btn)
        il.addLayout(row)
        il.addSpacing(6)
        layout.addWidget(inner)
        self.adjustSize()

        # 右下角定位
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 20,
                  screen.height() - self.height() - 60)

    def _select(self, idx, text):
        self.close()
        if self._on_select:
            self._on_select(idx, text)

    def _dismiss(self):
        self.close()
        if self._on_dismiss:
            self._on_dismiss()
