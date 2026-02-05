"""Вспомогательные утилиты и структуры."""

import re
from dataclasses import dataclass
from typing import Optional


# Регулярка для формата "Фамилия ИО".
STUDENT_SHORT_RE = re.compile(r"^[^\s]+ [A-ZА-ЯЁ]{2}$")


# Результат анализа титульной страницы.
@dataclass
class TitleAnalysisResult:
    signature_confidence: float
    zacheno_confidence: float
    flags: list[str]
    debug: dict


def is_valid_student_short(value: str) -> bool:
    # Проверяем формат "Фамилия ИО".
    return bool(STUDENT_SHORT_RE.match(value))


def build_student_key(full_name: str) -> Optional[str]:
    # Конвертируем ФИО в ключ "Фамилия ИО".
    parts = full_name.split()
    if len(parts) < 3:
        return None
    surname = parts[0]
    initials = "".join([parts[1][0], parts[2][0]]).upper()
    return f"{surname} {initials}"


def split_filename(filename: str) -> tuple[str, str]:
    # Делим имя файла на базу и расширение.
    if "." not in filename:
        return filename, ""
    base, ext = filename.rsplit(".", 1)
    return base, ext
