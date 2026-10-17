import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.Schemas.facilities import FacilityAdd, RoomsFacilityAdd
from src.model.facilities import FacilitiesORMRoom


async def test_facility_repository_crud(db):
    facility = await db.facilities.add(FacilityAdd(title="Wi-Fi"))
    facility_id = facility.id
    await db.commit()
    stored = await db.facilities.get_one_or_none(id=facility_id)
    assert stored.title == "Wi-Fi"
    assert {facility.id for facility in await db.facilities.get_all()} == {facility_id}

    await db.facilities.put(FacilityAdd(title="Fast Wi-Fi"), id=facility_id)
    await db.commit()
    db.session.expire_all()
    assert (await db.facilities.get_one_or_none(id=facility_id)).title == "Fast Wi-Fi"

    await db.facilities.delete(id=facility_id)
    await db.commit()
    assert await db.facilities.get_one_or_none(id=facility_id) is None
    assert await db.facilities.get_all() == []


async def test_facility_repository_bulk_insert(db):
    await db.facilities.add_bulk(
        [FacilityAdd(title="Pool"), FacilityAdd(title="Parking")]
    )
    await db.commit()
    facilities = await db.facilities.get_all()
    assert {facility.title for facility in facilities} == {"Pool", "Parking"}
    assert len({facility.id for facility in facilities}) == 2


async def test_facility_repository_missing_id(db):
    assert await db.facilities.get_one_or_none(id=999999) is None


async def test_room_facilities_bulk_insert(db):
    facility = await db.facilities.add(FacilityAdd(title="Wi-Fi"))
    facility_id = facility.id
    await db.rooms_facilities.add_bulk(
        [
            RoomsFacilityAdd(room_id=1, facility_id=facility_id),
            RoomsFacilityAdd(room_id=2, facility_id=facility_id),
        ]
    )
    await db.commit()
    result = await db.session.execute(
        select(FacilitiesORMRoom.room_id, FacilitiesORMRoom.facility_id)
    )
    assert set(result.all()) == {(1, facility_id), (2, facility_id)}


async def test_room_facilities_replace_deduplicates_and_preserves_other_rooms(db):
    first = await db.facilities.add(FacilityAdd(title="Pool"))
    second = await db.facilities.add(FacilityAdd(title="Spa"))
    third = await db.facilities.add(FacilityAdd(title="Parking"))
    first_id, second_id, third_id = first.id, second.id, third.id
    await db.rooms_facilities.set_rooms_facility(1, [first_id, second_id])
    await db.rooms_facilities.set_rooms_facility(2, [first_id])
    await db.commit()

    await db.rooms_facilities.set_rooms_facility(1, [second_id, third_id, third_id])
    await db.commit()
    result = await db.session.execute(
        select(FacilitiesORMRoom.room_id, FacilitiesORMRoom.facility_id)
    )
    rows = result.all()
    assert len(rows) == 3
    assert set(rows) == {(1, second_id), (1, third_id), (2, first_id)}

    await db.rooms_facilities.set_rooms_facility(1, [second_id, third_id, third_id])
    await db.commit()
    result = await db.session.execute(
        select(FacilitiesORMRoom.room_id, FacilitiesORMRoom.facility_id)
    )
    assert len(result.all()) == 3

    await db.rooms_facilities.set_rooms_facility(1, [])
    await db.commit()
    result = await db.session.execute(
        select(FacilitiesORMRoom.room_id, FacilitiesORMRoom.facility_id)
    )
    assert result.all() == [(2, first_id)]


async def test_deleting_facility_cascades_room_links(db):
    facility = await db.facilities.add(FacilityAdd(title="Spa"))
    facility_id = facility.id
    await db.rooms_facilities.set_rooms_facility(1, [facility_id])
    await db.commit()
    await db.facilities.delete(id=facility_id)
    await db.commit()
    result = await db.session.execute(
        select(FacilitiesORMRoom).filter_by(facility_id=facility_id)
    )
    assert result.scalars().all() == []
    assert await db.rooms.get_one_or_none(id=1) is not None


async def test_deleting_room_cascades_facility_links(db):
    facility = await db.facilities.add(FacilityAdd(title="Pool"))
    facility_id = facility.id
    await db.rooms_facilities.set_rooms_facility(1, [facility_id])
    await db.commit()
    await db.rooms.delete(id=1)
    await db.commit()
    result = await db.session.execute(select(FacilitiesORMRoom).filter_by(room_id=1))
    assert result.scalars().all() == []
    assert await db.facilities.get_one_or_none(id=facility_id) is not None


@pytest.mark.parametrize("invalid_target", ["room", "facility"])
async def test_room_facilities_reject_invalid_foreign_keys(db, invalid_target):
    facility = await db.facilities.add(FacilityAdd(title="Wi-Fi"))
    room_id = 999999 if invalid_target == "room" else 1
    facility_id = facility.id if invalid_target == "room" else 999999
    await db.commit()
    with pytest.raises(IntegrityError):
        await db.rooms_facilities.set_rooms_facility(room_id, [facility_id])
