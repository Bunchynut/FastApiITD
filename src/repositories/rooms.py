from sqlalchemy import select

from src.Schemas.facilities import RoomWithFacilities
from src.Schemas.rooms import RoomsId
from datetime import date
from sqlalchemy.orm import joinedload

from src.repositories.base import BaseRepository
from src.model.rooms import RoomsOrm
from src.repositories.mappers.mapper import RoomDataMapper
from src.repositories.utils import available_room_ids_for_dates


class RoomsRepositories(BaseRepository):
    model = RoomsOrm
    mapper = RoomDataMapper
    async def get_filtered_by_time(
            self,
            hotel_id: int,
            date_from: date,
            date_to: date,
    ):
        available_room_ids_query = available_room_ids_for_dates(
            date_from=date_from, date_to=date_to, hotel_id=hotel_id
        )

        query = select(self.model).options(joinedload(self.model.facilities)).filter(
            RoomsOrm.id.in_(available_room_ids_query)
        )
        result = await self.session.execute(query)
        return [RoomWithFacilities.model_validate(model,from_attributes=True) for model in result.unique().scalars().all()]


    async def get_one_or_none_with_option(self, **filter_by):
        query = select(self.model).options(joinedload(self.model.facilities)).filter_by(**filter_by)
        result = await self.session.execute(query)
        res = result.unique().scalars().one_or_none()
        if res is None:
            return None
        return res
