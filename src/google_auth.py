"""Xác thực Google dùng chung cho Drive (M5) và Calendar (M6b).

Dùng OAuth của chính người dùng: ba biến môi trường cấu hình một lần theo docs/google-setup.md.
Tài khoản dịch vụ không dùng được vì nó không có dung lượng Drive để ghi vào Drive cá nhân.
"""
from google.oauth2.credentials import Credentials

from src.config import env

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPE_DRIVE = "https://www.googleapis.com/auth/drive.file"
SCOPE_CALENDAR = "https://www.googleapis.com/auth/calendar.events"
REQUIRED_VARS = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")


class GoogleAuthError(RuntimeError):
    """Thiếu cấu hình hoặc xác thực Google thất bại (thông điệp tiếng Việt, không chứa khoá)."""


def missing_vars() -> list[str]:
    """Tên các biến Google còn thiếu (chỉ tên, không bao giờ giá trị)."""
    return [name for name in REQUIRED_VARS if not env(name)]


def has_google_config() -> bool:
    """Đủ cả ba biến Google hay chưa."""
    return not missing_vars()


def get_credentials(scopes: list[str]) -> Credentials:
    """Dựng credentials từ refresh token; access token được làm mới lười khi gọi API lần đầu."""
    missing = missing_vars()
    if missing:
        raise GoogleAuthError(
            "Thiếu biến môi trường Google: " + ", ".join(missing) + ". Xem hướng dẫn trong docs/google-setup.md."
        )
    return Credentials(
        token=None,
        refresh_token=env("GOOGLE_REFRESH_TOKEN"),
        client_id=env("GOOGLE_CLIENT_ID"),
        client_secret=env("GOOGLE_CLIENT_SECRET"),
        token_uri=TOKEN_URI,
        scopes=list(scopes),
    )
