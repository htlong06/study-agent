"""Kiểm thử M1: Canvas client (kịch bản M1-01 đến M1-12). Không gọi mạng."""
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

from src import canvas, contracts

NOW = datetime(2026, 10, 29, 0, 0, tzinfo=timezone.utc)
TOKEN = "SECRET-TOKEN-123"


class FakeResp:
    def __init__(self, data=None, status=200, headers=None):
        self._data, self.status_code, self.headers = data, status, headers or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=0):
        yield self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSession:
    """Trả phản hồi theo URL; ghi lại các lời gọi."""

    def __init__(self, routes):
        self.routes, self.calls, self.headers = routes, [], {}

    def get(self, url, params=None, **kwargs):
        self.calls.append((url, params))
        return self.routes[url]


def make_client(routes):
    client = canvas.CanvasClient("https://lms.example.test/", TOKEN)
    client.session = FakeSession(routes)
    return client


def test_m1_01_next_link_co_trang_ke():
    header = '<https://x/a?page=1>; rel="current", <https://x/a?page=2>; rel="next", <https://x/a?page=9>; rel="last"'
    assert canvas.next_link(header) == "https://x/a?page=2"


def test_m1_02_next_link_khong_co():
    assert canvas.next_link("") is None
    assert canvas.next_link(None) is None
    assert canvas.next_link('<https://x/a?page=1>; rel="current"') is None


def test_m1_03_get_all_phan_trang():
    base = "https://lms.example.test/api/v1/courses"
    routes = {
        base: FakeResp([{"id": 1}, {"id": 2}], headers={"Link": f'<{base}?page=2>; rel="next"'}),
        f"{base}?page=2": FakeResp([{"id": 3}], headers={"Link": f'<{base}?page=3>; rel="next"'}),
        f"{base}?page=3": FakeResp([{"id": 4}]),
    }
    client = make_client(routes)
    assert [c["id"] for c in client.get_all("/courses")] == [1, 2, 3, 4]
    # tham số chỉ gửi ở trang đầu, các trang sau dùng URL Canvas trả về
    assert client.session.calls[0][1]["per_page"] == 100
    assert client.session.calls[1][1] is None


def test_m1_04_401_khong_lo_token():
    base = "https://lms.example.test/api/v1/courses"
    client = make_client({base: FakeResp({}, status=401)})
    with pytest.raises(PermissionError) as err:
        client.get_all("/courses")
    assert TOKEN not in str(err.value)
    assert "401" in str(err.value)


def test_m1_04b_thieu_token():
    with pytest.raises(ValueError):
        canvas.CanvasClient("https://lms.example.test", "")


def test_m1_05_courses_bo_muc_thieu_truong():
    base = "https://lms.example.test/api/v1/courses"
    client = make_client(
        {
            base: FakeResp(
                [
                    {"id": 1, "name": "Giải tích 2", "course_code": "MAT1100"},
                    {"name": "Thiếu id"},
                    {"id": 3},
                    {"id": 4, "name": "Không mã môn"},
                ]
            )
        }
    )
    got = client.courses()
    assert [c["id"] for c in got] == [1, 4]
    assert got[1]["code"] == ""


class FakeClient:
    """Thay CanvasClient cho portal_snapshot và download_materials."""

    def __init__(self, courses, assignments=None, files=None, fail_course=None):
        self._courses, self._assignments = courses, assignments or {}
        self._files, self.fail_course = files or {}, fail_course
        self.downloads = []

    def courses(self):
        return self._courses

    def assignments(self, course_id):
        if course_id == self.fail_course:
            raise requests.ConnectionError("mất mạng")
        return self._assignments.get(course_id, [])

    def files(self, course_id):
        return self._files.get(course_id, [])

    def download(self, file_info, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * file_info["size"])
        self.downloads.append(file_info["id"])
        return dest


COURSES = [{"id": 101, "name": "Giải tích 2", "code": "MAT1100"}, {"id": 102, "name": "Vật lý 1", "code": "PHY1100"}]


