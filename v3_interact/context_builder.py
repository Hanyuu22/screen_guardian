"""
v3_interact / context_builder.py
将 screen history + 用户选择 → LLM system prompt
"""


def build_system_prompt(history: list[dict], stuck_reason: str, selected_option: str | None = None) -> str:
    """构建带屏幕上下文的 system prompt"""
    history_lines = []
    for i, h in enumerate(history, 1):
        anomaly = f"  [异常: {h['anomaly']}]" if h.get("anomaly") else ""
        repeated = " (重复帧)" if h.get("repeated") else ""
        history_lines.append(
            f"  {i}. [{h.get('app','?')}] {h.get('task','?')}  状态:{h.get('status','?')}{anomaly}{repeated}"
        )
    history_str = "\n".join(history_lines) if history_lines else "  (暂无记录)"

    selected_str = (
        f"\n用户认为最可能的问题是：\n  {selected_option}"
        if selected_option else ""
    )

    return f"""你是一个桌面助手，专门帮助用户解决在电脑使用过程中遇到的问题。

## 用户屏幕最近状态（时间顺序）
{history_str}

## 检测到的问题
{stuck_reason or "屏幕状态异常，用户可能遇到了困难"}{selected_str}

## 你的职责
1. 基于上述上下文，给出具体可操作的帮助建议
2. 如果用户追问，结合上下文继续深入解答
3. 回答简洁，优先给出命令/步骤，而非长篇理论
4. 用中文回答
"""


def build_first_message(stuck_reason: str, selected_option: str | None, suggestions: list[str]) -> str:
    """生成对话第一条 AI 消息"""
    if selected_option:
        return (
            f"我注意到你可能遇到了这个问题：**{selected_option}**\n\n"
            f"让我来帮你解决。请告诉我更多细节，或者直接试试下面的方向：\n\n"
            + "\n".join(f"{i+1}. {s}" for i, s in enumerate(suggestions[:3]))
        )
    else:
        return (
            f"我检测到你可能遇到了困难：{stuck_reason}\n\n"
            f"以下是一些可能有用的方向：\n\n"
            + "\n".join(f"{i+1}. {s}" for i, s in enumerate(suggestions[:3]))
            + "\n\n你可以告诉我更多情况，我来帮你进一步分析。"
        )
