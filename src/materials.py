"""M3: biến file bài giảng (.pdf, .txt, .md) thành Document theo hợp đồng C3.

Không gọi mạng, không gọi LLM. Kết quả xác định: cùng đầu vào cho cùng đầu ra.
"""
import json
import logging
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from src.contracts import validate_document

log = logging.getLogger(__name__)

TEXT_SUFFIXES = {".txt", ".md"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | {".pdf"}
WARN_OCR = "PDF là ảnh quét, cần OCR"
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_SENTENCE_END = re.compile(r"[.?!](?=\s)|\n")


def _decode(raw: bytes) -> tuple[str, list[str]]:
    """Giải mã văn bản; thử UTF-8 (cả BOM), rồi cp1258, cuối cùng thay ký tự lỗi."""
    try:
        return raw.decode("utf-8-sig"), []
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp1258"), ["Mã hóa không phải UTF-8, đã đọc bằng cp1258"]
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace"), ["Mã hóa lạ, một số ký tự bị thay bằng dấu thay thế"]


def _read_pdf(path: Path) -> tuple[str, list[str]]:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except (PyPdfError, NotImplementedError):
            return "", ["PDF bị khóa bằng mật khẩu, không đọc được"]
    pages = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except (PyPdfError, ValueError, KeyError, TypeError) as exc:
            log.warning("Bỏ qua một trang lỗi trong %s: %s", path.name, type(exc).__name__)
            continue
        if text.strip():
            pages.append(text)
    if not pages:
        return "", [WARN_OCR]
    return "\n\n".join(pages), []


def extract_text(path: Path) -> tuple[str, list[str]]:
    """Đọc .pdf, .txt, .md; trả (văn bản đã chuẩn hóa, danh sách cảnh báo)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text, warnings = _read_pdf(path)
    elif suffix in TEXT_SUFFIXES:
        text, warnings = _decode(path.read_bytes())
    else:
        return "", [f"Định dạng {suffix or '(không đuôi)'} chưa được hỗ trợ"]
    return normalize_text(text), warnings


def normalize_text(text: str) -> str:
    """Chuẩn hóa: NFC, bỏ ký tự điều khiển, nối từ gạch nối cuối dòng, gộp dòng trống."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = _CONTROL.sub("", text)
    text = re.sub(r"[  ]+\n", "\n", text)
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _cut_point(text: str, limit: int, floor: float = 0.0) -> int:
    """Vị trí cắt trong text[:limit]: cuối câu gần nhất (không sớm hơn `floor`), không thì khoảng trắng."""
    window = text[:limit]
    ends = [m.end() for m in _SENTENCE_END.finditer(window)]
    if ends and ends[-1] >= max(limit * 0.3, floor):
        return ends[-1]
    space = max(window.rfind(" "), window.rfind("\n"))
    return space + 1 if space > 0 else limit


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    """Cắt đoạn dài hơn max_chars thành các mảnh không dài hơn max_chars."""
    pieces = []
    rest = paragraph
    while len(rest) > max_chars:
        cut = _cut_point(rest, max_chars)
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        pieces.append(rest)
    return [p for p in pieces if p]


def chunk_text(text: str, min_chars: int = 800, max_chars: int = 3000) -> list[str]:
    """Chia theo đoạn văn rồi gộp cho mỗi chunk dài min..max ký tự (chỉ chunk cuối được ngắn hơn)."""
    units = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if paragraph:
            units.extend(_split_long(paragraph, max_chars))

    sep = "\n\n"
    chunks: list[str] = []
    cur = ""
    for unit in units:
        while unit:
            if not cur:
                cur, unit = unit, ""
            elif len(cur) + len(sep) + len(unit) <= max_chars:
                cur, unit = cur + sep + unit, ""
            elif len(cur) >= min_chars:
                chunks.append(cur)
                cur = ""
            else:
                # cur còn ngắn mà unit không vừa: lấy phần đầu unit cho đủ min rồi đóng chunk
                room = max_chars - len(cur) - len(sep)
                cut = _cut_point(unit, room, floor=min_chars - len(cur) - len(sep))
                cur = cur + sep + unit[:cut].strip()
                unit = unit[cut:].strip()
                chunks.append(cur)
                cur = ""
    if cur:
        chunks.append(cur)
    return chunks


def _title(path: Path) -> str:
    stem = re.sub(r"^\d+-", "", path.stem) or path.stem
    return re.sub(r"[-_]+", " ", stem).strip()


def load_documents(course_id: int, folder: Path, root: Path) -> list[dict]:
    """Mỗi file trong folder thành một Document (C3); `file` là đường dẫn tương đối so với root."""
    folder, root = Path(folder), Path(root)
    files = [p for p in folder.rglob("*") if p.is_file() and not p.name.startswith(".")]
    documents = []
    for path in sorted(files, key=lambda p: p.relative_to(root).as_posix() if p.is_relative_to(root) else p.as_posix()):
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        try:
            text, warnings = extract_text(path)
        except (PyPdfError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            log.warning("Không đọc được %s: %s", rel, type(exc).__name__)
            text, warnings = "", [f"Không đọc được file ({type(exc).__name__})"]
        if not text and not warnings:
            warnings = ["File không có nội dung văn bản"]
        document = {
            "course_id": course_id,
            "file": rel,
            "title": _title(path),
            "chunks": chunk_text(text) if text else [],
            "warnings": warnings,
        }
        documents.append(validate_document(document))
    return documents


def write_documents(course_id: int, documents: list[dict], out_dir: Path) -> Path:
    """Ghi out/documents/<course_id>.json (UTF-8, indent=2, kết thúc bằng dòng trống)."""
    for document in documents:
        validate_document(document)
    target = Path(out_dir) / "documents" / f"{course_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(documents, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
