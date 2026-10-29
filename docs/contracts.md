# Hợp đồng dữ liệu giữa các module

Mọi module trao đổi qua 5 loại file dưới đây (ngoài tài liệu bài giảng). Thay đổi hợp đồng cần chủ dự án duyệt; không module nào được tự thêm hay bớt trường.

Quy ước chung: UTF-8, thời gian ISO 8601 có múi giờ, `id` môn học là số nguyên của Canvas, trường tùy chọn ghi rõ `null` thay vì bỏ trống.

## C1. `out/portal.json` (Portal Agent ghi, Planner và Study đọc)

```json
{
  "generated_at": "2026-10-29T00:00:00+00:00",
  "courses": [{"id": 101, "name": "Giải tích 2", "code": "MAT1100"}],
  "assignments": [
    {
      "course_id": 101,
      "course": "Giải tích 2",
      "name": "Bài tập tuần 5",
      "due_at": "2026-11-02T16:59:00Z",
      "url": "https://portal.uet.vnu.edu.vn/courses/101/assignments/7"
    }
  ],
  "errors": []
}
```

Ràng buộc: `assignments` đã lọc theo cửa sổ `LOOKAHEAD_DAYS` và sắp theo `due_at` tăng dần; `errors` là danh sách chuỗi tiếng Việt, không chứa token.

## C2. `data/materials/<course_id>-<slug>/<file_id>-<slug>.<pdf|txt|md>` (tài liệu bài giảng)

Tên thư mục và file do `canvas.download_materials` đặt. Không module nào khác đổi tên hay xóa.

## C3. Document (M3 trả về trong bộ nhớ, đồng thời ghi `out/documents/<course_id>.json`)

```json
{
  "course_id": 101,
  "file": "101-giai-tich-2/555-chuong-3.pdf",
  "title": "chuong 3",
  "chunks": ["Đoạn văn bản thứ nhất ...", "Đoạn văn bản thứ hai ..."],
  "warnings": []
}
```

Ràng buộc: mỗi chunk dài 800 đến 3000 ký tự (đoạn cuối được ngắn hơn); không chunk rỗng; `warnings` ghi khi PDF là ảnh quét không có chữ.

## C4. `out/quiz-<course_id>.json` (Study Agent ghi, Quiz client và Orchestrator đọc)

```json
{
  "course_id": 101,
  "course": "Giải tích 2",
  "topic": "Tích phân bội",
  "generated_at": "2026-10-29T00:05:00+00:00",
  "model": "gemini-2.5-flash",
  "pass_ratio": 0.7,
  "questions": [
    {
      "id": "q1",
      "question": "Công thức đổi biến trong tọa độ cực là gì?",
      "options": ["A ...", "B ...", "C ...", "D ..."],
      "answer_index": 2,
      "explanation": "Vì ...",
      "source": {"file": "101-giai-tich-2/555-chuong-3.pdf", "quote": "đoạn trích nguyên văn từ tài liệu"}
    }
  ]
}
```

Ràng buộc: đúng 4 `options`; `answer_index` từ 0 đến 3; `id` duy nhất trong file (`q1`, `q2`, ...); `source.quote` phải xuất hiện nguyên văn trong tài liệu nguồn (sau khi chuẩn hóa khoảng trắng), nếu không câu hỏi bị loại; `pass_ratio` mặc định 0.7.

## C5. `out/plan.json` (Planner ghi, Orchestrator đọc)

```json
{
  "generated_at": "2026-10-29T00:10:00+00:00",
  "timezone": "Asia/Ho_Chi_Minh",
  "sessions": [
    {
      "course_id": 101,
      "course": "Giải tích 2",
      "start": "2026-11-01T19:00:00+07:00",
      "end": "2026-11-01T19:45:00+07:00",
      "reason": "deadline",
      "calendar_event_id": null
    }
  ]
}
```

Ràng buộc: `reason` là `"deadline"` hoặc `"class"`; mỗi phiên dài 25 đến 45 phút; các phiên không chồng nhau và không chồng sự kiện đã có; `calendar_event_id` là `null` cho đến khi M6b tạo sự kiện.

## C6. `out/today.json` (Orchestrator ghi, đưa lên Google Drive cho điện thoại)

```json
{
  "date": "2026-10-29",
  "timezone": "Asia/Ho_Chi_Minh",
  "pass_ratio": 0.7,
  "sessions": [ { "...": "như một phần tử của plan.sessions" } ],
  "quizzes": ["quiz-101.json"]
}
```

Ràng buộc: `sessions` chỉ gồm phiên trong ngày `date` (theo múi giờ ghi trong file); `quizzes` là tên file, nằm cùng thư mục trên Drive.

## Quy tắc đặt tên và phiên bản

- Mỗi file hợp đồng có thể thêm trường `"schema_version": 1`; nếu có thì module đọc phải bỏ qua phiên bản không hiểu và báo lỗi rõ ràng.
- Module đọc phải **bỏ qua trường lạ** (để thêm trường sau này không làm hỏng), nhưng **báo lỗi khi thiếu trường bắt buộc**.
