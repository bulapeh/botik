import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Добавляем корень проекта в sys.path для импортов модулей
sys.path.insert(0, str(ROOT))
