"""Service orchestration for task creation from text."""

from typing import Tuple, Dict, Any, Optional
from .models import TaskFromTextRequest
from .storage import TaskStore
from .proposer import TaskProposer, ProviderUnavailableError
from .policy import review_proposal


def process_task_from_text(
    request: TaskFromTextRequest,
    store: TaskStore,
    proposer: TaskProposer,
    allow_calculated_due_date: bool = False,
) -> Tuple[int, Dict[str, Any]]:
    """
    Головний бізнес-оркестратор:
    1. Перевірка входу.
    2. Виклик моделі через proposer.
    3. Валідація пропозиції та перевірка grounding через policy.
    4. Збереження у store або повернення відмови без зміни даних.
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

    # Перевірка пропозиції політикою застосунку
    outcome = review_proposal(text, proposal, allow_calculated_due_date=allow_calculated_due_date)

    if outcome.status == "valid" and outcome.task_data:
        saved_task = store.add(outcome.task_data)
        response_data = saved_task.model_dump()
        response_data["status"] = "created"
        response_data["path"] = outcome.path
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
