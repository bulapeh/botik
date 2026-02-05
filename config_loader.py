import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class Config:
    raw: Dict[str, Any]

    @property
    def telegram_token(self) -> str:
        return self.raw["telegram"]["token"]

    @property
    def polling_interval_sec(self) -> int:
        return int(self.raw["telegram"].get("polling_interval_sec", 1))


def load_config(path: str) -> Config:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return Config(raw=data)
