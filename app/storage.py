"""Persistence layer for Task Registry Service."""

import os
import json
import threading
from pathlib import Path
from typing import List, Optional
from .models import Task, TaskCreate


class TaskStore:
    """Потокобезпечне сховище задач із підтримкою збереження у JSON файл."""

    def __init__(self, file_path: Optional[str] = None):
        self._lock = threading.Lock()
        self._tasks: List[Task] = []
        self._next_id: int = 1
        self._file_path: Optional[Path] = Path(file_path) if file_path and file_path != ":memory:" else None

        if self._file_path:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_file()

    def _load_from_file(self) -> None:
        if self._file_path and self._file_path.exists():
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._tasks = [Task(**item) for item in data]
                    if self._tasks:
                        self._next_id = max(t.id for t in self._tasks) + 1
            except Exception:
                self._tasks = []
                self._next_id = 1

    def _save_to_file(self) -> None:
        if self._file_path:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump([t.model_dump() for t in self._tasks], f, ensure_ascii=False, indent=2)

    def list(self) -> List[Task]:
        with self._lock:
            return list(self._tasks)

    def add(self, data: TaskCreate) -> Task:
        with self._lock:
            task = Task(id=self._next_id, **data.model_dump())
            self._next_id += 1
            self._tasks.append(task)
            self._save_to_file()
            return task

    def get(self, task_id: int) -> Optional[Task]:
        with self._lock:
            for task in self._tasks:
                if task.id == task_id:
                    return task
            return None

    def clear(self) -> None:
        with self._lock:
            self._tasks = []
            self._next_id = 1
            if self._file_path and self._file_path.exists():
                try:
                    self._file_path.unlink()
                except OSError:
                    pass


# Глобальний екземпляр сховища за замовчуванням
_default_store: Optional[TaskStore] = None


def get_store() -> TaskStore:
    global _default_store
    if _default_store is None:
        store_path = os.getenv("TASK_STORE_PATH", "data/tasks.json")
        _default_store = TaskStore(store_path)
    return _default_store


def set_default_store(store: TaskStore) -> None:
    global _default_store
    _default_store = store
