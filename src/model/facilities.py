from src.DataBase import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey


class FacilitiesORM(Base):

    __tablename__ = 'facilities'


    id : Mapped[int] = mapped_column(primary_key=True)
    title : Mapped[str] = mapped_column(String(length=100))


class FacilitiesORMRoom(Base):

    __tablename__ = 'rooms_facilities'

    id : Mapped[int] = mapped_column(primary_key=True)
    room_id : Mapped[str] = mapped_column(ForeignKey('rooms.id'))
    facility_id : Mapped[int] = mapped_column(ForeignKey('facilities.id'))


