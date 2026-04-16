"""
v0_probe / test_detect.py
验证 qwen-plus stuck 判断：JSON 格式、判断准确性、Prompt 有效性
用 mock history 构造三种场景测试
"""
import time
import json
import re
import requests

API_KEY = "sk-765ab8c8b795499dba6bea8e5373646f"
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
PROXIES = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

DETECT_PROMPT_TEMPLATE = """\
以下是用户屏幕最近 {n} 次状态记录（时间顺序，每条间隔约20秒）：

{history}

请判断用户是否陷入困境（如：重复操作无进展、长时间报错未解决、安装/编译卡住、等待超时等）。

返回 JSON，格式如下（只返回 JSON，不要其他文字）：
{{"stuck": true或false, "confidence": 0到1的小数, "reason": "简短原因或null", "suggestions": ["建议1", "建议2", "建议3"]}}
"""


# 三种 mock 场景
MOCK_SCENARIOS = {
    "正常工作流": [
        {"app": "VSCode", "task": "编辑 Python 文件 utils.py", "status": "normal", "anomaly": None},
        {"app": "Terminal", "task": "运行 pytest 测试", "status": "normal", "anomaly": None},
        {"app": "Browser", "task": "查看 pytest 文档", "status": "normal", "anomaly": None},
        {"app": "VSCode", "task": "修改代码逻辑", "status": "normal", "anomaly": None},
        {"app": "Terminal", "task": "再次运行 pytest，测试通过", "status": "normal", "anomaly": None},
    ],
    "pip 安装卡死": [
        {"app": "Terminal", "task": "运行 pip install torch", "status": "loading", "anomaly": None},
        {"app": "Terminal", "task": "pip install torch 仍在下载，进度条卡在 47%", "status": "loading", "anomaly": "下载进度长时间无变化"},
        {"app": "Terminal", "task": "pip install torch 进度条卡在 47%", "status": "loading", "anomaly": "进度条卡住超过1分钟"},
        {"app": "Terminal", "task": "pip install torch 进度条仍卡在 47%", "status": "loading", "anomaly": "进度条长时间未动"},
        {"app": "Terminal", "task": "pip install torch 没有任何变化", "status": "loading", "anomaly": "疑似网络问题或卡死"},
    ],
    "重复报错未解决": [
        {"app": "Terminal", "task": "运行 python app.py", "status": "error", "anomaly": "ModuleNotFoundError: No module named 'fastapi'"},
        {"app": "Browser", "task": "搜索 ModuleNotFoundError fastapi", "status": "normal", "anomaly": None},
        {"app": "Terminal", "task": "运行 python app.py", "status": "error", "anomaly": "ModuleNotFoundError: No module named 'fastapi'"},
        {"app": "Terminal", "task": "pip install fastapi 完成", "status": "normal", "anomaly": None},
        {"app": "Terminal", "task": "运行 python app.py", "status": "error", "anomaly": "ModuleNotFoundError: No module named 'fastapi'"},
    ],
}


def format_history(records: list) -> str:
    lines = []
    for i, r in enumerate(records, 1):
        anomaly_str = f"  ⚠ 异常: {r['anomaly']}" if r.get("anomaly") else ""
        lines.append(f"{i}. [{r['app']}] {r['task']} (状态: {r['status']}){anomaly_str}")
    return "\n".join(lines)


def detect_stuck(records: list) -> dict:
    history_str = format_history(records)
    prompt = DETECT_PROMPT_TEMPLATE.format(n=len(records), history=history_str)

    payload = {
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
    }
    t0 = time.time()
    resp = requests.post(API_URL, headers=HEADERS, json=payload,
                         proxies=PROXIES, timeout=30)
    elapsed = time.time() - t0
    resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"].strip()

    # 提取 JSON（可能被 ```json ``` 包裹）
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    parsed = None
    if m:
        try:
            parsed = json.loads(m.group())
        except json.JSONDecodeError:
            pass

    return {
        "elapsed": round(elapsed, 2),
        "raw": raw,
        "parsed": parsed,
        "usage": resp.json().get("usage", {}),
    }


if __name__ == "__main__":
    print("=" * 58)
    print("Screen Guardian v0 — Stuck 检测验证")
    print("=" * 58)

    all_ok = True
    for scenario_name, records in MOCK_SCENARIOS.items():
        print(f"\n{'─'*58}")
        print(f"场景: {scenario_name}")
        print("历史记录:")
        for line in format_history(records).split('\n'):
            print(f"  {line}")
        print()

        try:
            result = detect_stuck(records)
            print(f"  耗时   : {result['elapsed']}s")
            print(f"  Token  : {result['usage'].get('total_tokens', '?')}")
            print(f"  原始回复: {result['raw'][:300]}")

            p = result["parsed"]
            if p:
                print(f"\n  解析结果:")
                print(f"    stuck      = {p.get('stuck')}")
                print(f"    confidence = {p.get('confidence')}")
                print(f"    reason     = {p.get('reason')}")
                print(f"    suggestions:")
                for s in p.get("suggestions", []):
                    print(f"      - {s}")

                # 简单验证
                if scenario_name == "正常工作流" and p.get("stuck") is True:
                    print("  [警告] 正常场景被误判为 stuck")
                    all_ok = False
                elif scenario_name != "正常工作流" and p.get("stuck") is False:
                    print(f"  [警告] 困境场景未被检测到")
                    all_ok = False
                else:
                    print("  [✓] 判断符合预期")
            else:
                print("  [✗] JSON 解析失败")
                all_ok = False

        except Exception as e:
            print(f"  [错误] {e}")
            all_ok = False

    print(f"\n{'='*58}")
    print(f"结论: {'✓ 全部场景判断正确' if all_ok else '✗ 存在误判，需调整 Prompt'}")
    print("=" * 58)
