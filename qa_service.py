"""Сервис ответов на вопросы на основе базы знаний и OpenAI."""

from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI


@dataclass
class QaResult:
    success: bool
    answer: str
    error: str | None = None


class QaService:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._qa_cfg = config.get("qa", {})
        self._knowledge_text = self._load_knowledge_base()
        self._client = OpenAI(api_key=self._qa_cfg.get("openai_api_key", ""))

    def _load_knowledge_base(self) -> str:
        path = self._qa_cfg.get("knowledge_base_path", "knowledge_base.md")
        max_chars = int(self._qa_cfg.get("max_knowledge_chars", 12000))
        try:
            text = Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return "База знаний не найдена. Ответьте, что справка недоступна."
        return text[:max_chars]

    def answer(self, question: str) -> QaResult:
        if not self._qa_cfg.get("enabled", False):
            return QaResult(success=False, answer="", error="QA disabled")
        api_key = self._qa_cfg.get("openai_api_key", "")
        if not api_key or "PUT_OPENAI_KEY_HERE" in api_key:
            return QaResult(
                success=False,
                answer="",
                error="Missing OpenAI API key",
            )

        model = self._qa_cfg.get("openai_model", "gpt-4o-mini")
        max_tokens = int(self._qa_cfg.get("max_answer_tokens", 500))

        system_prompt = (
            "Ты помощник Telegram-бота проверки портфолио. "
            "Отвечай строго по базе знаний ниже, кратко и понятно для студента. "
            "Если ответа нет в базе, скажи, что информации нет."
        )
        user_prompt = (
            "База знаний:\n"
            f"{self._knowledge_text}\n\n"
            f"Вопрос студента:\n{question}"
        )
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
        )
        answer = response.choices[0].message.content.strip()
        return QaResult(success=True, answer=answer)
