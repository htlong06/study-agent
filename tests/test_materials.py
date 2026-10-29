"""Kiểm thử M3 (materials.py). Mã kịch bản M3-01..M3-10 nằm trong tên hàm và docstring."""
import json
import unicodedata

import pytest
from pypdf import PdfWriter

from src.contracts import validate_document
from src.materials import (
    chunk_text, extract_text, load_documents, normalize_text, write_documents,
)

VI = "Tích phân bội và đổi biến trong tọa độ cực. Đây là đoạn văn tiếng Việt có dấu."


def make_text_pdf(path, pages):
    """Tạo PDF tối thiểu, mỗi trang một dòng chữ ASCII (Helvetica)."""
    objs = []
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objs.append("<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    font_id = 3 + 2 * len(pages)
    for i, text in enumerate(pages):
        content_id = 4 + 2 * i
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
                    f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>")
        stream = f"BT /F1 12 Tf 72 700 Td ({text}) Tj ET"
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = b"%PDF-1.4\n"
    offsets = []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(out)


def to_cp1258(text):
    """cp1258 chỉ có sẵn chữ cái gốc (â, ê, ơ...); dấu thanh phải là ký tự tổ hợp rời."""
    tones = {"\u0300", "\u0301", "\u0303", "\u0309", "\u0323"}
    out = []
    for ch in unicodedata.normalize("NFC", text):
        parts = unicodedata.normalize("NFD", ch)
        base = unicodedata.normalize("NFC", "".join(c for c in parts if c not in tones))
        out.append(base + "".join(c for c in parts if c in tones))
    return "".join(out).encode("cp1258")


def long_text(paragraphs=40, sentences=6):
    para = " ".join(f"Câu số {i} nói về tích phân và đạo hàm." for i in range(sentences))
    return "\n\n".join(f"{para} Đoạn {p}." for p in range(paragraphs))


def test_m3_01_read_txt_utf8_vietnamese(tmp_path):
    """M3-01: .txt UTF-8 có tiếng Việt giữ đúng dấu."""
    f = tmp_path / "a.txt"
    f.write_text(VI, encoding="utf-8")
    text, warnings = extract_text(f)
    assert text == VI and warnings == []


def test_m3_01_utf8_bom_is_stripped(tmp_path):
    """M3-01: BOM đầu file không lọt vào văn bản."""
    f = tmp_path / "a.txt"
    f.write_bytes(b"\xef\xbb\xbf" + VI.encode("utf-8"))
    assert extract_text(f)[0] == VI


def test_m3_02_read_markdown(tmp_path):
    """M3-02: .md đọc được, không lỗi."""
    f = tmp_path / "ghi-chu.md"
    f.write_text("# Chương 1\n\nNội dung **đậm**.", encoding="utf-8")
    text, warnings = extract_text(f)
    assert "Chương 1" in text and warnings == []


def test_m3_03_cp1258_with_warning(tmp_path):
    """M3-03: file cp1258 đọc được và có cảnh báo mã hóa."""
    f = tmp_path / "cu.txt"
    f.write_bytes(to_cp1258(VI))
    text, warnings = extract_text(f)
    assert text == VI
    assert any("cp1258" in w for w in warnings)


def test_m3_04_pdf_with_text(tmp_path):
    """M3-04: PDF có chữ, trích đúng nội dung các trang."""
    f = tmp_path / "c.pdf"
    make_text_pdf(f, ["Trang mot Integral", "Trang hai Derivative"])
    text, warnings = extract_text(f)
    assert "Trang mot Integral" in text and "Trang hai Derivative" in text
    assert text.index("Trang mot") < text.index("Trang hai")
    assert warnings == []


def test_m3_05_scanned_pdf_needs_ocr(tmp_path):
    """M3-05: PDF không có chữ (ảnh quét) cho văn bản rỗng và cảnh báo cần OCR."""
    f = tmp_path / "scan.pdf"
    w = PdfWriter()
    w.add_blank_page(612, 792)
    with f.open("wb") as fh:
        w.write(fh)
    text, warnings = extract_text(f)
    assert text == ""
    assert any("OCR" in x for x in warnings)


def test_m3_06_normalize():
    """M3-06: gộp dòng trống, nối từ gạch nối, bỏ ký tự điều khiển, NFD về NFC."""
    nfd = unicodedata.normalize("NFD", "tích phân")
    raw = f"{nfd}\x00\x07\n\n\n\n\nphương trình vi-\nphân bậc hai\r\n\r\ncuối"
    out = normalize_text(raw)
    assert "\n\n\n" not in out
    assert "viphân" in out
    assert "\x00" not in out and "\x07" not in out
    assert unicodedata.is_normalized("NFC", out)
    assert out.startswith("tích phân")


def test_m3_07_chunk_sizes():
    """M3-07: mỗi chunk 800..3000 ký tự, chỉ chunk cuối được ngắn hơn."""
    chunks = chunk_text(long_text())
    assert len(chunks) > 3
    assert all(c.strip() for c in chunks)
    assert all(800 <= len(c) <= 3000 for c in chunks[:-1])
    assert len(chunks[-1]) <= 3000


def test_m3_07_short_text_single_chunk():
    """M3-07: văn bản ngắn cho một chunk; văn bản rỗng không cho chunk nào."""
    assert chunk_text("ngắn thôi") == ["ngắn thôi"]
    assert chunk_text("") == []


@pytest.mark.parametrize("sizes", [[100, 100, 2900], [50, 2990, 40, 2990], [700, 2400, 700]])
def test_m3_07_chunk_bounds_with_awkward_paragraphs(sizes):
    """M3-07: đoạn có độ dài khó (gần min, gần max) vẫn giữ ràng buộc."""
    paras = [("từ " * 2000)[:n].strip() for n in sizes]
    chunks = chunk_text("\n\n".join(paras))
    assert all(800 <= len(c) <= 3000 for c in chunks[:-1])
    assert all(len(c) <= 3000 for c in chunks)
    validate_document({"course_id": 1, "file": "x", "title": "t", "chunks": chunks, "warnings": []})


def test_m3_08_long_paragraph_cut_at_sentence_end():
    """M3-08: đoạn đơn dài hơn 3000 ký tự cắt ở cuối câu, không cắt giữa từ."""
    sentence = "Đạo hàm riêng mô tả tốc độ thay đổi theo một biến."
    para = " ".join([sentence] * 120)  # một đoạn, không có dòng trống
    assert len(para) > 3000
    chunks = chunk_text(para)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 3000
        assert c.endswith(".")  # kết thúc ở cuối câu
        assert all(w in sentence.split() for w in c.split())  # không có từ bị cắt dở


def test_m3_08_no_whitespace_text_hard_cut():
    """M3-08: chuỗi quá dài không có khoảng trắng vẫn không vượt max_chars."""
    chunks = chunk_text("a" * 7000)
    assert all(len(c) <= 3000 for c in chunks)
    assert "".join(chunks) == "a" * 7000


def make_course(tmp_path):
    root = tmp_path / "materials"
    folder = root / "101-giai-tich-2"
    folder.mkdir(parents=True)
    (folder / "555-chuong-3.txt").write_text(long_text(10), encoding="utf-8")
    (folder / "100-bai-tap.md").write_text("Bài tập 1\n\nGiải tích.", encoding="utf-8")
    make_text_pdf(folder / "200-slide.pdf", ["Slide one text"])
    return root, folder


def test_m3_09_broken_file_does_not_stop_folder(tmp_path):
    """M3-09: file hỏng có cảnh báo hoặc chunks rỗng, các file khác vẫn xử lý."""
    root, folder = make_course(tmp_path)
    (folder / "300-hong.pdf").write_bytes(b"day khong phai pdf")
    (folder / "400-bai-giang.docx").write_bytes(b"PK\x03\x04")
    docs = {d["file"].split("/")[-1]: d for d in load_documents(101, folder, root)}
    assert docs["300-hong.pdf"]["chunks"] == [] and docs["300-hong.pdf"]["warnings"]
    assert docs["400-bai-giang.docx"]["chunks"] == [] and docs["400-bai-giang.docx"]["warnings"]
    assert docs["555-chuong-3.txt"]["chunks"]
    assert docs["200-slide.pdf"]["chunks"]


def test_m3_10_deterministic_sorted_and_valid(tmp_path):
    """M3-10: chạy hai lần cho kết quả giống hệt, sắp theo tên, qua validate_document."""
    root, folder = make_course(tmp_path)
    first = load_documents(101, folder, root)
    second = load_documents(101, folder, root)
    assert first == second
    names = [d["file"] for d in first]
    assert names == sorted(names)
    assert names[0] == "101-giai-tich-2/100-bai-tap.md"
    for d in first:
        validate_document(d)
        assert d["course_id"] == 101
    assert first[-1]["title"] == "chuong 3"


def test_m3_10_write_documents_roundtrip(tmp_path):
    """M3-10: ghi out/documents/<course_id>.json UTF-8, indent=2, kết thúc bằng dòng trống."""
    root, folder = make_course(tmp_path)
    docs = load_documents(101, folder, root)
    path = write_documents(101, docs, tmp_path / "out")
    assert path == tmp_path / "out" / "documents" / "101.json"
    raw = path.read_text(encoding="utf-8")
    assert raw.endswith("}\n]\n") or raw.endswith("]\n")
    assert "Bài tập" in raw  # ensure_ascii=False
    assert json.loads(raw) == docs
    assert write_documents(101, docs, tmp_path / "out").read_text(encoding="utf-8") == raw


def test_m3_10_write_rejects_invalid_document(tmp_path):
    """M3-10: không ghi Document sai hợp đồng C3."""
    with pytest.raises(Exception):
        write_documents(1, [{"course_id": 1}], tmp_path)
