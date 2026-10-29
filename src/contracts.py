"""Kiểm tra dữ liệu theo hợp đồng trong docs/contracts.md.

Mọi module dùng chung các hàm này trong test để đầu ra luôn khớp schema.
Quy tắc: thiếu trường bắt buộc thì báo lỗi, trường lạ thì bỏ qua.
"""
from datetime import datetime

REASONS = {"deadline", "class"}


class ContractError(ValueError):
    pass


def _need(obj, key, types, where):
    if not isinstance(obj, dict) or key not in obj:
        raise ContractError(f"{where}: thiếu trường '{key}'")
    if not isinstance(obj[key], types) or isinstance(obj[key], bool) and bool not in _as_tuple(types):
        raise ContractError(f"{where}.{key}: sai kiểu dữ liệu")
    return obj[key]


def _as_tuple(types):
    return types if isinstance(types, tuple) else (types,)


def parse_time(value, where="thời gian"):
    """Đọc ISO 8601 có múi giờ (chấp nhận hậu tố Z); báo lỗi nếu thiếu múi giờ."""
    if not isinstance(value, str):
        raise ContractError(f"{where}: phải là chuỗi ISO 8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ContractError(f"{where}: không đọc được '{value}'")
    if parsed.tzinfo is None:
        raise ContractError(f"{where}: thiếu múi giờ trong '{value}'")
    return parsed


def validate_portal(data):
    parse_time(_need(data, "generated_at", str, "portal"), "portal.generated_at")
    for i, c in enumerate(_need(data, "courses", list, "portal")):
        _need(c, "id", int, f"portal.courses[{i}]")
        _need(c, "name", str, f"portal.courses[{i}]")
        _need(c, "code", str, f"portal.courses[{i}]")
    previous = None
    for i, a in enumerate(_need(data, "assignments", list, "portal")):
        where = f"portal.assignments[{i}]"
        _need(a, "course_id", int, where)
        _need(a, "course", str, where)
        _need(a, "name", str, where)
        _need(a, "url", str, where)
        due = parse_time(_need(a, "due_at", str, where), f"{where}.due_at")
        if previous and due < previous:
            raise ContractError("portal.assignments: phải sắp theo due_at tăng dần")
        previous = due
    for i, e in enumerate(_need(data, "errors", list, "portal")):
        if not isinstance(e, str):
            raise ContractError(f"portal.errors[{i}]: phải là chuỗi")
    return data


def validate_document(doc, min_chars=800, max_chars=3000):
    _need(doc, "course_id", int, "document")
    _need(doc, "file", str, "document")
    _need(doc, "title", str, "document")
    chunks = _need(doc, "chunks", list, "document")
    _need(doc, "warnings", list, "document")
    for i, chunk in enumerate(chunks):
        if not isinstance(chunk, str) or not chunk.strip():
            raise ContractError(f"document.chunks[{i}]: rỗng hoặc sai kiểu")
        if len(chunk) > max_chars:
            raise ContractError(f"document.chunks[{i}]: dài hơn {max_chars} ký tự")
        if len(chunk) < min_chars and i != len(chunks) - 1:
            raise ContractError(f"document.chunks[{i}]: ngắn hơn {min_chars} ký tự (chỉ đoạn cuối được ngắn)")
    return doc


def _norm(text):
    return " ".join(text.split()).lower()


def validate_quiz(quiz, sources=None):
    """`sources`: dict {tên file: toàn văn}. Nếu có, kiểm tra trích dẫn xuất hiện nguyên văn."""
    _need(quiz, "course_id", int, "quiz")
    for key in ("course", "topic", "model"):
        _need(quiz, key, str, "quiz")
    parse_time(_need(quiz, "generated_at", str, "quiz"), "quiz.generated_at")
    ratio = _need(quiz, "pass_ratio", (int, float), "quiz")
    if not 0 < ratio <= 1:
        raise ContractError("quiz.pass_ratio: phải trong (0, 1]")
    seen = set()
    questions = _need(quiz, "questions", list, "quiz")
    if not questions:
        raise ContractError("quiz.questions: không được rỗng")
    for i, q in enumerate(questions):
        where = f"quiz.questions[{i}]"
        qid = _need(q, "id", str, where)
        if qid in seen:
            raise ContractError(f"{where}: id '{qid}' bị trùng")
        seen.add(qid)
        _need(q, "question", str, where)
        _need(q, "explanation", str, where)
        options = _need(q, "options", list, where)
        if len(options) != 4 or not all(isinstance(o, str) and o.strip() for o in options):
            raise ContractError(f"{where}.options: phải đúng 4 chuỗi không rỗng")
        idx = _need(q, "answer_index", int, where)
        if not 0 <= idx <= 3:
            raise ContractError(f"{where}.answer_index: phải từ 0 đến 3")
        src = _need(q, "source", dict, where)
        file, quote = _need(src, "file", str, where + ".source"), _need(src, "quote", str, where + ".source")
        if sources is not None:
            if file not in sources:
                raise ContractError(f"{where}.source.file: '{file}' không có trong tài liệu nguồn")
            if _norm(quote) not in _norm(sources[file]):
                raise ContractError(f"{where}.source.quote: không xuất hiện nguyên văn trong tài liệu")
    return quiz


def validate_session(s, where="session"):
    _need(s, "course_id", int, where)
    _need(s, "course", str, where)
    start = parse_time(_need(s, "start", str, where), f"{where}.start")
    end = parse_time(_need(s, "end", str, where), f"{where}.end")
    minutes = (end - start).total_seconds() / 60
    if not 25 <= minutes <= 45:
        raise ContractError(f"{where}: phiên phải dài 25 đến 45 phút (hiện {minutes:g})")
    if _need(s, "reason", str, where) not in REASONS:
        raise ContractError(f"{where}.reason: phải là 'deadline' hoặc 'class'")
    if "calendar_event_id" not in s:
        raise ContractError(f"{where}: thiếu trường 'calendar_event_id' (null nếu chưa tạo)")
    if s["calendar_event_id"] is not None and not isinstance(s["calendar_event_id"], str):
        raise ContractError(f"{where}.calendar_event_id: phải là chuỗi hoặc null")
    return start, end


def validate_plan(plan):
    parse_time(_need(plan, "generated_at", str, "plan"), "plan.generated_at")
    _need(plan, "timezone", str, "plan")
    spans = []
    for i, s in enumerate(_need(plan, "sessions", list, "plan")):
        spans.append(validate_session(s, f"plan.sessions[{i}]"))
    spans.sort()
    for (_, prev_end), (next_start, _) in zip(spans, spans[1:]):
        if next_start < prev_end:
            raise ContractError("plan.sessions: có hai phiên chồng nhau")
    return plan


def validate_today(today):
    date = _need(today, "date", str, "today")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ContractError("today.date: phải có dạng YYYY-MM-DD")
    _need(today, "timezone", str, "today")
    ratio = _need(today, "pass_ratio", (int, float), "today")
    if not 0 < ratio <= 1:
        raise ContractError("today.pass_ratio: phải trong (0, 1]")
    for i, s in enumerate(_need(today, "sessions", list, "today")):
        start, _ = validate_session(s, f"today.sessions[{i}]")
        if start.strftime("%Y-%m-%d") != date:
            raise ContractError(f"today.sessions[{i}]: không thuộc ngày {date}")
    for i, name in enumerate(_need(today, "quizzes", list, "today")):
        if not isinstance(name, str) or "/" in name:
            raise ContractError(f"today.quizzes[{i}]: phải là tên file, không có đường dẫn")
    return today
