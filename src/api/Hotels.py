from fastapi import Query, Path, Body, APIRouter

from src.Schemas.Schemas import HotelPost, HotelPatch
from src.api.Dependencied import paginationDep, DBDep

router = APIRouter(prefix='/hotels', tags=['Отели'])


@router.get('', summary='Получить данные')
async def get_hotels(
            pagination: paginationDep,
            db: DBDep,
            title: str | None = Query(None,description='Название города') ,
            id: int | None  = Query(None,description='Айди'),
            location: str | None  = Query(None,description='Имя')):
    per_page = pagination.per_page or 5
    return await db.hotels.get_all(
            location = location,
            title = title,
            id = id,
            limit = per_page,
            offset = (pagination.page - 1) * per_page
        )



@router.delete('/{hotel_id}', summary='Удалить обьект')
async def delete_hotel(db: DBDep,hotel_id:int = Path(description='Удалить по айди')):
        await db.hotels.delete(id=hotel_id)
        await db.commit()
        return {'status': 'OK'}


@router.post('', summary='Добавaить обьект')
async def create_hotel(db: DBDep,hotel_data:HotelPost = Body(openapi_examples={
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
        await db.hotels.add(hotel_data.model_dump())
        await db.commit()
        return {'status': 'OK','data': hotel_data.model_dump()}


@router.put('/{hotel_id}',description='Полностью поменять обьект',summary='Полностью поменять обьект')
async def put_hotel(db: DBDep,hotel_data:HotelPost,hotel_id:int = Path(description='Поменять')):
        await db.hotels.put(id=hotel_id,data=hotel_data.model_dump())
        await db.commit()
        return {'status': 'OK'}

@router.patch('/{hotel_id}',description='Частично поменять обьект',summary='Частично поменять обьект')
async def patch_hotel(db: DBDep,hotel_data:HotelPatch,
                hotel_id:int = Path(description='Поменять')):
        await db.hotels.put(id=hotel_id,exclude_unset= True, data=hotel_data)
        await db.hotels.commit()
        return {'status': 'OK'}



