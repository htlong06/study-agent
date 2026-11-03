"""Kiểm thử M6a (scheduler.py). Mã kịch bản M6a-01..M6a-12 nằm trong tên hàm và docstring."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.contracts import validate_plan
from src.scheduler import free_slots, plan_sessions

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
D = date(2026, 11, 1)


def at(h, m=0, day=D):
    return datetime.combine(day, time(h, m), tzinfo=TZ)


def portal(*assignments):
    return {"generated_at": "2026-10-29T00:00:00+00:00", "courses": [], "errors": [],
            "assignments": [
                {"course_id": cid, "course": f"Môn {cid}", "name": name, "due_at": due, "url": "https://x.test"}
                for cid, name, due in assignments]}


def local(session, key):
    return datetime.fromisoformat(session[key])


def minutes(session):
    return (local(session, "end") - local(session, "start")) / timedelta(minutes=1)


NOW = datetime(2026, 10, 29, 3, 0, tzinfo=timezone.utc)  # 10:00 ngày 29/10 giờ Việt Nam


def test_m6a_01_free_slots_around_busy():
    """M6a-01: một giờ bận giữa khung 18:00-22:00 cho hai khoảng trống hai bên."""
    slots = free_slots(D, [(at(19), at(20))], TZ, buffer_min=0)
    assert slots == [(at(18), at(19)), (at(20), at(22))]


def test_m6a_01_no_busy_whole_window():
    """M6a-01: không có giờ bận thì cả khung học là trống."""
    assert free_slots(D, [], TZ) == [(at(18), at(22))]


def test_m6a_02_free_slots_buffer():
    """M6a-02: đệm 10 phút ở hai đầu giờ bận."""
    slots = free_slots(D, [(at(19), at(20))], TZ, buffer_min=10)
    assert slots == [(at(18), at(18, 50)), (at(20, 10), at(22))]


def test_m6a_02_overlapping_busy_merged():
    """M6a-02: các giờ bận chồng nhau được gộp, không sinh khoảng trống giả."""
    busy = [(at(19), at(20)), (at(19, 30), at(20, 30))]
    assert free_slots(D, busy, TZ, buffer_min=0) == [(at(18), at(19)), (at(20, 30), at(22))]


def test_m6a_03_busy_outside_window_ignored():
    """M6a-03: giờ bận hoàn toàn ngoài khung học không ảnh hưởng."""
    busy = [(at(8), at(12)), (at(22, 30), at(23, 30))]
    assert free_slots(D, busy, TZ) == [(at(18), at(22))]


def test_m6a_03_busy_in_utc_is_converted():
    """M6a-03: giờ bận ở múi giờ UTC vẫn được tính đúng theo giờ địa phương."""
    busy = [(at(19).astimezone(timezone.utc), at(20).astimezone(timezone.utc))]
    assert free_slots(D, busy, TZ, buffer_min=0) == [(at(18), at(19)), (at(20), at(22))]


def test_m6a_04_session_day_before_deadline_in_window():
    """M6a-04: deadline sau 3 ngày, phiên rơi vào ngày trước hạn trong khung 18-22."""
    p = portal((101, "BT5", "2026-11-01T16:59:00Z"))  # hạn 23:59 ngày 1/11
    plan, left = plan_sessions(p, [], NOW)
    validate_plan(plan)
    assert left == []
    s = plan["sessions"][0]
    assert local(s, "start").date() == date(2026, 10, 31)
    assert time(18, 0) <= local(s, "start").time() and local(s, "end").time() <= time(22, 0)
    assert s["reason"] == "deadline" and s["calendar_event_id"] is None


def test_m6a_05_never_in_the_past():
    """M6a-05: now 21:50 và ngày ưu tiên là hôm nay thì không xếp vào quá khứ."""
    now = at(21, 50, day=date(2026, 10, 30))
    p = portal((101, "BT", "2026-10-31T16:59:00Z"))  # hạn 23:59 ngày 31/10, ưu tiên 30/10
    plan, left = plan_sessions(p, [], now)
    assert left == []
    s = plan["sessions"][0]
    assert local(s, "start") >= now.astimezone(TZ)
    assert local(s, "start").date() == date(2026, 10, 31)  # 10 phút còn lại < 25 nên dời sang ngày sau


def test_m6a_05_starts_from_now_rounded_up():
    """M6a-05: bắt đầu từ now làm tròn lên 5 phút khi còn đủ thời gian."""
    now = datetime(2026, 10, 30, 18, 2, 30, tzinfo=TZ)
    p = portal((101, "BT", "2026-10-31T16:59:00Z"))
    plan, _ = plan_sessions(p, [], now)
    assert local(plan["sessions"][0], "start") == datetime(2026, 10, 30, 18, 5, tzinfo=TZ)


def test_m6a_06_all_free_slots_after_deadline():
    """M6a-06: hạn nộp 10:00 hôm nay, mọi chỗ trống (18-22) đều sau hạn thì không xếp."""
    now = datetime(2026, 10, 30, 8, 0, tzinfo=TZ)
    p = portal((101, "BT", datetime(2026, 10, 30, 10, 0, tzinfo=TZ).astimezone(timezone.utc).isoformat()))
    plan, left = plan_sessions(p, [], now)
    assert plan["sessions"] == []
    assert len(left) == 1 and left[0]["reason"] == "hết chỗ trống trước hạn"
    assert left[0]["course_id"] == 101 and left[0]["assignments"] == ["BT"]


def test_m6a_07_same_course_same_day_one_session():
    """M6a-07: ba bài tập cùng môn cùng ngày hạn chỉ cho một phiên."""
    p = portal((101, "A", "2026-11-02T10:00:00Z"), (101, "B", "2026-11-02T12:00:00Z"),
               (101, "C", "2026-11-02T16:00:00Z"))
    plan, left = plan_sessions(p, [], NOW)
    assert len(plan["sessions"]) == 1 and left == []


def test_m6a_07_different_days_separate_sessions():
    """M6a-07: cùng môn nhưng khác ngày hạn thì mỗi hạn một phiên."""
    p = portal((101, "A", "2026-11-02T16:59:00Z"), (101, "B", "2026-11-05T16:59:00Z"))
    plan, _ = plan_sessions(p, [], NOW)
    assert len(plan["sessions"]) == 2


def test_m6a_08_max_per_day():
    """M6a-08: bốn môn cùng hạn một ngày, max_per_day=2, không ngày nào quá 2 phiên."""
    p = portal(*[(cid, "BT", "2026-11-04T16:59:00Z") for cid in (1, 2, 3, 4)])
    plan, left = plan_sessions(p, [], NOW, max_per_day=2)
    validate_plan(plan)
    per_day = {}
    for s in plan["sessions"]:
        per_day[local(s, "start").date()] = per_day.get(local(s, "start").date(), 0) + 1
    assert max(per_day.values()) <= 2
    assert len(plan["sessions"]) + len(left) == 4


def test_m6a_09_no_overlap_and_buffer():
    """M6a-09: không phiên nào chồng nhau hay chồng giờ bận, có đệm 10 phút."""
    day = date(2026, 10, 31)
    busy = [(at(18, 30, day), at(19, 30, day))]
    p = portal(*[(cid, "BT", "2026-11-01T16:59:00Z") for cid in (1, 2, 3)])
    plan, _ = plan_sessions(p, busy, NOW, max_per_day=3)
    validate_plan(plan)
    spans = sorted((local(s, "start"), local(s, "end")) for s in plan["sessions"])
    for (s0, e0), (s1, e1) in zip(spans, spans[1:]):
        assert s1 - e0 >= timedelta(minutes=10)
    for s, e in spans:
        for b0, b1 in busy:
            assert e + timedelta(minutes=10) <= b0 or s >= b1 + timedelta(minutes=10)


def test_m6a_10_reasons_for_unplaceable():
    """M6a-10: hết chỗ trống và hạn đã qua cho đúng hai lý do."""
    day = date(2026, 10, 30)
    busy = [(at(0, 0, day), at(23, 59, day))]  # hôm nay bận kín, hạn là tối nay
    now = at(9, 0, day)
    p = portal((1, "Hết chỗ", "2026-10-30T16:59:00Z"), (2, "Đã qua", "2026-10-29T01:00:00Z"))
    plan, left = plan_sessions(p, busy, now)
    assert plan["sessions"] == []
    assert {x["course_id"]: x["reason"] for x in left} == {1: "hết chỗ trống trước hạn", 2: "hạn đã qua"}


def test_m6a_11_due_day_uses_local_time():
    """M6a-11: 16:59Z là 23:59 ngày 1/11, 17:01Z là 00:01 ngày 2/11 giờ Việt Nam."""
    p1 = portal((101, "A", "2026-11-01T16:59:00Z"))
    p2 = portal((101, "A", "2026-11-01T17:01:00Z"))
    s1 = plan_sessions(p1, [], NOW)[0]["sessions"][0]
    s2 = plan_sessions(p2, [], NOW)[0]["sessions"][0]
    assert local(s1, "start").date() == date(2026, 10, 31)  # trước hạn một ngày của 1/11
    assert local(s2, "start").date() == date(2026, 11, 1)   # hạn là 2/11 nên ưu tiên 1/11


def test_m6a_11_same_local_day_grouped():
    """M6a-11: hai hạn 16:59Z và 17:01Z khác ngày địa phương nên không gộp."""
    p = portal((101, "A", "2026-11-01T16:59:00Z"), (101, "B", "2026-11-01T17:01:00Z"))
    plan, _ = plan_sessions(p, [], NOW)
    assert len(plan["sessions"]) == 2


def test_m6a_12_deterministic_valid_and_length():
    """M6a-12: chạy hai lần giống hệt, qua validate_plan, mỗi phiên 25-45 phút."""
    p = portal((1, "A", "2026-11-02T16:59:00Z"), (2, "B", "2026-11-03T16:59:00Z"),
               (3, "C", "2026-11-03T10:00:00Z"))
    busy = [(at(18, 40, date(2026, 11, 1)), at(21, 50, date(2026, 11, 1)))]
    first = plan_sessions(p, busy, NOW)
    second = plan_sessions(p, busy, NOW)
    assert first == second
    validate_plan(first[0])
    assert first[0]["generated_at"] == NOW.astimezone(TZ).isoformat()
    for s in first[0]["sessions"]:
        assert 25 <= minutes(s) <= 45


def test_m6a_12_short_gap_uses_gap_not_below_25():
    """M6a-12: khoảng trống 30 phút thì phiên 30 phút; dưới 25 phút thì bỏ qua."""
    day = date(2026, 10, 31)
    busy = [(at(18, 0, day), at(20, 0, day)), (at(20, 50, day), at(23, 0, day))]  # trống 20:10-20:40 = 30 phút
    p = portal((101, "A", "2026-11-01T16:59:00Z"))
    plan, _ = plan_sessions(p, busy, NOW)
    s = plan["sessions"][0]
    assert local(s, "start") == at(20, 10, day) and minutes(s) == 30


def test_m6a_never_after_deadline_even_with_free_late_slots():
    """M6a-06: phiên không bao giờ kết thúc sau hạn nộp."""
    now = datetime(2026, 10, 30, 8, 0, tzinfo=TZ)
    due = datetime(2026, 10, 30, 18, 20, tzinfo=TZ)
    plan, left = plan_sessions(portal((1, "A", due.isoformat())), [], now, days_before=0)
    assert plan["sessions"] == [] and left[0]["reason"] == "hết chỗ trống trước hạn"
    due = datetime(2026, 10, 30, 19, 0, tzinfo=TZ)
    plan, _ = plan_sessions(portal((1, "A", due.isoformat())), [], now, days_before=0)
    assert local(plan["sessions"][0], "end") <= due


def test_m6a_invalid_arguments():
    """M6a-12: tham số sai thì báo lỗi rõ ràng."""
    with pytest.raises(ValueError):
        plan_sessions(portal(), [], NOW, session_min=10)
    with pytest.raises(ValueError):
        plan_sessions(portal(), [], datetime(2026, 10, 29, 3, 0))
