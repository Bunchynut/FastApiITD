from pydantic import BaseModel, ConfigDict


class FacilityAdd(BaseModel):
    title: str


class Facility(FacilityAdd):
    id: int

    model_config = ConfigDict(from_attributes=True)


class RoomsFacilityAdd(BaseModel):
    room_id: int
    facility_id: int


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