from fastapi import APIRouter, Depends, HTTPException

from src.Schemas.booking import AddBookingRequest, BookingAdd
from src.api.dependencies import DatabaseDep, CurrentUserIdDep, require_admin

router = APIRouter(prefix='/booking',tags=['Бронирование'])

@router.post('', summary='Бронирование')
async def booking(
    db: DatabaseDep,
    data: AddBookingRequest,
    user_id: CurrentUserIdDep
):
    room = await db.rooms.get_one_or_none(id=data.room_id)

    if not room:
        raise HTTPException(
            status_code=404,
            detail='Неверный айди комнаты'
        )

    booking_data = BookingAdd(
        room_id=data.room_id,
        date_from=data.date_from,
        date_to=data.date_to,
        user_id=user_id,
        price=room.price
    )

    add_booking = await db.booking.add_booking(booking_data, hotel_id=room.hotel_id)

    await db.commit()

    return {
        'status': 'OK',
        'data': add_booking
    }


@router.get('',summary='Получить все данные бронирования', dependencies=[Depends(require_admin)])
async def get_all_bookings(db:DatabaseDep):
    get = await db.booking.get_all()
    return {'status':get}


@router.get('/me',summary='Получить данные бронирования по айди')
async def get_my_bookings(db:DatabaseDep,user_id: CurrentUserIdDep):
    return await db.booking.get_filtered(user_id=user_id)
