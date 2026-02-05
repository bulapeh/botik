"""Интеграция с Google Sheets через gspread."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import gspread

from errors import ErrorCode, ErrorDetail
from utils import build_student_key


@dataclass
class SheetUpdateResult:
    # Результат попытки записи в Google Sheets
    success: bool
    error: Optional[ErrorDetail] = None


def update_sheet(
    config: dict,
    group: str,
    student_short: str,
    discipline_info: dict,
) -> SheetUpdateResult:
    # Авторизация и открытие таблицы
    sheets_cfg = config["google_sheets"]
    try:
        client = gspread.service_account(filename=sheets_cfg["service_account_json_path"])
        sheet = client.open_by_key(sheets_cfg["spreadsheet_id"])
        worksheet = sheet.worksheet(group)
    except Exception:
        return SheetUpdateResult(
            success=False,
            error=ErrorDetail(
                code=ErrorCode.SHEETS_ERROR,
                message="Не удалось открыть лист группы в Google Sheets.",
            ),
        )

    try:
        header_row = int(sheets_cfg.get("header_row_index", 1))
        fio_header = sheets_cfg.get("fio_column_header", "Фамилия Имя Отчество")
        headers = worksheet.row_values(header_row)
        # Находим колонку ФИО
        fio_col_idx = _find_header_index(headers, fio_header)
        if fio_col_idx is None:
            return SheetUpdateResult(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.SHEETS_ERROR,
                    message="Не удалось найти колонку с ФИО в журнале.",
                ),
            )

        column_header = (
            discipline_info.get("sheet_column_header")
            or discipline_info.get("discipline_short")
            or discipline_info.get("discipline_full")
        )
        # Находим колонку дисциплины
        discipline_col_idx = _find_header_index(headers, column_header)
        if discipline_col_idx is None:
            return SheetUpdateResult(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.SHEETS_ERROR,
                    message="Не удалось найти колонку дисциплины в журнале.",
                ),
            )

        # Ищем строку студента по ключу "Фамилия ИО"
        fio_values = worksheet.col_values(fio_col_idx)
        matched_row = _find_student_row(fio_values, student_short)
        if matched_row is None:
            return SheetUpdateResult(
                success=False,
                error=ErrorDetail(
                    code=ErrorCode.SHEETS_ERROR,
                    message="Не удалось однозначно определить строку студента.",
                ),
            )

        # Записываем значение (TRUE по умолчанию)
        value_to_set = sheets_cfg.get("value_to_set", True)
        worksheet.update_cell(matched_row, discipline_col_idx, value_to_set)
    except Exception:
        return SheetUpdateResult(
            success=False,
            error=ErrorDetail(
                code=ErrorCode.SHEETS_ERROR,
                message="Ошибка при записи в Google Sheets.",
            ),
        )

    return SheetUpdateResult(success=True)


def _find_header_index(headers: list[str], header_name: str) -> Optional[int]:
    # Ищем заголовок в первой строке
    for idx, header in enumerate(headers, start=1):
        if header.strip() == header_name:
            return idx
    return None


def _find_student_row(fio_values: list[str], student_short: str) -> Optional[int]:
    # Находим ровно одно совпадение по сокращённому ключу
    matches: list[int] = []
    for idx, value in enumerate(fio_values, start=1):
        key = build_student_key(value.strip())
        if key and key == student_short:
            matches.append(idx)
    if len(matches) == 1:
        return matches[0]
    return None
