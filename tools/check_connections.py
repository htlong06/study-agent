"""Kiểm tra kết nối thật tới Canvas, LLM, Google Drive và Google Calendar bằng khoá trong môi trường (.env hoặc Secrets).

Cách dùng:
    python tools/check_connections.py                      # dịch vụ thiếu khoá thì bỏ qua
    python tools/check_connections.py --require canvas,gemini,drive,calendar
    python tools/check_connections.py --write-calendar     # tạo rồi xóa ngay một sự kiện thử (kiểm tra quyền ghi lịch)
Thoát mã 1 nếu có dịch vụ lỗi hoặc dịch vụ bắt buộc (--require) bị thiếu khoá.
Công cụ không bao giờ in khoá hay token; thông báo lỗi chỉ gồm câu tiếng Việt hoặc tên loại lỗi.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import gcal, llm  # noqa: E402
from src.canvas import CanvasClient  # noqa: E402
from src.config import env, load_env  # noqa: E402
from src.google_auth import GoogleAuthError, has_google_config, missing_vars  # noqa: E402
from src.store import DriveStore, StoreError, make_store  # noqa: E402

OK, SKIP, FAIL = "ok", "skip", "fail"
SYMBOL = {OK: "✓", SKIP: "–", FAIL: "✗"}
SERVICES = ("canvas", "gemini", "groq", "openrouter", "drive", "calendar")
TEST_FILE = "kiem-tra-ket-noi.json"


def _unexpected(exc: Exception) -> tuple[str, str]:
    return FAIL, f"lỗi không rõ ({exc.__class__.__name__})"


def check_canvas() -> tuple[str, str]:
    base, token = env("CANVAS_BASE_URL"), env("CANVAS_TOKEN")
    missing = [n for n, v in (("CANVAS_BASE_URL", base), ("CANVAS_TOKEN", token)) if not v]
    if missing:
        return SKIP, "thiếu " + ", ".join(missing)
    try:
        courses = CanvasClient(base, token).courses()
    except PermissionError as exc:
        return FAIL, str(exc)
    except requests.RequestException as exc:
        return FAIL, f"lỗi mạng ({exc.__class__.__name__}), kiểm tra CANVAS_BASE_URL"
    except Exception as exc:  # noqa: BLE001 - công cụ chẩn đoán: báo mọi lỗi mà không lộ nội dung
        return _unexpected(exc)
    return OK, f"đọc được {len(courses)} môn học (chỉ đọc)"


def check_llm(name: str) -> tuple[str, str]:
    key_name, fn = llm.PROVIDERS[name]
    if not env(key_name):
        return SKIP, f"thiếu {key_name}"
    try:
        text = fn("Chỉ trả lời đúng một từ: ok", None, False)
    except llm.LLMError as exc:
        return FAIL, str(exc)
    except Exception as exc:  # noqa: BLE001
        return _unexpected(exc)
    return (OK, "model trả lời bình thường") if text and text.strip() else (FAIL, "model trả về rỗng")


def check_drive() -> tuple[str, str]:
    if not has_google_config():
        return SKIP, "thiếu " + ", ".join(missing_vars())
    try:
        store = make_store()
        if not isinstance(store, DriveStore):
            return FAIL, "không dựng được kho Drive"
        payload = {"ghi_chú": "Tiếng Việt có dấu", "at": datetime.now(timezone.utc).isoformat()}
        store.put_json(TEST_FILE, payload)
        if store.get_json(TEST_FILE) != payload:
            return FAIL, "ghi được nhưng đọc lại không khớp"
        names = store.list_names()
    except (StoreError, GoogleAuthError) as exc:
        return FAIL, str(exc)
    except Exception as exc:  # noqa: BLE001
        return _unexpected(exc)
    return OK, f"ghi và đọc lại được {TEST_FILE} trong thư mục {env('DRIVE_FOLDER_NAME', 'StudyAgent')} ({len(names)} file)"


def check_calendar(write: bool) -> tuple[str, str]:
    if not has_google_config():
        return SKIP, "thiếu " + ", ".join(missing_vars())
    event_id, service, cal = None, None, gcal.calendar_id()
    try:
        service = gcal.make_service()
        now = datetime.now(timezone.utc)
        busy = gcal.list_busy(service, cal, now, now + timedelta(days=1))
        detail = f"đọc được lịch ({len(busy)} khoảng bận trong 24 giờ tới)"
        if write:
            start = (now + timedelta(days=2)).replace(minute=0, second=0, microsecond=0)
            body = {"summary": "Kiểm tra kết nối Study Agent (tự xóa)",
                    "start": {"dateTime": start.isoformat()}, "end": {"dateTime": (start + timedelta(minutes=30)).isoformat()},
                    "extendedProperties": {"private": {gcal.KEY_PROP: "kiem-tra-ket-noi"}}}
            event_id = gcal._execute(service.events().insert(calendarId=cal, body=body))["id"]
            detail += ", tạo được sự kiện thử"
    except (gcal.CalendarError, GoogleAuthError) as exc:
        return FAIL, str(exc)
    except Exception as exc:  # noqa: BLE001
        return _unexpected(exc)
    finally:
        if event_id:  # luôn dọn sự kiện thử, chỉ xóa đúng sự kiện vừa tạo
            try:
                gcal._execute(service.events().delete(calendarId=cal, eventId=event_id))
            except Exception:  # noqa: BLE001
                print(f"! Không xóa được sự kiện thử {event_id}, hãy xóa tay trong Calendar.", file=sys.stderr)
    return OK, detail + (" và đã xóa" if write else "")


def run(require: set[str], write_calendar: bool) -> tuple[list[tuple[str, str, str]], int]:
    checks = {"canvas": check_canvas, "gemini": lambda: check_llm("gemini"), "groq": lambda: check_llm("groq"),
              "openrouter": lambda: check_llm("openrouter"), "drive": check_drive,
              "calendar": lambda: check_calendar(write_calendar)}
    results = []
    for name in SERVICES:
        status, detail = checks[name]()
        if status == SKIP and name in require:
            status = FAIL
            detail += " (dịch vụ bắt buộc)"
        results.append((name, status, detail))
    return results, int(any(s == FAIL for _, s, _ in results))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--require", default="", help="dịch vụ bắt buộc, cách nhau dấu phẩy")
    parser.add_argument("--write-calendar", action="store_true", help="tạo rồi xóa một sự kiện thử")
    args = parser.parse_args(argv)
    require = {s.strip() for s in args.require.split(",") if s.strip()}
    unknown = require - set(SERVICES)
    if unknown:
        print("Tên dịch vụ không hợp lệ: " + ", ".join(sorted(unknown)) + ". Chọn trong: " + ", ".join(SERVICES))
        return 2
    load_env()
    results, code = run(require, args.write_calendar)
    lines = [f"{SYMBOL[status]} {name}: {detail}" for name, status, detail in results]
    print("\n".join(lines))
    if code:
        verdict = "CÓ LỖI, xem các dòng ✗ ở trên"
    elif all(status == SKIP for _, status, _ in results):
        verdict = "CHƯA KIỂM TRA ĐƯỢC DỊCH VỤ NÀO (thiếu khoá hết)"
    else:
        verdict = "CÁC DỊCH VỤ ĐÃ KIỂM TRA ĐỀU ĐẠT"
    print("Kết quả: " + verdict)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## Kiểm tra kết nối\n\n" + "\n".join(f"- {line}" for line in lines) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
