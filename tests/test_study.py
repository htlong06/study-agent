"""Kiểm thử M4 (study.py). Mã kịch bản M4-01..M4-12 nằm trong tên hàm và docstring. LLM luôn là bản giả."""
import copy
import json
from datetime import datetime, timezone

import pytest

from src import study
from src.contracts import validate_quiz
from src.llm import LLMError
from src.study import build_prompt, generate_quiz, pick_chunks, validate_questions
from tests import samples

FILE = samples.SOURCE_FILE
TEXT = samples.SOURCE_TEXT
COURSE = {"id": 101, "name": "Giải tích 2"}
QUOTES = [
    "Trong tọa độ cực, phần tử diện tích dA bằng r dr dθ.",
    "Tích phân bội hai lớp của hàm liên tục trên miền đóng, bị chặn luôn tồn tại.",
    "Công thức đổi biến giúp đưa tích phân về dạng đơn giản hơn.",
    "phần tử diện tích dA bằng r dr dθ",
    "hàm liên tục trên miền đóng",
    "giúp đưa tích phân về dạng",
]
NOW = datetime(2026, 10, 29, 0, 5, tzinfo=timezone.utc)


def doc(file=FILE, chunks=None):
    return {"course_id": 101, "file": file, "title": "chuong 3", "chunks": chunks if chunks is not None else [TEXT],
            "warnings": []}


def raw_q(i=0, **override):
    q = {"question": f"Câu hỏi số {i}: nội dung nào đúng?",
         "options": [f"Phương án A{i}", f"Phương án B{i}", f"Phương án C{i}", f"Phương án D{i}"],
         "answer_index": i % 4, "explanation": f"Vì tài liệu nói như vậy ({i}).",
         "source": {"file": FILE, "quote": QUOTES[i % len(QUOTES)]}}
    q.update(override)
    return q


def reply(questions, topic="Tích phân bội"):
    return json.dumps({"topic": topic, "questions": questions}, ensure_ascii=False)


class FakeLLM:
    """Trả lần lượt các phản hồi (chuỗi) hoặc ném ngoại lệ nếu phần tử là ngoại lệ."""

    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, prompt, system=None, json_mode=False):
        self.calls.append({"prompt": prompt, "system": system, "json_mode": json_mode})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_m4_01_build_prompt_contents():
    """M4-01: có nhãn file của từng chunk, yêu cầu 4 lựa chọn, chỉ trả JSON, xin n + 2 câu."""
    chunks = [{"file": "101-a/200-moi.pdf", "title": "moi", "text": "Nội dung mới."},
              {"file": "101-a/100-cu.pdf", "title": "cu", "text": "Nội dung cũ."}]
    system, prompt = build_prompt(COURSE, chunks, 8)
    assert "Tệp: 101-a/200-moi.pdf" in prompt and "Tệp: 101-a/100-cu.pdf" in prompt
    assert "Nội dung mới." in prompt and "Nội dung cũ." in prompt
    assert "10 câu hỏi" in prompt and "Giải tích 2" in prompt
    assert "đúng 4 lựa chọn" in system and "JSON" in system and "NGUYÊN VĂN" in system
    assert "chỉ dùng nội dung" in system.lower() and "không bịa" in system.lower()
    assert '"topic"' in system and '"questions"' in system and '"answer_index"' in system  # có mô tả định dạng
    assert build_prompt(COURSE, chunks, 5)[1].count("7 câu hỏi") == 1


def test_m4_02_prompt_excludes_personal_data_and_secrets():
    """M4-02: dữ liệu giả có email và chuỗi giống token không lọt vào prompt."""
    course = {"id": 101, "name": "Giải tích 2", "teacher_email": "thay.giao@vnu.edu.vn", "token": "TOKEN-ABC-123"}
    chunks = [{"file": FILE, "title": "ten.nguoi.dung@gmail.com", "owner": "Nguyễn Văn A", "api_key": "AIzaSyFAKEKEY1234567890",
               "text": "Liên hệ ten.nguoi.dung@gmail.com. Khoá AIzaSyFAKEKEY1234567890 và Bearer abcdef1234567890. "
                       "Refresh 1//0gFAKEREFRESHTOKEN. Secret GOCSPX-FAKEFAKEFAKE12. Tích phân là gì?"}]
    system, prompt = build_prompt(course, chunks, 8)
    blob = system + prompt
    for secret in ("thay.giao@vnu.edu.vn", "TOKEN-ABC-123", "ten.nguoi.dung@gmail.com", "AIzaSyFAKEKEY",
                   "abcdef1234567890", "FAKEREFRESHTOKEN", "GOCSPX-FAKE", "Nguyễn Văn A"):
        assert secret not in blob, secret
    assert "Tích phân là gì?" in prompt  # nội dung bài giảng vẫn còn


