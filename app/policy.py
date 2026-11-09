"""Application policy and verification engine for LLM task proposals."""

import re
from datetime import datetime, date, timedelta
from typing import Union, Dict, Any, List, Optional
from .models import TaskProposal, ProposalOutcome, TaskCreate


AMBIGUITY_MARKERS = [
    " або ",
    " чи скоріше ",
    " хоча краще ",
    " не впевнений ",
    " під питанням ",
    "або передати",
]


def calculate_nearest_friday(ref_date: Optional[date] = None) -> str:
    """
    Обчислює дату найближчої п'ятниці відповідно до PM-правила CR-001:
    - Пн-Чт (0..3): п'ятниця цього тижня.
    - Пт (4): переноситься на п'ятницю наступного тижня (+7 днів).
    - Сб-Нд (5..6): п'ятниця наступного тижня.
    """
    if ref_date is None:
        ref_date = date.today()

    weekday = ref_date.weekday()
    if weekday < 4:
        delta = 4 - weekday
    elif weekday == 4:
        delta = 7
    else:
        delta = (4 - weekday) + 7

    target_date = ref_date + timedelta(days=delta)
    return target_date.strftime("%Y-%m-%d")



def review_proposal(
    raw_text: str,
    proposal: Union[TaskProposal, Dict[str, Any]],
    allow_calculated_due_date: bool = False,
) -> ProposalOutcome:
    """
    Перевіряє пропозицію моделі на відповідність продуктовому контракту та виконує grounding check.
    
    Правила:
    1. Перевірка обов'язкових полів (title, assignee, due_date).
    2. Перевірка наявності суперечностей у тексті повідомлення.
    3. Перевірка валідності формату дати (ISO YYYY-MM-DD).
    4. Grounding check відповідального: ім'я або псевдонім має зустрічатися у вхідному тексті.
    5. Grounding check дати: дата має бути згадана у тексті (якщо не увімкнено allow_calculated_due_date).
    """
    if isinstance(proposal, TaskProposal):
        data = proposal.model_dump()
    else:
        data = dict(proposal)

    title = data.get("title")
    description = data.get("description")
    assignee = data.get("assignee")
    due_date = data.get("due_date")

    # 1. Перевірка обов'язкових полів
    missing: List[str] = []
    if not title or not str(title).strip():
        missing.append("title")
    if not assignee or not str(assignee).strip():
        missing.append("assignee")
    if not due_date or not str(due_date).strip():
        missing.append("due_date")

    if missing:
        return ProposalOutcome(
            status="needs_clarification",
            reason=f"Відсутні обов'язкові поля: {', '.join(missing)}",
            missing_fields=missing,
        )

    title_str = str(title).strip()
    assignee_str = str(assignee).strip()
    due_date_str = str(due_date).strip()
    desc_str = str(description).strip() if description and str(description).strip() else title_str

    # 2. Перевірка наявності неоднозначностей або конфліктних маркерів у вхідному тексті
    text_lower = f" {raw_text.lower()} "
    for marker in AMBIGUITY_MARKERS:
        if marker in text_lower:
            return ProposalOutcome(
                status="needs_clarification",
                reason=f"Вхідний текст містить суперечливі або неоднозначні формулювання ('{marker.strip()}')",
                missing_fields=["conflict"],
            )

    # 3. Перевірка коректності дати
    try:
        datetime.strptime(due_date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return ProposalOutcome(
            status="invalid_semantics",
            reason=f"Некоректний формат дати: '{due_date_str}'. Очікується ISO YYYY-MM-DD",
        )

    # 4. Grounding Check: захист від вигаданого відповідального (Anti-Hallucination)
    # Перевіряємо, чи є ім'я або основа імені у вихідному тексті (case-insensitive)
    assignee_clean = re.sub(r"[^\w\s]", "", assignee_str).strip().lower()
    raw_text_clean = re.sub(r"[^\w\s]", " ", raw_text).strip().lower()
    raw_words = set(raw_text_clean.split())

    # Якщо повне ім'я або хоча б одне слово з імені не присутнє у словах тексту
    assignee_words = assignee_clean.split()
    if not any(word in raw_words or word in raw_text_clean for word in assignee_words):
        return ProposalOutcome(
            status="invalid_semantics",
            reason=f"Галюцинація: відповідального '{assignee_str}' немає у вхідному тексті",
        )

    # 5. Grounding Check: захист від вигаданої дати
    if not allow_calculated_due_date:
        if due_date_str not in raw_text:
            return ProposalOutcome(
                status="invalid_semantics",
                reason=f"Галюцинація: дати '{due_date_str}' немає у вхідному тексті",
            )

    # 6. Створення валідованого об'єкта задачі
    try:
        task_create = TaskCreate(
            title=title_str,
            description=desc_str,
            assignee=assignee_str,
            due_date=due_date_str,
        )
    except Exception as e:
        return ProposalOutcome(
            status="invalid_semantics",
            reason=f"Порушення схеми даних задачі: {e}",
        )

    return ProposalOutcome(
        status="valid",
        task_data=task_create,
        reason=None,
        path="llm",
    )
