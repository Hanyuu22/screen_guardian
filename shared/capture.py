"""
shared/capture.py — 跨平台截图模块
自动检测环境选择截图方式：
  - WSL2  : PowerShell 截取 Windows 屏幕
  - Linux : mss 截取 X11/Wayland 屏幕
  - Windows: mss 直接截取
"""
import os
import sys
import platform
import subprocess
import tempfile
from pathlib import Path


def _is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except Exception:
        return False


IS_WSL     = _is_wsl()
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX   = platform.system() == "Linux" and not IS_WSL

# 截图保存路径
if IS_WSL:
    SCREENSHOT_PATH = "/mnt/c/temp/sg_guardian.png"
else:
    SCREENSHOT_PATH = str(Path(tempfile.gettempdir()) / "sg_guardian.png")

_PS_SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$s = [Windows.Forms.Screen]::PrimaryScreen.Bounds
$b = New-Object Drawing.Bitmap($s.Width, $s.Height)
$g = [Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen(0, 0, 0, 0, $b.Size)
New-Item -ItemType Directory -Force -Path C:\temp | Out-Null
$b.Save('C:\temp\sg_guardian.png')
$g.Dispose(); $b.Dispose()
"""


def take_screenshot() -> bool:
    """截图并保存到 SCREENSHOT_PATH，返回是否成功"""
    try:
        if IS_WSL:
            return _capture_wsl()
        else:
            return _capture_mss()
    except Exception as e:
        print(f"截图失败: {e}", file=sys.stderr)
        return False


def _capture_wsl() -> bool:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", _PS_SCRIPT],
        capture_output=True, timeout=12,
    )
    return result.returncode == 0 and os.path.exists(SCREENSHOT_PATH)


def _capture_mss() -> bool:
    import mss
    import mss.tools
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # 主显示器
        img = sct.grab(monitor)
        mss.tools.to_png(img.rgb, img.size, output=SCREENSHOT_PATH)
    return os.path.exists(SCREENSHOT_PATH)
