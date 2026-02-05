"""Проверка структуры ZIP и правил именования PDF без полной распаковки."""

import re
import zipfile
from typing import Any, Dict

from check_context import CheckContext
from errors import ErrorCode, ErrorDetail
from utils import is_valid_student_short, split_filename

# PDF должен содержать ровно 4 блока, разделённых "_".
PDF_NAME_RE = re.compile(r"^[^_]+_[^_]+_[^_]+_[^_]+$")
# Формат кода работы: буквы + опциональный номер.
WORKCODE_RE = re.compile(r"^([A-ZА-ЯЁ]{2,3})(\d+)?$")


class StructureValidator:
    def __init__(self, config: Dict[str, Any]) -> None:
        # Сохраняем справочники для проверки
        self.config = config
        self.disciplines = config["disciplines"]
        self.worktypes = config["worktypes"]
        self.worktype_map = self._build_worktype_map()
        self.discipline_full_map = {d["discipline_full"]: d for d in self.disciplines}

    def _build_worktype_map(self) -> dict[str, dict]:
        # Готовим быстрый доступ по названию папки типа работ
        mapping: dict[str, dict] = {}
        for item in self.worktypes:
            if "alias_of" in item:
                mapping[item["folder"]] = {"alias_of": item["alias_of"]}
            else:
                mapping[item["folder"]] = item
        return mapping

    def validate(self, zip_path: str) -> CheckContext:
        # Основная точка входа для проверки ZIP
        context = CheckContext(zip_path=zip_path)
        context.worktype_map = self.worktype_map
        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                self._validate_entries(archive, context)
        except zipfile.BadZipFile:
            context.errors.append(
                ErrorDetail(
                    code=ErrorCode.INVALID_ARCHIVE,
                    message="Файл не является корректным ZIP-архивом.",
                )
            )
        return context

    def _validate_entries(self, archive: zipfile.ZipFile, context: CheckContext) -> None:
        # Собираем ключевые параметры из всех элементов архива
        root_group = None
        student = None
        discipline = None
        pdf_paths: list[str] = []

        for info in archive.infolist():
            name = info.filename
            # Запрещаем служебные файлы/папки
            if "__MACOSX" in name or name.lower().endswith("thumbs.db"):
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_STRUCTURE,
                        message="Архив содержит запрещённые служебные файлы или папки.",
                        path=name,
                    )
                )
                continue
            parts = [p for p in name.split("/") if p]
            if not parts:
                continue

            if info.is_dir():
                # Лишние уровни каталогов запрещены
                if len(parts) > 4:
                    context.errors.append(
                        ErrorDetail(
                            code=ErrorCode.INVALID_STRUCTURE,
                            message="Лишний уровень папок в архиве.",
                            path=name,
                        )
                    )
                continue

            if len(parts) != 5:
                # Файлы должны быть строго на 5-м уровне
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_STRUCTURE,
                        message="Неверная структура папок в архиве.",
                        path=name,
                    )
                )
                continue

            group, student_short, discipline_full, worktype_folder, filename = parts

            if root_group is None:
                root_group = group
            elif group != root_group:
                # Больше одной группы в архиве
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_STRUCTURE,
                        message="В архиве обнаружено несколько папок групп.",
                        path=name,
                    )
                )

            if student is None:
                student = student_short
            elif student_short != student:
                # Больше одного студента в архиве
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_STRUCTURE,
                        message="В архиве обнаружено несколько папок студентов.",
                        path=name,
                    )
                )

            if not is_valid_student_short(student_short):
                # Формат папки студента должен быть "Фамилия ИО"
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_STRUCTURE,
                        message="Неверный формат папки студента (ожидается 'Фамилия ИО').",
                        path=name,
                    )
                )

            if discipline is None:
                discipline = discipline_full
            elif discipline_full != discipline:
                # Разрешена только одна дисциплина
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.MULTIPLE_DISCIPLINES,
                        message="В портфолио должна быть ровно одна дисциплина.",
                        path=name,
                    )
                )

            if discipline_full not in self.discipline_full_map:
                # Дисциплина должна быть из whitelist
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_STRUCTURE,
                        message="Дисциплина отсутствует в списке разрешённых.",
                        path=name,
                    )
                )

            if worktype_folder not in self.worktype_map:
                # Тип работы должен быть из whitelist
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.UNKNOWN_WORKTYPE,
                        message="Неизвестный тип работ в папке.",
                        path=name,
                    )
                )

            base, ext = split_filename(filename)
            if ext.lower() != "pdf":
                # На последнем уровне разрешены только PDF
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_STRUCTURE,
                        message="Разрешены только PDF-файлы на последнем уровне.",
                        path=name,
                    )
                )
            else:
                if not PDF_NAME_RE.match(base):
                    # PDF-имя должно соответствовать шаблону
                    context.errors.append(
                        ErrorDetail(
                            code=ErrorCode.INVALID_FILENAME,
                            message="Неверный формат имени PDF-файла.",
                            path=name,
                        )
                    )
                else:
                    self._validate_pdf_name(
                        base,
                        group,
                        student_short,
                        discipline_full,
                        worktype_folder,
                        context,
                        name,
                    )
                pdf_paths.append(name)

        if root_group:
            context.group = root_group
        if student:
            context.student_short = student
        if discipline:
            context.discipline_full = discipline
            context.discipline_short = self.discipline_full_map.get(discipline, {}).get(
                "discipline_short"
            )
        context.pdf_paths = pdf_paths
        if not pdf_paths:
            # Если PDF не найдено — сразу ошибка
            context.errors.append(
                ErrorDetail(
                    code=ErrorCode.INVALID_STRUCTURE,
                    message="В архиве не найдено ни одного PDF-файла.",
                )
            )

    def _validate_pdf_name(
        self,
        base: str,
        group: str,
        student_short: str,
        discipline_full: str,
        worktype_folder: str,
        context: CheckContext,
        path: str,
    ) -> None:
        group_part, student_part, discipline_part, work_part = base.split("_")
        if group_part != group:
            # Группа в имени файла должна совпадать с корнем
            context.errors.append(
                ErrorDetail(
                    code=ErrorCode.INVALID_FILENAME,
                    message="Группа в имени файла не совпадает с корневой папкой.",
                    path=path,
                )
            )
        if student_part != student_short:
            # ФИО в имени файла должно совпадать с папкой
            context.errors.append(
                ErrorDetail(
                    code=ErrorCode.INVALID_FILENAME,
                    message="ФИО в имени файла не совпадает с папкой студента.",
                    path=path,
                )
            )

        discipline_info = self.discipline_full_map.get(discipline_full)
        if discipline_info:
            expected_short = discipline_info["discipline_short"]
            if discipline_part != expected_short:
                # Сокращение дисциплины из справочника
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_FILENAME,
                        message="Сокращение дисциплины в имени файла не совпадает со справочником.",
                        path=path,
                    )
                )

        worktype_info = self.worktype_map.get(worktype_folder)
        if worktype_info and "alias_of" in worktype_info:
            # Алиасы приводим к базовой записи
            worktype_info = self.worktype_map.get(worktype_info["alias_of"])

        if worktype_info:
            expected_code = worktype_info.get("code")
            match = WORKCODE_RE.match(work_part)
            if not match:
                # Код работы в PDF не соответствует формату
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_FILENAME,
                        message="Неверный формат типа работы в имени файла.",
                        path=path,
                    )
                )
                return
            code, number = match.groups()
            if expected_code and code != expected_code:
                # Код работы должен совпадать с папкой типа работ
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_FILENAME,
                        message="Код типа работы в имени файла не соответствует папке.",
                        path=path,
                    )
                )
            number_required = bool(worktype_info.get("number_required"))
            number_forbidden = bool(worktype_info.get("number_forbidden"))
            if number_required and not number:
                # Номер обязателен
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_FILENAME,
                        message="Для данного типа работы требуется номер.",
                        path=path,
                    )
                )
            if number_forbidden and number:
                # Номер запрещён
                context.errors.append(
                    ErrorDetail(
                        code=ErrorCode.INVALID_FILENAME,
                        message="Для данного типа работы номер не допускается.",
                        path=path,
                    )
                )
