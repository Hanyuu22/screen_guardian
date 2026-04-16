"""
v1_loop / guardian.py — 核心监控循环
截图 → diff → VLM分析 → history → 每5轮 stuck 检测 → 终端输出
"""
import subprocess
import time
import json
import re
import io
import base64
import hashlib
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image

# ── 路径修正：支持从任意目录运行 ──────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    API_KEY, API_BASE, PROXIES, VLM_MODEL, TEXT_MODEL,
    WSL_READ_PATH, CHECK_INTERVAL, DETECT_EVERY,
    HISTORY_SIZE, COOLDOWN, STUCK_CONFIDENCE_THRESHOLD,
    IMG_MAX_WIDTH, IMG_QUALITY, LOG_DIR,
)

# ── 日志配置 ──────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"v1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
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
    '{"app": "当前应用名", "task": "用户正在做什么（15字内）", '
    '"status": "normal/loading/error/idle", "anomaly": "异常描述或null"}'
)

DETECT_PROMPT = """\
以下是用户屏幕最近 {n} 次状态记录（时间顺序，每条间隔约{interval}秒）：

{history}

请判断用户是否陷入困境（重复操作无进展、长时间报错、安装/编译卡住、等待超时等）。

只返回 JSON：
{{"stuck": true或false, "confidence": 0到1的小数, "reason": "简短原因或null", "suggestions": ["建议1", "建议2", "建议3"]}}
"""


# ════════════════════════════════════════════════════
# 截图
# ════════════════════════════════════════════════════

def take_screenshot() -> bool:
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command', PS_SCREENSHOT],
            capture_output=True, timeout=12
        )
        return result.returncode == 0 and os.path.exists(WSL_READ_PATH)
    except Exception as e:
        log.warning(f"截图失败: {e}")
        return False


# ════════════════════════════════════════════════════
# 图像处理
# ════════════════════════════════════════════════════

def img_hash(path: str) -> str:
    img = Image.open(path).resize((64, 36)).convert("L")
    return hashlib.md5(img.tobytes()).hexdigest()


def img_to_base64(path: str) -> str:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if w > IMG_MAX_WIDTH:
        img = img.resize((IMG_MAX_WIDTH, int(h * IMG_MAX_WIDTH / w)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=IMG_QUALITY)
    return base64.b64encode(buf.getvalue()).decode()


# ════════════════════════════════════════════════════
# LLM 调用
# ════════════════════════════════════════════════════

def call_llm(messages: list, model: str, max_tokens: int = 200) -> str:
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    resp = requests.post(API_BASE, headers=HEADERS, json=payload,
                         proxies=PROXIES, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def analyze_screen(b64_img: str) -> dict:
    """VLM 分析当前截图 → 返回结构化状态 dict"""
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
            {"type": "text", "text": VLM_PROMPT},
        ]
    }]
    raw = call_llm(messages, VLM_MODEL, max_tokens=150)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {"app": "unknown", "task": raw[:50], "status": "unknown", "anomaly": None}


def detect_stuck(history: list) -> dict | None:
    """分析历史，判断是否 stuck"""
    lines = []
    for i, h in enumerate(history, 1):
        anomaly = f"  ⚠ {h['anomaly']}" if h.get("anomaly") else ""
        lines.append(f"{i}. [{h['app']}] {h['task']} (状态: {h['status']}){anomaly}")

    prompt = DETECT_PROMPT.format(
        n=len(history),
        interval=CHECK_INTERVAL,
        history="\n".join(lines),
    )
    messages = [{"role": "user", "content": prompt}]
    try:
        raw = call_llm(messages, TEXT_MODEL, max_tokens=300)
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        log.warning(f"stuck 检测失败: {e}")
    return None


# ════════════════════════════════════════════════════
# 主循环
# ════════════════════════════════════════════════════

def run():
    log.info("=" * 55)
    log.info("Screen Guardian v1 启动  Ctrl+C 退出")
    log.info(f"截图间隔: {CHECK_INTERVAL}s  检测周期: 每{DETECT_EVERY}轮")
    log.info("=" * 55)

    history: list[dict] = []
    last_hash: str | None = None
    last_alert_time: float = 0.0
    cycle = 0

    while True:
        cycle += 1
        t_cycle = time.time()
        log.info(f"── 第 {cycle} 轮 ──────────────────────────────")

        # 1. 截图
        if not take_screenshot():
            log.warning("截图失败，跳过本轮")
            time.sleep(CHECK_INTERVAL)
            continue

        # 2. Diff：计算 hash，判断画面是否变化
        current_hash = img_hash(WSL_READ_PATH)
        if current_hash == last_hash:
            log.info("画面无变化 → 跳过 VLM，复用上条历史")
            if history:
                # 复制最后一条，标记 repeat
                entry = dict(history[-1])
                entry["repeated"] = True
                history.append(entry)
            else:
                history.append({"app": "unknown", "task": "初始静止", "status": "idle", "anomaly": None})
        else:
            # 3. VLM 分析
            last_hash = current_hash
            t_vlm = time.time()
            b64 = img_to_base64(WSL_READ_PATH)
            state = analyze_screen(b64)
            vlm_elapsed = round(time.time() - t_vlm, 2)

            log.info(f"VLM ({vlm_elapsed}s) → [{state['app']}] {state['task']}  状态:{state['status']}")
            if state.get("anomaly"):
                log.info(f"  ⚠  异常: {state['anomaly']}")

            history.append(state)

        # 保持历史长度
        if len(history) > HISTORY_SIZE:
            history.pop(0)

        # 4. 每 DETECT_EVERY 轮做一次 stuck 检测
        if cycle % DETECT_EVERY == 0 and len(history) >= 3:
            now = time.time()
            if now - last_alert_time < COOLDOWN:
                remaining = int(COOLDOWN - (now - last_alert_time))
                log.info(f"[检测] 冷却期内，剩余 {remaining}s，跳过")
            else:
                log.info("[检测] 分析历史中...")
                t_det = time.time()
                result = detect_stuck(history)
                det_elapsed = round(time.time() - t_det, 2)

                if result:
                    stuck = result.get("stuck", False)
                    conf  = result.get("confidence", 0)
                    reason = result.get("reason", "")
                    log.info(f"[检测] ({det_elapsed}s) stuck={stuck}  confidence={conf}")
                    if reason:
                        log.info(f"[检测] 原因: {reason}")
                    for s in result.get("suggestions", []):
                        log.info(f"[检测]   → {s}")

                    if stuck and conf >= STUCK_CONFIDENCE_THRESHOLD:
                        log.info("[!] 触发困境警告！（v2 将在此处弹窗）")
                        last_alert_time = now
                else:
                    log.info("[检测] 返回结果无效")

        # 5. 等待下一轮
        elapsed = time.time() - t_cycle
        sleep_time = max(0, CHECK_INTERVAL - elapsed)
        log.info(f"本轮耗时 {round(elapsed,2)}s，等待 {round(sleep_time,1)}s")
        time.sleep(sleep_time)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log.info("\n用户中断，退出。")
