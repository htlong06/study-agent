"""M5: kho lưu file kết quả (today.json, quiz-*.json) trên Google Drive hoặc trong thư mục cục bộ.

Hai kho có cùng giao diện nên Orchestrator không cần biết đang dùng loại nào.
"""
import json
import logging
import mimetypes
import shutil
import time
from pathlib import Path
from typing import Protocol

from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaInMemoryUpload

from src.config import OUT_DIR, env
from src.google_auth import SCOPE_DRIVE, get_credentials, has_google_config, refresh_error_message

log = logging.getLogger(__name__)

RETRIES = 3
FOLDER_MIME = "application/vnd.google-apps.folder"
DEFAULT_FOLDER_NAME = "StudyAgent"
_sleep = time.sleep  # tách riêng để test không phải chờ thật

MSG_NO_ACCESS = (
    "Không truy cập được thư mục Drive. Hãy kiểm tra Drive API đã bật, quyền drive.file "
    "đã được cấp, và refresh token còn hiệu lực (docs/google-setup.md)."
)


class StoreError(RuntimeError):
    """Lỗi kho lưu trữ; thông điệp tiếng Việt, không chứa khoá hay token."""


class Store(Protocol):
    def put_json(self, name: str, obj: dict) -> None: ...
    def get_json(self, name: str) -> dict | None: ...
    def put_file(self, local_path: Path, name: str) -> None: ...
    def list_names(self) -> list[str]: ...


def check_name(name: str) -> str:
    """Chỉ nhận tên file đơn thuần, chặn ghi ra ngoài thư mục."""
    if not isinstance(name, str) or not name.strip() or "\x00" in name \
            or "/" in name or "\\" in name or ".." in name:
        raise ValueError("Tên file không hợp lệ: chỉ được là tên file, không chứa '/', '\\' hay '..'")
    return name


def _dump(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _load(raw: bytes, name: str) -> dict:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StoreError(f"File {name} không phải JSON hợp lệ") from None


class LocalStore:
    """Lưu trong một thư mục trên máy (dùng khi test hoặc khi chưa cấu hình Drive)."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def put_json(self, name: str, obj: dict) -> None:
        self._write(check_name(name), _dump(obj))

    def get_json(self, name: str) -> dict | None:
        path = self.folder / check_name(name)
        return _load(path.read_bytes(), name) if path.is_file() else None

    def put_file(self, local_path: Path, name: str) -> None:
        check_name(name)
        self.folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, self.folder / name)

    def list_names(self) -> list[str]:
        if not self.folder.is_dir():
            return []
        return sorted(p.name for p in self.folder.iterdir() if p.is_file())

    def _write(self, name: str, data: bytes) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / name).write_bytes(data)


def _q(value: str) -> str:
    """Thoát ký tự đặc biệt trong chuỗi truy vấn Drive."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _is_rate_limited(err: HttpError) -> bool:
    content = err.content if isinstance(err.content, bytes) else str(err.content).encode()
    return b"ratelimit" in content.lower()


class DriveStore:
    """Lưu trong một thư mục Drive.

    Scope `drive.file` là đủ vì ứng dụng chỉ cần các file và thư mục do chính nó tạo: thư mục
    được tìm theo tên hoặc tạo mới ở lần dùng đầu tiên (không gọi mạng khi khởi tạo).
    """

    def __init__(self, service, folder_name: str = DEFAULT_FOLDER_NAME, folder_id: str | None = None):
        self._svc = service
        self._folder_name = folder_name
        self._folder_id = folder_id

    # --- hạ tầng ---
    def _execute(self, request):
        """Chạy một yêu cầu, thử lại 429/5xx tối đa RETRIES lượt, đổi lỗi thành StoreError tiếng Việt."""
        for attempt in range(RETRIES):
            try:
                return request.execute()
            except RefreshError as err:
                raise StoreError(refresh_error_message(err)) from None
            except HttpError as err:
                status = err.resp.status
                retryable = status == 429 or status >= 500 or (status == 403 and _is_rate_limited(err))
                if retryable and attempt < RETRIES - 1:
                    log.warning("Drive trả lỗi %s, thử lại lần %s", status, attempt + 2)
                    _sleep(2 ** (attempt + 1))
                    continue
                if status in (403, 404) and not retryable:
                    raise StoreError(MSG_NO_ACCESS) from None
                raise StoreError(f"Google Drive trả lỗi {status} sau {attempt + 1} lần thử") from None

    def _folder(self) -> str:
        if self._folder_id:
            return self._folder_id
        query = (f"name = '{_q(self._folder_name)}' and mimeType = '{FOLDER_MIME}' "
                 "and 'root' in parents and trashed = false")
        found = self._execute(self._svc.files().list(
            q=query, fields="files(id,name)", orderBy="createdTime", pageSize=10, spaces="drive"))
        files = found.get("files", [])
        if files:
            self._folder_id = files[0]["id"]
        else:
            created = self._execute(self._svc.files().create(
                body={"name": self._folder_name, "mimeType": FOLDER_MIME}, fields="id"))
            self._folder_id = created["id"]
            log.info("Đã tạo thư mục Drive %s", self._folder_name)
        return self._folder_id

    def _find(self, name: str) -> str | None:
        query = f"name = '{_q(name)}' and '{self._folder()}' in parents and trashed = false"
        found = self._execute(self._svc.files().list(
            q=query, fields="files(id,name)", orderBy="modifiedTime desc", pageSize=10, spaces="drive"))
        files = found.get("files", [])
        return files[0]["id"] if files else None

    def _put(self, name: str, media) -> None:
        """Ghi đè nếu đã có file cùng tên trong thư mục, không tạo bản trùng tên."""
        existing = self._find(name)
        if existing:
            self._execute(self._svc.files().update(fileId=existing, media_body=media, fields="id"))
        else:
            self._execute(self._svc.files().create(
                body={"name": name, "parents": [self._folder()]}, media_body=media, fields="id"))

    # --- giao diện Store ---
    def put_json(self, name: str, obj: dict) -> None:
        check_name(name)
        self._put(name, MediaInMemoryUpload(_dump(obj), mimetype="application/json", resumable=False))

    def get_json(self, name: str) -> dict | None:
        check_name(name)
        file_id = self._find(name)
        if file_id is None:
            return None
        return _load(self._execute(self._svc.files().get_media(fileId=file_id)), name)

    def put_file(self, local_path: Path, name: str) -> None:
        check_name(name)
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        self._put(name, MediaFileUpload(str(local_path), mimetype=mime, resumable=False))

    def list_names(self) -> list[str]:
        names, token = [], None
        while True:
            page = self._execute(self._svc.files().list(
                q=f"'{self._folder()}' in parents and trashed = false",
                fields="nextPageToken,files(name)", pageSize=100, pageToken=token, spaces="drive"))
            names += [f["name"] for f in page.get("files", [])]
            token = page.get("nextPageToken")
            if not token:
                return sorted(names)


def make_store(local_folder: Path | None = None) -> Store:
    """DriveStore nếu có đủ ba biến Google OAuth, ngược lại LocalStore(out/). Không gọi mạng."""
    if has_google_config():
        service = build("drive", "v3", credentials=get_credentials([SCOPE_DRIVE]), cache_discovery=False)
        return DriveStore(service, folder_name=env("DRIVE_FOLDER_NAME", DEFAULT_FOLDER_NAME))
    return LocalStore(local_folder or OUT_DIR)
