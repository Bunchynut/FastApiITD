from pydantic import BaseModel, Field, ConfigDict


class HotelPost(BaseModel):
    title: str
    location: str


class Hotel(HotelPost):
    id: int
    model_config = ConfigDict(from_attributes=True)

class HotelPatch(BaseModel):
    title: str | None = Field(None),
    location: str | None = Field(None)