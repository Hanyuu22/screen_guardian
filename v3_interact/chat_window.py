"""
v3_interact / chat_window.py — 带屏幕上下文的多轮对话窗口
支持追问，关闭后主循环继续运行
"""
import threading
import tkinter as tk
from tkinter import scrolledtext, font as tkfont
from typing import Callable
import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "v1_loop"))
from context_builder import build_system_prompt
from config import API_KEY, API_BASE, PROXIES, TEXT_MODEL

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


class ChatWindow:
    """多轮对话窗口"""

    def __init__(
        self,
        history: list[dict],
        stuck_reason: str,
        selected_option: str | None,
        suggestions: list[str],
        initial_message: str,
    ):
        self.messages: list[dict] = []  # 对话历史（不含 system）
        self.system_prompt = build_system_prompt(history, stuck_reason, selected_option)
        self.initial_message = initial_message
        self.suggestions = suggestions
        self._sending = False

    def open(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        root = tk.Tk()
        root.title("Screen Guardian — 帮助对话")
        root.geometry("560x520")
        root.resizable(True, True)
        root.attributes("-topmost", True)

        # 窗口居中
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"560x520+{(sw-560)//2}+{(sh-560)//2}")

        title_font = tkfont.Font(family="Microsoft YaHei", size=11, weight="bold")
        msg_font   = tkfont.Font(family="Microsoft YaHei", size=9)
        input_font = tkfont.Font(family="Microsoft YaHei", size=10)

        # ── 标题 ──────────────────────────────────────
        tk.Frame(root, bg="#2c3e50", height=40).pack(fill="x")
        # Re-place label on top of frame trick via pack order
        root.children[list(root.children)[-1]].pack_forget()

        header = tk.Frame(root, bg="#2c3e50", height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="  Screen Guardian — 帮助对话",
                 bg="#2c3e50", fg="white", font=title_font, anchor="w"
                 ).pack(fill="both", expand=True, padx=8)

        # ── 对话区 ────────────────────────────────────
        chat_frame = tk.Frame(root, bg="white")
        chat_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        self.chat_box = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, state="disabled",
            font=msg_font, bg="#f9f9f9", relief="flat",
            padx=8, pady=8,
        )
        self.chat_box.pack(fill="both", expand=True)

        # 文字颜色标签
        self.chat_box.tag_config("ai_name",   foreground="#2980b9", font=(msg_font.actual()["family"], 9, "bold"))
        self.chat_box.tag_config("ai_text",   foreground="#2c3e50")
        self.chat_box.tag_config("user_name", foreground="#27ae60", font=(msg_font.actual()["family"], 9, "bold"))
        self.chat_box.tag_config("user_text", foreground="#2c3e50")
        self.chat_box.tag_config("thinking",  foreground="#95a5a6", font=(msg_font.actual()["family"], 8, "italic"))

        # ── 输入区 ────────────────────────────────────
        input_frame = tk.Frame(root, bg="white", pady=4)
        input_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.input_box = tk.Text(
            input_frame, height=3, font=input_font,
            relief="solid", bd=1, padx=6, pady=4,
            wrap=tk.WORD,
        )
        self.input_box.pack(side="left", fill="both", expand=True)
        self.input_box.bind("<Return>", self._on_enter)
        self.input_box.bind("<Shift-Return>", lambda e: None)  # Shift+Enter 换行

        send_btn = tk.Button(
            input_frame,
            text="发送\n(Enter)",
            font=tkfont.Font(family="Microsoft YaHei", size=9),
            bg="#3498db", fg="white",
            activebackground="#2980b9", activeforeground="white",
            relief="flat", padx=8,
            cursor="hand2",
            command=self._send,
        )
        send_btn.pack(side="right", fill="y", padx=(6, 0))
        self.send_btn = send_btn

        self.root = root

        # 显示 AI 初始消息
        self._append_ai(self.initial_message)
        self.messages.append({"role": "assistant", "content": self.initial_message})

        root.mainloop()

    def _append_ai(self, text: str):
        self.chat_box.config(state="normal")
        self.chat_box.insert(tk.END, "助手  ", "ai_name")
        self.chat_box.insert(tk.END, text + "\n\n", "ai_text")
        self.chat_box.config(state="disabled")
        self.chat_box.see(tk.END)

    def _append_user(self, text: str):
        self.chat_box.config(state="normal")
        self.chat_box.insert(tk.END, "你  ", "user_name")
        self.chat_box.insert(tk.END, text + "\n\n", "user_text")
        self.chat_box.config(state="disabled")
        self.chat_box.see(tk.END)

    def _append_thinking(self):
        self.chat_box.config(state="normal")
        self.chat_box.insert(tk.END, "助手正在思考...\n", "thinking")
        self.chat_box.config(state="disabled")
        self.chat_box.see(tk.END)

    def _remove_thinking(self):
        """删除最后一行"助手正在思考..."行"""
        self.chat_box.config(state="normal")
        end_idx = self.chat_box.index(tk.END)
        # 向前找 "thinking" 标签的最后位置
        start = self.chat_box.search("助手正在思考...", "1.0", backwards=True, stopindex=tk.END)
        if start:
            line_end = self.chat_box.index(f"{start} lineend+1c")
            self.chat_box.delete(start, line_end)
        self.chat_box.config(state="disabled")

    def _on_enter(self, event):
        if not event.state & 0x1:  # 没按 Shift
            self._send()
            return "break"

    def _send(self):
        if self._sending:
            return
        text = self.input_box.get("1.0", tk.END).strip()
        if not text:
            return

        self.input_box.delete("1.0", tk.END)
        self._append_user(text)
        self.messages.append({"role": "user", "content": text})
        self._sending = True
        self.send_btn.config(state="disabled")
        self._append_thinking()

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

        # 回到主线程更新 UI
        self.root.after(0, self._on_reply, reply)

    def _on_reply(self, reply: str):
        self._remove_thinking()
        self._append_ai(reply)
        self._sending = False
        self.send_btn.config(state="normal")
        self.input_box.focus_set()


