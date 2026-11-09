"""Pydantic data models for Task Registry Service."""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class TaskBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=100, description="Коротка назва задачі")
    description: str = Field(..., min_length=1, max_length=500, description="Детальний опис")
    assignee: str = Field(..., min_length=2, max_length=50, description="Відповідальний за задачу")
    due_date: str = Field(..., description="Строк виконання у форматі YYYY-MM-DD")

    @field_validator("due_date")
    @classmethod
    def validate_due_date_format(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError(f"Некоректний формат дати: '{value}'. Очікується ISO YYYY-MM-DD")
        return value

    @field_validator("title", "description", "assignee")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Поле не може складатися лише з пробілів")
        return stripped


class TaskCreate(TaskBase):
    """Схема для ручного створення задачі."""
    pass


class Task(TaskBase):
    """Схема збереженої задачі з присвоєним технічним ID."""
    id: int = Field(..., description="Унікальний ідентифікатор задачі")


class TaskFromTextRequest(BaseModel):
    """Запит на створення задачі з тексту повідомлення."""
    text: str = Field(..., min_length=5, max_length=2000, description="Текст домовленості після зустрічі")


class TaskProposal(BaseModel):
    """Неперевірена пропозиція мовної моделі."""
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[str] = None


class ProposalOutcome(BaseModel):
    """Результат аналізу пропозиції політикою застосунку."""
    status: Literal["valid", "needs_clarification", "invalid_semantics", "provider_unavailable"]
    task_data: Optional[TaskCreate] = None
    reason: Optional[str] = None
    missing_fields: Optional[List[str]] = None
    path: str = "llm"
