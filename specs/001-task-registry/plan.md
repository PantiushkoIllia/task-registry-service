# Технічний план: Сервіс реєстру задач

**Ціль:** Реалізація сервісу згідно зі специфікацією `spec.md`.  
**Архітектура:** Модульний моноліт на базі FastAPI.  

---

## 1. Архітектурні компоненти

1. **`app/models.py` (Data Models):**
   - Pydantic v2 моделі:
     - `Task`: повна сутність задачі (`id`, `title`, `description`, `assignee`, `due_date`).
     - `TaskCreate`: вхідні дані для ручного створення (`title`, `description`, `assignee`, `due_date`).
     - `TaskFromTextRequest`: вхідні дані для AI-ендпоінту (`text`).
     - `TaskProposal`: вихід моделі / пропозиція перед валідацією.
     - `ProposalOutcome`: результат роботи політики (`status`, `task_data`, `reason`, `missing_fields`).

2. **`app/storage.py` (Persistence Layer):**
   - Клас `TaskStore`:
     - Підтримка збереження у файлі JSON або у внутрішньому списку.
     - Метод `list() -> list[Task]`
     - Метод `add(task_data: TaskCreate) -> Task`: генерує автоінкрементний або унікальний `id`, атомарно зберігає стан.
     - Метод `clear()`: очищення сховища для тестових прогонів.
   - Механізм Dependency Injection для FastAPI (`get_store()`).

3. **`app/policy.py` (Application Policy & Grounding Engine):**
   - Функція `review_proposal(raw_text: str, proposal: TaskProposal) -> ProposalOutcome`:
     - Перевірка обов'язкових полів.
     - Перевірка формату дати `YYYY-MM-DD`.
     - Grounding Check:
       - Ім'я `assignee` шукається у вихідному тексті (з урахуванням нормалізації регістру).
       - Строк `due_date` шукається у вихідному тексті.
     - Перевірка на конфліктні маркери (наприклад, «або», «чи скоріше», «хоча краще»).
     - Повернення статусів: `valid`, `needs_clarification`, `invalid_semantics`.

4. **`app/proposer.py` (LLM Integration Layer):**
   - Базовий абстрактний клас або протокол `TaskProposer`.
   - `MockProposer`: детермінований імітатор відповідей для тестів та відтворення без API-ключа (підтримує сценарії валідні, неповні, суперечливі, зламаний JSON, галюцинації).
   - `OpenAIProposer`: реалізація через клієнт `OpenAI` (OpenAI / OpenRouter API).
   - Фабрика або DI `get_proposer()`.

5. **`app/service.py` (Service Orchestrator):**
   - Функція `process_task_from_text(text: str, store: TaskStore, proposer: TaskProposer) -> tuple[int, dict]`:
     - Перевірка довжини вхідного тексту (від 5 до 2000 символів).
     - Виклик пропоузера моделі з обробкою помилок провайдера (`ProviderUnavailableError` -> HTTP 503).
     - Виклик `review_proposal`.
     - При успіху (`valid`) -> запис у `store` -> повернення (201, `task`).
     - При неуспіху (`needs_clarification` або `invalid_semantics`) -> повернення (422, `error_body`) БЕЗ збереження.

6. **`app/main.py` (HTTP Routing):**
   - Ініціалізація `FastAPI(title="Task Registry Service")`.
   - Маршрути:
     - `GET /tasks` -> список
     - `POST /tasks` -> ручне створення
     - `POST /tasks/from-text` -> видобування через AI з політикою
     - `GET /health` -> діагностичний ендпоінт.

---

## 2. Стратегія тестування
- **Unit Tests:**
  - `test_storage.py`: перевірка CRUD, автоінкременту id, незалежності копій.
  - `test_policy.py`: перевірка всіх правил валідації та відсікання галюцинацій.
- **Integration Tests:**
  - `test_service.py`: перевірка оркестратора сервісу та обробки збоїв провайдера.
  - `test_api.py`: повне тестування через `TestClient` (FastAPI) усіх статус-кодів (200, 201, 422, 503).
- **Mutation / Test-the-Test:**
  - `test_mutation.py`: навмисне відключення перевірки grounding (імітація помилки розробника) для демонстрації чутливості тестів та перевірка відновлення (recovery).
