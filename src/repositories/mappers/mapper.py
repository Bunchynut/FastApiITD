from src.Schemas.Schemas import Hotel
from src.Schemas.booking import BookingId
from src.Schemas.facilities import Facility, RoomsFacility
from src.Schemas.rooms import RoomsId
from src.Schemas.users import UserId
from src.model.bookings import BookingORM
from src.model.facilities import FacilitiesORM, FacilitiesORMRoom
from src.model.hotels import HotelOrm
from src.model.rooms import RoomsOrm
from src.model.users import UsersOrm
from src.repositories.mappers.base import DataMapper


class HotelDataMapper(DataMapper):
    db_model = HotelOrm
    schema = Hotel

class RoomDataMapper(DataMapper):
    db_model = RoomsOrm
    schema = RoomsId

class UserDataMapper(DataMapper):
    db_model = UsersOrm
    schema = UserId

class BookingDataMapper(DataMapper):
    db_model = BookingORM
    schema = BookingId

class FacilityDataMapper(DataMapper):
    db_model = FacilitiesORM
    schema = Facility

class RoomsFacilityDataMapper(DataMapper):
    db_model = FacilitiesORMRoom
    schema = RoomsFacility
