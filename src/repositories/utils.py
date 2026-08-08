from datetime import date

from sqlalchemy import select, func

from src.model.bookings import BookingORM
from src.model.rooms import RoomsOrm


def rooms_ids_from_booking(
    date_from: date,
    date_to: date,
    hotel_id: int | None = None
    ):

    rooms_count = (
    select(BookingORM.room_id, func.count("*").label("rooms_booked"))
    .select_from(BookingORM)
    .filter(
        BookingORM.date_from <= date_to,
        BookingORM.date_to >= date_from,
    )
    .group_by(BookingORM.room_id)
    .cte(name="rooms_count")
    )

    rooms_left_table = (
    select(
        RoomsOrm.id.label("room_id"),
        (RoomsOrm.quantity - func.coalesce(rooms_count.c.rooms_booked, 0)).label("rooms_left"),
    )
    .select_from(RoomsOrm)
    .outerjoin(rooms_count, RoomsOrm.id == rooms_count.c.room_id)
    .cte(name="rooms_left_table")
    )

    rooms_ids_for_hotel = (
    select(RoomsOrm.id)
    .select_from(RoomsOrm))
    if hotel_id is not None:
        rooms_ids_for_hotel = rooms_ids_for_hotel.filter_by(hotel_id=hotel_id)
    rooms_ids_for_hotel = (rooms_ids_for_hotel
    .subquery(name="rooms_ids_for_hotel")
    )

    rooms_ids_to_get = (
    select(rooms_left_table.c.room_id)
    .select_from(rooms_left_table)
    .filter(
        rooms_left_table.c.rooms_left > 0,
        rooms_left_table.c.room_id.in_(rooms_ids_for_hotel),
    )
    )

    return rooms_ids_to_get