"""Unit tests for Service Orchestration layer."""

import pytest
from app.service import process_task_from_text
from app.storage import TaskStore
from app.proposer import MockProposer, ProviderUnavailableError
from app.models import TaskFromTextRequest, TaskProposal


def test_service_successful_creation(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    proposer = MockProposer()
    req = TaskFromTextRequest(
        text="Підготувати документацію; опис: розділ архітектури; відповідальний: Максим; строк: 2026-11-25"
    )

    code, resp = process_task_from_text(req, store, proposer)
    assert code == 201
    assert resp["status"] == "created"
    assert resp["id"] == 1
    assert resp["assignee"] == "Максим"
    assert resp["due_date"] == "2026-11-25"
    assert len(store.list()) == 1


def test_service_provider_unavailable(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    proposer = MockProposer()
    req = TaskFromTextRequest(
        text="Терміново зробити реліз; simulate_provider_error; відповідальний: Ірина; строк: 2026-11-20"
    )

    code, resp = process_task_from_text(req, store, proposer)
    assert code == 503
    assert resp["status"] == "provider_unavailable"
    assert len(store.list()) == 0  # Сховище не змінюється!


def test_service_malformed_proposal(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    proposer = MockProposer()
    req = TaskFromTextRequest(
        text="Терміново оновити; simulate_malformed_json; відповідальний: Ірина; строк: 2026-11-20"
    )

    code, resp = process_task_from_text(req, store, proposer)
    assert code == 422
    assert resp["status"] == "invalid_semantics"
    assert len(store.list()) == 0


def test_service_hallucination_leaves_storage_untouched(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    proposer = MockProposer()
    # Текст містить 'постачальником', що тригерить галюцинацію 'Богдан' у MockProposer
    req = TaskFromTextRequest(
        text="Узгодити контракт із постачальником; опис: перевірити підписи; відповідальний: Ірина; строк: 2026-11-30"
    )

    code, resp = process_task_from_text(req, store, proposer)
    assert code == 422
    assert resp["status"] == "invalid_semantics"
    assert "богдан" in resp["reason"].lower()
    assert len(store.list()) == 0
