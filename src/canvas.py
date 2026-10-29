"""Portal Agent: chỉ ĐỌC dữ liệu từ UET-LMS (Canvas). Không nộp bài, không sửa gì trên LMS."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

TEXT_EXTS = {".pdf", ".txt", ".md"}


def next_link(link_header):
    """Lấy URL trang kế tiếp từ header Link của Canvas."""
    if not link_header:
        return None
    match = re.search(r'<([^>]+)>\s*;\s*rel="next"', link_header)
    return match.group(1) if match else None


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s_-]+", "-", text)[:60] or "mon-hoc"


class CanvasClient:
    def __init__(self, base_url, token, timeout=30):
        if not token:
            raise ValueError("Thiếu CANVAS_TOKEN")
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"

    def get_all(self, path, params=None):
        url = f"{self.base}/api/v1{path}"
        params = dict(params or {})
        params.setdefault("per_page", 100)
        items = []
        while url:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 401:
                raise PermissionError("Canvas từ chối token (401): token sai, hết hạn hoặc bị thu hồi")
            resp.raise_for_status()
            data = resp.json()
            items.extend(data if isinstance(data, list) else [data])
            url = next_link(resp.headers.get("Link"))
            params = None  # URL trang kế tiếp đã chứa sẵn tham số
        return items

    def courses(self):
        raw = self.get_all("/courses", {"enrollment_state": "active"})
        return [
            {"id": c["id"], "name": c["name"], "code": c.get("course_code", "")}
            for c in raw
            if isinstance(c, dict) and c.get("id") and c.get("name")
        ]

    def assignments(self, course_id):
        return self.get_all(f"/courses/{course_id}/assignments", {"bucket": "upcoming"})

    def files(self, course_id):
        return self.get_all(f"/courses/{course_id}/files", {"sort": "updated_at", "order": "desc"})

    def download(self, file_info, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self.session.get(file_info["url"], stream=True, timeout=self.timeout * 4) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
        return dest


def portal_snapshot(client, days=14, now=None):
    """Môn học đang học và bài tập sắp đến hạn trong `days` ngày tới."""
    now = now or datetime.now(timezone.utc)
    limit = now + timedelta(days=days)
    courses = client.courses()
    assignments, errors = [], []
    for course in courses:
        try:
            for a in client.assignments(course["id"]):
                due = a.get("due_at")
                if not due:
                    continue
                due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
                if now <= due_dt <= limit:
                    assignments.append(
                        {
                            "course_id": course["id"],
                            "course": course["name"],
                            "name": a.get("name", ""),
                            "due_at": due,
                            "url": a.get("html_url", ""),
                        }
                    )
        except (requests.RequestException, PermissionError) as exc:
            errors.append(f"{course['name']}: {exc}")
    assignments.sort(key=lambda a: a["due_at"])
    return {
        "generated_at": now.isoformat(),
        "courses": courses,
        "assignments": assignments,
        "errors": errors,
    }


def download_materials(client, course, dest_root, max_files=15, max_mb=25):
    """Tải file pdf/txt/md mới nhất của môn về data/materials/<id>-<tên-môn>/ (bỏ qua file đã có)."""
    folder = Path(dest_root) / f"{course['id']}-{slugify(course['name'])}"
    saved = []
    try:
        files = client.files(course["id"])
    except (requests.RequestException, PermissionError):
        return saved  # nhiều môn khóa mục Files, bỏ qua
    for f in files:
        name = f.get("display_name") or f.get("filename") or ""
        if Path(name).suffix.lower() not in TEXT_EXTS:
            continue
        if f.get("size", 0) > max_mb * 1024 * 1024 or not f.get("url"):
            continue
        dest = folder / f"{f['id']}-{slugify(Path(name).stem)}{Path(name).suffix.lower()}"
        if dest.exists() and dest.stat().st_size == f.get("size", -1):
            saved.append(dest)
        else:
            try:
                saved.append(client.download(f, dest))
            except requests.RequestException:
                continue
        if len(saved) >= max_files:
            break
    return saved
