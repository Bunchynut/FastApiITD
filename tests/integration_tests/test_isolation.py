import pytest

from src.Schemas.Schemas import HotelPost
from src.Schemas.facilities import FacilityAdd
from src.Schemas.rooms import RoomsTestMain


@pytest.mark.parametrize("attempt", [1, 2, 3])
async def test_each_test_starts_with_clean_seed_data(db, ac, attempt):
    assert len(await db.hotels.get_all()) == 3
    assert len(await db.rooms.get_all()) == 4
    assert await db.users.get_all() == []
    assert await db.booking.get_all() == []
    assert await db.facilities.get_all() == []
    assert not ac.cookies
    hotel = await db.hotels.add(
        HotelPost(title=f"Isolation {attempt}", location="Temporary")
    )
    await db.rooms.add(
        RoomsTestMain(hotel_id=hotel.id, title="Temporary", price=100, quantity=1)
    )
    await db.facilities.add(FacilityAdd(title="Temporary"))
    await db.commit()
    assert len(await db.hotels.get_all()) == 4
