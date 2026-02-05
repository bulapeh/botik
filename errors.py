"""Типы ошибок и форматирование сообщений для пользователя."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    # Внутренние коды используются в логах/контексте.
    INVALID_ARCHIVE = "invalid_archive"
    INVALID_STRUCTURE = "invalid_structure"
    INVALID_FILENAME = "invalid_filename"
    INVALID_PDF = "invalid_pdf"
    UNKNOWN_WORKTYPE = "unknown_worktype"
    MULTIPLE_DISCIPLINES = "multiple_disciplines"
    SHEETS_ERROR = "sheets_error"


# Подробность об ошибке: код, текст и путь в ZIP (если есть).
@dataclass(frozen=True)
class ErrorDetail:
    code: ErrorCode
    message: str
    path: Optional[str] = None


# Человекочитаемое сообщение для пользователя.
@dataclass(frozen=True)
class UserMessage:
    text: str


def format_user_report(errors: list[ErrorDetail]) -> UserMessage:
    # Превращаем список ошибок в отчёт без внутренних кодов.
    lines = ["Обнаружены ошибки в архиве:"]
    for error in errors:
        if error.path:
            lines.append(f"• {error.message} (путь: {error.path})")
        else:
            lines.append(f"• {error.message}")
    return UserMessage(text="\n".join(lines))
