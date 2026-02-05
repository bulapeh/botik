"""Правила принятия/отклонения/ручной проверки портфолио."""

from dataclasses import dataclass
from enum import Enum

from check_context import CheckContext


class DecisionStatus(str, Enum):
    # Итоговые статусы решения
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True)
class DecisionResult:
    # Результат работы decision_engine
    status: DecisionStatus
    reason: str


def decide(context: CheckContext, config: dict) -> DecisionResult:
    # Любые структурные ошибки => отклонение
    if context.errors:
        return DecisionResult(
            status=DecisionStatus.REJECTED,
            reason="Найдены ошибки в структуре или именах файлов.",
        )

    # Если включена проверка титула — смотрим confidence
    title_config = config.get("title_check", {})
    if title_config.get("enabled") and context.title_analysis:
        signature_threshold = float(title_config.get("signature_threshold", 0.6))
        zacheno_threshold = float(title_config.get("zacheno_threshold", 0.6))
        signature_ok = context.title_analysis.signature_confidence >= signature_threshold
        zacheno_ok = context.title_analysis.zacheno_confidence >= zacheno_threshold
        if signature_ok or zacheno_ok:
            return DecisionResult(
                status=DecisionStatus.ACCEPTED,
                reason="Портфолио прошло автоматическую проверку титульного листа.",
            )
        return DecisionResult(
            status=DecisionStatus.REJECTED,
            reason="Не удалось подтвердить подпись или отметку на титульном листе.",
        )

    # Если CV выключен — достаточно структуры
    return DecisionResult(
        status=DecisionStatus.ACCEPTED,
        reason="Портфолио прошло структурную проверку.",
    )
