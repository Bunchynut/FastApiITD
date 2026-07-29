from src.DataBase import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Enum as sqlalchemyEnum
from enum import Enum

class SexEnum(str, Enum):
    male = 'male'
    female = 'female'

class UsersOrm(Base):

    __tablename__ = "users"


    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(length=100),unique=True)
    hashed_password: Mapped[str] = mapped_column(String(length=100))
    number: Mapped[str] = mapped_column(String(length=20))
    first_name: Mapped[str] = mapped_column(String(length=20))
    second_name: Mapped[str] = mapped_column(String(length=20))
    sex: Mapped[SexEnum] = mapped_column(String(length=10))