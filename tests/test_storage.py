"""Unit tests for TaskStore persistence layer."""

import pytest
from app.storage import TaskStore
from app.models import TaskCreate


def test_storage_add_and_list(tmp_path):
    store_file = tmp_path / "tasks.json"
    store = TaskStore(str(store_file))

    assert store.list() == []

    t1 = store.add(TaskCreate(
        title="Задача 1",
        description="Опис 1",
        assignee="Ірина",
        due_date="2026-11-20"
    ))
    assert t1.id == 1
    assert t1.title == "Задача 1"

    t2 = store.add(TaskCreate(
        title="Задача 2",
        description="Опис 2",
        assignee="Максим",
        due_date="2026-11-25"
    ))
    assert t2.id == 2

    tasks = store.list()
    assert len(tasks) == 2
    assert tasks[0].id == 1
    assert tasks[1].id == 2


def test_storage_persistence_across_instances(tmp_path):
    store_file = tmp_path / "persistent.json"
    store1 = TaskStore(str(store_file))
    store1.add(TaskCreate(
        title="Постійна задача",
        description="Опис",
        assignee="Олексій",
        due_date="2026-12-01"
    ))

    # Створюємо другий екземпляр з тим самим файлом
    store2 = TaskStore(str(store_file))
    loaded_tasks = store2.list()
    assert len(loaded_tasks) == 1
    assert loaded_tasks[0].title == "Постійна задача"
    assert loaded_tasks[0].id == 1

    # Наступна задача повинна отримати id = 2
    t2 = store2.add(TaskCreate(
        title="Друга задача",
        description="Опис 2",
        assignee="Ірина",
        due_date="2026-12-05"
    ))
    assert t2.id == 2


def test_storage_clear(tmp_path):
    store_file = tmp_path / "clear_test.json"
    store = TaskStore(str(store_file))
    store.add(TaskCreate(
        title="Тест",
        description="Опис",
        assignee="Ірина",
        due_date="2026-11-15"
    ))
    assert len(store.list()) == 1

    store.clear()
    assert len(store.list()) == 0
