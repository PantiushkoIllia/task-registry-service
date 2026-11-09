"""Service orchestration for task creation from text."""

from datetime import date
from typing import Tuple, Dict, Any, Optional
from .models import TaskFromTextRequest
from .storage import TaskStore
from .proposer import TaskProposer, ProviderUnavailableError
from .policy import review_proposal, calculate_nearest_friday


def process_task_from_text(
    request: TaskFromTextRequest,
    store: TaskStore,
    proposer: TaskProposer,
    allow_calculated_due_date: bool = True,
    reference_date: Optional[date] = None,
) -> Tuple[int, Dict[str, Any]]:
    """
    Головний бізнес-оркестратор:
    1. Перевірка входу.
    2. Виклик моделі через proposer.
    3. Обробка відсутнього строку за правилом CR-001 (найближча п'ятниця).
    4. Валідація пропозиції та перевірка grounding через policy.
    5. Збереження у store або повернення відмови без зміни даних.
    """
    text = request.text.strip()
    if len(text) < 5:
        return 422, {
            "status": "needs_clarification",
            "reason": "Текст повідомлення занадто короткий (мінімум 5 символів)",
            "missing_fields": ["text"],
        }

    # Виклик моделі з контролем збоїв провайдера
    try:
        proposal = proposer.propose(text)
    except ProviderUnavailableError as e:
        return 503, {
            "status": "provider_unavailable",
            "reason": str(e),
        }
    except Exception as e:
        return 422, {
            "status": "invalid_semantics",
            "reason": f"Структурний збій відповіді моделі: {e}",
        }

    # Правило CR-001: якщо дата не вказана у пропозиції/тексті, але правило увімкнене
    auto_due_date = False
    if allow_calculated_due_date and (proposal.due_date is None or not str(proposal.due_date).strip()):
        calculated_friday = calculate_nearest_friday(reference_date)
        proposal.due_date = calculated_friday
        auto_due_date = True

    # Перевірка пропозиції політикою застосунку
    outcome = review_proposal(
        text,
        proposal,
        allow_calculated_due_date=auto_due_date,
    )

    if outcome.status == "valid" and outcome.task_data:
        saved_task = store.add(outcome.task_data)
        response_data = saved_task.model_dump()
        response_data["status"] = "created"
        response_data["path"] = outcome.path
        response_data["auto_due_date"] = auto_due_date
        if auto_due_date:
            response_data["notice"] = (
                f"Строк не було вказано; автоматично встановлено найближчу п'ятницю: {proposal.due_date}"
            )
        return 201, response_data

    if outcome.status == "needs_clarification":
        return 422, {
            "status": "needs_clarification",
            "reason": outcome.reason,
            "missing_fields": outcome.missing_fields or [],
        }

    # invalid_semantics
    return 422, {
        "status": "invalid_semantics",
        "reason": outcome.reason,
    }
