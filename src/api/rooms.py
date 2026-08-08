from datetime import date

from fastapi import APIRouter, Query, Body, HTTPException, Path

from src.Schemas.facilities import RoomsFacilityAdd
from src.Schemas.rooms import  RoomsPutSchema, RoomsAdd
from src.api.Dependencied import DBDep

router = APIRouter(prefix='/rooms', tags=['Номера'])


@router.get("/{hotel_id}/rooms",summary='Узнать свободные номера')
async def get_rooms(
        hotel_id: int,
        db: DBDep,
        date_from: date = Query(example="2026-08-01"),
        date_to: date = Query(example="2026-08-10"),
):
    return await db.rooms.get_filtered_by_time(hotel_id=hotel_id, date_from=date_from, date_to=date_to)


@router.get('',summary='Получить данные номера')
async def get_rooms(db: DBDep,id: int | None = Query(None,description='Айди'),
    hotel_id: int | None = Query(None,description='Айди отеля'),
    title: str | None = Query(None,description='Заголовок'),
    description: str | None = Query(None,description='Описание'),
    price: int | None = Query(None,description='Цена'),
    quantity: int | None = Query(None,description='Кол-во')):
    return await db.rooms.get_all(
        id = id,
        hotel_id = hotel_id,
        title = title,
        description = description,
        price = price,
        quantity = quantity)


@router.post('',summary='Добавить номер')
async def post_rooms(db: DBDep,Schema:RoomsAdd = Body()):
    Hotel = await db.hotels.get_one_or_none(id=Schema.hotel_id)
    if Hotel is None:
        raise HTTPException(status_code=404,detail='Неверный айди отеля')

    room = await db.rooms.add(Schema.model_dump(exclude={'facilities_ids'}))
    rooms_facilities_data = [RoomsFacilityAdd(room_id=room.id, facility_id=f_id)for f_id in Schema.facilities_ids]
    await db.rooms_facilities.add_bulk(rooms_facilities_data)
    await db.commit()
    return {'status':'OK','data':Schema.model_dump()}


@router.delete('/{id}',summary='Удалить номер')
async def delete_rooms(db: DBDep,id:int = Path(description='Айди номера')):
        await db.rooms.delete(id=id)
        await db.commit()
        return {'status','OK'}


@router.put('/{id}/{hotel_id}',summary='Полностью поменять обьект')
async def put_rooms(db: DBDep,Schema:RoomsPutSchema,hotel_id:int | None = Path(description='Введите айди отеля'), id:int | None = Path(description='Введите айди номера')):
    await db.rooms.put(id=id,hotel_id=hotel_id,data=Schema)
    await db.commit()
    return {'status','OK'}


@router.patch('/{id}/{hotel_id}',summary='Частично поменять обьект')
async def patch_rooms(db: DBDep,Schema:RoomsPutSchema,hotel_id:int | None = Path(description='Введите айди отеля'), id:int | None = Path(description='Введите айди номера')):
    await db.rooms.put(id=id,hotel_id=hotel_id,data=Schema,exclude_unset=True)
    await db.commit()
    return {'status','OK'}