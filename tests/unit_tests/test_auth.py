from datetime import datetime, timezone

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.api.Dependencied import get_token, get_user_id
from src.serves import auth as auth_module


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
    return auth_module.auth()


def test_password_hash_is_salted_and_verifies(authentication):
    first = authentication.hashed_password("correct horse")
    second = authentication.hashed_password("correct horse")

    assert first != "correct horse"
    assert first != second
    assert authentication.verify_password("correct horse", first)
    assert authentication.verify_password("correct horse", second)
    assert not authentication.verify_password("wrong password", first)


def test_access_token_preserves_payload_and_sets_expiry(authentication):
    data = {"user_id": 17, "role": "guest", "exp": 1}

    token = authentication.create_access_token(data)
    decoded = jwt.decode(
        token, auth_module.settings.JWT_SECRET_KEY, algorithms=["HS256"]
    )

    assert data == {"user_id": 17, "role": "guest", "exp": 1}
    assert decoded == {
        "user_id": 17,
        "role": "guest",
        "exp": int(datetime(2030, 1, 2, 12, 5, tzinfo=timezone.utc).timestamp()),
    }
    assert authentication.decode_token(token) == decoded
    assert get_user_id(token) == 17


@pytest.mark.parametrize("token", ["not-a-jwt", ""])
@pytest.mark.xfail(
    strict=True,
    raises=TypeError,
    reason="auth.decode_token imports aiohttp.HTTPException, which rejects status_code/detail",
)
def test_malformed_token_returns_unauthorized(authentication, token):
    with pytest.raises(HTTPException) as error:
        authentication.decode_token(token)
    assert error.value.status_code == 401


@pytest.mark.xfail(
    strict=True,
    raises=TypeError,
    reason="Invalid signature reaches the incompatible aiohttp.HTTPException constructor",
)
def test_token_signed_by_another_key_returns_unauthorized(authentication):
    token = jwt.encode(
        {"user_id": 17},
        "another-test-signing-key-at-least-32-characters",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as error:
        authentication.decode_token(token)
    assert error.value.status_code == 401


@pytest.mark.xfail(
    strict=True,
    raises=jwt.ExpiredSignatureError,
    reason="auth.decode_token does not handle ExpiredSignatureError",
)
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


@pytest.mark.xfail(
    strict=True,
    raises=KeyError,
    reason="get_user_id indexes user_id without validating the JWT payload",
)
def test_token_without_user_id_returns_unauthorized(authentication):
    token = authentication.create_access_token({"role": "guest"})
    with pytest.raises(HTTPException) as error:
        get_user_id(token)
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
