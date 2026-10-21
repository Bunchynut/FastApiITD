from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.Schemas.facilities import Facility
from src.Schemas.types import PostgresId, StoredText


class RoomsAdd(BaseModel):
    hotel_id : PostgresId
    title: StoredText = Field(max_length=100)
    description: StoredText | None = Field(None, max_length=100)
    price: int = Field(ge=0, le=2147483647)
    quantity: int = Field(ge=0, le=2147483647)
    facilities_ids: list[int] = Field(default_factory=list)


class RoomsCreateData(BaseModel):
    hotel_id: PostgresId
    title: StoredText = Field(max_length=100)
    description: StoredText | None = Field(None, max_length=100)
    price: int = Field(ge=0, le=2147483647)
    quantity: int = Field(ge=0, le=2147483647)


class RoomsTestMain(BaseModel):
    hotel_id: PostgresId
    title: StoredText
    description: StoredText | None = Field(None, max_length=100)
    price: int
    quantity: int

class RoomsId(RoomsAdd):
    id: PostgresId

    model_config = ConfigDict(from_attributes=True)


class RoomsPutSchema(BaseModel):
    title: StoredText = Field(max_length=100)
    description: StoredText | None = Field(max_length=100)
    price: int = Field(ge=0, le=2147483647)
    quantity: int = Field(ge=0, le=2147483647)


class PutRoomsPutSchema(BaseModel):
    title: StoredText = Field(max_length=100)
    description: StoredText | None = Field(max_length=100)
    price: int = Field(ge=0, le=2147483647)
    quantity: int = Field(ge=0, le=2147483647)
    facilities_ids: list[int] = Field(default_factory=list)


class RoomsPatchSchema(BaseModel):
    title: Optional[StoredText] = Field(None, max_length=100)
    description: Optional[StoredText] = Field(None, max_length=100)
    price: Optional[int] = Field(None, ge=0, le=2147483647)
    quantity: Optional[int] = Field(None, ge=0, le=2147483647)
    facilities_ids: list[int] = Field(default_factory=list)

    @field_validator("title", "price", "quantity", mode="before")
    @classmethod
    def reject_null_non_nullable_fields(cls, value):
        if value is None:
            raise ValueError("Field may not be null")
        return value


class SchemaWithRels(BaseModel):
    facilities: list[Facility]
