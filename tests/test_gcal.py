"""Kiểm thử M6b (gcal.py). Mã kịch bản M6b-01..M6b-10 nằm trong tên hàm và docstring.

Dùng `service` giả (FakeCalendar) chỉ có events().list/insert, nên mọi lời gọi sửa hoặc xóa đều lỗi ngay.
"""
import copy
from datetime import datetime, timedelta, timezone

import httplib2
import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from src import gcal
from src.contracts import validate_plan
from src.gcal import CalendarAccessError, CalendarError, calendar_id, create_events, list_busy, session_key
from tests import samples

TZ = timezone(timedelta(hours=7))
START = datetime(2026, 11, 1, 0, 0, tzinfo=TZ)
END = datetime(2026, 11, 2, 0, 0, tzinfo=TZ)


def http_error(status, body=b"{}"):
    return HttpError(httplib2.Response({"status": str(status)}), body)


class FakeRequest:
    def __init__(self, fake, method, kwargs):
        self.fake, self.method, self.kwargs = fake, method, kwargs

    def execute(self):
        self.fake.calls.append((self.method, self.kwargs))
        queue = self.fake.errors.get(self.method)
        if queue:
            err = queue.pop(0)
            if err is not None:
                raise err
        return getattr(self.fake, "_" + self.method)(**self.kwargs)


class FakeCalendar:
    """events() chỉ có list và insert; tự động có id, lọc theo privateExtendedProperty, phân trang."""

    def __init__(self, events=None, page_size=100):
        self.events = list(events or [])
        self.errors, self.calls, self.page_size, self._n = {}, [], page_size, 0

    def list(self, **kw): return FakeRequest(self, "list", kw)
    def insert(self, **kw): return FakeRequest(self, "insert", kw)

    def count(self, method):
        return sum(1 for m, _ in self.calls if m == method)

    def _list(self, privateExtendedProperty=None, pageToken=None, **_):
        rows = self.events
        if privateExtendedProperty:
            k, v = privateExtendedProperty.split("=", 1)
            rows = [e for e in rows if e.get("extendedProperties", {}).get("private", {}).get(k) == v]
        i = int(pageToken or 0)
        out = {"items": rows[i:i + self.page_size]}
        if i + self.page_size < len(rows):
            out["nextPageToken"] = str(i + self.page_size)
        return out

    def _insert(self, calendarId, body):
        self._n += 1
        event = dict(body, id=f"ev{self._n}", status="confirmed")
        self.events.append(event)
        return event


class Service:
    """Giống service thật: service.events() trả đối tượng có list và insert."""

    def __init__(self, fake):
        self.fake = fake

    def events(self):
        return self.fake


def make(events=None, page_size=100):
    fake = FakeCalendar(events, page_size)
    return fake, Service(fake)


def ev(start, end, **extra):
    base = {"id": "x", "status": "confirmed",
            "start": {"dateTime": start}, "end": {"dateTime": end}}
    base.update(extra)
    return base


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    waits = []
    monkeypatch.setattr(gcal, "_sleep", waits.append)
    return waits


def test_m6b_01_list_busy_follows_pages():
    """M6b-01: kết quả hai trang, đi hết nextPageToken, gom đủ sự kiện."""
    events = [ev(f"2026-11-01T{h:02d}:00:00+07:00", f"2026-11-01T{h:02d}:30:00+07:00", id=f"e{h}") for h in (8, 10, 14)]
    fake, service = make(events, page_size=2)
    busy = list_busy(service, "primary", START, END)
    assert len(busy) == 3 and fake.count("list") == 2
    assert busy[0][0] == datetime(2026, 11, 1, 8, 0, tzinfo=TZ)


