"""Unit tests for Application Policy and Grounding Verification."""

import pytest
from app.policy import review_proposal
from app.models import TaskProposal


def test_policy_valid_proposal():
    text = "Підготувати релізний звіт; опис: перевірити тести; відповідальний: Ірина; строк: 2026-11-20"
    proposal = TaskProposal(
        title="Підготувати релізний звіт",
        description="перевірити тести",
        assignee="Ірина",
        due_date="2026-11-20",
    )
    outcome = review_proposal(text, proposal)
    assert outcome.status == "valid"
    assert outcome.task_data is not None
    assert outcome.task_data.title == "Підготувати релізний звіт"
    assert outcome.task_data.assignee == "Ірина"
    assert outcome.task_data.due_date == "2026-11-20"


def test_policy_missing_fields():
    text = "Підготувати звіт; відповідальний: Ірина"
    proposal = TaskProposal(
        title="Підготувати звіт",
        description="Опис",
        assignee="Ірина",
        due_date=None,
    )
    outcome = review_proposal(text, proposal)
    assert outcome.status == "needs_clarification"
    assert "due_date" in outcome.missing_fields
    assert "відсутні обов'язкові поля" in outcome.reason.lower()


def test_policy_invalid_date_format():
    text = "Підготувати звіт; відповідальний: Ірина; строк: 20-11-2026"
    proposal = TaskProposal(
        title="Підготувати звіт",
        description="Опис",
        assignee="Ірина",
        due_date="20-11-2026",  # Не ISO
    )
    outcome = review_proposal(text, proposal)
    assert outcome.status == "invalid_semantics"
    assert "некоректний формат дати" in outcome.reason.lower()


def test_policy_hallucinated_assignee():
    """Перевірка анти-галюцинації: виконавець Богдан відсутній у вхідному тексті."""
    text = "Підготувати звіт; відповідальний: Ірина; строк: 2026-11-20"
    proposal = TaskProposal(
        title="Підготувати звіт",
        description="Опис",
        assignee="Богдан",  # Галюцинація!
        due_date="2026-11-20",
    )
    outcome = review_proposal(text, proposal)
    assert outcome.status == "invalid_semantics"
    assert "галюцинація" in outcome.reason.lower()
    assert "богдан" in outcome.reason.lower()


def test_policy_hallucinated_due_date():
    """Перевірка анти-галюцинації: дата 2026-12-31 відсутня у тексті."""
    text = "Підготувати звіт; відповідальний: Ірина; строк: 2026-11-20"
    proposal = TaskProposal(
        title="Підготувати звіт",
        description="Опис",
        assignee="Ірина",
        due_date="2026-12-31",  # Галюцинація!
    )
    outcome = review_proposal(text, proposal)
    assert outcome.status == "invalid_semantics"
    assert "галюцинація" in outcome.reason.lower()
    assert "2026-12-31" in outcome.reason.lower()


def test_policy_ambiguous_text_rejected():
    """Текст із маркером вибору повертає needs_clarification."""
    text = "Відповідальний: Ірина, або передати це завдання Олегу; строк: 2026-11-20"
    proposal = TaskProposal(
        title="Передати завдання",
        description="Опис",
        assignee="Ірина",
        due_date="2026-11-20",
    )
    outcome = review_proposal(text, proposal)
    assert outcome.status == "needs_clarification"
    assert "суперечливі" in outcome.reason.lower()
