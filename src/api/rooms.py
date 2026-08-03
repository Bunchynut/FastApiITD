from fastapi import APIRouter, Query, Body, HTTPException, Path

from src.DataBase import async_session_maker
from src.Schemas.rooms import RoomsSchema, RoomsPutSchema
from src.repositories.hotels import HotelsRepositories
from src.repositories.rooms import RoomsRepositories

router = APIRouter(prefix='/rooms', tags=['Номера'])


@router.get('',summary='Получить данные номера')
async def get_rooms(id: int | None = Query(None,description='Айди'),
    hotel_id: int | None = Query(None,description='Айди отеля'),
    title: str | None = Query(None,description='Заголовок'),
    description: str | None = Query(None,description='Описание'),
    price: int | None = Query(None,description='Цена'),
    quantity: int | None = Query(None,description='Кол-во')):
    async with async_session_maker() as session:
        return await RoomsRepositories(session).get_all(
            id = id,
            hotel_id = hotel_id,
            title = title,
            description = description,
            price = price,
            quantity = quantity)


@router.post('',summary='Добавить номер')
async def post_rooms(Schema:RoomsSchema = Body(openapi_examples={
    "1": {
        "summary": "1",
        "value": {
            "hotel_id": "1",
            "title": "Номер с одной двухспальной кроватью",
            "description": "Однокомнатный номер с одной двухспальной кроватью, душем и доп. опциями и т.д. ",
            "price": "3000",
            "quantity": "10",
        }
    },
    "2": {
        "summary": "2",
        "value": {
            "hotel_id": "2",
            "title": "Номер с двумя односпальными корватями",
            "description": "Однокомнатный номер с двумя односпальными кроватями и т.д.",
            "price": "2499",
            "quantity": "10",
        }
    }
})
):
    async with async_session_maker() as session:
        Hotel = await HotelsRepositories(session).get_one_or_none(id=Schema.hotel_id)
        if Hotel is None:
            raise HTTPException(status_code=404,detail='Неверный айди отеля')
        await RoomsRepositories(session).add(Schema.model_dump())
        await session.commit()
    return {'status':'OK','data':Schema.model_dump()}


@router.delete('/{id}',summary='Удалить номер')
async def delete_rooms(id:int = Path(description='Айди номера')):
    async with async_session_maker() as session:
        await RoomsRepositories(session).delete(id=id)
        await session.commit()
        return {'status','OK'}


@router.put('/{id}/{hotel_id}',summary='Полностью поменять обьект')
async def put_rooms(Schema:RoomsPutSchema,hotel_id:int | None = Path(description='Введите айди отеля'), id:int | None = Path(description='Введите айди номера')):
    async with async_session_maker() as session:
        await RoomsRepositories(session).put(id=id,hotel_id=hotel_id,data=Schema)
        await session.commit()
    return {'status','OK'}


@router.patch('/{id}/{hotel_id}',summary='Частично поменять обьект')
async def patch_rooms(Schema:RoomsPutSchema,hotel_id:int | None = Path(description='Введите айди отеля'), id:int | None = Path(description='Введите айди номера')):
    async with async_session_maker() as session:
        await RoomsRepositories(session).put(id=id,hotel_id=hotel_id,data=Schema,exclude_unset=True)
        await session.commit()
    return {'status','OK'}