"""v3_interact / config.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "v1_loop"))
from config import *  # noqa: F401, F403
