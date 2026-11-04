"""Xác thực Google dùng chung cho Drive (M5) và Calendar (M6b).

Dùng OAuth của chính người dùng: ba biến môi trường cấu hình một lần theo docs/google-setup.md.
Tài khoản dịch vụ không dùng được vì nó không có dung lượng Drive để ghi vào Drive cá nhân.
"""
import re

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


# Mã lỗi OAuth của Google không phải bí mật; nêu ra để biết sửa đúng chỗ (chỉ in mã nằm trong danh sách này).
_REFRESH_HINTS = {
    "invalid_client": "Client ID hoặc Client secret không đúng, hoặc secret đã bị đổi hay xóa. "
                      "Cập nhật GOOGLE_CLIENT_ID và GOOGLE_CLIENT_SECRET cho khớp với Google Cloud.",
    "invalid_grant": "Refresh token hết hạn, bị thu hồi, đã dán sai, hoặc được cấp cho một Client ID khác. "
                     "Hãy lấy lại token bằng đúng Client ID đang dùng.",
    "unauthorized_client": "Client không được phép xin các quyền này. Kiểm tra hai scope ở mục Data Access "
                           "và trạng thái In production.",
    "invalid_scope": "Quyền (scope) của token không hợp lệ hoặc chưa được cấp. Lấy lại token với đủ hai scope.",
}


def refresh_error_message(exc: Exception) -> str:
    """Thông điệp tiếng Việt cho lỗi làm mới token, kèm mã lỗi Google và cách sửa; không chứa khoá hay token."""
    code = None
    for arg in getattr(exc, "args", ()):
        if isinstance(arg, dict) and arg.get("error") in _REFRESH_HINTS:
            code = arg["error"]
    if code is None and getattr(exc, "args", None):
        match = re.match(r"([a-z_]+)\b", str(exc.args[0]))
        code = match.group(1) if match and match.group(1) in _REFRESH_HINTS else None
    hint = _REFRESH_HINTS.get(code, "Refresh token hết hạn hoặc bị thu hồi, hãy lấy lại.")
    label = f" (mã lỗi Google: {code})" if code else ""
    return f"Không làm mới được đăng nhập Google{label}. {hint} Xem docs/google-setup.md."
