from fastapi import APIRouter, Depends, HTTPException

from src.Schemas.booking import AddBookingRequest, BookingAdd
from src.api.dependencies import CurrentUserIdDep, CurrentUserDep, DatabaseDep, require_admin
from src.repositories.booking import RoomUnavailableError

router = APIRouter(prefix='/booking',tags=['Бронирование'])

@router.post('', summary='Создать бронирование')
async def create_booking(
    db: DatabaseDep,
    data: AddBookingRequest,
    user: CurrentUserDep
):
    room = await db.rooms.get_one_or_none(id=data.room_id)

    if not room:
        raise HTTPException(
            status_code=404,
            detail='Комната не найдена'
        )

    booking_request = BookingAdd(
        room_id=data.room_id,
        date_from=data.date_from,
        date_to=data.date_to,
        user_id=user.id,
        price=room.price
    )

    try:
        created_booking = await db.booking.add_booking(
            booking_request, hotel_id=room.hotel_id
        )
    except RoomUnavailableError as error:
        raise HTTPException(
            status_code=409,
            detail='Комната уже занята на выбранные даты',
        ) from error

    await db.commit()

    return {
        'status': 'OK',
        'data': created_booking
    }


@router.get('', summary='Список бронирований', dependencies=[Depends(require_admin)])
async def get_bookings(db: DatabaseDep):
    bookings = await db.booking.get_all()
    return {'status': bookings}


@router.get('/me', summary='Мои бронирования')
async def get_my_bookings(db: DatabaseDep, user_id: CurrentUserIdDep):
    return await db.booking.get_filtered(user_id=user_id)
