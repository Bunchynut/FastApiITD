import json

from fastapi import APIRouter, Depends
from fastapi_cache.decorator import cache


from src.Schemas.facilities import FacilityAdd
from src.api.dependencies import DatabaseDep, require_admin
from src.init import redis_manager

router = APIRouter(prefix='/facilities', tags=['Опции'])


@router.get('/',summary='Получить опции')
@cache(expire=10)
async def get_facilities(db:DatabaseDep):
    return await db.facilities.get_all()




@router.post('/',summary='Добавить опцию', dependencies=[Depends(require_admin)])
async def add_facility(db:DatabaseDep,data:FacilityAdd):
    facility = await db.facilities.add(data)
    await db.commit()
    return {'data':facility}

