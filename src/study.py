"""M4: nhờ LLM soạn quiz từ tài liệu bài giảng, rồi kiểm tra bằng mã (C3 vào, C4 ra).

LLM chỉ sinh nội dung. Mọi kiểm tra (cấu trúc, đáp án, trích dẫn nguyên văn) là mã xác định.
"""
import logging
import re
from datetime import datetime, timezone

from src.config import env
from src.contracts import ContractError, validate_quiz
from src.llm import LLMError, call_llm, parse_json

log = logging.getLogger(__name__)

PASS_RATIO = 0.7
MIN_VALID = 3
MIN_QUOTE_CHARS = 10   # trích dẫn quá ngắn thì ai cũng "khớp", không chứng minh được gì
EXTRA_QUESTIONS = 2    # xin dư để còn sau khi loại câu lỗi

SYSTEM_PROMPT = """Bạn là trợ lý soạn câu hỏi trắc nghiệm ôn tập cho sinh viên đại học.

Quy tắc bắt buộc:
1. Chỉ dùng nội dung trong phần TÀI LIỆU người dùng cung cấp. Không thêm kiến thức bên ngoài, không bịa.
2. Mỗi câu hỏi có đúng 4 lựa chọn (options), đúng 1 đáp án. answer_index là vị trí của đáp án đúng, từ 0 đến 3; hãy đặt đáp án đúng ở các vị trí khác nhau.
3. explanation là giải thích ngắn (1 đến 2 câu, tiếng Việt) vì sao đáp án đó đúng.
4. source.file là đúng nhãn tệp (phần sau "Tệp:") chứa nội dung của câu hỏi. source.quote là một đoạn trích NGUYÊN VĂN, đúng từng ký tự, dài ít nhất 10 ký tự, sao chép từ chính tệp đó. Không diễn đạt lại, không sửa dấu hay dấu câu.
5. Câu hỏi viết bằng tiếng Việt, rõ ràng, tự đứng được, không hỏi về tên tệp hay số trang.
6. Chỉ trả về JSON hợp lệ, không thêm văn bản nào khác, đúng định dạng:
{"topic": "chủ đề chung", "questions": [{"question": "...", "options": ["...", "...", "...", "..."], "answer_index": 0, "explanation": "...", "source": {"file": "...", "quote": "..."}}]}"""

# Dữ liệu nhạy cảm có thể lẫn trong văn bản tài liệu: không đưa vào prompt gửi LLM.
_SECRET_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),                 # email
    re.compile(r"\bBearer\s+[\w.~+/=-]{8,}", re.IGNORECASE),     # tiêu đề xác thực
    re.compile(r"\b(?:AIza|GOCSPX-|ya29\.|1//|gsk_|sk-)[\w.-]{8,}"),  # khoá Google, Groq, OpenAI/OpenRouter
]


