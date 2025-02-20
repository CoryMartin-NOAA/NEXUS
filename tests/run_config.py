"""
Run one or more of our config cases on Hera to test them.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CONFIG_BASE_DIR = REPO / "config"

config_dirs = sorted(p for p in CONFIG_BASE_DIR.glob("*") if p.is_dir())

print(config_dirs)
