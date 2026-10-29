"""Kiểm thử M0: cấu hình (kịch bản M0-01 đến M0-06)."""
import os

import pytest

from src import config


@pytest.fixture
def clean_env(monkeypatch):
    """Môi trường riêng cho từng test, không làm rò biến sang test khác."""
    monkeypatch.setattr(os, "environ", {})
    return os.environ


def user_vars(environ):
    """Biến do test đặt (pytest tự thêm PYTEST_CURRENT_TEST nên phải loại ra)."""
    return {k: v for k, v in environ.items() if k != "PYTEST_CURRENT_TEST"}


def test_m0_01_load_env_doc_file(tmp_path, clean_env):
    f = tmp_path / ".env"
    f.write_text("CANVAS_TOKEN=abc\nGEMINI_MODEL=gemini-2.5-flash\n", encoding="utf-8")
    config.load_env(f)
    assert clean_env["CANVAS_TOKEN"] == "abc"
    assert clean_env["GEMINI_MODEL"] == "gemini-2.5-flash"


def test_m0_02_bien_co_san_duoc_uu_tien(tmp_path, clean_env):
    clean_env["CANVAS_TOKEN"] = "tu-secrets"
    f = tmp_path / ".env"
    f.write_text("CANVAS_TOKEN=tu-file\n", encoding="utf-8")
    config.load_env(f)
    assert clean_env["CANVAS_TOKEN"] == "tu-secrets"


def test_m0_03_bo_qua_dong_khong_hop_le(tmp_path, clean_env):
    f = tmp_path / ".env"
    f.write_text("# chú thích\n\nkhong co dau bang\nA=1\n", encoding="utf-8")
    config.load_env(f)
    assert user_vars(clean_env) == {"A": "1"}


def test_m0_04_go_dau_nhay(tmp_path, clean_env):
    f = tmp_path / ".env"
    f.write_text("A=\"giá trị kép\"\nB='giá trị đơn'\nC=a=b\n", encoding="utf-8")
    config.load_env(f)
    assert clean_env["A"] == "giá trị kép"
    assert clean_env["B"] == "giá trị đơn"
    assert clean_env["C"] == "a=b"  # chỉ tách ở dấu = đầu tiên


def test_m0_04b_khong_co_file_env_khong_loi(tmp_path, clean_env):
    config.load_env(tmp_path / "khong-ton-tai.env")
    assert user_vars(clean_env) == {}


def test_m0_05_env_tra_mac_dinh_khi_rong(clean_env):
    clean_env["EMPTY"] = ""
    assert config.env("EMPTY", "mặc định") == "mặc định"
    assert config.env("KHONG_CO", "x") == "x"
    assert config.env("KHONG_CO") is None


def test_m0_06_env_int_sai_dinh_dang_tra_mac_dinh(clean_env):
    clean_env["N"] = "không phải số"
    assert config.env_int("N", 8) == 8
    clean_env["N"] = "12"
    assert config.env_int("N", 8) == 12
    assert config.env_int("CHUA_DAT", 5) == 5
