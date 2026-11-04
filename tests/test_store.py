"""Kiểm thử M5 (google_auth.py, store.py). Mã kịch bản M5-01..M5-10 nằm trong tên hàm và docstring.

DriveStore chạy với một `service` giả (FakeDrive) lưu file trong bộ nhớ, không cần mạng.
"""
import re
import socket

import httplib2
import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from src import store as store_mod
from src.google_auth import GoogleAuthError, REQUIRED_VARS, SCOPE_DRIVE, get_credentials, has_google_config
from src.store import DriveStore, LocalStore, StoreError, make_store

SECRETS = {"GOOGLE_CLIENT_ID": "cid-secret-111", "GOOGLE_CLIENT_SECRET": "csecret-222", "GOOGLE_REFRESH_TOKEN": "1//rtoken-333"}


def http_error(status, body=b"{}"):
    return HttpError(httplib2.Response({"status": str(status)}), body)


class FakeRequest:
    def __init__(self, fake, method, kwargs):
        self.fake, self.method, self.kwargs = fake, method, kwargs

    def execute(self):
        self.fake.calls.append((self.method, self.kwargs))
        queue = self.fake.errors.get(self.method)
        if queue:
            raise queue.pop(0)
        return getattr(self.fake, "_" + self.method)(**self.kwargs)


class FakeDrive:
    """Giả lập files().list/create/update/get_media của Drive v3 (đủ cho DriveStore)."""

    def __init__(self, page_size=100):
        self.items = {}      # id -> {name, parents, mime, content}
        self.calls = []
        self.errors = {}     # tên hàm -> danh sách ngoại lệ sẽ ném lần lượt
        self.page_size = page_size
        self._n = 0

    def files(self):
        return self

    def list(self, **kw): return FakeRequest(self, "list", kw)
    def create(self, **kw): return FakeRequest(self, "create", kw)
    def update(self, **kw): return FakeRequest(self, "update", kw)
    def get_media(self, **kw): return FakeRequest(self, "get_media", kw)

    def count(self, method):
        return sum(1 for m, _ in self.calls if m == method)

    def _new_id(self):
        self._n += 1
        return f"id{self._n}"

    def _list(self, q, pageToken=None, **_):
        name = re.search(r"name = '((?:[^'\\]|\\.)*)'", q)
        parent = re.search(r"'(\w+)' in parents", q)
        mime = re.search(r"mimeType = '([^']+)'", q)
        rows = []
        for fid, it in self.items.items():
            if name and it["name"] != name.group(1).replace("\\'", "'").replace("\\\\", "\\"):
                continue
            if parent and parent.group(1) not in it["parents"]:
                continue
            if mime and it["mime"] != mime.group(1):
                continue
            rows.append({"id": fid, "name": it["name"]})
        start = int(pageToken or 0)
        out = {"files": rows[start:start + self.page_size]}
        if start + self.page_size < len(rows):
            out["nextPageToken"] = str(start + self.page_size)
        return out

    def _create(self, body, media_body=None, **_):
        fid = self._new_id()
        content = media_body.getbytes(0, media_body.size()) if media_body is not None else b""
        self.items[fid] = {"name": body["name"], "parents": body.get("parents", ["root"]),
                           "mime": body.get("mimeType", "file"), "content": content}
        return {"id": fid}

    def _update(self, fileId, media_body, **_):
        self.items[fileId]["content"] = media_body.getbytes(0, media_body.size())
        return {"id": fileId}

    def _get_media(self, fileId):
        return self.items[fileId]["content"]

    def files_named(self, name):
        return [it for it in self.items.values() if it["name"] == name]


@pytest.fixture(params=["local", "drive"])
def store(request, tmp_path):
    if request.param == "local":
        return LocalStore(tmp_path / "kho")
    return DriveStore(FakeDrive())


@pytest.fixture
def no_sleep(monkeypatch):
    waits = []
    monkeypatch.setattr(store_mod, "_sleep", waits.append)
    return waits


DATA = {"date": "2026-10-29", "ghi_chú": "Tích phân bội đổi biến", "n": [1, 2, 3]}


def test_m5_01_put_get_roundtrip_vietnamese(store):
    """M5-01: put_json rồi get_json (cả hai kho) nhận lại đúng dữ liệu, tiếng Việt nguyên vẹn."""
    store.put_json("today.json", DATA)
    assert store.get_json("today.json") == DATA


