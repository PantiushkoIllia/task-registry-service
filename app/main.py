"""FastAPI application entrypoint for Task Registry Service."""

from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Response, status
from fastapi.responses import JSONResponse
from typing import List

from .models import Task, TaskCreate, TaskFromTextRequest
from .storage import TaskStore, get_store
from .proposer import TaskProposer, get_proposer
from .service import process_task_from_text

# Завантажуємо налаштування середовища
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

app = FastAPI(
    title="Task Registry Service",
    description="Локальний сервіс ведення реєстру задач із перевіреним видобуванням через LLM",
    version="1.0.0",
)


@app.get("/health", tags=["system"])
def health_check():
    """Перевірка доступності сервісу."""
    return {"status": "ok"}


@app.get("/tasks", response_model=List[Task], tags=["tasks"])
def list_tasks(store: TaskStore = Depends(get_store)) -> List[Task]:
    """Отримання списку всіх зареєстрованих задач."""
    return store.list()


@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED, tags=["tasks"])
def create_task_manual(data: TaskCreate, store: TaskStore = Depends(get_store)) -> Task:
    """Ручне створення задачі (без участі мовної моделі)."""
    return store.add(data)


@app.post("/tasks/from-text", tags=["tasks"])
def create_task_from_text(
    request: TaskFromTextRequest,
    store: TaskStore = Depends(get_store),
    proposer: TaskProposer = Depends(get_proposer),
):
    """Створення задачі з тексту повідомлення за допомогою перевіреної LLM-пропозиції."""
    status_code, content = process_task_from_text(request, store, proposer)
    return JSONResponse(status_code=status_code, content=content)