def test_m6b_01_request_parameters():
    """M6b-01: gọi list với singleEvents, orderBy startTime và khoảng thời gian."""
    fake, service = make([])
    list_busy(service, "lich-cua-toi", START, END)
    kw = fake.calls[0][1]
    assert kw["calendarId"] == "lich-cua-toi" and kw["singleEvents"] is True and kw["orderBy"] == "startTime"
    assert kw["timeMin"] == START.isoformat() and kw["timeMax"] == END.isoformat()


def test_m6b_02_ignores_cancelled_transparent_allday():
    """M6b-02: sự kiện cancelled, transparent và cả ngày đều bị bỏ."""
    events = [
        ev("2026-11-01T09:00:00+07:00", "2026-11-01T10:00:00+07:00", status="cancelled"),
        ev("2026-11-01T11:00:00+07:00", "2026-11-01T12:00:00+07:00", transparency="transparent"),
        {"id": "a", "status": "confirmed", "start": {"date": "2026-11-01"}, "end": {"date": "2026-11-02"}},
        ev("2026-11-01T13:00:00+07:00", "2026-11-01T14:00:00+07:00"),
    ]
    _, service = make(events)
    assert list_busy(service, "primary", START, END) == [
        (datetime(2026, 11, 1, 13, tzinfo=TZ), datetime(2026, 11, 1, 14, tzinfo=TZ))]


def test_m6b_03_merge_overlapping_and_adjacent_sorted():
    """M6b-03: khoảng chồng hoặc liền nhau gộp thành một, kết quả tăng dần, mốc UTC vẫn đúng."""
    events = [
        ev("2026-11-01T15:00:00+07:00", "2026-11-01T16:00:00+07:00"),
        ev("2026-11-01T09:00:00+07:00", "2026-11-01T10:30:00+07:00"),
        ev("2026-11-01T10:00:00+07:00", "2026-11-01T11:00:00+07:00"),
        ev("2026-11-01T11:00:00+07:00", "2026-11-01T11:30:00+07:00"),
        ev("2026-11-01T08:30:00Z", "2026-11-01T09:00:00Z"),  # 15:30-16:00 giờ VN, nằm trong khoảng 15:00-16:00
    ]
    _, service = make(events)
    busy = list_busy(service, "primary", START, END)
    assert busy == [(datetime(2026, 11, 1, 9, tzinfo=TZ), datetime(2026, 11, 1, 11, 30, tzinfo=TZ)),
                    (datetime(2026, 11, 1, 15, tzinfo=TZ), datetime(2026, 11, 1, 16, tzinfo=TZ))]


def test_m6b_03_clipped_to_window():
    """M6b-03: sự kiện vắt qua biên cửa sổ được cắt trong [start, end)."""
    _, service = make([ev("2026-10-31T23:00:00+07:00", "2026-11-01T01:00:00+07:00")])
    assert list_busy(service, "primary", START, END) == [(START, datetime(2026, 11, 1, 1, tzinfo=TZ))]


def two_session_plan():
    plan = samples.plan()
    first = copy.deepcopy(plan["sessions"][0])
    second = dict(first, course_id=102, course="Vật lý 2",
                  start="2026-11-02T19:00:00+07:00", end="2026-11-02T19:45:00+07:00")
    first.update(start="2026-11-01T19:00:00+07:00", end="2026-11-01T19:45:00+07:00", calendar_event_id=None)
    second["calendar_event_id"] = None
    plan["sessions"] = [first, second]
    return plan


def test_m6b_04_create_two_events_and_fill_ids():
    """M6b-04: plan 2 phiên gọi tạo 2 sự kiện và điền calendar_event_id."""
    fake, service = make()
    out = create_events(service, "primary", two_session_plan())
    assert fake.count("insert") == 2
    assert [s["calendar_event_id"] for s in out["sessions"]] == ["ev1", "ev2"]
    validate_plan(out)


