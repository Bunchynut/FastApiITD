from src.DataBase import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Enum as sqlalchemyEnum
from enum import Enum

class SexEnum(str, Enum):
    male = 'male'
    female = 'female'

class UserRole(str, Enum):
    user = 'user'
    admin = 'admin'

class UsersOrm(Base):

    __tablename__ = "users"


    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(length=100),unique=True)
    hashed_password: Mapped[str] = mapped_column(String(length=100))
    number: Mapped[str] = mapped_column(String(length=20))
    first_name: Mapped[str] = mapped_column(String(length=20))
    second_name: Mapped[str] = mapped_column(String(length=20))
    sex: Mapped[SexEnum] = mapped_column(String(length=10))
    role: Mapped[UserRole] = mapped_column(
        sqlalchemyEnum(
            UserRole,
            name='user_role',
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=UserRole.user,
        server_default=UserRole.user.value,
    )
