from fastapi import APIRouter, Response, HTTPException
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from src.Schemas.users import UserRegister, UserAdd, UserLogin, UserId
from src.api.dependencies import CurrentUserDep, DatabaseDep
from src.config import settings
from src.serves.auth import AuthService

router = APIRouter(prefix="/users",tags = ["Аутентификация и регистрация"])


@router.post("/login",summary='Вход в систему')
async def login_users(db: DatabaseDep,data: UserLogin,
                      response: Response):
    user = await db.users.get_user_with_hashed(email=data.email)
    if not user:
        raise HTTPException(status_code=401,
                                detail='Пользователя с таким email не существует')
    if not await run_in_threadpool(
        AuthService().verify_password, data.password, user.hashed_password
    ):
        raise HTTPException(status_code=401,
                                detail='Неправильный пароль')
    access_token = AuthService().create_access_token({"user_id": user.id})
    response.set_cookie(
        'access_token',
        access_token,
        httponly=True,
        samesite='lax',
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=settings.MODE == 'PROD',
    )
    return {'access_token': access_token}


@router.post("/auth",summary='Добавить пользователя')
async def post_users(db: DatabaseDep,data: UserRegister):
    hashed_password = await run_in_threadpool(AuthService().hashed_password, data.password)
    new_user_bd = UserAdd(email= data.email, hashed_password= hashed_password, number= data.number, first_name= data.first_name, second_name= data.second_name, sex= data.sex)
    try:
        await db.users.add(new_user_bd)
        await db.commit()
    except IntegrityError as error:
        await db.session.rollback()
        database_error = error.orig
        driver_error = getattr(database_error, "__cause__", None)
        sqlstate = getattr(database_error, "sqlstate", None) or getattr(
            driver_error, "sqlstate", None
        )
        constraint = getattr(database_error, "constraint_name", None) or getattr(
            driver_error, "constraint_name", None
        )
        if sqlstate == "23505" and constraint == "users_email_key":
            raise HTTPException(
                status_code=409, detail="Email already registered"
            ) from error
        raise
    return {'status': 'OK'}


@router.get('/only_auth',summary='Получение данных куки',response_model=UserId)
async def only_auth(user: CurrentUserDep):
    return user


@router.post('/out_system',summary='Выход из системы')
async def out_system(response: Response):
    response.delete_cookie(
        'access_token',
        httponly=True,
        samesite='lax',
        secure=settings.MODE == 'PROD',
    )
    return {'status': 'Ok'}
