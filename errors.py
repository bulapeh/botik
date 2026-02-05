from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    INVALID_ARCHIVE = "invalid_archive"
    INVALID_STRUCTURE = "invalid_structure"
    INVALID_FILENAME = "invalid_filename"
    INVALID_PDF = "invalid_pdf"
    UNKNOWN_WORKTYPE = "unknown_worktype"
    MULTIPLE_DISCIPLINES = "multiple_disciplines"
    SHEETS_ERROR = "sheets_error"


@dataclass(frozen=True)
class ErrorDetail:
    code: ErrorCode
    message: str
    path: Optional[str] = None


@dataclass(frozen=True)
class UserMessage:
    text: str


def format_user_report(errors: list[ErrorDetail]) -> UserMessage:
    lines = ["Обнаружены ошибки в архиве:"]
    for error in errors:
        if error.path:
            lines.append(f"• {error.message} (путь: {error.path})")
        else:
            lines.append(f"• {error.message}")
    return UserMessage(text="\n".join(lines))
