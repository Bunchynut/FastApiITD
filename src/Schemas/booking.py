from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator
from src.Schemas.types import PostgresId


class BookingAdd(BaseModel):
    date_from: date
    date_to: date
    price: int
    user_id: PostgresId
    room_id: PostgresId
class BookingId(BookingAdd):
    id: PostgresId

    model_config = ConfigDict(from_attributes=True)


class AddBookingRequest(BaseModel):
    room_id: PostgresId
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_to <= self.date_from:
            raise ValueError("date_to must be later than date_from")
        return self


class BookingGet(BaseModel):
    id: PostgresId
