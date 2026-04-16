"""
v0_probe / test_capture.py
验证 PowerShell 截图是否可用：耗时、文件大小、图像可读性
"""
import subprocess
import time
import os
from pathlib import Path

WIN_SAVE_PATH = r"C:\temp\sg.png"
WSL_READ_PATH = "/mnt/c/temp/sg.png"

PS_SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$s = [Windows.Forms.Screen]::PrimaryScreen.Bounds
$b = New-Object Drawing.Bitmap($s.Width, $s.Height)
$g = [Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen(0, 0, 0, 0, $b.Size)
New-Item -ItemType Directory -Force -Path C:\temp | Out-Null
$b.Save('C:\temp\sg.png')
$g.Dispose()
$b.Dispose()
Write-Output "OK $($s.Width)x$($s.Height)"
"""

def take_screenshot() -> dict:
    t0 = time.time()
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-Command', PS_SCRIPT],
        capture_output=True, text=True, timeout=15
    )
    elapsed = time.time() - t0

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    info = {
        "elapsed": round(elapsed, 2),
        "returncode": result.returncode,
        "ps_output": stdout,
        "ps_error": stderr,
        "file_exists": os.path.exists(WSL_READ_PATH),
        "file_size_kb": 0,
        "resolution": "unknown",
    }

    if info["file_exists"]:
        info["file_size_kb"] = round(os.path.getsize(WSL_READ_PATH) / 1024, 1)

    # 解析分辨率
    for token in stdout.split():
        if 'x' in token and token.replace('x', '').isdigit() is False:
            try:
                w, h = token.split('x')
                int(w); int(h)
                info["resolution"] = token
            except:
                pass

    return info


def verify_image_readable():
    """用 Pillow 打开验证图像完整性"""
    try:
        from PIL import Image
        img = Image.open(WSL_READ_PATH)
        return f"OK  mode={img.mode}  size={img.size}"
    except Exception as e:
        return f"FAIL  {e}"


if __name__ == "__main__":
    print("=" * 50)
    print("Screen Guardian v0 — 截图验证")
    print("=" * 50)

    print("\n[1] 执行截图...")
    info = take_screenshot()

    print(f"  耗时      : {info['elapsed']}s")
    print(f"  returncode: {info['returncode']}")
    print(f"  PS 输出   : {info['ps_output'] or '(空)'}")
    if info['ps_error']:
        print(f"  PS 错误   : {info['ps_error'][:200]}")
    print(f"  文件存在  : {info['file_exists']}")
    print(f"  文件大小  : {info['file_size_kb']} KB")
    print(f"  分辨率    : {info['resolution']}")

    print("\n[2] 验证图像可读性...")
    print(f"  Pillow    : {verify_image_readable()}")

    print("\n[3] 连续截图3次，测量稳定性...")
    times = []
    for i in range(3):
        t0 = time.time()
        subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command', PS_SCRIPT],
            capture_output=True, timeout=15
        )
        times.append(round(time.time() - t0, 2))
        print(f"  第{i+1}次: {times[-1]}s")

    print(f"\n  平均耗时: {round(sum(times)/len(times), 2)}s")
    print(f"  最大耗时: {max(times)}s")

    print("\n" + "=" * 50)
    ok = info['file_exists'] and info['file_size_kb'] > 10 and info['returncode'] == 0
    print(f"结论: {'✓ 截图验证通过' if ok else '✗ 截图验证失败，请检查上方错误'}")
    print("=" * 50)
