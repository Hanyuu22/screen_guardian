"""v2_notify / config.py — 从 v1 继承，无需修改"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "v1_loop"))
from config import *  # noqa: F401, F403
