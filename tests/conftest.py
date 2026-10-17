import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env-test", override=False)

for key, value in {
    "MODE": "TEST",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_USER": "postgres",
    "DB_PASS": "test",
    "DB_NAME": "hotels_test",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "JWT_SECRET_KEY": "test-only-secret-key-with-at-least-32-bytes",
    "JWT_ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
}.items():
    os.environ.setdefault(key, value)


def pytest_collection_modifyitems(items):
    for item in items:
        if "integration_tests" in item.path.parts:
            item.add_marker(pytest.mark.integration)
        elif "unit_tests" in item.path.parts:
            item.add_marker(pytest.mark.unit)


@pytest.fixture
def user_data():
    return {
        "email": "user@example.com",
        "password": "string",
        "number": "+79999999999",
        "first_name": "string",
        "second_name": "string",
        "sex": "male",
    }
