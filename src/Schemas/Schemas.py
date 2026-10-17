from pydantic import BaseModel, Field, ConfigDict


class HotelPost(BaseModel):
    title: str
    location: str


class Hotel(HotelPost):
    id: int

class HotelPatch(BaseModel):
    title: str | None = Field(None),
    location: str | None = Field(None)


class GetHotel(BaseModel):
    id: int
    title: str | None = Field(None)
    location: str | None = Field(None)