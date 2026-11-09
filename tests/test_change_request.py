"""Tests for Change Request CR-001 (Nearest Friday Due Date Rule)."""

from datetime import date
import pytest
from app.policy import calculate_nearest_friday
from app.models import TaskFromTextRequest
from app.service import process_task_from_text
from app.storage import TaskStore
from app.proposer import MockProposer


def test_calculate_nearest_friday_algorithm():
    """Перевірка обчислення найближчої п'ятниці для кожного дня тижня."""
    # Понеділок: 2026-11-09 -> П'ятниця 2026-11-13 (+4 дні)
    monday = date(2026, 11, 9)
    assert calculate_nearest_friday(monday) == "2026-11-13"

    # Четвер: 2026-11-12 -> П'ятниця 2026-11-13 (+1 день)
    thursday = date(2026, 11, 12)
    assert calculate_nearest_friday(thursday) == "2026-11-13"

    # П'ятниця: 2026-11-13 -> Наступна п'ятниця 2026-11-20 (+7 днів)
    # Згідно з PM-специфікацією, у п'ятницю не ставимо дедлайн «на сьогодні»
    friday = date(2026, 11, 13)
    assert calculate_nearest_friday(friday) == "2026-11-20"

    # Субота: 2026-11-14 -> Наступна п'ятниця 2026-11-20 (+6 днів)
    saturday = date(2026, 11, 14)
    assert calculate_nearest_friday(saturday) == "2026-11-20"

    # Неділя: 2026-11-15 -> Наступна п'ятниця 2026-11-20 (+5 днів)
    sunday = date(2026, 11, 15)
    assert calculate_nearest_friday(sunday) == "2026-11-20"


def test_cr_auto_due_date_applied_when_date_missing(tmp_path):
    """AC-4b: Якщо строк не вказано, автоматично призначається найближча п'ятниця."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    proposer = MockProposer()
    ref_date = date(2026, 11, 9)  # Понеділок

    req = TaskFromTextRequest(
        text="Оновити бібліотеки в проєкті; опис: безпековий аудит; відповідальний: Олексій"
    )

    code, resp = process_task_from_text(
        req, store, proposer, allow_calculated_due_date=True, reference_date=ref_date
    )

    assert code == 201
    assert resp["status"] == "created"
    assert resp["auto_due_date"] is True
    assert resp["due_date"] == "2026-11-13"  # Найближча п'ятниця
    assert "notice" in resp
    assert "2026-11-13" in resp["notice"]
    assert len(store.list()) == 1


def test_cr_explicit_date_wins_over_friday(tmp_path):
    """AC-4a: Явна дата в тексті має вищий пріоритет над правилом п'ятниці."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    proposer = MockProposer()
    ref_date = date(2026, 11, 9)

    req = TaskFromTextRequest(
        text="Підготувати релізний звіт; опис: чекліст; відповідальний: Ірина; строк: 2026-11-25"
    )

    code, resp = process_task_from_text(
        req, store, proposer, allow_calculated_due_date=True, reference_date=ref_date
    )

    assert code == 201
    assert resp["auto_due_date"] is False
    assert resp["due_date"] == "2026-11-25"
    assert "notice" not in resp


def test_cr_regression_missing_assignee_still_rejected(tmp_path):
    """Регресійний тест: відсутність відповідального НЕ компенсується автоматично і повертає 422."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    proposer = MockProposer()

    req = TaskFromTextRequest(
        text="Терміново оновити продакшн без вказівки відповідального; строк: 2026-11-20"
    )

    code, resp = process_task_from_text(req, store, proposer)
    assert code == 422
    assert resp["status"] == "needs_clarification"
    assert "assignee" in resp["missing_fields"]
    assert len(store.list()) == 0


def test_cr_regression_manual_creation_requires_explicit_due_date(client):
    """Регресійний тест: ручне створення POST /tasks не підставляє дату автоматично."""
    invalid_manual = {
        "title": "Ручна задача без дати",
        "description": "Опис",
        "assignee": "Ірина",
        # due_date відсутня
    }
    resp = client.post("/tasks", json=invalid_manual)
    assert resp.status_code == 422
