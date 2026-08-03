from pydantic import BaseModel


class RoomsSchema(BaseModel):
    hotel_id : int
    title: str
    description: str
    price: int
    quantity: int


class RoomsPutSchema(BaseModel):
    title: str
    description: str
    price: int
    quantity: int