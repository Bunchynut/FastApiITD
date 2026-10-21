from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException
from passlib.context import CryptContext
from passlib.exc import PasswordValueError

from src.config import settings


class AuthService:
    pwd_context = CryptContext(
        schemes=["pbkdf2_sha256", "bcrypt"],
        deprecated="auto",
        pbkdf2_sha256__default_rounds=600_000,
    )

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except PasswordValueError:
            return False

    def create_access_token(self, data: dict) -> str:
        to_encode = {"user_id": data.get("user_id")}
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        to_encode["exp"] = expire
        return jwt.encode(
            to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

    def hashed_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    def decode_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"require": ["exp", "user_id"]},
            )
        except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError) as error:
            raise HTTPException(status_code=401, detail="Неверный токен") from error
        if (
            type(payload["user_id"]) is not int
            or not 1 <= payload["user_id"] <= 2147483647
        ):
            raise HTTPException(status_code=401, detail="Неверный токен")
        return payload
