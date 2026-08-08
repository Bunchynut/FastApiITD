from src.Schemas.rooms import RoomsId
from datetime import date


from src.repositories.base import BaseRepository
from src.model.rooms import RoomsOrm
from src.repositories.utils import rooms_ids_from_booking


class RoomsRepositories(BaseRepository):
    model = RoomsOrm
    schema = RoomsId

    async def get_filtered_by_time(
            self,
            hotel_id: int,
            date_from: date,
            date_to: date,
    ):
        rooms_ids_to_get = rooms_ids_from_booking(date_from=date_from, date_to=date_to, hotel_id=hotel_id)

        return await self.get_filtered(RoomsOrm.id.in_(rooms_ids_to_get),RoomsOrm.hotel_id == hotel_id)