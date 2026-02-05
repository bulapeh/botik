"""Загрузка конфигурации из config.json при старте приложения."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


# Обёртка над конфигом для типового доступа к ключам.
@dataclass(frozen=True)
class Config:
    raw: Dict[str, Any]

    @property
    def telegram_token(self) -> str:
        # Токен Telegram-бота
        return self.raw["telegram"]["token"]

    @property
    def polling_interval_sec(self) -> int:
        # Интервал опроса в секундах (по умолчанию 1)
        return int(self.raw["telegram"].get("polling_interval_sec", 1))


def load_config(path: str) -> Config:
    # Читаем конфиг один раз на запуск (без hot-reload).
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return Config(raw=data)
