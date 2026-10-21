from pydantic import BaseModel, Field, ConfigDict, field_validator
from src.Schemas.types import PostgresId, StoredText


class HotelPost(BaseModel):
    title: StoredText = Field(max_length=100)
    location: StoredText = Field(max_length=100)


class Hotel(HotelPost):
    id: PostgresId

class HotelPatch(BaseModel):
    title: StoredText | None = Field(None, max_length=100)
    location: StoredText | None = Field(None, max_length=100)

    @field_validator("title", "location", mode="before")
    @classmethod
    def reject_null_non_nullable_fields(cls, value):
        if value is None:
            raise ValueError("Field may not be null")
        return value


class GetHotel(BaseModel):
    id: PostgresId
    title: StoredText | None = Field(None)
    location: StoredText | None = Field(None)
