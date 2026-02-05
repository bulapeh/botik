from check_context import CheckContext
from decision_engine import DecisionStatus, decide
from errors import ErrorDetail, ErrorCode
from utils import TitleAnalysisResult


def test_decision_rejected_on_errors():
    # Наличие ошибок должно приводить к отказу
    context = CheckContext(zip_path="test.zip")
    context.errors.append(
        ErrorDetail(code=ErrorCode.INVALID_STRUCTURE, message="bad", path="x")
    )
    result = decide(context, {"title_check": {"enabled": False}})
    assert result.status == DecisionStatus.REJECTED


def test_decision_with_title_check():
    # Если титул прошёл по порогу — принимаем
    context = CheckContext(zip_path="test.zip")
    context.title_analysis = TitleAnalysisResult(
        signature_confidence=0.7,
        zacheno_confidence=0.2,
        flags=[],
        debug={},
    )
    result = decide(
        context,
        {"title_check": {"enabled": True, "signature_threshold": 0.6, "zacheno_threshold": 0.6}},
    )
    assert result.status == DecisionStatus.ACCEPTED