def _scrub(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[đã ẩn]", text)
    return text


def _norm(text: str) -> str:
    """Gộp khoảng trắng và bỏ phân biệt hoa thường; giống hệt cách contracts.validate_quiz so khớp."""
    return " ".join(text.split()).lower()


def build_prompt(course: dict, chunks: list[dict], n: int) -> tuple[str, str]:
    """Trả (system, prompt). Mỗi chunk kèm nhãn file để LLM trích đúng nguồn."""
    parts = [f'Hãy soạn {n + EXTRA_QUESTIONS} câu hỏi trắc nghiệm ôn tập cho môn "{course["name"]}" '
             "từ các tài liệu dưới đây.\n\nTÀI LIỆU:"]
    for chunk in chunks:
        parts.append(f"\n=== Tệp: {chunk['file']} ===\n{_scrub(chunk['text'])}")
    return SYSTEM_PROMPT, "\n".join(parts)


def _file_rank(file: str) -> tuple[int, str]:
    """Id file Canvas tăng theo thời gian tải lên, nên id lớn hơn nghĩa là mới hơn."""
    match = re.match(r"(\d+)-", file.rsplit("/", 1)[-1])  # chỉ xét tên file, không xét thư mục môn
    return (int(match.group(1)) if match else -1, file)


def pick_chunks(documents: list[dict], max_chars: int = 12000) -> list[dict]:
    """Chọn các chunk đưa vào prompt, ưu tiên tài liệu mới nhất, tổng không quá max_chars."""
    picked, total = [], 0
    for doc in sorted(documents, key=lambda d: _file_rank(d["file"]), reverse=True):
        for text in doc.get("chunks", []):
            if total + len(text) > max_chars:
                continue
            picked.append({"file": doc["file"], "title": doc.get("title", ""), "text": text})
            total += len(text)
    return picked


def _check_question(q, sources: dict[str, str], seen: set[str]) -> tuple[dict | None, str | None]:
    """Trả (câu đã làm sạch, None) nếu hợp lệ, hoặc (None, lý do)."""
    if not isinstance(q, dict):
        return None, "không phải một đối tượng"
    for key in ("question", "options", "answer_index", "explanation", "source"):
        if key not in q:
            return None, f"thiếu trường '{key}'"
    question, explanation = q["question"], q["explanation"]
    if not isinstance(question, str) or not question.strip():
        return None, "câu hỏi rỗng"
    if not isinstance(explanation, str) or not explanation.strip():
        return None, "thiếu giải thích"
    options = q["options"]
    if not isinstance(options, list) or len(options) != 4 \
            or not all(isinstance(o, str) and o.strip() for o in options):
        return None, "options phải đúng 4 chuỗi không rỗng"
    if len({_norm(o) for o in options}) != 4:
        return None, "có hai lựa chọn trùng nhau"
    idx = q["answer_index"]
    if isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx <= 3:
        return None, "answer_index phải là số nguyên từ 0 đến 3"
    src = q["source"]
    if not isinstance(src, dict) or not isinstance(src.get("file"), str) or not isinstance(src.get("quote"), str):
        return None, "source thiếu file hoặc quote"
    if src["file"] not in sources:
        return None, "source.file không có trong tài liệu nguồn"
    quote = _norm(src["quote"])
    if len(quote) < MIN_QUOTE_CHARS:
        return None, "source.quote quá ngắn"
    if quote not in _norm(sources[src["file"]]):
        return None, "source.quote không xuất hiện nguyên văn trong tài liệu"
    key = _norm(question)
    if key in seen:
        return None, "trùng với một câu hỏi đã có"
    seen.add(key)
    return {
        "question": question.strip(),
        "options": [o.strip() for o in options],
        "answer_index": idx,
        "explanation": explanation.strip(),
        "source": {"file": src["file"], "quote": src["quote"].strip()},
    }, None


def validate_questions(raw: list[dict], sources: dict[str, str]) -> tuple[list[dict], list[str]]:
    """Trả (câu hợp lệ đã đánh lại id q1, q2, ..., danh sách lý do loại)."""
    valid, reasons, seen = [], [], set()
    for i, q in enumerate(raw if isinstance(raw, list) else [], start=1):
        clean, reason = _check_question(q, sources, seen)
        if reason:
            reasons.append(f"Câu {i}: {reason}")
            continue
        valid.append({"id": f"q{len(valid) + 1}", **clean})
    return valid, reasons


def _configured_model() -> str:
    """Tên model của nhà cung cấp đầu tiên có khoá. call_llm không báo nhà cung cấp nào đã trả lời."""
    models = {"gemini": ("GEMINI_API_KEY", "GEMINI_MODEL", "gemini-2.5-flash"),
              "groq": ("GROQ_API_KEY", "GROQ_MODEL", "llama-3.3-70b-versatile"),
              "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "openrouter")}
    for name in (n.strip() for n in env("LLM_ORDER", "gemini,groq,openrouter").split(",")):
        if name in models and env(models[name][0]):
            return env(models[name][1], models[name][2])
    return "unknown"


def _ask(llm, system: str, prompt: str) -> dict | None:
    """Gọi LLM một lần; trả JSON đã tách (dạng {"questions": [...]}) hoặc None nếu lỗi hay JSON hỏng."""
    try:
        text = llm(prompt, system=system, json_mode=True)
    except LLMError as exc:
        log.warning("LLM lỗi khi soạn quiz: %s", exc)
        return None
    try:
        data = parse_json(text)
    except (ValueError, TypeError, AttributeError):
        log.warning("LLM trả JSON hỏng khi soạn quiz")
        return None
    if isinstance(data, list):
        data = {"questions": data}
    questions = data.get("questions") if isinstance(data, dict) else None
    return data if isinstance(questions, list) and questions else None


def generate_quiz(course: dict, documents: list[dict], llm=call_llm, n: int = 8, now=None) -> dict | None:
    """Trả quiz theo C4, hoặc None nếu không đủ câu hợp lệ. `llm` truyền vào để test thay bằng giả."""
    chunks = pick_chunks(documents)
    if not chunks:
        log.warning("Môn %s không có đoạn văn nào để soạn quiz", course.get("id"))
        return None
    system, prompt = build_prompt(course, chunks, n)

    data = _ask(llm, system, prompt)
    if data is None:
        data = _ask(llm, system, prompt)  # thử lại đúng một lần
    if data is None:
        return None

    sources = {d["file"]: "\n\n".join(d.get("chunks", [])) for d in documents}
    valid, reasons = validate_questions(data["questions"], sources)
    for reason in reasons:
        log.info("Loại câu hỏi: %s", reason)
    if len(valid) < MIN_VALID:
        log.warning("Môn %s chỉ có %s câu hợp lệ (cần ít nhất %s)", course.get("id"), len(valid), MIN_VALID)
        return None

    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    topic = data.get("topic") if isinstance(data.get("topic"), str) and data["topic"].strip() else course["name"]
    quiz = {
        "course_id": course["id"],
        "course": course["name"],
        "topic": topic.strip(),
        "generated_at": moment.isoformat(),
        "model": _configured_model(),
        "pass_ratio": PASS_RATIO,
        "questions": valid[:n],
    }
    try:
        return validate_quiz(quiz, sources)
    except ContractError as exc:
        log.warning("Quiz không qua kiểm tra hợp đồng: %s", exc)
        return None
