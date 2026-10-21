import asyncio
from datetime import date
from uuid import uuid4

from sqlalchemy import delete, event, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.Schemas.booking import BookingAdd
from src.model.bookings import BookingORM
from src.model.hotels import HotelOrm
from src.model.rooms import RoomsOrm
from src.model.users import SexEnum, UsersOrm
from src.repositories.booking import BookingRepository, RoomUnavailableError


async def test_concurrent_reservations_do_not_oversell(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid4().hex
    async with session_factory.begin() as session:
        hotel = HotelOrm(title=f"Hotel {suffix}", location="Test")
        user = UsersOrm(
            email=f"{suffix}@example.com",
            hashed_password="test-hash",
            number="+79999999999",
            first_name="Test",
            second_name="Guest",
            sex=SexEnum.male,
        )
        session.add_all([hotel, user])
        await session.flush()
        room = RoomsOrm(
            hotel_id=hotel.id,
            title=f"Room {suffix}",
            description=None,
            price=100,
            quantity=1,
        )
        session.add(room)
        await session.flush()
        hotel_id, user_id, room_id = hotel.id, user.id, room.id

    first_session = session_factory()
    second_session = session_factory()
    waiting_for_room_lock = asyncio.Event()
    listener_registered = False
    second_reservation = None

    def detect_room_lock(_connection, _cursor, statement, _parameters, _context, _many):
        if "FOR UPDATE" in statement.upper():
            waiting_for_room_lock.set()

    async def reserve_in_second_session():
        data = BookingAdd(
            room_id=room_id,
            user_id=user_id,
            price=100,
            date_from=date(2030, 1, 1),
            date_to=date(2030, 1, 3),
        )
        try:
            await BookingRepository(second_session).add_booking(data, hotel_id=hotel_id)
            await second_session.commit()
            return True
        except RoomUnavailableError:
            await second_session.rollback()
            return False

    try:
        await first_session.execute(
            select(RoomsOrm).where(RoomsOrm.id == room_id).with_for_update()
        )
        first_session.add(
            BookingORM(
                room_id=room_id,
                user_id=user_id,
                price=100,
                date_from=date(2030, 1, 1),
                date_to=date(2030, 1, 3),
            )
        )
        await first_session.flush()

        event.listen(test_engine.sync_engine, "before_cursor_execute", detect_room_lock)
        listener_registered = True
        second_reservation = asyncio.create_task(reserve_in_second_session())
        await asyncio.wait_for(waiting_for_room_lock.wait(), timeout=5)
        await first_session.commit()
        assert await asyncio.wait_for(second_reservation, timeout=5) is False
    finally:
        if listener_registered:
            event.remove(
                test_engine.sync_engine, "before_cursor_execute", detect_room_lock
            )
        if first_session.in_transaction():
            await first_session.rollback()
        if second_reservation is not None and not second_reservation.done():
            try:
                await asyncio.wait_for(second_reservation, timeout=5)
            except asyncio.TimeoutError:
                second_reservation.cancel()
        if second_session.in_transaction():
            await second_session.rollback()
        await first_session.close()
        await second_session.close()
        async with session_factory.begin() as session:
            await session.execute(
                delete(BookingORM).where(BookingORM.room_id == room_id)
            )
            await session.execute(delete(RoomsOrm).where(RoomsOrm.id == room_id))
            await session.execute(delete(HotelOrm).where(HotelOrm.id == hotel_id))
            await session.execute(delete(UsersOrm).where(UsersOrm.id == user_id))
