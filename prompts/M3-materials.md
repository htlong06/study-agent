# M3 · Tài liệu: trích chữ và chia đoạn

Bạn là kỹ sư Python. Hãy đọc `CONVENTIONS.md` và `docs/contracts.md` (mục C2, C3) rồi làm đúng module này, không sửa file nào khác ngoài `src/materials.py` và `tests/test_materials.py`.

## Mục tiêu

Biến các file bài giảng đã tải về (`data/materials/<course_id>-<slug>/...`) thành các `Document` (hợp đồng C3) để Study Agent đưa vào LLM. Không gọi mạng, không gọi LLM.

## Hàm công khai cần có

```python
def extract_text(path: Path) -> tuple[str, list[str]]:
    """Đọc .pdf, .txt, .md. Trả (văn bản, danh sách cảnh báo)."""

def chunk_text(text: str, min_chars: int = 800, max_chars: int = 3000) -> list[str]:
    """Chia theo đoạn văn rồi gộp cho mỗi chunk dài min..max ký tự."""

def load_documents(course_id: int, folder: Path, root: Path) -> list[dict]:
    """Mỗi file trong folder -> một Document theo C3. `file` là đường dẫn tương đối so với `root`."""

def write_documents(course_id: int, documents: list[dict], out_dir: Path) -> Path:
    """Ghi out/documents/<course_id>.json (UTF-8, indent=2)."""
```

## Yêu cầu

1. PDF dùng `pypdf`. Trang không có chữ thì bỏ qua; nếu toàn bộ file không có chữ, trả văn bản rỗng kèm cảnh báo "PDF là ảnh quét, cần OCR" (không tự OCR).
2. `.txt` và `.md` đọc UTF-8; nếu lỗi mã hóa, thử `utf-8-sig` rồi `cp1258`, vẫn lỗi thì thay ký tự lỗi và ghi cảnh báo.
3. Chuẩn hóa: bỏ ký tự điều khiển, gộp nhiều dòng trống liên tiếp thành một, nối từ bị ngắt dòng bằng dấu gạch nối cuối dòng, giữ nguyên dấu tiếng Việt (Unicode NFC).
4. Chia đoạn theo dòng trống; đoạn dài hơn `max_chars` thì cắt ở cuối câu gần nhất (dấu `.`, `?`, `!`, hoặc xuống dòng), không cắt giữa từ. Gộp đoạn ngắn cho đến khi chunk đạt `min_chars`. Chỉ chunk cuối được ngắn hơn `min_chars`. Không có chunk rỗng.
5. Một file hỏng không làm dừng cả thư mục: bỏ qua file đó, thêm cảnh báo vào Document của nó (hoặc trả Document `chunks: []`).
6. Kết quả sắp theo tên file để chạy lại cho ra thứ tự giống nhau (xác định).

## Tiêu chí hoàn thành

- Mọi `Document` trả về qua `contracts.validate_document`.
- Chạy 2 lần cho cùng đầu vào cho ra cùng đầu ra.
- Đã làm xong các kịch bản `M3-01` đến `M3-10` trong `docs/test-plan.md`, mỗi kịch bản có test.

## Ngoài phạm vi

OCR ảnh, tải file từ Canvas (đã có ở M1), gọi LLM, đọc `.docx` và `.pptx` (ghi vào "Đề xuất thay đổi" nếu bạn thấy cần).

Cuối phiên, dán báo cáo bàn giao theo mục 8 của `CONVENTIONS.md`.
