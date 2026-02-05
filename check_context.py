from dataclasses import dataclass, field
from typing import Optional

from errors import ErrorDetail
from utils import TitleAnalysisResult


@dataclass
class CheckContext:
    zip_path: str
    group: Optional[str] = None
    student_short: Optional[str] = None
    discipline_full: Optional[str] = None
    discipline_short: Optional[str] = None
    pdf_paths: list[str] = field(default_factory=list)
    errors: list[ErrorDetail] = field(default_factory=list)
    title_analysis: Optional[TitleAnalysisResult] = None
    worktype_map: dict[str, dict] = field(default_factory=dict)
