from pydantic import BaseModel
from sqlalchemy import select, insert, delete, update

from src.repositories.mappers.base import DataMapper


class BaseRepository():
    model = None
    mapper: DataMapper = None

    def __init__(self,session):
        self.session = session


    async def get_filtered(self, *filter, **filter_by):
        query = select(self.model).filter(*filter).filter_by(**filter_by)
        result = await self.session.execute(query)
        models = result.scalars().all()


    async def get_all(self, *args, **kwargs):
        query = select(self.model)
        result = await self.session.execute(query)
        return [self.mapper.map_to_domain_entity(hotel) for hotel in result.scalars().all()]


    async def get_one_or_none(self, **filter_by):
        query = select(self.model).filter_by(**filter_by)
        result = await self.session.execute(query)
        res = result.unique().scalars().one_or_none()
        if res is None:
            return None
        return res


    async def add(self,data: BaseModel):
        add_hotel_stmt = (insert(self.model).values(**data.model_dump()).returning(self.model))
        result = await self.session.execute(add_hotel_stmt)
        return result.scalars().one()

    async def add_bulk(self,data: list[BaseModel]):
        add_hotel_stmt = (insert(self.model).values([item.model_dump() for item in data]).returning(self.model))
        await self.session.execute(add_hotel_stmt)

    async def delete(self,**filter_by) -> None:
        delete_hotel_stmt = delete(self.model).filter_by(**filter_by)
        await self.session.execute(delete_hotel_stmt)

    async def put(self,data: BaseModel,exclude_unset: bool = False,**filter_by) -> None:
        put_hotel_stmt = (
            update(self.model).filter_by(**filter_by).values(**data.model_dump(exclude_unset=exclude_unset,exclude={'facilities_ids'}))
        )
        await self.session.execute(put_hotel_stmt)

    async def put_bulk(self,data: list[BaseModel],exclude_unset: bool = False,**filter_by) -> None:
        put_hotel_stmt = update(self.model).filter_by(**filter_by).values([item.model_dump(exclude_unset=exclude_unset,exclude={'facilities_ids'}) for item in data])
        await self.session.execute(put_hotel_stmt)
















