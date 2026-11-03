"""M6b: đọc giờ bận từ Google Calendar và tạo sự kiện cho các phiên ôn trong plan (C5).

Chạy lại nhiều lần không tạo trùng: mỗi phiên mang khoá `studyAgentKey` trong extendedProperties.
Chỉ đụng tới các sự kiện có khoá này; sự kiện khác của người dùng không bao giờ bị sửa hay xóa.
"""
import copy
import logging
import time
from datetime import datetime, timezone

from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import env
from src.contracts import validate_plan
from src.google_auth import SCOPE_CALENDAR, get_credentials

log = logging.getLogger(__name__)

RETRIES = 3
KEY_PROP = "studyAgentKey"
REMINDER_MIN = 15
_sleep = time.sleep  # tách riêng để test không phải chờ thật

MSG_NO_ACCESS = (
    "Không truy cập được lịch Google. Hãy kiểm tra Calendar API đã bật, quyền calendar.events "
    "đã được cấp và GOOGLE_CALENDAR_ID đúng (docs/google-setup.md)."
)
MSG_REFRESH = "Refresh token hết hạn hoặc bị thu hồi, hãy lấy lại theo docs/google-setup.md."


class CalendarError(RuntimeError):
    """Lỗi Calendar; thông điệp tiếng Việt, không chứa khoá, token hay email."""


class CalendarAccessError(CalendarError):
    """Lỗi quyền hoặc xác thực: không thể cứu bằng cách bỏ qua một phiên."""


def calendar_id() -> str:
    """Lịch dùng để xếp phiên: GOOGLE_CALENDAR_ID nếu có, mặc định lịch chính của người dùng."""
    return env("GOOGLE_CALENDAR_ID", "primary")


def make_service():
    """Dịch vụ Calendar v3 dùng chung OAuth với Drive; không gọi mạng khi tạo."""
    return build("calendar", "v3", credentials=get_credentials([SCOPE_CALENDAR]), cache_discovery=False)


def _execute(request):
    """Chạy một yêu cầu, thử lại 429/5xx tối đa RETRIES lượt, đổi lỗi thành CalendarError tiếng Việt."""
    for attempt in range(RETRIES):
        try:
            return request.execute()
        except RefreshError:
            raise CalendarAccessError(MSG_REFRESH) from None
        except HttpError as err:
            status = err.resp.status
            raw = err.content if isinstance(err.content, bytes) else str(err.content).encode()
            retryable = status == 429 or status >= 500 or (status == 403 and b"ratelimit" in raw.lower())
            if retryable and attempt < RETRIES - 1:
                log.warning("Calendar trả lỗi %s, thử lại lần %s", status, attempt + 2)
                _sleep(2 ** (attempt + 1))
                continue
            if status in (403, 404) and not retryable:
                raise CalendarAccessError(MSG_NO_ACCESS) from None
            raise CalendarError(f"Google Calendar trả lỗi {status} sau {attempt + 1} lần thử") from None


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _merge(spans):
    merged = []
    for s, e in sorted(spans):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def list_busy(service, calendar_id: str, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Khoảng bận trong [start, end), sắp tăng dần, đã gộp các khoảng chồng nhau."""
    spans, token = [], None
    while True:
        page = _execute(service.events().list(
            calendarId=calendar_id, timeMin=start.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=250, pageToken=token))
        for ev in page.get("items", []):
            if ev.get("status") == "cancelled" or ev.get("transparency") == "transparent":
                continue
            begin, finish = ev.get("start", {}), ev.get("end", {})
            if "dateTime" not in begin or "dateTime" not in finish:  # sự kiện cả ngày
                continue
            s, e = max(_parse(begin["dateTime"]), start), min(_parse(finish["dateTime"]), end)
            if e > s:
                spans.append((s, e))
        token = page.get("nextPageToken")
        if not token:
            return _merge(spans)


def session_key(session: dict) -> str:
    """Khoá ổn định theo course_id và giờ bắt đầu (quy về UTC), dùng để chống tạo trùng."""
    start = _parse(session["start"]).astimezone(timezone.utc)
    return f"{session['course_id']}-{start.strftime('%Y%m%dT%H%M%SZ')}"


def _event_body(session: dict, tz_name: str, key: str) -> dict:
    lines = ["Phiên ôn bài do Study Agent xếp tự động."]
    if session.get("reason") == "deadline":
        lines.append("Lý do: sắp đến hạn nộp bài của môn này.")
    names = [n for n in session.get("assignments", []) if isinstance(n, str)]
    if names:
        lines.append("Bài tập đến hạn: " + "; ".join(names))
    return {
        "summary": f"Ôn bài: {session['course']}",
        "description": "\n".join(lines),
        "start": {"dateTime": session["start"], "timeZone": tz_name},
        "end": {"dateTime": session["end"], "timeZone": tz_name},
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": REMINDER_MIN}]},
        "extendedProperties": {"private": {KEY_PROP: key}},
    }


def _existing_id(service, calendar_id: str, key: str) -> str | None:
    page = _execute(service.events().list(
        calendarId=calendar_id, privateExtendedProperty=f"{KEY_PROP}={key}", maxResults=5))
    for ev in page.get("items", []):
        if ev.get("status") != "cancelled":
            return ev["id"]
    return None


def create_events(service, calendar_id: str, plan: dict) -> dict:
    """Tạo sự kiện cho từng phiên chưa có calendar_event_id, trả plan mới đã điền id (không sửa plan đầu vào)."""
    result = copy.deepcopy(plan)
    for session in result["sessions"]:
        if session.get("calendar_event_id"):
            continue
        key = session_key(session)
        try:
            event_id = _existing_id(service, calendar_id, key)
            if event_id is None:
                created = _execute(service.events().insert(
                    calendarId=calendar_id, body=_event_body(session, result["timezone"], key)))
                event_id = created["id"]
            session["calendar_event_id"] = event_id
        except CalendarAccessError:
            raise
        except CalendarError as err:
            log.warning("Bỏ qua một phiên ôn của môn %s: %s", session.get("course_id"), err)
    return validate_plan(result)
