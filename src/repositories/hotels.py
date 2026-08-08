from datetime import date

from sqlalchemy import select

from src.Schemas.Schemas import Hotel
from src.model.hotels import HotelOrm
from src.model.rooms import RoomsOrm
from src.repositories.base import BaseRepository
from src.repositories.utils import rooms_ids_from_booking


class HotelsRepositories(BaseRepository):
    model = HotelOrm
    schema = Hotel

    async def get_filtered_by_time(
            self,
            date_from: date,
            date_to: date,
            location,
            title,
            id,
            limit,
            offset
    ) -> list[Hotel]:
        rooms_ids_to_get = rooms_ids_from_booking(date_from=date_from, date_to=date_to)
        hotels_ids_to_get = (
            select(RoomsOrm.hotel_id)
            .select_from(RoomsOrm)
            .filter(RoomsOrm.id.in_(rooms_ids_to_get))
        )

        query = select(HotelOrm).filter(HotelOrm.id.in_(hotels_ids_to_get))
        if id is not None:
            query = query.filter_by(id=id)
        if title:
            query = query.filter(HotelOrm.title.ilike(f'%{title}%'))
        if location:
            query = query.filter(HotelOrm.location.ilike(f'%{location}%'))
        query = (
            query
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()