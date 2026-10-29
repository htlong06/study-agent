# M6b · Google Calendar adapter

Bạn là kỹ sư Python. Hãy đọc `CONVENTIONS.md`, `docs/contracts.md` (C5) và `src/google_auth.py` (do M5 viết). Chỉ sửa `src/gcal.py` và `tests/test_gcal.py`.

## Mục tiêu

Đọc các khoảng bận từ lịch của người dùng và tạo sự kiện cho các phiên ôn trong plan, **không bao giờ tạo trùng** khi chạy lại.

## Giả định kỹ thuật (đã chốt)

Dùng tài khoản dịch vụ; người dùng đã chia sẻ lịch với quyền "Thực hiện thay đổi đối với sự kiện". ID lịch (thường là email Gmail của người dùng) nằm trong `GOOGLE_CALENDAR_ID`; **thiếu biến này thì ném lỗi rõ ràng**, không dùng `primary` (vì `primary` của tài khoản dịch vụ là lịch riêng của nó). Scope: `https://www.googleapis.com/auth/calendar.events`.

## Hàm công khai cần có

```python
def list_busy(service, calendar_id: str, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Khoảng bận trong [start, end), sắp tăng dần, đã gộp các khoảng chồng nhau."""

def create_events(service, calendar_id: str, plan: dict) -> dict:
    """Tạo sự kiện cho từng phiên chưa có calendar_event_id, trả plan mới đã điền id (không sửa plan đầu vào)."""

def session_key(session: dict) -> str:
    """Khoá ổn định theo course_id và start, dùng để chống tạo trùng."""
```

## Yêu cầu

1. `list_busy` dùng `events().list(singleEvents=True, orderBy="startTime", timeMin, timeMax)` và duyệt hết các trang (`nextPageToken`).
2. Bỏ qua sự kiện: `status == "cancelled"`; `transparency == "transparent"` (hiển thị là rảnh); sự kiện cả ngày (chỉ có `start.date`, không có `start.dateTime`).
3. Gộp các khoảng bận chồng hoặc liền nhau thành một.
4. `create_events` đặt `extendedProperties.private.studyAgentKey = session_key(...)`. Trước khi tạo, tìm sự kiện cùng khoá (`privateExtendedProperty=studyAgentKey=...`); nếu có thì **tái sử dụng id**, không tạo mới.
5. Tiêu đề sự kiện: `Ôn bài: <tên môn>`; mô tả tiếng Việt nêu lý do và danh sách bài tập đến hạn nếu có. Nhắc trước 15 phút (`reminders.overrides`). Không đưa token hay email vào mô tả.
6. Không xóa hay sửa sự kiện nào ngoài những sự kiện có khoá `studyAgentKey`.
7. Lỗi API: thử lại tối đa 3 lần với 429 và 5xx; 403 và 404 thì ném lỗi tiếng Việt "chưa chia sẻ lịch cho tài khoản dịch vụ".
8. Một phiên lỗi không làm hỏng các phiên khác: phiên đó giữ `calendar_event_id = null` và được ghi log cảnh báo.

## Tiêu chí hoàn thành

- Plan trả về qua `contracts.validate_plan`.
- Test dùng `service` giả, không cần mạng.
- Đã làm xong các kịch bản `M6b-01` đến `M6b-10` trong `docs/test-plan.md`.

## Ngoài phạm vi

Lập lịch (M6a), xác thực (M5), xóa phiên cũ khi plan đổi.

Cuối phiên, dán báo cáo bàn giao theo mục 8 của `CONVENTIONS.md`.
