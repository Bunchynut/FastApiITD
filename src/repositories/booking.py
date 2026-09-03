from datetime import date

from src.model.bookings import BookingORM
from src.repositories.base import BaseRepository
from src.Schemas.booking import BookingId
from sqlalchemy import select
from src.repositories.mappers.mapper import BookingDataMapper


class BookingRepository(BaseRepository):
    model = BookingORM
    schema = BookingDataMapper

    async def get_booking_today_checkin(self):
        query = (
            select(BookingORM).
            filter(BookingORM.date_from == date.today())
        )
        res = await self.session.execute(query)
        return [self.mapper.map_to_domain_entity(booking) for booking in res.scalars().all()]