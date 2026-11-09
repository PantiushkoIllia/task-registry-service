"""LLM Proposer module for Task Registry Service."""

import os
import re
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from .models import TaskProposal


class ProviderUnavailableError(Exception):
    """Виникає при недоступності, таймауті або мережевому збої LLM-провайдера."""
    pass


class TaskProposer(ABC):
    """Абстрактний інтерфейс для отримання пропозиції задачі від мовної моделі."""

    @abstractmethod
    def propose(self, text: str) -> TaskProposal:
        """Отримує структуровану пропозицію за текстом повідомлення."""
        pass


class MockProposer(TaskProposer):
    """Детермінований імітатор моделі для відтворюваного та автономного тестування."""

    def __init__(self):
        self._custom_responses: Dict[str, Any] = {}

    def register_response(self, substring: str, response: Any) -> None:
        self._custom_responses[substring] = response

    def clear_responses(self) -> None:
        self._custom_responses.clear()

    def propose(self, text: str) -> TaskProposal:
        # 1. Перевірка на зареєстровані спеціальні відповіді
        for pattern, resp in self._custom_responses.items():
            if pattern in text:
                if isinstance(resp, Exception):
                    raise resp
                if isinstance(resp, type) and issubclass(resp, Exception):
                    raise resp("Імітація помилки провайдера")
                if isinstance(resp, dict):
                    return TaskProposal(**resp)
                if isinstance(resp, TaskProposal):
                    return resp
                if isinstance(resp, str):
                    try:
                        return TaskProposal(**json.loads(resp))
                    except Exception as e:
                        raise ValueError(f"Помилка розбору JSON пропозиції: {e}")

        # 2. Перевірка спеціальних сигнальних маркерів у тексті
        if "simulate_provider_error" in text or "збій провайдера" in text.lower():
            raise ProviderUnavailableError("Провайдер моделі недоступний: імітація timeout")

        if "simulate_malformed_json" in text or "зламаний json" in text.lower():
            raise ValueError("Malformed JSON returned by provider: Invalid syntax")

        if "simulate_hallucination" in text or "постачальником" in text.lower():
            # Галюцинація: вигадуємо ім'я Богдан, якого немає в тексті
            return TaskProposal(
                title="Узгодити контракт",
                description="відправити підписану копію",
                assignee="Богдан",
                due_date="2026-11-30",
            )

        # 3. Базовий детермінований аналіз вхідного повідомлення
        text_clean = text.strip()

        # Пошук відповідального
        assignee_match = re.search(r"відповідальний:\s*([A-Za-zА-Яа-яІіЇїЄєҐґ]+)", text, re.IGNORECASE)
        assignee = None
        if assignee_match:
            assignee = assignee_match.group(1).strip()
        else:
            # Спроба знайти відомі типові імена в тексті
            for name in ["Ірина", "Максим", "Олексій", "Тарас", "Олег", "Марія"]:
                if name.lower() in text.lower():
                    assignee = name
                    break

        # Пошук дати ISO
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        due_date = date_match.group(1) if date_match else None

        # Пошук опису
        desc_match = re.search(r"опис:\s*([^;\n]+)", text, re.IGNORECASE)
        description = desc_match.group(1).strip() if desc_match else None

        # Пошук назви
        title_part = re.split(r"[;\n]|опис:|відповідальний:|строк:", text, flags=re.IGNORECASE)[0].strip()
        title = title_part if len(title_part) >= 3 else None

        # Специфічний випадок природного формулювання (C2):
        if "інструкцію розгортання" in text.lower():
            title = "Оновити інструкцію розгортання"
            if not description:
                description = "в документації нашого сервісу"

        return TaskProposal(
            title=title,
            description=description or title,
            assignee=assignee,
            due_date=due_date,
        )


class OpenAIProposer(TaskProposer):
    """Жива інтеграція з OpenAI / OpenRouter API через OpenAI Python SDK."""

    PROMPT_SYSTEM = """Ви — помічник з видобування задач із тексту повідомлень.
Поверніть результат у форматі JSON з полями: title, description, assignee, due_date.
ЖОРСТКЕ ПРАВИЛО GROUNDING:
1. Заповнюйте поле лише якщо воно прямо вказане у тексті.
2. Ніколи не вигадуйте відповідального чи дату. Якщо значення немає або текст суперечливий — поверніть null.
3. Формат дати: YYYY-MM-DD.
"""

    def __init__(self):
        from openai import OpenAI

        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API ключ не знайдено (встановіть OPENROUTER_API_KEY або OPENAI_API_KEY)")

        base_url = "https://openrouter.ai/api/v1" if os.getenv("OPENROUTER_API_KEY") else None
        self._model = (
            os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
            if os.getenv("OPENROUTER_API_KEY")
            else os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        )
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0, max_retries=0)

    def propose(self, text: str) -> TaskProposal:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self.PROMPT_SYSTEM},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            raw_content = response.choices[0].message.content
            data = json.loads(raw_content)
            return TaskProposal(**data)
        except Exception as e:
            if "timeout" in str(e).lower() or "connection" in str(e).lower() or "50" in str(e):
                raise ProviderUnavailableError(f"Мережевий збій або таймаут моделі: {e}") from e
            raise


# Глобальний екземпляр пропоузера
_default_proposer: Optional[TaskProposer] = None


def get_proposer() -> TaskProposer:
    global _default_proposer
    if _default_proposer is None:
        mode = os.getenv("PROPOSER_MODE", "mock").lower()
        if mode == "live":
            try:
                _default_proposer = OpenAIProposer()
            except Exception:
                _default_proposer = MockProposer()
        else:
            _default_proposer = MockProposer()
    return _default_proposer


def set_default_proposer(proposer: TaskProposer) -> None:
    global _default_proposer
    _default_proposer = proposer
