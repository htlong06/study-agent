# M5 · Kho Google Drive và xác thực Google

Bạn là kỹ sư Python. Hãy đọc `CONVENTIONS.md` và `docs/contracts.md` (C6). Chỉ sửa `src/google_auth.py`, `src/store.py`, `tests/test_store.py` và thêm `google-api-python-client`, `google-auth` vào `requirements.txt`.

## Mục tiêu

Cho backend một chỗ duy nhất để lưu và đọc file kết quả (`today.json`, `quiz-*.json`) trên Google Drive, cùng một hàm xác thực dùng chung cho Drive và Calendar. Có thêm bản lưu cục bộ cùng giao diện để test và để chạy khi không có Drive.

## Giả định kỹ thuật (đã chốt)

Dùng **OAuth của chính người dùng** (đã đổi từ tài khoản dịch vụ ngày 03/11/2026 vì tài khoản dịch vụ không có dung lượng Drive, không ghi được vào Drive cá nhân). Ba biến môi trường: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` (một refresh token dùng chung cho Drive và Calendar, cấp cho hai scope `drive.file` và `calendar.events`). Hướng dẫn tạo nằm ở `docs/google-setup.md`.

Với scope `drive.file`, ứng dụng chỉ thấy các file và thư mục **do chính nó tạo**. Vì vậy mã **tự tạo thư mục `StudyAgent`** trong Drive của người dùng (tên đọc từ `DRIVE_FOLDER_NAME`, mặc định `StudyAgent`) rồi lưu mọi file vào đó. Không có `DRIVE_FOLDER_ID` do người dùng nhập.

## Giao diện công khai

```python
# src/google_auth.py
def get_credentials(scopes: list[str]):
    """Dựng credentials OAuth từ GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN.
    Thiếu biến thì ném lỗi tiếng Việt nêu đúng tên biến thiếu (không nêu giá trị)."""

# src/store.py
class Store(Protocol):
    def put_json(self, name: str, obj: dict) -> None: ...
    def get_json(self, name: str) -> dict | None: ...   # None nếu không có
    def put_file(self, local_path: Path, name: str) -> None: ...
    def list_names(self) -> list[str]: ...

class LocalStore:   # lưu trong một thư mục
    def __init__(self, folder: Path): ...

class DriveStore:   # lưu trong thư mục Drive do chính ứng dụng tạo
    def __init__(self, service, folder_name: str = "StudyAgent", folder_id: str | None = None): ...
    # folder_id None thì tìm thư mục theo tên (chỉ thấy thư mục do ứng dụng tạo), chưa có thì tạo; làm lười ở lần dùng đầu tiên

def make_store() -> Store:
    """DriveStore nếu có đủ ba biến Google OAuth, ngược lại LocalStore(out/)."""
```

## Yêu cầu

1. `put_json` và `put_file` **ghi đè** nếu file cùng tên đã có trong thư mục (không tạo bản trùng tên). Dùng `files().list` với truy vấn theo tên và thư mục cha, sau đó `update` hoặc `create`.
2. `name` chỉ là tên file; có `/` hoặc `..` thì ném `ValueError` (chặn ghi ra ngoài thư mục).
3. Scope tối thiểu: `https://www.googleapis.com/auth/drive.file` cho Drive; ghi rõ trong docstring vì sao đủ dùng (ứng dụng chỉ cần các file do chính nó tạo).
4. Thử lại tối đa 3 lượt gọi với lỗi 429 và 5xx, chờ tăng dần (như `src/llm.py`). Lỗi 403 hoặc 404 thì ném lỗi tiếng Việt nói rõ không truy cập được thư mục Drive và gợi ý kiểm tra quyền `drive.file` cùng refresh token. Lỗi làm mới token (`RefreshError`, ví dụ `invalid_grant`) thì ném lỗi tiếng Việt "refresh token hết hạn hoặc bị thu hồi, hãy lấy lại theo docs/google-setup.md". Không in khoá hay token.
5. Client secret, refresh token và access token không bao giờ xuất hiện trong log, thông điệp lỗi hay test.
6. Hàm `make_store` không gọi mạng khi tạo `LocalStore`; `DriveStore` cũng không gọi mạng cho đến thao tác đầu tiên.

## Tiêu chí hoàn thành

- Test dùng `service` giả (đối tượng Python có `files().list/create/update/get_media`), không cần mạng.
- `LocalStore` và `DriveStore` qua cùng một bộ test hành vi chung.
- Đã làm xong các kịch bản `M5-01` đến `M5-10` trong `docs/test-plan.md`.

## Ngoài phạm vi

Calendar (M6b), tạo OAuth client hay lấy refresh token trên Google Cloud (người dùng làm tay theo `docs/google-setup.md`).

Cuối phiên, dán báo cáo bàn giao theo mục 8 của `CONVENTIONS.md`.
