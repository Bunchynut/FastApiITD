from datetime import date

from fastapi import APIRouter, Query, Body, HTTPException, Path, Depends

from src.Schemas.facilities import RoomsFacilityAdd
from src.Schemas.rooms import RoomsAdd, RoomsCreateData, PutRoomsPutSchema, RoomsPatchSchema
from src.api.dependencies import DatabaseDep, require_admin
from sqlalchemy.exc import IntegrityError
from src.Schemas.types import PostgresId

router = APIRouter(prefix='/rooms', tags=['Номера'])


async def _ensure_facilities_exist(db: DatabaseDep, facilities_ids: list[int]):
    if set(facilities_ids) != await db.facilities.get_existing_ids(facilities_ids):
        raise HTTPException(status_code=404, detail='Facility not found')


@router.get("/{hotel_id}/rooms",summary='Узнать свободные номера')
async def get_rooms(
        hotel_id: PostgresId,
        db: DatabaseDep,
        date_from: date = Query(examples="2026-08-01"),
        date_to: date = Query(examples="2026-08-10"),
):
    if date_to <= date_from:
        raise HTTPException(status_code=422, detail='date_to must be later than date_from')
    return await db.rooms.get_filtered_by_time(hotel_id=hotel_id, date_from=date_from, date_to=date_to)


@router.get('',summary='Получить данные номера')
async def get_rooms(
    db: DatabaseDep,
    id: PostgresId = Query(ge=1, le=2147483647, description='Айди номера'),
    hotel_id: PostgresId | None = Query(None, description='Айди отеля'),
):
    filters = {"id": id}
    if hotel_id is not None:
        filters["hotel_id"] = hotel_id
    return await db.rooms.get_one_or_none_with_option(**filters)

@router.post('',summary='Добавить номер', dependencies=[Depends(require_admin)])
async def post_rooms(db: DatabaseDep, Schema:RoomsAdd = Body()):
    Hotel = await db.hotels.get_one_or_none(id=Schema.hotel_id)
    if Hotel is None:
        raise HTTPException(status_code=404,detail='Неверный айди отеля')

    await _ensure_facilities_exist(db, Schema.facilities_ids)
    room_data = RoomsCreateData.model_validate(Schema.model_dump(exclude={'facilities_ids'}))
    room = await db.rooms.add(room_data)
    if Schema.facilities_ids:
        rooms_facilities_data = [
            RoomsFacilityAdd(room_id=room.id, facility_id=f_id)
            for f_id in dict.fromkeys(Schema.facilities_ids)
        ]
        await db.rooms_facilities.add_bulk(rooms_facilities_data)
    await db.commit()
    return {'status':'OK','data':Schema.model_dump()}


@router.delete('/{id}',summary='Удалить номер', dependencies=[Depends(require_admin)])
async def delete_rooms(
    db: DatabaseDep,
    id: PostgresId = Path(ge=1, le=2147483647, description='Айди номера')
):
        if await db.rooms.get_one_or_none(id=id) is None:
            raise HTTPException(status_code=404, detail='Room not found')
        try:
            await db.rooms.delete(id=id)
            await db.commit()
        except IntegrityError as exc:
            await db.session.rollback()
            sqlstate = getattr(exc.orig, 'sqlstate', None) or getattr(exc.orig, 'pgcode', None)
            if sqlstate == '23503':
                raise HTTPException(status_code=409, detail='Room is still in use') from exc
            raise
        return {'status': 'OK'}


@router.put('/{room_id}/{hotel_id}',summary='Полностью поменять обьект', dependencies=[Depends(require_admin)])
async def put_rooms(
    room_id: PostgresId,
    db: DatabaseDep,
    Schema: PutRoomsPutSchema,
    hotel_id: PostgresId = Path(ge=1, le=2147483647, description='Введите айди отеля'),
):
    if await db.rooms.get_one_or_none(id=room_id, hotel_id=hotel_id) is None:
        raise HTTPException(status_code=404, detail='Room not found')
    await _ensure_facilities_exist(db, Schema.facilities_ids)
    await db.rooms.put(id=room_id, hotel_id=hotel_id, data=Schema)
    await db.rooms_facilities.set_rooms_facility(room_id, facilities_ids=Schema.facilities_ids)
    await db.commit()
    return {'status': 'OK'}


@router.patch('/{room_id}/{hotel_id}',summary='Частично поменять обьект', dependencies=[Depends(require_admin)])
async def patch_rooms(
    room_id: PostgresId,
    db: DatabaseDep,
    Schema: RoomsPatchSchema,
    hotel_id: PostgresId = Path(ge=1, le=2147483647, description='Введите айди отеля'),
):
    if await db.rooms.get_one_or_none(id=room_id, hotel_id=hotel_id) is None:
        raise HTTPException(status_code=404, detail='Room not found')
    room_dict = Schema.model_dump(exclude_unset=True)
    room_data = {k: v for k, v in room_dict.items() if k != 'facilities_ids'}
    if 'facilities_ids' in room_dict:
        await _ensure_facilities_exist(db, room_dict['facilities_ids'])
    if room_data:
        await db.rooms.put(
            id=room_id, hotel_id=hotel_id, data=Schema, exclude_unset=True
        )
    if 'facilities_ids' in room_dict:
        await db.rooms_facilities.set_rooms_facility(room_id, facilities_ids=room_dict['facilities_ids'])
    await db.commit()
    return {'status': 'OK'}
