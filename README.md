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
│   ├── users/
│   ├── hotels/
│   ├── rooms/
│   ├── bookings/
│   ├── facilities/
│   ├── images/
│   ├── DataBase.py
│   └── FastApiOb.py
│
├── tests/
├── migrations/
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

---

# Тестирование

Для тестирования API используются:

* Pytest
* HTTPX
* AsyncClient
* ASGITransport

Для тестов используется отдельная тестовая база данных.

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

JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
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

Документация ReDoc:

```text
http://127.0.0.1:8000/redoc
```

---

# API

В проекте реализованы отдельные API-модули:

```text
/users
/hotels
/rooms
/bookings
/facilities
/images
```

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
