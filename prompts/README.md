# Prompt giao việc cho từng module

Cách dùng: mở một phiên AI mới, dán nội dung file prompt của module cần làm, và đính kèm `CONVENTIONS.md`, `docs/contracts.md`, cùng các file nguồn trong cột "Cần đọc". Mỗi phiên chỉ làm đúng một module.

| Mã | Module | File được sửa | Cần đọc | Phụ thuộc | Trạng thái | Giai đoạn |
| --- | --- | --- | --- | --- | --- | --- |
| M0 | Nền tảng: cấu hình, hợp đồng, quy ước | `src/config.py`, `src/contracts.py` | `CONVENTIONS.md` | không | Có mã, có test | 0 |
| M1 | Portal Agent: Canvas client | `src/canvas.py` | `docs/contracts.md` C1, C2 | M0 | Có mã, có test | 1 |
| M2 | Cổng LLM: Gemini, Groq, OpenRouter | `src/llm.py` | `src/config.py` | M0 | Có mã, có test | 1 |
| M3 | Tài liệu: trích chữ và chia đoạn | `src/materials.py` | C2, C3 | M0, M1 | Chưa làm | 1 |
| M4 | Study Agent: sinh và kiểm quiz | `src/study.py` | C3, C4, `src/llm.py` | M0, M2, M3 | Chưa làm | 1 |
| M5 | Kho Google Drive và xác thực Google | `src/google_auth.py`, `src/store.py` | C6 | M0 | Chưa làm | 2 |
| M6a | Bộ xếp lịch ôn (hàm thuần) | `src/scheduler.py` | C1, C5 | M0 | Chưa làm | 2 |
| M6b | Google Calendar adapter | `src/gcal.py` | C5, `src/google_auth.py` | M0, M5 | Chưa làm | 2 |
| M7 | Orchestrator và GitHub Actions | `src/orchestrator.py`, `.github/workflows/daily.yml` | tất cả hợp đồng | M1, M3, M4, M5, M6a, M6b | Chưa làm | 2 |
| M8 | Quiz client (trang web một file) | `web/quiz.html`, `web/grade.js` | C4, C6 | M0 | Chưa làm | 2 |
| M9 | Guard trên Android | (chưa chia nhỏ) | C6 | M8 | **Để sau** | 3 |

## Thứ tự và phần có thể làm song song

- Làm ngay, song song được: **M3**, **M5**, **M6a**, **M8** (chỉ cần M0, đã xong).
- Sau M3 và M2: **M4**.
- Sau M5: **M6b**.
- Cuối cùng: **M7** (ghép tất cả), rồi dùng thử 2 tuần trước khi quyết định M9.

## Danh sách file prompt

`M3-materials.md`, `M4-study.md`, `M5-google-store.md`, `M6a-scheduler.md`, `M6b-gcal.md`, `M7-orchestrator.md`, `M8-quiz-client.md`, `M9-guard.md`. Module M0, M1, M2 đã có mã nên chỉ cần bổ sung khi sửa lỗi; yêu cầu của chúng nằm trong `docs/test-plan.md`.
