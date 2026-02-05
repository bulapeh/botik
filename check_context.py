"""Контекст одной проверки портфолио (живёт только в RAM)."""

from dataclasses import dataclass, field
from typing import Optional

from errors import ErrorDetail
from utils import TitleAnalysisResult


# Контекст передаётся между модулями вместо прямых импортов/ссылок.
@dataclass
class CheckContext:
    zip_path: str
    # Уровень 1: группа (корень ZIP)
    group: Optional[str] = None
    # Уровень 2: Фамилия ИО (краткая форма)
    student_short: Optional[str] = None
    # Уровень 3: полное название дисциплины
    discipline_full: Optional[str] = None
    # Сокращение дисциплины из справочника
    discipline_short: Optional[str] = None
    # Пути к PDF внутри ZIP
    pdf_paths: list[str] = field(default_factory=list)
    # Ошибки, собранные на разных шагах
    errors: list[ErrorDetail] = field(default_factory=list)
    # Результат анализа титула (если включено)
    title_analysis: Optional[TitleAnalysisResult] = None
    # Справочник типов работ (folder -> параметры)
    worktype_map: dict[str, dict] = field(default_factory=dict)