def test_m4_03_pick_chunks_budget_and_newest_first():
    """M4-03: pick_chunks vượt giới hạn thì tổng không quá max_chars, ưu tiên tài liệu mới nhất."""
    docs = [doc("101-a/100-cu.pdf", ["c" * 400, "d" * 400]),
            doc("101-a/900-moi.pdf", ["a" * 500, "b" * 500]),
            doc("101-a/500-giua.pdf", ["e" * 300])]
    picked = pick_chunks(docs, max_chars=1300)
    assert sum(len(c["text"]) for c in picked) <= 1300
    assert [c["file"] for c in picked][:2] == ["101-a/900-moi.pdf", "101-a/900-moi.pdf"]
    assert "101-a/100-cu.pdf" not in [c["file"] for c in picked] or len(picked) > 2
    assert all(set(c) >= {"file", "title", "text"} for c in picked)
    assert pick_chunks(docs, max_chars=0) == []


def test_m4_03_default_limit_and_file_without_id():  # thư mục môn cũng bắt đầu bằng số (id môn), không được tính nhầm
    """M4-03: giới hạn mặc định 12000; tên file không có id xếp sau các file có id."""
    docs = [doc("101-a/khong-id.pdf", ["x" * 5000]), doc("101-a/7-co-id.pdf", ["y" * 5000, "z" * 5000])]
    picked = pick_chunks(docs)
    assert sum(len(c["text"]) for c in picked) <= 12000
    assert picked[0]["file"] == "101-a/7-co-id.pdf"


def test_m4_04_generate_quiz_happy_path():
    """M4-04: LLM giả trả đủ câu hợp lệ thì quiz qua validate_quiz, tối đa n câu, id q1, q2, ..."""
    llm = FakeLLM(reply([raw_q(i) for i in range(10)]))
    quiz = generate_quiz(COURSE, [doc()], llm=llm, n=8, now=NOW)
    assert validate_quiz(quiz, {FILE: TEXT}) is quiz
    assert [q["id"] for q in quiz["questions"]] == [f"q{i}" for i in range(1, 9)]
    assert quiz["course_id"] == 101 and quiz["course"] == "Giải tích 2" and quiz["topic"] == "Tích phân bội"
    assert quiz["pass_ratio"] == 0.7 and quiz["generated_at"] == NOW.isoformat()
    assert len(llm.calls) == 1 and llm.calls[0]["json_mode"] is True
    assert "10 câu hỏi" in llm.calls[0]["prompt"]


def test_m4_04_accepts_fenced_json_and_bare_list_and_default_topic():
    """M4-04: chấp nhận JSON bọc trong ```json, danh sách trần, và dùng tên môn khi thiếu topic."""
    fenced = "```json\n" + reply([raw_q(i) for i in range(4)]) + "\n```"
    quiz = generate_quiz(COURSE, [doc()], llm=FakeLLM(fenced), now=NOW)
    assert len(quiz["questions"]) == 4
    bare = json.dumps([raw_q(i) for i in range(4)], ensure_ascii=False)
    quiz = generate_quiz(COURSE, [doc()], llm=FakeLLM(bare), now=NOW)
    assert quiz["topic"] == "Giải tích 2"


def test_m4_04_naive_now_gets_utc():
    """M4-04: now không có múi giờ được coi là UTC để quiz luôn có múi giờ."""
    quiz = generate_quiz(COURSE, [doc()], llm=FakeLLM(reply([raw_q(i) for i in range(4)])), now=datetime(2026, 10, 29, 0, 5))
    assert quiz["generated_at"].endswith("+00:00")


@pytest.mark.parametrize("override", [
    {"options": ["A1", "B1", "C1"]},
    {"options": ["A1", "B1", "C1", "D1", "E1"]},
    {"options": ["A1", "B1", "C1", "  "]},
    {"options": ["A1", "B1", "C1", 4]},
    {"options": "A1 B1 C1 D1"},
])
def test_m4_05_bad_options_dropped_with_reason(override):
    """M4-05: số lựa chọn khác 4 hoặc lựa chọn rỗng thì bị loại, có lý do."""
    valid, reasons = validate_questions([raw_q(0, **override), raw_q(1)], {FILE: TEXT})
    assert [q["id"] for q in valid] == ["q1"] and valid[0]["question"].startswith("Câu hỏi số 1")
    assert len(reasons) == 1 and "options" in reasons[0] and reasons[0].startswith("Câu 1")


