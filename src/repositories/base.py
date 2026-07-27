from pydantic import BaseModel
from sqlalchemy import select, insert, delete, update

from src.Schemas.Schemas import Hotel


class BaseRepository():
    model = None
    schema: BaseModel = None

    def __init__(self,session):
        self.session = session

    async def get_all(self, *args, **kwargs):
        query = select(self.model)
        result = await self.session.execute(query)
        return [self.schema.model_validate(hotel) for hotel in result.scalars().all()]

    async def get_one_or_none(self, **filter_by):
        query = select(self.model).filter_by(**filter_by)
        result = await self.session.execute(query)
        res = result.scalars().one_or_none()
        if res is None:
            return None
        return res

    async def add(self,data: BaseModel):
        add_hotel_stmt = (insert(self.model).values(**data))
        result = await self.session.execute(add_hotel_stmt)
        return result.scalars().one()

    async def delete(self,**filter_by) -> None:
        delete_hotel_stmt = delete(self.model).filter_by(**filter_by)
        await self.session.execute(delete_hotel_stmt)

    async def put(self,data: BaseModel,exclude_unset: bool = False,**filter_by) -> None:
        put_hotel_stmt = (
            update(self.model).filter_by(**filter_by).values(**data.model_dump(exclude_unset=exclude_unset))
        )
        await self.session.execute(put_hotel_stmt)