def assignment(name, due):
    return {"name": name, "due_at": due, "html_url": "https://lms.example.test/a"}


def test_m1_06_loc_cua_so_ngay_va_sap_xep():
    client = FakeClient(
        COURSES,
        {
            101: [
                assignment("Xa", "2026-12-30T10:00:00Z"),  # ngoài 14 ngày
                assignment("Sau", "2026-11-05T10:00:00Z"),
                assignment("Qua khu", "2026-10-01T10:00:00Z"),  # đã qua
            ],
            102: [assignment("Sớm", "2026-10-30T10:00:00Z")],
        },
    )
    snap = canvas.portal_snapshot(client, days=14, now=NOW)
    assert [a["name"] for a in snap["assignments"]] == ["Sớm", "Sau"]
    assert snap["assignments"][0]["course"] == "Vật lý 1"


def test_m1_07_bai_tap_khong_co_han_bi_bo():
    client = FakeClient(COURSES, {101: [{"name": "Không hạn", "due_at": None}]})
    assert canvas.portal_snapshot(client, now=NOW)["assignments"] == []


def test_m1_08_mot_mon_loi_khong_dung_ca_lan_chay():
    client = FakeClient(COURSES, {102: [assignment("Vẫn có", "2026-10-30T10:00:00Z")]}, fail_course=101)
    snap = canvas.portal_snapshot(client, now=NOW)
    assert [a["name"] for a in snap["assignments"]] == ["Vẫn có"]
    assert len(snap["errors"]) == 1
    assert "Giải tích 2" in snap["errors"][0]


def test_m1_09_snapshot_dung_hop_dong():
    client = FakeClient(COURSES, {101: [assignment("BT", "2026-11-02T16:59:00Z")]})
    contracts.validate_portal(canvas.portal_snapshot(client, now=NOW))


def file_info(fid, name, size=10):
    return {"id": fid, "display_name": name, "size": size, "url": f"https://lms.example.test/f/{fid}"}


def test_m1_10_chi_tai_pdf_txt_md_nho(tmp_path):
    client = FakeClient(
        COURSES,
        files={
            101: [
                file_info(1, "Chương 1.pdf"),
                file_info(2, "Ghi chú.TXT"),
                file_info(3, "Slide.pptx"),
                file_info(4, "Hình.png"),
                file_info(5, "Khổng lồ.pdf", size=30 * 1024 * 1024),
                file_info(6, "readme.md"),
            ]
        },
    )
    saved = canvas.download_materials(client, COURSES[0], tmp_path)
    assert sorted(client.downloads) == [1, 2, 6]
    assert all(p.exists() and p.parent.parent == tmp_path for p in saved)


def test_m1_10b_gioi_han_so_file(tmp_path):
    client = FakeClient(COURSES, files={101: [file_info(i, f"f{i}.pdf") for i in range(1, 9)]})
    assert len(canvas.download_materials(client, COURSES[0], tmp_path, max_files=3)) == 3


def test_m1_10c_muc_files_bi_khoa_khong_gay_loi(tmp_path):
    class Locked(FakeClient):
        def files(self, course_id):
            raise requests.HTTPError("HTTP 403")

    assert canvas.download_materials(Locked(COURSES), COURSES[0], tmp_path) == []


def test_m1_11_khong_tai_lai_file_da_co(tmp_path):
    client = FakeClient(COURSES, files={101: [file_info(1, "Chương 1.pdf", size=10)]})
    canvas.download_materials(client, COURSES[0], tmp_path)
    canvas.download_materials(client, COURSES[0], tmp_path)
    assert client.downloads == [1]


def test_m1_12_slugify():
    assert canvas.slugify("Giải tích 2!") == "giải-tích-2"
    assert canvas.slugify("a  b__c") == "a-b-c"
    assert canvas.slugify("***") == "mon-hoc"
    assert len(canvas.slugify("x" * 200)) <= 60
