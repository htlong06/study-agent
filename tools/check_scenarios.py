"""Kiểm tra mọi mã kịch bản trong docs/test-plan.md đều có test tương ứng.

Cách dùng:
    python tools/check_scenarios.py            # tất cả module
    python tools/check_scenarios.py M3 M4      # chỉ các module nêu tên
Thoát mã 1 nếu còn kịch bản chưa có test.

Một kịch bản `M3-04` được coi là có test khi trong thư mục tests/ (hoặc web/*.test.js
cho M8) xuất hiện `m3_04` (tên hàm) hoặc `M3-04` (docstring, comment).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "test-plan.md"


def scenario_ids(modules=None):
    ids = re.findall(r"^\| (M\d+[ab]?-\d+) \|", PLAN.read_text(encoding="utf-8"), flags=re.M)
    if modules:
        wanted = {m.upper() for m in modules}
        ids = [i for i in ids if i.split("-")[0].upper() in wanted]
    return ids


def test_corpus():
    files = list((ROOT / "tests").glob("test_*.py")) + list((ROOT / "web").glob("*.test.js"))
    return "\n".join(f.read_text(encoding="utf-8") for f in files).lower()


def main(argv):
    ids = scenario_ids(argv or None)
    if not ids:
        print("Không tìm thấy kịch bản nào cho các module đã chọn.")
        return 1
    corpus = test_corpus()
    missing = [i for i in ids if i.lower() not in corpus and i.lower().replace("-", "_") not in corpus]
    print(f"{len(ids) - len(missing)}/{len(ids)} kịch bản đã có test.")
    for i in missing:
        print("  thiếu:", i)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
