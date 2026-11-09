# Перелік задач розробки (Tasks Backlog)

**Функція:** `001-task-registry`  
**Підхід:** Specification-Driven Development (SDD) & Test-First  

---

## 1. Таблиця трасування: Критерії приймання → Задачі

| Критерій | Назва критерію | Відповідні задачі | Тестові файли |
|---|---|---|---|
| **AC-1** | Перегляд списку задач | TASK-1, TASK-2, TASK-6 | `tests/test_storage.py`, `tests/test_api.py` |
| **AC-2** | Ручне створення задачі | TASK-1, TASK-2, TASK-6 | `tests/test_storage.py`, `tests/test_api.py` |
| **AC-3** | Захист від некоректного ручного входу | TASK-1, TASK-6 | `tests/test_api.py` |
| **AC-4** | AI-видобування з тексту та Grounding | TASK-3, TASK-4, TASK-5, TASK-6 | `tests/test_policy.py`, `tests/test_service.py`, `tests/test_api.py` |
| **AC-5** | Стійкість до збоїв провайдера та ізоляція | TASK-4, TASK-5, TASK-6 | `tests/test_service.py`, `tests/test_api.py` |

---

## 2. Послідовність задач розробки

### Фаза 1. Моделі даних та сховище (Data & Storage)
- [x] **TASK-1: Моделі Pydantic та контракти даних**
  - **Файл:** `app/models.py`
  - **Опис:** Визначення схем `Task`, `TaskCreate`, `TaskFromTextRequest`, `TaskProposal`, `ProposalOutcome`.
  - **DoD:** Схеми валідують мінімальну довжину, формати дат, відкидають зайві поля.

- [x] **TASK-2: Сховище задач із тестовою ізоляцією**
  - **Файли:** `app/storage.py`, `tests/test_storage.py`
  - **Опис:** Реалізація `TaskStore` із підтримкою файлу JSON або пам'яті, методами `list()`, `add()`, `clear()`.
  - **DoD:** Unit-тести підтверджують унікальність `id`, збереження стану та успішне очищення.

### Фаза 2. Політика верифікації та захист від галюцинацій (Policy & Proposer)
- [x] **TASK-3: Двигун політики та Grounding Check**
  - **Файли:** `app/policy.py`, `tests/test_policy.py`
  - **Опис:** Реалізація `review_proposal` з перевіркою присутності `assignee` та `due_date` у вхідному тексті.
  - **DoD:** Тести перевіряють статус `valid`, відхилення галюцинацій (`invalid_semantics`) та неповноту/суперечність (`needs_clarification`).

- [x] **TASK-4: Модуль виклику LLM (Proposer)**
  - **Файли:** `app/proposer.py`
  - **Опис:** Реалізація `MockProposer` (з підтримкою детермінованих сценаріїв) та `OpenAIProposer` (OpenAI / OpenRouter).
  - **DoD:** Надійна обробка та підняття `ProviderUnavailableError` при помилках мережі чи симуляції збою.

### Фаза 3. Сервісний оркестратор та HTTP API (Service & Routing)
- [x] **TASK-5: Сервісний оркестратор**
  - **Файли:** `app/service.py`, `tests/test_service.py`
  - **Опис:** Об'єднання перевірки довжини тексту, виклику пропоузера, політики та сховища.
  - **DoD:** При збої або неповних даних сховище гарантовано не змінюється.

- [x] **TASK-6: Маршрутизація FastAPI та кінцеві точки**
  - **Файли:** `app/main.py`, `tests/test_api.py`
  - **Опис:** Реалізація ендпоінтів `GET /tasks`, `POST /tasks`, `POST /tasks/from-text`.
  - **DoD:** Інтеграційні тести через `TestClient` перевіряють усі сценарії статусів 200, 201, 422, 503.

### Фаза 4. Чутливість тестів та відновлення (Mutation Testing)
- [x] **TASK-7: Мутаційне тестування (Test-the-Test)**
  - **Файли:** `tests/test_mutation.py`
  - **Опис:** Тест перевіряє чутливість тестового набору: навмисне видалення Grounding Check призводить до падіння тесту; після повернення правила тести проходять успішно.
  - **DoD:** Зафіксовано доказ падіння та відновлення.