def open_chat(
    history: list[dict],
    stuck_reason: str,
    selected_option: str | None,
    suggestions: list[str],
    initial_message: str,
) -> ChatWindow:
    """对外接口：打开对话窗口并返回实例"""
    win = ChatWindow(
        history=history,
        stuck_reason=stuck_reason,
        selected_option=selected_option,
        suggestions=suggestions,
        initial_message=initial_message,
    )
    win.open()
    return win


# ── 独立测试 ──────────────────────────────────────────
if __name__ == "__main__":
    import time

    mock_history = [
        {"app": "Terminal", "task": "运行 pip install torch", "status": "loading", "anomaly": None},
        {"app": "Terminal", "task": "pip install 进度条卡在47%", "status": "loading", "anomaly": "下载进度长时间无变化"},
        {"app": "Terminal", "task": "pip install 进度条仍卡在47%", "status": "loading", "anomaly": "进度条卡住超过1分钟"},
    ]

    win = open_chat(
        history=mock_history,
        stuck_reason="pip install torch 进度条卡在47%超过2分钟",
        selected_option="改用国内镜像源重新安装",
        suggestions=[
            "pip install torch -i https://pypi.tuna.tsinghua.edu.cn/simple/",
            "检查网络代理配置",
            "用 conda install pytorch 替代",
        ],
        initial_message=(
            "我注意到你的 pip 安装进度卡住了，这通常是网络问题导致的。\n\n"
            "你选择了使用国内镜像源，这是个好方法。\n\n"
            "请先按 Ctrl+C 终止当前安装，然后运行：\n\n"
            "pip install torch -i https://pypi.tuna.tsinghua.edu.cn/simple/\n\n"
            "有什么其他问题可以告诉我。"
        ),
    )

    print("对话窗口已打开，主线程继续运行...")
    time.sleep(60)
    print("测试结束")
