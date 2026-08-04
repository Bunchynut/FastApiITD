from typing import Annotated

from fastapi import Depends, Query, HTTPException, Request
from pydantic import BaseModel

from src.DataBase import async_session_maker
from src.serves.auth import auth
from src.utils.db_manager import DBManager


class PaginationParams(BaseModel):
    page: Annotated[int | None,Query(1,ge=1)]
    per_page: Annotated[int | None,Query(None,ge=1,le=30)]

paginationDep = Annotated[PaginationParams,Depends()]


def get_token(request: Request) -> str:
    token = request.cookies.get('access_token', None)
    if not token:
        raise HTTPException(status_code=401,detail='Вы не предоставили токен доступа')
    return token


def get_user_id(token: str = Depends(get_token)) -> int:
    data = auth().decode_token(token)
    return data['user_id']


UserIdDep = Annotated[int,Depends(get_user_id)]


def get_db_manager():
    return DBManager(session_factory=async_session_maker())


async def get_db():
    async with get_db_manager() as db:
        yield db


DBDep = Annotated[DBManager,Depends(get_db)]