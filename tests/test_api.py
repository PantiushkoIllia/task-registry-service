"""Integration tests for Task Registry Service HTTP API."""

import pytest


def test_get_tasks_initial(client):
    """AC-1: Отримання початкового списку задач (має бути порожнім масивом або списком)."""
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_task_manual(client):
    """AC-2: Ручне створення задачі."""
    before_resp = client.get("/tasks")
    before_tasks = before_resp.json()

    payload = {
        "title": "Підготувати звіт",
        "description": "Фінальний релізний звіт",
        "assignee": "Ірина",
        "due_date": "2026-11-20",
    }
    resp = client.post("/tasks", json=payload)
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"] == 1
    assert created["title"] == payload["title"]
    assert created["assignee"] == payload["assignee"]
    assert created["due_date"] == payload["due_date"]

    after_tasks = client.get("/tasks").json()
    assert len(after_tasks) == len(before_tasks) + 1
    assert after_tasks[0]["id"] == created["id"]


def test_create_task_invalid_manual(client):
    """AC-3: Відмова при некоректних даних ручного введення без зміни сховища."""
    before_tasks = client.get("/tasks").json()

    # Хибний вхід: невалідний формат дати та занадто коротка назва
    invalid_payload = {
        "title": "A",
        "description": "Опис",
        "assignee": "Ірина",
        "due_date": "20-11-2026",
    }
    resp = client.post("/tasks", json=invalid_payload)
    assert resp.status_code == 422

    after_tasks = client.get("/tasks").json()
    assert after_tasks == before_tasks


def test_ai_create_valid(client):
    """AC-4: Успішне створення задачі з тексту повідомлення."""
    before_tasks = client.get("/tasks").json()

    payload = {
        "text": "Підготувати релізний звіт; опис: перевірити метрики; відповідальний: Ірина; строк: 2026-11-20"
    }
    resp = client.post("/tasks/from-text", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "created"
    assert data["assignee"] == "Ірина"
    assert data["due_date"] == "2026-11-20"
    assert data["id"] is not None

    after_tasks = client.get("/tasks").json()
    assert len(after_tasks) == len(before_tasks) + 1


def test_ai_missing_or_ambiguous(client):
    """AC-4: Неповний або неоднозначний текст повертає 422 needs_clarification без зміни сховища."""
    before_tasks = client.get("/tasks").json()

    # Відсутня дата
    resp = client.post("/tasks/from-text", json={
        "text": "Оновити залежності; опис: патчі безпеки; відповідальний: Олексій"
    })
    assert resp.status_code == 422
    assert resp.json()["status"] == "needs_clarification"
    assert "due_date" in resp.json()["missing_fields"]

    # Суперечливий текст (конфлікт відповідальних)
    resp_conflict = client.post("/tasks/from-text", json={
        "text": "Відповідальний: Ірина, або передати це завдання Олегу; строк: 2026-11-20"
    })
    assert resp_conflict.status_code == 422
    assert resp_conflict.json()["status"] == "needs_clarification"

    after_tasks = client.get("/tasks").json()
    assert after_tasks == before_tasks


def test_ai_malformed_structure(client):
    """AC-4: Модель повертає зламану структуру -> 422 без зміни сховища."""
    before_tasks = client.get("/tasks").json()

    resp = client.post("/tasks/from-text", json={
        "text": "Оновити сервіс; simulate_malformed_json; відповідальний: Ірина; строк: 2026-11-20"
    })
    assert resp.status_code == 422
    assert resp.json()["status"] == "invalid_semantics"

    after_tasks = client.get("/tasks").json()
    assert after_tasks == before_tasks


def test_ai_hallucination_rejected(client):
    """AC-4: Модель намагається призначити вигаданого виконавця -> відхилення з 422."""
    before_tasks = client.get("/tasks").json()

    resp = client.post("/tasks/from-text", json={
        "text": "Узгодити контракт із постачальником; опис: фінальна версія; відповідальний: Ірина; строк: 2026-11-30"
    })
    assert resp.status_code == 422
    assert resp.json()["status"] == "invalid_semantics"
    assert "галюцинація" in resp.json()["reason"].lower()

    after_tasks = client.get("/tasks").json()
    assert after_tasks == before_tasks


def test_provider_failure_and_manual_resilience(client):
    """AC-5: Збій LLM повертає 503, але подальше ручне створення та список працюють бездоганно."""
    before_tasks = client.get("/tasks").json()

    # Запит до AI з помилкою провайдера
    resp = client.post("/tasks/from-text", json={
        "text": "simulate_provider_error: створити задачу"
    })
    assert resp.status_code == 503
    assert resp.json()["status"] == "provider_unavailable"

    # Перевіряємо незмінність сховища
    assert client.get("/tasks").json() == before_tasks

    # Перевіряємо, що ручне створення працює без проблем
    manual_resp = client.post("/tasks", json={
        "title": "Термінова ручна задача",
        "description": "Створена під час збою провайдера",
        "assignee": "Тарас",
        "due_date": "2026-11-22",
    })
    assert manual_resp.status_code == 201

    after_tasks = client.get("/tasks").json()
    assert len(after_tasks) == len(before_tasks) + 1
