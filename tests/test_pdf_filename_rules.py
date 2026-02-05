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
            {"folder": "Практические работы", "alias_of": "Практические занятия"},
            {"folder": "Практические занятия", "code": "ПЗ", "number_required": True},
        ],
    }


def create_zip(tmp_path: Path, files: dict[str, bytes]) -> Path:
    zip_path = tmp_path / "portfolio.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return zip_path


def test_practice_requires_pz_code(tmp_path: Path):
    config = build_config()
    validator = StructureValidator(config)
    files = {
        "ИТ-21б/Иванов ИО/Сети и системы радиосвязи/Практические работы/"
        "ИТ-21б_Иванов ИО_СиСР_ПР1.pdf": b"%PDF-1.4\n1 0 obj\nendobj",
    }
    zip_path = create_zip(tmp_path, files)

    context = validator.validate(str(zip_path))

    assert context.errors
