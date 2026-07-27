from fastapi import Query, Path, Body, APIRouter
from sqlalchemy import insert, select, or_, and_

from src.DataBase import async_session_maker
from src.Schemas.Schemas import HotelPost, HotelPatch
from src.api.Dependencied import  paginationDep
from src.model.hotels import HotelOrm
from src.repositories.hotels import HotelsRepositories

router = APIRouter(prefix='/hotels', tags=['Отели'])


@router.get('', summary='Получить данные')
async def get_hotels(pagination: paginationDep,
                title: str | None = Query(None,description='Название города') ,
               id: int | None  = Query(None,description='Айди'),
               location: str | None  = Query(None,description='Имя')):
    per_page = pagination.per_page or 5
    async with async_session_maker() as session:
        return await HotelsRepositories(session).get_all(
            location = location,
            title = title,
            id = id,
            limit = per_page,
            offset = (pagination.page - 1) * per_page
        )



@router.delete('/{hotel_id}', summary='Удалить обьект')
async def delete_hotel(hotel_id:int = Path(description='Удалить по айди')):
    async with async_session_maker() as session:
        await HotelsRepositories(session).delete(id=hotel_id)
        await session.commit()
    return {'status': 'OK'}


@router.post('', summary='Добавaить обьект')
async def create_hotel(hotel_data:HotelPost = Body(openapi_examples={
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
    async with async_session_maker() as session:
        await HotelsRepositories(session).add(hotel_data.model_dump())
        await session.commit()
    return {'status': 'OK','data': hotel_data.model_dump()}


@router.put('/{hotel_id}',description='Полностью поменять обьект',summary='Полностью поменять обьект')
async def put_hotel(hotel_data:HotelPost,hotel_id:int = Path(description='Поменять')):
    async with async_session_maker() as session:
        await HotelsRepositories(session).put(id=hotel_id,data=hotel_data.model_dump())
        await session.commit()
    return {'status': 'OK'}

@router.patch('/{hotel_id}',description='Частично поменять обьект',summary='Частично поменять обьект')
async def patch_hotel(hotel_data:HotelPatch,
                hotel_id:int = Path(description='Поменять')):
    async with async_session_maker() as session:
        await HotelsRepositories(session).put(id=hotel_id,exclude_unset= True, data=hotel_data)
        await session.commit()
    return {'status': 'OK'}



