from datetime import date

from fastapi import Query, Path, Body, APIRouter, HTTPException, Depends
from sqlalchemy.exc import IntegrityError

from src.Schemas.Schemas import HotelPost, HotelPatch
from src.api.dependencies import PaginationDep, DatabaseDep, require_admin
from src.Schemas.types import PostgresId, StoredText
from src.cache_keys import http_request_cache_key_builder


from fastapi_cache.decorator import cache


router = APIRouter(prefix='/hotels', tags=['Отели'])


@router.get('', summary='Получить данные')
@cache(expire=10, key_builder=http_request_cache_key_builder)
async def get_hotels(
            pagination: PaginationDep,
            db: DatabaseDep,
            date_from: date = Query(examples="2026-08-01"),
            date_to: date = Query(examples="2026-08-10"),
            title: StoredText | None = Query(None,description='Название города') ,
            id: PostgresId | None  = Query(None,description='Айди'),
            location: StoredText | None  = Query(None,description='Имя')):

    if date_to <= date_from:
        raise HTTPException(status_code=422, detail='date_to must be later than date_from')
    per_page = pagination.per_page or 5
    return await db.hotels.get_filtered_by_time(
            date_from=date_from,
            date_to=date_to,
            location = location,
            title = title,
            id = id,
            limit = per_page,
            offset = (pagination.page - 1) * per_page
        )



@router.delete('/{hotel_id}', summary='Удалить обьект', dependencies=[Depends(require_admin)])
async def delete_hotel(
    db: DatabaseDep,
    hotel_id: PostgresId = Path(ge=1, le=2147483647, description='Удалить по айди')
):
        if await db.hotels.get_one_or_none(id=hotel_id) is None:
            raise HTTPException(status_code=404, detail='Hotel not found')
        try:
            await db.hotels.delete(id=hotel_id)
            await db.commit()
        except IntegrityError as exc:
            await db.session.rollback()
            sqlstate = getattr(exc.orig, 'sqlstate', None) or getattr(exc.orig, 'pgcode', None)
            if sqlstate == '23503':
                raise HTTPException(status_code=409, detail='Hotel is still in use') from exc
            raise
        return {'status': 'OK'}


@router.post('', summary='Добавaить обьект', dependencies=[Depends(require_admin)])
async def create_hotel(db: DatabaseDep, hotel_data:HotelPost = Body(openapi_examples={
    "1": {
        "summary": "Сочи",
        "value": {
            "title": "Отель Сочи 5 звезд",
            "location": "Улю Моря 1",
        }
    },
    "2": {
        "summary": "Дубай",
        "value": {
            "title": "Отель Дубай",
            "location": "Ул. Моря 1",
        }
    }
})
):
        await db.hotels.add(hotel_data)
        await db.commit()
        return {'status': 'OK','data': hotel_data.model_dump()}


@router.put('/{hotel_id}',description='Полностью поменять обьект',summary='Полностью поменять обьект', dependencies=[Depends(require_admin)])
async def put_hotel(
    db: DatabaseDep,
    hotel_data: HotelPost,
    hotel_id: PostgresId = Path(ge=1, le=2147483647, description='Поменять'),
):
        if await db.hotels.get_one_or_none(id=hotel_id) is None:
            raise HTTPException(status_code=404, detail='Hotel not found')
        await db.hotels.put(id=hotel_id, data=hotel_data)
        await db.commit()
        return {'status': 'OK'}

@router.patch('/{hotel_id}',description='Частично поменять обьект',summary='Частично поменять обьект', dependencies=[Depends(require_admin)])
async def patch_hotel(db: DatabaseDep,hotel_data:HotelPatch,
                hotel_id:PostgresId = Path(ge=1, le=2147483647, description='Поменять')):
        if await db.hotels.get_one_or_none(id=hotel_id) is None:
            raise HTTPException(status_code=404, detail='Hotel not found')
        if hotel_data.model_fields_set:
            await db.hotels.put(id=hotel_id, exclude_unset=True, data=hotel_data)
            await db.commit()
        return {'status': 'OK'}



