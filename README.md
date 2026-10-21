# FastApiITD

Backend REST API для сервиса бронирования отелей, разработанный на **FastAPI**, **PostgreSQL** и **SQLAlchemy**.

Проект демонстрирует работу с асинхронным backend-приложением, базой данных, миграциями, авторизацией, кешированием и API-тестами.

---

# Стек технологий

* Python
* FastAPI
* PostgreSQL
* SQLAlchemy 2.0
* AsyncPG
* Alembic
* Pydantic
* JWT
* Redis
* FastAPI Cache
* Pytest
* HTTPX

---

# Возможности проекта

API реализует работу с:

* пользователями
* авторизацией
* отелями
* комнатами
* бронированиями
* удобствами отелей
* изображениями

В проекте используется асинхронная работа с базой данных и разделение логики приложения по отдельным модулям.

---

# Структура проекта

```text
FastApiITD/
├── src/
│   ├── api/
│   ├── Schemas/
│   ├── model/
│   ├── repositories/
│   ├── migrations/
│   ├── serves/
│   ├── tasks/
│   ├── static/images/
│   ├── DataBase.py
│   └── FastApiOb.py
│
├── tests/
├── alembic.ini
├── pytest.ini
├── requirements.txt
├── .gitignore
└── README.md
```

---

# Авторизация

Авторизация пользователей реализована с использованием **JWT-токенов**.

Пользователь может зарегистрироваться и авторизоваться в приложении.

Для защищённых эндпоинтов используется проверка JWT-токена.
Новые пароли хранятся с PBKDF2-SHA256; старые bcrypt-хеши остаются совместимыми.

После входа приложение проверяет роль пользователя в PostgreSQL. Новые
аккаунты получают роль `user`; создание и изменение отелей, номеров,
удобств, загрузка изображений и просмотр всех бронирований доступны роли
`admin`. Чтобы назначить первого администратора, зарегистрируйте пользователя
и выполните в PostgreSQL:

```sql
UPDATE users SET role = 'admin' WHERE email = 'admin@example.com';
```

---

# База данных

В качестве основной базы данных используется **PostgreSQL**.

Работа с БД реализована асинхронно с помощью:

* SQLAlchemy
* AsyncPG

Для управления изменениями структуры базы данных используется **Alembic**.

Применение миграций:

```bash
alembic upgrade head
```

---

# Redis

Redis используется для кеширования данных приложения.

Для работы с кешем используется **FastAPI Cache**.

Redis также используется как брокер Celery и должен быть доступен по
`REDIS_HOST` и `REDIS_PORT` во время работы приложения и фоновых задач.
Если Redis установлен в Ubuntu WSL, откройте `wsl -d Ubuntu` и оставьте
терминал запущенным. Команда `redis-cli ping` внутри Ubuntu должна вернуть `PONG`.

Для обработки изображений отдельно запустите worker из корня проекта
с активированным виртуальным окружением. Для локального запуска на Windows:

```bash
python -m celery -A src.tasks.celery_app:celery_app worker --pool=solo --loglevel=INFO
```

---

# Тестирование

Для тестирования API используются:

* Pytest
* HTTPX
* AsyncClient
* ASGITransport

Для интеграционных тестов используется отдельная схема в тестовой PostgreSQL и откат данных после каждого теста. Unit-тесты не требуют внешних сервисов. Установка, команды запуска и ограничения проверок описаны в [tests/README.md](tests/README.md).

Запуск тестов:

```bash
pytest
```

---

# Установка

## 1. Клонирование репозитория

```bash
git clone https://github.com/Bunchynut/FastApiITD.git
cd FastApiITD
```

## 2. Создание виртуального окружения

```bash
python -m venv .venv
```

## 3. Активация виртуального окружения

Windows:

```bash
.venv\Scripts\activate
```

## 4. Установка зависимостей

```bash
pip install -r requirements.txt
```

---

# Переменные окружения

Создайте файл `.env` в корне проекта.

Пример конфигурации:

```env
MODE=DEV

DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASS=your_password
DB_NAME=hotels

REDIS_HOST=localhost
REDIS_PORT=6379

JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Файлы `.env`, содержащие пароли и секретные ключи, не должны добавляться в Git.

Для примера конфигурации рекомендуется использовать файл `.env.example`.

---

# Запуск приложения

Запуск FastAPI:

```bash
fastapi dev src/FastApiOb.py
```

После запуска Swagger UI будет доступен по адресу:

```text
http://127.0.0.1:8000/docs
```

ReDoc отключён.

---

# API

В проекте реализованы отдельные API-модули:

```text
/users
/hotels
/rooms
/booking
/facilities
/images
```

Загруженные оригиналы хранятся в `src/static/images`, а варианты изображений —
в подкаталоге `src/static/images/thumbnails`.

Подробное описание эндпоинтов доступно через Swagger UI после запуска приложения.

---

# Что демонстрирует проект

Проект показывает навыки работы с:

* REST API на FastAPI
* асинхронным Python
* PostgreSQL
* SQLAlchemy ORM
* репозиторным подходом к работе с БД
* Pydantic
* JWT-авторизацией
* Alembic
* Redis
* кешированием
* API-тестированием
* переменными окружения
* конфигурацией приложения

---

# Автор

**Кирилл Туркин**

GitHub: [Bunchynut](https://github.com/Bunchynut)
