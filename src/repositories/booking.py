from src.model.bookings import BookingORM
from src.repositories.base import BaseRepository
from src.Schemas.booking import BookingId

class BookingRepository(BaseRepository):
    model = BookingORM
    schema = BookingId