def test_m5_02_get_missing_returns_none(store):
    """M5-02: get_json với tên không tồn tại trả None."""
    assert store.get_json("khong-co.json") is None


def test_m5_03_put_twice_keeps_single_file(store):
    """M5-03: put_json hai lần cùng tên chỉ còn một file, nội dung là bản mới."""
    store.put_json("today.json", {"v": 1})
    store.put_json("today.json", {"v": 2})
    assert store.get_json("today.json") == {"v": 2}
    assert store.list_names() == ["today.json"]


def test_m5_04_put_file(store, tmp_path):
    """M5-04: put_file lưu đúng nội dung, ghi đè khi cùng tên."""
    src = tmp_path / "bai.txt"
    src.write_bytes("Nội dung bài giảng\n".encode("utf-8"))
    store.put_file(src, "bai.txt")
    assert "bai.txt" in store.list_names()
    src.write_bytes("Bản mới\n".encode("utf-8"))
    store.put_file(src, "bai.txt")
    assert store.list_names().count("bai.txt") == 1
    if isinstance(store, LocalStore):
        assert (store.folder / "bai.txt").read_text(encoding="utf-8") == "Bản mới\n"
    else:
        assert store._svc.files_named("bai.txt")[0]["content"] == "Bản mới\n".encode("utf-8")


def test_m5_05_list_names(store):
    """M5-05: list_names liệt kê đúng các tên (đã sắp xếp)."""
    assert store.list_names() == []
    for name in ("quiz-102.json", "today.json", "quiz-101.json"):
        store.put_json(name, {"x": 1})
    assert store.list_names() == ["quiz-101.json", "quiz-102.json", "today.json"]


def test_m5_05_list_names_follows_pagination():
    """M5-05: list_names đi hết các trang của Drive."""
    drive = FakeDrive(page_size=2)
    s = DriveStore(drive)
    for i in range(5):
        s.put_json(f"f{i}.json", {"i": i})
    assert s.list_names() == [f"f{i}.json" for i in range(5)]
    assert drive.count("list") > 5


@pytest.mark.parametrize("bad", ["../x.json", "a/b.json", "..", "a\\b.json", "", "  ", "x..json"])
def test_m5_06_bad_names_rejected(store, bad, tmp_path):
    """M5-06: tên có '/' hoặc '..' (và tên rỗng) ném ValueError ở cả hai kho, ở mọi thao tác."""
    f = tmp_path / "f.txt"
    f.write_text("x")
    with pytest.raises(ValueError):
        store.put_json(bad, {})
    with pytest.raises(ValueError):
        store.get_json(bad)
    with pytest.raises(ValueError):
        store.put_file(f, bad)


def test_m5_06_local_store_cannot_escape_folder(tmp_path):
    """M5-06: không có file nào được ghi ra ngoài thư mục của kho."""
    s = LocalStore(tmp_path / "kho")
    with pytest.raises(ValueError):
        s.put_json("../thoat.json", {})
    assert not (tmp_path / "thoat.json").exists()


def test_m5_07_drive_creates_then_updates():
    """M5-07: tạo mới khi chưa có, cập nhật khi đã có (kiểm tra lời gọi create và update)."""
    drive = FakeDrive()
    s = DriveStore(drive)
    s.put_json("today.json", {"v": 1})
    uploads = [(m, kw) for m, kw in drive.calls if m in ("create", "update") and "media_body" in kw]
    assert [m for m, _ in uploads] == ["create"]
    s.put_json("today.json", {"v": 2})
    uploads = [(m, kw) for m, kw in drive.calls if m in ("create", "update") and "media_body" in kw]
    assert [m for m, _ in uploads] == ["create", "update"]
    assert len(drive.files_named("today.json")) == 1


def test_m5_07_drive_creates_folder_once_and_reuses():
    """M5-07: tự tạo thư mục StudyAgent khi chưa có; cửa hàng mới dùng lại thư mục cũ."""
    drive = FakeDrive()
    DriveStore(drive).put_json("a.json", {})
    folders = [it for it in drive.items.values() if it["mime"] == store_mod.FOLDER_MIME]
    assert [f["name"] for f in folders] == ["StudyAgent"] and folders[0]["parents"] == ["root"]
    DriveStore(drive).put_json("b.json", {})
    assert len([it for it in drive.items.values() if it["mime"] == store_mod.FOLDER_MIME]) == 1
    assert sorted(DriveStore(drive).list_names()) == ["a.json", "b.json"]
    file_item = drive.files_named("a.json")[0]
    folder_id = next(i for i, it in drive.items.items() if it["name"] == "StudyAgent")
    assert file_item["parents"] == [folder_id]


