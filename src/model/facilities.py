from src.DataBase import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, UniqueConstraint


class FacilitiesORM(Base):

    __tablename__ = 'facilities'


    id : Mapped[int] = mapped_column(primary_key=True)
    title : Mapped[str] = mapped_column(String(length=100))

    rooms: Mapped[list['RoomsOrm']] = relationship(
        back_populates='facilities',
        secondary='rooms_facilities'
    )



class FacilitiesORMRoom(Base):

    __tablename__ = 'rooms_facilities'
    __table_args__ = (UniqueConstraint('room_id', 'facility_id', name='uq_rooms_facilities_room_facility'),)

    id : Mapped[int] = mapped_column(primary_key=True)
    room_id : Mapped[str] = mapped_column(ForeignKey('rooms.id',ondelete='CASCADE'))
    facility_id : Mapped[int] = mapped_column(ForeignKey('facilities.id',ondelete='CASCADE'))


