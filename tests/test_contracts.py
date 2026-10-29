"""Kiểm thử M0: bộ kiểm tra hợp đồng (kịch bản M0-07 đến M0-12)."""
import pytest

from src import contracts
from src.contracts import ContractError
from tests import samples


def test_m0_07_portal_hop_le():
    data = samples.portal()
    assert contracts.validate_portal(data) is data


def test_m0_08_portal_thieu_truong():
    data = samples.portal()
    del data["courses"][0]["code"]
    with pytest.raises(ContractError, match="code"):
        contracts.validate_portal(data)


def test_m0_08b_portal_sai_thu_tu_due_at():
    data = samples.portal()
    data["assignments"].reverse()
    with pytest.raises(ContractError, match="due_at"):
        contracts.validate_portal(data)


def test_m0_08c_portal_thoi_gian_thieu_mui_gio():
    data = samples.portal()
    data["assignments"][0]["due_at"] = "2026-11-02T16:59:00"
    with pytest.raises(ContractError, match="múi giờ"):
        contracts.validate_portal(data)


def test_m0_09_quiz_hop_le():
    assert contracts.validate_quiz(samples.quiz(), samples.sources())


def test_m0_09b_quiz_3_lua_chon():
    q = samples.quiz()
    q["questions"][0]["options"].pop()
    with pytest.raises(ContractError, match="4 chuỗi"):
        contracts.validate_quiz(q)


def test_m0_09c_quiz_answer_index_ngoai_khoang():
    q = samples.quiz()
    q["questions"][0]["answer_index"] = 4
    with pytest.raises(ContractError, match="0 đến 3"):
        contracts.validate_quiz(q)


def test_m0_09d_quiz_id_trung():
    q = samples.quiz()
    q["questions"][1]["id"] = "q1"
    with pytest.raises(ContractError, match="trùng"):
        contracts.validate_quiz(q)


def test_m0_09e_quiz_khong_chap_nhan_bool_lam_so():
    q = samples.quiz()
    q["questions"][0]["answer_index"] = True
    with pytest.raises(ContractError):
        contracts.validate_quiz(q)


def test_m0_10_trich_dan_phai_nguyen_van():
    q = samples.quiz()
    q["questions"][0]["source"]["quote"] = "câu này không có trong tài liệu"
    with pytest.raises(ContractError, match="nguyên văn"):
        contracts.validate_quiz(q, samples.sources())


def test_m0_10b_khac_khoang_trang_va_hoa_thuong_van_chap_nhan():
    q = samples.quiz()
    q["questions"][0]["source"]["quote"] = "PHẦN TỬ  diện tích\ndA bằng r dr dθ"
    assert contracts.validate_quiz(q, samples.sources())


def test_m0_10c_file_nguon_la():
    q = samples.quiz()
    q["questions"][0]["source"]["file"] = "khong-co.pdf"
    with pytest.raises(ContractError, match="không có trong tài liệu nguồn"):
        contracts.validate_quiz(q, samples.sources())


def test_m0_11_plan_hop_le():
    assert contracts.validate_plan(samples.plan())


def test_m0_11b_hai_phien_chong_nhau():
    p = samples.plan()
    p["sessions"].append(samples.session(start="2026-11-01T19:30:00+07:00", end="2026-11-01T20:10:00+07:00"))
    with pytest.raises(ContractError, match="chồng"):
        contracts.validate_plan(p)


def test_m0_11c_phien_60_phut():
    p = samples.plan()
    p["sessions"][0]["end"] = "2026-11-01T20:00:00+07:00"
    with pytest.raises(ContractError, match="25 đến 45"):
        contracts.validate_plan(p)


def test_m0_11d_phien_thieu_calendar_event_id():
    p = samples.plan()
    del p["sessions"][0]["calendar_event_id"]
    with pytest.raises(ContractError, match="calendar_event_id"):
        contracts.validate_plan(p)


def test_m0_12_today_hop_le():
    assert contracts.validate_today(samples.today())


def test_m0_12b_today_phien_ngoai_ngay():
    t = samples.today()
    t["date"] = "2026-11-02"
    with pytest.raises(ContractError, match="không thuộc ngày"):
        contracts.validate_today(t)


def test_m0_12c_today_quiz_co_duong_dan():
    t = samples.today()
    t["quizzes"] = ["out/quiz-101.json"]
    with pytest.raises(ContractError, match="tên file"):
        contracts.validate_today(t)


def test_m0_12d_today_ngay_sai_dinh_dang():
    t = samples.today()
    t["date"] = "01/11/2026"
    with pytest.raises(ContractError, match="YYYY-MM-DD"):
        contracts.validate_today(t)


def test_m0_bo_qua_truong_la():
    data = samples.portal()
    data["truong_moi"] = 123
    assert contracts.validate_portal(data)
