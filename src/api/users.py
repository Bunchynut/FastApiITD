from fastapi import APIRouter, Response, HTTPException

from src.Schemas.users import UserRegister, UserAdd, UserLogin, UserId
from src.api.dependencies import DatabaseDep, CurrentUserDep
from src.serves.auth import AuthService

router = APIRouter(prefix="/users",tags = ["Аутентификация и регистрация"])


@router.post("/login",summary='Вход в систему')
async def login_users(db: DatabaseDep,data: UserLogin,
                      response: Response):
    user = await db.users.get_user_with_hashed(email=data.email)
    if not user:
        raise HTTPException(status_code=401,
                                detail='Пользователя с таким email не существует')
    if not AuthService().verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401,
                                detail='Неправильный пароль')
    access_token = AuthService().create_access_token({"user_id": user.id})
    response.set_cookie('access_token', access_token)
    return {'access_token': access_token}


@router.post("/auth",summary='Добавить пользователя')
async def register_user(db: DatabaseDep,data: UserRegister):
    hashed_password = AuthService().hashed_password(data.password)
    new_user_bd = UserAdd(email= data.email, hashed_password= hashed_password, number= data.number, first_name= data.first_name, second_name= data.second_name, sex= data.sex)
    await db.users.add(new_user_bd)
    await db.commit()
    return {'status': 'OK'}


@router.get('/only_auth',summary='Получение данных куки',response_model=UserId)
async def get_current_user_profile(user: CurrentUserDep):
    return user


@router.post('/out_system',summary='Выход из системы')
async def out_system(response: Response):
    response.delete_cookie('access_token')
    return {'status': 'Ok'}