"""
v2_notify / notifier.py — tkinter 弹窗通知
在独立线程弹出，不阻塞主循环
回调：用户选择 → on_select(choice_index, choice_text)
      用户忽略 → on_dismiss()
"""
import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable


def show_popup(
    reason: str,
    suggestions: list[str],
    on_select: Callable[[int, str], None] | None = None,
    on_dismiss: Callable[[], None] | None = None,
) -> None:
    """在独立线程中弹出帮助窗口"""

    def _run():
        root = tk.Tk()
        root.title("Screen Guardian")
        root.geometry("480x320")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        # 窗口居中
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - 480) // 2
        y = sh - 380  # 靠近屏幕底部
        root.geometry(f"480x320+{x}+{y}")

        # ── 标题栏 ──────────────────────────────────
        title_frame = tk.Frame(root, bg="#2c3e50", height=44)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame,
            text="  Screen Guardian  —  发现可能的问题",
            bg="#2c3e50", fg="white",
            font=("Microsoft YaHei", 11, "bold"),
            anchor="w",
        ).pack(side="left", fill="both", expand=True, padx=8)

        # ── 原因 ────────────────────────────────────
        reason_frame = tk.Frame(root, bg="#ecf0f1", pady=8)
        reason_frame.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(
            reason_frame,
            text=f"检测到：{reason}",
            bg="#ecf0f1", fg="#2c3e50",
            font=("Microsoft YaHei", 10),
            wraplength=440, justify="left", anchor="w",
        ).pack(fill="x", padx=8)

        # ── 建议按钮 ─────────────────────────────────
        btn_frame = tk.Frame(root, bg="white")
        btn_frame.pack(fill="both", expand=True, padx=16, pady=4)

        btn_font = tkfont.Font(family="Microsoft YaHei", size=9)

        def make_handler(idx, text):
            def handler():
                root.destroy()
                if on_select:
                    on_select(idx, text)
            return handler

        colors = ["#3498db", "#27ae60", "#8e44ad"]
        for i, suggestion in enumerate(suggestions[:3]):
            color = colors[i % len(colors)]
            btn = tk.Button(
                btn_frame,
                text=f"  {i+1}.  {suggestion}",
                font=btn_font,
                bg=color, fg="white",
                activebackground=color, activeforeground="white",
                relief="flat", anchor="w",
                padx=10, pady=6,
                cursor="hand2",
                command=make_handler(i, suggestion),
                wraplength=420,
            )
            btn.pack(fill="x", pady=3)

        # ── 忽略按钮 ─────────────────────────────────
        dismiss_frame = tk.Frame(root, bg="white")
        dismiss_frame.pack(fill="x", padx=16, pady=(0, 10))

        def dismiss():
            root.destroy()
            if on_dismiss:
                on_dismiss()

        tk.Button(
            dismiss_frame,
            text="没问题，忽略",
            font=("Microsoft YaHei", 9),
            bg="#bdc3c7", fg="#7f8c8d",
            activebackground="#95a5a6", activeforeground="white",
            relief="flat", padx=12, pady=4,
            cursor="hand2",
            command=dismiss,
        ).pack(side="right")

        root.mainloop()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


# ── 独立测试 ──────────────────────────────────────────
if __name__ == "__main__":
    import time

    def on_select(idx, text):
        print(f"[回调] 用户选择了选项 {idx+1}: {text}")

    def on_dismiss():
        print("[回调] 用户选择忽略")

    print("弹出测试窗口...")
    show_popup(
        reason="pip install torch 进度条卡住超过3分钟，疑似网络问题",
        suggestions=[
            "改用国内镜像：pip install torch -i https://pypi.tuna.tsinghua.edu.cn/simple/",
            "检查代理设置，尝试关闭/切换 VPN",
            "用 conda install pytorch -c pytorch 替代",
        ],
        on_select=on_select,
        on_dismiss=on_dismiss,
    )

    print("主线程继续运行（模拟主循环不被阻塞）...")
    for i in range(30):
        print(f"  主循环第 {i+1} 秒...")
        time.sleep(1)
    print("测试结束")
