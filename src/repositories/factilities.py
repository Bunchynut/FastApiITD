from src.model.facilities import FacilitiesORM, FacilitiesORMRoom
from src.repositories.base import BaseRepository
from src.Schemas.facilities import FacilityAdd, RoomsFacility


class FacilitiesRepository(BaseRepository):
    model = FacilitiesORM
    schema = FacilityAdd


class RoomsFacilitiesRepository(BaseRepository):
    model = FacilitiesORMRoom
    schema =  RoomsFacility