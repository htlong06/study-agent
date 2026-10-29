"""Dữ liệu mẫu hợp lệ theo docs/contracts.md. Mọi test nên dùng lại các hàm này thay vì tự bịa.

Mỗi hàm trả về bản sao mới, được phép sửa để tạo trường hợp lỗi.
"""
import copy

SOURCE_FILE = "101-giai-tich-2/555-chuong-3.pdf"
SOURCE_TEXT = (
    "Tích phân bội hai lớp của hàm liên tục trên miền đóng, bị chặn luôn tồn tại. "
    "Trong tọa độ cực, phần tử diện tích dA bằng r dr dθ. "
    "Công thức đổi biến giúp đưa tích phân về dạng đơn giản hơn."
)

_PORTAL = {
    "generated_at": "2026-10-29T00:00:00+00:00",
    "courses": [{"id": 101, "name": "Giải tích 2", "code": "MAT1100"}],
    "assignments": [
        {
            "course_id": 101,
            "course": "Giải tích 2",
            "name": "Bài tập tuần 5",
            "due_at": "2026-11-02T16:59:00Z",
            "url": "https://portal.example.test/courses/101/assignments/7",
        },
        {
            "course_id": 101,
            "course": "Giải tích 2",
            "name": "Bài tập tuần 6",
            "due_at": "2026-11-09T16:59:00Z",
            "url": "https://portal.example.test/courses/101/assignments/8",
        },
    ],
    "errors": [],
}

_QUIZ = {
    "course_id": 101,
    "course": "Giải tích 2",
    "topic": "Tích phân bội",
    "generated_at": "2026-10-29T00:05:00+00:00",
    "model": "gemini-2.5-flash",
    "pass_ratio": 0.7,
    "questions": [
        {
            "id": "q1",
            "question": "Trong tọa độ cực, phần tử diện tích dA bằng gì?",
            "options": ["dr dθ", "r dθ", "r dr dθ", "r² dr dθ"],
            "answer_index": 2,
            "explanation": "Hệ số Jacobi của phép đổi biến sang tọa độ cực là r.",
            "source": {"file": SOURCE_FILE, "quote": "phần tử diện tích dA bằng r dr dθ"},
        },
        {
            "id": "q2",
            "question": "Tích phân bội hai lớp của hàm liên tục trên miền đóng, bị chặn thì sao?",
            "options": ["Luôn tồn tại", "Không tồn tại", "Chỉ tồn tại khi hàm dương", "Chưa xác định"],
            "answer_index": 0,
            "explanation": "Đây là kết quả cơ bản về khả tích.",
            "source": {"file": SOURCE_FILE, "quote": "luôn tồn tại"},
        },
    ],
}

_SESSION = {
    "course_id": 101,
    "course": "Giải tích 2",
    "start": "2026-11-01T19:00:00+07:00",
    "end": "2026-11-01T19:45:00+07:00",
    "reason": "deadline",
    "calendar_event_id": None,
}

_PLAN = {
    "generated_at": "2026-10-29T00:10:00+00:00",
    "timezone": "Asia/Ho_Chi_Minh",
    "sessions": [_SESSION],
}

_TODAY = {
    "date": "2026-11-01",
    "timezone": "Asia/Ho_Chi_Minh",
    "pass_ratio": 0.7,
    "sessions": [_SESSION],
    "quizzes": ["quiz-101.json"],
}


def portal():
    return copy.deepcopy(_PORTAL)


def quiz():
    return copy.deepcopy(_QUIZ)


def session(**changes):
    s = copy.deepcopy(_SESSION)
    s.update(changes)
    return s


def plan():
    return copy.deepcopy(_PLAN)


def today():
    return copy.deepcopy(_TODAY)


def sources():
    return {SOURCE_FILE: SOURCE_TEXT}
