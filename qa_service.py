"""Сервис ответов на вопросы на основе базы знаний и OpenAI."""

from dataclasses import dataclass
from collections import OrderedDict
from pathlib import Path
import time

from openai import OpenAI, RateLimitError


@dataclass
class QaResult:
    success: bool
    answer: str
    error: str | None = None
    source: str | None = None


class QaService:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._qa_cfg = config.get("qa", {})
        self._knowledge_text = self._load_knowledge_base()
        self._client = OpenAI(api_key=self._qa_cfg.get("openai_api_key", ""))
        # Время (unix), до которого мы не делаем новые запросы после 429
        self._rate_limit_until = 0.0
        self._cache: OrderedDict[str, str] = OrderedDict()

    def _load_knowledge_base(self) -> str:
        path = self._qa_cfg.get("knowledge_base_path", "knowledge_base.md")
        max_chars = int(self._qa_cfg.get("max_knowledge_chars", 12000))
        try:
            text = Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return "База знаний не найдена. Ответьте, что справка недоступна."
        return text[:max_chars]

    def _local_answer(self, question: str) -> str | None:
        if not self._qa_cfg.get("fallback_local_enabled", True):
            return None
        normalized = question.strip().lower()
        if not normalized:
            return None
        paragraphs = [p.strip() for p in self._knowledge_text.split("\n\n") if p.strip()]
        best_score = 0
        best_paragraph = None
        for paragraph in paragraphs:
            score = paragraph.lower().count(normalized)
            if score > best_score:
                best_score = score
                best_paragraph = paragraph
        return best_paragraph

    def answer(self, question: str) -> QaResult:
        if not self._qa_cfg.get("enabled", False):
            return QaResult(success=False, answer="", error="QA disabled")
        cached = self._cache.get(question)
        if cached:
            return QaResult(success=True, answer=cached, source="cache")
        # Если недавно получили 429 — не стучимся в API до истечения cooldown
        if time.time() < self._rate_limit_until:
            local = self._local_answer(question)
            if local:
                return QaResult(success=True, answer=local, source="local")
            return QaResult(success=False, answer="", error="Rate limit cooldown")
        api_key = self._qa_cfg.get("openai_api_key", "")
        if not api_key or "PUT_OPENAI_KEY_HERE" in api_key:
            local = self._local_answer(question)
            if local:
                return QaResult(success=True, answer=local, source="local")
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
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
            )
        except RateLimitError as exc:
            cooldown = int(self._qa_cfg.get("rate_limit_cooldown_sec", 60))
            self._rate_limit_until = time.time() + max(cooldown, 1)
            # Различаем исчерпанную квоту и временный лимит
            error_text = str(exc).lower()
            error_code = getattr(exc, "code", None)
            if error_code == "insufficient_quota" or "insufficient_quota" in error_text:
                local = self._local_answer(question)
                if local:
                    return QaResult(success=True, answer=local, source="local")
                return QaResult(success=False, answer="", error="Insufficient quota")
            local = self._local_answer(question)
            if local:
                return QaResult(success=True, answer=local, source="local")
            return QaResult(success=False, answer="", error="Rate limit exceeded")
        answer = response.choices[0].message.content.strip()
        self._cache[question] = answer
        cache_size = int(self._qa_cfg.get("cache_size", 50))
        while len(self._cache) > max(cache_size, 1):
            self._cache.popitem(last=False)
        return QaResult(success=True, answer=answer, source="openai")
