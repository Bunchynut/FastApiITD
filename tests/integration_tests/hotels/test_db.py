from src.DataBase import async_session_maker, async_session_maker_null_pull
from src.Schemas.Schemas import HotelPost
from src.utils.db_manager import DBManager


async def test_add_hotel():
    hotel_data = HotelPost(title='Hotel1', location='New York')
    async with DBManager(session_factory=async_session_maker_null_pull) as db:
        await db.hotels.add(hotel_data)
        await db.commit()