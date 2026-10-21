from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.model.facilities import FacilitiesORM, FacilitiesORMRoom
from src.model.hotels import HotelOrm
from src.model.rooms import RoomsOrm
from src.repositories.factilities import RoomsFacilitiesRepository


class CompetingInsertSession:
    def __init__(self, session, competing_repository, competing_session, link):
        self.session = session
        self.competing_repository = competing_repository
        self.competing_session = competing_session
        self.link = link
        self.insert_intercepted = False

    async def execute(self, statement, *args, **kwargs):
        if (
            not self.insert_intercepted
            and "insert into rooms_facilities" in str(statement).lower()
        ):
            self.insert_intercepted = True
            await self.competing_repository.set_rooms_facility(*self.link)
            await self.competing_session.commit()
        return await self.session.execute(statement, *args, **kwargs)


async def test_stale_room_facility_insert_ignores_concurrent_duplicate(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    suffix = uuid4().hex
    async with session_factory.begin() as session:
        hotel = HotelOrm(title=f"Race hotel {suffix}", location="Test")
        facility = FacilitiesORM(title=f"Race facility {suffix}")
        session.add_all([hotel, facility])
        await session.flush()
        room = RoomsOrm(
            hotel_id=hotel.id,
            title=f"Race room {suffix}",
            description=None,
            price=0,
            quantity=0,
        )
        session.add(room)
        await session.flush()
        hotel_id, room_id, facility_id = hotel.id, room.id, facility.id

    first_session, second_session = session_factory(), session_factory()
    try:
        competitor = RoomsFacilitiesRepository(second_session)
        first_repository = RoomsFacilitiesRepository(
            CompetingInsertSession(
                first_session, competitor, second_session, (room_id, [facility_id])
            )
        )
        await first_repository.set_rooms_facility(room_id, [facility_id])
        await first_session.commit()

        async with session_factory() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(FacilitiesORMRoom)
                .where(
                    FacilitiesORMRoom.room_id == room_id,
                    FacilitiesORMRoom.facility_id == facility_id,
                )
            )
        assert count == 1
    finally:
        await first_session.rollback()
        await second_session.rollback()
        await first_session.close()
        await second_session.close()
        async with session_factory.begin() as session:
            await session.execute(
                delete(FacilitiesORMRoom).where(
                    FacilitiesORMRoom.room_id == room_id
                )
            )
            await session.execute(delete(RoomsOrm).where(RoomsOrm.id == room_id))
            await session.execute(
                delete(FacilitiesORM).where(FacilitiesORM.id == facility_id)
            )
            await session.execute(delete(HotelOrm).where(HotelOrm.id == hotel_id))
