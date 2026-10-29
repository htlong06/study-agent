# M4 · Study Agent: sinh và kiểm quiz

Bạn là kỹ sư Python. Hãy đọc `CONVENTIONS.md`, `docs/contracts.md` (C3, C4) và `src/llm.py`. Chỉ sửa `src/study.py` và `tests/test_study.py`.

## Mục tiêu

Từ các `Document` của một môn, nhờ LLM soạn một bộ quiz trắc nghiệm theo hợp đồng C4, rồi **kiểm tra bằng mã** để chỉ giữ câu hỏi đúng cấu trúc và có trích dẫn thật trong tài liệu. LLM chỉ sinh nội dung; mọi kiểm tra là mã xác định.

## Hàm công khai cần có

```python
def build_prompt(course: dict, chunks: list[dict], n: int) -> tuple[str, str]:
    """Trả (system, prompt). Mỗi chunk kèm nhãn file để LLM trích đúng nguồn."""

def validate_questions(raw: list[dict], sources: dict[str, str]) -> tuple[list[dict], list[str]]:
    """Trả (câu hợp lệ đã đánh lại id q1, q2, ..., danh sách lý do loại)."""

def pick_chunks(documents: list[dict], max_chars: int = 12000) -> list[dict]:
    """Chọn các chunk đưa vào prompt, ưu tiên tài liệu mới nhất, tổng không quá max_chars."""

def generate_quiz(course: dict, documents: list[dict], llm=call_llm, n: int = 8, now=None) -> dict | None:
    """Trả quiz theo C4, hoặc None nếu không đủ câu hợp lệ. `llm` truyền vào để test thay bằng giả."""
```

## Yêu cầu về prompt gửi LLM

1. System prompt (tiếng Việt) nói rõ: chỉ dùng nội dung trong tài liệu được cung cấp; không bịa; mỗi câu có đúng 4 lựa chọn, đúng 1 đáp án; kèm giải thích ngắn; kèm `source.file` và `source.quote` là **đoạn trích nguyên văn** từ tài liệu; trả về **chỉ JSON**.
2. Định dạng JSON mong đợi: `{"topic": str, "questions": [{"question", "options", "answer_index", "explanation", "source": {"file", "quote"}}]}`.
3. Prompt chỉ chứa nội dung bài giảng, **không** chứa token, email, tên người dùng hay dữ liệu cá nhân.
4. Yêu cầu sinh `n + 2` câu để còn dư sau khi loại câu lỗi.

## Yêu cầu về kiểm tra (bằng mã)

Loại câu hỏi (và ghi lý do) nếu: thiếu trường; `options` không đúng 4 chuỗi không rỗng; `answer_index` ngoài 0 đến 3; hai lựa chọn trùng nhau; `source.file` không có trong nguồn; `source.quote` không xuất hiện nguyên văn trong tài liệu (so sánh sau khi gộp khoảng trắng và không phân biệt hoa thường); câu hỏi trùng một câu đã có. Giữ tối đa `n` câu. Nếu còn ít hơn 3 câu hợp lệ thì trả `None`.

## Xử lý lỗi

- LLM trả JSON hỏng: dùng `llm.parse_json`; nếu vẫn lỗi, thử lại **một lần** rồi trả `None`.
- Ngoại lệ `LLMError` được bắt, ghi log cảnh báo, trả `None`. Không làm sập orchestrator.

## Tiêu chí hoàn thành

- Quiz trả về qua `contracts.validate_quiz(quiz, sources)`.
- Test chạy hoàn toàn bằng LLM giả, không cần mạng hay khoá.
- Đã làm xong các kịch bản `M4-01` đến `M4-12` trong `docs/test-plan.md`.

## Ngoài phạm vi

Chấm điểm khi người dùng làm bài (M8), lưu file lên Drive (M5, M7).

Cuối phiên, dán báo cáo bàn giao theo mục 8 của `CONVENTIONS.md`.
