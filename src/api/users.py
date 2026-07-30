from fastapi import APIRouter, Response, Request, HTTPException

from src.DataBase import async_session_maker
from src.Schemas.users import UserRegister, UserAdd, UserLogin, UserResponse, UserId
from src.repositories.users import UsersRepository
from src.serves.auth import auth

router = APIRouter(prefix="/users",tags = ["Аутентификация и регистрация"])


@router.post("/login",summary='Вход в систему')
async def login_users(data: UserLogin,
                      response: Response):
    async with async_session_maker() as session:
        user = await UsersRepository(session).get_user_with_hashed(email=data.email)
        if not user:
            raise HTTPException(status_code=401,
                                detail='Пользователя с таким email не существует')
        if not auth().verify_password(data.password, user.hashed_password):
            raise HTTPException(status_code=401,
                                detail='Неправильный пароль')
        access_token = auth().create_access_token({"user_id": user.id})
        response.set_cookie('access_token', access_token)
        return {'access_token': access_token}


@router.post("/auth",summary='Добавить пользователя')
async def post_users(data: UserRegister):
    hashed_password = auth().hashed_password(data.password)
    new_user_bd = UserAdd(email= data.email, hashed_password= hashed_password, number= data.number, first_name= data.first_name, second_name= data.second_name, sex= data.sex)
    async with async_session_maker() as session:
        await UsersRepository(session).add(new_user_bd.model_dump())
        await session.commit()
    return {'status': 'OK'}


@router.get('/only_auth',summary='Получение данных куки',response_model=UserId)
async def only_auth(request: Request):
    access_token = request.cookies.get('access_token', None)
    data = auth().decode_token(access_token)
    user_id = data['user_id']
    async with async_session_maker() as session:
        user = await UsersRepository(session).get_one_or_none(id=user_id)
        return user