@pytest.mark.parametrize("bad", [4, -1, "2", 2.0, None, True, [1]])
def test_m4_06_bad_answer_index_dropped(bad):
    """M4-06: answer_index ngoài 0 đến 3 hoặc không phải số nguyên thì bị loại."""
    valid, reasons = validate_questions([raw_q(0, answer_index=bad)], {FILE: TEXT})
    assert valid == [] and "answer_index" in reasons[0]


def test_m4_07_duplicate_options_dropped():
    """M4-07: hai lựa chọn trùng nhau (kể cả khác hoa thường hay khoảng trắng) thì bị loại."""
    for opts in (["A", "B", "C", "A"], ["Hằng  số", "hằng số", "C", "D"]):
        valid, reasons = validate_questions([raw_q(0, options=opts)], {FILE: TEXT})
        assert valid == [] and "trùng" in reasons[0]


def test_m4_08_quote_must_be_verbatim_but_tolerates_whitespace_and_case():
    """M4-08: quote không có nguyên văn thì bị loại; chỉ khác khoảng trắng hoặc hoa thường thì giữ."""
    src = lambda quote: {"file": FILE, "quote": quote}
    wrong = raw_q(0, source=src("Trong tọa độ cực, diện tích bằng r dr dθ thôi mà."))
    spaced = raw_q(1, source=src("Trong   tọa độ cực,\nphần tử  diện tích dA  bằng r dr dθ."))
    upper = raw_q(2, source=src("CÔNG THỨC ĐỔI BIẾN GIÚP ĐƯA TÍCH PHÂN VỀ DẠNG ĐƠN GIẢN HƠN."))
    valid, reasons = validate_questions([wrong, spaced, upper], {FILE: TEXT})
    assert [q["question"][:10] for q in valid] == ["Câu hỏi số", "Câu hỏi số"] and len(valid) == 2
    assert len(reasons) == 1 and "nguyên văn" in reasons[0] and reasons[0].startswith("Câu 1")


def test_m4_08_short_or_empty_quote_dropped():
    """M4-08: quote quá ngắn hoặc rỗng bị loại, vì mọi văn bản đều chứa các đoạn ngắn."""
    for quote in ("", "dA", "tích phân"):
        valid, reasons = validate_questions([raw_q(0, source={"file": FILE, "quote": quote})], {FILE: TEXT})
        assert valid == [] and "quote" in reasons[0]


def test_m4_09_unknown_source_file_dropped():
    """M4-09: source.file không có trong nguồn thì bị loại; thiếu source cũng bị loại."""
    valid, reasons = validate_questions([raw_q(0, source={"file": "khac/999-khong-co.pdf", "quote": QUOTES[0]})], {FILE: TEXT})
    assert valid == [] and "source.file" in reasons[0]
    valid, reasons = validate_questions([{k: v for k, v in raw_q(0).items() if k != "source"}, "không phải dict", None], {FILE: TEXT})
    assert valid == [] and len(reasons) == 3 and "thiếu trường 'source'" in reasons[0]


def test_m4_10_duplicate_question_keeps_one():
    """M4-10: hai câu hỏi giống hệt nhau (kể cả khác hoa thường hay khoảng trắng) chỉ giữ một, id vẫn liên tục."""
    a = raw_q(0)
    b = raw_q(1, question="  " + a["question"].upper() + " ")
    c = raw_q(2)
    valid, reasons = validate_questions([a, b, c], {FILE: TEXT})
    assert [q["id"] for q in valid] == ["q1", "q2"] and len(reasons) == 1 and "trùng" in reasons[0]


def test_m4_11_fewer_than_three_valid_returns_none():
    """M4-11: còn ít hơn 3 câu hợp lệ thì generate_quiz trả None; đúng 3 thì được."""
    bad = raw_q(5, answer_index=9)
    assert generate_quiz(COURSE, [doc()], llm=FakeLLM(reply([raw_q(0), raw_q(1), bad])), now=NOW) is None
    assert generate_quiz(COURSE, [doc()], llm=FakeLLM(reply([raw_q(0), raw_q(1), raw_q(2), bad])), now=NOW) is not None


def test_m4_11_no_documents_or_chunks_returns_none_without_calling_llm():
    """M4-11: không có chunk nào thì không gọi LLM và trả None."""
    llm = FakeLLM()
    assert generate_quiz(COURSE, [], llm=llm, now=NOW) is None
    assert generate_quiz(COURSE, [doc(chunks=[])], llm=llm, now=NOW) is None
    assert llm.calls == []


