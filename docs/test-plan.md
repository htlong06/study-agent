# Kế hoạch kiểm thử

Mỗi kịch bản có mã `<module>-<số>`. Mỗi mã phải có ít nhất một test (tên hàm hoặc docstring chứa mã), chạy được bằng `python -m pytest` mà không cần mạng hay khoá (xem `CONVENTIONS.md` mục 5). Mô-đun M8 dùng `node --test web/` thay cho pytest.

Cách đặt tên test: `test_m3_04_pdf_co_chu` (mã viết thường, gạch dưới) hoặc docstring bắt đầu bằng `M3-04`.

## M0 · Cấu hình và hợp đồng (`tests/test_config.py`, `tests/test_contracts.py`)

| Mã | Kịch bản | Kết quả mong đợi |
| --- | --- | --- |
| M0-01 | `load_env` đọc file `.env` | Biến trong file xuất hiện trong môi trường |
| M0-02 | Biến đã có sẵn trong môi trường | Giá trị có sẵn được giữ, không bị file ghi đè |
| M0-03 | File có dòng trống, dòng chú thích, dòng không có `=` | Bỏ qua, không lỗi |
| M0-04 | Giá trị có dấu nháy đơn hoặc kép | Dấu nháy được gỡ |
| M0-05 | `env` với biến rỗng hoặc không có | Trả về giá trị mặc định |
| M0-06 | `env_int` với chuỗi không phải số | Trả về mặc định, không ném lỗi |
| M0-07 | `validate_portal` với dữ liệu đúng | Trả lại dữ liệu, không lỗi |
| M0-08 | `validate_portal` thiếu trường, sai thứ tự `due_at`, thời gian thiếu múi giờ | Ném `ContractError` nêu đúng trường |
| M0-09 | `validate_quiz` với 3 lựa chọn, `answer_index` = 4, id trùng | Ném `ContractError` |
| M0-10 | `validate_quiz` với `sources`, trích dẫn không có trong tài liệu | Ném `ContractError`; khác khoảng trắng và hoa thường thì chấp nhận |
| M0-11 | `validate_plan` có hai phiên chồng nhau, phiên 60 phút | Ném `ContractError` |
| M0-12 | `validate_today` có phiên ngoài ngày, `quizzes` chứa đường dẫn | Ném `ContractError` |

## M1 · Portal Agent / Canvas client (`tests/test_canvas.py`)

| Mã | Kịch bản | Kết quả mong đợi |
| --- | --- | --- |
| M1-01 | `next_link` với header có `rel="next"` | Trả đúng URL trang kế |
| M1-02 | `next_link` với header rỗng hoặc không có `next` | Trả `None` |
| M1-03 | `get_all` gặp 3 trang kết quả | Gộp đủ phần tử, đi theo header `Link` |
| M1-04 | Canvas trả 401 | Ném `PermissionError`, thông điệp không chứa token |
| M1-05 | `courses` gặp mục thiếu `id` hoặc `name` | Mục đó bị bỏ |
| M1-06 | `portal_snapshot` với hạn trong và ngoài cửa sổ ngày | Chỉ giữ hạn trong cửa sổ, sắp tăng dần |
| M1-07 | Bài tập không có `due_at` | Bị bỏ, không lỗi |
| M1-08 | Một môn ném lỗi mạng | Ghi vào `errors`, các môn khác vẫn xử lý |
| M1-09 | Kết quả `portal_snapshot` | Qua `validate_portal` |
| M1-10 | `download_materials` với file pdf, docx, png và file quá lớn | Chỉ tải pdf, txt, md nhỏ hơn giới hạn |
| M1-11 | Tải lại khi file đã có đúng kích thước | Không tải lại |
| M1-12 | `slugify` với tiếng Việt, ký hiệu và chuỗi rỗng | Kết quả chỉ gồm chữ, số, gạch nối; chuỗi rỗng trả `mon-hoc` |

## M2 · Cổng LLM (`tests/test_llm.py`)

