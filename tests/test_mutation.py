"""Mutation testing (Test-the-Test) demonstrating test sensitivity to defects."""

import pytest
from app.policy import review_proposal
from app.models import TaskProposal, ProposalOutcome, TaskCreate


def mutated_review_proposal_without_grounding(raw_text: str, proposal: TaskProposal) -> ProposalOutcome:
    """
    МУТАЦІЯ (Дефект у коді розробника):
    Розробник випадково видалив або пропустив Grounding Check і сліпо довірився моделі!
    """
    # Мутована функція НЕ перевіряє присутність assignee у raw_text!
    return ProposalOutcome(
        status="valid",
        task_data=TaskCreate(
            title=proposal.title or "За замовчуванням",
            description=proposal.description or "Опис",
            assignee=proposal.assignee,  # Приймає навіть якщо це вигадане ім'я!
            due_date=proposal.due_date,
        ),
    )


def test_mutation_sensitivity_detection():
    """
    Доведення чутливості тесту:
    1. На мутованій версії (без Grounding Check) тест фіксує пропуск галюцинації (помилковий статус 'valid').
    2. На реальній версії policy тест гарантовано відхиляє галюцинацію зі статусом 'invalid_semantics'.
    """
    text = "Підготувати звіт; відповідальний: Ірина; строк: 2026-11-20"
    hallucinated_proposal = TaskProposal(
        title="Підготувати звіт",
        description="Опис",
        assignee="Богдан",  # Богдана немає в тексті!
        due_date="2026-11-20",
    )

    # 1. Перевіряємо, що мутована функція пропускає галюцинацію (дефект виявлено)
    mutated_outcome = mutated_review_proposal_without_grounding(text, hallucinated_proposal)
    assert mutated_outcome.status == "valid", "Мутована функція помилково пропустила галюцинацію"

    # 2. Перевіряємо, що еталонна функція review_proposal успішно ловить дефект і блокує його
    real_outcome = review_proposal(text, hallucinated_proposal)
    assert real_outcome.status == "invalid_semantics", "Справжня політика повинна заблокувати галюцинацію!"
    assert "галюцинація" in real_outcome.reason.lower()
