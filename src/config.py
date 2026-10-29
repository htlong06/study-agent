"""Đọc cấu hình từ biến môi trường và file .env (không in ra bất kỳ khoá nào)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATERIALS_DIR = ROOT / "data" / "materials"
OUT_DIR = ROOT / "out"


def load_env(path=None):
    """Nạp .env nếu có. Biến đã đặt sẵn trong môi trường (ví dụ GitHub Secrets) được ưu tiên."""
    path = Path(path) if path else ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def env(name, default=None):
    value = os.environ.get(name)
    return value if value else default


def env_int(name, default):
    try:
        return int(env(name, default))
    except (TypeError, ValueError):
        return default
