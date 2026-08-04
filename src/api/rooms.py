from fastapi import APIRouter, Query, Body, HTTPException, Path

from src.Schemas.rooms import  RoomsPutSchema, RoomsAdd
from src.api.Dependencied import DBDep

router = APIRouter(prefix='/rooms', tags=['Номера'])


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
async def post_rooms(db: DBDep,Schema:RoomsAdd = Body(openapi_examples={
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
    Hotel = await db.hotels.get_one_or_none(id=Schema.hotel_id)
    if Hotel is None:
        raise HTTPException(status_code=404,detail='Неверный айди отеля')
    await db.rooms.add(Schema.model_dump())
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