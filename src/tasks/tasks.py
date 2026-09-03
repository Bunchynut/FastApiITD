import asyncio

from PIL import Image
import os

from src.DataBase import async_session_maker, async_session_maker_null_pull
from src.tasks.celery_app import celery_app
from src.utils.db_manager import DBManager


@celery_app.task
def resize_image(image_path: str):
    sizes = [1000, 500, 200]
    output_folder = 'src/static/images'

    img = Image.open(image_path)

    base_name = os.path.basename(image_path)
    name, ext = os.path.splitext(base_name)

    for size in sizes:
        img_resized = img.resize((size, int(img.height * (size / img.width))), Image.Resampling.LANCZOS)

        new_file_name = f"{name}_{size}px{ext}"

        output_path = os.path.join(output_folder, new_file_name)

        img_resized.save(output_path)

    print(f"Изображение сохранено в следующих размерах: {sizes} в папке {output_folder}")


async def get_booking_with_today_checkin_helper():
    print('Запускаюсь')
    async with DBManager(session_factory=async_session_maker_null_pull) as db:
        bookings = await db.bookings.get_bookings_with_today_checkin()
        print(f'{bookings}')

@celery_app.task(name='booking_today_checkin')
def send_email_booking_today_checkin():
    asyncio.run(get_booking_with_today_checkin_helper())