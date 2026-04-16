"""
v0_probe / test_analyze.py
验证 qwen-vl-plus 视觉分析：准确性、耗时、Prompt 质量
"""
import base64
import time
import json
import io
import requests
from PIL import Image

WSL_READ_PATH = "/mnt/c/temp/sg.png"
API_KEY = "sk-765ab8c8b795499dba6bea8e5373646f"
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
PROXIES = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

def img_to_base64(path: str, max_width: int = 1280) -> str:
    """缩放后转 base64，减少 token 消耗"""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        img = img.resize((max_width, int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def analyze(b64_img: str, prompt: str) -> dict:
    payload = {
        "model": "qwen-vl-plus",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 200,
    }
    t0 = time.time()
    resp = requests.post(API_URL, headers=HEADERS, json=payload,
                         proxies=PROXIES, timeout=30)
    elapsed = time.time() - t0
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    usage = resp.json().get("usage", {})
    return {"content": content, "elapsed": round(elapsed, 2), "usage": usage}


PROMPTS = {
    "简短描述": (
        "用一句话描述当前屏幕内容（应用名+用户正在做什么），"
        "重点标注：错误信息、等待/加载状态、卡住的迹象。控制在25字以内。"
    ),
    "结构化状态": (
        "分析屏幕，以 JSON 格式返回：\n"
        '{"app": "当前应用", "task": "用户正在做什么", '
        '"status": "normal/loading/error/idle", "anomaly": "异常描述或null"}\n'
        "只返回 JSON。"
    ),
    "异常检测": (
        "屏幕上是否有错误提示、弹窗、卡死迹象或异常状态？"
        "如果有，详细描述；如果没有，回答'正常'。"
    ),
}


if __name__ == "__main__":
    import subprocess

    # 先截一张新鲜截图
    PS_SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$s = [Windows.Forms.Screen]::PrimaryScreen.Bounds
$b = New-Object Drawing.Bitmap($s.Width, $s.Height)
$g = [Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen(0, 0, 0, 0, $b.Size)
$b.Save('C:\temp\sg.png')
$g.Dispose(); $b.Dispose()
"""
    print("=" * 55)
    print("Screen Guardian v0 — VLM 视觉分析验证")
    print("=" * 55)

    print("\n[1] 截取当前屏幕...")
    subprocess.run(['powershell.exe', '-NoProfile', '-Command', PS_SCRIPT],
                   capture_output=True, timeout=15)
    print("  截图完成")

    print("\n[2] 压缩图像 (→ 1280px JPEG)...")
    b64 = img_to_base64(WSL_READ_PATH)
    print(f"  base64 长度: {len(b64):,} chars (~{len(b64)//1024}KB)")

    print("\n[3] 测试三种 Prompt...\n")
    for name, prompt in PROMPTS.items():
        print(f"  ── Prompt: {name} ──")
        try:
            result = analyze(b64, prompt)
            print(f"  耗时  : {result['elapsed']}s")
            print(f"  Token : {result['usage']}")
            print(f"  回复  : {result['content']}")
        except Exception as e:
            print(f"  错误  : {e}")
        print()

    print("=" * 55)
    print("结论: 观察上方三种 Prompt 的效果，选择最适合的用于 v1")
    print("推荐: '简短描述' 用于每轮存储，'结构化状态' 可选用于检测")
    print("=" * 55)
