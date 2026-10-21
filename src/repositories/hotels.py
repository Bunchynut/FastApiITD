from datetime import date
from sqlalchemy import select

from src.Schemas.Schemas import Hotel
from src.model.hotels import HotelOrm
from src.model.rooms import RoomsOrm
from src.repositories.base import BaseRepository
from src.repositories.mappers.mapper import HotelDataMapper
from src.repositories.utils import available_room_ids_for_dates


class HotelsRepositories(BaseRepository):
    model = HotelOrm
    mapper = HotelDataMapper

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
        available_room_ids_query = available_room_ids_for_dates(
            date_from=date_from, date_to=date_to
        )
        hotels_ids_to_get = (
            select(RoomsOrm.hotel_id)
            .select_from(RoomsOrm)
            .filter(RoomsOrm.id.in_(available_room_ids_query))
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
            .order_by(HotelOrm.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