def test_m6b_05_second_run_does_not_duplicate():
    """M6b-05: chạy lần hai không tạo thêm, dùng lại id theo khoá studyAgentKey."""
    fake, service = make()
    first = create_events(service, "primary", two_session_plan())
    second = create_events(service, "primary", two_session_plan())  # plan gốc chưa có id (như lần chạy mới)
    assert fake.count("insert") == 2
    assert [s["calendar_event_id"] for s in second["sessions"]] == [s["calendar_event_id"] for s in first["sessions"]]
    assert len(fake.events) == 2


def test_m6b_05_session_with_id_skipped():
    """M6b-05: phiên đã có calendar_event_id thì không gọi gì."""
    fake, service = make()
    plan = two_session_plan()
    plan["sessions"][0]["calendar_event_id"] = "da-co"
    out = create_events(service, "primary", plan)
    assert out["sessions"][0]["calendar_event_id"] == "da-co" and fake.count("insert") == 1


def test_m6b_05_session_key_stable_across_timezones():
    """M6b-05: khoá giống nhau cho cùng một thời điểm dù viết ở múi giờ nào, khác nhau khi khác môn hoặc giờ."""
    a = {"course_id": 101, "start": "2026-11-01T19:00:00+07:00"}
    b = {"course_id": 101, "start": "2026-11-01T12:00:00Z"}
    assert session_key(a) == session_key(b)
    assert session_key(a) != session_key(dict(a, course_id=102))
    assert session_key(a) != session_key(dict(a, start="2026-11-01T19:05:00+07:00"))


def test_m6b_06_input_plan_not_mutated():
    """M6b-06: plan đầu vào không bị sửa, kết quả là bản mới."""
    _, service = make()
    plan = two_session_plan()
    snapshot = copy.deepcopy(plan)
    out = create_events(service, "primary", plan)
    assert plan == snapshot and out is not plan


def test_m6b_07_event_content_and_privacy(monkeypatch):
    """M6b-07: tiêu đề 'Ôn bài: <môn>', nhắc trước 15 phút, khoá studyAgentKey, không chứa email hay token."""
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "1//bi-mat-xyz")
    fake, service = make()
    plan = two_session_plan()
    plan["sessions"][0]["assignments"] = ["Bài tập tuần 5", "Bài tập tuần 6"]
    create_events(service, "primary", plan)
    body = fake.events[0]
    assert body["summary"] == "Ôn bài: Giải tích 2"
    assert body["reminders"] == {"useDefault": False, "overrides": [{"method": "popup", "minutes": 15}]}
    assert body["extendedProperties"]["private"]["studyAgentKey"] == session_key(plan["sessions"][0])
    assert "Bài tập tuần 5" in body["description"] and "hạn nộp" in body["description"]
    assert body["start"] == {"dateTime": "2026-11-01T19:00:00+07:00", "timeZone": "Asia/Ho_Chi_Minh"}
    blob = repr(body)
    assert "@" not in blob and "bi-mat-xyz" not in blob


def test_m6b_08_foreign_events_untouched():
    """M6b-08: sự kiện không mang khoá không bị sửa hay xóa (service giả không có update, delete, patch)."""
    foreign = ev("2026-11-01T19:00:00+07:00", "2026-11-01T19:45:00+07:00", id="cua-toi", summary="Họp nhóm")
    before = copy.deepcopy(foreign)
    fake, service = make([foreign])
    create_events(service, "primary", two_session_plan())
    assert fake.events[0] == before and len(fake.events) == 3
    assert {m for m, _ in fake.calls} <= {"list", "insert"}


def test_m6b_09_one_failing_session_does_not_break_others():
    """M6b-09: một phiên lỗi API giữ null, phiên khác vẫn được tạo."""
    fake, service = make()
    fake.errors["insert"] = [http_error(400), None]
    out = create_events(service, "primary", two_session_plan())
    assert out["sessions"][0]["calendar_event_id"] is None
    assert out["sessions"][1]["calendar_event_id"] == "ev1"
    validate_plan(out)


