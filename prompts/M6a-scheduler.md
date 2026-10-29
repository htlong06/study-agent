# M6a · Bộ xếp lịch ôn (hàm thuần)

Bạn là kỹ sư Python. Hãy đọc `CONVENTIONS.md` và `docs/contracts.md` (C1, C5). Chỉ sửa `src/scheduler.py` và `tests/test_scheduler.py`. Module này **không I/O, không gọi mạng, không gọi LLM**.

## Mục tiêu

Từ danh sách deadline (C1) và các khoảng đã bận, tạo ra các phiên ôn bài (C5) vào giờ trống. Cùng đầu vào phải cho cùng đầu ra.

## Hàm công khai cần có

```python
def free_slots(day: date, busy: list[tuple[datetime, datetime]], tz: ZoneInfo,
               window=(time(18, 0), time(22, 0)), buffer_min: int = 10) -> list[tuple[datetime, datetime]]:
    """Các khoảng trống trong khung học của ngày `day`, đã trừ giờ bận và đệm hai đầu."""

def plan_sessions(portal: dict, busy: list[tuple[datetime, datetime]], now: datetime,
                  tz_name: str = "Asia/Ho_Chi_Minh", session_min: int = 45,
                  max_per_day: int = 2, days_before: int = 1,
                  window=(time(18, 0), time(22, 0))) -> tuple[dict, list[dict]]:
    """Trả (plan theo C5, danh sách deadline không xếp được kèm lý do)."""
```

## Quy tắc xếp lịch

1. Mỗi **môn** có deadline trong cửa sổ được xếp tối đa **1 phiên cho mỗi deadline gần nhất**; nhiều bài tập cùng môn đến hạn cùng ngày thì gộp thành một phiên. `reason` = `"deadline"`.
2. Ngày ưu tiên là `days_before` ngày trước ngày đến hạn (theo múi giờ địa phương). Nếu ngày đó đã qua hoặc không còn chỗ trống, thử lùi dần về hôm nay, **không bao giờ xếp sau hạn nộp** và **không xếp vào quá khứ** (bắt đầu không sớm hơn `now`, làm tròn lên 5 phút).
3. Phiên dài `session_min` (25 đến 45 phút). Nếu khoảng trống ngắn hơn nhưng không dưới 25 phút thì dùng khoảng đó.
4. Không chồng giờ bận, không chồng phiên khác, giữ đệm 10 phút giữa các phiên. Mỗi ngày tối đa `max_per_day` phiên.
5. Xử lý deadline theo thứ tự `due_at` tăng dần; deadline gần hơn được chọn chỗ trước.
6. Deadline không xếp được thì **không bỏ lặng lẽ**: đưa vào danh sách thứ hai kèm lý do (`"hết chỗ trống trước hạn"`, `"hạn đã qua"`).
7. Ngày chuyển giờ, ranh giới nửa đêm và `due_at` ở múi giờ UTC đều phải đổi sang giờ địa phương trước khi tính "ngày".
8. `calendar_event_id` luôn là `null`; `generated_at` lấy từ `now`.

## Tiêu chí hoàn thành

- Plan trả về qua `contracts.validate_plan`.
- Đã làm xong các kịch bản `M6a-01` đến `M6a-12` trong `docs/test-plan.md`, dùng `now` cố định (không gọi `datetime.now()` trong hàm).

## Ngoài phạm vi

Đọc hay ghi Google Calendar (M6b), phiên loại `class` (chưa có nguồn thời khóa biểu).

Cuối phiên, dán báo cáo bàn giao theo mục 8 của `CONVENTIONS.md`.