def test_m5_07_no_network_before_first_use():
    """M5-07: tạo DriveStore không gọi Drive; chỉ thao tác đầu tiên mới gọi."""
    drive = FakeDrive()
    s = DriveStore(drive)
    assert drive.calls == []
    s.list_names()
    assert drive.calls


def test_m5_07_name_with_quote_is_escaped():
    """M5-07: tên file có dấu nháy đơn không làm hỏng truy vấn."""
    drive = FakeDrive()
    s = DriveStore(drive)
    s.put_json("it's.json", {"v": 1})
    s.put_json("it's.json", {"v": 2})
    assert s.get_json("it's.json") == {"v": 2}
    assert len(drive.files_named("it's.json")) == 1


def test_m5_08_retry_429_then_success(no_sleep):
    """M5-08: 429 hai lần rồi thành công thì vẫn xong, có chờ tăng dần."""
    drive = FakeDrive()
    s = DriveStore(drive, folder_id="root")
    drive.errors["list"] = [http_error(429), http_error(503)]
    s.put_json("a.json", {"v": 1})
    assert s.get_json("a.json") == {"v": 1}
    assert no_sleep == [2, 4]


def test_m5_08_429_gives_up_after_three_attempts(no_sleep):
    """M5-08: 429 liên tục thì thử đúng 3 lượt rồi báo lỗi."""
    drive = FakeDrive()
    s = DriveStore(drive, folder_id="root")
    drive.errors["list"] = [http_error(429)] * 10
    with pytest.raises(StoreError) as exc:
        s.put_json("a.json", {})
    assert drive.count("list") == 3
    assert "429" in str(exc.value)


def test_m5_08_rate_limit_403_is_retried(no_sleep):
    """M5-08: 403 do rateLimitExceeded được coi là tạm thời và thử lại."""
    drive = FakeDrive()
    s = DriveStore(drive, folder_id="root")
    drive.errors["list"] = [http_error(403, b'{"error": {"errors": [{"reason": "userRateLimitExceeded"}]}}')]
    assert s.get_json("a.json") is None
    assert drive.count("list") == 2


@pytest.mark.parametrize("status", [403, 404])
def test_m5_09_403_404_vietnamese_error_no_secrets(status, monkeypatch, no_sleep):
    """M5-09: 403 hoặc 404 cho lỗi tiếng Việt về quyền truy cập Drive, không lộ khoá, token hay email."""
    for k, v in SECRETS.items():
        monkeypatch.setenv(k, v)
    drive = FakeDrive()
    drive.errors["list"] = [http_error(status, b'{"message": "chi tiet nhay cam"}')]
    with pytest.raises(StoreError) as exc:
        DriveStore(drive, folder_id="root").put_json("a.json", {})
    msg = str(exc.value)
    assert "Drive" in msg and "drive.file" in msg
    assert drive.count("list") == 1  # không thử lại
    assert not any(v in msg for v in SECRETS.values()) and "@" not in msg and "nhay cam" not in msg


def test_m5_09_refresh_token_revoked(monkeypatch):
    """M5-09: lỗi làm mới token (invalid_grant) cho thông điệp tiếng Việt chỉ cách lấy lại token."""
    drive = FakeDrive()
    drive.errors["list"] = [RefreshError("invalid_grant: Token has been expired or revoked.")]
    with pytest.raises(StoreError) as exc:
        DriveStore(drive, folder_id="root").list_names()
    msg = str(exc.value)
    assert "refresh token" in msg.lower() and "google-setup" in msg
    assert "mã lỗi Google: invalid_grant" in msg and "Token has been expired" not in msg


def clear_google_env(monkeypatch):
    for name in REQUIRED_VARS:
        monkeypatch.delenv(name, raising=False)


def test_m5_10_get_credentials_missing_names_only_variable_names(monkeypatch):
    """M5-10: get_credentials thiếu biến thì lỗi rõ ràng, nêu đúng tên biến thiếu."""
    clear_google_env(monkeypatch)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", SECRETS["GOOGLE_CLIENT_ID"])
    with pytest.raises(GoogleAuthError) as exc:
        get_credentials([SCOPE_DRIVE])
    msg = str(exc.value)
    assert "GOOGLE_CLIENT_SECRET" in msg and "GOOGLE_REFRESH_TOKEN" in msg and "GOOGLE_CLIENT_ID" not in msg
    assert SECRETS["GOOGLE_CLIENT_ID"] not in msg


