from datetime import date

from pydantic import BaseModel, ConfigDict


class BookingAdd(BaseModel):
    date_from: date
    date_to: date
    price: int
    user_id: int
    room_id: int
class BookingId(BookingAdd):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AddBookingRequest(BaseModel):
    room_id: int
    date_from: date
    date_to: date


class BookingGet(BaseModel):
    id: int
