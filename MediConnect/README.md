## MediConnect (MVP)

Универсальная платформа для обмена медицинскими данными между пациентами, врачами и мед. учреждениями.

### MVP-ограничения
- Документы храним как **строки** (например: URL/путь/идентификатор/текст). Без файлового хранилища.
- Основной фокус: **доступ по согласию**, **аудит**, **мульти-организации**.

### Ключевые модули (в БД)
- **Идентичность**: `users`, `user_identities`
- **Организации**: `orgs`, `org_memberships`
- **Документы**: `documents` (контент в `content_text`)
- **Согласия/доступы**: `consents` (к документам или ко всем документам пациента)
- **Аудит**: `audit_events`

### Быстрый старт (PostgreSQL)
1. Создайте базу и примените схему:

```sql
\i db/schema.sql
```

2. (Опционально) Заполните тестовыми данными:

```sql
\i db/seed.sql
```

3. Примеры запросов:

```sql
\i db/queries.sql
```

### Docker (быстро поднять PostgreSQL)
Из папки `MediConnect`:

```bash
docker compose up -d
```

Если база уже запускалась раньше, схема могла не примениться автоматически (volume сохраняется).
В этом проекте это решает сервис `migrate`, он применяет `db/schema.sql` и `db/seed.sql` при каждом `up`.

### API (FastAPI)
После `docker compose up -d` API доступен на:
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Основные эндпоинты:
- `POST /auth/register` — регистрация (email/phone + пароль)
- `POST /auth/token` — логин (OAuth2 password flow) → JWT
- `GET /me` — текущий пользователь
- `POST /documents` — создать документ (в MVP только пациент создаёт свои)
- `GET /documents` — список доступных документов (учитывает согласия)
- `GET /documents/{id}` — получить документ (проверка `can_read_document`)
- `POST /consents` — выдать согласие (в MVP только пациент)
- `POST /consents/{id}/revoke` — отозвать согласие
- `GET /consents` — список согласий (пациент: выданные; врач: полученные; админ: все)
- `POST /orgs` — создать организацию (org_admin/platform_admin)
- `GET /orgs` — список организаций (мои организации; admin: все)
- `POST /orgs/{org_id}/members` — добавить участника (org_admin админ этой org или platform_admin)
- `GET /orgs/{org_id}/members` — список участников организации
- `GET /audit` — аудит по пациенту (пациент видит свой; platform_admin — по `patient_user_id`)

### Тесты API (pytest)
Интеграционные тесты ходят в запущенный API.

Из папки `MediConnect/api`:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Если API на другом адресе:

```bash
BASE_URL=http://localhost:8000 pytest
```

### Как это использовать (идея)
- Пациент создаёт документ в `documents`.
- Пациент выдаёт доступ врачу через `consents`:
  - либо на конкретный документ (`document_id`)
  - либо “ко всем документам пациента” (`scope = 'all_documents'`)
  - на период времени (`valid_from`, `valid_until`)
- Любое чтение/изменение записывается в `audit_events`.

### Проверка доступа (в БД)
В `db/schema.sql` добавлены функции:
- `can_read_document(actor_user_id, document_id, actor_org_id)` → `boolean`
- `list_accessible_documents(actor_user_id, patient_user_id, actor_org_id)` → таблица документов


