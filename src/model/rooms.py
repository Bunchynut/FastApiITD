from src.DataBase import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import CheckConstraint, ForeignKey, String


class RoomsOrm(Base):

    __tablename__ = 'rooms'
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_rooms_price_nonnegative"),
        CheckConstraint("quantity >= 0", name="ck_rooms_quantity_nonnegative"),
    )


    id : Mapped[int] = mapped_column(primary_key=True)
    hotel_id : Mapped[int] = mapped_column(ForeignKey('hotels.id'))
    title: Mapped[str] = mapped_column(String(length=100))
    description: Mapped[str | None] = mapped_column(String(length=100))
    price: Mapped[int]
    quantity: Mapped[int]

    facilities: Mapped[list['FacilitiesORM']] = relationship(
        back_populates='rooms',
        secondary='rooms_facilities',
    )


