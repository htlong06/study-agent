"""M6a: xếp các phiên ôn bài vào giờ trống. Hàm thuần: không I/O, không mạng, không LLM.

Cùng đầu vào (kể cả `now`) luôn cho cùng đầu ra.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MIN_SESSION_MIN = 25
MAX_SESSION_MIN = 45
ROUND_MIN = 5
REASON_PAST = "hạn đã qua"
REASON_FULL = "hết chỗ trống trước hạn"
REASON_NO_DUE = "bài tập không có hạn nộp"


def _merge(spans):
    """Gộp các khoảng chồng hoặc liền nhau, sắp tăng dần."""
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def free_slots(day: date, busy: list[tuple[datetime, datetime]], tz: ZoneInfo,
               window=(time(18, 0), time(22, 0)), buffer_min: int = 10) -> list[tuple[datetime, datetime]]:
    """Các khoảng trống trong khung học của ngày `day`, đã trừ giờ bận và đệm hai đầu."""
    start = datetime.combine(day, window[0], tzinfo=tz)
    end = datetime.combine(day, window[1], tzinfo=tz)
    if end <= start:
        return []
    pad = timedelta(minutes=buffer_min)
    blocked = _merge([(b0 - pad, b1 + pad) for b0, b1 in busy if b1 > b0])
    slots = []
    cursor = start
    for b0, b1 in blocked:
        if b1 <= cursor:
            continue
        if b0 >= end:
            break
        if b0 > cursor:
            slots.append((cursor, b0))
        cursor = max(cursor, b1)
    if cursor < end:
        slots.append((cursor, end))
    return [(s.astimezone(tz), e.astimezone(tz)) for s, e in slots if e > s]


def _round_up(moment: datetime, minutes: int = ROUND_MIN) -> datetime:
    """Làm tròn lên bội số của `minutes` phút (bỏ giây)."""
    base = moment.replace(second=0, microsecond=0)
    extra = (-base.minute) % minutes
    if moment > base and extra == 0:
        extra = minutes
    return base + timedelta(minutes=extra)


def _group_deadlines(assignments, tz):
    """Gộp bài tập cùng môn và cùng ngày hạn (giờ địa phương) thành một deadline."""
    groups = {}
    no_due = {}
    for a in assignments:
        if not a.get("due_at"):
            no_due.setdefault(a["course_id"], {"course": a["course"], "names": []})["names"].append(a["name"])
            continue
        due = datetime.fromisoformat(a["due_at"].replace("Z", "+00:00")).astimezone(tz)
        key = (a["course_id"], due.date())
        g = groups.setdefault(key, {"course_id": a["course_id"], "course": a["course"], "due": due, "names": []})
        g["due"] = min(g["due"], due)  # mốc sớm nhất trong ngày là hạn thực sự
        g["names"].append(a["name"])
    deadlines = sorted(groups.values(), key=lambda g: (g["due"], g["course_id"]))
    return deadlines, no_due


def _candidate_days(preferred: date, today: date, due_day: date) -> list[date]:
    """Ngày ưu tiên, lùi dần về hôm nay, cuối cùng mới đến các ngày sát hạn hơn."""
    first = max(preferred, today)
    earlier = [first - timedelta(days=i) for i in range((first - today).days + 1)]
    later = [first + timedelta(days=i) for i in range(1, (due_day - first).days + 1)]
    return earlier + later


def _place(day, busy, placed, due, now_floor, tz, window, session_min, max_per_day, buffer_min):
    """Tìm phiên sớm nhất trong ngày `day`; trả (start, end) hoặc None."""
    if sum(1 for s, _ in placed if s.astimezone(tz).date() == day) >= max_per_day:
        return None
    for start, end in free_slots(day, busy + placed, tz, window, buffer_min):
        start = _round_up(max(start, now_floor))
        end = min(end, due)
        length = (end - start) / timedelta(minutes=1)
        if length >= MIN_SESSION_MIN:
            return start, start + timedelta(minutes=min(session_min, int(length)))
    return None


def plan_sessions(portal: dict, busy: list[tuple[datetime, datetime]], now: datetime,
                  tz_name: str = "Asia/Ho_Chi_Minh", session_min: int = 45,
                  max_per_day: int = 2, days_before: int = 1,
                  window=(time(18, 0), time(22, 0)), buffer_min: int = 10) -> tuple[dict, list[dict]]:
    """Trả (plan theo C5, danh sách deadline không xếp được kèm lý do)."""
    if not MIN_SESSION_MIN <= session_min <= MAX_SESSION_MIN:
        raise ValueError(f"session_min phải từ {MIN_SESSION_MIN} đến {MAX_SESSION_MIN} phút")
    if now.tzinfo is None:
        raise ValueError("now phải có múi giờ")
    tz = ZoneInfo(tz_name)
    local_now = now.astimezone(tz)
    today = local_now.date()
    now_floor = _round_up(local_now)

    deadlines, no_due = _group_deadlines(portal.get("assignments", []), tz)
    placed: list[tuple[datetime, datetime]] = []
    sessions: list[dict] = []
    unscheduled: list[dict] = []

    for g in deadlines:
        item = {"course_id": g["course_id"], "course": g["course"],
                "due_at": g["due"].isoformat(), "assignments": g["names"]}
        if g["due"] <= local_now:
            unscheduled.append({**item, "reason": REASON_PAST})
            continue
        preferred = g["due"].date() - timedelta(days=days_before)
        slot = None
        for day in _candidate_days(preferred, today, g["due"].date()):
            slot = _place(day, busy, placed, g["due"], now_floor, tz, window,
                          session_min, max_per_day, buffer_min)
            if slot:
                break
        if not slot:
            unscheduled.append({**item, "reason": REASON_FULL})
            continue
        placed.append(slot)
        sessions.append({
            "course_id": g["course_id"], "course": g["course"],
            "start": slot[0].isoformat(), "end": slot[1].isoformat(),
            "reason": "deadline", "calendar_event_id": None,
        })

    for course_id, info in sorted(no_due.items()):
        unscheduled.append({"course_id": course_id, "course": info["course"], "due_at": None,
                            "assignments": info["names"], "reason": REASON_NO_DUE})

    sessions.sort(key=lambda s: (s["start"], s["course_id"]))
    plan = {"generated_at": local_now.isoformat(), "timezone": tz_name, "sessions": sessions}
    return plan, unscheduled
