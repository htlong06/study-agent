# Cài đặt Google (Drive và Calendar) cho Study Agent

Study Agent dùng **OAuth của chính bạn**, không dùng tài khoản dịch vụ (service account): tài khoản dịch vụ không có dung lượng Drive nên không ghi được vào Drive cá nhân. Một refresh token dùng chung cho Drive và Calendar. Bạn làm một lần.

## Biến cần có

| Biến | Ý nghĩa | Bắt buộc |
|---|---|---|
| `GOOGLE_CLIENT_ID` | Client ID của OAuth client (Web application) | có |
| `GOOGLE_CLIENT_SECRET` | Client secret | có |
| `GOOGLE_REFRESH_TOKEN` | Refresh token cấp cho hai scope bên dưới | có |
| `GOOGLE_CALENDAR_ID` | Lịch dùng để xếp phiên ôn, mặc định `primary` | không |
| `DRIVE_FOLDER_NAME` | Tên thư mục trong Drive, mặc định `StudyAgent` | không |

Trên máy: đặt trong `.env`. Trên GitHub Actions: đặt trong Settings → Secrets and variables → Actions.

## Các bước (Google Cloud)

1. Tạo dự án, bật **Google Drive API** và **Google Calendar API**.
2. Google Auth Platform: điền Branding (kể cả trang chủ, chính sách riêng tư, điều khoản và Authorized domain), thêm hai scope bên dưới ở mục Data Access, rồi **Publish app** để trạng thái là *In production* (ở chế độ *Testing* refresh token chỉ sống 7 ngày).
3. Clients: tạo client loại **Web application**, thêm redirect URI `https://developers.google.com/oauthplayground`.
4. Mở OAuth 2.0 Playground: bánh răng → tick *Use your own OAuth credentials* (Access type *Offline*), dán Client ID và Client secret, dán hai scope, **Authorize APIs**, đăng nhập đúng Gmail muốn chứa lịch và Drive, rồi **Exchange authorization code for tokens** và chép Refresh token.

Hai scope (cách nhau bằng dấu cách):

```
https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/calendar.events
```

`drive.file` chỉ cho thấy các file do chính ứng dụng tạo, nên mã tự tạo thư mục `StudyAgent` trong Drive của bạn; bạn không cần tạo hay chia sẻ thư mục.

## Thử nhanh trên máy

```
python -m pytest -m live tests/test_store.py
```

Lệnh này ghi một file `kiem-tra-ket-noi.json` vào thư mục `StudyAgent` trong Drive của bạn.

## Khi gặp lỗi

- *Refresh token hết hạn hoặc bị thu hồi* (`invalid_grant`): lấy lại token ở bước 4. Hay gặp nếu ứng dụng còn ở chế độ Testing hoặc bạn đã thu hồi quyền tại myaccount.google.com/permissions.
- *Không truy cập được thư mục Drive*: kiểm tra Drive API đã bật và token được cấp đúng hai scope.
- Chỉ dùng một Client ID cho cả lúc lấy token lẫn khi chạy; quyền `drive.file` gắn với từng ứng dụng.
- Không dán Client secret, token vào chat, issue hay file trong repo. Lỡ lộ thì tạo secret mới trong Google Cloud (Add secret) và thu hồi token cũ.
