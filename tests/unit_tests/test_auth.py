from datetime import datetime, timezone

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.api.dependencies import get_token, get_current_user
from src.serves import auth as auth_module
from passlib.context import CryptContext


@pytest.fixture
def authentication(monkeypatch):
    fixed_now = datetime(2030, 1, 2, 12, 0, tzinfo=timezone.utc)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(fixed_now.timestamp(), tz)

    monkeypatch.setattr(auth_module, "datetime", FrozenDatetime)
    monkeypatch.setattr(jwt.api_jwt, "datetime", FrozenDatetime)
    monkeypatch.setattr(
        auth_module.settings,
        "JWT_SECRET_KEY",
        "unit-test-signing-key-at-least-32-characters",
    )
    monkeypatch.setattr(auth_module.settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(auth_module.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 5)
    return auth_module.AuthService()


def test_password_hash_is_salted_and_verifies(authentication):
    first = authentication.hashed_password("correct horse")
    second = authentication.hashed_password("correct horse")

    assert first != "correct horse"
    assert first != second
    assert authentication.verify_password("correct horse", first)
    assert authentication.verify_password("correct horse", second)
    assert not authentication.verify_password("wrong password", first)


def test_new_password_hashes_distinguish_passwords_after_bcrypt_limit(authentication):
    common_prefix = "p" * 72
    first = authentication.hashed_password(common_prefix + "first")
    second = authentication.hashed_password(common_prefix + "second")

    assert authentication.verify_password(common_prefix + "first", first)
    assert not authentication.verify_password(common_prefix + "second", first)
    assert authentication.verify_password(common_prefix + "second", second)


def test_new_password_hash_uses_at_least_600000_pbkdf2_rounds(authentication):
    password_hash = authentication.hashed_password("correct horse")

    assert password_hash.startswith("$pbkdf2-sha256$")
    assert int(password_hash.split("$")[2]) >= 600_000
    assert len(password_hash) <= 100
    assert authentication.verify_password("correct horse", password_hash)


def test_legacy_bcrypt_password_hash_still_verifies(authentication):
    legacy_hash = CryptContext(schemes=["bcrypt"]).hash("legacy password")

    assert len(legacy_hash) <= 100
    assert authentication.verify_password("legacy password", legacy_hash)
    assert not authentication.verify_password("different password", legacy_hash)


def test_legacy_bcrypt_hash_rejects_password_with_nul(authentication):
    legacy_hash = CryptContext(schemes=["bcrypt"]).hash("legacy password")

    assert not authentication.verify_password("legacy password\u0000tail", legacy_hash)


async def test_access_token_contains_only_user_id_and_sets_expiry(authentication):
    data = {"user_id": 17, "role": "guest", "exp": 1}

    token = authentication.create_access_token(data)
    decoded = jwt.decode(
        token, auth_module.settings.JWT_SECRET_KEY, algorithms=["HS256"]
    )

    assert decoded == {
        "user_id": 17,
        "exp": int(datetime(2030, 1, 2, 12, 5, tzinfo=timezone.utc).timestamp()),
    }
    assert set(decoded) == {"user_id", "exp"}
    assert authentication.decode_token(token) == decoded
    assert (await get_current_user(db=FakeDB(), token=token)).id == 17


@pytest.mark.parametrize("token", ["not-a-jwt", ""])
def test_malformed_token_returns_unauthorized(authentication, token):
    with pytest.raises(HTTPException) as error:
        authentication.decode_token(token)
    assert error.value.status_code == 401


def test_token_signed_by_another_key_returns_unauthorized(authentication):
    token = jwt.encode(
        {"user_id": 17},
        "another-test-signing-key-at-least-32-characters",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as error:
        authentication.decode_token(token)
    assert error.value.status_code == 401


def test_expired_token_returns_unauthorized(authentication):
    token = jwt.encode(
        {
            "user_id": 17,
            "exp": int(datetime(2030, 1, 2, 11, 59, tzinfo=timezone.utc).timestamp()),
        },
        auth_module.settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as error:
        authentication.decode_token(token)
    assert error.value.status_code == 401


async def test_token_without_user_id_returns_unauthorized(authentication):
    token = authentication.create_access_token({"role": "guest"})
    with pytest.raises(HTTPException) as error:
        await get_current_user(db=FakeDB(), token=token)
    assert error.value.status_code == 401


def test_token_without_expiry_returns_unauthorized(authentication):
    token = jwt.encode(
        {"user_id": 17},
        auth_module.settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as error:
        authentication.decode_token(token)
    assert error.value.status_code == 401


@pytest.mark.parametrize("cookie", [None, "access_token="])
def test_missing_access_cookie_returns_unauthorized(cookie):
    headers = [] if cookie is None else [(b"cookie", cookie.encode())]
    request = Request({"type": "http", "headers": headers})

    with pytest.raises(HTTPException) as error:
        get_token(request)
    assert error.value.status_code == 401


def test_access_cookie_is_read_without_using_other_cookies():
    request = Request(
        {
            "type": "http",
            "headers": [(b"cookie", b"other=value; access_token=token-value")],
        }
    )
    assert get_token(request) == "token-value"


class FakeDB:
    class users:
        @staticmethod
        async def get_one_or_none(**kwargs):
            return type("User", (), {"id": kwargs["id"], "role": "user"})()


@pytest.mark.parametrize("user_id", [None, "17", True, 0, -1, 1.5])
async def test_token_with_invalid_user_id_returns_unauthorized(authentication, user_id):
    token = jwt.encode(
        {"user_id": user_id, "exp": int(datetime(2030, 1, 2, 12, 5, tzinfo=timezone.utc).timestamp())},
        auth_module.settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as error:
        await get_current_user(db=FakeDB(), token=token)
    assert error.value.status_code == 401


def test_token_without_exp_returns_unauthorized(authentication):
    token = jwt.encode(
        {"user_id": 17}, auth_module.settings.JWT_SECRET_KEY, algorithm="HS256"
    )
    with pytest.raises(HTTPException) as error:
        authentication.decode_token(token)
    assert error.value.status_code == 401
