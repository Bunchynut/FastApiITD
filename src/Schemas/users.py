from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.model.users import SexEnum, UserRole
from src.Schemas.types import PostgresId, StoredText


class UserRegister(BaseModel):
    email: EmailStr = Field(max_length=100)
    password: str = Field(min_length=1, max_length=4096)
    number: StoredText = Field(max_length=20, pattern=r'^\+?[0-9]{10,15}$')
    first_name: StoredText = Field(max_length=20)
    second_name: StoredText = Field(max_length=20)
    sex: SexEnum
    model_config = ConfigDict(extra="forbid")


class UserAdd(BaseModel):
    email: EmailStr = Field(max_length=100)
    hashed_password: str
    number: StoredText = Field(max_length=20, pattern=r'^\+?[0-9]{10,15}$')
    first_name: StoredText = Field(max_length=20)
    second_name: StoredText = Field(max_length=20)
    sex: SexEnum
    role: UserRole = UserRole.user


class UserId(BaseModel):
    id: PostgresId
    email: EmailStr
    number: str
    first_name: str
    second_name: str
    sex: SexEnum
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=4096)


class UserWithPasswordHash(UserId):
    hashed_password: str


class UserResponse(BaseModel):
    access_token: str
