from dataclasses import dataclass
from enum import Enum

from check_context import CheckContext


class DecisionStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True)
class DecisionResult:
    status: DecisionStatus
    reason: str


def decide(context: CheckContext, config: dict) -> DecisionResult:
    if context.errors:
        return DecisionResult(
            status=DecisionStatus.REJECTED,
            reason="Найдены ошибки в структуре или именах файлов.",
        )

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

    return DecisionResult(
        status=DecisionStatus.ACCEPTED,
        reason="Портфолио прошло структурную проверку.",
    )
