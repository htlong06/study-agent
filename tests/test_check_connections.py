"""Kiểm thử offline cho tools/check_connections.py: không gọi mạng, không cần khoá."""
import importlib.util
from pathlib import Path

import pytest
import requests

from src.google_auth import REQUIRED_VARS

spec = importlib.util.spec_from_file_location("check_connections", Path(__file__).resolve().parent.parent / "tools" / "check_connections.py")
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

ALL_VARS = ("CANVAS_BASE_URL", "CANVAS_TOKEN", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", *REQUIRED_VARS,
            "GOOGLE_CALENDAR_ID", "DRIVE_FOLDER_NAME")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ALL_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(cc, "load_env", lambda: None)  # không đọc .env thật của máy


def test_nothing_configured_skips_everything_and_says_so(capsys):
    assert cc.main([]) == 0
    out = capsys.readouterr().out
    assert out.count("–") == 6 and "CHƯA KIỂM TRA ĐƯỢC DỊCH VỤ NÀO" in out


def test_required_service_missing_fails(capsys):
    assert cc.main(["--require", "canvas,drive"]) == 1
    out = capsys.readouterr().out
    assert "✗ canvas" in out and "✗ drive" in out and "dịch vụ bắt buộc" in out and "✗ gemini" not in out


def test_unknown_service_name_rejected(capsys):
    assert cc.main(["--require", "facebook"]) == 2


def test_canvas_ok_and_401(monkeypatch):
    monkeypatch.setenv("CANVAS_BASE_URL", "https://lms.example.test")
    monkeypatch.setenv("CANVAS_TOKEN", "TOKEN-BI-MAT-123")

    class Good:
        def __init__(self, base, token): pass
        def courses(self): return [{"id": 1}, {"id": 2}]

    class Unauthorized(Good):
        def courses(self): raise PermissionError("Canvas từ chối token (401): token sai, hết hạn hoặc bị thu hồi")

    monkeypatch.setattr(cc, "CanvasClient", Good)
    assert cc.check_canvas() == (cc.OK, "đọc được 2 môn học (chỉ đọc)")
    monkeypatch.setattr(cc, "CanvasClient", Unauthorized)
    status, detail = cc.check_canvas()
    assert status == cc.FAIL and "401" in detail and "TOKEN-BI-MAT-123" not in detail


def test_errors_never_leak_secrets(monkeypatch, capsys):
    monkeypatch.setenv("CANVAS_BASE_URL", "https://lms.example.test")
    monkeypatch.setenv("CANVAS_TOKEN", "TOKEN-BI-MAT-123")
    monkeypatch.setenv("GEMINI_API_KEY", "KHOA-GEMINI-456")

    class Boom:
        def __init__(self, base, token): pass
        def courses(self): raise requests.ConnectionError("không nối được TOKEN-BI-MAT-123")

    def boom_llm(prompt, system, json_mode):
        raise RuntimeError("lỗi chứa KHOA-GEMINI-456")

    monkeypatch.setattr(cc, "CanvasClient", Boom)
    monkeypatch.setitem(cc.llm.PROVIDERS, "gemini", ("GEMINI_API_KEY", boom_llm))
    assert cc.main([]) == 1
    out = capsys.readouterr().out
    assert "TOKEN-BI-MAT-123" not in out and "KHOA-GEMINI-456" not in out
    assert "ConnectionError" in out and "RuntimeError" in out


def test_llm_provider_checks(monkeypatch):
    assert cc.check_llm("groq") == (cc.SKIP, "thiếu GROQ_API_KEY")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setitem(cc.llm.PROVIDERS, "groq", ("GROQ_API_KEY", lambda p, s, j: "ok"))
    assert cc.check_llm("groq")[0] == cc.OK
    monkeypatch.setitem(cc.llm.PROVIDERS, "groq", ("GROQ_API_KEY", lambda p, s, j: "  "))
    assert cc.check_llm("groq")[0] == cc.FAIL


class FakeEvents:
    def __init__(self, svc, kind, kw): self.svc, self.kind, self.kw = svc, kind, kw
    def execute(self):
        self.svc.calls.append(self.kind)
        if self.kind == "list":
            if self.svc.fail_list:
                raise cc.gcal.CalendarAccessError("Không truy cập được lịch Google.")
            return {"items": []}
        if self.kind == "insert":
            return {"id": "thu1"}
        return {}


class FakeService:
    def __init__(self, fail_list=False): self.calls, self.fail_list = [], fail_list
    def events(self): return self
    def list(self, **kw): return FakeEvents(self, "list", kw)
    def insert(self, **kw): return FakeEvents(self, "insert", kw)
    def delete(self, **kw): return FakeEvents(self, "delete", kw)


def google_env(monkeypatch):
    for name in REQUIRED_VARS:
        monkeypatch.setenv(name, "x")


def test_calendar_write_test_creates_then_deletes(monkeypatch):
    google_env(monkeypatch)
    svc = FakeService()
    monkeypatch.setattr(cc.gcal, "make_service", lambda: svc)
    status, detail = cc.check_calendar(write=True)
    assert status == cc.OK and "đã xóa" in detail
    assert svc.calls == ["list", "insert", "delete"]


def test_calendar_read_only_by_default_and_no_delete_when_nothing_created(monkeypatch):
    google_env(monkeypatch)
    svc = FakeService()
    monkeypatch.setattr(cc.gcal, "make_service", lambda: svc)
    assert cc.check_calendar(write=False)[0] == cc.OK and svc.calls == ["list"]
    svc = FakeService(fail_list=True)
    monkeypatch.setattr(cc.gcal, "make_service", lambda: svc)
    status, detail = cc.check_calendar(write=True)
    assert status == cc.FAIL and "lịch" in detail and svc.calls == ["list"]


def test_drive_roundtrip_with_fake_store(monkeypatch):
    google_env(monkeypatch)

    class Mem(cc.DriveStore):
        def __init__(self): self.data = {}
        def put_json(self, name, obj): self.data[name] = obj
        def get_json(self, name): return self.data.get(name)
        def list_names(self): return sorted(self.data)

    monkeypatch.setattr(cc, "make_store", lambda: Mem())
    status, detail = cc.check_drive()
    assert status == cc.OK and cc.TEST_FILE in detail
