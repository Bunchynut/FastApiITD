from src.DataBase import async_session_maker, async_session_maker_null_pull
from src.Schemas.Schemas import HotelPost
from src.utils.db_manager import DBManager


async def test_add_hotel(db):
    hotel_data = HotelPost(title='Hotel1', location='New York')
    await db.hotels.add(hotel_data)
    await db.commit()