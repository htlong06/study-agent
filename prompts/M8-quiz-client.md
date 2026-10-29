# M8 · Quiz client (trang web một file)

Bạn là kỹ sư web. Hãy đọc `CONVENTIONS.md` và `docs/contracts.md` (C4, C6). Chỉ tạo `web/quiz.html`, `web/grade.js`, `web/grade.test.js`.

## Mục tiêu

Một trang web chạy trên trình duyệt điện thoại để làm quiz ôn bài. **Không gọi mạng, không dùng thư viện ngoài, không gửi dữ liệu đi đâu.** Chấm điểm bằng mã trên máy.

## Cách nạp dữ liệu

Người dùng bấm "Chọn file" và chọn `today.json` cùng các `quiz-*.json` (bộ chọn file của Android hiển thị được Google Drive). Trang đọc file bằng `FileReader`. Nếu thiếu quiz nêu trong `today.json`, hiện thông báo rõ tên file còn thiếu.

## `web/grade.js` (hàm thuần, dùng được trong trình duyệt và Node)

```js
grade(quiz, answers) -> { correct, total, ratio, passed, wrong: [questionId, ...] }
// answers: { "q1": 2, "q2": 0, ... }; câu chưa trả lời tính là sai
dayStatus(today, results) -> { done: boolean, pending: [courseId, ...] }
// results: { [courseId]: { ratio, passed } }; done khi mọi quiz trong today.quizzes đã passed
validateQuizShape(quiz) -> { ok: boolean, error?: string }  // theo C4
```
Xuất bằng `module.exports` khi có `module`, và gắn vào `window.StudyGrade` khi chạy trong trình duyệt.

## Giao diện (`quiz.html`)

1. Tiếng Việt, ưu tiên màn hình điện thoại, chữ đọc được ngoài nắng, hỗ trợ chế độ tối theo hệ thống.
2. Mỗi lần một câu, 4 lựa chọn là nút lớn dễ bấm; có tiến độ "Câu 3 / 8".
3. Sau khi chọn: hiện đúng hay sai, đáp án đúng, `explanation`, và `source.quote` kèm tên file nguồn.
4. Cuối bài: điểm, tỉ lệ so với `pass_ratio`, danh sách câu sai để xem lại, nút "Làm lại" (xáo thứ tự lựa chọn mỗi lần, `answer_index` được tính lại cho đúng).
5. Kết quả mỗi môn lưu `localStorage["study-agent.result.<date>.<course_id>"] = {ratio, passed, at}`; khi mọi quiz của ngày đều đạt, lưu `localStorage["study-agent.done.<date>"] = "1"` và hiện "Hôm nay đã xong".
6. `localStorage` có thể lỗi hoặc rỗng: bọc `try/catch`, trang vẫn chạy được.
7. Nội dung từ file JSON chèn vào trang bằng `textContent`, **không dùng `innerHTML`** (tránh chèn mã).

## Tiêu chí hoàn thành

- `node --test web/` qua toàn bộ test.
- Mở `quiz.html` bằng trình duyệt, nạp bộ fixture, làm hết một quiz không lỗi console.
- Đã làm xong các kịch bản `M8-01` đến `M8-10` trong `docs/test-plan.md`.

## Ngoài phạm vi

Gửi cờ "đã xong" sang ứng dụng chặn game (thuộc M9; ghi vấn đề này vào "Đề xuất thay đổi" nếu có ý tưởng), đồng bộ giữa các thiết bị.

Cuối phiên, dán báo cáo bàn giao theo mục 8 của `CONVENTIONS.md`.
