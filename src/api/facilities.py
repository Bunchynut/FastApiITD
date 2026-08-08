from fastapi import APIRouter

from src.Schemas.facilities import FacilityAdd
from src.api.Dependencied import DBDep

router = APIRouter(prefix='/facilities', tags=['Опции'])


@router.get('/',summary='Получить опции')
async def get_facilities(db:DBDep,
                         id:int,
                         title:str):
    return await db.facilities.get_filtered(id=id,title=title)


@router.post('/',summary='Добавить опцию')
async def add_facility(db:DBDep,data:FacilityAdd):
    await db.facilities.add(data.model_dump())
    await db.commit()
    return {'status':'OK'}

