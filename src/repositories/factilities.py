
from sqlalchemy import select, insert, delete

from src.model.facilities import FacilitiesORM, FacilitiesORMRoom
from src.repositories.base import BaseRepository
from src.Schemas.facilities import FacilityAdd, RoomsFacility
from src.repositories.mappers.mapper import FacilityDataMapper


class FacilitiesRepository(BaseRepository):
    model = FacilitiesORM
    mapper = FacilityDataMapper


class RoomsFacilitiesRepository(BaseRepository):
    model = FacilitiesORMRoom
    schema =  RoomsFacility

    async def set_rooms_facility(self,room_id :int, facilities_ids: list[int]):
        query = select(self.model.facility_id).filter_by(room_id=room_id)
        res = await self.session.execute(query)
        current_facilities_ids: list[int] = res.scalars().all()
        re_del: list[int] = list(set(current_facilities_ids) - set(facilities_ids))
        re_ins: list[int] = list(set(facilities_ids) - set(current_facilities_ids))
        if re_del:
            facilities_ids_stmt = (
                delete(self.model)
                       .filter(
                    self.model.room_id == room_id,
                    self.model.facility_id.in_(re_del)
            ))
            await self.session.execute(facilities_ids_stmt)
        if re_ins:
            facilities_ids_ins = (insert(self.model)
                                  .values([{'room_id': room_id, 'facility_id': f_id} for f_id in re_ins]))
            await self.session.execute(facilities_ids_ins)