def test_m5_10_get_credentials_builds_oauth_credentials(monkeypatch):
    """M5-10: đủ biến thì dựng credentials OAuth đúng scope, chưa gọi mạng."""
    for k, v in SECRETS.items():
        monkeypatch.setenv(k, v)
    creds = get_credentials([SCOPE_DRIVE])
    assert isinstance(creds, Credentials)
    assert creds.refresh_token == SECRETS["GOOGLE_REFRESH_TOKEN"]
    assert creds.token is None and list(creds.scopes) == [SCOPE_DRIVE]
    assert has_google_config()


def test_m5_10_make_store_local_when_missing(monkeypatch, tmp_path):
    """M5-10: thiếu biến Google thì dùng LocalStore, không tạo thư mục khi chỉ khởi tạo."""
    clear_google_env(monkeypatch)
    s = make_store(tmp_path / "out")
    assert isinstance(s, LocalStore)
    assert not (tmp_path / "out").exists()
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "x")  # chỉ có một phần vẫn là LocalStore
    assert isinstance(make_store(tmp_path / "out"), LocalStore)


def test_m5_10_make_store_drive_without_network(monkeypatch):
    """M5-10: đủ biến thì DriveStore, và việc tạo kho không mở kết nối mạng nào."""
    for k, v in SECRETS.items():
        monkeypatch.setenv(k, v)

    def no_network(*a, **k):
        raise AssertionError("không được gọi mạng khi tạo kho")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    s = make_store()
    assert isinstance(s, DriveStore)


def test_m5_10_make_store_uses_folder_name_env(monkeypatch):
    """M5-10: DRIVE_FOLDER_NAME đổi tên thư mục Drive."""
    for k, v in SECRETS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("DRIVE_FOLDER_NAME", "OnBai")
    assert make_store()._folder_name == "OnBai"


def test_m5_secrets_never_in_logs_or_errors(monkeypatch, caplog, no_sleep):
    """M5-09: khoá và token không xuất hiện trong log hay thông điệp lỗi khi có sự cố."""
    for k, v in SECRETS.items():
        monkeypatch.setenv(k, v)
    drive = FakeDrive()
    drive.errors["list"] = [http_error(500), http_error(500), http_error(500)]
    caplog.set_level("DEBUG")
    with pytest.raises(StoreError) as exc:
        DriveStore(drive, folder_id="root").list_names()
    blob = caplog.text + str(exc.value)
    assert not any(v in blob for v in SECRETS.values())


@pytest.mark.live
def test_m5_live_drive_roundtrip():
    """Chạy tay: python -m pytest -m live tests/test_store.py (cần ba biến Google trong .env). Ghi một file thử vào thư mục StudyAgent."""
    from src.config import load_env
    load_env()
    if not has_google_config():
        pytest.skip("chưa có GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN")
    s = make_store()
    assert isinstance(s, DriveStore)
    s.put_json("kiem-tra-ket-noi.json", {"ghi_chú": "Tiếng Việt có dấu"})
    assert s.get_json("kiem-tra-ket-noi.json") == {"ghi_chú": "Tiếng Việt có dấu"}
    assert "kiem-tra-ket-noi.json" in s.list_names()


@pytest.mark.parametrize("exc, code, hint", [
    (RefreshError("invalid_client: Unauthorized", {"error": "invalid_client", "error_description": "Unauthorized"}), "invalid_client", "Client secret"),
    (RefreshError("invalid_grant: Bad Request", {"error": "invalid_grant", "error_description": "Bad Request"}), "invalid_grant", "Client ID khác"),
    (RefreshError("unauthorized_client: x"), "unauthorized_client", "scope"),
    (RefreshError("điều gì đó lạ SECRET-123"), None, "hết hạn hoặc bị thu hồi"),
])
def test_m5_09_refresh_error_names_google_code_and_fix(exc, code, hint):
    """M5-09: lỗi làm mới token nêu mã lỗi Google và cách sửa tương ứng, không lộ nội dung lạ."""
    from src.google_auth import refresh_error_message
    msg = refresh_error_message(exc)
    assert hint in msg and "google-setup" in msg
    assert (f"mã lỗi Google: {code}" in msg) if code else ("mã lỗi" not in msg)
    assert "SECRET-123" not in msg and "Unauthorized" not in msg and "Bad Request" not in msg
