import json

from fastapi import APIRouter
from fastapi_cache.decorator import cache


from src.Schemas.facilities import FacilityAdd
from src.api.Dependencied import DBDep
from src.init import redis_manager

router = APIRouter(prefix='/facilities', tags=['Опции'])


@router.get('/',summary='Получить опции')
@cache(expire=10)
async def get_facilities(db:DBDep):
    return await db.facilities.get_all()




@router.post('/',summary='Добавить опцию')
async def add_facility(db:DBDep,data:FacilityAdd):
    await db.facilities.add(data.model_dump())
    await db.commit()
    return {'status':'OK'}

