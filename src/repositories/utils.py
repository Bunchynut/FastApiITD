from datetime import date

from sqlalchemy import and_, func, select

from src.model.bookings import BookingORM
from src.model.rooms import RoomsOrm


def available_room_ids_for_dates(
    date_from: date,
    date_to: date,
    hotel_id: int | None = None
    ):

    overlapping_stays = (
        select(
            BookingORM.room_id,
            func.greatest(BookingORM.date_from, date_from).label("occupancy_start"),
        )
        .where(BookingORM.date_from < date_to, BookingORM.date_to > date_from)
        .cte("overlapping_stays")
    )
    occupancy_at_starts = (
        select(
            overlapping_stays.c.room_id,
            overlapping_stays.c.occupancy_start,
            func.count(func.distinct(BookingORM.id)).label("rooms_booked"),
        )
        .join(
            BookingORM,
            and_(
                BookingORM.room_id == overlapping_stays.c.room_id,
                BookingORM.date_from <= overlapping_stays.c.occupancy_start,
                BookingORM.date_to > overlapping_stays.c.occupancy_start,
            ),
        )
        .group_by(overlapping_stays.c.room_id, overlapping_stays.c.occupancy_start)
        .cte("occupancy_at_starts")
    )
    peak_occupancy = (
        select(
            occupancy_at_starts.c.room_id,
            func.max(occupancy_at_starts.c.rooms_booked).label("rooms_booked"),
        )
        .group_by(occupancy_at_starts.c.room_id)
        .cte("peak_occupancy")
    )

    room_availability = (
        select(
            RoomsOrm.id.label("room_id"),
            (RoomsOrm.quantity - func.coalesce(peak_occupancy.c.rooms_booked, 0)).label(
                "rooms_left"
            ),
        )
        .select_from(RoomsOrm)
        .outerjoin(peak_occupancy, RoomsOrm.id == peak_occupancy.c.room_id)
        .cte("room_availability")
    )

    hotel_room_ids = select(RoomsOrm.id)
    if hotel_id is not None:
        hotel_room_ids = hotel_room_ids.filter_by(hotel_id=hotel_id)
    return (
        select(room_availability.c.room_id)
        .where(
            room_availability.c.rooms_left > 0,
            room_availability.c.room_id.in_(hotel_room_ids),
        )
    )
