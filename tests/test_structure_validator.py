import zipfile
from pathlib import Path

from structure_validator import StructureValidator


def build_config():
    return {
        "disciplines": [
            {
                "discipline_full": "Сети и системы радиосвязи",
                "discipline_short": "СиСР",
                "sheet_column_header": "СиСР",
            }
        ],
        "worktypes": [
            {"folder": "Лабораторные работы", "code": "ЛР", "number_required": True},
            {"folder": "Практические занятия", "code": "ПЗ", "number_required": True},
            {"folder": "Практические работы", "alias_of": "Практические занятия"},
            {"folder": "Курсовая работа", "code": "КР", "number_required": False, "number_forbidden": True},
        ],
    }


def create_zip(tmp_path: Path, files: dict[str, bytes]) -> Path:
    zip_path = tmp_path / "portfolio.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return zip_path


def test_valid_structure(tmp_path: Path):
    config = build_config()
    validator = StructureValidator(config)
    files = {
        "ИТ-21б/Иванов ИО/Сети и системы радиосвязи/Лабораторные работы/"
        "ИТ-21б_Иванов ИО_СиСР_ЛР1.pdf": b"%PDF-1.4\n1 0 obj\nendobj",
    }
    zip_path = create_zip(tmp_path, files)

    context = validator.validate(str(zip_path))

    assert context.errors == []
    assert context.group == "ИТ-21б"
    assert context.student_short == "Иванов ИО"
    assert context.discipline_full == "Сети и системы радиосвязи"


def test_extra_files_rejected(tmp_path: Path):
    config = build_config()
    validator = StructureValidator(config)
    files = {
        "ИТ-21б/Иванов ИО/Сети и системы радиосвязи/Лабораторные работы/"
        "ИТ-21б_Иванов ИО_СиСР_ЛР1.pdf": b"%PDF-1.4\n1 0 obj\nendobj",
        "__MACOSX/._junk": b"test",
    }
    zip_path = create_zip(tmp_path, files)

    context = validator.validate(str(zip_path))

    assert context.errors
