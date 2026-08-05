from dataclasses import Field

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.model.users import SexEnum


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    number: str
    first_name: str
    second_name: str
    sex: SexEnum


class UserAdd(BaseModel):
    email: EmailStr
    hashed_password: str
    number: str = Field(pattern=r'^\+?[0-9]{10,15}$')
    first_name: str
    second_name: str
    sex: SexEnum


class UserId(BaseModel):
    id: int
    email: EmailStr
    number: str
    first_name: str
    second_name: str
    sex: SexEnum
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password:str


class UserId_With_Hashed(UserId):
    hashed_password: str


class UserResponse(BaseModel):
    access_token: str