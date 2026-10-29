# M5 · Kho Google Drive và xác thực Google

Bạn là kỹ sư Python. Hãy đọc `CONVENTIONS.md` và `docs/contracts.md` (C6). Chỉ sửa `src/google_auth.py`, `src/store.py`, `tests/test_store.py` và thêm `google-api-python-client`, `google-auth` vào `requirements.txt`.

## Mục tiêu

Cho backend một chỗ duy nhất để lưu và đọc file kết quả (`today.json`, `quiz-*.json`) trên Google Drive, cùng một hàm xác thực dùng chung cho Drive và Calendar. Có thêm bản lưu cục bộ cùng giao diện để test và để chạy khi không có Drive.

## Giả định kỹ thuật (đã chốt)

Dùng **tài khoản dịch vụ (service account)**: JSON khoá nằm trong biến `GOOGLE_SERVICE_ACCOUNT_JSON` (nội dung JSON, không phải đường dẫn). Người dùng chia sẻ thư mục Drive và lịch cho email của tài khoản dịch vụ. ID thư mục Drive nằm trong `DRIVE_FOLDER_ID`.

## Giao diện công khai

```python
# src/google_auth.py
def get_credentials(scopes: list[str]):
    """Đọc GOOGLE_SERVICE_ACCOUNT_JSON, trả credentials. Thiếu biến thì ném lỗi tiếng Việt rõ ràng."""

# src/store.py
class Store(Protocol):
    def put_json(self, name: str, obj: dict) -> None: ...
    def get_json(self, name: str) -> dict | None: ...   # None nếu không có
    def put_file(self, local_path: Path, name: str) -> None: ...
    def list_names(self) -> list[str]: ...

class LocalStore:   # lưu trong một thư mục
    def __init__(self, folder: Path): ...

class DriveStore:   # lưu trong thư mục Drive
    def __init__(self, service, folder_id: str): ...

def make_store() -> Store:
    """DriveStore nếu có đủ GOOGLE_SERVICE_ACCOUNT_JSON và DRIVE_FOLDER_ID, ngược lại LocalStore(out/)."""
```

## Yêu cầu

1. `put_json` và `put_file` **ghi đè** nếu file cùng tên đã có trong thư mục (không tạo bản trùng tên). Dùng `files().list` với truy vấn theo tên và thư mục cha, sau đó `update` hoặc `create`.
2. `name` chỉ là tên file; có `/` hoặc `..` thì ném `ValueError` (chặn ghi ra ngoài thư mục).
3. Scope tối thiểu: `https://www.googleapis.com/auth/drive.file` cho Drive; ghi rõ vì sao đủ dùng khi thư mục đã được chia sẻ.
4. Thử lại tối đa 3 lần với lỗi 429 và 5xx, chờ tăng dần. Lỗi 403 hoặc 404 thì ném lỗi tiếng Việt nói rõ "chưa chia sẻ thư mục cho email tài khoản dịch vụ" (không in email hay khoá).
5. Khoá JSON không bao giờ xuất hiện trong log, thông điệp lỗi hay test.
6. Hàm `make_store` không gọi mạng khi tạo `LocalStore`.

## Tiêu chí hoàn thành

- Test dùng `service` giả (đối tượng Python có `files().list/create/update/get_media`), không cần mạng.
- `LocalStore` và `DriveStore` qua cùng một bộ test hành vi chung.
- Đã làm xong các kịch bản `M5-01` đến `M5-10` trong `docs/test-plan.md`.

## Ngoài phạm vi

Calendar (M6b), tạo tài khoản dịch vụ hay cấp quyền trên Google Cloud (người dùng làm tay; ghi hướng dẫn 5 dòng vào báo cáo bàn giao).

Cuối phiên, dán báo cáo bàn giao theo mục 8 của `CONVENTIONS.md`.
