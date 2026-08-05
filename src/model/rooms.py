from src.DataBase import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String,ForeignKey


class RoomsOrm(Base):

    __tablename__ = 'rooms'


    id : Mapped[int] = mapped_column(primary_key=True)
    hotel_id : Mapped[int] = mapped_column(ForeignKey('hotels.id'))
    title: Mapped[str] = mapped_column(String(length=100))
    description: Mapped[str | None] = mapped_column(String(length=100))
    price: Mapped[int]
    quantity: Mapped[int]



