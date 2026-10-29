# M9 · Guard trên Android (để sau, chưa giao việc)

Trạng thái: **hoãn** theo quyết định của chủ dự án (27/10/2026). Không bắt đầu module này cho đến khi M1 đến M8 chạy tự động ổn định ít nhất 2 tuần.

## Mục tiêu đã thống nhất

Khi người dùng mở game trong danh sách mà hôm nay chưa xong quiz thì hiện màn hình chặn; xong quiz đạt ngưỡng thì mở khóa. Việc chặn do **mã quy tắc cố định chạy trên máy**, không dùng LLM và không phụ thuộc mạng. Đây là cơ chế tự kỷ luật: người dùng luôn tắt hoặc gỡ được.

## Vấn đề phải giải quyết trước khi giao

1. **Kênh báo "đã xong"**: trang web M8 lưu kết quả trong `localStorage` của trình duyệt, mà MacroDroid hay Tasker không đọc được. Cần chọn một kênh: (a) Guard viết bằng Kotlin và nhúng chính trang quiz trong WebView; (b) trang quiz mở một đường dẫn mà ứng dụng chặn game nhận; (c) người dùng nhập mã mở khóa do trang quiz hiển thị. Cần thử nghiệm trên máy thật rồi mới chốt.
2. Danh sách game cần chặn và khung giờ được phép chơi.
3. Quyền cần cấp: Usage access, hiển thị trên ứng dụng khác. **Không dùng AccessibilityService.**
4. Máy Android của người dùng: hãng, phiên bản, chính sách tiết kiệm pin có tự tắt dịch vụ nền không.

## Tiêu chí hoàn thành dự kiến

Chặn đúng game, mở khóa sau khi đạt ngưỡng 70%, vẫn hoạt động khi mất mạng, và tắt được dễ dàng trong cài đặt.

Khi sẵn sàng, bước đầu là tách module này thành các phần nhỏ (phát hiện ứng dụng đang mở, màn hình chặn, đọc cờ "đã xong") rồi viết prompt riêng như các module khác.
