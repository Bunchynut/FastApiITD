from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from src.Schemas.facilities import Facility


class RoomsAdd(BaseModel):
    hotel_id : int
    title: str | None = None
    description: str | None = None
    price: int | None = None
    quantity: int | None = None
    facilities_ids: list[int] | None = None


class RoomsTestMain(BaseModel):
    hotel_id: int
    title: str | None = None
    description: str | None = None
    price: int | None = None
    quantity: int | None = None

class RoomsId(RoomsAdd):
    id: int

    model_config = ConfigDict(from_attributes=True)


class RoomsPutSchema(BaseModel):
    title: str
    description: str
    price: int
    quantity: int


class PutRoomsPutSchema(BaseModel):
    title: str
    description: str
    price: int
    quantity: int
    facilities_ids: list[int] =  []


class RoomsPatchSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    quantity: Optional[int] = None
    facilities_ids: Optional[list[int]] = None


class SchemaWithRels(BaseModel):
    facilities: list[Facility]