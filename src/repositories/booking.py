from datetime import date

from src.model.bookings import BookingORM
from src.model.rooms import RoomsOrm
from src.repositories.base import BaseRepository
from src.Schemas.booking import BookingId, BookingAdd
from sqlalchemy import select
from src.repositories.mappers.mapper import BookingDataMapper
from src.repositories.utils import available_room_ids_for_dates


class BookingRepository(BaseRepository):
    model = BookingORM
    mapper = BookingDataMapper

    async def get_booking_today_checkin(self):
        query = (
            select(BookingORM).
            filter(BookingORM.date_from == date.today())
        )
        res = await self.session.execute(query)
        return [self.mapper.map_to_domain_entity(booking) for booking in res.scalars().all()]

    async def add_booking(self, data: BookingAdd, hotel_id: int):
        room = await self.session.scalar(
            select(RoomsOrm).where(RoomsOrm.id == data.room_id).with_for_update()
        )
        if room is None:
            raise RoomUnavailableError

        available_room_ids_query = available_room_ids_for_dates(
            date_from=data.date_from,
            date_to=data.date_to,
            hotel_id=hotel_id
        )
        availability_result = await self.session.execute(available_room_ids_query)
        available_room_ids = availability_result.scalars().all()
        if data.room_id in available_room_ids:
            new_booking = await self.add(data)
            return new_booking
        raise RoomUnavailableError


class RoomUnavailableError(Exception):
    pass
