from pydantic import EmailStr
from sqlalchemy import select, insert

from src.Schemas.users import UserId, UserId_With_Hashed
from src.model.users import UsersOrm
from src.repositories.base import BaseRepository



class UsersRepository(BaseRepository):
    model = UsersOrm
    schema = UserId



    async def get_user_with_hashed(self, email: EmailStr):
        query = select(self.model).filter_by(email=email)
        result = await self.session.execute(query)
        res = result.scalars().one_or_none()
        if not res:
            return None
        return UserId_With_Hashed.model_validate(res)