| Mã | Kịch bản | Kết quả mong đợi |
| --- | --- | --- |
| M2-01 | `parse_json` với JSON thuần | Trả đúng đối tượng |
| M2-02 | `parse_json` với JSON bọc trong ```json | Trả đúng đối tượng |
| M2-03 | `parse_json` có chữ thừa trước và sau JSON | Trả đúng đối tượng |
| M2-04 | `parse_json` không có JSON | Ném `ValueError` |
| M2-05 | `call_llm` khi nhà cung cấp đầu chạy tốt | Dùng nhà cung cấp đầu, không gọi các nhà khác |
| M2-06 | Nhà cung cấp đầu ném `LLMError` | Chuyển sang nhà kế tiếp |
| M2-07 | Nhà cung cấp thiếu khoá | Bị bỏ qua, không gọi mạng |
| M2-08 | Tất cả đều lỗi | Ném `LLMError` liệt kê lý do, không chứa khoá |
| M2-09 | `_post` gặp 429 rồi 200 | Thử lại và thành công (thay `time.sleep` để test nhanh) |
| M2-10 | `_post` gặp 400 | Ném `LLMError` ngay, không thử lại |
| M2-11 | OpenRouter thiếu `OPENROUTER_MODEL` | Ném `LLMError` có hướng dẫn |
| M2-12 | Gemini trả phản hồi không có `candidates` | Ném `LLMError` |

## M3 · Tài liệu (`tests/test_materials.py`)

| Mã | Kịch bản | Kết quả mong đợi |
| --- | --- | --- |
| M3-01 | Đọc `.txt` UTF-8 có tiếng Việt | Văn bản đúng dấu |
| M3-02 | Đọc `.md` | Văn bản đọc được, không lỗi |
| M3-03 | File mã hóa `cp1258` | Đọc được, có cảnh báo mã hóa |
| M3-04 | PDF có chữ (tạo trong test) | Trích đúng nội dung các trang |
| M3-05 | PDF không có chữ (ảnh quét) | Văn bản rỗng và cảnh báo "cần OCR" |
| M3-06 | Chuẩn hóa: nhiều dòng trống, từ bị gạch nối cuối dòng, ký tự điều khiển, Unicode NFD | Dòng trống gộp một, từ nối lại, ký tự điều khiển bỏ, đổi về NFC |
| M3-07 | `chunk_text` với văn bản dài | Mỗi chunk 800 đến 3000 ký tự, chỉ chunk cuối được ngắn hơn |
| M3-08 | Đoạn đơn dài hơn 3000 ký tự | Cắt ở cuối câu, không cắt giữa từ |
| M3-09 | Thư mục có một file hỏng | File hỏng có cảnh báo hoặc `chunks` rỗng, các file khác vẫn xử lý |
| M3-10 | Chạy hai lần, nhiều file | Kết quả giống hệt, sắp theo tên, qua `validate_document` |

## M4 · Study Agent (`tests/test_study.py`)

| Mã | Kịch bản | Kết quả mong đợi |
| --- | --- | --- |
| M4-01 | `build_prompt` | Có nhãn file của từng chunk, yêu cầu 4 lựa chọn, chỉ trả JSON, xin `n + 2` câu |
| M4-02 | `build_prompt` với dữ liệu giả có email và chuỗi giống token | Prompt không chứa các chuỗi đó |
| M4-03 | `pick_chunks` vượt giới hạn ký tự | Tổng không quá `max_chars`, ưu tiên tài liệu mới nhất |
| M4-04 | `generate_quiz` với LLM giả trả đủ câu hợp lệ | Quiz qua `validate_quiz`, tối đa `n` câu, id `q1`, `q2`, ... |
| M4-05 | Câu có số lựa chọn khác 4 hoặc lựa chọn rỗng | Bị loại, có lý do |
| M4-06 | `answer_index` ngoài 0 đến 3 hoặc không phải số | Bị loại |
| M4-07 | Hai lựa chọn trùng nhau | Bị loại |
| M4-08 | `source.quote` không có nguyên văn trong tài liệu | Bị loại; nếu chỉ khác khoảng trắng hoặc hoa thường thì giữ |
| M4-09 | `source.file` không có trong nguồn | Bị loại |
| M4-10 | Hai câu hỏi giống hệt nhau | Giữ một |
| M4-11 | Còn ít hơn 3 câu hợp lệ | `generate_quiz` trả `None` |
| M4-12 | LLM ném `LLMError` hoặc trả JSON hỏng | Thử lại đúng một lần rồi trả `None`, không ném ngoại lệ |

## M5 · Kho Google Drive (`tests/test_store.py`)

| Mã | Kịch bản | Kết quả mong đợi |
| --- | --- | --- |
| M5-01 | `put_json` rồi `get_json` (cả hai loại kho) | Nhận lại đúng dữ liệu, tiếng Việt nguyên vẹn |
| M5-02 | `get_json` với tên không tồn tại | Trả `None` |
| M5-03 | `put_json` hai lần cùng tên | Chỉ một file, nội dung là bản mới |
| M5-04 | `put_file` | File được lưu đúng nội dung |
| M5-05 | `list_names` | Liệt kê đúng các tên |
| M5-06 | Tên có `/` hoặc `..` | Ném `ValueError` ở cả hai kho |
| M5-07 | `DriveStore` với service giả | Tạo mới khi chưa có, cập nhật khi đã có (kiểm tra lời gọi `create` và `update`) |
| M5-08 | Service giả trả 429 | Thử lại tối đa 3 lần rồi báo lỗi |
| M5-09 | Service giả trả 403 hoặc 404 | Lỗi tiếng Việt về việc chưa chia sẻ thư mục, không lộ khoá hay email |
| M5-10 | `make_store` thiếu hoặc đủ biến; `get_credentials` thiếu biến | Chọn đúng loại kho; không gọi mạng khi tạo `LocalStore`; lỗi rõ ràng khi thiếu biến |

## M6a · Bộ xếp lịch (`tests/test_scheduler.py`)

| Mã | Kịch bản | Kết quả mong đợi |
| --- | --- | --- |
| M6a-01 | `free_slots` có một giờ bận giữa khung 18:00 đến 22:00 | Hai khoảng trống hai bên, không chồng giờ bận |
| M6a-02 | `free_slots` với đệm 10 phút | Hai đầu mỗi giờ bận được chừa 10 phút |
| M6a-03 | Giờ bận hoàn toàn ngoài khung học | Không ảnh hưởng khoảng trống |
| M6a-04 | Một deadline sau 3 ngày | Phiên rơi vào ngày trước hạn, trong khung 18:00 đến 22:00 |
| M6a-05 | `now` là 21:50 và ngày ưu tiên là hôm nay | Không xếp vào quá khứ; bắt đầu từ `now` làm tròn lên 5 phút hoặc dời ngày |
| M6a-06 | Mọi chỗ trống đều sau hạn nộp | Không xếp, deadline vào danh sách không xếp được |
| M6a-07 | Ba bài tập cùng môn cùng ngày hạn | Chỉ một phiên cho môn đó |
| M6a-08 | Bốn môn cùng hạn một ngày, `max_per_day = 2` | Không ngày nào quá 2 phiên |
| M6a-09 | Có giờ bận và các phiên đã xếp | Không phiên nào chồng nhau hay chồng giờ bận, có đệm 10 phút |
| M6a-10 | Hết chỗ trống, hạn đã qua | Có lý do `hết chỗ trống trước hạn` và `hạn đã qua` |
| M6a-11 | `due_at` 16:59Z (23:59 giờ Việt Nam) và 17:01Z (00:01 hôm sau) | "Ngày đến hạn" tính theo giờ địa phương, đúng ngày |
| M6a-12 | Chạy hai lần cùng đầu vào | Kết quả giống hệt, qua `validate_plan`, mỗi phiên 25 đến 45 phút |

## M6b · Google Calendar (`tests/test_gcal.py`)

| Mã | Kịch bản | Kết quả mong đợi |
| --- | --- | --- |
| M6b-01 | `list_busy` với kết quả hai trang | Đi hết `nextPageToken`, gom đủ sự kiện |
| M6b-02 | Có sự kiện `cancelled`, `transparent` và cả ngày | Cả ba loại bị bỏ |
| M6b-03 | Các khoảng bận chồng hoặc liền nhau | Gộp thành một khoảng, sắp tăng dần |
| M6b-04 | `create_events` với plan 2 phiên | Gọi tạo 2 sự kiện và điền `calendar_event_id` |
| M6b-05 | Chạy `create_events` lần hai | Không tạo thêm, dùng lại id theo khoá `studyAgentKey` |
| M6b-06 | Kiểm tra plan đầu vào sau khi gọi | Không bị sửa (trả bản mới) |
| M6b-07 | Nội dung sự kiện | Tiêu đề `Ôn bài: <môn>`, nhắc trước 15 phút, không chứa email hay token |
| M6b-08 | Lịch có sự kiện không mang khoá | Không bị sửa hay xóa |
| M6b-09 | Một phiên bị lỗi API | Phiên đó giữ `null`, phiên khác vẫn được tạo |
| M6b-10 | Thiếu `GOOGLE_CALENDAR_ID`; 403 và 404; 429 | Lỗi rõ ràng; lỗi tiếng Việt "chưa chia sẻ lịch"; 429 thử lại tối đa 3 lần |

## M7 · Orchestrator và Actions (`tests/test_orchestrator.py`)

| Mã | Kịch bản | Kết quả mong đợi |
| --- | --- | --- |
| M7-01 | Chạy đủ các bước với module giả | Sinh `portal.json`, `quiz-*.json`, `plan.json`, `today.json`, `run-report.json`, đều đúng hợp đồng |
| M7-02 | `portal` ném lỗi | Các bước sau `skipped`, mã thoát 1 |
| M7-03 | Một môn lỗi ở `materials` | Môn đó bị bỏ, vẫn chạy `plan` và `publish` |
| M7-04 | `generate_quiz` trả `None` | Không ghi quiz môn đó, báo cáo ghi rõ |
| M7-05 | `plan` ném lỗi (Calendar) | `today.json` có `sessions: []`, quiz vẫn được publish |
| M7-06 | 5 môn có deadline, `MAX_QUIZZES = 2` | Chỉ sinh quiz cho 2 môn có hạn gần nhất |
| M7-07 | Phiên của hôm nay và ngày mai, `now` gần nửa đêm giờ Việt Nam | `today.json` chỉ chứa phiên của ngày hiện tại theo `Asia/Ho_Chi_Minh` |
| M7-08 | `--dry-run` | Không gọi `put_json` của Drive, không tạo sự kiện; vẫn ghi file trong `out/` |
| M7-09 | `--only study,plan` | Chỉ chạy các bước được chọn |
| M7-10 | Quét `run-report.json` và log | Không chứa token, khoá hay email |
| M7-11 | Mã thoát | 0 khi `portal` ổn dù bước khác lỗi một phần; 1 khi `portal` hoặc `publish` lỗi |
| M7-12 | `daily.yml` | YAML hợp lệ, cron `0 0 * * *`, có `timeout-minutes`, `permissions`, `concurrency`, chạy `pytest` trước orchestrator, không chứa giá trị bí mật |

## M8 · Quiz client (`web/grade.test.js` và kiểm tra bằng trình duyệt)

| Mã | Kịch bản | Kết quả mong đợi |
| --- | --- | --- |
| M8-01 | `grade` khi trả lời đúng hết | `ratio` = 1, `passed` = true, `wrong` rỗng |
| M8-02 | Có câu sai và câu bỏ trống | Câu bỏ trống tính sai, `wrong` liệt kê đúng id |
| M8-03 | 7/10 với `pass_ratio` 0.7; 6/10 | 7/10 đạt; 6/10 không đạt (tránh lỗi làm tròn số thực) |
| M8-04 | `dayStatus` khi đủ và khi thiếu kết quả | `done` đúng, `pending` liệt kê đúng môn |
| M8-05 | `validateQuizShape` với quiz đúng và quiz sai | `ok` đúng, thông điệp lỗi nêu rõ trường |
| M8-06 | Xáo lựa chọn nhiều lần | Đáp án đúng luôn trỏ đúng lựa chọn gốc |
| M8-07 | Nạp bộ fixture, làm hết một quiz trong trình duyệt | Không lỗi console, hiện điểm cuối bài |
| M8-08 | `today.json` nêu quiz chưa được chọn | Thông báo đúng tên file còn thiếu |
| M8-09 | `localStorage` ném lỗi hoặc bị chặn | Trang vẫn chạy được |
| M8-10 | Câu hỏi chứa `<img src=x onerror=alert(1)>` | Hiển thị như chữ, không chạy mã |
