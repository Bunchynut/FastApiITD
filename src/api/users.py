from fastapi import APIRouter
from src.DataBase import async_session_maker
from src.Schemas.users import UserRequests, UserAdd
from src.repositories.users import UsersRepository

from passlib.context import CryptContext
router = APIRouter(prefix="/users",tags = ["Аутентификация и регистрация"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated='auto')

@router.post("/auth")
async def post_users(data: UserRequests):
    hashed_password = pwd_context.hash(data.password)
    new_user_bd = UserAdd(email= data.email, hashed_password= hashed_password, number= data.number, first_name= data.first_name, second_name= data.second_name, sex= data.sex)
    async with async_session_maker() as session:
        await UsersRepository(session).add(new_user_bd.model_dump())
        await session.commit()
    return {'status': 'OK'}