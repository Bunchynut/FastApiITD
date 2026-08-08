from pydantic import BaseModel, ConfigDict


class RoomsAdd(BaseModel):
    hotel_id : int
    title: str
    description: str
    price: int
    quantity: int
    facilities_ids: list[int] | None = None

class RoomsId(RoomsAdd):
    id: int

    model_config = ConfigDict(from_attributes=True)


class RoomsPutSchema(BaseModel):
    title: str
    description: str
    price: int
    quantity: int