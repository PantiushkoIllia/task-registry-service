"""Pytest fixtures for Task Registry Service tests."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.storage import TaskStore, get_store
from app.proposer import MockProposer, get_proposer


@pytest.fixture
def mock_proposer():
    """Свіжий екземпляр MockProposer для тестів."""
    proposer = MockProposer()
    return proposer


@pytest.fixture
def isolated_store(tmp_path):
    """Ізольоване сховище задач у тимчасовій директорії pytest."""
    store_file = tmp_path / "test_tasks.json"
    return TaskStore(str(store_file))


@pytest.fixture
def client(isolated_store, mock_proposer):
    """TestClient з перекритими залежностями сховища та пропоузера."""
    app.dependency_overrides[get_store] = lambda: isolated_store
    app.dependency_overrides[get_proposer] = lambda: mock_proposer
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
