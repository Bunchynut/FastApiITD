from sqlalchemy import select

from src.Schemas.Schemas import Hotel
from src.model.hotels import HotelOrm
from src.repositories.base import BaseRepository


class HotelsRepositories(BaseRepository):
    model = HotelOrm
    schema = Hotel
    async def get_all(
            self,
            location,
            title,
            id,
            limit,
            offset
    ):
        query = select(HotelOrm)
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
