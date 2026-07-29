from src.Schemas.users import UserId
from src.model.users import UsersOrm
from src.repositories.base import BaseRepository



class UsersRepository(BaseRepository):
    model = UsersOrm
    schema = UserId