"""Kiểm thử M2: cổng LLM (kịch bản M2-01 đến M2-12). Không gọi mạng, không cần khoá."""
import os

import pytest

from src import llm
from src.llm import LLMError


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.setattr(os, "environ", {})
    return os.environ


def test_m2_01_parse_json_thuan():
    assert llm.parse_json('{"a": 1}') == {"a": 1}
    assert llm.parse_json("[1, 2]") == [1, 2]


def test_m2_02_parse_json_boc_code_fence():
    assert llm.parse_json('```json\n{"a": "tiếng Việt"}\n```') == {"a": "tiếng Việt"}
    assert llm.parse_json('```\n{"a": 1}\n```') == {"a": 1}


def test_m2_03_parse_json_co_chu_thua():
    assert llm.parse_json('Đây là kết quả:\n{"a": [1, {"b": 2}]}\nChúc bạn học tốt!') == {"a": [1, {"b": 2}]}


def test_m2_04_parse_json_khong_co_json():
    with pytest.raises(ValueError):
        llm.parse_json("xin lỗi, tôi không làm được")


def fake_provider(result=None, error=None, log=None, name=""):
    def fn(prompt, system, json_mode):
        if log is not None:
            log.append(name)
        if error:
            raise LLMError(error)
        return result

    return fn


def setup_providers(monkeypatch, clean_env, **providers):
    """providers: tên -> (có khoá?, hàm giả)."""
    keys = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
    clean_env["LLM_ORDER"] = ",".join(providers)
    for name, (has_key, fn) in providers.items():
        monkeypatch.setitem(llm.PROVIDERS, name, (keys[name], fn))
        if has_key:
            clean_env[keys[name]] = f"{name}-KHOA-BI-MAT"


def test_m2_05_dung_nha_cung_cap_dau(monkeypatch, clean_env):
    log = []
    setup_providers(
        monkeypatch,
        clean_env,
        gemini=(True, fake_provider("từ gemini", log=log, name="gemini")),
        groq=(True, fake_provider("từ groq", log=log, name="groq")),
    )
    assert llm.call_llm("xin chào") == "từ gemini"
    assert log == ["gemini"]


def test_m2_06_chuyen_sang_nha_cung_cap_ke_tiep(monkeypatch, clean_env):
    setup_providers(
        monkeypatch,
        clean_env,
        gemini=(True, fake_provider(error="HTTP 429")),
        groq=(True, fake_provider("từ groq")),
    )
    assert llm.call_llm("xin chào") == "từ groq"


def test_m2_07_bo_qua_nha_cung_cap_thieu_khoa(monkeypatch, clean_env):
    log = []
    setup_providers(
        monkeypatch,
        clean_env,
        gemini=(False, fake_provider("không được gọi", log=log, name="gemini")),
        groq=(True, fake_provider("từ groq", log=log, name="groq")),
    )
    assert llm.call_llm("xin chào") == "từ groq"
    assert log == ["groq"]


def test_m2_08_tat_ca_loi_khong_lo_khoa(monkeypatch, clean_env):
    setup_providers(
        monkeypatch,
        clean_env,
        gemini=(True, fake_provider(error="HTTP 500")),
        groq=(False, fake_provider("không được gọi")),
    )
    with pytest.raises(LLMError) as err:
        llm.call_llm("xin chào")
    text = str(err.value)
    assert "gemini: HTTP 500" in text and "groq: chưa có khoá" in text
    assert "KHOA-BI-MAT" not in text


class FakeHttp:
    def __init__(self, statuses):
        self.statuses, self.calls = list(statuses), 0

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls += 1
        status = self.statuses.pop(0)

        class R:
            status_code = status

            @staticmethod
            def json():
                return {"ok": True}

        return R


def test_m2_09_thu_lai_khi_429_roi_thanh_cong(monkeypatch):
    sleeps = []
    http = FakeHttp([429, 200])
    monkeypatch.setattr(llm.requests, "post", http)
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    assert llm._post("https://x", {}, {}) == {"ok": True}
    assert http.calls == 2 and sleeps == [2]


def test_m2_09b_het_luot_thu_lai(monkeypatch):
    sleeps = []
    http = FakeHttp([429, 503, 500])
    monkeypatch.setattr(llm.requests, "post", http)
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    with pytest.raises(LLMError, match="500"):
        llm._post("https://x", {}, {})
    assert http.calls == 3
    assert sleeps == [2, 4]  # không chờ thừa sau lần thử cuối


def test_m2_10_loi_400_khong_thu_lai(monkeypatch):
    http = FakeHttp([400, 200])
    monkeypatch.setattr(llm.requests, "post", http)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    with pytest.raises(LLMError, match="400"):
        llm._post("https://x", {}, {})
    assert http.calls == 1


def test_m2_11_openrouter_thieu_model(clean_env):
    clean_env["OPENROUTER_API_KEY"] = "k"
    clean_env["LLM_ORDER"] = "openrouter"
    with pytest.raises(LLMError, match="OPENROUTER_MODEL"):
        llm.call_llm("xin chào")


def test_m2_12_gemini_phan_hoi_rong(monkeypatch, clean_env):
    clean_env["GEMINI_API_KEY"] = "k"
    monkeypatch.setattr(llm, "_post", lambda *a, **k: {})
    with pytest.raises(LLMError, match="rỗng"):
        llm._gemini("xin chào", None, False)


def test_m2_12b_gemini_doc_dung_noi_dung(monkeypatch, clean_env):
    clean_env["GEMINI_API_KEY"] = "k"
    sent = {}

    def fake_post(url, headers, body, retries=3):
        sent.update(url=url, headers=headers, body=body)
        return {"candidates": [{"content": {"parts": [{"text": "Xin "}, {"text": "chào"}]}}]}

    monkeypatch.setattr(llm, "_post", fake_post)
    assert llm._gemini("câu hỏi", "hệ thống", True) == "Xin chào"
    assert sent["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert sent["body"]["systemInstruction"]["parts"][0]["text"] == "hệ thống"
    assert "k" not in sent["url"].split("?")[-1]  # khoá đi qua header, không nằm trên URL
