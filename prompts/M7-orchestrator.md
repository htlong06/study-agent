# M7 · Orchestrator và GitHub Actions

Bạn là kỹ sư Python. Hãy đọc `CONVENTIONS.md`, toàn bộ `docs/contracts.md`, và API công khai của M1, M3, M4, M5, M6a, M6b. Chỉ sửa `src/orchestrator.py`, `tests/test_orchestrator.py`, `.github/workflows/daily.yml`. Bạn **ghép** các module có sẵn, không viết lại logic của chúng.

## Mục tiêu

Một lệnh `python -m src.orchestrator` chạy cả chuỗi mỗi sáng, và một workflow GitHub Actions chạy lệnh đó theo lịch. Một bước lỗi không được kéo sập các bước không phụ thuộc vào nó.

## Chuỗi bước

1. **portal:** `CanvasClient` rồi `portal_snapshot` rồi ghi `out/portal.json` (qua `validate_portal`).
2. **materials:** với mỗi môn có deadline sắp tới, `download_materials` rồi `load_documents` rồi `write_documents`.
3. **study:** chọn tối đa `MAX_QUIZZES` môn có deadline gần nhất và có tài liệu, gọi `generate_quiz`, ghi `out/quiz-<course_id>.json`.
4. **plan:** `gcal.list_busy` rồi `scheduler.plan_sessions` rồi `gcal.create_events` rồi ghi `out/plan.json`.
5. **publish:** dựng `out/today.json` (chỉ các phiên trong ngày hiện tại theo `Asia/Ho_Chi_Minh`, `quizzes` là tên file), rồi `store.put_json` cho `today.json` và từng `quiz-*.json`.
6. **report:** ghi `out/run-report.json` dạng `{"started_at", "finished_at", "steps": [{"name", "status": "ok|skipped|failed", "detail"}]}` và in tóm tắt tiếng Việt ra log. Report là file nội bộ, không thuộc hợp đồng C1 đến C6, và **không chứa token, khoá, email**.

## Quy tắc chịu lỗi

- `portal` lỗi thì các bước sau không có dữ liệu: đánh dấu `skipped`, thoát mã 1.
- `materials` hoặc `study` lỗi một môn: bỏ môn đó, ghi `detail`, vẫn chạy `plan` và `publish`.
- `plan` lỗi (ví dụ Calendar): vẫn `publish` quiz; `today.json` có `sessions: []`.
- Thoát mã 0 nếu `portal` ổn (kể cả khi bước khác lỗi một phần); mã 1 nếu `portal` lỗi hoặc `publish` lỗi.

## Tham số dòng lệnh

`--dry-run` (không ghi lên Drive, không tạo sự kiện Calendar; vẫn ghi file trong `out/`), `--only portal,materials,study,plan,publish`, `--now ISO8601` (cố định thời gian để test).

## GitHub Actions (`daily.yml`)

- Kích hoạt: `schedule` cron `0 0 * * *` (07:00 giờ Việt Nam) và `workflow_dispatch`.
- `runs-on: ubuntu-latest`, `timeout-minutes: 10`, `permissions: contents: read`, `concurrency` để không chạy chồng.
- Python 3.11, cache pip, `pip install -r requirements.txt`, chạy `python -m pytest -q` **trước** rồi mới chạy orchestrator.
- Biến lấy từ Secrets: `CANVAS_BASE_URL`, `CANVAS_TOKEN`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `DRIVE_FOLDER_ID`, `GOOGLE_CALENDAR_ID`. Không `echo` secrets, không bật chế độ debug in biến môi trường.
- Không tải `out/` hay `data/` lên artifact và không commit chúng.

## Tiêu chí hoàn thành

- Test dùng các module phụ thuộc giả (mock), không cần mạng.
- Đã làm xong các kịch bản `M7-01` đến `M7-12` trong `docs/test-plan.md`.
- File workflow hợp lệ YAML và không chứa giá trị bí mật.

## Ngoài phạm vi

Guard trên Android (M9), tự sửa hợp đồng dữ liệu.

Cuối phiên, dán báo cáo bàn giao theo mục 8 của `CONVENTIONS.md`.
