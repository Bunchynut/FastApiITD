from src.Schemas.rooms import RoomsId
from src.model.rooms import RoomsOrm
from src.repositories.base import BaseRepository


class RoomsRepositories(BaseRepository):
    model = RoomsOrm
    schema = RoomsId
