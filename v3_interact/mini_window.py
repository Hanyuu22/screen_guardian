"""
v3_interact / mini_window.py — 常驻状态小窗
右上角固定显示，实时反映监控状态，不抢焦点
"""
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

FONT_FAMILY = "Microsoft YaHei"

STATUS_STYLE = {
    "monitoring": ("#27ae60", "● 监控中"),   # 绿
    "paused":     ("#e67e22", "● 对话中"),   # 橙
    "alert":      ("#e74c3c", "● 发现问题"), # 红
}


class MiniWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._reposition()

    def _build_ui(self):
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool                   # 不在任务栏显示
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(240, 48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # 状态指示 + 文字
        self._status_lbl = QLabel("● 监控中")
        self._status_lbl.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        self._status_lbl.setStyleSheet("color:#27ae60;")
        layout.addWidget(self._status_lbl)

        # 当前任务
        self._task_lbl = QLabel("等待首次截图...")
        self._task_lbl.setFont(QFont(FONT_FAMILY, 8))
        self._task_lbl.setStyleSheet("color:#bdc3c7;")
        self._task_lbl.setMaximumWidth(140)
        layout.addWidget(self._task_lbl, stretch=1)

        self.setStyleSheet("""
            QWidget {
                background: rgba(30, 39, 46, 210);
                border-radius: 8px;
            }
        """)

    def _reposition(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 16, 16)

    def set_status(self, key: str, task: str = ""):
        """key: 'monitoring' | 'paused' | 'alert'"""
        color, text = STATUS_STYLE.get(key, STATUS_STYLE["monitoring"])
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(f"color:{color};")
        if task:
            # 截断过长文字
            display = task if len(task) <= 14 else task[:13] + "…"
            self._task_lbl.setText(display)

    def set_task(self, app: str, task: str):
        text = f"[{app}] {task}" if app and app != "unknown" else task
        display = text if len(text) <= 16 else text[:15] + "…"
        self._task_lbl.setText(display)
