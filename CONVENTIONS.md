# Quy ước phát triển (đọc trước khi viết bất kỳ dòng mã nào)

Áp dụng cho mọi AI hoặc người tham gia dự án Study Agent. Mỗi module được giao riêng, nên các quy ước dưới đây là cách duy nhất để các phần ghép lại với nhau mà không phải sửa nhau.

## 1. Nguyên tắc cốt lõi

1. **Một module, một việc.** Chỉ sửa file thuộc module được giao (xem cột "File được sửa" trong `prompts/README.md`). Cần thay đổi file ngoài phạm vi thì dừng lại và ghi vào mục "Đề xuất thay đổi" của báo cáo, không tự sửa.
2. **Giao tiếp giữa module chỉ qua hợp đồng dữ liệu** trong `docs/contracts.md` (file JSON có schema). Không import chéo nội bộ của module khác, trừ các hàm công khai đã ghi trong prompt của module đó.
3. **Chỉ LLM được phép "sáng tạo"; mọi thứ còn lại là mã xác định.** Lập lịch, chấm quiz, chặn game, lọc dữ liệu đều là mã thường, test được, không gọi LLM.
4. **Portal chỉ đọc.** Không bao giờ nộp bài, sửa hay xóa dữ liệu trên UET-LMS.
5. **Không bí mật trong mã.** Token và khoá chỉ lấy từ biến môi trường (`.env` hoặc GitHub Secrets), không in ra log, không đưa vào ví dụ, test hay prompt gửi LLM.

## 2. Công nghệ và cấu trúc

- Python 3.11 trở lên, chỉ dùng thư viện trong `requirements.txt`. Cần thêm thư viện thì nêu lý do trong báo cáo, và ưu tiên thư viện chuẩn.
- Cấu trúc thư mục:

```
src/            mã nguồn, mỗi module một file hoặc một gói nhỏ
tests/          pytest, tên file test_<module>.py
tests/fixtures/ dữ liệu mẫu giả (không dùng dữ liệu thật của người dùng)
prompts/        prompt giao việc cho từng module
docs/           hợp đồng dữ liệu, kế hoạch kiểm thử
data/           tài liệu bài giảng tải về (bị .gitignore)
out/            kết quả chạy: portal.json, quiz-*.json, plan.json, today.json (bị .gitignore)
```

## 3. Phong cách mã

- Định danh (biến, hàm, lớp, tên file) bằng **tiếng Anh**, `snake_case` cho hàm và biến, `PascalCase` cho lớp.
- Docstring, comment và thông báo cho người dùng bằng **tiếng Việt**, ngắn gọn, nói "vì sao" chứ không lặp lại "làm gì".
- Mọi hàm công khai có type hint và một docstring một dòng.
- Không dùng biến toàn cục thay đổi được. Cấu hình lấy qua `src/config.py` (`env`, `env_int`).
- Hàm thuần (không I/O) tách riêng khỏi hàm gọi mạng hoặc đọc ghi file, để test không cần mạng.
- Thời gian luôn là **ISO 8601 có múi giờ**. Lưu và trao đổi bằng UTC (`...Z`) hoặc có offset; chỉ đổi sang `Asia/Ho_Chi_Minh` khi hiển thị hoặc khi xếp lịch theo giờ địa phương.
- File JSON ghi bằng `ensure_ascii=False, indent=2`, mã hóa UTF-8, kết thúc bằng dòng trống.

## 4. Xử lý lỗi và log

- Lỗi mạng và lỗi API: thử lại tối đa 3 lần với thời gian chờ tăng dần, rồi ném ngoại lệ có thông điệp tiếng Việt, **không bao giờ chứa token hay khoá**.
- Một môn hoặc một file lỗi **không được làm hỏng cả lần chạy**: ghi vào trường `errors` của file kết quả rồi đi tiếp.
- Chỉ dùng `logging` của thư viện chuẩn, không `print` trong `src/` (trừ `main`/CLI). Mức `INFO` cho tiến trình, `WARNING` cho lỗi đã bỏ qua, `ERROR` cho lỗi dừng chạy.
- Không nuốt ngoại lệ im lặng: `except` chỉ bắt đúng loại ngoại lệ cần thiết.

## 5. Kiểm thử

- Mỗi module phải có `tests/test_<module>.py` chạy được bằng `python -m pytest` **không cần mạng và không cần khoá**. Mọi lời gọi HTTP, Drive, Calendar, LLM được thay bằng đối tượng giả (mock) hoặc dữ liệu trong `tests/fixtures/`.
- Kịch bản bắt buộc cho từng module nằm ở `docs/test-plan.md`. Mỗi kịch bản có mã (ví dụ `M1-03`) và phải có ít nhất một test mang mã đó trong tên hoặc docstring.
- Kiểm thử tích hợp thật (gọi API thật) đánh dấu `@pytest.mark.live` và mặc định bị bỏ qua; chỉ chạy tay khi có khoá.
- Mã mới phải làm cho toàn bộ test hiện có vẫn qua. Không xóa hay nới lỏng test của người khác để cho qua.

## 6. Định nghĩa "xong" (Definition of Done)

Một module chỉ được coi là xong khi cả 6 điều đúng:

1. Đáp ứng mọi mục trong "Tiêu chí hoàn thành" của prompt module.
2. Đầu ra khớp đúng schema trong `docs/contracts.md` (có test kiểm tra schema).
3. Mọi kịch bản trong `docs/test-plan.md` của module có test và đều qua.
4. Không có khoá, token, dữ liệu cá nhân hay tài liệu bản quyền trong mã, fixture hay log.
5. Không sửa file ngoài phạm vi được giao.
6. Có báo cáo bàn giao theo mẫu ở mục 8.

## 7. Git

- Nhánh: `module/<mã-module>-<tên-ngắn>`, ví dụ `module/m3-materials`.
- Commit nhỏ, thông điệp tiếng Việt theo dạng `<mã-module>: <việc đã làm>`, ví dụ `M3: tách văn bản PDF theo đoạn`.
- Không commit `.env`, `data/`, `out/`. Lỡ commit khoá thì thu hồi khoá ngay, xóa file là chưa đủ.

## 8. Báo cáo bàn giao (dán vào cuối phiên làm việc)

```
Module: <mã và tên>
Đã làm: <vài dòng>
File đã tạo/sửa: <danh sách>
Cách chạy test: python -m pytest tests/test_<module>.py
Kết quả test: <số qua / tổng>
Kịch bản chưa làm được và lý do: <hoặc "không có">
Đề xuất thay đổi ngoài phạm vi: <hoặc "không có">
Giả định đã dùng: <hoặc "không có">
```

## 9. Khi thiếu thông tin

Không đoán những điều có thể làm hỏng dữ liệu hoặc quyền riêng tư (ví dụ: tên trường trong JSON, quyền Google cần xin). Nếu prompt hoặc hợp đồng không nói rõ: chọn phương án an toàn nhất, ghi vào mục "Giả định đã dùng", và đi tiếp.