def test_m4_12_llm_error_retried_once_then_none(caplog):
    """M4-12: LLMError thì thử lại đúng một lần rồi trả None, không ném ngoại lệ."""
    llm = FakeLLM(LLMError("hết hạn mức"), LLMError("hết hạn mức"))
    caplog.set_level("WARNING")
    assert generate_quiz(COURSE, [doc()], llm=llm, now=NOW) is None
    assert len(llm.calls) == 2 and "LLM lỗi" in caplog.text


def test_m4_12_broken_json_retried_once_then_none():
    """M4-12: JSON hỏng thì thử lại đúng một lần rồi trả None."""
    llm = FakeLLM("đây không phải JSON", "{ \"questions\": [ {")
    assert generate_quiz(COURSE, [doc()], llm=llm, now=NOW) is None
    assert len(llm.calls) == 2


def test_m4_12_recovers_on_retry():
    """M4-12: lần đầu lỗi, lần hai đúng thì có quiz."""
    llm = FakeLLM(LLMError("tạm thời"), reply([raw_q(i) for i in range(4)]))
    quiz = generate_quiz(COURSE, [doc()], llm=llm, now=NOW)
    assert quiz is not None and len(llm.calls) == 2


@pytest.mark.parametrize("weird", ['{"questions": "không phải danh sách"}', "[]", '"chuỗi"', "null", '{"topic": "x"}'])
def test_m4_12_wrong_shape_treated_as_broken(weird):
    """M4-12: JSON hợp lệ nhưng sai hình dạng (không có danh sách questions, hoặc rỗng) được xử lý như JSON hỏng."""
    llm = FakeLLM(weird, weird)
    assert generate_quiz(COURSE, [doc()], llm=llm, now=NOW) is None
    assert len(llm.calls) == 2


def test_m4_non_string_llm_reply_does_not_crash():
    """M4-12: phản hồi không phải chuỗi không làm sập."""
    assert generate_quiz(COURSE, [doc()], llm=FakeLLM(None, 123), now=NOW) is None


def test_m4_output_agrees_with_contract_validator():
    """M4-04: mọi câu study.validate_questions giữ đều qua contracts.validate_quiz với cùng nguồn."""
    raws = [raw_q(i) for i in range(6)] + [raw_q(0, source={"file": FILE, "quote": "không có trong tài liệu đâu nhé"})]
    valid, _ = validate_questions(raws, {FILE: TEXT})
    quiz = {"course_id": 101, "course": "x", "topic": "y", "generated_at": NOW.isoformat(), "model": "m",
            "pass_ratio": 0.7, "questions": valid}
    validate_quiz(quiz, {FILE: TEXT})


def test_m4_does_not_mutate_inputs():
    """M4-04: tài liệu và danh sách thô đầu vào không bị sửa."""
    docs, raws = [doc()], [raw_q(i) for i in range(4)]
    snap = (copy.deepcopy(docs), copy.deepcopy(raws))
    generate_quiz(COURSE, docs, llm=FakeLLM(reply(raws)), now=NOW)
    validate_questions(raws, {FILE: TEXT})
    assert (docs, raws) == snap


def test_m4_model_name_follows_configured_provider(monkeypatch):
    """M4-04: trường model ghi nhà cung cấp đầu tiên có khoá."""
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert study._configured_model() == "unknown"
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert study._configured_model() == "llama-3.3-70b-versatile"
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    assert study._configured_model() == "gemini-test"


@pytest.mark.live
def test_m4_live_gemini_generates_valid_quiz():
    """Chạy tay: python -m pytest -m live tests/test_study.py (cần GEMINI_API_KEY trong .env). Gọi LLM thật một lần."""
    from src.config import load_env
    load_env()
    if not study.env("GEMINI_API_KEY"):
        pytest.skip("chưa có GEMINI_API_KEY")
    text = "\n\n".join([
        "Đạo hàm của hàm số tại một điểm là giới hạn của tỉ số giữa số gia của hàm và số gia của đối số khi số gia đối số tiến tới không.",
        "Tích phân xác định của hàm liên tục trên đoạn đóng bằng hiệu giá trị nguyên hàm tại hai đầu mút, theo công thức Newton-Leibniz.",
        "Một hàm khả vi tại một điểm thì liên tục tại điểm đó, nhưng điều ngược lại nói chung không đúng.",
        "Chuỗi hình học với công bội có giá trị tuyệt đối nhỏ hơn một thì hội tụ và có tổng bằng số hạng đầu chia cho một trừ công bội.",
    ])
    docs = [doc("101-giai-tich/1-bai-giang.txt", [text])]
    quiz = generate_quiz(COURSE, docs, n=4)
    assert quiz is not None
    validate_quiz(quiz, {"101-giai-tich/1-bai-giang.txt": text})