def test_m6b_09_persistent_5xx_session_skipped_with_warning(caplog):
    """M6b-09: 5xx kéo dài chỉ bỏ phiên đó và ghi cảnh báo, không ném lỗi."""
    fake, service = make()
    fake.errors["insert"] = [http_error(503)] * 3
    caplog.set_level("WARNING")
    out = create_events(service, "primary", two_session_plan())
    assert out["sessions"][0]["calendar_event_id"] is None and out["sessions"][1]["calendar_event_id"] == "ev1"
    assert "Bỏ qua một phiên" in caplog.text


def test_m6b_10_calendar_id_defaults_to_primary(monkeypatch):
    """M6b-10: không đặt GOOGLE_CALENDAR_ID thì dùng lịch chính primary; có đặt thì dùng giá trị đó."""
    monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)
    assert calendar_id() == "primary"
    monkeypatch.setenv("GOOGLE_CALENDAR_ID", "abc@example.test")
    assert calendar_id() == "abc@example.test"


@pytest.mark.parametrize("status", [403, 404])
def test_m6b_10_access_errors_vietnamese_no_secrets(status, monkeypatch):
    """M6b-10: 403 và 404 cho lỗi tiếng Việt về quyền truy cập lịch, không thử lại, không lộ khoá hay email."""
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "1//bi-mat-xyz")
    fake, service = make()
    fake.errors["list"] = [http_error(status, b'{"message": "chi tiet nhay cam"}')]
    with pytest.raises(CalendarAccessError) as exc:
        list_busy(service, "ai-do@example.test", START, END)
    msg = str(exc.value)
    assert "lịch" in msg and "calendar.events" in msg
    assert fake.count("list") == 1
    assert "bi-mat-xyz" not in msg and "ai-do@example.test" not in msg and "nhay cam" not in msg


def test_m6b_10_access_error_aborts_create_events():
    """M6b-10: lỗi quyền khi tạo sự kiện ném lỗi ngay (không nuốt như lỗi của riêng một phiên)."""
    fake, service = make()
    fake.errors["insert"] = [http_error(403)]
    with pytest.raises(CalendarAccessError):
        create_events(service, "primary", two_session_plan())


def test_m6b_10_429_retries_at_most_three_times(no_sleep):
    """M6b-10: 429 thử lại tối đa 3 lượt rồi báo lỗi, chờ tăng dần."""
    fake, service = make()
    fake.errors["list"] = [http_error(429)] * 10
    with pytest.raises(CalendarError) as exc:
        list_busy(service, "primary", START, END)
    assert fake.count("list") == 3 and no_sleep == [2, 4] and "429" in str(exc.value)


def test_m6b_10_429_then_success(no_sleep):
    """M6b-10: 429 một lần rồi thành công vẫn trả kết quả."""
    fake, service = make([ev("2026-11-01T09:00:00+07:00", "2026-11-01T10:00:00+07:00")])
    fake.errors["list"] = [http_error(429)]
    assert len(list_busy(service, "primary", START, END)) == 1


def test_m6b_10_revoked_token_message():
    """M6b-10: lỗi làm mới token cho thông điệp tiếng Việt chỉ cách lấy lại token."""
    fake, service = make()
    fake.errors["list"] = [RefreshError("invalid_grant: bad")]
    with pytest.raises(CalendarAccessError) as exc:
        list_busy(service, "primary", START, END)
    assert "refresh token" in str(exc.value).lower() and "invalid_grant" not in str(exc.value)


def test_m6b_make_service_offline(monkeypatch):
    """M6b-10: tạo dịch vụ Calendar không mở kết nối mạng; thiếu biến thì lỗi nêu tên biến."""
    import socket
    from src.google_auth import GoogleAuthError
    for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(GoogleAuthError):
        gcal.make_service()
    for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"):
        monkeypatch.setenv(name, "x")

    def no_network(*a, **k):
        raise AssertionError("không được gọi mạng")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    assert gcal.make_service() is not None
