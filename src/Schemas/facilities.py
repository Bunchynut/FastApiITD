from pydantic import BaseModel, ConfigDict, Field
from src.Schemas.types import PostgresId, StoredText


class FacilityAdd(BaseModel):
    title: StoredText = Field(max_length=100)


class Facility(FacilityAdd):
    id: PostgresId

    model_config = ConfigDict(from_attributes=True)


class RoomsFacilityAdd(BaseModel):
    room_id: PostgresId
    facility_id: PostgresId


class RoomsFacility(RoomsFacilityAdd):
    id: int

class RoomWithFacilities(BaseModel):
    id: int
    hotel_id: int
    title: str
    description: str | None = None
    price: int
    quantity: int
    facilities: list[Facility]
