from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel

from src.DataBase import async_session_maker
from src.model.users import UsersOrm
from src.serves.auth import AuthService
from src.utils.db_manager import DBManager


class PaginationParams(BaseModel):
    page: Annotated[int, Query(1, ge=1)]
    per_page: Annotated[int | None, Query(None, ge=1, le=30)]


PaginationDep = Annotated[PaginationParams, Depends()]


def get_token(request: Request) -> str:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Вы не предоставили токен доступа")
    return token


async def get_current_user(
    db: "DatabaseDep", token: str = Depends(get_token)
) -> UsersOrm:
    data = AuthService().decode_token(token)
    user = await db.users.get_one_or_none(id=data["user_id"])
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


CurrentUserDep = Annotated[UsersOrm, Depends(get_current_user)]


async def get_user_id(current_user: CurrentUserDep) -> int:
    return current_user.id


CurrentUserIdDep = Annotated[int, Depends(get_user_id)]


async def require_admin(current_user: CurrentUserDep) -> UsersOrm:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return current_user


def get_db_manager() -> DBManager:
    return DBManager(session_factory=async_session_maker)


async def get_db():
    async with get_db_manager() as db:
        yield db


DatabaseDep = Annotated[DBManager, Depends(get_db)]
