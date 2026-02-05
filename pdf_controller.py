"""Работа с PDF внутри ZIP: проверка страниц и извлечение титула."""

import io
import zipfile
from typing import Optional

from PyPDF2 import PdfReader

from errors import ErrorCode, ErrorDetail


class PdfController:
    def __init__(self, min_pages: int = 2) -> None:
        # Минимальное число страниц (титул + минимум 1)
        self.min_pages = min_pages

    def validate_pdf(self, archive: zipfile.ZipFile, pdf_path: str) -> Optional[ErrorDetail]:
        # Проверяем, что PDF читается и имеет нужное число страниц
        try:
            with archive.open(pdf_path) as handle:
                data = handle.read()
            reader = PdfReader(io.BytesIO(data))
            if len(reader.pages) < self.min_pages:
                return ErrorDetail(
                    code=ErrorCode.INVALID_PDF,
                    message="PDF содержит меньше двух страниц.",
                    path=pdf_path,
                )
        except Exception:
            return ErrorDetail(
                code=ErrorCode.INVALID_PDF,
                message="Не удалось прочитать PDF-файл.",
                path=pdf_path,
            )
        return None

    def extract_title_page(self, archive: zipfile.ZipFile, pdf_path: str) -> Optional[bytes]:
        # Опционально: извлекаем титульную страницу как PNG
        try:
            from pdf2image import convert_from_bytes
        except ImportError:
            return None
        with archive.open(pdf_path) as handle:
            data = handle.read()
        images = convert_from_bytes(data, first_page=1, last_page=1)
        if not images:
            return None
        image = images[0]
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
