from fastapi import APIRouter, Response, HTTPException

from src.Schemas.users import UserRegister, UserAdd, UserLogin, UserId
from src.api.Dependencied import UserIdDep, DBDep
from src.serves.auth import auth

router = APIRouter(prefix="/users",tags = ["Аутентификация и регистрация"])


@router.post("/login",summary='Вход в систему')
async def login_users(db: DBDep,data: UserLogin,
                      response: Response):
    user = await db.users.get_user_with_hashed(email=data.email)
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
async def post_users(db: DBDep,data: UserRegister):
    hashed_password = auth().hashed_password(data.password)
    new_user_bd = UserAdd(email= data.email, hashed_password= hashed_password, number= data.number, first_name= data.first_name, second_name= data.second_name, sex= data.sex)
    await db.users.add(new_user_bd.model_dump())
    await db.commit()
    return {'status': 'OK'}


@router.get('/only_auth',summary='Получение данных куки',response_model=UserId)
async def only_auth(db: DBDep,user_id: UserIdDep):
    user = await db.users.get_one_or_none(id=user_id)
    return user


@router.post('/out_system',summary='Выход из системы')
async def out_system(response: Response):
    response.delete_cookie('access_token')
    return {'status': 'Ok'}